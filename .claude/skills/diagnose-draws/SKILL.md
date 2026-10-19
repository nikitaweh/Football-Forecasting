---
name: diagnose-draws
description: Diagnose draw-prediction quality (calibration vs discrimination), test the constant draw recalibration (c ≈ 1.35), probe for draw signals, and compare draw modes. Use for anything about draws, DrawProb or the draw NLL.
---

# Diagnose Draws

Draws are the documented weak spot (NLL ~1.61 vs ~0.59 for home wins). These scripts separate two questions: is the draw *level* wrong (calibration), or can the model not tell *which* matches draw (discrimination)?

## When to Use

- Any question about draw probabilities or the recalibration factor
- Before shipping a draw mode for the live season
- After new matchdays were added

## Run (read-only, saved runs only)

```bash
PY="C:/AI Projekt/.venv/Scripts/python.exe"
cd "Sports Api Data/Testruns/Code"
"$PY" diagnose_draws.py        # calibration vs discrimination; c scan in-sample and leave-one-matchday-out
"$PY" probe_draw_signal.py     # ROC-AUC draw vs non-draw per signal, incl. bookie; bootstrap 90 % CI
"$PY" compare_draw_modes.py --matchdays 8 18   # base vs draw-mode folders, per outcome, vs bookie
```

## New draw-mode runs (needs BART, ask first)

```bash
"$PY" backtest_draw_modes.py --matchdays 8 18 --max-runs 50
```
Writes timestamped `MD{NN}_{mode}_..._{YYYYMMDD_HHMMSS}/` folders; base folders are never overwritten.

## How to Read It

- Use the leave-one-matchday-out c, not the in-sample optimum.
- If the bookie's draw AUC is itself near 0.5, draw discrimination is close to unforecastable; a level fix is the realistic ceiling.
- Accept a draw change only if D improves and H/A do not get worse.

## Output Format

```text
Calibration: mean DrawProb X vs observed draw rate Y (N matches)
Discrimination: AUC model X [CI], bookie Y [CI]
Recalibration: c_LOMO = X, total NLL change X, per outcome H/D/A changes
Verdict
```
