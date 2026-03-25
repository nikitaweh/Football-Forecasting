import math
import os
import random
import pandas as pd
from bartpy.sklearnmodel import SklearnModel
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# Pfad zum Datenordner anpassen
DATA_PATH = r'C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection'
TESTRUNS_PATH = r'C:/AI Projekt/KI-Projekt/Sports Api Data/Testruns'
FUTURE_OUTPUT_PATH = os.path.join(TESTRUNS_PATH, 'Datacollection future')
REFERENCE_OUTPUT_PATH = os.path.join(TESTRUNS_PATH, 'Datacollection reference')
WEATHER_HIST_PATH = os.path.join(DATA_PATH, 'historical_weather_data_78.csv')
MAX_RUNS = 20

# === PREDICTION TARGET SWITCH ===
# "future"    = predict next unplayed matches
# "reference" = predict matches from match_results_references.csv for debugging/evaluation
PREDICTION_MODE = 'future'
REFERENCE_PREDICTION_LIMIT = None

if PREDICTION_MODE == 'future':
    OUTPUT_PATH = FUTURE_OUTPUT_PATH
    RESULTS_PATH = os.path.join(FUTURE_OUTPUT_PATH, 'match_results_references.csv')
    FALLBACK_RESULTS_PATH = None
    DECISION_OUT_PATH = os.path.join(FUTURE_OUTPUT_PATH, 'future_candidate_ranking.csv')
    RUN_HISTORY_SOURCE_PATH = os.path.join(REFERENCE_OUTPUT_PATH, 'surrogate_run_history.csv')
elif PREDICTION_MODE == 'reference':
    OUTPUT_PATH = REFERENCE_OUTPUT_PATH
    RESULTS_PATH = os.path.join(REFERENCE_OUTPUT_PATH, 'match_results_references.csv')
    FALLBACK_RESULTS_PATH = os.path.join(DATA_PATH, 'match_results_references.csv')
    DECISION_OUT_PATH = os.path.join(REFERENCE_OUTPUT_PATH, 'pareto_front.csv')
    RUN_HISTORY_SOURCE_PATH = os.path.join(REFERENCE_OUTPUT_PATH, 'surrogate_run_history.csv')
else:
    raise ValueError("PREDICTION_MODE must be either 'future' or 'reference'.")

os.makedirs(OUTPUT_PATH, exist_ok=True)
PREDICTION_OUT_PATH = os.path.join(OUTPUT_PATH, 'prediction_weight_runs.csv')
RUN_SUMMARY_OUT_PATH = os.path.join(OUTPUT_PATH, 'prediction_weight_run_summary.csv')
RUN_HISTORY_PATH = os.path.join(OUTPUT_PATH, 'surrogate_run_history.csv')
PARETO_OUT_PATH = DECISION_OUT_PATH
FUTURE_OUTCOME_TABLE_PATH = os.path.join(OUTPUT_PATH, 'future_outcome_table.csv')
WEATHER_FUTURE_PATH = os.path.join(OUTPUT_PATH, 'weather_data.csv')

# === SURROGATE MODEL SWITCH ===
# "gbr" = Gradient Boosting (recommended for now)
# "nn"  = Neural Network surrogate (use when you have much more data)
SURROGATE_MODEL = 'gbr'
SURROGATE_MIN_HISTORY = 100
SURROGATE_CANDIDATES = 300
SURROGATE_RANDOM_FRACTION = 0.2
PARETO_TARGET_SIZE = 20

# === H2H K SEARCH RANGE ===
H2H_K_RANGE = (1, 10)
H2H_K_DEFAULT = 2

# 1. Laden
match_stats   = pd.read_csv(os.path.join(DATA_PATH, 'match_statistics_filtered_78.csv'))
stammdaten    = pd.read_csv(os.path.join(DATA_PATH, 'Stammdaten_78.csv'))
teams         = pd.read_csv(os.path.join(DATA_PATH, 'Teams_78.csv'))

def load_weather(path):
    if not path or not os.path.exists(path):
        return pd.DataFrame()
    try:
        w = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    w = w.rename(columns={
        'Temperature (C)': 'Weather_Temperature_C',
        'Pressure': 'Weather_Pressure',
        'Humidity': 'Weather_Humidity',
        'Wind Speed': 'Weather_WindSpeed',
        'Wind Direction': 'Weather_WindDirection',
        'Rain': 'Weather_Rain',
        'Snow': 'Weather_Snow'
    })
    keep_cols = [
        'MatchID',
        'Weather_Temperature_C',
        'Weather_Pressure',
        'Weather_Humidity',
        'Weather_WindSpeed',
        'Weather_WindDirection',
        'Weather_Rain',
        'Weather_Snow'
    ]
    for col in keep_cols:
        if col not in w.columns:
            w[col] = float('nan')
    w = w[keep_cols]
    for col in keep_cols[1:]:
        w[col] = pd.to_numeric(w[col], errors='coerce')
    return w

# 2. Umbenennen
stammdaten.rename(columns={
    'Home Team ID': 'HomeTeamID', 'Away Team ID': 'AwayTeamID',
    'Home Team': 'HomeTeam', 'Away Team': 'AwayTeam',
    'Date': 'MatchDate', 'Gespielt': 'Played'
}, inplace=True)

match_stats.rename(columns={
    'Match ID': 'MatchID',
    'Home Goals': 'HomeGoals', 'Away Goals': 'AwayGoals',
    'Home Possession': 'HomePossession', 'Away Possession': 'AwayPossession',
    'Home Shots': 'HomeShots', 'Away Shots': 'AwayShots',
    'Home Shots on Target': 'HomeShotsOnTarget', 'Away Shots on Target': 'AwayShotsOnTarget',
    'Home Passes': 'HomePasses', 'Away Passes': 'AwayPasses',
    'Home Pass Accuracy': 'HomePassAccuracy', 'Away Pass Accuracy': 'AwayPassAccuracy',
    'Home Fouls': 'HomeFouls', 'Away Fouls': 'AwayFouls',
    'Home Yellow Card': 'HomeYellowCard', 'Away Yellow Card': 'AwayYellowCard',
    'Home Red Card': 'HomeRedCard', 'Away Red Card': 'AwayRedCard',
    'Home Offsides': 'HomeOffsides', 'Away Offsides': 'AwayOffsides',
    'Home Corners': 'HomeCorners', 'Away Corners': 'AwayCorners'
}, inplace=True)

teams.rename(columns={
    'Team ID': 'TeamID', 'Team Name': 'TeamName',
    'Stadion ID': 'StadiumID', 'Capacity': 'StadiumCapacity'
}, inplace=True)

# 3. Zusammenführen – WICHTIG: mit STAMMDATEN starten, damit ungespielte Spiele erhalten bleiben
df = stammdaten.merge(match_stats, on='MatchID', how='left')

teams_home = teams.add_suffix('_Home')
teams_away = teams.add_suffix('_Away')
df = (
    df
    .merge(teams_home, left_on='HomeTeamID', right_on='TeamID_Home', how='left')
    .merge(teams_away, left_on='AwayTeamID', right_on='TeamID_Away', how='left')
)

