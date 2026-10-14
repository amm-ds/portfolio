"""Project manifest: the showcase API and docs read ``portfolio.yaml`` files
instead of parsing READMEs (platform.md §Contracts)."""

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import Field

from portfolio_core.schemas import PortfolioBaseModel


class ProjectInfo(PortfolioBaseModel):
    id: str = Field(pattern=r"^\d{2}-[a-z0-9-]+$")
    title: str
    domain: str
    topic: str = Field(min_length=1, description="Display grouping key for the projects index.")
    techniques: list[str]
    data: str = Field(description="Data source summary, e.g. 'NYC TLC (real)'")
    status: str = Field(default="working", pattern="^(flagship|working|planned)$")
    order: int = 0


def load_project(root: Path) -> ProjectInfo | None:
    manifest = root / "portfolio.yaml"
    if not manifest.exists():
        return None
    data = yaml.safe_load(manifest.read_text())
    return ProjectInfo.model_validate(data)


def load_index(projects_root: Path) -> list[ProjectInfo]:
    """All project manifests, ordered for presentation."""
    projects = [
        p for p in projects_root.iterdir() if p.is_dir() and (p / "portfolio.yaml").exists()
    ]
    infos = [info for p in projects if (info := load_project(p)) is not None]
    return sorted(infos, key=lambda i: (i.order, i.id))
