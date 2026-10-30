"""Unit tests for scripts/lint_story_language.py (the plain-language story gate).

The script is stdlib-only; the tests are not — they cross-check the script's
minimal YAML-subset parser against PyYAML on the ten committed story.yaml
files, so any drift between the hand-rolled parser and real YAML is caught.
"""

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "lint_story_language.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("lint_story_language", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclass introspection resolves the module via sys.modules
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lsl = _load_module()

MATCHER = lsl.glossary_matcher(lsl.load_glossary(lsl.GLOSSARY_JSON))


def _write_story(tmp_path: Path, body: str) -> Path:
    d = tmp_path / "99-test"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "story.yaml"
    f.write_text(body, encoding="utf-8")
    return f


def _lint(tmp_path: Path, body: str):
    return lsl.lint_story(_write_story(tmp_path, body), MATCHER)


CLEAN_STORY = """\
project_id: 99-test
short_version: Short copy for cards.
sections:
  - id: background
    text_md: |
      **In plain terms:** a small system that works. The naive baseline is beaten
      by a wide margin, with a holdout scored once at the end.
  - id: evaluation
    text_md: |
      **Business summary:** the gain is real on this data, and the holdout keeps
      it honest. The baseline is beaten by a wide margin, with a holdout scored
      once at the end.
  - id: conclusions
    text_md: |
      **Run and wave record.** Wave 3 added the holdout gate.
"""

# --- sentence splitting --------------------------------------------------------


def test_split_sentences_basic_punctuation():
    assert lsl.split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]


def test_split_sentences_protects_measurements_and_abbreviations():
    text = (
        "Recall is 0.831 vs. 0.677 on the graded set, i.e. a solid gap. "
        "See https://example.com/a.b for e.g. llama.cpp 0.40.12 builds. "
        "Wait... then it holds 4.2 pp. Done."
    )
    sents = lsl.split_sentences(text)
    assert len(sents) == 4, sents
    assert "0.831 vs. 0.677" in sents[0]
    assert "i.e." in sents[0]
    assert "https://example.com/a.b" in sents[1]
    assert "e.g." in sents[1] and "0.40.12" in sents[1]
    assert sents[2].startswith("Wait...") and "pp." in sents[2]
    assert sents[3] == "Done."


def test_split_sentences_strips_markdown_edge_markers():
    assert lsl.split_sentences("**Bold start.** Next sentence.")[0] == "Bold start."


def test_split_sentences_empty_and_punctuation_only():
    assert lsl.split_sentences("") == []
    assert lsl.split_sentences("...") == []


# --- syllables + Flesch --------------------------------------------------------


@pytest.mark.parametrize(
    ("word", "expected"),
    [("a", 1), ("the", 1), ("strengths", 1), ("equation", 3), ("rate", 1), ("700", 0)],
)
def test_count_syllables(word, expected):
    assert lsl.count_syllables(word) == expected


def test_flesch_ease_hand_computed():
    # 3 sentences, 33 monosyllabic words: 206.835 - 1.015*11 - 84.6*1.0
    sentence = "The cat sat on the mat and the dog ran far."
    score = lsl.flesch_ease(" ".join([sentence] * 3))
    assert score is not None
    assert abs(score - 111.07) < 0.01


def test_flesch_easy_text_scores_higher_than_jargon():
    easy = (
        "The cat sat on the mat. The dog ran to the barn. The sun was warm that day. "
        "The boy had a red kite. The girl drank cold milk."
    )
    jargon = (
        "Heteroscedastic tokenization pipelines amortize quantization drift across "
        "the backtest horizon. Recalibrated cross-encoder reranking modulates the "
        "approximate nearest-neighbour frontier. Regularized sequential calibration "
        "estimators stabilize drift under distribution shift."
    )
    easy_score, jargon_score = lsl.flesch_ease(easy), lsl.flesch_ease(jargon)
    assert easy_score is not None and jargon_score is not None
    assert easy_score > jargon_score


def test_flesch_ease_too_short_returns_none():
    assert lsl.flesch_ease("Too short.") is None


# --- duplicate top-level keys ---------------------------------------------------


def test_duplicate_top_level_keys_detected_with_lines():
    raw = (
        "project_id: p\n"
        "sections:\n"
        "  - id: background\n"
        "    text_md: x\n"
        "short_version: A\n"
        "sections:\n"
        "  - id: results\n"
        "    text_md: y\n"
        "short_version: B\n"
    )
    assert lsl.duplicate_top_level_keys(raw) == [("sections", 6), ("short_version", 9)]


def test_duplicate_top_level_keys_clean_file():
    assert lsl.duplicate_top_level_keys(CLEAN_STORY) == []


def test_duplicate_top_level_keys_ignores_indented_and_col0_list_items():
    raw = (
        "figure_captions:\n"
        "  a: one\n"
        "  a: two\n"  # nested map keys are not top-level duplicates
        "sections:\n"
        "- id: background\n"
        "  text_md: |\n"
        "    has a line\n"
        "- id: results\n"
        "  text_md: z\n"
    )
    assert lsl.duplicate_top_level_keys(raw) == []


