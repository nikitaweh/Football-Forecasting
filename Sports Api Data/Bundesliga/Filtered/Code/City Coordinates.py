import json
import csv
import requests
import os
import time

# OpenWeatherMap API-Schlüssel
api_key = "3820fa176fb1bbea6f35ea43ae9f2d1c"

# Pfad zur Eingabe‑JSON-Datei mit den Bundesliga‑Teams
input_json_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/Bundesliga Teams.json"

# Pfad zum Ausgabe‑Ordner und zur Ausgabe‑CSV-Datei
output_directory = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection"
output_csv_file  = os.path.join(output_directory, "city_coordinates_78.csv")

# Sicherstellen, dass das Ausgabeverzeichnis existiert
os.makedirs(output_directory, exist_ok=True)

# Override‑Mapping für spezielle Team‑City‑Paare
city_overrides = {
    "Bayern München":           "Munich",
    "1899 Hoffenheim":          "Hoffenheim",
    "Eintracht Frankfurt":      "Frankfurt",
    "1. FC Heidenheim":         "Heidenheim",
    "Borussia Mönchengladbach": "Gladbach",
    "1.FC Köln":                "Cologne",
    "Hannover 96":              "Hanover",
    "1. FC Nürnberg":           "Nuremberg",
}

# 1) JSON‑Datei einlesen und Team‑City‑Paare sammeln
with open(input_json_file, "r", encoding="utf-8") as f:
    data = json.load(f)

teams_list = data.get("response", [])
team_city_list = []
for entry in teams_list:
    team_name = entry.get("team", {}).get("name")
    city      = entry.get("venue", {}).get("city")
    if not team_name:
        continue

    # Override anwenden, falls vorhanden
    city = city_overrides.get(team_name, city)

    if city:
        team_city_list.append((team_name, city))

# 2) Für jede Stadt die Geokoordinaten abfragen
city_coordinates = []
for team, city in team_city_list:
    geo_url = "http://api.openweathermap.org/geo/1.0/direct"
    params  = {"q": city, "limit": 1, "appid": api_key}
    try:
        resp = requests.get(geo_url, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json()
        if results:
            lat = results[0].get("lat")
            lon = results[0].get("lon")
            city_coordinates.append({
                "Team"     : team,
                "City"     : city,
                "Latitude" : lat,
                "Longitude": lon
            })
            print(f"{team} – {city}: {lat}, {lon}")
        else:
            print(f"Keine Geodaten für {team} ({city}) gefunden.")
    except Exception as e:
        print(f"Fehler bei der Abfrage für {team} ({city}): {e}")

# 3) Ergebnisse in die CSV schreiben
with open(output_csv_file, mode="w", encoding="utf-8", newline="") as csvfile:
    fieldnames = ["Team", "City", "Latitude", "Longitude"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(city_coordinates)

print(f"\nKoordinaten wurden erfolgreich in '{output_csv_file}' gespeichert.")
