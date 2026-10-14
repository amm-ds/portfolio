import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from showcase_api.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_projects_index(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    (tmp_path / "01-demo").mkdir()
    (tmp_path / "01-demo" / "portfolio.yaml").write_text(
        "id: 01-demo\ntitle: Demo\ndomain: x\ntechniques: [t]\ndata: s\norder: 1\n"
    )
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)
    r = client.get("/projects")
    assert r.status_code == 200
    body = r.json()
    assert body[0]["id"] == "01-demo"


def test_metrics_404_for_unknown(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    (tmp_path / "01-demo").mkdir(parents=True)
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)
    r = client.get("/projects/01-demo/metrics")
    assert r.status_code == 404
    r2 = client.get("/projects/99-nope/metrics")
    assert r2.status_code == 404


def test_metrics_and_figures_served(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    figs = tmp_path / "01-demo" / "reports" / "figures"
    figs.mkdir(parents=True)
    (tmp_path / "01-demo" / "reports" / "metrics.json").write_text(json.dumps({"m": {"f1": 0.9}}))
    (figs / "bars.html").write_text("<html>fig</html>")
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)

    r = client.get("/projects/01-demo/metrics")
    assert r.json() == {"m": {"f1": 0.9}}
    assert client.get("/projects/01-demo/figures").json() == ["bars"]
    r = client.get("/projects/01-demo/figures/bars")
    assert r.status_code == 200 and "fig" in r.text


def test_chat_gated_off_by_default() -> None:
    """RAG chat is an LLM cost proxy: routes must not exist unless explicitly enabled."""
    r = client.post("/rag/chat", json={"question": "hi"})
    assert r.status_code == 405  # caught by the SPA catch-all (GET-only) → 405


def test_chat_request_validation() -> None:
    from pydantic import ValidationError
    from showcase_api.main import ChatRequest

    with pytest.raises(ValidationError):
        ChatRequest(question="")
    with pytest.raises(ValidationError):
        ChatRequest(question="x" * 4001)


def test_story_endpoint(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    (tmp_path / "01-demo").mkdir(parents=True)
    (tmp_path / "01-demo" / "portfolio.yaml").write_text(
        "id: 01-demo\ntitle: Demo\ndomain: x\ntechniques: [t]\ndata: s\norder: 1\n"
    )
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)

    r = client.get("/projects/01-demo/story")
    assert r.status_code == 404

    (tmp_path / "01-demo" / "story.yaml").write_text(
        "project_id: 01-demo\n"
        "sections:\n"
        "  - id: background\n"
        "    text_md: Why this exists.\n"
        "  - id: results\n"
        "    text_md: Numbers.\n"
        "    figures: [bars]\n"
    )
    r = client.get("/projects/01-demo/story")
    assert r.status_code == 200
    body = r.json()
    assert [s["id"] for s in body["sections"]] == ["background", "results"]
    assert body["sections"][0]["title"] == "Background"
    assert body["sections"][1]["figures"] == ["bars"]


def test_report_endpoint(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    (tmp_path / "01-demo").mkdir(parents=True)
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)
    r = client.get("/projects/01-demo/report")
    assert r.status_code == 404
    (tmp_path / "01-demo" / "reports").mkdir()
    (tmp_path / "01-demo" / "reports" / "report.html").write_text("<html>report</html>")
    r = client.get("/projects/01-demo/report")
    assert r.status_code == 200 and "report" in r.text


def test_forecast_503_without_artifacts(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    monkeypatch.setattr(main, "_SERVING_DIR", tmp_path / "no-such-dir")
    r = client.post(
        "/projects/07-open-data-mobility/forecast",
        json={"zone_id": 132, "features": {"lag_24": 5.0}},
    )
    assert r.status_code == 503
