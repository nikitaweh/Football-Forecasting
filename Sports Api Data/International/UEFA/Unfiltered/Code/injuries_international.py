#!/usr/bin/env python3
import argparse
import json
import os
import time
from datetime import datetime, timezone

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path

# Repo root: KI_PROJECT_ROOT if set (VPS), else derived from this file's location.
PROJECT_ROOT = Path(os.environ.get("KI_PROJECT_ROOT") or Path(__file__).resolve().parents[5]).as_posix()


def _secret(name):
    """API keys come from the environment (systemd EnvironmentFile on the VPS)
    or, failing that, from the gitignored .env at the repo root."""
    env_file = os.path.join(PROJECT_ROOT, ".env")
    if name not in os.environ and os.path.exists(env_file):
        with open(env_file, encoding="utf-8") as fh:
            for line in fh:
                key, sep, value = line.strip().partition("=")
                if sep and not key.startswith("#"):
                    os.environ.setdefault(key.strip(), value.strip().strip('"'))
    if not os.environ.get(name):
        raise RuntimeError(f"{name} is not set (environment or {env_file})")
    return os.environ[name]



# ---------------------------
# Pfade anpassen
# ---------------------------
INPUT_FILE = rf"{PROJECT_ROOT}/Sports Api Data/International/UEFA/Unfiltered/Datacollection/fixtures_international.json"
OUTPUT_FILE = rf"{PROJECT_ROOT}/Sports Api Data/International/UEFA/Unfiltered/Datacollection/injuries_international.json"

# ---------------------------
# API-Konfiguration
# ---------------------------
API_HOST = "v3.football.api-sports.io"
API_URL = f"https://{API_HOST}/injuries"
HEADERS = {
    "x-rapidapi-host": API_HOST,
    "x-rapidapi-key": _secret("API_FOOTBALL_KEY"),
}
REQUEST_CONNECT_TIMEOUT = 4
REQUEST_READ_TIMEOUT = 12
REQUEST_RETRIES = 2
REQUEST_BACKOFF_SECONDS = 1.0


def _current_season():
    # Internationale Wettbewerbe nutzen das Kalenderjahr bzw. das Startjahr
    # (Nations League 2024 = Sep 2024 - Jun 2025, EM = Kalenderjahr).
    return datetime.now(timezone.utc).year


def _seasons_to_refresh():
    # Vorjahr immer mit abdecken, da z.B. Nations-League-Finals im Folgejahr
    # noch zur Vorjahres-Saison gehoeren.
    season = _current_season()
    return {season - 1, season}


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


def fetch_injuries(full_load=False):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if full_load:
        print(f"[{now}] Hinweis: --full-load ist deaktiviert. Es wird inkrementell fortgesetzt.")
    print(f"[{now}] Starte fetch_injuries(inkrementell) ...")

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"[{now}] Fehler beim Laden der Fixture-Datei: {exc}")
        return

    seasons = _seasons_to_refresh()
    fixture_ids = []
    for item in data.get("response", []):
        season = item.get("league", {}).get("season")
        if season not in seasons:
            continue
        fid = item.get("fixture", {}).get("id") or item.get("fixture_id")
        if fid is not None:
            fixture_ids.append(fid)
    print(
        f"[{now}] Aktuelle Saison(s): {sorted(seasons)} - "
        f"Gefundene Fixture-IDs: {len(fixture_ids)}"
    )

    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f).get("injuries_by_fixture", {})
        except Exception:
            existing = {}
    else:
        existing = {}

    ids_with_data = {
        fid_str
        for fid_str, injuries in existing.items()
        if isinstance(injuries, list) and len(injuries) > 0
    }
    new_ids = [fid for fid in fixture_ids if str(fid) not in ids_with_data]
    print(f"[{now}] Zu verarbeitende Fixture-IDs: {len(new_ids)}")

    refreshed = 0
    refreshed_with_data = 0

    with _build_session() as session:
        for fid in new_ids:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] Hole Injuries fuer Fixture {fid} ...")
            try:
                resp = session.get(
                    API_URL,
                    params={"fixture": fid},
                    timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT),
                )
                resp.raise_for_status()
                injuries_list = resp.json().get("response", [])
            except Exception as exc:
                print(f"-> Fehler bei Fixture {fid}: {exc}")
                injuries_list = []

            for inj in injuries_list:
                if isinstance(inj.get("player"), dict):
                    inj["player"].pop("photo", None)
                if isinstance(inj.get("team"), dict):
                    inj["team"].pop("logo", None)
                if isinstance(inj.get("league"), dict):
                    inj["league"].pop("logo", None)
                    inj["league"].pop("flag", None)

            existing[str(fid)] = injuries_list
            refreshed += 1
            if injuries_list:
                refreshed_with_data += 1
            time.sleep(0.08)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"injuries_by_fixture": existing}, f, ensure_ascii=False, indent=2)

    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Injuries gespeichert in: {OUTPUT_FILE} "
        f"(aktualisiert: {refreshed}, mit Daten: {refreshed_with_data})"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Injury-Daten abrufen (UEFA)")
    parser.add_argument(
        "--full-load",
        action="store_true",
        help="Deaktiviert: wird ignoriert, es laeuft immer inkrementell",
    )
    args = parser.parse_args()

    fetch_injuries(full_load=args.full_load)

    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(fetch_injuries, trigger=CronTrigger(day_of_week="sat,sun,mon", hour="1", minute="0"))
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scheduler gestartet fuer sa, so & mo 01:00 Uhr (incremental)")
    sched.start()
