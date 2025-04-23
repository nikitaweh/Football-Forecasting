import json
import csv
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# Dateipfade (anpassen)
input_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"
output_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/Stammdaten_78.csv"

# Mapping zur Anpassung der Teamnamen
team_name_overrides = {
    "Bayern Munich": "Bayern München",
    "Hertha Berlin": "Hertha BSC",
    "Borussia Monchengladbach": "Borussia Mönchengladbach",
    "FC Nurnberg": "1. FC Nürnberg",
    "Fortuna Dusseldorf": "Fortuna Düsseldorf",
    "FC Heidenheim": "1. FC Heidenheim",
    "Vfl Bochum": "VfL Bochum",
    "SpVgg Greuther Furth": "SpVgg Greuther Fürth"
}

# Lade die Fixture-Daten
with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

fixtures = data.get("response", [])
rows = []
berlin_tz = ZoneInfo("Europe/Berlin")  # MEZ/MESZ

for fixture in fixtures:
    fixture_data = fixture.get("fixture", {})
    league_data = fixture.get("league", {})
    teams_data = fixture.get("teams", {})
    venue_data = fixture_data.get("venue", {})

    # IDs etc.
    match_id     = fixture_data.get("id")
    league_id    = league_data.get("id")
    season       = league_data.get("season")
    matchday     = league_data.get("round")

    # Datum und UTC‑Zeit aus fixture.date
    date_time_str = fixture_data.get("date", "")
    try:
        dt_utc = datetime.fromisoformat(date_time_str.replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone(berlin_tz)
        date_part = dt_local.date().isoformat()
        time_part = dt_local.time().isoformat(timespec="seconds")
    except Exception:
        date_part = ""
        time_part = ""

    # Teams
    raw_home = teams_data.get("home", {}).get("name", "")
    raw_away = teams_data.get("away", {}).get("name", "")
    # Override der Teamnamen
    home_team = team_name_overrides.get(raw_home, raw_home)
    away_team = team_name_overrides.get(raw_away, raw_away)
    home_team_id = teams_data.get("home", {}).get("id")
    away_team_id = teams_data.get("away", {}).get("id")

    # Stadion & Schiedsrichter
    stadium = venue_data.get("name")
    referee = fixture_data.get("referee")

    rows.append({
        "Match_ID":      match_id,
        "League_ID":     league_id,
        "Season":        season,
        "Matchday":      matchday,
        "Date":          date_part,
        "Time":          time_part,
        "Home Team":     home_team,
        "Away Team":     away_team,
        "Home Team ID":  home_team_id,
        "Away Team ID":  away_team_id,
        "Stadion":       stadium,
        "Referee":       referee
    })

# Definierte Spalten (Header) der Stammdaten-Tabelle
fieldnames = [
    "Match_ID", "League_ID", "Season", "Matchday",
    "Date", "Time", "Home Team", "Away Team",
    "Home Team ID", "Away Team ID", "Stadion", "Referee"
]

# Ausgabeverzeichnis sicherstellen und CSV schreiben
os.makedirs(os.path.dirname(output_file), exist_ok=True)
with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Stammdaten-Tabelle wurde in '{output_file}' gespeichert.")
