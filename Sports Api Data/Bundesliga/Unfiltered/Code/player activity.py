import json
import os
import time
import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Konfiguration
# ---------------------------
INPUT_JSON = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/players_profiles_78.json"
OUTPUT_JSON = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/players_activity_78.json"
API_URL    = "https://v3.football.api-sports.io/players/seasons"
HEADERS    = {
    'x-rapidapi-host': "v3.football.api-sports.io",
    'x-rapidapi-key': "5fa2372f2bfcbedb8ef7b85c86f0a27a"
}

def fetch_player_activity():
    # 1) Spieler-IDs aus Profil-Datei laden
    with open(INPUT_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    player_ids = [
        p.get("player_id")
        for p in data.get("players", [])
        if p.get("player_id") is not None
    ]
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Gefundene {len(player_ids)} Spieler-IDs")

    # 2) Abfrage der Seasons für jeden Spieler
    seasons_by_player = {}
    for pid in player_ids:
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
