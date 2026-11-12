"""CLI config loading: params.yaml overlay and command surface (offline)."""

from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from rag_agent.cli import load_config
from rag_agent.config import RAGConfig


def test_load_config_defaults_without_params_yaml(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config()
    assert isinstance(config, RAGConfig)
    assert config.top_k == 5
    assert config.chunk_sizes == [200, 400, 800]


def test_load_config_overlays_known_keys_and_warns_unknown(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "params.yaml").write_text(
        "top_k: 7\nchunk_sizes:\n  - 100\nmystery_key: 1\n", encoding="utf-8"
    )
    config = load_config()
    assert config.top_k == 7
    assert config.chunk_sizes == [100]


def test_load_config_env_overrides_diagnostics_only(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """R6 diagnostics knobs: env overrides apply on top of params.yaml."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "params.yaml").write_text(
        "verify:\n  enabled: true\n  min_support: 0.6\n", encoding="utf-8"
    )
    monkeypatch.setenv("RAG_GATE_MIN_COVERAGE", "0.0")
    monkeypatch.setenv("RAG_GATE_MIN_MAX_SIMILARITY", "0.0")
    monkeypatch.setenv("VERIFY_DIAGNOSE_MECH", "true")
    config = load_config()
    assert config.evidence_gate.min_coverage == 0.0
    assert config.evidence_gate.min_max_similarity == 0.0
    assert config.verify.diagnose_mech is True
    # unrelated tunables keep their params.yaml values
    assert config.verify.min_support == 0.6


def test_load_config_env_overrides_absent_by_default(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for var in (
        "RAG_GATE_MIN_COVERAGE",
        "RAG_GATE_MIN_MAX_SIMILARITY",
        "VERIFY_DIAGNOSE_MECH",
    ):
        monkeypatch.delenv(var, raising=False)
    config = load_config()
    assert config.evidence_gate.min_coverage > 0.0
    assert config.verify.diagnose_mech is False
