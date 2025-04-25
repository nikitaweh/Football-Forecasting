import os
import time
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Pfade zu den Eingabe- und Ausgabedateien
# ---------------------------
historic_weather_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/bereinigte_datei.csv"
stammdaten_file       = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/Stammdaten_78.csv"
city_coordinates_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/city_coordinates_78.csv"
output_csv_file       = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/historical_weather_data_78.csv"

# ---------------------------
# OpenWeather API Key und History-Endpoint
# ---------------------------
API_KEY  = "8738a0031c3e965eaece939dbc7faf1d"
BASE_URL = "https://history.openweathermap.org/data/2.5/history/city"

# ---------------------------
# Hilfsfunktion: Wetter-Offsets je nach Anstoßzeit
# ---------------------------
def get_weather_offsets(match_dt):
    if match_dt.minute == 0:
        return [pd.Timedelta(hours=h) for h in (0, 1, 2, 3)]
    elif match_dt.minute == 30:
        return [pd.Timedelta(minutes=m) for m in (-30, 30, 90, 150)]
    elif match_dt.minute == 45:
        return [pd.Timedelta(minutes=m) for m in (-45, 15, 75, 135)]
    else:
        return [pd.Timedelta(hours=h) for h in (0, 1, 2, 3)]

# ---------------------------
# Hilfsfunktion: Eine Wetter-Abfrage durchführen (History/city)
# ---------------------------
def fetch_weather(lat, lon, dt_local):
    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=ZoneInfo("Europe/Berlin"))
    ts = int(dt_local.astimezone(ZoneInfo("UTC")).timestamp())
    params = {
        "lat": lat,
        "lon": lon,
        "type": "hour",
        "start": ts,
        "end":   ts + 3600,
        "appid": API_KEY
    }
    resp = requests.get(BASE_URL, params=params)
    resp.raise_for_status()
    data = resp.json().get("list", [])
    if not data:
        return {"Temperature (C)": None, "Pressure": None, "Humidity": None,
                "Wind Speed": None, "Wind Direction": None, "Rain": 0, "Snow": 0}
    rec = data[0]
    main = rec.get("main", {})
    wind = rec.get("wind", {})
    return {
        "Temperature (C)": main.get("temp"),
        "Pressure":        main.get("pressure"),
        "Humidity":        main.get("humidity"),
        "Wind Speed":      wind.get("speed"),
        "Wind Direction":  wind.get("deg"),
        "Rain":            rec.get("rain", {}).get("1h", 0),
        "Snow":            rec.get("snow", {}).get("1h", 0)
    }
  
