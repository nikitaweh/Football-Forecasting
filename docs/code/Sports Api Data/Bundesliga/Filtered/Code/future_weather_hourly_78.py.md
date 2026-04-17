# `future_weather_hourly_78.py`

Source: `Sports Api Data/Bundesliga/Filtered/Code/future_weather_hourly_78.py`

## Überblick

Dieses Skript sammelt, bereinigt oder exportiert Wetterdaten fuer das Projekt.

## Zweck / Responsibilities

- Schreibt aufbereitete Ergebnisse in Projektdateien oder Zieltabellen.
- Kommuniziert mit externen APIs und verarbeitet deren Antworten weiter.
- Kann als geplanter Job ueber einen Scheduler ausgefuehrt werden.
- Transformiert tabellarische Daten ueber DataFrames und CSV-Operationen.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `get_weather_offsets(match_dt)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `_load_stammdaten()`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `_load_team_coords()`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `_parse_stammdaten_datetime(date_str, time_str)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `_load_matches_in_window(start_local, end_local)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `_build_future_fixtures(now_local)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `_build_forecast_index(entries)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `_empty_forecast()`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `_fetch_forecast(lat, lon)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `_pick_forecast_entry(forecast, target_utc)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `_extract_weather(entry, source)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `_write_output_csv(df)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `main()`: Startet den typischen Ausfuehrungsablauf des Skripts.
- `run_if_match_hour()`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.

## Inputs / Outputs & Side-effects

**Inputs**
- Keine klar benannten Eingabepfade erkannt; Details stehen im Quelltext.

**Outputs**
- `OUTPUT_COLUMNS`: `[`

**Side-effects**
- Schreibt Dateien im Projektverzeichnis oder aktualisiert bestehende Artefakte.
- Fuehrt Netzwerkzugriffe auf externe APIs aus.
- Kann als lang laufender Scheduler-Prozess gestartet werden.
- Schreibt Laufzeit- und Fehlerhinweise auf ``stdout``.
- Legt Zielordner bei Bedarf automatisch an.

## Konfiguration / Env

- `API_KEY`: `"abcc68d734dd721e64e567bb8c6c4bb8"`
- Keine offensichtliche Nutzung von Umgebungsvariablen erkannt.

## Interne Abhaengigkeiten / Imports

- `apscheduler.schedulers.blocking.BlockingScheduler`
- `apscheduler.triggers.cron.CronTrigger`
- `datetime.datetime`
- `os`
- `pandas`
- `requests`
- `zoneinfo.ZoneInfo`

## Beispiel

- Typischer Aufruf: ``python "Sports Api Data/Bundesliga/Filtered/Code/future_weather_hourly_78.py"``

## Edge Cases / Notes

- Netzwerkfehler, Timeouts oder API-Limits koennen den Lauf unterbrechen oder zu leeren Ergebnissen fuehren.
- Beim Direktstart kann das Skript nach der ersten Verarbeitung im Scheduler weiterlaufen.
- Unerwartete oder leere Quelldateien fuehren typischerweise zu fruehen Fehlern oder leeren DataFrames oder Listen.
- Bestehende Zieldateien koennen bei jedem Lauf ueberschrieben oder ergaenzt werden.

