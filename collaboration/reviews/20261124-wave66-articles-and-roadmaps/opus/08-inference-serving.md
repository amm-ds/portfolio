# Review: 08-inference-serving `story.yaml` (Wave 6.6)

Reviewer: Claude Opus (read-only). Target: `projects/08-inference-serving/story.yaml` at working tree.
Note: `git diff -- projects/08-inference-serving/story.yaml` is empty. The Wave 6.6 edits are already committed in `18adc59d`, so this review covers that committed version.
Evidence checked: `reports/metrics.json` (19 cells), `data/bench_run.json`, `data/bench_run_repeat.json`, `data/prompts.json`, `params.yaml`, `README.md`, `DESIGN.md`, `docs/projects/08-inference-serving.md`, `docs/architecture/adr/0006-*.md`, `src/inference_serving/report.py`.

## Grades

| # | Dimension | Grade |
|---|---|---|
| 1 | Structure and article logic | 7 |
| 2 | Engagement and human-like narrative | 6 |
| 3 | Language quality | 5 |
| 4 | Technical detail depth | 7 |
| 5 | Truthfulness | 7 |
| 6 | Roadmap cards | 7 |
| 7 | Consistency with gold template | 6 |
| | **Overall** | **6.5** |

## 1. Structure and article logic (7)

