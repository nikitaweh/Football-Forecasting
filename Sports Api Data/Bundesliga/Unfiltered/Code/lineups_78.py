#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

FIXTURES_FILE_PATH = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"
OUTPUT_FILE_PATH = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/lineups_league_78.json"

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
    if full_load:
        print(f"[{datetime.now()}] Hinweis: --full-load ist deaktiviert. Es wird inkrementell fortgesetzt.")
    print(f"[{datetime.now()}] Starte Abruf der Lineup-Daten (inkrementell) ...")

    try:
        with open(FIXTURES_FILE_PATH, "r", encoding="utf-8") as f:
            fixtures_data = json.load(f).get("response", [])
    except FileNotFoundError:
        print(f"[{datetime.now()}] FEHLER: Fixture-Datei nicht gefunden.")
        return

    fixture_ids = [fx.get("fixture", {}).get("id") for fx in fixtures_data if fx.get("fixture", {}).get("id")]
    print(f"[{datetime.now()}] Gefundene Fixture-IDs: {len(fixture_ids)}")

    try:
        with open(OUTPUT_FILE_PATH, "r", encoding="utf-8") as f:
            existing_lineups = json.load(f).get("response", [])
    except (FileNotFoundError, json.JSONDecodeError):
        existing_lineups = []

    existing_by_id = {
        ln.get("fixture_id"): ln
        for ln in existing_lineups
        if ln.get("fixture_id") is not None
    }
    ids_with_data = {
        fid
        for fid, ln in existing_by_id.items()
        if isinstance(ln.get("response"), list) and len(ln.get("response")) > 0
    }

    refreshed = 0
    refreshed_with_data = 0
    with _build_session() as session:
        for fid in fixture_ids:
            if fid in ids_with_data:
                continue

            try:
                lineup_data = _api_get_json(session, "/fixtures/lineups", params={"fixture": fid})
            except Exception as exc:
                print(f"[{datetime.now()}] Fehler bei Fixture {fid}: {exc}")
                lineup_data = {"response": []}

            remove_keys(lineup_data, {"logo", "photo"})
            lineup_data["fixture_id"] = fid
            existing_by_id[fid] = lineup_data
            refreshed += 1

            if isinstance(lineup_data.get("response"), list) and len(lineup_data.get("response")) > 0:
                refreshed_with_data += 1

    existing_lineups = [existing_by_id[fid] for fid in fixture_ids if fid in existing_by_id]
    os.makedirs(os.path.dirname(OUTPUT_FILE_PATH), exist_ok=True)
    with open(OUTPUT_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump({"response": existing_lineups}, f, ensure_ascii=False, indent=4)

    print(
        f"[{datetime.now()}] Aktualisiert {refreshed} Fixture-Datensaetze "
        f"({refreshed_with_data} mit Lineups) in {OUTPUT_FILE_PATH}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lineup-Daten abrufen und planen")
    parser.add_argument(
        "--full-load",
        action="store_true",
        help="Deaktiviert: wird ignoriert, es laeuft immer inkrementell",
    )
    args = parser.parse_args()

    collect_lineups(full_load=args.full_load)

    sched = BlockingScheduler(timezone="Europe/Berlin")
    trigger = CronTrigger(day_of_week="sat,sun,mon", hour="0", minute="0")
    sched.add_job(collect_lineups, trigger=trigger)
    print(f"[{datetime.now()}] Scheduler gestartet: Sa/So/Mo 00:00 (inkrementell)")
    sched.start()
