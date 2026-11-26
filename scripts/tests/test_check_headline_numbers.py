"""Drift-check coverage: a stale headline is flagged, a clean claim passes."""

import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "check_headline_numbers",
    Path(__file__).resolve().parents[1] / "check_headline_numbers.py",
)
headline = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(headline)


def _fixture_project(root: Path, *, drift: bool) -> None:
    """A minimal fake project whose README claims a headline number."""
    project = root / "projects" / "99-fixture"
    (project / "reports").mkdir(parents=True)
    value = 999.0 if drift else 42.0
    (project / "reports" / "metrics.json").write_text(
        json.dumps({"headline": {"value": value}}), encoding="utf-8"
    )
    (project / "README.md").write_text(f"headline {_fmt_expected(value)}\n", encoding="utf-8")
    (project / "story.yaml").write_text(
        f"project_id: 99-fixture\nshort_version: {_fmt_expected(value)}\n",
        encoding="utf-8",
    )


def _fmt_expected(value: float) -> str:
    return f"{value:,.0f}"


def test_clean_claim_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture_project(tmp_path, drift=False)
    claim = {
        "project": "99-fixture",
        "label": "fixture headline",
        "values": lambda: ["42"],
        "surfaces": ["README.md", "story.yaml"],
    }
    monkeypatch.setattr(headline, "ROOT", tmp_path)
    assert headline.check_claim(claim) == []


def test_stale_headline_is_flagged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture_project(tmp_path, drift=True)
    claim = {
        "project": "99-fixture",
        "label": "fixture headline",
        "values": lambda: ["42"],
        "surfaces": ["README.md"],
    }
    monkeypatch.setattr(headline, "ROOT", tmp_path)
    failures = headline.check_claim(claim)
    assert len(failures) == 1
    assert "'42' not found" in failures[0]


def test_broken_source_reports_instead_of_tracing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    claim = {
        "project": "99-fixture",
        "label": "fixture headline",
        "values": lambda: (_ for _ in ()).throw(KeyError("metrics")),
        "surfaces": ["README.md"],
    }
    monkeypatch.setattr(headline, "ROOT", tmp_path)
    failures = headline.check_claim(claim)
    assert len(failures) == 1
    assert "could not derive" in failures[0]


def test_known_drift_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(headline, "KNOWN_DRIFT", {"uncovered:99-fixture"})
    assert headline._is_known("99-fixture: anything")
    assert not headline._is_known("01-rag-agent: drift")
    assert not headline._is_known("02-demand-forecasting: drift")


def test_m04_is_covered_by_its_committed_cascade_record() -> None:
    """04 is no longer registered as uncovered; its claim verifies."""
    assert set() == headline.KNOWN_DRIFT
    assert headline._m04() == ["0.9529", "0.9539", "0.023671"]
    claim = next(c for c in headline.CLAIMS if c["project"] == "04-nlp-classification")
    assert headline.check_claim(claim) == []


def test_m01_derives_final_v3_headline_from_committed_reports() -> None:
    """The 01 claim is anchored to committed final_v3 artifacts, not hard-coded."""
    assert headline._m01() == ["0.9091", "0.946"]


def test_m01_claim_verifies_against_real_repo() -> None:
    """The 01-rag-agent claim (README + story.yaml) matches its report sources."""
    claim = next(c for c in headline.CLAIMS if c["project"] == "01-rag-agent")
    assert claim["label"] == "final_v3 F1 + promoted S3 recall@5"
    assert headline.check_claim(claim) == []


def test_m15_derives_negative_primary_result_from_sealed_metrics() -> None:
    """The pricing card must retain the measured loss against B1."""
    assert headline._m15() == ["0.5120", "-1.86"]


def test_m15_claim_verifies_against_real_repo() -> None:
    """README and article both preserve the sealed RL result and P1 lift."""
    claim = next(c for c in headline.CLAIMS if c["project"] == "15-dynamic-pricing-rl")
    assert claim["label"] == "sealed RL mean + relative lift versus B1"
    assert headline.check_claim(claim) == []


def test_m10_reads_paired_baseline_intervals_from_committed_report() -> None:
    """The 10 headline CI is gated, read from the committed report.html."""
    assert headline._m10() == [
        "2,812",
        "42,613",
        "+$718",
        "+$4,767",
        "\u2212$13,125",
        "\u2212$5,808",
    ]


def test_m10_metrics_ci_matches_the_report_source() -> None:
    """The paired intervals are persisted in metrics.json analysis.ci too."""
    assert headline._m10_metrics_ci() == ["+$718", "+$4,767", "\u2212$13,125", "\u2212$5,808"]
    assert headline._m10_metrics_ci() == headline._m10()[2:]


def test_m10_metrics_ci_claim_verifies_against_real_repo() -> None:
    """README and article carry the intervals gated from metrics.json."""
    claim = next(
        c
        for c in headline.CLAIMS
        if c["project"] == "10-uplift-experimentation" and c["values"] is headline._m10_metrics_ci
    )
    assert headline.check_claim(claim) == []


def test_m10_claim_verifies_against_real_repo() -> None:
    """README and article both carry the delta and both paired intervals."""
    claim = next(c for c in headline.CLAIMS if c["project"] == "10-uplift-experimentation")
    assert headline.check_claim(claim) == []


def test_root_relative_surface_is_checked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("Pinned: WRMSSE 0.6161\n", encoding="utf-8")
    claim = {
        "project": "99-fixture",
        "label": "root surface",
        "values": lambda: ["0.6211"],
        "surfaces": ["//docs/index.md"],
    }
    monkeypatch.setattr(headline, "ROOT", tmp_path)
    failures = headline.check_claim(claim)
    assert len(failures) == 1 and "'0.6211' not found" in failures[0]


def test_m02_pinned_and_origin_range_verify_against_real_repo() -> None:
    assert headline._m02_pinned() == ["ensemble official WRMSSE 0.6211"]
    assert headline._m02_origins() == ["`24%` to `42%`"]
    for claim in headline.CLAIMS:
        if claim["values"] in (headline._m02_pinned, headline._m02_origins):
            assert headline.check_claim(claim) == []
