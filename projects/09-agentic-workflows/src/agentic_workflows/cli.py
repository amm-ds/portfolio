"""Typer entrypoints: one command per DVC stage."""

import typer

from agentic_workflows.config import ProjectConfig, Settings

app = typer.Typer(help="09-agentic-workflows pipeline CLI")


@app.command()
def prepare(config: str = "params.yaml") -> None:
    """Prepare stage (fetch/validate/materialize data)."""
    _ = ProjectConfig()  # load from `config` in real implementation
    _ = Settings()
    typer.echo("prepare: not implemented yet")


@app.command()
def evaluate(config: str = "params.yaml") -> None:
    """Evaluate stage (metrics, figures, report)."""
    _ = ProjectConfig()
    typer.echo("evaluate: not implemented yet")


if __name__ == "__main__":
    app()
