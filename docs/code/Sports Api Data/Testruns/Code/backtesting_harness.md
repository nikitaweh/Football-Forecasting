# Backtesting Harness — Implementation Summary

**Date:** 2026-05-27
**Scope:** Off-season tooling to evaluate the prediction pipeline on historical matchdays with strict no-leakage controls, plus a real bookmaker baseline for honest scoring.

---

## Why this was built

After the 2025/26 Bundesliga season ended, we had only two matchdays of honest evaluation data (MD33 good, MD34 poor). That was not enough to answer the structural questions that had built up:

- Is the future-mode ranker systematically picking poorly, or was MD34 just unlucky?
- Is the new player-base implementation actually helping?
- Are some weight combinations consistently better across matchdays, or does each matchday have its own optimum?

The pipeline had no way to ask: **"predict matchday N using only data from before matchday N, then score against the actual outcome."** Building that capability is what unlocks every downstream improvement: each fix can now be measured against a stable, leakage-free baseline.

---

## What was added or changed

### 1. New config knobs in [AI_match_stats_prediction.py](../../../../Sports%20Api%20Data/Testruns/Code/AI_match_stats_prediction.py)

Three environment-variable overrides were added so the driver can parameterise each per-matchday invocation without editing the source file. All three default to `None`/off, leaving production behaviour untouched.

