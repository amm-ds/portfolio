"""Local LLM parity check: MLX-LM server vs Ollama (L2, 2026-11-21).

Runs the 10 fixed parity prompts through both local backends at temperature 0
with the same system prompt and max tokens, saves outputs side by side, runs
the agent tool-call check through the project's agent code path against each
endpoint, and records speed. Localhost only; zero hosted calls.

Outputs land in reports/local_llm_parity/ (prompt_outputs.json,
tool_call_check.json, speed.json). Nothing here edits production code.

    ~/.venvs/mlx-lm/bin/python not needed; run with the project venv:
    uv run python scripts/local_llm_parity.py
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "local_llm_parity"
MLX = "http://127.0.0.1:8080/v1/chat/completions"
OLLAMA_MODEL = "qwen3.6:35b-a3b-q4_K_M"
MLX_MODEL = "mlx-community/Qwen3.6-35B-A3B-4bit"

# Same system prompt and ceiling for both backends.
SYSTEM = "You are a meticulous research assistant. Answer precisely."
MAX_TOKENS = 512

GENERATION_TASKS = [
    "In one sentence, what causes the seasons on Earth?",
    "List three greenhouse gases in a single sentence.",
]


def chat_mlx(prompt: str) -> dict[str, Any]:
    """MLX via its OpenAI-compatible server; thinking disabled via chat_template_kwargs."""
    payload = {
        "model": MLX_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        MLX,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as resp:  # noqa: S310 - localhost
        body = json.load(resp)
    elapsed = time.perf_counter() - start
    choice = body["choices"][0]
    usage = body.get("usage", {})
    return {
        "text": choice["message"]["content"] or "",
        "finish_reason": choice.get("finish_reason"),
        "completion_tokens": usage.get("completion_tokens"),
        "elapsed_s": round(elapsed, 2),
        "tok_per_s": (
            round(usage["completion_tokens"] / elapsed, 2)
            if usage.get("completion_tokens")
            else None
        ),
        "thinking": "disabled",
    }


def chat_ollama(prompt: str) -> dict[str, Any]:
    """Ollama via its native /api/chat; thinking disabled via think:false (the /v1
    endpoint ignores the flag, verified during setup)."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "think": False,
        "stream": False,
        "options": {"temperature": 0, "num_predict": MAX_TOKENS},
    }
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as resp:  # noqa: S310 - localhost
        body = json.load(resp)
    elapsed = time.perf_counter() - start
    eval_duration = body.get("eval_duration", 0) / 1e9  # ns -> s
    eval_count = body.get("eval_count", 0)
    return {
        "text": body["message"]["content"],
        "finish_reason": "stop" if body.get("done") else None,
        "completion_tokens": eval_count,
        "elapsed_s": round(elapsed, 2),
        "tok_per_s": round(eval_count / eval_duration, 2) if eval_duration else None,
        "thinking": "disabled",
    }


def parity_prompts() -> list[str]:
    g120 = json.loads((ROOT / "data" / "golden_sealed_v2.json").read_text())
    # 8 sealed-v2 questions: mix of categories; includes 62-file index 26
    # (the pathological Eysturoy question, 120-index 53).
    picks = [g120[53]["question"]]
    for want in (
        "single_hop",
        "multi_hop",
        "single_hop",
        "unanswerable",
        "multi_hop",
        "single_hop",
        "single_hop",
    ):
        for q in g120:
            if q["category"] == want and q["question"] not in picks:
                picks.append(q["question"])
                break
    if len(picks) != 8:
        raise ValueError(f"expected 8 sealed picks, got {len(picks)}")
    return picks + GENERATION_TASKS


def run_parity() -> list[dict[str, Any]]:
    rows = []
    for i, prompt in enumerate(parity_prompts()):
        mlx = chat_mlx(prompt)
        oll = chat_ollama(prompt)
        rows.append(
            {
                "id": f"p{i:02d}",
                "prompt": prompt,
                "exact_match": mlx["text"] == oll["text"],
                "mlx": mlx,
                "ollama": oll,
            }
        )
        print(f"p{i:02d} exact_match={rows[-1]['exact_match']}")
    return rows


