#!/usr/bin/env python3
import http.client
import json
import os
import time
import schedule
import argparse
from datetime import datetime

# ---------------------------
# Pfade anpassen
# ---------------------------
INPUT_FILE  = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"
OUTPUT_FILE = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/match_statistics_league_78.json"

# ---------------------------
# API-Konfiguration
# ---------------------------
API_HOST = "v3.football.api-sports.io"
API_KEY  = "5fa2372f2bfcbedb8ef7b85c86f0a27a"
HEADERS  = {
    'x-rapidapi-host': API_HOST,
    'x-rapidapi-key':  API_KEY
}

def remove_keys(obj, keys_to_remove):
    """
    Entfernt rekursiv alle Schlüssel aus dicts und nested Strukturen.
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

def collect_match_statistics(full_load=False):
    print(f"[{datetime.now()}] Starte Abruf (full_load={full_load}) ...")

    # 1) Fixtures einlesen
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            fixtures_data = json.load(f).get("response", [])
        print(f"[{datetime.now()}] {len(fixtures_data)} Fixtures geladen.")
    except FileNotFoundError:
        print(f"[{datetime.now()}] Fehler: Fixture-Datei nicht gefunden")
        return

    # 2) Bestehende Statistiken (nur im Inkremental-Modus)
    if full_load:
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)
            print(f"[{datetime.now()}] Alte Statistik-Datei gelöscht (Full-Load).")
        existing_stats = []
        existing_ids   = set()
    else:
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing_stats = json.load(f).get("response", [])
            print(f"[{datetime.now()}] {len(existing_stats)} bestehende Statistiken geladen.")
        except (FileNotFoundError, json.JSONDecodeError):
            existing_stats = []
            print(f"[{datetime.now()}] Keine bestehende Statistik-Datei gefunden; neue Liste erstellt.")
        existing_ids = {stat.get("fixture_id") for stat in existing_stats if stat.get("fixture_id") is not None}

    # 3) Filter: nur Finished-Spiele (status.short == "FT")
    to_fetch = []
    for fx in fixtures_data:
        fixture     = fx.get("fixture", {})
        status_short = fixture.get("status", {}).get("short")
        mid          = fixture.get("id")

        # Nur abgeschlossene Spiele und keine Duplikate
        if status_short != "FT" or mid in existing_ids:
            continue
        to_fetch.append(mid)

    print(f"[{datetime.now()}] {len(to_fetch)} abgeschlossene Matches zum Abruf gefunden.")

    if not to_fetch:
        print(f"[{datetime.now()}] Keine neuen Statistiken gefunden.")
        return

    # 4) Abrufen der neuen Statistiken
    conn = http.client.HTTPSConnection(API_HOST)
    new_stats = []
    for idx, mid in enumerate(to_fetch, 1):
        print(f"[{idx}/{len(to_fetch)}] Abruf für Match-ID {mid}...")
        conn.request("GET", f"/fixtures/statistics?fixture={mid}", headers=HEADERS)
        res = conn.getresponse()
        raw = res.read()
        try:
            stat_json = json.loads(raw.decode('utf-8'))
        except json.JSONDecodeError:
            print(f"[{idx}/{len(to_fetch)}] JSON-Fehler für Match-ID {mid}.")
            continue
        remove_keys(stat_json, {"logo"})
        stat_json["fixture_id"] = mid
        new_stats.append(stat_json)
        time.sleep(0.15)
    conn.close()

    # 5) Speichern
    existing_stats.extend(new_stats)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({"response": existing_stats}, f, ensure_ascii=False, indent=4)
    print(f"[{datetime.now()}] {len(new_stats)} neue Statistiken gespeichert.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Match-Statistiken abrufen")
    parser.add_argument(
        "--full-load",
        action="store_true",
        help="Alle beendeten Spiele neu abfragen (alte Daten werden gelöscht)"
    )
    args = parser.parse_args()

    # Initialer Lauf: Full- oder Inkremental-Modus je nach Flag
    collect_match_statistics(full_load=args.full_load)

    # Geplante Läufe immer im Inkremental-Modus
    schedule.every().saturday.at("01:00").do(collect_match_statistics, full_load=False)
    schedule.every().sunday.at("01:00").do(collect_match_statistics, full_load=False)
    schedule.every().monday.at("01:00").do(collect_match_statistics, full_load=False)

    print("Scheduler läuft...")
    while True:
        schedule.run_pending()
        time.sleep(60)
