"""Showcase API — serves project results, served-model inference, and the RAG demo.

Nothing here contains training logic; it reads the artifacts projects produce
(reports/metrics.json, reports/figures/*.{json,html}, reports/models/serving/*)
and delegates chat to Project 01's agent. The /rag/chat routes register only when
RAG_CHAT_ENABLED=1 (they are an LLM cost proxy; locally RAG_CHAT_ENABLED=1)
and fail closed with a 503 when the package or the retrieval index is absent
— the standard production image deliberately omits both, see the Dockerfile
header. Served inference: 02/05/07 read persisted serving artifacts (503 with
build instructions when absent); 06 solves VRPTW instances purely from the
request body with the tuned config from its params.yaml.
"""

import hashlib
import json
import os
import re
import threading
import time
import uuid
from collections.abc import AsyncIterator, Callable
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from portfolio_core.demo import DemoManifest, load_demo_index, to_registry_entry
from portfolio_core.logging import get_logger, setup_logging
from portfolio_core.manifest import load_index
from portfolio_core.story import ProjectStory, load_story
from pydantic import BaseModel, ConfigDict, Field
from routing_optimization.schemas import Problem, RoutePlan, TwoOptTuning
from starlette.exceptions import HTTPException as StarletteHTTPException

from showcase_api import __version__, serving
from showcase_api.contact import router as contact_router
from showcase_api.live import _LIVE_GUARD, _run_bounded_with_timeout
from showcase_api.live import LiveGuard as LiveGuard  # Test-facing re-export.
from showcase_api.middleware import (
    BodyLimitMiddleware,
    RateLimitMiddleware,
    RequestIdMiddleware,
    RequestLoggingMiddleware,
)
from showcase_api.spa import WEB_DIST, _index_html
from showcase_api.spa import router as spa_router

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
PROJECTS_ROOT = REPO_ROOT / "projects"
_DOCS_ASSETS = Path(__file__).with_name("static")

_PID_RE = r"^\d{2}-[a-z0-9-]+$"

setup_logging("INFO")
app = FastAPI(title="amm-ds portfolio showcase", version=__version__, docs_url=None)


@app.get("/docs", include_in_schema=False)
def swagger_ui() -> HTMLResponse:
    """Swagger UI with same-origin assets; no runtime CDN availability required."""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{app.title} - Swagger UI",
        swagger_js_url="/docs-assets/swagger-ui-bundle.js",
        swagger_css_url="/docs-assets/swagger-ui.css",
        swagger_favicon_url="/favicon.svg",
    )


@app.get("/docs-assets/{asset}", include_in_schema=False)
def swagger_ui_asset(asset: str) -> FileResponse:
    if asset not in {"swagger-ui-bundle.js", "swagger-ui.css"}:
        raise HTTPException(status_code=404, detail="unknown documentation asset")
    return FileResponse(
        _DOCS_ASSETS / asset,
        headers={"Cache-Control": "public, max-age=3600, stale-while-revalidate=86400"},
    )


class FiniteInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


def _request_id(request: Request) -> str:
    """The id RequestIdMiddleware stashed on the request state (fresh one when
    the request never passed through it, e.g. a hand-built Request in tests)."""
    rid = getattr(request.state, "request_id", None)
    return rid if isinstance(rid, str) and rid else uuid.uuid4().hex[:12]


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Every HTTP error (404/409/413/422/429/503/...) gets the same shape:
    ``{"error": <detail>, "request_id": <id>}`` — never a stack trace. Client
    errors log a WARNING with the request id; 5xx errors log an ERROR."""
    rid = _request_id(request)
    body: dict[str, Any] = {"error": str(exc.detail), "request_id": rid}
    hint = getattr(exc, "hint", None)
    if hint:
        body["hint"] = hint
    if exc.status_code >= 500:
        logger.error(
            "%s %s -> %d rid=%s: %s",
            request.method,
            request.url.path,
            exc.status_code,
            rid,
            exc.detail,
        )
    else:
        logger.warning(
            "%s %s -> %d rid=%s: %s",
            request.method,
            request.url.path,
            exc.status_code,
            rid,
            exc.detail,
        )
    return JSONResponse(body, status_code=exc.status_code, headers=dict(exc.headers or {}))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """422s keep the field errors under ``details`` but share the error/request_id
    envelope; pydantic messages only, no internals."""
    rid = _request_id(request)
    errors = [
        {key: value for key, value in error.items() if key != "input"} for error in exc.errors()
    ]
    details = jsonable_encoder(errors, custom_encoder={ValueError: str})
    summary = [(error.get("loc"), error.get("type")) for error in errors]
    logger.warning("%s %s -> 422 rid=%s: %s", request.method, request.url.path, rid, summary)
    return JSONResponse(
        {"error": "request validation failed", "request_id": rid, "details": details},
        status_code=422,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort 500: the traceback goes to the log (with the request id),
    never to the client."""
    rid = _request_id(request)
    logger.exception(
        "%s %s -> 500 rid=%s: unhandled %s",
        request.method,
        request.url.path,
        rid,
        type(exc).__name__,
    )
    return JSONResponse({"error": "internal server error", "request_id": rid}, status_code=500)


# Production floor (see showcase_api.middleware docstrings): request id → body
# cap → rate limit → request log. Last added runs outermost, so the log line
# sees the final status (including 413/429) and latency of the whole chain.
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIdMiddleware)