def run_tool_call_check() -> list[dict[str, Any]]:
    """Agent tool-call check through the project's agent code path, per endpoint."""
    os.environ["RAG_NATIVE_OUTPUT"] = "1"  # documented local generation path
    os.environ.pop("LLM_API_KEY", None)
    os.environ.pop("LLM_BASE_URL", None)
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    from rag_agent.agent import build_agent
    from rag_agent.config import RAGConfig
    from rag_agent.index import (
        CrossEncoderReranker,
        Retriever,
        SentenceTransformerEmbedder,
        load_index,
    )

    config = RAGConfig()
    size = config.chunk_sizes[len(config.chunk_sizes) // 2]
    index, chunks = load_index(config.index_path(size))
    retriever = Retriever(
        config,
        index,
        chunks,
        embed_fn=SentenceTransformerEmbedder(config.embedding_model),
        rerank_fn=CrossEncoderReranker(config.reranker_model),
    )
    g120 = json.loads((ROOT / "data" / "golden_sealed_v2.json").read_text())
    targets = {
        "search_a": g120[0]["question"],
        "search_b": g120[4]["question"],
        "search_c": g120[10]["question"],
        "read_excerpt": g120[2]["question"],
    }
    endpoints = {
        "mlx": ("http://127.0.0.1:8080/v1", MLX_MODEL),
        "ollama": ("http://localhost:11434/v1", OLLAMA_MODEL),
    }
    # Count tool invocations at the Retriever seam (the agent's only tools).
    counts = {"search": 0, "read": 0}
    orig_search = retriever.search
    orig_get = retriever.get_chunk

    def counted_search(*args: Any, **kwargs: Any) -> Any:
        counts["search"] += 1
        return orig_search(*args, **kwargs)

    def counted_get(*args: Any, **kwargs: Any) -> Any:
        counts["read"] += 1
        return orig_get(*args, **kwargs)

    setattr(retriever, "search", counted_search)  # noqa: B010 - deliberate instance shadowing for counting
    setattr(retriever, "get_chunk", counted_get)  # noqa: B010 - deliberate instance shadowing for counting

    results = []
    for backend, (base, model_name) in endpoints.items():
        provider = OpenAIProvider(base_url=base, api_key="local")
        model = OpenAIChatModel(model_name, provider=provider)
        agent = build_agent(config, model=model)
        for label, question in targets.items():
            counts["search"] = 0
            counts["read"] = 0
            start = time.perf_counter()
            try:
                result = agent.run_sync(question, deps=retriever)
                output = result.output
                valid = hasattr(output, "summary")
                text = output.summary[:120] if valid else None
                error = None
            except Exception as exc:  # broad: record and continue
                valid = False
                text = None
                error = f"{type(exc).__name__}: {exc}"[:200]
            results.append(
                {
                    "backend": backend,
                    "case": label,
                    "question": question[:80],
                    "search_documents_calls": counts["search"],
                    "read_excerpt_calls": counts["read"],
                    "schema_valid": valid,
                    "summary_prefix": text,
                    "elapsed_s": round(time.perf_counter() - start, 2),
                    "error": error,
                }
            )
            print(
                backend,
                label,
                "search=",
                counts["search"],
                "read=",
                counts["read"],
                "valid=",
                valid,
            )
    return results


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = run_parity()
    (OUT / "prompt_outputs.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    checks = run_tool_call_check()
    (OUT / "tool_call_check.json").write_text(
        json.dumps(checks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    meta = {
        "generated_at": datetime.now(UTC).isoformat(),
        "system_prompt": SYSTEM,
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "mlx_model": MLX_MODEL,
        "ollama_model": OLLAMA_MODEL,
        "exact_match_rate": round(sum(r["exact_match"] for r in rows) / len(rows), 4),
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print("written:", OUT)


if __name__ == "__main__":
    main()
