import json
import csv
import os

# ----------------------------
# Pfade zu den Input- und Output-Dateien
# ----------------------------
fixtures_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"
stats_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/match_statistics_league_78.json"
output_csv = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/match_statistics_filtered_78.csv"

# ----------------------------
# Hilfsfunktionen
# ----------------------------
def parse_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except:
        return None

def parse_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except:
        return None

def parse_percentage(value):
    if isinstance(value, str) and '%' in value:
        try:
            return int(value.replace('%', '').strip())
        except:
            return None
    return None

def get_stat_value(stat_list, stat_type):
    """
    Sucht in stat_list (Liste von Dicts mit 'type' und 'value') nach stat_type
    und gibt den 'value' zurück. Falls nicht vorhanden, None.
    """
    for item in stat_list:
        if item.get("type") == stat_type:
            return item.get("value")
    return None

# ----------------------------
# 1) fixtures_league_78.json einlesen
#    -> Match-Infos + Tore
# ----------------------------
with open(fixtures_file, "r", encoding="utf-8") as f:
    fixtures_data = json.load(f)

fixtures_response = fixtures_data.get("response", [])

# fixtures_dict[fixture_id] = {
#   "home_id": ...,
#   "away_id": ...,
#   "home_goals": ...,
#   "away_goals": ...
# }
fixtures_dict = {}
for fx in fixtures_response:
    fixture_info = fx.get("fixture", {})
    teams_info   = fx.get("teams", {})
    goals_info   = fx.get("goals", {})

    fid         = fixture_info.get("id")
    home_id     = teams_info.get("home", {}).get("id")
    away_id     = teams_info.get("away", {}).get("id")
    home_goals  = goals_info.get("home")
    away_goals  = goals_info.get("away")

    if fid is not None:
        fixtures_dict[fid] = {
            "home_id": home_id,
            "away_id": away_id,
            "home_goals": home_goals,
            "away_goals": away_goals
        }

# ----------------------------
# 2) match_statistics_league_78.json einlesen
#    -> Für jede fixture_id zwei Blöcke: home und away
# ----------------------------
with open(stats_file, "r", encoding="utf-8") as f:
    stats_data = json.load(f)

stats_response = stats_data.get("response", [])

# stats_dict[fixture_id] = {
#   "home": { ...Statistik... },
#   "away": { ...Statistik... }
# }
stats_dict = {}

for item in stats_response:
    fixture_id = item.get("fixture_id")
    stat_list  = item.get("response", [])  # meist 2 Einträge: [ {team:..., statistics: [...]}, {team:..., statistics: [...]} ]

    if fixture_id not in fixtures_dict:
        continue

    home_id = fixtures_dict[fixture_id]["home_id"]
    away_id = fixtures_dict[fixture_id]["away_id"]

    stats_dict[fixture_id] = {
        "home": {},
        "away": {}
    }

    for team_stats in stat_list:
        team_id = team_stats.get("team", {}).get("id")
        stat_items = team_stats.get("statistics", [])

        if team_id == home_id:
            side = "home"
        elif team_id == away_id:
            side = "away"
        else:
            continue

        # Shots on Goal -> Shots on Target
        # Hole Werte aus 'statistics'
        # Shots on Goal -> Shots on Target
        shots_on_goal_val = parse_int(get_stat_value(stat_items, "Shots on Goal"))
        shots_off_goal_val = parse_int(get_stat_value(stat_items, "Shots off Goal"))
        total_shots = None
        if shots_on_goal_val is not None and shots_off_goal_val is not None:
            total_shots = shots_on_goal_val + shots_off_goal_val
        elif shots_on_goal_val is not None:
            total_shots = shots_on_goal_val
        elif shots_off_goal_val is not None:
            total_shots = shots_off_goal_val

        # Ball Possession (z. B. '53%')
        possession_str = get_stat_value(stat_items, "Ball Possession")
        possession_pct = parse_percentage(possession_str)  # z. B. 53 aus "53%"

        # Fouls, Yellow Cards, Red Cards, Offsides, Corners, Passes, Pass Accuracy
        fouls_val = parse_int(get_stat_value(stat_items, "Fouls"))
        yellow_val = parse_int(get_stat_value(stat_items, "Yellow Cards"))
        red_val = parse_int(get_stat_value(stat_items, "Red Cards"))
        offsides_val = parse_int(get_stat_value(stat_items, "Offsides"))
        corners_val = parse_int(get_stat_value(stat_items, "Corner Kicks"))
        passes_val = parse_int(get_stat_value(stat_items, "Total passes"))
        pass_accuracy_str = get_stat_value(stat_items, "Passes %")
        pass_accuracy_val = parse_percentage(pass_accuracy_str)
        
        # Expected Goals: Schlüssel "expected_goals" verwenden
        xg_str = get_stat_value(stat_items, "expected_goals")
        xg_val = parse_float(xg_str)

        stats_dict[fixture_id][side] = {
            "shots_on_target": shots_on_goal_val,
            "shots": total_shots,
            "possession": possession_pct,
            "fouls": fouls_val,
            "yellow": yellow_val,
            "red": red_val,
            "offsides": offsides_val,
            "corners": corners_val,
            "passes": passes_val,
            "pass_accuracy": pass_accuracy_val,
            "xg": xg_val
        }

