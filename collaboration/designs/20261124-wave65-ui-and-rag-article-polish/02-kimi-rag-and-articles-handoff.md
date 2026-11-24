# Implementation Handoff: RAG 01 Article Depth & Report-Backed Polish (Wave 6.5B)

Date: 2026-11-24
Designer: Claude Code
Executor: Kimi Code
Status: **approved (ready for Kimi execution on a new branch from `main` @ `4409e2ae`)**
Related artifacts:
- `projects/01-rag-agent/story.yaml` (current baseline at `4409e2ae`)
- `projects/01-rag-agent/README.md`, `DESIGN.md`, `reports/`
- `collaboration/reviews/20261124-rag-article-review/00-review.md`

---

## 1. Objective & Owner Feedback

The UI/demo CSS fixes, neutral 5-card roadmap, and tracker fixes (`T1–T6`) are **already shipped on `main` (`4409e2ae`)** — **do not alter them**.

The owner reviewed `projects/01-rag-agent/story.yaml` at `4409e2ae` and asked for **more depth, richer explanations, and fuller narrative text** ("between what was before and how is it now"), grounded directly in the committed `projects/01-rag-agent/reports/` artifacts and written in engaging, clear, non-jargon-choked prose that showcases real technical expertise for both technical and non-technical readers.

---

## 2. Scope & Guardrails

### In Scope
- `projects/01-rag-agent/story.yaml` — expand `objectives`, `data`, `eda`, `training`, `evaluation`, `results`, and `conclusions` prose to rich, substantive case-study depth while keeping `background` under its 150-word hard cap.
- `projects/01-rag-agent/README.md` and `docs/projects/01-rag-agent.md` — minor prose/language alignment only if needed so numbers and terminology match `story.yaml` 1:1.
- `apps/showcase-web/src/lib/staticRegistry.ts` (and `storyShort.ts` / `route_manifest.json` only if `check` requires regeneration).

### Out of Scope
- **Do NOT touch** `apps/showcase-web/src/styles/*` or `ProjectsIndex.test.tsx` / `ForecastWorkbench.test.tsx` (Wave 6.5 UI fixes already shipped).
- **Do NOT touch** `projects/01-rag-agent/story.yaml` `roadmap:` (keep the 5 neutral milestone cards as-is) or `short_version:`.
- **Do NOT run** any hosted LLM calls or paid APIs, and **do not** fabricate numbers not found in committed `reports/`.
- **Do not commit, push, or merge.**

---

## 3. Authoring & Depth Contract (`projects/01-rag-agent/story.yaml`)

Read these committed reports first so every explanation, mechanism, and metric is 100% grounded:
- `projects/01-rag-agent/reports/final_v3_e2e/f1_summary.json`
- `projects/01-rag-agent/reports/final_v3_e2e/metrics.json`
- `projects/01-rag-agent/reports/retrieval_sweeps/s3_structure_hybrid_diverse__final_v3.json`
- `projects/01-rag-agent/reports/retrieval_baseline/final_v3.json`
- `projects/01-rag-agent/reports/judge_calibration_v2/owner_sample_validated.json`
- `projects/01-rag-agent/reports/metrics.json` & `DESIGN.md`

### Target Word-Count & Readability Sweet Spot
Hit **substantial depth without triggering any `lint_story_language.py` error or warning**:
- `background`: **130–145 words** (hard cap is `150` words; keep tight!).
- `objectives`: **240–300 words** (explain *why* each guardrail exists: calibrated refusal vs. open-web hallucination, `0.6` claim support floor + 2 bounded repairs, `$0.01/query` ceiling, local-vs-hosted privacy trade-off).
- `data`: **240–300 words** (explain corpus curation, anchor titles, 12,000-char cap rationale, SHA-256 contract, and why the 3-way mix tests retrieval, multi-hop composition, and refusal).
- `eda`: **190–240 words** (explain topic balance vs. dump-order bias, right-censored lengths, missing flagship pages discovered during scan, and how direct verification prevented misleading averages).
- `training`: **430–500 words** (soft cap `550`; explain *how and why* each of the 4 stages of `S3` works — title-anchored `S1` chunks, FAISS + BM25 RRF `k=60` fusion `S2`, cross-encoder reranking + 2-chunk per-article cap `S3` — plus the tuning evidence from chunk-size sweep, MiniLM vs. BGE-small, and reranker lift `0.718 -> 0.808`, alongside the `search()` code excerpt).
- `evaluation`: **420–500 words** (soft cap `550`; explain seeded floors, all three judges — rubric taxonomy, RAGAS, per-claim verifier — what failed in the earlier 44% false-acceptance judge, how `judge_v2` near-miss negatives fixed it to `30/30` agent-audited agreement, bounded agent loop rails `12/16/200k` + soft in-tool ceiling, and the honest disclosures on single-family judging + `final_v3` consumption).
- `results`: **400–480 words** (soft cap `550`; explain the `final_v3` outcomes in depth — overall F1/accuracy/faithfulness with Wilson CIs, single-hop/multi-hop/unanswerable slices, `verify_funnel` claim-level accounting, why failures shifted from hallucinations `17/65` to conservative unnecessary refusals `10/92`, real chat trace transparency, and exact cost/latency).
- `conclusions`: Keep the structured `## Results summary`, `## What the experiment taught`, `## Limits`, `## Exact numbers`, `## Measured alternatives`, and `## Protocol` sections rich and well-organized.

### Non-Negotiable Structure & Factual Rules
1. **Section Rhythm:** Bold hook + 2–3 plain-English sentences $\to$ diagram (where defined) $\to$ detailed, scannable bullet points $\to$ summary table / visualization context $\to$ `**In plain terms:**` takeaway ending with `[Next: <Section> →](#sec-<id>)`.
2. **Readability (`Flesch >= 45`):** Use crisp, direct sentences (12–20 words on average) and clear verbs so technical depth stays effortless to read and `lint_story_language.py` reports **0 errors, 0 warnings**. No em-dash clause joins (`—`); use periods or colons cleanly. Use `pp.` (with period) if abbreviating percentage points.
3. **Truth-in-Copy (Preserve All Opus Fixes):**
   - Answer-path spend is `$1.014` (`$0.0084/query`), total incl. judging is `$1.458` (`$0.0121/query`) — never cite `$2.0392` or `$2.04`.
   - Say `1 of 120 answers` kept an unsupported claim (and `2 of 150` judged claims before drop/repair).
   - Say `S3` led on `all-articles@5` across development splits (not raw `recall@5` on every split).
   - Distinguish `10` unnecessary empty answers vs. `11 of 92` answerable questions missed (including 1 retrieval miss).
   - Explicitly note that `kimi-for-coding` generated, verified, and judged (cross-judge pending), that `30/30` was a reviewer-agent audit (owner hand-label pending), and that `final_v3` is consumed.

---

## 4. Verification Gates (Run All Before Closeout)

```bash
uv run python scripts/lint_story_language.py   # MUST be 0 errors, 0 warnings
uv run python scripts/check_headline_numbers.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/check_docs.py
uv run python scripts/gen_static_registry.py --check
uv run python scripts/gen_story_short.py --check
uv run python scripts/gen_route_manifest.py --check
uv run mkdocs build --strict
cd apps/showcase-web && npm test && npm run lint && npm run build
```

Write your closeout at `collaboration/reviews/20261124-wave65b-rag-article/00-closeout.md` with word counts, Flesch scores, and full gate outputs, then stop without committing.