def _project_dir(pid: str) -> Path:
    # Validate the id shape (manifest.ProjectInfo.pattern) so path segments can
    # never shift resolution outside projects/ (e.g. pid="..").
    if not re.match(_PID_RE, pid):
        raise HTTPException(status_code=404, detail=f"unknown project: {pid}")
    d = PROJECTS_ROOT / pid
    if not d.is_dir():
        raise HTTPException(status_code=404, detail=f"unknown project: {pid}")
    return d


@app.get("/health")
def health() -> JSONResponse:
    """Cheap liveness response; ``ready`` is retained for existing clients.

    ``ready`` is True when every demo payload file and every served-model
    bundle the live endpoints need is present on disk. ``sha`` identifies the
    build (``BUILD_SHA`` env, ``dev`` locally). Never cached.
    """
    return JSONResponse(
        {
            "status": "ok",
            "ready": _readiness(),
            "sha": os.environ.get("BUILD_SHA", "dev"),
            "version": __version__,
        },
        headers={"Cache-Control": "no-store"},
    )


@app.get("/ready")
def readiness() -> JSONResponse:
    """Readiness probe: unlike liveness, unready artifacts produce a 503."""
    ready = _readiness()
    return JSONResponse(
        {"status": "ok" if ready else "unavailable", "ready": ready},
        status_code=200 if ready else 503,
        headers={"Cache-Control": "no-store"},
    )


# --- Contact phone gate (router in showcase_api.contact) ----------------------
# The direct phone line never ships in the frontend bundle; the page reveals
# it only after this one deliberate step. CONTACT_PHONE is set per deployment.
app.include_router(contact_router)


def _serving_ready(serving_dir: Path, extra_json: tuple[str, ...] = ()) -> bool:
    """A serving bundle is ready when its required artifact files exist."""
    names = ("model.joblib", "meta.json", *extra_json)
    return all((serving_dir / name).is_file() for name in names)


def _readiness() -> bool:
    """Demo payload files + serving bundles the live POST endpoints need."""
    for m in _demo_manifests(PROJECTS_ROOT):
        if m.payload is not None and not (PROJECTS_ROOT / m.project / m.payload.path).is_file():
            return False
    try:
        mobility_ready = all(
            _serving_ready(_service_dir(service), ("zones.json",))
            for service in ("yellow", "green")
        )
    except (HTTPException, OSError, ValueError):
        return False
    return mobility_ready and all(
        _serving_ready(d) for d in (_DEMAND_SERVING_DIR, _CHURN_SERVING_DIR)
    )


# --- Startup-computed indexes (served with ETag) ------------------------------
# The /projects, /projects/headlines and /demos payloads are read from disk once
# per projects root and served from memory with an ETag; If-None-Match gets a 304. The
# cache key is the projects-root *path*, so tests that monkeypatch
# PROJECTS_ROOT to a tmp dir still see fresh data.


def _content_etag(content: bytes) -> str:
    """Short quoted ETag for a payload: first 16 hex chars of its sha256."""
    return '"' + hashlib.sha256(content).hexdigest()[:16] + '"'


def _cached_payload(root: Path, kind: str, compute: Callable[[], Any]) -> tuple[str, str]:
    """(etag, body) for a JSON payload, computed once per (root, kind).

    ``kind`` discriminates payloads that share a root path — /projects and
    /demos both key on PROJECTS_ROOT and would otherwise collide (whichever
    endpoint is hit first would serve its payload for both).
    """
    key = (Path(root), kind)
    if key not in _PAYLOAD_CACHE:
        # compact separators — FastAPI's serializer emits no spaces, and the
        # docker smoke (plus any byte-comparing consumers) greps the compact
        # form ('"id":"01-rag-agent"'); json.dumps' default would insert a
        # space after every ':' and break them.
        body = json.dumps(compute(), sort_keys=True, separators=(",", ":"))
        etag = _content_etag(body.encode())
        _PAYLOAD_CACHE[key] = (etag, body)
    return _PAYLOAD_CACHE[key]


_PAYLOAD_CACHE: dict[tuple[Path, str], tuple[str, str]] = {}
_DEMO_MANIFEST_CACHE: dict[Path, list[DemoManifest]] = {}


def _demo_manifests(root: Path) -> list[DemoManifest]:
    """Demo manifests for a projects root, loaded once per root path."""
    key = Path(root)
    if key not in _DEMO_MANIFEST_CACHE:
        _DEMO_MANIFEST_CACHE[key] = load_demo_index(key)
    return _DEMO_MANIFEST_CACHE[key]


def _etag_response(request: Request, etag: str, body: str) -> Response:
    """200 with ETag, or 304 when If-None-Match matches."""
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(
        content=body,
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": "no-cache"},
    )


@app.get("/projects")
def projects(request: Request) -> Response:
    """Project index JSON — unless a browser navigates here directly (refresh /
    deep link), in which case serve the SPA and let the client-side router
    render the projects page. API clients (curl, fetch with an explicit JSON
    accept) get the payload, computed once at startup and served with ETag."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return (
            HTMLResponse(_index_html(), headers={"Cache-Control": "no-cache"})
            if WEB_DIST.exists()
            else JSONResponse({"error": "web build not found"}, status_code=503)
        )
    etag, body = _cached_payload(
        PROJECTS_ROOT, "projects", lambda: [m.model_dump() for m in load_index(PROJECTS_ROOT)]
    )
    return _etag_response(request, etag, body)


def _metrics_file(d: Path) -> Path | None:
    """Canonical metrics path, including 02's full-panel and UCI fallbacks."""
    return next(
        (
            f
            for f in (
                d / "reports_m5_full" / "metrics.json",
                d / "reports_uci" / "metrics.json",
                d / "reports" / "metrics.json",
            )
            if f.exists()
        ),
        None,
    )


