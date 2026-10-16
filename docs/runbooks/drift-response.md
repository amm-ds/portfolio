# Runbook — model/data drift response

**Applies to:** all projects. **Severity guide:** eval-metrics regression >10%
relative on a fixed holdout = incident.

## Detect

- Scheduled eval re-run (`dvc repro evaluate`) compares against the pinned
  baseline metrics in the project's `reports/metrics.json`.
- Project 07's drift observatory (`.github/workflows/drift-observatory.yml`)
  scores every newly published TLC month against the pinned serving model and
  opens an issue when the relative MAE regression exceeds tolerance; reports
  land in `projects/07-open-data-mobility/reports/drift/`.
- DQ gates (`DQReport`) failing where they previously passed signals upstream
  schema drift (dataset cards pin the expected snapshot — check for source
  changes first).

## Respond

1. **Freeze.** Do not retrain on drifted data until the cause is classified.
2. **Classify.**
   - *Data drift:* source schema/values changed → check the dataset card URL and
     checksum; if the source published a new snapshot, pin a new snapshot
     (update card: date + checksum) and treat as a data refresh.
   - *Concept drift:* features stable, relationship degraded → schedule
     retraining with the time-CV splitter; review feature set.
3. **Rollback.** Re-run `dvc repro` from the last good commit — every stage is
   deterministic given pinned inputs.
4. **Record.** Note the drift, cause, and action in the project's DESIGN.md
   changelog section.

## Prevent

- Repro-time checksum verification (prepare stages fail loudly).
- Time-based CV everywhere a temporal split matters — random splits mask drift.
