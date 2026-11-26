# Review: 11-data-engineering story.yaml (Wave 6.6)

- Target: `projects/11-data-engineering/story.yaml` (480 lines)
- Gold template: `projects/01-rag-agent/story.yaml`
- Round diff: `git diff -- projects/11-data-engineering/story.yaml` is **empty**. The working tree is clean, and the Wave 6.6 edits are already committed in `18adc59d`. I reviewed `git show 18adc59d -- projects/11-data-engineering/story.yaml` as the round diff.
- Evidence checked: `README.md`, `DESIGN.md`, `reports/results.md`, `reports/metrics.json`, `reports/evaluation_metadata.json`, `src/data_engineering/{engines,tasks,synthetic,harness}.py`, `apps/showcase-web/src/diagrams/auto/11-data-engineering-3.ts`.
- Reviewer mode: read-only. No repository file other than this review was written.

## What the round changed

- Renamed every `**Business summary:**` to `**In plain terms:**` (7 sections).
- Added a one-line closing transition with an anchor link before each `In plain terms` (6 sections).
- Bolded the first sentence of Background.
- Roadmap: titles changed from past tense with a full stop to imperative with no full stop. Two details lost their numbers: "39 of 39 measured cells" became "every measured cell", and "Log-log slopes 0.31-0.76 ..." became "The two columnar engines grow sub-linearly ...".

The round was mechanical. It did not touch any of the truthfulness problems below, and the roadmap edits made two details vaguer.

## Grades

| # | Dimension | Grade | One-line reason |
|---|---|---|---|
| 1 | Structure and article logic | 7 | Clear arc from protocol to data, measurement, and lessons. Transitions are present but formulaic, one points readers to the wrong section, and Results/Conclusions repeat each other heavily. |
| 2 | Engagement and human-like narrative | 6 | Concrete catches (N/A borough, EWR rounding cliff) are the best material. The prose is a tour-guide loop of "Read the…", "Follow one…", "Use the…". |
| 3 | Language quality | 6 | Mostly clear, but there is undefined jargon ("ladder"), headline numbers repeat about 7 times, and the article explains Parquet and CSV to a reader it then hands "ulp". |
| 4 | Technical detail depth | 8 | Strong protocol: untraced medians, a separate tracemalloc pass, fresh-process RSS, a float-band determinism gate, log-log slopes, and honest Limits. A code excerpt is included. |
| 5 | Truthfulness | 5 | The benchmark tables match `results.md`/`metrics.json` exactly. The whole EDA paragraph has no committed source, and five prose claims contradict the committed metrics. |
| 6 | Roadmap cards | 7 | Verb-first, all ≤90 chars, sensible statuses. One title is garbled, details lost specificity this round, and the README's deferred work is missing. |
| 7 | Consistency with gold template | 7 | Every section has `In plain terms`. Transitions use one rigid "X; next, the Y (link)" fragment, while the gold version uses varied full sentences ("next, we trace how…"). |
| | **Overall** | **6.5** | Solid engineering article with an exact core record. The EDA section and several interpretive sentences do not survive a check against the project's own files. |

## 1. Structure and article logic (7)

- The section order works: contract (Background), rules (Objectives), pinned input (Data), what the data looks like (EDA), engines and speedups (Training), protocol evidence and scaling (Evaluation), three figures (Results), record (Conclusions).
- **L136-137, transition misroute:** "next, the speedup figure and the parity catches ([Training →](#sec-training))". The parity catches (N/A borough, EWR drift) are in **Evaluation** (L241-250), not Training.
- **L222-229:** Evaluation opens on "platform sizing decision" and "what an engine change buys" before any evidence. The sizing frame is asserted but never resolved. No sentence says which engine to pick for which workload.
- **Results (L269-307) vs Conclusions (L309-422):** the totals 0.16 / 0.22 / 2.99 / 40.55 s, the geomean x19.2 / x14.9, and the memory ranges each appear in Training, Results, and Conclusions, then again in the headline table and Record table. Results L295-299 is a near-verbatim restatement of Training L193-196.
- The transitions are all one shape: "The diagram sets…; next, …" (L22, L66, L99, L136, L215, L262, L301). Several are verbless fragments: "next, the pinned January file and its projection".

## 2. Engagement (6)

