"""Workbench integration: the production API serves the same read-only contract."""

from fastapi.testclient import TestClient

from showcase_api.main import app


def test_workbench_datasets_and_runs() -> None:
    client = TestClient(app)
    datasets = client.get("/datasets")
    assert datasets.status_code == 200
    assert len(datasets.json()) == 2
    runs = client.get("/runs")
    assert runs.status_code == 200
    assert len(runs.json()) == 4
    detail = client.get("/runs/run-routing-a")
    assert detail.status_code == 200
    assert len(detail.json()["cases"]) == 12


def test_workbench_unknown_run() -> None:
    client = TestClient(app)
    assert client.get("/runs/does-not-exist").status_code == 404
