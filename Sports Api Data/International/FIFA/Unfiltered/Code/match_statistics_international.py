#!/usr/bin/env python3
import argparse
import json
import os
import time
from datetime import datetime

import requests
import schedule
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------
# Pfade anpassen
# ---------------------------
INPUT_FILE = r"C:/AI Projekt/KI-Projekt/Sports Api Data/International/FIFA/Unfiltered/Datacollection/fixtures_international.json"
OUTPUT_FILE = r"C:/AI Projekt/KI-Projekt/Sports Api Data/International/FIFA/Unfiltered/Datacollection/match_statistics_international.json"

# ---------------------------
# API-Konfiguration
# ---------------------------
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


def collect_match_statistics(full_load=False):
    print(f"[{datetime.now()}] Starte Abruf (international, full_load={full_load}) ...")

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            fixtures_data = json.load(f).get("response", [])
        print(f"[{datetime.now()}] {len(fixtures_data)} Fixtures geladen.")
    except FileNotFoundError:
        print(f"[{datetime.now()}] Fehler: Fixture-Datei nicht gefunden")
        return

    if full_load:
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)
            print(f"[{datetime.now()}] Alte Statistik-Datei geloescht (Full-Load).")
        existing_stats = []
        existing_ids = set()
    else:
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing_stats = json.load(f).get("response", [])
            print(f"[{datetime.now()}] {len(existing_stats)} bestehende Statistiken geladen.")
        except (FileNotFoundError, json.JSONDecodeError):
            existing_stats = []
            print(f"[{datetime.now()}] Keine bestehende Statistik-Datei gefunden; neue Liste erstellt.")
        existing_ids = {
            stat.get("fixture_id")
            for stat in existing_stats
            if stat.get("fixture_id") is not None
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
        print(f"[{datetime.now()}] Keine neuen Statistiken gefunden.")
        return

    new_stats = []
    with _build_session() as session:
        for idx, match_id in enumerate(to_fetch, 1):
            print(f"[{idx}/{len(to_fetch)}] Abruf fuer Match-ID {match_id}...")
            try:
                stat_json = _api_get_json(session, "/fixtures/statistics", params={"fixture": match_id})
            except Exception as exc:
                print(f"[{idx}/{len(to_fetch)}] Fehler fuer Match-ID {match_id}: {exc}")
                continue

            remove_keys(stat_json, {"logo"})
            stat_json["fixture_id"] = match_id
            new_stats.append(stat_json)
            time.sleep(0.12)

    existing_stats.extend(new_stats)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"response": existing_stats}, f, ensure_ascii=False, indent=4)
    print(f"[{datetime.now()}] {len(new_stats)} neue Statistiken gespeichert.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Match-Statistiken abrufen (international)")
    parser.add_argument(
        "--full-load",
        action="store_true",
        help="Alle beendeten Spiele neu abfragen (alte Daten werden geloescht)",
    )
    args = parser.parse_args()

    collect_match_statistics(full_load=args.full_load)

    schedule.every().tuesday.at("01:00").do(collect_match_statistics, full_load=False)
    schedule.every().wednesday.at("01:00").do(collect_match_statistics, full_load=False)
    schedule.every().thursday.at("01:00").do(collect_match_statistics, full_load=False)

    print("Scheduler laeuft...")
    while True:
        schedule.run_pending()
        time.sleep(60)
