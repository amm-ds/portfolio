# Round-2 review: 08-inference-serving `story.yaml`

Reviewer: Claude Opus (read-only). Target: `projects/08-inference-serving/story.yaml` at HEAD (last changed in `e69bba84`).
Round-1 review: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/08-inference-serving.md` (reviewed `18adc59d`).
Evidence re-checked: `reports/metrics.json` (19 cells, `_meta` lineage), `data/bench_run.json` (Ollama 0.40.4, 2026-10-15, `full: true`), `data/bench_run_repeat.json` (Ollama **0.40.12**, 2026-10-30, `full: false`), `params.yaml`, `README.md`, `DESIGN.md`, `docs/projects/08-inference-serving.md`, `docs/architecture/adr/0006-*.md`, `reports/figures/*.json`, `apps/showcase-web/src/lib/markdown.tsx` (fence parser). One external fact checked online: the gpt-oss model card (arXiv 2508.10925).

Line numbers below refer to the current HEAD file.

## What changed between rounds

A semantic diff (YAML parsed, `text_md` compared) between `18adc59d` and `e69bba84` shows:

- **Background was rewritten** into the gold's three-step pattern: a bold lead line, the diagram, a "Follow the benchmark in three steps" list, a transition, and a plain-terms card (L47–61).
- **All eight `In plain terms` cards were rewritten** in more casual language.
- Backticks were added around numbers and terms throughout.
- Roadmap, key concepts, figure captions, and the body of every other section are **unchanged in substance**.

As a result, almost every round-1 finding is still present. The new plain-terms cards also introduce new overclaims (see Truthfulness).

## Grades

| # | Dimension | R1 | R2 |
|---|---|---|---|
| 1 | Structure and article logic | 7 | 7 |
| 2 | Engagement and human-like narrative | 6 | 6 |
| 3 | Language quality | 5 | 5 |
| 4 | Technical depth | 7 | 7 |
| 5 | Truthfulness | 7 | 5 |
| 6 | Roadmap cards | 7 | 7 |
| 7 | Consistency with gold template | 6 | 6.5 |
| | **Overall** | **6.5** | **6** |

Truthfulness drops from round 1 for two reasons. Round 1 missed one factual error ("dense" gpt-oss), and the new plain-terms cards add overclaims ("answered 7× faster", "full 32-billion-parameter model", "equal accuracy").

## 1. Structure and article logic (7)

- The arc is sound: background, contract, shared task, guardrail, grid, latency limit, engine panel, then exact tables, protocol, and limits. The new background now leads with the three steps and the outcome, as the gold does.
- **L243–244:** "That attempt remains in the revision notes in Details" still points to a section that does not exist. No "Details" or "revision notes" section exists in the story or in the showcase-web pages.
- **L220:** "The grid sets the champion" is still there. The training section shows throughput only; the champion verdict comes from latency in the next section.
- **The co-tenant repeat is told four times:** L40 (key concepts), L242, L304–307, and L378–380. Conclusions still restates 2.9×, 7×, 0.81 s, and 1.00 from earlier sections.
- **L319–320 diagram fence:** it is still indented 12 spaces, so 6 spaces remain after YAML parsing. I re-verified the impact. The site's own renderer (`apps/showcase-web/src/lib/markdown.tsx`) detects fences with `FENCE_RE = /^\s*```/`, which accepts leading whitespace, so this diagram **does render** on the site. Round 1 overstated the severity. The fence is still inconsistent with the gold and would break in any CommonMark renderer.

## 2. Engagement and narrative (6)

- **Opening (L47):** the opening improved. It now has a bold lead and a gold-style three-step list. It still opens on a tally ("One laptop, five local AI setups, 760 requests, zero failures.") rather than on a stake or question. The strongest hook in the evidence is still buried in EDA at L146–149: qwen3.6 defaulted to thinking mode and "silently burned the entire 128-token budget" (docs page L97).
- **Diagram narration:** the article still describes its diagrams instead of the decision: "Use the measurement contract diagram as the study checklist" (L70), "Follow the request envelope in the diagram" (L107), "The diagram's last step" (L115), "Follow the serving-grid diagram from left to right" (L167), and "The evidence-lineage diagram below is the reading guide" (L279).
- **No concrete example:** the article still never shows a prompt (`data/prompts.json`), never says that an answer is about 45 tokens (1810 tokens / 40 requests), and never says what 0.81 s means to a user.
- The new plain-terms cards are warmer ("for a fair race", L159), but they trade precision for tone (see Truthfulness).

## 3. Language quality (5)

- **L101–118, definition stubs unchanged:** "Synthetic means made locally." / "Temperature controls randomness." / "Reasoning means intermediate thinking. It is off." / "Pydantic is a Python library for data checks." / "Deterministic means the same input gets the same result."
- **L108:** "It is 0, so retries use the same setting" is still a non sequitur. Temperature 0 gives (near-)greedy decoding and has nothing to do with retries.
- **L361–362:** "Async HTTPX streaming uses a Python web client to receive tokens as they arrive" is still a tautology.
- **L77, L177 ("1 through 8"), L48 ("`1` to `8`"), L96 ("from 1 to 8"):** these still suggest eight rungs. The rungs are 1/2/4/8, and the quant and engine arms run only at c=1.
- **L305, L379, "10–`30×`":** the backtick formatting is broken, because the code span wraps only half of the range.
- **Transitions:** all six still use the formula "X; next, the Y (…)" (L93, L128, L156, L220, L251, L271).
- **Repetition:** "0.81" appears 7 times and "7×" 6 times.
- **New, L102–103:** "Nothing is downloaded, so no license applies" is wrong as written. The prompts are local, but every model is downloaded under its own license. Scope the sentence to the prompts.
- **L369, cost formula:** "measured tok/s × declared 100 W draw × $0.30/kWh" is dimensionally wrong as written. The figure divides by tok/s: (1e6 / 67.73 / 3600) h × 0.1 kW × $0.30 = $0.123.

## 4. Technical depth (7)

The strengths are unchanged: nearest-rank percentiles, a real semaphore code excerpt, separate aggregate and per-request tok/s, an explicit packaging confound, a recorded missing MLX build, and a reproducible cost.

These round-1 gaps are all still open:
- With n=40 and nearest-rank, p99 is the maximum observation, and the article does not say so.
- Flat or declining aggregate tok/s with near-linear p95 growth points to serialized decoding. The article neither names this interpretation nor carries the docs caveat ("does not isolate memory bandwidth, batching, or another cause").
- `max_tokens 128` is never stated (L108 says only "A token budget").
- gpt-oss:20b (c=1 p95 1.64 s, 36.8 tok/s) appears in no number. The gemma4:31b MLX grid (c=1..8) is missing from the table.
- QAT-int4 is 53% faster than Q8_0 on the same runner (9.83 vs 6.43 tok/s). This is the only clean same-runner quantization comparison, and the docs page already draws it out. The article does not.

## 5. Truthfulness (5)

Re-verified as correct:
- 760 requests, 19 cells, 0 failures, and every rate at 1.00. The qwen3.6 p50/p95/p99, TTFT, and agg tok/s rows match `metrics.json` to 4 decimal places.
- The qwen3:32b rows, and the gemma4 mlx, q8_0, and qat c=1 rows.
- 7.08× tok/s (67.73/9.56), 2.92× (18.79/6.43), and $0.123 (re-derived).
- Ollama 0.40.4, macOS 26.5 arm64, 128 GB (docs L26, ADR-0006 L20), 2026-10-15 and 2026-10-30, 100 W and $0.30/kWh.
- The 3×3 default and the under-45-minute target (README L37), the switch-expert-weights failure (DESIGN L41–44), and the reasoning-burn smoke pass (docs L97).
- "Hurt only the llama.cpp path" (MLX repeat cells were 0.56–0.73× of the original p95, so they were faster).
- The quality table arms (qat, q8_0, mlx) match `quality_quant.json`.

Untraceable or contradicted claims:

| Line(s) | Claim | Finding |
|---|---|---|
| L40, L305, L379 | llama.cpp cells degraded "10–30×" | **Untraceable number (still present).** No committed file contains it. Re-derived from `bench_run_repeat.json` against `bench_run.json`: the p95 ratio ranges from 5.06× (gemma q8_0) through 7.2–12.5× (qwen3.6) to 21–35× (gpt-oss), and the tok/s drop from 5.2× to 29.3×. |
| L305–306, L379–380 | "memory-bandwidth contention … not a build regression" / "because other workloads competed for memory bandwidth" | **Contradicted (still present).** The repeat ran on Ollama **0.40.12**, while the original ran on 0.40.4, so a build change is not ruled out. The docs page says the run "does not isolate memory bandwidth". |
| L306–307 | repeat "is outside the committed evidence path" | **Misleading (still present).** `data/bench_run_repeat.json` is committed. It is outside the aggregated path only. |
| L169, L172–173; also L61, L223 (new) | qwen3:32b "at full precision" / "full 32-billion-parameter model" | **Untraceable number (still present, and now spread to two plain-terms cards).** No committed file gives its precision. The article's own table at L330 shows "—". Ollama's `qwen3:32b` family ships Q4_K_M as its standard 20 GB build, so "full precision" is very likely false. |
| L169, L329 | gemma4:31b (grid arm) is "4-bit MLX" | **Untraceable number (still present).** DESIGN L61 calls only the `-mlx` engine-panel tag 4-bit. No file states the quant of the plain `gemma4:31b` tag. |
| L61 (new) | the 4-bit model "answered 7× faster" than the 32B | **Contradicted number.** 7× is the tok/s ratio. The answer-time ratio is 5.06/0.81 = 6.2× on p95 and 3.42/0.63 = 5.4× on p50. |
| L168, L328 (missed in R1) | gpt-oss:20b is "a dense 20B" / "dense" | **Contradicted.** The gpt-oss model card (arXiv 2508.10925) describes a mixture-of-experts model with 20.9B total and 3.6B active parameters. No repo file calls it dense. This also undercuts the "MoE vs dense" framing, because the second-fastest arm is also an MoE. |
| L61, L394 (new) | "equal accuracy" / "equal test accuracy" | **Overclaim.** The README and figure caption call the check a saturated smoke check that "does not establish quality". It is a tie on schema and keywords, not accuracy. |
| L109, roadmap L26 | reasoning "is off" / "Reasoning disabled" | **Partly wrong.** `params.yaml` sets `reasoning_effort: low` for gpt-oss (README L19, DESIGN L77). |
| L243–244 | "revision notes in Details" | **Untraceable pointer (still present).** |
| L334 | table "keeps the exact per-cell values" | **Overclaim (still present).** 8 of 19 cells are absent: gpt-oss ×4 and gemma4:31b MLX ×4. |
| L102–103 (new catch) | "Nothing is downloaded, so no license applies" | **Inaccurate scope.** The models are downloaded artifacts with licenses. |

**Count: 4 untraceable or contradicted numbers** (10–30×, "full precision" for the 32B, "4-bit" for gemma4:31b, and "7× faster answered"), plus 8 non-numeric untraceable, contradicted, or overclaimed statements.

## 6. Roadmap cards (7)

Unchanged from round 1. All titles are verb-first, and every detail is 90 characters or fewer (the longest, L23, is 65). The order is 4 shipped, then 1 next.

The shipped claims are verified against the repo:
- **Task standardized:** `data/prompts.json` and `schemas.py`.
- **Full grid committed:** `data/bench_run.json`, 760 requests, `full: true`.
- **Config error caught:** docs L97 and `params.yaml` `reasoning_effort`.
- **Re-derived offline:** `report` is offline, and `_meta` lineage is in `metrics.json`.

Open issues, all still present:
- **L26:** the detail drops the hook and is partly wrong because gpt-oss uses `low`. Suggested: "Thinking mode burned the 128-token cap; reasoning set to none/low."
- **L32:** two unrelated blockers share one card. Split them, or add "Isolate the engine with a same-quant pair".
- **Missing card:** no card covers the saturated quality check. Add, for example, a `later` card: "Replace the smoke check with a graded task".
- **L20:** the detail could name the controls ("8 prompts, temp 0, 128-token cap, one Answer schema").

## 7. Consistency with gold template (6.5)

- **Improved:** the background now matches the gold pattern of a bold lead, diagram, three-step list, linked transition, and plain-terms card.
- **Still divergent:**
  - **Bold leads:** the data, EDA, evaluation, results, and conclusions sections start cold, with no bold lead line. Training has a bold line only mid-section, at L190.
  - **Transitions:** these are noun-phrase fragments, not the gold's full "we" sentences.
  - **No target table:** objectives has no target-versus-result table, so the "verdict" has nothing to clear.
  - **Fence indentation:** the indented fence at L319 does not match the gold.
  - **Plain-terms cards:** they still mostly repeat the headline rather than add information.
- **Minor:** the top-level key order (`figure_captions`, `roadmap`, `key_concepts`, `sections`) and the `metrics_keys: []` field differ from the gold. This is cosmetic.

## Round-1 finding status

| # | Round-1 finding | Status | Evidence at HEAD |
|---|---|---|---|
| 1 | Diagram fence over-indented | STILL PRESENT (low impact) | L319–320. The site renderer tolerates it, but it does not match the gold. |
| 2 | "revision notes in Details" pointer | STILL PRESENT | L243–244 |
| 3 | Conclusions repeats earlier numbers; co-tenant repeat 4× | STILL PRESENT | L40, L242, L304, L378 |
| 4 | "The grid sets the champion" overclaims | STILL PRESENT | L220 |
| 5 | Opening lacks a hook; reasoning burn buried | PARTLY FIXED | L47–57 now gold-shaped; the hook is still in EDA at L146 |
| 6 | Sections narrate diagrams, not decisions | STILL PRESENT | L70, L107, L115, L167, L279 |
| 7 | No concrete prompt or answer length | STILL PRESENT | none in file |
| 8 | Choppy definition stubs in data | STILL PRESENT | L101–118 |
| 9 | "per token, a text fragment" appositive | FIXED | removed with the background rewrite |
| 10 | "Records favor a 4-bit MoE" awkward subject | FIXED | removed |
| 11 | "so retries use the same setting" non sequitur | STILL PRESENT | L108 |
| 12 | HTTPX tautology | STILL PRESENT | L361–362 |
| 13 | "1 through 8" implies eight rungs | STILL PRESENT | L48, L77, L96, L177 |
| 14 | Repeated 0.81 and 7×; formulaic transitions | STILL PRESENT | 7× and 6×; L93, L128, L156, L220, L251, L271 |
| 15 | p99 equals max at n=40 not stated | STILL PRESENT | L365–366 |
| 16 | Serialization interpretation and cause caveat missing | STILL PRESENT | L184–188, L234–238 |
| 17 | `max_tokens 128` unstated | STILL PRESENT | L108 |
| 18 | gpt-oss numbers absent | STILL PRESENT | — |
| 19 | "exact per-cell values" overclaim | STILL PRESENT | L334 |
| 20 | QAT vs Q8_0 53% not drawn out | STILL PRESENT | only in the table, L349–350 |
| 21 | qwen3:32b "full precision" | STILL PRESENT (spread) | L169, L172; now also L61, L223 |
| 22 | gemma4:31b "4-bit MLX" | STILL PRESENT | L169, L329 |
| 23 | "10–30×" untraceable | STILL PRESENT | L40, L305, L379 |
| 24 | Memory-bandwidth causal claim | STILL PRESENT | L305–306, L379–380 |
| 25 | "outside the committed evidence path" | STILL PRESENT | L306–307 |
| 26 | Roadmap L26 detail drops the hook | STILL PRESENT | L26 |
| 27 | Roadmap L32 joins two blockers | STILL PRESENT | L32 |
| 28 | No quality-gap roadmap card | STILL PRESENT | — |
| 29 | Roadmap L20 lacks controls | STILL PRESENT | L20 |
| 30 | Transitions not in gold voice | STILL PRESENT | as #14 |
| 31 | Missing bold lead lines | STILL PRESENT | data, EDA, evaluation, results, conclusions |
| 32 | No target-vs-result table | STILL PRESENT | objectives L65–96 |

Totals: **2 fixed, 1 partly fixed, 29 still present.**

## Top 5 remaining fixes (by severity)

1. **Remove the unsupported causal claim and the invented range (L305–307, L379–380, L40, L242).**
   - Replace "This was memory-bandwidth contention … not a build regression. That repeat is outside the committed evidence path" with wording that states the facts. The repeat ran on Ollama 0.40.12 under co-tenant load, so the cause is not isolated. The raw record is committed at `data/bench_run_repeat.json` but is not aggregated.
   - Replace "10–30×" with the derived range ("about 5–35× slower on p95"), or commit a derived ratio file under `reports/` and quote it.
2. **Fix the model facts (L168–173, L328–330, L61, L223).**
   - gpt-oss:20b is an MoE (20.9B total, 3.6B active), not dense.
   - Drop "full precision" and "full 32-billion-parameter model" for qwen3:32b, or verify its quant from the Ollama manifest and commit it.
   - Do not call gemma4:31b "4-bit" until a committed file says so.
   - Reframe "MoE vs dense" as qwen3.6 MoE versus dense qwen3:32b, and note that gpt-oss is also an MoE.
3. **Repair the new plain-terms overclaims (L61, L223, L394, L159).**
   - "Answered 7× faster" should say "generated about 7× the tokens per second" or "answered about 6× faster at p95".
   - "Equal accuracy" should say "tied on a saturated schema-and-keyword check".
   - State reasoning precisely: none for qwen3.6, low for gpt-oss (L109, roadmap L26).
4. **Make the reference tables and pointers honest (L243–244, L334, L184–188).**
   - Delete or retarget the "Details" pointer.
   - Either add the gpt-oss and gemma4:31b MLX rows, or say "selected cells; all 19 in `reports/metrics.json`".
   - State `max_tokens 128`, say that p99 is the maximum at n=40, and carry the docs caveat that the run does not isolate the cause of flat throughput.
   - Draw out the QAT-int4 vs Q8_0 53% speed result.
5. **Rewrite the data section and transitions in connected prose (L101–118, L108, L361, L77, L177, L93…L271).**
   - Merge the definition stubs.
   - Delete the "retries" sentence and the HTTPX tautology.
   - Say "rungs 1/2/4/8".
   - Fix the broken "10–`30×`" code spans.
   - Correct the cost-formula wording at L369 (divide by tok/s).
   - Give data, EDA, evaluation, results, and conclusions bold lead lines, and convert the "X; next, the Y" fragments into gold-style "we" sentences.

## Ready to publish?

**No.** The round-2 commit reshaped the background and rewrote the plain-terms cards, but it did not touch any round-1 truthfulness finding. The new cards add more overclaims. Three factual problems remain on the page:
- an invented "10–30×" range;
- a causal claim contradicted by the committed Ollama version change;
- wrong architecture and precision labels: gpt-oss "dense", qwen3:32b "full precision", and gemma4:31b "4-bit".

These must be corrected before publication. Fixes 1–3 are small text edits that need no new run.
