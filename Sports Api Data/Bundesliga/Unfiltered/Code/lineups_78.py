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

def collect_lineups():
    print(f"[{datetime.now()}] Starte Abruf der Lineup-Daten ...")
    
    # ---------------------------
    # Pfade zu den Input- und Output-Dateien
    # ---------------------------
    fixtures_file_path = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"
    output_file_path = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/lineups_league_78.json"

    # ---------------------------
    # 1) Fixture-IDs aus der Input-Datei extrahieren
    # ---------------------------
    try:
        with open(fixtures_file_path, "r", encoding="utf-8") as f:
            fixtures_data = json.load(f)
        print(f"[{datetime.now()}] Fixture-Daten geladen.")
    except FileNotFoundError:
        print(f"[{datetime.now()}] FEHLER: Fixture-Datei '{fixtures_file_path}' nicht gefunden.")
        return

    fixture_ids = []
    for fixture in fixtures_data.get("response", []):
        fixture_info = fixture.get("fixture", {})
        fid = fixture_info.get("id")
        if fid is not None:
            fixture_ids.append(fid)
    print(f"[{datetime.now()}] Es wurden {len(fixture_ids)} Fixture-IDs gefunden.")

    # ---------------------------
    # 2) Bereits vorhandene Lineup-Daten laden (falls vorhanden)
    # ---------------------------
    try:
        with open(output_file_path, "r", encoding="utf-8") as f:
            existing_lineups_data = json.load(f)
            existing_lineups = existing_lineups_data.get("response", [])
        print(f"[{datetime.now()}] Es wurden {len(existing_lineups)} bestehende Lineup-Datensätze gefunden.")
    except FileNotFoundError:
        existing_lineups = []
        print(f"[{datetime.now()}] Keine bestehende Lineup-Datei gefunden. Eine neue Liste wird erstellt.")

    # Erstelle eine Menge mit bereits erfassten Fixture-IDs aus den vorhandenen Lineup-Daten
    existing_lineup_ids = set()
    for lineup in existing_lineups:
        fid = lineup.get("fixture_id")
        if fid is not None:
            existing_lineup_ids.add(fid)

    # ---------------------------
    # 3) Für jede Fixture-ID nur dann Lineup-Daten abrufen, wenn sie noch nicht vorhanden sind
    # ---------------------------
    conn = http.client.HTTPSConnection("v3.football.api-sports.io")
    headers = {
        'x-rapidapi-host': "v3.football.api-sports.io",
        'x-rapidapi-key': "5fa2372f2bfcbedb8ef7b85c86f0a27a"  # Ersetze diesen Schlüssel ggf. durch deinen
    }

    new_lineups = []
    total_ids = len(fixture_ids)
    for idx, fid in enumerate(fixture_ids, start=1):
        if fid in existing_lineup_ids:
            print(f"[{idx}/{total_ids}] Lineup für Fixture-ID {fid} existiert bereits, überspringe.")
            continue

        endpoint = f"/fixtures/lineups?fixture={fid}"
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        try:
            lineup_data = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            print(f"[{idx}/{total_ids}] Fehler beim Dekodieren der Lineup-Daten für Fixture-ID {fid}.")
            continue

        # Entferne rekursiv die Schlüssel "logo" und "photo"
        remove_keys(lineup_data, {"logo", "photo"})

        # Füge zur besseren Zuordnung die Fixture-ID hinzu
        lineup_data["fixture_id"] = fid
        new_lineups.append(lineup_data)
        print(f"[{idx}/{total_ids}] Lineup für Fixture-ID {fid} abgerufen.")
        time.sleep(0.15)  # Kurze Pause zur Einhaltung der API-Limits

    conn.close()

    if new_lineups:
        existing_lineups.extend(new_lineups)
        print(f"[{datetime.now()}] Es wurden {len(new_lineups)} neue Lineup-Datensätze hinzugefügt.")
    else:
        print(f"[{datetime.now()}] Für alle Fixture-IDs sind bereits Lineup-Daten vorhanden.")

    # ---------------------------
    # 4) Ergebnisse speichern
    # ---------------------------
    output_data = {"response": existing_lineups}
    with open(output_file_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    print(f"[{datetime.now()}] Alle Lineup-Daten wurden in '{output_file_path}' gespeichert.")

# ---------------------------
# Planung: Automatische Ausführung jeden Samstag, Sonntag und Montag um 00:00 Uhr
# ---------------------------
schedule.every().saturday.at("00:01").do(collect_lineups)
schedule.every().sunday.at("00:01").do(collect_lineups)
schedule.every().monday.at("00:01").do(collect_lineups)

print("Scheduler gestartet. Warte auf die nächsten Ausführungen ...")
while True:
    schedule.run_pending()
    time.sleep(60)  # Einmal pro Minute prüfen, ob ein geplanter Job fällig ist.
