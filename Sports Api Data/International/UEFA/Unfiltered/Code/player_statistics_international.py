import json
import os
import tempfile
import time
from datetime import datetime, timezone

import requests
import schedule
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



INPUT_FILE_PATH = rf"{PROJECT_ROOT}/Sports Api Data/International/UEFA/Unfiltered/Datacollection/fixtures_international.json"
OUTPUT_FILE_PATH = rf"{PROJECT_ROOT}/Sports Api Data/International/UEFA/Unfiltered/Datacollection/player_statistics_per_fixture_international.json"

API_HOST = "v3.football.api-sports.io"
BASE_URL = f"https://{API_HOST}"
HEADERS = {
    "x-rapidapi-host": API_HOST,
    "x-rapidapi-key": _secret("API_FOOTBALL_KEY"),
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


def _current_season():
    # Internationale Wettbewerbe nutzen das Kalenderjahr bzw. das Startjahr.
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


def _api_get_json(session, endpoint, params=None):
    url = f"{BASE_URL}{endpoint}"
    response = session.get(url, params=params, timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT))
    response.raise_for_status()
    return response.json()


def _atomic_write_json(file_path, payload):
    target_dir = os.path.dirname(file_path)
    target_name = os.path.basename(file_path)
    os.makedirs(target_dir, exist_ok=True)

    # Recognisable prefix/suffix so any stray temp file is obviously ours.
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=target_dir,
        prefix=f".{target_name}.tmp_",
        suffix=".part",
        delete=False,
    ) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=4)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = tmp.name

    # On Windows, os.replace can transiently fail with PermissionError when
    # the target is held open by another process (OneDrive, antivirus, IDE
    # indexer, a previous run). Retry a few times before giving up.
    last_exc = None
    for attempt in range(6):
        try:
            os.replace(tmp_path, file_path)
            return
        except PermissionError as exc:
            last_exc = exc
            time.sleep(0.5 * (2 ** attempt))  # 0.5, 1, 2, 4, 8, 16s
    # Replace failed permanently — clean up the temp file so it doesn't linger.
    try:
        os.remove(tmp_path)
    except OSError:
        pass
    raise last_exc


def collect_player_stats():
    print(f"[{datetime.now()}] Starte Abruf der individuellen Spielerstatistiken (international)...")

    try:
        with open(INPUT_FILE_PATH, "r", encoding="utf-8") as f:
            fixtures_data = json.load(f)
        print(f"[{datetime.now()}] Fixture-Daten geladen.")
    except FileNotFoundError:
        print(f"[{datetime.now()}] FEHLER: Fixture-Datei '{INPUT_FILE_PATH}' nicht gefunden.")
        return

    seasons_to_refresh = _seasons_to_refresh()
    fixture_ids = []
    refresh_ids = set()
    for fixture in fixtures_data.get("response", []):
        fid = fixture.get("fixture", {}).get("id")
        if fid is None:
            continue
        fixture_ids.append(fid)
        if fixture.get("league", {}).get("season") in seasons_to_refresh:
            refresh_ids.add(fid)
    print(
        f"[{datetime.now()}] {len(fixture_ids)} Fixture-IDs gefunden, "
        f"davon {len(refresh_ids)} aus Saison(s) {sorted(seasons_to_refresh)} (werden refreshed)."
    )

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

    # Index by fixture_id so current-season entries can be overwritten in place.
    stats_by_fid = {
        entry.get("fixture_id"): entry
        for entry in existing_stats
        if entry.get("fixture_id") is not None
    }

    total_ids = len(fixture_ids)
    fetched_new = 0
    refreshed = 0
    failed = 0
    with _build_session() as session:
        for idx, fid in enumerate(fixture_ids, start=1):
            is_refresh = fid in refresh_ids
            already_have = fid in stats_by_fid
            if already_have and not is_refresh:
                continue

            try:
                stats_json = _api_get_json(session, "/fixtures/players", params={"fixture": fid})
            except Exception as exc:
                print(f"[{idx}/{total_ids}] Fehler fuer Fixture-ID {fid}: {exc}")
                failed += 1
                continue

            remove_keys(stats_json, {"logo", "photo"})
            stats_json["fixture_id"] = fid
            stats_by_fid[fid] = stats_json
            if already_have:
                refreshed += 1
            else:
                fetched_new += 1
            time.sleep(0.12)

    print(
        f"[{datetime.now()}] Neu hinzugefuegt: {fetched_new}, aktualisiert: {refreshed}, "
        f"fehlgeschlagen: {failed}."
    )

    output_data = {"response": list(stats_by_fid.values())}
    _atomic_write_json(OUTPUT_FILE_PATH, output_data)
    print(f"[{datetime.now()}] Fertig. Datei gespeichert: '{OUTPUT_FILE_PATH}'")


if __name__ == "__main__":
    collect_player_stats()

    schedule.every().tuesday.at("01:00").do(collect_player_stats)
    schedule.every().wednesday.at("01:00").do(collect_player_stats)
    schedule.every().thursday.at("01:00").do(collect_player_stats)

    print("Scheduler gestartet. Warte auf die naechsten Ausfuehrungen ...")
    while True:
        schedule.run_pending()
        time.sleep(60)
