"""Generator coverage: the summary module derives from the committed report only."""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "gen_agent_eval_summary",
    Path(__file__).resolve().parents[1] / "gen_agent_eval_summary.py",
)
gen = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(gen)

FIXTURE = """# agent_chat_suite — eval report

Model: `fake-model`

| case | kind | grader | verdict |
|---|---|---|---|
| alpha [1/2] | answer | AnswerKeywords | pass |
| alpha [2/2] | answer | AnswerKeywords | fail |
| beta [1/2] | refuse | RefusalGraceful | pass |

Passed 2/3 grader assertions.
"""


def test_parse_counts_per_kind_and_totals(tmp_path: Path) -> None:
    report = tmp_path / "evals.md"
    report.write_text(FIXTURE, encoding="utf-8")
    summary = gen.parse_report(report)
    assert summary["model"] == "fake-model"
    assert summary["cases"] == 2
    assert summary["repetitions"] == 2
    assert summary["executions"] == 4
    assert summary["assertions"] == 3
    assert summary["passed"] == 2
    assert summary["report_total"] == (2, 3)
    by_kind = {k["kind"]: k for k in summary["by_kind"]}
    assert by_kind["answer"] == {"kind": "answer", "assertions": 2, "passed": 1}
    assert by_kind["refuse"] == {"kind": "refuse", "assertions": 1, "passed": 1}


def test_parse_real_committed_report() -> None:
    summary = gen.parse_report(gen.REPORT)
    assert summary["assertions"] == 108
    assert summary["passed"] == 108
    assert summary["executions"] == 48
    assert summary["report_total"] == (108, 108)
    assert sum(k["assertions"] for k in summary["by_kind"]) == 108


def test_render_is_deterministic(tmp_path: Path) -> None:
    report = tmp_path / "evals.md"
    report.write_text(FIXTURE, encoding="utf-8")
    a = gen.render(gen.parse_report(report))
    b = gen.render(gen.parse_report(report))
    assert a == b
    assert '"fake-model"' in a
