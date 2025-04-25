import http.client
import json
import os
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Konfiguration
# ---------------------------
LEAGUES_FILE_PATH = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/Bundesliga.json"
OUTPUT_FILE_PATH  = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/Bundesliga Teams.json"

API_HOST = "v3.football.api-sports.io"
HEADERS  = {
    'x-rapidapi-host': "v3.football.api-sports.io",
    'x-rapidapi-key': "5fa2372f2bfcbedb8ef7b85c86f0a27a"
}

def remove_keys(obj, keys_to_remove):
    """
    Entfernt rekursiv alle Schlüssel, die in keys_to_remove enthalten sind,
    aus Dictionaries und Listen.
    """
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if key in keys_to_remove:
                del obj[key]
            else:
                remove_keys(obj[key], keys_to_remove)
    elif isinstance(obj, list):
        for item in obj:
            remove_keys(item, keys_to_remove)

def fetch_all_teams():
    # 1) Liga-IDs laden
    with open(LEAGUES_FILE_PATH, "r", encoding="utf-8") as f:
        leagues_data = json.load(f)

    league_ids = {
        item.get("league", {}).get("id")
        for item in leagues_data.get("response", [])
        if item.get("league", {}).get("id") is not None
    }
    league_ids = list(league_ids)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Gefundene Liga-IDs: {league_ids}")

    # 2) Seasons ab 2017 bis heute
    current_year = datetime.now().year
    seasons = list(range(2017, current_year + 1))
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Abzufragende Seasons: {seasons}")

    all_teams = []
    conn = http.client.HTTPSConnection(API_HOST)

    # 3) API-Calls pro Liga und Saison
    for league_id in league_ids:
        for season in seasons:
            endpoint = f"/teams?league={league_id}&season={season}"
            conn.request("GET", endpoint, headers=HEADERS)
            res = conn.getresponse()
            data = res.read()
            body = json.loads(data.decode("utf-8"))
            teams = body.get("response", [])
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Liga {league_id}, Saison {season}: {len(teams)} Teams")
            all_teams.extend(teams)

    # 4) Keys "logo" und "image" entfernen
    for team in all_teams:
        remove_keys(team, {"logo", "image"})

    # 5) Duplikate anhand team["team"]["id"] eliminieren
    unique = {}
    for entry in all_teams:
        team_info = entry.get("team", {})
        tid = team_info.get("id")
        if tid is not None and tid not in unique:
            unique[tid] = entry

    output_data = {"response": list(unique.values())}

    # 6) Speichern
    os.makedirs(os.path.dirname(OUTPUT_FILE_PATH), exist_ok=True)
    with open(OUTPUT_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Alle eindeutigen Teams gespeichert in: {OUTPUT_FILE_PATH}")


if __name__ == "__main__":
    sched = BlockingScheduler(timezone="Europe/Berlin")
    # CronTrigger: Saturday, Sunday, Monday um 01:00
    sched.add_job(
        fetch_all_teams,
        trigger=CronTrigger(day_of_week="sat,sun,mon", hour="1", minute="0")
    )
    print("Scheduler gestartet – läuft samstags, sonntags & montags um 01:00 Uhr (Europe/Berlin)")
    sched.start()
