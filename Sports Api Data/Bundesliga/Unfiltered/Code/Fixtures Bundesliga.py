import schedule
import time
import http.client
import json
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

def collect_fixtures():
    # Feste League ID
    league_id = 78

    # Definierter Speicherpfad für die JSON-Datei
    output_file_path = "C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"

    # Bestehende Fixture-Daten laden, falls die Datei existiert
    try:
        with open(output_file_path, "r", encoding="utf-8") as f:
            output_data = json.load(f)
            existing_fixtures = output_data.get("response", [])
        print(f"[{datetime.now()}] Es wurden {len(existing_fixtures)} bestehende Fixtures gefunden.")
    except FileNotFoundError:
        existing_fixtures = []
        print(f"[{datetime.now()}] Es wurde keine bestehende Datei gefunden. Eine neue Liste wird erstellt.")

    # Erstelle eine Menge mit bereits vorhandenen Fixture-IDs, basierend darauf, dass die ID unter fixture["fixture"]["id"] vorliegt
    existing_ids = set()
    for fixture in existing_fixtures:
        try:
            fixture_id = fixture["fixture"]["id"]
            existing_ids.add(fixture_id)
        except KeyError:
            # Falls die Struktur abweicht, wird die ID nicht berücksichtigt.
            pass

    # Definiere Seasons ab 2017 bis zum aktuellen Jahr
    current_year = datetime.now().year
    seasons = list(range(2017, current_year + 1))

    # Aufbau der HTTPS-Verbindung zur API
    conn = http.client.HTTPSConnection("v3.football.api-sports.io")
    headers = {
        'x-rapidapi-host': "v3.football.api-sports.io",
        'x-rapidapi-key': "5fa2372f2bfcbedb8ef7b85c86f0a27a"
    }

    # Für jede Season werden neue Fixtures abgefragt und es wird überprüft,
    # ob die Fixture anhand ihrer ID bereits in der bestehenden Liste vorhanden ist.
    for season in seasons:
        endpoint = f"/fixtures?league={league_id}&season={season}"
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        fixtures_data = json.loads(data.decode("utf-8"))
    
        fixtures = fixtures_data.get("response", [])
        new_fixtures = []
        if fixtures:
            for fixture in fixtures:
                remove_keys(fixture, {"logo", "flag"})
                try:
                    fixture_id = fixture["fixture"]["id"]
                except KeyError:
                    fixture_id = None
                if fixture_id is not None:
                    if fixture_id not in existing_ids:
                        new_fixtures.append(fixture)
                        existing_ids.add(fixture_id)
                else:
                    if fixture not in existing_fixtures:
                        new_fixtures.append(fixture)
            if new_fixtures:
                existing_fixtures.extend(new_fixtures)
                print(f"[{datetime.now()}] Es wurden {len(new_fixtures)} neue Fixtures für Liga {league_id} in der Saison {season} gefunden.")
            else:
                print(f"[{datetime.now()}] Für Liga {league_id} in der Saison {season} wurden keine neuen Fixtures gefunden.")
        else:
            print(f"[{datetime.now()}] Für Liga {league_id} in der Saison {season} wurden keine Fixtures gefunden.")
    
    # Erstelle ein Dictionary für die finale Ausgabe
    output_data = {"response": existing_fixtures}
    
    # Speichern der Fixture-Daten in der JSON-Datei
    with open(output_file_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    
    print(f"[{datetime.now()}] Alle Fixture-Daten für Liga {league_id} wurden in '{output_file_path}' gespeichert.")

# Planung: Führe die Funktion jeden Samstag, Sonntag und Montag um 00:00 Uhr aus
schedule.every().saturday.at("00:00").do(collect_fixtures)
schedule.every().sunday.at("00:00").do(collect_fixtures)
schedule.every().monday.at("00:00").do(collect_fixtures)

print("Scheduler gestartet. Warte auf die nächsten Termine...")

# Endlosschleife, die den Scheduler am Laufen hält
while True:
    schedule.run_pending()
    time.sleep(60)  # Prüft einmal pro Minute, ob ein Termin ansteht.
