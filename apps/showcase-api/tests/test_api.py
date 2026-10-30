import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from showcase_api import main
from showcase_api.main import app
from showcase_api.middleware import RateLimiter, RateLimitMiddleware

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["sha"] == "dev"  # BUILD_SHA unset locally
    assert body["version"]
    assert isinstance(body["ready"], bool)
    assert r.headers["Cache-Control"] == "no-store"


def test_health_readiness_reflects_missing_artifacts(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """ready=False when a serving bundle or a demo payload file is missing."""
    from showcase_api import main

    monkeypatch.delenv("BUILD_SHA", raising=False)
    monkeypatch.setattr(main, "_DEMAND_SERVING_DIR", tmp_path / "no-such-dir")
    assert client.get("/health").json()["ready"] is False

    _write_demo_project(tmp_path / "with-demo")
    (tmp_path / "with-demo" / "05-ml-pipeline-churn" / "reports" / "demo_payload.json").unlink()
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path / "with-demo")
    assert client.get("/health").json()["ready"] is False


def test_ready_controls_status_without_changing_liveness(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(main, "_readiness", lambda: False)
    unready = client.get("/ready")
    assert unready.status_code == 503
    assert unready.json() == {"status": "unavailable", "ready": False}
    assert unready.headers["Cache-Control"] == "no-store"
    assert client.get("/health").status_code == 200

    monkeypatch.setattr(main, "_readiness", lambda: True)
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ok", "ready": True}


def test_console_script_invokes_uvicorn(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import uvicorn
    from showcase_api.__main__ import main as launch

    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    launch()
    assert calls == [
        (("showcase_api.main:app",), {"host": "0.0.0.0", "port": 8000})  # noqa: S104
    ]


def test_projects_index(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    (tmp_path / "01-demo").mkdir()
    (tmp_path / "01-demo" / "portfolio.yaml").write_text(
        "id: 01-demo\ntitle: Demo\ndomain: x\ntopic: T\ntechniques: [t]\ndata: s\norder: 1\n"
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


def test_metrics_prefer_uci_track(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """02 ships two tracks; reports_uci/ is the canonical one when present."""
    from showcase_api import main

    reports = tmp_path / "01-demo" / "reports"
    uci = tmp_path / "01-demo" / "reports_uci"
    reports.mkdir(parents=True)
    uci.mkdir()
    (reports / "metrics.json").write_text(json.dumps({"m": {"f1": 0.9}}))
    (uci / "metrics.json").write_text(json.dumps({"m": {"f1": 0.95}}))
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)

    assert client.get("/projects/01-demo/metrics").json() == {"m": {"f1": 0.95}}


def test_figures_served_per_track(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A `track:` prefix resolves into reports_<track>/figures/ (02's dual
    tracks); unprefixed names and unknown tracks keep the old behavior."""
    from showcase_api import main

    figs = tmp_path / "01-demo" / "reports" / "figures"
    uci_figs = tmp_path / "01-demo" / "reports_uci" / "figures"
    figs.mkdir(parents=True)
    uci_figs.mkdir(parents=True)
    (figs / "bars.html").write_text("<html>fig</html>")
    (uci_figs / "bars.html").write_text("<html>uci fig</html>")
    (uci_figs / "bars.json").write_text(json.dumps({"data": [], "layout": {}}))
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)

    assert client.get("/projects/01-demo/figures/bars").text == "<html>fig</html>"
    r = client.get("/projects/01-demo/figures/uci:bars")
    assert r.status_code == 200 and "uci fig" in r.text
    r = client.get("/projects/01-demo/figures/uci:bars.json")
    assert r.status_code == 200 and r.json() == {"data": [], "layout": {}}
    # unknown track → 404, never a path escape
    assert client.get("/projects/01-demo/figures/nope:bars").status_code == 404
    assert client.get("/projects/01-demo/figures/uci:missing").status_code == 404


def test_chat_gated_off_by_default() -> None:
    """RAG chat is an LLM cost proxy: routes must not exist unless explicitly enabled."""
    r = client.post("/rag/chat", json={"question": "hi"})
    # Not registered: 404 without the web build (CI), 405 via the GET-only
    # SPA catch-all when the build is present (local/dev container).
    assert r.status_code in (404, 405)


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
        "id: 01-demo\ntitle: Demo\ndomain: x\ntopic: T\ntechniques: [t]\ndata: s\norder: 1\n"
    )
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)

    r = client.get("/projects/01-demo/story")
    assert r.status_code == 404

    (tmp_path / "01-demo" / "story.yaml").write_text(
        "project_id: 01-demo\n"
        "short_version: Demo short copy.\n"
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


def test_report_endpoint_prefers_m5_then_uci_then_reports(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """02's canonical report is reports_m5/report.html; the UCI and synthetic
    tracks stay reachable through the fallback chain."""
    from showcase_api import main

    d = tmp_path / "01-demo"
    (d / "reports").mkdir(parents=True)
    (d / "reports" / "report.html").write_text("<html>synthetic report</html>")
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)
    r = client.get("/projects/01-demo/report")
    assert r.status_code == 200 and "synthetic report" in r.text
    (d / "reports_uci").mkdir()
    (d / "reports_uci" / "report.html").write_text("<html>uci report</html>")
    r = client.get("/projects/01-demo/report")
    assert r.status_code == 200 and "uci report" in r.text
    (d / "reports_m5").mkdir()
    (d / "reports_m5" / "report.html").write_text("<html>m5 report</html>")
    r = client.get("/projects/01-demo/report")
    assert r.status_code == 200 and "m5 report" in r.text


# --- Demo platform: registry / manifest / payload ----------------------------

_DEMO_YAML = """\
id: churn-sandbox
title: churn threshold sandbox
hook: Move the alarm threshold and watch the cost curve move.
project: 05-ml-pipeline-churn
group: retain customers
skills: [calibration]
modes: [browser, live]
hero:
  label: decision cost per 1,400 customers
  value: "$601 vs $1,035 naive"
  ci: paired bootstrap CI [-485, -343]
scenarios:
  - name: base
    controls: {fn_ratio: 5, threshold: 0.175}
live_endpoints:
  - method: POST
    path: /projects/05-ml-pipeline-churn/score
    label: live customer scoring
    cost: free-local
payload:
  path: reports/demo_payload.json
  schema_version: 1
  required_keys: [demo, thresholds, overall]
"""

_DEMO_PAYLOAD = {"demo": "churn-threshold-sandbox", "thresholds": [0.1], "overall": {}}


def _write_demo_project(root: Path) -> None:
    """One project dir with portfolio.yaml + demo.yaml + built payload."""
    proj = root / "05-ml-pipeline-churn"
    reports = proj / "reports"
    reports.mkdir(parents=True)
    (proj / "portfolio.yaml").write_text(
        "id: 05-ml-pipeline-churn\ntitle: Churn\ndomain: x\ntopic: T\n"
        "techniques: [t]\ndata: s\norder: 5\n"
    )
    (proj / "demo.yaml").write_text(_DEMO_YAML)
    (reports / "demo_payload.json").write_text(json.dumps(_DEMO_PAYLOAD))


def test_demos_registry_entry_shape(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    _write_demo_project(tmp_path)
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)

    r = client.get("/demos")
    assert r.status_code == 200
    (entry,) = r.json()
    assert entry == {
        "id": "churn-sandbox",
        "title": "churn threshold sandbox",
        "hook": "Move the alarm threshold and watch the cost curve move.",
        "group": "retain customers",
        "href": "/demos/churn-sandbox",
        "project": "05-ml-pipeline-churn",
        "status": "live",
        "hero": {
            "label": "decision cost per 1,400 customers",
            "value": "$601 vs $1,035 naive",
            "ci": "paired bootstrap CI [-485, -343]",
        },
    }


def test_demo_manifest_round_trip(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    _write_demo_project(tmp_path)
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)

    r = client.get("/demos/churn-sandbox/manifest")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "churn-sandbox"
    assert body["scenarios"][0] == {"name": "base", "controls": {"fn_ratio": 5, "threshold": 0.175}}
    assert body["live_endpoints"][0] == {
        "method": "POST",
        "path": "/projects/05-ml-pipeline-churn/score",
        "label": "live customer scoring",
        "cost": "free-local",
    }
    assert body["payload"] == {
        "path": "reports/demo_payload.json",
        "schema_version": 1,
        "required_keys": ["demo", "thresholds", "overall"],
    }

    assert client.get("/demos/nope/manifest").status_code == 404


def test_demo_payload_200_and_cache_header(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    _write_demo_project(tmp_path)
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)

    r = client.get("/demos/churn-sandbox/payload")
    assert r.status_code == 200
    assert r.json() == _DEMO_PAYLOAD
    assert r.headers["Cache-Control"] == "public, max-age=3600, stale-while-revalidate=86400"
    assert r.headers["ETag"]
    # If-None-Match on the ETag -> 304
    r2 = client.get("/demos/churn-sandbox/payload", headers={"If-None-Match": r.headers["ETag"]})
    assert r2.status_code == 304


def test_demo_payload_404_unknown_demo(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    _write_demo_project(tmp_path)
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)

    assert client.get("/demos/nope/payload").status_code == 404


def test_demo_payload_404_when_not_built(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    proj = tmp_path / "05-ml-pipeline-churn"
    proj.mkdir(parents=True)
    (proj / "demo.yaml").write_text(_DEMO_YAML)
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)

    r = client.get("/demos/churn-sandbox/payload")
    assert r.status_code == 404
    assert "demo-payload" in r.json()["error"]


def test_demo_payload_409_on_missing_required_key(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    from showcase_api import main

    _write_demo_project(tmp_path)
    bad = dict(_DEMO_PAYLOAD)
    del bad["overall"]
    payload_file = tmp_path / "05-ml-pipeline-churn" / "reports" / "demo_payload.json"
    payload_file.write_text(json.dumps(bad))
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)

    r = client.get("/demos/churn-sandbox/payload")
    assert r.status_code == 409
    assert "overall" in r.json()["error"]


def test_forecast_503_without_artifacts(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    monkeypatch.setattr(main, "_SERVING_DIR", tmp_path / "no-such-dir")
    r = client.post(
        "/projects/07-open-data-mobility/forecast",
        json={"zone_id": 132, "features": {"lag_24": 5.0}},
    )
    assert r.status_code == 503


# --- Project 07: per-service forecast (wave 15 green bundle) -------------------
# These hit the committed serving bundle (a deployable artifact per the repo
# .gitignore policy), so the example rows and expected outputs are fixed.


_MOBILITY_FORECAST_URL = "/projects/07-open-data-mobility/forecast"


def _mobility_example(service_dir: Path) -> dict:
    """The bundle's own committed example row — a fixed input with a fixed output."""
    meta = json.loads((service_dir / "meta.json").read_text())
    return {"zone_id": meta["example"]["zone_id"], "features": meta["example"]["features"]}


def _mobility_expected(service_dir: Path, body: dict) -> tuple[float, float]:
    """Recompute prediction/p90 straight from the bundle, independently of the
    endpoint — the test encodes the serving math like 02's _SumRegressor does,
    so it guards the wiring (routing, feature order, transform) rather than the
    model quality, and survives bundle rebuilds."""
    import joblib

    bundle = joblib.load(service_dir / "model.joblib")
    meta = json.loads((service_dir / "meta.json").read_text())
    feature_names = list(meta.get("feature_names") or bundle.get("feature_names") or [])
    row = np.array([[float(body["features"][f]) for f in feature_names]])
    pred = float(bundle["gbm"].predict(row)[0])
    p90 = float(bundle["p90"].predict(row)[0])
    if bundle.get("target_transform") == "log1p":
        pred = float(np.expm1(pred))
        p90 = float(np.expm1(p90))
    return round(max(0.0, pred), 3), round(max(0.0, p90), 3)


def test_mobility_forecast_defaults_to_yellow_service() -> None:
    """No service field: the response is exactly the yellow forecast plus the
    new echo key — pre-wave-15 clients only see an additive field."""
    from showcase_api import main

    body = _mobility_example(main._SERVING_DIR)
    r = client.post(_MOBILITY_FORECAST_URL, json=body)
    assert r.status_code == 200
    expected_pred, expected_p90 = _mobility_expected(main._SERVING_DIR, body)
    assert r.json() == {
        "zone_id": body["zone_id"],
        "borough": "Queens",
        "zone": "JFK Airport",
        "prediction": expected_pred,
        "p90": expected_p90,
        "service": "yellow",
    }


def test_mobility_forecast_green_service_matches_committed_bundle() -> None:
    """service="green" routes to the committed green bundle: the response must
    equal a direct prediction from that bundle's own model + example row, and
    differ from yellow on the same body (proving routing, not just the echo)."""
    from showcase_api import main

    green_dir = main._SERVING_DIR / "green"
    green_meta = json.loads((green_dir / "meta.json").read_text())
    assert green_meta["service"] == "green"  # the committed green metadata
    assert green_meta["train_runs"] == ["gbm_green_served"]
    body = _mobility_example(green_dir)
    r = client.post(_MOBILITY_FORECAST_URL, json={**body, "service": "green"})
    assert r.status_code == 200
    payload = r.json()
    assert payload["service"] == "green"
    expected_pred, expected_p90 = _mobility_expected(green_dir, body)
    assert payload["prediction"] == expected_pred
    assert payload["p90"] == expected_p90
    yellow_pred, _ = _mobility_expected(main._SERVING_DIR, body)
    assert expected_pred != yellow_pred


def test_mobility_forecast_unknown_service_is_422() -> None:
    r = client.post(
        _MOBILITY_FORECAST_URL,
        json={"zone_id": 132, "features": {"lag_1": 1.0}, "service": "uber"},
    )
    assert r.status_code == 422


def test_health_ready_still_true_with_green_bundle() -> None:
    """Wiring green into the endpoint must not flip readiness: every bundle and
    demo payload the live endpoints need is committed."""
    body = client.get("/health").json()
    assert body["ready"] is True


# --- Project 02: served demand forecast --------------------------------------


class _SumRegressor:
    """Stand-in for the 02 champion: scores an object row (numerics + series_id)."""

    def fit(self, X: object, y: object) -> "_SumRegressor":
        return self

    def predict(self, X: object) -> np.ndarray:
        arr = np.asarray(X, dtype=object)
        return np.array(
            [float(sum(float(v) for v in row if isinstance(v, (int, float)))) for row in arr]
        )


def _write_demand_artifact(serving_dir: Path, with_series_list: bool = True) -> None:
    """Tiny fabricated 02 artifact matching the real bundle shape."""
    import joblib

    serving_dir.mkdir(parents=True)
    joblib.dump(
        {"model": _SumRegressor(), "feature_names": ["lag_1", "hour"], "target_transform": None},
        serving_dir / "model.joblib",
    )
    meta: dict = {
        "model_name": "sum-demo",
        "example_row": {"series_id": "S1", "lag_1": 1.0, "hour": 3.0},
    }
    if with_series_list:
        meta["series"] = ["S1", "S2"]
    (serving_dir / "meta.json").write_text(json.dumps(meta))


def test_demand_forecast_503_without_artifacts(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    monkeypatch.setattr(main, "_DEMAND_SERVING_DIR", tmp_path / "no-such-dir")
    r = client.post(
        "/projects/02-demand-forecasting/forecast",
        json={"series_id": "S1", "features": {"lag_1": 1.0, "hour": 3.0}},
    )
    assert r.status_code == 503


def test_demand_forecast_happy_path_and_guards(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    _write_demand_artifact(tmp_path / "serving")
    monkeypatch.setattr(main, "_DEMAND_SERVING_DIR", tmp_path / "serving")

    r = client.post(
        "/projects/02-demand-forecasting/forecast",
        json={"series_id": "S1", "features": {"lag_1": 1.0, "hour": 3.0}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "sum-demo"
    # the stand-in sums the numeric feature cells: 1.0 + 3.0
    assert body["forecast"] == 4.0

    # unknown series -> 422
    r = client.post(
        "/projects/02-demand-forecasting/forecast",
        json={"series_id": "NOPE", "features": {"lag_1": 1.0, "hour": 3.0}},
    )
    assert r.status_code == 422
    # missing feature -> 422
    r = client.post(
        "/projects/02-demand-forecasting/forecast",
        json={"series_id": "S1", "features": {"lag_1": 1.0}},
    )
    assert r.status_code == 422


def test_demand_forecast_series_derived_from_example(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """No series list in meta: the known series is derived from example_row."""
    from showcase_api import main

    _write_demand_artifact(tmp_path / "serving", with_series_list=False)
    monkeypatch.setattr(main, "_DEMAND_SERVING_DIR", tmp_path / "serving")

    r = client.post(
        "/projects/02-demand-forecasting/forecast",
        json={"series_id": "S1", "features": {"lag_1": 1.0, "hour": 3.0}},
    )
    assert r.status_code == 200
    r = client.post(
        "/projects/02-demand-forecasting/forecast",
        json={"series_id": "S2", "features": {"lag_1": 1.0, "hour": 3.0}},
    )
    assert r.status_code == 422


# --- Project 05: served churn scoring ----------------------------------------


def _write_churn_artifact(serving_dir: Path) -> None:
    """Tiny fabricated 05 artifact: DataFrame pipeline incl. a string categorical."""
    import joblib
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    frame = pd.DataFrame(
        {
            "tenure_months": [1.0, 60.0, 2.0, 72.0],
            "monthly_charges": [90.0, 30.0, 85.0, 25.0],
            "contract": ["month-to-month", "one-year", "month-to-month", "two-year"],
        }
    )
    pre = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["contract"]),
            ("num", "passthrough", ["tenure_months", "monthly_charges"]),
        ]
    )
    pipe = Pipeline([("prep", pre), ("clf", LogisticRegression())]).fit(frame, [1, 0, 1, 0])
    serving_dir.mkdir(parents=True)
    joblib.dump(
        {
            "model": pipe,
            "feature_names": ["tenure_months", "monthly_charges", "contract"],
            "decision": {"threshold": 0.175, "fp_cost": 1, "fn_cost": 5},
        },
        serving_dir / "model.joblib",
    )
    (serving_dir / "meta.json").write_text(
        json.dumps(
            {
                "model_name": "logreg-demo",
                "example_row": {
                    "tenure_months": 1.0,
                    "monthly_charges": 90.0,
                    "contract": "month-to-month",
                },
            }
        )
    )


def test_churn_score_503_without_artifacts(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    monkeypatch.setattr(main, "_CHURN_SERVING_DIR", tmp_path / "no-such-dir")
    r = client.post(
        "/projects/05-ml-pipeline-churn/score",
        json={"features": {"tenure_months": 1.0, "monthly_charges": 90.0}},
    )
    assert r.status_code == 503


def test_churn_score_happy_path_and_guards(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    _write_churn_artifact(tmp_path / "serving")
    monkeypatch.setattr(main, "_CHURN_SERVING_DIR", tmp_path / "serving")

    r = client.post(
        "/projects/05-ml-pipeline-churn/score",
        json={
            "features": {
                "tenure_months": 1.0,
                "monthly_charges": 90.0,
                "contract": "month-to-month",
            }
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["churn_probability"] <= 1.0
    decision = body["decision"]
    assert decision["alarm"] == (body["churn_probability"] >= decision["threshold"])
    assert decision["threshold"] == 0.175
    assert "expected_cost_note" in decision and "5" in decision["expected_cost_note"]

    # missing feature -> 422
    r = client.post(
        "/projects/05-ml-pipeline-churn/score",
        json={"features": {"tenure_months": 1.0, "monthly_charges": 90.0}},
    )
    assert r.status_code == 422


def test_churn_score_returns_503_when_capacity_busy(tmp_path: Path, monkeypatch) -> None:
    """Four concurrent scores max; a fifth request gets a fast 503."""
    import threading

    import showcase_api.main as main_mod

    _write_churn_artifact(tmp_path / "serving")
    monkeypatch.setattr(main_mod, "_CHURN_SERVING_DIR", tmp_path / "serving")

    s = threading.BoundedSemaphore(4)
    for _ in range(4):
        s.acquire()
    monkeypatch.setattr(main_mod, "_CHURN_SEMAPHORE", s)
    r = client.post(
        "/projects/05-ml-pipeline-churn/score",
        json={
            "features": {
                "tenure_months": 1.0,
                "monthly_charges": 90.0,
                "contract": "month-to-month",
            }
        },
    )
    assert r.status_code == 503
    assert "busy" in r.json()["error"]


# --- Project 06: served VRPTW solving ----------------------------------------


def _vrptw_payload(n_customers: int) -> dict:
    customers = [
        {
            "id": 0,
            "x": 50.0,
            "y": 50.0,
            "demand": 0.0,
            "ready_time": 0.0,
            "due_time": 1000.0,
            "service_time": 0.0,
        }
    ]
    for i in range(1, n_customers + 1):
        customers.append(
            {
                "id": i,
                "x": float(i * 10),
                "y": float(i % 5),
                "demand": 10.0,
                "ready_time": 0.0,
                "due_time": 900.0,
                "service_time": 5.0,
            }
        )
    return {
        "name": f"TEST-{n_customers}",
        "customers": customers,
        "vehicle_capacity": 40.0,
        "max_vehicles": 25,
    }


def test_solve_happy_path_feasible_plan() -> None:
    from routing_optimization.schemas import Problem, RoutePlan

    payload = _vrptw_payload(5)
    r = client.post("/projects/06-routing-optimization/solve", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["solver"] == "two_opt_tuned"
    assert body["runtime_s"] >= 0.0
    plan = RoutePlan.model_validate({k: v for k, v in body.items() if k != "runtime_s"})
    plan.validate_against(Problem.model_validate(payload))


def test_solve_rejects_too_many_customers() -> None:
    r = client.post("/projects/06-routing-optimization/solve", json=_vrptw_payload(201))
    assert r.status_code == 422


# --- Production hardening middleware -----------------------------------------


def _rate_limit_mw() -> RateLimitMiddleware:
    """The RateLimitMiddleware instance inside the app's built middleware stack."""
    from showcase_api.main import app

    if app.middleware_stack is None:  # stack builds lazily on first request
        client.get("/health")
    node = app.middleware_stack
    while node is not None:
        if isinstance(node, RateLimitMiddleware):
            return node
        node = getattr(node, "app", None)
    raise AssertionError("RateLimitMiddleware not in stack")


@pytest.fixture(autouse=True)
def _relax_rate_limit():  # type: ignore[no-untyped-def]
    """The suite fires many POSTs within microseconds; swap in a high-capacity
    bucket so only the dedicated limiter tests feel the real cap."""
    mw = _rate_limit_mw()
    original = mw.limiter
    mw.limiter = RateLimiter(per_minute=600_000, burst=100_000)
    try:
        yield
    finally:
        mw.limiter = original


def test_rate_limiter_defaults_and_env_override(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    default = RateLimiter.from_env()
    assert default.capacity == 10.0  # burst default
    assert default.rate_per_second == 30 / 60.0  # RATE_LIMIT_PER_MINUTE default

    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "120")
    overridden = RateLimiter.from_env()
    assert overridden.rate_per_second == 120 / 60.0


def test_rate_limiter_refill_window() -> None:
    """Token bucket: burst drains, retry_after reported, window refills."""
    import time

    from showcase_api.middleware import RateLimiter

    rl = RateLimiter(per_minute=60, burst=2)  # 1 token/s refill
    assert rl.check("ip")[0]
    assert rl.check("ip")[0]
    allowed, retry_after = rl.check("ip")
    assert not allowed
    assert 0.0 < retry_after <= 1.0

    # Simulate the refill window elapsing: 10 s at 1 token/s refills fully.
    tokens, _last = rl._buckets["ip"]
    rl._buckets["ip"] = (tokens, time.monotonic() - 10.0)
    assert rl.check("ip")[0]


def test_rate_limit_burst_then_429_and_reset() -> None:
    """Middleware: burst is allowed, the next POST in the window is 429 with
    Retry-After; clearing the in-memory buckets (window reset) allows again."""
    mw = _rate_limit_mw()
    original = mw.limiter
    mw.limiter = RateLimiter(per_minute=2, burst=2)
    try:
        url = "/projects/02-demand-forecasting/forecast"
        body = {"series_id": "S1", "features": {"lag_1": 1.0}}
        assert client.post(url, json=body).status_code != 429
        assert client.post(url, json=body).status_code != 429
        r = client.post(url, json=body)
        assert r.status_code == 429
        assert float(r.headers["Retry-After"]) > 0.0

        mw.limiter._buckets.clear()  # window reset
        assert client.post(url, json=body).status_code != 429
    finally:
        mw.limiter = original


def test_body_limit_rejects_oversized_body() -> None:
    """Global ~1 MB cap: an oversized POST body is rejected 413."""
    r = client.post(
        "/projects/02-demand-forecasting/forecast",
        content=b'{"series_id": "S1", "features": {"pad": "%s"}}' % (b"x" * 1_100_000),
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 413


def test_request_logging_emits_one_line(caplog) -> None:  # type: ignore[no-untyped-def]
    import logging

    with caplog.at_level(logging.INFO, logger="showcase_api.middleware"):
        r = client.get("/health")
    assert r.status_code == 200
    lines = [
        rec.getMessage()
        for rec in caplog.records
        if rec.name == "showcase_api.middleware" and "GET /health -> 200" in rec.getMessage()
    ]
    assert len(lines) == 1
    assert "ms" in lines[0]


def test_rate_limiter_store_is_bounded() -> None:
    """Bucket dict must not grow unbounded under key spam (audit pass 3 f3)."""
    from showcase_api.middleware import RateLimiter

    limiter = RateLimiter(per_minute=60, burst=2, max_keys=5)
    for i in range(50):
        allowed, _ = limiter.check(f"spam-{i}")
        assert allowed  # each fresh key gets burst tokens
    assert len(limiter._buckets) <= 5


def test_rate_limiter_evicts_stalest_on_overflow() -> None:
    from showcase_api.middleware import RateLimiter

    limiter = RateLimiter(per_minute=1, burst=1, max_keys=3)
    limiter.check("a")
    limiter.check("b")
    limiter.check("c")
    for _ in range(3):  # drain burst so next inserts have old refill times
        limiter.check("a")
        limiter.check("b")
        limiter.check("c")
    limiter.check("d-new")  # overflow: evicts the stalest existing key
    assert len(limiter._buckets) <= 3
    assert "d-new" in limiter._buckets


def test_solve_returns_503_when_capacity_busy(monkeypatch) -> None:
    """Two concurrent solves max; a third request gets a fast 503."""
    import threading

    import showcase_api.main as main_mod

    # Exhaust both slots for the duration of the test.
    s = threading.BoundedSemaphore(2)
    s.acquire()
    s.acquire()
    monkeypatch.setattr(main_mod, "_SOLVE_SEMAPHORE", s)
    r = client.post("/projects/06-routing-optimization/solve", json=_vrptw_payload(5))
    assert r.status_code == 503
    assert "busy" in r.json()["error"]


def test_solve_timeout_retains_slot_until_worker_finishes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A client timeout must not free capacity still used by the abandoned worker."""
    import threading

    from fastapi import HTTPException
    from routing_optimization.schemas import Problem

    semaphore = threading.BoundedSemaphore(1)
    worker_started = threading.Event()
    worker_release = threading.Event()
    worker_finished = threading.Event()
    monkeypatch.setattr(main, "_SOLVE_SEMAPHORE", semaphore)

    def slow_solve(_problem):  # type: ignore[no-untyped-def]
        worker_started.set()
        assert worker_release.wait(2)

    def timeout_after_worker_starts(fn):  # type: ignore[no-untyped-def]
        def run() -> None:
            try:
                fn()
            finally:
                worker_finished.set()

        thread = threading.Thread(target=run)
        thread.start()
        assert worker_started.wait(2)
        timeout_after_worker_starts.thread = thread
        raise HTTPException(status_code=504, detail="timed out")

    timeout_after_worker_starts.thread = None
    monkeypatch.setattr(main, "_solve_routing_inner", slow_solve)
    monkeypatch.setattr(main, "_run_with_timeout", timeout_after_worker_starts)
    problem = Problem.model_validate(_vrptw_payload(1))

    with pytest.raises(HTTPException, match="timed out"):
        main.solve_routing(problem)
    assert not semaphore.acquire(blocking=False)

    worker_release.set()
    assert worker_finished.wait(2)
    timeout_after_worker_starts.thread.join(2)
    assert semaphore.acquire(blocking=False)
    semaphore.release()


def test_forecast_workers_share_a_bounded_capacity(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Two forecasts run; a third fails fast until a worker releases its slot."""
    import threading

    from fastapi import HTTPException

    semaphore = threading.BoundedSemaphore(2)
    both_started = threading.Event()
    worker_release = threading.Event()
    lock = threading.Lock()
    started = 0
    responses = []
    errors = []
    monkeypatch.setattr(main, "_FORECAST_SEMAPHORE", semaphore)
    monkeypatch.setattr(main, "_run_with_timeout", lambda fn: fn())

    class BlockingRegressor:
        def predict(self, _row):  # type: ignore[no-untyped-def]
            nonlocal started
            with lock:
                started += 1
                if started == 2:
                    both_started.set()
            assert worker_release.wait(2)
            return np.array([2.0])

    artifacts = {
        "model": {
            "model": BlockingRegressor(),
            "feature_names": ["lag_1"],
            "target_transform": None,
        },
        "meta": {"model_name": "blocking"},
    }
    monkeypatch.setattr(main.serving, "cached_artifacts", lambda _path: artifacts)
    request = main.DemandForecastRequest(series_id="S1", features={"lag_1": 1.0})

    def call_forecast() -> None:
        try:
            responses.append(main.forecast_demand(request))
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [threading.Thread(target=call_forecast) for _ in range(2)]
    for thread in threads:
        thread.start()
    try:
        assert both_started.wait(2)
        with pytest.raises(HTTPException) as exc_info:
            main.forecast_demand(request)
        assert exc_info.value.status_code == 503
    finally:
        worker_release.set()
        for thread in threads:
            thread.join(2)

    assert not errors
    assert len(responses) == 2
    assert all(response.forecast == 2.0 for response in responses)
    assert semaphore.acquire(blocking=False)
    assert semaphore.acquire(blocking=False)
    semaphore.release()
    semaphore.release()


# --- Route manifest 404 / cache headers / kill switch / IP hashing ------------


@pytest.fixture()
def fake_web_dist(tmp_path: Path, monkeypatch):  # type: ignore[no-untyped-def]
    """A minimal web build in tmp: index.html + one hashed asset. Patches the
    WEB_DIST the catch-all reads, and an SPA manifest with one static route,
    one wildcard route, one project deep link, and one demo deep link."""
    from showcase_api import main

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa shell</html>")
    (dist / "assets" / "app-a1b2c3.js").write_text("console.log(1)")
    monkeypatch.setattr(main, "WEB_DIST", dist)
    monkeypatch.setattr(
        main, "_SPA_PATTERNS", ["/", "/projects", "/projects/*", "/demos/churn-sandbox"]
    )
    return dist


def test_spa_known_routes_serve_index_html(fake_web_dist) -> None:  # type: ignore[no-untyped-def]
    for path in ("/", "/projects", "/projects/05-ml-pipeline-churn", "/demos/churn-sandbox"):
        r = client.get(path, headers={"accept": "text/html"})
        assert r.status_code == 200, path
        assert "spa shell" in r.text
        assert r.headers["Cache-Control"] == "no-cache"
        assert r.headers["X-Request-ID"]


def test_spa_unknown_path_gets_real_404_json(fake_web_dist) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/definitely/not/a/route")
    assert r.status_code == 404
    body = r.json()
    assert "unknown path" in body["error"]
    assert len(body["request_id"]) == 12  # short uuid4
    # wildcard patterns match exactly one segment: /projects/a/b is unknown
    assert client.get("/projects/too/deep").status_code == 404


def test_spa_hashed_assets_immutable_else_no_cache(fake_web_dist) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/assets/app-a1b2c3.js")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "public, max-age=31536000, immutable"


def test_figures_cache_headers_and_etag(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    figs = tmp_path / "01-demo" / "reports" / "figures"
    figs.mkdir(parents=True)
    (figs / "bars.html").write_text("<html>fig</html>")
    (figs / "bars.json").write_text(json.dumps({"data": [], "layout": {}}))
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)

    for url in ("/projects/01-demo/figures/bars", "/projects/01-demo/figures/bars.json"):
        r = client.get(url)
        assert r.status_code == 200
        assert r.headers["Cache-Control"] == "public, max-age=3600, stale-while-revalidate=86400"
        etag = r.headers["ETag"]
        assert client.get(url, headers={"If-None-Match": etag}).status_code == 304


def test_projects_and_demos_indexes_have_etag(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Startup-computed indexes: same ETag across calls, 304 on If-None-Match."""
    from showcase_api import main

    _write_demo_project(tmp_path)
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)

    for url in ("/projects", "/demos"):
        r = client.get(url)
        assert r.status_code == 200
        etag = r.headers["ETag"]
        assert etag
        assert client.get(url, headers={"If-None-Match": etag}).status_code == 304
        assert client.get(url).headers["ETag"] == etag  # computed once


def test_http_errors_share_error_request_id_envelope() -> None:
    r = client.get("/projects/99-nope/metrics")
    assert r.status_code == 404
    body = r.json()
    assert set(body) == {"error", "request_id"}
    assert body["request_id"] == r.headers["X-Request-ID"]
    # 422 validation errors share the envelope
    r2 = client.post("/projects/02-demand-forecasting/forecast", json={"series_id": "S1"})
    assert r2.status_code == 422
    assert r2.json()["request_id"] == r2.headers["X-Request-ID"]


# --- Live kill switch + daily budget -------------------------------------------


def _patch_guard(monkeypatch, **kwargs):  # type: ignore[no-untyped-def]
    """Swap in an isolated LiveGuard so kill-switch/budget tests never touch
    the process-wide counter other tests share."""
    import showcase_api.main as main_mod

    guard = main_mod.LiveGuard(**kwargs)
    monkeypatch.setattr(main_mod, "_LIVE_GUARD", guard)
    return guard


def test_kill_switch_env_returns_503_with_hint(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _patch_guard(monkeypatch, kill_switch=True)
    r = client.post(
        "/projects/02-demand-forecasting/forecast",
        json={"series_id": "S1", "features": {"lag_1": 1.0}},
    )
    assert r.status_code == 503
    body = r.json()
    assert body["hint"] == "precomputed demo replay remains available"
    assert body["request_id"]


def test_kill_switch_file_flag_returns_503(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    _patch_guard(monkeypatch)
    flag = tmp_path / "live_disabled"
    flag.write_text("")
    monkeypatch.setattr("showcase_api.main._LIVE_DISABLE_FLAG", flag)
    r = client.post(
        "/projects/05-ml-pipeline-churn/score",
        json={"features": {"tenure_months": 1.0}},
    )
    assert r.status_code == 503
    assert r.json()["hint"] == "precomputed demo replay remains available"


def test_live_guard_daily_budget_and_80pct_alert(caplog, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import logging

    guard = _patch_guard(monkeypatch, budget=4)
    url = "/projects/02-demand-forecasting/forecast"
    body = {"series_id": "S1", "features": {"lag_1": 1.0}}
    with caplog.at_level(logging.WARNING, logger="showcase_api.main"):
        for _ in range(4):  # 80% of 4 -> alert logged on the 4th call
            # gated through; whether the call 200s/422s depends on artifacts
            r = client.post(url, json=body)
            assert "budget" not in r.json().get("error", "")
        assert any("80%" in rec.getMessage() for rec in caplog.records)
        r = client.post(url, json=body)  # 5th call: over budget
        assert r.status_code == 503
        assert "budget" in r.json()["error"]
        assert r.json()["hint"] == "precomputed demo replay remains available"
        assert guard._count == 5


# --- Client-IP hashing in request logs -----------------------------------------


def test_hash_client_ip_is_salted_truncated_sha256() -> None:
    import hashlib

    from showcase_api.middleware import hash_client_ip

    h = hash_client_ip("203.0.113.7", salt="test-salt")
    assert h == hashlib.sha256(b"test-salt203.0.113.7").hexdigest()[:12]
    assert len(h) == 12 and h != "203.0.113.7"
    # different salt or IP -> different hash; default salt is stable
    assert hash_client_ip("203.0.113.7", salt="other") != h
    assert hash_client_ip("203.0.113.8", salt="test-salt") != h
    assert hash_client_ip("1.2.3.4") == hash_client_ip("1.2.3.4", salt="dev-salt")


def test_missing_ip_hash_salt_warns_once_and_falls_back(caplog, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Unset/empty IP_HASH_SALT must not fail open silently: the middleware
    falls back to the public default salt and logs a one-time WARNING."""
    import logging

    from showcase_api import middleware

    monkeypatch.delenv("IP_HASH_SALT", raising=False)
    monkeypatch.setattr(middleware, "_salt_warning_emitted", False)
    with caplog.at_level(logging.WARNING, logger="showcase_api.middleware"):
        mw1 = middleware.RequestLoggingMiddleware(lambda *a: None)
        mw2 = middleware.RequestLoggingMiddleware(lambda *a: None)
    assert mw1._salt == "dev-salt" and mw2._salt == "dev-salt"
    warnings = [r for r in caplog.records if "IP_HASH_SALT" in r.getMessage()]
    assert len(warnings) == 1
    # an explicit salt (even via the env) suppresses the warning entirely
    monkeypatch.setattr(middleware, "_salt_warning_emitted", False)
    monkeypatch.setenv("IP_HASH_SALT", "from-env")
    with caplog.at_level(logging.WARNING, logger="showcase_api.middleware"):
        middleware.RequestLoggingMiddleware(lambda *a: None)
    assert [r for r in caplog.records if "IP_HASH_SALT" in r.getMessage()] == warnings


def test_request_log_line_contains_hashed_ip_not_raw(caplog) -> None:  # type: ignore[no-untyped-def]
    import logging

    with caplog.at_level(logging.INFO, logger="showcase_api.middleware"):
        client.get("/health", headers={"x-forwarded-for": "203.0.113.7"})
    lines = [
        rec.getMessage()
        for rec in caplog.records
        if rec.name == "showcase_api.middleware" and "GET /health -> 200" in rec.getMessage()
    ]
    assert len(lines) == 1
    line = lines[0]
    assert "203.0.113.7" not in line  # raw IP never logged
    assert "ip=" in line and "rid=" in line


def test_projects_and_demos_payloads_do_not_collide(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Regression: /demos hit BEFORE /projects must not poison the projects
    payload — both indexes cache by (root, kind) since sharing PROJECTS_ROOT."""
    (tmp_path / "01-demo-project").mkdir()
    (tmp_path / "01-demo-project" / "portfolio.yaml").write_text(
        "id: 01-demo-project\ntitle: Demo Project\ndomain: x\ntopic: T\n"
        "techniques: [t]\ndata: s\norder: 1\n"
    )
    (tmp_path / "01-demo-project" / "demo.yaml").write_text(
        "id: some-demo\ntitle: Some Demo\nhook: h.\nproject: 01-demo-project\n"
        "group: g\nskills: [x]\nmodes: [browser]\n"
    )
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)
    main._PAYLOAD_CACHE.clear()
    client = TestClient(main.app)
    demos_first = client.get("/demos")
    projects_after = client.get("/projects")
    assert projects_after.status_code == 200
    body = projects_after.json()
    assert any(p.get("id") == "01-demo-project" for p in body), body
    assert not any(p.get("id") == "some-demo" for p in body), body
    assert demos_first.status_code == 200


def test_every_committed_project_story_parses() -> None:
    """Guard against the C-phase content-edit failure mode: a story.yaml that
    drifts from the pydantic schema 500s its page. Every committed project
    must serve story 200 against the real repo tree."""
    from showcase_api.main import PROJECTS_ROOT, load_index

    ids = [m.id for m in load_index(PROJECTS_ROOT)]
    assert len(ids) >= 10, ids
    bad = [pid for pid in ids if client.get(f"/projects/{pid}/story").status_code != 200]
    assert not bad, f"story endpoints failing: {bad}"


def test_indexes_serialize_compact_no_spaces() -> None:
    """The pre-ETag FastAPI serializer emitted compact JSON; the docker
    smoke greps '"id":"01-rag-agent"'. The cached-payload path must too."""
    r = client.get("/projects")
    assert r.status_code == 200
    assert '"id": "01-rag-agent"' not in r.text
    assert '"id":"01-rag-agent"' in r.text
    d = client.get("/demos")
    assert d.status_code == 200
    assert ": " not in d.text.split('"hero"')[0]
