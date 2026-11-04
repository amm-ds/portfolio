"""Typer CLI: train → benchmark → docker → report (+ serve).

``all`` chains every stage in-process; each individual command is what
``dvc.yaml`` runs per stage. ``serve`` is the project-local FastAPI entry the
benchmark harness and the container both use.
"""

from pathlib import Path
from typing import Annotated

import typer
from portfolio_core.logging import get_logger

from model_serving.config import load_config
from model_serving.service.model import BackendName

app = typer.Typer(
    help="Model API serving & Docker deployment for the champion tabular MLP (exp. 12 recipe).",
    add_completion=False,
)
log = get_logger(__name__)

OptParams = Annotated[Path, typer.Option(help="YAML file with config keys.")]
OptBackend = Annotated[BackendName, typer.Option(help="Serving backend.")]
OptHost = Annotated[str, typer.Option(help="Bind host.")]
OptPort = Annotated[int, typer.Option(help="Bind port.")]


@app.command()
def train(params_file: OptParams = Path("params.yaml")) -> None:
    """Re-derive the champion (exp. 12 recipe), persist native + ONNX artifacts."""
    from model_serving.artifacts import train_core

    train_core(load_config(params_file))


@app.command()
def benchmark(params_file: OptParams = Path("params.yaml")) -> None:
    """Load-test the running service: concurrency sweep + batch curve, both backends."""
    from model_serving.bench import benchmark_core

    benchmark_core(load_config(params_file))


@app.command()
def docker(params_file: OptParams = Path("params.yaml")) -> None:
    """Multi-stage image build, size measurement, compose smoke."""
    from model_serving.dockerbuild import docker_core

    docker_core(load_config(params_file))


@app.command()
def report(params_file: OptParams = Path("params.yaml")) -> None:
    """Assemble metrics.json, figures, report.html + results.md from the artifacts."""
    from model_serving.report import report_core

    report_core(load_config(params_file))


@app.command()
def serve(
    backend: OptBackend = "onnx",
    host: OptHost = "127.0.0.1",
    port: OptPort = 8137,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Run the serving app (what the harness and the container start)."""
    import uvicorn

    from model_serving.service.app import create_app

    cfg = load_config(params_file)
    models_dir = cfg.data_dir / "models"
    log.info("serve: backend=%s models=%s on %s:%d", backend, models_dir, host, port)
    uvicorn.run(create_app(models_dir=models_dir, backend=backend), host=host, port=port)


@app.command("all")
def run_all(params_file: OptParams = Path("params.yaml")) -> None:
    """Run the full study: train → benchmark → docker → report."""
    train(params_file)
    benchmark(params_file)
    docker(params_file)
    report(params_file)


if __name__ == "__main__":
    app()
