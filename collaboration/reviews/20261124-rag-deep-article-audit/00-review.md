# In-Depth Article Audit: `01-rag-agent` (Components, Narrative, Logic, Diagrams, Truthfulness)

Date: 2026-11-24
Authors: Neon Reviewer + Code/Component Audit
Repo state: `main` @ `8833358c`
Scope: `projects/01-rag-agent/story.yaml`, `apps/showcase-web/src/components/{CaseStudy,StorySection,KeyConceptsCard,GlossaryCard,BusinessImplication,FigureCard,RoadmapBlock}.tsx`, `apps/showcase-web/src/diagrams/{ragPipeline.ts,auto/01-rag-agent-*.ts}`, `projects/01-rag-agent/src/rag_agent/{index,agent,verify,config}.py`, and `projects/01-rag-agent/reports/`.

---

## 0. Baseline Telemetry (`scripts/lint_story_language.py`)

| Section | Words | Flesch | Budget / Floor | Figures | Diagram |
|---|---:|---:|---|---|---|
| `background` | 133 | 58.9 | cap 150 / floor 45 | `[]` | `01-rag-pipeline` |
| `objectives` | 297 | 45.4 | soft 550 / floor 45 | `[]` | `auto-01-rag-agent-1` |
| `data` | 288 | 47.9 | soft 550 / floor 45 | `[]` | `auto-01-rag-agent-2` |
| `eda` | 249 | 50.8 | soft 550 / floor 45 | `eda_corpus_composition` | — |
| `training` | 435 | 55.3 | soft 550 / floor 45 | `retrieval_ladder`, `chunk_size_sweep`, `model_comparison` | — |
| `evaluation` | 423 | 46.2 | soft 550 / floor 45 | `latency_histogram`, `kimi_generation_comparison`, `fusion_arm_comparison` | `auto-01-rag-agent-3` |
| `results` | 406 | 49.7 | soft 550 / floor 45 | `final_outcome`, `failure_taxonomy`, `verify_funnel` | `auto-01-rag-agent-4` |
| `conclusions` | 487 | 34.7 | collapsed `<details>` exempt | `retrieval_funnel` | — |
| **Main-thread total** | **2,231** | — | **soft 2,600 (369w headroom)** | 11 total | 5 total |

---

## 1. Components & Layout (`apps/showcase-web`)

- **Vertical figure stack (`StorySection.tsx:114-118`, `story.css:18`)**: `.story-cols` renders `.story-main` (prose -> `BusinessImplication` "In plain terms" -> `StoryMetricsTable`) first, followed by `.story-figs` (up to 3 `FigureCard`s stacked vertically). In `training`, `evaluation`, and `results`, all 3 charts appear *after* the entire section text, so each chart's prose reference should clearly anchor what the reader is about to inspect below.
- **`Background` card cluster (`CaseStudy.tsx:77-82`)**: Renders three consecutive accent-left cards (`BusinessImplication` -> `KeyConceptsCard` -> `GlossaryCard`) immediately before `02 Objectives`, which slightly front-loads reference material before the problem statement.
- **Misplaced `conclusions` figure (`StorySection.tsx:134-143`, `story.yaml:232`)**: `conclusions` attaches `figures: [retrieval_funnel]` (an old 65-question tuning funnel). Because `.story-figs` renders *outside* `<details>`, that tuning chart appears visibly next to `Results summary` (`120`-question `final_v3`) even though `conclusions` prose never mentions it.
- **`RoadmapBlock.tsx:19-45`**: Upgraded in `8833358c` to render `/01` step index, bold `title`, and visible `detail` for all 4 `shipped` nodes (while `next` stays authored in YAML only per house convention).

---

## 2. Engagement, Language & Human-Like Narrative

- **Strong sections**: `background` (hooks with *"When every answer carries a citation, what can still go wrong?"*), `training` (uses the concrete Wright Flyer chunk example), and `results:163` (*"Failures moved, they did not disappear"*).
- **Where prose still reads like telemetry**:
  - `objectives:28-33` reads like a spec sheet rather than explaining *why* an LLM cites a valid passage while inverting a date or bridging two unrelated sentences.
  - `evaluation:140-143` compresses the *judge discovery story* (earlier judge rubber-stamping 44% of bad claims) into parenthetical stats.
  - `results:161-164` packs 30+ numbers into 4 bullets; grouping metrics into **Headline accuracy**, **Verify-loop funnel**, **Failure shift**, and **Latency & cost** (moving granular decimals to the table) will read much more naturally.
