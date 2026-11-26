# Review round 3: 13-model-serving story.yaml

- Target: `projects/13-model-serving/story.yaml`, working tree on `wave8-articles-truthfulness-2026-11-25` (HEAD `c05accd0` plus uncommitted Wave 8 edits)
- Gold template: `projects/01-rag-agent/story.yaml`
- Prior round: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus-round2/13-model-serving.md`
- Evidence re-checked (all tracked): `reports/metrics.json` (every serving cell re-extracted, p50 ratios recomputed), `reports/docker_slim.json`, `reports/train_run.json`, `reports/results.md`, `reports/figures/backend_comparison_slope.json`, `README.md`, `DESIGN.md`, `Dockerfile.slim`, `params.yaml`, `src/model_serving/artifacts.py`
- Reviewer: Claude (Opus), read-only. Line numbers refer to the working-tree file.

## Summary

Wave 8 fixed almost everything round 2 asked for. The batch table now holds real ONNX p50 values. The parity passage gives the gate formula, the standardized-space caveat, and the correct "about 140×" ratio. The "one-millionth of a bike" card is gone. Every "~2 ms", mixed-backend p95, "970 on both", "ties elsewhere" and "within noise at every cell" claim is gone or scoped. The inline glossary is cut to a handful of useful definitions, the transitions are varied and folded into sentences, and the roadmap cards carry numbers and a `Gate:`.

One new numeric error came with the rewrite. The concurrency p50 gap is now given as "at most 3.6%" (L189, L213, L285), but the c4 cell differs by 4.0% (native base) or 4.2% (ONNX base). The old "4%" was correct. Round 2 mis-stated the c4 gap as 2.5% and that error propagated; this review corrects it. The same mistake reaches the slope caption (L395, "0.97–1.04"; the c4 ratio is 0.960). A second, smaller issue: L211–L212 now calls CPU contention "a hypothesis, not an isolated cause", but L177, L207, L345 and the L391 caption still state it as fact.

## Grades

| # | Dimension | R1 | R2 | R3 |
|---|---|---|---|---|
| 1 | Structure and article logic | 7 | 7 | 8 |
| 2 | Engagement and human-like narrative | 6 | 6 | 7 |
| 3 | Language quality | 5 | 5 | 7 |
| 4 | Technical depth | 8 | 7 | 8 |
| 5 | Truthfulness | 6 | 5 | 7 |
| 6 | Roadmap cards | 7 | 7 | 9 |
| 7 | Consistency with gold template | 7 | 7 | 8 |
| | **Overall** | **6.5** | **6.3** | **7.7** |

## 1. Structure and article logic: 8

- Fixed: transitions are now part of a sentence that says what the next section shows (L53–L54, L82–L83, L109–L110, L160–L161, L195–L196, L254–L255). Only L31 keeps a bare "Next, …", and that is acceptable in a background lead.
- Fixed: the excerpt attribution (L158) and the transition (L160) are now separate paragraphs.
- Still present: the image and cost story is told three times. Results covers it at L218–L240. Conclusions repeats it in the summary (L264–L268), the exact-numbers prose (L309–L316), and Limits (L349–L355). Wave 8 adds the 12.8 GB counterfactual at L232–L233, which is useful, but Lesson 4 (L287–L289) then tells the same chown story again.
- Still present: the background question at L19 is answered only through the three-step list (L25–L29), with no direct "It takes…" sentence. This is minor.

## 2. Engagement and human-like narrative: 7

The cut from 40+ inline definitions to roughly six (MAE L38–L39, RSS L219, TLS and auth L246–L247, p99 L294, lockfile and non-root L334–L335) is the biggest improvement this round. The argument now reads continuously. The concrete engineering details still carry the piece: the chown layer and 12.8 GB counterfactual (L232–L235), CUDA libraries that are never loaded (L224, L287–L288), and the c16 sag with an explicit hypothesis (L208–L212). The plain-terms cards at L56, L85 and L163 read as outcomes. L198 and L257 are still mostly number lists.

## 3. Language quality: 7

- Fixed: the objectives stretch (L37–L41) is now three full sentences.
- Fixed: "No dynamic batching is enabled to explain that shape" now reads "the sag is not a batching artifact" (L209–L211). "Supports dropping the framework safely" now reads "the enforced prediction-parity check covers the exported model" (L250–L252). "Torch-free native image" is now "CPU-only torch native image" (L348). The cost is written `$0.0000115` (L315). MAE is called an error, not an accuracy (L85).
- New: L90–L91 is telegraphic: "They span every hour and weather situations `1`–`4`. Cyclical terms lie in `[-1, 1]`. Lags reach `800`." Merge into one sentence, for example: "They span every hour, weather situations 1–4, cyclical terms in [-1, 1], and lags up to 800."
- L127 and L183 are unwrapped long lines that sit among wrapped prose. This is cosmetic.
- L281–L282: "too tight on ill-scaled outputs or too loose on good ones". Adding a relative term only loosens the gate, so it cannot fix "too loose". Drop the second half, or reword it as "an absolute gate sized for well-scaled outputs is too tight on large ones".

## 4. Technical depth: 8

All three round-2 gaps are closed:

- The tolerance formula is given inline (L98) and matches `artifacts.py:142`.
- The standardized-space relation is explicit (L96, L104–L105). The ×y_std arithmetic checks out: 1.237e-04 / 7.15e-07 ≈ 173, consistent with `parity.space`.
- The c16 sag has a hypothesis, and it is labeled as one (L211–L212).

Remaining depth issues:

- The hypothesis framing is applied unevenly. See Truthfulness row 3.
- The batch caption L392 calls per-request latency "queue-dominated", but the body (L185) says "the chart does not isolate queueing from computation".

## 5. Truthfulness: 7

Traceable (re-verified against tracked files):

- MAE 25.43163249606178, abs diff 0.0, tolerance 0.05.
- Parity 7.15e-07 scaled and 1.2367e-04 on the rentals scale, n=512, tolerance 1e-4, opset 17; the gate formula; "about 140×" (1e-4 / 7.15e-07 = 139.9).
- r = 0.9873; 15 selected fields; probe-grid ranges (weathersit 1–4, lags uniform 0–800, `artifacts.py:97–108`); 8-week test window (`params.yaml:9`).
- Training 2.424 s (`train_run.json:196`).
- Load protocol: 300 requests per concurrency cell, 60 per batch size, 20 warm-up requests excluded, 3 repeats; benchmark stage 25.137 s.
- c1 p50 1.63/1.58 ms; p95 1.99/1.87 ms (2.0/1.9); p99 2.22/2.20 ms.
- c4 throughput 932.5/969.9 req/s (933/970, knee ~950); "p95 under 6 ms through c4" (max 5.08 ms).
- c64 p50 65.4/63.1 ms; c64 p95 0.249/0.210 s.
- All ONNX table rows L300–L307, including the corrected batch p50 values 65.1/48.5/51.0/65.3 ms.
- Batch throughput at b128: 55.8k native, 57.5k ONNX.
- Backend gaps: c64 throughput 13.8% (714.9/628.3); b8 +15.4% (5104.4/4424.5); b32 +11.2% (18673.9/16796.6); b1 native +12.5% (577.2/513.1).
- 4,320 requests per backend (3×(4×300 + 4×60)), zero errors.
- RSS 298.4/317.8 MB.
- Full image 6,466 MB (145 base, 6,192 venv, 1 model); slim image 291 MB, 22.2×, 149 MB venv, smoke passed; six pins plus `--no-deps` portfolio-core (`Dockerfile.slim:30–37`); 12.8 GB pre-fix (`DESIGN.md:54`).
- Cost 1.152e-05 at 65 W and $0.30/kWh on the c16 basis; compose smoke passed; frame sha256 matches project 12's contract.

Untraceable, contradicted, or mis-scoped claims:

| # | Line | Claim | Evidence | Verdict |
|---|---|---|---|---|
| 1 | L189, L213, L285 | concurrency `p50` "differs by at most `3.6%`" | p50 ONNX/native: c1 0.972, c4 **0.960**, c16 1.035, c64 0.965. The c4 gap is 4.0% of native and 4.2% of ONNX | **Contradicted** (new in Wave 8; the old "4%" was right) |
| 2 | L395 | "four concurrency p50 ratios span 0.97–1.04" | c4 ratio is 3.857/4.019 = 0.960 (`backend_comparison_slope.json`) | **Contradicted** (new) |
| 3 | L177, L207, L345, L391 | "driver and service contend for one CPU"; "where the shared CPU saturates"; "High-concurrency cells measure contention"; "curves bend where one shared CPU saturates" | L211–L212 says contention is "a hypothesis, not an isolated cause"; nothing measured CPU utilisation | **Mis-scoped**: stated as fact in four places, as a hypothesis in one |
| 4 | L392 | "queue-dominated per-request latency" | L185: "does not isolate queueing from computation" | **Mis-scoped** (pre-existing, not flagged in round 2) |
| 5 | L207 | "`p50` about `63 ms` at 64 clients" | ONNX 63.1 ms; native 65.4 ms (L178 gives both) | **Single-backend figure stated generally** (minor) |
| 6 | L384 | key concept: "Measure its venv, torch, and unused CUDA components" | Only the base, venv and model were measured; torch and CUDA sizes are inferred from the slim delta (as L222–L224 now correctly says) | **Residual of round-2 #22** |

Count: 3 numeric claims are untraceable or contradicted (rows 1, 2, 5). There are also 3 mis-scoped qualitative claims (rows 3, 4, 6).

## 6. Roadmap cards: 9

- Titles all start with a verb. Details are all 90 characters or fewer; the longest (L374) is 75.
- Every shipped status matches the repo. Card 1: reproduction and parity both `passed: true`. Card 2: zero errors in all 16 cells per backend. Card 3: the `--backend` flag and the readiness gate are in `service/model.py` and `app.py`. Card 4: `Dockerfile.slim` exists and `docker_slim.json` has `smoke.passed: true`, 291 MB, 22.2×.
- Fixed: card 1 (L362) and card 4 (L371) now carry numbers. The next card (L374) has a `Gate:`, matching gold L284.
- Nit: L371 uses "22.2x" while the body uses "22.2×". Gold uses plain text, so this is fine.

## 7. Consistency with gold template: 8

- Matches gold: the section set, a plain-terms card in all 8 sections, anchor transitions folded into sentences, the Conclusions sub-structure (summary, lessons, exact numbers, protocol, limits), figures attached to evaluation and results, and a `Gate:` on the next card.
- Remaining gaps: the L198 and L257 plain-terms cards are number lists, where gold's cards state outcomes. Results and Conclusions overlap more than gold's do.

## Round-2 finding status

| # | Round-2 finding | Status | Current evidence |
|---|---|---|---|
| 1 | Templated "X is Y; next, Z" transitions | FIXED | L53, L82, L109, L160, L195, L254 vary and fold; only L31 keeps "Next," |
| 2 | Attribution runs into transition | FIXED | blank line L159 |
| 3 | Results/Conclusions repeat image and cost | STILL PRESENT | L218–L240 vs L264–L268, L287–L289, L309–L316, L349–L355 |
| 4 | Background question never answered directly | PARTLY FIXED | three-step list L25–L29 (unchanged) |
| 5 | Inline glossary overload | FIXED | about 6 definitions remain |
| 6 | Choppy opening / fragment stacking | PARTLY FIXED | L37–L41 fixed; new fragments at L90–L91 |
| 7 | "reads as noise" repetition | FIXED | removed |
| 8 | Plain-terms cards repeat ledger numbers | PARTLY FIXED | L198, L257 still number lists |
| 9 | "The diagram…" leads | FIXED (cards) | body still diagram-led, as gold is |
| 10 | Awkward fragments (6.5 GB fixed build; "dropping the framework") | FIXED | L232–L235, L250–L252 |
| 11 | Tolerance formula not given | FIXED | L98 |
| 12 | Standardized-space clause missing | FIXED | L96, L104–L105 |
| 13 | No hypothesis for the c16 sag | FIXED | L211–L212 (but see new error N3) |
| 14 | "three orders inside the gate" | FIXED | L96 "about 140×" |
| 15 | Batch "p50" column held means | FIXED | L304–L307 = ONNX p50 |
| 16 | "~15%" untraceable | FIXED | — |
| 17 | "ties elsewhere" | FIXED | L190–L193 lists batch gaps |
| 18 | "within noise at every cell" / unscoped 4% | PARTLY FIXED | scoped to concurrency, but the figure is now wrong (3.6% vs 4.0%) |
| 19 | "970 on both backends" | FIXED | L208 "933 native and 970 ONNX" |
| 20 | "about 2 ms" vs 1.6 ms | FIXED | L174, L198, L257, L390 |
| 21 | Mixed-backend p95 2.0 ms | FIXED | L3, L29, L175 give 2.0/1.9 |
| 22 | venv composition inferred, not measured | PARTLY FIXED | L4, L222–L224 fixed; L384 key concept residual |
| 23 | Frame-hash match with 12 | RESOLVED (round 2) | — |
| 24 | Roadmap details lacked numbers or gate | FIXED | L362, L371, L374 |
| 25 | Transitions not folded (gold) | FIXED | as #1 |
| T2 | "one-millionth of a bike" (L132 old) | FIXED | L112 "at most 0.00012 rentals" |
| T9 | "p95 about 0.21 s" at c64 | FIXED | L178 "0.249/0.210 s" |
| L3 | "25.43 bikes/hour accuracy" | FIXED | L85 "average error" |
| L3 | "$1.15e-05" | FIXED | L315 `$0.0000115` |

Totals for the 25 numbered findings: 1 still present (#3), 5 partly fixed (#4, #6, #8, #18, #22), 19 fixed or resolved. All four additional round-2 items are fixed.

## New errors introduced by Wave 8

| # | Line | Issue |
|---|---|---|
| N1 | L189, L213, L285 | "concurrency `p50` differs by at most `3.6%`". The c4 gap is 4.0–4.2%. This came from round 2's wrong c4 figure (2.5%); the previous "4%" was correct. |
| N2 | L395 | Caption "ratios span 0.97–1.04". The actual range is 0.96–1.04. |
| N3 | L211–L212 vs L177, L207, L345, L391 | The new hypothesis framing contradicts the unchanged factual CPU-contention statements elsewhere. |
| N4 | L90–L91 | Telegraphic fragment run ("Cyclical terms lie in [-1, 1]. Lags reach 800."). |

## Top 5 remaining fixes

1. **L189, L213, L285: change "at most `3.6%`" to "at most `4%`"** (or "`4.0%`", c4 relative to native). This is a numeric contradiction repeated in three places.
2. **L395: change "0.97–1.04" to "0.96–1.04".**
3. **L177, L207, L345, L391: hedge the contention claims** to match L211–L212. For example: L177 "Beyond it, driver and service likely contend for one CPU"; L207 "at 64 clients, where the shared CPU is likely saturated"; L391 "The curves bend where the shared CPU likely saturates". At L392, drop "queue-dominated" or say "flat per-request latency (queueing and compute not separated)".
4. **L207: "`p50` about `63 ms`"** → "`p50` `65.4/63.1 ms` native/ONNX". **L384: "Measure its venv, torch, and unused CUDA components"** → "Measure base, venv, and model layers, and infer framework weight from a slim build".
5. **Polish:** merge L90–L91 into one sentence. Fix the L281–L282 "too loose on good ones" logic. Trim the third retelling of image and cost in Conclusions (L309–L316 or L349–L352). Turn the L198 and L257 plain-terms cards into outcome statements.

## Ready to publish?

**No, but close.** Two numeric contradictions are new in this round: "at most 3.6%" in three body lines, and the "0.97–1.04" caption. A reader who checks the slope figure or `metrics.json` against the article will see them. Fixes 1 and 2 are single-token edits, and fix 3 is a few words per line. With those three done, the article is publishable. Fixes 4 and 5 are polish.
