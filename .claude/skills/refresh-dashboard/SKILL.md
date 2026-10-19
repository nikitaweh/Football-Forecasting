---
name: refresh-dashboard
description: Rebuild the data behind the R Shiny dashboard (build_dashboard_data.py) and the website data files (website/build_data.py, build_data_international.py). Use after backtests, new results or new mode folders. Does not upload anything to Hostinger.
---

# Refresh Dashboard and Website Data

Presentation only: these scripts reuse existing metric code, so they never define new numbers.

## When to Use

- After `run-backtest`, `eval-dixon-coles`, `backtest_draw_modes.py` or `update-results`
- When the dashboard or website shows stale numbers

## Run

```bash
PY="C:/AI Projekt/.venv/Scripts/python.exe"
"$PY" "Sports Api Data/Testruns/Code/build_dashboard_data.py"   # -> dashboard/data/*.csv + manifest.json
"$PY" website/build_data.py                                      # -> website/data.js
"$PY" website/build_data_international.py                        # -> website/data.international.js
```
`website/refresh_data.py` is the scheduled, hash-gated version for Windows Task Scheduler; run it manually only to test the schedule.

## Checks

- `dashboard/data/manifest.json`: `generated_at` updated, coverage counts plausible (matchdays, modes).
- Compare one headline number (e.g. season median NLL) with `season_summary.csv`; they must match.
- Do not upload. Deployment to Hostinger is a separate step and goes through the `security` agent first.

## Output Format

```text
Dashboard: N files written, coverage: X matchdays, Y modes
Website: data.js (N matches), data.international.js (N matches)
Spot check: [metric] dashboard X = source X
```
