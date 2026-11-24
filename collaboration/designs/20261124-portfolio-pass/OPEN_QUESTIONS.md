# Open questions for the owner: portfolio pass

Date: 2026-11-24. Answer inline under each question, or reply in chat. Items marked **blocking** stop the affected step in `03-implementation-handoff.md`; everything else proceeds on the stated default.

## Q1 (blocking for demo sizing): viewport and screenshot

The owner's screenshot of the demo cards is not visible to the design session. Please provide:
- the viewport width and height (and browser zoom) where the cards look wrong,
- the screenshot path (inside this repo or an absolute path),
- what "wrong" looks like: too narrow, too tall, empty right half, or stretched.

Default if not answered: implement the grid-cap removal only; report demo sizing as open.

## Q2 (blocking for demo sizing): which demo surface

Which surface did you mean?
- A. The demo cards on `/projects#demos` (the two cards: Churn Threshold Sandbox, Demand Forecast Workbench).
- B. The Demand Forecast Workbench page (`/demos/forecast-workbench`): KPI tiles, notice strip, header.
- C. Both.

Default: A only (the grid-cap fix covers it). Options B/C enable `02-architecture-proposal.md` §2.3(c).

## Q3 (blocking for roadmap): wording

Confirm or edit the five RAG 01 roadmap cards in `02-architecture-proposal.md` §4.2. Shipped cards are public; the `next` card is not rendered on the site. Specifically:
1. "Pin a bounded Wikipedia corpus"
2. "Promote hybrid retrieval with reranking"
3. "Audit the answer-checking judge"
4. "Bound and verify every answer"
5. next: "Reduce unnecessary refusals"

Also confirm: is "95%" acceptable in a public detail line (rounded from 0.9457 recall@5)? Default: yes.

## Q4 (non-blocking): rollout beyond RAG 01

After the RAG 01 pilot is reviewed, should the same section pattern and neutral roadmap roll out to projects 02–13 in a separate pass? Default: a separate design, after you review the RAG 01 pilot.

## Q5 (non-blocking): headline numbers in metrics.json

The final_v3 headline numbers (F1 0.9091, S3 recall@5 0.9457, faithfulness 0.8717) live in `experiment_log.json`, `retrieval_sweeps/` and `final_v3_e2e/metrics.json`. `reports/metrics.json` holds an older run. Should these be promoted into `reports/metrics.json` so the headline guard reads them directly? Default: keep the current per-artifact traceability and name the source in each claim.

## Q6 (non-blocking): cumulative spend

The $2.04 cumulative spend appears in the story only as history from `DESIGN.md` and `README.md`. Show it as current cost, or keep it as history only? Default: history only; the final pass spend is shown instead.

## Q7 (non-blocking): wide-screen card width

At 2560 px two columns are about 1,200 px wide each. Keep 2 columns and full width (default), add a 3-column layout at ≥1800 px, or cap the grid at a wider value? Decide after Q1.
