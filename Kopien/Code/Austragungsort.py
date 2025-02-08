import os
import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime, timedelta

# Definiere den Ordner, in dem die Ausgabedatei gespeichert werden soll
output_directory = "C:/AI Projekt/KI-Projekt/Kopien/Datensammlungen"

# (Optional: Falls du den aktuellen Skriptpfad benötigst, kannst du das so ermitteln:)
# current_directory = os.path.dirname(os.path.abspath(__file__))

base_url = "https://www.bundesliga.com/en/bundesliga/matchday"
seasons = ["2017-2018", "2018-2019", "2019-2020", "2020-2021", "2021-2022", "2022-2023", "2023-2024", "2024-2025"]

def last_sunday(year, month):
    """Hilfsfunktion: Liefert den letzten Sonntag eines Monats."""
    last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    return last_day - timedelta(days=(last_day.weekday() + 1) % 7)

class MatchScraper:
    def __init__(self, base_url, seasons):
        self.base_url = base_url
        self.seasons = seasons
        self.team_mapping = {}  # {Kürzel: Vollständiger Name}
        self.stadium_mapping = {}  # {Vollständiger Name: Stadionname}
        self.merged_teams = {"HDH": "FCH"}  # Kürzel, die zusammengeführt werden

    def fetch_and_parse(self, url):
        """Holt die HTML-Inhalte von der URL und parst sie."""
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch URL {url}, Status Code: {response.status_code}")
        soup = BeautifulSoup(response.content, "html.parser")
        return soup

    def scrape_team_mapping(self):
        """Iteriert über alle Saisons und extrahiert das Team-Mapping."""
        for season in self.seasons:
            # Dynamische URL für den 1. Spieltag der Saison
            url = f"{self.base_url}/{season}/2"
            try:
                soup = self.fetch_and_parse(url)
                fixtures = soup.find_all("a", class_="matchFixture")
                for fixture in fixtures:
                    try:
                        # Heimteam-Daten extrahieren
                        home_team_name = fixture.find("match-team", {"side": "home"}).find("div", class_="name d-none d-lg-block d-xl-block").text.strip()
                        home_team_short = fixture.find("div", class_="cell home").find("div", class_="tlc").text.strip()
                        home_team_short = self.resolve_team_short(home_team_short)
                        self.team_mapping[home_team_short] = home_team_name
                        # Auswärtsteam-Daten extrahieren
                        away_team_name = fixture.find("match-team", {"side": "away"}).find("div", class_="name d-none d-lg-block d-xl-block").text.strip()
                        away_team_short = fixture.find("div", class_="cell away").find("div", class_="tlc").text.strip()
                        away_team_short = self.resolve_team_short(away_team_short)
                        self.team_mapping[away_team_short] = away_team_name
                    except Exception:
                        pass  # Fehler in einem Fixture ignorieren
            except Exception:
                pass  # Fehler beim Abrufen einer Saison ignorieren

    def resolve_team_short(self, team_short):
        """Gibt das aufgelöste Kürzel zurück, falls es zusammengeführt wird."""
        return self.merged_teams.get(team_short, team_short)

    def add_stadium_mapping(self):
        """Manuelles Mapping der Stadien zu den vollständigen Teamnamen."""
        self.stadium_mapping = {
            "FC Bayern München": "Munich",
            "Bayer 04 Leverkusen": "Leverkusen",
            "VfL Wolfsburg": "Wolfsburg",
            "Borussia Dortmund": "Dortmund",
            "1. FSV Mainz 05": "Mainz",
            "Hannover 96": "Hanover",
            "Hamburger SV": "Hamburg",
            "FC Augsburg": "Augsburg",
            "Hertha BSC": "Berlin",
            "TSG Hoffenheim": "Hoffenheim",
            "SV Werder Bremen": "Bremen",
            "FC Schalke 04": "Gelsenkirchen",
            "RB Leipzig": "Leipzig",
            "SC Freiburg": "Freiburg im Breisgau",
            "Eintracht Frankfurt": "Frankfurt",
            "Borussia Mönchengladbach": "Gladbach",
            "1. FC Köln": "Cologne",
            "Fortuna Düsseldorf": "Düsseldorf",
            "1. FC Nürnberg": "Nuremberg",
            "VfB Stuttgart": "Stuttgart",
            "SC Paderborn 07": "Paderborn",
            "1. FC Union Berlin": "Berlin",
            "DSC Arminia Bielefeld": "Bielefeld",
            "VfL Bochum 1848": "Bochum",
            "SV Darmstadt 98": "Darmstadt",
            "Holstein Kiel": "Kiel",
            "FC St. Pauli": "Hamburg",
            "1. FC Heidenheim 1846": "Heidenheim",
            "SpVgg Greuther Fürth": "Fürth"
        }

    def save_to_csv(self, filename="team_location.csv"):
        """Speichert das Team-Kürzel und zugehörige Stadionnamen in einer CSV-Datei im angegebenen Ausgabeverzeichnis."""
        file_path = os.path.join(output_directory, filename)
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Team Short", "Stadt"])  # CSV-Header
            for team_short, team_full in sorted(self.team_mapping.items()):
                stadium_name = self.stadium_mapping.get(team_full, "Unknown Stadium")
                writer.writerow([team_short, stadium_name])
        print(f"CSV-Datei wurde gespeichert: {file_path}")

# Nutzung des Scraping-Tools
scraper = MatchScraper(base_url, seasons)
scraper.scrape_team_mapping()  # Teamnamen und Kürzel scrapen
scraper.add_stadium_mapping()  # Stadionnamen zuordnen
scraper.save_to_csv("team_location.csv")
