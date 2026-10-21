from pathlib import Path

import pytest
from portfolio_core.demo import DemoManifest, load_demo, load_demo_index, to_registry_entry
from pydantic import ValidationError

_VALID = """
id: churn-sandbox
title: churn threshold sandbox
hook: Move the threshold.
project: 05-ml-pipeline-churn
group: retain customers
modes: [browser, live]
payload:
  path: reports/demo_payload.json
  required_keys: [demo, project]
"""


def _write(tmp_path: Path, text: str = _VALID) -> Path:
    (tmp_path / "demo.yaml").write_text(text)
    return tmp_path


def test_load_demo_roundtrip(tmp_path: Path) -> None:
    demo = load_demo(_write(tmp_path))
    assert isinstance(demo, DemoManifest)
    assert demo.id == "churn-sandbox"
    assert demo.modes == ["browser", "live"]
    assert demo.payload.path == "reports/demo_payload.json"
    entry = to_registry_entry(demo)
    assert entry == {
        "id": "churn-sandbox",
        "title": "churn threshold sandbox",
        "hook": "Move the threshold.",
        "group": "retain customers",
        "href": "/demos/churn-sandbox",
        "project": "05-ml-pipeline-churn",
        "status": "live",
        "hero": None,
    }


def test_load_demo_missing_returns_none(tmp_path: Path) -> None:
    assert load_demo(tmp_path) is None


def test_demo_index_sorted_by_group_and_id(tmp_path: Path) -> None:
    (tmp_path / "01-zeta").mkdir()
    (tmp_path / "01-zeta" / "demo.yaml").write_text(
        _VALID.replace("churn-sandbox", "zz-demo")
        .replace("retain customers", "aaa-group")
        .replace("05-ml-pipeline-churn", "01-zeta")
    )
    (tmp_path / "02-no-demo").mkdir()
    (tmp_path / "03-alpha").mkdir()
    (tmp_path / "03-alpha" / "demo.yaml").write_text(
        _VALID.replace("retain customers", "aaa-group")
        .replace("05-ml-pipeline-churn", "03-alpha")
    )
    idx = load_demo_index(tmp_path)
    assert [d.id for d in idx] == ["churn-sandbox", "zz-demo"]
    assert all(isinstance(d, DemoManifest) for d in idx)


def test_bad_id_pattern_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        load_demo(_write(tmp_path, _VALID.replace("id: churn-sandbox", "id: Bad ID!")))


def test_missing_hook_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        load_demo(_write(tmp_path, _VALID.replace("hook: Move the threshold.\n", "")))


def test_live_endpoint_path_must_be_absolute(tmp_path: Path) -> None:
    bad = _VALID.replace(
        "payload:", "live_endpoints:\n  - {method: POST, path: no-slash, label: x}\npayload:"
    )
    with pytest.raises(ValidationError):
        load_demo(_write(tmp_path, bad))
