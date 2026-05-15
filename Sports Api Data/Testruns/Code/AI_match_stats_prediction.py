import math
import os
import random
from datetime import datetime
import pandas as pd
from bartpy.sklearnmodel import SklearnModel
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.model_selection import KFold, train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# Pfad zum Datenordner anpassen
DATA_PATH = r'C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection'
TESTRUNS_PATH = r'C:/AI Projekt/KI-Projekt/Sports Api Data/Testruns'
FUTURE_OUTPUT_PATH = os.path.join(TESTRUNS_PATH, 'Datacollection future')
REFERENCE_OUTPUT_PATH = os.path.join(TESTRUNS_PATH, 'Datacollection reference')
WEATHER_HIST_PATH = os.path.join(DATA_PATH, 'historical_weather_data_78.csv')
LINEUPS_PATH = os.path.join(DATA_PATH, 'lineups_league_78.csv')
INJURIES_PATH = os.path.join(DATA_PATH, 'injuries_league_78.csv')
PLAYER_STATS_PATH = os.path.join(DATA_PATH, 'player_statistics_per_fixture_league_78.csv')
MAX_RUNS = 200
RANDOM_STATE = 42
random.seed(RANDOM_STATE)

# === PREDICTION TARGET SWITCH ===
# "future"    = predict next unplayed matches
# "reference" = predict matches from match_results_references.csv for debugging/evaluation
PREDICTION_MODE = 'future'
REFERENCE_PREDICTION_LIMIT = None

# === MATCH STATS SWITCH ===
# "actual"    = use actual current-match stats (reference mode only)
# "predicted" = predict current-match stats from pre-match data only
# "off"       = remove match stats from the outcome model
MATCH_STATS_MODE = 'predicted' if PREDICTION_MODE == 'future' else 'actual'
MATCH_STATS_MODEL = 'gbr'
MATCH_STATS_CV_SPLITS = 5
MATCH_STATS_MIN_ROWS = 25

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

if MATCH_STATS_MODE not in {'actual', 'predicted', 'off'}:
    raise ValueError("MATCH_STATS_MODE must be 'actual', 'predicted', or 'off'.")
if PREDICTION_MODE == 'future' and MATCH_STATS_MODE == 'actual':
    raise ValueError("Future mode cannot use MATCH_STATS_MODE='actual' because current-match stats are unavailable before kickoff.")

os.makedirs(OUTPUT_PATH, exist_ok=True)
PREDICTION_OUT_PATH = os.path.join(OUTPUT_PATH, 'prediction_weight_runs.csv')
RUN_SUMMARY_OUT_PATH = os.path.join(OUTPUT_PATH, 'prediction_weight_run_summary.csv')
RUN_HISTORY_PATH = os.path.join(OUTPUT_PATH, 'surrogate_run_history.csv')
PARETO_OUT_PATH = DECISION_OUT_PATH
FUTURE_OUTCOME_TABLE_PATH = os.path.join(OUTPUT_PATH, 'future_outcome_table.csv')
WEATHER_FUTURE_PATH = os.path.join(DATA_PATH, 'future_weather_data_78.csv')
PREDICTED_MATCH_STATS_OUT_PATH = os.path.join(OUTPUT_PATH, 'predicted_match_stats.csv')
FUTURE_PREDICTION_SOURCE_PATH = os.path.join(FUTURE_OUTPUT_PATH, 'prediction_weight_runs.csv')
FUTURE_RUN_SUMMARY_SOURCE_PATH = os.path.join(FUTURE_OUTPUT_PATH, 'prediction_weight_run_summary.csv')
FUTURE_VS_REFERENCE_METRICS_PATH = os.path.join(FUTURE_OUTPUT_PATH, 'future_vs_reference_metrics.csv')

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
FEATURE_SCHEMA_VERSION = 'bases_v2_hybrid'

GENERAL_SUBGROUP_BLEND = {
    'GoalCreation': 0.55,
    'GameControl': 0.30,
    'DisciplineSetPiece': 0.15
}

PLAYER_MIN_APPEARANCES = 5
PLAYER_ROLLING_WINDOW = 8
PLAYER_STARTPROB_FALLBACK = 0.15
PLAYER_POSITION_IMPORTANCE = {
    'GK': 1.15,
    'DEF': 1.00,
    'MID': 1.05,
    'FWD': 1.10
}

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


def coerce_numeric_columns(df_src, columns):
    for col in columns:
        if col in df_src.columns:
            df_src[col] = pd.to_numeric(df_src[col], errors='coerce')

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
    'Home Corners': 'HomeCorners', 'Away Corners': 'AwayCorners',
    'Expected Goals (xG) Home': 'HomeXG', 'Expected Goals (xG) Away': 'AwayXG'
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
    numeric_weather_cols = [c for c in weather_all.columns if c not in ('MatchID',) and weather_all[c].dtype in (float, 'float64', 'float32', int, 'int64')]
    weather_all = weather_all.groupby('MatchID', as_index=False)[numeric_weather_cols].mean()
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

