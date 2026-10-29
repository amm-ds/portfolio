#!/usr/bin/env python3
"""Scaffold a new showcase project with the standard platform layout.

Usage:
    uv run python scripts/new_project.py 08-recommendation "Product Recommendation"

Creates projects/08-recommendation/ wired for the uv workspace (pyproject with
portfolio-core/eval deps), portfolio.yaml + story.yaml skeletons (8 canonical
sections per portfolio_core.story), params.yaml, dvc.yaml template, typed src
stubs (config/schemas/cli), tests dir, data/reports/notebooks dirs.

Then: add your own dependencies to the pyproject, run `uv sync --all-packages`,
and implement the stages. See docs/engineering-playbook.md §Adding a project.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECTS_ROOT = REPO_ROOT / "projects"

PYPROJECT = """[project]
name = "{dirname}"
version = "0.1.0"
description = "Portfolio project {dirname}."
requires-python = ">=3.12"
dependencies = [
    # add project-specific deps here (keep them minimal and justified)
    "typer>=0.12",
    "plotly>=5.24",
    "polars>=1.9",
    "numpy>=2.1",
    "portfolio-core",
    "portfolio-eval",
]

[project.scripts]
{pkg} = "{pkg}.cli:app"

[tool.uv.sources]
portfolio-core = {{ workspace = true }}
portfolio-eval = {{ workspace = true }}

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{pkg}"]
"""

PORTFOLIO_YAML = """id: {dirname}
title: {title}
domain: <domain>
topic: <topic — display grouping key, e.g. "Forecasting & Time Series">
techniques:
  - <technique>
data: <source summary>
status: working
order: {order}
"""

STORY_YAML = """project_id: {dirname}
roadmap:
  - status: remaining
    text: <first roadmap item>
  - status: deferred
    text: <parked item — with its reason>
sections:
  - id: background
    text_md: |
      <why this problem matters — 2-4 short paragraphs>
  - id: objectives
    text_md: |
      <what success looks like; the SLOs/eval criteria>
  - id: data
    text_md: |
      <sources, licenses, why this data; add a dataset card to docs/data-registry/>
  - id: eda
    text_md: |
      <what the data looks like; reference 1-2 EDA figures>
  - id: training
    text_md: |
      <methods, why chosen; reference ADRs where relevant>
  - id: evaluation
    text_md: |
      <protocol: splits, metrics, gates — and the naive baseline you compare against>
  - id: results
    text_md: |
      <real numbers; a markdown run ladder table; the delta vs the naive baseline>
  - id: conclusions
    text_md: |
      <what works, what doesn't, what a client should take away>
"""

PARAMS_YAML = """seed: 42
"""

DVC_YAML = """stages:
  prepare:
    cmd: uv run python -m {pkg}.cli prepare
    deps:
      - src/{pkg}
      - params.yaml
    outs:
      - data
  evaluate:
    cmd: uv run python -m {pkg}.cli evaluate
    deps:
      - src/{pkg}
      - params.yaml
      - data
    outs:
      - reports/metrics.json
      - reports/report.html
      - reports/figures
"""

CONFIG_PY = '''"""Configuration: pydantic models only — no constants in logic."""

from portfolio_core.config import Settings as CoreSettings
from portfolio_core.schemas import PortfolioBaseModel


class Settings(CoreSettings):
    """Project settings (env handling inherited from the platform)."""


class ProjectConfig(PortfolioBaseModel):
    """Tunables for this project. Mirror every field in params.yaml."""

    seed: int = 42
'''

SCHEMAS_PY = '''"""Typed contracts for this project (ADR-0002)."""

from pydantic import Field

from portfolio_core.schemas import PortfolioBaseModel


class ExampleRecord(PortfolioBaseModel):
    """One validated record — replace with the project's real schema."""

    id: str = Field(min_length=1)
'''

CLI_PY = '''"""Typer entrypoints: one command per DVC stage."""

import typer

from {pkg}.config import ProjectConfig, Settings

app = typer.Typer(help="{dirname} pipeline CLI")


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
'''

README = """# {title}

> Status: scaffolded — follow docs/engineering-playbook.md §Adding a new showcase project.

- Problem: <one line>
- Design: [DESIGN.md](DESIGN.md)
- Story: [story.yaml](story.yaml) (served at `/projects/{dirname}/story`)

## Reproduce

```bash
uv run python -m {pkg}.cli prepare
uv run python -m {pkg}.cli evaluate
```
"""

MODEL_CARD = """# Model Card — {title}

## Intended use
<who/what this is for — and not for>

## Data
<sources, slices, known limitations>

## Metrics
<headline metrics by slice, evaluation protocol>

## Limits
<where the model/artifact should not be trusted>
"""

DESIGN = """# DESIGN — {title}

## Requirements

## Options considered

## Decision

## Changelog
"""

TEST_INIT = """def test_scaffold_imports() -> None:
    import {pkg}

    assert {pkg} is not None
"""


def package_name(slug: str) -> str:
    """Derive a valid import package name from the directory slug."""
    parts = slug.split("-")[1:]  # drop the NN- prefix
    pkg = "_".join(parts) or "project"
    if pkg[0].isdigit():
        pkg = f"project_{pkg}"
    return re.sub(r"[^a-z0-9_]", "", pkg.lower())


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    dirname = sys.argv[1]
    title = " ".join(sys.argv[2:]) or dirname
    if not re.match(r"^\d{2}-[a-z0-9-]+$", dirname):
        sys.exit(f"dir name must match NN-slug (e.g. 08-recommendation), got: {dirname}")
    root = PROJECTS_ROOT / dirname
    if root.exists():
        sys.exit(f"already exists: {root}")
    pkg = package_name(dirname)
    order = int(dirname[:2])
    fmt = dict(dirname=dirname, title=title, pkg=pkg, order=order)

    (root / "src" / pkg).mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "data").mkdir()
    (root / "reports").mkdir()
    (root / "notebooks").mkdir()
    (root / "data" / ".gitkeep").touch()

    files = {
        "pyproject.toml": PYPROJECT,
        "portfolio.yaml": PORTFOLIO_YAML,
        "story.yaml": STORY_YAML,
        "params.yaml": PARAMS_YAML,
        "dvc.yaml": DVC_YAML,
        "README.md": README,
        "DESIGN.md": DESIGN,
        "MODEL_CARD.md": MODEL_CARD,
        f"src/{pkg}/__init__.py": "",
        f"src/{pkg}/config.py": CONFIG_PY,
        f"src/{pkg}/schemas.py": SCHEMAS_PY,
        f"src/{pkg}/cli.py": CLI_PY,
        "tests/test_scaffold.py": TEST_INIT,
    }
    for rel, content in files.items():
        (root / rel).write_text(content.format(**fmt))

    print(f"scaffolded {root}")
    print("next: add deps to pyproject.toml, `uv sync --all-packages`, implement the stages")


if __name__ == "__main__":
    main()