weather_hist = load_weather(WEATHER_HIST_PATH)
weather_future = load_weather(WEATHER_FUTURE_PATH)
if not weather_hist.empty or not weather_future.empty:
    weather_all = pd.concat([weather_hist, weather_future], ignore_index=True)
    weather_all = weather_all.dropna(subset=['MatchID'])
    weather_all = weather_all.drop_duplicates(subset=['MatchID'], keep='last')
    df = df.merge(weather_all, on='MatchID', how='left')

# Team-Form und Grundstärke (historisch + Rolling)
df['MatchDate'] = pd.to_datetime(df['MatchDate'], errors='coerce')

played_mask = df['Played'] == True
played_df = df[played_mask].copy()
played_df = played_df[played_df['HomeGoals'].notna() & played_df['AwayGoals'].notna()].copy()

h2h_home = played_df[['MatchID', 'MatchDate', 'HomeTeamID', 'AwayTeamID', 'HomeGoals', 'AwayGoals']].copy()
h2h_home = h2h_home.rename(columns={
    'HomeTeamID': 'TeamID',
    'AwayTeamID': 'OpponentID',
    'HomeGoals': 'GoalsFor',
    'AwayGoals': 'GoalsAgainst'
})
h2h_home['IsHome'] = 1

h2h_away = played_df[['MatchID', 'MatchDate', 'AwayTeamID', 'HomeTeamID', 'AwayGoals', 'HomeGoals']].copy()
h2h_away = h2h_away.rename(columns={
    'AwayTeamID': 'TeamID',
    'HomeTeamID': 'OpponentID',
    'AwayGoals': 'GoalsFor',
    'HomeGoals': 'GoalsAgainst'
})
h2h_away['IsHome'] = 0

h2h_long = pd.concat([h2h_home, h2h_away], ignore_index=True)
h2h_long['Points'] = (
    (h2h_long['GoalsFor'] > h2h_long['GoalsAgainst']).astype(int) * 3
    + (h2h_long['GoalsFor'] == h2h_long['GoalsAgainst']).astype(int)
)

def summarize_h2h(subset):
    if subset.empty:
        return {
            'AvgGoalDiff': float('nan'),
            'AvgGoalsFor': float('nan'),
            'AvgGoalsAgainst': float('nan'),
            'AvgPoints': float('nan'),
            'WinRate': float('nan'),
            'MatchCount': float('nan')
        }
    goal_diff = subset['GoalsFor'] - subset['GoalsAgainst']
    return {
        'AvgGoalDiff': float(goal_diff.mean()),
        'AvgGoalsFor': float(subset['GoalsFor'].mean()),
        'AvgGoalsAgainst': float(subset['GoalsAgainst'].mean()),
        'AvgPoints': float(subset['Points'].mean()),
        'WinRate': float((subset['GoalsFor'] > subset['GoalsAgainst']).mean()),
        'MatchCount': float(len(subset))
    }

def add_h2h_features(df_src):
    base = df_src[df_src['MatchDate'].notna()].copy()
    out_rows = []
    for _, row in base.iterrows():
        match_id = row['MatchID']
        home_id = row['HomeTeamID']
        away_id = row['AwayTeamID']
        match_date = row['MatchDate']

        if pd.isna(home_id) or pd.isna(away_id) or pd.isna(match_date):
            combined = summarize_h2h(pd.DataFrame())
            venue = summarize_h2h(pd.DataFrame())
        else:
            subset = h2h_long[
                (h2h_long['TeamID'] == home_id)
                & (h2h_long['OpponentID'] == away_id)
                & (h2h_long['MatchDate'] < match_date)
            ]
            combined = summarize_h2h(subset)
            venue = summarize_h2h(subset[subset['IsHome'] == 1])

        out_rows.append({
            'MatchID': match_id,
            'H2H_Combined_AvgGoalDiff': combined['AvgGoalDiff'],
            'H2H_Combined_AvgGoalsFor': combined['AvgGoalsFor'],
            'H2H_Combined_AvgGoalsAgainst': combined['AvgGoalsAgainst'],
            'H2H_Combined_AvgPoints': combined['AvgPoints'],
            'H2H_Combined_WinRate': combined['WinRate'],
            'H2H_Combined_MatchCount': combined['MatchCount'],
            'H2H_Venue_AvgGoalDiff': venue['AvgGoalDiff'],
            'H2H_Venue_AvgGoalsFor': venue['AvgGoalsFor'],
            'H2H_Venue_AvgGoalsAgainst': venue['AvgGoalsAgainst'],
            'H2H_Venue_AvgPoints': venue['AvgPoints'],
            'H2H_Venue_WinRate': venue['WinRate'],
            'H2H_Venue_MatchCount': venue['MatchCount']
        })

    return pd.DataFrame(out_rows)

H2H_COMBINED_FEATURES = [
    'H2H_Combined_AvgGoalDiff', 'H2H_Combined_AvgGoalsFor', 'H2H_Combined_AvgGoalsAgainst',
    'H2H_Combined_AvgPoints', 'H2H_Combined_WinRate'
]
H2H_VENUE_FEATURES = [
    'H2H_Venue_AvgGoalDiff', 'H2H_Venue_AvgGoalsFor', 'H2H_Venue_AvgGoalsAgainst',
    'H2H_Venue_AvgPoints', 'H2H_Venue_WinRate'
]

def apply_h2h_scaling(feature_df, k):
    df_scaled = feature_df.copy()
    if 'H2H_Combined_MatchCount' in df_scaled.columns:
        alpha_c = df_scaled['H2H_Combined_MatchCount'] / (df_scaled['H2H_Combined_MatchCount'] + k)
        for col in H2H_COMBINED_FEATURES:
            if col in df_scaled.columns:
                df_scaled[col] = df_scaled[col] * alpha_c
    if 'H2H_Venue_MatchCount' in df_scaled.columns:
        alpha_v = df_scaled['H2H_Venue_MatchCount'] / (df_scaled['H2H_Venue_MatchCount'] + k)
        for col in H2H_VENUE_FEATURES:
            if col in df_scaled.columns:
                df_scaled[col] = df_scaled[col] * alpha_v
    return df_scaled

home_rows = played_df[['MatchID', 'MatchDate', 'HomeTeamID', 'HomeGoals', 'AwayGoals']].copy()
home_rows = home_rows.rename(columns={
    'HomeTeamID': 'TeamID',
    'HomeGoals': 'GoalsFor',
    'AwayGoals': 'GoalsAgainst'
})
home_rows['IsHome'] = 1

away_rows = played_df[['MatchID', 'MatchDate', 'AwayTeamID', 'AwayGoals', 'HomeGoals']].copy()
away_rows = away_rows.rename(columns={
    'AwayTeamID': 'TeamID',
    'AwayGoals': 'GoalsFor',
    'HomeGoals': 'GoalsAgainst'
})
away_rows['IsHome'] = 0

