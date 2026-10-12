"""Showcase API — serves project results and the RAG demo.

Nothing here contains training logic; it reads the artifacts projects produce
(reports/metrics.json, reports/figures/*.html) and delegates chat to Project
01's agent when that package is installed (it is, in the workspace/Docker image).
"""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from portfolio_core.logging import get_logger, setup_logging
from portfolio_core.manifest import ProjectInfo, load_index
from portfolio_core.story import ProjectStory, load_story
from pydantic import BaseModel, Field

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
PROJECTS_ROOT = REPO_ROOT / "projects"
WEB_DIST = REPO_ROOT / "apps" / "showcase-web" / "dist"

setup_logging("INFO")
app = FastAPI(title="amm-ds portfolio showcase", version="0.1.0")


def _project_dir(pid: str) -> Path:
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


@app.get("/projects/{pid}/figures/{name}", response_class=HTMLResponse)
def figure(pid: str, name: str) -> str:
    f = _project_dir(pid) / "reports" / "figures" / f"{name}.html"
    if not f.exists():
        raise HTTPException(status_code=404, detail=f"no figure {name!r} for {pid}")
    return f.read_text()


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)


_RAG_PROJECT = PROJECTS_ROOT / "01-rag-agent"
_agent_cache: Any = None


async def _load_agent() -> Any:
    """Build (once) the Project 01 agent + retriever, anchored to its index.

    Raises 503 when the package or the built index is unavailable (e.g. a
    fresh container before ``dvc repro`` / ``build-index`` has run).
    """
    global _agent_cache
    if _agent_cache is not None:
        return _agent_cache
    try:
        from rag_agent.agent import build_agent
        from rag_agent.config import RAGConfig
        from rag_agent.index import CrossEncoderReranker, Retriever, SentenceTransformerEmbedder
    except ImportError as e:  # pragma: no cover - depends on workspace install
        raise HTTPException(status_code=503, detail=f"RAG agent package unavailable: {e}") from e
    if not (_RAG_PROJECT / "data" / "index").is_dir():
        raise HTTPException(
            status_code=503,
            detail="retrieval index not built — run `uv run python -m rag_agent.cli build-index` "
            "(or dvc repro) in projects/01-rag-agent first",
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
        raise HTTPException(status_code=503, detail=f"retriever unavailable: {e}") from e
    _agent_cache = (build_agent(cfg), retriever)
    return _agent_cache


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
    from fastapi.responses import FileResponse, HTMLResponse
    from starlette.responses import Response

    def _index_html() -> str:
        # Read per request: rebuilds replace hashed asset names, so a cached
        # copy at import time would point at deleted files.
        return (WEB_DIST / "index.html").read_text()

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> Response:
        """Serve the React build: real files as-is, everything else → index.html.

        Registered last, so API routes above always win. Without this, deep
        links/refresh on client-side routes (e.g. /projects/07-...) 404.
        """
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return HTMLResponse(_index_html())
