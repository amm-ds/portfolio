# Review: 13-model-serving story.yaml (Wave 6.6)

- Target: `projects/13-model-serving/story.yaml`
- Gold template: `projects/01-rag-agent/story.yaml`
- Evidence checked: `reports/metrics.json`, `reports/docker_run.json`, `reports/docker_slim.json`, `reports/train_run.json`, `README.md`, `DESIGN.md`, `Dockerfile`, `Dockerfile.slim`, `src/model_serving/artifacts.py`, `params.yaml`
- Reviewer: Claude (Opus), read-only

Note on scope: the brief said the Wave 6.6 edits are uncommitted. The working tree is clean. The edits are in HEAD (`18adc59d`). I reviewed the round as `git diff HEAD~1 -- projects/13-model-serving/story.yaml`, which has 39 insertions and 19 deletions. The round did three things. It renamed `Business summary` to `In plain terms`. It added one closing transition per section. It rewrote the roadmap titles in imperative form.

## Grades

| # | Dimension | Grade |
|---|---|---|
| 1 | Structure and article logic | 7 |
| 2 | Engagement and human-like narrative | 6 |
| 3 | Language quality | 5 |
| 4 | Technical detail depth | 8 |
| 5 | Truthfulness | 6 |
| 6 | Roadmap cards | 7 |
| 7 | Consistency with gold template | 7 |
| | **Overall** | **6.5** |

## 1. Structure and article logic: 7

The structure is good. Each section has one job: background, then gates, rebuild, probe grid, service, protocol, ledger, and summary. Each new transition points to the right next anchor. Results also comes before Conclusions, which avoids a common problem: the ledger does not repeat the evaluation narrative.

Problems:

- **The transitions all use one template.** Every new transition reads "The X is Y; next, Z ([Sec →])". The instances are L29, L61, L98, L131, L189, L228, and L287. Seven of them in a row read as boilerplate. Gold uses the same `next,` hook but changes the sentence around it. Compare gold L35, L61, L82, and L136, which describe what the reader will see.
- **L188–L189 lose their paragraph break.** The excerpt attribution line runs straight into the transition with no blank line between them. In Markdown they render as one paragraph: "...app.py). The service is warmed; next, ...".
- **Results repeats material across L237–L295.** The section restates four bullets "shown above" (L239). It then covers the footprint, the slim image, the chown fix, cost, the compose smoke test, and the out-of-scope list. After that, Conclusions repeats most of it at L298–L305, L346–L352, and L374–L392. The image-size and cost story is told three times.
- **The background heading asks a question the article never answers directly** ("What does it take…", L13). The conclusions answer with numbers, not with a statement of "what it takes".

## 2. Engagement and human-like narrative: 6

The best passages are concrete: the chown layer story (L267–L269), the line "the CPU tabular model carries CUDA libraries it never loads" (L324–L325), and the queue-sag observation at c16 (L246–L247). Those read like an engineer who did the work.

The rest is undercut by inline glossary sentences. A definition appears about every two sentences. Examples: "A seed is…" (L42), "A checksum is a fingerprint…" (L87), "A scaler is…" (L110), "Float32 is…" (L116), "JSON is a text format…" (L143), "A healthcheck is…" (L161), "Inference means…" (L166), "Latency is…" (L207), "Concurrency is…" (L201), "Rows/s counts…" (L218), and "SHA-256 is a checksum…" (L359). Training (L140–L168) alone defines state_dict, JSON, opset, dynamic batch, Pydantic, readiness, healthcheck, and inference. The narrative never builds momentum. An expert reader skims past the definitions, and a lay reader still gets no story.

## 3. Language quality: 5

- **The definition stacking makes the rhythm choppy.** Look at the opening paragraph (L13–L18): "It is a small multilayer perceptron (MLP). An MLP is a neural network that learns from tables. It predicts hourly bike rentals. FastAPI is a Python tool… An API, or application programming interface, sets the rules…" That is five short declaratives on four different subjects.
- **L16 is an unwrapped 120+ character line** introduced in this round ("network that learns from tables. It predicts hourly bike rentals. FastAPI is…"). It breaks the file's wrap convention.
- **"Reads as noise" appears three times:** "read as scheduling noise" at L224–L225, L323, and L426, plus "floating-point noise" at L126 and "noisy ~15% delta" at L294.
- **The "In plain terms" cards repeat the same numbers.** L231–L234, L290–L294, and the headline (L2) all list "1.6 ms p50 (p95 2.0 ms, p99 2.2 ms; n = 300…), ~950 req/s knee, ~56k rows/s". A plain-terms card should translate the result, not repeat the ledger.
- **"The diagram…" opens almost every card:** L32, L101, L134, L192, and L394. Each card is a description of the diagram, not a takeaway.
- **Awkward fragments:**
  - "The measured 6.5 GB bar is the fixed build" (L267) is unclear until L269.
  - "the parity gate supports dropping the framework safely" (L284–L285) is vague.
  - "Deployment needs — not a noisy ~15% delta — guide the backend choice" (L293–L294) introduces a number the reader has never seen.

