"""The single sealed C evaluation (R7): local generation + hosted adjudication.

Per the R7 plan's final measurement: the local pipeline generates (Ollama
qwen2.5:3b — the non-thinking instruct substitute after qwen3:4b ignored
think-off at ~60s/call and qwen3:4b-instruct-2507 is absent from the
registry), while the rubric judge AND claim verifier run hosted (the local
judge failed calibration: false-rejection 83.5%, kappa 0.155 — diagnostics
only). Hosted adjudication is bounded by the \$2.50 cloud-equivalent budget.

Usage (from the project root, hosted env sourced):
    uv run python scripts/run_sealed_c.py

The run lands under metrics.json detail.stress_c + question_traces_stress_c.json
with the R6/R7 run record (dataset hash, commit, thresholds, caps, cost).
"""

from __future__ import annotations

import os
from pathlib import Path

from rag_agent.cli import load_config
from rag_agent.evaluate import run_stress_eval


def main() -> None:
    os.environ["OLLAMA_MODEL"] = "qwen2.5:3b"
    os.environ["RAG_NATIVE_OUTPUT"] = "1"  # grammar-constrained output locally

    import httpx
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.ollama import OllamaProvider

    local_model = OpenAIChatModel(
        model_name=os.environ["OLLAMA_MODEL"],
        provider=OllamaProvider(
            base_url="http://127.0.0.1:11434/v1",
            api_key="ollama",
            http_client=httpx.AsyncClient(timeout=120.0),
        ),
    )
    config = load_config()  # params.yaml overlay: retrieval_best + thresholds
    # Judges stay hosted (calibrated hosted adjudication); the USD/token caps
    # guard the hosted phases; the agent itself is the local model above.
    os.environ.setdefault("LLM_COST_LIMIT_USD", "6")
    os.environ.setdefault("LLM_TOTAL_TOKENS_LIMIT", "80000000")
    payload = run_stress_eval(
        config,
        questions_path=Path("data/golden_stress_c.json"),
        tag="_c",
        model=local_model,
        meter_active=True,
    )
    print(
        "overall:",
        payload["taxonomy"]["correct_share"],
        "| unsupported:",
        payload["taxonomy"]["counts"].get("unsupported-claim", 0),
    )
    print(
        "refusal:",
        payload["abstention"]["refusal_accuracy"],
        "| false abstention:",
        payload["abstention"]["false_abstention_rate"],
    )
    print(
        "spend:",
        payload["meter"]["total"]["spend_usd"],
        "| budget_terminated:",
        payload["budget_terminated"],
    )
    print("slices:", payload["by_slice"])


if __name__ == "__main__":
    main()
