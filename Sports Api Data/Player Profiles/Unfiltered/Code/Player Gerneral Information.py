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
# Basis-Ausgabepfad; für jede Liga wird eine eigene Datei erstellt
OUTPUT_JSON = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection/players_profiles"
# Liste der Liga-IDs, die abgefragt werden sollen
# 78 = Bundesliga, 1 = World Cup, 4 = Euro Championship,
# 5 = UEFA Nations League, 10 = Friendlies (international)
LEAGUE_IDS  = [78, 1, 4, 5, 10]

RETRY_LIMIT = 3
RETRY_DELAY = 5  # Sekunden zwischen Versuchen


def get_with_retry(url, params, headers):
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except (ConnectionError, HTTPError, RequestException) as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Fehler beim Abruf von {url} (Versuch {attempt}/{RETRY_LIMIT}): {e}")
            if attempt < RETRY_LIMIT:
                time.sleep(RETRY_DELAY)
            else:
                raise


def fetch_player_profiles():
    headers = {"x-apisports-key": API_KEY}

    for league_id in LEAGUE_IDS:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Verarbeite Liga {league_id} …")
        # 1) Saisoninfo zur Liga laden
        leagues_data = get_with_retry(f"{API_HOST}/leagues", {"league": league_id}, headers)
        resp = leagues_data.get("response", [])
        if not resp:
            print(f"Keine Daten für Liga {league_id}")
            continue
        league_info = resp[0]
        seasons = league_info.get("seasons", [])
        print(f"Gefundene Saisonjahre für Liga {league_id}: {[s['year'] for s in seasons]}")

        # 2) Spielerdaten pro Saison ab 2017 abrufen
        basic_players = []
        for season_entry in seasons:
            year = season_entry.get("year")
            if not year or year < 2017:
                continue
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Hole Daten Saison {year} …")
            page = 1
            while True:
                params = {"league": league_id, "season": year, "page": page}
                body = get_with_retry(f"{API_HOST}/players", params, headers)
                players = body.get("response", [])
                if not players:
                    break
                for p in players:
                    pl = p.get("player", {})
                    basic_players.append({
                        "league_id":    league_id,
                        "season":       year,
                        "player_id":    pl.get("id"),
                        "player_name":  pl.get("name"),
                        "firstname":    pl.get("firstname"),
                        "lastname":     pl.get("lastname"),
                        "age":          pl.get("age"),
                        "birth_date":   pl.get("birth", {}).get("date"),
                        "birth_place":  pl.get("birth", {}).get("place"),
                        "birth_country":pl.get("birth", {}).get("country"),
                        "nationality":  pl.get("nationality"),
                        "height":       pl.get("height"),
                        "weight":       pl.get("weight")
                    })
                total = body.get("paging", {}).get("total", 1)
                if page >= total:
                    break
                page += 1

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Liga {league_id}: {len(basic_players)} Datensätze gesammelt.")

        # 3) Speichern als JSON
        os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
        out_path = f"{OUTPUT_JSON}_league_{league_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "league_id": league_id,
                "seasons":   [s["year"] for s in seasons if s.get("year") >= 2017],
                "count":     len(basic_players),
                "players":   basic_players
            }, f, ensure_ascii=False, indent=2)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Gespeichert: {out_path}")


if __name__ == "__main__":
    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(
        fetch_player_profiles,
        trigger=CronTrigger(day="1", hour="0", minute="00")
    )
    print(f"Scheduler gestartet – nächster Lauf am 1. des Monats um 00:30 Uhr (Europe/Berlin)")
    sched.start()
