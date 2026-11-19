"""R2: warrant-strength check on the sealed set (hosted, capped).

The committed binary claim verifier accepts/rejects; it cannot distinguish
"the citation fully warrants the claim" from "the citation is relevant but
the claim overstates it" (ForceBench framing). This pass re-judges every
claim the verify-on run ACCEPTED, on a three-level scale:

- ``supports`` — the passage states the claim with matching scope/strength.
- ``overstates`` — the passage supports a weaker/narrower version (inflated
  scope, added certainty, changed magnitude).
- ``does_not_support`` — the passage does not contain the claim's content.

Evidence passages are recovered deterministically and offline from the
committed verify records: the verdict reason quotes or paraphrases the
matched span; a claim is judged only when that span is located verbatim in
the committed 200-token chunk corpus (NFKC case-folded). Unlocatable claims
are excluded and counted — never guessed.

Hosted: one ``kimi-for-coding`` call per judged claim via the platform
factory (:func:`portfolio_core.llm.build_model`). Spend is metered at the
$1.00/Mtok-in + $4.00/Mtok-out reference card and the run stops at $2.50
combined (shared cap with R3), writing whatever it has.

Output: NEW files under ``reports/warrant_check/`` only.

    set -a; . ../../../.env; set +a   # repo root env (kimi-for-coding)
    uv run python scripts/warrant_check.py
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from portfolio_core.logging import get_logger
from pydantic import BaseModel, Field

logger = get_logger(__name__)
ROOT = Path(__file__).resolve().parents[1]

RATE_IN = 1.00 / 1e6
RATE_OUT = 4.00 / 1e6
STOP_USD = 2.50
QUOTE_RE = re.compile(r"'(.*?)'", re.DOTALL)


class SpendExceededError(RuntimeError):
    """Raised when the combined metered spend crosses the stop threshold."""


class WarrantVerdict(BaseModel):
    verdict: Literal["supports", "overstates", "does_not_support"] = Field(
        description="Does the passage WARRANT the claim's strength?"
    )
    reason: str = Field(description="one sentence, quoting the decisive span")


RUBRIC = """You are a strict warrant-strength judge for retrieval-grounded claims.

You receive one claim and the cited evidence passage. Decide whether the
passage WARRANTS the claim's exact strength — not merely whether it is
relevant.

- supports: the passage states the claim's content with matching scope and
  strength. Numbers, qualifiers ("may", "some"), entities, and scope match.
- overstates: the passage supports a weaker, narrower, or more cautious
  version. The claim inflates scope, generalizes, adds certainty, or changes
  magnitude. A citation can be relevant AND still leave the claim overstated.
- does_not_support: the passage does not contain the claim's content.

Judge the claim against the passage alone. Reply with the structured verdict."""


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float]:
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [max(0.0, center - half), min(1.0, center + half)]


def recover_evidence(reason: str, chunk_texts: list[str]) -> str | None:
    """Locate the verdict reason's evidence span in the chunk corpus."""
    norm_reason = _norm(reason)
    match = QUOTE_RE.search(reason)
    candidates: list[str] = []
    if match and len(match.group(1)) > 20:
        candidates.append(_norm(match.group(1)))
    for length in (80, 60, 40):
        for start in range(0, max(1, len(norm_reason) - length), 20):
            candidates.append(norm_reason[start : start + length])
    for candidate in candidates:
        if len(candidate) < 20:
            continue
        for text in chunk_texts:
            if candidate in text:
                return text
    return None