# --- parser cross-check against PyYAML on the committed stories -----------------


def test_parse_story_matches_yaml_on_committed_stories():
    stories = sorted((REPO_ROOT / "projects").glob("*/story.yaml"))
    assert len(stories) == 10
    for f in stories:
        raw = f.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        parsed = lsl.parse_story(raw)
        assert parsed.section_ids == [s["id"] for s in data["sections"]], f.parent.name
        for section in data["sections"]:
            expected = section["text_md"].rstrip("\n")
            assert parsed.sections[section["id"]].rstrip("\n") == expected, (
                f.parent.name,
                section["id"],
            )
            assert parsed.figures.get(section["id"], []) == (section.get("figures") or []), (
                f.parent.name,
                section["id"],
            )


# --- lint_story rule behavior ---------------------------------------------------


def test_clean_story_has_no_errors(tmp_path):
    findings = _lint(tmp_path, CLEAN_STORY)
    assert [f for f in findings if f.level == "ERROR"] == []


def test_second_card_marker_in_one_section_is_error(tmp_path):
    body = CLEAN_STORY.replace(
        "      **In plain terms:** a small system that works.",
        "      **In plain terms:** a small system that works.\n\n"
        "      **Business summary:** a second card",
    )
    findings = _lint(tmp_path, body)
    assert any(f.rule == "summary-card-count" for f in findings)


def test_marker_not_in_final_block_is_error(tmp_path):
    body = CLEAN_STORY.replace(
        "      **In plain terms:** a small system that works. The naive baseline is beaten\n"
        "      by a wide margin, with a holdout scored once at the end.",
        "      Intro prose first.\n\n"
        "      **In plain terms:** a small system\n\n"
        "      Trailing prose after the card.",
    )
    findings = _lint(tmp_path, body)
    assert any(f.rule == "summary-card-placement" for f in findings)


def test_missing_card_warns_not_errors(tmp_path):
    body = (
        "project_id: 99-test\n"
        "sections:\n"
        "  - id: background\n"
        "    text_md: |\n"
        "      Plain prose with no summary card at all.\n"
    )
    findings = _lint(tmp_path, body)
    assert not any(f.level == "ERROR" for f in findings)
    assert any(f.rule == "no-summary-card" for f in findings)


def test_more_than_three_figures_in_section_is_error(tmp_path):
    body = (
        "project_id: 99-test\n"
        "sections:\n"
        "  - id: results\n"
        "    text_md: |\n"
        "      **Business summary:** four figures is one too many here.\n"
        "    figures: [one, two, three, four]\n"
    )
    findings = _lint(tmp_path, body)
    hits = [f for f in findings if f.rule == "figure-cap"]
    assert len(hits) == 1
    assert "4 figure cards" in hits[0].message


def test_block_style_figures_are_counted(tmp_path):
    body = (
        "project_id: 99-test\n"
        "sections:\n"
        "  - id: results\n"
        "    text_md: |\n"
        "      **Business summary:** three is the cap and three is fine.\n"
        "    figures:\n"
        "      - one\n"
        "      - two\n"
        "      - three\n"
    )
    findings = _lint(tmp_path, body)
    assert not any(f.rule == "figure-cap" for f in findings)


def test_changelog_in_conclusions_requires_revision_notes_heading(tmp_path):
    body = (
        "project_id: 99-test\n"
        "sections:\n"
        "  - id: conclusions\n"
        "    text_md: |\n"
        "      Main-thread wrap-up stays clean.\n\n"
        "      ### Revision notes\n\n"
        "      **Run and wave record.** Wave 3 added the holdout gate.\n"
    )
    findings = _lint(tmp_path, body)
    assert not any(f.rule == "changelog-phrase" for f in findings)
    # wave narrative before the heading is flagged even inside conclusions
    body2 = body.replace(
        "      Main-thread wrap-up stays clean.\n\n      ### Revision notes\n\n",
        "      Wave 2 shipped first.\n\n      ### Revision notes\n\n",
    )
    findings2 = _lint(tmp_path, body2)
    hits = [f for f in findings2 if f.rule == "changelog-phrase"]
    assert len(hits) == 1 and "Wave 2" in hits[0].message


def test_conclusions_without_revision_notes_heading_stay_grandfathered(tmp_path):
    # Legacy stories predate the subsection contract: their conclusions keep
    # the old blanket allowance until they adopt the skeleton.
    body = (
        "project_id: 99-test\n"
        "sections:\n"
        "  - id: conclusions\n"
        "    text_md: |\n"
        "      **Run and wave record.** Wave 3 added the holdout gate.\n"
    )
    findings = _lint(tmp_path, body)
    assert not any(f.rule == "changelog-phrase" for f in findings)


