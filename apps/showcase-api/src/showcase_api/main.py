"""Showcase API — serves project results and the RAG demo.

Nothing here contains training logic; it reads the artifacts projects produce
(reports/metrics.json, reports/figures/*.html) and delegates chat to Project
01's agent when that package is installed (it is, in the workspace/Docker image).
"""

import json
import os
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from portfolio_core.logging import get_logger, setup_logging
from portfolio_core.manifest import ProjectInfo, load_index
from portfolio_core.story import ProjectStory, load_story
from pydantic import BaseModel, Field

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
PROJECTS_ROOT = REPO_ROOT / "projects"
WEB_DIST = REPO_ROOT / "apps" / "showcase-web" / "dist"

_PID_RE = r"^\d{2}-[a-z0-9-]+$"

setup_logging("INFO")
app = FastAPI(title="amm-ds portfolio showcase", version="0.1.0")


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
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/projects")
def projects() -> list[ProjectInfo]:
    return list(load_index(PROJECTS_ROOT))


@app.get("/projects/{pid}/metrics")
def metrics(pid: str) -> dict[str, Any]:
    f = _project_dir(pid) / "reports" / "metrics.json"
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


@app.get("/projects/{pid}/figures")
def figures(pid: str) -> list[str]:
    figs = sorted((_project_dir(pid) / "reports" / "figures").glob("*.html"))
    return [f.stem for f in figs]


@app.get("/projects/{pid}/figures/{name}.json")
def figure_json(pid: str, name: str) -> Any:
    """Plotly JSON payload (same content the React app could render natively)."""
    f = _project_dir(pid) / "reports" / "figures" / f"{name}.json"
    if not f.exists():
        raise HTTPException(status_code=404, detail=f"no figure JSON {name!r} for {pid}")
    data: Any = json.loads(f.read_text())
    return data


@app.get("/projects/{pid}/figures/{name}", response_class=HTMLResponse)
def figure(pid: str, name: str) -> str:
    f = _project_dir(pid) / "reports" / "figures" / f"{name}.html"
    if not f.exists():
        raise HTTPException(status_code=404, detail=f"no figure {name!r} for {pid}")
    return f.read_text()


@app.get("/projects/{pid}/report", response_class=HTMLResponse)
def report(pid: str) -> str:
    """The project's full evaluation report (reports/report.html)."""
    f = _project_dir(pid) / "reports" / "report.html"
    if not f.exists():
        raise HTTPException(status_code=404, detail=f"no report yet for {pid} — run its pipeline")
    return f.read_text()


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


_serving_cache: tuple[Any, dict[str, Any], list[dict[str, Any]]] | None = None


def _serving_artifacts() -> tuple[Any, dict[str, Any], list[dict[str, Any]]] | None:
    """Load the serving bundle once and cache it (joblib load is ~10 ms per call
    on a 6.5 MB artifact — not per-request material, and caching removes the
    disk-amplification concern entirely)."""
    global _serving_cache
    if _serving_cache is not None:
        return _serving_cache
    model_path, meta_path, zones_path = (
        _SERVING_DIR / "model.joblib",
        _SERVING_DIR / "meta.json",
        _SERVING_DIR / "zones.json",
    )
    if not (model_path.exists() and meta_path.exists() and zones_path.exists()):
        return None
    import joblib

    bundle = joblib.load(model_path)
    meta = json.loads(meta_path.read_text())
    zones = json.loads(zones_path.read_text())
    _serving_cache = (bundle, meta, zones)
    return _serving_cache


@app.post(f"/projects/{_MOBILITY_ID}/forecast", response_model=ForecastResponse)
def forecast_mobility(request: ForecastRequest) -> ForecastResponse:
    """Zone-hour demand forecast from the persisted tuned GBM (+p90 band)."""
    artifacts = _serving_artifacts()
    if artifacts is None:
        raise HTTPException(
            status_code=503,
            detail="serving artifacts not built — run `uv run python -m mobility.cli "
            "build-serving-artifact` in projects/07-open-data-mobility first",
        )
    bundle, meta, zones = artifacts
    zone_row = next((z for z in zones if z.get("location_id") == request.zone_id), None)
    if zone_row is None:
        raise HTTPException(status_code=422, detail=f"unknown zone_id {request.zone_id}")
    feature_names: list[str] = list(meta.get("feature_names") or bundle.get("feature_names") or [])
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
        except Exception as e:
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


if WEB_DIST.exists():
    from starlette.responses import Response

    _WEB_DIST_RESOLVED = WEB_DIST.resolve()

    def _index_html() -> str:
        # Read per request: rebuilds replace hashed asset names, so a cached
        # copy at import time would point at deleted files.
        return (WEB_DIST / "index.html").read_text()

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> Response:
        """Serve the React build: real files as-is, everything else → index.html.

        Registered last, so API routes above always win. Without this, deep
        links/refresh on client-side routes (e.g. /projects/07-...) 404.
        Paths are resolved and confined to WEB_DIST — dot segments fall back
        to index.html instead of escaping the build directory (path traversal).
        """
        if full_path:
            candidate = (WEB_DIST / full_path).resolve()
            if candidate.is_relative_to(_WEB_DIST_RESOLVED) and candidate.is_file():
                return FileResponse(candidate)
        return HTMLResponse(_index_html())
