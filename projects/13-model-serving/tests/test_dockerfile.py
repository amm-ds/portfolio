"""Dockerfile + compose: lint-level contract checks (no daemon in tests)."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _dockerfile() -> str:
    return (PROJECT_ROOT / "Dockerfile").read_text()


def _compose() -> str:
    return (PROJECT_ROOT / "docker-compose.yml").read_text()


def test_multistage_uv_lock_install() -> None:
    text = _dockerfile()
    assert text.count("FROM") >= 2  # build + runtime stages
    assert "uv sync --frozen" in text  # lockfile-pinned install
    assert "python:3.12-slim" in text  # slim runtime base
    assert "--no-editable" in text  # self-contained venv in the runtime stage


def test_runtime_hygiene() -> None:
    text = _dockerfile()
    assert "USER appuser" in text
    assert "EXPOSE 8000" in text
    assert "HEALTHCHECK" in text
    assert "--factory" in text and "model_serving.service.app:create_app" in text
    # the venv is built at its final path — venv shebangs are absolute
    assert "WORKDIR /app" in text and "/opt/ws" not in text


def test_model_is_baked_in() -> None:
    text = _dockerfile()
    assert "image/serving" in text and "/app/models" in text
    assert "SERVING_BACKEND" in text


def test_compose_api_and_smoke() -> None:
    text = _compose()
    assert "api:" in text and "smoke:" in text
    assert "service_healthy" in text  # smoke waits for the healthcheck
    assert "model_serving.service.smoke" in text
    assert "8138:8000" in text  # host port kept away from the bench port


def _slim_dockerfile() -> str:
    return (PROJECT_ROOT / "Dockerfile.slim").read_text()


def test_slim_multistage_explicit_pins() -> None:
    text = _slim_dockerfile()
    assert text.count("FROM") >= 2  # build + runtime stages
    # no workspace sync: an explicit minimal pin set, locked to uv.lock versions
    assert "uv venv" in text and "uv pip install" in text
    assert "uv sync" not in text
    for pin in (
        "fastapi==0.143.0",
        "uvicorn==0.54.0",
        "onnxruntime==1.31.1",
        "numpy==2.5.4",
        "pydantic==2.14.1",
        "pydantic-settings==2.15.0",
    ):
        assert pin in text, f"slim pin drifted from uv.lock: {pin}"
    assert "--no-deps ./libs/portfolio-core" in text
    # pandas is train-stage only: the service imports it nowhere on the ONNX
    # path (mlp.py is imported lazily by the native branch) — shipping it
    # would double the venv for nothing.
    assert "pandas" not in text.split("FROM", 1)[-1]


def test_slim_is_onnx_only_and_torch_free() -> None:
    text = _slim_dockerfile()
    assert "SERVING_BACKEND=onnx" in text
    assert "PYTHONPATH=/app" in text  # source copied, not pip-installed
    # hard contract: no torch among the actual build instructions (the header
    # comment naming what was removed is fine)
    instructions = text.split("FROM", 1)[-1]
    assert "torch" not in instructions


def test_slim_runtime_hygiene_matches_full() -> None:
    slim = _slim_dockerfile()
    for token in ("USER appuser", "EXPOSE 8000", "HEALTHCHECK", "--factory"):
        assert token in slim, f"slim image lost the full image's {token}"
    assert "model_serving.service.app:create_app" in slim