team_long = pd.concat([home_rows, away_rows], ignore_index=True)
team_long['Points'] = (
    (team_long['GoalsFor'] > team_long['GoalsAgainst']).astype(int) * 3
    + (team_long['GoalsFor'] == team_long['GoalsAgainst']).astype(int)
)

rolling_window = 5
team_long = team_long.sort_values(['TeamID', 'MatchDate'])
team_long['AvgGoalsFor_L5'] = (
    team_long.groupby('TeamID')['GoalsFor']
    .apply(lambda s: s.shift(1).rolling(rolling_window, min_periods=1).mean())
    .reset_index(level=0, drop=True)
)
team_long['AvgGoalsAgainst_L5'] = (
    team_long.groupby('TeamID')['GoalsAgainst']
    .apply(lambda s: s.shift(1).rolling(rolling_window, min_periods=1).mean())
    .reset_index(level=0, drop=True)
)
team_long['AvgPoints_L5'] = (
    team_long.groupby('TeamID')['Points']
    .apply(lambda s: s.shift(1).rolling(rolling_window, min_periods=1).mean())
    .reset_index(level=0, drop=True)
)

team_strength = team_long.groupby('TeamID').agg(
    BaseAvgGoalsFor=('GoalsFor', 'mean'),
    BaseAvgGoalsAgainst=('GoalsAgainst', 'mean'),
    BaseAvgPoints=('Points', 'mean')
)

df['Home_BaseAvgGoalsFor'] = df['HomeTeamID'].map(team_strength['BaseAvgGoalsFor'])
df['Home_BaseAvgGoalsAgainst'] = df['HomeTeamID'].map(team_strength['BaseAvgGoalsAgainst'])
df['Home_BaseAvgPoints'] = df['HomeTeamID'].map(team_strength['BaseAvgPoints'])
df['Away_BaseAvgGoalsFor'] = df['AwayTeamID'].map(team_strength['BaseAvgGoalsFor'])
df['Away_BaseAvgGoalsAgainst'] = df['AwayTeamID'].map(team_strength['BaseAvgGoalsAgainst'])
df['Away_BaseAvgPoints'] = df['AwayTeamID'].map(team_strength['BaseAvgPoints'])

team_long_feats = team_long[['TeamID', 'MatchDate', 'AvgGoalsFor_L5', 'AvgGoalsAgainst_L5', 'AvgPoints_L5']].copy()
team_long_feats = team_long_feats.sort_values(['TeamID', 'MatchDate'])

def add_team_asof_features(df_src, team_id_col, prefix):
    base = df_src[df_src['MatchDate'].notna()].copy()
    out_frames = []
    for team_id, grp in base.groupby(team_id_col, sort=False):
        team_hist = team_long_feats[team_long_feats['TeamID'] == team_id]
        if team_hist.empty:
            temp = grp[['MatchID']].copy()
            temp['AvgGoalsFor_L5'] = float('nan')
            temp['AvgGoalsAgainst_L5'] = float('nan')
            temp['AvgPoints_L5'] = float('nan')
            out_frames.append(temp)
            continue
        merged = pd.merge_asof(
            grp.sort_values('MatchDate'),
            team_hist.sort_values('MatchDate'),
            on='MatchDate',
            direction='backward',
            allow_exact_matches=True
        )
        out_frames.append(merged[['MatchID', 'AvgGoalsFor_L5', 'AvgGoalsAgainst_L5', 'AvgPoints_L5']])
    out = pd.concat(out_frames, ignore_index=True)
    out = out.rename(columns={
        'AvgGoalsFor_L5': f'{prefix}_AvgGoalsFor_L5',
        'AvgGoalsAgainst_L5': f'{prefix}_AvgGoalsAgainst_L5',
        'AvgPoints_L5': f'{prefix}_AvgPoints_L5'
    })
    return out

home_asof = add_team_asof_features(df, 'HomeTeamID', 'Home')
df = df.merge(home_asof, on='MatchID', how='left')

away_asof = add_team_asof_features(df, 'AwayTeamID', 'Away')
df = df.merge(away_asof, on='MatchID', how='left')

h2h_feats = add_h2h_features(df)
df = df.merge(h2h_feats, on='MatchID', how='left')

# 4. Split nach 'Played'
train_df   = df[df['Played'] == True].copy()
predict_df = df[df['Played'] == False].copy()

# --- Nur die nächsten 9 ungespielten Spiele nach Datum ---
if False and PREDICTION_MODE == 'future' and not predict_df.empty:
    predict_df['MatchDate'] = pd.to_datetime(predict_df['MatchDate'], errors='coerce')
    predict_df = predict_df.sort_values('MatchDate').head(9).copy()
    print(f"Nächste ungespielte Spiele (bis zu 9): {len(predict_df)}")

# 5. Ziel (numerisch)
train_df['GoalDiff'] = train_df['HomeGoals'] - train_df['AwayGoals']
train_df = train_df[train_df['GoalDiff'].notna()].copy()

# 7. Features (Achtung: kommen aus match_stats und sind bei ungespielten oft NaN – XGBoost kann NaN handlen)
features = [
    'Home_BaseAvgGoalsFor', 'Home_BaseAvgGoalsAgainst', 'Home_BaseAvgPoints',
    'Away_BaseAvgGoalsFor', 'Away_BaseAvgGoalsAgainst', 'Away_BaseAvgPoints',
    'Home_AvgGoalsFor_L5', 'Home_AvgGoalsAgainst_L5', 'Home_AvgPoints_L5',
    'Away_AvgGoalsFor_L5', 'Away_AvgGoalsAgainst_L5', 'Away_AvgPoints_L5',
    'H2H_Combined_AvgGoalDiff', 'H2H_Combined_AvgGoalsFor', 'H2H_Combined_AvgGoalsAgainst',
    'H2H_Combined_AvgPoints', 'H2H_Combined_WinRate', 'H2H_Combined_MatchCount',
    'H2H_Venue_AvgGoalDiff', 'H2H_Venue_AvgGoalsFor', 'H2H_Venue_AvgGoalsAgainst',
    'H2H_Venue_AvgPoints', 'H2H_Venue_WinRate', 'H2H_Venue_MatchCount'
]

match_stats_features = [
    'HomePossession', 'AwayPossession',
    'HomeShots', 'AwayShots',
    'HomeShotsOnTarget', 'AwayShotsOnTarget',
    'HomePasses', 'AwayPasses',
    'HomePassAccuracy', 'AwayPassAccuracy',
    'HomeFouls', 'AwayFouls',
    'HomeYellowCard', 'AwayYellowCard',
    'HomeRedCard', 'AwayRedCard',
    'HomeOffsides', 'AwayOffsides',
    'HomeCorners', 'AwayCorners'
]
features += match_stats_features

weather_features = [
    'Weather_Temperature_C',
    'Weather_Pressure',
    'Weather_Humidity',
    'Weather_WindSpeed',
    'Weather_WindDirection',
    'Weather_Rain',
    'Weather_Snow'
]
features += weather_features
weight_cols = [f'Weight_{feat}' for feat in features]

