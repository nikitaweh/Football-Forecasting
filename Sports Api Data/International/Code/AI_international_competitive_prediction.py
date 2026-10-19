import argparse
import json
import math
import os
import pickle
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline


COMPETITIVE_LEAGUES = frozenset({
    'World Cup',
    'Euro Championship',
    'UEFA Nations League',
    'World Cup - Qualification Africa',
    'World Cup - Qualification Asia',
    'World Cup - Qualification CONCACAF',
    'World Cup - Qualification Europe',
    'World Cup - Qualification Oceania',
    'World Cup - Qualification South America',
    'World Cup - Qualification Intercontinental Play-offs',
    'Euro Championship - Qualification',
})
FINISHED_STATUSES = {'FT', 'AET', 'PEN'}
RANDOM_STATE = 42

INTERNATIONAL_DIR = Path(__file__).resolve().parents[1]

# The data pipeline is split into FIFA and UEFA confederation branches. This stays a
# single combined model: it reads the competitive Stammdaten/fixtures from BOTH branches
# and concatenates them. Friendlies live in each branch's separate Friendlies/ subtree
# and are intentionally NOT read here (they are excluded from COMPETITIVE_LEAGUES anyway).
BRANCHES = ('FIFA', 'UEFA')
STAMMDATEN_PATHS = [
    INTERNATIONAL_DIR / branch / 'Filtered' / 'Datacollection' / 'Stammdaten_international.csv'
    for branch in BRANCHES
]
RAW_FIXTURES_PATHS = [
    INTERNATIONAL_DIR / branch / 'Unfiltered' / 'Datacollection' / 'fixtures_international.json'
    for branch in BRANCHES
]
DEFAULT_OUTPUT_DIR = INTERNATIONAL_DIR / 'Model Output' / 'competitive'

FEATURE_COLUMNS = [
    'EloDiff',
    'HomePointsL5', 'AwayPointsL5', 'PointsFormDiffL5',
    'HomeGoalDiffL5', 'AwayGoalDiffL5', 'GoalDiffFormDiffL5',
    'AttackDiffL5', 'DefenceDiffL5',
    'ExperienceDiff', 'RestDaysDiff',
    'IsKnockout',
    'Competition_WorldCup',
    'Competition_WorldCupQualification',
    'Competition_Euro',
    'Competition_EuroQualification',
    'Competition_NationsLeague',
]


def parse_args():
    parser = argparse.ArgumentParser(
        description='Train and run a separate outcome model using competitive international matches only.'
    )
    parser.add_argument(
        '--as-of',
        default=os.environ.get('INTERNATIONAL_AS_OF_DATE', ''),
        help='Information cutoff in YYYY-MM-DD format; defaults to today.',
    )
    parser.add_argument(
        '--engine',
        choices=['bart', 'gbr'],
        default=(os.environ.get('INTERNATIONAL_ENGINE', '').strip().lower() or 'bart'),
        help="Outcome regressor for the goal difference: 'bart' (default, same engine as the "
             "Bundesliga model) or 'gbr' (the original GradientBoostingRegressor).",
    )
    parser.add_argument(
        '--outcome',
        choices=['normal', 'dixon_coles', 'dixon_coles_draw_ratio', 'draw_multilayer_overlay'],
        default=(os.environ.get('INTERNATIONAL_OUTCOME_MODE', '').strip().lower() or 'normal'),
        help="How the predicted goal difference becomes Win/Draw/Loss: 'normal' (grid-searched "
             "Gaussian draw zone, default), 'dixon_coles' (Poisson scoreline grid with low-score "
             "correction), 'dixon_coles_draw_ratio' (Dixon-Coles draw %, keep the normal H:A ratio), "
             "or 'draw_multilayer_overlay' (ratio-preserving: lift draws for evenly-matched, "
             "low-scoring games via strength + score layers).",
    )
    parser.add_argument(
        '--dc-rho',
        type=float,
        default=(float(os.environ['INTERNATIONAL_DC_RHO']) if os.environ.get('INTERNATIONAL_DC_RHO', '').strip() else None),
        help='Override the Dixon-Coles low-score correction rho instead of calibrating it.',
    )
    parser.add_argument(
        '--dc-total',
        type=float,
        default=(float(os.environ['INTERNATIONAL_DC_TOTAL']) if os.environ.get('INTERNATIONAL_DC_TOTAL', '').strip() else None),
        help='Override the Dixon-Coles assumed average total goals instead of calibrating it.',
    )
    parser.add_argument(
        '--overlay-alpha',
        type=float,
        default=(float(os.environ['INTERNATIONAL_OVERLAY_ALPHA']) if os.environ.get('INTERNATIONAL_OVERLAY_ALPHA', '').strip() else None),
        help='Override the draw-overlay lift strength alpha (0..1) instead of calibrating it.',
    )
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def _normal_cdf(values):
    values = np.asarray(values, dtype='float64')
    return np.vectorize(lambda x: 0.5 * (1.0 + math.erf(x / math.sqrt(2.0))))(values)


