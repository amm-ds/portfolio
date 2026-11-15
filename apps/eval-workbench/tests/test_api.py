"""API contract tests: datasets, runs, run detail, health/ready."""

from fastapi.testclient import TestClient

from eval_workbench.main import app


def test_datasets() -> None:
    client = TestClient(app)
    resp = client.get("/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    for record in data:
        assert {"id", "name", "version", "n_cases"} <= set(record)


def test_runs() -> None:
    client = TestClient(app)
    resp = client.get("/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 4
    completed = [r for r in runs if r["completed"]]
    incomplete = [r for r in runs if not r["completed"]]
    assert len(completed) == 3
    for r in completed:
        assert 0.0 <= r["accuracy"] <= 1.0
        assert 0.0 <= r["f1"] <= 1.0
        assert r["p95_latency_ms"] >= 0.0
        assert r["cost_usd"] >= 0.0
    for r in incomplete:
        assert r["accuracy"] is None
        assert r["f1"] is None
        assert r["p95_latency_ms"] is None


def test_run_detail() -> None:
    client = TestClient(app)
    resp = client.get("/runs/run-routing-a")
    assert resp.status_code == 200
    run = resp.json()
    assert run["id"] == "run-routing-a"
    assert len(run["cases"]) == 12
    for case in run["cases"]:
        assert {"id", "question", "expected", "actual", "passed", "latency_ms"} <= set(case)


def test_run_detail_unknown() -> None:
    client = TestClient(app)
    resp = client.get("/runs/does-not-exist")
    assert resp.status_code == 404


def test_health_ready() -> None:
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"ready": True}