def build_player_base_features(df_src):
    result_cols = [
        'MatchID',
        'Home_PlayerBaseScore', 'Away_PlayerBaseScore',
        'Home_PlayerAbsencePenalty', 'Away_PlayerAbsencePenalty',
        'Player_BaseDiff', 'Player_AbsencePenaltyDiff'
    ]
    match_meta = df_src[[
        'MatchID', 'MatchDate', 'HomeTeamID', 'AwayTeamID',
        'HomeTeam', 'AwayTeam', 'Played'
    ]].drop_duplicates(subset=['MatchID']).copy()
    for col in ['Home_PlayerBaseScore', 'Away_PlayerBaseScore', 'Home_PlayerAbsencePenalty', 'Away_PlayerAbsencePenalty']:
        match_meta[col] = 0.0

    def safe_read_csv(path):
        if not path or not os.path.exists(path):
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()

    def to_int_id(value):
        if pd.isna(value):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def parse_start_flag(value):
        if isinstance(value, bool):
            return bool(value)
        return str(value).strip().lower() in {'true', '1', 'yes', 'y'}

    def normalize_position(value):
        key = str(value).strip().upper()
        if key in {'G', 'GK', 'GOALKEEPER'}:
            return 'GK'
        if key in {'D', 'DEF'}:
            return 'DEF'
        if key in {'M', 'MID'}:
            return 'MID'
        if key in {'F', 'FW', 'FWD'}:
            return 'FWD'
        return 'MID'

    def normalize_team_name(value):
        return str(value).strip().lower()

    match_meta['MatchDate'] = pd.to_datetime(match_meta['MatchDate'], errors='coerce')
    match_meta['MatchID'] = pd.to_numeric(match_meta['MatchID'], errors='coerce')
    match_meta = match_meta.dropna(subset=['MatchID']).copy()
    match_meta['MatchID'] = match_meta['MatchID'].astype(int)

    for col in ['HomeTeamID', 'AwayTeamID']:
        match_meta[col] = pd.to_numeric(match_meta[col], errors='coerce')

    lineups = safe_read_csv(LINEUPS_PATH)
    injuries = safe_read_csv(INJURIES_PATH)
    player_stats = safe_read_csv(PLAYER_STATS_PATH)
    if player_stats.empty:
        out = match_meta[['MatchID']].copy()
        for col in result_cols[1:]:
            out[col] = 0.0
        return out[result_cols]

    stats_rename = {
        'Team ID': 'TeamID',
        'Player ID': 'PlayerID',
        'Minutes Played': 'MinutesPlayed',
        'Total Goals': 'TotalGoals',
        'Assists': 'Assists',
        'Total Shots': 'TotalShots',
        'Shots on Target': 'ShotsOnTarget',
        'Passes': 'Passes',
        'Pass Accuracy': 'PassAccuracy',
        'Tackles': 'Tackles',
        'Interceptions': 'Interceptions',
        'Duels Won': 'DuelsWon',
        'Yellow Cards': 'YellowCards',
        'Red Cards': 'RedCards',
        'Rating': 'Rating'
    }
    player_stats = player_stats.rename(columns=stats_rename)

    for col in ['MatchID', 'TeamID', 'PlayerID']:
        if col not in player_stats.columns:
            player_stats[col] = float('nan')
        player_stats[col] = pd.to_numeric(player_stats[col], errors='coerce')

    numeric_cols = [
        'MinutesPlayed', 'TotalGoals', 'Assists', 'TotalShots', 'ShotsOnTarget',
        'Passes', 'Tackles', 'Interceptions', 'DuelsWon', 'YellowCards', 'RedCards', 'Rating'
    ]
    for col in numeric_cols:
        if col not in player_stats.columns:
            player_stats[col] = float('nan')

    if 'PassAccuracy' not in player_stats.columns:
        player_stats['PassAccuracy'] = float('nan')
    player_stats['PassAccuracy'] = pd.to_numeric(
        player_stats['PassAccuracy'].astype(str).str.replace('%', '', regex=False),
        errors='coerce'
    )

    player_stats = player_stats.merge(
        match_meta[['MatchID', 'MatchDate', 'Played']],
        on='MatchID',
        how='left'
    )
    player_stats = player_stats.dropna(subset=['MatchID', 'TeamID', 'PlayerID', 'MatchDate']).copy()
    player_stats['MatchID'] = player_stats['MatchID'].astype(int)
    player_stats['TeamID'] = player_stats['TeamID'].astype(int)
    player_stats['PlayerID'] = player_stats['PlayerID'].astype(int)

    lineups_match = pd.DataFrame(columns=['MatchID', 'TeamID', 'PlayerID', 'StartXI', 'PositionGroup'])
    if not lineups.empty:
        lineups = lineups.rename(columns={
            'Home Team ID': 'HomeTeamID',
            'Away Team ID': 'AwayTeamID',
            'Player ID': 'PlayerID',
            'Team Name': 'TeamName',
            'Pos': 'PosRaw'
        })
        for col in ['MatchID', 'PlayerID']:
            if col not in lineups.columns:
                lineups[col] = float('nan')
            lineups[col] = pd.to_numeric(lineups[col], errors='coerce')

        if 'StartXI' not in lineups.columns:
            lineups['StartXI'] = False
        lineups['StartXI'] = lineups['StartXI'].apply(parse_start_flag)

        if 'PosRaw' not in lineups.columns:
            lineups['PosRaw'] = ''
        lineups['PositionGroup'] = lineups['PosRaw'].apply(normalize_position)

        team_name_to_id = {}
        for _, row in match_meta[['HomeTeam', 'HomeTeamID']].dropna().drop_duplicates().iterrows():
            team_name_to_id[normalize_team_name(row['HomeTeam'])] = to_int_id(row['HomeTeamID'])
        for _, row in match_meta[['AwayTeam', 'AwayTeamID']].dropna().drop_duplicates().iterrows():
            team_name_to_id[normalize_team_name(row['AwayTeam'])] = to_int_id(row['AwayTeamID'])

        if 'TeamName' in lineups.columns:
            lineups['TeamID'] = lineups['TeamName'].apply(lambda n: team_name_to_id.get(normalize_team_name(n)))
        else:
            lineups['TeamID'] = float('nan')

        infer_team = player_stats[['MatchID', 'PlayerID', 'TeamID']].drop_duplicates(subset=['MatchID', 'PlayerID', 'TeamID'])
        lineups = lineups.merge(
            infer_team.rename(columns={'TeamID': 'TeamID_FromStats'}),
            on=['MatchID', 'PlayerID'],
            how='left'
        )
        lineups['TeamID'] = pd.to_numeric(lineups['TeamID'], errors='coerce')
        lineups['TeamID'] = lineups['TeamID'].fillna(lineups['TeamID_FromStats'])

        lineups = lineups.dropna(subset=['MatchID', 'PlayerID', 'TeamID']).copy()
        lineups['MatchID'] = lineups['MatchID'].astype(int)
        lineups['PlayerID'] = lineups['PlayerID'].astype(int)
        lineups['TeamID'] = lineups['TeamID'].astype(int)

        lineups_match = lineups[['MatchID', 'TeamID', 'PlayerID', 'StartXI', 'PositionGroup']].drop_duplicates(
            subset=['MatchID', 'TeamID', 'PlayerID'],
            keep='last'
        )

    player_stats = player_stats.merge(
        lineups_match,
        on=['MatchID', 'TeamID', 'PlayerID'],
        how='left'
    )

    if not lineups_match.empty:
        starter_pos_map = lineups_match[lineups_match['StartXI']].groupby(['TeamID', 'PlayerID'])['PositionGroup'].agg(
            lambda s: s.mode().iloc[0] if not s.mode().empty else 'MID'
        )
        player_stats = player_stats.set_index(['TeamID', 'PlayerID'])
        player_stats['PositionGroup'] = player_stats['PositionGroup'].fillna(starter_pos_map)
        player_stats = player_stats.reset_index()

    player_stats['PositionGroup'] = player_stats['PositionGroup'].fillna('MID').apply(normalize_position)

    minutes_factor = pd.to_numeric(player_stats['MinutesPlayed'], errors='coerce').clip(lower=0, upper=90).fillna(0.0) / 90.0
    goals = pd.to_numeric(player_stats['TotalGoals'], errors='coerce').fillna(0.0)
    assists = pd.to_numeric(player_stats['Assists'], errors='coerce').fillna(0.0)
    shots_on_target = pd.to_numeric(player_stats['ShotsOnTarget'], errors='coerce').fillna(0.0)
    total_shots = pd.to_numeric(player_stats['TotalShots'], errors='coerce').fillna(0.0)
    tackles = pd.to_numeric(player_stats['Tackles'], errors='coerce').fillna(0.0)
    interceptions = pd.to_numeric(player_stats['Interceptions'], errors='coerce').fillna(0.0)
    duels_won = pd.to_numeric(player_stats['DuelsWon'], errors='coerce').fillna(0.0)
    yellow = pd.to_numeric(player_stats['YellowCards'], errors='coerce').fillna(0.0)
    red = pd.to_numeric(player_stats['RedCards'], errors='coerce').fillna(0.0)
    rating = pd.to_numeric(player_stats['Rating'], errors='coerce')
    rating_norm = ((rating - 6.0) / 2.0).clip(lower=-1.0, upper=2.0).fillna(0.0)

    raw_score = (
        0.35 * goals
        + 0.25 * assists
        + 0.08 * shots_on_target
        + 0.04 * total_shots
        + 0.06 * tackles
        + 0.06 * interceptions
        + 0.05 * duels_won
        + 0.11 * rating_norm
        - 0.08 * yellow
        - 0.25 * red
    )
    player_stats['PlayerMatchScore'] = minutes_factor * raw_score

    player_stats = player_stats.sort_values(['PlayerID', 'MatchDate', 'MatchID']).copy()
    player_stats['PlayerRollingScore'] = (
        player_stats.groupby('PlayerID')['PlayerMatchScore']
        .transform(lambda s: s.shift(1).rolling(PLAYER_ROLLING_WINDOW, min_periods=1).mean())
    )
    player_stats['PlayerPriorAppearances'] = player_stats.groupby('PlayerID').cumcount()

    qualified = player_stats[
        (player_stats['PlayerPriorAppearances'] >= PLAYER_MIN_APPEARANCES)
        & player_stats['PlayerRollingScore'].notna()
    ].copy()
    if qualified.empty:
        qualified = player_stats[player_stats['PlayerRollingScore'].notna()].copy()

    global_fallback = float(qualified['PlayerRollingScore'].median()) if not qualified.empty else 0.0
    team_medians = qualified.groupby('TeamID')['PlayerRollingScore'].median().to_dict() if not qualified.empty else {}
    pos_medians = qualified.groupby('PositionGroup')['PlayerRollingScore'].median().to_dict() if not qualified.empty else {}
    team_pos_medians = qualified.groupby(['TeamID', 'PositionGroup'])['PlayerRollingScore'].median().to_dict() if not qualified.empty else {}

    def fallback_score(team_id, position_group):
        pos = normalize_position(position_group)
        team_key = to_int_id(team_id)
        if team_key is not None and (team_key, pos) in team_pos_medians and pd.notna(team_pos_medians[(team_key, pos)]):
            return float(team_pos_medians[(team_key, pos)])
        if team_key is not None and team_key in team_medians and pd.notna(team_medians[team_key]):
            return float(team_medians[team_key])
        if pos in pos_medians and pd.notna(pos_medians[pos]):
            return float(pos_medians[pos])
        return float(global_fallback)

    position_weight = {
        pos: float(weight)
        for pos, weight in PLAYER_POSITION_IMPORTANCE.items()
    }

    start_hist = pd.DataFrame(columns=['MatchID', 'TeamID', 'PlayerID', 'PositionGroup', 'StartRate'])
    if not lineups_match.empty:
        start_hist = lineups_match.merge(
            match_meta[['MatchID', 'MatchDate']],
            on='MatchID',
            how='left'
        )
        start_hist = start_hist.dropna(subset=['MatchDate']).sort_values(['TeamID', 'PlayerID', 'MatchDate'])
        start_hist['StarterNumeric'] = start_hist['StartXI'].astype(float)

    start_rate_map = {}
    if not start_hist.empty:
        start_rate_map = start_hist.groupby(['TeamID', 'PlayerID'])['StarterNumeric'].mean().to_dict()

    start_tables = {}
    if not start_hist.empty:
        for (team_id, player_id), grp in start_hist.groupby(['TeamID', 'PlayerID']):
            start_tables[(int(team_id), int(player_id))] = grp[['MatchDate', 'StarterNumeric']].sort_values('MatchDate')

    def start_rate_at(team_id, player_id, match_date):
        table = start_tables.get((team_id, player_id))
        if table is None or table.empty:
            return PLAYER_STARTPROB_FALLBACK
        if pd.isna(match_date):
            return float(table['StarterNumeric'].mean())
        prior = table[table['MatchDate'] < match_date]
        if prior.empty:
            return PLAYER_STARTPROB_FALLBACK
        return float(prior['StarterNumeric'].mean())

    stats_players = player_stats[['TeamID', 'PlayerID', 'PositionGroup']].drop_duplicates(subset=['TeamID', 'PlayerID'])
    roster_rows = []
    for _, r in stats_players.iterrows():
        team_id = to_int_id(r['TeamID'])
        player_id = to_int_id(r['PlayerID'])
        if team_id is None or player_id is None:
            continue
        roster_rows.append({
            'TeamID': team_id,
            'PlayerID': player_id,
            'PositionGroup': normalize_position(r['PositionGroup']),
            'StartRate': float(start_rate_map.get((team_id, player_id), PLAYER_STARTPROB_FALLBACK))
        })

    roster_df = pd.DataFrame(roster_rows)
    roster_by_team = {}
    if not roster_df.empty:
        for team_id, grp in roster_df.groupby('TeamID'):
            roster_by_team[int(team_id)] = grp.to_dict('records')

    profile_tables = {}
    for (team_id, player_id), grp in player_stats.groupby(['TeamID', 'PlayerID']):
        profile_tables[(int(team_id), int(player_id))] = grp[['MatchDate', 'PlayerRollingScore', 'PlayerPriorAppearances', 'PositionGroup']].sort_values('MatchDate')

    def latest_profile(team_id, player_id, match_date):
        table = profile_tables.get((team_id, player_id))
        if table is None or pd.isna(match_date):
            return float('nan'), 0, 'MID'
        prior = table[table['MatchDate'] < match_date]
        if prior.empty:
            last_pos = table['PositionGroup'].dropna().iloc[-1] if not table['PositionGroup'].dropna().empty else 'MID'
            return float('nan'), 0, normalize_position(last_pos)
        row = prior.iloc[-1]
        return (
            float(row['PlayerRollingScore']) if pd.notna(row['PlayerRollingScore']) else float('nan'),
            int(row['PlayerPriorAppearances']) if pd.notna(row['PlayerPriorAppearances']) else 0,
            normalize_position(row['PositionGroup'])
        )

    injury_map = {}
    if not injuries.empty:
        injuries = injuries.rename(columns={
            'Team ID': 'TeamID',
            'Player ID': 'PlayerID',
            'Injury Type': 'InjuryType'
        })
        for col in ['MatchID', 'TeamID', 'PlayerID']:
            if col in injuries.columns:
                injuries[col] = pd.to_numeric(injuries[col], errors='coerce')
        injuries = injuries.dropna(subset=['MatchID', 'TeamID', 'PlayerID']).copy()
        for _, row in injuries.iterrows():
            match_id = to_int_id(row['MatchID'])
            team_id = to_int_id(row['TeamID'])
            player_id = to_int_id(row['PlayerID'])
            if match_id is None or team_id is None or player_id is None:
                continue
            injury_key = (match_id, team_id)
            injury_map.setdefault(injury_key, set()).add(player_id)

    def compute_absence_penalty(team_id, injured_players, match_date):
        if not injured_players:
            return 0.0
        total = 0.0
        counted = 0
        for injured_player_id in injured_players:
            score, prior_apps, pos = latest_profile(team_id, injured_player_id, match_date)
            if prior_apps < PLAYER_MIN_APPEARANCES or pd.isna(score):
                continue
            replacement = fallback_score(team_id, pos)
            gap = max(0.0, score - replacement)
            start_prob = max(
                0.1,
                min(1.0, float(start_rate_at(team_id, injured_player_id, match_date)))
            )
            total += gap * float(position_weight.get(pos, 1.0)) * start_prob
            counted += 1
        if counted == 0:
            return 0.0
        return total / float(counted)

    match_date_lookup = match_meta.set_index('MatchID')['MatchDate'].to_dict()

    played_match_ids = set(match_meta.loc[match_meta['Played'] == True, 'MatchID'].tolist())
    team_feature_rows = []

    if not lineups_match.empty:
        starter_rows = lineups_match[
            (lineups_match['StartXI'])
            & (lineups_match['MatchID'].isin(played_match_ids))
        ].copy()
        starter_rows = starter_rows.merge(
            player_stats[['MatchID', 'TeamID', 'PlayerID', 'PlayerRollingScore', 'PlayerPriorAppearances', 'PositionGroup']],
            on=['MatchID', 'TeamID', 'PlayerID'],
            how='left',
            suffixes=('', '_Stats')
        )
        starter_rows['PosFinal'] = starter_rows['PositionGroup'].combine_first(starter_rows.get('PositionGroup_Stats', pd.Series(index=starter_rows.index, dtype='object')))
        starter_rows['PosFinal'] = starter_rows['PosFinal'].fillna('MID').apply(normalize_position)
        starter_rows['PosWeight'] = starter_rows['PosFinal'].map(position_weight).fillna(1.0)

        valid_hist = (
            pd.to_numeric(starter_rows['PlayerPriorAppearances'], errors='coerce').fillna(0) >= PLAYER_MIN_APPEARANCES
        ) & pd.to_numeric(starter_rows['PlayerRollingScore'], errors='coerce').notna()
        starter_rows['EffectiveScore'] = pd.to_numeric(starter_rows['PlayerRollingScore'], errors='coerce')

        missing_mask = ~valid_hist
        if missing_mask.any():
            starter_rows.loc[missing_mask, 'EffectiveScore'] = starter_rows.loc[missing_mask].apply(
                lambda r: fallback_score(r['TeamID'], r['PosFinal']),
                axis=1
            )

        starter_rows['WeightedScore'] = starter_rows['EffectiveScore'] * starter_rows['PosWeight']
        agg = starter_rows.groupby(['MatchID', 'TeamID'], as_index=False).agg(
            WeightedScoreSum=('WeightedScore', 'sum'),
            WeightSum=('PosWeight', 'sum')
        )
        agg['PlayerTeamScore'] = agg['WeightedScoreSum'] / agg['WeightSum'].replace(0, float('nan'))
        agg['PlayerTeamScore'] = agg['PlayerTeamScore'].fillna(global_fallback)

        for _, r in agg.iterrows():
            match_id = int(r['MatchID'])
            team_id = int(r['TeamID'])
            match_date = match_date_lookup.get(match_id, pd.NaT)
            injured = injury_map.get((match_id, team_id), set())
            team_feature_rows.append({
                'MatchID': match_id,
                'TeamID': team_id,
                'PlayerTeamScore': float(r['PlayerTeamScore']),
                'AbsencePenalty': float(compute_absence_penalty(team_id, injured, match_date))
            })

    future_matches = match_meta[match_meta['Played'] != True].copy()
    for _, match_row in future_matches.iterrows():
        match_id = to_int_id(match_row['MatchID'])
        match_date = match_row['MatchDate']
        for team_col in ['HomeTeamID', 'AwayTeamID']:
            team_id = to_int_id(match_row[team_col])
            if match_id is None or team_id is None:
                continue

            roster = roster_by_team.get(team_id, [])
            injured_players = injury_map.get((match_id, team_id), set())

            weighted_sum = 0.0
            weight_total = 0.0
            for player in roster:
                player_id = to_int_id(player.get('PlayerID'))
                if player_id is None or player_id in injured_players:
                    continue
                start_prob = max(0.0, min(1.0, float(player.get('StartRate', PLAYER_STARTPROB_FALLBACK))))
                if start_prob <= 0.0:
                    continue

                score, prior_apps, pos = latest_profile(team_id, player_id, match_date)
                if prior_apps < PLAYER_MIN_APPEARANCES or pd.isna(score):
                    score = fallback_score(team_id, pos)
                pos_weight_value = float(position_weight.get(pos, 1.0))
                player_weight = pos_weight_value * start_prob
                weighted_sum += score * player_weight
                weight_total += player_weight

            if weight_total > 0:
                team_score = weighted_sum / weight_total
            else:
                team_score = fallback_score(team_id, 'MID')

            team_feature_rows.append({
                'MatchID': match_id,
                'TeamID': team_id,
                'PlayerTeamScore': float(team_score),
                'AbsencePenalty': float(compute_absence_penalty(team_id, injured_players, match_date))
            })

    team_feature_lookup = {
        (int(r['MatchID']), int(r['TeamID'])): (float(r['PlayerTeamScore']), float(r['AbsencePenalty']))
        for r in team_feature_rows
        if r.get('MatchID') is not None and r.get('TeamID') is not None
    }

    home_scores = []
    away_scores = []
    home_absence = []
    away_absence = []
    for _, row in match_meta.iterrows():
        match_id = to_int_id(row['MatchID'])
        home_team_id = to_int_id(row['HomeTeamID'])
        away_team_id = to_int_id(row['AwayTeamID'])

        if match_id is not None and home_team_id is not None and (match_id, home_team_id) in team_feature_lookup:
            h_score, h_penalty = team_feature_lookup[(match_id, home_team_id)]
        else:
            h_score = fallback_score(home_team_id, 'MID')
            h_penalty = 0.0

        if match_id is not None and away_team_id is not None and (match_id, away_team_id) in team_feature_lookup:
            a_score, a_penalty = team_feature_lookup[(match_id, away_team_id)]
        else:
            a_score = fallback_score(away_team_id, 'MID')
            a_penalty = 0.0

        home_scores.append(float(h_score))
        away_scores.append(float(a_score))
        home_absence.append(float(h_penalty))
        away_absence.append(float(a_penalty))

    out = match_meta[['MatchID']].copy()
    out['Home_PlayerBaseScore'] = home_scores
    out['Away_PlayerBaseScore'] = away_scores
    out['Home_PlayerAbsencePenalty'] = home_absence
    out['Away_PlayerAbsencePenalty'] = away_absence
    out['Player_BaseDiff'] = out['Home_PlayerBaseScore'] - out['Away_PlayerBaseScore']
    out['Player_AbsencePenaltyDiff'] = out['Away_PlayerAbsencePenalty'] - out['Home_PlayerAbsencePenalty']
    return out[result_cols]


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

