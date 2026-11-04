"""Service behavior: health/ready, batch==per-row, paired backends, request ids."""

from model_serving.artifacts import probe_grid
from model_serving.bench import payloads_from_grid
from model_serving.config import ServingConfig
from model_serving.service.app import create_app
from model_serving.service.model import ModelLoader
from model_serving.service.schemas import FeatureRow
from starlette.testclient import TestClient


def _row_dict(tiny_models: dict[str, object]) -> dict[str, object]:
    cfg = tiny_models["cfg"]
    assert isinstance(cfg, ServingConfig)
    grid = probe_grid(4, cfg.seed, tiny_models["selected"])  # type: ignore[arg-type]
    return payloads_from_grid(grid, 1, cfg.seed)[0]


def test_health_and_ready(tiny_models: dict[str, object]) -> None:
    app = create_app(models_dir=tiny_models["models_dir"], backend="onnx")  # type: ignore[arg-type]
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json()["backend"] == "onnx"


def test_prediction_matches_direct_loader(tiny_models: dict[str, object]) -> None:
    app = create_app(models_dir=tiny_models["models_dir"], backend="native")  # type: ignore[arg-type]
    row = _row_dict(tiny_models)
    loader = ModelLoader(tiny_models["models_dir"], "native")  # type: ignore[arg-type]
    (direct,) = loader.predict_rows([FeatureRow.model_validate(row)])
    with TestClient(app) as client:
        got = client.post("/predict", json={"row": row}).json()["prediction"]
    assert abs(got - float(direct)) < 1e-6


def test_batch_equals_per_row(tiny_models: dict[str, object]) -> None:
    app = create_app(models_dir=tiny_models["models_dir"], backend="onnx")  # type: ignore[arg-type]
    rows = [_row_dict(tiny_models) for _ in range(3)]
    with TestClient(app) as client:
        batch = client.post("/predict/batch", json={"rows": rows}).json()["predictions"]
        singles = [client.post("/predict", json={"row": r}).json()["prediction"] for r in rows]
    for b, s in zip(batch, singles, strict=True):
        assert abs(b - s) < 1e-6


def test_paired_backends_agree(tiny_models: dict[str, object]) -> None:
    row = _row_dict(tiny_models)
    preds = {}
    for backend in ("native", "onnx"):
        app = create_app(models_dir=tiny_models["models_dir"], backend=backend)  # type: ignore[arg-type]
        with TestClient(app) as client:
            preds[backend] = client.post("/predict", json={"row": row}).json()["prediction"]
    assert abs(preds["native"] - preds["onnx"]) < 1e-2


def test_request_id_echoed_in_header_and_body(tiny_models: dict[str, object]) -> None:
    app = create_app(models_dir=tiny_models["models_dir"], backend="native")  # type: ignore[arg-type]
    with TestClient(app) as client:
        r = client.post("/predict", json={"row": _row_dict(tiny_models)})
        assert r.headers["X-Request-Id"] == r.json()["request_id"]
        echoed = client.post(
            "/predict",
            json={"row": _row_dict(tiny_models)},
            headers={"X-Request-Id": "fixed-id-1"},
        )
        assert echoed.json()["request_id"] == "fixed-id-1"
