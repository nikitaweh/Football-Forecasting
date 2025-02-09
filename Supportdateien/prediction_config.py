import pandas as pd
import math

# CSV-Dateien laden
current_season_data = pd.read_csv('c:/AI Projekt/Webscraping/Hauptdatein/Bundesliga_odds_results.csv')
head_to_head_data = pd.read_csv('c:/AI Projekt/Webscraping/Hauptdatein/team_stats.csv')
historical_data = pd.read_csv('c:/AI Projekt/Webscraping/Hauptdatein/match_results.csv')

# Debugging aktiviert
DEBUG = True

# Saisondaten berechnen: Durchschnittliche Tore pro Spiel und kassierte Tore
def calculate_current_season_averages(team, home=True):
    if home:
        # Durchschnittliche Tore pro Heimspiel und kassierte Tore berechnen
        avg_goals = current_season_data[current_season_data['home_team'] == team]['home_score'].mean()
        avg_conceded = current_season_data[current_season_data['home_team'] == team]['away_score'].mean()
    else:
        # Durchschnittliche Tore pro Auswärtsspiel und kassierte Tore berechnen
        avg_goals = current_season_data[current_season_data['away_team'] == team]['away_score'].mean()
        avg_conceded = current_season_data[current_season_data['away_team'] == team]['home_score'].mean()
    return avg_goals, avg_conceded

# Berechnung der Tordifferenz basierend auf Saisondaten
def calculate_goal_difference(home_team, away_team):
    home_avg_goals, home_avg_conceded = calculate_current_season_averages(home_team, home=True)
    away_avg_goals, away_avg_conceded = calculate_current_season_averages(away_team, home=False)

    # Berücksichtigung sowohl erzielter als auch kassierter Tore
    home_goal_potential = home_avg_goals - away_avg_conceded  # Tore des Heimteams gegen das Auswärtsteam
    away_goal_potential = away_avg_goals - home_avg_conceded  # Tore des Auswärtsteams gegen das Heimteam
    
    goal_difference = home_goal_potential - away_goal_potential

    if DEBUG:
        print(f"[DEBUG] home_goal_potential: {home_goal_potential}, away_goal_potential: {away_goal_potential}, goal_difference: {goal_difference}")
    
    return home_goal_potential, away_goal_potential, goal_difference

# Head-to-Head-Daten laden und berechnen
def calculate_head_to_head_rates(home_team, away_team):
    h2h_data = head_to_head_data[(head_to_head_data['Home Team'] == home_team) & (head_to_head_data['Away Team'] == away_team)]
    if not h2h_data.empty:
        home_win_rate = h2h_data['Home Win Rate'].iloc[0]
        draw_rate = h2h_data['Draw Rate'].iloc[0]
        away_win_rate = h2h_data['Away Win Rate'].iloc[0]
    else:
        home_win_rate = draw_rate = away_win_rate = 0.33  # Annahme bei fehlenden Daten
    return home_win_rate, draw_rate, away_win_rate

# Historische Basiswahrscheinlichkeiten für `dynamic_min` und `dynamic_max`
def calculate_historical_baseline(team):
    global historical_data
    # Suche nach Heim- und Auswärtsspielen
    home_team_data = historical_data[historical_data['Home Team'] == team]
    away_team_data = historical_data[historical_data['Away Team'] == team]

    # Gewinnraten berechnen
    home_win_rate = (
        home_team_data[home_team_data['Result'] == 'Win'].shape[0] / home_team_data.shape[0]
        if not home_team_data.empty else 0)
    away_win_rate = (
        away_team_data[away_team_data['Result'] == 'Win'].shape[0] / away_team_data.shape[0]
        if not away_team_data.empty else 0)
    # Unentschiedenraten berechnen
    home_draw_rate = (
        home_team_data[home_team_data['Result'] == 'Draw'].shape[0] / home_team_data.shape[0]
        if not home_team_data.empty else 0)
    away_draw_rate = (
        away_team_data[away_team_data['Result'] == 'Draw'].shape[0] / away_team_data.shape[0]
        if not away_team_data.empty else 0)

    # Verlustraten berechnen
    home_lose_rate = (
        home_team_data[home_team_data['Result'] == 'Loss'].shape[0] / home_team_data.shape[0]
        if not home_team_data.empty else 0)
    away_lose_rate = (
        away_team_data[away_team_data['Result'] == 'Loss'].shape[0] / away_team_data.shape[0]
        if not away_team_data.empty else 0)

    # Durchschnittswerte berechnen
    win_rate = (home_win_rate + away_win_rate) / 2
    draw_rate = (home_draw_rate + away_draw_rate) / 2
    lose_rate = (home_lose_rate + away_lose_rate) / 2

    return win_rate, draw_rate, lose_rate

