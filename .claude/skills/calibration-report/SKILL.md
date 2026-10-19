---
name: calibration-report
description: Calibration report for the backtest floor forecast vs bookmaker - reliability diagrams and ECE per outcome H/D/A, Murphy decomposition of the Brier score, and a paired bootstrap CI for the Brier and NLL gap. Use for calibration, reliability or thesis questions.
---

# Calibration Report

Thesis core metric set. Read-only over `Datacollection backtest/MD{NN}/prediction_weight_runs.csv`; uses the floor forecast (per-match mean over runs), actual results and overround-free BWIN probabilities on the same matches.

## When to Use

- Questions on calibration, reliability, ECE or Brier decomposition
- Before claiming the model is better or worse than the bookmaker
- Thesis figures

## Run

```bash
PY="C:/AI Projekt/.venv/Scripts/python.exe"
"$PY" .claude/skills/calibration-report/calibration_report.py --bins 10 --bootstrap 2000
```
Writes to `Sports Api Data/Testruns/Datacollection backtest/calibration_report/`: `calibration_summary.csv`, `reliability_bins.csv`, `reliability_diagram.png` (if matplotlib is installed).

## How to Read It

- Quantile bins: with ~300 matches, 10 bins means ~30 matches per bin; bin frequencies are noisy. Use `--bins 5` for the draw class.
- Brier = reliability − resolution + uncertainty (per outcome). Reliability is the calibration error; resolution is discrimination.
- The gap CI is paired over matches. If it contains 0, there is no demonstrated difference.
- Known structural issue: σ comes from in-sample residuals (homoscedastic), which tends to make probabilities overconfident. Look for this in the reliability curve.

## Output Format

```text
Matches: N over M matchdays
| Source | Brier | NLL | ECE H | ECE D | ECE A |
Model − bookie Brier: X [90 % CI a, b]; NLL: X [a, b]
Per outcome: reliability / resolution, model vs bookie
Interpretation: over-/underconfident where, and what it means for the thesis
```
