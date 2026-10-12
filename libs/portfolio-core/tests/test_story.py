from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from portfolio_core.story import (
    CANONICAL_SECTIONS,
    ProjectStory,
    StorySection,
    load_story,
)


def _section(sid: str, **kw: object) -> StorySection:
    return StorySection(id=sid, title="T", text_md="body", **kw)  # type: ignore[arg-type]


def test_full_canonical_story_roundtrip(tmp_path: Path) -> None:
    story = ProjectStory(
        project_id="01-demo",
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
        sections=[
            StorySection(id="background", title="B", text_md="x", figures=["overview"]),
            StorySection(id="results", title="R", text_md="y", metrics_keys=["gbm_mean"]),
        ],
    )
    assert story.sections[0].figures == ["overview"]
    assert story.sections[1].metrics_keys == ["gbm_mean"]
