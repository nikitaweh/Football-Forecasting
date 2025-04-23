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

# Pfad zur leagues_all.json und zum Output
leagues_file_path = "C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/Bundesliga.json"
output_file_path = "C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/Bundesliga Teams.json"

# Liga-IDs aus der Datei extrahieren
with open(leagues_file_path, "r", encoding="utf-8") as f:
    leagues_data = json.load(f)

league_ids = []
for item in leagues_data.get("response", []):
    league_info = item.get("league", {})
    league_id = league_info.get("id")
    if league_id is not None:
        league_ids.append(league_id)

# Duplikate entfernen (falls vorhanden)
league_ids = list(set(league_ids))
print(f"Gefundene Liga-IDs: {league_ids}")

# Definiere Seasons ab 2017 bis zum aktuellen Jahr
current_year = datetime.now().year
seasons = list(range(2017, current_year + 1))
print(f"Abzufragende Seasons: {seasons}")

all_teams = []  # Liste zum Sammeln aller Team-Daten

# Aufbau der HTTPS-Verbindung zur API
conn = http.client.HTTPSConnection("v3.football.api-sports.io")
headers = {
    'x-rapidapi-host': "v3.football.api-sports.io",
    'x-rapidapi-key': "5fa2372f2bfcbedb8ef7b85c86f0a27a"
}

# Für jede Liga und jede Season einen API-Call durchführen (ohne Pagination)
for league_id in league_ids:
    for season in seasons:
        endpoint = f"/teams?league={league_id}&season={season}"
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        json_data = json.loads(data.decode("utf-8"))
        
        teams = json_data.get("response", [])
        if teams:
            print(f"Liga {league_id}, Saison {season}: {len(teams)} Teams gefunden.")
            all_teams.extend(teams)
        else:
            print(f"Liga {league_id}, Saison {season}: Keine Teams gefunden.")

# Entferne rekursiv die Schlüssel "logo" und "image" aus den Team-Daten
for team in all_teams:
    remove_keys(team, {"logo", "image"})

# Duplikate entfernen – anhand der internen Team-ID (angenommen, sie befindet sich in entry["team"]["id"])
unique_teams = {}
for entry in all_teams:
    team_info = entry.get("team", {})
    team_id = team_info.get("id")
    if team_id is not None:
        # Nur einmal speichern
        if team_id not in unique_teams:
            unique_teams[team_id] = entry

# Zusammenführen der eindeutigen Teams in einem Dictionary
output_data = {"response": list(unique_teams.values())}

# Speichern der Daten in einer JSON-Datei im gewünschten Pfad
with open(output_file_path, "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=4)

print(f"Alle eindeutigen Team-Daten aus allen Ligen wurden in '{output_file_path}' gespeichert.")
