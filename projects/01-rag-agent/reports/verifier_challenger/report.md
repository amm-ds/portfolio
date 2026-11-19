# Verifier challenger Phase 1 report

Generated: 2026-11-19T23:48:36.675379+00:00 (commit `eebe331e9c048804b115c72e327dac7c782b0e06`)

## Checkpoint

- `lytang/MiniCheck-Flan-T5-Large` revision `96eafd01cee2d16cf81aaa2fb226b14f422a37b3`
- License: mit (record: reports/verifier_challenger/license.md)
- License text sha256: `24b88d376d17db5d38c02f2f799a3e6aa282e1628c3b6ccc89de4409d49e8146`

## Split

- File: `data/calibration/verifier_split.json`, seed 42
- Counts per label: `{"supported": {"dev": 48, "test": 49}, "unsupported": {"dev": 48, "test": 49}}`
- claims.jsonl sha256: `675ac742796a273f47c743148b9e33829e7de26ff4e8d68e170e980e885859bc`

## Threshold (DEV only)

- `0.9410304427146912` (dev accuracy max, ties to lower threshold); DEV n=96, accuracy 0.9271

## TEST results (n per label above)

- FA strict (unsupported accepted): 2/49 = 0.0408, Wilson 95% [0.0113, 0.1371]
- False rejection (supported rejected): 7/49 = 0.1429, Wilson 95% [0.071, 0.2667]

### Sensitivity: TEST excluding `manual_review` rows

- FA strict: 0/46 = 0.0, Wilson 95% [0.0, 0.0771]
- False rejection: 7/49 = 0.1429, Wilson 95% [0.071, 0.2667]

## Baselines on the same TEST claims

- hosted_qwen3_4b_pooled: FA strict 37/92 = 0.4022, Wilson 95% [0.3078, 0.5043]; FR 1/98 = 0.0102
- hosted_qwen3_4b_run0: FA strict 16/46 = 0.3478, Wilson 95% [0.2268, 0.4923]; FR 0/49 = 0.0
- hosted_qwen3_4b_run1: FA strict 21/46 = 0.4565, Wilson 95% [0.3215, 0.5982]; FR 1/49 = 0.0204
- covered 95/98 TEST ids (source: `reports/judge_calibration_hosted/qwen3_4b-20261115T125747/predictions.jsonl`)
- local qwen2.5:3b on ALL 194 claims (aggregate, no per-claim verdicts committed): FA strict 0.4433, Wilson 95% [0.3752, 0.5136]

## Flip rate (two full CPU re-scores)

- 0/194 = 0.0; max |score_a - score_b| = 0.000000
- chunking: 0 multi-chunk claims of 194

## Gate (pre-registered)

- FA rate <= 0.25: 0.0408 -> PASS
- FA Wilson UCB < 0.3269: 0.1371 -> PASS
- FR rate <= 0.1: 0.1429 -> FAIL
- Flip rate <= 0.05: 0.0 -> PASS
- **Overall: FAIL**

Runtime 120.49 s on CPU (fp32, batch size 1), no hosted calls ($0).

