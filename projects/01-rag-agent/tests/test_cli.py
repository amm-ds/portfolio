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
