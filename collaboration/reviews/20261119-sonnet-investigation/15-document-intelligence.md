# 15 Document intelligence app: investigation

Date: 2026-11-19 (searches on 2026-11-18). Labels: SB / SEC / GAP. Source IDs map to `99-sources.md`.

## Current state (committed)
- Born-digital PDF workbench: per-page Pydantic AI analysis (cited summary, entities, topics), cited page chat, deterministic citation resolution against PyMuPDF spans after a unicode fold; no tools or write capability for the agents. Source: `apps/document-intelligence/README.md`.
- Metrics files: `apps/document-intelligence/reports/offline-metrics.json` and `live-metrics.json`; dataset: 7 committed synthetic born-digital mixed documents, 8 reference pages, revision 2026-11-08.1.
- Live run (`live-metrics.json`, live_model kimi:kimi-for-coding): entity F1 0.677 (precision 0.524, recall 0.957, type accuracy 0.957), QA answer accuracy 1.0, QA token F1 0.840, summary key-point coverage 0.818, topic F1 0.5, evidence resolvability 1.0, unsupported citation rate 0.0, page failure rate 0.0, analysis miss rate 1.0; p50 38.5 s, p95 86.4 s.
- Offline (`offline-metrics.json`, fake analyzer): entity F1 0.757 (precision 1.0, recall 0.609), QA accuracy 0.875, summary coverage 0.364, topic F1 0.467. The offline numbers measure the scripted analyzer, not a model.
- The cost estimate in both files is a character/4 estimate with zero configured prices, not provider metering.
- Limits to keep beside any number: 7 synthetic documents, 8 reference pages; every page is an "analysis miss" under the file's own definition (any uncovered key point, entity/topic F1 below 1.0, etc.).

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | Citation quality: ALCE-style citation recall and precision via entailment. The app resolves quotes exactly against parsed passages (strong), but exact resolution proves the quote exists, not that it supports the claim. | SEC | S48 |
| G2 | Parsing quality is not measured: OmniDocBench evaluates 981 pages across 9 document types with edit distance for text, TEDS for tables, reading-order distance; reading order and cross-page content remain hard. Our dataset is synthetic and born-digital. | SEC | S49 |
| G3 | Evaluation set size: 7 documents and 8 pages cannot support rates beyond descriptive; entity precision 0.524 live vs 1.0 offline shows sensitivity to the scorer's exact-match rule. | GAP (no source needed; our file) | none |
| G4 | Grader brittleness: normalised exact match on (text, name, type) can score a valid entity as a false positive; the agent-eval guidance says to read transcripts to see whether failures are fair. | SB | S05 |
| G5 | Judge calibration if an LLM grader is added: report kappa and re-calibrate on prompt or model change. | SEC | S09, S10 |

## Candidate improvements
**A. Error taxonomy of the live entity false positives (precision 0.524).**
- Method: read the 7-document live output and classify each false-positive entity: valid but unlabelled, span variant, wrong type, hallucinated. If most are valid-but-unlabelled, the benchmark's reference set is the limit, not the model. Report counts; existing metrics unchanged.
- Reference: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents (S05).
- Cost: reading only.
- Stop condition: over 50% hallucinated; then escalate as a model-quality finding.

**B. Add a second, non-synthetic fixture slice (10-20 pages from public-domain born-digital PDFs).**
- Method: choose public-domain or permissively licensed documents; hand-label key points, entities and QA; run offline parse plus live analysis; report parsing metrics (text edit distance, table TEDS where tables exist) and the existing metrics with Wilson intervals.
- Reference: https://arxiv.org/html/2412.07626v2 (S49) for metric definitions.
- Cost: labelling (2-3 days); live calls under an owner cap.
- Stop condition: licence of a source document forbids committing the text; replace the document.

**C. Entailment-based citation-support check on resolved quotes.**
- Method: for each resolved citation, test whether the quoted passage entails the summary sentence or answer span with a small local checker; report support precision.
- Reference: https://arxiv.org/pdf/2305.14627 (S48); https://arxiv.org/html/2404.10774v2 (S52).
- Cost: compute only, about 1-2 days.
- Stop condition: checker agrees with hand labels on fewer than 80% of 30 items.

**D. Multi-trial live run (k=3) for variance on the 7 documents.**
- Method: three live analyses per document; report entity F1 and key-point coverage spread.
- Reference: S05; S03.
- Cost: hosted calls under an owner cap (latency p50 38.5 s per case in the committed run).
- Stop condition: spread larger than any proposed prompt change's effect; stop and fix the metric first.

## Ranked recommendation
1. A (false-positive taxonomy): free, tells whether the metric or the model is the limit.
2. C (entailment check), then B (non-synthetic slice).
3. D (multi-trial).

## Queries used (standard, 2026-11-18)
- "document question answering citation attribution evaluation ALCE citation precision recall PDF extraction benchmark OmniDocBench"
- "PDF parsing benchmark OmniDocBench document parsing evaluation text table reading order"
- "agent evaluation best practices multiple trials pass@k pass^k graders transcripts Anthropic demystifying evals for AI agents"
