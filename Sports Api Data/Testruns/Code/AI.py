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
OUTPUT_PATH = r'C:/AI Projekt/KI-Projekt/Sports Api Data/Testruns/Datacollection'
RESULTS_PATH = os.path.join(OUTPUT_PATH, 'match_results_references.csv')
FALLBACK_RESULTS_PATH = os.path.join(DATA_PATH, 'match_results_references.csv')
PREDICTION_OUT_PATH = os.path.join(OUTPUT_PATH, 'prediction_weight_runs.csv')
RUN_SUMMARY_OUT_PATH = os.path.join(OUTPUT_PATH, 'prediction_weight_run_summary.csv')
RUN_HISTORY_PATH = os.path.join(OUTPUT_PATH, 'surrogate_run_history.csv')
PARETO_OUT_PATH = os.path.join(OUTPUT_PATH, 'pareto_front.csv')
WEATHER_HIST_PATH = os.path.join(DATA_PATH, 'historical_weather_data_78.csv')
WEATHER_FUTURE_PATH = os.path.join(OUTPUT_PATH, 'weather_data.csv')
MAX_RUNS = 700

# === SURROGATE MODEL SWITCH ===
# "gbr" = Gradient Boosting (recommended for now)
# "nn"  = Neural Network surrogate (use when you have much more data)
SURROGATE_MODEL = 'gbr'
SURROGATE_MIN_HISTORY = 100
SURROGATE_CANDIDATES = 300
SURROGATE_RANDOM_FRACTION = 0.2

# === H2H K SEARCH RANGE (integers only) ===
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
if not predict_df.empty:
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

# 7a. Train/Test
X_train, X_val, y_train, y_val = train_test_split(
    train_df[features], train_df['GoalDiff'], test_size=0.2, random_state=42
)

# 8. Trainieren (pro Run, nach H2H-Skalierung)
ref_results = load_reference_results(RESULTS_PATH, FALLBACK_RESULTS_PATH)
run_limit = MAX_RUNS if ref_results is not None else 1

print("GoalDiff NaNs:", train_df['GoalDiff'].isna().sum())
print("X_train NaNs (raw):", X_train.isna().sum().sum())
if ref_results is None:
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

    history_df = load_run_history(RUN_HISTORY_PATH, weight_cols)
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
        weights = {feat: float(cand[f'Weight_{feat}']) for feat in features}
        weight_vec = pd.Series(weights, index=features).values

        X_train_scaled = apply_h2h_scaling(X_train_base, run_k)
        X_pred_scaled = apply_h2h_scaling(X_pred_base, run_k)

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
            valid_probs = merged['ProbActual'].dropna()
            if not valid_probs.empty:
                run_score = float((-valid_probs.apply(math.log)).mean())
            pred_df = merged

            actual_rows = merged['ActualResult'].dropna()
            if not actual_rows.empty:
                predicted = merged[['WinProb', 'DrawProb', 'LoseProb']].idxmax(axis=1)
                predicted = predicted.map({'WinProb': 'H', 'DrawProb': 'D', 'LoseProb': 'A'})
                correct_mask = (predicted[actual_rows.index] == actual_rows)
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

        metric_row = {
            'RunID': run_id,
            'BatchID': batch_id,
            'H2H_K': run_k,
            'AvgNLL': run_score,
            'Accuracy': run_accuracy,
            'NumMatchesScored': run_count
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
        summary_df = summary_df.sort_values(['AvgNLL', 'Accuracy'], ascending=[True, False])
        summary_df.to_csv(RUN_SUMMARY_OUT_PATH, index=False)
        print(summary_df.head(5))

        history_updated = pd.concat([history_df, summary_df], ignore_index=True)
        history_updated.to_csv(RUN_HISTORY_PATH, index=False)

        pareto_df = compute_pareto_front(history_updated)
        pareto_df.to_csv(PARETO_OUT_PATH, index=False)
