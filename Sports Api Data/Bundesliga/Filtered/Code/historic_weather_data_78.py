import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------
# Pfade zu den Eingabe- und Ausgabedateien
# ---------------------------
historic_weather_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/bereinigte_datei.csv"
stammdaten_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/Stammdaten_78.csv"
city_coordinates_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/city_coordinates_78.csv"
output_csv_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/historical_weather_data_78.csv"

# ---------------------------
# OpenWeather API Key und History-Endpoint
# ---------------------------
API_KEY = "8738a0031c3e965eaece939dbc7faf1d"
BASE_URL = "https://history.openweathermap.org/data/2.5/history/city"
REQUEST_CONNECT_TIMEOUT = 4
REQUEST_READ_TIMEOUT = 8
REQUEST_RETRIES = 2
REQUEST_BACKOFF_SECONDS = 1.0


def _empty_weather_record():
    return {
        "Temperature (C)": None,
        "Pressure": None,
        "Humidity": None,
        "Wind Speed": None,
        "Wind Direction": None,
        "Rain": 0,
        "Snow": 0,
    }


def _has_valid_coordinates(lat, lon):
    try:
        if lat is None or lon is None:
            return False
        if pd.isna(lat) or pd.isna(lon):
            return False
        float(lat)
        float(lon)
        return True
    except Exception:
        return False


def _build_session():
    retry = Retry(
        total=REQUEST_RETRIES,
        connect=REQUEST_RETRIES,
        read=REQUEST_RETRIES,
        status=REQUEST_RETRIES,
        backoff_factor=REQUEST_BACKOFF_SECONDS,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "bundesliga-historic-weather/1.0",
            "Accept": "application/json",
        }
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ---------------------------
# Hilfsfunktion: Wetter-Offsets je nach Anstosszeit
# ---------------------------
def get_weather_offsets(match_dt):
    if match_dt.minute == 0:
        return [pd.Timedelta(hours=h) for h in (0, 1, 2, 3)]
    if match_dt.minute == 30:
        return [pd.Timedelta(minutes=m) for m in (-30, 30, 90, 150)]
    if match_dt.minute == 45:
        return [pd.Timedelta(minutes=m) for m in (-45, 15, 75, 135)]
    return [pd.Timedelta(hours=h) for h in (0, 1, 2, 3)]


# ---------------------------
# Hilfsfunktion: Eine Wetter-Abfrage durchfuehren (History/city)
# ---------------------------
def _last_sunday(year, month):
    day = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
    while day.weekday() != 6:
        day -= pd.Timedelta(days=1)
    return day


def _adjust_request_time(dt_local):
    year = dt_local.year
    tz = ZoneInfo("Europe/Berlin")
    start = _last_sunday(year, 3).replace(hour=3, minute=0, second=0, microsecond=0, tzinfo=tz)
    end = _last_sunday(year, 10).replace(hour=1, minute=59, second=59, microsecond=999, tzinfo=tz)
    if start <= dt_local <= end:
        return dt_local - pd.Timedelta(hours=2)
    return dt_local - pd.Timedelta(hours=1)


def _request_weather_with_attempts(session, params):
    last_error = None
    total_attempts = REQUEST_RETRIES + 1

    for attempt in range(1, total_attempts + 1):
        try:
            resp = session.get(
                BASE_URL,
                params=params,
                timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT),
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout as exc:
            last_error = exc
            print(f"History-Weather Timeout (Versuch {attempt}/{total_attempts}).")
        except requests.exceptions.RequestException as exc:
            last_error = exc
            status_code = getattr(exc.response, "status_code", None)
            print(f"History-Weather HTTP/Netzwerkfehler (Versuch {attempt}/{total_attempts}): {exc}")
            if status_code and 400 <= status_code < 500 and status_code != 429:
                break

        if attempt < total_attempts:
            time.sleep(REQUEST_BACKOFF_SECONDS * attempt)

    if last_error:
        raise last_error
    raise RuntimeError("History-Weather Request fehlgeschlagen ohne konkrete Exception.")