missing = [f for f in features if f not in train_df.columns]
if missing:
    raise ValueError(f"Fehlende Feature-Spalten im Trainingsdatensatz: {missing}")

def load_reference_results(primary_path, fallback_path=None):
    for path in [primary_path, fallback_path]:
        if not path or not os.path.exists(path):
            continue
        try:
            ref = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            continue
        if not {'MatchID', 'HomeGoals', 'AwayGoals'}.issubset(ref.columns):
            try:
                ref = pd.read_csv(
                    path,
                    header=None,
                    names=['MatchID', 'HomeGoals', 'AwayGoals', 'Result'],
                    usecols=[0, 1, 2, 3]
                )
            except pd.errors.EmptyDataError:
                continue
        required = {'MatchID', 'HomeGoals', 'AwayGoals'}
        if not required.issubset(ref.columns):
            raise ValueError(f"Reference file missing columns: {sorted(required - set(ref.columns))}")
        ref = ref.copy()
        ref['HomeGoals'] = pd.to_numeric(ref['HomeGoals'], errors='coerce')
        ref['AwayGoals'] = pd.to_numeric(ref['AwayGoals'], errors='coerce')
        ref = ref.dropna(subset=['MatchID', 'HomeGoals', 'AwayGoals'])
        if 'Result' not in ref.columns:
            ref['Result'] = ref.apply(
                lambda r: 'H' if r['HomeGoals'] > r['AwayGoals']
                else ('A' if r['HomeGoals'] < r['AwayGoals'] else 'D'),
                axis=1
            )
        return ref.set_index('MatchID')
    return None

def build_prediction_frame(df_src, ref_results, mode, future_limit=9, reference_limit=None):
    if mode == 'reference':
        if ref_results is None or ref_results.empty:
            raise ValueError(
                "PREDICTION_MODE='reference' requires match_results_references.csv "
                "with valid MatchID, HomeGoals, and AwayGoals rows."
            )
        ref_ids = pd.Index(ref_results.index)
        pred = df_src[df_src['MatchID'].isin(ref_ids)].copy()
        if pred.empty:
            raise ValueError(
                "No MatchIDs from match_results_references.csv were found in the main dataset."
            )
        pred['MatchDate'] = pd.to_datetime(pred['MatchDate'], errors='coerce')
        pred = pred.sort_values('MatchDate').copy()
        if reference_limit is not None:
            pred = pred.head(int(reference_limit)).copy()
        missing_ids = sorted(set(ref_ids.tolist()) - set(pred['MatchID'].tolist()))
        if missing_ids:
            print(f"Reference mode: {len(missing_ids)} MatchIDs from the reference file were not found in the dataset.")
        print(f"Referenzspiele fuer Debugging/Training: {len(pred)}")
        return pred

    if mode != 'future':
        raise ValueError("PREDICTION_MODE must be either 'future' or 'reference'.")

    pred = df_src[df_src['Played'] == False].copy()
    if not pred.empty:
        pred['MatchDate'] = pd.to_datetime(pred['MatchDate'], errors='coerce')
        pred = pred.sort_values('MatchDate').head(future_limit).copy()
    print(f"Naechste ungespielte Spiele (bis zu {future_limit}): {len(pred)}")
    return pred

def mean_available(values, default_value=1.25):
    valid = [float(v) for v in values if pd.notna(v)]
    if not valid:
        return float(default_value)
    return float(sum(valid) / len(valid))

def estimate_scoreline(match_row, predicted_goal_diff, predicted_result):
    home_attack = mean_available([
        match_row.get('Home_BaseAvgGoalsFor'),
        match_row.get('Home_AvgGoalsFor_L5')
    ], default_value=1.5)
    away_defense = mean_available([
        match_row.get('Away_BaseAvgGoalsAgainst'),
        match_row.get('Away_AvgGoalsAgainst_L5')
    ], default_value=1.4)
    away_attack = mean_available([
        match_row.get('Away_BaseAvgGoalsFor'),
        match_row.get('Away_AvgGoalsFor_L5')
    ], default_value=1.2)
    home_defense = mean_available([
        match_row.get('Home_BaseAvgGoalsAgainst'),
        match_row.get('Home_AvgGoalsAgainst_L5')
    ], default_value=1.3)

    total_goals = max(0.2, mean_available([
        (home_attack + away_defense) / 2.0,
        (away_attack + home_defense) / 2.0
    ], default_value=2.6) * 2.0)

    exp_home = (total_goals + predicted_goal_diff) / 2.0
    exp_away = total_goals - exp_home
    if exp_home < 0:
        exp_home = 0.0
        exp_away = total_goals
    if exp_away < 0:
        exp_away = 0.0
        exp_home = total_goals

    pred_home_goals = int(round(exp_home))
    pred_away_goals = int(round(exp_away))

    if predicted_result == 'H' and pred_home_goals <= pred_away_goals:
        pred_home_goals = pred_away_goals + 1
    elif predicted_result == 'A' and pred_away_goals <= pred_home_goals:
        pred_away_goals = pred_home_goals + 1
    elif predicted_result == 'D' and pred_home_goals != pred_away_goals:
        draw_goals = int(round((exp_home + exp_away) / 2.0))
        pred_home_goals = draw_goals
        pred_away_goals = draw_goals

    return (
        float(exp_home),
        float(exp_away),
        int(pred_home_goals),
        int(pred_away_goals)
    )

def compute_pareto_front(df, nll_col='AvgNLL', acc_col='Accuracy'):
    base = df.dropna(subset=[nll_col, acc_col]).copy()
    if base.empty:
        return base
    base = base.sort_values([nll_col, acc_col], ascending=[True, False])
    pareto_rows = []
    best_acc = -float('inf')
    for _, row in base.iterrows():
        if row[acc_col] > best_acc:
            pareto_rows.append(row)
            best_acc = row[acc_col]
    return pd.DataFrame(pareto_rows)

def build_pareto_decision_set(df, target_size=PARETO_TARGET_SIZE):
    strict = compute_pareto_front(df)
    if strict.empty:
        return strict

    ranked = df.copy()
    if 'Pred_AvgNLL' not in ranked.columns:
        ranked['Pred_AvgNLL'] = float('nan')
    if 'Pred_Accuracy' not in ranked.columns:
        ranked['Pred_Accuracy'] = float('nan')
    ranked['AvgNLL'] = pd.to_numeric(ranked['AvgNLL'], errors='coerce')
    ranked['Accuracy'] = pd.to_numeric(ranked['Accuracy'], errors='coerce')
    ranked['Pred_AvgNLL'] = pd.to_numeric(ranked['Pred_AvgNLL'], errors='coerce')
    ranked['Pred_Accuracy'] = pd.to_numeric(ranked['Pred_Accuracy'], errors='coerce')
    ranked['Ranking_AvgNLL'] = ranked['AvgNLL'].combine_first(ranked['Pred_AvgNLL'])
    ranked['Ranking_Accuracy'] = ranked['Accuracy'].combine_first(ranked['Pred_Accuracy'])
    ranked = ranked.dropna(subset=['Ranking_AvgNLL', 'Ranking_Accuracy']).copy()
    if ranked.empty:
        out = strict.copy()
        out['IsStrictPareto'] = True
        return out

    ranked = ranked.sort_values(
        ['Ranking_AvgNLL', 'Ranking_Accuracy'],
        ascending=[True, False]
    )
    strict_ids = set(strict.index.tolist())
    decision = strict.copy()
    decision['IsStrictPareto'] = True

    if len(decision) < target_size:
        fillers = ranked.loc[~ranked.index.isin(strict_ids)].head(target_size - len(decision)).copy()
        if not fillers.empty:
            fillers['IsStrictPareto'] = False
            decision = pd.concat([decision, fillers], ignore_index=False)

    decision = decision.sort_values(
        ['IsStrictPareto', 'Ranking_AvgNLL', 'Ranking_Accuracy'],
        ascending=[False, True, False]
    ).head(target_size)
    decision = decision.reset_index(drop=True)
    decision['DecisionRank'] = range(1, len(decision) + 1)
    return decision

