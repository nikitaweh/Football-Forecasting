import json
import os
import time
import requests
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Pfade anpassen
# ---------------------------
INPUT_FILE  = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"
OUTPUT_FILE = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/injuries_league_78.json"

# ---------------------------
# API-Konfiguration
# ---------------------------
API_URL = "https://v3.football.api-sports.io/injuries"
API_KEY = "5fa2372f2bfcbedb8ef7b85c86f0a27a"
HEADERS = {
    'x-apisports-key': API_KEY
}
RATE_LIMIT = 1  # Sekunden Pause zwischen den Anfragen

def fetch_injuries():
    # 1) Fixture-IDs aus Datei laden
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fixture_ids = []
    for item in data.get('response', []):
        fid = None
        if isinstance(item.get('fixture'), dict):
            fid = item['fixture'].get('id')
        if fid is None:
            fid = item.get('fixture_id')
        if fid is not None:
            fixture_ids.append(fid)

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Gefundene Fixture-IDs: {len(fixture_ids)}")

    # 2) Injuries pro Fixture abfragen und unerwünschte Felder entfernen
    injuries_by_fixture = {}
    for fid in fixture_ids:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Hole Injuries für Fixture {fid} …")
        params = {'fixture': fid}
        try:
            resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            body = resp.json()
            injuries_list = body.get('response', [])
        except Exception as e:
            print(f"→ Fehler bei Fixture {fid}: {e}")
            injuries_list = []

        # Entferne photo, logo, flag aus jedem Injury-Eintrag
        for inj in injuries_list:
            if isinstance(inj.get('player'), dict):
                inj['player'].pop('photo', None)
            if isinstance(inj.get('team'), dict):
                inj['team'].pop('logo', None)
            if isinstance(inj.get('league'), dict):
                inj['league'].pop('logo', None)
                inj['league'].pop('flag', None)

        injuries_by_fixture[str(fid)] = injuries_list
        time.sleep(RATE_LIMIT)

    # 3) Speichern als JSON
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({'injuries_by_fixture': injuries_by_fixture}, f, ensure_ascii=False, indent=2)

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Injuries gespeichert in: {OUTPUT_FILE}")


if __name__ == "__main__":
    # Scheduler initialisieren
    sched = BlockingScheduler(timezone="Europe/Berlin")
    # CronTrigger: Samstag, Sonntag und Montag um 01:00 Uhr
    sched.add_job(
        fetch_injuries,
        trigger=CronTrigger(day_of_week="sat,sun,mon", hour="1", minute="0")
    )
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scheduler gestartet – läuft samstags, sonntags & montags um 01:00 Uhr (Europe/Berlin)")
    sched.start()
