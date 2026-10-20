import glob
import json
import os
import time
import requests
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
INPUT_DIR = rf"{PROJECT_ROOT}/Sports Api Data/Player Profiles/Unfiltered/Datacollection"
INPUT_PATTERN = os.path.join(INPUT_DIR, "players_profiles*.json")
OUTPUT_JSON = rf"{PROJECT_ROOT}/Sports Api Data/Player Profiles/Unfiltered/Datacollection/players_activity_78.json"
API_URL    = "https://v3.football.api-sports.io/players/seasons"
HEADERS    = {
    'x-rapidapi-host': "v3.football.api-sports.io",
    'x-rapidapi-key': _secret("API_FOOTBALL_KEY")
}

def fetch_player_activity(refresh_existing=False):
    # 1) Spieler-IDs aus allen Profil-Dateien laden (Bundesliga + international)
    player_ids = []
    seen = set()
    for path in sorted(glob.glob(INPUT_PATTERN)):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Fehler beim Laden von {path}: {e}")
            continue
        for p in data.get("players", []):
            pid = p.get("player_id")
            if pid is not None and pid not in seen:
                seen.add(pid)
                player_ids.append(pid)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Gefundene {len(player_ids)} eindeutige Spieler-IDs")

    # 1.1) Bereits abgefragte Spieler laden (inkrementell)
    seasons_by_player = {}
    if not refresh_existing and os.path.exists(OUTPUT_JSON):
        try:
            with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
                seasons_by_player = json.load(f).get("players_seasons", {})
        except Exception:
            seasons_by_player = {}
    ids_to_fetch = [
        pid for pid in player_ids
        if refresh_existing or not seasons_by_player.get(str(pid))
    ]
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Davon neu abzufragen: {len(ids_to_fetch)}")

    # 2) Abfrage der Seasons für jeden Spieler
    for pid in ids_to_fetch:
        print(f"Hole Seasons für Spieler {pid} …")
        try:
            resp = requests.get(API_URL, params={"player": pid}, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            body = resp.json()
            seasons = body.get("response", [])
        except Exception as e:
            print(f"Fehler bei Spieler {pid}: {e}")
            seasons = []
        seasons_by_player[str(pid)] = seasons

    # 3) Speichern der Ergebnisse
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({
            "generated_at": generated_at,
            "players_seasons": seasons_by_player
        }, f, ensure_ascii=False, indent=2)

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Spieler-Seasons gespeichert in: {OUTPUT_JSON}")

if __name__ == "__main__":
    # Scheduler initialisieren
    sched = BlockingScheduler(timezone="Europe/Berlin")
    # Cron: je 1. des Monats um 00:00 Uhr
    sched.add_job(
        fetch_player_activity,
        trigger=CronTrigger(day="1", hour="1", minute="0")
    )
    print("Scheduler gestartet – nächster Lauf am 1. des Monats um 00:00 Uhr (Europe/Berlin)")
    sched.start()
