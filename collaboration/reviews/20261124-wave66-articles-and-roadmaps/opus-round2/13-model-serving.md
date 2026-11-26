# Review round 2: 13-model-serving story.yaml

- Target: `projects/13-model-serving/story.yaml` at HEAD (last touched in `e69bba84`)
- Gold template: `projects/01-rag-agent/story.yaml`
- Prior round: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/13-model-serving.md`
- Evidence re-checked: `reports/metrics.json` (all serving cells re-extracted), `reports/docker_slim.json`, `reports/docker_run.json`, `reports/train_run.json`, `README.md`, `DESIGN.md`, `Dockerfile.slim`, `src/model_serving/artifacts.py`, `projects/12-tabular-ml-lifecycle/data/dataset_contract.json`
- Reviewer: Claude (Opus), read-only. Line numbers refer to the current HEAD file.

## Summary

The `e69bba84` round rewrote the background section into a three-step list and turned the plain-terms cards into outcome sentences. It also removed the untraceable "~15%". None of the round-1 numeric defects in the evaluation, results, and table sections were fixed. The batch rows are still ONNX means labelled as p50. "Three orders inside the gate" is still there, and so are "ties elsewhere", "within noise at every cell", and "about 2 ms". The round also added a new error: L132 now says parity is "less than one-millionth of a bike". On the rentals scale the measured gap is 1.24e-04 bikes, which is about 170 times larger than that.

## Grades

| # | Dimension | R1 | R2 |
|---|---|---|---|
| 1 | Structure and article logic | 7 | 7 |
| 2 | Engagement and human-like narrative | 6 | 6 |
| 3 | Language quality | 5 | 5 |
| 4 | Technical depth | 8 | 7 |
| 5 | Truthfulness | 6 | 5 |
| 6 | Roadmap cards | 7 | 7 |
| 7 | Consistency with gold template | 7 | 7 |
| | **Overall** | **6.5** | **6.3** |

Technical depth drops one point. The two round-1 gaps (no tolerance formula, no hypothesis for the c16 sag) are still open, and the new plain-terms card at L132 confuses the standardized output space with the rentals scale.

## 1. Structure and article logic: 7

- Better: the background (L19–L33) now answers its own question with three steps: rebuild and match, serve and probe, measure load. This partly resolves the round-1 "question never answered" finding.
- Still present: every transition uses one template. L31 "Next, …", L61 "The gates need a rebuilt champion; next, …", L97 "The rebuild is verified; next, …", L129 "The grid passes parity; next, …", L185 "The service is warmed; next, …", L223 "The protocol is paired; next, …", L279 "The ledger stands; next, …". Each one is a standalone one- or two-line paragraph. Gold folds the `next,` hook into a sentence that describes what the reader will see (gold L36, L137).
- Still present: L184 (the excerpt attribution) and L185 (the transition) have no blank line between them, so they render as one paragraph.
- Still present: Results (L230–L243) says it restates "the first four bullets … shown above". Conclusions then restates the same numbers a third time (L288–L293, L323–L340). The image-size and cost story appears in L245–L266, L338–L340, and L374–L380.

## 2. Engagement and human-like narrative: 6

The concrete engineering passages are still the best part: the chown layer (L259–L261), "CUDA libraries it never loads" (L312–L314), and the c16 sag (L238). The plain-terms cards now read as outcomes, which helps.

The glossary density is unchanged and in places has grown. Definitions in the body text: seed (L42), ONNX, parity, native torch, max-abs, grid (L44–L49, five definitions in six lines), validation MAE (L72), cyclical features, lags, embedding (L76–L80), checksum (L86), r (L88), request schema (L93), scaler (L108), ONNX Runtime (L111), float32 (L114), kernel-order noise (L116), HTTP 422 (L126), state_dict, JSON, opset, dynamic batch (L138–L142), Pydantic (L149), readiness (L151), healthcheck (L157), inference (L162), async driver (L192), concurrency (L196), backend (L58), latency, p50, p95 (L202–L203), throughput, knee (L204–L206), "CPU, or central processing unit" (L207–L208), rows/s (L213), RSS (L246), venv (L248), shebang (L260), smoke test (L256), TLS and authentication (L272–L274), p99 (L319), SHA-256 (L347), lockfile and non-root (L359–L360). That is more than 40 inline definitions. An ML-engineering reader does not need "CPU, or central processing unit", and the definitions break up the argument.

## 3. Language quality: 5

- Objectives (L37–L49) is the worst stretch: "First reproduce the champion. Next verify export parity. Then measure serving. Mean absolute error (`MAE`) is … Test `MAE` uses … A seed is …" These are telegraphic fragments mixed with glossary entries.
- L238–L240 "No dynamic batching is enabled to explain that shape" reads as if dynamic batching would explain the sag. The intended meaning seems to be "the sag is not a batching artifact". Rewrite it.
- L259 "The measured `6.5 GB` bar is the fixed build" is still unclear without the 12.8 GB counterfactual, which `DESIGN.md:54` records and the article omits.
- L276–L277 "the parity gate supports dropping the framework safely" is still vague.
- L372–L373 "a torch-free native image is future work" contradicts itself, because native means torch. L376–L377 says the real point: a CPU-only torch native image. Use that wording.
- L339 "$1.15e-05 per 1k predictions": a dollar sign on scientific notation reads poorly. Use `$0.0000115` to match L263.
- "read as scheduling noise" still repeats at L220, L311, and L420, with "floating-point noise" at L124.
- L100 "25.43 bikes/hour accuracy": MAE is an error, not an accuracy. Say "a 25.43 bikes/hour average error".

## 4. Technical depth: 7

Strengths are unchanged: paired byte-identical payloads, 20 warm-up requests excluded, median of 3 repeats with min/max bands, nearest-rank percentiles, opset 17 with a dynamic batch axis, readiness tied to a real warm-up inference, `COPY --chown` instead of `chown -R`, and the pinned slim dependency set.

Open gaps:

- The tolerance formula is still only described in prose (L113–L118). Code: `limit = tolerance + 1e-5 * max(1, max|native_scaled|)` (`artifacts.py:142`). One inline formula would replace five sentences.
- The output space is still not explained where it matters. L112 says "raw network output", and L123–L124 gives the rentals-scale gap of 1.2e-04, which is numerically larger than the 1e-4 gate, without saying that the gate is applied in standardized space. Only L337 says "standardized network output". `metrics.json` `parity.space` gives the exact relation (end-to-end = scaled × y_std).
- The c16 throughput sag (470 req/s, below both c4 and c64) still has no hypothesis beyond "shared CPU", for example single-worker event-loop contention or client/server CPU contention.

## 5. Truthfulness: 5

Traceable (re-verified): 25.43163249606178 with abs diff 0.0 and tolerance 0.05; parity 7.15e-07 scaled and 1.24e-04 on the rentals scale, n=512, tolerance 1e-4, opset 17; r=0.9873; 15 selected fields; 300 requests per cell, 60 per batch size, 20 warm-up excluded, 3 repeats, 25.1 s bench; the ONNX concurrency rows in L325–L328 (p50/p95/p99/throughput); batch throughputs 513 / 5,104 / 18,674 / 57,451 rows/s; ~56k rows/s at b128 (native 55.8k, ONNX 57.5k); 13.8% at c64 (714.9/628.3); concurrency p50 gap ≤4% (c4 2.5%, c16 3.6%, c64 3.6%); 4,320 requests with zero errors; RSS 298/318 MB; image 6,466 MB (base 145, venv 6,192, model 1); slim 291 MB, 22.2×, venv 149 MB, six pins plus portfolio-core `--no-deps` (`Dockerfile.slim:30–37`); cost 1.15e-05 at 65 W and $0.30/kWh on the c16 basis; train runtime 2.4 s ("seconds", L137); compose smoke passed; slim smoke passed.

Resolved on re-check: the data_note "identical frame hash" (L6–L7) is traceable. `train_run.json:175` `frame_sha256` `42adb7aa…` equals `projects/12-tabular-ml-lifecycle/data/dataset_contract.json:7` `checksum_sha256`.

Untraceable, contradicted, or mis-scoped:

| # | Line | Claim | Evidence | Verdict |
|---|---|---|---|---|
| 1 | L113 | "three orders inside the 1e-4 gate" | 1e-4 / 7.15e-07 ≈ 140×, about 2.1 orders | **Contradicted** (round 1, unfixed) |
| 2 | L132 | "within 0.000001 (less than one-millionth of a bike)" | 7.15e-07 is in standardized units; on the rentals (bike) scale the gap is 1.24e-04, about 1/8,000 of a bike | **Contradicted** (new this round) |
| 3 | L329–L332 | batch rows under `p50`: 65.9 / 53.0 / 56.4 / 73.1 ms | These are ONNX `mean_s`. ONNX batch p50 values are 65.1 / 48.5 / 51.0 / 65.3 ms | **Contradicted** (round 1, unfixed) |
| 4 | L204, L282, L415 | single-request p50 "about 2 ms" / "~2 ms" | 1.6 ms on both backends, and the article says 1.6 ms elsewhere | **Inconsistent** (unfixed) |
| 5 | L3, L29, L226 | "p95 2.0 ms" | Native p95 is 2.0 ms; ONNX is 1.9 ms, and the table at L325 shows 1.9 ms | **Mixed-backend** (unfixed) |
| 6 | L237 | "peak near 970 req/s at concurrency 4 on both backends" | Native is 932.5 | **Contradicted** for native (unfixed) |
| 7 | L218, L334, L219, L310 | "ties elsewhere"; "within noise at every cell"; "p50 medians differ by at most 4%"; "13.8% only at the c64 throughput cell" | Batch throughput: ONNX +15.4% at b8 and +11.2% at b32, native +12.5% at b1. Batch p50: b1 53.0 vs 65.1 ms, b8 58.6 vs 48.5 ms | **Overstated**: true only for concurrency cells (unfixed) |
| 8 | L3–L4, L249–L250 | venv is "mostly torch and unused CUDA libraries" | No per-package breakdown is committed. It is inferred from the slim venv (149 MB vs 6,192 MB) | **Inferred, not measured** (unfixed) |
| 9 | L208 | at 64 clients "p95 about 0.21 s" | ONNX 0.210 s; native 0.249 s | **Single-backend figure stated generally** |

There are 9 untraceable, contradicted, or mis-scoped numeric claims. There is also one semantic mislabel (L100, "accuracy" for MAE).

## 6. Roadmap cards: 7

- Titles all start with a verb. Details are all 90 characters or fewer (longest is L399 at about 66).
- Shipped status checked against the repo. Card 1: `metrics.json` reproduction and parity both `passed: true`. Card 2: zero errors in all cells. Card 3: the `--backend` flag and the readiness gate are in `service/model.py` and `app.py`. Card 4: `Dockerfile.slim` and `docker_slim.json` `smoke.passed: true`. All four "shipped" statuses match reality.
- Still present: L387 "sits orders inside the gate" and L396 "lands at a fraction of the size" are vague where gold keeps numbers (gold L281). Suggested details: "Parity max-abs 7.2e-07 on 512 probe rows vs a 1e-4 gate." and "Slim ONNX image 291 MB, 22.2x smaller than 6.5 GB; smoke-passed."
- Still present: the next card (L397–L399) has no `Gate:`, unlike gold L284. Suggested: "Gate: paired harness rerun on the target host before any capacity quote."

## 7. Consistency with gold template: 7

- Matches gold: the label set, `In plain terms` in all 8 sections, anchor transitions, Conclusions sub-structure, figures attached to evaluation and results, and long unwrapped bullet lines (gold also has them, so the round-1 wrap note is moot).
- Plain-terms cards now state outcomes like gold's. L226 and L282 still mainly list numbers, and L282 repeats the "~2 ms" inconsistency.
- Gold puts the transition inside a substantive sentence (gold L36, L137). Here each transition is still a separate templated line.

## Round-1 finding status

| # | Round-1 finding | Status | Current evidence |
|---|---|---|---|
| 1 | Templated "X is Y; next, Z" transitions | STILL PRESENT | L61, L97, L129, L185, L223, L279 |
| 2 | Attribution line runs into the transition | STILL PRESENT | L184–L185 |
| 3 | Results/Conclusions repetition of image and cost | STILL PRESENT | L230–L266 vs L288–L293, L323–L340, L374–L380 |
| 4 | Background question never answered | PARTLY FIXED | three-step list L25–L29; no direct "it takes…" statement |
| 5 | Inline glossary overload | STILL PRESENT | 40+ definitions; see §2 |
| 6 | Choppy opening and unwrapped L16 | PARTLY FIXED | opening rewritten; the same stacking moved to L37–L49; wrap is moot per gold |
| 7 | "reads as noise" repetition | STILL PRESENT | L220, L311, L420 |
| 8 | Plain-terms cards repeat ledger numbers | PARTLY FIXED | L33, L100, L188 fixed; L226 and L282 still number lists |
| 9 | "The diagram…" opens cards | FIXED (cards) | no card starts that way; the body is still diagram-led (L54, L75, L92, L288, L300, L318) |
| 10 | Awkward fragments (6.5 GB fixed build; "supports dropping the framework"; ~15%) | PARTLY FIXED | ~15% gone; L259 and L276–L277 remain |
| 11 | Tolerance formula not given | STILL PRESENT | L113–L118 |
| 12 | Standardized-space clause for 1.2e-04 | PARTLY FIXED | L337 says standardized; L112 and L123–L124 still do not; L132 now wrong |
| 13 | No hypothesis for the c16 sag | STILL PRESENT | L207, L238 |
| 14 | "three orders inside the gate" | STILL PRESENT | L113 |
| 15 | Batch "p50" column holds means | STILL PRESENT | L329–L332 |
| 16 | "~15% delta" untraceable | FIXED | removed |
| 17 | "ties elsewhere" | STILL PRESENT | L218 |
| 18 | "within noise at every cell" / unscoped 4% | STILL PRESENT | L334, L219, L241, L310 |
| 19 | "peak near 970 on both backends" | STILL PRESENT | L237 |
| 20 | "about 2 ms" vs 1.6 ms | STILL PRESENT | L204, L282, L415 |
| 21 | Mixed-backend p95 2.0 ms | STILL PRESENT | L3, L29, L226 |
| 22 | venv composition inferred, not measured | STILL PRESENT | L3–L4, L249–L250 |
| 23 | Frame hash match with 12 not verifiable | RESOLVED ON RE-CHECK | matches `12-tabular-ml-lifecycle/data/dataset_contract.json:7` |
| 24 | Roadmap details lost numbers; card 3 weaker; card 5 has no gate | STILL PRESENT | L387, L393, L396, L399 |
| 25 | Transitions not folded into paragraphs (gold) | STILL PRESENT | as in #1 |

Totals: 17 still present, 5 partly fixed, 3 fixed or resolved.

## Top 5 remaining fixes (by severity)

1. **L329–L332: mislabeled batch p50.** Replace 65.9 / 53.0 / 56.4 / 73.1 with the ONNX p50 values 65.1 / 48.5 / 51.0 / 65.3 ms, or rename the column. This is a wrong number in the expert reference table.
2. **L132: "less than one-millionth of a bike".** Change it to "about one ten-thousandth of a bike (1.2e-04)". Also change "match training" to "match the native model". At L112 and L123–L124, add that the 1e-4 gate is applied to standardized output, so the rentals-scale gap = scaled gap × y_std. Change L113 "three orders" to "about 140×".
3. **L218, L219, L310, L334: unscoped parity-of-backends claims.** Limit "ties", "at most 4%", and "within noise at every cell" to the four concurrency cells. Then state the batch spread: ONNX +15% at b8 and +11% at b32, native +12% at b1.
4. **L204, L282, L415 "~2 ms"; L3, L29, L226 "p95 2.0 ms"; L237 "970 on both"; L208 "0.21 s".** Pick one backend (ONNX, to match the table) or give both values, and say 1.6 ms everywhere. At L237, say "933 native / 970 ONNX" without "on both".
5. **Narrative and roadmap polish.** Cut at least half the inline definitions (start with L42, L86, L114, L139, L157, L162, L207–L208, L347). Vary and fold the transitions (L61–L279), and add the blank line at L184/L185. Mark the venv composition as inferred from the slim delta (L3–L4, L249–L250). Restore the numbers in roadmap L387 and L396, and add a `Gate:` to L399.

## Ready to publish?

**No.** The expert table (L329–L332) still contains mislabeled values. This round added a new factual error in a plain-terms card (L132). Five round-1 numeric defects remain (L113, L204, L218, L237, L334). Fixes 1–4 are small text edits against `metrics.json` and would bring truthfulness up to publishable.