# ---------------------------
# main(): Erzeugt die Basis-CSV aus lokalen historischen Wetterdaten
# ---------------------------
"""
def main():
    print("Erzeuge Basis-CSV …")
    # 1) Lokale historische Wetterdaten einlesen
    weather_df = pd.read_csv(historic_weather_file)

    # 2) Stammdaten einlesen und DateTime kombinieren
    stam_df = pd.read_csv(stammdaten_file, dtype={"Match_ID": int})
    stam_df['DateTime'] = pd.to_datetime(stam_df['Date'] + ' ' + stam_df['Time'])
    # Spiele vor 4. Januar 2025
    stam_df = stam_df[stam_df['DateTime'] < pd.Timestamp("2025-01-04")]

    # 3) Aufbereitung der lokalen Wetterdaten
    weather_df['dt_iso'] = weather_df['dt_iso'].str.replace(" +0000 UTC", "", regex=False)
    weather_df['DateTime'] = pd.to_datetime(weather_df['dt_iso'], format="%Y-%m-%d %H:%M:%S")
    weather_df = weather_df.rename(columns={
        'city_name':'City', 'temp':'Temperature (C)', 'pressure':'Pressure',
        'humidity':'Humidity','wind_speed':'Wind Speed','wind_deg':'Wind Direction',
        'rain_1h':'Rain','snow_1h':'Snow'
    })[['City','DateTime','Temperature (C)','Pressure','Humidity','Wind Speed','Wind Direction','Rain','Snow']]
    weather_df[['Rain','Snow']] = weather_df[['Rain','Snow']].fillna(0)

    # 4) Merge Stammdaten mit Stadt-Koordinaten
    coords_df = pd.read_csv(city_coordinates_file)
    merged = stam_df.merge(coords_df, left_on='Home Team', right_on='Team', how='left')

    # 5) Erzeuge Abfrage-Zeitpunkte
    recs = []
    for _, row in merged.iterrows():
        for off in get_weather_offsets(row['DateTime']):
            rec = row.to_dict()
            rec['Weather_Request_Time'] = row['DateTime'] + off
            recs.append(rec)
    exp = pd.DataFrame(recs)

    # 6) Merge mit lokalen Wetterdaten
    final = exp.merge(
        weather_df,
        left_on=['City','Weather_Request_Time'],
        right_on=['City','DateTime'],
        how='left'
    )

    # 7) Auswahl und Speicherung
    out = final[['Match_ID','Home Team','City','Weather_Request_Time',
                 'Temperature (C)','Pressure','Humidity',
                 'Wind Speed','Wind Direction','Rain','Snow']]
    out = out.rename(columns={'Weather_Request_Time':'DateTime'})
    out['DateTime'] = out['DateTime'].dt.strftime("%A %d %B,%Y,%H:%M")
    out = out.drop_duplicates(subset=['Match_ID','Home Team','City','DateTime'])

    os.makedirs(os.path.dirname(output_csv_file), exist_ok=True)
    out.to_csv(output_csv_file, index=False)
    print("Basis-CSV erstellt:", output_csv_file)
"""
# ---------------------------
# Aktualisierung: Neue API-Daten anhängen
# ---------------------------
def query_api_data_by_match_id():
    if not os.path.exists(output_csv_file):
        print("historical_weather_data.csv fehlt – bitte zuerst main() ausführen.")
        return

    exist_df = pd.read_csv(output_csv_file, dtype={"Match_ID": int})
    max_id = exist_df['Match_ID'].max()
    print(f"Max Match_ID in CSV: {max_id}")

    stam_df = pd.read_csv(stammdaten_file, dtype={"Match_ID": int})
    stam_df['DateTime'] = pd.to_datetime(stam_df['Date'] + ' ' + stam_df['Time'])
    now = datetime.now()
    stam_df = stam_df[stam_df['DateTime'] < now]

    new_games = stam_df[stam_df['Match_ID'] > max_id]
    if new_games.empty:
        print("Keine neuen Spiele gefunden.")
        return
    print(f"Neue Spiele: {new_games['Match_ID'].tolist()}")

    coords_df = pd.read_csv(city_coordinates_file)
    merged = new_games.merge(coords_df, left_on='Home Team', right_on='Team', how='left')

    api_rows = []
    for _, row in merged.iterrows():
        for off in get_weather_offsets(row['DateTime']):
            dt_req = row['DateTime'] + off
            print(f"Hole Wetterdaten für Match {row['Match_ID']} um {dt_req}")
            w = fetch_weather(row['Latitude'], row['Longitude'], dt_req)
            api_rows.append({
                'Match_ID':      row['Match_ID'],
                'Home Team':     row['Home Team'],
                'City':          row['City'],
                'DateTime':      dt_req,
                'Temperature (C)': w.get('Temperature (C)'),
                'Pressure':        w.get('Pressure'),
                'Humidity':        w.get('Humidity'),
                'Wind Speed':      w.get('Wind Speed'),
                'Wind Direction':  w.get('Wind Direction'),
                'Rain':            w.get('Rain'),
                'Snow':            w.get('Snow')
            })

    if api_rows:
        new_df = pd.DataFrame(api_rows)
        new_df['DateTime'] = new_df['DateTime'].dt.strftime("%A %d %B,%Y,%H:%M")
        new_df.to_csv(output_csv_file, mode='a', header=False, index=False)
        print(f"{len(new_df)} neue Zeilen angehängt. Neue Max Match_ID: {new_df['Match_ID'].max()}")
    else:
        print("Keine neuen API-Daten abgerufen.")

# ---------------------------
# Scheduler Setup
# ---------------------------
if __name__ == "__main__":
    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(
        query_api_data_by_match_id,
        trigger=CronTrigger(day_of_week="sat,sun,mon", hour="3", minute="0")
    )
    print(f"Scheduler gestartet – läuft samstags, sonntags & montags um 03:00 Uhr (Europe/Berlin)")
    sched.start()
