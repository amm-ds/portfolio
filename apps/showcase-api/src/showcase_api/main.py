"""Showcase API — serves project results, served-model inference, and the RAG demo.

Nothing here contains training logic; it reads the artifacts projects produce
(reports/metrics.json, reports/figures/*.html, reports/models/serving/*) and
delegates chat to Project 01's agent when that package is installed (it is, in
the workspace/Docker image). Served inference: 02/05/07 read persisted serving
artifacts (503 with build instructions when absent); 06 solves VRPTW instances
purely from the request body with the tuned config from its params.yaml.
"""

import hashlib
import json
import os
import re
import threading
import time
import uuid
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.routing import APIRoute
from portfolio_core.demo import DemoManifest, load_demo_index, to_registry_entry
from portfolio_core.logging import get_logger, setup_logging
from portfolio_core.manifest import load_index
from portfolio_core.story import ProjectStory, load_story
from pydantic import BaseModel, Field
from routing_optimization.schemas import Problem, RoutePlan, TwoOptTuning
from starlette.exceptions import HTTPException as StarletteHTTPException

from showcase_api import __version__, serving
from showcase_api.middleware import (
    BodyLimitMiddleware,
    RateLimitMiddleware,
    RequestIdMiddleware,
    RequestLoggingMiddleware,
)

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
PROJECTS_ROOT = REPO_ROOT / "projects"
WEB_DIST = REPO_ROOT / "apps" / "showcase-web" / "dist"

_PID_RE = r"^\d{2}-[a-z0-9-]+$"

