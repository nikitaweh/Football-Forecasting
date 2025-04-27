import http.client
import json
import os
import time
import schedule
from datetime import datetime

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

def collect_player_stats():
    print(f"[{datetime.now()}] Starte Abruf der individuellen Spielerstatistiken...")
    
    # ---------------------------
    # Pfade zu den Input- und Output-Dateien
    # ---------------------------
    input_file_path = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"
    output_file_path = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/player_statistics_per_fixture_league_78.json"

    # ---------------------------
    # 1) Fixture-IDs aus der Input-Datei extrahieren
    # ---------------------------
    try:
        with open(input_file_path, "r", encoding="utf-8") as f:
            fixtures_data = json.load(f)
        print(f"[{datetime.now()}] Fixture-Daten geladen.")
    except FileNotFoundError:
        print(f"[{datetime.now()}] FEHLER: Fixture-Datei '{input_file_path}' nicht gefunden.")
        return

    fixture_ids = []
    for fixture in fixtures_data.get("response", []):
        fixture_info = fixture.get("fixture", {})
        fid = fixture_info.get("id")
        if fid is not None:
            fixture_ids.append(fid)
    print(f"[{datetime.now()}] Es wurden {len(fixture_ids)} Fixture-IDs gefunden.")

    # ---------------------------
    # 2) Bereits vorhandene Spielerstatistiken laden (Duplikatschutz)
    # ---------------------------
    try:
        with open(output_file_path, "r", encoding="utf-8") as f:
            existing_stats_data = json.load(f)
            existing_stats = existing_stats_data.get("response", [])
        print(f"[{datetime.now()}] Es wurden {len(existing_stats)} bestehende Spielerstatistiken gefunden.")
    except FileNotFoundError:
        existing_stats = []
        print(f"[{datetime.now()}] Keine bestehende Spielerstatistik-Datei gefunden. Es wird eine neue Liste erstellt.")
    
    existing_fixture_ids = {stats.get("fixture_id") for stats in existing_stats if stats.get("fixture_id") is not None}

    # ---------------------------
    # 3) Für jede Fixture-ID individuelle Spielerstatistiken abrufen
    # ---------------------------
    conn = http.client.HTTPSConnection("v3.football.api-sports.io")
    headers = {
        'x-rapidapi-host': "v3.football.api-sports.io",
        'x-rapidapi-key': "5fa2372f2bfcbedb8ef7b85c86f0a27a"
    }

    new_stats = []
    total_ids = len(fixture_ids)
    for idx, fid in enumerate(fixture_ids, start=1):
        if fid in existing_fixture_ids:
            print(f"[{idx}/{total_ids}] Fixture-ID {fid} bereits erfasst, überspringe.")
            continue

        endpoint = f"/fixtures/players?fixture={fid}"
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        try:
            stats_json = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            print(f"[{idx}/{total_ids}] Fehler beim Dekodieren für Fixture-ID {fid}.")
            continue

        remove_keys(stats_json, {"logo", "photo"})
        stats_json["fixture_id"] = fid
        new_stats.append(stats_json)
        print(f"[{idx}/{total_ids}] Daten für Fixture-ID {fid} abgerufen.")
        time.sleep(0.15)

    conn.close()

    if new_stats:
        existing_stats.extend(new_stats)
        print(f"[{datetime.now()}] {len(new_stats)} neue Einträge hinzugefügt.")
    else:
        print(f"[{datetime.now()}] Keine neuen Daten gefunden.")

    # ---------------------------
    # 4) In Datei speichern
    # ---------------------------
    output_data = {"response": existing_stats}
    with open(output_file_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    print(f"[{datetime.now()}] Fertig. Datei gespeichert: '{output_file_path}'")

# ---------------------------
# Planung: Automatische Ausführung
# ---------------------------
schedule.every().saturday.at("01:00").do(collect_player_stats)
schedule.every().sunday.at("01:00").do(collect_player_stats)
schedule.every().monday.at("01:00").do(collect_player_stats)

# 1) Direkt beim Start einmal ausführen
collect_player_stats()

print("Scheduler gestartet. Warte auf die nächsten Ausführungen ...")
# 2) Scheduler-Schleife
while True:
    schedule.run_pending()
    time.sleep(3600)
