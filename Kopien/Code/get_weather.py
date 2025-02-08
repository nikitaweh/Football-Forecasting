import os
import time
import requests
import pandas as pd

# Pfade zu den Eingabedateien und zum Output
historic_weather_file = "C:/AI Projekt/KI-Projekt/Hauptdateien/Datensammlungen/bereinigte_datei.csv"
team_location_file = "C:/AI Projekt/KI-Projekt/Hauptdateien/Datensammlungen/team_location.csv"
past_season_file = "C:/AI Projekt/KI-Projekt/Hauptdateien/Datensammlungen/past_season_results.csv"
output_csv_file = os.path.join("C:/AI Projekt/KI-Projekt/Hauptdateien/Datensammlungen", "historical_weather_data.csv")
city_coordinates_file = "C:/AI Projekt/KI-Projekt/Hauptdateien/Datensammlungen/city_coordinates.csv"

# OpenWeather API Key (wie von dir angegeben)
API_KEY = "8738a0031c3e965eaece939dbc7faf1d"

def get_weather_offsets(match_dt):
    """
    Gibt eine Liste von Timedelta-Offsets zurück, basierend auf der Kick-off-Zeit:
      - Bei Kick-off zu einer vollen Stunde (Minute == 0):
            Offsets: 0, +1h, +2h, +3h
      - Bei Kick-off zu einer halben Stunde (Minute == 30):
            Offsets: -30min, +30min, +90min, +150min
      - Andernfalls wird der Fall wie bei der vollen Stunde behandelt.
    """
    if match_dt.minute == 0:
        return [pd.Timedelta(hours=0),
                pd.Timedelta(hours=1),
                pd.Timedelta(hours=2),
                pd.Timedelta(hours=3)]
    elif match_dt.minute == 30:
        return [pd.Timedelta(minutes=-30),
                pd.Timedelta(minutes=30),
                pd.Timedelta(minutes=90),
                pd.Timedelta(minutes=150)]
    else:
        return [pd.Timedelta(hours=0),
                pd.Timedelta(hours=1),
                pd.Timedelta(hours=2),
                pd.Timedelta(hours=3)]