setup_logging("INFO")
app = FastAPI(title="amm-ds portfolio showcase", version=__version__)


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
    logger.warning("%s %s -> 422 rid=%s: %s", request.method, request.url.path, rid, exc.errors())
    return JSONResponse(
        {"error": "request validation failed", "request_id": rid, "details": exc.errors()},
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
    """Liveness + readiness in one cheap call (Docker HEALTHCHECK hits this).

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


def _serving_ready(serving_dir: Path) -> bool:
    """A serving bundle is loadable when its model.joblib + meta.json exist."""
    return (serving_dir / "model.joblib").is_file() and (serving_dir / "meta.json").is_file()


def _readiness() -> bool:
    """Demo payload files + serving bundles the live POST endpoints need."""
    for m in _demo_manifests(PROJECTS_ROOT):
        if m.payload is not None and not (PROJECTS_ROOT / m.project / m.payload.path).is_file():
            return False
    return all(_serving_ready(d) for d in (_DEMAND_SERVING_DIR, _CHURN_SERVING_DIR, _SERVING_DIR))


# --- Startup-computed indexes (served with ETag) ------------------------------
# The /projects and /demos payloads are read from disk once per projects root
# and then served from memory with an ETag; If-None-Match gets a 304. The
# cache key is the projects-root *path*, so tests that monkeypatch
# PROJECTS_ROOT to a tmp dir still see fresh data.


def _cached_payload(root: Path, compute: Callable[[], Any]) -> tuple[str, str]:
    """(etag, body) for a JSON payload, computed once per root path."""
    key = Path(root)
    if key not in _PAYLOAD_CACHE:
        body = json.dumps(compute(), sort_keys=True)
        etag = '"' + hashlib.sha256(body.encode()).hexdigest()[:16] + '"'
        _PAYLOAD_CACHE[key] = (etag, body)
    return _PAYLOAD_CACHE[key]


_PAYLOAD_CACHE: dict[Path, tuple[str, str]] = {}
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
        PROJECTS_ROOT, lambda: [m.model_dump() for m in load_index(PROJECTS_ROOT)]
    )
    return _etag_response(request, etag, body)


@app.get("/projects/{pid}/metrics")
def metrics(pid: str) -> dict[str, Any]:
    # 02-demand-forecasting ships two tracks (CI/synthetic in reports/, the
    # primary real-data UCI run in reports_uci/, see its story.yaml); when a
    # project carries a reports_uci/ dir that track is the canonical source
    # for the numbers the story quotes. Everywhere else reports/ is it.
    d = _project_dir(pid)
    f = d / "reports_uci" / "metrics.json"
    if not f.exists():
        f = d / "reports" / "metrics.json"
    if not f.exists():
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
    forecasting ships two tracks (CI/synthetic in ``reports/figures/``, the
    primary UCI run in ``reports_uci/figures/``) and its story.yaml names
    figures per track (e.g. ``uci:metrics_bars``). Unprefixed names keep the
    canonical ``reports/figures/`` location every other project uses.
    """
    track, sep, bare = name.partition(":")
    d = _project_dir(pid)
    candidates = (
        [d / f"reports_{track}" / "figures" / f"{bare}.{ext}"]
        if sep
        else [d / "reports" / "figures" / f"{name}.{ext}"]
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
    """Interactive figure HTML, cached 1 h (stale-while-revalidate 24 h) + ETag."""
    f = _figure_file(pid, name, "html")
    if f is None:
        raise HTTPException(status_code=404, detail=f"no figure {name!r} for {pid}")
    return _cached_file_response(request, f, media_type="text/html")


def _cached_file_response(request: Request, path: Path, media_type: str) -> Response:
    """200 with CDN cache headers + content ETag, or 304 on If-None-Match."""
    content = path.read_bytes()
    etag = '"' + hashlib.sha256(content).hexdigest()[:16] + '"'
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


# --- Interactive demos (Wave 1: churn threshold sandbox, project 05) ---------
# Demos are declared by each project's demo.yaml (see portfolio_core.demo) and
# served here generically: the registry index, the manifest, and the compact
# precomputed payload (built by the project's pipeline, validated against the
# manifest's required_keys / schema_version). Live POST endpoints live under
# /projects/<pid>/; the UI lives in showcase-web at /demos/<id>.


def _demo_or_404(demo_id: str) -> DemoManifest:
    for m in load_demo_index(PROJECTS_ROOT):
        if m.id == demo_id:
            return m
    raise HTTPException(status_code=404, detail=f"unknown demo: {demo_id}")


@app.get("/demos")
def demos_index(request: Request) -> Response:
    """Registry entries for the frontend demos index (sorted by group, id),
    computed once at startup and served with ETag."""
    etag, body = _cached_payload(
        PROJECTS_ROOT, lambda: [to_registry_entry(m) for m in _demo_manifests(PROJECTS_ROOT)]
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
    409 when the payload violates the manifest contract (missing required keys
    or a schema_version mismatch).
    """
    m = _demo_or_404(demo_id)
    if m.payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"demo {demo_id} declares no payload yet — the manifest is a placeholder",
        )
    f = PROJECTS_ROOT / m.project / m.payload.path
    if not f.exists():
        raise HTTPException(
            status_code=404,
            detail=f"demo payload not built for {m.project} — run its demo-payload "
            f"stage to write {m.payload.path}",
        )
    data: dict[str, Any] = json.loads(f.read_text())
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
    etag = '"' + hashlib.sha256(f.read_bytes()).hexdigest()[:16] + '"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(
        data,
        headers={
            "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
            "ETag": etag,
        },
    )


@app.get("/projects/{pid}/report", response_class=HTMLResponse)
def report(pid: str) -> str:
    """The project's full evaluation report (HTML).

    Track-aware resolution, most-recent headline first: 02-demand-forecasting
    now ships three tracks — the M5 headline in ``reports_m5/`` (canonical),
    the UCI sparse track in ``reports_uci/``, and the synthetic CI track in
    ``reports/``. Everywhere else ``reports/report.html`` is it.
    """
    d = _project_dir(pid)
    for candidate in (
        d / "reports_m5" / "report.html",
        d / "reports_uci" / "report.html",
        d / "reports" / "report.html",
    ):
        if candidate.exists():
            return candidate.read_text()
    raise HTTPException(status_code=404, detail=f"no report yet for {pid} — run its pipeline")


# --- Live-call guard + wall-clock cap ----------------------------------------
# The live POST endpoints (/forecast, /score, /solve) run real model inference
# on request. Two production guardrails, both fail closed:
#
# - Kill switch: LIVE_KILL_SWITCH=1 in the env, or the file /tmp/live_disabled
#   exists → every live call gets a fast 503 pointing at the precomputed demo
#   replay. Cheap circuit breaker during incidents.
# - Daily budget: a global in-process counter (UTC day) capped by
#   DAILY_LIVE_BUDGET (default 1000). At 80% a WARNING is logged once per day;
#   past the budget every call gets 503 until the day rolls over.

# Spec'd operator kill-switch flag: touching this file disables the live POST
# endpoints (503 + replay hint) until it is removed.
_LIVE_DISABLE_FLAG = Path("/tmp/live_disabled")  # noqa: S108
_LIVE_TIMEOUT_S = 10.0  # wall-clock cap for /solve and the /forecast POSTs
_LIVE_BUDGET_DEFAULT = 1000
_LIVE_REPLAY_HINT = "precomputed demo replay remains available"


class LiveGuard:
    """Kill-switch + daily call budget for the live POST endpoints."""

    def __init__(self, budget: int = _LIVE_BUDGET_DEFAULT, kill_switch: bool = False):
        self.budget = budget
        self.kill_switch = kill_switch
        self._lock = threading.Lock()
        self._day = ""
        self._count = 0
        self._alerted = False

    @classmethod
    def from_env(cls) -> "LiveGuard":
        raw = os.environ.get("DAILY_LIVE_BUDGET", "")
        budget = int(raw) if raw else _LIVE_BUDGET_DEFAULT
        return cls(budget=budget, kill_switch=os.environ.get("LIVE_KILL_SWITCH") == "1")

    def disabled(self) -> bool:
        return self.kill_switch or _LIVE_DISABLE_FLAG.exists()

    def gate(self) -> None:
        """Raise 503 when live calls are disabled or the daily budget is spent."""
        if self.disabled():
            raise LiveCallBlocked("live inference temporarily disabled")
        today = datetime.now(UTC).date().isoformat()
        with self._lock:
            if today != self._day:
                self._day, self._count, self._alerted = today, 0, False
            self._count += 1
            count = self._count
        if count > self.budget:
            logger.warning("live daily budget exhausted: %d/%d calls", count, self.budget)
            raise LiveCallBlocked("daily live-call budget exhausted")
        if not self._alerted and count >= 0.8 * self.budget:
            self._alerted = True
            logger.warning("live daily budget at 80%%: %d/%d calls today", count, self.budget)


class LiveCallBlocked(HTTPException):
    """503 raised by the live-call guard; the handler surfaces ``hint`` so the
    client knows the precomputed demo replay still works."""

    def __init__(self, detail: str):
        super().__init__(status_code=503, detail=detail)
        self.hint = _LIVE_REPLAY_HINT


_LIVE_GUARD = LiveGuard.from_env()


def _run_with_timeout[T](fn: Callable[[], T], seconds: float = _LIVE_TIMEOUT_S) -> T:
    """Run CPU-bound inference work on a worker thread with a wall-clock cap.

    On timeout the worker is abandoned (it cannot be killed mid-predict) and
    the caller gets a 504; the solve semaphore is still released by the
    endpoint's finally block, so one slow solve cannot exhaust capacity.
    """
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(fn).result(timeout=seconds)
    except FutureTimeout as e:
        raise HTTPException(
            status_code=504, detail=f"request exceeded the {seconds:.0f}s wall-clock cap"
        ) from e
    finally:
        pool.shutdown(wait=False)


# --- Served forecasts (Project 07) -----------------------------------------
# Loads the compact serving artifact built by `mobility.cli build-serving-artifact`;
# see projects/07-open-data-mobility/SERVING.md for the contract.

_MOBILITY_ID = "07-open-data-mobility"
_SERVING_DIR = _project_dir(_MOBILITY_ID) / "reports" / "models" / "serving"


class ForecastRequest(BaseModel):
    zone_id: int = Field(ge=1)
    features: dict[str, float] = Field(min_length=1, max_length=64)


class ForecastResponse(BaseModel):
    zone_id: int
    borough: str
    zone: str
    prediction: float
    p90: float


def _serving_artifacts() -> tuple[Any, dict[str, Any], list[dict[str, Any]]] | None:
    """Load the serving bundle once and cache it (joblib load is ~10 ms per call
    on a 6.5 MB artifact — not per-request material, and caching removes the
    disk-amplification concern entirely)."""
    artifacts = serving.cached_artifacts(_SERVING_DIR, extra_json=("zones.json",))
    if artifacts is None:
        return None
    return artifacts["model"], artifacts["meta"], artifacts["zones"]


@app.post(f"/projects/{_MOBILITY_ID}/forecast", response_model=ForecastResponse)
def forecast_mobility(request: ForecastRequest) -> ForecastResponse:
    """Zone-hour demand forecast from the persisted tuned GBM (+p90 band)."""
    _LIVE_GUARD.gate()
    artifacts = _serving_artifacts()
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
        )

    return _run_with_timeout(_predict)


# --- Served forecasts (Project 02) ------------------------------------------
# Contract: projects/02-demand-forecasting/reports/models/serving/ holds
# model.joblib ({"model": sklearn Pipeline taking a raw dict with a string
# series_id + numeric features, "feature_names", "target_transform"}) and
# meta.json ({"model_name", "series": [...known series ids...], "example_row"}).

_DEMAND_ID = "02-demand-forecasting"
_DEMAND_SERVING_DIR = _project_dir(_DEMAND_ID) / "reports" / "models" / "serving"


class DemandForecastRequest(BaseModel):
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

    return _run_with_timeout(_predict)


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


class ChurnScoreRequest(BaseModel):
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
    """Churn probability + cost-threshold alarm from the persisted pipeline."""
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
    if not _SOLVE_SEMAPHORE.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail="solve capacity busy (2 concurrent solves max) — retry shortly",
        )
    try:
        return _run_with_timeout(lambda: _solve_routing_inner(problem))
    finally:
        # On timeout the abandoned worker may still hold its slot briefly; the
        # semaphore is released here regardless so capacity recovers.
        _SOLVE_SEMAPHORE.release()


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


def _index_html() -> str:
    """The built SPA shell, read per request: rebuilds replace hashed asset
    names, so a cached copy at import time would point at deleted files."""
    return (WEB_DIST / "index.html").read_text()


# --- SPA catch-all + route manifest -------------------------------------------
# The catch-all serves the React build for known client-side routes and returns
# a real JSON 404 (with request_id) for everything else. The manifest combines
# the API routes registered above (collected at startup) with the known SPA
# routes from route_manifest.json — generated by scripts/gen_route_manifest.py
# (App.tsx routes + project ids + demo ids) and committed at build/CI time.

_MANIFEST_FILE = Path(__file__).with_name("route_manifest.json")


def _pattern_match(pattern: str, path: str) -> bool:
    """Exact match where each ``*`` pattern segment matches one non-empty path
    segment (mirrors React Router's single-``:param`` semantics)."""
    if pattern == "/":
        return path.strip("/") == ""
    pp = [s for s in pattern.split("/") if s]
    sp = [s for s in path.split("/") if s]
    return len(pp) == len(sp) and all(p == "*" or p == s for p, s in zip(pp, sp, strict=True))


def _spa_patterns() -> list[str]:
    """Known SPA routes from the generated manifest.

    Fallback when the manifest file is missing/stale-broken (e.g. an editable
    install without the committed artifact): derive the same routes from the
    projects root plus the static routes hardcoded in App.tsx, and warn.
    """
    try:
        data = json.loads(_MANIFEST_FILE.read_text())
        return [str(p) for p in data["spa_routes"]]
    except (OSError, KeyError, ValueError) as e:
        logger.warning("route manifest unavailable (%s); deriving SPA routes", e)
        patterns = ["/", "/projects", "/experiments", "/services", "/contact", "/about"]
        try:
            patterns += [f"/projects/{m.id}" for m in load_index(PROJECTS_ROOT)]
            patterns += [f"/demos/{m.id}" for m in load_demo_index(PROJECTS_ROOT)]
        except OSError:
            pass
        return patterns


def _api_patterns() -> list[tuple[str, str]]:
    """(method, path-pattern) for every API route, path params as ``*``."""
    out = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            pattern = re.sub(r"\{[^}]+\}", "*", route.path)
            for method in route.methods or ():
                out.append((method, pattern))
    return out


_SPA_PATTERNS = _spa_patterns()
_API_PATTERNS = _api_patterns()


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str) -> Response:
    """Serve the React build: hashed assets as-is, known SPA routes →
    index.html, anything else → real JSON 404.

    Registered last, so API routes above always win. Paths are resolved and
    confined to WEB_DIST — dot segments fall back to index.html instead of
    escaping the build directory (path traversal). Without a web build every
    unknown GET is a structured 404.
    """
    path = "/" + full_path if not full_path.startswith("/") else full_path
    if WEB_DIST.exists():
        if full_path:
            candidate = (WEB_DIST / full_path).resolve()
            if candidate.is_relative_to(WEB_DIST.resolve()) and candidate.is_file():
                # Vite content-hashes everything under /assets/ → immutable;
                # any other file (favicon, manifests) must be revalidated.
                cache = (
                    "public, max-age=31536000, immutable"
                    if full_path.startswith("assets/")
                    else "no-cache"
                )
                return FileResponse(candidate, headers={"Cache-Control": cache})
        if any(_pattern_match(p, path) for p in _SPA_PATTERNS):
            return HTMLResponse(_index_html(), headers={"Cache-Control": "no-cache"})
    elif any(_pattern_match(p, path) for p in _SPA_PATTERNS):
        raise HTTPException(status_code=404, detail="web build not found")
    raise HTTPException(status_code=404, detail=f"unknown path: {path}")