player_base_feats = build_player_base_features(df)
df = df.merge(player_base_feats, on='MatchID', how='left')
for player_col in [
    'Home_PlayerBaseScore', 'Away_PlayerBaseScore',
    'Home_PlayerAbsencePenalty', 'Away_PlayerAbsencePenalty',
    'Player_BaseDiff', 'Player_AbsencePenaltyDiff'
]:
    if player_col not in df.columns:
        df[player_col] = 0.0
    df[player_col] = pd.to_numeric(df[player_col], errors='coerce').fillna(0.0)

# 4. Feature groups
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

# 7. Features (Signal-Architektur: General + H2H + Player + Weather-Context)
team_form_features = [
    'Home_BaseAvgGoalsFor', 'Home_BaseAvgGoalsAgainst', 'Home_BaseAvgPoints',
    'Away_BaseAvgGoalsFor', 'Away_BaseAvgGoalsAgainst', 'Away_BaseAvgPoints',
    'Home_AvgGoalsFor_L5', 'Home_AvgGoalsAgainst_L5', 'Home_AvgPoints_L5',
    'Away_AvgGoalsFor_L5', 'Away_AvgGoalsAgainst_L5', 'Away_AvgPoints_L5'
]

h2h_base_features = H2H_COMBINED_FEATURES + H2H_VENUE_FEATURES
h2h_count_features = ['H2H_Combined_MatchCount', 'H2H_Venue_MatchCount']
player_base_input_features = ['Player_BaseDiff', 'Player_AbsencePenaltyDiff']
outcome_prematch_features = team_form_features + h2h_base_features + h2h_count_features + player_base_input_features

