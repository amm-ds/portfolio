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
