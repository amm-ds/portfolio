"""R8.1: repo-scope export must never ship secrets, whatever their origin."""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "export_agent_chat_zip",
    Path(__file__).resolve().parents[1] / "export_agent_chat_zip.py",
)
export = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(export)


def test_secret_name_patterns() -> None:
    for name in (
        ".env",
        ".env.production",
        ".env.local",
        ".env.staging",
        "service.pem",
        "private.key",
        "backup.key",
        "cert.pem",
        "id_rsa",
        "id_ed25519",
        "id_ecdsa",
        "other-local.db",
        "data.sqlite",
        "data.sqlite3",
        "credentials.json",
        "secrets.yaml",
        "config.secret.yaml",
        "keystore.jks",
        "bundle.p12",
        "prod.pfx",
        "vault.jks",
        "id_rsa.pem",
    ):
        assert export._is_secret(name), name


def test_normal_code_is_not_flagged() -> None:
    for name in (
        "main.py",
        "config.py",
        "params.yaml",
        "pyproject.toml",
        "uv.lock",
        "README.md",
        "story.yaml",
        "dataset_contract.json",
        "id_rsa.pub",  # public keys are not secrets
    ):
        assert not export._is_secret(name), name


def test_collect_files_excludes_secret_variants(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    for secret in (
        ".env.production",
        ".env.local",
        "service.pem",
        "private.key",
        "backup.key",
        "cert.pem",
        "other-local.db",
        "data.sqlite",
        "credentials.json",
        "secrets.yaml",
        "config.secret.yaml",
        "keystore.jks",
        "bundle.p12",
        "prod.pfx",
        "vault.jks",
        "id_rsa",
        "id_ed25519",
        "id_ecdsa",
        "id_rsa.pem",
    ):
        (tmp_path / secret).write_text("nope", encoding="utf-8")
    origins = {"tracked": {"src/main.py"}, "ignored": set(), "untracked": set()}
    files = export.collect_files(origins, tmp_path)
    assert set(files) == {"src/main.py"}
