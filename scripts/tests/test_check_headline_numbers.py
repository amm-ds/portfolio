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


def test_known_drift_filter() -> None:
    assert headline._is_known("01-rag-agent: anything")
    assert headline._is_known("04-nlp-classification: anything")
    assert not headline._is_known("02-demand-forecasting: drift")