match_stats_features = [
    'HomeXG', 'AwayXG',
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
weather_features = [
    'Weather_Temperature_C',
    'Weather_Pressure',
    'Weather_Humidity',
    'Weather_WindSpeed',
    'Weather_WindDirection',
    'Weather_Rain',
    'Weather_Snow'
]

team_context_features = [
    'HomeTeamID',
    'AwayTeamID'
]

match_stats_model_features = outcome_prematch_features + weather_features
outcome_signal_input_features_base = outcome_prematch_features + weather_features
outcome_signal_input_features_with_match_stats = outcome_signal_input_features_base + match_stats_features
outcome_features_base = outcome_signal_input_features_base
outcome_features_with_match_stats = outcome_signal_input_features_with_match_stats
count_match_stats_features = [
    'HomeShots', 'AwayShots',
    'HomeShotsOnTarget', 'AwayShotsOnTarget',
    'HomePasses', 'AwayPasses',
    'HomeFouls', 'AwayFouls',
    'HomeYellowCard', 'AwayYellowCard',
    'HomeRedCard', 'AwayRedCard',
    'HomeOffsides', 'AwayOffsides',
    'HomeCorners', 'AwayCorners'
]

GENERAL_SIGNAL_GROUP_SPECS = {
    'GoalCreation': [
        {'weight_name': 'General_GoalCreation_XG', 'home': 'HomeXG', 'away': 'AwayXG', 'invert': False},
        {'weight_name': 'General_GoalCreation_ShotsOnTarget', 'home': 'HomeShotsOnTarget', 'away': 'AwayShotsOnTarget', 'invert': False},
        {'weight_name': 'General_GoalCreation_Shots', 'home': 'HomeShots', 'away': 'AwayShots', 'invert': False}
    ],
    'GameControl': [
        {'weight_name': 'General_GameControl_Possession', 'home': 'HomePossession', 'away': 'AwayPossession', 'invert': False},
        {'weight_name': 'General_GameControl_Passes', 'home': 'HomePasses', 'away': 'AwayPasses', 'invert': False},
        {'weight_name': 'General_GameControl_PassAccuracy', 'home': 'HomePassAccuracy', 'away': 'AwayPassAccuracy', 'invert': False}
    ],
    'DisciplineSetPiece': [
        {'weight_name': 'General_DisciplineSetPiece_Fouls', 'home': 'HomeFouls', 'away': 'AwayFouls', 'invert': True},
        {'weight_name': 'General_DisciplineSetPiece_YellowCard', 'home': 'HomeYellowCard', 'away': 'AwayYellowCard', 'invert': True},
        {'weight_name': 'General_DisciplineSetPiece_RedCard', 'home': 'HomeRedCard', 'away': 'AwayRedCard', 'invert': True},
        {'weight_name': 'General_DisciplineSetPiece_Corners', 'home': 'HomeCorners', 'away': 'AwayCorners', 'invert': False},
        {'weight_name': 'General_DisciplineSetPiece_Offsides', 'home': 'HomeOffsides', 'away': 'AwayOffsides', 'invert': True}
    ]
}

H2H_SIGNAL_SPECS = [
    {'weight_name': f'H2H_{feat}', 'column': feat}
    for feat in h2h_base_features
]
WEATHER_CONTEXT_SPECS = [
    {'weight_name': f'WeatherContext_{feat}', 'column': feat}
    for feat in weather_features
]
PLAYER_BASE_SIGNAL_SPECS = [
    {'weight_name': 'Player_FormDiff', 'column': 'Player_BaseDiff'},
    {'weight_name': 'Player_AbsencePenaltyDiff', 'column': 'Player_AbsencePenaltyDiff'}
]
BASE_MULTIPLIER_PARAMETER_NAMES = [
    'BaseMultiplier_General',
    'BaseMultiplier_H2H',
    'BaseMultiplier_Player'
]
BASE_SIGNAL_FEATURES = [
    'General_BaseSignal',
    'H2H_BaseSignal',
    'Player_BaseSignal'
]
required_feature_columns = list(dict.fromkeys(
    match_stats_model_features + match_stats_features + ['HomeGoals', 'AwayGoals']
))
missing = [f for f in required_feature_columns if f not in df.columns]
if missing:
    raise ValueError(f"Missing required columns in merged dataset: {missing}")
coerce_numeric_columns(df, required_feature_columns)

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


def read_optional_csv(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def first_non_null_value(values, default_value=float('nan')):
    for value in values:
        if pd.notna(value):
            return value
    return default_value


def outcome_from_goals(home_goals, away_goals):
    if pd.isna(home_goals) or pd.isna(away_goals):
        return float('nan')
    if home_goals > away_goals:
        return 'H'
    if home_goals < away_goals:
        return 'A'
    return 'D'


def prepare_run_summary(summary_df):
    prepared = summary_df.copy()
    if prepared.empty:
        return prepared

    numeric_cols = [
        'AvgNLL', 'Accuracy', 'Pred_AvgNLL', 'Pred_Accuracy',
        'ResolvedAvgNLL', 'ResolvedAccuracy',
        'MeanTopProb', 'MeanProbGap', 'MeanEntropy',
        'MatchedReferenceCount', 'NumMatchesScored', 'H2H_K', 'BatchID'
    ]
    for col in numeric_cols:
        if col in prepared.columns:
            prepared[col] = pd.to_numeric(prepared[col], errors='coerce')

    if 'MatchedReferenceCount' in prepared.columns:
        prepared['ScoredAgainstReferences'] = prepared['MatchedReferenceCount'].fillna(0) > 0
    else:
        prepared['ScoredAgainstReferences'] = False

    pred_nll_col = prepared['Pred_AvgNLL'] if 'Pred_AvgNLL' in prepared.columns else pd.Series(float('nan'), index=prepared.index)
    pred_acc_col = prepared['Pred_Accuracy'] if 'Pred_Accuracy' in prepared.columns else pd.Series(float('nan'), index=prepared.index)
    prepared['Ranking_AvgNLL'] = prepared['AvgNLL'].combine_first(pred_nll_col)
    prepared['Ranking_Accuracy'] = prepared['Accuracy'].combine_first(pred_acc_col)
    prepared = prepared.sort_values(
        ['ScoredAgainstReferences', 'Ranking_AvgNLL', 'Ranking_Accuracy'],
        ascending=[False, True, False]
    )
    return prepared


def append_to_run_history(history_path, summary_df):
    existing_mode_history = read_optional_csv(history_path)
    if not existing_mode_history.empty and 'MatchStatsMode' not in existing_mode_history.columns:
        existing_mode_history['MatchStatsMode'] = 'actual'
    if not existing_mode_history.empty and 'PredictionSource' not in existing_mode_history.columns:
        existing_mode_history['PredictionSource'] = 'simulation'
    if not existing_mode_history.empty and 'SourcePredictionMode' not in existing_mode_history.columns:
        if 'PredictionMode' in existing_mode_history.columns:
            existing_mode_history['SourcePredictionMode'] = existing_mode_history['PredictionMode']
        else:
            existing_mode_history['SourcePredictionMode'] = 'reference'
    if not existing_mode_history.empty and 'FeatureSchemaVersion' not in existing_mode_history.columns:
        existing_mode_history['FeatureSchemaVersion'] = 'legacy_v1'

    if existing_mode_history.empty:
        history_updated = summary_df.copy()
    else:
        history_updated = pd.DataFrame.from_records(
            existing_mode_history.to_dict('records') + summary_df.to_dict('records')
        )

    dedupe_cols = [col for col in ['PredictionSource', 'MatchStatsMode', 'FeatureSchemaVersion', 'BatchID', 'RunID'] if col in history_updated.columns]
    if dedupe_cols:
        history_updated = history_updated.drop_duplicates(subset=dedupe_cols, keep='last')

    history_updated.to_csv(history_path, index=False)
    return history_updated




def append_future_vs_reference_metrics(metrics_path, summary_df):
    """Append a per-run evaluation snapshot when saved future predictions are scored
    against reference results (AvgNLL/Accuracy). Creates the CSV if missing.

    The CSV is stored in the future output folder so that future runs keep their
    evaluation history close to the generated predictions.
    """
    if summary_df is None or summary_df.empty:
        return read_optional_csv(metrics_path)

    evaluation_ts = datetime.now().isoformat(timespec='seconds')
    snapshot = summary_df.copy()
    snapshot['EvaluationTimestamp'] = evaluation_ts
    snapshot['EvaluationType'] = 'future_vs_reference'

    if 'AvgNLL' in snapshot.columns and 'Pred_AvgNLL' in snapshot.columns:
        snapshot['Delta_AvgNLL_vs_Pred'] = snapshot['AvgNLL'] - snapshot['Pred_AvgNLL']
    if 'Accuracy' in snapshot.columns and 'Pred_Accuracy' in snapshot.columns:
        snapshot['Delta_Accuracy_vs_Pred'] = snapshot['Accuracy'] - snapshot['Pred_Accuracy']
    if 'ResolvedAvgNLL' in snapshot.columns and 'AvgNLL' in snapshot.columns:
        snapshot['Delta_ResolvedAvgNLL_vs_Actual'] = snapshot['ResolvedAvgNLL'] - snapshot['AvgNLL']
    if 'ResolvedAccuracy' in snapshot.columns and 'Accuracy' in snapshot.columns:
        snapshot['Delta_ResolvedAccuracy_vs_Actual'] = snapshot['ResolvedAccuracy'] - snapshot['Accuracy']

    if 'Ranking_AvgNLL' in snapshot.columns:
        snapshot['EvalRank_AvgNLL'] = pd.to_numeric(snapshot['Ranking_AvgNLL'], errors='coerce').rank(method='min', ascending=True)
    if 'Ranking_Accuracy' in snapshot.columns:
        snapshot['EvalRank_Accuracy'] = pd.to_numeric(snapshot['Ranking_Accuracy'], errors='coerce').rank(method='min', ascending=False)
    if {'EvalRank_AvgNLL', 'EvalRank_Accuracy'}.issubset(snapshot.columns):
        a = snapshot['EvalRank_AvgNLL'].fillna(snapshot['EvalRank_AvgNLL'].max(skipna=True) + 1)
        b = snapshot['EvalRank_Accuracy'].fillna(snapshot['EvalRank_Accuracy'].max(skipna=True) + 1)
        snapshot['EvalRank_Combined'] = a + b
        best = snapshot['EvalRank_Combined'].min(skipna=True)
        snapshot['EvalIsBestCombined'] = snapshot['EvalRank_Combined'] == best

    existing = read_optional_csv(metrics_path)
    if existing.empty:
        updated = snapshot
    else:
        updated = pd.concat([existing, snapshot], ignore_index=True, sort=False)

    dedupe_cols = [c for c in [
        'EvaluationTimestamp', 'EvaluationType',
        'PredictionSource', 'SourcePredictionMode', 'MatchStatsMode',
        'FeatureSchemaVersion', 'BatchID', 'RunID'
    ] if c in updated.columns]
    if dedupe_cols:
        updated = updated.drop_duplicates(subset=dedupe_cols, keep='last')

    sort_cols = [c for c in ['EvaluationTimestamp', 'EvalIsBestCombined', 'Ranking_AvgNLL', 'Ranking_Accuracy'] if c in updated.columns]
    if sort_cols:
        ascending = [False] * len(sort_cols)
        if 'EvalIsBestCombined' in sort_cols:
            ascending[sort_cols.index('EvalIsBestCombined')] = False
        if 'Ranking_AvgNLL' in sort_cols:
            ascending[sort_cols.index('Ranking_AvgNLL')] = True
        if 'Ranking_Accuracy' in sort_cols:
            ascending[sort_cols.index('Ranking_Accuracy')] = False
        updated = updated.sort_values(sort_cols, ascending=ascending)

    updated.to_csv(metrics_path, index=False)
    return updated
def try_backfill_reference_from_future(ref_results):
    if ref_results is None or ref_results.empty:
        return pd.DataFrame(), pd.DataFrame()

    future_runs = read_optional_csv(FUTURE_PREDICTION_SOURCE_PATH)
    if future_runs.empty or 'MatchID' not in future_runs.columns or 'RunID' not in future_runs.columns:
        return pd.DataFrame(), pd.DataFrame()

    future_runs = future_runs.copy()
    future_runs['MatchID'] = pd.to_numeric(future_runs['MatchID'], errors='coerce')
    future_runs = future_runs.dropna(subset=['MatchID', 'RunID']).copy()
    if future_runs.empty:
        return pd.DataFrame(), pd.DataFrame()

    future_runs['MatchID'] = future_runs['MatchID'].astype(ref_results.index.dtype, copy=False)
    matched_rows = future_runs[future_runs['MatchID'].isin(ref_results.index)].copy()
    if matched_rows.empty:
        return pd.DataFrame(), pd.DataFrame()

    if 'MatchStatsMode' not in matched_rows.columns:
        matched_rows['MatchStatsMode'] = 'predicted'
    if 'PredictionMode' not in matched_rows.columns:
        matched_rows['PredictionMode'] = 'future'

    future_summary = read_optional_csv(FUTURE_RUN_SUMMARY_SOURCE_PATH)
    summary_merge_cols = ['RunID']
    for col in ['BatchID', 'Pred_AvgNLL', 'Pred_Accuracy', 'MeanTopProb', 'MeanProbGap', 'MeanEntropy', 'H2H_K']:
        if col in future_summary.columns and col not in matched_rows.columns:
            summary_merge_cols.append(col)
    if len(summary_merge_cols) > 1:
        summary_meta = future_summary[summary_merge_cols].drop_duplicates(subset=['RunID'], keep='last')
        matched_rows = matched_rows.merge(summary_meta, on='RunID', how='left')

    ref_actual = ref_results[['HomeGoals', 'AwayGoals', 'Result']].rename(columns={
        'HomeGoals': 'ActualHomeGoals',
        'AwayGoals': 'ActualAwayGoals',
        'Result': 'ActualResult'
    })

    scored_runs = []
    summary_rows = []

    for run_id, run_df in matched_rows.groupby('RunID', sort=True):
        scored = run_df.copy()
        source_prediction_mode = first_non_null_value(scored['PredictionMode'].tolist(), 'future')
        match_stats_mode = first_non_null_value(scored['MatchStatsMode'].tolist(), 'predicted')
        feature_schema_version = first_non_null_value(
            scored['FeatureSchemaVersion'].tolist() if 'FeatureSchemaVersion' in scored.columns else [],
            FEATURE_SCHEMA_VERSION
        )
        batch_id = first_non_null_value(scored['BatchID'].tolist() if 'BatchID' in scored.columns else [], 1)
        h2h_k = first_non_null_value(scored['H2H_K'].tolist() if 'H2H_K' in scored.columns else [], H2H_K_DEFAULT)

        scored = scored.merge(ref_actual, left_on='MatchID', right_index=True, how='left')
        scored['ActualResult'] = scored['ActualResult'].where(
            scored['ActualResult'].isin(['H', 'D', 'A']),
            scored.apply(lambda row: outcome_from_goals(row['ActualHomeGoals'], row['ActualAwayGoals']), axis=1)
        )

        def prob_for_actual(row):
            if row['ActualResult'] == 'H':
                return row['WinProb']
            if row['ActualResult'] == 'D':
                return row['DrawProb']
            if row['ActualResult'] == 'A':
                return row['LoseProb']
            return float('nan')

        scored['ProbActual'] = scored.apply(prob_for_actual, axis=1)
        scored['ProbActual'] = pd.to_numeric(scored['ProbActual'], errors='coerce').clip(lower=1e-12)
        scored['MatchNLL'] = scored['ProbActual'].apply(lambda p: -math.log(p) if pd.notna(p) else float('nan'))
        scored['IsCorrect'] = (
            scored['PredictedResult'].notna()
            & scored['ActualResult'].notna()
            & (scored['PredictedResult'] == scored['ActualResult'])
        )

        actual_rows = scored['ActualResult'].dropna()
        matched_reference_count = int(actual_rows.count())
        run_score = float(scored.loc[actual_rows.index, 'MatchNLL'].mean()) if matched_reference_count > 0 else float('nan')
        run_accuracy = float(scored.loc[actual_rows.index, 'IsCorrect'].mean()) if matched_reference_count > 0 else float('nan')
        run_count = matched_reference_count

        pred_run_nll = first_non_null_value(
            (scored['RunPredictedAvgNLL'].tolist() if 'RunPredictedAvgNLL' in scored.columns else [])
            + (scored['Pred_AvgNLL'].tolist() if 'Pred_AvgNLL' in scored.columns else []),
            float('nan')
        )
        pred_run_acc = first_non_null_value(
            (scored['RunPredictedAccuracy'].tolist() if 'RunPredictedAccuracy' in scored.columns else [])
            + (scored['Pred_Accuracy'].tolist() if 'Pred_Accuracy' in scored.columns else []),
            float('nan')
        )

        prob_frame = scored[['WinProb', 'DrawProb', 'LoseProb']].apply(pd.to_numeric, errors='coerce')
        top_prob = prob_frame.max(axis=1)
        second_prob = prob_frame.apply(
            lambda row: row.nlargest(2).iloc[-1] if row.notna().sum() >= 2 else float('nan'),
            axis=1
        )
        prob_gap = top_prob - second_prob
        prob_entropy = prob_frame.apply(
            lambda row: -sum(p * math.log(max(p, 1e-12)) for p in row.dropna()) if row.notna().any() else float('nan'),
            axis=1
        )

        mean_top_prob = first_non_null_value(
            scored['MeanTopProb'].tolist() if 'MeanTopProb' in scored.columns else [],
            float(top_prob.mean()) if not top_prob.dropna().empty else float('nan')
        )
        mean_prob_gap = first_non_null_value(
            scored['MeanProbGap'].tolist() if 'MeanProbGap' in scored.columns else [],
            float(prob_gap.mean()) if not prob_gap.dropna().empty else float('nan')
        )
        mean_entropy = first_non_null_value(
            scored['MeanEntropy'].tolist() if 'MeanEntropy' in scored.columns else [],
            float(prob_entropy.mean()) if not prob_entropy.dropna().empty else float('nan')
        )

        resolved_run_nll = run_score if pd.notna(run_score) else pred_run_nll
        resolved_run_accuracy = run_accuracy if pd.notna(run_accuracy) else pred_run_acc
        metric_source = 'reference' if matched_reference_count > 0 else ('surrogate' if pd.notna(pred_run_nll) or pd.notna(pred_run_acc) else 'none')

        scored['SourcePredictionMode'] = source_prediction_mode
        scored['PredictionMode'] = 'reference'
        scored['PredictionSource'] = 'future_backfill'
        scored['MatchStatsMode'] = match_stats_mode
        scored['FeatureSchemaVersion'] = feature_schema_version
        scored['RunResolvedAvgNLL'] = resolved_run_nll
        scored['RunResolvedAccuracy'] = resolved_run_accuracy
        scored['RunMetricSource'] = metric_source
        scored['RunActualAvgNLL'] = run_score
        scored['RunActualAccuracy'] = run_accuracy
        scored['RunPredictedAvgNLL'] = pred_run_nll
        scored['RunPredictedAccuracy'] = pred_run_acc

        metric_row = {
            'RunID': run_id,
            'BatchID': batch_id,
            'PredictionMode': 'reference',
            'PredictionSource': 'future_backfill',
            'SourcePredictionMode': source_prediction_mode,
            'MatchStatsMode': match_stats_mode,
            'FeatureSchemaVersion': feature_schema_version,
            'H2H_K': h2h_k,
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
        for col in [c for c in scored.columns if c.startswith('Weight_')]:
            metric_row[col] = first_non_null_value(scored[col].tolist(), float('nan'))

        summary_rows.append(metric_row)
        scored_runs.append(scored)

    if not scored_runs:
        return pd.DataFrame(), pd.DataFrame()

    all_pred_df = pd.concat(scored_runs, ignore_index=True)
    summary_df = prepare_run_summary(pd.DataFrame(summary_rows))
    return all_pred_df, summary_df

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


def make_match_stats_regressor():
    if MATCH_STATS_MODEL != 'gbr':
        raise ValueError("MATCH_STATS_MODEL currently supports only 'gbr'.")
    return GradientBoostingRegressor(random_state=RANDOM_STATE)


def fit_match_stats_estimator(x_train, y_train):
    imputer = SimpleImputer(strategy='median')
    x_train_imp = imputer.fit_transform(x_train)
    model = make_match_stats_regressor()
    model.fit(x_train_imp, y_train)
    return imputer, model


def postprocess_match_stats(pred_df):
    processed = pred_df.copy()
    if processed.empty:
        return processed

    for col in ['HomePossession', 'AwayPossession', 'HomePassAccuracy', 'AwayPassAccuracy']:
        if col in processed.columns:
            processed[col] = pd.to_numeric(processed[col], errors='coerce').clip(lower=0.0, upper=100.0)

    if {'HomePossession', 'AwayPossession'}.issubset(processed.columns):
        home_pos = pd.to_numeric(processed['HomePossession'], errors='coerce')
        away_pos = pd.to_numeric(processed['AwayPossession'], errors='coerce')
        total = home_pos + away_pos
        valid = home_pos.notna() & away_pos.notna() & (total > 0)
        processed.loc[valid, 'HomePossession'] = 100.0 * home_pos.loc[valid] / total.loc[valid]
        processed.loc[valid, 'AwayPossession'] = 100.0 - processed.loc[valid, 'HomePossession']
        processed.loc[~valid, 'HomePossession'] = 50.0
        processed.loc[~valid, 'AwayPossession'] = 50.0
        processed['HomePossession'] = processed['HomePossession'].round(2)
        processed['AwayPossession'] = processed['AwayPossession'].round(2)

    for col in ['HomePassAccuracy', 'AwayPassAccuracy']:
        if col in processed.columns:
            processed[col] = processed[col].round(2)

    for col in count_match_stats_features:
        if col in processed.columns:
            processed[col] = pd.to_numeric(processed[col], errors='coerce').clip(lower=0.0).round()
            processed[col] = processed[col].fillna(0.0).astype(int)

    return processed


def build_match_stats_predictions(train_df, predict_df, feature_cols, target_cols):
    train_pred = pd.DataFrame(index=train_df.index)
    predict_pred = pd.DataFrame(index=predict_df.index)
    summary_rows = []

    for target in target_cols:
        y_full = pd.to_numeric(train_df[target], errors='coerce')
        valid_mask = y_full.notna()
        observed_count = int(valid_mask.sum())
        unique_values = int(y_full.loc[valid_mask].nunique(dropna=True)) if observed_count > 0 else 0
        fallback_value = float(y_full.loc[valid_mask].median()) if observed_count > 0 else 0.0

        train_target_pred = pd.Series(float('nan'), index=train_df.index, dtype='float64')
        predict_target_pred = pd.Series(fallback_value, index=predict_df.index, dtype='float64')
        used_model = False

        if observed_count >= MATCH_STATS_MIN_ROWS and unique_values > 1:
            x_valid = train_df.loc[valid_mask, feature_cols].copy()
            y_valid = y_full.loc[valid_mask].astype(float).copy()
            n_splits = min(MATCH_STATS_CV_SPLITS, len(x_valid))
            if n_splits >= 2:
                kfold = KFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
                for fit_idx, holdout_idx in kfold.split(x_valid):
                    x_fit = x_valid.iloc[fit_idx]
                    y_fit = y_valid.iloc[fit_idx]
                    x_holdout = x_valid.iloc[holdout_idx]

                    if y_fit.nunique(dropna=True) <= 1:
                        holdout_pred = [float(y_fit.iloc[0])] * len(holdout_idx)
                    else:
                        imputer, model = fit_match_stats_estimator(x_fit, y_fit)
                        holdout_pred = model.predict(imputer.transform(x_holdout))
                    train_target_pred.loc[x_valid.index[holdout_idx]] = holdout_pred

                imputer, model = fit_match_stats_estimator(x_valid, y_valid)
                used_model = True

                remaining_mask = train_target_pred.isna()
                if remaining_mask.any():
                    train_target_pred.loc[remaining_mask] = fallback_value
                if not predict_df.empty:
                    predict_target_pred = pd.Series(
                        model.predict(imputer.transform(predict_df[feature_cols])),
                        index=predict_df.index,
                        dtype='float64'
                    )

        if not used_model:
            train_target_pred = train_target_pred.fillna(fallback_value)
            if not predict_df.empty:
                predict_target_pred = predict_target_pred.fillna(fallback_value)

        train_pred[target] = train_target_pred
        predict_pred[target] = predict_target_pred
        summary_rows.append({
            'Target': target,
            'ObservedRows': observed_count,
            'UniqueValues': unique_values,
            'FallbackValue': fallback_value,
            'UsedModel': used_model
        })

    train_pred = postprocess_match_stats(train_pred)
    predict_pred = postprocess_match_stats(predict_pred)
    summary_df = pd.DataFrame(summary_rows)
    return train_pred, predict_pred, summary_df


def apply_match_stats_mode(train_df, predict_df, raw_predict_df):
    train_enriched = train_df.copy()
    predict_enriched = predict_df.copy()
    predicted_stats_output = pd.DataFrame()
    match_stats_summary = pd.DataFrame()

    if MATCH_STATS_MODE == 'off':
        return train_enriched, predict_enriched, outcome_features_base, predicted_stats_output, match_stats_summary

    if MATCH_STATS_MODE == 'actual':
        return train_enriched, predict_enriched, outcome_features_with_match_stats, predicted_stats_output, match_stats_summary

    train_stats_pred, predict_stats_pred, match_stats_summary = build_match_stats_predictions(
        train_enriched,
        predict_enriched,
        match_stats_model_features,
        match_stats_features
    )

    for col in match_stats_features:
        train_enriched[col] = train_stats_pred[col].reindex(train_enriched.index)
        predict_enriched[col] = predict_stats_pred[col].reindex(predict_enriched.index)

    predicted_stats_output = raw_predict_df[['MatchID', 'MatchDate', 'HomeTeam', 'AwayTeam']].copy()
    predicted_stats_output['PredictionMode'] = PREDICTION_MODE
    predicted_stats_output['MatchStatsMode'] = MATCH_STATS_MODE
    predicted_stats_output['MatchStatsModel'] = MATCH_STATS_MODEL
    for col in match_stats_features:
        predicted_stats_output[col] = predict_stats_pred[col].reindex(predicted_stats_output.index)
        if col in raw_predict_df.columns:
            predicted_stats_output[f'Actual_{col}'] = raw_predict_df[col].reindex(predicted_stats_output.index)

    return (
        train_enriched,
        predict_enriched,
        outcome_features_with_match_stats,
        predicted_stats_output,
        match_stats_summary
    )


def resolve_weight_value(weight_map, key, default_value=1.0):
    raw_value = weight_map.get(key, default_value)
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return float(default_value)
    if not math.isfinite(value):
        return float(default_value)
    return value


def collect_weight_parameter_names(match_stats_mode):
    params = []
    if match_stats_mode != 'off':
        for subgroup in GENERAL_SIGNAL_GROUP_SPECS.values():
            params.extend(spec['weight_name'] for spec in subgroup)
    params.extend(spec['weight_name'] for spec in H2H_SIGNAL_SPECS)
    params.extend(spec['weight_name'] for spec in PLAYER_BASE_SIGNAL_SPECS)
    params.extend(spec['weight_name'] for spec in WEATHER_CONTEXT_SPECS)
    params.extend(BASE_MULTIPLIER_PARAMETER_NAMES)
    return params


def weighted_signal_from_specs(signal_df, specs, weight_map):
    if signal_df.empty or not specs:
        return pd.Series(0.0, index=signal_df.index, dtype='float64')

    weighted_sum = pd.Series(0.0, index=signal_df.index, dtype='float64')
    total_weight = 0.0

    for spec in specs:
        weight_name = spec['weight_name']
        w = resolve_weight_value(weight_map, weight_name, 1.0)
        if w <= 0:
            continue

        if 'column' in spec:
            col = spec['column']
            if col in signal_df.columns:
                values = pd.to_numeric(signal_df[col], errors='coerce')
            else:
                values = pd.Series(0.0, index=signal_df.index, dtype='float64')
        else:
            home_col = spec['home']
            away_col = spec['away']
            if home_col in signal_df.columns and away_col in signal_df.columns:
                home_vals = pd.to_numeric(signal_df[home_col], errors='coerce')
                away_vals = pd.to_numeric(signal_df[away_col], errors='coerce')
                if spec.get('invert', False):
                    values = away_vals - home_vals
                else:
                    values = home_vals - away_vals
            else:
                values = pd.Series(0.0, index=signal_df.index, dtype='float64')

        weighted_sum = weighted_sum + values.fillna(0.0) * w
        total_weight += w

    if total_weight <= 0:
        return pd.Series(0.0, index=signal_df.index, dtype='float64')
    return weighted_sum / total_weight


def build_outcome_design_matrix(signal_df, weight_map, match_stats_mode):
    design = pd.DataFrame(index=signal_df.index)

    if match_stats_mode == 'off':
        general_signal = pd.Series(0.0, index=signal_df.index, dtype='float64')
    else:
        subgroup_signals = {}
        for subgroup_name, specs in GENERAL_SIGNAL_GROUP_SPECS.items():
            subgroup_signals[subgroup_name] = weighted_signal_from_specs(signal_df, specs, weight_map)

        general_signal = pd.Series(0.0, index=signal_df.index, dtype='float64')
        for subgroup_name, blend_weight in GENERAL_SUBGROUP_BLEND.items():
            general_signal = general_signal + subgroup_signals.get(
                subgroup_name,
                pd.Series(0.0, index=signal_df.index, dtype='float64')
            ) * float(blend_weight)

    general_multiplier = resolve_weight_value(weight_map, 'BaseMultiplier_General', 1.0)
    h2h_multiplier = resolve_weight_value(weight_map, 'BaseMultiplier_H2H', 1.0)
    player_multiplier = resolve_weight_value(weight_map, 'BaseMultiplier_Player', 1.0)

    h2h_signal = weighted_signal_from_specs(signal_df, H2H_SIGNAL_SPECS, weight_map)
    player_signal = weighted_signal_from_specs(signal_df, PLAYER_BASE_SIGNAL_SPECS, weight_map)

    design['General_BaseSignal'] = general_signal * general_multiplier
    design['H2H_BaseSignal'] = h2h_signal * h2h_multiplier
    design['Player_BaseSignal'] = player_signal * player_multiplier

    for spec in WEATHER_CONTEXT_SPECS:
        col = spec['column']
        weight_name = spec['weight_name']
        w = resolve_weight_value(weight_map, weight_name, 1.0)
        if col in signal_df.columns:
            values = pd.to_numeric(signal_df[col], errors='coerce').fillna(0.0)
        else:
            values = pd.Series(0.0, index=signal_df.index, dtype='float64')
        design[col] = values * w

    return design


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
        ranked.loc[valid] = values.loc[valid].rank(ascending=True, pct=True)
    else:
        ranked.loc[valid] = values.loc[valid].rank(ascending=False, pct=True)
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


def drop_empty_weight_columns(df):
    if df is None or df.empty:
        return df
    cleaned = df.copy()
    weight_cols = [c for c in cleaned.columns if c.startswith('Weight_')]
    for col in weight_cols:
        if cleaned[col].notna().sum() == 0:
            cleaned = cleaned.drop(columns=[col])

    hybrid_prefixes = (
        'Weight_General_',
        'Weight_H2H_H2H_',
        'Weight_Player_',
        'Weight_WeatherContext_',
        'Weight_BaseMultiplier_'
    )
    remaining_weight_cols = [c for c in cleaned.columns if c.startswith('Weight_')]
    has_hybrid_weights = any(col.startswith(hybrid_prefixes) for col in remaining_weight_cols)
    if has_hybrid_weights:
        legacy_cols = [col for col in remaining_weight_cols if not col.startswith(hybrid_prefixes)]
        if legacy_cols:
            cleaned = cleaned.drop(columns=legacy_cols)
    return cleaned


def persist_decision_table(decision_df, output_path):
    if decision_df is None:
        decision_df = pd.DataFrame()

    if decision_df.empty:
        existing = read_optional_csv(output_path)
        if not existing.empty:
            print(f"Decision set empty for current run; keeping existing file: {output_path}")
            return existing
        decision_df.to_csv(output_path, index=False)
        return decision_df

    cleaned = drop_empty_weight_columns(decision_df)
    cleaned.to_csv(output_path, index=False)
    return cleaned



def _safe_float(value, default_value=float('nan')):
    try:
        num = float(value)
    except (TypeError, ValueError):
        return float(default_value)
    if not math.isfinite(num):
        return float(default_value)
    return num


def _mean_valid(values, default_value=1.0):
    valid = [float(v) for v in values if pd.notna(v)]
    if not valid:
        return float(default_value)
    return float(sum(valid) / len(valid))


def _legacy_weight(row, suffix, default_value=float('nan')):
    return _safe_float(row.get(f'Weight_{suffix}'), default_value)


def _history_row_key(row, key_cols):
    key = []
    for col in key_cols:
        value = row.get(col, float('nan'))
        if pd.isna(value):
            key.append('__nan__')
        else:
            key.append(str(value))
    return tuple(key)


def migrate_legacy_history_to_hybrid(history_df, target_schema_version):
    if history_df is None or history_df.empty:
        return history_df, 0

    hist = history_df.copy()
    if 'FeatureSchemaVersion' not in hist.columns:
        hist['FeatureSchemaVersion'] = 'legacy_v1'
    if 'SourcePredictionMode' not in hist.columns:
        if 'PredictionMode' in hist.columns:
            hist['SourcePredictionMode'] = hist['PredictionMode']
        else:
            hist['SourcePredictionMode'] = 'reference'

    key_cols = [c for c in ['PredictionSource', 'MatchStatsMode', 'SourcePredictionMode', 'BatchID', 'RunID'] if c in hist.columns]
    if not key_cols:
        return hist, 0

    existing_target = hist[hist['FeatureSchemaVersion'] == target_schema_version]
    existing_keys = {
        _history_row_key(row, key_cols)
        for _, row in existing_target.iterrows()
    }

    legacy_mask = hist['FeatureSchemaVersion'].isin(['legacy_v1', 'legacy'])
    legacy_rows = hist[legacy_mask].copy()
    if legacy_rows.empty:
        return hist, 0

    legacy_probe_suffixes = [
        'HomeShots', 'AwayShots',
        'HomeShotsOnTarget', 'AwayShotsOnTarget',
        'H2H_Combined_AvgGoalDiff',
        'Weather_Temperature_C'
    ]

    migrated_rows = []
    h2h_suffixes = [
        'H2H_Combined_AvgGoalDiff', 'H2H_Combined_AvgGoalsFor', 'H2H_Combined_AvgGoalsAgainst',
        'H2H_Combined_AvgPoints', 'H2H_Combined_WinRate',
        'H2H_Venue_AvgGoalDiff', 'H2H_Venue_AvgGoalsFor', 'H2H_Venue_AvgGoalsAgainst',
        'H2H_Venue_AvgPoints', 'H2H_Venue_WinRate'
    ]
    weather_suffixes = [
        'Weather_Temperature_C', 'Weather_Pressure', 'Weather_Humidity',
        'Weather_WindSpeed', 'Weather_WindDirection', 'Weather_Rain', 'Weather_Snow'
    ]

    for _, row in legacy_rows.iterrows():
        row_key = _history_row_key(row, key_cols)
        if row_key in existing_keys:
            continue

        probe_values = [_legacy_weight(row, suffix) for suffix in legacy_probe_suffixes]
        if all(pd.isna(v) for v in probe_values):
            continue

        migrated = row.copy()
        migrated['FeatureSchemaVersion'] = target_schema_version

        legacy_weight_cols = [
            c for c in migrated.index
            if c.startswith('Weight_Home_')
            or c.startswith('Weight_Away_')
            or c.startswith('Weight_Weather_')
            or c.startswith('Weight_H2H_Combined_')
            or c.startswith('Weight_H2H_Venue_')
        ]
        for legacy_col in legacy_weight_cols:
            migrated[legacy_col] = float('nan')

        shots_on_target_weight = _mean_valid([
            _legacy_weight(row, 'HomeShotsOnTarget'),
            _legacy_weight(row, 'AwayShotsOnTarget')
        ], default_value=1.0)
        shots_weight = _mean_valid([
            _legacy_weight(row, 'HomeShots'),
            _legacy_weight(row, 'AwayShots')
        ], default_value=1.0)
        xg_weight = _mean_valid([
            _legacy_weight(row, 'HomeXG'),
            _legacy_weight(row, 'AwayXG'),
            shots_on_target_weight,
            shots_weight
        ], default_value=1.0)

        migrated['Weight_General_GoalCreation_XG'] = xg_weight
        migrated['Weight_General_GoalCreation_ShotsOnTarget'] = shots_on_target_weight
        migrated['Weight_General_GoalCreation_Shots'] = shots_weight

        migrated['Weight_General_GameControl_Possession'] = _mean_valid([
            _legacy_weight(row, 'HomePossession'),
            _legacy_weight(row, 'AwayPossession')
        ], default_value=1.0)
        migrated['Weight_General_GameControl_Passes'] = _mean_valid([
            _legacy_weight(row, 'HomePasses'),
            _legacy_weight(row, 'AwayPasses')
        ], default_value=1.0)
        migrated['Weight_General_GameControl_PassAccuracy'] = _mean_valid([
            _legacy_weight(row, 'HomePassAccuracy'),
            _legacy_weight(row, 'AwayPassAccuracy')
        ], default_value=1.0)

        migrated['Weight_General_DisciplineSetPiece_Fouls'] = _mean_valid([
            _legacy_weight(row, 'HomeFouls'),
            _legacy_weight(row, 'AwayFouls')
        ], default_value=1.0)
        migrated['Weight_General_DisciplineSetPiece_YellowCard'] = _mean_valid([
            _legacy_weight(row, 'HomeYellowCard'),
            _legacy_weight(row, 'AwayYellowCard')
        ], default_value=1.0)
        migrated['Weight_General_DisciplineSetPiece_RedCard'] = _mean_valid([
            _legacy_weight(row, 'HomeRedCard'),
            _legacy_weight(row, 'AwayRedCard')
        ], default_value=1.0)
        migrated['Weight_General_DisciplineSetPiece_Corners'] = _mean_valid([
            _legacy_weight(row, 'HomeCorners'),
            _legacy_weight(row, 'AwayCorners')
        ], default_value=1.0)
        migrated['Weight_General_DisciplineSetPiece_Offsides'] = _mean_valid([
            _legacy_weight(row, 'HomeOffsides'),
            _legacy_weight(row, 'AwayOffsides')
        ], default_value=1.0)

        for suffix in h2h_suffixes:
            migrated[f'Weight_H2H_{suffix}'] = _legacy_weight(row, suffix, default_value=1.0)

        for suffix in weather_suffixes:
            migrated[f'Weight_WeatherContext_{suffix}'] = _legacy_weight(row, suffix, default_value=1.0)

        migrated['Weight_Player_FormDiff'] = 1.0
        migrated['Weight_Player_AbsencePenaltyDiff'] = 1.0
        migrated['Weight_BaseMultiplier_General'] = 1.0
        migrated['Weight_BaseMultiplier_H2H'] = 1.0
        migrated['Weight_BaseMultiplier_Player'] = 1.0
        migrated['IsMigratedFromLegacy'] = True

        migrated_rows.append(migrated)
        existing_keys.add(row_key)

    if not migrated_rows:
        return hist, 0

    migrated_df = pd.DataFrame(migrated_rows)
    updated = pd.concat([hist, migrated_df], ignore_index=True, sort=False)
    dedupe_cols = [c for c in ['PredictionSource', 'MatchStatsMode', 'FeatureSchemaVersion', 'BatchID', 'RunID'] if c in updated.columns]
    if dedupe_cols:
        updated = updated.drop_duplicates(subset=dedupe_cols, keep='last')
    return updated, len(migrated_rows)


def ensure_migrated_history_schema(history_path, target_schema_version):
    existing = read_optional_csv(history_path)
    if existing.empty:
        return 0

    if 'MatchStatsMode' not in existing.columns:
        existing['MatchStatsMode'] = 'actual'
    if 'PredictionSource' not in existing.columns:
        existing['PredictionSource'] = 'simulation'
    if 'SourcePredictionMode' not in existing.columns:
        if 'PredictionMode' in existing.columns:
            existing['SourcePredictionMode'] = existing['PredictionMode']
        else:
            existing['SourcePredictionMode'] = 'reference'
    if 'FeatureSchemaVersion' not in existing.columns:
        existing['FeatureSchemaVersion'] = 'legacy_v1'

    migrated_history, migrated_count = migrate_legacy_history_to_hybrid(existing, target_schema_version)
    if migrated_count > 0:
        migrated_history.to_csv(history_path, index=False)
    return migrated_count


def load_run_history(path, weight_cols, match_stats_mode, source_prediction_mode=None, feature_schema_version=None):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        hist = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    if 'MatchStatsMode' not in hist.columns:
        hist['MatchStatsMode'] = 'actual'
    if 'SourcePredictionMode' not in hist.columns:
        if 'PredictionMode' in hist.columns:
            hist['SourcePredictionMode'] = hist['PredictionMode']
        else:
            hist['SourcePredictionMode'] = 'reference'
    if 'FeatureSchemaVersion' not in hist.columns:
        hist['FeatureSchemaVersion'] = 'legacy_v1'

    hist = hist[hist['MatchStatsMode'] == match_stats_mode].copy()
    if source_prediction_mode is not None:
        hist = hist[hist['SourcePredictionMode'] == source_prediction_mode].copy()
    if feature_schema_version is not None:
        hist = hist[hist['FeatureSchemaVersion'] == feature_schema_version].copy()
    if hist.empty:
        return hist

    for col in weight_cols:
        if col not in hist.columns:
            hist[col] = 1.0
    for col in ['AvgNLL', 'Accuracy', 'H2H_K']:
        if col not in hist.columns:
            hist[col] = float('nan')

    for col in weight_cols + ['AvgNLL', 'Accuracy', 'H2H_K']:
        hist[col] = pd.to_numeric(hist[col], errors='coerce')

    if weight_cols:
        hist[weight_cols] = hist[weight_cols].fillna(1.0)
    if 'H2H_K' in hist.columns:
        hist['H2H_K'] = hist['H2H_K'].fillna(H2H_K_DEFAULT)

    hist = hist.dropna(subset=['AvgNLL', 'Accuracy', 'H2H_K'])
    return hist

def train_surrogate_model(history_df, feature_cols, target_col):
    X = history_df[feature_cols]
    y = history_df[target_col]
    if SURROGATE_MODEL == 'nn':
        model = make_pipeline(
            StandardScaler(),
            MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=500, random_state=RANDOM_STATE)
        )
    else:
        model = GradientBoostingRegressor(random_state=RANDOM_STATE)
    model.fit(X, y)
    return model

def generate_candidate_df(num, weight_parameter_names, k_range):
    rows = []
    for _ in range(num):
        row = {f'Weight_{param}': random.random() * 2.0 for param in weight_parameter_names}
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
        explore = remaining.sample(n=min(explore_count, len(remaining)), random_state=RANDOM_STATE)
        selected = pd.concat([selected, explore])

    return selected.reset_index(drop=True)

# 8. Trainieren (pro Run, nach H2H-Skalierung)
ref_results = load_reference_results(RESULTS_PATH, FALLBACK_RESULTS_PATH)
print(f"Prediction mode: {PREDICTION_MODE}")
print(f"Match stats mode: {MATCH_STATS_MODE}")
print(f"Output path: {OUTPUT_PATH}")
print(f"Surrogate history source: {RUN_HISTORY_SOURCE_PATH}")

for history_path in {RUN_HISTORY_SOURCE_PATH, RUN_HISTORY_PATH}:
    migrated_count = ensure_migrated_history_schema(history_path, FEATURE_SCHEMA_VERSION)
    if migrated_count > 0:
        print(f"Migrated {migrated_count} legacy run-history rows to {FEATURE_SCHEMA_VERSION}: {history_path}")

if PREDICTION_MODE == 'reference':
    backfill_pred_df, backfill_summary_df = try_backfill_reference_from_future(ref_results)
    if not backfill_pred_df.empty:
        matched_ids = sorted(backfill_pred_df['MatchID'].dropna().unique().tolist())
        unresolved_ids = []
        if ref_results is not None and not ref_results.empty:
            unresolved_ids = sorted(set(ref_results.index.tolist()) - set(matched_ids))

        print(
            f"Reference mode: using backfilled future predictions for "
            f"{len(matched_ids)} MatchIDs across {backfill_summary_df['RunID'].nunique()} saved runs."
        )
        if unresolved_ids:
            print(
                f"Reference mode: {len(unresolved_ids)} MatchIDs in match_results_references.csv "
                f"had no matching saved future prediction and were skipped."
            )

        backfill_pred_df.to_csv(PREDICTION_OUT_PATH, index=False)
        backfill_summary_df.to_csv(RUN_SUMMARY_OUT_PATH, index=False)
        evaluation_history = append_future_vs_reference_metrics(FUTURE_VS_REFERENCE_METRICS_PATH, backfill_summary_df)
        print(f"Updated future-vs-reference evaluation log: {FUTURE_VS_REFERENCE_METRICS_PATH}")
        if not evaluation_history.empty:
            eval_cols = [c for c in [
                'EvaluationTimestamp', 'RunID', 'BatchID', 'MatchStatsMode',
                'AvgNLL', 'Accuracy', 'Pred_AvgNLL', 'Pred_Accuracy',
                'Delta_AvgNLL_vs_Pred', 'Delta_Accuracy_vs_Pred',
                'EvalRank_Combined', 'EvalIsBestCombined'
            ] if c in evaluation_history.columns]
            if eval_cols:
                print(evaluation_history[eval_cols].head(10))


        display_cols = [col for col in [
            'RunID', 'MatchID', 'MatchDate', 'HomeTeam', 'AwayTeam',
            'PredictedResult', 'ActualResult', 'ProbActual', 'MatchNLL'
        ] if col in backfill_pred_df.columns]
        if display_cols:
            print(backfill_pred_df[display_cols].head(10))
        print(backfill_summary_df.head(5))

        history_updated = append_to_run_history(RUN_HISTORY_PATH, backfill_summary_df)
        backfill_modes = backfill_summary_df['MatchStatsMode'].dropna().unique().tolist()
        if backfill_modes and 'MatchStatsMode' in history_updated.columns:
            current_mode_history = history_updated[history_updated['MatchStatsMode'].isin(backfill_modes)].copy()
        else:
            current_mode_history = history_updated.copy()
        if 'FeatureSchemaVersion' in current_mode_history.columns:
            current_mode_history = current_mode_history[current_mode_history['FeatureSchemaVersion'] == FEATURE_SCHEMA_VERSION].copy()

        decision_df = build_pareto_decision_set(current_mode_history, PARETO_TARGET_SIZE)
        decision_df = persist_decision_table(decision_df, PARETO_OUT_PATH)
        print(decision_df.head(5))
        raise SystemExit(0)

predict_df = build_prediction_frame(
    df,
    ref_results,
    PREDICTION_MODE,
    future_limit=9,
    reference_limit=REFERENCE_PREDICTION_LIMIT
)
raw_predict_df = predict_df.copy()

train_df = df[df['Played'] == True].copy()
if PREDICTION_MODE == 'reference':
    train_df = train_df[~train_df['MatchID'].isin(predict_df['MatchID'])].copy()
    print(f"Training matches after excluding reference targets: {len(train_df)}")

train_df, predict_df, signal_input_features, predicted_match_stats_df, match_stats_summary_df = apply_match_stats_mode(
    train_df,
    predict_df,
    raw_predict_df
)
weight_parameter_names = collect_weight_parameter_names(MATCH_STATS_MODE)
weight_cols = [f'Weight_{param}' for param in weight_parameter_names]

if MATCH_STATS_MODE == 'predicted':
    if predicted_match_stats_df.empty:
        predicted_match_stats_df = pd.DataFrame(columns=[
            'MatchID', 'MatchDate', 'HomeTeam', 'AwayTeam',
            'PredictionMode', 'MatchStatsMode', 'MatchStatsModel'
        ] + match_stats_features)
    predicted_match_stats_df.to_csv(PREDICTED_MATCH_STATS_OUT_PATH, index=False)
    if not match_stats_summary_df.empty:
        print(match_stats_summary_df.head(len(match_stats_summary_df)))

train_df['GoalDiff'] = train_df['HomeGoals'] - train_df['AwayGoals']
train_df = train_df[train_df['GoalDiff'].notna()].copy()
if train_df.empty:
    raise ValueError("Training dataset is empty after applying the selected prediction mode.")

X_train, X_val, y_train, y_val = train_test_split(
    train_df[signal_input_features], train_df['GoalDiff'], test_size=0.2, random_state=RANDOM_STATE
)

run_limit = MAX_RUNS if (PREDICTION_MODE == 'future' or ref_results is not None) else 1

print("GoalDiff NaNs:", train_df['GoalDiff'].isna().sum())
print("X_train NaNs (raw):", X_train.isna().sum().sum())
if PREDICTION_MODE == 'reference' and ref_results is None:
    print(f"Reference results not found at {RESULTS_PATH} (or fallback {FALLBACK_RESULTS_PATH}); running only 1 weight set.")


# 9. Vorhersage (nur naechste 9)
all_runs = []
run_metrics = []
best_score = None
best_run = None

if predict_df.empty:
    pred_df = pd.DataFrame(columns=['MatchID','MatchDate','HomeTeam','AwayTeam','PredictedGoalDiff'])
    print("Keine ungespielten Spiele gefunden. Leere Ergebnis-Tabelle:")
    print(pred_df.head(9))
else:
    X_train_base = X_train.copy()
    X_pred_base = predict_df[signal_input_features].copy()

    draw_margin = 0.5

    def normal_cdf(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def outcome_from_row(row):
        if row['HomeGoals'] > row['AwayGoals']:
            return 'H'
        if row['HomeGoals'] < row['AwayGoals']:
            return 'A'
        return 'D'

    def resolve_h2h_k(value):
        try:
            k_val = float(value)
        except (TypeError, ValueError):
            return int(H2H_K_DEFAULT)
        if not math.isfinite(k_val):
            return int(H2H_K_DEFAULT)
        low = int(H2H_K_RANGE[0])
        high = int(H2H_K_RANGE[1])
        return max(low, min(high, int(round(k_val))))

    history_df = load_run_history(
        RUN_HISTORY_SOURCE_PATH,
        weight_cols,
        MATCH_STATS_MODE,
        PREDICTION_MODE,
        FEATURE_SCHEMA_VERSION
    )
    use_surrogate = len(history_df) >= SURROGATE_MIN_HISTORY

    if use_surrogate:
        feature_cols = weight_cols + ['H2H_K']
        nll_model = train_surrogate_model(history_df, feature_cols, 'AvgNLL')
        acc_model = train_surrogate_model(history_df, feature_cols, 'Accuracy')
        candidate_df = generate_candidate_df(max(SURROGATE_CANDIDATES, run_limit), weight_parameter_names, H2H_K_RANGE)
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
        selected_df = generate_candidate_df(run_limit, weight_parameter_names, H2H_K_RANGE)

    batch_id = 1
    if not history_df.empty and 'BatchID' in history_df.columns:
        try:
            batch_id = int(history_df['BatchID'].max()) + 1
        except Exception:
            batch_id = 1

    for idx, cand in selected_df.iterrows():
        run_id = idx + 1
        run_k = resolve_h2h_k(cand['H2H_K'] if 'H2H_K' in cand.index else H2H_K_DEFAULT)
        pred_run_nll = float(cand['Pred_AvgNLL']) if 'Pred_AvgNLL' in cand.index and pd.notna(cand['Pred_AvgNLL']) else float('nan')
        pred_run_acc = float(cand['Pred_Accuracy']) if 'Pred_Accuracy' in cand.index and pd.notna(cand['Pred_Accuracy']) else float('nan')
        weights = {}
        for param in weight_parameter_names:
            col_name = f'Weight_{param}'
            if col_name in cand.index and pd.notna(cand[col_name]):
                weights[param] = float(cand[col_name])
            else:
                weights[param] = 1.0

        X_train_scaled = apply_h2h_scaling(X_train_base, run_k)
        X_pred_scaled = apply_h2h_scaling(X_pred_base, run_k)

        if len(X_train_scaled) != len(y_train):
            raise ValueError(
                f"Training feature/target length mismatch: X_train_scaled={len(X_train_scaled)} "
                f"vs y_train={len(y_train)}"
            )

        imputer = SimpleImputer(strategy='median')
        X_train_imp = pd.DataFrame(
            imputer.fit_transform(X_train_scaled),
            columns=X_train_scaled.columns,
            index=X_train_scaled.index
        )
        X_pred_imp = pd.DataFrame(
            imputer.transform(X_pred_scaled),
            columns=X_pred_scaled.columns,
            index=X_pred_scaled.index
        )

        X_train_w = build_outcome_design_matrix(X_train_imp, weights, MATCH_STATS_MODE)
        X_pred_w = build_outcome_design_matrix(X_pred_imp, weights, MATCH_STATS_MODE)

        # Use a single worker to avoid multiprocessing pipe permission issues on restricted hosts.
        model = SklearnModel(n_trees=50, n_jobs=1)
        model.fit(X_train_w.values, y_train.values)

        train_preds = model.predict(X_train_w.values)
        residuals = y_train.values - train_preds
        sigma = float(pd.Series(residuals).std())
        if not math.isfinite(sigma) or sigma <= 0:
            sigma = 1.0

        preds = model.predict(X_pred_w.values)

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
        pred_df['PredictionMode'] = PREDICTION_MODE
        pred_df['PredictionSource'] = 'simulation'
        pred_df['SourcePredictionMode'] = PREDICTION_MODE
        pred_df['MatchStatsMode'] = MATCH_STATS_MODE
        pred_df['FeatureSchemaVersion'] = FEATURE_SCHEMA_VERSION
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

        for base_col in BASE_SIGNAL_FEATURES:
            if base_col in X_pred_w.columns:
                pred_df[base_col] = X_pred_w[base_col].values

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

        for param in weight_parameter_names:
            pred_df[f'Weight_{param}'] = weights[param]

        if 'H2H_Combined_MatchCount' in pred_df.columns:
            pred_df['H2H_Combined_Alpha'] = pred_df['H2H_Combined_MatchCount'].apply(
                lambda c: c / (c + run_k) if pd.notna(c) and c >= 0 else float('nan')
            )
        if 'H2H_Venue_MatchCount' in pred_df.columns:
            pred_df['H2H_Venue_Alpha'] = pred_df['H2H_Venue_MatchCount'].apply(
                lambda c: c / (c + run_k) if pd.notna(c) and c >= 0 else float('nan')
            )

        if 'H2H_Combined_Alpha' in pred_df.columns:
            for spec in H2H_SIGNAL_SPECS:
                feat = spec['column']
                if feat in H2H_COMBINED_FEATURES:
                    wcol = f"Weight_{spec['weight_name']}"
                    if wcol in pred_df.columns:
                        pred_df[f'Effective_{wcol}'] = pred_df[wcol] * pred_df['H2H_Combined_Alpha']
        if 'H2H_Venue_Alpha' in pred_df.columns:
            for spec in H2H_SIGNAL_SPECS:
                feat = spec['column']
                if feat in H2H_VENUE_FEATURES:
                    wcol = f"Weight_{spec['weight_name']}"
                    if wcol in pred_df.columns:
                        pred_df[f'Effective_{wcol}'] = pred_df[wcol] * pred_df['H2H_Venue_Alpha']

        run_score = None
        run_accuracy = None
        run_count = 0
        matched_reference_count = 0
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
            'PredictionMode': PREDICTION_MODE,
            'PredictionSource': 'simulation',
            'SourcePredictionMode': PREDICTION_MODE,
            'MatchStatsMode': MATCH_STATS_MODE,
            'FeatureSchemaVersion': FEATURE_SCHEMA_VERSION,
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
        for param in weight_parameter_names:
            metric_row[f'Weight_{param}'] = weights[param]
        run_metrics.append(metric_row)
        all_runs.append(pred_df)



    all_pred_df = pd.concat(all_runs, ignore_index=True) if all_runs else pred_df.copy()
    all_pred_df.to_csv(PREDICTION_OUT_PATH, index=False)

    cols = ['RunID','MatchID','MatchDate','HomeTeam','AwayTeam','WinProb','DrawProb','LoseProb']
    display_cols = [col for col in cols if col in all_pred_df.columns]
    if display_cols:
        print(all_pred_df[display_cols].head(10))
    else:
        print(all_pred_df.head(10))
    if best_run is not None:
        print(f"Best run: {best_run} (avg NLL={best_score:.6f})")
    if run_metrics:
        summary_df = prepare_run_summary(pd.DataFrame(run_metrics))
        summary_df.to_csv(RUN_SUMMARY_OUT_PATH, index=False)
        print(summary_df.head(5))

        history_updated = append_to_run_history(RUN_HISTORY_PATH, summary_df)

        current_mode_history = history_updated.copy()
        if 'MatchStatsMode' in current_mode_history.columns:
            current_mode_history = current_mode_history[current_mode_history['MatchStatsMode'] == MATCH_STATS_MODE].copy()
        if 'FeatureSchemaVersion' in current_mode_history.columns:
            current_mode_history = current_mode_history[current_mode_history['FeatureSchemaVersion'] == FEATURE_SCHEMA_VERSION].copy()

        if PREDICTION_MODE == 'reference':
            decision_df = build_pareto_decision_set(current_mode_history, PARETO_TARGET_SIZE)
        else:
            decision_df = build_future_candidate_ranking(summary_df, PARETO_TARGET_SIZE)
        decision_df = persist_decision_table(decision_df, PARETO_OUT_PATH)
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
                'PredictionMode', 'MatchStatsMode',
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
    else:
        pd.DataFrame().to_csv(RUN_SUMMARY_OUT_PATH, index=False)
        persist_decision_table(pd.DataFrame(), PARETO_OUT_PATH)
        if PREDICTION_MODE != 'reference':
            pd.DataFrame().to_csv(FUTURE_OUTCOME_TABLE_PATH, index=False)
