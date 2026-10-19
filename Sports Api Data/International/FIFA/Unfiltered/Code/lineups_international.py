#!/usr/bin/env python3
import argparse
import json
import os
import time
from datetime import datetime

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

FIXTURES_FILE_PATH = r"C:/AI Projekt/KI-Projekt/Sports Api Data/International/FIFA/Unfiltered/Datacollection/fixtures_international.json"
OUTPUT_FILE_PATH = r"C:/AI Projekt/KI-Projekt/Sports Api Data/International/FIFA/Unfiltered/Datacollection/lineups_international.json"

API_HOST = "v3.football.api-sports.io"
BASE_URL = f"https://{API_HOST}"
HEADERS = {
    "x-rapidapi-host": API_HOST,
    "x-rapidapi-key": "5fa2372f2bfcbedb8ef7b85c86f0a27a",
}
REQUEST_CONNECT_TIMEOUT = 4
REQUEST_READ_TIMEOUT = 12
REQUEST_RETRIES = 2
REQUEST_BACKOFF_SECONDS = 1.0

# Beendete Spielstatus bei internationalen Spielen (inkl. Verlaengerung/Elfmeterschiessen)
FINISHED_STATUSES = {"FT", "AET", "PEN"}


def remove_keys(obj, keys_to_remove):
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if key in keys_to_remove:
                del obj[key]
            else:
                remove_keys(obj[key], keys_to_remove)
    elif isinstance(obj, list):
        for item in obj:
            remove_keys(item, keys_to_remove)


def _build_session():
    retry = Retry(
        total=REQUEST_RETRIES,
        connect=REQUEST_RETRIES,
        read=REQUEST_RETRIES,
        status=REQUEST_RETRIES,
        backoff_factor=REQUEST_BACKOFF_SECONDS,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)

    session = requests.Session()
    session.headers.update(HEADERS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _api_get_json(session, endpoint, params=None):
    url = f"{BASE_URL}{endpoint}"
    response = session.get(url, params=params, timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT))
    response.raise_for_status()
    return response.json()


def collect_lineups(full_load=False):
    print(f"[{datetime.now()}] Starte Abruf der Lineup-Daten (international, full_load={full_load}) ...")

    try:
        with open(FIXTURES_FILE_PATH, "r", encoding="utf-8") as f:
            fixtures_data = json.load(f).get("response", [])
        print(f"[{datetime.now()}] {len(fixtures_data)} Fixtures geladen.")
    except FileNotFoundError:
        print(f"[{datetime.now()}] FEHLER: Fixture-Datei nicht gefunden.")
        return

    if full_load:
        if os.path.exists(OUTPUT_FILE_PATH):
            os.remove(OUTPUT_FILE_PATH)
            print(f"[{datetime.now()}] Alte Lineup-Datei geloescht (Full-Load).")
        existing_lineups = []
        existing_ids = set()
    else:
        try:
            with open(OUTPUT_FILE_PATH, "r", encoding="utf-8") as f:
                existing_lineups = json.load(f).get("response", [])
            print(f"[{datetime.now()}] {len(existing_lineups)} bestehende Lineups geladen.")
        except (FileNotFoundError, json.JSONDecodeError):
            existing_lineups = []
            print(f"[{datetime.now()}] Keine bestehende Lineup-Datei gefunden; neue Liste erstellt.")
        existing_ids = {
            ln.get("fixture_id")
            for ln in existing_lineups
            if ln.get("fixture_id") is not None
        }

    to_fetch = []
    for fx in fixtures_data:
        fixture = fx.get("fixture", {})
        status_short = fixture.get("status", {}).get("short")
        match_id = fixture.get("id")

        if status_short not in FINISHED_STATUSES or match_id in existing_ids:
            continue
        to_fetch.append(match_id)

    print(f"[{datetime.now()}] {len(to_fetch)} abgeschlossene Matches zum Abruf gefunden.")

    if not to_fetch:
        print(f"[{datetime.now()}] Keine neuen Lineups gefunden.")
        return

    new_lineups = []
    refreshed_with_data = 0
    with _build_session() as session:
        for idx, match_id in enumerate(to_fetch, 1):
            print(f"[{idx}/{len(to_fetch)}] Abruf fuer Match-ID {match_id}...")
            try:
                lineup_data = _api_get_json(session, "/fixtures/lineups", params={"fixture": match_id})
            except Exception as exc:
                print(f"[{idx}/{len(to_fetch)}] Fehler fuer Match-ID {match_id}: {exc}")
                continue

            remove_keys(lineup_data, {"logo", "photo"})
            lineup_data["fixture_id"] = match_id
            new_lineups.append(lineup_data)

            if isinstance(lineup_data.get("response"), list) and len(lineup_data.get("response")) > 0:
                refreshed_with_data += 1
            time.sleep(0.12)

    existing_lineups.extend(new_lineups)
    os.makedirs(os.path.dirname(OUTPUT_FILE_PATH), exist_ok=True)
    with open(OUTPUT_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump({"response": existing_lineups}, f, ensure_ascii=False, indent=4)

    print(
        f"[{datetime.now()}] {len(new_lineups)} neue Lineup-Datensaetze "
        f"({refreshed_with_data} mit Lineups) gespeichert in {OUTPUT_FILE_PATH}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lineup-Daten abrufen und planen (international)")
    parser.add_argument(
        "--full-load",
        action="store_true",
        help="Alle beendeten Spiele neu abfragen (alte Daten werden geloescht)",
    )
    args = parser.parse_args()

    collect_lineups(full_load=args.full_load)

    sched = BlockingScheduler(timezone="Europe/Berlin")
    trigger = CronTrigger(day_of_week="tue,wed,thu", hour="0", minute="0")
    sched.add_job(collect_lineups, trigger=trigger)
    print(f"[{datetime.now()}] Scheduler gestartet: Di/Mi/Do 00:00 (inkrementell)")
    sched.start()
