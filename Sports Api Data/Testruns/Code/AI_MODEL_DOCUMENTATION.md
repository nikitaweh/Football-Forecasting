# AI Model Documentation

## Purpose

This model predicts football match outcomes for two use cases:

- `future` mode: predict upcoming unplayed matches
- `reference` mode: predict matches listed in `match_results_references.csv` for debugging and evaluation

The model does **not** directly learn exact scorelines. Its main target is:

```text
GoalDiff = HomeGoals - AwayGoals
```

From the predicted goal difference, the script derives:

- `WinProb`
- `DrawProb`
- `LoseProb`
- `PredictedResult`
- an estimated scoreline

## Data Sources

The script currently merges data from:

- `Stammdaten_78.csv`
- `match_statistics_filtered_78.csv`
- `Teams_78.csv`
- `historical_weather_data_78.csv`
- `weather_data.csv` in the active output folder

## Feature Groups

### 1. Base Team Strength

Season-level team averages:

- `Home_BaseAvgGoalsFor`
- `Home_BaseAvgGoalsAgainst`
- `Home_BaseAvgPoints`
- `Away_BaseAvgGoalsFor`
- `Away_BaseAvgGoalsAgainst`
- `Away_BaseAvgPoints`

These are computed from all played matches.

### 2. Rolling Last-5 Form

For each team, the script computes shifted rolling averages:

- `AvgGoalsFor_L5`
- `AvgGoalsAgainst_L5`
- `AvgPoints_L5`

The shift ensures that a match does not use its own outcome in its features.

### 3. Head-to-Head (H2H)

For every matchup, the script calculates:

- combined H2H history
- venue-specific H2H history

Metrics:

- average goal difference
- average goals for
- average goals against
- average points
- win rate
- match count

### 4. Match Statistics

Current match-stat features include:

- possession
- shots
- shots on target
- passes
- pass accuracy
- fouls
- yellow cards
- red cards
- offsides
- corners

for both home and away teams.

Important: in real future predictions, these values are not known unless they are estimated externally. If they are missing, they are median-imputed.

### 5. Weather

Weather features:

- `Weather_Temperature_C`
- `Weather_Pressure`
- `Weather_Humidity`
- `Weather_WindSpeed`
- `Weather_WindDirection`
- `Weather_Rain`
- `Weather_Snow`

## Mathematical Feature Construction

### Points

Points are defined as:

```text
Points = 3 * I(win) + 1 * I(draw)
```

where:

- win: `GoalsFor > GoalsAgainst`
- draw: `GoalsFor == GoalsAgainst`

### Rolling Form

For a team at match time `t`:

```text
AvgGoalsFor_L5(t) = mean(GoalsFor(t-1), ..., GoalsFor(t-5))
```

Same logic applies to goals against and points.

### H2H Reliability Scaling

H2H features are scaled with:

```text
alpha = MatchCount / (MatchCount + k)
```

where:

- `MatchCount` = number of prior H2H matches
- `k` = tunable integer parameter in `[1, 10]`

Scaled H2H features:

```text
ScaledH2H = RawH2H * alpha
```

Effective H2H feature weight:

```text
EffectiveWeight_H2H = Weight_H2H * alpha
```

## Feature Weights

Each run samples one weight for every feature:

```text
Weight_feature ~ Uniform(0, 2)
```

and one integer H2H parameter:

```text
H2H_K ~ IntegerUniform(1, 10)
```

After imputation, features are multiplied element-wise by the weight vector:

```text
X_weighted = X_imputed * weight_vector
```

This means the model does not internally learn one fixed coefficient per feature. Instead, the script searches across many alternative weighted feature spaces.

## Main Predictive Model

The main predictive model is BART:

```text
SklearnModel(n_trees=50)
```

Training flow:

1. historical matches are selected
2. `GoalDiff` is computed
3. data is split with `train_test_split`
4. H2H scaling is applied
5. missing values are median-imputed
6. weighted features are passed into the BART model

The learned function is:

```text
GoalDiff_hat = f(weighted_features)
```

## Probability Conversion

The BART model predicts a goal-difference mean `mu`.

Residual spread is estimated on the training set:

```text
sigma = std(y_train - train_predictions)
```

Then the script uses a normal approximation with draw margin `0.5`:

```text
z_hi = (0.5 - mu) / sigma
z_lo = (-0.5 - mu) / sigma

DrawProb = Phi(z_hi) - Phi(z_lo)
LoseProb = Phi(z_lo)
WinProb  = 1 - Phi(z_hi)
```

