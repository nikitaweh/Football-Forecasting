# ORAKEL Performance Dashboard (R Shiny)

A live, auto-refreshing dashboard for the ORAKEL prediction models. It shows
**Bundesliga** backtest performance across every matchday **and** across every
mode / finetuning variant we've tried, plus the **International** model — so
statistical analysis is a glance instead of a script run.

## Quick start

```powershell
# one-click: installs packages (first run), refreshes data, opens the app
dashboard\run_dashboard.ps1
```

Then open <http://127.0.0.1:4849> (it launches automatically).

Prerequisite: **R** (installed via `winget install RProject.R`). The launcher
finds Rscript, installs the needed CRAN packages into your user library on first
run, and uses the project's Python venv to build the data.

## How it works (two layers)

```
 source CSVs ──▶ build_dashboard_data.py ──▶ dashboard/data/*.csv ──▶ app.R (Shiny)
 (backtest folders,   (reuses existing             (tidy, dashboard-       (reads + plots,
  match results,       analysis modules:            ready tables)           auto-reloads)
  BWIN odds,           analyze_backtest_results,
  intl validation)     compare_draw_modes)
```

1. **`Sports Api Data/Testruns/Code/build_dashboard_data.py`** — the data layer.
   It does **not** invent metrics; it reuses `analyze_backtest_results.py`
   (NLL / accuracy / bookie gap / ensemble) and `compare_draw_modes.py`
   (per-outcome H/D/A NLL) and writes tidy CSVs into `dashboard/data/`.
2. **`app.R` + `R/`** — the Shiny app reads those CSVs with `reactiveFileReader`,
   so it reloads the instant they change.

## Auto-refresh

While the app runs it polls the source folders (~10 s). When it sees **new
outcome data** (e.g. `match_results_references.csv` updated) or a **new mode
folder** (`MD08_..._50runs_...`), it re-runs the exporter and the charts update —
no restart. Toggle this with **Auto-refresh** in the sidebar, or hit
**Refresh now**. The *Status* tab shows the manifest and refresh log.

## Tabs

| Tab | What you see |
|-----|--------------|
| **Season curve** | NLL & accuracy per matchday, model vs BWIN bookie; KPI cards; markers where the model beats the bookie. |
| **Mode comparison** | For matchdays with variants: best NLL/accuracy per mode, the per-outcome H/D/A guardrail, and a sortable table. |
| **Run spread** | Box plots of every run's NLL/accuracy per matchday — the spread of finetuning. |
| **International** | NLL/accuracy by competition, outcome mix, probability calibration (reliability). |
| **Status** | Data manifest, fingerprints, refresh log, matchday coverage. |

## Files

```
dashboard/
  app.R                 Shiny UI + server
  R/theme.R             minimal/clean/modern bslib + plotly theme
  R/load_data.R         paths, change detection, exporter trigger, CSV readers
  R/plots.R             plotly chart helpers
  data/                 tidy CSVs (written by the exporter)
  install_packages.R    installs CRAN deps into the user library (idempotent)
  run_dashboard.ps1     launcher
```

## Manual commands

```powershell
# rebuild the data only
& "Supportdateien\.venv\Scripts\python.exe" "Sports Api Data\Testruns\Code\build_dashboard_data.py"

# run the app only (from repo root)
$rs = "C:\Program Files (x86)\R\R-4.6.1\bin\x64\Rscript.exe"
$env:R_LIBS_USER = "$env:LOCALAPPDATA\R\win-library\4.6"
& $rs -e "shiny::runApp('dashboard', port = 4849, launch.browser = TRUE)"
```