def rank_component(series, smaller_is_better=False):
    values = pd.to_numeric(series, errors='coerce')
    ranked = pd.Series(float('nan'), index=values.index, dtype='float64')
    valid = values.notna()
    if not valid.any():
        return ranked
    if smaller_is_better:
        ranked.loc[valid] = values.loc[valid].rank(ascending=False, pct=True)
    else:
        ranked.loc[valid] = values.loc[valid].rank(ascending=True, pct=True)
    return ranked

def build_future_candidate_ranking(df, target_size=PARETO_TARGET_SIZE):
    ranked = df.copy()
    for col in [
        'Pred_AvgNLL', 'Pred_Accuracy',
        'MeanTopProb', 'MeanProbGap', 'MeanEntropy'
    ]:
        if col not in ranked.columns:
            ranked[col] = float('nan')
        ranked[col] = pd.to_numeric(ranked[col], errors='coerce')

    ranked['HasSurrogateMetrics'] = (
        ranked['Pred_AvgNLL'].notna() & ranked['Pred_Accuracy'].notna()
    )
    ranked['RecommendationSource'] = ranked['HasSurrogateMetrics'].map(
        lambda has_surrogate: 'surrogate' if has_surrogate else 'confidence_fallback'
    )

    ranked['PredNLLComponent'] = rank_component(ranked['Pred_AvgNLL'], smaller_is_better=True)
    ranked['PredAccuracyComponent'] = rank_component(ranked['Pred_Accuracy'], smaller_is_better=False)
    ranked['ConfidenceComponent'] = rank_component(ranked['MeanTopProb'], smaller_is_better=False)
    ranked['GapComponent'] = rank_component(ranked['MeanProbGap'], smaller_is_better=False)
    ranked['EntropyComponent'] = rank_component(ranked['MeanEntropy'], smaller_is_better=True)

    fallback_score = (
        0.45 * ranked['ConfidenceComponent'].fillna(0.0)
        + 0.35 * ranked['GapComponent'].fillna(0.0)
        + 0.20 * ranked['EntropyComponent'].fillna(0.0)
    )
    surrogate_balanced = (
        0.50 * ranked['PredNLLComponent'].fillna(0.0)
        + 0.50 * ranked['PredAccuracyComponent'].fillna(0.0)
    )
    surrogate_conservative = (
        0.70 * ranked['PredNLLComponent'].fillna(0.0)
        + 0.20 * ranked['ConfidenceComponent'].fillna(0.0)
        + 0.10 * ranked['EntropyComponent'].fillna(0.0)
    )
    surrogate_aggressive = (
        0.70 * ranked['PredAccuracyComponent'].fillna(0.0)
        + 0.20 * ranked['GapComponent'].fillna(0.0)
        + 0.10 * ranked['ConfidenceComponent'].fillna(0.0)
    )
    fallback_conservative = (
        0.60 * ranked['ConfidenceComponent'].fillna(0.0)
        + 0.40 * ranked['EntropyComponent'].fillna(0.0)
    )
    fallback_aggressive = (
        0.60 * ranked['GapComponent'].fillna(0.0)
        + 0.40 * ranked['ConfidenceComponent'].fillna(0.0)
    )

    ranked['BalancedScore'] = fallback_score
    ranked['ConservativeScore'] = fallback_conservative
    ranked['AggressiveScore'] = fallback_aggressive

    has_surrogate = ranked['HasSurrogateMetrics']
    ranked.loc[has_surrogate, 'BalancedScore'] = surrogate_balanced.loc[has_surrogate]
    ranked.loc[has_surrogate, 'ConservativeScore'] = surrogate_conservative.loc[has_surrogate]
    ranked.loc[has_surrogate, 'AggressiveScore'] = surrogate_aggressive.loc[has_surrogate]

    ranked = ranked.sort_values(
        ['BalancedScore', 'ConservativeScore', 'AggressiveScore'],
        ascending=[False, False, False]
    ).copy()
    if ranked.empty:
        return ranked

    balanced_pick = ranked.sort_values('BalancedScore', ascending=False).head(1).copy()
    conservative_pick = ranked.sort_values('ConservativeScore', ascending=False).head(1).copy()
    aggressive_pick = ranked.sort_values('AggressiveScore', ascending=False).head(1).copy()

    decision = pd.concat([balanced_pick, conservative_pick, aggressive_pick, ranked], ignore_index=False)
    decision = decision.drop_duplicates(subset=['RunID']).head(target_size).copy()
    decision = decision.reset_index(drop=True)
    decision['DecisionRank'] = range(1, len(decision) + 1)

    balanced_run_id = balanced_pick['RunID'].iloc[0]
    conservative_run_id = conservative_pick['RunID'].iloc[0]
    aggressive_run_id = aggressive_pick['RunID'].iloc[0]
    decision['IsBalancedRecommendation'] = decision['RunID'] == balanced_run_id
    decision['IsConservativeRecommendation'] = decision['RunID'] == conservative_run_id
    decision['IsAggressiveRecommendation'] = decision['RunID'] == aggressive_run_id

    def recommendation_label(row):
        labels = []
        if row['IsBalancedRecommendation']:
            labels.append('Balanced')
        if row['IsConservativeRecommendation']:
            labels.append('Conservative')
        if row['IsAggressiveRecommendation']:
            labels.append('Aggressive')
        return ', '.join(labels) if labels else 'Candidate'

    decision['RecommendationLabel'] = decision.apply(recommendation_label, axis=1)
    return decision

def load_run_history(path, weight_cols):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        hist = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    for col in weight_cols + ['AvgNLL', 'Accuracy', 'H2H_K']:
        if col not in hist.columns:
            hist[col] = float('nan')
    if 'H2H_K' in hist.columns:
        hist['H2H_K'] = hist['H2H_K'].fillna(H2H_K_DEFAULT)
    for col in weight_cols + ['AvgNLL', 'Accuracy', 'H2H_K']:
        hist[col] = pd.to_numeric(hist[col], errors='coerce')
    hist = hist.dropna(subset=weight_cols + ['AvgNLL', 'Accuracy', 'H2H_K'])
    return hist

