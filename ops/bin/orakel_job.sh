#!/usr/bin/env bash
# orakel_job.sh <job>  --  every scheduled VPS job goes through here.
#
# Jobs (each started by ops/systemd/orakel-<job>.timer):
#   collect-daily        fixtures, injuries, weather for Bundesliga; fixtures + injuries for FIFA/UEFA
#   predict-bundesliga   kickoff guard -> fresh pre-match data -> odds snapshot -> prediction -> website
#   predict-international kickoff guard -> fresh fixtures -> international model
#   postmatch            match/player stats + lineups, results reference, historical odds, dashboard data
#   website-refresh      rebuild data.js if its sources changed and publish it to the web root
#
# Every job except website-refresh takes the shared pipeline lock, so two jobs never write
# the same CSVs at once (e.g. postmatch vs. prediction on match_results_references.csv).
# Exit code != 0 makes systemd start orakel-notify@<unit>.service (WhatsApp alert).
set -euo pipefail

JOB=${1:?usage: orakel_job.sh <job>}
ROOT=${KI_PROJECT_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${ORAKEL_PYTHON:-$ROOT/.venv/bin/python}
SAD="$ROOT/Sports Api Data"
export KI_PROJECT_ROOT=$ROOT PYTHONUNBUFFERED=1

log() { echo "[$JOB] $*"; }

with_lock() {
  local lock_dir=${ORAKEL_LOCK_DIR:-/run/lock/orakel}
  mkdir -p "$lock_dir"
  exec 9>"$lock_dir/pipeline.lock"
  if ! flock -w "${ORAKEL_LOCK_WAIT:-10800}" 9; then
    log "pipeline lock not free after ${ORAKEL_LOCK_WAIT:-10800}s -- giving up"
    exit 75
  fi
}

# Exit 10 from the guard means "nothing to do": end the job successfully.
guard() {
  local rc=0
  "$PY" "$ROOT/ops/bin/kickoff_guard.py" "$1" \
    --window-hours "${ORAKEL_WINDOW_HOURS:-36}" --min-lead-hours "${ORAKEL_MIN_LEAD_HOURS:-3}" || rc=$?
  if [ "$rc" -eq 10 ]; then exit 0; fi
  return "$rc"
}

bundesliga() { "$PY" "$SAD/Bundesliga/Code/bundesliga_combined_pipeline_78.py" "$@"; }
international() {
  "$PY" "$SAD/International/FIFA/Code/pipeline.py" "$@"
  "$PY" "$SAD/International/UEFA/Code/pipeline.py" "$@"
}

case "$JOB" in
  collect-daily)
    with_lock
    bundesliga --steps fixtures injuries weather --continue-on-error
    international --steps fixtures injuries --continue-on-error
    ;;

  predict-bundesliga)
    with_lock
    guard bundesliga
    bundesliga --steps fixtures injuries lineups weather --continue-on-error
    "$PY" "$SAD/Testruns/BWIN Odds/Code/bwin_upcoming_odds_download.py" \
      || log "odds snapshot failed -- prediction continues without a fresh benchmark"
    # future + predicted is the only leakage-safe live combination (future + actual is blocked).
    MATCH_STATS_MODE_OVERRIDE=predicted "$PY" "$SAD/Testruns/Code/AI_match_stats_prediction.py"
    # Keep every published table: a later run must never silently replace what was live.
    out="$SAD/Testruns/Datacollection future"
    mkdir -p "$out/archive"
    cp "$out/future_outcome_table.csv" "$out/archive/future_outcome_table_$(date +%Y%m%d_%H%M%S).csv"
    "$PY" "$ROOT/website/refresh_data.py"
    ;;

  predict-international)
    with_lock
    guard international
    international --steps fixtures injuries lineups --continue-on-error
    "$PY" "$SAD/International/Code/AI_international_competitive_prediction.py"
    ;;

  postmatch)
    with_lock
    bundesliga --steps fixtures matchstats playerstats lineups --continue-on-error
    international --steps fixtures matchstats playerstats lineups --continue-on-error
    "$PY" "$SAD/Testruns/Code/update_match_results_references.py"
    "$PY" "$SAD/Testruns/BWIN Odds/Code/bwin_historical_odds_download.py" \
      || log "historical odds download failed"
    "$PY" "$SAD/Testruns/Code/build_dashboard_data.py"
    "$PY" "$ROOT/website/refresh_data.py"
    ;;

  website-refresh)
    "$PY" "$ROOT/website/refresh_data.py"
    ;;

  *)
    echo "unknown job: $JOB" >&2
    exit 2
    ;;
esac
log "done"
