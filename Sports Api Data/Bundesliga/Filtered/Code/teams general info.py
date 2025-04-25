import json
import csv
import os
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Dateipfade anpassen
# ---------------------------
INPUT_FILE_PATH = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/Bundesliga Teams.json"
OUTPUT_FILE_PATH = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/Teams_78.csv"

# ---------------------------
# Funktion: JSON zu CSV konvertieren
# ---------------------------
def convert_teams_to_csv():
    try:
        with open(INPUT_FILE_PATH, "r", encoding="utf-8") as infile:
            data = json.load(infile)
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Fehler beim Laden der JSON: {e}")
        return

    teams = data.get("response", [])
    fieldnames = ["Team Name", "Team ID", "Stadion ID", "Capacity"]

    os.makedirs(os.path.dirname(OUTPUT_FILE_PATH), exist_ok=True)
    try:
        with open(OUTPUT_FILE_PATH, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for entry in teams:
                team_info = entry.get("team", {})
                venue_info = entry.get("venue", {})
                row = {
                    "Team Name": team_info.get("name", ""),
                    "Team ID": team_info.get("id", ""),
                    "Stadion ID": venue_info.get("id", ""),
                    "Capacity": venue_info.get("capacity", ""),
                }
                writer.writerow(row)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] CSV-Datei wurde gespeichert: {OUTPUT_FILE_PATH}")
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Fehler beim Schreiben der CSV: {e}")

# ---------------------------
# Scheduler Setup: jährlich am 1. August um 03:00 Uhr
# ---------------------------
if __name__ == "__main__":
    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(
        convert_teams_to_csv,
        trigger=CronTrigger(month="8", day="1", hour="3", minute="0")
    )
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scheduler gestartet – läuft jährlich am 01.08 um 03:00 Uhr (Europe/Berlin)")
    sched.start()
