import pytest
from hypothesis import given
from hypothesis import strategies as st
from portfolio_core.dq import DQCheck, DQGateError, DQReport


def test_report_passes_when_all_checks_pass() -> None:
    r = DQReport(dataset="d", n_rows=100)
    r.add(DQCheck(name="a", passed=True))
    assert r.passed and r.n_failed == 0


def test_raise_if_failed_halts_loudly() -> None:
    r = DQReport(dataset="d", n_rows=100)
    r.add(DQCheck(name="bad", passed=False, detail="too many nulls"))
    with pytest.raises(DQGateError) as exc:
        r.raise_if_failed()
    assert "bad" in str(exc.value)
    assert exc.value.report is r


@given(st.floats(min_value=0, max_value=1), st.floats(min_value=0, max_value=1))
def test_null_rate_gate_boundary(null_rate: float, threshold: float) -> None:
    r = DQReport(dataset="d", n_rows=1000)
    r.check_null_rate("col", null_rate, threshold)
    (check,) = r.checks
    assert check.passed == (null_rate <= threshold)


def test_range_gate() -> None:
    r = DQReport(dataset="d", n_rows=10)
    r.check_range("x", min_observed=-5, max_observed=105, lo=0, hi=100)
    assert not r.passed


def test_freshness_gate() -> None:
    r = DQReport(dataset="d", n_rows=10)
    r.check_freshness("2026-01-01", "2026-06-01")
    assert not r.passed
