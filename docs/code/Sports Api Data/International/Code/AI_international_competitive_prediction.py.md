# `AI_international_competitive_prediction.py`

Source: `Sports Api Data/International/Code/AI_international_competitive_prediction.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Erzeugt Spielprognosen und bewertet Ergebniswahrscheinlichkeiten anhand der konfigurierten Modell- und Datenpfade.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `parse_args()`
  Verwendet `argparse.ArgumentParser`, `parser.add_argument`, `os.environ.get`, `os.environ.get('INTERNATIONAL_ENGINE', '').strip().lower`. Rueckgabe unter anderem: `parser.parse_args()`.
- `_normal_cdf(values)`
  Verwendet `np.asarray`, `np.vectorize(lambda x: 0.5 * (1.0 + math.erf(x / math.sqrt(2.0))))`, `np.vectorize`, `math.erf`. Rueckgabe unter anderem: `np.vectorize(lambda x: 0.5 * (1.0 + math.erf(x / math.sqrt(2.0))))(values)`.
- `goal_diff_probabilities(predicted_goal_diff, sigma, draw_margin)`
  Verwendet `np.asarray`, `max`, `float`, `_normal_cdf`. Rueckgabe unter anderem: `probs / probs.sum(axis=1, keepdims=True)`.
- `load_regulation_results()`
  Verwendet `fixtures_path.exists`, `fixtures_path.open`, `json.load`, `payload.get`. Rueckgabe unter anderem: `results`.
- `load_competitive_fixtures(as_of)`
  Verwendet `pd.read_csv`, `path.exists`, `FileNotFoundError`, `', '.join`. Rueckgabe unter anderem: `fixtures.sort_values(['MatchDate', 'MatchID']).reset_index(drop=True)`.
- `_recent_summary(history, current_date, window=5)`
  Verwendet `float`, `np.mean`. Rueckgabe unter anderem: `{'points': float(np.mean([row['points'] for row in prior])), 'goal_diff': float(np.mean([row['goa...`.
- `_rest_days(history, current_date)`
  Verwendet `float`, `min`, `max`. Rueckgabe unter anderem: `float(min(60, max(0, (current_date - prior_dates[-1]).days)))`.
- `_is_knockout(stage)`
  Verwendet `str(stage).strip().lower`, `str(stage).strip`, `str`, `float`. Rueckgabe unter anderem: `float(any((token in text for token in ('round of', '8th', 'quarter', 'semi', 'final', '3rd place'...`.
- `build_features(fixtures)`
  Verwendet `defaultdict`, `fixtures.iterrows`, `int`, `_recent_summary`. Rueckgabe unter anderem: `pd.DataFrame(rows)`.
- `make_model(engine='bart')`
  Verwendet `make_pipeline`, `SimpleImputer`, `GradientBoostingRegressor`, `SklearnModel`. Rueckgabe unter anderem: `make_pipeline(SimpleImputer(strategy='median'), GradientBoostingRegressor(loss='huber', n_estimat...`.
- `actual_class_indices(goal_diff)`
  Verwendet `np.asarray`, `np.where`. Rueckgabe unter anderem: `np.where(goal_diff > 0, 0, np.where(goal_diff < 0, 2, 1))`.
- `calibration_score(predictions, actual_goal_diff, sigma, margin)`
  Verwendet `goal_diff_probabilities`, `actual_class_indices`, `float`, `np.mean`. Rueckgabe unter anderem: `nll`.
- `calibrate_probability_mapping(predictions, actual_goal_diff)`
  Verwendet `np.arange`, `calibration_score`, `float`. Rueckgabe unter anderem: `{'nll': best[0], 'sigma': best[1], 'draw_margin': best[2]}`.
- `expected_goals_from_diff(goal_diff, total_goals)`
  Verwendet `np.maximum`, `np.asarray`. Rueckgabe unter anderem: `(home, away)`.
- `_poisson_pmf(lam, max_goals)`
  Verwendet `max`, `min`, `float`, `math.exp`. Rueckgabe unter anderem: `pmf`.
- `_score_grid_probs(lam_home, lam_away, rho, max_goals)`
  Verwendet `_poisson_pmf`, `enumerate`, `max`, `math.isfinite`. Rueckgabe unter anderem: `(p_home / total, p_draw / total, p_away / total)`.
- `dixon_coles_probabilities(goal_diff, total_goals, rho, max_goals=DC_MAX_GOALS, draw_ratio=False, base_probs=None)`
  Verwendet `np.asarray`, `expected_goals_from_diff`, `np.empty`, `len`. Rueckgabe unter anderem: `out / out.sum(axis=1, keepdims=True)`.
- `calibrate_dixon_coles(predictions, actual_goal_diff, max_goals=DC_MAX_GOALS)`
  Verwendet `actual_class_indices`, `np.arange`, `len`, `dixon_coles_probabilities`. Rueckgabe unter anderem: `{'nll': best[0], 'total_goals': best[1], 'rho': best[2]}`.
- `_overlay_sim(values, scale)`
  Verwendet `np.exp`, `max`, `np.abs`, `float`. Rueckgabe unter anderem: `np.exp(-np.abs(np.asarray(values, dtype='float64')) / max(0.05, float(scale)))`.
- `overlay_signal_scales(frame, predicted_goal_diff)`
  Median absolute value per signal → the closeness scale for that signal.
- `overlay_draw_signal(frame, predicted_goal_diff, expected_home, expected_away, scales, total_cap=INTL_OVERLAY_TOTAL_CAP)`
  Per-match draw-ishness in [0, 1] (independent of the lift strength / band).
- `apply_draw_overlay(base_probs, draw_signal, alpha, min_prob, max_prob)`
  Verwendet `np.asarray`, `np.maximum`, `np.clip`, `np.where`. Rueckgabe unter anderem: `out / out.sum(axis=1, keepdims=True)`.
- `calibrate_overlay(frame, predictions, actual_goal_diff, sigma, draw_margin, scales)`
  Verwendet `goal_diff_probabilities`, `expected_goals_from_diff`, `overlay_draw_signal`, `actual_class_indices`. Rueckgabe unter anderem: `{'nll': best[0], 'alpha': best[1], 'min_prob': best[2], 'max_prob': best[3]}`.
- `outcome_probabilities(predictions, outcome, frame=None)`
  Map predicted goal differences to an Nx3 [H, D, A] array for the active mode.
- `classification_metrics(probs, actual_goal_diff)`
  Verwendet `actual_class_indices`, `np.arange`, `len`, `float`. Rueckgabe unter anderem: `{'nll': nll, 'accuracy': accuracy, 'brier': brier}`.
- `add_prediction_columns(frame, predictions, outcome)`
  Verwendet `frame.copy`, `np.asarray`, `outcome_probabilities`, `np.array`. Rueckgabe unter anderem: `out`.
- `main()`
  Verwendet `parse_args`, `pd.to_datetime`, `pd.Timestamp.now().normalize`, `pd.Timestamp.now`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `os.environ.get('INTERNATIONAL_AS_OF_DATE', '')`
- `os.environ.get('INTERNATIONAL_ENGINE', '')`
- `os.environ.get('INTERNATIONAL_OUTCOME_MODE', '')`
- `os.environ.get('INTERNATIONAL_DC_RHO', '')`
- `os.environ.get('INTERNATIONAL_DC_TOTAL', '')`
- `os.environ.get('INTERNATIONAL_OVERLAY_ALPHA', '')`
- `fixtures_path.open('r', encoding='utf-8')`
- `json.load(handle)`
- `payload.get('response', [])`
- `item.get('fixture', {})`
- `fixture.get('id')`
- `fixture.get('status', {}).get('short')`
- `fixture.get('status', {})`
- `item.get('score', {}).get('fulltime', {})`
- `item.get('score', {})`
- `regulation.get('home')`
- `regulation.get('away')`
- `item.get('goals', {})`
- `goals.get('home')`
- `goals.get('away')`
- `pd.read_csv(path)`
- `results.get(int(match_id), (np.nan, np.nan, None))`

### Konfiguration und Environment

- `COMPETITIVE_LEAGUES = frozenset({'World Cup', 'Euro Championship', 'UEFA Nations League', 'World Cup - Qualification Africa', 'World Cup - Qualification Asia', 'World Cup - Qualification CONCACAF', 'World Cup - Qualification Europe', 'World Cup - Qualificat...`
- `FINISHED_STATUSES = {'FT', 'AET', 'PEN'}`
- `RANDOM_STATE = 42`
- `INTERNATIONAL_DIR = Path(__file__).resolve().parents[1]`
- `BRANCHES = ('FIFA', 'UEFA')`
- `STAMMDATEN_PATHS = [INTERNATIONAL_DIR / branch / 'Filtered' / 'Datacollection' / 'Stammdaten_international.csv' for branch in BRANCHES]`
- `RAW_FIXTURES_PATHS = [INTERNATIONAL_DIR / branch / 'Unfiltered' / 'Datacollection' / 'fixtures_international.json' for branch in BRANCHES]`
- `DEFAULT_OUTPUT_DIR = INTERNATIONAL_DIR / 'Model Output' / 'competitive'`
- `FEATURE_COLUMNS = ['EloDiff', 'HomePointsL5', 'AwayPointsL5', 'PointsFormDiffL5', 'HomeGoalDiffL5', 'AwayGoalDiffL5', 'GoalDiffFormDiffL5', 'AttackDiffL5', 'DefenceDiffL5', 'ExperienceDiff', 'RestDaysDiff', 'IsKnockout', 'Competition_WorldCup', 'Competition...`
- `DC_MAX_GOALS = 10`
- `INTL_OVERLAY_SIGNALS = [('PredictedGoalDiff', 0.4), ('EloDiff', 0.25), ('PointsFormDiffL5', 0.12), ('GoalDiffFormDiffL5', 0.12), ('AttackDiffL5', 0.055), ('DefenceDiffL5', 0.055)]`
- `INTL_OVERLAY_TOTAL_CAP = 2.6`
- `parser.add_argument('--as-of', default=os.environ.get('INTERNATIONAL_AS_OF_DATE', ''), help='Information cutoff in YYYY-MM-DD format; defaults to today.')`
- `os.environ.get('INTERNATIONAL_AS_OF_DATE', '')`
- `parser.add_argument('--engine', choices=['bart', 'gbr'], default=os.environ.get('INTERNATIONAL_ENGINE', '').strip().lower() or 'bart', help="Outcome regressor for the goal difference: 'bart' (default, same engine as the Bundesliga model) or 'gbr' (the origi...`
- `os.environ.get('INTERNATIONAL_ENGINE', '').strip().lower()`
- `os.environ.get('INTERNATIONAL_ENGINE', '').strip()`
- `os.environ.get('INTERNATIONAL_ENGINE', '')`
- `parser.add_argument('--outcome', choices=['normal', 'dixon_coles', 'dixon_coles_draw_ratio', 'draw_multilayer_overlay'], default=os.environ.get('INTERNATIONAL_OUTCOME_MODE', '').strip().lower() or 'normal', help="How the predicted goal difference becomes Wi...`
- `os.environ.get('INTERNATIONAL_OUTCOME_MODE', '').strip().lower()`
- `os.environ.get('INTERNATIONAL_OUTCOME_MODE', '').strip()`
- `os.environ.get('INTERNATIONAL_OUTCOME_MODE', '')`
- `parser.add_argument('--dc-rho', type=float, default=float(os.environ['INTERNATIONAL_DC_RHO']) if os.environ.get('INTERNATIONAL_DC_RHO', '').strip() else None, help='Override the Dixon-Coles low-score correction rho instead of calibrating it.')`
- `os.environ.get('INTERNATIONAL_DC_RHO', '').strip()`
- `os.environ.get('INTERNATIONAL_DC_RHO', '')`

### Imports und interne Abhaengigkeiten

- `import argparse`
- `import json`
- `import math`
- `import os`
- `import pickle`
- `from collections import defaultdict`
- `from pathlib import Path`
- `import numpy as np`
- `import pandas as pd`
- `from sklearn.ensemble import GradientBoostingRegressor`
- `from sklearn.impute import SimpleImputer`
- `from sklearn.pipeline import make_pipeline`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/International/Code/AI_international_competitive_prediction.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `Exception`.
