"""Release gate coverage for story-rendered figure artifacts and captions."""

import importlib.util
from pathlib import Path

import pytest
import yaml

_SPEC = importlib.util.spec_from_file_location(
    "check_release_artifacts",
    Path(__file__).resolve().parents[1] / "check_release_artifacts.py",
)
release = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(release)


def _story_project(
    root: Path,
    *,
    payload: str | None = '{"data": [{"x": [1], "y": [2]}], "layout": {}}\n',
    caption: str | None = "The fixture figure compares two measured points.",
    project_name: str = "01-demo",
    figure: str = "trend",
    report_dir: str = "reports",
) -> Path:
    project = root / project_name
    figures = project / report_dir / "figures"
    figures.mkdir(parents=True)
    (project / "portfolio.yaml").write_text("status: active\n", encoding="utf-8")
    story = {
        "project_id": project_name,
        "short_version": "A measured demo result on a small fixture dataset.",
        "sections": [{"id": "results", "text_md": "Compare the two points.", "figures": [figure]}],
    }
    if caption is not None:
        story["figure_captions"] = {figure: caption}
    (project / "story.yaml").write_text(yaml.safe_dump(story), encoding="utf-8")
    if payload is not None:
        stem = figure.partition(":")[2] or figure
        (figures / f"{stem}.json").write_text(payload, encoding="utf-8")
    return project


def test_story_figures_accepts_present_nonempty_captioned_payload(tmp_path: Path) -> None:
    _story_project(tmp_path)

    assert release.check_story_figures(tmp_path) == []


@pytest.mark.parametrize(
    ("project_name", "figure", "report_dir"),
    [
        ("01-demo", "uci:trend", "reports_uci"),
        ("02-demand-forecasting", "m5_full_trend", "reports_m5_full"),
    ],
)
def test_story_figures_resolves_rendered_track_payloads(
    tmp_path: Path, project_name: str, figure: str, report_dir: str
) -> None:
    _story_project(tmp_path, project_name=project_name, figure=figure, report_dir=report_dir)

    assert release.check_story_figures(tmp_path) == []


def test_story_figures_rejects_missing_payload(tmp_path: Path) -> None:
    _story_project(tmp_path, payload=None)

    assert release.check_story_figures(tmp_path) == ["01-demo: missing story figure trend.json"]


@pytest.mark.parametrize("payload", ["", " \n\t"])
def test_story_figures_rejects_empty_payload(tmp_path: Path, payload: str) -> None:
    _story_project(tmp_path, payload=payload)

    assert release.check_story_figures(tmp_path) == ["01-demo: empty story figure trend.json"]


@pytest.mark.parametrize("caption", [None, "  \n"])
def test_story_figures_rejects_missing_or_blank_caption(
    tmp_path: Path, caption: str | None
) -> None:
    _story_project(tmp_path, caption=caption)

    assert release.check_story_figures(tmp_path) == [
        "01-demo: missing caption for story figure trend"
    ]
