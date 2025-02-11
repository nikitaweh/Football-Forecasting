import os
import time
import requests
import pandas as pd

# Definiere den Basisordner für alle Dateien
base_dir = "C:/AI Projekt/KI-Projekt/Kopien/Datensammlungen"

# Pfade zu den Eingabedateien und zum Output
historic_weather_file = os.path.join(base_dir, "bereinigte_datei.csv")
team_location_file = os.path.join(base_dir, "team_location.csv")
past_season_file = os.path.join(base_dir, "past_season_results.csv")
city_coordinates_file = os.path.join(base_dir, "city_coordinates.csv")
output_csv_file = os.path.join(base_dir, "historical_weather_data.csv")

# OpenWeather API Key
API_KEY = "8738a0031c3e965eaece939dbc7faf1d"

def get_weather_offsets(match_dt):
    if match_dt.minute == 0:
        return [pd.Timedelta(hours=0), pd.Timedelta(hours=1), pd.Timedelta(hours=2), pd.Timedelta(hours=3)]
    elif match_dt.minute == 30:
        return [pd.Timedelta(minutes=-30), pd.Timedelta(minutes=30), pd.Timedelta(minutes=90), pd.Timedelta(minutes=150)]
    else:
        return [pd.Timedelta(hours=0), pd.Timedelta(hours=1), pd.Timedelta(hours=2), pd.Timedelta(hours=3)]

def main():
    """
    Verarbeitet alle Spieldaten aus past_season_file (vor 04.01.2025) und erstellt die CSV
    mithilfe der lokalen historischen Wetterdaten. Fehlende Regen-/Schnee-Werte werden durch 0 ersetzt.
    """
    # 1. CSV-Dateien einlesen
    weather_df = pd.read_csv(historic_weather_file)
    team_location_df = pd.read_csv(team_location_file)
    past_results_df = pd.read_csv(past_season_file)
    
    # 2. Datum aufbereiten
    past_results_df['Date'] = past_results_df['Date'].str.rstrip(',')
    past_results_df['Time'] = past_results_df['Time'].str.rstrip(',')
    past_results_df['Year'] = past_results_df['Year'].astype(str).str.rstrip(',')
    past_results_df['CombinedDate'] = past_results_df['Date'] + ',' + past_results_df['Year'] + ',' + past_results_df['Time']
    past_results_df['DateTime'] = pd.to_datetime(past_results_df['CombinedDate'], format="%A %d %B,%Y,%H:%M")
    
    cutoff = pd.Timestamp("2025-01-04")
    past_results_df = past_results_df[past_results_df['DateTime'] < cutoff]
    
    # 3. Weather-Daten vorbereiten
    weather_df['dt_iso'] = weather_df['dt_iso'].str.replace(" +0000 UTC", "", regex=False)
    weather_df['DateTime'] = pd.to_datetime(weather_df['dt_iso'], format="%Y-%m-%d %H:%M:%S")
    
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
    
    # 4. Fehlende Regen-/Schnee-Werte ersetzen
    weather_df['Rain'] = weather_df['Rain'].fillna(0)
    weather_df['Snow'] = weather_df['Snow'].fillna(0)
    
    # 5. Merge mit Team-Standorten
    results_with_city = past_results_df.merge(team_location_df, left_on='Home Team', right_on='Team Short', how='left')
    results_with_city = results_with_city.rename(columns={'Stadt': 'City'})
    
    # 6. Wetter-Zeitpunkte berechnen
    expanded_rows = []
    for idx, row in results_with_city.iterrows():
        match_dt = row['DateTime']
        offsets = get_weather_offsets(match_dt)
        for offset in offsets:
            new_row = row.copy()
            new_row['Weather_Request_Time'] = match_dt + offset
            expanded_rows.append(new_row)
    expanded_df = pd.DataFrame(expanded_rows)
    
    # 7. Merge mit den Wetterdaten
    merged_df = pd.merge(expanded_df, weather_df,
                         left_on=['City', 'Weather_Request_Time'],
                         right_on=['City', 'DateTime'],
                         how='left')
    
    # 8. Spalten auswählen und umbenennen
    final_df = merged_df[['Match ID', 'Home Team', 'City', 'Weather_Request_Time',
                          'Temperature (C)', 'Pressure', 'Humidity',
                          'Wind Speed', 'Wind Direction', 'Rain', 'Snow']]
    final_df = final_df.rename(columns={'Weather_Request_Time': 'DateTime'})
    
    final_df['DateTime'] = final_df['DateTime'].dt.strftime("%A %d %B,%Y,%H:%M")
    final_df = final_df.drop_duplicates(subset=['Match ID', 'Home Team', 'City', 'DateTime'])
    
    # Sicherstellen, dass der Ordner existiert
    os.makedirs(os.path.dirname(output_csv_file), exist_ok=True)
    
    final_df.to_csv(output_csv_file, index=False)
    print("CSV-Datei (Spiele bis 04.01.2025) wurde erstellt:", output_csv_file)

