"""Exporter contract tests: exclusions, per-file provenance, git failure (P1-4)."""

import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

GIT = shutil.which("git") or "/usr/bin/git"


def _git(*args: str, cwd: Path) -> None:
    subprocess.run([GIT, *args], cwd=cwd, check=True)  # noqa: S603 - test fixture


REPO_ROOT = Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    "export_agent_chat_zip", REPO_ROOT / "scripts" / "export_agent_chat_zip.py"
)
assert _SPEC is not None and _SPEC.loader is not None
exporter = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault(_SPEC.name, exporter)
_SPEC.loader.exec_module(exporter)


@pytest.fixture()
def handoff(tmp_path, monkeypatch):
    """A throwaway git repo shaped like the real one: tmp/apps/agent-chat + tmp/artifacts."""
    root = tmp_path / "repo"
    app = root / "apps" / "agent-chat"
    app.mkdir(parents=True)
    (app / "src").mkdir()
    (app / "src" / "tracked.py").write_text("print('tracked')\n")
    (root / ".gitignore").write_text("artifacts/\nignored-reports/\n")
    (app / "ignored-reports").mkdir()
    (app / "ignored-reports" / "focus.json").write_text("{}")

    _git("init", "-q", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "t", cwd=root)
    _git("add", "-A", cwd=root)
    _git("commit", "-qm", "seed", cwd=root)
    # untracked: created after the seed commit
    (app / "untracked-note.txt").write_text("hi")

    monkeypatch.setattr(exporter, "REPO", root)
    monkeypatch.setattr(exporter, "APP", app)
    monkeypatch.setattr(exporter, "OUT_DIR", root / "artifacts" / "agent-chat-zips")
    monkeypatch.setattr(sys, "argv", ["export_agent_chat_zip.py"])
    return root, app


def run_export() -> Path:
    assert exporter.main() == 0
    zips = sorted((exporter.OUT_DIR).glob("*.zip"))
    assert zips, "no zip produced"
    return zips[-1]


def manifest(zf_path: Path) -> dict:
    with zipfile.ZipFile(zf_path) as zf:
        return json.loads(zf.read("STATUS.json"))


def test_runner_state_and_sensitive_files_are_excluded(handoff):
    _, app = handoff
    for rel in [
        "node_modules/dep/index.js",
        "test-results/.last-run.json",
        "playwright-report/index.html",
        "coverage/lcov.info",
        ".venv/lib/site.py",
        "agent_chat_memory/session.json",
        "data/raw/corpus.jsonl",
        "data/index/faiss.bin",
        "dist/bundle.js",
        "agent_chat.db",
        ".env",
        ".DS_Store",
        "pkg/__pycache__/mod.pyc",
    ]:
        p = app / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")

    meta = manifest(run_export())
    shipped = set(meta["files"])
    for rel in [
        "node_modules/dep/index.js",
        "test-results/.last-run.json",
        "playwright-report/index.html",
        "coverage/lcov.info",
        ".venv/lib/site.py",
        "agent_chat_memory/session.json",
        "data/raw/corpus.jsonl",
        "data/index/faiss.bin",
        "dist/bundle.js",
        "agent_chat.db",
        ".env",
        ".DS_Store",
        "pkg/__pycache__/mod.pyc",
    ]:
        assert rel not in shipped, rel
    # intended payload present
    assert "src/tracked.py" in shipped
    assert "untracked-note.txt" in shipped  # provenance-labeled, still shipped


def test_per_file_provenance_and_counts(handoff):
    meta = manifest(run_export())
    files = meta["files"]
    assert files["src/tracked.py"]["origin"] == "tracked"
    assert files["ignored-reports/focus.json"]["origin"] == "ignored"
    assert files["untracked-note.txt"]["origin"] == "untracked"
    assert meta["payload_origins"] == {"tracked": 1, "ignored": 1, "untracked": 1}


def test_dirty_flag_reports_modified_tracked_file(handoff):
    _, app = handoff
    (app / "src" / "tracked.py").write_text("changed\n")
    meta = manifest(run_export())
    assert meta["dirty"] is True
    assert any("tracked.py" in line for line in meta["dirty_files"])
    # ignored files alone do not make the export dirty
    (app / "ignored-reports" / "focus.json").write_text('{"new": 1}')
    meta2 = manifest(run_export())
    assert meta2["dirty"] is True  # still the tracked.py modification


def test_versions_increment_and_diff_against_previous(handoff, capsys):
    run_export()
    _, app = handoff
    (app / "new-file.txt").write_text("new")
    zf = run_export()
    meta = manifest(zf)
    assert meta["version"] == 2
    out = capsys.readouterr().out
    assert "added (1): new-file.txt" in out


def test_fails_clearly_outside_a_git_worktree(tmp_path, monkeypatch, capsys):
    root = tmp_path / "not-a-repo"
    app = root / "apps" / "agent-chat"
    app.mkdir(parents=True)
    (app / "x.py").write_text("x")
    monkeypatch.setattr(exporter, "REPO", root)
    monkeypatch.setattr(exporter, "APP", app)
    monkeypatch.setattr(exporter, "OUT_DIR", root / "artifacts")
    monkeypatch.setattr(sys, "argv", ["export_agent_chat_zip.py"])
    assert exporter.main() == 1
    assert "git" in capsys.readouterr().err.lower()
