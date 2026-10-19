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
OUTPUT_FILE = r"C:/AI Projekt/KI-Projekt/Sports Api Data/International/UEFA/Unfiltered/Datacollection/fixtures_international.json"

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

# UEFA-Wettbewerbe (api-football Liga-IDs): Europameisterschaft, Nations League und
# EM-Qualifikation. FIFA-Wettbewerbe (WM inkl. Qualifikation) liegen im Zweig
# International/FIFA/. Vereins-Freundschaftsspiele werden separat im
# Friendlies/-Unterzweig gesammelt.
LEAGUE_IDS = {
    4: "Euro Championship",
    5: "UEFA Nations League",
    960: "Euro Championship - Qualification",
}
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


def fetch_fixtures_by_league_season(session, league_id, season):
    print(f"Starte Abruf Liga {league_id} ({LEAGUE_IDS.get(league_id, '?')}), Saison {season}...")
    try:
        data = _api_get_json(session, "/fixtures", params={"league": league_id, "season": season})
        fixtures = data.get("response", [])
        for fixture in fixtures:
            remove_keys(fixture, {"logo", "flag"})
        return fixtures
    except Exception as exc:
        print(f"Liga {league_id}, Saison {season}: Fehler beim Abruf: {exc}")
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


def _current_season():
    # Internationale Wettbewerbe nutzen das Kalenderjahr bzw. das Startjahr
    # (Nations League 2024 = Sep 2024 - Jun 2025, Friendlies = Kalenderjahr).
    return datetime.now(timezone.utc).year


def _seasons_to_refresh():
    # Vorjahr immer mit abdecken, da z.B. Nations-League-Finals im Folgejahr
    # noch zur Vorjahres-Saison gehoeren.
    season = _current_season()
    return [season - 1, season]


def fetch_full_fixtures():
    current_season = _current_season()
    seasons = list(range(START_SEASON, current_season + 1))
    all_fixtures = []
    seen_ids = set()

    with _build_session() as session:
        for league_id in LEAGUE_IDS:
            for season in seasons:
                fixtures = fetch_fixtures_by_league_season(session, league_id, season)
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

    by_id = {}
    order = []
    for fixture in existing:
        fid = fixture.get("fixture", {}).get("id")
        if fid is None:
            continue
        if fid not in by_id:
            order.append(fid)
        by_id[fid] = fixture

    added = 0
    updated = 0
    with _build_session() as session:
        for league_id in LEAGUE_IDS:
            for season in _seasons_to_refresh():
                fixtures = fetch_fixtures_by_league_season(session, league_id, season)
                for fixture in fixtures:
                    fid = fixture.get("fixture", {}).get("id")
                    if fid is None:
                        continue
                    if fid in by_id:
                        if by_id[fid] != fixture:
                            by_id[fid] = fixture
                            updated += 1
                    else:
                        by_id[fid] = fixture
                        order.append(fid)
                        added += 1

    combined = [by_id[fid] for fid in order]
    save_all(combined)
    print(f"{added} neue Spiele, {updated} aktualisiert.")


if __name__ == "__main__":
    if os.path.exists(OUTPUT_FILE):
        fetch_new_fixtures()
    else:
        fetch_full_fixtures()

    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(fetch_new_fixtures, trigger=CronTrigger(day_of_week="tue,wed,thu", hour="0", minute="0"))
    print("Scheduler gestartet fuer regelmaessige Delta-Aktualisierungen.")
    sched.start()
