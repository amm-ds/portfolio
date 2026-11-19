# Third pass: articles, language, roadmap, projects page, and the leftovers

Date: 2026-11-19
Reviewer: Claude Code
Owner decision recorded: roadmaps show finalized steps only (`shipped`). `next` and `blocked` stay in the stories as authored state and are not rendered.
Implementation: none changed. This is the plan and the findings. Handoffs follow after owner approval.

## A. What the roadmap shows now, and what it cannot do

With only `shipped` rendered, a visitor sees what was finished, not what is planned. Two consequences:
1. **The forward plan is invisible on the page.** The `next` and `blocked` cards carry the open work (for example 11's 10M real-trip benchmark and 12's TabPFN challenger). Those items need a home in the article body, under a "Next" heading, or they disappear from the reader's view.
2. **Shipped titles mix three kinds of statement**, which makes the list hard to scan:
   - outcome: "Served MLP ties LightGBM on validation." (clear)
   - method: "Ranked chunk, model, and rerank choices." (tells the reader what was done, not what it showed)
   - jargon: "Added fleet-first ranking and CP-SAT arms." (06), "xGB tested −4.1% better" (07).

**Proposed milestone card rule (for the next pass):**
- Title: an outcome, 3–7 words, plain words, no abbreviations.
- Detail: one number or one decision, 90 characters or fewer, with the unit.
- Each project: 3–5 shipped milestones, in the order they happened.
- Next steps move to a short "Next" paragraph at the end of the article, with the gate that would change the claim.

## B. Roadmap cards that need rewriting (shipped only)

| Project | Card to fix | Problem | Proposed title |
|---|---|---|---|
| 01 RAG | "Ranked chunk, model, and rerank choices." | method, not outcome | "Chunk size and model choice tied on recall." |
| 01 RAG | "Shipped verify-on answers with three judges." | "verify-on" is internal jargon | "Answers pass a three-judge citation check." |
| 04 NLP | "Buy macro-F1 with data, not device." | unclear | "Macro-F1 rises 1.3–1.6 points per 3× more data." |
| 04 NLP | "Beat every rung with full data." | metric is the test split (0.9460), while the short copy quotes the fresh split (0.953 → 0.954) | rename to say "test split" in the detail |
| 06 Routing | "Added fleet-first ranking and CP-SAT arms." | jargon | "Solver arms tie on runtime at 12 s." |
| 07 Mobility | "xGB tested −4.1% better; the holdout has no vote." | "xGB" is not defined; the short copy calls the model "served GBM" | "Validation winner served; test leader rejected." |
| 08 Serving | "Caught a silent reasoning misconfiguration first." | reads as a bug report | "A silent config error was caught before the runs." |
| 09 Agentic | "Behavioral contracts made every call planned." | "contracts" is abstract | "All 52 captured calls followed the plan." |
| 10 Uplift | "Found the send-cost targeting break-even." | "$0.30" needs the unit and what it breaks | "Targeting wins once email costs exceed about $0.30." |
| 11 Data eng | "Polars and DuckDB scale sub-linearly." | log-log slope jargon | "Polars and DuckDB scale better than linearly." |

## C. Language and cross-validation across the articles

Checked: the roadmap titles and details against the short copy in `storyShort.ts` and the story text.

1. **04 uses two splits for the same claim.** The roadmap quotes the test macro-F1 (0.9460), the short copy quotes the fresh split (0.953 → 0.954). Both may be correct, but a visitor will see two different numbers. Name the split in both places.
2. **02 uses "one scored test origin" and "selection uses 2 origins".** Both are right, but the article should say once, in one sentence, which origin is scored and which are used for selection.
3. **07 calls the model "served GBM" in the copy and "xGB" in the roadmap.** Choose one name.
4. **Apps (agent-chat and document-intelligence) were covered by the UI pass only.** They have not had a content review. The document-intelligence eval table is now correct (H4/H5); agent-chat has a summary table generated from the report (H5). Their prose has not been checked against the committed reports.
5. **Language rules from P2 are applied to 01–13 but were not re-read after the roadmap changes.** The roadmap now shows shipped cards only, so each article's "Next" content needs a check.

## D. Projects page cards

The projects page shows: title, the `short_version` text, a results chip from the headline metric, and tags. Checks:
- **Short copy and roadmap agree on the headline numbers** for 01, 03, 09, 12 and 13 (checked against the P2 numbers list).
- **04 and 07 disagree on naming** (see C1 and C3). Fix in the short copy and the roadmap together.
- **Apps cards** use `summary` and `does` (in `apps.ts`). The summaries are accurate. The `does` line for agent-chat names "Kimi" and "Ollama" as providers; that's correct but it is a provider list that will age, so keep it generic: "a hosted or local model, with fallback".
- **Demo cards** use `title` and a digit-free "does" line. No numbers, so they cannot go stale.

Proposed rule: every card's results chip and short copy come from one place (the headline check already enforces the number). Add a check that each card's name for a model matches the article's name for the same model.

## E. RAG agent: deeper refinement

Current state (from the short copy and the roadmap):
- Stress set: 30 questions, 0.733 correct (CI [0.567, 0.867]); unsupported outcomes 5 of 30 (was 11).
- Independent set B: 0.633 correct; 9 of 30 unsupported, over the ≤6/30 gate. Two gates failed.
- Sealed held-out gate expanded from 15 to 55 questions; 9 of 11 failures are grounding, not retrieval.
- Cost: $0.000906 per query.