def _first_numeric_metric(run: Any) -> dict[str, str | float | int] | None:
    if not isinstance(run, dict):
        return None
    for metric, value in run.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return {"metric": metric, "value": value}
    return None


def _headline_metric(data: Any) -> dict[str, str | float | int] | None:
    """Mirror the web's pickHeadlineMetric: champion, then non-baselines."""
    if not isinstance(data, dict):
        return None
    meta = data.get("_meta")
    champion = meta.get("champion") if isinstance(meta, dict) else None
    if isinstance(champion, str):
        headline = _first_numeric_metric(data.get(champion))
        if headline is not None:
            return headline
    runs = [run for run in data if not run.startswith("_")]
    ordered = [
        *[
            run
            for run in runs
            if not re.search(r"naive|random|lag|majority|persistence", run, re.IGNORECASE)
        ],
        *[
            run
            for run in runs
            if re.search(r"naive|random|lag|majority|persistence", run, re.IGNORECASE)
        ],
    ]
    return next(
        (headline for run in ordered if (headline := _first_numeric_metric(data[run])) is not None),
        None,
    )


def _project_headlines() -> dict[str, dict[str, str | float | int]]:
    """Compact per-project card headlines, omitting unavailable metrics."""
    headlines: dict[str, dict[str, str | float | int]] = {}
    for manifest in load_index(PROJECTS_ROOT):
        f = _metrics_file(PROJECTS_ROOT / manifest.id)
        if f is None:
            continue
        try:
            headline = _headline_metric(json.loads(f.read_text()))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if headline is not None:
            headlines[manifest.id] = headline
    return headlines


@app.get("/projects/headlines")
def project_headlines(request: Request) -> Response:
    """Compact headline-metric index for project cards, cached with an ETag."""
    etag, body = _cached_payload(PROJECTS_ROOT, "headlines", _project_headlines)
    return _etag_response(request, etag, body)


@app.get("/projects/{pid}/metrics")
def metrics(pid: str) -> dict[str, Any]:
    # 02-demand-forecasting's canonical numbers are the full-panel M5 run
    # (reports_m5_full/); the sparse UCI track (reports_uci/) is the live
    # fallback behind it, the subset (reports_m5/) stays on disk as a CI
    # anchor reachable via track-prefixed figure names, not /metrics.
    # Everywhere else reports/ is it.
    d = _project_dir(pid)
    f = _metrics_file(d)
    if f is None:
        raise HTTPException(status_code=404, detail=f"no metrics yet for {pid} — run its pipeline")
    data: dict[str, Any] = json.loads(f.read_text())
    return data


@app.get("/projects/{pid}/story")
def story(pid: str) -> ProjectStory:
    """The project's case study (common 8-section showcase framework)."""
    s = load_story(_project_dir(pid))
    if s is None:
        raise HTTPException(status_code=404, detail=f"no story.yaml yet for {pid}")
    return s


def _figure_file(pid: str, name: str, ext: str) -> Path | None:
    """Resolve a figure payload to an existing file, or None.

    A ``track:`` prefix selects a sibling track directory — 02-demand-
    forecasting names figures per track (e.g. ``m5:wape_bars`` →
    ``reports_m5/figures/wape_bars.ext``); its full-panel M5 figures live in
    ``reports_m5_full/figures/`` and shadow the subset track for both prefixed
    and prefix-free names (``m5_full_*`` ids resolve there directly). Every
    other project keeps the canonical ``reports/figures/`` location.
    """
    track, sep, bare = name.partition(":")
    stem = bare if sep else name
    d = _project_dir(pid)
    candidates: list[Path] = []
    if d.name == "02-demand-forecasting":
        # The full-panel M5 track is 02's canonical headline: check its
        # figures first so prefix-free names (and any m5: name shared across
        # tracks) serve the final results.
        candidates.append(d / "reports_m5_full" / "figures" / f"{stem}.{ext}")
    candidates.append(
        d / f"reports_{track}" / "figures" / f"{stem}.{ext}"
        if sep
        else d / "reports" / "figures" / f"{stem}.{ext}"
    )
    return next((f for f in candidates if f.exists()), None)


@app.get("/projects/{pid}/figures")
def figures(pid: str) -> list[str]:
    figs = sorted((_project_dir(pid) / "reports" / "figures").glob("*.html"))
    return [f.stem for f in figs]


@app.get("/projects/{pid}/figures/{name}.json")
def figure_json(pid: str, name: str, request: Request) -> Any:
    """Plotly JSON payload (same content the React app could render natively).

    Cached 1 h by clients/CDN (stale-while-revalidate 24 h) behind an ETag."""
    f = _figure_file(pid, name, "json")
    if f is None:
        raise HTTPException(status_code=404, detail=f"no figure JSON {name!r} for {pid}")
    return _cached_file_response(request, f, media_type="application/json")


@app.get("/projects/{pid}/figures/{name}")
def figure(pid: str, name: str, request: Request) -> Response:
    """Interactive figure HTML, cached 1 h (stale-while-revalidate 24 h) + ETag.

    HTML is a regenerable artifact and some projects commit only its Plotly
    JSON source. Render that source on demand so fresh clones and production
    images expose the same standalone figures as a pipeline-run workspace.
    """
    f = _figure_file(pid, name, "html")
    if f is not None:
        return _cached_file_response(request, f, media_type="text/html")
    source = _figure_file(pid, name, "json")
    if source is None:
        raise HTTPException(status_code=404, detail=f"no figure {name!r} for {pid}")
    content = _render_figure_html(str(source), source.stat().st_mtime_ns)
    return _cached_content_response(request, content, media_type="text/html")