where `Phi` is the standard normal CDF.

Predicted class:

```text
PredictedResult = argmax(WinProb, DrawProb, LoseProb)
```

## Scoreline Estimation

The scoreline is a derived estimate, not a direct model output.

The script computes:

```text
home_attack = mean(Home_BaseAvgGoalsFor, Home_AvgGoalsFor_L5)
away_defense = mean(Away_BaseAvgGoalsAgainst, Away_AvgGoalsAgainst_L5)
away_attack = mean(Away_BaseAvgGoalsFor, Away_AvgGoalsFor_L5)
home_defense = mean(Home_BaseAvgGoalsAgainst, Home_AvgGoalsAgainst_L5)
```

Estimated total goals:

```text
total_goals = 2 * mean(
    (home_attack + away_defense) / 2,
    (away_attack + home_defense) / 2
)
```

Expected goals:

```text
ExpectedHomeGoals = (total_goals + PredictedGoalDiff) / 2
ExpectedAwayGoals = total_goals - ExpectedHomeGoals
```

After rounding, the scoreline is forced to be consistent with `PredictedResult`.

## Evaluation in Reference Mode

When actual results are available, evaluation works as follows.

For each match:

```text
ProbActual =
    WinProb  if actual result is home win
    DrawProb if actual result is draw
    LoseProb if actual result is away win
```

The script clips probabilities:

```text
ProbActual = max(ProbActual, 1e-12)
```

Per-match negative log-likelihood:

```text
MatchNLL = -log(ProbActual)
```

Per-run metrics:

```text
AvgNLL = mean(MatchNLL)
Accuracy = mean(PredictedResult == ActualResult)
```

Interpretation:

- lower `AvgNLL` is better
- higher `Accuracy` is better

## Surrogate Model

If enough scored reference history exists, the script trains surrogate models to estimate run quality.

Threshold:

```text
SURROGATE_MIN_HISTORY = 100
```

Current default surrogate:

```text
GradientBoostingRegressor
```

Optional switch:

```text
MLPRegressor
```

Two surrogate targets are trained:

- predicted `AvgNLL`
- predicted `Accuracy`

Surrogate inputs:

- every feature weight
- `H2H_K`

## Candidate Generation

Candidate runs are generated with:

- random feature weights in `[0, 2]`
- random `H2H_K` in `[1, 10]`

If the surrogate is available:

1. candidates are scored with predicted `AvgNLL` and `Accuracy`
2. a Pareto-like selection is used
3. a fraction is kept random for exploration

## Future Candidate Ranking

In `future` mode, there is no true `AvgNLL` or `Accuracy` yet.

So the script builds an estimated ranking using either:

- surrogate-estimated metrics, or
- fallback confidence metrics

### Confidence Metrics

For each run, the script computes:

- `MeanTopProb`
- `MeanProbGap`
- `MeanEntropy`

Definitions:

```text
TopProb = max(WinProb, DrawProb, LoseProb)
ProbGap = TopProb - second_highest_probability
Entropy = -sum(p * log(p))
```

Then future ranking scores are built.

If surrogate metrics exist:

```text
BalancedScore =
0.50 * PredNLLComponent + 0.50 * PredAccuracyComponent

ConservativeScore =
0.70 * PredNLLComponent + 0.20 * ConfidenceComponent + 0.10 * EntropyComponent

AggressiveScore =
0.70 * PredAccuracyComponent + 0.20 * GapComponent + 0.10 * ConfidenceComponent
```

If surrogate metrics do not exist:

```text
FallbackScore =
0.45 * ConfidenceComponent + 0.35 * GapComponent + 0.20 * EntropyComponent
```

The highest-ranked future run is used to build:

- `future_candidate_ranking.csv`
- `future_outcome_table.csv`

## Output Files

### Future Mode

- `prediction_weight_runs.csv`
- `prediction_weight_run_summary.csv`
- `surrogate_run_history.csv`
- `future_candidate_ranking.csv`
- `future_outcome_table.csv`

### Reference Mode

- `prediction_weight_runs.csv`
- `prediction_weight_run_summary.csv`
- `surrogate_run_history.csv`
- `pareto_front.csv`

## Important Caveat

The strongest current limitation is that match-stat features are post-match type features unless estimated beforehand. For the most realistic future forecasting, the model should eventually use:

- true pre-match features
- or separately predicted match-stat estimates

Until then, the most robust pre-match information remains:

- base team strength
- rolling form
- H2H
- weather
