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
stammdaten_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/Stammdaten_78.csv"
city_coordinates_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/city_coordinates_78.csv"
output_csv_file = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/future_weather_data_78.csv"

OUTPUT_COLUMNS = [
    "MatchID",
    "Home Team ID",
    "Home Team",
    "City",
    "DateTime",
    "Temperature (C)",
    "Pressure",
    "Humidity",
    "Wind Speed",
    "Wind Direction",
    "Rain",
    "Snow"
]

# ---------------------------
# OpenWeather API Key und Forecast-Endpoint
# ---------------------------
API_KEY = "abcc68d734dd721e64e567bb8c6c4bb8"
HOURLY_FORECAST_URL = "https://pro.openweathermap.org/data/2.5/forecast/hourly"
REQUEST_CONNECT_TIMEOUT = 4
REQUEST_READ_TIMEOUT = 8
REQUEST_RETRIES = 1
REQUEST_BACKOFF_SECONDS = 1.0

# ---------------------------
# Hilfsfunktion: Wetter-Offsets je nach Anstosszeit
# ---------------------------
def get_weather_offsets(match_dt):
    if match_dt.minute == 0:
        return [pd.Timedelta(hours=h) for h in (0, 1, 2, 3)]
    elif match_dt.minute == 30:
        return [pd.Timedelta(minutes=m) for m in (-30, 30, 90, 150)]
    elif match_dt.minute == 45:
        return [pd.Timedelta(minutes=m) for m in (-45, 15, 75, 135)]
    return [pd.Timedelta(hours=h) for h in (0, 1, 2, 3)]

def _load_stammdaten():
    return pd.read_csv(stammdaten_file)

def _load_team_coords():
    coords_df = pd.read_csv(city_coordinates_file)
    name_to_coords = coords_df.set_index("Team")[["City", "Latitude", "Longitude"]].to_dict("index")
    return name_to_coords

def _parse_stammdaten_datetime(date_str, time_str):
    try:
        dt_naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        return dt_naive.replace(tzinfo=ZoneInfo("Europe/Berlin"))
    except Exception:
        return None

def _load_matches_in_window(start_local, end_local):
    stam_df = _load_stammdaten()
    in_window = []
    for _, row in stam_df.iterrows():
        date_str = str(row.get("Date", "")).strip()
        time_str = str(row.get("Time", "")).strip()
        if not date_str or not time_str:
            continue
        dt_local = _parse_stammdaten_datetime(date_str, time_str)
        if dt_local is None:
            continue
        if start_local <= dt_local <= end_local:
            in_window.append(dt_local)
    return in_window

def _build_future_fixtures(now_local):
    stam_df = _load_stammdaten()
    name_to_coords = _load_team_coords()
    items = []

    for _, row in stam_df.iterrows():
        date_str = str(row.get("Date", "")).strip()
        time_str = str(row.get("Time", "")).strip()
        if not date_str or not time_str:
            continue
        dt_local = _parse_stammdaten_datetime(date_str, time_str)
        if dt_local is None or dt_local <= now_local:
            continue

        home_id = row.get("Home Team ID")
        home_name = str(row.get("Home Team", "")).strip()
        coords = name_to_coords.get(home_name)
        if not coords:
            print(f"Keine Koordinaten gefunden fuer Team: {home_name} (ID {home_id})")
            continue

        items.append({
            "MatchID": row.get("MatchID"),
            "Home Team ID": home_id,
            "Home Team": home_name,
            "City": coords.get("City"),
            "Latitude": coords.get("Latitude"),
            "Longitude": coords.get("Longitude"),
            "MatchDateTime": dt_local
        })

    return items

def _build_forecast_index(entries):
    by_time = {}
    times = []
    for entry in entries:
        ts = entry.get("dt")
        if ts is None:
            continue
        dt_utc = datetime.fromtimestamp(ts, tz=ZoneInfo("UTC")).replace(minute=0, second=0, microsecond=0)
        by_time[dt_utc] = entry
        times.append(dt_utc)
    times_sorted = sorted(set(times))
    return {"by_time": by_time, "times": times_sorted, "min_time": times_sorted[0] if times_sorted else None, "max_time": times_sorted[-1] if times_sorted else None}

def _empty_forecast():
    return {"by_time": {}, "times": [], "min_time": None, "max_time": None, "source": "forecast"}

