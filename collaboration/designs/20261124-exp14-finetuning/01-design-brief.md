# Project 14 Design Brief — LLM Fine-Tuning (Gemma vs. Qwen on Structured Intent Classification)

Date: 2026-11-24
Author: Claude Code (Architect)
Status: Design Brief (awaiting owner approval before implementation handoff)
Target Package: `projects/14-llm-finetuning` (`llm_finetuning`)

---

## 1. Why This Project Exists (Portfolio Gap)

The portfolio already covers encoder-based text classification (`04-nlp-classification`: TF-IDF, Sentence-Transformers, DeBERTa) and prompt-engineered tool-use RAG (`01-rag-agent`), but **no experiment tests parameter-efficient weight adaptation (LoRA / QLoRA) of open-weights generative Small Language Models (SLMs)**.

Fine-tuning a 3B–4B open-weights model to emit **both** a fine-grained domain label (77 classes) and a **strict, schema-validated JSON payload** solves a real production bottleneck: zero-shot generative models suffer from label drift, prose leakage, and semantic confusion across overlapping classes, while single-head classifiers cannot emit structured multi-field metadata without custom heads.

---

## 2. Objective & Research Questions

1. **Quantified Fine-Tuning Lift:** How much macro-F1, top-1 accuracy, and JSON schema compliance do **LoRA-tuned Qwen2.5-3B-Instruct** and **Gemma-3-4B-it** gain over their zero-shot and 5-shot base models on an identical locked golden test set?
2. **Cross-Family Comparison (Qwen vs. Gemma):** Under matched LoRA rank (`r=16, alpha=32`), training budget, and 4-bit quantization on Apple Silicon (`arm64`), how do Qwen and Gemma compare on classification accuracy, schema adherence, adapter footprint, peak unified memory, and serving throughput (tokens/sec, p50/p95 latency)?
3. **Sample Efficiency & Cost Curve:** Does LoRA saturation occur at 25%, 50%, or 100% of training data, and how does the fine-tuned 3B–4B generative model compare against a classical TF-IDF + Logistic Regression floor and a DeBERTa encoder reference?

---

## 3. Golden Dataset & Split Discipline