| Env var | Effect | Default |
|---|---|---|
| `BACKTEST_DATE_CUTOFF` | Strips all matches with `MatchDate >= cutoff` from the training set. The leakage guard: when backtesting MD15, the model cannot see MD16+. | not set |
| `MAX_RUNS_OVERRIDE` | Caps BART weight-sample runs per matchday. Backtests use 50 so each matchday finishes in hours instead of half a day. | not set (uses file's `MAX_RUNS = 200`) |
| `MATCH_STATS_MODE_OVERRIDE` | Forces `predicted` for the match-stats layer regardless of `PREDICTION_MODE`. Without this, reference mode defaults to `actual` stats, which would leak post-match information into the outcome model. | not set |

Code locations:
- `BACKTEST_DATE_CUTOFF` parsing near the top of the file (line ~27)
- Training-set filter near the end (line ~2350): `train_df = train_df[pd.to_datetime(train_df['MatchDate'], errors='coerce') < BACKTEST_DATE_CUTOFF].copy()`
- `MAX_RUNS_OVERRIDE` next to the `MAX_RUNS = 200` constant
- `MATCH_STATS_MODE_OVERRIDE` immediately after the existing `MATCH_STATS_MODE` line

### 2. New driver: [backtest_matchdays.py](../../../../Sports%20Api%20Data/Testruns/Code/backtest_matchdays.py)

Walks the season's played matchdays and runs the main pipeline once per chosen matchday with the appropriate env overrides. Per matchday it:

1. Reads `Stammdaten_78.csv` to look up the matchday's fixtures and earliest match date.
2. Writes those fixtures to `Datacollection reference/match_results_references.csv` (the existing reference-mode input file).
3. Sets `BACKTEST_DATE_CUTOFF` to the matchday's earliest date, plus `MAX_RUNS_OVERRIDE` and `MATCH_STATS_MODE_OVERRIDE`.
4. Invokes `AI_match_stats_prediction.py` as a subprocess.
5. Copies `prediction_weight_runs.csv`, `prediction_weight_run_summary.csv`, and `pareto_front.csv` from the live reference output folder into `Datacollection backtest/MD{N}/`, plus a small `meta.txt`.

CLI:
```
python backtest_matchdays.py --all
python backtest_matchdays.py --matchdays 5 10 15 20 25 30
python backtest_matchdays.py --random 8 --seed 42
python backtest_matchdays.py --random 8 --max-runs 50 --match-stats-mode predicted
```

The driver is **resumable**: if `MD{N}/prediction_weight_run_summary.csv` already exists, that matchday is skipped on the next invocation. Useful when the laptop sleeps mid-sweep.

**Side effect to be aware of:** the driver overwrites `match_results_references.csv` on every iteration. After a sweep, that file will contain the last processed matchday's fixtures. The pipeline's existing idempotent backfill skip (the earlier change at line ~1228 of the main script) ensures this doesn't cause data corruption — it just means the live reference folder won't reflect any one specific matchday cleanly after a sweep.

### 3. New aggregator: [analyze_backtest_results.py](../../../../Sports%20Api%20Data/Testruns/Code/analyze_backtest_results.py)

Reads every `Datacollection backtest/MD{N}/` folder and emits a season-level report plus `Datacollection backtest/season_summary.csv`. Reports include:

- **Per-matchday performance** — best/mean NLL and accuracy, per-matchday baseline NLL, gap-vs-bookie, and beats-bookie flag.
- **Per-match head-to-head** — across all backtested matchdays, how often the best model run beats the bookmaker on individual matches.
- **Hardest matchdays** — bottom decile by best-NLL.
- **Weight stability** — mean/std/CV of each weight across each matchday's best-run weight vector. Low std = consistent across matchdays (robust signal); high std = matchday-dependent (possible overfitting).
- **Surrogate calibration** — per-matchday Pearson correlation of `Pred_AvgNLL` vs actual `AvgNLL`. Direct test of whether the surrogate ranks candidates correctly.

### 4. Aggregator upgrade: real bookmaker odds as baseline

The first version of the aggregator used a synthetic Bundesliga-historical prior (45% Home / 25% Draw / 30% Away) as the per-matchday baseline. This was a weak bar — every matchday trivially beat it because the model has *some* predictive signal.

After the BWIN historical odds file landed in [BWIN Odds/Datacollection/](../../../../Sports%20Api%20Data/Testruns/BWIN%20Odds/Datacollection/), the aggregator was switched to compute the real bookmaker NLL per match. The math:

1. For each match: `p_raw = 1 / decimal_odd` for H/D/A.
2. Normalise to remove the bookmaker's overround: `p = p_raw / (p_H_raw + p_D_raw + p_A_raw)`.
3. Per-match NLL: `-ln(p_actual)`.
4. Matchday baseline: average per-match NLL across the matchday's 9 fixtures.

The aggregator auto-selects the most recent `bwin_historical_odds_*.csv` from the odds folder. If a match has no odds entry, it falls back to the naive prior for that match (current coverage: 100%).

`season_summary.csv` columns now include `BookieNLL`, `GapVsBookie`, `BeatsBookie`, `MatchesBeatingBookie`, `MatchesCompared` — replacing the old `BaselineNLL` and `NLLBeatsBaseline`.

---

## Findings from the first 8-matchday sweep

Sweep: `--random 8 --seed 42 --max-runs 50 --match-stats-mode predicted`. Matchdays sampled: **MD2, MD4, MD5, MD8, MD18, MD24, MD31, MD34**. ~3.5 hours of wall-clock compute per matchday under the predicted-stats path (one-time GBR layer + 50 BART runs).

### Against the real bookmaker baseline

| Metric | Value |
|---|---|
| Matchdays beating bookmaker | **6 / 8** (MD2 narrow loss; MD18 decisive loss) |
| Per-match head-to-head | **42 / 72 (58.3%)** of matches won by best run |
| Mean per-match gap (model − bookie) | **−0.058 NLL** (negative = model better) |
| Best matchday | MD8 (6H/0D/3A): −0.156 vs bookie, 7/9 per-match wins |
| Worst matchday | MD18 (3H/**5D**/1A): +0.120 vs bookie, 2/9 per-match wins |

The model has **real but modest alpha** over the market — clearly positive on average, but the edge is small enough that ranker quality matters a lot.

### Structural findings

1. **Player base is real signal.** `Player_AbsencePenaltyDiff` is among the most stable best-run weights across matchdays (mean 1.34, CV 0.28). The optimiser converges on similar values regardless of the matchday, which is exactly what a useful feature should do.

2. **Weather Rain/Snow are noise.** Highest CV of any weights (Snow CV 0.78, Rain CV 0.62). The optimiser cannot pin them down — likely because rain/snow events are rare. Candidates for regularisation or removal.

3. **Surrogate is structurally weak.** Across the 6 matchdays where it was active (MD2, MD4 were too early for it to engage):

| Matchday | Pearson r (Pred_AvgNLL vs actual AvgNLL) |
|---|---|
| MD8 | +0.45 |
| MD5 | +0.17 |
| MD18 | +0.06 |
| MD24 | ≈0 |
| MD31 | **−0.14** |
| MD34 | −0.07 |
| **Mean** | **+0.078** |

Half the matchdays are near-zero or negative. The earlier "ranker picked 177/200" anecdote from MD34 is consistent with a ranker that on average barely outperforms random selection.

4. **Draws are the most concrete failure mode.** MD18 had 5 draws and was the worst matchday by every metric. The model's GoalDiff → outcome conversion assigns draws low probability by construction.

### Cold-start observation

The surrogate requires `SURROGATE_MIN_HISTORY = 100` runs. Early-season backtests (MD2, MD4 in this sample) had `BACKTEST_DATE_CUTOFF` set so early that the run-history file did not meet that threshold. `Pred_AvgNLL` was all-NaN for those matchdays, and the ranker silently fell through to the confidence-only path. So **early-season backtests cannot be used to evaluate surrogate calibration** — only mid-and-late-season ones.

---

## How to use the harness going forward

### Reproduce these findings
```
python backtest_matchdays.py --random 8 --seed 42 --max-runs 50 --match-stats-mode predicted
python analyze_backtest_results.py
```

### Expand to the full season (~3 days of compute, leave running)
```
python backtest_matchdays.py --all --max-runs 50 --match-stats-mode predicted
python analyze_backtest_results.py
```

### Test a code change end-to-end

1. Implement the change.
2. Delete the matchdays you want to re-evaluate: `rm -rf "Sports Api Data/Testruns/Datacollection backtest/MD0X"` for any subset.
3. Re-run the driver — only deleted matchdays are recomputed (resumable behaviour).
4. Re-run the aggregator and compare `season_summary.csv` before/after.

### Outputs
- `Datacollection backtest/MD{N}/` — per-matchday outputs (4 files each).
- `Datacollection backtest/season_summary.csv` — one row per matchday with all the new bookie-baseline columns.
- `Datacollection backtest/_archive_*` — folders prefixed with `_` are ignored by the aggregator; useful for stashing old runs without losing them.

---

## Open items

Concrete, ranked by leverage as of this writing:

1. **Fix the surrogate** — biggest leverage on future-mode ranker quality. Options ranged from simplest (drop the surrogate, use confidence fallback only) to most involved (replace with a different model class or feature set).
2. **Improve draw prediction** — directly attacks MD18-style failure mode. Possible angle: explicit draw-probability head instead of deriving draws from GoalDiff band.
3. **Expand sweep to all 34 matchdays** — firms up the N=8 conclusions before any structural change. ~3 days of compute.
4. **Investigate weather Rain/Snow noise** — drop or regularise if they're not earning their weight.

The harness exists to measure each of these — the next change should be implemented, re-run through `backtest_matchdays.py`, and compared against this run's `season_summary.csv` to see whether the per-match gap and per-matchday win count improved.
