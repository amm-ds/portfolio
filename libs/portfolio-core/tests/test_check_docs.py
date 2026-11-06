"""Focused tests for the first-party documentation gate."""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "check_docs.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_docs", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check_docs = _load_module()


def _write(root: Path, relative: str, text: str = "# Document\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_doc_files_covers_first_party_instruction_surfaces(tmp_path: Path) -> None:
    included = [
        "AGENTS.md",
        "README.md",
        "projects/01-example/README.md",
        "apps/example/README.md",
        "apps/example/nested/README.md",
        "libs/example/README.md",
        "registry/README.md",
        "deploy/DEPLOY.md",
        "deploy/nested/runbook.md",
        "docs/engineering/guide.md",
    ]
    excluded = [
        "apps/example/node_modules/dependency/README.md",
        "libs/example/.venv/package/README.md",
        "docs/engineering/skills/ponytail/SKILL.md",
        "docs/third_party/package/README.md",
    ]
    for relative in [*included, *excluded]:
        _write(tmp_path, relative)

    discovered = {path.relative_to(tmp_path).as_posix() for path in check_docs.doc_files(tmp_path)}

    assert discovered == set(included)


def test_code_fences_require_tags_and_accept_indented_closing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_docs, "REPO", tmp_path)
    tagged = _write(
        tmp_path,
        "deploy/tagged.md",
        "# Commands\n\n```bash\nuv run pytest -q\n  ```  \n",
    )
    untagged = _write(tmp_path, "apps/example/README.md", "# Tree\n\n```\nsrc/\n```\n")

    assert check_docs.check_code_fences([tagged]) == []
    assert check_docs.check_code_fences([untagged]) == [
        "apps/example/README.md:3: fenced block missing a language tag"
    ]
    assert check_docs.fenced_spans(tagged.read_text()) == [(3, 5)]


def test_current_snapshot_check_is_scoped_and_ignores_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_docs, "REPO", tmp_path)
    readme = _write(
        tmp_path,
        "projects/01-example/README.md",
        "# Current\n\n```text\nwave 14\n```\n\nWave 15 added a detector.\n",
    )
    design = _write(tmp_path, "projects/01-example/DESIGN.md", "## Changelog\n\nWave 15.\n")

    problems = check_docs.check_current_snapshots([readme, design])

    assert len(problems) == 1
    assert problems[0].startswith("projects/01-example/README.md:7: 'Wave 15'")


def test_command_heavy_readme_has_no_prose_or_dash_scoring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_docs, "REPO", tmp_path)
    readme = _write(
        tmp_path,
        "README.md",
        "# Commands\n\nUse 1\u20133 retries, x → y, and `a-b`.\n\n| a | b |\n|---|---|\n",
    )

    assert check_docs.check_current_snapshots([readme]) == []
    assert check_docs.check_code_fences([readme]) == []
