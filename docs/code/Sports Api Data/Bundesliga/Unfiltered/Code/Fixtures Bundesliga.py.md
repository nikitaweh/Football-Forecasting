# `Fixtures Bundesliga.py`

Source: `Sports Api Data/Bundesliga/Unfiltered/Code/Fixtures Bundesliga.py`

## Überblick

Dieses Skript verarbeitet Spielplaene beziehungsweise Fixture-Daten fuer die Bundesliga-Pipeline.

## Zweck / Responsibilities

- Schreibt aufbereitete Ergebnisse in Projektdateien oder Zieltabellen.
- Kann als geplanter Job ueber einen Scheduler ausgefuehrt werden.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `remove_keys(obj, keys_to_remove)`: Entfernt rekursiv alle angegebenen SchlÃ¼ssel aus dicts und nested Strukturen.
- `fetch_fixtures_by_season(season)`: Ruft alle Fixtures einer Liga fÃ¼r eine gegebene Saison ab und entfernt logo/flag. (Ohne Filter auf 'Not Started' -> lÃ¤dt auch ungespiel...
- `save_all(fixtures)`: Speichert alle Fixtures als Liste unter dem last_run Zeitstempel.
- `fetch_full_fixtures()`: Holt alle Spiele seit Saison START_SEASON Ã¼ber Saison-Parameter.
- `fetch_new_fixtures()`: Holt nur neue Spiele basierend auf vorhandener Datei.

## Inputs / Outputs & Side-effects

**Inputs**
- Keine klar benannten Eingabepfade erkannt; Details stehen im Quelltext.

**Outputs**
- `OUTPUT_FILE`: `r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"`

**Side-effects**
- Schreibt Dateien im Projektverzeichnis oder aktualisiert bestehende Artefakte.
- Kann als lang laufender Scheduler-Prozess gestartet werden.
- Schreibt Laufzeit- und Fehlerhinweise auf ``stdout``.
- Legt Zielordner bei Bedarf automatisch an.

## Konfiguration / Env

- `API_KEY`: `"5fa2372f2bfcbedb8ef7b85c86f0a27a"`
- `HEADERS`: `{`
- Keine offensichtliche Nutzung von Umgebungsvariablen erkannt.

## Interne Abhaengigkeiten / Imports

- `apscheduler.schedulers.blocking.BlockingScheduler`
- `apscheduler.triggers.cron.CronTrigger`
- `datetime.datetime`
- `datetime.timezone`
- `http.client`
- `json`
- `os`

## Beispiel

- Typischer Aufruf: ``python "Sports Api Data/Bundesliga/Unfiltered/Code/Fixtures Bundesliga.py"``

## Edge Cases / Notes

- Beim Direktstart kann das Skript nach der ersten Verarbeitung im Scheduler weiterlaufen.
- Unerwartete oder leere Quelldateien fuehren typischerweise zu fruehen Fehlern oder leeren DataFrames oder Listen.
- Bestehende Zieldateien koennen bei jedem Lauf ueberschrieben oder ergaenzt werden.