def _request_forecast_with_retries(params):
    last_error = None
    total_attempts = REQUEST_RETRIES + 1

    for attempt in range(1, total_attempts + 1):
        try:
            resp = requests.get(
                HOURLY_FORECAST_URL,
                params=params,
                timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT)
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout as e:
            last_error = e
            print(f"Forecast Timeout (Versuch {attempt}/{total_attempts}).")
        except requests.exceptions.RequestException as e:
            last_error = e
            status_code = getattr(e.response, "status_code", None)
            print(f"Forecast HTTP/Netzwerkfehler (Versuch {attempt}/{total_attempts}): {e}")
            # 4xx (ausser 429) sind meist nicht transient und werden nicht erneut versucht.
            if status_code and 400 <= status_code < 500 and status_code != 429:
                break

        if attempt < total_attempts:
            time.sleep(REQUEST_BACKOFF_SECONDS * attempt)

    if last_error:
        raise last_error
    raise RuntimeError("Forecast-Request fehlgeschlagen ohne konkrete Exception.")

def _fetch_forecast(lat, lon):
    try:
        params = {
            "lat": lat,
            "lon": lon,
            "appid": API_KEY,
            "units": "metric"
        }
        data = _request_forecast_with_retries(params)
        hourly = data.get("list") or data.get("hourly", [])
        if hourly:
            forecast = _build_forecast_index(hourly)
            forecast["source"] = "forecast"
            return forecast
    except Exception as e:
        print(f"Forecast fehlgeschlagen ({lat}, {lon}): {e}")
    return _empty_forecast()

def _pick_forecast_entry(forecast, target_utc):
    target_utc = target_utc.replace(minute=0, second=0, microsecond=0)
    if forecast["max_time"] and target_utc > forecast["max_time"]:
        return None
    if target_utc in forecast["by_time"]:
        return forecast["by_time"][target_utc]

    if not forecast["times"]:
        return None
    nearest = min(forecast["times"], key=lambda t: abs((t - target_utc).total_seconds()))
    if abs((nearest - target_utc).total_seconds()) > 5400:
        return None
    return forecast["by_time"][nearest]

def _extract_weather(entry, source):
    main = entry.get("main", {})
    wind = entry.get("wind", {})
    return {
        "Temperature (C)": main.get("temp"),
        "Pressure": main.get("pressure"),
        "Humidity": main.get("humidity"),
        "Wind Speed": wind.get("speed"),
        "Wind Direction": wind.get("deg"),
        "Rain": entry.get("rain", {}).get("3h", 0),
        "Snow": entry.get("snow", {}).get("3h", 0)
    }

def _write_output_csv(df):
    os.makedirs(os.path.dirname(output_csv_file), exist_ok=True)
    if df.empty:
        if os.path.exists(output_csv_file):
            print("Keine neuen Forecast-Zeilen. Bestehende Output-CSV bleibt unveraendert:", output_csv_file)
        else:
            pd.DataFrame(columns=OUTPUT_COLUMNS).to_csv(output_csv_file, index=False)
            print("Keine neuen Forecast-Zeilen. Leere Output-CSV erstellt:", output_csv_file)
    else:
        df.to_csv(output_csv_file, index=False)
        print(f"{len(df)} neue Forecast-Zeilen geschrieben: {output_csv_file}")