- The strongest narrative material is the two bugs the gates caught (L241-250). It sits halfway down Evaluation. The short_version and Background do not mention it, yet it is the most human, memorable part of the story.
- Imperative diagram-tour openers repeat across sections: "Follow one task through" (L15), "Read the diagram from input" (L63), "Follow the projection branch" (L88), "Use the EDA diagram" (L109), "Read the per-task spread" (L203), "Read the per-task evidence" (L228), "Follow one cell" (L231), "Read the three figures" (L271), "Use the dot plot" (L295), "Read the summary diagram" (L313). That is ten in one article.
- EDA's `In plain terms` (L139) opens "The diagram covers 2.96 million real trips". It narrates the diagram instead of stating a finding.

## 3. Language quality (6)

- **L200 "40.55 s for the ladder"**: "ladder" is never defined in the article. It is internal vocabulary from README L73.
- L3 short_version reads as a run-on: "…sqlite answers every SQL task but file conversion leaves it ~29x slower; 1M-10M tracks show the fast two scaling sub-linearly. NYC TLC 2024-01." The trailing fragment is a dangling label.
- Register mismatch: Parquet, CSV, join, floating point, CI, and RSS each get a lay definition (L34-52). Five paragraphs later the reader gets "one ulp of a rounding cliff" (L247-248) and "parameterized SQL … bound paths" (L149, L161).
- L283 "tie at 529-633 MB": a 20% spread is not a tie. README says "land within", which is more accurate.
- L421 "a 7-44x spread by task" covers Polars only. DuckDB's per-task range starts at 4.1x (L196).

## 4. Technical detail depth (8)

Good for an expert reader:
- Lazy plan timing includes `collect` (L147-149).
- sqlite's from-files workflow is explicitly timed (L154-158). The Limits section separates it from a long-lived database (L414-416).
- Determinism gate rationale: float reorder versus structural drift (L245-250).
- Cold-read caveat that the page cache is not dropped (L412-413).
- Scalability uses median of 2 with no probes (L393-395, matches DESIGN.md L130).

Technical gaps:
- **L146-147** "pandas reads with PyArrow … and parses CSV timestamps". Only parquet uses PyArrow. CSV goes through the default C parser: `pd.read_csv(path, parse_dates=[...])` at `engines.py:44`. This matters because pandas's CSV read is the largest single pandas cost.
- **L37** "sort distinct values" misdescribes `distinct_sort`. In `metrics.json` that task is "top-10 pickup zones by fare (ties by trips, zone)".
- **L205-206** "object-heavy group-by and window paths". The `groupby` task reads only datetime and numeric columns (`_GROUPBY_COLS`, `tasks.py:223`). DESIGN.md L63 says the working schema has no object columns. The explanation for the pandas cost is not supported.

## 5. Truthfulness (5)

### Verified (exact match to committed files)

The headline table L362-374 matches `results.md` and `metrics.json` cell for cell. The figures below were all checked as well:

- Data scale: 2,964,624 rows; 43 MB parquet (42,552,670 B); 157 MB CSV vs ~700 MB (DESIGN L33); 31 partitions; 35 distinct dates (DESIGN L45); 95,600/day (2,964,624/31).
- Headline results: geomeans 19.157 / 14.886 / 0.035; totals 2.99 / 0.16 / 0.22 / 40.55; ~29x slower (1/0.035); per-task ranges 6.7-43.5 and 4.1-38.4; Polars fastest on 9 of 10; sqlite slowest on 9 of 10.
- Memory: peak RSS ranges for each engine (L279-281, L319-320, L380).
- Cold vs warm: CSV 1.23 / 1.165 and sqlite 5.82 / 5.75.
- Scalability: all slope ranges; 10M group-by 1.15 / 0.031 / 0.020 / 26.4 s; CSV read 19.4 s vs 0.12 s.
- Speedup caption: sqlite ratios 75-1985x (`speedup_vs_sqlite` min 75.07, max 1984.9) and 0.01-0.2x vs pandas.
- Parity and protocol: 1,658 N/A trips (README L139); EWR 295 trips (`metrics.json`); 1e-5 band; 39 cells; ~26 s CI.
- Environment: versions, 16 cores, and arm64 (`evaluation_metadata.json`).
- The code excerpt L165-186 matches `tasks.py` L199-219.

