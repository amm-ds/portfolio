# Telco churn (IBM sample)

- **Canonical source:** https://github.com/IBM/telco-customer-churn-on-icp4d
  (raw CSV: `data/Telco-Customer-Churn.csv`, pinned by sha256 in Project 05's
  config; the HF id `julien-c/telco-churn` cited in earlier planning does not
  exist — this repo is the documented fallback)
- **License/terms:** IBM sample data — free to use for demonstration and
  research per IBM's sample-data terms; fictitious customers, no PII.
- **Used by:** Project 05 (churn modeling — real-data primary track)
- **Size:** 7,043 customers × 21 columns (demographics, services, account,
  churn label); base churn rate 26.5%.

## Snapshot policy

Fetched at prepare time via `portfolio_core.io.fetch` with the sha256 below
verified; the prepared frame is checksummed again into the DatasetContract.
The project's synthetic generator remains as the clearly-labeled CI path
(`data_source: synthetic`), so tests never touch the network.

| Field | Value |
|---|---|
| Snapshot date | 2026-10-15 |
| Format | CSV (single file) |
| SHA-256 | `16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91` |
| Split used | stratified 80/20 → 5,634 train / 1,409 holdout |

## Schema mapping (Project 05)

| Telco column | Project column | Role |
|---|---|---|
| tenure | tenure_months | numeric feature |
| MonthlyCharges | monthly_charges | numeric feature |
| Contract | contract | categorical feature + fairness slice |
| InternetService | internet_service | categorical feature |
| gender | gender | fairness slice |
| SeniorCitizen | senior_citizen | fairness slice |
| Churn | churned | target |
| TotalCharges | — | dropped (blank rows; derivable from tenure × monthly charges) |
