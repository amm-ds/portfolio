"""Serving-artifact loading shared by the project POST endpoints.

Contract: ``projects/<pid>/reports/models/serving/`` holds ``model.joblib``
(a dict whose ``model`` key is the fitted estimator, per each project's
SERVING.md) and ``meta.json`` (schema/build metadata). Project 07 additionally
ships ``zones.json`` — pass it via ``extra_json``.

``load_artifacts`` reads the files once; ``cached_artifacts`` memoizes per
serving dir (the joblib load is ~ms per call on a multi-MB artifact — not
per-request material). Cache keys are the serving-dir paths, so monkeypatched
dirs in tests never collide with the real ones.
"""

import json
from pathlib import Path
from typing import Any

#: Parsed serving bundle: joblib model dict under ``model``, meta.json under
#: ``meta``, each ``extra_json`` file under its stem. None when absent.
Artifacts = dict[str, Any] | None

_cache: dict[Path, Artifacts] = {}


def load_artifacts(serving_dir: Path, extra_json: tuple[str, ...] = ()) -> Artifacts:
    """Load ``model.joblib`` + ``meta.json`` (+ any ``extra_json`` files).

    Returns ``None`` when the directory or any required file is absent, so
    endpoints can raise their 503-with-build-instructions.
    """
    model_path = serving_dir / "model.joblib"
    meta_path = serving_dir / "meta.json"
    if not (model_path.exists() and meta_path.exists()):
        return None
    import joblib

    artifacts: dict[str, Any] = {
        "model": joblib.load(model_path),
        "meta": json.loads(meta_path.read_text()),
    }
    for name in extra_json:
        path = serving_dir / name
        if not path.exists():
            return None
        artifacts[Path(name).stem] = json.loads(path.read_text())
    return artifacts


def cached_artifacts(serving_dir: Path, extra_json: tuple[str, ...] = ()) -> Artifacts:
    """Lazy per-directory cache around :func:`load_artifacts`."""
    key = Path(serving_dir)
    if key not in _cache:
        _cache[key] = load_artifacts(key, extra_json)
    return _cache[key]


def clear_cache() -> None:
    """Drop all cached bundles (tests reload after monkeypatching)."""
    _cache.clear()