## 4. Technical detail depth: 8

The depth is strong for a serving write-up:

- paired byte-identical payloads
- warm-up excluded, with the count stated (20)
- nearest-rank percentiles
- median of 3 repeats with min/max bands
- an absolute-plus-relative float32 parity tolerance, with the reason for the relative term
- opset 17 with a dynamic batch axis
- readiness tied to a successful warm-up inference, with the code excerpt
- `COPY --chown` versus `chown -R` layer duplication
- venv shebang path pinning
- a slim image with the dependencies listed

Honest negatives are stated: no dynamic batching, the c64 cell measures contention, and the cost basis is c16 rather than the knee.

Gaps:

- **The tolerance formula is described but not given.** The code uses `limit = tol + 1e-5 * max(1, max|native|)` (`src/model_serving/artifacts.py:142`). One inline formula would replace two sentences.
- **The rentals-scale gap of 1.2e-04 (L125–L126) is numerically larger than the 1e-4 gate value.** The article never says the gate runs in standardized output space. `metrics.json` records `space: standardized network output (end-to-end deviation = value x y_std)`. An expert will read L125 as "the gate failed on the real scale". Add one clause.
- **Single-worker uvicorn, and the driver sharing the CPU, explain the c16 sag.** The article states the sag but offers no hypothesis beyond "shared CPU", for example event-loop contention or GIL-bound handlers.

## 5. Truthfulness: 6

Checked and traceable:

- Reproduction 25.43163249606178, abs diff 0.0 (metrics `reproduction`)
- Parity 7.15e-07 scaled, 1.24e-04 on the rentals scale, n=512, tolerance 1e-4, opset 17
- r=0.9873 for `atemp`
- 15 selected fields
- 8-week test window (`params.yaml`)
- Probe ranges: weathersit 1–4 and lags 0–800 (`artifacts.py:97–108`)
- 300 requests per cell, 60 per batch size, 20 warm-up excluded, 3 repeats
- Bench runtime 25.1 s
- ONNX concurrency table: p50, p95, p99, and throughput for c1/c4/c16/c64
- ONNX c64 lead of 13.8% (714.9 / 628.3)
- p50 gap of at most 4% on the concurrency cells
- Throughput 933 / 970 at c4
- 4,320 requests per backend with zero errors (3 × (4·300 + 4·60))
- RSS 298 / 318 MB
- Image 6466 MB (base 145, venv 6192, model 1)
- Slim image 291 MB, 22.2×, venv 149 MB, six pinned packages plus portfolio-core `--no-deps` (`Dockerfile.slim:30–37`)
- Cost 1.15e-05 at 65 W and $0.30/kWh on the c16 basis
- Train runtime 2.4 s ("seconds", L141)
- chown doubling: 12.8 GB vs 6.5 GB (`DESIGN.md:52–55`)
- Compose smoke test passed

Untraceable or contradicted:

| Line | Claim | Evidence | Verdict |
|---|---|---|---|
| L115 | "three orders inside the 1e-4 gate" | 1e-4 / 7.15e-07 ≈ 140×, about 2.1 orders | **Contradicted** |
| L341–L344 | Batch rows in the `p50` column: 65.9 / 53.0 / 56.4 / 73.1 ms | Those are ONNX `mean_s`. The ONNX batch p50 values are 65.1 / 48.5 / 51.0 / 65.3 ms | **Contradicted** (mislabeled column) |
| L294 | "not a noisy ~15% delta" | No 15% figure is stated anywhere. The only stated delta is 13.8%. ONNX's b8 batch throughput lead (+15.4%) is never mentioned | **Untraceable** as written |
| L223 | "ONNX… ties elsewhere" | Batch throughput: b8 +15.4%, b32 +11.2%, b1 −11.1% (native leads) | **Contradicted** unless scoped to concurrency cells |
| L346 | "Native tracks ONNX within noise at every cell" | Batch p50: b1 53.0 vs 65.1 ms (23%), b8 58.6 vs 48.5 ms (21%) | **Overstated** (true for concurrency cells only) |
| L245–L246 | "peak near 970 req/s at concurrency 4 on both backends" | Native is 933. Elsewhere the article says "~950 knee" | **Inconsistent** |
| L208, L424 | "Single-request p50 is about 2 ms" / "~2 ms" | 1.6 ms on both backends, and the article says 1.6 ms everywhere else | **Inconsistent** rounding |
| L2, L231, L290 | "p95 2.0 ms" | That is native (2.0). ONNX is 1.9, and the table at L337 uses ONNX 1.9 | **Mixed-backend** figure |
| L2, L257–L258 | venv is "mostly torch and unused CUDA libraries" | No per-package size breakdown is committed. This is inferred from the slim venv (149 MB vs 6192 MB) | **Inferred, not measured**. Say so or cite the slim delta |
| L3 | "identical frame hash" to experiment 12 | `train_run.json:175` records the hash for 13. The match with 12 cannot be checked from project 13's files | Cross-project, not verifiable here |

That is three numeric claims that are contradicted or untraceable: "three orders", the batch "p50" values, and "~15%". There are also four scope or consistency defects and one inference presented as measurement.

## 6. Roadmap cards: 7

All titles start with a verb, and all details are 90 characters or fewer (longest about 61). The statuses make sense: four shipped and one next. Gold titles also use the imperative, so the shipped-in-imperative style matches gold.

This round lost specificity. "Parity max-abs 7.2e-07 on 512 seeded probe rows against the 1e-4 gate" became "sits orders inside the gate". "Slim image 291 MB, 22.2x smaller" became "lands at a fraction of the size". Gold details keep their numbers ("30/30 blind owner-labelled audit; 104/120 final answers"). Restore the 291 MB and 22.2× figures; they fit in 90 characters. Card 3's detail, "One flag switches the backend", is weaker than the original "Only the --backend flag differs". Card 5 has no gate, while gold's next card does ("Gate: cross-judge check…"). Name the trigger for card 5, for example "Gate: paired harness rerun on the target host before any capacity quote."

## 7. Consistency with gold template: 7

The labels now match. `In plain terms` appears in all 8 sections, and every section except conclusions ends with an anchor transition, which is the same as gold.

Differences from gold:

- Gold's plain-terms cards state an outcome in one sentence ("The assistant answers from checked passages or refuses honestly…"). Here they describe diagrams ("The diagram covers…", "The diagram ties…").
- Gold puts the transition inside the paragraph that introduces the figure (gold L82, L181). Here every transition is a separate one-line paragraph.
- Gold has one plain-terms card per section with no number list. Cards L231–L234 and L290–L294 are number dumps.

## Top 5 fixes (by severity)

1. **L335–L344, the batch rows under the `p50` column.** "65.9 ms/req", "53.0 ms/req", "56.4 ms/req", and "73.1 ms/req" are ONNX *means*, not p50. Either swap in the p50 values (65.1 / 48.5 / 51.0 / 65.3 ms) or add a `mean` column and leave the p50 cells blank.
2. **L223 "ties elsewhere" and L346 "within noise at every cell".** Scope both to the concurrency cells. Then state the batch spread honestly: ONNX leads b8 by +15% and b32 by +11%, and native leads b1 by 11%. The same applies to "p50 medians differ by at most 4%" at L224, L249, and L322; that holds only for concurrency cells.
3. **L115 "three orders inside the 1e-4 gate".** Change it to "about 140× inside" or "two orders inside". At L125–L126, add that the gate runs on standardized output, so the 1.2e-04 rentals-scale gap is the scaled gap × `y_std`, not a gate failure.
4. **L294 "not a noisy ~15% delta".** Replace it with a traceable figure, such as "the 13.8% c64 gap", or name the b8 batch gap explicitly. Also bring L245 ("peak near 970… on both backends") and L208 / L424 ("about 2 ms") into line with "~950 req/s knee" and "1.6 ms".
5. **L29, L61, L98, L131, L189, L228, L287, the templated transitions, and L32, L101, L134, L192, L394, the "The diagram…" cards.** Vary the transition sentences and fold them into the preceding paragraph, as gold does. Rewrite each plain-terms card as a one-sentence outcome. Separately, cut about half of the inline definitions (L42, L87, L116, L143, L161, L166, L218, L359), rewrap L16, and restore numbers in roadmap details L403 and L412 ("291 MB, 22.2× smaller, smoke-passed").
