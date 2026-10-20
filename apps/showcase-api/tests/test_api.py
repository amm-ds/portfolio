import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from showcase_api.main import app
from showcase_api.middleware import RateLimiter, RateLimitMiddleware

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


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


def test_demo_payload_route(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    pid = main.DEMO_PAYLOADS["churn-sandbox"]
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path)

    r = client.get("/demos/churn-sandbox/payload")
    assert r.status_code == 404  # payload not built yet

    reports = tmp_path / pid / "reports"
    reports.mkdir(parents=True)
    payload = {"demo": "churn-threshold-sandbox", "thresholds": [0.1]}
    (reports / "demo_payload.json").write_text(json.dumps(payload))
    r = client.get("/demos/churn-sandbox/payload")
    assert r.status_code == 200
    assert r.json() == payload

    assert client.get("/demos/nope/payload").status_code == 404


def test_forecast_503_without_artifacts(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from showcase_api import main

    monkeypatch.setattr(main, "_SERVING_DIR", tmp_path / "no-such-dir")
    r = client.post(
        "/projects/07-open-data-mobility/forecast",
        json={"zone_id": 132, "features": {"lag_24": 5.0}},
    )
    assert r.status_code == 503


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
    assert "busy" in r.json()["detail"]
