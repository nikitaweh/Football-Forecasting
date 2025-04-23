#!/usr/bin/env python3
import os
import csv
import time
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

# Konfiguration
output_directory = "C:/AI Projekt/KI-Projekt/Kopien/Datensammlungen"
seasons = ["2024-2025"]
current_season = "2024-2025"
total_matchdays = 34  # Gesamtzahl der Spieltage in der Saison

# --------------------------------------------------------------------------------
# Scraper-Klasse (basierend auf dem bisherigen Code)
# --------------------------------------------------------------------------------
class BundesligaStatsScraper:
    def __init__(self, seasons, current_season, total_matchdays=34):
        self.seasons = seasons
        self.current_season = current_season
        self.total_matchdays = total_matchdays
        self.current_matchday = 0  # wird dynamisch aktualisiert
        self.head_to_head_stats = defaultdict(lambda: {
            'games': 0, 'home_goals': 0, 'away_goals': 0,
            'home_wins': 0, 'away_wins': 0, 'draws': 0
        })
        self.match_results = []  # enthält alle Spiele (ohne Match-ID)
        self.merged_teams = {"HDH": "FCH"}  # Kürzel zum Zusammenführen
        self.match_id_counter = 1  # Zähler für eindeutige Match-IDs

        # Lade bereits gespeicherte Ergebnisse (falls vorhanden)
        self.existing_results = self.load_existing_results("past_season_results.csv")
        if self.existing_results:
            self.match_results = self.existing_results
            # Bestimme den zuletzt gespeicherten Spieltag (als Zahl)
            self.last_stored_matchday = max(int(row[1]) for row in self.match_results)
        else:
            self.last_stored_matchday = 0

    def load_existing_results(self, filename):
        file_path = os.path.join(output_directory, filename)
        if os.path.exists(file_path):
            with open(file_path, mode="r", newline='', encoding="utf-8") as file:
                reader = csv.reader(file)
                header = next(reader, None)  # Überspringe Header
                results = [row[1:] for row in reader]  # Überspringe die Match-ID-Spalte
            return results
        else:
            return None

    def scrape_matchday(self, season, matchday):
        url = f"https://www.bundesliga.com/en/bundesliga/matchday/{season}/{matchday}"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        date_headers = soup.find_all("match-date-header", class_="ng-star-inserted")
        date_time_mapping = []

        # Hilfsfunktion: Bestimme den letzten Sonntag im Monat
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
                date_str = f"{weekday} {day}"  # z. B. "Friday 24 August"
                time_str = time_tag.get_text(strip=True)
                try:
                    time_obj = datetime.strptime(time_str, "%H:%M")
                    match_month = datetime.strptime(day, "%d %B").month
                    if match_month > 6:  # Spiele ab Juli gehören zum Startjahr
                        match_year = season_start_year
                    else:
                        match_year = season_end_year
                    last_sunday_march = last_sunday(match_year, 3)
                    last_sunday_october = last_sunday(match_year, 10)
                    match_date = datetime.strptime(f"{day} {match_year}", "%d %B %Y")
                    if last_sunday_march <= match_date < last_sunday_october:
                        time_obj += timedelta(hours=2)  # Sommerzeit
                    else:
                        time_obj += timedelta(hours=1)  # Winterzeit
                    time_formatted = time_obj.strftime("%H:%M")
                except ValueError:
                    time_formatted = time_str
                date_time_mapping.append({
                    "header": date_header, 
                    "date": date_str, 
                    "time": time_formatted, 
                    "year": match_year, 
                    "matches": []
                })

        if not date_time_mapping:
            return []  # Keine Daten gefunden

        # Verknüpfe score-bug-Elemente mit dem passenden Datum/Uhrzeit-Eintrag
        current_index = 0
        score_bugs = soup.find_all("score-bug", class_="ng-star-inserted")
        for score_bug in score_bugs:
            if current_index >= len(date_time_mapping):
                break
            while (current_index < len(date_time_mapping) - 1 and 
                   date_time_mapping[current_index + 1]["header"].find_next("score-bug") == score_bug):
                current_index += 1
            date_time_mapping[current_index]["matches"].append(score_bug)

        matchday_results = []
        for entry in date_time_mapping:
            date_str = entry["date"]
            time_str = entry["time"]
            match_year = entry["year"]
            for score_bug in entry["matches"]:
                try:
                    home_team_tag = score_bug.find('div', class_=["cell home", "cell home white"])
                    away_team_tag = score_bug.find('div', class_=["cell away", "cell away white"])
                    home_team = (home_team_tag.find('div', class_="tlc").text.strip() 
                                 if home_team_tag else 'Unknown')
                    away_team = (away_team_tag.find('div', class_="tlc").text.strip() 
                                 if away_team_tag else 'Unknown')
                    home_score = (home_team_tag.find('div', class_="score").text.strip() 
                                  if home_team_tag else '0')
                    away_score = (away_team_tag.find('div', class_="score").text.strip() 
                                  if away_team_tag else '0')
                    home_score_int = int(home_score)
                    away_score_int = int(away_score)
                    result = ("Win" if home_score_int > away_score_int 
                              else "Loss" if home_score_int < away_score_int 
                              else "Draw")
                    home_team = self.resolve_team_short(home_team)
                    away_team = self.resolve_team_short(away_team)
                    
                    # Spiel-Daten als Liste (Match-ID wird später zugewiesen)
                    game = [
                        season,               # Saison
                        str(matchday),        # Spieltag
                        date_str,             # Datum inkl. Wochentag
                        str(match_year),      # Jahr
                        time_str,             # Uhrzeit
                        home_team, 
                        str(home_score_int),  
                        away_team, 
                        str(away_score_int),  
                        result
                    ]
                    matchday_results.append(game)
                except Exception as e:
                    print(f"Fehler beim Extrahieren der Daten für Spieltag {matchday}: {e}")
                    continue
        return matchday_results

    def fetch_match_data(self):
        for season in self.seasons:
            print(f"\nVerarbeite Saison: {season}")
            start_matchday = self.last_stored_matchday if self.last_stored_matchday > 0 else 1
            for matchday in range(start_matchday, self.total_matchdays + 1):
                print(f"\nScrape Spieltag {matchday} ...")
                scraped_results = self.scrape_matchday(season, matchday)
                if not scraped_results:
                    print(f"Keine Daten für Spieltag {matchday} gefunden – vermutlich wurden noch keine Spiele ausgetragen.")
                    break
                
                # Zähle, wie viele Spiele für diesen Spieltag bereits gespeichert wurden
                stored_count = sum(1 for row in self.match_results 
                                   if row[0] == season and row[1] == str(matchday))
                
                if len(scraped_results) > stored_count:
                    new_games = scraped_results[stored_count:]
                    print(f"Neue Spiele gefunden für Spieltag {matchday}: {len(new_games)} Spiel(e)")
                    self.match_results.extend(new_games)
                    # Update der Head-to-Head-Statistiken für die neuen Spiele
                    for game in new_games:
                        try:
                            home_score_int = int(game[6])
                            away_score_int = int(game[8])
                        except Exception:
                            home_score_int = 0
                            away_score_int = 0
                        self.update_head_to_head_stats(game[5], game[7], home_score_int, away_score_int)
                    self.current_matchday = matchday
                else:
                    print(f"Für Spieltag {matchday} wurden keine neuen Spiele gefunden.")
                    # Annahme: Bei 9 Spielen gilt der Spieltag als abgeschlossen
                    if stored_count == 9:
                        self.current_matchday = matchday
                        print(f"Spieltag {matchday} gilt als abgeschlossen.")
                    else:
                        print(f"Spieltag {matchday} ist noch nicht vollständig. Aktualisierung wird gestoppt.")
                        self.current_matchday = matchday
                        break
            print(f"\nSaison {season} verarbeitet. Aktueller Spieltag: {self.current_matchday}")

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
        file_path = os.path.join(output_directory, filename)
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Match ID", "Season", "Matchday", "Date", "Year", "Time", 
                             "Home Team", "Home Goals", "Away Team", "Away Goals", "Result"])
            sorted_results = sorted(self.match_results, key=lambda x: (x[0], int(x[1])))
            match_id = 1
            for row in sorted_results:
                writer.writerow([match_id] + row)
                match_id += 1

