import argparse
import csv
import json
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# OpenWeatherMap API key
API_KEY = "3820fa176fb1bbea6f35ea43ae9f2d1c"

# Input/output paths
INPUT_JSON_FILE = Path(
    "C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/Bundesliga Teams.json"
)
OUTPUT_CSV_FILE = Path(
    "C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/city_coordinates_78.csv"
)

# Team-specific city overrides (spelling/disambiguation)
CITY_OVERRIDES = {
    "Bayern M\u00fcnchen": "Munich",
    "1899 Hoffenheim": "Hoffenheim",
    "Eintracht Frankfurt": "Frankfurt",
    "1. FC Heidenheim": "Heidenheim",
    "Borussia M\u00f6nchengladbach": "Gladbach",
    "1. FC K\u00f6ln": "Cologne",
    "Hannover 96": "Hanover",
    "1. FC N\u00fcrnberg": "Nuremberg",
}


def _safe_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_session():
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "bundesliga-city-coordinates/1.0",
            "Accept": "application/json",
        }
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _load_team_city_pairs(input_json_file):
    with input_json_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    teams_list = data.get("response", [])
    unique = {}
    for entry in teams_list:
        team_name = entry.get("team", {}).get("name")
        city = entry.get("venue", {}).get("city")

        if not team_name:
            continue

        city = CITY_OVERRIDES.get(team_name, city)
        if city:
            unique[team_name] = city

    return sorted(unique.items(), key=lambda x: x[0].lower())


def _load_existing_coordinates(csv_path):
    by_team = {}
    by_city = {}

    if not csv_path.exists():
        return by_team, by_city

    try:
        with csv_path.open("r", encoding="utf-8", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                team = (row.get("Team") or "").strip()
                city = (row.get("City") or "").strip()
                lat = _safe_float(row.get("Latitude"))
                lon = _safe_float(row.get("Longitude"))

                if not team or not city or lat is None or lon is None:
                    continue

                record = {
                    "Team": team,
                    "City": city,
                    "Latitude": lat,
                    "Longitude": lon,
                }
                by_team[team] = record
                by_city.setdefault(city, (lat, lon))
    except Exception as exc:
        print(f"WARN: Bestehende CSV konnte nicht geladen werden: {exc}")

    return by_team, by_city


def _pick_best_result(results):
    if not results:
        return None

    # Prefer German entries for Bundesliga cities if available.
    for item in results:
        if str(item.get("country", "")).upper() == "DE":
            return item

    return results[0]


def _fetch_coordinates_with_attempts(session, city, api_key, connect_timeout, read_timeout, max_attempts, backoff_seconds):
    url = "https://api.openweathermap.org/geo/1.0/direct"
    params = {"q": city, "limit": 5, "appid": api_key}

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = session.get(url, params=params, timeout=(connect_timeout, read_timeout))
            response.raise_for_status()
            results = response.json()
            selected = _pick_best_result(results)
            if not selected:
                return None
            lat = _safe_float(selected.get("lat"))
            lon = _safe_float(selected.get("lon"))
            if lat is None or lon is None:
                return None
            return lat, lon
        except requests.exceptions.RequestException as exc:
            last_error = exc
            status_code = getattr(exc.response, "status_code", None)
            print(
                f"WARN: Geocoding fehlgeschlagen fuer '{city}' (Versuch {attempt}/{max_attempts}): {exc}"
            )
            # Non-429 4xx are usually not transient.
            if status_code and 400 <= status_code < 500 and status_code != 429:
                break
        except Exception as exc:
            last_error = exc
            print(
                f"WARN: Unerwarteter Fehler beim Geocoding fuer '{city}' "
                f"(Versuch {attempt}/{max_attempts}): {exc}"
            )

        if attempt < max_attempts:
            time.sleep(backoff_seconds * attempt)

    if last_error:
        print(f"WARN: Geocoding final fehlgeschlagen fuer '{city}': {last_error}")
    return None


def _write_output(csv_path, rows):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as csvfile:
        fieldnames = ["Team", "City", "Latitude", "Longitude"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Generate Bundesliga team city coordinates.")
    parser.add_argument("--connect-timeout", type=float, default=4.0)
    parser.add_argument("--read-timeout", type=float, default=8.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--backoff-seconds", type=float, default=1.0)
    parser.add_argument("--no-cache", action="store_true", help="Do not reuse coordinates from existing CSV.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 when not all teams could be resolved.",
    )
    args = parser.parse_args()

    team_city_list = _load_team_city_pairs(INPUT_JSON_FILE)
    if not team_city_list:
        print("WARN: Keine Team/Stadt-Paare gefunden.")
        _write_output(OUTPUT_CSV_FILE, [])
        return 0

    existing_by_team, existing_by_city = _load_existing_coordinates(OUTPUT_CSV_FILE)
    session = _build_session()

    rows = []
    city_cache = {}
    missing = []
    stats = {
        "cache_team": 0,
        "cache_city": 0,
        "fetched": 0,
        "failed": 0,
    }

    for team, city in team_city_list:
        lat = None
        lon = None

        if not args.no_cache:
            existing_team_row = existing_by_team.get(team)
            if existing_team_row and existing_team_row.get("City") == city:
                lat = existing_team_row.get("Latitude")
                lon = existing_team_row.get("Longitude")
                stats["cache_team"] += 1

        if (lat is None or lon is None) and city in city_cache:
            lat, lon = city_cache[city]
            stats["cache_city"] += 1

        if (lat is None or lon is None) and (not args.no_cache) and city in existing_by_city:
            lat, lon = existing_by_city[city]
            stats["cache_city"] += 1

        if lat is None or lon is None:
            fetched = _fetch_coordinates_with_attempts(
                session=session,
                city=city,
                api_key=API_KEY,
                connect_timeout=args.connect_timeout,
                read_timeout=args.read_timeout,
                max_attempts=max(1, args.max_attempts),
                backoff_seconds=max(0.0, args.backoff_seconds),
            )
            if fetched is not None:
                lat, lon = fetched
                stats["fetched"] += 1

        if lat is None or lon is None:
            stats["failed"] += 1
            missing.append((team, city))
            print(f"WARN: Keine Geodaten fuer {team} ({city})")
            continue

        city_cache[city] = (lat, lon)
        rows.append(
            {
                "Team": team,
                "City": city,
                "Latitude": lat,
                "Longitude": lon,
            }
        )
        print(f"OK: {team} - {city}: {lat}, {lon}")

    _write_output(OUTPUT_CSV_FILE, rows)

    print("\nCity-Coordinates abgeschlossen.")
    print(f"Teams gesamt: {len(team_city_list)}")
    print(f"Geschrieben: {len(rows)}")
    print(
        "Quelle: "
        f"team-cache={stats['cache_team']}, "
        f"city-cache={stats['cache_city']}, "
        f"neu-abgerufen={stats['fetched']}, "
        f"fehlend={stats['failed']}"
    )
    print(f"CSV: {OUTPUT_CSV_FILE}")

    if missing:
        print("\nNicht aufgeloeste Teams:")
        for team, city in missing:
            print(f"- {team} ({city})")

    if args.strict and missing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
