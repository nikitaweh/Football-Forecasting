#!/usr/bin/env python3
import json
import os
import http.client
from datetime import datetime, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Pfade anpassen
# ---------------------------
OUTPUT_FILE = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"

# ---------------------------
# API-Konfiguration
# ---------------------------
API_HOST   = "v3.football.api-sports.io"
API_KEY    = "5fa2372f2bfcbedb8ef7b85c86f0a27a"
HEADERS    = {
    'x-rapidapi-host': API_HOST,
    'x-rapidapi-key':  API_KEY
}

LEAGUE_ID = 78
START_SEASON = 2017


def remove_keys(obj, keys_to_remove):
    """
    Entfernt rekursiv alle angegebenen Schlüssel aus dicts und nested Strukturen.
    """
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            if k in keys_to_remove:
                del obj[k]
            else:
                remove_keys(obj[k], keys_to_remove)
    elif isinstance(obj, list):
        for item in obj:
            remove_keys(item, keys_to_remove)


def fetch_fixtures_by_season(season):
    """
    Ruft alle Fixtures einer Liga für eine gegebene Saison ab und entfernt logo/flag.
    (Ohne Filter auf 'Not Started' -> lädt auch ungespielte Spiele)
    """
    print(f"Starte Abruf Saison {season}...")
    conn = http.client.HTTPSConnection(API_HOST)
    endpoint = f"/fixtures?league={LEAGUE_ID}&season={season}"
    conn.request("GET", endpoint, headers=HEADERS)
    res = conn.getresponse()
    raw = res.read().decode("utf-8")
    conn.close()

    try:
        data = json.loads(raw)
        fixtures = data.get("response", [])

        # Entferne ungewünschte Keys aus jeder Fixture
        for f in fixtures:
            remove_keys(f, {"logo", "flag"})

        # >>> WICHTIG: KEIN Filter mehr auf "Not Started"
        # fixtures = [f for f in fixtures if f.get("fixture", {}).get("status", {}).get("long") != "Not Started"]

        return fixtures
    except json.JSONDecodeError:
        print(f"Saison {season}: Ungültiges JSON, überspringe.")
        return []


def save_all(fixtures):
    """
    Speichert alle Fixtures als Liste unter dem last_run Zeitstempel.
    """
    out = {
        "last_run": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "response": fixtures
    }
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=4)
    print(f"Gespeichert: {len(fixtures)} Spiele.")


def fetch_full_fixtures():
    """
    Holt alle Spiele seit Saison START_SEASON über Saison-Parameter.
    """
    current_year = datetime.now(timezone.utc).year
    seasons = list(range(START_SEASON, current_year + 1))
    all_fixtures = []
    seen_ids = set()

    for season in seasons:
        fixtures = fetch_fixtures_by_season(season)
        for f in fixtures:
            fid = f.get("fixture", {}).get("id")
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                all_fixtures.append(f)

    save_all(all_fixtures)


def fetch_new_fixtures():
    """
    Holt nur neue Spiele basierend auf vorhandener Datei.
    """
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        existing = data.get("response", [])
    except (FileNotFoundError, json.JSONDecodeError):
        existing = []

    seen_ids = {fix.get("fixture", {}).get("id") for fix in existing if fix.get("fixture", {}).get("id")}
    new_fixtures = []

    current_season = datetime.now(timezone.utc).year
    fixtures = fetch_fixtures_by_season(current_season)
    for f in fixtures:
        fid = f.get("fixture", {}).get("id")
        if fid and fid not in seen_ids:
            seen_ids.add(fid)
            new_fixtures.append(f)

    if new_fixtures:
        combined = existing + new_fixtures
        save_all(combined)
        print(f"{len(new_fixtures)} neue Spiele hinzugefügt.")
    else:
        print("Keine neuen Spiele.")


if __name__ == "__main__":
    # Vollständiger Abruf aller Saison-Daten beim Start
    fetch_full_fixtures()

    # Scheduler: nur aktuelle Saison regelmäßig aktualisieren
    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(
        fetch_new_fixtures,
        trigger=CronTrigger(day_of_week="sat,sun,mon", hour="0", minute="0")
    )
    print("Scheduler gestartet für wöchentliche Delta-Aktualisierungen.")
    sched.start()
