import os
import csv
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd  # Für pd.Timedelta

# Definiere den Ordner, in dem die Dateien gespeichert sind
output_directory = "C:/AI Projekt/KI-Projekt/Kopien/Datensammlungen"

# Pfad zur CSV-Datei mit den Team-Standort-Daten
city_coordinates_file = os.path.join(output_directory, "city_coordinates.csv")

# Parameter für den Scraper
seasons = ["2024-2025"]
current_season = "2024-2025"
current_matchday = 21

# OpenWeatherMap API Key (stündlicher bzw. täglicher Forecast)
API_KEY = "abcc68d734dd721e64e567bb8c6c4bb8"

def load_team_locations(file_path):
    """
    Liest die CSV-Datei mit der Struktur: Team,City,Latitude,Longitude
    und gibt ein Dictionary zurück, das die Zuordnung enthält.
    """
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

# Lade die Team-Standort-Daten aus der CSV-Datei
team_locations = load_team_locations(city_coordinates_file)

def last_sunday(year, month):
    """Hilfsfunktion: Liefert den letzten Sonntag eines Monats."""
    last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    return last_day - timedelta(days=(last_day.weekday() + 1) % 7)

def get_weather_offsets(match_dt):
    """
    Liefert eine Liste von Offsets (als pd.Timedelta) für den stündlichen Forecast.
    Diese Offsets werden nur für Spiele innerhalb der nächsten 4 Tage angewandt.
    """
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
        # Zunächst speichern wir die gescrapten Spiele als Dictionary.
        # Später werden diese mit den Wetterdaten angereichert.
        self.match_results = []  
        self.merged_teams = {"HDH": "FCH"}  # Kürzel für ein mögliches Merging

    def fetch_future_match_data(self):
        for season in self.seasons:
            print(f"Fetching future matches for season: {season}")
            for matchday in range(self.current_matchday + 1, self.total_matchdays + 1):
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
                        # Entferne den Wochentag, um ein Datum zu erhalten, das sich einfacher parsen lässt
                        weekday = date_tag.find("span", class_="bold").text.strip() if date_tag.find("span", class_="bold") else ""
                        day = date_tag.get_text(strip=True).replace(weekday, "").strip()
                        time_str = time_tag.get_text(strip=True)
                        try:
                            time_obj = datetime.strptime(time_str, "%H:%M")
                            match_month = datetime.strptime(day, "%d %B").month

                            if match_month > 6:
                                match_year = season_start_year
                            else:
                                match_year = season_end_year

                            last_sunday_march = last_sunday(match_year, 3)
                            last_sunday_october = last_sunday(match_year, 10)
                            match_date = datetime.strptime(f"{day} {match_year}", "%d %B %Y")

                            if last_sunday_march <= match_date < last_sunday_october:
                                time_obj += timedelta(hours=2)
                            else:
                                time_obj += timedelta(hours=1)

                            time_formatted = time_obj.strftime("%H:%M")
                        except ValueError:
                            print(f"Error parsing time: {time_str} or date: {day}")
                            time_formatted = time_str
                            match_year = season_start_year

                        date_time_mapping.append({
                            "header": date_header,
                            "day": day,
                            "time": time_formatted,
                            "year": match_year,
                            "matches": []
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
                    time_str = entry["time"]
                    match_year = entry["year"]
                    for score_bug in entry["matches"]:
                        try:
                            home_team_tag = score_bug.find('div', class_=["cell home", "cell home white"])
                            home_team = home_team_tag.find('div', class_="tlc").text.strip() if home_team_tag else 'Unknown'
                            
                            # Erzeuge einen vollständigen Datum-Zeit-String im Format "10 May 2024 15:30"
                            datetime_str = f"{day} {match_year} {time_str}"
                            match_datetime = datetime.strptime(datetime_str, "%d %B %Y %H:%M")
                            
                            self.match_results.append({
                                "home_team": home_team,
                                "match_datetime": match_datetime
                            })
                        except Exception as e:
                            print(f"Error extracting data for match in matchday {matchday}: {e}")
                            continue

            print(f"Finished fetching future matches for season {season}.")

    def get_weather_data(self, match_datetime, lat, lon, api_key):
        """
        Holt den Wetterforecast für die angegebene Zeit und Position.
        Für Spiele innerhalb der nächsten 4 Tage wird der stündliche Forecast
        genutzt – es wird für jeden berechneten Offset ein eigener Forecast (als Dictionary)
        ermittelt und in einer Liste zurückgegeben.
        Für Spiele außerhalb der nächsten 4 Tage erfolgt der tägliche Forecast,
        wobei eine Liste mit einem Element zurückgegeben wird.
        """
        now = datetime.now()
        if match_datetime < now:
            return None

        # Spiele innerhalb der nächsten 4 Tage: stündlicher Forecast mit Offsets
        if match_datetime - now <= timedelta(days=4):
            url = f"https://pro.openweathermap.org/data/2.5/forecast/hourly?lat={lat}&lon={lon}&appid={api_key}"
            try:
                response = requests.get(url)
                data = response.json()
            except Exception as e:
                print(f"Fehler beim Abruf des stündlichen Forecasts: {e}")
                return None

            offsets = get_weather_offsets(match_datetime)
            forecast_list = data.get("list", [])
            forecasts = []  # Liste der Forecast-Dictionaries

            for offset in offsets:
                target_time = match_datetime + offset.to_pytimedelta()
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
            # Täglicher Forecast (bis zu 16 Tage) – hier wird eine Liste mit einem Element zurückgegeben.
            cnt = 16
            url = f"https://api.openweathermap.org/data/2.5/forecast/daily?lat={lat}&lon={lon}&cnt={cnt}&appid={api_key}"
            try:
                response = requests.get(url)
                data = response.json()
            except Exception as e:
                print(f"Fehler beim Abruf des täglichen Forecasts: {e}")
                return None

            best_forecast = None
            match_date = match_datetime.date()
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
                    "forecast_dt": match_datetime.strftime("%d %B %Y %H:%M"),
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

    def enrich_with_weather(self, api_key):
        """
        Für jedes Spiel wird anhand des Heimteams (mittels team_locations aus der CSV)
        die zugehörige Stadt und die geografischen Koordinaten ermittelt. Anschließend wird
        der passende Wetterforecast abgefragt. Für Spiele innerhalb der nächsten 4 Tage
        wird für jeden Offset eine eigene Zeile erzeugt.
        """
        enriched_results = []
        match_id = 1  # fortlaufende ID für jede Zeile

        for match in self.match_results:
            home_team = match["home_team"]
            match_datetime = match["match_datetime"]

            city = "Unknown"
            if home_team in team_locations:
                location = team_locations[home_team]
                city = location["city"]
                lat = location["lat"]
                lon = location["lon"]
                weather_data = self.get_weather_data(match_datetime, lat, lon, api_key)
            else:
                print(f"Keine Standortdaten für {home_team} gefunden.")
                weather_data = None

            if weather_data:
                for forecast in weather_data:
                    enriched_results.append({
                        "match_id": match_id,
                        "home_team": home_team,
                        "city": city,
                        "datetime": forecast["forecast_dt"],
                        "temp_c": forecast["temp_c"],
                        "pressure": forecast["pressure"],
                        "humidity": forecast["humidity"],
                        "wind_speed": forecast["wind_speed"],
                        "wind_direction": forecast["wind_direction"],
                        "rain": forecast["rain"],
                        "snow": forecast["snow"]
                    })
                    match_id += 1
            else:
                # Falls keine Wetterdaten abgerufen wurden, eine Zeile mit leeren Wetterfeldern
                enriched_results.append({
                    "match_id": match_id,
                    "home_team": home_team,
                    "city": city,
                    "datetime": match_datetime.strftime("%d %B %Y %H:%M"),
                    "temp_c": None,
                    "pressure": None,
                    "humidity": None,
                    "wind_speed": None,
                    "wind_direction": None,
                    "rain": None,
                    "snow": None
                })
                match_id += 1

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

if __name__ == "__main__":
    scraper = BundesligaStatsScraper(seasons, current_season, current_matchday)
    scraper.fetch_future_match_data()
    scraper.enrich_with_weather(API_KEY)
    scraper.save_match_results_to_csv("future_weather.csv")
