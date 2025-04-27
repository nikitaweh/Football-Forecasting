import json
import csv
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Dateipfade (anpassen)
# ---------------------------
INPUT_FILE = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"
OUTPUT_FILE = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/Stammdaten_78.csv"

# ---------------------------
# Mapping zur Anpassung der Teamnamen
# ---------------------------
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

# ---------------------------
# Funktion zur Konvertierung der Stammdaten
# ---------------------------
def convert_stammdaten_to_csv():
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Fehler beim Laden der JSON: {e}")
        return

    fixtures = data.get("response", [])
    rows = []
    berlin_tz = ZoneInfo("Europe/Berlin")

    for fixture in fixtures:
        fixture_data = fixture.get("fixture", {})
        league_data = fixture.get("league", {})
        teams_data = fixture.get("teams", {})
        venue_data = fixture_data.get("venue", {})

        MatchID     = fixture_data.get("id")
        league_id   = league_data.get("id")
        season      = league_data.get("season")
        matchday    = league_data.get("round")

        date_time_str = fixture_data.get("date", "")
        try:
            dt_utc    = datetime.fromisoformat(date_time_str.replace("Z", "+00:00"))
            dt_local  = dt_utc.astimezone(berlin_tz)
            date_part = dt_local.date().isoformat()
            time_part = dt_local.time().isoformat(timespec="seconds")
        except Exception:
            date_part = ""
            time_part = ""

        raw_home      = teams_data.get("home", {}).get("name", "")
        raw_away      = teams_data.get("away", {}).get("name", "")
        home_team     = team_name_overrides.get(raw_home, raw_home)
        away_team     = team_name_overrides.get(raw_away, raw_away)
        home_team_id  = teams_data.get("home", {}).get("id")
        away_team_id  = teams_data.get("away", {}).get("id")

        stadium = venue_data.get("name")
        referee = fixture_data.get("referee")

        rows.append({
            "MatchID":        MatchID,
            "League_ID":      league_id,
            "Season":         season,
            "Matchday":       matchday,
            "Date":           date_part,
            "Time":           time_part,
            "Home Team":      home_team,
            "Away Team":      away_team,
            "Home Team ID":   home_team_id,
            "Away Team ID":   away_team_id,
            "Stadion":        stadium,
            "Referee":        referee
        })

    fieldnames = [
        "MatchID", "League_ID", "Season", "Matchday",
        "Date", "Time", "Home Team", "Away Team",
        "Home Team ID", "Away Team ID", "Stadion", "Referee"
    ]
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    try:
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Stammdaten-CSV gespeichert: {OUTPUT_FILE}")
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Fehler beim Schreiben der CSV: {e}")

# ---------------------------
# Scheduler Setup
# ---------------------------
if __name__ == "__main__":
    # 1) Direkt beim Start einmal ausführen
    convert_stammdaten_to_csv()

    # 2) Scheduler starten
    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(
        convert_stammdaten_to_csv,
        trigger=CronTrigger(day_of_week="sat,sun,mon", hour="2", minute="0")
    )
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scheduler gestartet – läuft samstags, sonntags & montags um 02:00 Uhr (Europe/Berlin)")
    sched.start()
