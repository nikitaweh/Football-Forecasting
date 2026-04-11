# `Players profiles.py`

Source: `Sports Api Data/Player Profiles/Filtered/Code/Players profiles.py`

## Überblick

Dieses Skript verarbeitet Spieler- oder Profilinformationen und bereitet sie fuer die weitere Nutzung auf.

## Zweck / Responsibilities

- Schreibt aufbereitete Ergebnisse in Projektdateien oder Zieltabellen.
- Kann als geplanter Job ueber einen Scheduler ausgefuehrt werden.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `convert_player_information_csv()`: Konvertiert Quelldaten in ein neues Ausgabeformat.

## Inputs / Outputs & Side-effects

**Inputs**
- Keine klar benannten Eingabepfade erkannt; Details stehen im Quelltext.

**Outputs**
- `OUTPUT_CSV_FILE`: `os.path.join(r"C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Filtered/Datacollection","player_information_78.csv")`

**Side-effects**
- Schreibt Dateien im Projektverzeichnis oder aktualisiert bestehende Artefakte.
- Kann als lang laufender Scheduler-Prozess gestartet werden.
- Schreibt Laufzeit- und Fehlerhinweise auf ``stdout``.
- Legt Zielordner bei Bedarf automatisch an.

## Konfiguration / Env

- `PROFILES_FILE`: `os.path.join(BASE_DIR, "players_profiles_78.json")`
- `SEASONS_FILE`: `os.path.join(BASE_DIR, "players_activity_78.json")`
- `TRANSFERS_FILE`: `os.path.join(BASE_DIR, "transferhistory_78.json")`
- Keine offensichtliche Nutzung von Umgebungsvariablen erkannt.

## Interne Abhaengigkeiten / Imports

- `apscheduler.schedulers.blocking.BlockingScheduler`
- `apscheduler.triggers.cron.CronTrigger`
- `csv`
- `datetime.datetime`
- `json`
- `os`

## Beispiel

- Typischer Aufruf: ``python "Sports Api Data/Player Profiles/Filtered/Code/Players profiles.py"``

## Edge Cases / Notes

- Beim Direktstart kann das Skript nach der ersten Verarbeitung im Scheduler weiterlaufen.
- Unerwartete oder leere Quelldateien fuehren typischerweise zu fruehen Fehlern oder leeren DataFrames oder Listen.

