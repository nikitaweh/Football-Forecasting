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
def _last_sunday(year, month):
    day = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
    while day.weekday() != 6:
        day -= pd.Timedelta(days=1)
    return day

def _adjust_request_time(dt_local):
    year = dt_local.year
    tz = ZoneInfo("Europe/Berlin")
    start = _last_sunday(year, 3).replace(
        hour=3, minute=0, second=0, microsecond=0, tzinfo=tz
    )
    end = _last_sunday(year, 10).replace(
        hour=1, minute=59, second=59, microsecond=999, tzinfo=tz
    )
    if start <= dt_local <= end:
        return dt_local - pd.Timedelta(hours=2)
    return dt_local - pd.Timedelta(hours=1)

def fetch_weather(lat, lon, dt_local):
    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=ZoneInfo("Europe/Berlin"))
    dt_local = _adjust_request_time(dt_local)
    ts = int(dt_local.astimezone(ZoneInfo("UTC")).timestamp())
    params = {
        "lat": lat,
        "lon": lon,
        "type": "hour",
        "start": ts,
        "end":   ts + 3600,
        "appid": API_KEY,
        "units": "metric"
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
def main(overwrite=False):
    print("Erzeuge Basis-CSV …")
    # 1) Lokale historische Wetterdaten einlesen
    weather_df = pd.read_csv(historic_weather_file)

    # 2) Stammdaten einlesen und DateTime kombinieren
    stam_df = pd.read_csv(stammdaten_file, dtype={"MatchID": int})
    stam_df['DateTime'] = pd.to_datetime(stam_df['Date'] + ' ' + stam_df['Time'])
    stam_df = stam_df[stam_df['DateTime'] < datetime.now()]

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
    out = final[['MatchID','Home Team ID','Home Team','City','Weather_Request_Time',
                 'Temperature (C)','Pressure','Humidity',
                 'Wind Speed','Wind Direction','Rain','Snow']]
    out = out.rename(columns={'Weather_Request_Time':'DateTime'})
    out['DateTime'] = out['DateTime'].dt.strftime("%A %d %B,%Y,%H:%M")
    out = out.drop_duplicates(subset=['MatchID','Home Team ID','Home Team','City','DateTime'])

    os.makedirs(os.path.dirname(output_csv_file), exist_ok=True)
    if overwrite:
        out.to_csv(output_csv_file, index=False)
        print("Basis-CSV neu erstellt:", output_csv_file)
    elif os.path.exists(output_csv_file):
        exist_df = pd.read_csv(output_csv_file, dtype={"MatchID": int})
        key_cols = ['MatchID','Home Team ID','Home Team','City','DateTime']
        merged = out.merge(exist_df[key_cols], on=key_cols, how='left', indicator=True)
        new_out = merged[merged['_merge'] == 'left_only'][out.columns]
        if new_out.empty:
            print("Keine neuen Zeilen f\xc3\xbcr die Basis-CSV.")
        else:
            new_out.to_csv(output_csv_file, mode='a', header=False, index=False)
            print(f"{len(new_out)} neue Zeilen zur Basis-CSV hinzugef\xc3\xbcgt:", output_csv_file)
    else:
        out.to_csv(output_csv_file, index=False)
        print("Basis-CSV erstellt:", output_csv_file)

# ---------------------------
# Aktualisierung: Neue API-Daten anhängen
# ---------------------------
def query_api_data_by_match_id():
    if not os.path.exists(output_csv_file):
        print("historical_weather_data.csv fehlt – bitte zuerst main() ausführen.")
        return

    exist_df = pd.read_csv(output_csv_file, dtype={"MatchID": int})
    key_cols = ['MatchID','Home Team ID','Home Team','City','DateTime']
    existing_keys = set(exist_df[key_cols].itertuples(index=False, name=None))

    stam_df = pd.read_csv(stammdaten_file, dtype={"MatchID": int})
    stam_df['DateTime'] = pd.to_datetime(stam_df['Date'] + ' ' + stam_df['Time'])
    now = datetime.now()
    stam_df = stam_df[stam_df['DateTime'] < now]

    if stam_df.empty:
        print("Keine gestarteten Spiele gefunden.")
        return

    coords_df = pd.read_csv(city_coordinates_file)
    merged = stam_df.merge(coords_df, left_on='Home Team', right_on='Team', how='left')

    api_rows = []
    for _, row in merged.iterrows():
        for off in get_weather_offsets(row['DateTime']):
            dt_req = row['DateTime'] + off
            if dt_req > now:
                continue
            dt_req_str = dt_req.strftime("%A %d %B,%Y,%H:%M")
            key = (row['MatchID'], row['Home Team ID'], row['Home Team'], row['City'], dt_req_str)
            if key in existing_keys:
                continue
            print(f"Hole Wetterdaten für Match {row['MatchID']} um {dt_req}")
            w = fetch_weather(row['Latitude'], row['Longitude'], dt_req)
            api_rows.append({
                'MatchID':      row['MatchID'],
                'Home Team ID':     row['Home Team ID'],
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
            existing_keys.add(key)

    if api_rows:
        new_df = pd.DataFrame(api_rows)
        new_df['DateTime'] = new_df['DateTime'].dt.strftime("%A %d %B,%Y,%H:%M")
        new_df.to_csv(output_csv_file, mode='a', header=False, index=False)
        print(f"{len(new_df)} neue Zeilen angehaengt.")
    else:
        print("Keine fehlenden API-Daten gefunden.")

# ---------------------------
# Aktualisierung: Letztes Jahr neu per API abrufen
# ---------------------------
def refresh_last_year_api_data():
    if not os.path.exists(output_csv_file):
        print("historical_weather_data.csv fehlt – bitte zuerst main() ausführen.")
        return

    cutoff = datetime.now() - pd.Timedelta(days=365)

    # Bestehende Daten laden und letzte 365 Tage entfernen
    exist_df = pd.read_csv(output_csv_file, dtype={"MatchID": int})
    exist_df['DateTime'] = pd.to_datetime(
        exist_df['DateTime'],
        format="%A %d %B,%Y,%H:%M",
        errors="coerce"
    )
    keep_df = exist_df[exist_df['DateTime'] < cutoff].copy()

    # Spiele der letzten 365 Tage ermitteln
    stam_df = pd.read_csv(stammdaten_file, dtype={"MatchID": int})
    stam_df['DateTime'] = pd.to_datetime(stam_df['Date'] + ' ' + stam_df['Time'])
    recent_games = stam_df[(stam_df['DateTime'] >= cutoff) & (stam_df['DateTime'] < datetime.now())]
    if recent_games.empty:
        print("Keine Spiele im letzten Jahr gefunden.")
        keep_df.to_csv(output_csv_file, index=False)
        return

    coords_df = pd.read_csv(city_coordinates_file)
    merged = recent_games.merge(coords_df, left_on='Home Team', right_on='Team', how='left')

    api_rows = []
    for _, row in merged.iterrows():
        for off in get_weather_offsets(row['DateTime']):
            dt_req = row['DateTime'] + off
            print(f"Hole Wetterdaten fuer Match {row['MatchID']} um {dt_req}")
            w = fetch_weather(row['Latitude'], row['Longitude'], dt_req)
            api_rows.append({
                'MatchID':          row['MatchID'],
                'Home Team ID':     row['Home Team ID'],
                'Home Team':        row['Home Team'],
                'City':             row['City'],
                'DateTime':         dt_req,
                'Temperature (C)':  w.get('Temperature (C)'),
                'Pressure':         w.get('Pressure'),
                'Humidity':         w.get('Humidity'),
                'Wind Speed':       w.get('Wind Speed'),
                'Wind Direction':   w.get('Wind Direction'),
                'Rain':             w.get('Rain'),
                'Snow':             w.get('Snow')
            })

    if not api_rows:
        print("Keine API-Daten fuer das letzte Jahr abgerufen.")
        keep_df.to_csv(output_csv_file, index=False)
        return

    new_df = pd.DataFrame(api_rows)
    new_df['DateTime'] = new_df['DateTime'].dt.strftime("%A %d %B,%Y,%H:%M")
    keep_df['DateTime'] = keep_df['DateTime'].dt.strftime("%A %d %B,%Y,%H:%M")

    combined = pd.concat([keep_df, new_df], ignore_index=True)
    combined = combined.drop_duplicates(
        subset=['MatchID','Home Team ID','Home Team','City','DateTime']
    )
    combined.to_csv(output_csv_file, index=False)
    print("Letztes Jahr per API aktualisiert:", output_csv_file)

# ---------------------------
# Scheduler helper: Run only on full hours that match current games
# ---------------------------
def run_if_match_hour():
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    stam_df = pd.read_csv(stammdaten_file, dtype={"MatchID": int})
    stam_df['DateTime'] = pd.to_datetime(stam_df['Date'] + ' ' + stam_df['Time'])

    run_times = set()
    for _, row in stam_df.iterrows():
        match_dt = row['DateTime']
        for off in get_weather_offsets(match_dt):
            run_times.add((match_dt + off).replace(minute=0, second=0, microsecond=0))

    if now in run_times:
        print(f"Scheduler: hit {now} - run API update.")
        query_api_data_by_match_id()
    else:
        print(f"Scheduler: no match hour at {now}.")

# ---------------------------
# Scheduler Setup
# ---------------------------
if __name__ == "__main__":
    # 1) Nur neue Spiele per API ergänzen
    query_api_data_by_match_id()

    # 2) Scheduler nur starten, wenn explizit aktiviert
    enable_scheduler = True
    if enable_scheduler:
        sched = BlockingScheduler(timezone="Europe/Berlin")
        sched.add_job(
            run_if_match_hour,
            trigger=CronTrigger(minute="0")
        )
        print("Scheduler gestartet - prueft jede volle Stunde (Europe/Berlin)")
        sched.start()

