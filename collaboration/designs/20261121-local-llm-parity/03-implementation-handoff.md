# Implementation handoff: local LLM parity test (MLX vs Ollama)

Date: 2026-11-21
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-21): download of `mlx-community/Qwen3.6-35B-A3B-4bit` (about 20.4 GB) and deletion of Ollama models if disk space requires it. Zero hosted calls. Nothing else approved.

## Objective

Check whether MLX-LM serving the same Qwen3.6 35B-A3B model behaves like the Ollama copy the project already uses. This is the parity test only (L2). The full 120-question local run (L3) is NOT approved and needs its own owner approval after this report.

## Standing rules

- Branch `local-llm-parity-2026-11-21` from `main`. Commit with trailer `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`. Push with upstream. No merge.
- Zero hosted calls. Every model call goes to localhost. If any request leaves the machine, stop.
- MLX environment is `~/.venvs/mlx-lm` (mlx-lm 0.32.2, already installed). Do not install other dependencies into the project without stopping to ask.
- Do not edit the 01 project's production code, `params.yaml`, prompts, or committed reports.

## Disk rule (read first)

- Before the download, check free space. The download needs about 21 GB. Stop if free space would fall below 25 GB after it.
- Ollama deletions are allowed ONLY if free space is short. Candidate order: `gpt-oss:20b` (13 GB; referenced by project 08, so note that in the report), then `qwen3:4b` (2.5 GB). Delete at most what is needed to stay above 25 GB.
- NEVER delete `qwen2.5:3b` (digest `357c53fb659c…`, the pinned judge), `qwen3.6:35b-a3b-q4_K_M` (the local agent model used in the comparison), or `qwen3-embedding:0.6b`.
- Record every deletion (model, digest, size) in the report before doing it.
- Also record Hugging Face cache usage before and after. Do not delete anything from the Hugging Face cache.

## Steps

1. **Baseline (no download).** Record `df -h /`, `ollama list`, and the Ollama digest of `qwen3.6:35b-a3b-q4_K_M`. Record the chip and RAM.
2. **Download.** Download `mlx-community/Qwen3.6-35B-A3B-4bit` into the default Hugging Face cache using `~/.venvs/mlx-lm/bin/python`. Record the revision (commit hash) of the snapshot and total size.
3. **Serve.** Start `mlx_lm.server` on `127.0.0.1:8080` with that model, from `~/.venvs/mlx-lm`. Confirm with a `curl` to `127.0.0.1` only.
4. **Parity prompts (10 fixed prompts).** Choose them from the sealed-v2 questions and two short generation tasks. Run each prompt through BOTH the MLX server and Ollama (`qwen3.6:35b-a3b-q4_K_M`), with temperature 0 and the same system prompt and max tokens. Save both outputs side by side in `reports/local_llm_parity/`.
5. **Tool-call check.** Run 3 prompts that must call `search_documents` and 1 that must call `read_excerpt`, through the project's agent code path with the local endpoint. Record whether the tool calls parse, how many, and whether the final output validates against the `AnalysisResult` schema. Use the project's existing local path (`RAG_NATIVE_OUTPUT` setting as needed). Do not change production code.
6. **Speed.** Record tokens per second for both backends on the same prompt, and the peak memory.
7. **Report.** Write `collaboration/reviews/20261121-local-llm-parity-report/00-report.md` with: the revision and sizes, disk before and after, every deletion, the 10-prompt comparison (exact-match rate and where outputs differ), tool-call results, speed and memory, and a recommendation: proceed to L3, or not, and why.

## Gates

- Project 01 tests: `uv run pytest -q projects/01-rag-agent` (run only if code changed; report the 78.45% coverage gate separately).
- `uv run python scripts/check_headline_numbers.py` and `uv run python scripts/check_docs.py` (run if docs changed).
- Report actual output. Do not claim a gate passed unless it ran.

## Stop conditions

- Free disk would fall below 25 GB after the download, or Ollama deletions would be needed beyond the candidates above: stop and report.
- Any request leaves the machine (hosted call): stop.
- The Ollama digest of `qwen2.5:3b` or `qwen3.6:35b-a3b-q4_K_M` changes: stop.
- The MLX server fails to load the model or crashes twice: stop and report.
- Any parity or tool-call failure: report it. Do not start L3.

## Not approved in this handoff

- The 120-question local run (L3). Needs owner approval after the report.
- Any change to the production configuration or the judge.
- Any deletion outside the list above.
