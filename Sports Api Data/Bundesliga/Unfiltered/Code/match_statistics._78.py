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

def collect_match_statistics():
    print(f"[{datetime.now()}] Starte Abruf der Match-Statistiken ...")
    
    # Dateipfade
    input_file_path = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"
    output_file_path = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/match_statistics_league_78.json"

    # ---------------------------
    # 1) Fixture-Daten aus der Input-Datei laden und Match-IDs extrahieren
    # ---------------------------
    try:
        with open(input_file_path, "r", encoding="utf-8") as f:
            fixtures_data = json.load(f)
        print(f"[{datetime.now()}] Fixture-Daten geladen.")
    except FileNotFoundError:
        print(f"[{datetime.now()}] FEHLER: Fixture-Datei '{input_file_path}' nicht gefunden.")
        return

    match_ids = []
    for fixture in fixtures_data.get("response", []):
        fixture_info = fixture.get("fixture", {})
        match_id = fixture_info.get("id")
        if match_id is not None:
            match_ids.append(match_id)
    print(f"[{datetime.now()}] Es wurden {len(match_ids)} Match-IDs gefunden.")

    # ---------------------------
    # 2) Bestehende Match-Statistiken laden (zur Vermeidung von Duplikaten)
    # ---------------------------
    try:
        with open(output_file_path, "r", encoding="utf-8") as f:
            existing_stats_data = json.load(f)
            existing_stats = existing_stats_data.get("response", [])
        print(f"[{datetime.now()}] Es wurden {len(existing_stats)} bestehende Match-Statistiken gefunden.")
    except FileNotFoundError:
        existing_stats = []
        print(f"[{datetime.now()}] Keine bestehende Statistik-Datei gefunden. Es wird eine neue Liste erstellt.")

    # Erstelle eine Menge mit den bereits erfassten Match-IDs (aus fixture_id)
    existing_match_ids = set()
    for stat in existing_stats:
        fid = stat.get("fixture_id")
        if fid is not None:
            existing_match_ids.add(fid)

    # ---------------------------
    # 3) Für jede Match-ID werden die Statistiken abgefragt, sofern noch nicht vorhanden
    # ---------------------------
    conn = http.client.HTTPSConnection("v3.football.api-sports.io")
    headers = {
        'x-rapidapi-host': "v3.football.api-sports.io",
        'x-rapidapi-key': "5fa2372f2bfcbedb8ef7b85c86f0a27a"
    }

    new_statistics = []
    total_ids = len(match_ids)
    for idx, match_id in enumerate(match_ids, start=1):
        if match_id in existing_match_ids:
            print(f"[{idx}/{total_ids}] Statistiken für Match-ID {match_id} existieren bereits, überspringe.")
            continue

        endpoint = f"/fixtures/statistics?fixture={match_id}"
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        try:
            statistics_json = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            print(f"[{idx}/{total_ids}] Fehler beim Dekodieren der Statistiken für Match-ID {match_id}.")
            continue

        # Entferne rekursiv alle "logo"-Einträge
        remove_keys(statistics_json, {"logo"})

        # Fixture-ID zur besseren Zuordnung hinzufügen
        statistics_json["fixture_id"] = match_id
        new_statistics.append(statistics_json)
        print(f"[{idx}/{total_ids}] Statistiken für Match-ID {match_id} abgerufen.")
        time.sleep(0.15)  # Kurze Pause zur Einhaltung der API-Limits

    conn.close()

    if new_statistics:
        existing_stats.extend(new_statistics)
        print(f"[{datetime.now()}] Es wurden {len(new_statistics)} neue Match-Statistiken hinzugefügt.")
    else:
        print(f"[{datetime.now()}] Für alle Match-IDs sind bereits Statistiken vorhanden.")

    # ---------------------------
    # 4) Ergebnisse in der Output-Datei speichern
    # ---------------------------
    output_data = {"response": existing_stats}
    with open(output_file_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    print(f"[{datetime.now()}] Alle Match-Statistiken wurden in '{output_file_path}' gespeichert.")

# ---------------------------
# Planung: Automatische Ausführung jeden Samstag, Sonntag und Montag um 00:01 Uhr
# ---------------------------
schedule.every().saturday.at("00:01").do(collect_match_statistics)
schedule.every().sunday.at("00:01").do(collect_match_statistics)
schedule.every().monday.at("00:01").do(collect_match_statistics)

print("Scheduler gestartet. Warte auf die nächsten Ausführungen ...")
while True:
    schedule.run_pending()
    time.sleep(60)  # Alle 60 Sekunden prüfen, ob ein geplanter Job fällig ist.
