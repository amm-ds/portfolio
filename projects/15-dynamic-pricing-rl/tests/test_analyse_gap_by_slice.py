"""Tests for the grade-pass-6 gap-by-slice analysis (synthetic fixtures only)."""

import json
from pathlib import Path

import pytest
from dynamic_pricing import analyse_gap_by_slice as mod


def _fixture_payload(n: int = 60) -> dict:
    """60 episodes across three elasticity bands and three rho levels."""
    specs, rl, b1 = [], [], []
    for i in range(n):
        band = i % 3  # 0: least sensitive, 1: mid, 2: most sensitive
        specs.append({"epsilon": -(0.5 + band * 1.5), "rho": [0.7, 1.0, 1.3][band]})
        # least-sensitive: RL badly behind; most-sensitive: near tie
        rl.append([-2.0, -1.0, 0.0][band])
        b1.append(-1.0)
    return {
        "sets": {
            "test": {
                "specs": specs,
                "policies": {
                    "RL": {"normalised_profit": rl},
                    "B1": {"normalised_profit": b1},
                },
            }
        }
    }


def _write_reports(tmp_path: Path, payload: dict, n_reads: int = 3) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "test_episodes.json").write_text(json.dumps(payload))
    (reports / "sealed_access.json").write_text(json.dumps([{}] * n_reads))


def test_terciles_and_win_share_on_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_reports(tmp_path, _fixture_payload())
    monkeypatch.setattr(mod, "REPORTS", tmp_path / "reports")
    result = mod.analyse()
    # fixture: 20 episodes per band; least-sensitive band loses by 1.0,
    # mid ties, most-sensitive band wins by 1.0
    assert result["by_elasticity_tercile"]["low"]["mean_gap"] == pytest.approx(-1.0)
    assert result["by_elasticity_tercile"]["mid"]["mean_gap"] == pytest.approx(0.0)
    assert result["by_elasticity_tercile"]["high"]["mean_gap"] == pytest.approx(1.0)
    # RL > B1 exactly on the most-sensitive third
    assert result["rl_win_share"] == pytest.approx(20 / 60)
    assert result["n_episodes"] == 60
    assert result["resamples_below_zero"] >= 0
    assert len(result["elasticity_cuts_abs_epsilon"]) == 2


def test_refuses_when_sealed_log_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "REPORTS", tmp_path / "reports")
    with pytest.raises(SystemExit, match="sealed access log missing"):
        mod.analyse()


def test_refuses_when_sealed_log_has_more_than_three_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_reports(tmp_path, _fixture_payload(), n_reads=4)
    monkeypatch.setattr(mod, "REPORTS", tmp_path / "reports")
    with pytest.raises(SystemExit, match="> 3"):
        mod.analyse()


def test_committed_analysis_key_recomputes_identically() -> None:
    """The committed metrics.json analysis block must equal a fresh recompute
    (outside the script's provenance fields)."""
    committed = json.loads((mod.REPORTS / "metrics.json").read_text())["analysis"]["gap_by_slice"]
    fresh = mod.analyse()
    assert fresh["rl_win_share"] == committed["rl_win_share"]
    assert fresh["resamples_below_zero"] == committed["resamples_below_zero"]
    assert fresh["elasticity_cuts_abs_epsilon"] == pytest.approx(
        committed["elasticity_cuts_abs_epsilon"]
    )
    for name in ("low", "mid", "high"):
        assert fresh["by_elasticity_tercile"][name]["mean_gap"] == pytest.approx(
            committed["by_elasticity_tercile"][name]["mean_gap"]
        )
        assert fresh["by_elasticity_tercile"][name]["ci95"] == pytest.approx(
            committed["by_elasticity_tercile"][name]["ci95"]
        )
