import requests
from bs4 import BeautifulSoup
import pandas as pd  # Stelle sicher, dass du Pandas importierst

# Definiere die Saison
seasons = ["2024-2025"]

# Anzahl der Spieltage in der Bundesliga
total_matchdays = 34

# Definiere die aktuelle Saison und den aktuellen Spieltag
current_season = "2024-2025"  # Setze dies auf die aktuelle Saison
current_matchday = 9  # Setze dies auf den aktuellen Spieltag

# Liste zum Speichern der Ergebnisse
results_list = []

# Schleife durch jede Saison
for season in seasons:
    print(f"Fetching results for season: {season}")

    # Schleife durch alle Spieltage der Saison
    for matchday in range(1, total_matchdays + 1):
        # Breche die Schleife ab, wenn die aktuelle Saison und der aktuelle Spieltag erreicht wurden
        if season == current_season and matchday > current_matchday:
            print(f"Reached current matchday {current_matchday} of the season {current_season}. Stopping further fetching.")
            break

        url = f"https://www.bundesliga.com/en/bundesliga/matchday/{season}/{matchday}"
        print(f"Fetching results for matchday: {matchday} in season: {season}")

        # Anfrage an die Webseite senden
        response = requests.get(url)

        # HTML-Dokument parsen
        soup = BeautifulSoup(response.content, "html.parser")

        # Daten extrahieren
        results = soup.find_all("score-bug", class_="ng-star-inserted")

        # Wenn keine Ergebnisse gefunden wurden
        if not results:
            print(f"No results found for matchday {matchday}.")
            continue  # Gehe zur nächsten Spieltag, falls keine Ergebnisse

        # Schleife durch die Ergebnisse eines Spieltags
        for score in results:
            try:
                # Heimteam und -ergebnis extrahieren (prüft auf beide möglichen Klassen)
                home_team_tag = score.find('div', class_="cell home") or score.find('div', class_="cell home white")
                away_team_tag = score.find('div', class_="cell away") or score.find('div', class_="cell away white")

                # Überprüfen, ob die Tags vorhanden sind
                if home_team_tag is None or away_team_tag is None:
                    print(f"Error: Home or away team not found for matchday {matchday}.")
                    continue  # Überspringt dieses Spiel und fährt mit dem nächsten fort

                home_team = home_team_tag.find('div', class_="tlc").text.strip() if home_team_tag.find('div', class_="tlc") else 'Unknown'
                home_score = home_team_tag.find('div', class_="score ng-star-inserted").text.strip() if home_team_tag.find('div', class_="score ng-star-inserted") else '0'
                
                away_team = away_team_tag.find('div', class_="tlc").text.strip() if away_team_tag.find('div', class_="tlc") else 'Unknown'
                away_score = away_team_tag.find('div', class_="score ng-star-inserted").text.strip() if away_team_tag.find('div', class_="score ng-star-inserted") else '0'

                # Ergebnis bestimmen
                home_score_int = int(home_score)  # Umwandlung in int
                away_score_int = int(away_score)  # Umwandlung in int

                if home_score_int > away_score_int:
                    result = 'win'
                elif home_score_int < away_score_int:
                    result = 'loss'
                else:
                    result = 'draw'

                # Ergebnis zur Liste hinzufügen
                results_list.append({
                    'home_team': home_team,
                    'home_score': home_score_int,
                    'away_team': away_team,
                    'away_score': away_score_int,
                    'result': result
                })

                # Debugging-Informationen ausgeben
                print(f"{home_team} {home_score} : {away_score} {away_team} -> {result}")

            except Exception as e:
                print(f"Fehler beim Extrahieren der Daten für matchday {matchday}: {e}")
                continue  # Überspringt dieses Ergebnis und fährt mit dem nächsten fort

        print()  # Leerzeile zur besseren Lesbarkeit zwischen den Spieltagen

    print(f"Finished fetching results for season: {season}\n")

# Nach dem Scraping die Ergebnisse in eine CSV-Datei speichern
if results_list:  # Prüfe, ob die Liste nicht leer ist
    results_df = pd.DataFrame(results_list)  # Konvertiere die Liste in einen DataFrame
    results_df.to_csv('Bundesliga_odds_results.csv', index=False)  # Speichere den DataFrame als CSV-Datei
    print("Results saved to Bundesliga_odds_results.csv")
else:
    print("No results to save.")
