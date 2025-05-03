import os
import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# Pfad zum Datenordner anpassen (Windows-Pfade mit raw string)
DATA_PATH = r'C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection'

# 1. Laden aller Datensätze
match_stats = pd.read_csv(os.path.join(DATA_PATH, 'match_statistics_filtered_78.csv'))
stammdaten   = pd.read_csv(os.path.join(DATA_PATH, 'Stammdaten_78.csv'))
weather      = pd.read_csv(os.path.join(DATA_PATH, 'historical_weather_data_78.csv'))
injuries     = pd.read_csv(os.path.join(DATA_PATH, 'injuries_league_78.csv'))
lineups      = pd.read_csv(os.path.join(DATA_PATH, 'lineups_league_78.csv'))
teams        = pd.read_csv(os.path.join(DATA_PATH, 'Teams_78.csv'))

# Player Statistics mit low_memory=False einlesen und Rating numerisch sicherstellen
player_stats = pd.read_csv(
    os.path.join(DATA_PATH, 'player_statistics_per_fixture_league_78.csv'),
    low_memory=False
)
player_stats['Rating'] = pd.to_numeric(player_stats['Rating'], errors='coerce')

# 2. Spalten umbenennen
stammdaten.rename(columns={
    'Home Team ID': 'HomeTeamID', 'Away Team ID': 'AwayTeamID',
    'Home Team': 'HomeTeam', 'Away Team': 'AwayTeam',
    'Date': 'MatchDate', 'Gespielt': 'Played'
}, inplace=True)
injuries.rename(columns={
    'Player ID': 'PlayerID', 'Player Name': 'PlayerName',
    'Team ID': 'TeamID', 'Team Name': 'TeamName'
}, inplace=True)
lineups.rename(columns={
    'Home Team ID': 'HomeTeamID', 'Away Team ID': 'AwayTeamID',
    'Player ID': 'PlayerID', 'Player Name': 'PlayerName'
}, inplace=True)
player_stats.rename(columns={
    'Team ID': 'TeamID', 'Player ID': 'PlayerID', 'Player Name': 'PlayerName'
}, inplace=True)
teams.rename(columns={
    'Team ID': 'TeamID', 'Team Name': 'TeamName',
    'Stadion ID': 'StadiumID', 'Capacity': 'StadiumCapacity'
}, inplace=True)

# 3. Merge aller Daten
# 3.1 Match-Statistiken + Stammdaten
df = match_stats.merge(stammdaten, on='MatchID', how='left')
# 3.2 Wetterdaten
df = df.merge(weather, on='MatchID', how='left')
# 3.3 Team-Metadaten Home/Away
teams_home = teams.add_suffix('_Home')
teams_away = teams.add_suffix('_Away')
df = df.merge(
    teams_home, left_on='HomeTeamID', right_on='TeamID_Home', how='left'
).merge(
    teams_away, left_on='AwayTeamID', right_on='TeamID_Away', how='left'
)
# 3.4 Verletzungen
inj_agg = injuries.groupby(['MatchID', 'TeamID']).size().unstack(fill_value=0).add_prefix('NumInjuries_')
df = df.merge(inj_agg, on='MatchID', how='left').fillna(0)
# 3.5 Aufstellungen
home_lineup = lineups[lineups['StartXI']==True].groupby(['MatchID','HomeTeamID']).size().reset_index(name='StartXI_Home')
away_lineup = lineups[lineups['StartXI']==True].groupby(['MatchID','AwayTeamID']).size().reset_index(name='StartXI_Away')
df = df.merge(home_lineup[['MatchID','StartXI_Home']], on='MatchID', how='left')
df = df.merge(away_lineup[['MatchID','StartXI_Away']], on='MatchID', how='left')
df[['StartXI_Home','StartXI_Away']] = df[['StartXI_Home','StartXI_Away']].fillna(0)
# 3.6 Spielerstatistiken
player_agg = player_stats.groupby(['MatchID','TeamID'])['Rating'].mean().unstack(fill_value=0).add_prefix('AvgRating_')
df = df.merge(player_agg, on='MatchID', how='left').fillna(0)

# 4. Trainings- vs. Prognose-Daten
df_played = df[df['Played']==True].copy()
df_future = df[df['Played']==False].copy()

# 5. Feature-Liste
features = ['Home Goals','Away Goals','Home Possession','Away Possession']

# 6. Ergebnis in Trainingsdaten erzeugen
df_played.loc[:, 'Result'] = df_played.apply(
    lambda r: 'HomeWin' if r['Home Goals']>r['Away Goals'] else ('AwayWin' if r['Home Goals']<r['Away Goals'] else 'Draw'), axis=1
)

# 7. Label-Encoding
encoder = LabelEncoder()
df_played.loc[:, 'ResultEnc'] = encoder.fit_transform(df_played['Result'])

# 8. Modelltraining
X_train, X_val, y_train, y_val = train_test_split(
    df_played[features], df_played['ResultEnc'], test_size=0.2, random_state=42
)
model = XGBClassifier(eval_metric='mlogloss')
model.fit(X_train, y_train)

# 9. Vorhersage für zukünftige Matches
X_pred = df_future[features]
probs = model.predict_proba(X_pred)

# 10. Ergebnisse zusammenstellen
df_pred = pd.DataFrame(probs, columns=encoder.classes_, index=df_future.index)
df_pred['Predicted'] = df_pred.idxmax(axis=1)
df_pred['MatchID'] = df_future['MatchID']

# 11. Ausgabe
df_output = df_pred[['MatchID','Predicted'] + list(encoder.classes_)]
print(df_output)
