---
name: eval-dixon-coles
description: Evaluate the Dixon-Coles outcome mapping (full remap and draw-ratio variant) over all base backtest matchdays, and rebuild the per-matchday Dixon-Coles files. Use for Dixon-Coles, Poisson score-grid or rho questions.
---

# Evaluate Dixon-Coles

Dixon-Coles only remaps BART's saved expected goals to H/D/A, so everything is recomputed exactly from `MD{NN}/prediction_weight_runs.csv`. No BART, no memory issues. Parameters used in the MD8/MD18 runs: scale 1.05, rho -0.2, max_goals 10.

## When to Use

- Deciding between `normal`, `score_dixon_coles` and `score_dixon_coles_draw_ratio`
- After new base matchdays were added to the backtest
- Before refreshing the dashboard (it imports `build_frames` from `build_dixon_coles_backtest.py`)

## Run

```bash
PY="C:/AI Projekt/.venv/Scripts/python.exe"
cd "Sports Api Data/Testruns/Code"
"$PY" eval_dixon_coles_all.py              # full remap, H/D/A from the score grid
"$PY" eval_dixon_coles_draw_ratio_all.py   # Dixon-Coles draw level, BART's H:A ratio kept
"$PY" build_dixon_coles_backtest.py        # writes per-MD files + season file into Datacollection backtest/
```

## How to Read It

- Compare per outcome. Full Dixon-Coles tends to change H/A as well; the draw-ratio variant isolates the draw level.
- Changing rho or scale and re-evaluating on the same matchdays is in-sample tuning. Say so if it happens, and prefer leave-one-matchday-out.

## Output Format

```text
| Mode | NLL H | NLL D | NLL A | Total | vs base | vs bookie |
Params: scale, rho, max_goals   Matches: N
Recommendation with the guardrail: does D improve without H/A getting worse?
```