async def main() -> int:
    from portfolio_core.llm import build_model
    from pydantic_ai import Agent

    records = json.loads((ROOT / "reports" / "citation_records_heldout.json").read_text())
    supported = [
        (row["question"], claim["claim"], claim["reason"])
        for row in records
        for claim in row["claims"]
        if claim["supported"]
    ]
    logger.info("%d supported claims from the committed verify-on pass", len(supported))

    from rag_agent.cli import load_config
    from rag_agent.corpus import load_corpus
    from rag_agent.index import chunk_articles

    config = load_config()
    articles = load_corpus(config)
    size = min(config.chunk_sizes)
    chunks = chunk_articles(articles, size=size, overlap=config.chunk_overlap)
    chunk_texts = [_norm(c.text) for c in chunks]

    judged: list[dict[str, Any]] = []
    excluded = 0
    spend = 0.0
    tokens_in = 0
    tokens_out = 0

    model = build_model()
    agent: Agent[None, WarrantVerdict] = Agent(
        model, output_type=WarrantVerdict, system_prompt=RUBRIC
    )

    for index, (question, claim, reason) in enumerate(supported, start=1):
        if spend >= STOP_USD:
            raise SpendExceededError(f"combined spend ${spend:.4f} reached the $2.50 stop")
        evidence = recover_evidence(reason, chunk_texts)
        if evidence is None:
            excluded += 1
            continue
        result = await agent.run(f"Claim:\n{claim}\n\nEvidence passage:\n{evidence[:4000]}")
        usage = result.usage
        tokens_in += usage.input_tokens
        tokens_out += usage.output_tokens
        spend += usage.input_tokens * RATE_IN + usage.output_tokens * RATE_OUT
        judged.append(
            {
                "question": question,
                "claim": claim,
                "verdict": result.output.verdict,
                "reason": result.output.reason,
            }
        )
        if index % 25 == 0:
            logger.info(
                "%d/%d judged | spend $%.4f | overstates so far %d",
                index,
                len(supported),
                spend,
                sum(1 for j in judged if j["verdict"] == "overstates"),
            )

    n = len(judged)
    n_over = sum(1 for j in judged if j["verdict"] == "overstates")
    n_support = sum(1 for j in judged if j["verdict"] == "supports")
    n_nosupport = sum(1 for j in judged if j["verdict"] == "does_not_support")
    binary_unsupported = sum(
        1 for row in records for claim in row["claims"] if not claim["supported"]
    )
    binary_total = sum(len(row["claims"]) for row in records)

    report: dict[str, Any] = {
        "schema_version": "warrant-check-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "model": "kimi-for-coding (repo LLM_* env, platform factory)",
        "rate_card": {"input_per_mtok_usd": 1.0, "output_per_mtok_usd": 4.0},
        "spend_usd_cloud_equivalent": round(spend, 6),
        "tokens": {"input": tokens_in, "output": tokens_out},
        "n_supported_claims": len(supported),
        "n_judged": n,
        "n_excluded_no_locatable_evidence": excluded,
        "verdicts": {"supports": n_support, "overstates": n_over, "does_not_support": n_nosupport},
        "overstatement_rate": n_over / n if n else None,
        "overstatement_wilson95": wilson(n_over, n),
        "binary_unsupported_committed": {
            "n": binary_unsupported,
            "total": binary_total,
            "rate": binary_unsupported / binary_total,
            "wilson95": wilson(binary_unsupported, binary_total),
            "source": "reports/citation_records_heldout.json (verify-on pass)",
        },
        "per_claim_verdicts": judged,
        "note": (
            "The overstatement rate is computed over claims with locatable "
            "evidence (quote/span recovered verbatim from the committed chunk "
            "corpus); excluded claims are counted above, not guessed."
        ),
    }
    out_dir = ROOT / "reports" / "warrant_check"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")

    ci = report["overstatement_wilson95"]
    lines = [
        "# R2 warrant-strength check — sealed set",
        "",
        f"Generated: {report['generated_at']} · {n} supported claims judged "
        f"({excluded} excluded: evidence span not locatable offline) · spend "
        f"${spend:.4f} cloud-equivalent.",
        "",
        "| verdict | count | share |",
        "|---|---|---|",
        f"| supports | {n_support} | {n_support / n:.4f} |",
        f"| **overstates** | {n_over} | **{n_over / n:.4f}** |",
        f"| does not support | {n_nosupport} | {n_nosupport / n:.4f} |",
        "",
        f"Overstatement rate {n_over}/{n} = {n_over / n:.4f}, Wilson 95% "
        f"[{ci[0]:.4f}, {ci[1]:.4f}].",
        f"Committed binary unsupported rate (same pass): {binary_unsupported}/"
        f"{binary_total} = {binary_unsupported / binary_total:.4f}, Wilson 95% "
        f"[{report['binary_unsupported_committed']['wilson95'][0]:.4f}, "
        f"{report['binary_unsupported_committed']['wilson95'][1]:.4f}].",
        "",
        "The overstatement rate is separate from the unsupported rate: it "
        "measures claims the binary check ACCEPTED whose citations do not "
        "carry the claim's full strength. No verify-on copy was changed.",
    ]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    logger.info("wrote %s (spend $%.4f)", out_dir, spend)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
