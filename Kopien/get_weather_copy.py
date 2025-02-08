import csv
import requests
import os
from datetime import datetime, timedelta
import pandas as pd

# OpenWeatherMap API-Schlüssel
api_key = "8738a0031c3e965eaece939dbc7faf1d"

# Eingabedateien
historical_weather_file = "C:/AI Projekt/Webscraping/Hauptdateien/Supportdateien/Städte Wetterdaten/ec87034d1e01e441b93d5c488cad5e86.csv"
team_location_file = "C:/AI Projekt/Webscraping/Hauptdateien/Supportdateien/team_location.csv"
past_results_file = "C:/AI Projekt/Webscraping/Hauptdateien/past_season_results.csv"
city_coordinates_file = "C:/AI Projekt/Webscraping/Hauptdateien/Supportdateien/city_coordinates.csv"
output_csv_file = os.path.join("C:/AI Projekt/Webscraping/Hauptdateien/Supportdateien", "weather_data.csv")

# Sicherstellen, dass das Ausgabeverzeichnis existiert
if not os.path.exists(os.path.dirname(output_csv_file)):
    os.makedirs(os.path.dirname(output_csv_file))

# Spielzeit-Datumsbereiche extrahieren
def get_match_date_ranges():
    match_date_ranges = {}
    with open(past_results_file, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            home_team = row["Home Team"].strip()
            match_date = row["Date"].strip()
            match_time = row["Time"].strip()
            year = row["Year"].strip()
            try:
                match_datetime = datetime.strptime(f"{match_date} {year} {match_time}", "%A %d %B %Y %H:%M")
                match_date_ranges[match_datetime] = home_team
            except ValueError as e:
                print(f"Fehler beim Parsen des Datums: {match_date} {year} {match_time} -> {e}")
    return match_date_ranges

# Historische Wetterdaten laden und filtern
def load_historical_weather_optimized(match_date_ranges, team_to_city, file_path, chunksize=100000):
    historical_weather_data = []
    columns_to_read = [
        "city_name", "dt_iso", "temp", "pressure", "humidity", "wind_speed", "wind_deg", "rain_1h", "snow_1h"
    ]

    # Debugging-Schritt 2a: Erste Zeilen der Datei überprüfen
    test_chunk = pd.read_csv(file_path, nrows=10)  # Lade nur die ersten 10 Zeilen
    print("Erste Zeilen der Datei:")
    print(test_chunk.head())  # Ausgabe der ersten Zeilen zur Überprüfung

    # Verarbeitung der Datei in Blöcken
    for chunk in pd.read_csv(file_path, usecols=columns_to_read, chunksize=chunksize):
        chunk["dt_iso"] = pd.to_datetime(chunk["dt_iso"], format="%Y-%m-%d %H:%M:%S +0000 UTC", errors='coerce')
        chunk = chunk.dropna(subset=["dt_iso"])  # Entferne Zeilen mit ungültigen Datumsangaben

        for match_datetime, home_team in match_date_ranges.items():
            city = team_to_city.get(home_team)
            if not city:
                print(f"Stadt für Team {home_team} nicht gefunden.")
                continue

            print(f"Verarbeitung von Team: {home_team}, Stadt: {city}, Spielzeit: {match_datetime}")

            filtered_chunk = chunk[
                (chunk["city_name"] == city) &
                (chunk["dt_iso"].dt.date == match_datetime.date())
            ]

            print(f"Zeilen im Chunk: {len(chunk)}, Gefilterte Zeilen: {len(filtered_chunk)}")

            # Prüfe die Zeitfenster für jedes Spiel
            for _, row in filtered_chunk.iterrows():
                offsets = [-30, 30, 90, 150] if match_datetime.minute != 0 else [0, 60, 120, 180]
                for offset in offsets:  # Überprüfe Zeitpunkte entsprechend der Offsets
                    target_time = match_datetime + timedelta(minutes=offset)
                    if abs((row["dt_iso"] - target_time).total_seconds()) <= 1800:  # Toleranz von 30 Minuten
                        # Verhindere Duplikate
                        if not any(d["DateTime"] == row["dt_iso"].strftime("%Y-%m-%d %H:%M:%S") and d["Home Team"] == home_team for d in historical_weather_data):
                            historical_weather_data.append({
                                "Home Team": home_team,
                                "City": row["city_name"],
                                "DateTime": row["dt_iso"].strftime("%Y-%m-%d %H:%M:%S"),
                                "Temperature (C)": row["temp"],
                                "Pressure": row["pressure"],
                                "Humidity": row["humidity"],
                                "Wind Speed": row["wind_speed"],
                                "Wind Direction": row["wind_deg"],
                                "Rain": row.get("rain_1h", "0"),
                                "Snow": row.get("snow_1h", "0"),
                            })

    # Sortiere Wetterdaten chronologisch
    historical_weather_data.sort(key=lambda x: datetime.strptime(x["DateTime"], "%Y-%m-%d %H:%M:%S"))
    return historical_weather_data

# Team-Kürzel und Städtezuordnung laden
def load_team_to_city_mapping():
    team_to_city = {}
    with open(team_location_file, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            team = row["Team Short"].strip()
            city = row["Stadt"].strip()
            team_to_city[team] = city
    return team_to_city

# Koordinaten laden
def load_coordinates():
    coordinates = {}
    with open(city_coordinates_file, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            team = row["Team"].strip()
            coordinates[team] = {
                "City": row["City"].strip(),
                "Latitude": row["Latitude"].strip(),
                "Longitude": row["Longitude"].strip()
            }
    return coordinates

# Wetterdaten speichern in der gewünschten Reihenfolge
def save_weather_data(output_file, weather_data, match_date_ranges):
    with open(output_file, mode="w", encoding="utf-8", newline="") as file:
        # Definiere die Kopfzeile in der gewünschten Reihenfolge
        fieldnames = [
            "Home Team", "City", "DateTime", "Temperature (C)", "Pressure", "Humidity",
            "Wind Speed", "Wind Direction", "Rain", "Snow"
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        # Sortiere die Wetterdaten chronologisch
        weather_data.sort(key=lambda x: datetime.strptime(x["DateTime"], "%Y-%m-%d %H:%M:%S"))
        writer.writerows(weather_data)

# Neue Daten hinzufügen, ohne Duplikate
def append_new_weather_data(output_file, new_data):
    try:
        # Lese bestehende Daten
        existing_data = pd.read_csv(output_file)
        existing_data_set = set(
            zip(existing_data["Home Team"], existing_data["City"], existing_data["DateTime"])
        )

        # Neue Daten filtern
        filtered_new_data = [
            entry for entry in new_data
            if (entry["Home Team"], entry["City"], entry["DateTime"]) not in existing_data_set
        ]

        # Neue Daten anhängen
        if filtered_new_data:
            pd.DataFrame(filtered_new_data).to_csv(output_file, mode="a", header=False, index=False)
            print(f"{len(filtered_new_data)} neue Zeilen hinzugefügt.")
        else:
            print("Keine neuen Daten zum Hinzufügen.")
    except FileNotFoundError:
        # Wenn die Datei nicht existiert, speichere alle neuen Daten
        pd.DataFrame(new_data).to_csv(output_file, mode="w", header=True, index=False)
        print("Datei erstellt und alle Daten hinzugefügt.")
    except Exception as e:
        print(f"Fehler beim Hinzufügen der Daten: {e}")

# Hauptfunktion
def main():
    # Lade Datumsbereiche der Spiele
    match_date_ranges = get_match_date_ranges()

    # Lade Team-zu-Stadt-Mapping
    team_to_city = load_team_to_city_mapping()

    # Lade historische Wetterdaten und filtere sie nach den Spielzeiten
    historical_weather_data = load_historical_weather_optimized(match_date_ranges, team_to_city, historical_weather_file, chunksize=100000)
    coordinates = load_coordinates()

    # Ergebnisse und Wetterdaten verarbeiten
    weather_data_output = historical_weather_data

    # Neue Daten anhängen
    append_new_weather_data(output_csv_file, weather_data_output)

    # API-Integration für zusätzliche Wetterdaten
    existing_keys = set(
        (entry["Home Team"], entry["City"], entry["DateTime"]) for entry in weather_data_output
    )

    with open(past_results_file, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            home_team = row["Home Team"].strip()
            match_date = row["Date"].strip()
            match_time = row["Time"].strip()
            year = row["Year"].strip()

            try:
                match_datetime = datetime.strptime(f"{match_date} {year} {match_time}", "%A %d %B %Y %H:%M")
                hours_to_fetch = [-0.5, 0.5, 1.5, 2.5] if match_datetime.minute != 0 else [0, 1, 2, 3]
            except ValueError as ve:
                print(f"Fehler beim Parsen des Datums: {match_date} {year} {match_time} -> {ve}")
                continue

            # Überprüfen, ob das Spieldatum innerhalb von 7 Tagen vor dem aktuellen Datum liegt
            if (datetime.now() - match_datetime).days > 7:
                print(f"Spiel am {match_datetime} liegt außerhalb der API-Abfragedauer von 7 Tagen.")
                continue

            if home_team in coordinates:
                lat = coordinates[home_team]["Latitude"]
                lon = coordinates[home_team]["Longitude"]
                city = coordinates[home_team]["City"]
            else:
                print(f"Keine Koordinaten für {home_team} gefunden. Überprüfen Sie die Datei city_coordinates.csv.")
                continue

            for hour_offset in hours_to_fetch:
                target_datetime = match_datetime + timedelta(hours=hour_offset)
                formatted_datetime = target_datetime.strftime("%Y-%m-%d %H:%M:%S")
                entry_key = (home_team, city, formatted_datetime)

                if entry_key in existing_keys:
                    continue

                start_time = int(target_datetime.timestamp())
                end_time = int((target_datetime + timedelta(hours=1)).timestamp())

                params = {
                    "lat": lat,
                    "lon": lon,
                    "type": "hour",
                    "start": start_time,
                    "end": end_time,
                    "units": "metric",
                    "appid": api_key
                }

                try:
                    response = requests.get("http://history.openweathermap.org/data/2.5/history/city", params=params)
                    response.raise_for_status()
                    data = response.json()
                    for entry in data.get("list", []):
                        timestamp = datetime.fromtimestamp(entry["dt"]).strftime("%Y-%m-%d %H:%M:%S")
                        data_entry = {
                            "Home Team": home_team,
                            "City": city,
                            "DateTime": timestamp,
                            "Temperature (C)": entry["main"].get("temp", "N/A"),
                            "Pressure": entry["main"].get("pressure", "N/A"),
                            "Humidity": entry["main"].get("humidity", "N/A"),
                            "Wind Speed": entry["wind"].get("speed", "N/A"),
                            "Wind Direction": entry["wind"].get("deg", "N/A"),
                            "Rain": entry.get("rain", {}).get("1h", "0"),
                            "Snow": entry.get("snow", {}).get("1h", "0"),
                        }
                        if entry_key not in existing_keys:
                            weather_data_output.append(data_entry)
                            existing_keys.add(entry_key)
                    print(f"Wetterdaten für {home_team} erfolgreich abgerufen: Stunde {hour_offset}.")
                except requests.exceptions.RequestException as e:
                    print(f"Fehler bei der API-Anfrage für {home_team}: {e}")
                    
if __name__ == "__main__":
    main()