def goal_diff_probabilities(predicted_goal_diff, sigma, draw_margin):
    mu = np.asarray(predicted_goal_diff, dtype='float64')
    sigma = max(float(sigma), 0.05)
    draw_margin = max(float(draw_margin), 0.01)
    away = _normal_cdf((-draw_margin - mu) / sigma)
    home = 1.0 - _normal_cdf((draw_margin - mu) / sigma)
    draw = 1.0 - home - away
    probs = np.column_stack([home, draw, away])
    probs = np.clip(probs, 1e-9, 1.0)
    return probs / probs.sum(axis=1, keepdims=True)


def load_regulation_results():
    results = {}
    for fixtures_path in RAW_FIXTURES_PATHS:
        if not fixtures_path.exists():
            continue
        with fixtures_path.open('r', encoding='utf-8') as handle:
            payload = json.load(handle)

        for item in payload.get('response', []):
            fixture = item.get('fixture', {})
            fixture_id = fixture.get('id')
            status = fixture.get('status', {}).get('short')
            if fixture_id is None or status not in FINISHED_STATUSES:
                continue

            regulation = item.get('score', {}).get('fulltime', {}) or {}
            home_goals = regulation.get('home')
            away_goals = regulation.get('away')
            if home_goals is None or away_goals is None:
                goals = item.get('goals', {}) or {}
                home_goals = goals.get('home')
                away_goals = goals.get('away')
            if home_goals is None or away_goals is None:
                continue
            results[int(fixture_id)] = (float(home_goals), float(away_goals), status)
    return results


def load_competitive_fixtures(as_of):
    frames = [pd.read_csv(path) for path in STAMMDATEN_PATHS if path.exists()]
    if not frames:
        raise FileNotFoundError(
            'No Stammdaten found in any confederation branch: '
            + ', '.join(str(p) for p in STAMMDATEN_PATHS)
        )
    fixtures = pd.concat(frames, ignore_index=True)
    fixtures = fixtures.rename(columns={
        'Date': 'MatchDate',
        'Home Team': 'HomeTeam',
        'Away Team': 'AwayTeam',
        'Home Team ID': 'HomeTeamID',
        'Away Team ID': 'AwayTeamID',
        'League Name': 'Competition',
        'Matchday': 'Stage',
    })
    fixtures = fixtures[fixtures['Competition'].isin(COMPETITIVE_LEAGUES)].copy()
    fixtures['MatchID'] = pd.to_numeric(fixtures['MatchID'], errors='coerce')
    fixtures['HomeTeamID'] = pd.to_numeric(fixtures['HomeTeamID'], errors='coerce')
    fixtures['AwayTeamID'] = pd.to_numeric(fixtures['AwayTeamID'], errors='coerce')
    fixtures['MatchDate'] = pd.to_datetime(fixtures['MatchDate'], errors='coerce')
    fixtures = fixtures.dropna(
        subset=['MatchID', 'HomeTeamID', 'AwayTeamID', 'MatchDate']
    ).copy()
    fixtures[['MatchID', 'HomeTeamID', 'AwayTeamID']] = fixtures[
        ['MatchID', 'HomeTeamID', 'AwayTeamID']
    ].astype(int)

    results = load_regulation_results()
    fixtures['HomeGoals'] = fixtures['MatchID'].map(
        lambda match_id: results.get(int(match_id), (np.nan, np.nan, None))[0]
    )
    fixtures['AwayGoals'] = fixtures['MatchID'].map(
        lambda match_id: results.get(int(match_id), (np.nan, np.nan, None))[1]
    )
    fixtures['Status'] = fixtures['MatchID'].map(
        lambda match_id: results.get(int(match_id), (np.nan, np.nan, None))[2]
    )
    fixtures['PlayedForModel'] = (
        (fixtures['MatchDate'] < as_of)
        & fixtures['HomeGoals'].notna()
        & fixtures['AwayGoals'].notna()
    )
    return fixtures.sort_values(['MatchDate', 'MatchID']).reset_index(drop=True)