@lru_cache(maxsize=256)
def _render_figure_html(path: str, mtime_ns: int) -> bytes:
    """Render once per artifact version; Plotly otherwise generates random IDs."""
    del mtime_ns  # Cache key only: the path supplies the current contents.
    from plotly import io as pio

    html: str = pio.to_html(
        pio.from_json(Path(path).read_text()), include_plotlyjs="cdn", full_html=True
    )
    return html.encode()


def _cached_file_response(request: Request, path: Path, media_type: str) -> Response:
    """200 with CDN cache headers + content ETag, or 304 on If-None-Match."""
    return _cached_content_response(request, path.read_bytes(), media_type)


def _cached_content_response(request: Request, content: bytes, media_type: str) -> Response:
    etag = _content_etag(content)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
            "ETag": etag,
        },
    )


# --- Interactive demos (manifest-driven platform) -----------------------------
# Demos are declared by each project's demo.yaml (see portfolio_core.demo) and
# served here generically: the registry index, the manifest, and the compact
# precomputed payload (built by the project's pipeline, validated against the
# manifest's required_keys / schema_version). Live POST endpoints live under
# /projects/<pid>/; the UI lives in showcase-web at /demos/<id>.


def _demo_or_404(demo_id: str) -> DemoManifest:
    for m in _demo_manifests(PROJECTS_ROOT):
        if m.id == demo_id:
            return m
    raise HTTPException(status_code=404, detail=f"unknown demo: {demo_id}")


@app.get("/demos")
def demos_index(request: Request) -> Response:
    """Registry entries for the frontend demos index (sorted by group, id),
    computed once at startup and served with ETag."""
    etag, body = _cached_payload(
        PROJECTS_ROOT,
        "demos",
        lambda: [to_registry_entry(m) for m in _demo_manifests(PROJECTS_ROOT)],
    )
    return _etag_response(request, etag, body)


@app.get("/demos/{demo_id}/manifest")
def demo_manifest(demo_id: str) -> dict[str, Any]:
    """The demo's manifest as JSON (scenarios, live endpoints, payload ref)."""
    return _demo_or_404(demo_id).model_dump()


@app.get("/demos/{demo_id}/payload")
def demo_payload(demo_id: str, request: Request) -> Response:
    """The demo's committed payload JSON, cached 1 h by clients/CDN
    (stale-while-revalidate 24 h) behind an ETag.

    404 when the demo is unknown or its payload file hasn't been built yet;
    409 when the payload violates the manifest contract (unsafe path, non-object
    JSON, missing required keys, or a schema_version mismatch).
    """
    m = _demo_or_404(demo_id)
    if m.payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"demo {demo_id} declares no payload yet — the manifest is a placeholder",
        )
    project_dir = (PROJECTS_ROOT / m.project).resolve()
    f = (project_dir / m.payload.path).resolve()
    if f != project_dir and project_dir not in f.parents:
        raise HTTPException(
            status_code=409, detail=f"payload path for {demo_id} escapes the project dir"
        )
    if not f.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"demo payload not built for {m.project} — run its demo-payload "
            f"stage to write {m.payload.path}",
        )
    try:
        data: Any = json.loads(f.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=409, detail=f"payload for {demo_id} is not valid JSON"
        ) from None
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=409, detail=f"payload for {demo_id} must be a top-level JSON object"
        )
    missing = [k for k in m.payload.required_keys if k not in data]
    if missing:
        raise HTTPException(
            status_code=409,
            detail=f"payload for {demo_id} is missing required keys: {', '.join(missing)}",
        )
    payload_sv = data.get("schema_version")
    if payload_sv is not None and payload_sv != m.payload.schema_version:
        raise HTTPException(
            status_code=409,
            detail=f"payload schema_version {payload_sv} does not match manifest "
            f"schema_version {m.payload.schema_version}",
        )
    etag = _content_etag(f.read_bytes())
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(
        data,
        headers={
            "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
            "ETag": etag,
        },
    )


def _report_file(pid: str) -> Path:
    """Resolve the canonical report without reading its HTML body."""
    d = _project_dir(pid)
    for candidate in (
        d / "reports_m5_full" / "report.html",
        d / "reports_m5" / "report.html",
        d / "reports_uci" / "report.html",
        d / "reports" / "report.html",
    ):
        if candidate.exists():
            return candidate
    raise HTTPException(status_code=404, detail=f"no report yet for {pid} — run its pipeline")


def _report_document(pid: str) -> str:
    """Full-width report plus an escaped, collapsed view of its original HTML."""
    source = _report_file(pid).read_text()
    style = (
        "<style>body{max-width:none;margin:0;padding:1.25rem 1.5rem;}"
        ".report-source{margin-top:1rem;padding:.85rem 1.1rem;background:#1e293b;"
        "border:1px solid #334155;border-radius:10px}.report-source summary{cursor:pointer;"
        "color:#2dd4bf;font-family:monospace}.report-source pre{max-height:32rem;overflow:auto;"
        "white-space:pre-wrap;overflow-wrap:anywhere;font-size:.8rem}</style>"
    )
    details = (
        '<details class="report-source"><summary>HTML source</summary><pre>'
        f"{escape(source)}</pre></details>"
    )
    document = (
        source.replace("</head>", f"{style}</head>") if "</head>" in source else style + source
    )
    return (
        document.replace("</body>", f"{details}</body>")
        if "</body>" in document
        else document + details
    )