def fetch_weather(lat, lon, dt_local, session=None, cache=None):
    if not _has_valid_coordinates(lat, lon):
        return _empty_weather_record()

    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=ZoneInfo("Europe/Berlin"))

    dt_local = _adjust_request_time(dt_local)
    ts = int(dt_local.astimezone(ZoneInfo("UTC")).timestamp())
    cache_key = (round(float(lat), 6), round(float(lon), 6), ts)

    if cache is not None and cache_key in cache:
        return cache[cache_key]

    params = {
        "lat": lat,
        "lon": lon,
        "type": "hour",
        "start": ts,
        "end": ts + 3600,
        "appid": API_KEY,
        "units": "metric",
    }

    owns_session = session is None
    if owns_session:
        session = _build_session()

    result = _empty_weather_record()
    try:
        payload = _request_weather_with_attempts(session, params)
        data = payload.get("list", [])
        if data:
            rec = data[0]
            main = rec.get("main", {})
            wind = rec.get("wind", {})
            result = {
                "Temperature (C)": main.get("temp"),
                "Pressure": main.get("pressure"),
                "Humidity": main.get("humidity"),
                "Wind Speed": wind.get("speed"),
                "Wind Direction": wind.get("deg"),
                "Rain": rec.get("rain", {}).get("1h", 0),
                "Snow": rec.get("snow", {}).get("1h", 0),
            }
    except Exception as exc:
        print(f"History-Weather fehlgeschlagen ({lat}, {lon}, {dt_local}): {exc}")
    finally:
        if owns_session:
            session.close()

    if cache is not None:
        cache[cache_key] = result

    return result


# ---------------------------
# main(): Erzeugt die Basis-CSV aus lokalen historischen Wetterdaten
# ---------------------------
def main(overwrite=False):
    print("Erzeuge Basis-CSV ...")

    weather_df = pd.read_csv(historic_weather_file)

    stam_df = pd.read_csv(stammdaten_file, dtype={"MatchID": int})
    stam_df["DateTime"] = pd.to_datetime(stam_df["Date"] + " " + stam_df["Time"])
    stam_df = stam_df[stam_df["DateTime"] < datetime.now()]

    weather_df["dt_iso"] = weather_df["dt_iso"].str.replace(" +0000 UTC", "", regex=False)
    weather_df["DateTime"] = pd.to_datetime(weather_df["dt_iso"], format="%Y-%m-%d %H:%M:%S")
    weather_df = weather_df.rename(
        columns={
            "city_name": "City",
            "temp": "Temperature (C)",
            "pressure": "Pressure",
            "humidity": "Humidity",
            "wind_speed": "Wind Speed",
            "wind_deg": "Wind Direction",
            "rain_1h": "Rain",
            "snow_1h": "Snow",
        }
    )[["City", "DateTime", "Temperature (C)", "Pressure", "Humidity", "Wind Speed", "Wind Direction", "Rain", "Snow"]]
    weather_df[["Rain", "Snow"]] = weather_df[["Rain", "Snow"]].fillna(0)

    coords_df = pd.read_csv(city_coordinates_file)
    merged_df = stam_df.merge(coords_df, left_on="Home Team", right_on="Team", how="left")

    recs = []
    for _, row in merged_df.iterrows():
        for off in get_weather_offsets(row["DateTime"]):
            rec = row.to_dict()
            rec["Weather_Request_Time"] = row["DateTime"] + off
            recs.append(rec)
    exp_df = pd.DataFrame(recs)

    final_df = exp_df.merge(
        weather_df,
        left_on=["City", "Weather_Request_Time"],
        right_on=["City", "DateTime"],
        how="left",
    )

    out = final_df[[
        "MatchID",
        "Home Team ID",
        "Home Team",
        "City",
        "Weather_Request_Time",
        "Temperature (C)",
        "Pressure",
        "Humidity",
        "Wind Speed",
        "Wind Direction",
        "Rain",
        "Snow",
    ]]
    out = out.rename(columns={"Weather_Request_Time": "DateTime"})
    out["DateTime"] = out["DateTime"].dt.strftime("%A %d %B,%Y,%H:%M")
    out = out.drop_duplicates(subset=["MatchID", "Home Team ID", "Home Team", "City", "DateTime"])

    os.makedirs(os.path.dirname(output_csv_file), exist_ok=True)
    if overwrite:
        out.to_csv(output_csv_file, index=False)
        print("Basis-CSV neu erstellt:", output_csv_file)
    elif os.path.exists(output_csv_file):
        exist_df = pd.read_csv(output_csv_file, dtype={"MatchID": int})
        key_cols = ["MatchID", "Home Team ID", "Home Team", "City", "DateTime"]
        merged = out.merge(exist_df[key_cols], on=key_cols, how="left", indicator=True)
        new_out = merged[merged["_merge"] == "left_only"][out.columns]
        if new_out.empty:
            print("Keine neuen Zeilen fuer die Basis-CSV.")
        else:
            new_out.to_csv(output_csv_file, mode="a", header=False, index=False)
            print(f"{len(new_out)} neue Zeilen zur Basis-CSV hinzugefuegt: {output_csv_file}")
    else:
        out.to_csv(output_csv_file, index=False)
        print("Basis-CSV erstellt:", output_csv_file)