def _recent_summary(history, current_date, window=5):
    prior = [row for row in history if row['date'] < current_date][-window:]
    if not prior:
        return {
            'points': 1.0,
            'goal_diff': 0.0,
            'goals_for': 1.2,
            'goals_against': 1.2,
        }
    return {
        'points': float(np.mean([row['points'] for row in prior])),
        'goal_diff': float(np.mean([row['goals_for'] - row['goals_against'] for row in prior])),
        'goals_for': float(np.mean([row['goals_for'] for row in prior])),
        'goals_against': float(np.mean([row['goals_against'] for row in prior])),
    }


def _rest_days(history, current_date):
    prior_dates = [row['date'] for row in history if row['date'] < current_date]
    if not prior_dates:
        return 30.0
    return float(min(60, max(0, (current_date - prior_dates[-1]).days)))


def _is_knockout(stage):
    text = str(stage).strip().lower()
    return float(any(token in text for token in (
        'round of', '8th', 'quarter', 'semi', 'final', '3rd place', 'play-off', 'playoff'
    )))


def build_features(fixtures):
    ratings = defaultdict(lambda: 1500.0)
    histories = defaultdict(list)
    rows = []

    for _, match in fixtures.iterrows():
        home_id = int(match['HomeTeamID'])
        away_id = int(match['AwayTeamID'])
        match_date = match['MatchDate']
        home_recent = _recent_summary(histories[home_id], match_date)
        away_recent = _recent_summary(histories[away_id], match_date)
        competition = match['Competition']

        feature_row = match.to_dict()
        feature_row.update({
            'EloDiff': ratings[home_id] - ratings[away_id],
            'HomePointsL5': home_recent['points'],
            'AwayPointsL5': away_recent['points'],
            'PointsFormDiffL5': home_recent['points'] - away_recent['points'],
            'HomeGoalDiffL5': home_recent['goal_diff'],
            'AwayGoalDiffL5': away_recent['goal_diff'],
            'GoalDiffFormDiffL5': home_recent['goal_diff'] - away_recent['goal_diff'],
            'AttackDiffL5': home_recent['goals_for'] - away_recent['goals_for'],
            'DefenceDiffL5': away_recent['goals_against'] - home_recent['goals_against'],
            'ExperienceDiff': math.log1p(len(histories[home_id])) - math.log1p(len(histories[away_id])),
            'RestDaysDiff': (
                _rest_days(histories[home_id], match_date)
                - _rest_days(histories[away_id], match_date)
            ) / 30.0,
            'IsKnockout': _is_knockout(match.get('Stage')),
            'Competition_WorldCup': float(competition == 'World Cup'),
            'Competition_WorldCupQualification': float(
                str(competition).startswith('World Cup - Qualification')
            ),
            'Competition_Euro': float(competition == 'Euro Championship'),
            'Competition_EuroQualification': float(
                competition == 'Euro Championship - Qualification'
            ),
            'Competition_NationsLeague': float(competition == 'UEFA Nations League'),
        })
        rows.append(feature_row)

        if not bool(match['PlayedForModel']):
            continue

        home_goals = float(match['HomeGoals'])
        away_goals = float(match['AwayGoals'])
        goal_diff = home_goals - away_goals
        if goal_diff > 0:
            home_points, away_points, actual = 3.0, 0.0, 1.0
        elif goal_diff < 0:
            home_points, away_points, actual = 0.0, 3.0, 0.0
        else:
            home_points, away_points, actual = 1.0, 1.0, 0.5

        expected_home = 1.0 / (1.0 + 10.0 ** ((ratings[away_id] - ratings[home_id]) / 400.0))
        goal_multiplier = 1.0 + 0.15 * min(abs(goal_diff), 3.0)
        rating_change = 24.0 * goal_multiplier * (actual - expected_home)
        ratings[home_id] += rating_change
        ratings[away_id] -= rating_change
        histories[home_id].append({
            'date': match_date,
            'goals_for': home_goals,
            'goals_against': away_goals,
            'points': home_points,
        })
        histories[away_id].append({
            'date': match_date,
            'goals_for': away_goals,
            'goals_against': home_goals,
            'points': away_points,
        })

    return pd.DataFrame(rows)