# Register HEAD before GET so Starlette's implicit GET/HEAD pairing cannot make
# availability probes read the full report body.
@app.head("/projects/{pid}/report")
def report_availability(pid: str) -> Response:
    """Bodyless report availability probe; preserves GET's 404 behavior."""
    _report_file(pid)
    return Response(status_code=200)


@app.get("/projects/{pid}/report", response_class=HTMLResponse)
def report(pid: str) -> str:
    """The project's full-width evaluation report and its original HTML source.

    Track-aware resolution, most-recent headline first: 02-demand-forecasting
    ships the full-panel M5 headline in ``reports_m5_full/`` (canonical), the
    subset-era M5 track in ``reports_m5/``, the UCI sparse track in
    ``reports_uci/``, and the synthetic CI track in ``reports/``. Everywhere
    else ``reports/report.html`` is it.
    """
    return _report_document(pid)


# Shared cap for both forecast endpoints; abandoned timed-out workers still count.
_FORECAST_SEMAPHORE = threading.BoundedSemaphore(2)
_FORECAST_BUSY_DETAIL = "forecast capacity busy (2 concurrent forecasts max) — retry shortly"


# --- Served forecasts (Project 07) -----------------------------------------
# Loads the compact serving artifact built by `mobility.cli build-serving-artifact`;
# see projects/07-open-data-mobility/SERVING.md for the contract. Wave 15 added
# per-service bundles: services.json registers each service's bundle dir (the
# loader is directory-parameterized, so green/ loads as-is) and the request's
# `service` field selects one. Yellow stays the default and its path is
# untouched; the green bundle is cached per directory like the root one.

_MOBILITY_ID = "07-open-data-mobility"
_SERVING_DIR = _project_dir(_MOBILITY_ID) / "reports" / "models" / "serving"


class ForecastRequest(FiniteInput):
    zone_id: int = Field(ge=1)
    features: dict[str, float] = Field(min_length=1, max_length=64)
    # Per-service bundle selection: "yellow" (default, the root bundle) or
    # "green" (serving/green/, wave 15). Anything else is a 422.
    service: Literal["yellow", "green"] = "yellow"


class ForecastResponse(BaseModel):
    zone_id: int
    borough: str
    zone: str
    prediction: float
    p90: float
    # The selected service, echoed back; additive for pre-wave-15 clients.
    service: Literal["yellow", "green"]


def _service_dir(service: str) -> Path:
    """Resolve a service name to its bundle dir under ``_SERVING_DIR``.

    ``services.json`` (written by build-serving-artifact) is the registry; its
    ``dir`` values must stay inside the serving bundle so a corrupted registry
    can never shift resolution outside it. When the registry is absent (a
    pre-wave-15 yellow-only bundle) the legacy layout applies: yellow = the
    root bundle, green = green/.
    """
    registry_file = _SERVING_DIR / "services.json"
    if registry_file.is_file():
        registry = json.loads(registry_file.read_text())
        services = registry.get("services") if isinstance(registry, dict) else None
        entry = services.get(service) if isinstance(services, dict) else None
        if not isinstance(entry, dict):
            raise HTTPException(status_code=422, detail=f"unknown service {service!r}")
        resolved = (_SERVING_DIR / str(entry.get("dir") or ".")).resolve()
        root = _SERVING_DIR.resolve()
        if resolved != root and root not in resolved.parents:
            raise HTTPException(
                status_code=422, detail=f"service {service!r} dir escapes the serving bundle"
            )
        return resolved
    return _SERVING_DIR / "green" if service == "green" else _SERVING_DIR


def _service_artifacts(service: str) -> tuple[Any, dict[str, Any], list[dict[str, Any]]] | None:
    """The cached (model, meta, zones) triple for a service's bundle dir.

    ``None`` when that bundle is absent — the caller raises the 503 with build
    instructions, same as the pre-wave-15 behavior for the root bundle.
    """
    artifacts = serving.cached_artifacts(_service_dir(service), extra_json=("zones.json",))
    if artifacts is None:
        return None
    # Cross-check against the bundle meta: a meta that declares a service must
    # match the requested one (green/meta.json carries service: "green"; the
    # yellow root meta declares none, which means yellow).
    declared = artifacts["meta"].get("service")
    if declared is not None and declared != service:
        raise HTTPException(
            status_code=422, detail=f"bundle declares service {declared!r}, not {service!r}"
        )
    return artifacts["model"], artifacts["meta"], artifacts["zones"]


