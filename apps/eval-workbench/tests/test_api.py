"""API contract tests: exact field shapes matching the frontend's types."""

from eval_workbench.main import app
from fastapi.testclient import TestClient

DATASET_FIELDS = {"id", "name", "version", "description", "case_count", "tags", "created_at"}
RUN_FIELDS = {
    "id",
    "dataset_id",
    "model",
    "status",
    "case_count",
    "failed_cases",
    "metrics",
    "created_at",
    "completed_at",
    "cases",
}
CASE_FIELDS = {"id", "input", "expected", "output", "passed", "latency_ms", "error"}
METRIC_FIELDS = {"accuracy", "f1", "p95_latency_ms", "cost_usd"}


def test_datasets_exact_shape() -> None:
    client = TestClient(app)
    resp = client.get("/datasets")
    assert resp.status_code == 200
    for record in resp.json():
        assert set(record) == DATASET_FIELDS
        assert isinstance(record["tags"], list)
        assert record["case_count"] >= 0


def test_runs_exact_shape() -> None:
    client = TestClient(app)
    resp = client.get("/runs")
    assert resp.status_code == 200
    for run in resp.json():
        assert set(run) == RUN_FIELDS
        if run["metrics"] is not None:
            assert set(run["metrics"]) == METRIC_FIELDS
            assert 0.0 <= run["metrics"]["accuracy"] <= 1.0
            assert 0.0 <= run["metrics"]["f1"] <= 1.0
            assert run["metrics"]["p95_latency_ms"] >= 0.0
            assert run["metrics"]["cost_usd"] >= 0.0
        else:
            assert run["status"] in ("queued", "running", "failed")


def test_run_detail_cases_exact_shape() -> None:
    client = TestClient(app)
    resp = client.get("/runs/run-routing-a")
    assert resp.status_code == 200
    run = resp.json()
    assert set(run) == RUN_FIELDS
    for case in run["cases"]:
        assert set(case) == CASE_FIELDS
        assert case["latency_ms"] >= 0.0
        if case["error"] is not None:
            assert isinstance(case["error"], str)


def test_run_detail_unknown() -> None:
    client = TestClient(app)
    assert client.get("/runs/does-not-exist").status_code == 404


def test_health_ready() -> None:
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"ready": True}