def train_surrogate_model(history_df, feature_cols, target_col):
    X = history_df[feature_cols]
    y = history_df[target_col]
    if SURROGATE_MODEL == 'nn':
        model = make_pipeline(
            StandardScaler(),
            MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=500, random_state=42)
        )
    else:
        model = GradientBoostingRegressor(random_state=42)
    model.fit(X, y)
    return model

def generate_candidate_df(num, features, k_range):
    rows = []
    for _ in range(num):
        row = {f'Weight_{feat}': random.random() * 2.0 for feat in features}
        row['H2H_K'] = random.randint(int(k_range[0]), int(k_range[1]))
        rows.append(row)
    return pd.DataFrame(rows)

def select_candidates_with_surrogate(candidates_df, pred_nll, pred_acc, max_runs, random_frac):
    df = candidates_df.copy()
    df['Pred_AvgNLL'] = pred_nll
    df['Pred_Accuracy'] = pred_acc
    pareto = compute_pareto_front(df, 'Pred_AvgNLL', 'Pred_Accuracy')
    pareto = pareto.sort_values(['Pred_AvgNLL', 'Pred_Accuracy'], ascending=[True, False])

    explore_count = int(max_runs * random_frac)
    exploit_count = max_runs - explore_count

    selected = pareto.head(exploit_count)
    if len(selected) < exploit_count:
        remaining = df.drop(selected.index)
        fill_needed = exploit_count - len(selected)
        fill = remaining.sort_values(['Pred_AvgNLL', 'Pred_Accuracy'], ascending=[True, False]).head(fill_needed)
        selected = pd.concat([selected, fill])

    remaining = df.drop(selected.index)
    if explore_count > 0 and not remaining.empty:
        explore = remaining.sample(n=min(explore_count, len(remaining)), random_state=42)
        selected = pd.concat([selected, explore])

    return selected.reset_index(drop=True)

# 8. Trainieren (pro Run, nach H2H-Skalierung)
ref_results = load_reference_results(RESULTS_PATH, FALLBACK_RESULTS_PATH)
print(f"Prediction mode: {PREDICTION_MODE}")
print(f"Output path: {OUTPUT_PATH}")
print(f"Surrogate history source: {RUN_HISTORY_SOURCE_PATH}")

predict_df = build_prediction_frame(
    df,
    ref_results,
    PREDICTION_MODE,
    future_limit=9,
    reference_limit=REFERENCE_PREDICTION_LIMIT
)

train_df = df[df['Played'] == True].copy()
if PREDICTION_MODE == 'reference':
    train_df = train_df[~train_df['MatchID'].isin(predict_df['MatchID'])].copy()
    print(f"Trainingsspiele nach Ausschluss der Referenzspiele: {len(train_df)}")

train_df['GoalDiff'] = train_df['HomeGoals'] - train_df['AwayGoals']
train_df = train_df[train_df['GoalDiff'].notna()].copy()
if train_df.empty:
    raise ValueError("Training dataset is empty after applying the selected prediction mode.")

X_train, X_val, y_train, y_val = train_test_split(
    train_df[features], train_df['GoalDiff'], test_size=0.2, random_state=42
)

run_limit = MAX_RUNS if (PREDICTION_MODE == 'future' or ref_results is not None) else 1

print("GoalDiff NaNs:", train_df['GoalDiff'].isna().sum())
print("X_train NaNs (raw):", X_train.isna().sum().sum())
if PREDICTION_MODE == 'reference' and ref_results is None:
    print(f"Reference results not found at {RESULTS_PATH} (or fallback {FALLBACK_RESULTS_PATH}); running only 1 weight set.")


# 9. Vorhersage (nur naechste 9)
if predict_df.empty:
    pred_df = pd.DataFrame(columns=['MatchID','MatchDate','HomeTeam','AwayTeam','PredictedGoalDiff'])
    print("Keine ungespielten Spiele gefunden. Leere Ergebnis-Tabelle:")
    print(pred_df.head(9))
