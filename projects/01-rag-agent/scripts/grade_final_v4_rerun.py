"""Grade the final_v4 rerun: replication judge + cross-family read (grade pass 5, phase 2c).

The final_v4 rerun (``reports/final_v4_rerun/``, run namespace
``final_v4-432d6b705715``) re-answered the 120 consumed final_v3 questions
with the phase-2b wiring that persists each answer and its per-claim verdicts.
This script grades those persisted answers twice:

1. **Replication judge** (``judge_replication.json``): the run's own in-loop
   rubric judging — ``LLMRubricJudge`` with ``RUBRIC_SYSTEM_PROMPT``
   (kimi-for-coding), the EXACT committed final_v3 judging path (same model,
   same prompt, same ``_judge_context`` construction). No new hosted calls:
   the verdicts are read from the fresh traces. The F1 delta vs the committed
   0.9091 therefore measures REGENERATION VARIANCE ONLY (same family, same
   prompt) — never family bias.
2. **Cross-family read** (``judge_cross_family.json``): local Ollama
   ``qwen2.5:3b`` (Qwen family, $0) re-judges the same persisted answers
   through the EXACT claim-judge prompt path of
   ``scripts/cross_family_judge.py`` (imported verbatim: ``SYSTEM_PROMPT`` +
   ``label_prompt``, temperature 0, seed 44) — the judge calibrated 28/30
   against owner labels in E8. Each surviving claim of an answered question is
   judged against the question's production retrieval context
   (``retriever.search(question, top_k=config.top_k)``, rebuilt locally and
   deterministically; the agent-cited union the rubric judge saw is not
   persisted, so the retrieved top-k is the reconstructable evidence base).
   An answer is supported iff EVERY judged claim is supported. This is a
   3B local model: a WEAK-EVIDENCE cross-family read, never a strong one.

``agreement.json`` carries per-judge answer-level F1 (the exact
``scripts/run_e2e_eval.py --summarize`` definition via ``summarize_rows``),
pairwise agreement + Cohen's kappa between the two judges, and the F1 deltas
vs the committed 0.9091. ``meter.json`` records generation + judging spend
against the $2.00 phase cap.

If Ollama or the qwen2.5:3b digest is unavailable, only the replication judge
is written and the cross-family read is reported as not run.

    uv run python scripts/grade_final_v4_rerun.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cross_family_judge import (  # noqa: E402  (exact prompt path, judge-only)
    ENDPOINT,
    MODEL,
    SEED,
    SYSTEM_PROMPT,
    cohens_kappa,
    label_prompt,
    parse_json_block,
    post,
    wilson,
)
from run_e2e_eval import summarize_rows  # noqa: E402  (the committed F1 definition)

REPORTS_DIR = ROOT / "reports" / "final_v4_rerun"
TRACES = REPORTS_DIR / "question_traces_heldout.json"
METRICS = REPORTS_DIR / "metrics.json"
RAW_DIR = REPORTS_DIR / "raw" / "cross_family"
RUN_MANIFEST = ROOT / "reports" / "runs" / "final_v4-432d6b705715" / "manifest.json"
COMMITTED_F1 = 0.9091
COMMITTED_F1_SOURCE = "reports/final_v3_e2e/f1_summary.json"
HOSTED_BUDGET_CAP_USD = 2.00
SURVIVING_STATES = {"accepted_original", "accepted_repaired"}
TAGS_ENDPOINT = "http://127.0.0.1:11434/api/tags"
VERSION_ENDPOINT = "http://127.0.0.1:11434/api/version"


def load_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(TRACES.read_text("utf-8"))
    if len(rows) != 120:
        raise SystemExit(f"expected 120 final_v4 rows, got {len(rows)}")
    return rows


def f1_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = summarize_rows(rows)
    return {
        "n_questions": summary["n_questions"],
        "tp": summary["tp"],
        "fp": summary["fp"],
        "tn": summary["tn"],
        "fn": summary["fn"],
        "precision": summary["precision"],
        "recall": summary["recall"],
        "f1": summary["f1"],
        "overall_accuracy": summary["overall_accuracy"],
        "errors": summary["errors"],
        "f1_definition": "scripts/run_e2e_eval.py summarize_rows (committed definition)",
        "delta_f1_vs_committed_0.9091": round(summary["f1"] - COMMITTED_F1, 4),
    }


def write_replication(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The run's in-loop kimi rubric verdicts = the committed judging path."""
    per_question = [
        {
            "question": r["question"],
            "expected_behavior": r["expected_behavior"],
            "verdict": r["verdict"],
            "faithfulness": r["faithfulness"],
            "abstained": r["abstained"],
            "retrieved_relevant": r["retrieved_relevant"],
            "cited_relevant": r["cited_relevant"],
        }
        for r in rows
    ]
    result: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "judge": {
            "model": "kimi-for-coding",
            "family": "Moonshot/Kimi (same family as the committed final_v3 judge)",
            "path": "in-loop LLMRubricJudge, RUBRIC_SYSTEM_PROMPT, over "
            "_judge_context(retrieved top-k union agent-cited chunks) — the exact "
            "committed final_v3 judging path; verdicts read from the fresh traces, "
            "no new hosted calls",
            "measures": "regeneration variance ONLY (same family, same prompt); "
            "NOT a family-bias measurement",
        },
        "f1": f1_block(rows),
        "committed_f1": COMMITTED_F1,
        "committed_f1_source": COMMITTED_F1_SOURCE,
        "per_question": per_question,
    }
    (REPORTS_DIR / "judge_replication.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    return result


def ollama_meta() -> dict[str, str] | None:
    """qwen2.5:3b digest/family, or None when Ollama/the model is unavailable."""
    import urllib.request

    try:
        with urllib.request.urlopen(TAGS_ENDPOINT, timeout=10) as resp:
            tags = dict(json.load(resp))
    except Exception as exc:
        print(f"cross-family: Ollama unavailable ({exc}); read not run")
        return None
    for entry in tags.get("models", []):
        if entry.get("name") == MODEL:
            details = entry.get("details", {})
            return {
                "model": MODEL,
                "digest": str(entry.get("digest", "")),
                "family": str(details.get("family", "")),
                "parameter_size": str(details.get("parameter_size", "")),
                "quantization": str(details.get("quantization_level", "")),
            }
    print(f"cross-family: model {MODEL} not installed; read not run")
    return None


def judge_claim(
    claim_text: str, evidence_label: str, evidence_text: str, slot: str, meta: dict[str, str]
) -> dict[str, Any]:
    """One claim through the exact cross_family_judge prompt path; raw persisted."""
    raw_path = RAW_DIR / f"{slot}.json"
    if raw_path.exists():
        return dict(json.loads(raw_path.read_text("utf-8")))
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": label_prompt(
                    {"chunk_id": evidence_label, "chunk_text": evidence_text, "claim": claim_text}
                ),
            },
        ],
        "stream": False,
        "options": {"temperature": 0, "seed": SEED, "num_predict": 512},
    }
    started = time.monotonic()
    body = post(payload, ENDPOINT)
    elapsed = time.monotonic() - started
    content = str(body.get("message", {}).get("content", ""))
    try:
        parsed = parse_json_block(content)
        if parsed.get("label") not in {"supported", "unsupported"}:
            raise ValueError(f"bad label: {parsed.get('label')!r}")
    except (ValueError, json.JSONDecodeError) as exc:
        parsed = {"label": None, "reason": f"parse error: {exc}"}
    record: dict[str, Any] = {
        "slot": slot,
        "model": meta["model"],
        "digest": meta["digest"],
        "claim": claim_text,
        "evidence_chunk_ids": evidence_label,
        "usage": {
            "input_tokens": int(body.get("prompt_eval_count", 0)),
            "output_tokens": int(body.get("eval_count", 0)),
        },
        "cost_usd_est": "0.0",
        "latency_s": round(elapsed, 2),
        "request_hosts": ["127.0.0.1"],
        "raw_response": content,
        "label": parsed.get("label"),
        "reason": parsed.get("reason"),
    }
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", "utf-8")
    return record