def make_model(engine='bart'):
    if engine == 'gbr':
        return make_pipeline(
            SimpleImputer(strategy='median'),
            GradientBoostingRegressor(
                loss='huber',
                n_estimators=220,
                learning_rate=0.03,
                max_depth=2,
                min_samples_leaf=12,
                subsample=0.85,
                random_state=RANDOM_STATE,
            ),
        )
    if engine == 'bart':
        # Imported lazily so the GBR path keeps working even without bartpy installed.
        # n_jobs=1 mirrors the Bundesliga model: avoids multiprocessing pipe issues on
        # restricted hosts. The median imputer guards against any missing engineered feature.
        from bartpy.sklearnmodel import SklearnModel
        return make_pipeline(
            SimpleImputer(strategy='median'),
            SklearnModel(n_trees=200, n_jobs=1),
        )
    raise ValueError(f"Unknown engine '{engine}'; expected 'bart' or 'gbr'.")


def actual_class_indices(goal_diff):
    goal_diff = np.asarray(goal_diff, dtype='float64')
    return np.where(goal_diff > 0, 0, np.where(goal_diff < 0, 2, 1))


def calibration_score(predictions, actual_goal_diff, sigma, margin):
    probs = goal_diff_probabilities(predictions, sigma, margin)
    actual = actual_class_indices(actual_goal_diff)
    nll = float(-np.mean(np.log(probs[np.arange(len(actual)), actual])))
    return nll


def calibrate_probability_mapping(predictions, actual_goal_diff):
    best = None
    for sigma in np.arange(0.70, 4.01, 0.05):
        for margin in np.arange(0.20, 1.61, 0.025):
            nll = calibration_score(predictions, actual_goal_diff, sigma, margin)
            candidate = (nll, float(sigma), float(margin))
            if best is None or candidate < best:
                best = candidate
    return {'nll': best[0], 'sigma': best[1], 'draw_margin': best[2]}


# --- Dixon-Coles outcome mode -------------------------------------------------
# A selectable alternative to the Gaussian draw zone: turn the predicted goal
# difference into expected home/away goals (using an assumed average total), build
# the Poisson scoreline grid, apply the Dixon-Coles low-score correction, and sum
# the cells into Home/Draw/Away. Mirrors score_distribution_outcome_probs in the
# Bundesliga model. The international model only knows expected goals (no match
# stats / H2H / player signals), so Dixon-Coles is the draw lever that actually fits.
DC_MAX_GOALS = 10


def expected_goals_from_diff(goal_diff, total_goals):
    home = np.maximum(0.15, total_goals / 2.0 + np.asarray(goal_diff, dtype='float64') / 2.0)
    away = np.maximum(0.15, total_goals / 2.0 - np.asarray(goal_diff, dtype='float64') / 2.0)
    return home, away


def _poisson_pmf(lam, max_goals):
    lam = max(0.02, min(8.0, float(lam)))
    pmf = [math.exp(-lam)]
    for goals in range(1, max_goals + 1):
        pmf.append(pmf[-1] * lam / float(goals))
    return pmf


def _score_grid_probs(lam_home, lam_away, rho, max_goals):
    home_pmf = _poisson_pmf(lam_home, max_goals)
    away_pmf = _poisson_pmf(lam_away, max_goals)
    p_home = p_draw = p_away = 0.0
    for home_goals, home_prob in enumerate(home_pmf):
        for away_goals, away_prob in enumerate(away_pmf):
            joint = home_prob * away_prob
            if rho:
                if home_goals == 0 and away_goals == 0:
                    joint *= max(1e-12, 1.0 - lam_home * lam_away * rho)
                elif home_goals == 0 and away_goals == 1:
                    joint *= max(1e-12, 1.0 + lam_home * rho)
                elif home_goals == 1 and away_goals == 0:
                    joint *= max(1e-12, 1.0 + lam_away * rho)
                elif home_goals == 1 and away_goals == 1:
                    joint *= max(1e-12, 1.0 - rho)
            if home_goals > away_goals:
                p_home += joint
            elif home_goals == away_goals:
                p_draw += joint
            else:
                p_away += joint
    total = p_home + p_draw + p_away
    if not math.isfinite(total) or total <= 0:
        return None
    return p_home / total, p_draw / total, p_away / total


