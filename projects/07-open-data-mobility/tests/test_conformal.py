"""Split-conformal arm: offsets, stratum assignment, before/after coverage."""

import polars as pl
from mobility.conformal import conformal_offset, evaluate_conformal


def _frame() -> pl.DataFrame:
    """Two zones with opposite coverage errors across two half-windows.

    The over-covered zone carries distinct scores so the conformal order
    statistic can actually exclude rows (a constant-score stratum is
    conservative by construction and stays at 100% — also correct, just not
    what this test demonstrates).
    """
    rows = []
    for i in range(80):
        half_ts = f"2024-10-{(i // 48) + 1}T{i % 24}:00:00"
        # sparse: band too tight (y=10 > q90=9.5) -> 0% before
        rows.append(
            {
                "zone_id": 1,
                "ts": half_ts,
                "y_true": 10.0,
                "y_gbm_tuned": 9.0,
                "y_p90_tuned": 9.5,
            }
        )
        # over-covered: q90 far above a ramp of actuals -> ~100% before
        rows.append(
            {
                "zone_id": 2,
                "ts": half_ts,
                "y_true": float(100 + (i % 40)),
                "y_gbm_tuned": 99.0,
                "y_p90_tuned": 200.0,
            }
        )
    return pl.DataFrame(rows)


def test_conformal_offset_order_statistic() -> None:
    scores = [float(i) for i in range(100)]
    # ceil(101*0.9) = 91st smallest (1-based) = 90.0 (0-based 90)
    assert conformal_offset(scores, 0.1) == 90.0
    assert conformal_offset([], 0.1) == 0.0


def test_offsets_move_coverage_toward_nominal() -> None:
    block = evaluate_conformal(_frame(), "y_p90_tuned", "y_gbm_tuned")
    assert block["calib_rows"] > 0 and block["eval_rows"] > 0
    # sparse was under-covered (< 90%); the over-covered zone lands in "mid"
    # with a two-zone fixture (terciles of two zones = sparse + mid)
    assert block["before"]["coverage_by_stratum"]["sparse"] < 0.9
    assert block["before"]["coverage_by_stratum"]["mid"] > 0.95
    # after: sparse up, mid down, overall near nominal
    after = block["after"]["coverage_by_stratum"]
    assert after["sparse"] > block["before"]["coverage_by_stratum"]["sparse"]
    assert after["mid"] < block["before"]["coverage_by_stratum"]["mid"]
    assert 0.8 <= block["after"]["coverage_overall"] <= 1.0
    # offsets: sparse positive (band widens), over-covered zone negative
    assert block["offsets"]["sparse"] > 0
    assert block["offsets"]["mid"] < 0
