"""Workbench integration: the production API serves the frontend's exact contract."""

from fastapi.testclient import TestClient
from showcase_api.main import app


def test_workbench_datasets_and_runs_shapes() -> None:
    client = TestClient(app)
    datasets = client.get("/datasets")
    assert datasets.status_code == 200
    for record in datasets.json():
        assert {"id", "name", "version", "case_count", "tags", "created_at"} <= set(record)
    runs = client.get("/runs")
    assert runs.status_code == 200
    for run in runs.json():
        assert {
            "id",
            "dataset_id",
            "model",
            "status",
            "case_count",
            "failed_cases",
            "metrics",
        } <= set(run)
        if run["metrics"] is not None:
            assert {"accuracy", "f1", "p95_latency_ms", "cost_usd"} <= set(run["metrics"])


def test_workbench_detail_and_unknown() -> None:
    client = TestClient(app)
    detail = client.get("/runs/run-routing-a")
    assert detail.status_code == 200
    for case in detail.json()["cases"]:
        assert {"id", "input", "expected", "output", "passed", "latency_ms", "error"} <= set(case)
    assert client.get("/runs/does-not-exist").status_code == 404
