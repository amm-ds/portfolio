"""The stream figure reports outcomes and drift, not a constant score trace."""

from anomaly_detection.stream import adaptive_stream_figure


def test_adaptive_stream_figure_has_outcomes_and_drift() -> None:
    result = {
        "fixed": {"flags": 12, "tp": 3, "fp": 9, "precision": 0.25, "recall": 0.5},
        "adaptive": {"flags": 10, "tp": 2, "fp": 8, "precision": 0.2, "recall": 1 / 3},
        "chunk_drift_z": [0.1, 1.2],
        "drift_z_max": 1.0,
        "drift_events": [1],
        "n_chunks": 2,
    }
    fig = adaptive_stream_figure(result)

    assert [trace.type for trace in fig.data] == ["bar", "bar", "scatter"]
    assert list(fig.data[0].y) == [12, 3, 9]
    assert list(fig.data[1].y) == [10, 2, 8]
    assert list(fig.data[2].y) == [0.1, 1.2]
    assert "score stream" not in str(fig.layout.title.text)
