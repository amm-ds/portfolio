# Verifier reconciliation report (local judge)

Generated: 2026-11-20T01:28:44.305235+00:00 (commit `561ad93acc2b6c0e60facf9ed2e2c6f660042c94`)

| prompt | FA all claims (Wilson 95%) | FA strict (Wilson 95%) | FR (Wilson 95%) |
|---|---|---|---|
| rubric (judge.py) | 23/194 = 0.1186 [0.0803, 0.1716] | 23/97 = 0.2371 [0.1635, 0.3307] | 12/97 = 0.1237 [0.0722, 0.2039] |
| entailment (calibrate_judge.py) | 2/194 = 0.0103 [0.0028, 0.0368] | 2/97 = 0.0206 [0.0057, 0.0721] | 83/97 = 0.8557 [0.7722, 0.912] |

- Agreement between prompts: 100/194 = 0.5155

## 2x2 rubric x entailment, by gold label

- supported: {'accept_accept': 14, 'accept_reject': 71, 'reject_accept': 0, 'reject_reject': 12}
- unsupported: {'accept_accept': 1, 'accept_reject': 22, 'reject_accept': 1, 'reject_reject': 73}

## Reconciliation against committed 0.4433

- Entailment FA all claims: 2/194 (tolerance ±1 claim around 86)
- Reproduced: **False**
- Decision: the committed 0.4433 or the cache path is wrong; discrepancy reported, cascade result unchanged (per handoff: stop, do not change the cascade result)

No hosted calls ($0).
