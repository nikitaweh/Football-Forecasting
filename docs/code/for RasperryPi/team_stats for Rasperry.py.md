# `team_stats for Rasperry.py`

Source: `for RasperryPi/team_stats for Rasperry.py`

## Überblick

Dieses Skript verarbeitet Team-bezogene Stammdaten oder abgeleitete Team-Statistiken.

## Zweck / Responsibilities

- Kommuniziert mit externen APIs und verarbeitet deren Antworten weiter.
- Kann als geplanter Job ueber einen Scheduler ausgefuehrt werden.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `BundesligaStatsScraper`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `__init__(self, seasons, current_season, total_matchdays=34)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `load_existing_results(self, filename)`: Laedt Eingabedaten und gibt die aufbereitete Struktur zurueck.
- `scrape_matchday(self, season, matchday)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `last_sunday(year, month)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `fetch_match_data(self)`: Ruft Quelldaten ab und verarbeitet die Antwort fuer die weitere Nutzung.
- `resolve_team_short(self, team_short)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `update_head_to_head_stats(self, home_team, away_team, home_goals, away_goals)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `save_to_csv(self, filename="head_to_head.csv")`: Persistiert Ergebnisse in eine Datei oder ein Zielsystem.
- `save_match_results_to_csv(self, filename="past_season_results.csv")`: Persistiert Ergebnisse in eine Datei oder ein Zielsystem.
- `read_planned_start_times(csv_path)`: Liest die CSV 'planned_start_times.csv' ein und berechnet: - geplanten Startzeitpunkt - Spielende: Annahme 120 Minuten Spielzeit + 15 Min...
- `update_matches()`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.

## Inputs / Outputs & Side-effects

**Inputs**
- Keine klar benannten Eingabepfade erkannt; Details stehen im Quelltext.

**Outputs**
- Keine klar benannten Ausgabepfade erkannt; das Modul kann trotzdem Daten im Lauf verarbeiten oder drucken.

**Side-effects**
- Schreibt Dateien im Projektverzeichnis oder aktualisiert bestehende Artefakte.
- Fuehrt Netzwerkzugriffe auf externe APIs aus.
- Kann als lang laufender Scheduler-Prozess gestartet werden.
- Schreibt Laufzeit- und Fehlerhinweise auf ``stdout``.

## Konfiguration / Env

- Keine markanten Top-Level-Konfigurationskonstanten erkannt.
- Keine offensichtliche Nutzung von Umgebungsvariablen erkannt.

## Interne Abhaengigkeiten / Imports

- `apscheduler.schedulers.background.BackgroundScheduler`
- `bs4.BeautifulSoup`
- `collections.defaultdict`
- `csv`
- `datetime.datetime`
- `datetime.timedelta`
- `os`
- `requests`
- `time`

## Beispiel

- Typischer Aufruf: ``python "for RasperryPi/team_stats for Rasperry.py"``

## Edge Cases / Notes

- Netzwerkfehler, Timeouts oder API-Limits koennen den Lauf unterbrechen oder zu leeren Ergebnissen fuehren.
- Beim Direktstart kann das Skript nach der ersten Verarbeitung im Scheduler weiterlaufen.

