# Next Step After the Future-vs-Reference Comparison

## Context

The user predicted Bundesliga matchday 1388596–1388604 in future mode and just ran reference mode after those matches were played (2026-05-08 to 2026-05-10). The honest backfill is now possible. They want a neutral expert read on whether the future-mode ranker performed acceptably or if something structural needs to change — and what the next step should be.

## What the data actually says (the neutral read)

The future-mode ranker selected **RunID 52** as its top candidate. When all 200 candidate runs are scored against the now-known actual outcomes:

| Metric | Picked (RunID 52) | Best in hindsight (RunID 155) | All-runs mean |
|---|---|---|---|
| AvgNLL | 0.8337 | 0.7367 | 0.8020 |
| Accuracy | 66.7% (6/9) | 77.8% (7/9) | 67.2% |
| Rank (by NLL) | **177 / 200 (bottom 12%)** | 1 / 200 | – |

Three of the misses were confidently wrong (Augsburg vs M'gladbach 46.5% Away, Köln vs Heidenheim 47.3% Home, Mainz vs Union 50.1% Home — all flipped) — exactly the failure pattern a confidence-driven ranker is known to suffer.

## The structural concern is real but not yet proven

Tracing `AI_match_stats_prediction.py`:

- Future-mode `build_future_candidate_ranking` (line 1803) ranks using a blend of **surrogate-predicted NLL/Accuracy** (`Pred_AvgNLL`, `Pred_Accuracy` — extrapolated from a regressor trained on past reference-mode AvgNLL) and **confidence proxies** (`MeanTopProb`, `MeanProbGap`, `MeanEntropy`).
- All four signals measure *what the model thinks of itself*, not what is true. A confidently miscalibrated weight combination will score well on every one of these proxies and still be wrong.
- The surrogate is trained on weights → AvgNLL from past matches. It never sees match-level features. When extrapolating to a new matchday, it assumes "weights that worked before will work again" — which only holds if the matches are statistically similar.

This is a **well-known ML pitfall**: optimizing on proxies that aren't your real metric. Mathematically valid critique.

**But:** one matchday is N=1. A 177/200 rank could be unlucky on this specific matchday, not systematic failure. The ranker may be fine on average. We cannot honestly conclude "structurally broken" from a single data point — even a bad-looking one.

## Verdict

- **More runs alone will not fix this.** 200 candidates were already generated; the ranker still chose the bottom 12%. Bumping to 500 or 1000 doesn't change the proxy → reality mismatch.
- **More reference data will help indirectly** by giving the surrogate more training signal, but won't repair the proxy-vs-truth gap.
- **Don't restructure the ranker yet.** Diagnose first across multiple matchdays. Acting on N=1 risks fixing a non-problem and missing the real one.

## Recommended approach: diagnose, then act

### Step 1 — Cheap calibration diagnostic (under an hour)

On the existing 200-run data for this matchday, compute the correlation between each proxy and the actual outcome quality:

- `MeanTopProb` vs actual NLL — does high confidence track low NLL?
- `MeanProbGap` vs actual accuracy
- `MeanEntropy` vs actual NLL
- `Pred_AvgNLL` vs actual `AvgNLL` — does the surrogate get the *direction* right, even if not the magnitude?

If any of these correlations are near zero or negative, that proxy is actively misleading the ranker. If they're positive but weak, the ranker is noisy but not broken.

Files to inspect:
- [Datacollection future/prediction_weight_runs.csv](Sports%20Api%20Data/Testruns/Datacollection%20future/prediction_weight_runs.csv) — the 200 candidate predictions
- [Datacollection future/prediction_weight_run_summary.csv](Sports%20Api%20Data/Testruns/Datacollection%20future/prediction_weight_run_summary.csv) — per-run proxies and Pred_AvgNLL
- [Datacollection reference/prediction_weight_run_summary.csv](Sports%20Api%20Data/Testruns/Datacollection%20reference/prediction_weight_run_summary.csv) — newly backfilled actual NLL/Accuracy per run

### Step 2 — Multi-matchday ranker backtest (the real diagnosis)

For each played matchday in 2025–2026 (or a sample of 5–10 of them), simulate the full future-mode workflow:
1. Treat that matchday as "the future" — exclude its data from training
2. Run the candidate generation + ranker as if predicting before kickoff
3. Record the rank of the top-picked candidate against the actual best (in hindsight) for that matchday
4. Aggregate: distribution of ranker quality across many matchdays

If the median rank is in the top half of candidates → the ranker is fine, this matchday was unlucky.
If the median is consistently in the bottom half → structural fix needed.

No code changes required for this diagnostic, just analysis scripts.

### Step 3 — Act based on what the diagnostic shows

- **If proxies don't correlate with truth (Step 1):** down-weight or drop those proxies in `build_future_candidate_ranking` (around line 1826–1844). Re-weight the blends toward whichever proxy actually tracks accuracy.
- **If the ranker is systematically poor (Step 2):** switch the top-1 pick to a **top-K ensemble** — average the predictions of the top 5–10 candidates by surrogate score. This is robust against a single bad pick and is the standard fix in similar ML setups.
- **If both diagnostics look OK:** collect more data (expand `match_results_references.csv` to 30–50 matches across multiple matchdays) and re-run. The single bad matchday was noise.

## Critical files referenced (for the eventual code change, not yet)

- [Sports Api Data/Testruns/Code/AI_match_stats_prediction.py](Sports%20Api%20Data/Testruns/Code/AI_match_stats_prediction.py)
  - `build_future_candidate_ranking` (around line 1803) — ranker logic
  - `select_candidates_with_surrogate` (around line 2212) — Pareto selection
  - `train_surrogate_model` / surrogate scoring (around lines 2191–2202, 2400–2410)
  - `SURROGATE_*` constants (lines 77–81)

## Verification

For Step 1: produce a small table of correlations (proxy vs actual NLL, proxy vs actual accuracy) over the 200 runs. Anything with |r| < 0.15 is a candidate for removal from the ranker.

For Step 2: produce a per-matchday "picked rank" distribution. Acceptable: median rank ≤ 50th percentile of candidates. Problematic: median rank > 70th percentile.

For Step 3 (if it activates): re-run the future-vs-reference comparison on a fresh matchday once one is played and confirm the picked candidate's actual NLL is closer to the hindsight best.

## What this plan does NOT do

- It does not change the ranker yet. The 177/200 result is alarming but not conclusive evidence of structural failure.
- It does not bump MAX_RUNS. More runs won't fix a proxy mismatch.
- It does not add an ensemble blindly. Ensemble helps only if Step 2 confirms the ranker has a systematic problem.
