# `match_statistics._78.py`

Source: `Sports Api Data/Bundesliga/Unfiltered/Code/match_statistics._78.py`

## Überblick

Dieses Skript kapselt mehrere Verarbeitungsschritte in Funktionen und dient als Datenpipeline innerhalb des Repos.

## Zweck / Responsibilities

- Liest Quelldaten aus konfigurierten Eingabedateien oder Datenordnern ein.
- Schreibt aufbereitete Ergebnisse in Projektdateien oder Zieltabellen.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `remove_keys(obj, keys_to_remove)`: Entfernt rekursiv alle SchlÃ¼ssel aus dicts und nested Strukturen.
- `collect_match_statistics(full_load=False)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.

## Inputs / Outputs & Side-effects

**Inputs**
- `INPUT_FILE`: `r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"`

**Outputs**
- `OUTPUT_FILE`: `r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/match_statistics_league_78.json"`

**Side-effects**
- Schreibt Dateien im Projektverzeichnis oder aktualisiert bestehende Artefakte.
- Schreibt Laufzeit- und Fehlerhinweise auf ``stdout``.
- Legt Zielordner bei Bedarf automatisch an.

## Konfiguration / Env

- `API_KEY`: `"5fa2372f2bfcbedb8ef7b85c86f0a27a"`
- `HEADERS`: `{`
- Keine offensichtliche Nutzung von Umgebungsvariablen erkannt.

## Interne Abhaengigkeiten / Imports

- `argparse`
- `datetime.datetime`
- `http.client`
- `json`
- `os`
- `schedule`
- `time`

## Beispiel

- Typischer Aufruf: ``python "Sports Api Data/Bundesliga/Unfiltered/Code/match_statistics._78.py"``

## Edge Cases / Notes

- Unerwartete oder leere Quelldateien fuehren typischerweise zu fruehen Fehlern oder leeren DataFrames oder Listen.
- Bestehende Zieldateien koennen bei jedem Lauf ueberschrieben oder ergaenzt werden.