@app.post(f"/projects/{_MOBILITY_ID}/forecast", response_model=ForecastResponse)
def forecast_mobility(request: ForecastRequest) -> ForecastResponse:
    """Zone-hour demand forecast from the persisted GBM pair (+p90 band).

    ``service`` selects the per-service bundle: "yellow" (default, unchanged
    behavior) or "green" (retrained green-taxi bundle, same contract).
    """
    _LIVE_GUARD.gate()
    artifacts = _service_artifacts(request.service)
    if artifacts is None:
        raise HTTPException(
            status_code=503,
            detail="serving artifacts not built — run `uv run python -m mobility.cli "
            "build-serving-artifact` in projects/07-open-data-mobility first",
        )

    def _predict() -> ForecastResponse:
        bundle, meta, zones = artifacts
        zone_row = next((z for z in zones if z.get("location_id") == request.zone_id), None)
        if zone_row is None:
            raise HTTPException(status_code=422, detail=f"unknown zone_id {request.zone_id}")
        feature_names: list[str] = list(
            meta.get("feature_names") or bundle.get("feature_names") or []
        )
        missing = [f for f in feature_names if f not in request.features]
        if missing:
            raise HTTPException(status_code=422, detail=f"missing features: {', '.join(missing)}")
        import numpy as np

        row = np.array([[float(request.features[f]) for f in feature_names]])
        pred = float(bundle["gbm"].predict(row)[0])
        p90 = float(bundle["p90"].predict(row)[0])
        tt = bundle.get("target_transform")
        if tt == "log1p":
            pred = float(np.expm1(pred))
            p90 = float(np.expm1(p90))
        return ForecastResponse(
            zone_id=request.zone_id,
            borough=str(zone_row.get("borough", "?")),
            zone=str(zone_row.get("zone", "?")),
            prediction=round(max(0.0, pred), 3),
            p90=round(max(0.0, p90), 3),
            service=request.service,
        )

    return _run_bounded_with_timeout(_predict, _FORECAST_SEMAPHORE, _FORECAST_BUSY_DETAIL)


# --- Served forecasts (Project 02) ------------------------------------------
# Contract: projects/02-demand-forecasting/reports/models/serving/ holds
# model.joblib ({"model": sklearn Pipeline taking a raw dict with a string
# series_id + numeric features, "feature_names", "target_transform"}) and
# meta.json ({"model_name", "series": [...known series ids...], "example_row"}).

_DEMAND_ID = "02-demand-forecasting"
_DEMAND_SERVING_DIR = _project_dir(_DEMAND_ID) / "reports" / "models" / "serving"


class DemandForecastRequest(FiniteInput):
    series_id: str = Field(min_length=1, max_length=128)
    features: dict[str, float] = Field(min_length=1, max_length=256)


class DemandForecastResponse(BaseModel):
    forecast: float
    model: str


@app.post(f"/projects/{_DEMAND_ID}/forecast", response_model=DemandForecastResponse)
def forecast_demand(request: DemandForecastRequest) -> DemandForecastResponse:
    """Per-series demand forecast from the persisted tuned pipeline."""
    _LIVE_GUARD.gate()
    artifacts = serving.cached_artifacts(_DEMAND_SERVING_DIR)
    if artifacts is None:
        raise HTTPException(
            status_code=503,
            detail="serving artifacts not built — run the serving stage in "
            "projects/02-demand-forecasting first (writes reports/models/serving/)",
        )

    def _predict() -> DemandForecastResponse:
        bundle: dict[str, Any] = artifacts["model"]
        meta: dict[str, Any] = artifacts["meta"]
        model = bundle["model"]
        feature_names: list[str] = list(
            bundle.get("feature_names") or meta.get("feature_names") or []
        )
        missing = [f for f in feature_names if f != "series_id" and f not in request.features]
        if missing:
            raise HTTPException(status_code=422, detail=f"missing features: {', '.join(missing)}")
        # Known-series list: meta["series"] when present; derived from the example
        # row's series_id otherwise (the serving meta may not enumerate series);
        # when neither exists, any series_id is accepted.
        known: Any = meta.get("series") or meta.get("series_ids") or meta.get("known_series")
        if known is None:
            example = meta.get("example_row")
            if isinstance(example, dict) and isinstance(example.get("series_id"), str):
                known = [example["series_id"]]
        if known is not None and request.series_id not in known:
            raise HTTPException(status_code=422, detail=f"unknown series_id {request.series_id!r}")
        # The champion pipeline scores an object row: numeric features in
        # feature_names order (series_id excluded), then the series_id string —
        # mirrors demand_forecasting's own serving test ("exactly like the API").
        import numpy as np

        row = np.array(
            [
                [float(request.features[f]) for f in feature_names if f != "series_id"]
                + [request.series_id]
            ],
            dtype=object,
        )
        pred = float(model.predict(row)[0])
        if bundle.get("target_transform") == "log1p":
            pred = float(np.expm1(pred))
        model_name = _model_label(meta, model)
        return DemandForecastResponse(forecast=round(max(0.0, pred), 4), model=model_name)

    return _run_bounded_with_timeout(_predict, _FORECAST_SEMAPHORE, _FORECAST_BUSY_DETAIL)


def _model_label(meta: dict[str, Any], model: Any) -> str:
    """Human model label: meta model_name, else train_runs/model_selection, else class."""
    name = meta.get("model_name")
    if not name:
        runs = meta.get("train_runs")
        if isinstance(runs, list) and runs:
            name = runs[0]
    if not name:
        selection = meta.get("model_selection")
        if isinstance(selection, dict):
            name = selection.get("champion") or selection.get("family")
    return str(name or type(model).__name__)


# --- Served churn scoring (Project 05) --------------------------------------
# Contract: projects/05-ml-pipeline-churn/reports/models/serving/ holds
# model.joblib ({"model": sklearn estimator (DataFrame row -> proba),
# "feature_names", "decision": {"threshold", "fp_cost", "fn_cost"}}) and
# meta.json ({"model_name"?, "example_row"}). feature_names may include
# string categoricals (e.g. contract, internet_service).

_CHURN_ID = "05-ml-pipeline-churn"
_CHURN_SERVING_DIR = _project_dir(_CHURN_ID) / "reports" / "models" / "serving"

