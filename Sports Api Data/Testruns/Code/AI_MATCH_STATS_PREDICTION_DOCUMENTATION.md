# AI Match Stats Prediction Documentation

## Purpose

`AI_match_stats_prediction.py` adds a separate match-stats prediction layer in
front of the existing weighted BART outcome model.

The script still predicts:

```text
GoalDiff = HomeGoals - AwayGoals
```

and then converts that into:

- `WinProb`
- `DrawProb`
- `LoseProb`
- `PredictedResult`
- an estimated scoreline

The key difference is that future mode no longer depends on unknown
current-match statistics.

## Modes

### `PREDICTION_MODE`

- `future`: predict upcoming unplayed matches
- `reference`: predict matches from `match_results_references.csv`

### `MATCH_STATS_MODE`

- `actual`: use real current-match stats directly
- `predicted`: predict current-match stats from pre-match information only
- `off`: remove current-match stats from the outcome model

Recommended usage:

- `future` + `predicted`
- `reference` + `actual` for standard evaluation
- `reference` + `predicted` for honest end-to-end backtesting

`future` + `actual` is blocked because those values are unavailable before
kickoff.

## Data Sources

The script merges:

- `Stammdaten_78.csv`
- `match_statistics_filtered_78.csv`
- `Teams_78.csv`
- `historical_weather_data_78.csv`
- `weather_data.csv` from the active output folder

## Pre-Match Inputs

The match-stats models use only information that exists before kickoff:

- base team strength
- rolling last-5 form
- H2H features
- weather
- `HomeTeamID`
- `AwayTeamID`

They do not use:

- actual current-match match stats
- the actual result
- current-match goals
- anything derived from the post-match outcome

## Match Stats Targets

The predicted match-stat layer covers:

- `HomePossession`, `AwayPossession`
- `HomeShots`, `AwayShots`
- `HomeShotsOnTarget`, `AwayShotsOnTarget`
- `HomePasses`, `AwayPasses`
- `HomePassAccuracy`, `AwayPassAccuracy`
- `HomeFouls`, `AwayFouls`
- `HomeYellowCard`, `AwayYellowCard`
- `HomeRedCard`, `AwayRedCard`
- `HomeOffsides`, `AwayOffsides`
- `HomeCorners`, `AwayCorners`

## Match Stats Models

The first-pass implementation uses:

- one `GradientBoostingRegressor` per target stat
- median-imputed pre-match inputs

For leakage-safe training alignment:

- played training matches receive out-of-fold predicted stats
- target prediction matches receive final-model predicted stats

This means that in `MATCH_STATS_MODE='predicted'`, the outcome model is trained
on predicted stats instead of real current-match stats.

## Post-Processing

Predicted stats are cleaned after model prediction:

- possession clipped to `0..100`
- pass accuracy clipped to `0..100`
- possession normalized to sum to `100`
- count stats clipped to non-negative values
- count stats rounded to integers

Count-like stats include:

- shots
- shots on target
- passes
- fouls
- yellow cards
- red cards
- offsides
- corners

## Outcome Model

After the match-stat stage, the original outcome pipeline remains intact:

1. sample one weight per feature
2. sample one integer `H2H_K`
3. apply H2H reliability scaling
4. median-impute missing values
5. train BART on `GoalDiff`
6. convert predicted goal difference into `WinProb`, `DrawProb`, `LoseProb`
7. derive a scoreline estimate

## Feature Sets

### Outcome Base Features

- base team strength
- rolling last-5 form
- H2H features
- weather

### Outcome Match Stats Features

- the real stats when `MATCH_STATS_MODE='actual'`
- the predicted stats when `MATCH_STATS_MODE='predicted'`
- omitted when `MATCH_STATS_MODE='off'`

## Leakage Controls

The script avoids leakage in three places:

1. Match-stats models use only pre-match inputs.
2. In reference mode, held-out reference matches are removed from the outcome
   training set.
3. In predicted mode, the outcome training rows receive out-of-fold stat
   predictions instead of their own real current-match stats.

## Outputs

The script keeps the existing outcome outputs:

- `prediction_weight_runs.csv`
- `prediction_weight_run_summary.csv`
- `future_candidate_ranking.csv` in future mode
- `future_outcome_table.csv` in future mode
- `pareto_front.csv` in reference mode

Additional output for predicted-stat runs:

- `predicted_match_stats.csv`

This file is written into the active output folder:

- `Datacollection future` for future predictions
- `Datacollection reference` for reference-mode backtests

It contains:

- match identity columns
- predicted match stats
- mode metadata
- actual match stats as comparison columns when available

## Surrogate History

The surrogate history file is filtered by `MatchStatsMode` before it is reused.
This prevents old `actual` runs from being mixed into `predicted`-mode
surrogate selection.

## Practical Reading

Use `reference` + `actual` to measure how strong the outcome model is with real
historical match stats.

Use `reference` + `predicted` to measure the full end-to-end pipeline you will
actually use in future mode.

Use `future` + `predicted` for real upcoming-match predictions.
