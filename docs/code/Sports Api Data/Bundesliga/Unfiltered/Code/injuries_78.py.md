# `injuries_78.py`

Source: `Sports Api Data/Bundesliga/Unfiltered/Code/injuries_78.py`

## Überblick

Dieses Skript verarbeitet Verletzungsdaten, typischerweise ueber API-Abrufe oder nachgelagerte Filterung.

## Zweck / Responsibilities

- Liest Quelldaten aus konfigurierten Eingabedateien oder Datenordnern ein.
- Schreibt aufbereitete Ergebnisse in Projektdateien oder Zieltabellen.
- Kommuniziert mit externen APIs und verarbeitet deren Antworten weiter.
- Kann als geplanter Job ueber einen Scheduler ausgefuehrt werden.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `fetch_injuries(full_load=False)`: Full-Load ist deaktiviert. Es werden immer neue Fixtures abgerufen und leere EintrÃ¤ge erneut abgefragt.

## Inputs / Outputs & Side-effects

**Inputs**
- `INPUT_FILE`: `r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"`

**Outputs**
- `OUTPUT_FILE`: `r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/injuries_league_78.json"`

**Side-effects**
- Schreibt Dateien im Projektverzeichnis oder aktualisiert bestehende Artefakte.
- Fuehrt Netzwerkzugriffe auf externe APIs aus.
- Kann als lang laufender Scheduler-Prozess gestartet werden.
- Schreibt Laufzeit- und Fehlerhinweise auf ``stdout``.
- Legt Zielordner bei Bedarf automatisch an.

## Konfiguration / Env

- `API_URL`: `"https://v3.football.api-sports.io/injuries"`
- `API_KEY`: `"5fa2372f2bfcbedb8ef7b85c86f0a27a"`
- `HEADERS`: `{`
- Keine offensichtliche Nutzung von Umgebungsvariablen erkannt.

## Interne Abhaengigkeiten / Imports

- `apscheduler.schedulers.blocking.BlockingScheduler`
- `apscheduler.triggers.cron.CronTrigger`
- `argparse`
- `datetime.datetime`
- `json`
- `os`
- `requests`
- `time`

## Beispiel

- Typischer Aufruf: ``python "Sports Api Data/Bundesliga/Unfiltered/Code/injuries_78.py"``

## Edge Cases / Notes

- Netzwerkfehler, Timeouts oder API-Limits koennen den Lauf unterbrechen oder zu leeren Ergebnissen fuehren.
- Beim Direktstart kann das Skript nach der ersten Verarbeitung im Scheduler weiterlaufen.
- Unerwartete oder leere Quelldateien fuehren typischerweise zu fruehen Fehlern oder leeren DataFrames oder Listen.
- Bestehende Zieldateien koennen bei jedem Lauf ueberschrieben oder ergaenzt werden.

