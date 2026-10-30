from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from portfolio_core.story import (
    CANONICAL_SECTIONS,
    ProjectStory,
    RoadmapItem,
    StorySection,
    load_story,
)


def _section(sid: str, **kw: object) -> StorySection:
    return StorySection(id=sid, title="T", text_md="body", **kw)  # type: ignore[arg-type]


_SHORT = "Plain short copy used for cards and SEO."


def test_full_canonical_story_roundtrip(tmp_path: Path) -> None:
    story = ProjectStory(
        project_id="01-demo",
        short_version=_SHORT,
        sections=[
            StorySection(id=sid, title="", text_md=f"content of {sid}")
            for sid in CANONICAL_SECTIONS
        ],
    )
    import yaml

    (tmp_path / "story.yaml").write_text(
        yaml.safe_dump(story.model_dump(mode="json"), sort_keys=False)
    )
    loaded = load_story(tmp_path)
    assert loaded is not None
    assert [s.id for s in loaded.sections] == list(CANONICAL_SECTIONS)
    results = loaded.section("results")
    assert results is not None and results.title != ""  # canonical title filled


def test_unknown_section_id_rejected() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        StorySection(id="motivation", title="T", text_md="x")


def test_duplicate_sections_rejected() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProjectStory(
            project_id="p",
            short_version=_SHORT,
            sections=[_section("background"), _section("background")],
        )


@given(
    st.lists(
        st.text(alphabet=st.characters(whitelist_categories=("Zs",)), min_size=0, max_size=3),
        min_size=1,
        max_size=3,
    )
)
def test_empty_figure_names_rejected(figs: list[str]) -> None:
    from pydantic import ValidationError

    try:
        _section("data", figures=figs)
    except ValidationError:
        pass
    else:
        for f in figs:
            assert f.strip()


def test_load_story_missing(tmp_path: Path) -> None:
    assert load_story(tmp_path) is None


def test_story_ordering_and_figures() -> None:
    story = ProjectStory(
        project_id="p",
        short_version=_SHORT,
        sections=[
            StorySection(id="background", title="B", text_md="x", figures=["overview"]),
            StorySection(id="results", title="R", text_md="y", metrics_keys=["gbm_mean"]),
        ],
    )
    assert story.sections[0].figures == ["overview"]
    assert story.sections[1].metrics_keys == ["gbm_mean"]


def test_roadmap_block_roundtrip(tmp_path: Path) -> None:
    story = ProjectStory(
        project_id="p",
        short_version=_SHORT,
        sections=[_section("background")],
        roadmap=[
            RoadmapItem(status="delivered", text="Shipped thing"),
            RoadmapItem(status="remaining", text="Open thing"),
            RoadmapItem(status="deferred", text="Parked thing — needs X"),
        ],
    )
    import yaml

    (tmp_path / "story.yaml").write_text(
        yaml.safe_dump(story.model_dump(mode="json"), sort_keys=False)
    )
    loaded = load_story(tmp_path)
    assert loaded is not None
    assert len(loaded.roadmap) == 3
    assert [r.status for r in loaded.roadmap] == ["delivered", "remaining", "deferred"]
    assert len(loaded.roadmap_by_status("remaining")) == 1


def test_roadmap_status_validated() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RoadmapItem(status="planned", text="x")


def test_header_fields_default_to_none() -> None:
    story = ProjectStory(project_id="p", short_version=_SHORT, sections=[_section("background")])
    assert story.headline is None
    assert story.data_note is None
    assert story.limits is None


def test_header_fields_parsed() -> None:
    story = ProjectStory(
        project_id="p",
        short_version=_SHORT,
        headline="MAE 12.3 ± 1.1 on the holdout month.",
        data_note="Real, 1.1M rows, CC-BY-4.0.",
        limits="Does not cover cross-city transfer.",
        sections=[_section("background")],
    )
    assert story.headline == "MAE 12.3 ± 1.1 on the holdout month."
    assert story.data_note == "Real, 1.1M rows, CC-BY-4.0."
    assert story.limits == "Does not cover cross-city transfer."


def test_header_fields_roundtrip(tmp_path: Path) -> None:
    import yaml

    (tmp_path / "story.yaml").write_text(
        yaml.safe_dump(
            {
                "project_id": "p",
                "short_version": _SHORT,
                "headline": "Result with uncertainty.",
                "data_note": "Synthetic, 50k rows, MIT.",
                "limits": "Not a causal claim.",
                "sections": [{"id": "background", "text_md": "x"}],
            },
            sort_keys=False,
        )
    )
    loaded = load_story(tmp_path)
    assert loaded is not None
    assert loaded.headline == "Result with uncertainty."
    assert loaded.data_note == "Synthetic, 50k rows, MIT."
    assert loaded.limits == "Not a causal claim."


@pytest.mark.parametrize("field", ["headline", "data_note", "limits"])
def test_header_fields_reject_wrong_types(field: str) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProjectStory(
            project_id="p",
            short_version=_SHORT,
            sections=[_section("background")],
            **{field: 42},  # type: ignore[arg-type]
        )


def test_short_version_required() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProjectStory(project_id="p", sections=[_section("background")])


def test_short_version_parsed_and_length_capped() -> None:
    from pydantic import ValidationError

    story = ProjectStory(
        project_id="p",
        short_version="A forecast pipeline that beats the seasonal-naive floor on real demand.",
        sections=[_section("background")],
    )
    assert story.short_version == (
        "A forecast pipeline that beats the seasonal-naive floor on real demand."
    )

    with pytest.raises(ValidationError):
        ProjectStory(project_id="p", short_version="", sections=[_section("background")])
    with pytest.raises(ValidationError):
        ProjectStory(project_id="p", short_version="x" * 281, sections=[_section("background")])


def test_short_version_rejects_wrong_type() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProjectStory(
            project_id="p",
            short_version=42,  # type: ignore[arg-type]
            sections=[_section("background")],
        )


def test_short_version_roundtrip(tmp_path: Path) -> None:
    import yaml

    (tmp_path / "story.yaml").write_text(
        yaml.safe_dump(
            {
                "project_id": "p",
                "short_version": "Plain short copy used for cards and SEO.",
                "sections": [{"id": "background", "text_md": "x"}],
            },
            sort_keys=False,
        )
    )
    loaded = load_story(tmp_path)
    assert loaded is not None
    assert loaded.short_version == "Plain short copy used for cards and SEO."


def test_section_titles_fixed_template() -> None:
    from portfolio_core.story import SECTION_TITLES

    assert SECTION_TITLES == {
        "background": "Background",
        "objectives": "Target & objectives",
        "data": "Data",
        "eda": "Exploratory analysis",
        "training": "Training & methods",
        "evaluation": "Evaluation setup",
        "results": "Results",
        "conclusions": "Conclusions & lessons",
    }


def test_load_story_fills_fixed_template_titles(tmp_path: Path) -> None:
    (tmp_path / "story.yaml").write_text(
        "project_id: p\n"
        f"short_version: {_SHORT}\n"
        "sections:\n"
        "  - id: background\n"
        "    text_md: x\n"
        "  - id: conclusions\n"
        "    text_md: y\n"
    )
    loaded = load_story(tmp_path)
    assert loaded is not None
    assert loaded.sections[0].title == "Background"
    assert loaded.sections[1].title == "Conclusions & lessons"


def test_section_figures_capped_at_three() -> None:
    from pydantic import ValidationError

    ok = _section("results", figures=["a", "b", "c"])
    assert ok.figures == ["a", "b", "c"]
    with pytest.raises(ValidationError):
        _section("results", figures=["a", "b", "c", "d"])
