# 06 VRPTW routing: investigation

Date: 2026-11-19 (searches on 2026-11-18). Labels: SB / SEC / GAP. Source IDs map to `99-sources.md`.

## Current state (committed)
- 56 standard Solomon 100-customer problems: hand-written search within 4.2% of best-known routes in about 1 second each, using 3.7 more vehicles than best-known on average; exact solver certifies small cases only. ALNS-hinted mean gap 4.23% (CI [3.22, 5.28], per the 2026-11-19 gap analysis). Eight solvers, plans validated before scoring; hinted CP-SAT ties ALNS at 12.0 s mean runtime. Source: `projects/06-routing-optimization/story.yaml`; metrics `projects/06-routing-optimization/reports/metrics.json`.
- Roadmap "next": larger Gehring-Homberger instances; needs an owner scope decision.

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | PyVRP (hybrid genetic search) is the open reference solver; the paper reports VRPTW results on 1000-customer Homberger and Gehring instances, not Solomon-100. | SB | S02 |
| G2 | **Conflict, unresolved by rule.** Kimi's W9 reading: PyVRP 0.40%, HGS-DIMACS 0.32%, DIMACS reference 0.29% (VRPTW). Search-snippet reading: PyVRP 0.27%, HGS-2012 0.28%, HGS-CVRP 0.16%. My fetch of arXiv 2403.13795v2 returned: VRPTW Table 2 (mean gap / gap of mean) PyVRP 0.40% / 0.46%, HGS-DIMACS 0.32% / 0.37%, DIMACS reference 0.29% / 0.31%; CVRP Table 1 (X instances) PyVRP 0.22% / 0.27%, HGS-2012 0.21% / 0.28%, HGS-CVRP 0.11% / 0.16%. So the snippet's three numbers match the "gap of mean" column of the CVRP table, not the VRPTW table. This is evidence the two readings come from different tables; I record it and leave the decision with the owner because the fetch tool summarises the page and I did not view the PDF. Do not cite PyVRP numbers until the owner closes it. | SB (fetched page, tool-summarised) vs SEC (snippet) | S02 |
| G3 | SINTEF's benchmark objective is hierarchical: minimise vehicles, then distance; distances in double precision, totals rounded to two decimals; exact-method papers use different precision so results are not directly comparable. Our 4.2% gap with 3.7 extra vehicles is therefore not a like-for-like win on SINTEF's objective; the copy already discloses the vehicle excess. | SEC | S58, S59 |
| G4 | No 2025-2026 head-to-head of HGS and ALNS on Solomon or Gehring-Homberger found. | GAP | none |
| G5 | Solomon remains the standard comparison set, often extended with Homberger and Gehring (a Dec 2025 paper, snippet). | SEC | S58 |

## Candidate improvements
**A. Run PyVRP as an in-repo reference arm on the same 56 Solomon-100 instances.**
- Method: add PyVRP (open source, HGS-based) as a ninth solver with the repo's validator, same time limits (1 s and 12 s), report gap to SINTEF best-known on distance and vehicle count separately. This produces our own number and avoids citing the disputed table.
- Reference: https://arxiv.org/html/2403.13795v2 (S02) for the solver description only.
- Cost: compute only; adds a dependency (owner decision); about 1-2 engineering days.
- Stop condition: PyVRP cannot be pinned to a licence/version the repo accepts, or plans fail the validator.

**B. Report vehicle-first ordering.**
- Method: re-tabulate committed results by SINTEF's hierarchy (vehicles, then distance) and show where the solver ties or loses on vehicles; no new solves.
- Reference: https://sintef.no/projectweb/top/vrptw/homberger-benchmark (S58).
- Cost: compute only, under 1 day.
- Stop condition: committed results lack per-instance vehicle counts.

**C. Unhinted arm with a longer budget (separate experiment).**
- Method: run unhinted CP-SAT/ALNS at 60 s and 300 s on a seeded 10-instance sample; add distances to the unhinted arm.
- Reference: none needed beyond SINTEF best-known (S59).
- Cost: compute; about 10 instances x 2 budgets.
- Stop condition: no instance improves; stop and keep the label.

**D. Gehring-Homberger 200-400 customer slice.**
- Method: scope decision for the owner; run ALNS and PyVRP on 10 instances at 200 customers first.
- Reference: S59 (SINTEF tables; numeric best-knowns not read: GAP).
- Cost: compute, plus owner scope decision.
- Stop condition: owner declines scope, or runtime exceeds 30 minutes per instance.

## Ranked recommendation
1. A (PyVRP arm): high value; resolves comparability without citing disputed tables.
2. B (vehicle-first table): high value, near-free.
3. C then D.

## Queries used (standard, 2026-11-18)
- "PyVRP arXiv 2403.13795 HGS-CVRP Solomon Homberger benchmark results"
- "Hybrid genetic search VRPTW Solomon Gehring Homberger 2025 state of the art ALNS comparison"
- "Gehring Homberger VRPTW 1000 customers best known solutions SINTEF benchmark hierarchical objective vehicles then distance"
- Fetched: arxiv.org/html/2403.13795v2.
