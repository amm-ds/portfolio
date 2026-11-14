"""R7 local-judge calibration: acceptance gates from labels-by-construction.

Runs the local claim/answer judge against the calibration set built by
build_calibration_set.py (ground truth certain by construction) and reports
the R7 acceptance gates: claim false-acceptance <=5% (95% UCB <=10%),
false-rejection <=10%, Cohen's kappa >= 0.80, answer agreement >=85%,
repeat-run flips <=2% at the pinned configuration.

The judge uses its own prompt and model profile, separate from generation.
Fully local (Ollama) — $0 hosted spend.

    uv run python scripts/build_calibration_set.py   # once
    uv run python scripts/calibrate_judge.py --model qwen3:4b --repeat 2
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from portfolio_core.logging import get_logger
from pydantic import BaseModel, Field
from pydantic_ai.settings import ModelSettings
from rag_agent.local_models import ollama_available

logger = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / "data" / "calibration"

CLAIM_PROMPT = """You are a strict entailment judge for retrieval-grounded answers.

Question: {question}

Evidence:
{evidence}

Claim: {claim}

Decide whether the evidence fully supports the claim. Any fact, number, date,
or inference not present in the evidence makes the claim unsupported."""


class ClaimVerdict(BaseModel):
    supported: bool
    reason: str = Field(min_length=1)


@dataclass
class Rates:
    false_acceptance: float  # judge supported | label unsupported
    false_rejection: float  # judge unsupported | label supported
    kappa: float
    flips: float  # repeat-run verdict flips


def _wilson_ucb(p: float, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 0.0
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return min(1.0, center + half)


def _cohens_kappa(a: list[bool], b: list[bool]) -> float:
    n = len(a)
    if n == 0:
        return 0.0
    p_o = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    p_yes_a = sum(a) / n
    p_yes_b = sum(b) / n
    p_e = p_yes_a * p_yes_b + (1 - p_yes_a) * (1 - p_yes_b)
    return (p_o - p_e) / (1 - p_e) if p_e < 1.0 else 1.0


def run_claim_judge(model: str, cases: list[dict[str, Any]]) -> list[bool | None]:
    """One pinned pass over the claim cases with the local model."""
    import os

    os.environ["OLLAMA_MODEL"] = model
    from portfolio_core.llm import build_model
    from rag_agent.provider import model_settings_for_provider

    agent = Agent(
        build_model(),
        output_type=ClaimVerdict,
        system_prompt=(
            "You check whether claims are entailed by retrieved evidence. You are "
            "strict: unsupported means the evidence does not state it. You never "
            "use outside knowledge."
        ),
        model_settings=model_settings_for_provider(),
        retries={"output": 2},
    )
    out: list[bool | None] = []
    for case in cases:
        prompt = CLAIM_PROMPT.format(
            question=case["question"], evidence=case["evidence"], claim=case["claim"]
        )
        try:
            result = agent.run_sync(prompt)
            out.append(bool(result.output.supported))
        except Exception as exc:  # broad: one stubborn case must not kill the pass
            logger.warning("calibration case failed (%s); recording as judge error", exc)
            out.append(None)  # excluded from the rates, counted separately
    return out


def evaluate(model: str, repeat: int) -> dict[str, Any]:
    claims = [
        json.loads(line)
        for line in (CAL / "claims.jsonl").read_text().splitlines()
        if line.strip()
    ]
    answers = [
        json.loads(line)
        for line in (CAL / "answers.jsonl").read_text().splitlines()
        if line.strip()
    ]
    passes = [run_claim_judge(model, claims) for _ in range(repeat)]

    labels = [c["label"] == "supported" for c in claims]
    judged0 = passes[0]
    paired = [(j, lab) for j, lab in zip(judged0, labels, strict=True) if j is not None]
    n_errors = len(judged0) - len(paired)
    fa = [1.0 for j, lab in paired if (not lab and j)]
    fr = [1.0 for j, lab in paired if (lab and not j)]
    n_unsup = sum(1 for _, lab in paired if not lab)
    n_sup = sum(1 for _, lab in paired if lab)
    fa_rate = sum(fa) / max(n_unsup, 1)
    fr_rate = sum(fr) / max(n_sup, 1)
    flip_pairs = [(a, b) for a, b in zip(*passes) if a is not None and b is not None]
    flips = (
        sum(1 for a, b in flip_pairs if a != b) / len(claims) if repeat > 1 and flip_pairs else 0.0
    )
    kappa = _cohens_kappa([bool(j) for j in judged0 if j is not None], [lab for j, lab in paired])

    # Answer-level: judge each answer draft for faithfulness vs its label.
    ans_judged: list[bool | None] = []
    for case in answers:
        judged_supported = run_claim_judge(model, [
            {
                "question": case["question"],
                "claim": case["answer"],
                "evidence": case["evidence"],
            }
        ])[0]
        ans_judged.append(judged_supported)
    ans_labels = [c["label"] == "correct" for c in answers]
    ans_paired = [(a, b) for a, b in zip(ans_judged, ans_labels, strict=True) if a is not None]
    ans_agreement = (
        sum(1 for a, b in ans_paired if a == b) / len(ans_paired) if ans_paired else 0.0
    )

    gates = {
        "claim_false_acceptance_rate": round(fa_rate, 4),
        "claim_false_acceptance_ucb95": round(_wilson_ucb(fa_rate, len(claims)), 4),
        "claim_false_rejection_rate": round(fr_rate, 4),
        "cohens_kappa": round(kappa, 4),
        "answer_agreement": round(ans_agreement, 4),
        "repeat_flip_rate": round(flips, 4),
        "n_judge_errors": n_errors,
        "n_claims": len(claims),
        "n_answers": len(answers),
        "repeat_runs": repeat,
        "model": model,
        "ACCEPTS": bool(
            fa_rate <= 0.05
            and _wilson_ucb(fa_rate, len(claims)) <= 0.10
            and fr_rate <= 0.10
            and kappa >= 0.80
            and ans_agreement >= 0.85
            and flips <= 0.02
        ),
    }
    return gates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--repeat", type=int, default=2)
    args = parser.parse_args()

    if not ollama_available():
        raise SystemExit("ollama not reachable — start the local server first")
    gates = evaluate(args.model, args.repeat)
    out_dir = ROOT / "reports" / "judge_calibration"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "results.json"
    out.write_text(json.dumps(gates, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(gates, indent=2))
    print(f"written: {out}")


if __name__ == "__main__":
    main()
