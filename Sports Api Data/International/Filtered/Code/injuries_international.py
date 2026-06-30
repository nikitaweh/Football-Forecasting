import json
import csv
import os
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Pfade anpassen
# ---------------------------
INPUT_JSON = r"C:/AI Projekt/KI-Projekt/Sports Api Data/International/Unfiltered/Datacollection/injuries_international.json"
OUTPUT_CSV = r"C:/AI Projekt/KI-Projekt/Sports Api Data/International/Filtered/Datacollection/injuries_international.csv"
NO_DATA_MARKER = "NaN"

# ---------------------------
# Funktion zur Konvertierung
# ---------------------------
def convert_injuries_to_csv():
    # 1) JSON einlesen
    with open(INPUT_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    injuries_by_fixture = data.get('injuries_by_fixture', {})

    # 2) CSV schreiben (ohne leere Fixtures)
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

    fieldnames = [
        'MatchID',
        'Player ID',
        'Player Name',
        'Team ID',
        'Team Name',
        'League ID',
        'League Name',
        'Injury Type',    # aus player.reason
    ]

    with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for fid, entries in injuries_by_fixture.items():
            if not entries:
                continue
            for inj in entries:
                if not isinstance(inj, dict):
                    continue
                if inj.get("no_data") == NO_DATA_MARKER:
                    continue

                player = inj.get('player', {})
                injury_reason = player.get('reason')

                row = {
                    'MatchID':       fid,
                    'Player ID':     player.get('id'),
                    'Player Name':   player.get('name'),
                    'Team ID':       inj.get('team', {}).get('id'),
                    'Team Name':     inj.get('team', {}).get('name', ''),
                    'League ID':     inj.get('league', {}).get('id'),
                    'League Name':   inj.get('league', {}).get('name'),
                    'Injury Type':   injury_reason,
                }
                writer.writerow(row)

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Injuries-CSV erstellt: {OUTPUT_CSV}")


if __name__ == "__main__":
    # 1) Job direkt beim Start ausführen
    convert_injuries_to_csv()

    # 2) Scheduler aufsetzen
    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(
        convert_injuries_to_csv,
        trigger=CronTrigger(day_of_week="tue,wed,thu", hour="3", minute="0")
    )
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scheduler gestartet – läuft dienstags, mittwochs & donnerstags um 03:00 Uhr (Europe/Berlin)")
    sched.start()
