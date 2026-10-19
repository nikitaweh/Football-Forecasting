---
name: run-backtest
description: Run the honest reference+predicted matchday backtest with backtest_matchdays.py and aggregate it with analyze_backtest_results.py. Manual only, because a run takes hours of BART fitting.
disable-model-invocation: true
---

# Run Backtest

Historical matchday backtest: for each target matchday the driver writes that matchday's fixtures to `match_results_references.csv`, sets `BACKTEST_DATE_CUTOFF` to its first kickoff, runs `AI_match_stats_prediction.py` and copies outputs to `Datacollection backtest/MD{NN}/`.

## When to Use

- After a change to the pipeline that must be validated out of sample
- To extend the backtest to new matchdays

Not for comparing outcome-probability modes on saved runs: use `compare-vs-bookie`, `eval-dixon-coles` or `diagnose-draws` (no BART needed).

## Before Running

1. Back up the active reference file. The driver overwrites it on every matchday:
   ```bash
   cp "Sports Api Data/Testruns/Datacollection reference/match_results_references.csv" \
      "Sports Api Data/Testruns/Datacollection reference/match_results_references.csv.bak"
   ```
2. Confirm with Nikita: matchdays, `--max-runs`, expected duration. Existing `MD{NN}/` folders with a run summary are skipped (resumable).
3. Use `--match-stats-mode predicted` (default). `actual` leaks post-match stats and is only a diagnostic.

## Run

```bash
PY="C:/AI Projekt/.venv/Scripts/python.exe"
cd "Sports Api Data/Testruns/Code"
"$PY" backtest_matchdays.py --matchdays 5 10 15 --max-runs 50 --match-stats-mode predicted
#   or --all | --random 8 --seed 42
"$PY" analyze_backtest_results.py
```
Run long jobs in the background and report progress per matchday.

## After Running

Restore the reference file from the `.bak` copy, then report.

## Output Format

```text
Matchdays: [list]  Runs per MD: N  Match-stats mode: predicted
Median AvgNLL across runs: model X.XXX | bookie X.XXX | gap +X.XXX
Beat rate vs bookie (median basis): XX % of matchdays
Per-outcome NLL (H/D/A): ...
Spread: IQR of AvgNLL per matchday; matchdays with unusual variance
Caveat: 9 matches per matchday, so differences under ~0.05 NLL are within noise unless the CI says otherwise
```
Source: `Datacollection backtest/season_summary.csv` and the printed report. Never headline the best run.