# Concurrency bound for the scoring endpoint, same pattern as the solve and
# forecast caps: sync endpoint → threadpool workers, so a threading
# semaphore. Churn predict is milliseconds (one DataFrame row through a small
# pipeline), but an unbounded burst would still pile up scoring threads; a
# 4-slot bound keeps fast clients served while slow outliers wait for the
# next attempt instead of stacking CPU work (audit pass 3, finding 3).
_CHURN_SEMAPHORE = threading.BoundedSemaphore(4)
_CHURN_BUSY_DETAIL = "scoring capacity busy (4 concurrent scores max) — retry shortly"


class ChurnScoreRequest(FiniteInput):
    # String values are allowed: feature_names include categoricals such as
    # contract / internet_service.
    features: dict[str, float | str] = Field(min_length=1, max_length=256)


class ChurnDecision(BaseModel):
    alarm: bool
    threshold: float
    expected_cost_note: str


class ChurnScoreResponse(BaseModel):
    churn_probability: float
    decision: ChurnDecision


@app.post(f"/projects/{_CHURN_ID}/score", response_model=ChurnScoreResponse)
def score_churn(request: ChurnScoreRequest) -> ChurnScoreResponse:
    """Churn probability + cost-threshold alarm from the persisted pipeline.

    Guarded like the forecast endpoints: 4 concurrent scores max (fast 503
    beyond that) and the shared 10 s wall-clock cap.
    """
    _LIVE_GUARD.gate()
    artifacts = serving.cached_artifacts(_CHURN_SERVING_DIR)
    if artifacts is None:
        raise HTTPException(
            status_code=503,
            detail="serving artifacts not built — run the serving stage in "
            "projects/05-ml-pipeline-churn first (writes reports/models/serving/)",
        )
    bundle: dict[str, Any] = artifacts["model"]
    meta: dict[str, Any] = artifacts["meta"]
    model = bundle["model"]
    feature_names: list[str] = list(bundle.get("feature_names") or meta.get("feature_names") or [])
    missing = [f for f in feature_names if f not in request.features]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing features: {', '.join(missing)}")

    def _predict() -> ChurnScoreResponse:
        row = {f: request.features[f] for f in feature_names}
        import pandas as pd  # typed package; root override covers missing stubs

        proba = float(model.predict_proba(pd.DataFrame([row]))[0, 1])
        decision_cfg: dict[str, Any] = dict(bundle.get("decision") or {})
        threshold = float(decision_cfg.get("threshold", 0.5))
        fp_cost = decision_cfg.get("fp_cost", 1)
        fn_cost = decision_cfg.get("fn_cost", 1)
        note = (
            f"alarm at p>={threshold:g}: expected cost {fp_cost} per false positive vs "
            f"{fn_cost} per missed churner (fn_cost weighted {fn_cost}x an fp)"
        )
        return ChurnScoreResponse(
            churn_probability=round(proba, 4),
            decision=ChurnDecision(
                alarm=proba >= threshold,
                threshold=threshold,
                expected_cost_note=note,
            ),
        )

    return _run_bounded_with_timeout(_predict, _CHURN_SEMAPHORE, _CHURN_BUSY_DETAIL)


# --- Served VRPTW solving (Project 06) --------------------------------------
# No artifacts: solving is a pure function of the Problem schema. The tuned
# 2-opt config is read from the project's params.yaml (solver_best, written by
# the solve stage); max_iterations is capped at that tuned value. ALNS is not
# served (keep worst-case latency low).

_ROUTING_ID = "06-routing-optimization"
_ROUTING_DIR = _project_dir(_ROUTING_ID)
_ROUTING_PARAMS = _ROUTING_DIR / "params.yaml"
_MAX_SOLVE_CUSTOMERS = 200
_SOLVE_SEED = 42


class SolveResponse(RoutePlan):
    """The RoutePlan pydantic JSON plus serving metadata."""

    runtime_s: float


def _two_opt_tuning() -> TwoOptTuning:
    """The tuned 2-opt config persisted under ``solver_best:`` in params.yaml.

    Falls back to the schema defaults when the file or block is absent.
    """
    raw: dict[str, Any] = {}
    try:
        import yaml  # type: ignore[import-untyped]

        data: dict[str, Any] = yaml.safe_load(_ROUTING_PARAMS.read_text()) or {}
        raw = dict(data.get("solver_best") or {})
    except FileNotFoundError:
        pass
    return TwoOptTuning(**{k: v for k, v in raw.items() if k in TwoOptTuning.model_fields})


# Concurrency cap for the CPU-bound solve endpoint: at most 2 solves run at
# once (sync endpoint → threadpool workers, so a threading semaphore, not
# asyncio). Excess requests get a fast 503 instead of queueing CPU work
# (audit pass 3, finding 3). Sized for the 2-cpu container limit in compose.
_SOLVE_SEMAPHORE = threading.BoundedSemaphore(2)


@app.post(f"/projects/{_ROUTING_ID}/solve", response_model=SolveResponse)
def solve_routing(problem: Problem) -> SolveResponse:
    """Solve a VRPTW instance with the tuned 2-opt portfolio (fixed seed 42).

    Guarded to n_customers <= 200, 2 concurrent solves, and a 10 s wall-clock
    cap; with the tuned config (max_iterations 50) the worst-case runtime on a
    200-customer R2-scale instance stays well under 30 s.
    """
    _LIVE_GUARD.gate()
    if problem.n_customers > _MAX_SOLVE_CUSTOMERS:
        raise HTTPException(
            status_code=422,
            detail=f"too many customers: {problem.n_customers} > {_MAX_SOLVE_CUSTOMERS} cap",
        )
    return _run_bounded_with_timeout(
        lambda: _solve_routing_inner(problem),
        _SOLVE_SEMAPHORE,
        "solve capacity busy (2 concurrent solves max) — retry shortly",
    )