else:
    X_train_base = X_train.copy()
    X_pred_base = predict_df[features].copy()

    draw_margin = 0.5

    def normal_cdf(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def outcome_from_row(row):
        if row['HomeGoals'] > row['AwayGoals']:
            return 'H'
        if row['HomeGoals'] < row['AwayGoals']:
            return 'A'
        return 'D'

    all_runs = []
    run_metrics = []
    best_score = None
    best_run = None

    history_df = load_run_history(RUN_HISTORY_SOURCE_PATH, weight_cols)
    use_surrogate = len(history_df) >= SURROGATE_MIN_HISTORY

    if use_surrogate:
        feature_cols = weight_cols + ['H2H_K']
        nll_model = train_surrogate_model(history_df, feature_cols, 'AvgNLL')
        acc_model = train_surrogate_model(history_df, feature_cols, 'Accuracy')
        candidate_df = generate_candidate_df(max(SURROGATE_CANDIDATES, run_limit), features, H2H_K_RANGE)
        pred_nll = nll_model.predict(candidate_df[feature_cols])
        pred_acc = acc_model.predict(candidate_df[feature_cols])
        selected_df = select_candidates_with_surrogate(
            candidate_df,
            pred_nll,
            pred_acc,
            run_limit,
            SURROGATE_RANDOM_FRACTION
        )
    else:
        selected_df = generate_candidate_df(run_limit, features, H2H_K_RANGE)

    batch_id = 1
    if not history_df.empty and 'BatchID' in history_df.columns:
        try:
            batch_id = int(history_df['BatchID'].max()) + 1
        except Exception:
            batch_id = 1

    for idx, cand in selected_df.iterrows():
        run_id = idx + 1
        run_k = int(cand['H2H_K'])
        pred_run_nll = float(cand['Pred_AvgNLL']) if 'Pred_AvgNLL' in cand.index and pd.notna(cand['Pred_AvgNLL']) else float('nan')
        pred_run_acc = float(cand['Pred_Accuracy']) if 'Pred_Accuracy' in cand.index and pd.notna(cand['Pred_Accuracy']) else float('nan')
        weights = {feat: float(cand[f'Weight_{feat}']) for feat in features}
        weight_vec = pd.Series(weights, index=features).values

        X_train_scaled = apply_h2h_scaling(X_train_base, run_k)
        X_pred_scaled = apply_h2h_scaling(X_pred_base, run_k)

        if len(X_train_scaled) != len(y_train):
            raise ValueError(
                f"Training feature/target length mismatch: X_train_scaled={len(X_train_scaled)} "
                f"vs y_train={len(y_train)}"
            )

        imputer = SimpleImputer(strategy='median')
        X_train_imp = imputer.fit_transform(X_train_scaled)
        X_pred_imp = imputer.transform(X_pred_scaled)

        X_train_w = X_train_imp * weight_vec
        model = SklearnModel(n_trees=50)
        model.fit(X_train_w, y_train.values)

        train_preds = model.predict(X_train_w)
        residuals = y_train.values - train_preds
        sigma = float(pd.Series(residuals).std())
        if not math.isfinite(sigma) or sigma <= 0:
            sigma = 1.0

        X_pred_w = X_pred_imp * weight_vec
        preds = model.predict(X_pred_w)

        win_probs = []
        draw_probs = []
        lose_probs = []
        for mu in preds:
            if not math.isfinite(mu):
                win_probs.append(float('nan'))
                draw_probs.append(float('nan'))
                lose_probs.append(float('nan'))
                continue
            z_hi = (draw_margin - mu) / sigma
            z_lo = (-draw_margin - mu) / sigma
            cdf_hi = normal_cdf(z_hi)
            cdf_lo = normal_cdf(z_lo)
            draw_p = max(0.0, min(1.0, cdf_hi - cdf_lo))
            lose_p = max(0.0, min(1.0, cdf_lo))
            win_p = max(0.0, min(1.0, 1.0 - cdf_hi))
            win_probs.append(win_p)
            draw_probs.append(draw_p)
            lose_probs.append(lose_p)

        pred_df = pd.DataFrame(index=predict_df.index)
        pred_df['RunID'] = run_id
        pred_df['WinProb'] = win_probs
        pred_df['DrawProb'] = draw_probs
        pred_df['LoseProb'] = lose_probs
        pred_df['MatchID']   = predict_df['MatchID'].values
        pred_df['MatchDate'] = predict_df['MatchDate'].values
        pred_df['HomeTeam']  = predict_df['HomeTeam'].values
        pred_df['AwayTeam']  = predict_df['AwayTeam'].values
        pred_df['H2H_K'] = run_k
        pred_df['PredictedGoalDiff'] = preds
        pred_df['PredictedResult'] = pred_df[['WinProb', 'DrawProb', 'LoseProb']].idxmax(axis=1)
        pred_df['PredictedResult'] = pred_df['PredictedResult'].map({'WinProb': 'H', 'DrawProb': 'D', 'LoseProb': 'A'})

        score_estimates = [
            estimate_scoreline(predict_df.loc[idx], pred_df.at[idx, 'PredictedGoalDiff'], pred_df.at[idx, 'PredictedResult'])
            for idx in pred_df.index
        ]
        pred_df['ExpectedHomeGoals'] = [row[0] for row in score_estimates]
        pred_df['ExpectedAwayGoals'] = [row[1] for row in score_estimates]
        pred_df['PredictedHomeGoals'] = [row[2] for row in score_estimates]
        pred_df['PredictedAwayGoals'] = [row[3] for row in score_estimates]
        pred_df['PredictedScoreline'] = (
            pred_df['PredictedHomeGoals'].astype(int).astype(str)
            + '-'
            + pred_df['PredictedAwayGoals'].astype(int).astype(str)
        )

        if 'H2H_Combined_MatchCount' in predict_df.columns:
            pred_df['H2H_Combined_MatchCount'] = predict_df['H2H_Combined_MatchCount'].values
        if 'H2H_Venue_MatchCount' in predict_df.columns:
            pred_df['H2H_Venue_MatchCount'] = predict_df['H2H_Venue_MatchCount'].values

        for feat in features:
            pred_df[f'Weight_{feat}'] = weights[feat]

        if 'H2H_Combined_MatchCount' in pred_df.columns:
            pred_df['H2H_Combined_Alpha'] = pred_df['H2H_Combined_MatchCount'].apply(
                lambda c: c / (c + run_k) if pd.notna(c) and c >= 0 else float('nan')
            )
        if 'H2H_Venue_MatchCount' in pred_df.columns:
            pred_df['H2H_Venue_Alpha'] = pred_df['H2H_Venue_MatchCount'].apply(
                lambda c: c / (c + run_k) if pd.notna(c) and c >= 0 else float('nan')
            )

        if 'H2H_Combined_Alpha' in pred_df.columns:
            for feat in H2H_COMBINED_FEATURES:
                if f'Weight_{feat}' in pred_df.columns:
                    pred_df[f'EffectiveWeight_{feat}'] = pred_df[f'Weight_{feat}'] * pred_df['H2H_Combined_Alpha']
        if 'H2H_Venue_Alpha' in pred_df.columns:
            for feat in H2H_VENUE_FEATURES:
                if f'Weight_{feat}' in pred_df.columns:
                    pred_df[f'EffectiveWeight_{feat}'] = pred_df[f'Weight_{feat}'] * pred_df['H2H_Venue_Alpha']

        run_score = None
        run_accuracy = None
        run_count = 0
        matched_reference_count = 0
        early_stop = False
        if ref_results is not None:
            merged = pred_df.merge(
                ref_results[['HomeGoals', 'AwayGoals', 'Result']],
                left_on='MatchID',
                right_index=True,
                how='left'
            )
            merged['ActualResult'] = merged.apply(
                lambda r: outcome_from_row(r) if pd.notna(r['HomeGoals']) else float('nan'),
                axis=1
            )

            def prob_for_actual(row):
                if row['ActualResult'] == 'H':
                    return row['WinProb']
                if row['ActualResult'] == 'D':
                    return row['DrawProb']
                if row['ActualResult'] == 'A':
                    return row['LoseProb']
                return float('nan')

            merged['ProbActual'] = merged.apply(prob_for_actual, axis=1)
            merged['ProbActual'] = merged['ProbActual'].clip(lower=1e-12)
            merged['MatchNLL'] = merged['ProbActual'].apply(lambda p: -math.log(p) if pd.notna(p) else float('nan'))
            merged['IsCorrect'] = (
                merged['PredictedResult'].notna()
                & merged['ActualResult'].notna()
                & (merged['PredictedResult'] == merged['ActualResult'])
            )
            valid_probs = merged['ProbActual'].dropna()
            if not valid_probs.empty:
                run_score = float((-valid_probs.apply(math.log)).mean())
            pred_df = merged

            actual_rows = merged['ActualResult'].dropna()
            matched_reference_count = int(actual_rows.count())
            if not actual_rows.empty:
                correct_mask = (merged.loc[actual_rows.index, 'PredictedResult'] == actual_rows)
                run_accuracy = float(correct_mask.mean())
                run_count = int(correct_mask.count())
                all_correct = correct_mask.all()
                if all_correct:
                    best_run = run_id
                    best_score = run_score
                    early_stop = True

        if run_score is not None:
            if best_score is None or run_score < best_score:
                best_score = run_score
                best_run = run_id

        prob_frame = pred_df[['WinProb', 'DrawProb', 'LoseProb']].apply(pd.to_numeric, errors='coerce')
        top_prob = prob_frame.max(axis=1)
        second_prob = prob_frame.apply(
            lambda row: row.nlargest(2).iloc[-1] if row.notna().sum() >= 2 else float('nan'),
            axis=1
        )
        prob_gap = top_prob - second_prob
        prob_entropy = prob_frame.apply(
            lambda row: -sum(
                p * math.log(max(p, 1e-12))
                for p in row.dropna()
            ) if row.notna().any() else float('nan'),
            axis=1
        )
        mean_top_prob = float(top_prob.mean()) if not top_prob.dropna().empty else float('nan')
        mean_prob_gap = float(prob_gap.mean()) if not prob_gap.dropna().empty else float('nan')
        mean_entropy = float(prob_entropy.mean()) if not prob_entropy.dropna().empty else float('nan')

        resolved_run_nll = run_score if run_score is not None else pred_run_nll
        resolved_run_accuracy = run_accuracy if run_accuracy is not None else pred_run_acc
        if matched_reference_count > 0:
            metric_source = 'reference'
        elif pd.notna(pred_run_nll) or pd.notna(pred_run_acc):
            metric_source = 'surrogate'
        else:
            metric_source = 'none'

        pred_df['RunResolvedAvgNLL'] = resolved_run_nll
        pred_df['RunResolvedAccuracy'] = resolved_run_accuracy
        pred_df['RunMetricSource'] = metric_source
        pred_df['RunActualAvgNLL'] = run_score
        pred_df['RunActualAccuracy'] = run_accuracy
        pred_df['RunPredictedAvgNLL'] = pred_run_nll
        pred_df['RunPredictedAccuracy'] = pred_run_acc

        metric_row = {
            'RunID': run_id,
            'BatchID': batch_id,
            'H2H_K': run_k,
            'AvgNLL': run_score,
            'Accuracy': run_accuracy,
            'NumMatchesScored': run_count,
            'MatchedReferenceCount': matched_reference_count,
            'Pred_AvgNLL': pred_run_nll,
            'Pred_Accuracy': pred_run_acc,
            'ResolvedAvgNLL': resolved_run_nll,
            'ResolvedAccuracy': resolved_run_accuracy,
            'MetricSource': metric_source,
            'MeanTopProb': mean_top_prob,
            'MeanProbGap': mean_prob_gap,
            'MeanEntropy': mean_entropy
        }
        for feat in features:
            metric_row[f'Weight_{feat}'] = weights[feat]
        run_metrics.append(metric_row)
        all_runs.append(pred_df)

        if early_stop:
            break

    all_pred_df = pd.concat(all_runs, ignore_index=True)
    all_pred_df.to_csv(PREDICTION_OUT_PATH, index=False)

    cols = ['RunID','MatchID','MatchDate','HomeTeam','AwayTeam','WinProb','DrawProb','LoseProb']
    print(all_pred_df[cols].head(10))
    if best_run is not None:
        print(f"Best run: {best_run} (avg NLL={best_score:.6f})")
    if run_metrics:
        summary_df = pd.DataFrame(run_metrics)
        summary_df['AvgNLL'] = pd.to_numeric(summary_df['AvgNLL'], errors='coerce')
        summary_df['Accuracy'] = pd.to_numeric(summary_df['Accuracy'], errors='coerce')
        summary_df['Pred_AvgNLL'] = pd.to_numeric(summary_df['Pred_AvgNLL'], errors='coerce')
        summary_df['Pred_Accuracy'] = pd.to_numeric(summary_df['Pred_Accuracy'], errors='coerce')
        summary_df['MeanTopProb'] = pd.to_numeric(summary_df['MeanTopProb'], errors='coerce')
        summary_df['MeanProbGap'] = pd.to_numeric(summary_df['MeanProbGap'], errors='coerce')
        summary_df['MeanEntropy'] = pd.to_numeric(summary_df['MeanEntropy'], errors='coerce')
        summary_df['ScoredAgainstReferences'] = summary_df['MatchedReferenceCount'] > 0
        summary_df['Ranking_AvgNLL'] = summary_df['AvgNLL'].combine_first(summary_df['Pred_AvgNLL'])
        summary_df['Ranking_Accuracy'] = summary_df['Accuracy'].combine_first(summary_df['Pred_Accuracy'])
        summary_df['ResolvedAvgNLL'] = pd.to_numeric(summary_df['ResolvedAvgNLL'], errors='coerce')
        summary_df['ResolvedAccuracy'] = pd.to_numeric(summary_df['ResolvedAccuracy'], errors='coerce')
        summary_df = summary_df.sort_values(
            ['ScoredAgainstReferences', 'Ranking_AvgNLL', 'Ranking_Accuracy'],
            ascending=[False, True, False]
        )
        summary_df.to_csv(RUN_SUMMARY_OUT_PATH, index=False)
        print(summary_df.head(5))

        if os.path.exists(RUN_HISTORY_PATH):
            try:
                existing_mode_history = pd.read_csv(RUN_HISTORY_PATH)
            except pd.errors.EmptyDataError:
                existing_mode_history = pd.DataFrame()
        else:
            existing_mode_history = pd.DataFrame()

        if existing_mode_history.empty:
            history_updated = summary_df.copy()
        else:
            history_updated = pd.DataFrame.from_records(
                existing_mode_history.to_dict('records') + summary_df.to_dict('records')
            )
        history_updated.to_csv(RUN_HISTORY_PATH, index=False)

        if PREDICTION_MODE == 'reference':
            decision_df = build_pareto_decision_set(history_updated, PARETO_TARGET_SIZE)
        else:
            decision_df = build_future_candidate_ranking(summary_df, PARETO_TARGET_SIZE)
        decision_df.to_csv(PARETO_OUT_PATH, index=False)
        print(decision_df.head(5))

        if PREDICTION_MODE == 'future' and not decision_df.empty:
            balanced_choice = decision_df[decision_df['IsBalancedRecommendation']].head(1)
            if balanced_choice.empty:
                balanced_choice = decision_df.head(1)
            selected_run_id = int(balanced_choice['RunID'].iloc[0])
            selected_label = balanced_choice['RecommendationLabel'].iloc[0]

            outcome_table = all_pred_df[all_pred_df['RunID'] == selected_run_id].copy()
            outcome_table['MostLikelyOutcomeProbability'] = outcome_table[['WinProb', 'DrawProb', 'LoseProb']].max(axis=1)
            outcome_table['MostLikelyOutcome'] = outcome_table['PredictedResult'].map({
                'H': 'HomeWin',
                'D': 'Draw',
                'A': 'AwayWin'
            })
            outcome_table['RecommendedRunID'] = selected_run_id
            outcome_table['RecommendationLabel'] = selected_label

            final_cols = [
                'MatchID', 'MatchDate', 'HomeTeam', 'AwayTeam',
                'RecommendedRunID', 'RecommendationLabel',
                'WinProb', 'DrawProb', 'LoseProb',
                'MostLikelyOutcome', 'MostLikelyOutcomeProbability',
                'PredictedGoalDiff',
                'ExpectedHomeGoals', 'ExpectedAwayGoals',
                'PredictedHomeGoals', 'PredictedAwayGoals',
                'PredictedScoreline', 'H2H_K'
            ]
            outcome_table = outcome_table[final_cols].sort_values('MatchDate')
            outcome_table.to_csv(FUTURE_OUTCOME_TABLE_PATH, index=False)
            print(outcome_table.head(10))
