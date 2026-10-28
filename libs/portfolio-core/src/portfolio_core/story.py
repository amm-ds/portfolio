"""Case-study story contract: the common framework every project showcases.

Every project authors a ``story.yaml`` next to its ``portfolio.yaml``; the
showcase API serves it and the web app renders the sections uniformly. This
module is the single source of truth for the framework (platform.md §Contracts).
"""

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import Field, model_validator

from portfolio_core.schemas import PortfolioBaseModel

CANONICAL_SECTIONS: tuple[str, ...] = (
    "background",
    "objectives",
    "data",
    "eda",
    "training",
    "evaluation",
    "results",
    "conclusions",
)

SECTION_TITLES: dict[str, str] = {
    "background": "Background",
    "objectives": "Target & objectives",
    "data": "Data",
    "eda": "Exploratory analysis",
    "training": "Training & methods",
    "evaluation": "Evaluation setup",
    "results": "Results",
    "conclusions": "Conclusions & lessons",
}


class StorySection(PortfolioBaseModel):
    """One section of the case study.

    ``figures`` references names served by ``GET /projects/{id}/figures/{name}``
    (no extension). ``metrics_keys`` optionally references run names in
    ``reports/metrics.json`` the UI should highlight in this section.
    """

    id: str
    title: str = Field(default="", description="Empty → filled from the canonical section title.")
    text_md: str = Field(min_length=1, description="Client-readable markdown prose.")
    figures: list[str] = Field(default_factory=list)
    metrics_keys: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _canonical_id(self) -> "StorySection":
        if self.id not in CANONICAL_SECTIONS:
            raise ValueError(
                f"unknown story section id: {self.id!r}; canonical: {', '.join(CANONICAL_SECTIONS)}"
            )
        for fig in self.figures:
            if not fig.strip():
                raise ValueError("figure names must be non-empty")
        return self


class RoadmapItem(PortfolioBaseModel):
    """One roadmap entry. Status drives the case-study roadmap visual:
    delivered (done, with results elsewhere in the story), remaining
    (genuinely open forward work), or deferred (consciously parked, with
    the reason in the text)."""

    status: str = Field(pattern="^(delivered|remaining|deferred)$")
    text: str = Field(min_length=1, max_length=300)


class ProjectStory(PortfolioBaseModel):
    """The full case study for one project."""

    project_id: str = Field(min_length=1)
    headline: str | None = Field(
        default=None,
        description="One sentence: the result plus its uncertainty.",
    )
    data_note: str | None = Field(
        default=None,
        description="One sentence: real/synthetic, size, license.",
    )
    limits: str | None = Field(
        default=None,
        description="One sentence: what the story does not show.",
    )
    sections: list[StorySection] = Field(min_length=1)
    roadmap: list[RoadmapItem] = Field(
        default_factory=list,
        description="Finalized roadmap: delivered/deferred/remaining, no history.",
    )
    figure_captions: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Programmatically-linked commentary for figures, keyed by figure id "
            "(as listed in sections' `figures:`). Rendered as a footer under each "
            "chart in the showcase app — the chart itself stays clean (short "
            "descriptive title), the 'so what' lives here. Convention: caption "
            "every rendered figure, 1-2 plain-language sentences, numbers exact."
        ),
    )

    @model_validator(mode="after")
    def _unique_sections(self) -> "ProjectStory":
        ids = [s.id for s in self.sections]
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"duplicate story sections: {', '.join(dupes)}")
        return self

    @model_validator(mode="after")
    def _captions_match_rendered_figures(self) -> "ProjectStory":
        rendered = {f for s in self.sections for f in (s.figures or [])}
        strays = sorted(set(self.figure_captions) - rendered)
        if strays:
            raise ValueError(f"figure_captions keys without a rendered figure: {', '.join(strays)}")
        return self

    def section(self, section_id: str) -> StorySection | None:
        return next((s for s in self.sections if s.id == section_id), None)

    def roadmap_by_status(self, status: str) -> list[RoadmapItem]:
        return [r for r in self.roadmap if r.status == status]


def default_title(section_id: str) -> str:
    """Display title for a canonical section id."""
    return SECTION_TITLES.get(section_id, section_id.replace("_", " ").title())


def load_story(project_dir: Path) -> ProjectStory | None:
    """Parse ``<project_dir>/story.yaml``; None when not authored yet."""
    f = project_dir / "story.yaml"
    if not f.exists():
        return None
    data = yaml.safe_load(f.read_text())
    story = ProjectStory.model_validate(data)
    # Fill display titles for sections that only declared an id.
    for s in story.sections:
        if not s.title:
            s.title = default_title(s.id)
    return story
