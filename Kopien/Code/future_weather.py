import os
import csv
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd  # Für pd.Timedelta

# Definiere den Ordner, in dem die Dateien gespeichert sind
output_directory = "C:/AI Projekt/KI-Projekt/Kopien/Datensammlungen"

# Pfade zu den CSV-Dateien
city_coordinates_file = os.path.join(output_directory, "city_coordinates.csv")
past_season_results_file = os.path.join(output_directory, "past_season_results.csv")
planned_start_times_file = os.path.join(output_directory, "planned_start_times.csv")

# Parameter für den Scraper
seasons = ["2024-2025"]
current_season = "2024-2025"
current_matchday = 22

# OpenWeatherMap API Key (stündlicher bzw. täglicher Forecast)
API_KEY = "abcc68d734dd721e64e567bb8c6c4bb8"


def get_last_match_id(file_path):
    last_id = 0
    try:
        with open(file_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    mid = int(row["Match ID"])
                    if mid > last_id:
                        last_id = mid
                except Exception:
                    continue
    except Exception as e:
        print(f"Fehler beim Lesen der Datei {file_path}: {e}")
    return last_id


def get_live_match_id_for_game(file_path, season, matchday, home_team):
    """
    Sucht in der CSV past_season_results nach einem Live-Spiel, das zu Saison, Spieltag und Heimteam passt,
    und gibt dessen Match_ID zurück.
    """
    try:
        with open(file_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if (row["Season"].strip() == season and
                    int(row["Matchday"]) == matchday and
                    row["Home Team"].strip() == home_team and
                    row["Time"].strip().upper() == "LIVE"):
                    return int(row["Match ID"])
    except Exception as e:
        print("Fehler beim Suchen der Live Match ID:", e)
    return None


def load_team_locations(file_path):
    team_locations = {}
    try:
        with open(file_path, mode="r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                team = row["Team"].strip()
                city = row["City"].strip()
                try:
                    lat = float(row["Latitude"].strip())
                    lon = float(row["Longitude"].strip())
                except ValueError:
                    print(f"Fehler beim Parsen der Koordinaten für Team {team}.")
                    continue
                team_locations[team] = {"city": city, "lat": lat, "lon": lon}
    except Exception as e:
        print(f"Fehler beim Laden der Datei {file_path}: {e}")
    return team_locations


# Lade die Team-Standort-Daten
team_locations = load_team_locations(city_coordinates_file)


def last_sunday(year, month):
    last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    return last_day - timedelta(days=(last_day.weekday() + 1) % 7)


def get_weather_offsets(match_dt):
    if match_dt.minute == 0:
        return [pd.Timedelta(hours=0), pd.Timedelta(hours=1), pd.Timedelta(hours=2), pd.Timedelta(hours=3)]
    elif match_dt.minute == 30:
        return [pd.Timedelta(minutes=-30), pd.Timedelta(minutes=30), pd.Timedelta(minutes=90), pd.Timedelta(minutes=150)]
    else:
        return [pd.Timedelta(hours=0), pd.Timedelta(hours=1), pd.Timedelta(hours=2), pd.Timedelta(hours=3)]


class BundesligaStatsScraper:
    def __init__(self, seasons, current_season, current_matchday, total_matchdays=34):
        self.seasons = seasons
        self.current_season = current_season
        self.current_matchday = current_matchday
        self.total_matchdays = total_matchdays
        # Hier werden die gescrapten Match-Daten gespeichert.
        # Zusätzlich speichern wir raw_match_results, bevor sie durch enrich_with_weather überschrieben werden.
        self.match_results = []
        self.raw_match_results = []
        self.merged_teams = {"HDH": "FCH"}
    
    def fetch_future_match_data(self):
        now = datetime.now()
        results = []
        next_id = get_last_match_id(past_season_results_file) + 1  # Neue IDs beginnen hier
        for season in self.seasons:
            print(f"Fetching future matches for season: {season}")
            for matchday in range(self.current_matchday, self.total_matchdays + 1):
                url = f"https://www.bundesliga.com/en/bundesliga/matchday/{season}/{matchday}"
                print(f"Fetching matchday: {matchday} in season: {season}")
                response = requests.get(url)
                soup = BeautifulSoup(response.content, "html.parser")
                date_headers = soup.find_all("match-date-header", class_="ng-star-inserted")
                date_time_mapping = []
                season_start_year, season_end_year = map(int, season.split("-"))
                for date_header in date_headers:
                    date_tag = date_header.find("span", class_="day")
                    time_tag = date_header.find("span", class_="time")
                    if date_tag and time_tag:
                        weekday = date_tag.find("span", class_="bold").text.strip() if date_tag.find("span", class_="bold") else ""
                        day = date_tag.get_text(strip=True).replace(weekday, "").strip()
                        time_str = time_tag.get_text(strip=True)
                        if time_str.upper() == "LIVE":
                            # Versuche den geplanten Zeitpunkt aus dem HTML-Attribut
                            planned_time_str = time_tag.get("data-planned-time")
                            if planned_time_str:
                                try:
                                    t_obj = datetime.strptime(planned_time_str, "%H:%M")
                                    t_obj += timedelta(hours=1)
                                    planned_time_str = t_obj.strftime("%H:%M")
                                except Exception as e:
                                    print(f"Fehler beim Parsen des geplanten Zeitwertes: {planned_time_str} - {e}")
                                    planned_time_str = None
                            else:
                                planned_time_str = None
                            time_formatted = "LIVE"
                        else:
                            try:
                                t_obj = datetime.strptime(time_str, "%H:%M")
                                t_obj += timedelta(hours=1)
                                time_formatted = t_obj.strftime("%H:%M")
                            except ValueError:
                                print(f"Error parsing time: {time_str} or date: {day}")
                                time_formatted = time_str
                            planned_time_str = time_formatted
                        try:
                            match_year = season_start_year if datetime.strptime(day, "%d %B").month > 6 else season_end_year
                        except Exception:
                            match_year = season_start_year
                        date_time_mapping.append({
                            "header": date_header,
                            "day": day,
                            "time": time_formatted,
                            "planned_time_str": planned_time_str,
                            "year": match_year,
                            "matches": [],
                            "season": season,
                            "matchday": matchday
                        })
                if not date_time_mapping:
                    print(f"No date-time headers found for matchday {matchday}.")
                    continue
                current_index = 0
                score_bugs = soup.find_all("score-bug", class_="ng-star-inserted")
                for score_bug in score_bugs:
                    if current_index >= len(date_time_mapping):
                        print(f"Error: current_index {current_index} out of range for date_time_mapping.")
                        break
                    while current_index < len(date_time_mapping) - 1 and \
                          date_time_mapping[current_index + 1]["header"].find_next("score-bug") == score_bug:
                        current_index += 1
                    date_time_mapping[current_index]["matches"].append(score_bug)
                for entry in date_time_mapping:
                    day = entry["day"]
                    time_val = entry["time"]
                    match_year = entry["year"]
                    season_val = entry["season"]
                    matchday_val = entry["matchday"]
                    planned_time_str = entry["planned_time_str"]
                    for score_bug in entry["matches"]:
                        try:
                            home_team_tag = score_bug.find('div', class_=["cell home", "cell home white"])
                            home_team = home_team_tag.find('div', class_="tlc").text.strip() if home_team_tag else 'Unknown'
                            if time_val.upper() == "LIVE":
                                match_datetime = "LIVE"
                                planned_datetime = datetime.strptime(f"{day} {match_year} {planned_time_str}", "%d %B %Y %H:%M") if planned_time_str else None
                            else:
                                datetime_str = f"{day} {match_year} {time_val}"
                                match_datetime = datetime.strptime(datetime_str, "%d %B %Y %H:%M")
                                planned_datetime = match_datetime
                            if match_datetime != "LIVE" and match_datetime < now:
                                continue
                            # Weisen jedem Match eine eindeutige ID zu
                            current_id = next_id
                            next_id += 1
                            results.append({
                                "match_id": current_id,
                                "home_team": home_team,
                                "match_datetime": match_datetime,
                                "planned_datetime": planned_datetime,
                                "season": season_val,
                                "matchday": matchday_val,
                                "day": day
                            })
                        except Exception as e:
                            print(f"Error extracting data for match in matchday {matchday_val}: {e}")
                            continue
        print(f"Finished fetching future matches for season(s): {self.seasons}.")
        self.match_results = results
        self.raw_match_results = list(results)
    
    def get_weather_data(self, ref_dt, lat, lon, api_key):
        now = datetime.now()
        if ref_dt < now:
            return None
        if ref_dt - now <= timedelta(days=4):
            url = f"https://pro.openweathermap.org/data/2.5/forecast/hourly?lat={lat}&lon={lon}&appid={api_key}"
            try:
                response = requests.get(url)
                data = response.json()
            except Exception as e:
                print(f"Fehler beim Abruf des stündlichen Forecasts: {e}")
                return None
            offsets = get_weather_offsets(ref_dt)
            forecast_list = data.get("list", [])
            forecasts = []
            for offset in offsets:
                target_time = ref_dt + offset.to_pytimedelta()
                if target_time < now:
                    continue
                best_forecast = None
                min_diff = float('inf')
                for forecast in forecast_list:
                    forecast_time = datetime.fromtimestamp(forecast["dt"])
                    diff = abs((target_time - forecast_time).total_seconds())
                    if diff < min_diff:
                        min_diff = diff
                        best_forecast = forecast
                if best_forecast:
                    try:
                        temp_k = best_forecast["main"]["temp"]
                        pressure = best_forecast["main"]["pressure"]
                        humidity = best_forecast["main"]["humidity"]
                        wind_speed = best_forecast["wind"]["speed"]
                        wind_direction = best_forecast["wind"].get("deg", None)
                        rain = best_forecast.get("rain", {}).get("1h", 0)
                        snow = best_forecast.get("snow", {}).get("1h", 0)
                        forecast_dict = {
                            "forecast_dt": target_time.strftime("%d %B %Y %H:%M"),
                            "temp_c": round(temp_k - 273.15, 2),
                            "pressure": pressure,
                            "humidity": humidity,
                            "wind_speed": wind_speed,
                            "wind_direction": wind_direction,
                            "rain": rain,
                            "snow": snow
                        }
                        forecasts.append(forecast_dict)
                    except Exception as e:
                        print(f"Fehler bei der Verarbeitung eines Forecasts: {e}")
            if len(forecasts) == 0:
                return None
            return forecasts
        else:
            cnt = 16
            url = f"https://api.openweathermap.org/data/2.5/forecast/daily?lat={lat}&lon={lon}&cnt={cnt}&appid={api_key}"
            try:
                response = requests.get(url)
                data = response.json()
            except Exception as e:
                print(f"Fehler beim Abruf des täglichen Forecasts: {e}")
                return None
            best_forecast = None
            match_date = ref_dt.date()
            for forecast in data.get("list", []):
                forecast_date = datetime.fromtimestamp(forecast["dt"]).date()
                if forecast_date == match_date:
                    best_forecast = forecast
                    break
            if best_forecast is None:
                return None
            try:
                temp_k = best_forecast["temp"]["day"]
                pressure = best_forecast["pressure"]
                humidity = best_forecast["humidity"]
                wind_speed = best_forecast.get("speed", None)
                wind_direction = best_forecast.get("deg", None)
                rain = best_forecast.get("rain", 0)
                snow = best_forecast.get("snow", 0)
                forecast_dict = {
                    "forecast_dt": ref_dt.strftime("%d %B %Y %H:%M"),
                    "temp_c": round(temp_k - 273.15, 2),
                    "pressure": pressure,
                    "humidity": humidity,
                    "wind_speed": wind_speed,
                    "wind_direction": wind_direction,
                    "rain": rain,
                    "snow": snow
                }
                return [forecast_dict]
            except Exception as e:
                print(f"Fehler beim Extrahieren der Wetterdaten: {e}")
                return None

    def enrich_with_weather(self, api_key, starting_match_id=1):
        """
        Für jedes zukünftige Spiel wird anhand des Heimteams der passende Wetterforecast abgefragt.
        Wenn ein Spiel LIVE ist, wird der geplante Startzeitpunkt aus der CSV (identifiziert über die Match_ID)
        als Referenz genutzt.
        """
        # Lade die geplanten Startzeiten aus der CSV in ein Dictionary,
        # wobei der Schlüssel die Match_ID als String ist.
        planned_times = {}
        if os.path.exists(planned_start_times_file):
            with open(planned_start_times_file, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = row["Match ID"].strip()
                    planned_times[key] = row["Planned Start Time"].strip()

        enriched_results = []
        match_id = starting_match_id
        for match in self.match_results:
            home_team = match["home_team"]
            # Für Live-Spiele:
            if match["match_datetime"] == "LIVE":
                current_id = str(match["match_id"])
                if current_id in planned_times and planned_times[current_id]:
                    try:
                        planned_dt = datetime.strptime(planned_times[current_id], "%d %B %Y %H:%M")
                    except Exception as e:
                        print(f"Fehler beim Parsen der geplanten Zeit aus CSV für Match_ID {current_id}: {e}")
                        planned_dt = match.get("planned_datetime") or datetime.now()
                else:
                    planned_dt = match.get("planned_datetime") or datetime.now()

                live_id = get_live_match_id_for_game(past_season_results_file, match["season"], match["matchday"], home_team)
                if live_id is not None:
                    current_match_id = live_id
                else:
                    current_match_id = match["match_id"]
                weather_data = self.get_weather_data(planned_dt, team_locations[home_team]["lat"], team_locations[home_team]["lon"], api_key)
                if weather_data:
                    for forecast in weather_data:
                        enriched_results.append({
                            "match_id": current_match_id,
                            "home_team": home_team,
                            "city": team_locations[home_team]["city"],
                            "datetime": forecast["forecast_dt"],
                            "temp_c": forecast["temp_c"],
                            "pressure": forecast["pressure"],
                            "humidity": forecast["humidity"],
                            "wind_speed": forecast["wind_speed"],
                            "wind_direction": forecast["wind_direction"],
                            "rain": forecast["rain"],
                            "snow": forecast["snow"]
                        })
                else:
                    enriched_results.append({
                        "match_id": current_match_id,
                        "home_team": home_team,
                        "city": team_locations[home_team]["city"],
                        "datetime": "LIVE",
                        "temp_c": None,
                        "pressure": None,
                        "humidity": None,
                        "wind_speed": None,
                        "wind_direction": None,
                        "rain": None,
                        "snow": None
                    })
                continue

            # Für Nicht-Live-Spiele:
            weather_data = self.get_weather_data(match["match_datetime"], team_locations[home_team]["lat"], team_locations[home_team]["lon"], api_key)
            if weather_data:
                current_match_id = match["match_id"]
                for forecast in weather_data:
                    enriched_results.append({
                        "match_id": current_match_id,
                        "home_team": home_team,
                        "city": team_locations[home_team]["city"],
                        "datetime": forecast["forecast_dt"],
                        "temp_c": forecast["temp_c"],
                        "pressure": forecast["pressure"],
                        "humidity": forecast["humidity"],
                        "wind_speed": forecast["wind_speed"],
                        "wind_direction": forecast["wind_direction"],
                        "rain": forecast["rain"],
                        "snow": forecast["snow"]
                    })
            else:
                enriched_results.append({
                    "match_id": match["match_id"],
                    "home_team": home_team,
                    "city": team_locations[home_team]["city"],
                    "datetime": match["match_datetime"].strftime("%d %B %Y %H:%M") if match["match_datetime"] != "LIVE" else "LIVE",
                    "temp_c": None,
                    "pressure": None,
                    "humidity": None,
                    "wind_speed": None,
                    "wind_direction": None,
                    "rain": None,
                    "snow": None
                })
        self.match_results = enriched_results

    def save_match_results_to_csv(self, filename="future_weather.csv"):
        file_path = os.path.join(output_directory, filename)
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                "Match ID", "Home Team", "City", "DateTime", "Temperature (C)",
                "Pressure", "Humidity", "Wind Speed", "Wind Direction", "Rain", "Snow"
            ])
            for match in self.match_results:
                writer.writerow([
                    match["match_id"],
                    match["home_team"],
                    match["city"],
                    match["datetime"],
                    match["temp_c"],
                    match["pressure"],
                    match["humidity"],
                    match["wind_speed"],
                    match["wind_direction"],
                    match["rain"],
                    match["snow"]
                ])
        print(f"CSV-Datei wurde gespeichert: {file_path}")

    def save_planned_start_times_to_csv(self, filename="planned_start_times.csv"):
        file_path = os.path.join(output_directory, filename)
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Match ID", "Home Team", "Day", "Planned Start Time"])
            for match in self.raw_match_results:
                if match.get("planned_datetime") and match.get("planned_datetime") != "LIVE":
                    planned_str = match["planned_datetime"].strftime("%d %B %Y %H:%M")
                else:
                    planned_str = ""
                writer.writerow([match["match_id"], match["home_team"], match.get("day", ""), planned_str])
        print(f"Planned start times saved to {file_path}")


if __name__ == "__main__":
    last_id = get_last_match_id(past_season_results_file)
    starting_match_id = last_id + 1
    print(f"Starting Match ID: {starting_match_id}")

    scraper = BundesligaStatsScraper(seasons, current_season, current_matchday)
    scraper.fetch_future_match_data()
    # Zuerst werden die Wetterdaten angereichert
    scraper.enrich_with_weather(API_KEY, starting_match_id=starting_match_id)
    scraper.save_match_results_to_csv("future_weather.csv")
    # Danach speichern wir die geplanten Startzeiten anhand der Match_ID in eine separate CSV
    scraper.save_planned_start_times_to_csv("planned_start_times.csv")
