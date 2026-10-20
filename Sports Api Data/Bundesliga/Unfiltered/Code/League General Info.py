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



OUTPUT_FILE = rf"{PROJECT_ROOT}/Sports Api Data/Bundesliga/Unfiltered/Datacollection/Bundesliga.json"
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


def _api_get_json(session, endpoint):
    url = f"{BASE_URL}{endpoint}"
    response = session.get(url, timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT))
    response.raise_for_status()
    return response.json()


def fetch_bundesliga():
    try:
        with _build_session() as session:
            json_data = _api_get_json(session, "/leagues")
    except Exception as exc:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] API-Fehler beim Laden der Ligen: {exc}")
        return

    remove_keys(json_data, {"logo", "flag"})

    bundesliga_data = {
        "get": json_data.get("get"),
        "parameters": json_data.get("parameters"),
        "errors": json_data.get("errors"),
        "results": 0,
        "response": [],
    }

    for item in json_data.get("response", []):
        if (
            item.get("league", {}).get("name") == "Bundesliga"
            and item.get("country", {}).get("name") == "Germany"
        ):
            bundesliga_data["response"].append(item)

    bundesliga_data["results"] = len(bundesliga_data["response"])

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(bundesliga_data, f, ensure_ascii=False, indent=4)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Daten gespeichert: {OUTPUT_FILE}")


if __name__ == "__main__":
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Starte initialen Abruf der Bundesliga-Liga-Daten ...")
    fetch_bundesliga()
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Initialer Abruf abgeschlossen.")

    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(fetch_bundesliga, trigger=CronTrigger(day="1", hour="0", minute="0"))
    print("Scheduler gestartet - naechster Lauf am 1. des naechsten Monats um 00:00 Uhr")
    sched.start()
