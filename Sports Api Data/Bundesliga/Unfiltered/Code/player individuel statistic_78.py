import json
import os
import tempfile
import time
from datetime import datetime

import requests
import schedule
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

INPUT_FILE_PATH = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"
OUTPUT_FILE_PATH = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/player_statistics_per_fixture_league_78.json"

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


def _atomic_write_json(file_path, payload):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=os.path.dirname(file_path), delete=False) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=4)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = tmp.name

    os.replace(tmp_path, file_path)


def collect_player_stats():
    print(f"[{datetime.now()}] Starte Abruf der individuellen Spielerstatistiken...")

    try:
        with open(INPUT_FILE_PATH, "r", encoding="utf-8") as f:
            fixtures_data = json.load(f)
        print(f"[{datetime.now()}] Fixture-Daten geladen.")
    except FileNotFoundError:
        print(f"[{datetime.now()}] FEHLER: Fixture-Datei '{INPUT_FILE_PATH}' nicht gefunden.")
        return

    fixture_ids = []
    for fixture in fixtures_data.get("response", []):
        fixture_info = fixture.get("fixture", {})
        fid = fixture_info.get("id")
        if fid is not None:
            fixture_ids.append(fid)
    print(f"[{datetime.now()}] Es wurden {len(fixture_ids)} Fixture-IDs gefunden.")

    try:
        with open(OUTPUT_FILE_PATH, "r", encoding="utf-8") as f:
            existing_stats_data = json.load(f)
            existing_stats = existing_stats_data.get("response", [])
        print(f"[{datetime.now()}] Es wurden {len(existing_stats)} bestehende Spielerstatistiken gefunden.")
    except FileNotFoundError:
        existing_stats = []
        print(f"[{datetime.now()}] Keine bestehende Spielerstatistik-Datei gefunden. Es wird eine neue Liste erstellt.")
    except json.JSONDecodeError as exc:
        existing_stats = []
        backup_path = f"{OUTPUT_FILE_PATH}.corrupt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            os.replace(OUTPUT_FILE_PATH, backup_path)
            print(
                f"[{datetime.now()}] WARNUNG: Defekte JSON-Datei erkannt ({exc}). "
                f"Backup erstellt: '{backup_path}'. Es wird mit leerer Liste fortgesetzt."
            )
        except OSError:
            print(
                f"[{datetime.now()}] WARNUNG: Defekte JSON-Datei erkannt ({exc}). "
                "Backup konnte nicht erstellt werden, es wird mit leerer Liste fortgesetzt."
            )

    existing_fixture_ids = {
        stats.get("fixture_id")
        for stats in existing_stats
        if stats.get("fixture_id") is not None
    }

    new_stats = []
    total_ids = len(fixture_ids)
    with _build_session() as session:
        for idx, fid in enumerate(fixture_ids, start=1):
            if fid in existing_fixture_ids:
                print(f"[{idx}/{total_ids}] Fixture-ID {fid} bereits erfasst, ueberspringe.")
                continue

            try:
                stats_json = _api_get_json(session, "/fixtures/players", params={"fixture": fid})
            except Exception as exc:
                print(f"[{idx}/{total_ids}] Fehler fuer Fixture-ID {fid}: {exc}")
                continue

            remove_keys(stats_json, {"logo", "photo"})
            stats_json["fixture_id"] = fid
            new_stats.append(stats_json)
            print(f"[{idx}/{total_ids}] Daten fuer Fixture-ID {fid} abgerufen.")
            time.sleep(0.12)

    if new_stats:
        existing_stats.extend(new_stats)
        print(f"[{datetime.now()}] {len(new_stats)} neue Eintraege hinzugefuegt.")
    else:
        print(f"[{datetime.now()}] Keine neuen Daten gefunden.")

    output_data = {"response": existing_stats}
    _atomic_write_json(OUTPUT_FILE_PATH, output_data)
    print(f"[{datetime.now()}] Fertig. Datei gespeichert: '{OUTPUT_FILE_PATH}'")


if __name__ == "__main__":
    collect_player_stats()

    schedule.every().saturday.at("01:00").do(collect_player_stats)
    schedule.every().sunday.at("01:00").do(collect_player_stats)
    schedule.every().monday.at("01:00").do(collect_player_stats)

    print("Scheduler gestartet. Warte auf die naechsten Ausfuehrungen ...")
    while True:
        schedule.run_pending()
        time.sleep(60)
