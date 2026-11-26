#!/usr/bin/env bash
# E7 live repeats driver (2026-11-26): 5 identical live runs of the 19-task
# held-out suite against the hosted kimi-for-coding endpoint, same runner and
# grading as reports/live_confirmation_20261119 (see its README), plus a
# per-run hard budget stop for the experiment's $1.50 total cap.
#
# Usage (from the project directory):  bash reports/live_repeats_20261126/run_repeats.sh
set -euo pipefail

cd "$(dirname "$0")/../.."                   # projects/09-agentic-workflows
set -a && . ../../.env && set +a             # repo-root .env (never printed)

# Hard-stop arithmetic: never start a run when cumulative spend could cross
# $1.50 after one more $0.40-capped run. The cap is an abort threshold only;
# the reference run spent $0.094, so $0.40 is ~4x headroom and never binds.
export LLM_SUITE_COST_LIMIT_USD=0.40
MAX_RUNS=5
STOP_BEFORE_USD=1.10

OUT=reports/live_repeats_20261126
cumulative="0"

for i in $(seq 1 "$MAX_RUNS"); do
  stop=$(python3 -c "print(1 if float('$cumulative') >= $STOP_BEFORE_USD else 0)")
  if [ "$stop" = "1" ]; then
    echo "STOP: cumulative estimated spend \$$cumulative >= \$$STOP_BEFORE_USD before run $i (hard \$1.50 budget)"
    break
  fi
  mkdir -p "$OUT/run$i"
  echo "=== run $i — $(date -u +%H:%M:%S) ==="
  uv run python -m agentic_workflows.cli run-all --heldout \
    --records-path "$OUT/run$i/heldout_live_records.json" 2>&1 | tee "$OUT/run$i/run.log"
  spend=$(grep -oE 'estimated spend \$[0-9.]+' "$OUT/run$i/run.log" | tail -1 | grep -oE '[0-9.]+')
  cumulative=$(python3 -c "print(float('$cumulative') + float('${spend:-0}'))")
  echo "run $i estimated spend: \$${spend:-unknown} (cumulative \$$cumulative)"
  echo '{}' > "$OUT/run$i/metrics.json"
  uv run python -m agentic_workflows.cli evaluate --heldout \
    --records-path "$OUT/run$i/heldout_live_records.json" \
    --reports-dir "$OUT/run$i" 2>&1 | tee -a "$OUT/run$i/run.log"
  mv "$OUT/run$i/metrics.json" "$OUT/run$i/live_grading_metrics.json"
done
echo "ALL RUNS DONE — cumulative estimated spend: \$$cumulative"