def _solve_routing_inner(problem: Problem) -> SolveResponse:
    from routing_optimization.evaluate import solve_with_timing
    from routing_optimization.solver import two_opt
    from routing_optimization.tuning import best_start, restart_plans

    tuning = _two_opt_tuning()
    # Base constructions + untuned 2-opt via the project's entry point; the
    # served plan is the tuned 2-opt on the best construction/restart start
    # (mirrors run_solve's tuned stage).
    _runs, plans = solve_with_timing(problem, tuning.max_iterations, seed=_SOLVE_SEED)
    base = min((plans["nearest_neighbor"], plans["clarke_wright"]), key=lambda p: p.total_distance)
    start = best_start(base, restart_plans(problem, seed=_SOLVE_SEED, restarts=tuning.restarts))
    t0 = time.perf_counter()
    tuned = two_opt(
        problem,
        start,
        max_iterations=tuning.max_iterations,
        acceptance=tuning.acceptance,
        tail_exchange=tuning.tail_exchange,
    )
    runtime_s = time.perf_counter() - t0
    tuned.validate_against(problem)
    return SolveResponse(
        **{**tuned.model_dump(), "solver": "two_opt_tuned"}, runtime_s=round(runtime_s, 6)
    )


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


_RAG_PROJECT = PROJECTS_ROOT / "01-rag-agent"
_agent_cache: Any = None
_agent_lock: Any = None

# Public deployment: the chat endpoints are an LLM cost proxy — they register
# only when explicitly enabled (fail closed). Locally: RAG_CHAT_ENABLED=1.
_RAG_CHAT_ENABLED = os.environ.get("RAG_CHAT_ENABLED") == "1"


async def _load_agent() -> Any:
    """Build (once) the Project 01 agent + retriever, anchored to its index.

    Raises 503 when the package or the built index is unavailable (e.g. a
    fresh container before ``dvc repro`` / ``build-index`` has run).
    """
    global _agent_cache, _agent_lock
    if _agent_cache is not None:
        return _agent_cache
    if _agent_lock is None:
        import anyio

        _agent_lock = anyio.Lock()
    async with _agent_lock:
        if _agent_cache is not None:
            return _agent_cache
        try:
            from rag_agent.agent import build_agent
            from rag_agent.config import RAGConfig
            from rag_agent.index import (
                CrossEncoderReranker,
                Retriever,
                SentenceTransformerEmbedder,
            )
        except ImportError as e:  # pragma: no cover - depends on workspace install
            logger.warning("RAG agent package unavailable: %s", e)
            raise HTTPException(status_code=503, detail="RAG agent unavailable") from e
        if not (_RAG_PROJECT / "data" / "index").is_dir():
            raise HTTPException(
                status_code=503,
                detail="retrieval index not built — run `uv run python -m rag_agent.cli "
                "build-index` (or dvc repro) in projects/01-rag-agent first",
            )
        cfg = RAGConfig(
            corpus_path=_RAG_PROJECT / "data/raw/corpus.jsonl",
            contract_path=_RAG_PROJECT / "data/raw/dataset_contract.json",
            index_dir=_RAG_PROJECT / "data/index",
            eval_questions_path=_RAG_PROJECT / "src/rag_agent/eval_questions.json",
            reports_dir=_RAG_PROJECT / "reports",
        )
        default_size = cfg.chunk_sizes[len(cfg.chunk_sizes) // 2]
        try:
            retriever = Retriever.from_index_dir(
                cfg,
                cfg.index_path(default_size),
                SentenceTransformerEmbedder(cfg.embedding_model),
                CrossEncoderReranker(cfg.reranker_model),
            )
        except Exception as e:  # broad: any load failure → 503, chained
            logger.warning("retriever unavailable: %s", e)
            raise HTTPException(status_code=503, detail="retriever unavailable") from e
        _agent_cache = (build_agent(cfg), retriever)
        return _agent_cache


if _RAG_CHAT_ENABLED:

    @app.post("/rag/chat")
    async def rag_chat(request: ChatRequest) -> dict[str, str]:
        """Simple non-streaming chat: returns the AnalysisResult as JSON string."""
        agent, retriever = await _load_agent()
        result = await agent.run(request.question, deps=retriever)
        return {"answer": result.output.model_dump_json()}

    @app.post("/rag/chat/stream")
    async def rag_chat_stream(request: ChatRequest) -> Any:
        """SSE: `text` events (summary deltas), then a final `result` event (full JSON)."""
        from sse_starlette.sse import EventSourceResponse

        agent, retriever = await _load_agent()

        async def gen() -> AsyncIterator[dict[str, str]]:
            sent = 0
            final: Any = None
            async with agent.run_stream(request.question, deps=retriever) as result:
                # Structured output (AnalysisResult): stream incremental summary
                # text extracted from partial validated objects.
                async for partial in result.stream_output(debounce_by=0.1):
                    final = partial
                    summary = partial.summary or ""
                    if len(summary) > sent:
                        yield {"event": "text", "data": summary[sent:]}
                        sent = len(summary)
                if final is None:
                    final = await result.get_output()
                yield {"event": "result", "data": final.model_dump_json()}

        return EventSourceResponse(gen())


# Keep the catch-all last so every API route above wins.
app.include_router(spa_router)