# ---------------------------
# main(): Holt Forecasts fuer zukuenftige Matches
# ---------------------------
def main():
    now_local = datetime.now(ZoneInfo("Europe/Berlin"))
    fixtures = _build_future_fixtures(now_local)
    if not fixtures:
        print("Keine zukuenftigen Spiele in den Stammdaten gefunden.")
        _write_output_csv(pd.DataFrame(columns=OUTPUT_COLUMNS))
        return

    forecast_cache = {}
    rows = []

    for fx in fixtures:
        key = (fx["Latitude"], fx["Longitude"])
        if key not in forecast_cache:
            forecast_cache[key] = _fetch_forecast(fx["Latitude"], fx["Longitude"])
        forecast = forecast_cache[key]
        if not forecast["times"]:
            continue

        for off in get_weather_offsets(fx["MatchDateTime"]):
            dt_req_local = (fx["MatchDateTime"] + off).replace(minute=0, second=0, microsecond=0)
            if dt_req_local <= now_local:
                continue
            dt_req_utc = dt_req_local.astimezone(ZoneInfo("UTC"))
            entry = _pick_forecast_entry(forecast, dt_req_utc)
            if not entry:
                continue

            weather = _extract_weather(entry, forecast["source"])
            rows.append({
                "MatchID": fx["MatchID"],
                "Home Team ID": fx["Home Team ID"],
                "Home Team": fx["Home Team"],
                "City": fx["City"],
                "DateTime": dt_req_local,
                "Temperature (C)": weather.get("Temperature (C)"),
                "Pressure": weather.get("Pressure"),
                "Humidity": weather.get("Humidity"),
                "Wind Speed": weather.get("Wind Speed"),
                "Wind Direction": weather.get("Wind Direction"),
                "Rain": weather.get("Rain"),
                "Snow": weather.get("Snow")
            })

    if not rows:
        print("Keine Forecast-Zeilen im API-Zeitraum gefunden.")
        _write_output_csv(pd.DataFrame(columns=OUTPUT_COLUMNS))
        return

    out = pd.DataFrame(rows)
    out = out.drop_duplicates(subset=["MatchID", "Home Team ID", "Home Team", "City", "DateTime"])
    out["DateTime"] = out["DateTime"].dt.strftime("%A %d %B,%Y,%H:%M")
    if os.path.exists(output_csv_file):
        existing_df = pd.read_csv(output_csv_file, dtype={"MatchID": int})
    else:
        existing_df = pd.DataFrame(columns=OUTPUT_COLUMNS)

    key_cols = ["MatchID", "Home Team ID", "Home Team", "City", "DateTime"]
    for col in OUTPUT_COLUMNS:
        if col not in existing_df.columns:
            existing_df[col] = None

    # Vergangene Forecast-Slots aus der Datei entfernen.
    dropped_past = 0
    if not existing_df.empty:
        parsed_dt = pd.to_datetime(existing_df["DateTime"], format="%A %d %B,%Y,%H:%M", errors="coerce")
        fallback_mask = parsed_dt.isna()
        if fallback_mask.any():
            parsed_dt.loc[fallback_mask] = pd.to_datetime(existing_df.loc[fallback_mask, "DateTime"], errors="coerce")

        now_naive = now_local.replace(tzinfo=None)
        future_mask = parsed_dt > now_naive
        dropped_past = int((~future_mask).sum())
        existing_df = existing_df.loc[future_mask].copy()

    out_keys = set(out[key_cols].itertuples(index=False, name=None))
    existing_keys = set(existing_df[key_cols].drop_duplicates().itertuples(index=False, name=None)) if not existing_df.empty else set()

    inserted = len(out_keys - existing_keys)
    replaced = len(out_keys & existing_keys)

    keep_mask = ~existing_df[key_cols].apply(tuple, axis=1).isin(out_keys) if not existing_df.empty else pd.Series(dtype=bool)
    keep_df = existing_df.loc[keep_mask] if not existing_df.empty else existing_df

    combined_df = pd.concat([keep_df, out], ignore_index=True)
    combined_df = combined_df.drop_duplicates(subset=key_cols, keep="last")
    combined_df = combined_df[OUTPUT_COLUMNS]
    combined_df.to_csv(output_csv_file, index=False)

    print(
        f"Forecast upsert abgeschlossen: {inserted} neu, {replaced} aktualisiert, {dropped_past} vergangene Slots entfernt -> {output_csv_file}"
    )

# ---------------------------
# Scheduler helper: Run only on full hours that match current games
# ---------------------------
def run_if_match_hour():
    now_local = datetime.now(ZoneInfo("Europe/Berlin")).replace(minute=0, second=0, microsecond=0)
    start_local = now_local - pd.Timedelta(hours=4)
    end_local = now_local + pd.Timedelta(hours=4)

    match_times = _load_matches_in_window(start_local, end_local)
    run_times = set()
    for match_dt in match_times:
        for off in get_weather_offsets(match_dt):
            run_times.add((match_dt + off).replace(minute=0, second=0, microsecond=0))

    if now_local in run_times:
        print(f"Scheduler: hit {now_local} - run forecast update.")
        main()
    else:
        print(f"Scheduler: no match hour at {now_local}.")

# ---------------------------
# Scheduler Setup
# ---------------------------
if __name__ == "__main__":
    main()
    # Scheduler nur starten, wenn explizit aktiviert
    enable_scheduler = True
    if enable_scheduler:
        sched = BlockingScheduler(timezone="Europe/Berlin")
        sched.add_job(
            run_if_match_hour,
            trigger=CronTrigger(minute="0")
        )
        print("Scheduler gestartet - prueft jede volle Stunde (Europe/Berlin)")
        sched.start()




