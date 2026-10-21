"""Demo manifest: the showcase API and docs read ``demo.yaml`` files to serve
the manifest-driven demo platform instead of hardcoding demos."""

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import Field, field_validator

from portfolio_core.schemas import PortfolioBaseModel


class HeroMetric(PortfolioBaseModel):
    """Headline metric rendered on the demo card and view."""

    label: str
    value: str
    ci: str | None = None


class Scenario(PortfolioBaseModel):
    """Named preset for the demo controls, e.g. a high-cost-miss regime."""

    name: str = Field(pattern=r"^[a-z0-9-]+$")
    controls: dict[str, float | int | str | bool]


class LiveEndpoint(PortfolioBaseModel):
    """Live call the demo view may hit from the browser."""

    method: str = Field(pattern=r"^(GET|POST)$")
    path: str = Field(description="Route, must start with '/'")
    label: str
    cost: str = Field(default="free-local", description="e.g. 'free-local' or a $-per-call note")

    @field_validator("path")
    @classmethod
    def _absolute_path(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError("live endpoint path must start with '/'")
        return v


class PayloadRef(PortfolioBaseModel):
    """Reference to the committed payload JSON served by the API."""

    path: str = Field(description="Relative to the project dir, e.g. 'reports/demo_payload.json'")
    schema_version: int = 1
    required_keys: list[str] = Field(min_length=1)


class DemoManifest(PortfolioBaseModel):
    """One demo declared by ``projects/<pid>/demo.yaml``."""

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str
    hook: str = Field(min_length=1)
    project: str = Field(pattern=r"^\d{2}-[a-z0-9-]+$")
    group: str = Field(min_length=1, description="Business-problem grouping key for the index.")
    skills: list[str] = Field(default_factory=list)
    modes: list[str] = Field(min_length=1, description="e.g. 'browser' | 'live' | 'replay'")
    hero: HeroMetric | None = None
    scenarios: list[Scenario] = Field(default_factory=list)
    live_endpoints: list[LiveEndpoint] = Field(default_factory=list)
    payload: PayloadRef


def load_demo(root: Path) -> DemoManifest | None:
    """Read ``<root>/demo.yaml`` if present, else None."""
    manifest = root / "demo.yaml"
    if not manifest.exists():
        return None
    data = yaml.safe_load(manifest.read_text())
    return DemoManifest.model_validate(data)


def load_demo_index(projects_root: Path) -> list[DemoManifest]:
    """All demo manifests under ``projects/*/demo.yaml``, sorted by (group, id)."""
    projects = [p for p in projects_root.iterdir() if p.is_dir() and (p / "demo.yaml").exists()]
    demos = [d for p in projects if (d := load_demo(p)) is not None]
    return sorted(demos, key=lambda d: (d.group, d.id))


def to_registry_entry(m: DemoManifest) -> dict[str, object]:
    """Registry entry for the frontend demos index (fixed contract)."""
    return {
        "id": m.id,
        "title": m.title,
        "hook": m.hook,
        "group": m.group,
        "href": f"/demos/{m.id}",
        "project": m.project,
        "status": "live",
        "hero": m.hero.model_dump() if m.hero is not None else None,
    }