### Untraceable claims (no committed source in the project)

| Line | Claim | Finding |
|---|---|---|
| L112-114 | "quiet at 4 a.m., has two evening peaks, and is busier on business days than weekends" | The only source is the **synthetic generator's** docstring (`synthetic.py:62, 67`), which is not real-data EDA. The generator code also draws `hour` and `day` uniformly (`synthetic.py:68-70`), so the docstring is not true of the synthetic track either. No real-data hourly or weekday artifact is committed. |
| L116 | "a typical fare near $16" | No committed source. It appears only in the diagram `11-data-engineering-3.ts`, which mirrors the story. |
| L116-117 | "A long tail of airport and late-night rides stretches past $200" | No committed source, including for the attribution to airport and late-night rides. |
| L117-119 | "A handful of fares are negative because they are real fare adjustments" | No committed source for the count or the cause. |
| L139-140 | "strong daily patterns and skewed fares" | Inherits the four rows above. |
| L247-248 | "The 295-trip EWR borough sum sat within one ulp of a rounding cliff" | 295 EWR trips is in `metrics.json`. DESIGN L79 and `harness.py:115` describe the ulp case generically. Nothing committed ties it to the EWR sum. |
| L205-206 | "object-heavy group-by and window paths" | Not supported. See §4. |

### Contradicted by committed files

| Line | Claim | Evidence |
|---|---|---|
| L212 | "sqlite's join is its best cell at 3.65 s" | sqlite's fastest cell is **filter at 1.947 s**. Its best ratio to pandas is **read_csv at 0.202x** (join is 0.066x). Join is neither. |
| L290-291 | "pandas's cold CSV read (1.23 s) is the one place interpreter startup visibly registers" | CSV cold is only +5.5% (1.229 vs 1.165). pandas read_parquet is 0.072 vs 0.044 (+64%), partitioned_read 0.076 vs 0.048 (+59%), DuckDB write_parquet 0.111 vs 0.083. CSV is where startup registers **least** in relative terms. |
| L306 | "2-3x memory headroom for the columnar engines" | The pandas/Polars ratio runs 1.09x (write_parquet 577/529) to 3.2x (window). The pandas/DuckDB ratio runs 0.91x (write_parquet 577/633, so DuckDB uses more) to 4.3x (join 945/220). |
| L471-472 (memory_lollipop caption) | "Polars and DuckDB stay near 178-529 MB" | DuckDB peaks at 633 MB on write_parquet (`results.md`), and the article's own L281 says "DuckDB near 178-633 MB". |
| L199 | "conversions take 1.9-5.9 s per task" | 1.9-5.9 s is sqlite's **total task time**, load plus query. Conversion is not timed separately in `metrics.json`, so the range cannot be called conversion time. |
| L146-147 | pandas "reads with PyArrow … and parses CSV timestamps" | The CSV path uses the default parser (`engines.py:44`). |
| L37 | "sort distinct values" | The task is the top-10 zones by fare (`metrics.json` `distinct_sort.description`). |

**Count: 3 untraceable numbers** ("$16", "$200", "4 a.m."). In addition, **5 numeric claims contradict** committed metrics: L199 "1.9-5.9 s" labelled as conversion, L212 "3.65 s" as best cell, L290 "1.23 s … the one place", L306 "2-3x", L471 "178-529 MB". There are also 4 non-numeric untraceable or contradicted claims (L112-114 daily pattern, L117 negative-fare cause, L205 object-heavy, L247 EWR ulp attribution).

## 6. Roadmap cards (7)

| Card | Title verb-first | Detail chars | Status | Note |
|---|---|---|---|---|
| Gate every timing on identical rows | yes | 60 | shipped | This round dropped "39 of 39", which was traceable and more concrete. Restore it. |
| Keep timings honest with untraced medians | yes | 65 | shipped | Fine. |
| Catch dropped rows with parity checks | yes | 63 | shipped | Fine. This is the strongest card. |
| Show the fast two scale sub-linearly | yes, but garbled | 74 | shipped | The title parses badly ("the fast two scale" reads as a noun phrase). The detail lost the 0.31-0.76 vs ~1 slopes. Suggested: "Measure scaling from 1M to 10M rows" / "Polars and DuckDB slopes 0.31-0.76; pandas and sqlite ~1.0." (55 chars) |
| Benchmark real trips at 10M rows | yes | 50 | next | Sensible. Says nothing about how: one month has only 2.96M rows, so this needs about 4 months stacked. |

