# Sources and queries (2026-11-18, standard mode only)

| ID | URL / path | Label | Used for |
|---|---|---|---|
| C1 | https://arxiv.org/html/2403.13795v2 | SB | PyVRP Tables 1, 2, 4, 5 captions and numbers (tool-summarised page) |
| C2 | collaboration/designs/20261117-06-routing-review-fixes/pyvrp-solomon-results.json | SB (local) | local PyVRP run; `table_check` block |
| C3 | projects/06-routing-optimization/README.md, story.yaml | SB (local) | no PyVRP number cited |
| C4 | https://arxiv.org/abs/2607.11969 | SEC | Lyu stress test abstract (abstract page summarised) |
| C5 | https://huggingface.co/Prior-Labs/TabPFN-v2-clf (+ /blob/main/LICENSE.txt) | SB | card tag priorlabs-1-1; Prior Labs License v1.1, May 2025 |
| C6 | https://huggingface.co/Prior-Labs/TabPFN-v2-reg | SB | card tag priorlabs-1-1; no sample limit |
| C7 | https://econpapers.repec.org/RePEc:eee:intfor:v:38:y:2022:i:4:p:1346-1364 and https://statmodeling.stat.columbia.edu/wp-content/uploads/2021/10/M5_accuracy_competition.pdf | SEC / unreadable | M5 paper listing; PDF text not extractable |
| C8 | apps/agent-chat/reports/evals-kimi-for-coding.md, evals-kimi-k3-256k.md, evals-kimi-k3.1-pro.md; apps/showcase-web/src/lib/agentChatEvalSummary.ts; apps/showcase-web/src/pages/AgentChatArticle.tsx | SB (local) | counts |
| C9 | https://nips.cc/virtual/2024/poster/97690 | SEC | 40 algorithms (abstract) |
| C10 | https://github.com/TheDatumOrg/TSB-AD | SB | README: 40 stated, 35 listed, changelog |
| C11 | projects/10-uplift-experimentation/src/uplift_experimentation/qini.py, DESIGN.md, MODEL_CARD.md | SB (local) | formula |
| C12 | https://scikit-uplift.readthedocs.io/en/latest/api/metrics/qini_auc_score.html, https://libuplift.readthedocs.io/en/latest/auto_examples/evaluation/Qini_and_uplift_curves.html, https://arxiv.org/pdf/2608.00915 | SEC | Qini vs AUUC definitions and version drift (snippets) |

## Queries (WebSearch, standard mode, 2026-11-18)
1. "Lyu 2026 VUS-PR gamed NAB time series anomaly detection stress test arXiv"
2. "M5 accuracy competition results findings conclusions Makridakis evaluation rolling origin validation period 28 days"
3. "Qini coefficient Radcliffe definition versus AUUC area under uplift curve formula difference scikit-uplift"

## Fetches (WebFetch, 2026-11-18)
arxiv.org/html/2403.13795v2; arxiv.org/abs/2607.11969; huggingface.co Prior-Labs TabPFN-v2-clf (page, LICENSE.txt; /raw/main/LICENSE returned 404) and TabPFN-v2-reg; github.com/TheDatumOrg/TSB-AD; nips.cc poster 97690; Columbia M5 PDF (unreadable).

## Gaps
- Radcliffe 2007 original Qini definition: not read.
- M5 IJF paper methodology section: not read.
- Lyu PDF full text, NAB-specific numbers and N threshold: not read.
- TabPFN-2.5 licence text and the "v1.0" paper snippet: not re-checked.
- TSB-AD NeurIPS PDF and per-version method counts: not read.
