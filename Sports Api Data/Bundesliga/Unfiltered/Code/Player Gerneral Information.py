import json
import os
import time
import requests
from requests.exceptions import RequestException, HTTPError, ConnectionError
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Konfiguration
# ---------------------------
API_HOST    = "https://v3.football.api-sports.io"
API_KEY     = "5fa2372f2bfcbedb8ef7b85c86f0a27a"
INPUT_JSON  = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/Bundesliga.json"
OUTPUT_JSON = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/players_profiles_78.json"
RETRY_LIMIT = 3
RETRY_DELAY = 5  # Sekunden zwischen Versuchen

def get_with_retry(url, params, headers):
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except (ConnectionError, HTTPError, RequestException) as e:
            print(f"Fehler beim Abruf (Versuch {attempt}/{RETRY_LIMIT}): {e}")
            if attempt < RETRY_LIMIT:
                time.sleep(RETRY_DELAY)
            else:
                raise

def fetch_player_profiles():
    # 1) Liga- und Saisoninfo laden
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        league_data = json.load(f)

    league_info = league_data.get("response", [{}])[0]
    league_id   = league_info.get("league", {}).get("id")
    seasons     = league_info.get("seasons", [])
    if not league_id or not seasons:
        raise RuntimeError("Konnte Liga-ID oder Seasons nicht finden")
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Liga {league_id} mit Saisons: {[s.get('year') for s in seasons]}")

    # 2) Allgemeine Spielerdaten pro Saison ab 2017 abrufen
    headers = {"x-apisports-key": API_KEY}
    basic_players = []

    for season_entry in seasons:
        year = season_entry.get("year")
        if not year or year < 2017:
            continue
        print(f"Hole allgemeine Daten für Saison {year} …")
        page = 1
        while True:
            params = {"league": league_id, "season": year, "page": page}
            url = f"{API_HOST}/players"
            body = get_with_retry(url, params, headers)
            players_page = body.get("response", [])
            if not players_page:
                break
            for p in players_page:
                player_info = p.get('player', {})
                record = {
                    'season': year,
                    'player_id': player_info.get('id'),
                    'player_name': player_info.get('name'),
                    'firstname': player_info.get('firstname'),
                    'lastname': player_info.get('lastname'),
                    'age': player_info.get('age'),
                    'birth_date': player_info.get('birth', {}).get('date'),
                    'birth_place': player_info.get('birth', {}).get('place'),
                    'birth_country': player_info.get('birth', {}).get('country'),
                    'nationality': player_info.get('nationality'),
                    'height': player_info.get('height'),
                    'weight': player_info.get('weight'),
                }
                basic_players.append(record)
            total = body.get('paging', {}).get('total', 1)
            if page >= total:
                break
            page += 1

    print(f"Gesammelt: {len(basic_players)} Basis-Spielerdatensätze")

    # 3) Speichern als JSON
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            'league_id': league_id,
            'seasons': [s.get('year') for s in seasons if s.get('year') >= 2017],
            'count': len(basic_players),
            'players': basic_players
        }, f, ensure_ascii=False, indent=2)

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Ergebnis gespeichert in {OUTPUT_JSON}")


if __name__ == "__main__":
    sched = BlockingScheduler(timezone="Europe/Berlin")
    # CronTrigger: TAG=1, Stunde=0, Minute=0
    sched.add_job(fetch_player_profiles,
                  trigger=CronTrigger(day="1", hour="0", minute="30"))
    print("Scheduler gestartet – nächster Lauf am 1. des Monats um 00:00 Uhr (Europe/Berlin)")
    sched.start()
