import json
import csv
import os

# Pfade anpassen
input_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/lineups_league_78.json"
output_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/lineups_league_78.csv"

# Mapping zur Anpassung der Teamnamen
team_name_overrides = {
    "Bayern Munich":              "Bayern München",
    "Hertha Berlin":              "Hertha BSC",
    "Borussia Monchengladbach":   "Borussia Mönchengladbach",
    "FC Nurnberg":                "1. FC Nürnberg",
    "Fortuna Dusseldorf":         "Fortuna Düsseldorf",
    "FC Heidenheim":              "1. FC Heidenheim",
    "Vfl Bochum":                 "VfL Bochum",
    "SpVgg Greuther Furth":       "SpVgg Greuther Fürth"
}

# JSON-Datei laden
with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

rows = []

# Die API-Antwort enthält eine Liste unter dem Schlüssel "response"
outer_list = data.get("response", [])
if not isinstance(outer_list, list):
    print("Unerwartetes Format: 'response' ist keine Liste.")
else:
    for outer in outer_list:
        # Fixture-ID aus parameters oder aus fixture_id
        fixture_id = outer.get("parameters", {}).get("fixture") or outer.get("fixture_id")
        # Innere Lineups-Liste
        lineups = outer.get("response", [])
        if not isinstance(lineups, list):
            print(f"Unerwartetes Format in Element: 'response' ist keine Liste: {outer}")
            continue

        for entry in lineups:
            team   = entry.get("team")
            coach  = entry.get("coach")
            formation = entry.get("formation", "")

            # Validierung Team und Coach
            if not team or not coach:
                print("Überspringe Eintrag, fehlende Team- oder Coach-Daten:", entry)
                continue
            if not all(k in team for k in ("id", "name")):
                print("Unvollständige Team-Daten:", team)
                continue
            if not all(k in coach for k in ("id", "name")):
                print("Unvollständige Coach-Daten:", coach)
                continue

            team_id   = team["id"]
            # Ursprünglichen Namen anpassen
            raw_name  = team["name"]
            team_name = team_name_overrides.get(raw_name, raw_name)

            coach_id  = coach["id"]
            coach_name= coach["name"]

            # Startelf
            for player_entry in entry.get("startXI", []):
                player = player_entry.get("player")
                if not player or not all(k in player for k in ("id", "name")):
                    print("Überspringe player_entry, kein gültiger 'player':", player_entry)
                    continue
                rows.append({
                    "fixture_id":   fixture_id,
                    "team_id":      team_id,
                    "team_name":    team_name,
                    "coach_id":     coach_id,
                    "coach_name":   coach_name,
                    "formation":    formation,
                    "player_id":    player["id"],
                    "player_name":  player["name"],
                    "pos":          player.get("pos", ""),
                    "grid":         player.get("grid", ""),
                    "startXI":      True
                })
            # Ersatzspieler
            for sub_entry in entry.get("substitutes", []):
                player = sub_entry.get("player")
                if not player or not all(k in player for k in ("id", "name")):
                    print("Überspringe sub_entry, kein gültiger 'player':", sub_entry)
                    continue
                rows.append({
                    "fixture_id":   fixture_id,
                    "team_id":      team_id,
                    "team_name":    team_name,
                    "coach_id":     coach_id,
                    "coach_name":   coach_name,
                    "formation":    formation,
                    "player_id":    player["id"],
                    "player_name":  player["name"],
                    "pos":          player.get("pos", ""),
                    "grid":         player.get("grid", ""),
                    "startXI":      False
                })

# Schreibe die CSV, falls Daten extrahiert wurden
if rows:
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "fixture_id", "team_id", "team_name", "coach_id", "coach_name",
            "formation", "player_id", "player_name", "pos", "grid", "startXI"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV-Datei wurde erstellt: {output_file}")
else:
    print("Keine Daten extrahiert.")
