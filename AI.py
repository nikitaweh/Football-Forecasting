import os
import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# Pfad zum Datenordner anpassen
DATA_PATH = r'C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection'

# 1. Laden aller Datensätze
match_stats   = pd.read_csv(os.path.join(DATA_PATH, 'match_statistics_filtered_78.csv'))
stammdaten    = pd.read_csv(os.path.join(DATA_PATH, 'Stammdaten_78.csv'))
weather       = pd.read_csv(os.path.join(DATA_PATH, 'historical_weather_data_78.csv'))
injuries      = pd.read_csv(os.path.join(DATA_PATH, 'injuries_league_78.csv'))
lineups       = pd.read_csv(os.path.join(DATA_PATH, 'lineups_league_78.csv'))
teams         = pd.read_csv(os.path.join(DATA_PATH, 'Teams_78.csv'))
player_stats  = pd.read_csv(os.path.join(DATA_PATH, 'player_statistics_per_fixture_league_78.csv'), low_memory=False)

# 1.1 Wetterdaten aggregieren auf Match-Ebene
weather_agg = (
    weather.groupby('MatchID').agg({
        'Temperature (C)': 'mean',
        'Pressure':       'mean',
        'Humidity':       'mean',
        'Wind Speed':     'mean',
        'Rain':           'sum',
        'Snow':           'sum'
    })
    .reset_index()
    .rename(columns={
        'Temperature (C)': 'AvgTempC',
        'Pressure':       'AvgPressure',
        'Humidity':       'AvgHumidity',
        'Wind Speed':     'AvgWindSpeed',
        'Rain':           'TotalRain',
        'Snow':           'TotalSnow'
    })
)

# 2. Spalten umbenennen
stammdaten.rename(columns={
    'Home Team ID': 'HomeTeamID', 'Away Team ID': 'AwayTeamID',
    'Home Team': 'HomeTeam', 'Away Team': 'AwayTeam',
    'Date': 'MatchDate', 'Gespielt': 'Played'
}, inplace=True)
match_stats.rename(columns={
    'Home Goals': 'HomeGoals', 'Away Goals': 'AwayGoals',
    'Home Possession': 'HomePossession', 'Away Possession': 'AwayPossession'
}, inplace=True)
injuries.rename(columns={
    'Match ID': 'MatchID', 'Player ID': 'PlayerID', 'Player Name': 'PlayerName',
    'Team ID': 'TeamID', 'Team Name': 'TeamName'
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

# 3. Zusammenführen
# 3.1 Match-Statistiken + Stammdaten
df = match_stats.merge(stammdaten, on='MatchID', how='left')
# 3.2 Aggregierte Wetterdaten
df = df.merge(weather_agg, on='MatchID', how='left')
# 3.3 Team-Metadaten Home/Away
teams_home = teams.add_suffix('_Home')
teams_away  = teams.add_suffix('_Away')
df = (
    df
    .merge(teams_home, left_on='HomeTeamID', right_on='TeamID_Home', how='left')
    .merge(teams_away, left_on='AwayTeamID', right_on='TeamID_Away', how='left')
)
# 3.4 Verletzungen aggregieren
inj_agg = injuries.groupby(['MatchID', 'TeamID']).size().unstack(fill_value=0).add_prefix('NumInjuries_')
df = df.merge(inj_agg, on='MatchID', how='left').fillna(0)
# 3.5 Aufstellungen Home/Away
home_lp = lineups[lineups['StartXI']].groupby(['MatchID','HomeTeamID']).size().reset_index(name='StartXI_Home')
away_lp = lineups[lineups['StartXI']].groupby(['MatchID','AwayTeamID']).size().reset_index(name='StartXI_Away')
df = df.merge(home_lp[['MatchID','StartXI_Home']], on='MatchID', how='left')
df = df.merge(away_lp[['MatchID','StartXI_Away']], on='MatchID', how='left')
df[['StartXI_Home','StartXI_Away']] = df[['StartXI_Home','StartXI_Away']].fillna(0)
# 3.6 Spielerstatistiken aggregieren
player_agg = player_stats.groupby(['MatchID','TeamID'])['Rating'].mean().unstack(fill_value=0).add_prefix('AvgRating_')
df = df.merge(player_agg, on='MatchID', how='left').fillna(0)

# 4. Datenaufteilung basierend auf 'Played'
train_df = df[df['Played'] == True].copy()
predict_df = df[df['Played'] == False].copy()

# 4.1 Wetter-Features übernehmen
for col in ['AvgTempC','AvgPressure','AvgHumidity','AvgWindSpeed','TotalRain','TotalSnow']:
    train_df[col] = train_df[col]
    predict_df[col] = predict_df[col]

# 5. Ergebnis-Spalte direkt aus Stammdaten übernehmen
train_df['Result'] = train_df['Winner']

# 6. Encoding
encoder = LabelEncoder()
train_df['ResultEnc'] = encoder.fit_transform(train_df['Result'])

# 7. Train/Test Split für Trainingsdaten
features = ['HomeGoals','AwayGoals','HomePossession','AwayPossession',
            'AvgTempC','AvgPressure','AvgHumidity','AvgWindSpeed','TotalRain','TotalSnow']
X_train, X_val, y_train, y_val = train_test_split(
    train_df[features], train_df['ResultEnc'], test_size=0.2, random_state=42
)

# 8. Modelltraining
model = XGBClassifier(eval_metric='mlogloss')
model.fit(X_train, y_train)

# 9. Vorhersage für zukünftige Matches
X_pred = predict_df[features]
probs = model.predict_proba(X_pred)

# 10. Ergebnisse zusammenstellen
pred_df = pd.DataFrame(probs, columns=encoder.classes_, index=predict_df.index)
pred_df['Predicted'] = pred_df.idxmax(axis=1)
pred_df['MatchID']  = predict_df['MatchID']
pred_df['HomeTeam'] = predict_df['HomeTeam']
pred_df['AwayTeam'] = predict_df['AwayTeam']

# 11. Ausgabe (erste 9)
cols = ['MatchID','HomeTeam','AwayTeam','Predicted'] + list(encoder.classes_)
print(pred_df[cols].head(9))
