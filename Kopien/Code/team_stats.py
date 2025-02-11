import os
import csv
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from datetime import datetime, timedelta

# Definiere den Ordner, in dem die Ausgabedateien gespeichert werden sollen
output_directory = "C:/AI Projekt/KI-Projekt/Kopien/Datensammlungen"

# Falls benötigt, kannst du weiterhin den aktuellen Skriptpfad ermitteln
# current_directory = os.path.dirname(os.path.abspath(__file__))

seasons = ["2017-2018", "2018-2019", "2019-2020", "2020-2021", "2021-2022", "2022-2023", "2023-2024", "2024-2025"]
current_season = "2024-2025"
current_matchday = 21

class BundesligaStatsScraper:
    def __init__(self, seasons, current_season, current_matchday, total_matchdays=34):
        self.seasons = seasons
        self.current_season = current_season
        self.current_matchday = current_matchday
        self.total_matchdays = total_matchdays
        self.head_to_head_stats = defaultdict(lambda: {'games': 0, 'home_goals': 0, 'away_goals': 0, 'home_wins': 0, 'away_wins': 0, 'draws': 0})
        self.match_results = []
        self.merged_teams = {"HDH": "FCH"}  # Kürzel für das Merging
        self.match_id_counter = 1  # Zähler für eindeutige Match-IDs

    def fetch_match_data(self):
        for season in self.seasons:
            print(f"Fetching results for season: {season}")
            for matchday in range(1, self.total_matchdays + 1):
                if season == self.current_season and matchday > self.current_matchday:
                    print(f"Reached current matchday {self.current_matchday} of the season {self.current_season}. Stopping further fetching.")
                    break

                url = f"https://www.bundesliga.com/en/bundesliga/matchday/{season}/{matchday}"
                print(f"Matchday: {matchday} in season: {season}")

                response = requests.get(url)
                soup = BeautifulSoup(response.content, "html.parser")

                # Extrahiere alle `match-date-header` mit Datum und Zeit
                date_headers = soup.find_all("match-date-header", class_="ng-star-inserted")
                date_time_mapping = []  # Speichert `match-date-header`, Datum, Uhrzeit und zugehörige Spiele

                # Definiere Sommer- und Winterzeit basierend auf dem Jahr des Spiels
                def last_sunday(year, month):
                    last_day = datetime(year, month + 1, 1) - timedelta(days=1)
                    return last_day - timedelta(days=(last_day.weekday() + 1) % 7)

                season_start_year, season_end_year = map(int, season.split("-"))

                for date_header in date_headers:
                    date_tag = date_header.find("span", class_="day")
                    time_tag = date_header.find("span", class_="time")
                    if date_tag and time_tag:
                        weekday = date_tag.find("span", class_="bold").text.strip() if date_tag.find("span", class_="bold") else ""
                        day = date_tag.get_text(strip=True).replace(weekday, "").strip()
                        date = f"{weekday} {day}"  # Format: "Friday 24 August"

                        # Zeit anpassen basierend auf Sommer-/Winterzeit
                        time_str = time_tag.get_text(strip=True)
                        try:
                            time_obj = datetime.strptime(time_str, "%H:%M")

                            # Bestimme das Jahr des Spiels dynamisch basierend auf dem Monat
                            match_month = datetime.strptime(day, "%d %B").month
                            if match_month > 6:  # Spiele ab Juli gehören zum Startjahr
                                match_year = season_start_year
                            else:  # Spiele ab Januar gehören zum Endjahr
                                match_year = season_end_year

                            last_sunday_march = last_sunday(match_year, 3)
                            last_sunday_october = last_sunday(match_year, 10)
                            match_date = datetime.strptime(f"{day} {match_year}", "%d %B %Y")

                            if last_sunday_march <= match_date < last_sunday_october:
                                time_obj += timedelta(hours=2)  # Sommerzeit
                            else:
                                time_obj += timedelta(hours=1)  # Winterzeit

                            time = time_obj.strftime("%H:%M")
                        except ValueError:
                            print(f"Error parsing time: {time_str} or date: {day}")
                            time = time_str

                        date_time_mapping.append({"header": date_header, "date": date, "time": time, "year": match_year, "matches": []})

                if not date_time_mapping:
                    print(f"No date-time headers found for matchday {matchday}.")
                    continue

                # Verknüpfe `score-bug`-Elemente mit dem passenden `match-date-header`
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
                            away_team_tag = score_bug.find('div', class_=["cell away", "cell away white"])

                            home_team = home_team_tag.find('div', class_="tlc").text.strip() if home_team_tag else 'Unknown'
                            away_team = away_team_tag.find('div', class_="tlc").text.strip() if away_team_tag else 'Unknown'

                            home_score = home_team_tag.find('div', class_="score").text.strip() if home_team_tag else '0'
                            away_score = away_team_tag.find('div', class_="score").text.strip() if away_team_tag else '0'

                            home_score_int = int(home_score)
                            away_score_int = int(away_score)

                            result = "Win" if home_score_int > away_score_int else "Loss" if home_score_int < away_score_int else "Draw"

                            home_team = self.resolve_team_short(home_team)
                            away_team = self.resolve_team_short(away_team)

                            if [season, matchday, date, match_year, time, home_team, home_score_int, away_team, away_score_int, result] not in self.match_results:
                                self.match_results.append([
                                    season, matchday, date, match_year, time, home_team, home_score_int, away_team, away_score_int, result
                                ])
                                self.update_head_to_head_stats(home_team, away_team, home_score_int, away_score_int)
                        except Exception as e:
                            print(f"Error extracting data for match in matchday {matchday}: {e}")
                            continue

            print(f"Finished fetching results for season {season}.\n")

    def resolve_team_short(self, team_short):
        return self.merged_teams.get(team_short, team_short)

    def update_head_to_head_stats(self, home_team, away_team, home_goals, away_goals):
        home_team = self.resolve_team_short(home_team)
        away_team = self.resolve_team_short(away_team)
        matchup = (home_team, away_team)
        self.head_to_head_stats[matchup]['games'] += 1
        self.head_to_head_stats[matchup]['home_goals'] += home_goals
        self.head_to_head_stats[matchup]['away_goals'] += away_goals

        if home_goals > away_goals:
            self.head_to_head_stats[matchup]['home_wins'] += 1
        elif home_goals < away_goals:
            self.head_to_head_stats[matchup]['away_wins'] += 1
        else:
            self.head_to_head_stats[matchup]['draws'] += 1

    def save_to_csv(self, filename="head_to_head.csv"):
        # Speichere die CSV im output_directory
        file_path = os.path.join(output_directory, filename)
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                "Home Team", "Away Team", "Games", "Home Goals", "Away Goals",
                "Home Wins", "Away Wins", "Draws", "Avg Home Goals per Game",
                "Avg Away Goals per Game", "Home Win Rate", "Away Win Rate", "Draw Rate"
            ])

            for (home_team, away_team), stats in self.head_to_head_stats.items():
                games = stats['games']
                avg_home_goals = stats['home_goals'] / games if games > 0 else 0
                avg_away_goals = stats['away_goals'] / games if games > 0 else 0
                home_win_rate = (stats['home_wins'] / games) * 100 if games > 0 else 0
                away_win_rate = (stats['away_wins'] / games) * 100 if games > 0 else 0
                draw_rate = (stats['draws'] / games) * 100 if games > 0 else 0

                writer.writerow([
                    home_team, away_team, games,
                    stats['home_goals'], stats['away_goals'],
                    stats['home_wins'], stats['away_wins'], stats['draws'],
                    f"{avg_home_goals:.2f}", f"{avg_away_goals:.2f}",
                    f"{home_win_rate:.2f}", f"{away_win_rate:.2f}", f"{draw_rate:.2f}"
                ])

    def save_match_results_to_csv(self, filename="past_season_results.csv"):
        # Speichere die CSV im output_directory
        file_path = os.path.join(output_directory, filename)
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Match ID", "Season", "Matchday", "Date", "Year", "Time", "Home Team", "Home Goals", "Away Team", "Away Goals", "Result"])
            for match in self.match_results:
                writer.writerow([self.match_id_counter] + match)
                self.match_id_counter += 1

# Hauptteil des Programms
scraper = BundesligaStatsScraper(seasons, current_season, current_matchday)
scraper.fetch_match_data()
scraper.save_to_csv("head_to_head.csv")
scraper.save_match_results_to_csv("past_season_results.csv")
