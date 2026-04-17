# `lineups_78.py`

Source: `Sports Api Data/Bundesliga/Unfiltered/Code/lineups_78.py`

## Überblick

Dieses Skript verarbeitet Aufstellungen und ueberfuehrt Quelldaten in ein analysierbares Ausgabeformat.

## Zweck / Responsibilities

- Kann als geplanter Job ueber einen Scheduler ausgefuehrt werden.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `remove_keys(obj, keys_to_remove)`: Entfernt rekursiv alle SchlÃ¼ssel, die in keys_to_remove enthalten sind, aus Dictionaries und Listen.
- `collect_lineups(full_load=False)`: Holt die Lineup-Daten fÃ¼r alle Fixture-IDs aus der Input-Datei. Full-Load ist deaktiviert. Es werden immer neue Fixtures ergÃ¤nzt und le...

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
- `argparse`
- `datetime.datetime`
- `http.client`
- `json`
- `os`

## Beispiel

- Typischer Aufruf: ``python "Sports Api Data/Bundesliga/Unfiltered/Code/lineups_78.py"``

## Edge Cases / Notes

- Beim Direktstart kann das Skript nach der ersten Verarbeitung im Scheduler weiterlaufen.
- Unerwartete oder leere Quelldateien fuehren typischerweise zu fruehen Fehlern oder leeren DataFrames oder Listen.
- Bestehende Zieldateien koennen bei jedem Lauf ueberschrieben oder ergaenzt werden.

