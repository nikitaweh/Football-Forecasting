import os
import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# Pfad zum Datenordner anpassen
DATA_PATH = r'C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection'

# 1. Laden
match_stats   = pd.read_csv(os.path.join(DATA_PATH, 'match_statistics_filtered_78.csv'))
stammdaten    = pd.read_csv(os.path.join(DATA_PATH, 'Stammdaten_78.csv'))
injuries      = pd.read_csv(os.path.join(DATA_PATH, 'injuries_league_78.csv'))
lineups       = pd.read_csv(os.path.join(DATA_PATH, 'lineups_league_78.csv'))
teams         = pd.read_csv(os.path.join(DATA_PATH, 'Teams_78.csv'))
player_stats  = pd.read_csv(os.path.join(DATA_PATH, 'player_statistics_per_fixture_league_78.csv'), low_memory=False)

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

injuries.rename(columns={
    'Match ID': 'MatchID', 
    'Player ID': 'PlayerID', 
    'Player Name': 'PlayerName',
    'Team ID': 'TeamID', 'Team Name': 'TeamName',
    
}, inplace=True)

lineups.rename(columns={
    'Match ID': 'MatchID', 'Home Team ID': 'HomeTeamID', 'Away Team ID': 'AwayTeamID',
    'Player ID': 'PlayerID', 'Player Name': 'PlayerName', 'StartXI': 'StartXI'
}, inplace=True)

player_stats.rename(columns={
    'Match ID': 'MatchID', 'Team ID': 'TeamID', 'Player ID': 'PlayerID',
    'Player Name': 'PlayerName', 'Rating': 'Rating'
}, inplace=True)
player_stats['Rating'] = pd.to_numeric(player_stats['Rating'], errors='coerce')

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

# Verletzungen aggregieren (weit, pro TeamID) und nur dort NAs füllen
inj_agg = injuries.groupby(['MatchID', 'TeamID']).size().unstack(fill_value=0).add_prefix('NumInjuries_')
df = df.merge(inj_agg, on='MatchID', how='left')
inj_cols = [c for c in df.columns if c.startswith('NumInjuries_')]
if inj_cols:
    df[inj_cols] = df[inj_cols].fillna(0)

# Aufstellungen
home_lp = lineups[lineups['StartXI']].groupby(['MatchID','HomeTeamID']).size().reset_index(name='StartXI_Home')
away_lp = lineups[lineups['StartXI']].groupby(['MatchID','AwayTeamID']).size().reset_index(name='StartXI_Away')
df = df.merge(home_lp[['MatchID','StartXI_Home']], on='MatchID', how='left')
df = df.merge(away_lp[['MatchID','StartXI_Away']], on='MatchID', how='left')
df[['StartXI_Home','StartXI_Away']] = df[['StartXI_Home','StartXI_Away']].fillna(0)

# Spielerbewertungen
player_agg = player_stats.groupby(['MatchID','TeamID'])['Rating'].mean().unstack(fill_value=0).add_prefix('AvgRating_')
df = df.merge(player_agg, on='MatchID', how='left')
rating_cols = [c for c in df.columns if c.startswith('AvgRating_')]
if rating_cols:
    df[rating_cols] = df[rating_cols].fillna(0)

# 4. Split nach 'Played'
train_df   = df[df['Played'] == True].copy()
predict_df = df[df['Played'] == False].copy()

# --- Nur die nächsten 10 ungespielten Spiele nach Datum ---
if not predict_df.empty:
    predict_df['MatchDate'] = pd.to_datetime(predict_df['MatchDate'], errors='coerce')
    predict_df = predict_df.sort_values('MatchDate').head(10).copy()
    print(f"Nächste ungespielte Spiele (bis zu 10): {len(predict_df)}")

# 5. Ziel
train_df['Result'] = train_df['Winner']

# 6. Encoding
encoder = LabelEncoder()
train_df['ResultEnc'] = encoder.fit_transform(train_df['Result'])
all_class_names = list(encoder.classes_)

# 7. Features (Achtung: kommen aus match_stats und sind bei ungespielten oft NaN – XGBoost kann NaN handlen)
features = ['HomeGoals','AwayGoals',
            'HomePossession','AwayPossession', 
            'HomeShots','AwayShots', 
            'HomeShotsOnTarget','AwayShotsOnTarget',
            'HomePasses','AwayPasses',
            'HomePassAccuracy','AwayPassAccuracy',
            'HomeFouls','AwayFouls',
            'HomeYellowCard','AwayYellowCard',
            'HomeRedCard','AwayRedCard',
            'HomeOffsides','AwayOffsides',
            'HomeCorners','AwayCorners']
missing = [f for f in features if f not in train_df.columns]
if missing:
    raise ValueError(f"Fehlende Feature-Spalten im Trainingsdatensatz: {missing}")

# 7a. Train/Test
X_train, X_val, y_train, y_val = train_test_split(
    train_df[features], train_df['ResultEnc'], test_size=0.2, random_state=42, stratify=train_df['ResultEnc']
)

# 8. Trainieren
model = XGBClassifier(eval_metric='mlogloss', random_state=42)
model.fit(X_train, y_train)

# 9. Vorhersage (nur nächste 10)
if predict_df.empty:
    pred_df = pd.DataFrame(columns=['MatchID','MatchDate','HomeTeam','AwayTeam','Predicted'] + all_class_names)
    print("Keine ungespielten Spiele gefunden. Leere Ergebnis-Tabelle:")
    print(pred_df.head(10))
else:
    X_pred = predict_df[features]
    probs = model.predict_proba(X_pred)
    model_label_ids = model.classes_
    model_class_names = encoder.inverse_transform(model_label_ids)

    pred_df = pd.DataFrame(probs, columns=model_class_names, index=predict_df.index)

    for cls in all_class_names:
        if cls not in pred_df.columns:
            pred_df[cls] = 0.0
    pred_df = pred_df[all_class_names]

    pred_df['Predicted'] = pred_df[all_class_names].idxmax(axis=1)
    pred_df['MatchID']   = predict_df['MatchID'].values
    pred_df['MatchDate'] = predict_df['MatchDate'].values
    pred_df['HomeTeam']  = predict_df['HomeTeam'].values
    pred_df['AwayTeam']  = predict_df['AwayTeam'].values

    cols = ['MatchID','MatchDate','HomeTeam','AwayTeam','Predicted'] + all_class_names
    print(pred_df[cols].head(10))