def query_api_data_by_match_id():
    """
    Liest die bestehende CSV ein, ermittelt anhand der Match ID den höchsten Wert, und
    verarbeitet alle Spiele aus past_season_results.csv mit einer höheren Match ID. Anschließend
    werden die neuen Zeilen (mit API-Daten, Regen/Schnee = 0, falls nicht vorhanden) an die CSV angehängt.
    """
    try:
        existing_df = pd.read_csv(output_csv_file, dtype={"Match ID": int})
    except FileNotFoundError:
        print("CSV-Datei existiert noch nicht. Bitte führe zuerst 'main()' aus.")
        return

    print("In der CSV gefundene Match IDs:", existing_df["Match ID"].unique())
    max_match_id = existing_df["Match ID"].max()
    print("Maximale Match ID in CSV:", max_match_id)
    
    past_results_df = pd.read_csv(past_season_file, dtype={"Match ID": int})
    print("Maximale Match ID in past_season_results.csv:", past_results_df["Match ID"].max())
    
    new_games_df = past_results_df[past_results_df["Match ID"] > max_match_id]
    if new_games_df.empty:
        print("Keine neuen Spiele gefunden, deren Match ID größer als", max_match_id, "ist.")
        return

    print("Neue Spiele gefunden:", new_games_df["Match ID"].tolist())

    team_location_df = pd.read_csv(team_location_file)
    results_with_city = new_games_df.merge(team_location_df, left_on="Home Team", right_on="Team Short", how="left")
    results_with_city = results_with_city.rename(columns={"Stadt": "City"})
    
    results_with_city["Date"] = results_with_city["Date"].str.rstrip(',')
    results_with_city["Time"] = results_with_city["Time"].str.rstrip(',')
    results_with_city["Year"] = results_with_city["Year"].astype(str).str.rstrip(',')
    results_with_city["CombinedDate"] = results_with_city["Date"] + "," + results_with_city["Year"] + "," + results_with_city["Time"]
    try:
        results_with_city["DateTime"] = pd.to_datetime(results_with_city["CombinedDate"], format="%A %d %B,%Y,%H:%M")
    except Exception as e:
        print("Fehler beim Parsen der CombinedDate-Spalte:", e)
        return

    expanded_rows = []
    for idx, row in results_with_city.iterrows():
        match_dt = row["DateTime"]
        offsets = get_weather_offsets(match_dt)
        for offset in offsets:
            new_row = row.copy()
            new_row["Weather_Request_Time"] = match_dt + offset
            expanded_rows.append(new_row)
    expanded_df = pd.DataFrame(expanded_rows)
    
    try:
        coords_df = pd.read_csv(city_coordinates_file)
        city_coords = { row["City"].strip().lower(): (row["Latitude"], row["Longitude"])
                        for idx, row in coords_df.iterrows() }
    except Exception as e:
        print("Fehler beim Laden von city_coordinates.csv:", e)
        return

    new_rows = []
    base_url = "https://history.openweathermap.org/data/2.5/history/city"
    for index, row in expanded_df.iterrows():
        city = row["City"]
        dt_obj = row["Weather_Request_Time"]
        unix_start = int(dt_obj.timestamp())
        unix_end = unix_start + 3600

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

        record = weather_data["list"][0]
        main_data = record.get("main", {})
        wind_data = record.get("wind", {})
        temperature = main_data.get("temp")
        pressure = main_data.get("pressure")
        humidity = main_data.get("humidity")
        wind_speed = wind_data.get("speed")
        wind_deg = wind_data.get("deg")
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
        time.sleep(1)
    
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        new_df.to_csv(output_csv_file, mode='a', header=False, index=False)
        print(f"{len(new_df)} API-Daten wurden angehängt.")
    else:
        print("Keine neuen API-Daten abgerufen.")

    updated_df = pd.read_csv(output_csv_file, dtype={"Match ID": int})
    print("Neue maximale Match ID in CSV:", updated_df["Match ID"].max())

if __name__ == '__main__':
    main()
    query_api_data_by_match_id()
