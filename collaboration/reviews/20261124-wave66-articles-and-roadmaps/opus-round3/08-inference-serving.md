# Round-3 review: 08-inference-serving `story.yaml`

Reviewer: Claude Opus (read-only). Target: `projects/08-inference-serving/story.yaml` in the **working tree** (uncommitted Wave 8 edits on `wave8-articles-truthfulness-2026-11-25`, HEAD `c05accd0`).
Round-2 review: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus-round2/08-inference-serving.md`.
Gold template: `projects/01-rag-agent/story.yaml`.

Evidence re-checked from scratch: `reports/metrics.json` (19 cells, `_meta`), `data/bench_run.json` (Ollama 0.40.4, 2026-10-15, `full: true`), `params.yaml`, `README.md`, `DESIGN.md`, `reports/figures/*.json`, and `docs/projects/08-inference-serving.md`. All numbers were recomputed with a script from `bench_run.json`.

**Evidence status (`git ls-files`).** Under `data/`, only `data/bench_run.json` is tracked. `data/bench_run_repeat.json` is **gitignored**: `.gitignore:15 data/` matches it, and no exception like the one at `.gitignore:21` exists for it. It also has **no history in any branch** (`git log --all` is empty). `data/prompts.json` is likewise untracked; it is a DVC `prepare` output. Round 2 called the repeat file "committed". That was wrong, and Wave 8 has now written the same error into the article.

Line numbers refer to the working-tree file.

## What Wave 8 changed

The diff is substantial and targets the round-2 truthfulness list directly:

- **Co-tenant repeat:** "10–30×" became "about 5–35× on p95". The memory-bandwidth causal claim became "cause not isolated" and now names the Ollama 0.40.12 vs 0.40.4 change. The "revision notes in Details" pointer became "raw record committed at `data/bench_run_repeat.json`".
- **Model facts:** gpt-oss is now an MoE. qwen3:32b and gemma4:31b quantization is "unrecorded". The table quant cell reads "not recorded".
- **Plain-terms cards:** "answered 7× faster" became "7× tok/s, about 6× faster at p95". "Equal accuracy" became "tie on a saturated check".
- **Reasoning and request settings:** reasoning is stated as none for qwen3.6 and low for gpt-oss. `max_tokens 128` and temperature 0 are now stated, and the "retries" non sequitur was removed.
- **Licensing:** the scope is now correct (prompts are local; models keep their own licenses).
- **Rungs:** these now read `1/2/4/8` everywhere. The quant and engine arms are marked c=1 only.
- **Additions:** QAT-int4 vs Q8_0 (+53%) is drawn out, p99 is stated as the maximum at n=40, and the cost formula is now dimensionally correct.
- **Roadmap:** L26 and L31–32 were rewritten.

## Grades

| # | Dimension | R2 | R3 |
|---|---|---|---|
| 1 | Structure and article logic | 7 | 7 |
| 2 | Engagement and human-like narrative | 6 | 6 |
| 3 | Language quality | 5 | 6.5 |
| 4 | Technical depth | 7 | 7.5 |
| 5 | Truthfulness | 5 | 5.5 |
| 6 | Roadmap cards | 7 | 8 |
| 7 | Consistency with gold template | 6.5 | 6.5 |
| | **Overall** | **6** | **6.5** |

Truthfulness rises only half a point. Wave 8 fixed every round-2 model-fact and overclaim error. But the co-tenant paragraph, now told four times, rests entirely on a file that is not committed. Two sentences now assert that it *is* committed (L242, L306–307). That is a new, verifiable falsehood.

## 1. Structure and article logic (7)

- The arc is unchanged and sound: stake, measurement contract, shared task, guardrail, grid, latency limit, engine panel, then tables, protocol, and limits.
- **L219:** "The grid sets the champion" is still there. The training section shows throughput; the champion verdict comes from p95 latency in Evaluation.
- **The co-tenant repeat is told four times, now at greater length:** L40–41, L241–243, L303–307, and L377–380. Each telling restates the same three facts (llama.cpp slower, MLX fine, build changed).
- **The conclusions re-quote earlier sections:** 2.9× (L297), 7× and 0.81 s (L299–300), and 1.00 (L301).
- **L319–320:** the diagram fence is still indented 10 spaces. The site renderer tolerates it (`FENCE_RE = /^\s*```/`), but it does not match the gold and would break in CommonMark.
- **L48 and L166–169:** "five setups" counts the Q8_0/QAT pair as one and silently omits `gemma4:31b-mlx`, which is a seventh tag and an engine-panel arm. Readers who count the table (L327–331) or the cells will not get five.

## 2. Engagement and narrative (6)

- **Opening (L47):** it still opens on a tally. The best hook is now half-surfaced: roadmap L26 says "Thinking hit the 128-token cap". The body still buries it in EDA at L145–148, and it is not used as the stake.
- **Diagram narration:** the article still narrates diagrams instead of decisions at L70, L101, L114, L166, and L278. L107 was improved.
- **No concrete example:** there is still no example prompt, no answer length (about 45 tokens: 1810 / 40), and no sense of what 0.81 s or 7.8 s means to a user.
- **Plain-terms cards:** they are now accurate, but most restate the section headline rather than add a takeaway.

## 3. Language quality (6.5)

**Improved:**
- the "retries" non sequitur is gone (L107–109);
- the rungs read 1/2/4/8;
- the broken `10–`30×`` code spans are gone;
- the cost formula reads correctly (L369–370).

**Still present:**
- **Definition stubs:** "Synthetic means made locally." (L101), "Pydantic is a Python library for data checks." (L115), and "Deterministic means the same input gets the same result." (L117).
- **L361–362, HTTPX tautology:** "Async HTTPX streaming uses a Python web client to receive tokens as they arrive".
- **Formulaic transitions:** six use "X; next, the Y (…)" (L93, L127, L155, L219, L250, L270).
- **Repetition:** "0.81" appears 7 times, "7×" 6 times, and "2.9×" 4 times.

**New awkwardness:**
- **L378–379:** "under co-tenant load" appears twice in one sentence.
- **L147–148:** "Setting reasoning to `none` for qwen3.6, with the recorded `low` override for gpt-oss, and repeating…" is a long subject stack.
- **L102–103 and L167–172:** several lines are much longer than the surrounding wrap. This is cosmetic in YAML but signals patching.

## 4. Technical depth (7.5)

**Gains:**
- p99 is stated as the maximum at n=40 (L366);
- `max_tokens 128` and temperature 0 are stated (L107);
- per-model reasoning effort is stated (L108–109);
- QAT-int4 vs Q8_0 on one runner is drawn out (+53%, L169–170), the only clean same-runner quantization comparison;
- the cost derivation is correct.

**Still missing:**
- **Serialized decoding:** flat aggregate tok/s with near-linear p95 growth points to serialized decoding. The article neither names this nor carries the docs caveat (`docs/projects/08-inference-serving.md` L89: "does not isolate memory bandwidth, batching, or…").
- **gpt-oss:20b numbers:** none are quoted, though it is the second-fastest arm (c=1 p95 1.64 s, 36.78 tok/s). The gemma4:31b MLX grid c=1..8 is also absent from the table.
- **New precision issue, L184–185:** "aggregate tok/s is flat-to-declining" is true for qwen3.6 (67.7 → 50.2) and qwen3:32b (9.56 → 9.37). It is **false for two of the four lines in the same figure:** gpt-oss rises 36.78 → 39.96 and gemma4:31b MLX rises 17.58 → 18.54 (`toks_per_s.json`). The aggregate is flat-to-rising for those two runners, which would be the more interesting observation.

## 5. Truthfulness (5.5)

**Re-verified as correct**, recomputed from `data/bench_run.json` and matching `reports/metrics.json` and the figure JSONs:
- **Grid totals:** 760 requests, 19 cells, 0 failures, and both rates at 1.00 in every cell.
- **qwen3.6 rows:** the p50/p95/p99, TTFT, and aggregate tok/s rows (L340–342) match to 4 dp.
- **Other table rows:** the qwen3:32b rows (L343–344) and the gemma4:31b-mlx, q8_0, and qat c=1 rows (L345–350) all match.
- **Ratios:** 7.08× tok/s (67.73/9.56). "About 6× faster at p95" is 6.23× (5.0589/0.8114). 2.92× is 18.79/6.43. +53% is 9.83/6.43 = 1.529. $0.123 is 1e6/67.73/3600 × 0.1 kW × $0.30.
- **Platform:** Ollama 0.40.4, the 2026-10-15 date, `full: true`, and 128 GB, all from `bench_run.json` and the docs page.
- **Settings:** `max_tokens: 128`, `temperature: 0.0`, `reasoning_effort: none` with gpt-oss `low`, 100 W, and $0.30/kWh, all from `params.yaml`.
- **Docs and design:** the 3×3 default and the under-45-minute target (README L37), and the thinking-mode budget burn (docs L96–98).
- **Figures:** the engine panel shows 2.47/7.12 s and 18.8/6.4 tok/s (`engine_panel.json`). The quality table arms are qat, q8_0, and mlx (`quality_quant.json`). The latency whiskers are p50–p99 (`latency_concurrency.json`).
- **Range:** the 5–35× range is arithmetically right against the *local* repeat file (p95 ratio 5.06× for q8_0 up to 34.8× for gpt-oss c=1; MLX 0.56–0.73×). That file is not committed evidence, though (see below).

**Untraceable or contradicted claims:**

| Line(s) | Claim | Finding |
|---|---|---|
| L242, L306–307 | "Its raw record is committed at `data/bench_run_repeat.json`" / "The raw record is committed but not aggregated." | **Contradicted (NEW in Wave 8).** The file is gitignored (`.gitignore:15 data/`), has no `!` exception, and appears in no commit on any branch. Only `data/bench_run.json` is tracked. |
| L40, L304, L379 | llama.cpp "about 5–35× slower on p95" | **Untraceable number.** The value matches the uncommitted local file but no committed file. |
| L305, L380 | Repeat ran on Ollama "0.40.12" | **Untraceable number.** Its only source is the uncommitted file. No committed doc mentions 0.40.12 for this project. |
| L378 | "A 2026-10-30 repeat" | **Untraceable number.** Same source. |
| L241, L304 | "hurt only the llama.cpp path" / "while MLX held" | **Untraceable.** Same source. |
| L184–185 | "aggregate tok/s is flat-to-declining" | **Contradicted for 2 of 4 lines.** gpt-oss and gemma4 MLX rise (`toks_per_s.json`). This is pre-existing and missed in R2. |
| L352–354 | No MLX build exists "because conversion fails on switch-expert weights" | **Mild overreach.** DESIGN L41–44 says the registry has no MLX tag, "consistent with" an earlier failed conversion. The cause is inferred, not established. |
| L167–168, L328 | gpt-oss:20b is an "MoE" | **Correct but external.** It is supported by the gpt-oss model card, not by any repo file (`params.yaml` comments call it "MXFP4"). Acceptable; a one-line source would help. |
| L330 vs L329 | qwen3:32b quant shown as "—", gemma4:31b as "not recorded" | **Inconsistent notation.** L172 says both are unrecorded. Use the same label. |

**Count: 3 untraceable numbers** (5–35×, 0.40.12, 2026-10-30), all from one uncommitted file. There are also **2 contradicted statements** ("committed" ×2 as one new error, and "flat-to-declining") and 2 minor overreaches.

**Fix:** pick one of the following.
- **(a) Owner decision: commit the file.** Add `!projects/08-inference-serving/data/bench_run_repeat.json` to `.gitignore`, and ideally a small derived `reports/repeat_ratios.json`. Every claim then becomes traceable as written.
- **(b) Rewrite as an uncommitted note.** Cut the repeat down to one sentence in Limits that says the run is a local, uncommitted observation, with no numbers. Remove it from key concepts (L40–41), Evaluation (L241–243), and the evidence bullets (L303–307).

## 6. Roadmap cards (8)

- **Shape:** all titles are verb-first and every detail is at most 90 characters (49, 65, 63, 61, 70). The order is 4 shipped, then 1 next, matching the gold's 4+1.
- **Shipped claims verified:**
  - task standardized: prompts come from the code (`cli.py prepare`) and `schemas.py`;
  - grid committed: `data/bench_run.json` is tracked, with 760 requests and `full: true`;
  - config error caught: docs L96–98 and `params.yaml`;
  - re-derived offline: `report` is offline, and `_meta` lineage is in `metrics.json`.
- **L26 (FIXED):** the card now carries the hook and the correct none/low split.
- **L31–32 (improved):** "Validate the choice on shipping hardware" with "Gate: quiet target hardware, matched-quant runners, and a graded task." It now covers the graded-task gap. It still bundles three independent gates in one card. That is acceptable as a gate list, but the gold uses one outcome per card.
- **L20:** the detail still does not name the controls (temperature 0, 128-token cap, one Answer schema). The figure "8 schema-checked prompts" is correct.
- **Wording:** none of the shipped cards claims that the repeat is committed, which is good.

## 7. Consistency with gold template (6.5)

- **Bold leads:** the gold opens *every* section with a bold lead (01-rag-agent L6, L24, L50, L74, L95, L143, L169). The target has them only in background (L47), objectives (L66), and mid-training (L189). Data, EDA, evaluation, results, and conclusions start cold.
- **Transitions:** the gold uses full "we" sentences ("next, we trace how…"). The target uses noun-phrase fragments (L93–L270).
- **No target table:** objectives has no target-versus-result table (gold L36), so "wins" has no declared bar.
- **Fence:** the fence indentation at L319 differs from the gold.
- **Cosmetic:** the top-level key order and `metrics_keys: []` differ from the gold.

## Round-2 finding status

Rows 1–32 follow the round-2 table numbering; #9 and #10 were already fixed in R2. Rows A–G are the additional round-2 truthfulness and language items.

| # | Round-2 finding | Status | Evidence in working tree |
|---|---|---|---|
| 1 | Diagram fence over-indented | STILL PRESENT | L319–320 |
| 2 | "revision notes in Details" pointer | FIXED (replacement is false; see new error N1) | L241–243 |
| 3 | Conclusions repeat numbers; co-tenant told 4× | STILL PRESENT | L40, L241, L303, L377 |
| 4 | "The grid sets the champion" | STILL PRESENT | L219 |
| 5 | Opening lacks hook; reasoning burn buried | PARTLY FIXED | hook now in roadmap L26; body still at L145 |
| 6 | Sections narrate diagrams | STILL PRESENT | L70, L101, L114, L166, L278 |
| 7 | No concrete prompt or answer length | STILL PRESENT | — |
| 8 | Definition stubs in data | PARTLY FIXED | temperature and reasoning stubs gone; L101, L115, L117 remain |
| 11 | "retries" non sequitur | FIXED | L107–109 |
| 12 | HTTPX tautology | STILL PRESENT | L361–362 |
| 13 | "1 through 8" | FIXED | L48, L77, L96, L176 |
| 14 | Repeated 0.81/7×; formulaic transitions | STILL PRESENT | 7× / 6×; six "; next," transitions |
| 15 | p99 = max at n=40 unstated | FIXED | L366 |
| 16 | Serialization interpretation and cause caveat | STILL PRESENT | L183–187, L233–237 |
| 17 | `max_tokens 128` unstated | FIXED | L107 |
| 18 | gpt-oss numbers absent | STILL PRESENT | — |
| 19 | "exact per-cell values" | FIXED | L334–335 |
| 20 | QAT vs Q8_0 53% not drawn out | FIXED | L169–170 |
| 21 | qwen3:32b "full precision" | FIXED | L168, L172, L61, L222 |
| 22 | gemma4:31b "4-bit MLX" | FIXED | L167, L329 |
| 23 | "10–30×" untraceable | PARTLY FIXED | now 5–35×, correct vs the local file but still untraceable (uncommitted) |
| 24 | Memory-bandwidth causal claim | FIXED | L305–307, L380 |
| 25 | "outside the committed evidence path" | PARTLY FIXED (regressed) | now claims the opposite, which is also false (N1) |
| 26 | Roadmap L26 drops hook / wrong reasoning | FIXED | L26 |
| 27 | Roadmap next-card joins blockers | PARTLY FIXED | L31–32 reframed as a gate list |
| 28 | No quality-gap roadmap card | PARTLY FIXED | "graded task" folded into L32 |
| 29 | Roadmap L20 lacks controls | STILL PRESENT | L20 |
| 30 | Transitions not in gold voice | STILL PRESENT | L93–L270 |
| 31 | Missing bold lead lines | STILL PRESENT | data, EDA, evaluation, results, conclusions |
| 32 | No target-vs-result table | STILL PRESENT | objectives |
| A | gpt-oss "dense" | FIXED | L167, L328 |
| B | "answered 7× faster" | FIXED | L61, L222 |
| C | "equal accuracy" | FIXED | L61, L394 |
| D | "reasoning is off" | FIXED | L108–109, L147–148 |
| E | "Nothing is downloaded, so no license applies" | FIXED | L102–103 |
| F | Cost formula dimensionally wrong | FIXED | L369–370 |
| G | Broken `10–`30×`` code spans | FIXED | — |

**Totals (37 items):** 18 fixed, 6 partly fixed, **13 still present**.

## New errors introduced by Wave 8

- **N1 (high), L242 and L306–307:** "raw record is committed at `data/bench_run_repeat.json`" and "The raw record is committed but not aggregated." Both are false: the file is gitignored and appears in no commit. The round-2 reviewer made the same mistake, and Wave 8 copied it.
- **N2 (medium), L40, L304–305, L378–380:** the new specific numbers (5–35×, 0.40.12, 2026-10-30) make the co-tenant passage *more* detailed while its only source is uncommitted. The volume of untraceable detail grew, though each number is now arithmetically honest.
- **N3 (low), L378–379:** "under co-tenant load" is repeated within one sentence.
- **N4 (low), L48 vs L166–169:** "(plus single-request packaging arms)" is a clear improvement, but "five setups" still does not reconcile with seven model tags.

Pre-existing errors missed by R2 and found now: "flat-to-declining" (L184–185), and the "because conversion fails" causal wording (L352–354).

## Top 5 remaining fixes

1. **Resolve the co-tenant evidence (L40–41, L241–243, L303–307, L377–380).** Either the owner commits `data/bench_run_repeat.json`, via a `.gitignore` exception and ideally a derived ratio file under `reports/`, or the article drops "committed", drops the 5–35×, 0.40.12, and 2026-10-30 specifics, and keeps a single uncommitted-observation sentence in Limits. In both cases, tell the story once rather than four times.
2. **Correct "flat-to-declining" (L184–185).** Write: "aggregate tok/s is flat or slightly rising for gpt-oss and gemma4 MLX, and falls about 26% for qwen3.6". Add the serialized-decoding interpretation and the docs caveat ("does not isolate memory bandwidth, batching, or another cause").
3. **Fix the champion and causal overreaches (L219, L352–354, L330).** Change "The grid sets the champion" to a throughput-only claim. Change "because conversion fails" to "the registry has no MLX tag; an earlier conversion attempt failed on switch-expert weights". Use the same "not recorded" label for qwen3:32b as for gemma4:31b.
4. **Bring sections up to gold voice (L93–L270, data/EDA/evaluation/results/conclusions openers, L101/L115/L117, L361).** Add a bold lead to each section and convert the six "; next, the …" fragments into "we" sentences. Fold the three definition stubs into the sentences that use them, and delete the HTTPX tautology.
5. **Add one concrete example and the missing arm (L114–118, L338–350, L20).** Show one prompt and its about-45-token Answer. Add the gpt-oss row (c=1 p95 1.64 s, 36.78 tok/s) as the second MoE. Name the controls in roadmap L20 ("8 prompts, temp 0, 128-token cap, one Answer schema").

## Ready to publish?

**No.** Wave 8 fixed every model-fact and overclaim error from round 2, and the headline numbers are all correct. However, the article now twice asserts that `data/bench_run_repeat.json` is committed (L242, L306–307). It is gitignored and absent from history. Three specific numbers (5–35×, 0.40.12, 2026-10-30) rest only on that uncommitted file.

This is a small fix, either an owner `.gitignore` decision or about four sentence deletions. Once it lands, together with the "flat-to-declining" correction, the article clears the truthfulness bar. The remaining items are style and gold-voice polish.
