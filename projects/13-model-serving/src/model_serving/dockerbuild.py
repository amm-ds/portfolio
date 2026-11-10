"""Docker stage: stage artifacts, multi-stage build, real size, compose smoke.

The build context is the repository root (the root .dockerignore keeps the
fat out; the uv workspace + lockfile live at the root). The model is baked
in — ``image/serving/`` is staged from ``data/models/`` by this stage, so the
image never depends on a DVC cache. When the daemon is unavailable the stage
still records what it could not measure, instead of inventing a number.
"""

# ruff: noqa: S603,S607 - this module's whole job is driving the local `docker`
# CLI with fixed, module-built argv; no user input reaches subprocess.

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from portfolio_core.logging import get_logger

from model_serving.config import ServingConfig

log = get_logger(__name__)

DOCKERFILE = "Dockerfile"
STAGING_DIR = Path("image") / "serving"
BASE_IMAGE = "python:3.12-slim"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return project_root().parents[1]


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    r = subprocess.run(["docker", "info"], capture_output=True, text=True, check=False)
    return r.returncode == 0


def stage_artifacts(cfg: ServingConfig) -> Path:
    """Copy the serving artifacts to the image staging dir (context-visible).

    Root .dockerignore excludes every ``data/`` directory from the build
    context, so the baked-in model is staged under ``image/serving/`` — this
    stage, not the Dockerfile, owns that copy step.
    """
    src = cfg.data_dir / "models"
    if not (src / "model.onnx").exists():
        raise FileNotFoundError(f"{src}/model.onnx missing — run the train stage first")
    dst = project_root() / STAGING_DIR
    dst.mkdir(parents=True, exist_ok=True)
    for name in ("mlp.pt", "mlp_arch.json", "mlp_meta.json", "feature_contract.json", "model.onnx"):
        shutil.copy2(src / name, dst / name)
    return dst


def _docker(
    *args: str, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, cwd=cwd, check=check)


def build_image(cfg: ServingConfig) -> str:
    """Multi-stage build from the repo root; returns the image id."""
    r = _docker(
        "build",
        "--quiet",
        "-f",
        f"projects/13-model-serving/{DOCKERFILE}",
        "-t",
        cfg.image_ref,
        ".",
        cwd=repo_root(),
    )
    # --quiet prints the image id (build progress goes to stderr).
    return r.stdout.strip().splitlines()[-1]


def image_size_mb(image_ref: str) -> float:
    r = _docker("image", "inspect", "-f", "{{.Size}}", image_ref)
    return int(r.stdout.strip()) / 1e6


def image_footprint(image_ref: str) -> dict[str, Any]:
    """Size breakdown: runtime base, the synced venv, the baked model."""
    if _docker("image", "inspect", BASE_IMAGE, check=False).returncode != 0:
        _docker("pull", "-q", BASE_IMAGE)
    r = _docker(
        "run", "--rm", "--entrypoint", "/bin/sh", image_ref, "-c", "du -sm /app/.venv /app/models"
    )
    sizes: dict[str, float] = {}
    for line in r.stdout.strip().splitlines():
        size, path = line.split("\t")
        sizes[path] = float(size)
    return {
        "base_python_slim_mb": image_size_mb(BASE_IMAGE),
        "venv_mb": sizes.get("/app/.venv"),
        "models_mb": sizes.get("/app/models"),
        "total_mb": image_size_mb(image_ref),
    }


def compose_smoke(cfg: ServingConfig) -> dict[str, Any]:
    """docker compose: api + one-shot smoke service; returns the prediction."""
    compose = project_root() / "docker-compose.yml"
    project = "model-serving-13"
    up = _docker(
        "compose", "-p", project, "-f", str(compose), "up", "-d", "--wait", "api", cwd=repo_root()
    )
    if up.returncode != 0:
        _docker("compose", "-p", project, "-f", str(compose), "down", "-v", cwd=repo_root())
        raise RuntimeError(f"compose api did not become healthy:\n{up.stderr}")
    try:
        run = _docker(
            "compose", "-p", project, "-f", str(compose), "run", "--rm", "smoke", cwd=repo_root()
        )
        prediction: float | None = None
        for line in run.stdout.splitlines():
            if line.startswith("SMOKE prediction:"):
                prediction = float(line.split(":", 1)[1])
        ok = run.returncode == 0 and prediction is not None
        return {"passed": ok, "prediction": prediction, "stdout": run.stdout.strip()}
    finally:
        _docker("compose", "-p", project, "-f", str(compose), "down", "-v", cwd=repo_root())


def docker_core(cfg: ServingConfig) -> Path:
    """Build, measure, smoke — and record exactly which numbers are measured."""
    started = time.perf_counter()
    result: dict[str, Any] = {
        "dockerfile": DOCKERFILE,
        "compose": "docker-compose.yml",
        "build_context": "repository root (uv workspace; root .dockerignore applies)",
        "daemon_available": docker_available(),
    }
    if result["daemon_available"]:
        stage_artifacts(cfg)
        image_id = build_image(cfg)
        result["image_id"] = image_id
        result["image_ref"] = cfg.image_ref
        result.update(image_footprint(cfg.image_ref))
        smoke = compose_smoke(cfg)
        result["compose_smoke"] = smoke
        result["docker_run_alternative"] = (
            f"docker run --rm -p 8137:8000 -e SERVING_BACKEND=onnx {cfg.image_ref}"
        )
        result["measured"] = True
    else:
        result["measured"] = False
        result["note"] = (
            "docker daemon unavailable — image size and compose smoke not measured; "
            "the Dockerfile is exercised by tests/test_dockerfile.py lint checks only."
        )
    result["docker_runtime_s"] = round(time.perf_counter() - started, 3)
    out = cfg.reports_dir / "docker_run.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    log.info("docker: measured=%s -> %s", result["measured"], out)
    return out