def test_changelog_phrases_banned_outside_conclusions(tmp_path):
    body = (
        "project_id: 99-test\n"
        "sections:\n"
        "  - id: background\n"
        "    text_md: |\n"
        "      Wave 12 added caching, per the wave-2 artifact and the changelog.\n"
        "  - id: conclusions\n"
        "    text_md: |\n"
        "      **Run and wave record.** Wave 3 added the holdout gate.\n"
    )
    findings = _lint(tmp_path, body)
    hits = [f for f in findings if f.rule == "changelog-phrase"]
    assert len(hits) == 3  # "Wave 12", "wave-2", "changelog"
    assert all(f.location == "section background" for f in hits)


@pytest.mark.parametrize("n_words", [119, 120])
def test_first_section_cap_boundary_ok(tmp_path, n_words):
    body = (
        "project_id: 99-test\n"
        "sections:\n"
        "  - id: background\n"
        "    text_md: |\n"
        f"      {'word ' * n_words}\n"
    )
    findings = _lint(tmp_path, body)
    assert not any(f.rule == "first-section-cap" for f in findings)


def test_first_section_over_cap_is_error(tmp_path):
    body = (
        "project_id: 99-test\n"
        "sections:\n"
        "  - id: background\n"
        "    text_md: |\n"
        f"      {'word ' * 121}\n"
    )
    findings = _lint(tmp_path, body)
    hits = [f for f in findings if f.rule == "first-section-cap"]
    assert len(hits) == 1
    assert "121 words" in hits[0].message


def test_bare_pp_is_error_dotted_pp_is_fine(tmp_path):
    body = (
        "project_id: 99-test\n"
        "sections:\n"
        "  - id: background\n"
        "    text_md: |\n"
        "      The rate rises 2 pp overall and 3 pp. on the next line.\n"
    )
    findings = _lint(tmp_path, body)
    hits = [f for f in findings if f.rule == "pp-abbreviation"]
    assert len(hits) == 1
    assert "1x" in hits[0].message


def test_glossary_term_only_in_code_warns(tmp_path):
    body = (
        "project_id: 99-test\n"
        "sections:\n"
        "  - id: background\n"
        "    text_md: |\n"
        "      The config names use `baseline` and `holdout`.\n"
    )
    findings = _lint(tmp_path, body)
    warned = {f.message.split("'")[1] for f in findings if f.rule == "glossary-first-use"}
    assert {"baseline", "holdout"} <= warned


def test_glossary_term_in_prose_does_not_warn(tmp_path):
    body = (
        "project_id: 99-test\n"
        "sections:\n"
        "  - id: background\n"
        "    text_md: |\n"
        "      The baseline is beaten and the holdout was scored once.\n"
    )
    findings = _lint(tmp_path, body)
    assert not any(f.rule == "glossary-first-use" for f in findings)


def test_duplicate_key_finding_via_lint_story(tmp_path):
    body = (
        "project_id: 99-test\n"
        "short_version: A\n"
        "sections:\n"
        "  - id: background\n"
        "    text_md: x\n"
        "short_version: B\n"
    )
    findings = _lint(tmp_path, body)
    hits = [f for f in findings if f.rule == "duplicate-key"]
    assert len(hits) == 1
    assert hits[0].location == "line 6"


def test_budget_warnings_fire_when_constants_tightened(tmp_path, monkeypatch):
    monkeypatch.setattr(lsl, "SECTION_WORD_BUDGET", 5)
    monkeypatch.setattr(lsl, "MAIN_THREAD_WORD_BUDGET", 10)
    findings = _lint(tmp_path, CLEAN_STORY)
    rules = {f.rule for f in findings}
    assert "section-budget" in rules
    assert "main-thread-budget" in rules


# --- main() end-to-end ----------------------------------------------------------


def test_main_exit_codes_and_summary(tmp_path, capsys):
    (tmp_path / "98-clean").mkdir()
    (tmp_path / "98-clean" / "story.yaml").write_text(CLEAN_STORY.replace("99-test", "98-clean"))
    (tmp_path / "97-dirty").mkdir()
    (tmp_path / "97-dirty" / "story.yaml").write_text(
        CLEAN_STORY.replace("99-test", "97-dirty").replace(
            "      **In plain terms:** a small system",
            "      **In plain terms:** a small system that is 2 pp better",
        )
    )
    glossary = tmp_path / "glossary.json"
    glossary.write_text(
        '[{"term": "baseline", "slug": "baseline"}, {"term": "holdout", "slug": "holdout"}]'
    )
    rc = lsl.main(["--projects-root", str(tmp_path), "--glossary", str(glossary)])
    out = capsys.readouterr().out
    assert rc == 1  # the dirty story carries a pp-abbreviation ERROR
    # warnings: 3 sections x 2 stories without a figure/diagram (6 no-visual),
    # plus a low reading-ease on both evaluation sections (2)
    assert "2 stories — 1 error, 8 warnings" in out
    assert "97-dirty" in out and "pp-abbreviation" in out


def test_main_fails_when_no_stories(tmp_path, capsys):
    rc = lsl.main(["--projects-root", str(tmp_path)])
    assert rc == 1
    assert "no story.yaml" in capsys.readouterr().err
