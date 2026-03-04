#!/usr/bin/env python3
import http.client
import json
import os
import argparse
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

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

def collect_lineups(full_load=False):
    """
    Holt die Lineup-Daten für alle Fixture-IDs aus der Input-Datei.
    Full-Load ist deaktiviert.
    Es werden immer neue Fixtures ergänzt und leere Einträge erneut abgefragt.
    """
    if full_load:
        print(f"[{datetime.now()}] Hinweis: --full-load ist deaktiviert. Es wird inkrementell fortgesetzt.")
    print(f"[{datetime.now()}] Starte Abruf der Lineup-Daten (inkrementell) ...")

    fixtures_file_path = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"
    output_file_path   = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/lineups_league_78.json"

    try:
        with open(fixtures_file_path, "r", encoding="utf-8") as f:
            fixtures_data = json.load(f).get("response", [])
    except FileNotFoundError:
        print(f"[{datetime.now()}] FEHLER: Fixture-Datei nicht gefunden.")
        return

    fixture_ids = [fx.get("fixture", {}).get("id") for fx in fixtures_data if fx.get("fixture", {}).get("id")]
    print(f"[{datetime.now()}] Gefundene Fixture-IDs: {len(fixture_ids)}")

    try:
        with open(output_file_path, "r", encoding="utf-8") as f:
            existing_lineups = json.load(f).get("response", [])
    except (FileNotFoundError, json.JSONDecodeError):
        existing_lineups = []

    # Index bestehender Daten: pro Fixture-ID nur ein Datensatz.
    existing_by_id = {
        ln.get("fixture_id"): ln
        for ln in existing_lineups
        if ln.get("fixture_id") is not None
    }

    # Inkremental nur Fixtures überspringen, die bereits echte Lineups enthalten.
    ids_with_data = {
        fid
        for fid, ln in existing_by_id.items()
        if isinstance(ln.get("response"), list) and len(ln.get("response")) > 0
    }

    conn = http.client.HTTPSConnection("v3.football.api-sports.io")
    headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': "5fa2372f2bfcbedb8ef7b85c86f0a27a"}

    refreshed = 0
    refreshed_with_data = 0
    total = len(fixture_ids)
    for idx, fid in enumerate(fixture_ids, start=1):
        if fid in ids_with_data:
            continue
        conn.request("GET", f"/fixtures/lineups?fixture={fid}", headers=headers)
        res = conn.getresponse()
        try:
            lineup_data = json.loads(res.read().decode("utf-8"))
        except Exception:
            continue
        remove_keys(lineup_data, {"logo", "photo"})
        lineup_data["fixture_id"] = fid
        existing_by_id[fid] = lineup_data
        refreshed += 1
        if isinstance(lineup_data.get("response"), list) and len(lineup_data.get("response")) > 0:
            refreshed_with_data += 1
    conn.close()

    existing_lineups = [existing_by_id[fid] for fid in fixture_ids if fid in existing_by_id]
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
    with open(output_file_path, "w", encoding="utf-8") as f:
        json.dump({"response": existing_lineups}, f, ensure_ascii=False, indent=4)
    print(
        f"[{datetime.now()}] Aktualisiert {refreshed} Fixture-Datensaetze "
        f"({refreshed_with_data} mit Lineups) in {output_file_path}"
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lineup-Daten abrufen und planen")
    parser.add_argument(
        '--full-load',
        action='store_true',
        help='Deaktiviert: wird ignoriert, es laeuft immer inkrementell'
    )
    args = parser.parse_args()

    # Initialer Lauf (immer inkrementell)
    collect_lineups(full_load=args.full_load)

    # Scheduler einrichten für inkrementelle Updates
    sched = BlockingScheduler(timezone="Europe/Berlin")
    trigger = CronTrigger(day_of_week="sat,sun,mon", hour="0", minute="0")
    sched.add_job(collect_lineups, trigger=trigger)
    print(f"[{datetime.now()}] Scheduler gestartet: Sa/So/Mo 00:00 (inkrementell)")
    sched.start()