def dixon_coles_probabilities(goal_diff, total_goals, rho, max_goals=DC_MAX_GOALS,
                              draw_ratio=False, base_probs=None):
    goal_diff = np.asarray(goal_diff, dtype='float64')
    home_goals, away_goals = expected_goals_from_diff(goal_diff, total_goals)
    out = np.empty((len(goal_diff), 3), dtype='float64')
    for i in range(len(goal_diff)):
        grid = _score_grid_probs(float(home_goals[i]), float(away_goals[i]), rho, max_goals)
        if grid is None:
            out[i] = (np.nan, np.nan, np.nan)
            continue
        home, draw, away = grid
        if draw_ratio and base_probs is not None:
            base_home, _, base_away = base_probs[i]
            non_draw = base_home + base_away
            home_share = base_home / non_draw if non_draw > 0 else 0.5
            home = (1.0 - draw) * home_share
            away = (1.0 - draw) * (1.0 - home_share)
        out[i] = (home, draw, away)
    out = np.clip(out, 1e-9, 1.0)
    return out / out.sum(axis=1, keepdims=True)


def calibrate_dixon_coles(predictions, actual_goal_diff, max_goals=DC_MAX_GOALS):
    actual = actual_class_indices(actual_goal_diff)
    indices = np.arange(len(actual))
    best = None
    for total_goals in np.arange(2.0, 3.41, 0.10):
        for rho in np.arange(-0.25, 0.051, 0.05):
            probs = dixon_coles_probabilities(predictions, float(total_goals), float(rho), max_goals)
            nll = float(-np.mean(np.log(probs[indices, actual])))
            candidate = (nll, float(total_goals), float(rho))
            if best is None or candidate < best:
                best = candidate
    return {'nll': best[0], 'total_goals': best[1], 'rho': best[2]}


# --- Multilayer draw overlay --------------------------------------------------
# Ratio-preserving alternative to Dixon-Coles: keep BART's home:away split exactly,
# and only lift the DRAW probability for matches that look like draws. "Draw-ish" is
# a [0, 1] score from a strength layer (how evenly matched the teams are) modulated by
# a score layer (small goal gap + low total). Adapted from the Bundesliga
# draw_multilayer_overlay; the stats / discipline / H2H layers have no inputs for
# internationals, so the international version uses the signals it actually has.
INTL_OVERLAY_SIGNALS = [
    ('PredictedGoalDiff', 0.40),
    ('EloDiff', 0.25),
    ('PointsFormDiffL5', 0.12),
    ('GoalDiffFormDiffL5', 0.12),
    ('AttackDiffL5', 0.055),
    ('DefenceDiffL5', 0.055),
]
INTL_OVERLAY_TOTAL_CAP = 2.60


def _overlay_sim(values, scale):
    return np.exp(-np.abs(np.asarray(values, dtype='float64')) / max(0.05, float(scale)))


def overlay_signal_scales(frame, predicted_goal_diff):
    """Median absolute value per signal → the closeness scale for that signal."""
    scales = {}
    for col, _weight in INTL_OVERLAY_SIGNALS:
        if col == 'PredictedGoalDiff':
            values = np.abs(np.asarray(predicted_goal_diff, dtype='float64'))
        elif col in frame.columns:
            values = np.abs(pd.to_numeric(frame[col], errors='coerce').to_numpy())
        else:
            continue
        values = values[np.isfinite(values)]
        scales[col] = max(0.05, float(np.median(values)) if values.size else 1.0)
    return scales


def overlay_draw_signal(frame, predicted_goal_diff, expected_home, expected_away, scales,
                        total_cap=INTL_OVERLAY_TOTAL_CAP):
    """Per-match draw-ishness in [0, 1] (independent of the lift strength / band)."""
    predicted_goal_diff = np.asarray(predicted_goal_diff, dtype='float64')
    weighted = np.zeros(len(predicted_goal_diff))
    weight_total = np.zeros(len(predicted_goal_diff))
    for col, weight in INTL_OVERLAY_SIGNALS:
        if col == 'PredictedGoalDiff':
            values = predicted_goal_diff
        elif col in frame.columns:
            values = pd.to_numeric(frame[col], errors='coerce').to_numpy()
        else:
            continue
        similarity = _overlay_sim(values, scales.get(col, 1.0))
        valid = np.isfinite(similarity)
        weighted = np.where(valid, weighted + np.nan_to_num(similarity) * weight, weighted)
        weight_total = np.where(valid, weight_total + weight, weight_total)
    strength = np.where(weight_total > 0, weighted / weight_total, 0.5)

    goal_gap_similarity = _overlay_sim(expected_home - expected_away, 0.75)
    total_goals = np.maximum(0.0, expected_home + expected_away)
    high_total_penalty = np.exp(-np.maximum(0.0, total_goals - total_cap) / 1.10)
    score = 0.70 * goal_gap_similarity + 0.30 * high_total_penalty

    return np.clip(strength * (0.65 + 0.35 * score), 0.0, 1.0)