def cross_family_verdict(row: dict[str, Any], answer_supported: bool | None) -> str:
    """classify_question (reporting.py) with the qwen answer-level label in
    place of the rubric faithfulness test; an unjudged answer is never correct
    (the NaN guard's analog)."""
    if not row["format_ok"]:
        return "budget-terminated" if row["budget_terminated"] else "format-failure"
    if row["expected_behavior"] == "abstain":
        return "correct" if row["abstained"] else "unsupported-claim"
    if not row["retrieved_relevant"]:
        return "retrieval-miss"
    if row["abstained"]:
        return "empty-answer"
    if row["n_surviving_claims"] is not None and row["n_surviving_claims"] == 0:
        return "empty-answer"
    if answer_supported is None:
        return "unsupported-claim"
    return "correct" if answer_supported else "unsupported-claim"


def needs_judging(row: dict[str, Any]) -> bool:
    return (
        row["format_ok"]
        and row["expected_behavior"] == "answer"
        and not row["abstained"]
        and row["retrieved_relevant"]
        and not (row["n_surviving_claims"] is not None and row["n_surviving_claims"] == 0)
        and bool(row.get("answer"))
    )


def write_cross_family(rows: list[dict[str, Any]]) -> dict[str, Any]:
    meta = ollama_meta()
    if meta is None:
        result = {
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "not_run",
            "reason": "local Ollama qwen2.5:3b unavailable",
            "judge": {"model": MODEL, "endpoint": ENDPOINT},
        }
        (REPORTS_DIR / "judge_cross_family.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", "utf-8"
        )
        return result

    # Evidence: the production retrieval context (top config.top_k chunks),
    # rebuilt locally and deterministically — the reconstructable evidence base.
    from rag_agent.cli import load_config
    from rag_agent.evaluate import EMBEDDING_ARMS, query_prefixed
    from rag_agent.index import CrossEncoderReranker, Retriever, SentenceTransformerEmbedder

    config = load_config()
    chosen = config.retrieval_best
    if chosen is None:
        raise SystemExit("config.retrieval_best is required")
    arm = next(a for a in EMBEDDING_ARMS if a[0] == chosen.embedding_slug)
    embed_fn = SentenceTransformerEmbedder(chosen.embedding_model)
    retriever = Retriever.from_index_dir(
        config,
        config.index_path(chosen.chunk_size),
        embed_fn,
        CrossEncoderReranker(config.reranker_model) if chosen.rerank else None,
        query_prefixed(embed_fn, arm[2]),
    )

    per_question: list[dict[str, Any]] = []
    rejudged: list[dict[str, Any]] = []
    n_calls = n_parse_fail = 0
    for qi, row in enumerate(rows):
        answer_supported: bool | None = None
        judged_claims: list[dict[str, Any]] = []
        if needs_judging(row):
            evidence = retriever.search(row["question"], top_k=config.top_k)
            chunk_ids = [c.chunk_id for c in evidence]
            texts = []
            for cid in chunk_ids:
                chunk = retriever.get_chunk(cid)
                texts.append(chunk.text if chunk is not None else "")
            evidence_label = "+".join(chunk_ids)
            evidence_text = "\n\n".join(texts)
            claims = [
                c["claim"]
                for c in (row.get("claims") or [])
                if c.get("terminal_state") in SURVIVING_STATES
            ]
            if not claims:  # answered but no surviving-claim records: judge the answer whole
                claims = [str(row["answer"])]
            labels: list[str | None] = []
            for ci, claim_text in enumerate(claims):
                slot = f"q{qi:03d}_c{ci}"
                rec = judge_claim(claim_text, evidence_label, evidence_text, slot, meta)
                n_calls += 1
                labels.append(rec["label"])
                judged_claims.append(
                    {"claim": claim_text, "qwen_label": rec["label"], "reason": rec["reason"]}
                )
            n_parse_fail += sum(1 for lab in labels if lab is None)
            if all(lab is not None for lab in labels):
                answer_supported = all(lab == "supported" for lab in labels)
        verdict = cross_family_verdict(row, answer_supported)
        rejudged.append({**row, "verdict": verdict})
        per_question.append(
            {
                "question": row["question"],
                "expected_behavior": row["expected_behavior"],
                "judged": needs_judging(row),
                "qwen_answer_supported": answer_supported,
                "verdict": verdict,
                "replication_verdict": row["verdict"],
                "judged_claims": judged_claims,
            }
        )

    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "scored",
        "judge": {
            **meta,
            "endpoint": ENDPOINT,
            "temperature": 0,
            "seed": SEED,
            "family_note": "Qwen family (Alibaba) vs the committed Moonshot/Kimi judge — a "
            "cross-family read by a LOCAL 3B model: weak evidence, never a strong one",
        },
        "prompt_path": "scripts/cross_family_judge.py SYSTEM_PROMPT + label_prompt "
        "(imported verbatim; the E8 path calibrated 28/30 vs owner labels)",
        "evidence": "production retrieval context retriever.search(question, "
        "top_k=config.top_k) rebuilt locally; answer supported iff EVERY surviving "
        "claim is supported",
        "n_questions": len(rows),
        "n_judged": sum(1 for q in per_question if q["judged"]),
        "n_judge_calls": n_calls,
        "n_parse_failures": n_parse_fail,
        "f1": f1_block(rejudged),
        "committed_f1": COMMITTED_F1,
        "per_question": per_question,
    }
    (REPORTS_DIR / "judge_cross_family.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    return result


def write_agreement(
    rows: list[dict[str, Any]], replication: dict[str, Any], cross_family: dict[str, Any]
) -> dict[str, Any]:
    rep_f1 = replication["f1"]
    result: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "committed_f1": COMMITTED_F1,
        "committed_f1_source": COMMITTED_F1_SOURCE,
        "per_judge": {
            "replication_kimi_rubric": {
                "f1": rep_f1["f1"],
                "precision": rep_f1["precision"],
                "recall": rep_f1["recall"],
                "delta_f1_vs_committed": rep_f1["delta_f1_vs_committed_0.9091"],
                "reads": "regeneration variance (same family, same prompt as committed)",
            },
        },
    }
    if cross_family.get("status") != "scored":
        result["cross_family"] = {"status": "not_run", "reason": cross_family.get("reason")}
        result["outcome_rule"] = {
            "rule": "kappa >= 0.6 and F1 within 0.03 of 0.9091",
            "evaluable": False,
            "reason": "cross-family read not run",
        }
    else:
        cf_f1 = cross_family["f1"]
        result["per_judge"]["cross_family_qwen2.5_3b"] = {
            "f1": cf_f1["f1"],
            "precision": cf_f1["precision"],
            "recall": cf_f1["recall"],
            "delta_f1_vs_committed": cf_f1["delta_f1_vs_committed_0.9091"],
            "reads": "weak-evidence cross-family read (local 3B model)",
        }
        rep_labels = [r["verdict"] == "correct" for r in rows]
        cf_labels = [q["verdict"] == "correct" for q in cross_family["per_question"]]
        rep_bin = ["correct" if x else "not-correct" for x in rep_labels]
        cf_bin = ["correct" if x else "not-correct" for x in cf_labels]
        n = len(rep_bin)
        agree = sum(1 for a, b in zip(rep_bin, cf_bin, strict=True) if a == b)
        kappa = cohens_kappa(rep_bin, cf_bin)
        judged = [
            (a, b)
            for a, b, q in zip(rep_bin, cf_bin, cross_family["per_question"], strict=True)
            if q["judged"]
        ]
        judged_kappa = None
        if judged:
            judged_kappa = round(cohens_kappa([a for a, _ in judged], [b for _, b in judged]), 4)
        result["pairwise"] = {
            "n_questions": n,
            "verdict_agreement": round(agree / n, 4),
            "verdict_agreement_wilson95": [round(x, 6) for x in wilson(agree, n)],
            "cohens_kappa": round(kappa, 4),
            "answered_subset": {
                "n": len(judged),
                "verdict_agreement": round(sum(1 for a, b in judged if a == b) / len(judged), 4)
                if judged
                else None,
                "cohens_kappa": judged_kappa,
            },
        }
        f1_delta = round(rep_f1["f1"] - COMMITTED_F1, 4)
        result["outcome_rule"] = {
            "rule": "kappa >= 0.6 and F1 within 0.03 of 0.9091 (pass-5 plan, phase 2c)",
            "kappa": round(kappa, 4),
            "replication_f1": rep_f1["f1"],
            "replication_delta_vs_committed": f1_delta,
            "within_0.03": abs(f1_delta) <= 0.03,
            "passed": bool(kappa >= 0.6 and abs(f1_delta) <= 0.03),
            "evidence_strength": "the kappa leg is a WEAK-evidence cross-family read "
            "(local qwen2.5:3b); the replication leg is same-family and measures "
            "regeneration variance only",
        }
    (REPORTS_DIR / "agreement.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    return result


def write_meter(cross_family: dict[str, Any]) -> dict[str, Any]:
    generation_spend = 0.0
    hosts: set[str] = set()
    if METRICS.exists():
        detail = json.loads(METRICS.read_text("utf-8")).get("detail", {})
        for payload in detail.values():
            meter = payload.get("meter", {})
            if meter.get("active"):
                generation_spend += float(meter["total"]["spend_usd"])
    manifest_spend = 0.0
    if RUN_MANIFEST.exists():
        manifest_spend = float(
            json.loads(RUN_MANIFEST.read_text("utf-8")).get("cumulative_spend_usd", 0.0)
        )
    rows_path = RUN_MANIFEST.parent / "rows.jsonl"
    if rows_path.exists():
        for line in rows_path.read_text("utf-8").splitlines():
            if line.strip():
                hosts.update(json.loads(line).get("hosts", []))
    qwen_tokens = {"input": 0, "output": 0}
    if RAW_DIR.exists():
        for path in RAW_DIR.glob("*.json"):
            rec = json.loads(path.read_text("utf-8"))
            qwen_tokens["input"] += int(rec["usage"]["input_tokens"])
            qwen_tokens["output"] += int(rec["usage"]["output_tokens"])
    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "hosted_budget_cap_usd": HOSTED_BUDGET_CAP_USD,
        "generation": {
            "spend_usd_metered": round(generation_spend, 6),
            "spend_usd_checkpoint_manifest": round(manifest_spend, 6),
            "host": "api.kimi.com (kimi-for-coding)",
            "request_hosts": sorted(hosts),
        },
        "judging": {
            "replication": {"spend_usd": 0.0, "note": "verdicts read from the fresh traces"},
            "cross_family": {
                "spend_usd": 0.0,
                "status": cross_family.get("status"),
                "qwen_tokens": qwen_tokens,
                "request_hosts": ["127.0.0.1"],
            },
        },
        "total_hosted_spend_usd": round(max(generation_spend, manifest_spend), 6),
        "under_cap": max(generation_spend, manifest_spend) <= HOSTED_BUDGET_CAP_USD,
    }
    (REPORTS_DIR / "meter.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    return result


def main() -> int:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")  # local embedding loads stay offline
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    rows = load_rows()
    replication = write_replication(rows)
    rep_f1 = replication["f1"]
    print(f"replication F1: {rep_f1['f1']} (delta {rep_f1['delta_f1_vs_committed_0.9091']:+})")
    cross_family = write_cross_family(rows)
    if cross_family.get("status") == "scored":
        print(
            f"cross-family F1: {cross_family['f1']['f1']} "
            f"(judged {cross_family['n_judged']}/{cross_family['n_questions']}, "
            f"parse failures {cross_family['n_parse_failures']})"
        )
    agreement = write_agreement(rows, replication, cross_family)
    meter = write_meter(cross_family)
    print(json.dumps(agreement["outcome_rule"], indent=2))
    print(f"total hosted spend: ${meter['total_hosted_spend_usd']} of ${HOSTED_BUDGET_CAP_USD} cap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
