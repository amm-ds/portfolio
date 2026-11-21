# Local LLM parity report: MLX-LM vs Ollama (Qwen3.6-35B-A3B)

Date: 2026-11-21
Handoff: `collaboration/designs/20261121-local-llm-parity/03-implementation-handoff.md`
(approved: download + conditional deletions; zero hosted calls; L2 parity only)
Branch: `local-llm-parity-2026-11-21` from `main`. No merge, no deploy.
**Zero hosted calls: every request went to 127.0.0.1 or localhost.**

## 1. Baseline and disk

- Machine: Apple M4 Max, 128 GB RAM. Disk before: **78 GB free** (`df -h /`).
- Ollama models before (name / digest / size):
  - `qwen2.5:3b` `357c53fb659c5076de1d…` 1.93 GB — the pinned judge; digest
    re-verified after all work: **unchanged** (stop condition clear).
  - `qwen3:4b` `359d7dd4bcdab3d86b87…` 2.5 GB
  - `qwen3-embedding:0.6b` `ac6da0dfba84a81fdbfb…` 0.64 GB
  - `gpt-oss:20b` `f38aa0c53da5f8c49d08…` 13.79 GB (referenced by project 08)
  - `qwen3.6:35b-a3b-q4_K_M` `07d35212591fc27746f0…` 23.94 GB — the comparison
    model; digest re-verified after all work: **unchanged**.
- Hugging Face cache before: 19 GB.
- **Download**: `mlx-community/Qwen3.6-35B-A3B-4bit`, revision
  **`38740b847e4cb78f352aba30aa41c76e08e6eb46`** (also `refs/main`), 1,727 s,
  snapshot 19 GB on disk. HF cache after: 38 GB (nothing deleted from it).
- Disk after: **59 GB free** — above the 25 GB floor by 34 GB.
- **Ollama deletions: none.** Free space after the download (59 GB) made them
  unnecessary, as the owner predicted.

## 2. Serving

- `mlx_lm.server` (mlx-lm 0.32.2, `~/.venvs/mlx-lm`) on `127.0.0.1:8080`,
  started once, stayed up for all checks.
- Protocol note found during setup: Qwen3.6 is a thinking model. MLX accepts
  `chat_template_kwargs: {"enable_thinking": false}` on `/v1/chat/completions`;
  Ollama's `/v1` endpoint ignores both that flag and `think:false` (verified),
  so Ollama was driven via its native `/api/chat` with `think: false`,
  `stream: false`, `temperature: 0`, `num_predict: 512` — same effective
  configuration on both backends.

## 3. Parity prompts (10, temperature 0, same system prompt and 512-token ceiling)

8 sealed-v2 questions (including 120-index 53, the pathological Eysturoy
question) + 2 short generation tasks. Outputs saved side by side in
`reports/local_llm_parity/prompt_outputs.json`.

- **Exact-match rate: 0/10.**
- **Semantic parity: strong.** All 10 pairs agree on the facts, structure, and
  conclusions; differences are phrasings only (e.g. "This tunnel, which
  connects" vs "This tunnel connects"). Even the pathological unanswerable
  question produced the same correct opening date from both backends.
- Interpretation: exact string parity across two inference engines is not
  achievable (different kernels/numerics amplify at temperature 0). For L3,
  parity must be defined semantically (or by answer-correctness against the
  sealed labels), not by string equality.

## 4. Agent tool-call check (project agent code path, `RAG_NATIVE_OUTPUT=1`)

4 sealed questions (3 expected to search, 1 to read an excerpt), same
retriever, per backend. Counts recorded at the Retriever seam; schema check
against `AnalysisResult`. Full rows in `tool_call_check.json`.

| backend | search calls | read calls | schema-valid | note |
|---|---|---|---|---|
| MLX (4/4 cases) | 1 each | 1 each | **0/4** | tools parse and execute correctly; the grammar-constrained final answer hit the provider default token ceiling: `UnexpectedModelBehavior: Model token limit (provider default) exceeded before any response was generated` |
| Ollama (4/4 cases) | 0 | 0 | **4/4** | schema-valid JSON answers produced **without any tool call** on these prompts |

Two distinct behaviors, neither a drop-in match for the other: MLX's tool
protocol works end-to-end but its constrained generation overruns the server
default token cap (fixable server-side; no production change needed), while
Ollama answered parametrically without retrieval on these four prompts — a
grounding-behavior difference that must be reconciled with the eval path's
observed tool use before any L3 run.

## 5. Speed and memory

- Throughput on the 10 parity prompts (completion tokens / time): **MLX 78.7
  tok/s average** (23.6 cold → ~94-99 warm); **Ollama 95.8 tok/s average**
  (81.8-102.7). Total wall time for the 10 prompts: MLX 31.9 s, Ollama 34.9 s
  (MLX's shorter total is warm-cache skew on the shared machine — treat the
  per-prompt numbers as the comparison). Ollama is ~20% faster on this
  workload.
- Memory: Ollama reports **28 GB** for `qwen3.6:35b-a3b-q4_K_M` (`ollama ps`,
  100% GPU, 262k context). MLX's process RSS is not attributable on Apple
  silicon (Metal unified memory is wired, not charged to the process: server
  RSS reads 0.3 GB with the 19 GB model loaded); with MLX serving under load,
  system wired memory was 34 GB. Both fit comfortably in 128 GB; MLX's disk
  footprint is 19 GB vs Ollama's 23.94 GB for the same model.

## 6. Recommendation

**Do not proceed to L3 yet.** The parity layer that matters for the project
is the agent path, and it is not yet clean:

1. **MLX**: tool calls work, but every final-answer generation hit the MLX
   server default token ceiling under NativeOutput grammar constraint. Before
   L3, serve MLX with an explicit token ceiling (e.g. `--max-tokens 8192`) and
   re-run the 4-case check — no production code involved.
2. **Ollama**: on the same four prompts the model produced schema-valid JSON
   with zero tool calls; the eval path's tool use (seen in the G4 local repro)
   needs reconciling (prompt selection vs settings) so a local L3 measures
   retrieval-grounded answering, not parametric recall.
3. **Parity definition**: replace exact-match with a semantic/label-based
   criterion for any L3 go/no-go.

Raw generation parity (facts, style, speed class, memory class) is good
enough that MLX remains a viable local backend once the two agent-path items
are resolved. Speed is roughly comparable (Ollama ~20% faster), memory is a
wash in practice.

## 7. Gates and stop conditions

- No production code changed; project-01 pytest gate not required (script-only
  addition). The parity script passes ruff, ruff format, and mypy.
- `check_headline_numbers.py` / `check_docs.py`: docs changed only under
  `reports/` and `collaboration/` — ran both: headline shows only the external
  project-02 findings (S4 still blocked, owner to identify); docs OK.
- Stop conditions: no hosted calls; both protected digests unchanged; no
  deletions needed or performed; MLX server loaded on the first attempt and
  stayed up.

## 8. Deletions

**None.** The download alone (78 → 59 GB free) kept the disk above the 25 GB
floor; `gpt-oss:20b` and `qwen3:4b` were never at risk and nothing outside
the approved candidate list was touched.
