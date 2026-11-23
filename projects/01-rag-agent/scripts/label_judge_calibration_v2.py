"""Label judge_v2 claims with kimi-for-coding — step 1, Revision 3.

Hosted labelling calls ONLY, against the single permitted non-localhost host
named in ``reports/experiment_log.json`` before the first call (from
settings: https://api.kimi.com, model kimi-for-coding). Any request to any
other host stops the run. Hard cap $3.00 estimated spend (cloud-equivalent at
the kimi-k2.8 reference card), enforced twice: the platform SpendLedger with
LLM_COST_LIMIT_USD=3.0 in-process, and a pre-call cumulative check.

Every call writes ``reports/judge_calibration_v2/raw/<index>.json`` (model,
token counts, estimated cost, cumulative total, latency, hosts, raw response,
parsed label/reason) and appends one row to ``reports/experiment_log.json``.
Resumable: claims with an existing raw file are skipped.

After all claims are labelled, draws the owner sample: 30 claims written
UNLABELLED (no kind, no model label) to
``reports/judge_calibration_v2/owner_sample.json`` for the owner to label by
hand. Agreement is NOT computed here.

    uv run python scripts/label_judge_calibration_v2.py            # all 150
    uv run python scripts/label_judge_calibration_v2.py --limit 3  # smoke
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

os.environ["LLM_COST_LIMIT_USD"] = "3.0"  # before any portfolio_core import

from portfolio_core.config import get_settings
from portfolio_core.llm import build_model
from portfolio_core.llm_budget import (
    BudgetExceededError,
    budget_limits,
    get_ledger,
    meter_result,
)
from portfolio_core.logging import get_logger
from rag_agent.runner import HostGrabber

logger = get_logger(__name__)
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "reports" / "judge_calibration_v2" / "raw"
CLAIMS = ROOT / "data" / "judge_v2_claims.json"
OWNER_SAMPLE = ROOT / "reports" / "judge_calibration_v2" / "owner_sample.json"
LOG = ROOT / "reports" / "experiment_log.json"
LOCAL_HOSTS = {"localhost", "127.0.0.1", None}
SAMPLE_SEED = 44
SAMPLE_N = 30
MAX_CONSECUTIVE_ERRORS = 3

SYSTEM_PROMPT = """You are a strict claim-verification judge for RAG calibration.

You receive one evidence passage and one claim. Decide whether the claim is
supported by the passage, using ONLY the passage — never outside knowledge. A
claim is supported only if the passage states every fact in it; numbers and
dates must match exactly. If any part is missing, contradicted, or not stated,
the claim is unsupported.

