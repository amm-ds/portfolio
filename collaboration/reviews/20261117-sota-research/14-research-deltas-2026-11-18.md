# Research deltas, 2026-11-18

Date: 2026-11-18
Author: Claude Code
Scope: updates to `00-research-and-recommendations.md` found while preparing the next wave. Only items that change a decision or a card are listed. Confidence labels follow that file: **source-backed** (read the primary text), **secondary** (summary or aggregator), **hypothesis** (needs a test).

## 1. TabPFN licence and version (affects open question D, project 12)

- **Source-backed (docs, model cards):** TabPFN-2.5, 2.6 and 3 weights are released under non-commercial licences. The 2.6 model card limits commercial or production use and points to a Commercial Enterprise License (sales@priorlabs.ai). TabPFN-2 weights fall under the Prior Labs licence (Apache-style with attribution).
- **Source-backed (docs):** downloading TabPFN-2.5, 2.6, 3 and 3.5 weights needs an accepted licence on a Prior Labs account and `TABPFN_TOKEN`.
- **Secondary:** TabPFN-3.5 was released 2026-09-15 and is the current default. A secondary article says its licence forbids commercial or production use. Another source calls it permissive for research and evaluation. The two disagree, so the licence text must be read before use.
- **Secondary (PyPI, package release notes):** the code is Apache-style with attribution. The v10.0.0 release notes list no licence change.
- **Not verified:** `tabpfn==10.2.0`, the version named in the 12 open-questions file. The search found 10.0.0 but not 10.2.0. Check PyPI before any handoff names a version.
- **Impact:** option D in the open-questions plan (accept the licence and run TabPFN) also needs a licence decision. The portfolio is public, so a non-commercial weight licence may or may not cover it. Owner decision; this is not a technical question.

## 2. M5 accuracy and reconciliation (project 02)

- **Not verified:** the WRMSSE 0.52 top score, and the reconciled-LightGBM value. Searches returned only secondary sources and did not confirm either number.
- **Source-backed (arXiv 2103.08250, Anderer and Li):** top-down alignment approach placed second in the M5 Accuracy track. It is the strongest primary source for reconciliation in M5.
- **Secondary (arXiv 2609.27912, 2026):** global tree forecasters collapse at the hierarchical aggregate. This is a reason to report aggregate-level checks beside the 0.6161 headline.
- **Impact:** keep the reconciled row out of the headline until the reconciliation output exists (open-questions plan, option B). Add the 2026 aggregate-collapse result as context only after reading it.

## 3. PyVRP (project 06)

- **Not found:** a 2026 PyVRP release or new Homberger results. Only the 2024 arXiv paper and third-party packaging (`vrpr`) were found.
- **Check before citing:** the 2403.13795 benchmark table appears to list X-n (CVRP-style) instance names, while its caption says Homberger and Gehring VRPTW. The earlier SOTA file treated this as resolved. It is not resolved until the table is read directly.
- **Impact:** the 06 README must not cite PyVRP gap numbers until that table check is done.
- **Resolved 2026-11-19 (W9):** table read directly (arXiv 2403.13795v2). Table 4
  is the CVRP benchmark (X-n###-k## Uchoa instances); Table 5 is the VRPTW
  benchmark (C1_10_*/C2_10_*/R1_10_*/R2_10_*/RC1_10_*/RC2_10_* — Homberger and
  Gehring 1000-customer names). The caption matches Table 5; the X-n names
  belong to the CVRP table. No Solomon table exists. Published headline:
  PyVRP mean gap 0.40% / gap of mean 0.46% vs HGS-DIMACS 0.32% / DIMACS
  reference 0.29% (10 seeds, 2 h, PassMark-normalized, 27/300 BKS improved).
  Consequence: the paper's 0.40% is NOT comparable to this repository's
  Solomon-100 local run; 06 README keeps citing no PyVRP published gap.
  Full note: `collaboration/designs/20261117-06-routing-review-fixes/pyvrp-solomon-results.json → table_check`.

## 4. Anomaly metrics (project 03)

- **Source-backed (AAAI 2022, Kim et al.):** point adjustment can make a random score look state-of-the-art.
- **Source-backed (arXiv 2607.11969, Lyu, July 2026, preprint):** VUS-ROC is inflated on 131 series where VUS-PR is not, and never the reverse. The preprint recommends PR-based metrics and reporting single-run scores or the number of runs.
- **Impact:** keep VUS-PR as the headline. Add the number of runs to the 03 card. Treat the preprint as a single, unreplicated source.

## 5. Agent reliability (project 09)

- **Source-backed (τ-bench, Sierra):** the reliability metric is pass^k, the chance of succeeding on all k independent trials. The public board reports pass^1.
- **Secondary:** Layer3Labs and other aggregators quote top-model scores on τ²-bench. None were checked against taubench.com, so do not cite them.
- **Impact:** the 09 card reports single runs. For reliability wording, either report pass^k with k≥3 on the held-out set, or state "single run per task" explicitly. A multi-trial run would need an owner-approved hosted budget.

## 6. RAG citation grounding (project 01)

- **Source-backed (arXiv 2026, ForceBench preprint):** a relevant citation can still back an over-strong claim. Generic support prompts miss this often (47.2% monotonicity violation across four judges). Explicit warrant-strength prompting lowers it to 24.5%, still imperfect.
- **Secondary (2026 guides):** RAGAS faithfulness measures claim-level support, not accuracy. Store the judge model, dataset version and calibration date with each threshold.
- **Impact:** add a warrant-strength check and a judge calibration set to project 01. Both need hosted calls for the judge, so they need an owner-approved cap.

## Not changed by this pass

- Projects 04, 05, 07, 08, 10, 11, 12 (except the TabPFN licence), 13: no new primary-source finding that changes a decision. The earlier research file still stands for them.
