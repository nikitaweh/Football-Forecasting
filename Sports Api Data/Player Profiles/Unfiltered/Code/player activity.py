import glob
import json
import os
import time
import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Konfiguration
# ---------------------------
# Alle Profil-Dateien (Bundesliga + internationale Wettbewerbe) einlesen
INPUT_DIR = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection"
INPUT_PATTERN = os.path.join(INPUT_DIR, "players_profiles*.json")
OUTPUT_JSON = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection/players_activity_78.json"
API_URL    = "https://v3.football.api-sports.io/players/seasons"
HEADERS    = {
    'x-rapidapi-host': "v3.football.api-sports.io",
    'x-rapidapi-key': "5fa2372f2bfcbedb8ef7b85c86f0a27a"
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
