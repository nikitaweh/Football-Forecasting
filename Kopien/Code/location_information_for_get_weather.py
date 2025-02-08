import csv
import requests
import os

# OpenWeatherMap API-Schlüssel
api_key = "3820fa176fb1bbea6f35ea43ae9f2d1c"

# Pfad zur Eingabe-CSV-Datei
input_csv_file = "C:/AI Projekt/KI-Projekt/Kopien/Datensammlungen/team_location.csv"

# Pfad zur Ausgabe-CSV-Datei (in Supportdateien speichern)
output_directory = "C:/AI Projekt/KI-Projekt/Kopien/Datensammlungen"
output_csv_file = os.path.join(output_directory, "city_coordinates.csv")

# Sicherstellen, dass der Ausgabepfad existiert
if not os.path.exists(output_directory):
    os.makedirs(output_directory)

# Ergebnisse speichern
city_coordinates = []

# CSV-Datei einlesen und Geodaten abrufen
with open(input_csv_file, mode="r", encoding="utf-8") as file:
    reader = csv.DictReader(file)
    for row in reader:
        team = row["Team Short"]
        city = row["Stadt"]

        # Anfrage an die Geocoding API
        geo_url = "http://api.openweathermap.org/geo/1.0/direct"
        params = {
            "q": city,
            "limit": 1,
            "appid": api_key
        }

        response = requests.get(geo_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = data[0]["lat"]
                lon = data[0]["lon"]
                city_coordinates.append({"Team": team, "City": city, "Latitude": lat, "Longitude": lon})
                print(f"{city}: {lat}, {lon}")
            else:
                print(f"Keine Geodaten für {city}")
        else:
            print(f"Fehler bei {city}: {response.status_code}")

# Ergebnisse in einer neuen CSV-Datei speichern
with open(output_csv_file, mode="w", encoding="utf-8", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=["Team", "City", "Latitude", "Longitude"])
    writer.writeheader()
    writer.writerows(city_coordinates)

print(f"Koordinaten wurden erfolgreich in {output_csv_file} gespeichert.")