# `historic_weather_data_78.py`

Source: `Sports Api Data/Bundesliga/Filtered/Code/historic_weather_data_78.py`

## Überblick

Dieses Skript sammelt, bereinigt oder exportiert Wetterdaten fuer das Projekt.

## Zweck / Responsibilities

- Kommuniziert mit externen APIs und verarbeitet deren Antworten weiter.
- Kann als geplanter Job ueber einen Scheduler ausgefuehrt werden.
- Transformiert tabellarische Daten ueber DataFrames und CSV-Operationen.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `get_weather_offsets(match_dt)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `_last_sunday(year, month)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `_adjust_request_time(dt_local)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `fetch_weather(lat, lon, dt_local)`: Ruft Quelldaten ab und verarbeitet die Antwort fuer die weitere Nutzung.
- `main(overwrite=False)`: Startet den typischen Ausfuehrungsablauf des Skripts.
- `query_api_data_by_match_id()`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `refresh_last_year_api_data()`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `run_if_match_hour()`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.

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
- Legt Zielordner bei Bedarf automatisch an.

## Konfiguration / Env

- `API_KEY`: `"8738a0031c3e965eaece939dbc7faf1d"`
- Keine offensichtliche Nutzung von Umgebungsvariablen erkannt.

## Interne Abhaengigkeiten / Imports

- `apscheduler.schedulers.blocking.BlockingScheduler`
- `apscheduler.triggers.cron.CronTrigger`
- `datetime.datetime`
- `os`
- `pandas`
- `requests`
- `time`
- `zoneinfo.ZoneInfo`

## Beispiel

- Typischer Aufruf: ``python "Sports Api Data/Bundesliga/Filtered/Code/historic_weather_data_78.py"``

## Edge Cases / Notes

- Netzwerkfehler, Timeouts oder API-Limits koennen den Lauf unterbrechen oder zu leeren Ergebnissen fuehren.
- Beim Direktstart kann das Skript nach der ersten Verarbeitung im Scheduler weiterlaufen.
- Unerwartete oder leere Quelldateien fuehren typischerweise zu fruehen Fehlern oder leeren DataFrames oder Listen.
- Bestehende Zieldateien koennen bei jedem Lauf ueberschrieben oder ergaenzt werden.