- **Jargon & readability catches**:
  - `objectives` (Flesch **45.4**) and `evaluation` (Flesch **46.2**) sit right on the `45.0` warning floor. Splitting long parenthetical sentences will keep them comfortably `>= 48`.
  - Unexplained shorthand in prose: `"rows"` (`story.yaml:57` -> `"questions"`), `"membership-quota cost"` (`:32` -> `"flat-rate subscription"`), `all-articles@5` (`:92`, never defined in plain terms), `"sealed raw layer"` (`:94`), and `"mechanical checks"` (`:142, 162` — deterministic substring/number/date/negation checks in `verify.py` are never explained before their failure counts appear).

---

## 3. Article Logic & Cohesion

1. **Missing bridge on "mechanical checks"**: `evaluation:142` reports *"zero mechanical false rejections"* and `results:162` reports *"16 failed mechanical checks"*, without defining what those deterministic checks verify (`verify.py:217-280`: verbatim span substring, numbers, dates/months, temporal qualifiers, negation polarity).
2. **Chronology whiplash**: `training` promotes `S3` on `final_v3` (`0.9457`), then `evaluation` drops back to 65-question tuning floors (`0.677`) and displays 3 tuning-era charts, before jumping to `judge_v2` and `final_v3`.
3. **Cross-section repetition**: `0.9457` vs `0.9239` appears in 4 places; `104/120` / `F1 0.9091` / `1/120` appears in 5 places; `final_v3` consumption and pending owner hand-label appear in 3–4 places each. Tightening each section to *own* its piece of the story (Objectives = target; Training = S3 mechanism + ladder; Evaluation = judges + rails + disclosures; Results = final outcomes) removes echoes and frees room for deeper narrative.

---

## 4. Text vs. Image / Diagram Alignment (Critical Drift Found)

### Diagrams (`apps/showcase-web/src/diagrams/`)
| Diagram ID | File | Drift Found | Fix Needed |
|---|---|---|---|
| `01-rag-pipeline` | `ragPipeline.ts:4-103` | Claims pre-S3 tuning numbers (`0.831`, `5×k`, `23 s`, `39 repairs`, RAGAS `0.685`, refusal `0.900`); omits BM25 + RRF fusion (`S2`) and per-article cap (`S3`) | Update node facts/edges to S3 hybrid RRF (`6×k`), `0.946` recall@5, and `final_v3` latency/faithfulness |
| `auto-01-rag-agent-1` | `01-rag-agent-1.ts:6-72` | Minor: implies pre-gen corpus gate whereas code sets lexical gate `0.0` and agent decides post-search | Clarify in `objectives` prose or diagram label |
| `auto-01-rag-agent-2` | `01-rag-agent-2.ts:31` | Node `ev` says `"65 tuning, 55 sealed"`, omitting `120 final_v3` | Add `120 final` to `ev` node |
| `auto-01-rag-agent-3` | `01-rag-agent-3.ts:13,25` | Says `"Tuning pass, 65 questions"` and `"Sealed set, scored once"` | Update to reflect `judge_v2` 30/30 audit + `final_v3` |
| `auto-01-rag-agent-4` | `01-rag-agent-4.ts:8,55` | Title says `"Conclusions & lessons"` (embedded in `results`), node `s15` says `"Sealed 55-question set"` | Update title to `"Results"` and node to `120 final_v3` |

