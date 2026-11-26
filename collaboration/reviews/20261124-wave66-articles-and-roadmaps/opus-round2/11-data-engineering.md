# Round-2 review: 11-data-engineering story.yaml

- Target: `projects/11-data-engineering/story.yaml` at HEAD (445 lines). Line numbers below refer to this version.
- Gold template: `projects/01-rag-agent/story.yaml`
- Round-1 review: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/11-data-engineering.md` (graded the `18adc59d` version)
- Round diff: `git diff --word-diff -w 18adc59d HEAD -- projects/11-data-engineering/story.yaml`. The only commit touching the file since round 1 is `e69bba84`.
- Evidence re-checked: `README.md`, `DESIGN.md`, `reports/results.md`, `reports/metrics.json`, `reports/evaluation_metadata.json`, `src/data_engineering/{engines,fetch,synthetic}.py`, `apps/showcase-web/src/diagrams/auto/11-data-engineering-3.ts`.
- Mode: read-only. This file is the only one written.

## What changed since round 1

`e69bba84` mostly restyled the article. It did not fix the truthfulness findings.

- Background was rewritten. It now has a bold hook, "Speed claims mean little unless every engine returns the exact same table.", and three bold-led steps. This matches the gold template's shape.
- Most numbers, engine names, and figure ids are now wrapped in backticks.
- Every `In plain terms` line was rewritten into lay prose.
- Two tables were added: an engine summary in Training (L207-212) and a slope table in Evaluation (L260-266).
- The Results bullets were rewritten. The "tie" wording and the inverted cold-read claim are gone.
- The Conclusions `In plain terms` was rewritten, which removed "7-44x spread".
- The roadmap and figure captions changed only in YAML quoting.
- Training `metrics_keys` changed from `[groupby, read_csv, window]` to `[]`.

Every round-1 truthfulness finding except the cold-read inversion is still present. The edit also added one new untraceable claim: "rush-hour" at L129.

## Grades

| # | Dimension | R1 | R2 | One-line reason |
|---|---|---|---|---|
| 1 | Structure and article logic | 7 | 7 | The new Background and the two tables help. The misrouted transition is still there, and the headline totals now appear 6 times instead of 5. |
| 2 | Engagement and human-like narrative | 6 | 6 | The Background hook is better. The best material (the N/A borough and EWR catches) is still buried in Evaluation, and the ten "Read/Follow/Use the …" openers are unchanged. |
| 3 | Language quality | 6 | 6 | The lay `In plain terms` lines read better. Backtick wrapping is overdone and introduced typos (`` `$16.` ``, `` `$200.` `` with the full stop inside the code span, January `` `2024` ``, `` `4` `` engines). "ladder" is still undefined. |
| 4 | Technical depth | 8 | 8 | The slope table is a real addition. The three technical misdescriptions (PyArrow CSV, "sort distinct values", "object-heavy") remain. |
| 5 | Truthfulness | 5 | 5 | The tables still match `results.md` cell for cell. The EDA paragraph is still unsourced and now escalated to "rush-hour". Three numeric claims still contradict the metrics, and one more is mislabelled. |
| 6 | Roadmap cards | 7 | 6 | No round-1 roadmap finding was addressed. The title is still garbled, the details still have no numbers, and the deferred cold-cache work is still missing. |
| 7 | Consistency with gold template | 7 | 7 | Background now mirrors gold. The transitions are still stamped, and some are now clumsier ("pairs with `speedup_overview` before we inspect"). Evaluation still lacks gold's named-weakness question. |
| | **Overall** | **6.5** | **6.4** | The polish improved how the article reads, but it does not yet hold up against its own evidence. |

## 1. Structure and article logic (7)

- L126-127: the transition still sends readers to "the parity catches ([Training →](#sec-training))". The parity catches are in Evaluation (L235-244).
- L219-223: Evaluation still opens on "a platform sizing decision" and never resolves it. No sentence says which engine to pick for which workload.
- Repetition got worse. The totals 0.16 / 0.22 / 2.99 / 40.55 s appear at L181-182, L209-212 (the new table), L285-286, L291, L297, and L350. L282-286 still restates L178-184 almost word for word. The new Training table (L207-212) duplicates the headline table's last row at L350.
- The two new tables are useful. The slope table in particular gives the scalability claim concrete numbers.

## 2. Engagement (6)

- Better: the Background hook (L7) states the stakes in one sentence, as gold does.
- Still present: the short_version (L3) and Background say nothing about the parity catch. Silently losing 1,658 trips is the most memorable finding, and it sits in the middle of Evaluation (L235-239).
- Still present: there are ten diagram-tour imperatives: L13, L57, L80, L99, L191, L222, L225, L272, L282, L297.

## 3. Language quality (6)

- L188 "40.55 s for the ladder": "ladder" is still undefined in the article.
- L3: the short_version is still a run-on that ends in the label fragment "NYC TLC 2024-01."
- L106-107: `` `$16.` `` and `` `$200.` `` put the sentence's full stop inside the code span.
- Backtick use is inconsistent: `` `3.65` s `` (L200) and `` `0.12` s `` (L254) split the unit, while `` `1.15 s` `` (L253) does not. L297 wraps `` `10` ``, `` `4` ``, and January `` `2024` `` in code.
- L17 "Clean speed & RAM": the ampersand is a telegraphic heading. Gold uses "Draft & verify", so it is allowed, but "clean" is vague.
- The register mismatch is still present. Objectives gives lay definitions of Parquet, CSV, join, and floating point. Later the article uses "bound paths" (L149) without definition, and "ulp" at L241 is defined only after first use.
- L268 "slow down directly in proportion to file size": the slopes measure row count, not file size.

## 4. Technical depth (8)

Strengths from round 1 are kept: untraced medians, a separate tracemalloc pass, fresh-process RSS, the float-band gate, sqlite's from-files framing, and the Limits section. The new slope table (L260-266) matches `results.md` exactly.

Technical errors still present:

- L134-135: "`pandas` reads with `PyArrow` … and parses `CSV` timestamps". Only parquet goes through PyArrow. CSV uses `pd.read_csv(path, parse_dates=[...])` (`engines.py:44`).
- L31 "sort distinct values": the task is the top-10 pickup zones by fare, with tiebreaks (DESIGN L50, `metrics.json`).
- L193-194 "object-heavy group-by and window paths": the working schema has no object columns at the group-by stage (DESIGN L63, `_GROUPBY_COLS`).
- New, minor: L15 "Every engine reads the exact same `SHA-256`-checked parquet, `CSV`, and `31`-file layout". The SHA-256 pin covers the raw download only (`fetch.py:35-38`). The derived CSV and partitions are not hashed. L72-74 states this correctly.

## 5. Truthfulness (5)

### Verified at HEAD

- The headline table (L338-350), Record (L354-360), the new Training table (L207-212), and the new slope table (L260-266) match `results.md` and `metrics.json` cell for cell.
- Memory ranges (L278, L297, L356) match `results.md`: pandas 549-945, Polars 200-529, DuckDB 178-633, sqlite 396-1520.
- Cold reads (L280, L357) match: 1.229/1.165, 5.820/5.753, Polars 0.048, DuckDB 0.080.
- 1,658 N/A-borough trips is in `metrics.json` (`"Borough": "N/A" … "trips": 1658`) and README L139. 295 EWR trips is in `metrics.json`.
- 157 MB CSV (157,380,585 B), 43 MB parquet, 31 partitions, versions, 16 cores, and arm64 all match `evaluation_metadata.json`. The ~26 s CI time and 39 cells match README L12-15.
- Speedup caption: `speedup_vs_sqlite` max 1984.9. pandas-vs-sqlite runs 0.009-0.20x, which supports "0.01-0.2x, or 5-110x slower".

### Untraceable (no committed real-data source)

| Line | Claim | Status |
|---|---|---|
| L102-104 | "quiet at 4 a.m., has two evening peaks, and is busier on business days than weekends" | Still present. The only source is the synthetic generator docstring (`synthetic.py:62`), and the generator draws `hour` uniformly (`synthetic.py:69`). |
| L106 | "typical fare near `$16.`" | Still present. Also in diagram `11-data-engineering-3.ts` L25. |
| L106-107 | "airport and late-night rides stretches past `$200.`" | Still present. Also in diagram L31. |
| L107-108 | "fares are negative because they are real fare adjustments" | Still present. No count and no source. |
| L129 | "clear daily rush-hour patterns and a long tail of high fares" | New and escalated. Even the synthetic docstring says "evening peaks", not rush hour. |
| L241-242, L310 | "The 295-trip EWR borough sum sat within one `ulp` of a rounding cliff" | Still present. DESIGN L79 describes the ulp case generically and does not tie it to EWR. |
| L193-194 | "object-heavy group-by and window paths" | Still present (see §4). |

### Contradicted or mislabelled

| Line | Claim | Evidence | Status |
|---|---|---|---|
| L200 | "`sqlite`'s join is its best cell at `3.65` s" | sqlite's fastest cell is filter at 1.947 s. Its best ratio to pandas is read_csv at 0.20x. | Still present |
| L291 | "using 2–3× less memory" | pandas/Polars runs 1.09x (write_parquet) to 3.2x. pandas/DuckDB runs 0.91x (DuckDB uses more on write_parquet) to 4.3x (join). | Still present (moved from old L306) |
| L441 | memory_lollipop caption: "Polars and DuckDB stay near 178-529 MB" | DuckDB peaks at 633 MB on write_parquet. The article's own L278 and L356 say 178-633. | Still present |
| L187-188 | "conversions take 1.9-5.9 s per task" | That is sqlite's total task time (load plus query). Conversion is not timed separately. L277 "due to file conversion" repeats the attribution more softly. | Still present |
| L134-135 | pandas CSV via PyArrow | `engines.py:44` | Still present |
| L31 | "sort distinct values" | DESIGN L50 | Still present |
| L280 | (round 1: cold CSV "the one place interpreter startup visibly registers") | Rewritten to "Cold reads barely shift". This holds in absolute seconds. In relative terms pandas parquet shifts +64% (0.072 vs 0.044), which the sentence leaves out, but it is no longer contradicted. | Fixed |

**Untraceable numbers: 3** ("4 a.m.", "$16", "$200"). **Contradicted or mislabelled numbers: 4** (L187 "1.9-5.9 s" as conversion, L200 "3.65 s" as best cell, L291 "2–3×", L441 "178-529 MB"). There are also 5 non-numeric untraceable claims: L102-104, L107-108, L129, L193-194, and L241/L310.

## 6. Roadmap cards (6)

| L | Title | Verb-first | Detail chars | Status | Reality check |
|---|---|---|---|---|---|
| 400-401 | Gate every timing on identical rows | yes | 60 | shipped | True: 39/39 cells (README L12, Record L360). The detail still omits "39 of 39". |
| 403-404 | Keep timings honest with untraced medians | yes | 65 | shipped | True (`evaluation_metadata.json` protocol_statement). |
| 406-407 | Catch dropped rows with parity checks | yes | 63 | shipped | True: 1,658 in `metrics.json`, and the fix plus regression test is in README L140-141. |
| 409-410 | Show the fast two scale sub-linearly | yes, garbled | 74 | shipped | True (`results.md` slopes). The title still parses as a noun phrase, and the detail still has no numbers. |
| 412-413 | Benchmark real trips at 10M rows | yes | 50 | next | Reasonable, but it does not say how. One month has 2.96M rows, so this needs about 4 months stacked. |

The README's deferred items (L162-163, L215: out-of-core cold-cache track, further engines) still have no `next` card.

## 7. Consistency with the gold template (7)

- Improved: the Background structure (bold hook, three bold-led steps, a "Next, …" link, then `In plain terms`) now matches gold L5-20. `In plain terms` is present in all 7 sections.
- Still different: the gold Objectives opens with a bold thesis ("**Set four targets before any tuning begins.**"). Article 11's Objectives opens with "The protocol diagram below shows…" (L25).
- Still different: gold transitions are full sentences ("next, we trace how the corpus and test splits were built"). Article 11 still uses "X; next, the <noun phrase>" at L60, L91, L126, and L288. The two new ones (L203-205, L256-258) name chart ids such as `speedup_overview` in reader prose, which gold never does.
- Still different: gold Evaluation names its own weakness in a bold question. Article 11 does not.
- Still different: gold roadmap details keep their numbers ("30/30 … 104/120"). Article 11's do not.

## Round-1 finding status

| # | Round-1 finding | R2 line | Status |
|---|---|---|---|
| 1 | Transition misroute: parity catches → Training | L126-127 | STILL PRESENT |
| 2 | Evaluation sizing frame unresolved | L219-223 | STILL PRESENT |
| 3 | Results/Conclusions repeat headline numbers; Results restates Training | L282-286 vs L178-184 | STILL PRESENT (worse: the new table at L207-212 adds another repeat) |
| 4 | Formulaic, verbless transitions | L19, L60, L91, L126, L203, L256, L288 | PARTLY FIXED (Background's is fine; two new ones are clumsier) |
| 5 | Parity catch absent from short_version and Background | L3, L7-21 | STILL PRESENT |
| 6 | Ten "Read/Follow/Use the…" openers | 10 sites | STILL PRESENT |
| 7 | EDA `In plain terms` narrates the diagram | L129 | FIXED (it now states a finding, but the finding is untraceable; see #16) |
| 8 | "ladder" undefined | L188 | STILL PRESENT |
| 9 | short_version run-on and trailing fragment | L3 | STILL PRESENT |
| 10 | Register mismatch ("ulp", "bound paths") | L149, L241 | STILL PRESENT |
| 11 | "tie at 529-633 MB" | L278 | FIXED |
| 12 | "7-44x" applied to both engines | L304, L396 | FIXED |
| 13 | pandas reads CSV with PyArrow | L134-135 | STILL PRESENT |
| 14 | "sort distinct values" | L31 | STILL PRESENT |
| 15 | "object-heavy" group-by | L193-194 | STILL PRESENT |
| 16 | Daily pattern from the synthetic docstring | L102-104 (+L129 "rush-hour") | STILL PRESENT (escalated) |
| 17 | "$16" | L106 | STILL PRESENT |
| 18 | "$200" with airport and late-night attribution | L106-107 | STILL PRESENT |
| 19 | Negative fares are "real fare adjustments" | L107-108 | STILL PRESENT |
| 20 | EWR ulp attribution | L241-242, L310 | STILL PRESENT |
| 21 | sqlite join "best cell at 3.65 s" | L200 | STILL PRESENT |
| 22 | Cold CSV "the one place startup registers" | L280 | FIXED |
| 23 | "2-3x memory headroom" | L291 | STILL PRESENT |
| 24 | memory_lollipop caption "178-529 MB" | L441 | STILL PRESENT |
| 25 | "conversions take 1.9-5.9 s" | L187-188 | STILL PRESENT |
| 26 | Roadmap card 1: restore "39 of 39" | L401 | STILL PRESENT |
| 27 | Roadmap card 4: garbled title, slopes lost | L409-410 | STILL PRESENT |
| 28 | Roadmap card 5: say how to reach 10M real rows | L413 | STILL PRESENT |
| 29 | Missing `next` card for deferred cold-cache track | roadmap | STILL PRESENT |
| 30 | Evaluation lacks gold-style named weakness | L219-268 | STILL PRESENT |
| 31 | Diagram `11-data-engineering-3.ts` EDA labels | diagram L19-31 | STILL PRESENT |

Totals: 4 fixed, 1 partly fixed, **26 still present**.

## Top 5 remaining fixes (by severity)

1. **L102-110, L129, and diagram `11-data-engineering-3.ts` L19-31: source or cut the EDA claims.** The phrases are "quiet at 4 a.m. … two evening peaks … busier on business days", "near `$16.`", "past `$200.`", "real fare adjustments", and the new "clear daily rush-hour patterns". Either commit a real-data EDA artifact to `reports/` (hourly and weekday counts, fare quantiles, negative-fare count) and cite it, or replace the paragraph with traceable facts. Traceable facts include: 35 pickup dates (31 plus out-of-month dates such as 2002-12-31 and 2009-01-01, per the `metrics.json` groupby result), ~95,600 trips per day, and the filter's 168,468 trips with fare > $50 and > 10 miles. Then regenerate the diagram.
2. **L291 and L441: memory claims contradict `results.md`.** Change "using 2–3× less memory" to "using 2–4× less memory on compute tasks". Change the caption's "Polars and DuckDB stay near 178-529 MB" to "Polars 200-529 MB, DuckDB 178-633 MB".
3. **L200: "`sqlite`'s join is its best cell at `3.65` s" is false.** Replace it with: "`sqlite`'s fastest cell is the filter at `1.95 s`, and its `CSV` read comes closest to pandas at 0.2×; on every task the per-task import dominates."
4. **L186-188 (and the L277 attribution): mislabelled cost and undefined jargon.** Replace with "`sqlite` returns correct answers, but each task, load included, takes 1.9-5.9 s, `40.55 s` in total." Delete "for the ladder".
5. **Technical misdescriptions and routing: L134-135, L31, L193-194, L241/L310, L126-127.**
   - L134-135: change to "`pandas` reads parquet through `PyArrow` and `CSV` through its default parser."
   - L31: change "sort distinct values" to "rank the top 10 pickup zones by fare".
   - L193-194: drop "object-heavy".
   - L241 and L310: either cite a source tying the ulp case to EWR, or generalize to "a borough sum can sit within one ulp of a rounding cliff".
   - L126-127: point the transition at the speedup figure only, or link the parity catches to Evaluation.

Next after these: restore numbers in roadmap cards 1 and 4 and retitle card 4 (for example "Measure scaling from 1M to 10M rows" / "Polars and DuckDB slopes 0.31-0.76; pandas and sqlite ~1.0."). Add a cold-cache `next` card. Move the `$16.` and `$200.` full stops outside their backticks. Cut the L282-286 restatement.

## Ready to publish?

**No.** The core benchmark tables are exact, but the round-2 edit left every round-1 truthfulness defect except the cold-read inversion in place, and it added a new unsourced claim ("rush-hour"). A reader who checks the article against `results.md` will still find:

- three contradicted numbers: the sqlite best cell (L200), the memory ratio (L291), and the caption's DuckDB range (L441);
- one mislabelled range: "conversions" at L187;
- an EDA section that describes the synthetic generator's design intent as if it were real January 2024 data.