# ---------------------------
# Aktualisierung: Neue API-Daten anhaengen
# ---------------------------
def query_api_data_by_match_id():
    if not os.path.exists(output_csv_file):
        print("historical_weather_data.csv fehlt - bitte zuerst main() ausfuehren.")
        return

    exist_df = pd.read_csv(output_csv_file, dtype={"MatchID": int})
    key_cols = ["MatchID", "Home Team ID", "Home Team", "City", "DateTime"]
    weather_cols = [
        "Temperature (C)",
        "Pressure",
        "Humidity",
        "Wind Speed",
        "Wind Direction",
    ]

    for col in weather_cols:
        if col not in exist_df.columns:
            exist_df[col] = None

    stale_mask = exist_df[weather_cols].isna().all(axis=1)
    stale_keys = set(
        exist_df.loc[stale_mask, key_cols].drop_duplicates().itertuples(index=False, name=None)
    )
    existing_keys = set(
        exist_df.loc[~stale_mask, key_cols].drop_duplicates().itertuples(index=False, name=None)
    )

    if stale_keys:
        print(f"{len(stale_keys)} bestehende Zeitslots mit leeren Wetterwerten werden neu abgefragt.")

    stam_df = pd.read_csv(stammdaten_file, dtype={"MatchID": int})
    stam_df["DateTime"] = pd.to_datetime(stam_df["Date"] + " " + stam_df["Time"])
    now = datetime.now()
    stam_df = stam_df[stam_df["DateTime"] < now]

    if stam_df.empty:
        print("Keine gestarteten Spiele gefunden.")
        return

    coords_df = pd.read_csv(city_coordinates_file)
    merged_df = stam_df.merge(coords_df, left_on="Home Team", right_on="Team", how="left")

    session = _build_session()
    weather_cache = {}
    api_rows = []

    try:
        for _, row in merged_df.iterrows():
            if not _has_valid_coordinates(row.get("Latitude"), row.get("Longitude")):
                print(f"WARN: Keine gueltigen Koordinaten fuer Match {row.get('MatchID')} ({row.get('Home Team')}).")
                continue

            for off in get_weather_offsets(row["DateTime"]):
                dt_req = row["DateTime"] + off
                if dt_req > now:
                    continue

                dt_req_str = dt_req.strftime("%A %d %B,%Y,%H:%M")
                key = (row["MatchID"], row["Home Team ID"], row["Home Team"], row["City"], dt_req_str)

                if key in existing_keys and key not in stale_keys:
                    continue

                print(f"Hole Wetterdaten fuer Match {row['MatchID']} um {dt_req}")
                w = fetch_weather(row["Latitude"], row["Longitude"], dt_req, session=session, cache=weather_cache)
                api_rows.append(
                    {
                        "MatchID": row["MatchID"],
                        "Home Team ID": row["Home Team ID"],
                        "Home Team": row["Home Team"],
                        "City": row["City"],
                        "DateTime": dt_req,
                        "Temperature (C)": w.get("Temperature (C)"),
                        "Pressure": w.get("Pressure"),
                        "Humidity": w.get("Humidity"),
                        "Wind Speed": w.get("Wind Speed"),
                        "Wind Direction": w.get("Wind Direction"),
                        "Rain": w.get("Rain"),
                        "Snow": w.get("Snow"),
                    }
                )
                existing_keys.add(key)
                if key in stale_keys:
                    stale_keys.remove(key)
    finally:
        session.close()

    if api_rows:
        new_df = pd.DataFrame(api_rows)
        new_df["DateTime"] = new_df["DateTime"].dt.strftime("%A %d %B,%Y,%H:%M")

        updated_keys = set(new_df[key_cols].itertuples(index=False, name=None))
        keep_mask = ~exist_df[key_cols].apply(tuple, axis=1).isin(updated_keys)
        combined_df = pd.concat([exist_df.loc[keep_mask], new_df], ignore_index=True)
        combined_df = combined_df.drop_duplicates(subset=key_cols, keep="last")
        combined_df.to_csv(output_csv_file, index=False)

        print(f"{len(new_df)} Datensaetze aktualisiert/angehaengt.")
    else:
        print("Keine fehlenden API-Daten gefunden.")

