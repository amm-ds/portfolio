# Verifier challenger checkpoint: license and source record

Date: 2026-11-20
Approval: handoff `collaboration/designs/20261119-rag-verifier-challenger/03-implementation-handoff.md`
Step 0 — "approved (owner, 2026-11-20): Phase 1 only, including the download of
the MiniCheck-FT5 checkpoint named in Step 0, subject to its license check."

## Checkpoint

- Name: **MiniCheck-FT5** — `lytang/MiniCheck-Flan-T5-Large` on HuggingFace
  (MiniCheck-Flan-T5-Large, 770M parameters; Tang, Laban & Durrett, EMNLP 2024,
  arXiv 2404.10774).
- Source: https://huggingface.co/lytang/MiniCheck-Flan-T5-Large
- HuggingFace repo revision (pinned): `96eafd01cee2d16cf81aaa2fb226b14f422a37b3`
  (lastModified 2024-12-20, per the `huggingface_hub` API at download time).

## License

- SPDX: **MIT** — confirmed at download time from the model card metadata:
  repo tag `license:mit` and `cardData.license: mit`, both returned by
  `HfApi.model_info("lytang/MiniCheck-Flan-T5-Large")` on 2026-11-20.
- The MIT license permits research and portfolio (public-repository) use,
  including commercial use; attribution is preserved here and in the harness
  module docstring. The upstream code repository
  (https://github.com/Liyan06/MiniCheck) is the implementation reference for
  the scoring recipe, which this project re-implements against its existing
  `transformers`/`torch` lockfile entries instead of adding the `minicheck`
  package.

## Files and hashes (resolved snapshot)

- Weights: `pytorch_model.bin`, 3,132,807,711 bytes (≈3.13 GB), sha256
  `41291881e13c6235ed47149cec903bee9493e45d9d7325587a9fa2e266c526c0`.
- Tokenizer/config files: `tokenizer.json`, `tokenizer_config.json`,
  `special_tokens_map.json`, `added_tokens.json`, `spiece.model`,
  `config.json`, `generation_config.json` (sizes recorded in the HF cache;
  not hashed individually — the pinned revision is the integrity anchor).

## Notes

- Downloaded to the local HF cache (`snapshot_download`, unauthenticated) on
  2026-11-20; nothing is vendored into the repository.
- Inference is CPU-only, fp32, batch size 1, fully offline at scoring time;
  no hosted calls are made by the harness.