def apply_draw_overlay(base_probs, draw_signal, alpha, min_prob, max_prob):
    base_probs = np.asarray(base_probs, dtype='float64')
    base_home, base_draw, base_away = base_probs[:, 0], base_probs[:, 1], base_probs[:, 2]
    candidate = min_prob + (max_prob - min_prob) * draw_signal
    target = np.maximum(base_draw, candidate)
    final_draw = np.clip(base_draw + alpha * (target - base_draw), 0.0, 0.95)
    non_draw = base_home + base_away
    home_share = np.where(non_draw > 0, base_home / non_draw, 0.5)
    final_home = (1.0 - final_draw) * home_share
    final_away = (1.0 - final_draw) * (1.0 - home_share)
    out = np.clip(np.column_stack([final_home, final_draw, final_away]), 1e-9, 1.0)
    return out / out.sum(axis=1, keepdims=True)


def calibrate_overlay(frame, predictions, actual_goal_diff, sigma, draw_margin, scales):
    base = goal_diff_probabilities(predictions, sigma, draw_margin)
    expected_home, expected_away = expected_goals_from_diff(predictions, INTL_OVERLAY_TOTAL_CAP)
    draw_signal = overlay_draw_signal(frame, predictions, expected_home, expected_away, scales)
    actual = actual_class_indices(actual_goal_diff)
    indices = np.arange(len(actual))
    best = None
    for alpha in (0.2, 0.4, 0.6, 0.8, 1.0):
        for min_prob in (0.12, 0.16, 0.20):
            for max_prob in (0.30, 0.36, 0.42):
                probs = apply_draw_overlay(base, draw_signal, alpha, min_prob, max_prob)
                nll = float(-np.mean(np.log(probs[indices, actual])))
                candidate = (nll, float(alpha), float(min_prob), float(max_prob))
                if best is None or candidate < best:
                    best = candidate
    return {'nll': best[0], 'alpha': best[1], 'min_prob': best[2], 'max_prob': best[3]}


def outcome_probabilities(predictions, outcome, frame=None):
    """Map predicted goal differences to an Nx3 [H, D, A] array for the active mode."""
    mode = outcome['mode']
    base = goal_diff_probabilities(predictions, outcome['sigma'], outcome['draw_margin'])
    if mode == 'normal':
        return base
    if mode == 'draw_multilayer_overlay':
        if frame is None:
            raise ValueError('draw_multilayer_overlay needs the feature frame for its strength layer.')
        expected_home, expected_away = expected_goals_from_diff(predictions, INTL_OVERLAY_TOTAL_CAP)
        draw_signal = overlay_draw_signal(
            frame, predictions, expected_home, expected_away, outcome['overlay_scales']
        )
        return apply_draw_overlay(
            base, draw_signal,
            outcome['overlay_alpha'], outcome['overlay_min_prob'], outcome['overlay_max_prob']
        )
    return dixon_coles_probabilities(
        predictions,
        outcome['total_goals'],
        outcome['rho'],
        outcome.get('max_goals', DC_MAX_GOALS),
        draw_ratio=(mode == 'dixon_coles_draw_ratio'),
        base_probs=base,
    )


def classification_metrics(probs, actual_goal_diff):
    actual = actual_class_indices(actual_goal_diff)
    indices = np.arange(len(actual))
    nll = float(-np.mean(np.log(np.clip(probs[indices, actual], 1e-9, 1.0))))
    accuracy = float(np.mean(np.argmax(probs, axis=1) == actual))
    one_hot = np.eye(3)[actual]
    brier = float(np.mean(np.sum((probs - one_hot) ** 2, axis=1)))
    return {'nll': nll, 'accuracy': accuracy, 'brier': brier}


def add_prediction_columns(frame, predictions, outcome):
    out = frame.copy()
    predictions = np.asarray(predictions, dtype='float64')
    probs = outcome_probabilities(predictions, outcome, frame=frame)
    out['PredictedGoalDiff'] = predictions
    out['WinProb'] = probs[:, 0]
    out['DrawProb'] = probs[:, 1]
    out['LoseProb'] = probs[:, 2]
    labels = np.array(['H', 'D', 'A'])
    out['PredictedResult'] = labels[np.argmax(probs, axis=1)]

    # Keep the displayed scoreline consistent with the probabilities: the Dixon-Coles
    # modes use their calibrated average total; normal and the draw overlay keep 2.60.
    total_goals = outcome['total_goals'] if outcome['mode'].startswith('dixon_coles') else 2.60
    home_goals, away_goals = expected_goals_from_diff(predictions, total_goals)
    out['ExpectedHomeGoals'] = home_goals
    out['ExpectedAwayGoals'] = away_goals
    out['PredictedScore'] = (
        np.round(home_goals).astype(int).astype(str)
        + ':'
        + np.round(away_goals).astype(int).astype(str)
    )
    return out


