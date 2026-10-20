import glob
import json
import os
import time
import http.client
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
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
# Alle Profil-Dateien (Bundesliga + internationale Wettbewerbe) einlesen
INPUT_DIR     = rf"{PROJECT_ROOT}/Sports Api Data/Player Profiles/Unfiltered/Datacollection"
INPUT_PATTERN = os.path.join(INPUT_DIR, "players_profiles*.json")
OUTPUT_JSON = rf"{PROJECT_ROOT}/Sports Api Data/Player Profiles/Unfiltered/Datacollection/transferhistory_78.json"

API_HOST    = "v3.football.api-sports.io"
API_KEY     = _secret("API_FOOTBALL_KEY")
HEADERS     = {
    'x-rapidapi-host': API_HOST,
    'x-rapidapi-key':  API_KEY
}

def fetch_transfer_history(refresh_existing=False):
    # 1) Spieler-IDs aus allen Profil-Dateien sammeln (Bundesliga + international)
    player_ids = set()
    for path in sorted(glob.glob(INPUT_PATTERN)):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Fehler beim Laden von {path}: {e}")
            continue
        for p in data.get("players", []):
            if p.get("player_id") is not None:
                player_ids.add(str(p.get("player_id")))
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Gefundene {len(player_ids)} eindeutige Spieler-IDs")

    # 1.1) Bereits abgefragte Spieler laden (inkrementell)
    all_transfers = {}
    if not refresh_existing and os.path.exists(OUTPUT_JSON):
        try:
            with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
                all_transfers = json.load(f).get("transfers_by_player", {})
        except Exception:
            all_transfers = {}
    ids_to_fetch = sorted(
        pid for pid in player_ids
        if refresh_existing or not all_transfers.get(pid)
    )
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Davon neu abzufragen: {len(ids_to_fetch)}")

    # 2) Transfer-History abfragen
    conn = http.client.HTTPSConnection(API_HOST)

    for pid in ids_to_fetch:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Hole Transfers für Spieler {pid} …")
        path = f"/transfers?player={pid}"
        conn.request("GET", path, headers=HEADERS)
        res = conn.getresponse()
        raw = res.read().decode('utf-8')

        if res.status != 200:
            print(f"→ Fehler {res.status} für Spieler {pid}")
            transfers_list = []
        else:
            try:
                obj = json.loads(raw)
                transfers_list = obj.get("response", [])
            except json.JSONDecodeError:
                print(f"→ Ungültiges JSON für Spieler {pid}")
                transfers_list = []

        # logo-Felder entfernen
        for entry in transfers_list:
            for move in entry.get("transfers", []):
                teams = move.get("teams", {})
                if isinstance(teams.get("in"), dict):
                    teams["in"].pop("logo", None)
                if isinstance(teams.get("out"), dict):
                    teams["out"].pop("logo", None)
            if isinstance(entry.get("team"), dict):
                entry["team"].pop("logo", None)
            if isinstance(entry.get("league"), dict):
                entry["league"].pop("logo", None)

        all_transfers[pid] = transfers_list

    conn.close()

    # 3) Ergebnisse speichern
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({
            "generated_at": generated_at,
            "transfers_by_player": all_transfers
        }, f, ensure_ascii=False, indent=2)

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Transfer-Historien gespeichert in: {OUTPUT_JSON}")


if __name__ == "__main__":
    # Scheduler initialisieren
    sched = BlockingScheduler(timezone="Europe/Berlin")
    # CronTrigger: am 1. jedes Monats um 01:00 Uhr
    sched.add_job(
        fetch_transfer_history,
        trigger=CronTrigger(day="1", hour="1", minute="0")
    )
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scheduler gestartet – nächster Lauf am 1. des Monats um 01:00 Uhr (Europe/Berlin)")
    sched.start()