- The arc works: one run, then the contract, the shared task, the guardrail, the grid, the latency limit, the engine panel, and the exact tables. Every section closes with a transition and an `In plain terms` card.
- **Rendering defect, L347:** ` ```diagram auto-08-inference-serving-4` has 12 spaces of indentation inside a 6-space block scalar. That leaves 6 leading spaces after YAML parsing, so Markdown reads it as an indented code block and the diagram fence does not render. Project 05 has the same defect at L353.
- L267: "That attempt remains in the revision notes in Details" points to a "Details" section that this article does not contain. The reader cannot follow the pointer.
- Conclusions repeats evaluation and results almost word for word. The "What the evidence shows" bullets L325–338 restate 2.9×, 7×, 0.81 s, 1.00, and 10–30× from earlier sections. The co-tenant repeat appears four times: L50, L265–267, L332–335, and L406–408.
- The transition at L240, "The grid sets the champion," claims more than the section shows. The training section shows throughput, and latency comes next.

## 2. Engagement and narrative (6)

- The background opens on a fact ("One laptop, one run."), not on a question or a stake. The gold opens with a reader-facing tension ("When every answer carries a citation, what can still go wrong?"). The serving story has a natural hook that goes unused: a model that "silently burned the entire 128-token budget" (docs L97). That fact is buried in EDA at L164–167.
- Several sections read as instructions to look at a diagram: "Follow the request envelope in the diagram", "Follow the serving-grid diagram from left to right", "The diagram's last step", "Use the measurement contract diagram as the study checklist". The narrative is about the diagrams, not about the decision.
- Concrete, human moments are missing. The article never says what a prompt looks like ("What is the capital of France?" in `data/prompts.json`) or roughly how long an answer is (about 45 output tokens per request, from 1810 tokens / 40 requests).

## 3. Language quality (5)

- **Choppy definition sentences (data, L118–137):** "Synthetic means made locally." / "Pydantic is a Python library for data checks." / "Deterministic means the same input gets the same result." / "Reasoning means intermediate thinking. It is off." This reads like readability-score tuning. An expert finds it patronising, and a novice still gets no flow.
- **Misplaced appositive, L62–63:** "MoE activates only 3B parameters per token, a text fragment." Grammatically, the 3B parameters become "a text fragment".
- **Non sequitur, L125–126:** "It is 0, so retries use the same setting." Temperature 0 makes decoding (near-)deterministic. It has nothing to do with retries. The only retry in `bench.py` is the one-shot `json_schema` fallback at L195.
- **Tautology, L389–390:** "Async HTTPX streaming uses a Python web client to receive tokens as they arrive."
- **"1 through 8" (L92, L112, L197)** suggests eight rungs. The rungs are 1/2/4/8, and the quant and engine arms only run at c=1.
- **Repetition:** "0.81" appears 9 times. "7×" appears 5 times. Every transition uses the same "X; next, the Y (…)" formula (L108, L145, L174, L240, L274, L297). Four of the eight `In plain terms` cards repeat the 0.81 s / 7× headline.
- "Records favor a 4-bit mixture-of-experts" (L62) is an awkward subject. "Packaging and quantization confound engine differences" (L413) is fine but jargon-dense next to the simplified data section, so the register is inconsistent.

## 4. Technical detail depth (7)

Strong points: nearest-rank percentiles, client-side semaphore pacing with a real code excerpt, separate aggregate and per-request tok/s, a clearly stated packaging confound, a recorded missing MLX build, and a cost formula that is reproducible (1e6 / 67.73 tok/s = 4.10 h × 0.1 kW × $0.30 = $0.123).

Gaps an expert would notice:
- With n=40 and nearest-rank, p99 is the maximum (rank ceil(0.99·40) = 40th of 40), and p95 is the 38th sample. The article presents p99 as a tail estimate without saying that it is a single observation.
- The near-linear p95 growth with flat or declining aggregate tok/s (L257–259, table L370) strongly suggests that the server serializes requests instead of batching them. The article states the shape but never names this interpretation or the Ollama parallelism setting. The docs page explicitly says the run "does not isolate memory bandwidth, batching, or another cause", and that caveat should appear here as well.
- `max_tokens 128` is never stated. L126 only says "a token budget". It matters for the reasoning-burn story and for TTFT and tok/s interpretation.
- gpt-oss:20b is a full grid arm (4 cells, c=1 p95 1.64 s, 36.8 tok/s), yet none of its numbers appear anywhere in the article. gemma4:31b (MLX) at c=1..8 is also absent from the "exact per-cell values" table, which shows 11 of 19 cells (L366–378), and TTFT is given only for qwen3.6. The text at L362–364 says the table "keeps the exact per-cell values", which overclaims.
- The QAT-int4 versus Q8_0 speed result (9.83 vs 6.43 tok/s, about 53% faster on the same runner) is the only clean quant comparison in the run, and the article never draws it out. It is in the table but not discussed.

## 5. Truthfulness

Verified against `reports/metrics.json` and the docs: 760 requests / 19 cells / 0 failures; all quality rates 1.00; qwen3.6 p50/p95/p99 and TTFT and tok/s for every rung (table L368–370 matches to 4 dp); qwen3:32b rows; gemma4 mlx/q8_0/qat c=1 rows; 7× (67.73/9.56 = 7.08); 2.9× (18.79/6.43 = 2.92); 18.8 / 6.4 tok/s and 2.47 / 7.12 s; $0.12 (re-derived); Ollama 0.40.4; macOS 26.5 arm64; 128 GB (docs page L26, ADR-0006); 2026-10-15; 2026-10-30 (`bench_run_repeat.json` `started_at`); 100 W and $0.30/kWh; 3 models × 3 rungs default and the under-45-minute target; switch-expert weights failure (DESIGN.md); reasoning burn with zero valid answers (docs L97); general-knowledge prompts (`prompts.json`); "hurt only the llama.cpp path" (MLX cells got 0.6–0.7× faster in the repeat).

Untraceable or contradicted:

| Line(s) | Claim | Finding |
|---|---|---|
| L189–190 | "a dense 32B at full precision" | **Untraceable, likely wrong.** No committed file states qwen3:32b's precision. The article's own table at L358 shows quant "—". Ollama's default `qwen3:32b` tag is a 4-bit GGUF, not full precision. |
| L190, L357 | gemma4:31b is "4-bit MLX" | **Untraceable.** DESIGN.md calls only the `-mlx` engine-panel tag 4-bit. No file states the quant of the plain `gemma4:31b` grid arm. |
| L50, L332, L407 | "degraded llama.cpp cells 10–30×" | **Untraceable as stated.** No committed file contains "10–30×". Re-deriving from `bench_run_repeat.json` against `bench_run.json` gives a wider and uneven spread: p95 ratios of 5.1× (gemma q8_0), 7.2–12.5× (qwen3.6), and 21–35× (gpt-oss), with tok/s drops of 5.3–28×. The figure should be re-derived and named in a committed artifact, or worded as "5–35×". |
| L333–334 | "This was memory-bandwidth contention from other workloads, not a build regression." | **Contradicted / unsupported.** The repeat ran on Ollama **0.40.12** (`bench_run_repeat.json` `ollama_version`), not 0.40.4, so a build change cannot be ruled out. `docs/projects/08-inference-serving.md` L89 says the run "does not isolate memory bandwidth". |
| L335 | "That repeat is outside the committed evidence path" | **Misleading.** `data/bench_run_repeat.json` is committed. It is outside the *aggregated* path, not outside the committed evidence. |
| L267 | "remains in the revision notes in Details" | **Untraceable pointer**: no such section in this article. |
| L362–364 | table "keeps the exact per-cell values" | **Overclaim**: 8 of 19 cells (gpt-oss ×4, gemma4:31b mlx ×4) are missing. |

Count: **3 untraceable numbers** (10–30×, "full precision" for the 32B, "4-bit" for gemma4:31b), plus 4 non-numeric claims that are untraceable or contradicted.

## 6. Roadmap cards (7)

- All titles are verb-first, and all details are 90 characters or fewer (the longest, L36, is 65). Status ordering is sensible: 4 shipped, then 1 next.
- L38 "Catch a silent config error pre-run" is good, but its detail at L39 ("Reasoning disabled before the committed runs.") drops the hook. A better detail: "Thinking mode burned the 128-token budget; reasoning now off."
- L45 joins two unrelated blockers ("quiet-hardware access and an MLX build for the MoE") into one card. The Limits section (L418–420) lists two separate pending items: re-measurement and quant-matched engine isolation. Split them, or add a second `next` card ("Isolate the engine with a same-quant pair").
- No card covers the quality gap the article admits (a saturated smoke check). A `later` card such as "Replace the smoke check with a graded task" would make the roadmap honest about the weakest dimension.
- L33 "8 schema-checked prompts with keyword checklists." would be stronger with the controls: "8 prompts, temp 0, 128-token cap, one Answer schema."

## 7. Consistency with gold template (6)

- `In plain terms` cards are present in every section, single-sentence or two-sentence, as in the gold. However, the gold cards add information, while these mostly repeat the headline (see Language).
- Gold transitions are full sentences in the voice of "we", with the link at the end ("Next, we set the rules each answer must clear ([Objectives →](#sec-objectives))."). The 08 transitions are noun-phrase fragments ("next, the serving grid and the throughput figure"). This is formulaic and diverges from the gold voice.
- The gold opens each section with a bold lead line. Here only background and objectives have one. Data, EDA, training, evaluation, and results start cold.
- The gold uses a target-versus-result table in objectives. 08 states no targets (for example, a p95 SLO at c=1), so the "verdict" in evaluation has nothing to be checked against.
- The gold keeps the diagram fence at block indentation. 08 L347 breaks this (see Structure).

## Top 5 fixes (by severity)

1. **`projects/08-inference-serving/story.yaml` L333–335: remove the unsupported causal claim.** Replace "This was memory-bandwidth contention from other workloads, not a build regression. That repeat is outside the committed evidence path shown here." with wording that names the confounds: the repeat ran on Ollama 0.40.12 under co-tenant load, the cause is not isolated, and the raw record is committed at `data/bench_run_repeat.json` but not aggregated. Apply the same correction at L265–267 and L406–408.
2. **L189–190 and L357–358: fix the model descriptions.** Drop "at full precision" for qwen3:32b, or verify the quant from the Ollama manifest and commit it. Do the same for "4-bit MLX" on `gemma4:31b`, so that the prose and the table at L358 ("—") agree.
3. **L50, L332, L407: re-derive "10–30×".** Either commit a derived ratio (for example, in `reports/`) and quote the true range (about 5–35× on p95), or say "5–35× slower depending on the arm". The number currently exists in no committed file.
4. **L347: un-indent ` ```diagram auto-08-inference-serving-4` to the 6-space block level** so the evidence-lineage diagram renders. Then complete the table at L366–378: add gpt-oss:20b and gemma4:31b (MLX) at c=1..8, or change L362–364 "keeps the exact per-cell values" to "selected cells; all 19 in `reports/metrics.json`".
5. **L118–137 and L62–63, L125–126: rewrite the data section in connected prose.** Merge the definition stubs ("Synthetic means made locally." "Pydantic is a Python library for data checks."), fix "per token, a text fragment" and "so retries use the same setting", state `max_tokens 128`, and say that the rungs are 1/2/4/8 (L92, L112, L197) rather than "1 through 8". While there, vary the six identical "; next, the …" transitions to match the gold's full-sentence form.
