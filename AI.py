import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# Laden der Daten
match_statistics = pd.read_csv('C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/match_statistics_filtered_78.csv')
injuries = pd.read_csv('C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/injuries_league_78.csv')
weather = pd.read_csv('C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/historical_weather_data_78.csv')
teams = pd.read_csv('C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/Teams_78.csv')
stammdaten = pd.read_csv('C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/Stammdaten_78.csv')

# Beispiel-Merge: Match-Daten mit Team-Metadaten (Heim und Auswärts)
teams_home = teams.add_suffix('_Home')
teams_away = teams.add_suffix('_Away')
df = (match_statistics
      .merge(teams_home, left_on='HomeTeamID', right_on='TeamID_Home')
      .merge(teams_away, left_on='AwayTeamID', right_on='TeamID_Away'))

# Beispiel-Feature-Auswahl (anpassen nach Bedarf)
feature_cols = [
    'Goals_Home', 'Shots_Home', 'Possession_Home',
    'Goals_Away', 'Shots_Away', 'Possession_Away'
]
X = df[feature_cols]

# Zielvariable: Spielergebnis (Heimsieg=0, Unentschieden=1, Auswärtssieg=2)
le = LabelEncoder()
df['ResultEnc'] = le.fit_transform(df['Result'])
y = df['ResultEnc']

# Split in Trainings- und Testdaten
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42)

# XGBoost-Modell trainieren
model = XGBClassifier(use_label_encoder=False, eval_metric='mlogloss')
model.fit(X_train, y_train)

# Wahrscheinlichkeiten vorhersagen
probs = model.predict_proba(X_test)
probs_df = pd.DataFrame(probs, columns=le.classes_)

# Nutze lokal einfach:
print(probs_df.head())

# Oder in einem Jupyter-Notebook:
from IPython.display import display
display(probs_df.head())