# --------------------------------------------------------------------------------
# Funktionen zum Einlesen der geplanten Startzeiten
# --------------------------------------------------------------------------------
def read_planned_start_times(csv_path):
    """
    Liest die CSV 'planned_start_times.csv' ein und berechnet:
      - geplanten Startzeitpunkt
      - Spielende: Annahme 120 Minuten Spielzeit + 15 Minuten Puffer (insgesamt 135 Minuten)
    """
    matches = []
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Annahme: "Day" im Format YYYY-MM-DD, "Planned Start Time" im Format HH:MM
            match_date = row["Day"].strip()
            planned_time = row["Planned Start Time"].strip()
            planned_start = datetime.strptime(match_date + " " + planned_time, "%Y-%m-%d %H:%M")
            # Spiel dauert 120 Minuten, plus 15 Minuten Puffer nach Spielende
            match_end = planned_start + timedelta(minutes=135)
            row["planned_start_datetime"] = planned_start
            row["match_end_datetime"] = match_end
            matches.append(row)
    return matches

# --------------------------------------------------------------------------------
# Scheduler-Logik
# --------------------------------------------------------------------------------
# Globale Instanz des Scrapers
scraper = BundesligaStatsScraper(seasons, current_season, total_matchdays)

def update_matches():
    now = datetime.now()
    print(f"\n[{now}] Prüfe geplante Spiele aus 'planned_start_times.csv' ...")
    matches = read_planned_start_times("planned_start_times.csv")
    active_match = False
    for match in matches:
        # Prüfe, ob der aktuelle Zeitpunkt zwischen geplantem Start und Spielende liegt
        if match["planned_start_datetime"] <= now <= match["match_end_datetime"]:
            print(f"Match {match['Match ID']} ({match['Home Team']}) ist aktiv – Update wird gestartet.")
            active_match = True
        else:
            print(f"Match {match['Match ID']} ({match['Home Team']}) ist nicht aktiv.")
    if active_match:
        print("Aktualisiere Spieldaten...")
        scraper.fetch_match_data()
        scraper.save_to_csv("head_to_head.csv")
        scraper.save_match_results_to_csv("past_season_results.csv")
    else:
        print("Keine aktiven Spiele – Update wird übersprungen.")

# --------------------------------------------------------------------------------
# Main: Scheduler starten
# --------------------------------------------------------------------------------
if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    # Update alle 15 Minuten ausführen
    scheduler.add_job(update_matches, 'interval', minutes=15)
    scheduler.start()
    print("Scheduler gestartet. Drücke Strg+C zum Beenden.")
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("Scheduler gestoppt.")