# ----------------------------
# 3) CSV-Datei erstellen
# ----------------------------

fieldnames = [
    "MatchID",
    "Home Goals", "Away Goals",
    "Home Possession", "Away Possession",
    "Home Shots", "Away Shots",
    "Home Shots on Target", "Away Shots on Target",
    "Home Passes", "Away Passes",
    "Home Pass Accuracy", "Away Pass Accuracy",
    "Home Fouls", "Away Fouls",
    "Home Yellow Card", "Away Yellow Card",
    "Home Red Card", "Away Red Card",
    "Home Offsides", "Away Offsides",
    "Home Corners", "Away Corners",
    "Expected Goals (xG) Home", "Expected Goals (xG) Away"
]

rows = []

for fid, fx_data in fixtures_dict.items():
    if fid not in stats_dict:
        continue

    home_stats = stats_dict[fid]["home"]
    away_stats = stats_dict[fid]["away"]

    home_goals = fx_data["home_goals"]
    away_goals = fx_data["away_goals"]

    row = {
        "MatchID": fid,
        "Home Goals": home_goals,
        "Away Goals": away_goals,
        "Home Possession": home_stats.get("possession"),
        "Away Possession": away_stats.get("possession"),
        "Home Shots": home_stats.get("shots"),
        "Away Shots": away_stats.get("shots"),
        "Home Shots on Target": home_stats.get("shots_on_target"),
        "Away Shots on Target": away_stats.get("shots_on_target"),
        "Home Passes": home_stats.get("passes"),
        "Away Passes": away_stats.get("passes"),
        "Home Pass Accuracy": home_stats.get("pass_accuracy"),
        "Away Pass Accuracy": away_stats.get("pass_accuracy"),
        "Home Fouls": home_stats.get("fouls"),
        "Away Fouls": away_stats.get("fouls"),
        "Home Yellow Card": home_stats.get("yellow"),
        "Away Yellow Card": away_stats.get("yellow"),
        "Home Red Card": home_stats.get("red"),
        "Away Red Card": away_stats.get("red"),
        "Home Offsides": home_stats.get("offsides"),
        "Away Offsides": away_stats.get("offsides"),
        "Home Corners": home_stats.get("corners"),
        "Away Corners": away_stats.get("corners"),
        "Expected Goals (xG) Home": home_stats.get("xg"),
        "Expected Goals (xG) Away": away_stats.get("xg")
    }
    rows.append(row)

os.makedirs(os.path.dirname(output_csv), exist_ok=True)
with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Match-Statistiken als CSV in '{output_csv}' gespeichert.")