Respond with a JSON object only:
{"label": "supported" | "unsupported", "reason": "one short line"}"""


def append_log(row: dict[str, Any]) -> None:
    rows = json.loads(LOG.read_text("utf-8")) if LOG.exists() else []
    rows.append(row)
    LOG.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def parse_json_block(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON object in response")
    parsed: dict[str, Any] = json.loads(match.group(0))
    return parsed


def named_host() -> str:
    """The one permitted non-localhost host (from settings, no key material)."""
    url = urlparse(get_settings().llm_base_url)
    if not url.hostname:
        raise SystemExit("LLM_BASE_URL has no host; refusing hosted calls")
    return str(url.hostname)


def label_prompt(claim: dict[str, str]) -> str:
    return (
        f"Evidence ({claim['chunk_id']}):\n{claim['chunk_text']}\n\n"
        f"Claim: {claim['claim']}\n\nRespond with JSON only."
    )


def draw_owner_sample(claims: list[dict[str, str]], claims_sha: str) -> None:
    rng = random.Random(SAMPLE_SEED)  # noqa: S311 - seeded reproducibility
    picked = rng.sample(range(len(claims)), SAMPLE_N)
    items = [
        {
            "index": i,
            "claim": claims[i]["claim"],
            "chunk_id": claims[i]["chunk_id"],
            "chunk_text": claims[i]["chunk_text"],
        }
        for i in sorted(picked)
    ]
    OWNER_SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    OWNER_SAMPLE.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "claims_sha256": claims_sha,
                "seed": SAMPLE_SEED,
                "note": "UNLABELLED owner sample: label each claim supported/unsupported "
                "by hand, using the labelled set's chunk_text for the evidence.",
                "items": items,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.info("owner sample: %d claims -> %s", len(items), OWNER_SAMPLE.relative_to(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="label only the first N claims")
    parser.add_argument("--sample-only", action="store_true", help="skip labelling; rewrite sample")
    args = parser.parse_args()

    settings = get_settings()
    host = named_host()
    model_name = settings.llm_model or "kimi-for-coding"
    claims_sha = hashlib.sha256(CLAIMS.read_bytes()).hexdigest()
    logger.info("named Kimi API host: %s (model %s)", host, model_name)
    append_log(
        {
            "ts": datetime.now(UTC).isoformat(),
            "step": "judge-calibration-v2",
            "change": "host-declaration",
            "split": "n/a",
            "decision": "named-host",
            "reason": f"one permitted non-localhost host for step 1: {host} "
            f"(model {model_name}); any other hosted host stops the run; "
            "$3.00 estimated-spend cap",
        }
    )

    claims: list[dict[str, str]] = json.loads(CLAIMS.read_text("utf-8"))
    n_supported = sum(1 for c in claims if c.get("kind") == "supported")
    n_unsupported = len(claims) - n_supported
    if n_supported != 75 or n_unsupported < 70:
        raise SystemExit(
            f"expected 75 supported + >= 70 unsupported, got {n_supported}+{n_unsupported}"
        )

    ledger = get_ledger(settings)
    grabber = HostGrabber()
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.addHandler(grabber)
    httpx_logger.setLevel(logging.INFO)

    if not args.sample_only:
        from pydantic_ai import Agent

        model = build_model(settings)
        agent: Agent[Any, str] = Agent(model, system_prompt=SYSTEM_PROMPT, output_type=str)

        labelled = 0
        errors = 0
        todo = claims if args.limit is None else claims[: args.limit]
        for index, claim in enumerate(todo):
            raw_path = RAW_DIR / f"{index:03d}.json"
            if raw_path.exists():
                labelled += 1
                continue
            if ledger.spend_usd >= ledger.budget_usd:
                logger.error("STOP: estimated spend $%s reached the $3.00 cap", ledger.spend_usd)
                break
            started = time.monotonic()
            try:
                result = agent.run_sync(label_prompt(claim), usage_limits=budget_limits(settings))
            except Exception as exc:  # broad: transport/provider failures vary
                errors += 1
                raw_path.write_text(
                    json.dumps({"index": index, "error": f"{type(exc).__name__}: {exc}"}, indent=2)
                    + "\n",
                    encoding="utf-8",
                )
                logger.error("claim %d: %s", index, exc)
                if errors >= MAX_CONSECUTIVE_ERRORS:
                    raise SystemExit(f"STOP: {errors} consecutive labelling errors") from exc
                continue
            errors = 0
            try:
                record = meter_result(result, model_name, settings)
            except BudgetExceededError as exc:
                logger.error("STOP: %s", exc)
                break
            elapsed = time.monotonic() - started
            parsed: dict[str, Any] = {}
            try:
                parsed = parse_json_block(str(result.output))
                if parsed.get("label") not in {"supported", "unsupported"}:
                    raise ValueError(f"bad label: {parsed.get('label')!r}")
            except (ValueError, json.JSONDecodeError) as exc:
                parsed = {"label": None, "reason": f"parse error: {exc}"}
            request_hosts = sorted({h for h in grabber.hosts if h})
            raw: dict[str, Any] = {
                "index": index,
                "chunk_id": claim["chunk_id"],
                "model": model_name,
                "usage": {
                    "input_tokens": record.input_tokens,
                    "output_tokens": record.output_tokens,
                    "reasoning_tokens": record.reasoning_tokens,
                },
                "cost_usd_est": str(record.spend_usd),
                "cumulative_usd_est": str(ledger.spend_usd),
                "latency_s": round(elapsed, 2),
                "request_hosts": request_hosts,
                "raw_response": str(result.output),
                "label": parsed.get("label"),
                "reason": parsed.get("reason"),
            }
            bad = [h for h in raw["request_hosts"] if h not in LOCAL_HOSTS and h != host]
            if bad:
                raise SystemExit(f"STOP: request to non-permitted host(s): {bad}")
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", "utf-8")
            append_log(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "step": "judge-calibration-v2",
                    "change": "label",
                    "split": "n/a",
                    "claim_index": index,
                    "chunk_id": claim["chunk_id"],
                    "model": model_name,
                    "tokens_in": record.input_tokens,
                    "tokens_out": record.output_tokens,
                    "cost_usd_est": str(record.spend_usd),
                    "cumulative_usd_est": str(ledger.spend_usd),
                    "decision": "labelled",
                    "label": parsed.get("label"),
                }
            )
            labelled += 1
            if labelled % 25 == 0:
                logger.info(
                    "labelled %d/%d; running estimated spend $%s",
                    labelled,
                    len(todo),
                    ledger.spend_usd,
                )

    done = sum(1 for p in RAW_DIR.glob("*.json") if "error" not in json.loads(p.read_text("utf-8")))
    if done < len(claims):
        logger.error(
            "STOP: %d/%d claims labelled; estimated spend $%s of $3.00 cap",
            done,
            len(claims),
            ledger.spend_usd,
        )
        return 1
    logger.info(
        "all %d claims labelled; total estimated spend $%s (cloud-equivalent, not billed)",
        done,
        ledger.spend_usd,
    )
    draw_owner_sample(claims, claims_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