"""
def main():
    
    Verarbeitet alle Spieldaten aus past_season_file, deren Datum vor dem 04.01.2025 liegt,
    und erstellt daraus die CSV mithilfe der lokalen historischen Wetterdaten.
    Dabei werden fehlende Werte für Regen und Schnee durch 0 ersetzt.
    
    # 1. CSV-Dateien einlesen
    weather_df = pd.read_csv(historic_weather_file)
    team_location_df = pd.read_csv(team_location_file)
    past_results_df = pd.read_csv(past_season_file)
    
    # 2. Aufbereitung und Konvertierung der Datumsfelder in past_season_file
    past_results_df['Date'] = past_results_df['Date'].str.rstrip(',')
    past_results_df['Time'] = past_results_df['Time'].str.rstrip(',')
    past_results_df['Year'] = past_results_df['Year'].astype(str).str.rstrip(',')
    past_results_df['CombinedDate'] = past_results_df['Date'] + ',' + past_results_df['Year'] + ',' + past_results_df['Time']
    past_results_df['DateTime'] = pd.to_datetime(past_results_df['CombinedDate'], format="%A %d %B,%Y,%H:%M")
    
    # Filter: Nur Spiele, die vor dem 04.01.2025 liegen
    cutoff = pd.Timestamp("2025-01-04")
    past_results_df = past_results_df[past_results_df['DateTime'] < cutoff]
    
    # 3. Für weather_df: Entferne " +0000 UTC" aus der Spalte dt_iso und konvertiere in DateTime
    weather_df['dt_iso'] = weather_df['dt_iso'].str.replace(" +0000 UTC", "", regex=False)
    weather_df['DateTime'] = pd.to_datetime(weather_df['dt_iso'], format="%Y-%m-%d %H:%M:%S")
    
    # 4. Aufbereitung der Wetterdaten: Umbenennen der relevanten Spalten
    weather_df = weather_df.rename(columns={
        'city_name': 'City',
        'temp': 'Temperature (C)',
        'wind_speed': 'Wind Speed',
        'wind_deg': 'Wind Direction',
        'rain_1h': 'Rain',
        'snow_1h': 'Snow'
    })
    weather_df = weather_df[['City', 'DateTime', 'Temperature (C)', 'pressure', 'humidity',
                             'Wind Speed', 'Wind Direction', 'Rain', 'Snow']]
    weather_df = weather_df.rename(columns={'pressure': 'Pressure', 'humidity': 'Humidity'})
    
    # 4.1 Ersetze fehlende Werte für Regen und Schnee in den historischen Daten durch 0
    weather_df['Rain'] = weather_df['Rain'].fillna(0)
    weather_df['Snow'] = weather_df['Snow'].fillna(0)
    
    # 5. Merge mit den Team-Standorten (team_location_file hat die Spalten "Team Short" und "Stadt")
    results_with_city = past_results_df.merge(team_location_df, left_on='Home Team', right_on='Team Short', how='left')
    results_with_city = results_with_city.rename(columns={'Stadt': 'City'})
    
    # 6. Erzeuge für jeden Spiel-Datensatz (bis cutoff) die gewünschten Wetter-Zeitpunkte
    expanded_rows = []
    for idx, row in results_with_city.iterrows():
        match_dt = row['DateTime']
        offsets = get_weather_offsets(match_dt)
        for offset in offsets:
            new_row = row.copy()
            new_row['Weather_Request_Time'] = match_dt + offset
            expanded_rows.append(new_row)
    expanded_df = pd.DataFrame(expanded_rows)
    
    # 7. Exakten Merge mit weather_df (auf Basis von City und Weather_Request_Time)
    merged_df = pd.merge(expanded_df, weather_df,
                         left_on=['City', 'Weather_Request_Time'],
                         right_on=['City', 'DateTime'],
                         how='left')
    
    # 8. Gewünschte Spalten auswählen und umbenennen
    final_df = merged_df[['Match ID', 'Home Team', 'City', 'Weather_Request_Time',
                          'Temperature (C)', 'Pressure', 'Humidity',
                          'Wind Speed', 'Wind Direction', 'Rain', 'Snow']]
    final_df = final_df.rename(columns={'Weather_Request_Time': 'DateTime'})
    
    # 9. Formatierung der DateTime-Spalte in das gewünschte Format: "Wochentag Tag Monat,Jahr,Uhrzeit"
    final_df['DateTime'] = final_df['DateTime'].dt.strftime("%A %d %B,%Y,%H:%M")
    
    # 9.1 Entferne Duplikate, sodass jede Uhrzeit pro Spiel maximal einmal vorkommt
    final_df = final_df.drop_duplicates(subset=['Match ID', 'Home Team', 'City', 'DateTime'])
    
    # 10. Sicherstellen, dass der Zielordner existiert; andernfalls anlegen
    os.makedirs(os.path.dirname(output_csv_file), exist_ok=True)
    
    # 11. Ergebnis in CSV speichern (Überschreibt ggf. eine bestehende Datei)
    final_df.to_csv(output_csv_file, index=False)
    print("CSV-Datei (Spiele bis 04.01.2025) wurde erstellt:", output_csv_file)
"""
def query_api_data_by_match_id():
    """
    Liest die bestehende CSV (historical_weather_data.csv) ein und ermittelt anhand der
    Match ID den höchsten Eintrag. Anschließend werden aus past_season_results.csv alle Spiele
    ausgewählt, deren Match ID größer ist als dieser Wert. Für diese "neuen" Spiele wird dann
    wie gewohnt der Prozess (Merge mit Teamstandorten, Berechnung der Wetter-Zeitpunkte,
    API-Abfrage) durchgeführt und die neuen Zeilen werden an die CSV angehängt.
    Dabei wird in der API-Abfrage, falls kein Regen oder Schnee vorhanden ist, der Wert 0 gesetzt.
    """
    # 1. Bestehende CSV einlesen – hier explizit den Datentyp für "Match ID" setzen
    try:
        existing_df = pd.read_csv(output_csv_file, dtype={"Match ID": int})
    except FileNotFoundError:
        print("CSV-Datei existiert noch nicht. Bitte führe zuerst 'main()' aus.")
        return

    # Debug-Ausgabe: Welche Match IDs sind in der CSV enthalten?
    print("In der CSV gefundene Match IDs:", existing_df["Match ID"].unique())
    
    max_match_id = existing_df["Match ID"].max()
    print("Maximale Match ID in CSV:", max_match_id)
    
    # 2. past_season_results.csv laden und "Match ID" als Zahl erzwingen
    past_results_df = pd.read_csv(past_season_file, dtype={"Match ID": int})
    
    # Filter: Spiele, deren Match ID größer ist als max_match_id
    new_games_df = past_results_df[past_results_df["Match ID"] > max_match_id]
    if new_games_df.empty:
        print("Keine neuen Spiele gefunden, deren Match ID größer als", max_match_id, "ist.")
        return

    print("Neue Spiele (basierend auf Match ID) gefunden:", new_games_df["Match ID"].tolist())

    # 3. Merge mit team_location, um die Stadt (City) zu erhalten
    team_location_df = pd.read_csv(team_location_file)
    results_with_city = new_games_df.merge(team_location_df, left_on="Home Team", right_on="Team Short", how="left")
    results_with_city = results_with_city.rename(columns={"Stadt": "City"})
    
    # 4. Berechne für jedes Spiel den Timestamp (DateTime) aus den Spalten "Date", "Year" und "Time"
    results_with_city["Date"] = results_with_city["Date"].str.rstrip(',')
    results_with_city["Time"] = results_with_city["Time"].str.rstrip(',')
    results_with_city["Year"] = results_with_city["Year"].astype(str).str.rstrip(',')
    results_with_city["CombinedDate"] = results_with_city["Date"] + "," + results_with_city["Year"] + "," + results_with_city["Time"]
    try:
        results_with_city["DateTime"] = pd.to_datetime(results_with_city["CombinedDate"], format="%A %d %B,%Y,%H:%M")
    except Exception as e:
        print("Fehler beim Parsen der CombinedDate-Spalte in past_season_results.csv:", e)
        return

    # 5. Für jedes neue Spiel die gewünschten Wetter-Zeitpunkte berechnen
    expanded_rows = []
    for idx, row in results_with_city.iterrows():
        match_dt = row["DateTime"]
        offsets = get_weather_offsets(match_dt)
        for offset in offsets:
            new_row = row.copy()
            new_row["Weather_Request_Time"] = match_dt + offset
            expanded_rows.append(new_row)
    expanded_df = pd.DataFrame(expanded_rows)
    
    # 6. Lade city_coordinates.csv, um die Koordinaten zu erhalten
    try:
        coords_df = pd.read_csv(city_coordinates_file)
        city_coords = { row["City"].strip().lower(): (row["Latitude"], row["Longitude"]) 
                        for idx, row in coords_df.iterrows() }
    except Exception as e:
        print("Fehler beim Laden von city_coordinates.csv:", e)
        return

    # 7. Für jeden Datensatz aus expanded_df: API-Abfrage
    new_rows = []
    base_url = "https://history.openweathermap.org/data/2.5/history/city"
    for index, row in expanded_df.iterrows():
        city = row["City"]
        dt_obj = row["Weather_Request_Time"]
        unix_start = int(dt_obj.timestamp())
        unix_end = unix_start + 3600  # einstündiges Zeitfenster

        coords = city_coords.get(city.strip().lower())
        if not coords:
            print(f"Keine Koordinaten für Stadt {city} gefunden.")
            continue
        lat, lon = coords

        params = {
            "lat": lat,
            "lon": lon,
            "type": "hour",
            "start": unix_start,
            "end": unix_end,
            "appid": API_KEY,
            "units": "metric"
        }
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            weather_data = response.json()
        except Exception as e:
            print(f"Fehler bei der API-Abfrage für {city} um {dt_obj}: {e}")
            continue

        if "list" not in weather_data or not weather_data["list"]:
            print(f"Keine Daten in 'list' für {city} um {dt_obj}.")
            continue

        # Verwende den ersten Eintrag aus der Rückgabe
        record = weather_data["list"][0]
        main_data = record.get("main", {})
        wind_data = record.get("wind", {})
        temperature = main_data.get("temp")
        pressure = main_data.get("pressure")
        humidity = main_data.get("humidity")
        wind_speed = wind_data.get("speed")
        wind_deg = wind_data.get("deg")
        # Falls kein Regen/Schnee vorhanden ist, wird 0 gesetzt.
        rain = record.get("rain", {}).get("1h") if record.get("rain") else 0
        snow = record.get("snow", {}).get("1h") if record.get("snow") else 0

        new_row = {
            "Match ID": row["Match ID"],
            "Home Team": row["Home Team"],
            "City": city,
            "DateTime": dt_obj.strftime("%A %d %B,%Y,%H:%M"),
            "Temperature (C)": temperature,
            "Pressure": pressure,
            "Humidity": humidity,
            "Wind Speed": wind_speed,
            "Wind Direction": wind_deg,
            "Rain": rain,
            "Snow": snow
        }
        new_rows.append(new_row)
        time.sleep(1)  # Kurze Pause, um API-Rate-Limits zu schonen
    
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        new_df.to_csv(output_csv_file, mode='a', header=False, index=False)
        print(f"{len(new_df)} API-Daten wurden angehängt.")
    else:
        print("Keine neuen API-Daten abgerufen.")

    # Zum Abschluss: Lese die CSV neu ein und zeige die aktualisierte maximale Match ID
    updated_df = pd.read_csv(output_csv_file, dtype={"Match ID": int})
    print("Neue maximale Match ID in CSV:", updated_df["Match ID"].max())

if __name__ == '__main__':
#   main()
    query_api_data_by_match_id()
