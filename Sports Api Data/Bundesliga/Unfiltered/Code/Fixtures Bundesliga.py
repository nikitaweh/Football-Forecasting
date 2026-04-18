#!/usr/bin/env python3
import json
import os
from datetime import datetime, timezone

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------
# Pfade anpassen
# ---------------------------
OUTPUT_FILE = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"

# ---------------------------
# API-Konfiguration
# ---------------------------
API_HOST = "v3.football.api-sports.io"
BASE_URL = f"https://{API_HOST}"
API_KEY = "5fa2372f2bfcbedb8ef7b85c86f0a27a"
HEADERS = {
    "x-rapidapi-host": API_HOST,
    "x-rapidapi-key": API_KEY,
}
REQUEST_CONNECT_TIMEOUT = 4
REQUEST_READ_TIMEOUT = 12
REQUEST_RETRIES = 2
REQUEST_BACKOFF_SECONDS = 1.0

LEAGUE_ID = 78
START_SEASON = 2017


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


def fetch_fixtures_by_season(session, season):
    print(f"Starte Abruf Saison {season}...")
    try:
        data = _api_get_json(session, "/fixtures", params={"league": LEAGUE_ID, "season": season})
        fixtures = data.get("response", [])
        for fixture in fixtures:
            remove_keys(fixture, {"logo", "flag"})
        return fixtures
    except Exception as exc:
        print(f"Saison {season}: Fehler beim Abruf: {exc}")
        return []


def save_all(fixtures):
    out = {
        "last_run": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "response": fixtures,
    }
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=4)
    print(f"Gespeichert: {len(fixtures)} Spiele.")


def fetch_full_fixtures():
    current_year = datetime.now(timezone.utc).year
    seasons = list(range(START_SEASON, current_year + 1))
    all_fixtures = []
    seen_ids = set()

    with _build_session() as session:
        for season in seasons:
            fixtures = fetch_fixtures_by_season(session, season)
            for fixture in fixtures:
                fid = fixture.get("fixture", {}).get("id")
                if fid and fid not in seen_ids:
                    seen_ids.add(fid)
                    all_fixtures.append(fixture)

    save_all(all_fixtures)


def fetch_new_fixtures():
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        existing = data.get("response", [])
    except (FileNotFoundError, json.JSONDecodeError):
        existing = []

    seen_ids = {
        fixture.get("fixture", {}).get("id")
        for fixture in existing
        if fixture.get("fixture", {}).get("id")
    }
    new_fixtures = []

    current_season = datetime.now(timezone.utc).year
    with _build_session() as session:
        fixtures = fetch_fixtures_by_season(session, current_season)

    for fixture in fixtures:
        fid = fixture.get("fixture", {}).get("id")
        if fid and fid not in seen_ids:
            seen_ids.add(fid)
            new_fixtures.append(fixture)

    if new_fixtures:
        combined = existing + new_fixtures
        save_all(combined)
        print(f"{len(new_fixtures)} neue Spiele hinzugefuegt.")
    else:
        print("Keine neuen Spiele.")


if __name__ == "__main__":
    fetch_full_fixtures()

    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(fetch_new_fixtures, trigger=CronTrigger(day_of_week="sat,sun,mon", hour="0", minute="0"))
    print("Scheduler gestartet fuer regelmaessige Delta-Aktualisierungen.")
    sched.start()