What limits the claim now:
1. **Sample size.** 30 stress questions gives a 95% CI about ±0.15. Any change of a few questions is inside the noise.
2. **Grounding is the failure, not retrieval.** Retrieval is fine; the answer step over-claims. That points at the generation and the citation check, not the retriever.
3. **The judge is not calibrated.** The verify-on answers use three judges. None is checked against labelled human decisions, so the 9-of-30 unsupported rate has no known error rate.
4. **A relevant citation can still back an overstated claim** (ForceBench 2026, preprint, secondary). The current check asks whether the cited passage supports the claim, not whether it warrants its strength.

Proposed refinements, in order:
- **R1. Calibrate the judges.** Label 100 claims (supported, overstated, unsupported) by hand, measure each judge's agreement, and keep only judges that agree with the labels. Output: agreement table with a CI. Cost: no hosted calls if the labelled set is built from committed answers; a re-judge run needs a cap.
- **R2. Add a warrant-strength check.** Score the claim against the passage on a three-level scale (supports, overstates, does not support). Report the overstatement rate separately from the unsupported rate. Source: ForceBench (secondary).
- **R3. Grow the sealed set to 100+ questions** and re-run once, with the sealed set fixed before the run. This is the roadmap's "write a fresh sealed set first".
- **R4. Retrieval baseline.** Compare the current retriever with BM25 and a reranker on the same sealed set. If BM25 ties, say so; that tells the reader the retriever is not the bottleneck. Measure recall@5 with a CI.
- **R5. Report the error budget in the card.** Per query cost, latency median and p95, and the unsupported rate with its CI, next to each other.

Owner decisions needed for RAG: approve R1 and R2 as hosted judge runs under a cap (suggested $5), and approve R3 as a new sealed set (no hosted calls needed to build it, but the run costs).

## F. Leftovers from the earlier audits

From the second-pass review (`collaboration/reviews/20261119-project-review-2/00-index.md`):
- C1: 12 short copy missing the LightGBM validation tie. Check whether H-series or P2 fixed it.
- C2: 10 short copy names "+$2,812" without the metric. Check.
- C3: 06 "hand-written search" wording. Check.
- C4: 03 "proves" and "champion" definitions. Check.
- C6: 09 card missing the h19 caveat. Check.
- C5, C7: unread stale-word hits in 01, 12 and 13. Read them in context.

From the gap analysis (`collaboration/reviews/20261119-gap-analysis/00-gaps-benchmarks-approaches.md`):
- 06 PyVRP table conflict (two readings of arXiv 2403.13795v2): unresolved; do not cite PyVRP numbers.
- 02 reconciled M5 row: unresolved (owner decision).
- 03: VUS-PR on TSB-AD not run; run count disclosed in the card only.
- 04: selective-classification (coverage vs accuracy) not evaluated.
- 09: multi-trial reliability (pass^k) not run.
- 10: single-protocol Qini comparison not run.
- 12: TabPFN-2 challenger handoff approved; Kimi has not run it.

From the open questions (`OPEN_QUESTIONS.md` files):
- 02 reconciled LightGBM row; 04 cascade interval; 06 routing interval; 12 TabPFN (now the TabPFN-2 route).
- P2 open questions (8 items): 03 threshold_sweep numbers, 06 "8 published references", 09 short_version live claims, 09 unplanned calls, 13 three numbers, 10 two observations, 12 mandated text deviations, numbers traced only to design docs.

From the infrastructure:
- W3: provenance stamp drops `_meta` results blocks on regeneration.
- Full pytest result: the P2 report and Kimi's chat disagree on coverage (97.70% vs 97.80%); re-run before commit.
- Dev API on :8002 predates the schema change: restart before browser checks.
- Production deploy needed for H9 and the UI fixes.
- The TabPFN pin was reverted in this session (uncommitted on top of commit 390c141).

## G. Sequencing

1. **Owner review (now):** the open questions list (F), the roadmap rule (A), and the RAG proposals (E).
2. **Handoff Q1 (copy and roadmap, no numbers):** apply the milestone rule to all 13 projects; rewrite the cards in section B; fix the naming in section C; keep the existing headline numbers.
3. **Handoff Q2 (apps content review):** agent-chat and document-intelligence prose checked against their committed reports.
4. **Handoff Q3 (RAG R1–R5):** calibration first, then the warrant check, then the new sealed set, each under its own cap.
5. **Reviewer pass (Sonnet/Opus, top level):** check Q1–Q3 against the open questions and the gap analysis, then decide which leftovers close.
6. **Owner:** commit in parts, re-run pytest, restart the dev API, deploy.

## H. Owner decisions

1. Approve the milestone card rule (section A) for Q1.
2. Approve the section B rewrites, or send them back with your own titles.
3. Decide the 04 split naming (test or fresh) and the 07 model name (served GBM or xGB).
4. Approve RAG R1 and R2 as hosted judge runs under a $5 cap, and R3 as a new sealed set.
5. Decide whether the apps get the content review (Q2) in this pass.
6. Re-run the full pytest before you commit.