### Primary Dataset: `PolyAI/banking77`
- **Source:** [PolyAI/banking77 on Hugging Face](https://huggingface.co/datasets/PolyAI/banking77) (CC-BY-4.0), **10,003 train / 3,080 test** real customer-service banking queries across **77 fine-grained intents** (source-backed: [HF Banking77 LoRA benchmark](https://huggingface.co/spaces/evaluate/banking77) / [OpenReview LoRA classification benchmarks](https://openreview.net/)).
- **Why Banking77 (vs. 3-class sentiment):** Three-class sentiment (e.g., Financial PhraseBank) is too easy to saturate and hides calibration/confusion failure modes. Banking77 has tight semantic overlap (`card_arrival` vs `card_delivery_estimate`, `declined_card_payment` vs `card_payment_not_recognised`, `topping_up_by_card` vs `top_up_by_card_charge`) where zero-shot LLMs typically score **35%–66%** and misformat labels, whereas LoRA SLMs reach **~91.5%–92.1%** (source-backed: Hugging Face SLM LoRA benchmarks).
- **Structured Output Augmentation (Deterministic):** Each row is deterministically mapped via a committed taxonomy table (`src/llm_finetuning/taxonomy.py`) to a strict 2-field JSON target:
  ```json
  {"intent": "<canonical_77_label>", "domain_group": "<one_of_8_coarse_routing_queues>"}
  ```
  This turns the task from toy label matching into **structured triage + routing** without altering ground-truth labels.
- **Golden Hard Slice (300 rows):** A stratified 300-row slice carved from the official test set targeting the top 15 most-confused intent pairs (documented in `data/dataset_contract.json`), evaluated separately alongside the full 3,080-row test set.

### Split & Leakage Rules
| Split | Rows | Purpose | Leakage Guard |
|---|---:|---|---|
| `train` | 8,500 | LoRA gradient updates (stratified from official 10,003 train) | Deduped against `val` and `test` by normalized text hash |
| `val` | 1,503 | Learning rate, LoRA rank (`r=8` vs `r=16`), early stopping, prompt template | Never used in gradient steps |
| `test` | 3,080 | Official `banking77` test split — **locked until final single evaluation** | Hash-verified against train/val; zero prompt tuning on test |

### Data Registry Contract (`registry/`)
- Register `registry/banking77.dvc` (`dvc import-url --no-exec`) and `docs/data-registry/banking77.md` per `registry/README.md`.
- `prepare` stage verifies SHA-256 checksums of downloaded Parquet/JSONL splits, checks class balance (all 77 classes present in train/val/test), and emits `data/dataset_contract.json` + `reports/dq_report.md`.

---

## 4. Model Ladder & Baselines

All models are evaluated on the **exact same `test` (3,080) and `golden_hard` (300) rows** with identical JSON schema validation:

1. **Classical Non-LLM Floor:** `TF-IDF (1-2 ngrams) + LogisticRegression` + deterministic `intent -> domain_group` lookup. Establishes the sub-millisecond CPU baseline.
2. **Zero-Shot Base Models:**
   - `mlx-community/Qwen2.5-3B-Instruct-4bit` (zero-shot, temperature `0.0`, canonical 77-label system prompt + JSON schema).
   - `mlx-community/gemma-3-4b-it-4bit` (zero-shot, temperature `0.0`, identical prompt & schema).
3. **Few-Shot Base Models (5-Shot):** Same base models with 5 stratified in-context examples in the prompt to isolate *prompting* gains from *weight-update* gains.
4. **Fine-Tuned LoRA Challengers:**
   - `Qwen2.5-3B-Instruct` + LoRA (`r=16, alpha=32, dropout=0.05`, all linear projections, `packing=False`).
   - `Gemma-3-4B-it` + LoRA (`r=16, alpha=32, dropout=0.05`, all linear projections, `packing=False`).
5. **Required Ablations (Val Set, Before Locking Winner):**
   - LoRA Rank: `r=8` vs `r=16`.
   - Data Scaling Curve: `10%` (850), `25%` (2,125), `50%` (4,250), `100%` (8,500) training rows.
   - Pre-fuse Adapter vs. `mlx_lm.fuse` merged weights (latency + accuracy parity check).

---

## 5. SOTA Frameworks & Compute Strategy

- **Primary Training & Inference Stack (Apple Silicon `arm64`):** **`mlx-lm`** (`mlx_lm.lora`, `mlx_lm.fuse`, native Metal unified-memory execution) using 4-bit quantized `mlx-community` weights. Logs native peak unified memory (GB) and generation throughput (tok/s) (source-backed: [MLX LM](https://github.com/ml-explore/mlx-examples/tree/main/llms/mlx_lm)).
- **Portable Linux / CUDA Alternative (Optional Extra `[hf]`):** Hugging Face **`trl` (`SFTTrainer` / `SFTConfig`) + `peft` (`LoraConfig`) + `transformers`** (`BitsAndBytesConfig` 4-bit NF4), keeping identical ChatML/messages data formatting so the codebase is hardware-portable without coupling Linux CI to `mlx` (source-backed: [HF TRL SFTTrainer](https://huggingface.co/docs/trl/sft_trainer)).
- **CI Isolation Rule:** `mlx` and `mlx-lm` MUST be gated behind platform markers (`sys_platform == 'darwin' and platform_machine == 'arm64'`) or an optional `[finetune]` extra not installed in Linux CI (`ubuntu-latest`) or `showcase-api` Docker. CI tests run on deterministic CPU fixtures + schema/metric validators.

---

## 6. Success Criteria & Statistical Reporting

Per `docs/engineering/statistical-intervals.md`:
- **Primary Lift Metric:** Test Macro-F1 and Top-1 Accuracy lift (`Fine-Tuned - Zero-Shot`) with **paired row bootstrap 95% CI (2,000 resamples, seed 42)**. Success requires the 95% CI to **exclude zero** and achieve **>= +20.0 percentage points** accuracy lift over the base model.
- **Accuracy Target:** Winning LoRA model reaches **>= 88.0% Top-1 Accuracy** (95% Wilson CI) on full Banking77 test (`n = 3,080`).
- **Structural Reliability Target:** **>= 99.5% valid JSON + canonical label adherence** (measured before any fallback/regex recovery; Wilson 95% CI).
- **Footprint & Latency:** Peak training memory **<= 8.0 GB**, adapter checkpoint **<= 200 MB**, inference latency reported via **nearest-rank p50/p95** (`n = 300` warm queries).
- **Provenance:** Committed `reports/metrics.json` stamped via `scripts/stamp_metrics_meta.py` and guarded by `scripts/check_headline_numbers.py`.

---

## 7. Open Decisions for Owner Before Handoff

1. **Model Pair Confirmation:** Confirm **Qwen2.5-3B-Instruct** vs **Gemma-3-4B-it** (4-bit MLX) — or upgrade Qwen to `Qwen3-4B-Instruct-4bit` if available locally on Hugging Face `mlx-community` at execution time.
2. **Offline CI Twin:** Confirm generating a small seeded synthetic Banking77-like fixture (e.g., 160 rows across 8 intents) inside `tests/` so CI exercises the full `prepare -> validate -> evaluate -> metrics/bootstrap` pipeline offline without downloading 4B weights.
3. **Training Backend Priority:** Confirm running the real committed experiment on local Apple Silicon via `mlx-lm` while keeping the `trl`/`peft` adapter module tested via config/schema unit tests.
