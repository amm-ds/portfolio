"""Request schema: malformed payloads are rejected with the 422 shape."""

import pytest
from model_serving.service.app import create_app
from starlette.testclient import TestClient

VALID_ROW = {
    "hour": 8,
    "temp": 0.5,
    "hum": 0.6,
    "windspeed": 0.1,
    "weathersit": 1,
    "hour_sin": 0.5,
    "hour_cos": 0.5,
    "weekday_sin": 0.0,
    "weekday_cos": 1.0,
    "month_sin": 0.2,
    "month_cos": 0.9,
    "holiday": 0,
    "workingday": 1,
    "cnt_lag_1h": 120.0,
    "cnt_lag_24h": 150.0,
    "cnt_lag_168h": 140.0,
}


@pytest.fixture(scope="module")
def client(tiny_models: dict[str, object]) -> TestClient:
    app = create_app(models_dir=tiny_models["models_dir"], backend="native")  # type: ignore[arg-type]
    with TestClient(app) as c:  # lifespan runs warm-up
        yield c


def test_valid_row_returns_prediction(client: TestClient) -> None:
    r = client.post("/predict", json={"row": VALID_ROW})
    assert r.status_code == 200
    body = r.json()
    assert body["prediction"] > 0
    assert body["backend"] == "native"
    assert body["request_id"]


def test_hour_out_of_range_is_422(client: TestClient) -> None:
    bad = dict(VALID_ROW, hour=25)
    r = client.post("/predict", json={"row": bad})
    assert r.status_code == 422
    assert "detail" in r.json()


def test_missing_field_is_422(client: TestClient) -> None:
    r = client.post("/predict", json={"row": {"hour": 3}})
    assert r.status_code == 422


def test_wrong_type_is_422(client: TestClient) -> None:
    bad = dict(VALID_ROW, temp="hot")
    r = client.post("/predict", json={"row": bad})
    assert r.status_code == 422


def test_weathersit_out_of_domain_is_422(client: TestClient) -> None:
    bad = dict(VALID_ROW, weathersit=0)
    r = client.post("/predict", json={"row": bad})
    assert r.status_code == 422


def test_batch_limits_enforced(client: TestClient) -> None:
    empty = client.post("/predict/batch", json={"rows": []})
    assert empty.status_code == 422
    too_many = client.post("/predict/batch", json={"rows": [VALID_ROW] * 1025})
    assert too_many.status_code == 422
