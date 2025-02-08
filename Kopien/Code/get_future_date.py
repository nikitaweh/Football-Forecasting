import os
import csv
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from datetime import datetime, timedelta

# Definiere den Ordner, in dem die Ausgabedatei gespeichert werden soll
output_directory = "C:/AI Projekt/KI-Projekt/Kopien/Datensammlungen"

# Die restlichen Variablen bleiben unverändert:
seasons = ["2024-2025"]
current_season = "2024-2025"
current_matchday = 19

def last_sunday(year, month):
    """Hilfsfunktion: Liefert den letzten Sonntag eines Monats."""
    last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    return last_day - timedelta(days=(last_day.weekday() + 1) % 7)

class BundesligaStatsScraper:
    def __init__(self, seasons, current_season, current_matchday, total_matchdays=34):
        self.seasons = seasons
        self.current_season = current_season
        self.current_matchday = current_matchday
        self.total_matchdays = total_matchdays
        self.match_results = []
        self.merged_teams = {"HDH": "FCH"}  # Kürzel für das Merging

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
                        weekday = date_tag.find("span", class_="bold").text.strip() if date_tag.find("span", class_="bold") else ""
                        day = date_tag.get_text(strip=True).replace(weekday, "").strip()
                        date = f"{weekday} {day}"

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

                            time = time_obj.strftime("%H:%M")
                        except ValueError:
                            print(f"Error parsing time: {time_str} or date: {day}")
                            time = time_str

                        date_time_mapping.append({"header": date_header, "date": date, "time": time, "year": match_year, "matches": []})

                if not date_time_mapping:
                    print(f"No date-time headers found for matchday {matchday}.")
                    continue

                current_index = 0
                score_bugs = soup.find_all("score-bug", class_="ng-star-inserted")
                for score_bug in score_bugs:
                    if current_index >= len(date_time_mapping):
                        print(f"Error: current_index {current_index} out of range for date_time_mapping.")
                        break

                    while current_index < len(date_time_mapping) - 1 and date_time_mapping[current_index + 1]["header"].find_next("score-bug") == score_bug:
                        current_index += 1
                    date_time_mapping[current_index]["matches"].append(score_bug)

                for entry in date_time_mapping:
                    date = entry["date"]
                    time = entry["time"]
                    match_year = entry["year"]
                    for score_bug in entry["matches"]:
                        try:
                            home_team_tag = score_bug.find('div', class_=["cell home", "cell home white"])
                            home_team = home_team_tag.find('div', class_="tlc").text.strip() if home_team_tag else 'Unknown'

                            if [date, match_year, time, home_team] not in self.match_results:
                                self.match_results.append([
                                    date, match_year, time, home_team
                                ])
                        except Exception as e:
                            print(f"Error extracting data for match in matchday {matchday}: {e}")
                            continue

            print(f"Finished fetching future matches for season {season}.")

    def save_match_results_to_csv(self, filename="future_date.csv"):
        # Speichere die CSV im angegebenen output_directory
        file_path = os.path.join(output_directory, filename)
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Date", "Year", "Time", "Home Team"])
            writer.writerows(self.match_results)
        print(f"CSV-Datei wurde gespeichert: {file_path}")

# Hauptteil des Programms
scraper = BundesligaStatsScraper(seasons, current_season, current_matchday)
scraper.fetch_future_match_data()
scraper.save_match_results_to_csv("future_date.csv")
