"""Diagram-fence gate: an unregistered fence id fails, the real repo resolves."""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "check_diagram_fences",
    Path(__file__).resolve().parents[1] / "check_diagram_fences.py",
)
fences = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(fences)


def test_unregistered_fence_is_reported(tmp_path: Path) -> None:
    story = tmp_path / "projects" / "99-fixture" / "story.yaml"
    story.parent.mkdir(parents=True)
    story.write_text(
        "sections:\n- id: background\n  text_md: |\n"
        "    ```diagram known-spec\n    ```\n    ```diagram missing-spec\n    ```\n",
        encoding="utf-8",
    )
    registry = tmp_path / "index.ts"
    registry.write_text('export const S = {\n  "known-spec": KNOWN_SPEC,\n};\n', encoding="utf-8")
    refs = fences.fence_refs(tmp_path / "projects")
    assert [spec_id for _, spec_id in refs] == ["known-spec", "missing-spec"]
    failures = fences.unresolved(refs, fences.registered_ids((registry,)))
    assert failures == [
        "projects/99-fixture/story.yaml: ```diagram missing-spec``` is not registered"
    ]


def test_every_committed_fence_resolves() -> None:
    assert fences.unresolved(fences.fence_refs(), fences.registered_ids()) == []
