# `match statistics.py`

Source: `Sports Api Data/Bundesliga/Filtered/Code/match statistics.py`

## Überblick

Dieses Skript kapselt mehrere Verarbeitungsschritte in Funktionen und dient als Datenpipeline innerhalb des Repos.

## Zweck / Responsibilities

- Kann als geplanter Job ueber einen Scheduler ausgefuehrt werden.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `parse_int(value)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `parse_float(value)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `parse_percentage(value)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `get_stat_value(stat_list, stat_type)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `convert_match_statistics_to_csv()`: Konvertiert Quelldaten in ein neues Ausgabeformat.

## Inputs / Outputs & Side-effects

**Inputs**
- Keine klar benannten Eingabepfade erkannt; Details stehen im Quelltext.

**Outputs**
- Keine klar benannten Ausgabepfade erkannt; das Modul kann trotzdem Daten im Lauf verarbeiten oder drucken.

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

## Beispiel

- Typischer Aufruf: ``python "Sports Api Data/Bundesliga/Filtered/Code/match statistics.py"``

## Edge Cases / Notes

- Beim Direktstart kann das Skript nach der ersten Verarbeitung im Scheduler weiterlaufen.
- Unerwartete oder leere Quelldateien fuehren typischerweise zu fruehen Fehlern oder leeren DataFrames oder Listen.