def main():
    args = parse_args()
    as_of = pd.to_datetime(args.as_of, errors='coerce') if args.as_of else pd.Timestamp.now().normalize()
    if pd.isna(as_of):
        raise ValueError("--as-of must be a valid date such as 2026-06-20.")

    fixtures = load_competitive_fixtures(as_of)
    featured = build_features(fixtures)
    played = featured[featured['PlayedForModel']].copy()
    future = featured[
        (~featured['PlayedForModel']) & (featured['MatchDate'] >= as_of)
    ].copy()
    if len(played) < 150:
        raise ValueError(f'Only {len(played)} competitive training matches are available; at least 150 are required.')

    played['GoalDiff'] = played['HomeGoals'] - played['AwayGoals']
    train_end = max(100, int(len(played) * 0.70))
    calibration_end = max(train_end + 25, int(len(played) * 0.85))
    calibration_end = min(calibration_end, len(played) - 25)

    development = played.iloc[:train_end]
    calibration = played.iloc[train_end:calibration_end]
    test = played.iloc[calibration_end:]

    engine = args.engine
    print(f'Engine: {engine} · outcome mode: {args.outcome}')

    validation_model = make_model(engine)
    validation_model.fit(development[FEATURE_COLUMNS], development['GoalDiff'])
    calibration_predictions = validation_model.predict(calibration[FEATURE_COLUMNS])
    calibration_actual = calibration['GoalDiff'].to_numpy()

    # Closeness scales for the overlay: engineered signals from the full training set,
    # the goal-diff scale from the calibration predictions (representative spread).
    overlay_scales = overlay_signal_scales(played, calibration_predictions)

    # Calibrate every mapping on the same calibration split so they can be compared fairly.
    mapping = calibrate_probability_mapping(calibration_predictions, calibration_actual)
    dc_mapping = calibrate_dixon_coles(calibration_predictions, calibration_actual)
    if args.dc_rho is not None:
        dc_mapping['rho'] = float(args.dc_rho)
    if args.dc_total is not None:
        dc_mapping['total_goals'] = float(args.dc_total)
    overlay_mapping = calibrate_overlay(
        calibration, calibration_predictions, calibration_actual,
        mapping['sigma'], mapping['draw_margin'], overlay_scales
    )
    if args.overlay_alpha is not None:
        overlay_mapping['alpha'] = float(args.overlay_alpha)

    outcome = {
        'mode': args.outcome,
        'sigma': mapping['sigma'],
        'draw_margin': mapping['draw_margin'],
        'total_goals': dc_mapping['total_goals'],
        'rho': dc_mapping['rho'],
        'max_goals': DC_MAX_GOALS,
        'overlay_scales': overlay_scales,
        'overlay_alpha': overlay_mapping['alpha'],
        'overlay_min_prob': overlay_mapping['min_prob'],
        'overlay_max_prob': overlay_mapping['max_prob'],
    }

    test_predictions = validation_model.predict(test[FEATURE_COLUMNS])
    test_output = add_prediction_columns(test, test_predictions, outcome)
    test_actual = test['GoalDiff'].to_numpy()

    # Score the active mode plus every other outcome mode on the held-out test set so the
    # draw lever can be judged like-for-like (same BART predictions, different mapping).
    outcome_mode_comparison = {}
    for mode in ('normal', 'dixon_coles', 'dixon_coles_draw_ratio', 'draw_multilayer_overlay'):
        mode_probs = outcome_probabilities(test_predictions, {**outcome, 'mode': mode}, frame=test)
        outcome_mode_comparison[mode] = classification_metrics(mode_probs, test_actual)
    active_metrics = outcome_mode_comparison[args.outcome]
    test_nll = active_metrics['nll']
    test_accuracy = active_metrics['accuracy']
    test_brier = active_metrics['brier']

    test_actual_idx = actual_class_indices(test_actual)
    test_one_hot = np.eye(3)[test_actual_idx]
    development_actual = actual_class_indices(development['GoalDiff'].to_numpy())
    baseline_probs = np.bincount(development_actual, minlength=3).astype('float64')
    baseline_probs = baseline_probs / baseline_probs.sum()
    baseline_test_nll = float(-np.mean(np.log(baseline_probs[test_actual_idx])))
    baseline_test_accuracy = float(np.mean(np.argmax(baseline_probs) == test_actual_idx))
    baseline_test_brier = float(np.mean(np.sum((baseline_probs - test_one_hot) ** 2, axis=1)))

    final_model = make_model(engine)
    final_model.fit(played[FEATURE_COLUMNS], played['GoalDiff'])
    if future.empty:
        future_output = future.copy()
    else:
        future_predictions = final_model.predict(future[FEATURE_COLUMNS])
        future_output = add_prediction_columns(future, future_predictions, outcome)

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    prediction_columns = [
        'MatchID', 'MatchDate', 'Competition', 'Season', 'Stage',
        'HomeTeam', 'AwayTeam', 'PredictedResult', 'PredictedScore',
        'PredictedGoalDiff', 'ExpectedHomeGoals', 'ExpectedAwayGoals',
        'WinProb', 'DrawProb', 'LoseProb',
    ]
    future_output.reindex(columns=prediction_columns).to_csv(
        output_dir / 'international_competitive_predictions.csv',
        index=False,
    )

    validation_columns = prediction_columns + ['HomeGoals', 'AwayGoals', 'GoalDiff']
    test_output.reindex(columns=validation_columns).to_csv(
        output_dir / 'international_competitive_validation.csv',
        index=False,
    )

    payload = {
        'engine': engine,
        'outcome_mode': args.outcome,
        'feature_columns': FEATURE_COLUMNS,
        'competitive_leagues': sorted(COMPETITIVE_LEAGUES),
        'sigma': mapping['sigma'],
        'draw_margin': mapping['draw_margin'],
        'dc_total_goals': dc_mapping['total_goals'],
        'dc_rho': dc_mapping['rho'],
        'overlay_alpha': overlay_mapping['alpha'],
        'overlay_min_prob': overlay_mapping['min_prob'],
        'overlay_max_prob': overlay_mapping['max_prob'],
        'overlay_scales': overlay_scales,
        'as_of': as_of.isoformat(),
    }
    try:
        # BART models can carry unpicklable sampler state; keep the artefact useful either way.
        pickle.dumps(final_model)
        payload['model'] = final_model
    except Exception as exc:  # noqa: BLE001
        payload['model'] = None
        payload['model_pickle_error'] = f'{type(exc).__name__}: {exc}'
    with (output_dir / 'international_competitive_model.pkl').open('wb') as handle:
        pickle.dump(payload, handle)

    engine_label = {
        'bart': 'BART (bartpy SklearnModel, 200 trees) on regulation goal difference',
        'gbr': 'GradientBoostingRegressor on regulation goal difference',
    }[engine]
    metadata = {
        'as_of': as_of.isoformat(),
        'engine': engine,
        'outcome_mode': args.outcome,
        'competitive_leagues': sorted(COMPETITIVE_LEAGUES),
        'target_definition': '90-minute regulation result; penalties and extra time excluded',
        'training_matches': int(len(played)),
        'development_matches': int(len(development)),
        'calibration_matches': int(len(calibration)),
        'test_matches': int(len(test)),
        'future_matches': int(len(future_output)),
        'calibration_nll': mapping['nll'],
        'calibration_nll_dixon_coles': dc_mapping['nll'],
        'test_nll': test_nll,
        'test_accuracy': test_accuracy,
        'test_brier': test_brier,
        'outcome_mode_comparison': outcome_mode_comparison,
        'development_prior': {
            'H': float(baseline_probs[0]),
            'D': float(baseline_probs[1]),
            'A': float(baseline_probs[2]),
        },
        'baseline_test_nll': baseline_test_nll,
        'baseline_test_accuracy': baseline_test_accuracy,
        'baseline_test_brier': baseline_test_brier,
        'sigma': mapping['sigma'],
        'draw_margin': mapping['draw_margin'],
        'dc_total_goals': dc_mapping['total_goals'],
        'dc_rho': dc_mapping['rho'],
        'calibration_nll_overlay': overlay_mapping['nll'],
        'overlay_alpha': overlay_mapping['alpha'],
        'overlay_min_prob': overlay_mapping['min_prob'],
        'overlay_max_prob': overlay_mapping['max_prob'],
        'model': engine_label,
    }
    with (output_dir / 'international_competitive_model_metadata.json').open('w', encoding='utf-8') as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)

    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(f'Predictions written to: {output_dir / "international_competitive_predictions.csv"}')


if __name__ == '__main__':
    main()
