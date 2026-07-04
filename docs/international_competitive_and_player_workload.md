# Competitive international model and Bundesliga player workload

**Implemented:** 2026-06-20  
**Bundesliga model:** `Sports Api Data/Testruns/Code/AI_match_stats_prediction.py`  
**International model:** `Sports Api Data/International/Code/AI_international_competitive_prediction.py`

## Scope and separation

The international outcome model is a separate model instance. It does not reuse Bundesliga model parameters, residual variance, learned weights, or home-advantage assumptions. It does reuse the project's general convention of predicting regulation-time goal difference and converting it into H/D/A probabilities.

Only the following competitive competitions are eligible:

- World Cup
- Euro Championship
- UEFA Nations League
- World Cup qualification for Africa, Asia, CONCACAF, Europe, Oceania, South America and intercontinental play-offs
- Euro Championship qualification

Friendlies remain available in the raw collection for other analyses, but are excluded from both the international outcome model and the Bundesliga workload feature.

The fixture collector now knows the qualification competition IDs. These competitions enter the filtered datasets after the international collection pipeline is refreshed; existing local files are not retroactively populated by the code change alone.

## International target definition

The target is the score after 90 minutes. Extra time and penalties are excluded. This is important for a three-way H/D/A target because a knockout match that is level after 90 minutes is a draw even if a team later advances.

`match_statistics_international.py` now prefers `score.fulltime` from the raw API fixture. It falls back to the top-level goals only if the regulation score is unavailable.

## International model

The model uses chronological, pre-match features:

- neutral Elo difference without an automatic club-style home advantage
- rolling points and goal form over five matches
- attack and defence form differences
- prior-match experience and rest-day difference
- competition and knockout-stage indicators

The estimator is a `GradientBoostingRegressor` on regulation goal difference. Data are split chronologically into 70% development, 15% probability calibration and 15% untouched test. The final production estimator is then refit on all completed competitive matches before future matches are predicted.

Run:

```powershell
& 'Supportdateien/.venv/Scripts/python.exe' `
  'Sports Api Data/International/Code/AI_international_competitive_prediction.py' `
  --as-of 2026-06-20
```

Outputs are written to `Sports Api Data/International/Model Output/competitive/`:

- `international_competitive_predictions.csv`
- `international_competitive_validation.csv`
- `international_competitive_model.pkl`
- `international_competitive_model_metadata.json`

### Current validation status

With the local data available on 2026-06-20, the model used 1,182 completed competitive matches. The untouched final 178-match test block produced NLL 0.999, multiclass Brier score 0.597 and accuracy 56.2%. A development-period class-prior baseline produced NLL 1.081, Brier score 0.653 and accuracy 43.8% on the same test block.

This is an initial benchmark, not proof of superiority over a bookmaker or the Bundesliga model. The present probability mapping produced no draw as the maximum-probability class in the test block despite 48 actual draws. Draw probabilities are present and normalized, but the draw pick-rate problem is therefore not solved for international matches. A draw-specific decision rule must be validated out of sample before activation.

## Bundesliga workload feature

`player_workload_features.py` builds a per-player event index from:

1. actual Bundesliga minutes;
2. actual competitive international minutes when the filtered player-statistics CSV is available;
3. otherwise, confirmed competitive international starts with a 90-minute proxy.

International bench listings are not counted because the lineup file alone does not prove that a substitute entered the match.

For player `i` before match date `t`:

```text
short_load = min(2, minutes_i(t-14d, t) / 270)
long_load  = min(2, minutes_i(t-30d, t) / 540)
workload_i = 0.65 * short_load + 0.35 * long_load
```

The team workload is a position-weighted mean across the confirmed starting XI for played/reference matches. For future matches it is weighted by the existing estimated start probabilities. The model receives:

```text
Player_WorkloadDiff = Away_PlayerWorkload - Home_PlayerWorkload
```

Positive values therefore mean greater away-team load and are oriented in the same home-positive direction as the other player-base signals.

### Leakage controls

- only events with `event_date < target_match_date` are included;
- the target match's own minutes are excluded;
- international friendlies are excluded;
- future scheduled international matches are not workload events;
- old v1/v2 run histories are not relabelled as the new `bases_v3_player_workload` schema.

The schema change intentionally causes a surrogate cold start until enough v3 reference runs have been collected. Reusing older NLL targets would mix different feature spaces.

### Current data limitation

The current international player-statistics responses contain no player rows, so the implementation presently uses the confirmed-start proxy. The current local fixture collection also does not yet contain the newly configured qualification competitions. Consequently, the code is connected correctly but the incremental international workload signal remains sparse until the international fixtures, lineups and player statistics are refreshed.

## Required evaluation before treating workload as beneficial

Run the unchanged matchday backtest protocol for the v3 schema and compare it to an archived v2 baseline. At minimum report:

- mean and median NLL difference by matchday;
- H/D/A class-specific NLL and recall;
- performance around international windows versus ordinary weeks;
- number of matches with a non-zero international workload increment;
- stability of `Weight_Player_WorkloadDiff` across best runs.

The feature should be retained only if gains concentrate plausibly around congested periods and do not come from a small number of unstable outliers.
