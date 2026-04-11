# `Stammdaten_78.py`

Source: `Sports Api Data/Bundesliga/Filtered/Code/Stammdaten_78.py`

## Überblick

Dieses Skript kapselt mehrere Verarbeitungsschritte in Funktionen und dient als Datenpipeline innerhalb des Repos.

## Zweck / Responsibilities

- Liest Quelldaten aus konfigurierten Eingabedateien oder Datenordnern ein.
- Schreibt aufbereitete Ergebnisse in Projektdateien oder Zieltabellen.
- Kann als geplanter Job ueber einen Scheduler ausgefuehrt werden.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `convert_stammdaten_to_csv()`: Konvertiert Quelldaten in ein neues Ausgabeformat.

## Inputs / Outputs & Side-effects

**Inputs**
- `INPUT_FILE`: `r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"`

**Outputs**
- `OUTPUT_FILE`: `r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/Stammdaten_78.csv"`

**Side-effects**
- Schreibt Dateien im Projektverzeichnis oder aktualisiert bestehende Artefakte.
- Kann als lang laufender Scheduler-Prozess gestartet werden.
- Schreibt Laufzeit- und Fehlerhinweise auf ``stdout``.
- Legt Zielordner bei Bedarf automatisch an.

## Konfiguration / Env

- Keine markanten Top-Level-Konfigurationskonstanten erkannt.
- Keine offensichtliche Nutzung von Umgebungsvariablen erkannt.

## Interne Abhaengigkeiten / Imports

- `apscheduler.schedulers.blocking.BlockingScheduler`
- `apscheduler.triggers.cron.CronTrigger`
- `csv`
- `datetime.datetime`
- `json`
- `os`
- `zoneinfo.ZoneInfo`

## Beispiel

- Typischer Aufruf: ``python "Sports Api Data/Bundesliga/Filtered/Code/Stammdaten_78.py"``

## Edge Cases / Notes

- Beim Direktstart kann das Skript nach der ersten Verarbeitung im Scheduler weiterlaufen.
- Unerwartete oder leere Quelldateien fuehren typischerweise zu fruehen Fehlern oder leeren DataFrames oder Listen.