### Figures per Section (`story.yaml`)
- **`eda` (`[eda_corpus_composition]`)** & **`training` (`[retrieval_ladder, chunk_size_sweep, model_comparison]`)**: Aligned with prose.
- **`results` (`[final_outcome, failure_taxonomy, verify_funnel]`)**: Aligned with prose.
- **`evaluation` (`[latency_histogram, kimi_generation_comparison, fusion_arm_comparison]`)**: **Stranded.** `evaluation` prose never mentions `latency_histogram` (whose subtitle says `p50 26 s, p95 103 s`, clashing with `objectives` table's `16.5 s / 40.5 s`), `kimi_generation_comparison`, or `fusion_arm_comparison` (65-question tuning / 15-question raw layer). Prose should either explicitly introduce those 3 charts as tuning-era diagnostics or move `fusion_arm_comparison` to `training`/`conclusions`.
- **`conclusions` (`[retrieval_funnel]`)**: **Stranded.** Old 65-question tuning funnel renders right below `final_v3` (`120`-question) conclusions. Detach or replace with a `final_v3` summary visual.

---

## 5. Truthfulness vs. Code & Committed Results

Verified directly against `src/rag_agent/{index.py,agent.py,verify.py,config.py}` and `reports/{final_v3_e2e/f1_summary.json,final_v3_e2e/metrics.json,metrics.json}`:
- **Metrics (`final_v3_e2e`)**: All headline figures (`F1 0.9091`, `P 0.9524`, `R 0.8696`, `acc 0.8667 [0.7944, 0.9162]`, `faithfulness 0.8717 [0.8092, 0.9304]`, `104/10/4/1/1`, `verify 166/16/150/148/15/11/7/159`, `$0.781 + $0.233 = $1.014` / `$0.0084/q`, `$1.458` / `$0.0121/q`, `74%` cached input, `p50 16.5 s` / `p95 40.5 s`) match committed JSON **100%**.
- **Code parity**: `KEYWORD_SUPPORT_THRESHOLD = 0.6` (`verify.py:56`), `max_repair_calls = 2` (`config.py:134`), `agent_usage_limits` `12/16/200_000` (`config.py:201-203`, `agent.py:32-55`), and the `index.py:254-289` `search()` snippet match code accurately.
- **Minor caveats to clarify**:
  1. Note that the `kimi-k2.8-preview` meter rate card (`$1.00/$4.00`, 30% cached) differs from `config.py:190-191` (`$0.15/$0.60`).
  2. `latency_histogram.json` title says `p50 26 s, p95 103 s` vs `metrics.json` `25.888 s / 108.836 s` (binning/rounding difference).
  3. In `conclusions`, the 65-question tuning table's rubric faithfulness (`0.6209`) is scored on `n=55` answerable rows while RAGAS (`0.7337`) covers the 65-question pass (`metrics.json:342-354`).

---

## 6. Blueprint to Enlarge & Refine Text (Using 369w Headroom)

Add **~250–300 words** across `objectives` (`+50w`), `data` (`+40w`), `eda` (`+40w`), `training` (`+60w`), `evaluation` (`+50w`), `results` (`+30w`) while keeping `background <= 145w`, every section `< 520w`, and `Flesch >= 45`:
1. **`objectives` (+50w):** Explain *how* `verify.py` scores against full cited chunks (not 240-char snippets) and rewrites/drops failing claims; split long sentences.
2. **`data` (+40w):** Explain topic pattern/anchor matching (`config.py:36-102`) and why `final_v3` (`120` questions) superseded the `55`-question gate.
3. **`eda` (+40w):** Quantify the resulting chunk count and what right-censoring at `12,000` chars implies for multi-hop synthesis.
4. **`training` (+60w):** Define `all-articles@5` in plain English and explain why `RRF (k=60)` avoids score-calibration overfitting.
5. **`evaluation` (+50w):** Define "mechanical checks" (verbatim substring, numbers, dates, negation) *before* giving counts; narrate the 3 tuning charts explicitly if kept here; break up dense bullets.
6. **`results` (+30w):** Group metrics cleanly by theme and explain why 10 answerable questions returned empty answers.
7. **`conclusions`:** Detach `retrieval_funnel` and convert the 3 semicolon-heavy historical bullets into a crisp 5-row stress-runs table.

---

## 7. Pattern Rollout Standard for `02–13`

1. Keep the `[opening intro & description -> diagram -> mid paragraph + bullets/table -> **In plain terms:** -> figures]` section rhythm.
2. Audit every `auto-NN-*` and hand-built diagram against final shipped architecture and numbers before rollout.
3. Ensure every `figures:` entry is explicitly introduced in its section's prose (zero stranded charts).
4. Explain custom deterministic checks/rails *before* quoting their pass/fail counts, keep bullets to `2–3` key numbers each, and hold sentences short enough for `Flesch >= 45`.
