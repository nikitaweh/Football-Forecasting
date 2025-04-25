import json
import csv
import os
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Pfade anpassen
# ---------------------------
INPUT_JSON = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/lineups_league_78.json"
OUTPUT_CSV = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/lineups_league_78.csv"

# ---------------------------
# Teamnamen-Overrides
# ---------------------------
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

# ---------------------------
# Funktion: JSON zu CSV konvertieren
# ---------------------------
def convert_lineups_to_csv():
    # JSON laden
    try:
        with open(INPUT_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Fehler beim Laden der JSON: {e}")
        return

    rows = []
    outer_list = data.get("response", [])
    if not isinstance(outer_list, list):
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Unerwartetes Format: 'response' ist keine Liste.")
        return

    for outer in outer_list:
        fixture_id = outer.get("parameters", {}).get("fixture") or outer.get("fixture_id")
        lineups = outer.get("response", [])
        if not isinstance(lineups, list):
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Unerwartetes Format in Element: 'response' ist keine Liste: {outer}")
            continue

        for entry in lineups:
            team  = entry.get("team")
            coach = entry.get("coach")
            formation = entry.get("formation", "")
            if not team or not coach:
                continue
            if not all(k in team for k in ("id","name")) or not all(k in coach for k in ("id","name")):
                continue

            team_id   = team["id"]
            raw_name  = team["name"]
            team_name = team_name_overrides.get(raw_name, raw_name)
            coach_id  = coach["id"]
            coach_name= coach["name"]

            # Startelf
            for player_entry in entry.get("startXI", []):
                player = player_entry.get("player")
                if not player or not all(k in player for k in ("id","name")):
                    continue
                rows.append({
                    "fixture_id": fixture_id,
                    "team_id":    team_id,
                    "team_name":  team_name,
                    "coach_id":   coach_id,
                    "coach_name": coach_name,
                    "formation":  formation,
                    "player_id":  player["id"],
                    "player_name":player["name"],
                    "pos":         player.get("pos", ""),
                    "grid":        player.get("grid", ""),
                    "startXI":     True
                })
            # Ersatzspieler
            for sub_entry in entry.get("substitutes", []):
                player = sub_entry.get("player")
                if not player or not all(k in player for k in ("id","name")):
                    continue
                rows.append({
                    "fixture_id": fixture_id,
                    "team_id":    team_id,
                    "team_name":  team_name,
                    "coach_id":   coach_id,
                    "coach_name": coach_name,
                    "formation":  formation,
                    "player_id":  player["id"],
                    "player_name":player["name"],
                    "pos":         player.get("pos", ""),
                    "grid":        player.get("grid", ""),
                    "startXI":     False
                })

    if rows:
        os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["fixture_id","team_id","team_name","coach_id","coach_name","formation",
                          "player_id","player_name","pos","grid","startXI"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] CSV-Datei erstellt: {OUTPUT_CSV}")
    else:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Keine Daten extrahiert.")

if __name__ == "__main__":
    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(
        convert_lineups_to_csv,
        trigger=CronTrigger(day_of_week="sat,sun,mon", hour="3", minute="0")
    )
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scheduler gestartet – läuft samstags, sonntags & montags um 03:00 Uhr (Europe/Berlin)")
    sched.start()
