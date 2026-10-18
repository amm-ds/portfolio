"""Cross-service transfer: honest-takeaway figure + result structure."""

from mobility.transfer import fig_green_transfer


def _result() -> dict:
    return {
        "window": "2024-03 green taxi (n=100 zone-hours)",
        "features_from": "green Jan-Feb history",
        "overall": {
            "naive_lag24": {"mae": 0.212, "rmse": 1.10, "mape_pct": 81.8},
            "gbm_mean": {"mae": 0.294, "rmse": 0.911, "mape_pct": 66.6},
            "gbm_tuned": {"mae": 0.296, "rmse": 0.908, "mape_pct": 66.7},
        },
        "mae_by_borough": {
            "gbm_tuned": {"Manhattan": 0.42},
            "naive_lag24": {"Manhattan": 0.37},
        },
    }


def test_transfer_figure_marks_mixed_result() -> None:
    """When naive beats the GBM on MAE, the takeaway must say so plainly."""
    fig = fig_green_transfer(_result())
    # The takeaway rides in the title as a second line (add_takeaway).
    assert "Mixed transfer" in fig.layout.title.text
    assert "wins on RMSE" in fig.layout.title.text
    assert list(fig.data[0].x) == ["naive_lag24", "gbm_mean", "gbm_tuned"]  # reference first
