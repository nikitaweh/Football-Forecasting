import json
import os
from datetime import datetime

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path

# Repo root: KI_PROJECT_ROOT if set (VPS), else derived from this file's location.
PROJECT_ROOT = Path(os.environ.get("KI_PROJECT_ROOT") or Path(__file__).resolve().parents[4]).as_posix()


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
# Konfiguration
# ---------------------------
LEAGUES_FILE_PATH = rf"{PROJECT_ROOT}/Sports Api Data/Bundesliga/Unfiltered/Datacollection/Bundesliga.json"
OUTPUT_FILE_PATH = rf"{PROJECT_ROOT}/Sports Api Data/Bundesliga/Unfiltered/Datacollection/Bundesliga Teams.json"

API_HOST = "v3.football.api-sports.io"
BASE_URL = f"https://{API_HOST}"
HEADERS = {
    "x-rapidapi-host": API_HOST,
    "x-rapidapi-key": _secret("API_FOOTBALL_KEY"),
}
REQUEST_CONNECT_TIMEOUT = 4
REQUEST_READ_TIMEOUT = 10
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


def fetch_all_teams():
    try:
        with open(LEAGUES_FILE_PATH, "r", encoding="utf-8") as f:
            leagues_data = json.load(f)
    except Exception as exc:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Fehler beim Laden der Liga-Datei: {exc}")
        return

    league_ids = {
        item.get("league", {}).get("id")
        for item in leagues_data.get("response", [])
        if item.get("league", {}).get("id") is not None
    }
    league_ids = sorted(list(league_ids))
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Gefundene Liga-IDs: {league_ids}")

    current_year = datetime.now().year
    seasons = list(range(2017, current_year + 1))
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Abzufragende Seasons: {seasons}")

    all_teams = []
    with _build_session() as session:
        for league_id in league_ids:
            for season in seasons:
                try:
                    body = _api_get_json(
                        session,
                        "/teams",
                        params={"league": league_id, "season": season},
                    )
                    teams = body.get("response", [])
                    print(
                        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] "
                        f"Liga {league_id}, Saison {season}: {len(teams)} Teams"
                    )
                    all_teams.extend(teams)
                except Exception as exc:
                    print(
                        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] "
                        f"Fehler bei Liga {league_id}, Saison {season}: {exc}"
                    )

    for team in all_teams:
        remove_keys(team, {"logo", "image"})

    unique = {}
    for entry in all_teams:
        team_info = entry.get("team", {})
        tid = team_info.get("id")
        if tid is not None and tid not in unique:
            unique[tid] = entry

    output_data = {"response": list(unique.values())}

    os.makedirs(os.path.dirname(OUTPUT_FILE_PATH), exist_ok=True)
    with open(OUTPUT_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Alle eindeutigen Teams gespeichert in: {OUTPUT_FILE_PATH}")


if __name__ == "__main__":
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Starte initialen Abruf aller Teams ...")
    fetch_all_teams()
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Initialer Abruf abgeschlossen.")

    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(
        fetch_all_teams,
        trigger=CronTrigger(day_of_week="sat,sun,mon", hour="1", minute="0"),
    )
    print("Scheduler gestartet - laeuft samstags, sonntags & montags um 01:00 Uhr (Europe/Berlin)")
    sched.start()