# Aktualisierte dynamische Min- und Max-Berechnung
def calculate_dynamic_limits(home_team, away_team):
    # Historische Baseline-Werte holen
    home_baseline_win, _, home_baseline_lose = calculate_historical_baseline(home_team)
    away_baseline_win, _, away_baseline_lose = calculate_historical_baseline(away_team)

    # Dynamische Grenzen auf Basis der Baseline-Werte berechnen
    dynamic_min = min(home_baseline_lose, away_baseline_lose) * 0.5  # 50% der kleineren Verlustquote
    dynamic_max = max(home_baseline_win, away_baseline_win) * 1.5  # 150% der größeren Gewinnquote

        # Sicherstellen, dass dynamische Grenzen sinnvoll bleiben
    dynamic_min = max(0.05, dynamic_min)  # Mindestens 5% für realistische Dynamik
    dynamic_max = min(0.90, dynamic_max)   # Maximal 90%, um Extrema zu vermeiden
    
    if DEBUG:
        print(f"[DEBUG] dynamic_min: {dynamic_min}, dynamic_max: {dynamic_max}")
    
    return dynamic_min, dynamic_max

def calculate_dynamic_win_draw_lose_probability(home_team, away_team):
    # Saison- und Head-to-Head-Raten berechnen
    home_avg_goals, away_avg_goals, goal_difference = calculate_goal_difference(home_team, away_team)
    h2h_home_win_rate, h2h_draw_rate, h2h_away_win_rate = calculate_head_to_head_rates(home_team, away_team)
    base_home_win_rate, base_draw_rate, base_away_win_rate = calculate_historical_baseline(home_team)

    # Dynamische Grenzen berechnen
    dynamic_min, dynamic_max = calculate_dynamic_limits(home_team, away_team)

    # Basiswahrscheinlichkeiten setzen
    base_win_prob = max(dynamic_min, base_home_win_rate)
    base_lose_prob = max(dynamic_min, base_away_win_rate)
    base_draw_prob = max(dynamic_min, base_draw_rate)

    # Gewichtsfaktorberechnung
    weight_factor = min(1.0, math.exp(goal_difference / 2))  # Exponentiell steigender Wert

    # Anpassung der Wahrscheinlichkeiten
    adjusted_win_prob = base_win_prob * weight_factor + h2h_home_win_rate * (1 - weight_factor)
    adjusted_draw_prob = base_draw_prob * weight_factor + h2h_draw_rate * (1 - weight_factor)
    adjusted_lose_prob = base_lose_prob * weight_factor + h2h_away_win_rate * (1 - weight_factor)

    # Dynamische Grenzen anwenden
    adjusted_win_prob = max(dynamic_min, min(adjusted_win_prob, dynamic_max))
    adjusted_draw_prob = max(dynamic_min, min(adjusted_draw_prob, dynamic_max))
    adjusted_lose_prob = max(dynamic_min, min(adjusted_lose_prob, dynamic_max))

    # Wahrscheinlichkeiten überprüfen und korrigieren
    if adjusted_lose_prob <= 0:
        adjusted_lose_prob = dynamic_min  # Minimalwert setzen, falls Verlustwahrscheinlichkeit 0 ist

    # Neu-Normalisierung auf 100%
    total_prob = adjusted_win_prob + adjusted_draw_prob + adjusted_lose_prob
    if total_prob > 0:
        adjusted_win_prob /= total_prob
        adjusted_draw_prob /= total_prob
        adjusted_lose_prob /= total_prob

    # Debugging Informationen
    if DEBUG:
        print(f"[DEBUG] home_avg_goals: {home_avg_goals}, away_avg_goals: {away_avg_goals}, goal_difference: {goal_difference}")
        print(f"[DEBUG] dynamic_min: {dynamic_min}, dynamic_max: {dynamic_max}")
        print(f"[DEBUG] base_win_prob: {base_win_prob}, base_lose_prob: {base_lose_prob}, base_draw_prob: {base_draw_prob}")
        print(f"[DEBUG] adjusted_win_prob: {adjusted_win_prob}, adjusted_draw_prob: {adjusted_draw_prob}, adjusted_lose_prob: {adjusted_lose_prob}")

    return adjusted_win_prob, adjusted_draw_prob, adjusted_lose_prob

# Beispiel-Anwendung
home_team = "BVB"
away_team = "FCB"
win_prob, draw_prob, lose_prob = calculate_dynamic_win_draw_lose_probability(home_team, away_team)

print(f"Die Gewinnwahrscheinlichkeit für {home_team} gegen {away_team} beträgt {win_prob * 100:.2f}%")
print(f"Die Unentschiedenwahrscheinlichkeit beträgt {draw_prob * 100:.2f}%")
print(f"Die Niederlagenwahrscheinlichkeit beträgt {lose_prob * 100:.2f}%")

