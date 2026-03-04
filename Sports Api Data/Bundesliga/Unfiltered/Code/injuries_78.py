#!/usr/bin/env python3
import json
import os
import time
import requests
import argparse
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

def fetch_injuries(full_load=False):
    """
    Full-Load ist deaktiviert.
    Es werden immer neue Fixtures abgerufen und leere Einträge erneut abgefragt.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if full_load:
        print(f"[{now}] Hinweis: --full-load ist deaktiviert. Es wird inkrementell fortgesetzt.")
    print(f"[{now}] Starte fetch_injuries(inkrementell) ...")

    # 1) Fixture-IDs aus Input laden
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    fixture_ids = []
    for item in data.get('response', []):
        # Unterstützt beide Formate: nested dict oder direkt fixture_id
        fid = item.get('fixture', {}).get('id') or item.get('fixture_id')
        if fid is not None:
            fixture_ids.append(fid)
    print(f"[{now}] Gefundene Fixture-IDs insgesamt: {len(fixture_ids)}")

    # 2) Injuries-Store laden
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            existing = json.load(f).get('injuries_by_fixture', {})
    else:
        existing = {}

    # 3) Zu verarbeitende Fixture-IDs bestimmen
    ids_with_data = {
        fid_str
        for fid_str, injuries in existing.items()
        if isinstance(injuries, list) and len(injuries) > 0
    }

    # Skip nur IDs mit bereits vorhandenem Injury-Inhalt.
    # IDs mit leerer Liste werden erneut abgefragt.
    new_ids = [fid for fid in fixture_ids if str(fid) not in ids_with_data]
    print(f"[{now}] Zu verarbeitende Fixture-IDs: {len(new_ids)}")

    # 4) Injuries für jede ID abrufen
    refreshed = 0
    refreshed_with_data = 0
    for fid in new_ids:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] Hole Injuries für Fixture {fid} …")
        try:
            resp = requests.get(API_URL, params={'fixture': fid}, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            injuries_list = resp.json().get('response', [])
        except Exception as e:
            print(f"→ Fehler bei Fixture {fid}: {e}")
            injuries_list = []

        # Unerwünschte Felder entfernen
        for inj in injuries_list:
            if isinstance(inj.get('player'), dict):
                inj['player'].pop('photo', None)
            if isinstance(inj.get('team'), dict):
                inj['team'].pop('logo', None)
            if isinstance(inj.get('league'), dict):
                inj['league'].pop('logo', None)
                inj['league'].pop('flag', None)

        existing[str(fid)] = injuries_list
        refreshed += 1
        if injuries_list:
            refreshed_with_data += 1

    # 5) Speichern
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({'injuries_by_fixture': existing}, f, ensure_ascii=False, indent=2)

    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Injuries gespeichert in: {OUTPUT_FILE} "
        f"(aktualisiert: {refreshed}, mit Daten: {refreshed_with_data})"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Injury-Daten abrufen")
    parser.add_argument(
        '--full-load',
        action='store_true',
        help='Deaktiviert: wird ignoriert, es laeuft immer inkrementell'
    )
    args = parser.parse_args()

    # Einmaliger Erstaufruf (immer inkrementell)
    fetch_injuries(full_load=args.full_load)

    # Scheduler für inkrementelle Updates (ohne Full-Load)
    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(
        fetch_injuries,
        trigger=CronTrigger(day_of_week="sat,sun,mon", hour="1", minute="0")
    )
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scheduler gestartet für sa, so & mo 01:00 Uhr (incremental)")
    sched.start()