- The README Limits section (L159-162) names two deferred items: "the out-of-core cold-cache track and further engines". The roadmap has neither. The cold-cache item fixes a stated Limit (L412-413) and is a natural second `next` card, for example "Measure true cold-disk reads" / "Drop the OS page cache on a root-capable runner."
- Imperative titles on `shipped` cards match the gold template ("Pin Wikipedia corpus and contracts").

## 7. Consistency with the gold template (7)

- Every section ends with `**In plain terms:**`, as gold does. Good.
- Gold transitions are full sentences that say what the reader will do: "next, we trace how the corpus and test splits were built ([Data →](#sec-data))". Article 11 uses one template seven times: "<X> sets/is …; next, the <noun phrase> (link)". This reads as machine-stamped.
- Gold Evaluation names its own weakness in a bolded question ("**How clean are the test set and judge?**"). Article 11 Evaluation has no equivalent. Its weaknesses (single shared machine, page cache not dropped, synthetic 10M) appear only in the Conclusions Limits list.
- Gold roadmap details keep a number where one exists ("30/30 blind owner-labelled audit; 104/120"). This round removed numbers from two of article 11's cards.

## Top 5 fixes (by severity)

1. **`story.yaml` L108-120 and L139-141: remove or source the EDA claims.** The phrases are "quiet at 4 a.m., has two evening peaks, and is busier on business days", "typical fare near $16", "stretches past $200", and "fares are negative because they are real fare adjustments". None of these has a committed real-data source, and the daily-pattern sentence is copied from the synthetic generator's docstring. Either commit a real-data EDA artifact (hour/weekday counts, fare quantiles, negative-fare count) to `reports/` and cite it, or cut the paragraph down to traceable facts. Traceable facts include: 35 dates (31 + 4 out-of-month, including 2002-12-31 and 2009-01-01 per `evaluation_metadata.json`), 95.6k/day, and the filter selecting 168,468 trips with fare > $50 and > 10 miles. Update the labels in `apps/showcase-web/src/diagrams/auto/11-data-engineering-3.ts` L19-31 to match.
2. **L212: "sqlite's join is its best cell at 3.65 s" is false.** Replace it with: "sqlite's fastest cell is the filter at 1.95 s, and the CSV read is closest to pandas at 0.2x; on every task the per-task import dominates."
3. **L289-293: the cold-read bullet inverts the evidence.** "pandas's cold CSV read (1.23 s) is the one place interpreter startup visibly registers" is wrong. Rewrite it as: cold CSV adds about 5% for pandas (1.23 vs 1.17 s), while the short parquet reads show the largest relative jump (pandas 0.072 vs 0.044 s). sqlite's cold and warm reads stay within 1% because the load dominates.
4. **L306 and the memory_lollipop caption L471-472: the memory claims contradict `results.md`.** "2-3x memory headroom for the columnar engines" and "Polars and DuckDB stay near 178-529 MB" are both wrong. Replace them with "columnar engines use 2-4x less memory on compute tasks; on parquet write all three land at 529-633 MB", and set the caption to "Polars 200-529 MB, DuckDB 178-633 MB". Change "tie" at L283 to "land within".
5. **L198-200 and L146-147: mislabelled cost and parser.** "conversions take 1.9-5.9 s per task and 40.55 s for the ladder" mislabels total task time as conversion time and uses the undefined word "ladder". Change it to "sqlite's tasks, load included, take 1.9-5.9 s each and 40.55 s in total." At L146, change "pandas reads with PyArrow" to "pandas reads parquet through PyArrow and CSV through its default parser". Also fix the transition misroute at L136-137 ("the parity catches" are in Evaluation) and restore "39 of 39" in roadmap card 1 (L427).

Secondary (not ranked): drop "object-heavy" (L205), correct "sort distinct values" (L37), qualify "7-44x" as Polars-only (L421), cut the Results L295-299 restatement, and vary the ten imperative "Read/Follow/Use the …" openers.
