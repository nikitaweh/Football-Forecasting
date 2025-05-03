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
        MatchID = outer.get("parameters", {}).get("fixture") or outer.get("MatchID")
        lineups = outer.get("response", [])
        if not isinstance(lineups, list) or len(lineups) < 2:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Weniger als zwei Teams für Match {MatchID}, übersprungen.")
            continue

        # Home/Away per Index
        home_entry = lineups[0]
        away_entry = lineups[1]

        # Hilfsfunktion, um die Zeilen zu bauen
        def add_player_rows(entry, is_start, side):
            team      = entry.get("team", {})
            coach     = entry.get("coach", {})
            formation = entry.get("formation", "")
            if not team or not coach or "id" not in team or "id" not in coach:
                return []

            team_id    = team["id"]
            raw_name   = team["name"]
            team_name  = team_name_overrides.get(raw_name, raw_name)
            coach_id   = coach["id"]
            coach_name = coach["name"]

            # hier entscheiden wir, welche Spalte gefüllt wird
            home_id = team_id if side == "home" else ""
            away_id = team_id if side == "away" else ""

            out = []
            players = entry.get("startXI", []) if is_start else entry.get("substitutes", [])
            for p in players:
                pl = p.get("player", {})
                if not pl or "id" not in pl or "name" not in pl:
                    continue
                out.append({
                    "MatchID":       MatchID,
                    "Home Team ID":  home_id,
                    "Away Team ID":  away_id,
                    "Team Name":     team_name,
                    "Coach ID":      coach_id,
                    "Coach Name":    coach_name,
                    "Formation":     formation,
                    "Player ID":     pl["id"],
                    "Player Name":   pl["name"],
                    "Pos":           p.get("pos", ""),
                    "Grid":          p.get("grid", ""),
                    "StartXI":       is_start
                })
            return out

        # Startelf und Ersatz, jeweils mit Side-Angabe
        rows += add_player_rows(home_entry, True,  "home")
        rows += add_player_rows(away_entry, True,  "away")
        rows += add_player_rows(home_entry, False, "home")
        rows += add_player_rows(away_entry, False, "away")

    # CSV schreiben
    if rows:
        os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "MatchID",
                "Home Team ID",
                "Away Team ID",
                "Team Name",
                "Coach ID",
                "Coach Name",
                "Formation",
                "Player ID",
                "Player Name",
                "Pos",
                "Grid",
                "StartXI"
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] CSV-Datei erstellt: {OUTPUT_CSV}")
    else:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Keine Daten extrahiert.")
        
if __name__ == "__main__":
    # 1) Job direkt beim Start ausführen
    convert_lineups_to_csv()
    
    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(
        convert_lineups_to_csv,
        trigger=CronTrigger(day_of_week="sat,sun,mon", hour="3", minute="0")
    )
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scheduler gestartet – läuft samstags, sonntags & montags um 03:00 Uhr (Europe/Berlin)")
    sched.start()
