"""Showcase API — serves project results, served-model inference, and the RAG demo.

Nothing here contains training logic; it reads the artifacts projects produce
(reports/metrics.json, reports/figures/*.html, reports/models/serving/*) and
delegates chat to Project 01's agent when that package is installed (it is, in
the workspace/Docker image). Served inference: 02/05/07 read persisted serving
artifacts (503 with build instructions when absent); 06 solves VRPTW instances
purely from the request body with the tuned config from its params.yaml.
"""

import json
import os
import re
import threading
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from portfolio_core.logging import get_logger, setup_logging
from portfolio_core.manifest import load_index
from portfolio_core.story import ProjectStory, load_story
from pydantic import BaseModel, Field
from routing_optimization.schemas import Problem, RoutePlan, TwoOptTuning

from showcase_api import serving
from showcase_api.middleware import (
    BodyLimitMiddleware,
    RateLimitMiddleware,
    RequestLoggingMiddleware,
)

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
PROJECTS_ROOT = REPO_ROOT / "projects"
WEB_DIST = REPO_ROOT / "apps" / "showcase-web" / "dist"

_PID_RE = r"^\d{2}-[a-z0-9-]+$"

setup_logging("INFO")
app = FastAPI(title="amm-ds portfolio showcase", version="0.1.0")

# Production floor (see showcase_api.middleware docstrings): body cap → rate
# limit → request log. Last added runs outermost, so the log line sees the
# final status (including 413/429) and latency of the whole chain.
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)


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
def projects(request: Request) -> Response:
    """Project index JSON — unless a browser navigates here directly (refresh /
    deep link), in which case serve the SPA and let the client-side router
    render the projects page. API clients (curl, fetch with an explicit JSON
    accept) get the payload."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return (
            HTMLResponse(_index_html())
            if WEB_DIST.exists()
            else JSONResponse({"detail": "web build not found"}, status_code=503)
        )
    return JSONResponse([m.model_dump() for m in load_index(PROJECTS_ROOT)])


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
    artifacts = serving.cached_artifacts(_DEMAND_SERVING_DIR)
    if artifacts is None:
        raise HTTPException(
            status_code=503,
            detail="serving artifacts not built — run the serving stage in "
            "projects/02-demand-forecasting first (writes reports/models/serving/)",
        )
    bundle: dict[str, Any] = artifacts["model"]
    meta: dict[str, Any] = artifacts["meta"]
    model = bundle["model"]
    feature_names: list[str] = list(bundle.get("feature_names") or meta.get("feature_names") or [])
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
    import pandas as pd  # type: ignore[import-untyped]

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

    Guarded to n_customers <= 200 and to 2 concurrent solves; with the tuned
    config (max_iterations 50) the worst-case runtime on a 200-customer
    R2-scale instance stays well under 30 s.
    """
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
        return _solve_routing_inner(problem)
    finally:
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


if WEB_DIST.exists():
    from starlette.responses import Response

    _WEB_DIST_RESOLVED = WEB_DIST.resolve()

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
