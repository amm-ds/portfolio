# Hillstrom email marketing (MineThatData)

- **Canonical source:** http://minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv
  (Kevin Hillstrom's MineThatData "E-Mail Analytics And Data Mining Challenge",
  March 2008; author's site. HTTPS serves a self-signed certificate, so the
  pinned fetch is HTTP — checksum verification is the integrity control.
  Documented mirror: [W-Tran/uplift-modelling on GitHub](https://github.com/W-Tran/uplift-modelling/blob/master/data/hillstrom/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv))
- **License/terms:** challenge dataset published by the author for research and
  benchmarking; widely redistributed by the uplift-modeling literature
  (scikit-uplift, causalml, causeinfer all ship loaders for it). No explicit
  license file — treat as research-use, attribute MineThatData/Hillstrom.
- **Used by:** Project 10 (retention uplift & experimentation)
- **Size:** 64,000 customers × 12 columns: recency, history_segment, history
  (prior-year spend), mens, womens, zip_code, newbie, channel, segment
  (Mens E-Mail / Womens E-Mail / No E-Mail), visit, conversion, spend.

## Snapshot policy

Fetched at prepare time via `portfolio_core.io.fetch` with the sha256 below
verified (loud failure on upstream drift); the prepared two-arm frame is
checksummed again into the DatasetContract. The experiment is a one-shot
randomized 2008 campaign — there is no fresher snapshot to track, so the
checksum gate only guards corruption/mirror drift.

| Field | Value |
|---|---|
| Snapshot date | 2026-10-16 |
| Format | CSV (single file, ~3.8 MB) |
| SHA-256 | `0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece` |
| Arms used | Mens E-Mail (treatment) vs No E-Mail (control); Womens E-Mail reported in EDA |

## Schema mapping (Project 10)

| Hillstrom column | Project column | Role |
|---|---|---|
| recency | recency | numeric feature (months since last purchase) |
| history | history / log_history | numeric feature + CUPED covariate (pre-period spend) |
| mens / womens | mens / womens | binary features (merchandise flags) |
| newbie | newbie | binary feature |
| channel | channel | categorical feature (Phone / Web / Multichannel) |
| zip_code | zip_code | categorical feature (kept verbatim, incl. the upstream `Surburban` typo) |
| segment | treatment | 1 = Mens E-Mail arm, 0 = No E-Mail arm |
| conversion | conversion | primary outcome (~0.9% base rate) |
| visit | visit | secondary outcome (~15% base rate) |
| spend | spend | secondary outcome (grounding for the conversion margin) |
