# Round-3 review: 11-data-engineering story.yaml

- Target: `projects/11-data-engineering/story.yaml`, **working tree** (440 lines), on branch `wave8-articles-truthfulness-2026-11-25` with HEAD `c05accd0`. Line numbers below refer to the working tree.
- Round diff: `git diff -- projects/11-data-engineering/story.yaml`, plus `apps/showcase-web/src/diagrams/auto/11-data-engineering-3.ts`, which is also modified.
- Gold template: `projects/01-rag-agent/story.yaml`
- Round-2 review: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus-round2/11-data-engineering.md`. It graded HEAD, and every finding below was re-checked against the working tree.
- Evidence re-checked (all tracked; `reports/` contents are committed, only `reports/.gitignore` filters extras): `reports/results.md`, `reports/metrics.json`, `reports/evaluation_metadata.json`, `README.md`, `DESIGN.md`, `src/data_engineering/engines.py`.
- Mode: read-only. This file is the only one written.

## What Wave 8 changed

Wave 8 is a targeted truthfulness pass. It closes almost every numeric and factual defect from rounds 1 and 2.

- **EDA rewritten (L98-107, L126).** The unsourced daily pattern, "$16", "$200", the negative-fare claim, and "rush-hour" are gone. The section now has two traceable facts: 35 pickup dates (31 January plus 4 out-of-month) and the filter's 168,468 trips. The diagram `11-data-engineering-3.ts` was relabelled to match.
- **Technical fixes.**
  - pandas now reads CSV through its default parser (L131-132), which matches `engines.py:44`.
  - The task list says "rank the top 10 pickup zones by fare" (L31-32).
  - "object-heavy" is gone.
  - The SHA-256 scope is now correct (L15).
- **Number fixes.**
  - sqlite's fastest cell is the filter at 1.947 s (L195).
  - Memory is "about 2–4× less on compute tasks" (L286).
  - The memory_lollipop caption now gives the DuckDB range as 178-633 (L436).
  - "conversions take 1.9-5.9 s" became "each complete load-plus-query task" (L184).
  - "ladder" is gone.
- **Routing.** The EDA transition now points the parity catches at Evaluation (L123-124).
- **Roadmap.** Card 1 restores 39/39. Card 4 is retitled and carries slopes. Card 5 is now the deferred cold-cache work.

The cost of the pass: three sentences written as audit notes to the reviewer leaked into reader copy (see "New errors").

## Grades

| # | Dimension | R2 | R3 | One-line reason |
|---|---|---|---|---|
| 1 | Structure and article logic | 7 | 7 | The misroute is fixed. The Evaluation sizing frame is still unresolved, and the headline totals still repeat 6 times. |
| 2 | Engagement and human-like narrative | 6 | 6 | The EDA is now honest but thin. The meta sentences break the reader's flow. The parity catch is still buried. |
| 3 | Language quality | 6 | 6 | The ladder and $16./$200. typos are gone. New audit-voice sentences, "All 39/39", "file size" vs rows, and ragged line wrapping remain. |
| 4 | Technical depth | 8 | 8 | All three misdescriptions are fixed. EDA depth fell, and there is no real-data distribution artifact. |
| 5 | Truthfulness | 5 | 8 | Every number now traces to a committed file. Only a soft, unmeasured attribution ("mostly converting files") remains, and the README makes the same claim. |
| 6 | Roadmap cards | 6 | 8 | Verb-first titles, details of 58-74 chars, numbers restored, and the cold-cache card added. Card 5's gate is slightly misaligned with the README's deferred item. |
| 7 | Consistency with gold template | 7 | 7 | No bold Objectives thesis and no named-weakness question in Evaluation. Chart ids still appear in reader prose. |
| | **Overall** | **6.4** | **7.1** | The truthfulness is now sound. The writing still reads like a patched report rather than a finished article. |

## 1. Structure and article logic (7)

- Fixed: L123-124 now sends the parity catches to Evaluation.
- Still present: Evaluation opens with "support a platform sizing decision" (L214-218) and never makes the decision. No sentence says which engine fits which workload.
- Still present: the totals 0.16 / 0.22 / 2.99 / 40.55 s appear at L178-179, L202-207, L280-281, L286, L292, and L345. L277-281 still restates L175-181.
- New, structural: the EDA section (L96-127) now holds very little exploration. It has two facts and a meta disclaimer, then turns into measurement rules that belong in Objectives. The section's role in the story ("read the month") is mostly gone.

## 2. Engagement (6)

- Still present: the short_version (L3) and Background (L7-21) do not mention the 1,658 silently dropped trips. That is the most memorable result, and it sits in Evaluation (L230-234).
- Still present: there are ten diagram-tour imperatives: L13, L57, L80, L99, L188, L217, L220, L267, L277, L292.
- New: L106-107, L236-237, and L305 read as replies to a reviewer, not as narrative (see "New errors").

## 3. Language quality (6)

- Fixed: "ladder", the full stops inside backticks in `$16.`/`$200.`, and the PyArrow wording.
- Still present:
  - L3 is a run-on that ends in the fragment "NYC TLC 2024-01."
  - L263 "slow down directly in proportion to file size": the slopes are fitted against row count.
  - L236-237: "ulp" is used before it is defined.
  - L151-152: "bound paths" is never defined.
  - L248-249: the unit sits outside the backticks in `` `0.12` s `` but inside them in `` `1.15 s` ``.
- New:
  - L396 "All 39/39" is redundant. Use "39 of 39 measured cells passed…".
  - L190, L196, L237, L272-275, and L305 are now single long source lines inside otherwise hard-wrapped prose. This is cosmetic in YAML, but a sign of patching.
  - L185 "Conversion is not timed separately." is followed directly by L196 "The per-task import dominates the measured workflow". The first sentence weakens the second.

## 4. Technical depth (8)

The strengths are kept: untraced medians, the separate tracemalloc pass, fresh-process RSS, cold reads, the 1e-5 float band, the slope table, and the Limits section. All of round 2's technical misdescriptions are fixed:

- the pandas CSV reader (L131-132, matches `engines.py:44`);
- the distinct_sort task (L31-32, matches `metrics.json` "top-10 pickup zones by fare (ties by trips, zone)");
- "object-heavy" removed;
- the SHA-256 scope (L15, matches L72-75).

What was lost: the EDA has no real-data distribution at all. A small committed artifact would restore depth honestly, for example hourly counts, fare quantiles, and the number of negative fares.

## 5. Truthfulness (8)

### Verified in the working tree

| Line(s) | Claim | Source |
|---|---|---|
| L3, L8, L69, L292 | 2,964,624 rows, 43 MB | `metrics.json` dataset.n_rows; `evaluation_metadata.json` |
| L100-102 | 35 pickup dates, 31 January + 4 out-of-month | `metrics.json` groupby result: 35 days, including 2002-12-31, 2009-01-01, 2023-12-31, 2024-02-01 |
| L101 | ~95,600 per day | 2,964,624 / 31 = 95,633 |
| L105, L126 | 168,468 trips, fare > $50 and > 10 miles | `metrics.json` filter result rows = 168468 (identical on all 4 engines); description matches |
| L175-207, L333-345 | per-task medians, speedups, totals, geomeans | `results.md` and `metrics.json` summary (19.157 / 14.886 / 0.035; 0.163 / 0.221 / 2.986 / 40.549 s) |
| L195-196 | sqlite fastest cell is filter at 1.947 s; CSV read closest at 0.2× | `results.md` |
| L245-262, L354 | slopes and 10M timings | `results.md` scalability |
| L273, L292, L351, L436 | memory ranges | `results.md` memory |
| L286 | "about 2–4× less memory on compute tasks" | pandas/Polars 2.19-3.19×, pandas/DuckDB 2.72-4.30× on the six compute tasks |
| L274 | sqlite slowest 9/10, pandas slowest on write_parquet | `results.md` |
| L275, L352 | cold 1.23 vs 1.16, 5.82 vs 5.75 | `results.md` IO table |
| L231-234, L302 | 1,658 N/A-borough trips | `metrics.json`; README L138-141 |
| L320-322 | arm64, 16 cores, pandas 2.3.3, Polars 2.0.0, DuckDB 2.0.0, sqlite 3.47.1, pyarrow 26 | `evaluation_metadata.json` |
| L84, L50, L371 | 157 MB CSV, ~26 s CI | `evaluation_metadata.json`; README |
| L429-430 | caption 75-1985×, 0.01-0.2×, 5-110× slower | `speedup_vs_sqlite` max 1984.9; pandas/sqlite 0.009-0.20 |
| L405, L313-314 | slopes 0.31-0.76 vs 0.98-1.09 | `results.md` |
| L396 | 39/39 cells passed | README; Record L355 |

### Untraceable or contradicted

| Line | Claim | Status |
|---|---|---|
| L196, L272, L286 ("mostly converting files"), L424-426 caption | The per-task import or file conversion "dominates" sqlite's time | Soft. Conversion is not timed separately, as L185 itself says, and `metrics.json` sqlite `detail` is `{}`. README L100-101 makes the same claim, so it traces to committed prose, but not to a measurement. Suggest "likely dominated by the load step (not timed separately)", or cite the evidence: sqlite's in-SQL filter on 10M synthetic rows still takes 6.5 s. |
| L408 | "stack about four real months" as the gate for a cold-cache card | Not contradicted. README L215 defers a *bigger-than-RAM* out-of-core track, and four months (~12M rows) is not bigger than RAM on this machine. The gate does not match the deferred item. |

**Untraceable numbers: 0. Contradicted numbers: 0.** There is one soft, unmeasured causal attribution, and the README backs it.

## 6. Roadmap cards (8)

| L | Title | Verb-first | Detail chars | Status | Reality check |
|---|---|---|---|---|---|
| 394-396 | Gate every timing on identical rows | yes | 58 | shipped | True (README; Record L355). "All 39/39" is redundant. |
| 397-399 | Keep timings honest with untraced medians | yes | 65 | shipped | True (`evaluation_metadata.json` protocol; README L120-125). |
| 400-402 | Catch dropped rows with parity checks | yes | 63 | shipped | True (`metrics.json`; README fix plus regression test). |
| 403-405 | Measure scaling from 1M to 10M rows | yes | 65 | shipped | True (`results.md` slopes). |
| 406-408 | Extend the benchmark to cold caches | yes | 74 | next | Matches README L162-163 and L215 (deferred cold-cache track). The gate, "stack about four real months", fits the old "real 10M" card better than "bigger-than-RAM". Suggested detail: "Gate: a bigger-than-RAM real track and a pre-registered cache-drop protocol." |

All titles are at most 41 chars and all details at most 74 chars, and the "Gate:" prefix matches gold card 5. The "real trips at 10M" concern from round 2 has been folded into card 5's gate rather than kept as a separate card. That is acceptable.

## 7. Consistency with the gold template (7)

- Matches: the Background shape (bold hook, three bold-led steps, a "Next" link, then `In plain terms`), `In plain terms` in all 7 sections, the roadmap "Gate:" convention, and numbers in roadmap details.
- Still different:
  - Objectives opens with "The protocol diagram below shows…" (L25) instead of gold's bold thesis line.
  - Evaluation has no gold-style bold named-weakness question. The obvious one: **"How far does one laptop and one month generalize?"**
  - L198-200 and L251-253 name chart ids (`speedup_overview`, `scalability_lines`) in reader prose. Gold never does.
  - Transitions at L60-61, L91-92, and L283-284 keep the "X; next, the <noun phrase>" stamp.

## Round-2 finding status

| # | Round-2 finding | R3 line | Status |
|---|---|---|---|
| 1 | Transition misroute: parity catches → Training | L123-124 | FIXED |
| 2 | Evaluation sizing frame unresolved | L214-218 | STILL PRESENT |
| 3 | Headline totals repeated; Results restates Training | L178-207, L277-281, L286, L292, L345 | STILL PRESENT |
| 4 | Formulaic, verbless transitions | L60, L91, L198, L251, L283 | PARTLY FIXED (EDA one rewritten) |
| 5 | Parity catch absent from short_version and Background | L3, L7-21 | STILL PRESENT |
| 6 | Ten "Read/Follow/Use the…" openers | 10 sites | STILL PRESENT |
| 7 | EDA `In plain terms` | L126 | FIXED (now traceable) |
| 8 | "ladder" undefined | L184 | FIXED |
| 9 | short_version run-on and trailing fragment | L3 | STILL PRESENT |
| 10 | Register mismatch ("ulp" before definition, "bound paths") | L146, L236-237 | STILL PRESENT |
| 11 | "tie at 529-633 MB" | L273 | FIXED (round 2) |
| 12 | "7-44x" for both engines | n/a | FIXED (round 2) |
| 13 | pandas reads CSV with PyArrow | L131-132 | FIXED |
| 14 | "sort distinct values" | L31-32 | FIXED |
| 15 | "object-heavy" group-by | L190 | FIXED |
| 16 | Daily pattern from the synthetic docstring / "rush-hour" | L98-107, L126 | FIXED |
| 17 | "$16" | n/a | FIXED |
| 18 | "$200" with airport and late-night attribution | n/a | FIXED |
| 19 | Negative fares as "real fare adjustments" | n/a | FIXED |
| 20 | EWR ulp attribution | L236-237, L305 | FIXED in substance (but see new error N2) |
| 21 | sqlite join "best cell at 3.65 s" | L195 | FIXED |
| 22 | Cold-CSV inversion | L275 | FIXED (round 2) |
| 23 | "2–3× less memory" | L286 | FIXED |
| 24 | memory_lollipop caption "178-529 MB" | L436 | FIXED |
| 25 | "conversions take 1.9-5.9 s" | L184-185 | FIXED (residual attribution at L272/L286; see §5) |
| 26 | Roadmap card 1: restore 39 of 39 | L396 | FIXED |
| 27 | Roadmap card 4: garbled title, slopes lost | L403-405 | FIXED |
| 28 | Roadmap card 5: say how to reach 10M real rows | L406-408 | PARTLY FIXED (folded into the cold-cache gate) |
| 29 | Missing `next` card for deferred cold-cache track | L406-408 | FIXED |
| 30 | Evaluation lacks gold-style named weakness | L212-264 | STILL PRESENT |
| 31 | Diagram `11-data-engineering-3.ts` EDA labels | diagram L19-31 | FIXED |
| (body) | L15 SHA-256 scope overstated | L15 | FIXED |
| (body) | "file size" vs row count | L263 | STILL PRESENT |
| (body) | Objectives lacks bold thesis; chart ids in prose | L25, L198-200, L251-253 | STILL PRESENT |

Totals for the 31 numbered findings: **22 fixed, 2 partly fixed, 7 still present** (#2, 3, 5, 6, 9, 10, 30). Three un-numbered round-2 body notes are also still present. All 7 are structure, engagement, or style findings. No truthfulness finding is still present.

## New errors introduced by Wave 8

| # | Line | Problem |
|---|---|---|
| N1 | L106-107 | "This is a measured predicate result; the article makes no unsourced claim about typical fares, hourly peaks, or fare causes." This is an audit note to the reviewer, published as reader copy. A reader never saw those claims, so the denial is baffling. Delete it. |
| N2 | L236-237 | "the committed evidence does not tie that case specifically to EWR." This brings up EWR only to deny it, and "committed evidence" is repo jargon. Replace with "a group sum can sit within one ulp of a rounding cliff". |
| N3 | L305 | "no EWR-specific attribution is committed." The same leak appears in Conclusions. Delete the clause. |
| N4 | L185 vs L196, L272, L286 | The article states that conversion is not timed separately, then attributes sqlite's cost to import or conversion three times ("dominates", "due to file conversion", "mostly converting files"). Hedge it once, or cite indirect evidence. |
| N5 | L102-103 | "remain visible in the committed per-day result": more repo-voice. Use "stay in the per-day result instead of being dropped". |
| N6 | L96-127 | The EDA section is now mostly measurement rules. The "read the month" role is hollow, which hurts engagement and depth. This is not a factual error. |
| N7 | L396 | "All 39/39" is redundant. |

## Top 5 remaining fixes

1. **L106-107, L236-237, L305, L102-103: remove the audit-voice sentences (N1-N3, N5).** These are the only blockers. Each is a one-clause deletion or rewrite.
2. **L3 and L7-21: lead with the parity catch.** Rewrite the short_version as two sentences, for example: "Ten data tasks over 2.96M NYC taxi trips, parity-checked on four engines before any timing counted; the check caught pandas silently dropping 1,658 trips. Polars runs 19× and DuckDB 15× faster than pandas; sqlite is correct but ~29× slower once file loading is timed." Add a one-line mention to the Background's "Match check first" step.
3. **L214-218 and L212-264: resolve the sizing frame and add the named weakness.**
   - End Evaluation with an explicit recommendation, for example "Polars for dataframe pipelines, DuckDB for SQL-first teams, sqlite only when data already lives in a database".
   - Add a gold-style bold question about generality (one month, one laptop, warm page cache).
4. **L184-185, L196, L272, L286, and the L424-426 caption: make the sqlite cost attribution consistent.** Either hedge once ("the load step, not timed separately, likely dominates") or cite indirect evidence. For example, the 10M synthetic filter still takes 6.5 s in sqlite against pandas's 0.18 s.
5. **Cut the repetition and tidy the language.**
   - Drop L277-281, which restates Training.
   - Fix L263 "file size" → "row count".
   - Define "ulp" before L236 and "bound paths" at L146, or drop them.
   - Change L396 to "39 of 39".
   - Replace chart ids in prose (L198-200, L251-253) with figure names.
   - Optionally, align card 5's gate with README's "bigger-than-RAM" deferred track.

## Ready to publish?

**No, but it is one short editing pass away.** Every number and technical claim now traces to committed evidence, and the round-1/2 truthfulness defects are all fixed. The blockers are editorial:

- three reader-facing sentences written as reviewer notes (L106-107, L236-237, L305) would confuse any reader;
- the sqlite cost attribution contradicts the article's own caveat (L185 vs L286).

Fix 1 and 4 above, and the article is publishable at about 7.5. Fixes 2, 3, and 5 would lift it toward gold.
