---
name: compare-vs-bookie
description: Compare the model's outcome-probability variants against bookmaker odds (overround removed) on saved backtest runs, per outcome H/D/A. Use for "are we better than the bookie", beat rate, NLL gap, or World Cup vs bet365.
---

# Compare vs Bookie

Post-hoc and cheap: both scripts recompute every variant from the saved expected goals and base probabilities in `MD{NN}/prediction_weight_runs.csv`. No BART runs.

## When to Use

- After a backtest, to get the model vs. bookmaker verdict
- When asked about edge, beat rate or NLL gap
- International: World Cup 2026 matches vs bet365

## Run

```bash
PY="C:/AI Projekt/.venv/Scripts/python.exe"
cd "Sports Api Data/Testruns/Code"
"$PY" compare_models_vs_bookie.py      # Bundesliga, BWIN, variants: base, dixon_full a=1.0/0.4, dixon_draw_ratio, poisson_draw_ratio
"$PY" compare_worldcup_vs_bookie.py    # International, bet365
```

## How to Read It

- The deployable forecast is the floor: per-match mean of probabilities over runs.
- Bookmaker probabilities are 1/odds normalised to sum to 1 (overround removed).
- A variant only counts as better if it improves total NLL **and** does not degrade H or A noticeably (guardrail).
- Current project status for reference: parity, ~50 % beat rate, mean NLL gap near 0. A new claim of "edge" needs a CI that excludes 0 (use `calibration-report` for the paired bootstrap).

## Output Format

```text
| Variant | NLL H | NLL D | NLL A | NLL total | Gap vs bookie |
Matches: N  Matchdays: M
Verdict: [parity / better / worse], with the uncertainty stated
```