# ---------------------------
# Aktualisierung: Letztes Jahr neu per API abrufen
# ---------------------------
def refresh_last_year_api_data():
    if not os.path.exists(output_csv_file):
        print("historical_weather_data.csv fehlt - bitte zuerst main() ausfuehren.")
        return

    cutoff = datetime.now() - pd.Timedelta(days=365)

    exist_df = pd.read_csv(output_csv_file, dtype={"MatchID": int})
    exist_df["DateTime"] = pd.to_datetime(
        exist_df["DateTime"], format="%A %d %B,%Y,%H:%M", errors="coerce"
    )
    keep_df = exist_df[exist_df["DateTime"] < cutoff].copy()

    stam_df = pd.read_csv(stammdaten_file, dtype={"MatchID": int})
    stam_df["DateTime"] = pd.to_datetime(stam_df["Date"] + " " + stam_df["Time"])
    recent_games = stam_df[(stam_df["DateTime"] >= cutoff) & (stam_df["DateTime"] < datetime.now())]
    if recent_games.empty:
        print("Keine Spiele im letzten Jahr gefunden.")
        keep_df.to_csv(output_csv_file, index=False)
        return

    coords_df = pd.read_csv(city_coordinates_file)
    merged_df = recent_games.merge(coords_df, left_on="Home Team", right_on="Team", how="left")

    session = _build_session()
    weather_cache = {}
    api_rows = []

    try:
        for _, row in merged_df.iterrows():
            if not _has_valid_coordinates(row.get("Latitude"), row.get("Longitude")):
                print(f"WARN: Keine gueltigen Koordinaten fuer Match {row.get('MatchID')} ({row.get('Home Team')}).")
                continue

            for off in get_weather_offsets(row["DateTime"]):
                dt_req = row["DateTime"] + off
                print(f"Hole Wetterdaten fuer Match {row['MatchID']} um {dt_req}")
                w = fetch_weather(row["Latitude"], row["Longitude"], dt_req, session=session, cache=weather_cache)
                api_rows.append(
                    {
                        "MatchID": row["MatchID"],
                        "Home Team ID": row["Home Team ID"],
                        "Home Team": row["Home Team"],
                        "City": row["City"],
                        "DateTime": dt_req,
                        "Temperature (C)": w.get("Temperature (C)"),
                        "Pressure": w.get("Pressure"),
                        "Humidity": w.get("Humidity"),
                        "Wind Speed": w.get("Wind Speed"),
                        "Wind Direction": w.get("Wind Direction"),
                        "Rain": w.get("Rain"),
                        "Snow": w.get("Snow"),
                    }
                )
    finally:
        session.close()

    if not api_rows:
        print("Keine API-Daten fuer das letzte Jahr abgerufen.")
        keep_df.to_csv(output_csv_file, index=False)
        return

    new_df = pd.DataFrame(api_rows)
    new_df["DateTime"] = new_df["DateTime"].dt.strftime("%A %d %B,%Y,%H:%M")
    keep_df["DateTime"] = keep_df["DateTime"].dt.strftime("%A %d %B,%Y,%H:%M")

    combined = pd.concat([keep_df, new_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["MatchID", "Home Team ID", "Home Team", "City", "DateTime"])
    combined.to_csv(output_csv_file, index=False)
    print("Letztes Jahr per API aktualisiert:", output_csv_file)


# ---------------------------
# Scheduler helper: Run only on full hours that match current games
# ---------------------------
def run_if_match_hour():
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    stam_df = pd.read_csv(stammdaten_file, dtype={"MatchID": int})
    stam_df["DateTime"] = pd.to_datetime(stam_df["Date"] + " " + stam_df["Time"])

    run_times = set()
    for _, row in stam_df.iterrows():
        match_dt = row["DateTime"]
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
    query_api_data_by_match_id()

    enable_scheduler = True
    if enable_scheduler:
        sched = BlockingScheduler(timezone="Europe/Berlin")
        sched.add_job(run_if_match_hour, trigger=CronTrigger(minute="0"))
        print("Scheduler gestartet - prueft jede volle Stunde (Europe/Berlin)")
        sched.start()

