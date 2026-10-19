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

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Bereitet Players profiles fuer die tabellarische Weiterverarbeitung auf.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `convert_player_information_csv()`
  Verwendet `set`, `sorted`, `glob.glob`, `print`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `open(path, 'r', encoding='utf-8')`
- `json.load(f)`
- `file_data.get('players', [])`
- `p.get('player_id')`
- `open(SEASONS_FILE, 'r', encoding='utf-8')`
- `open(TRANSFERS_FILE, 'r', encoding='utf-8')`
- `seasons_data.get('players_seasons', {})`
- `profiles_data.get('players', [])`
- `p.get('firstname', '')`
- `p.get('lastname', '')`
- `p.get('birth_date', '')`
- `p.get('nationality', '')`
- `p.get('height', '')`
- `p.get('weight', '')`
- `seasons_data.get('players_seasons', {}).get(pid, [])`
- `transfers_data.get('transfers_by_player', {}).get(pid, [])`
- `transfers_data.get('transfers_by_player', {})`
- `entry.get('update', '')`
- `entry.get('transfers', [])`
- `m.get('date', '')`
- `m.get('teams', {}).get('in', {}).get('name')`
- `m.get('teams', {}).get('in', {})`

### Konfiguration und Environment

- `BASE_DIR = 'C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection'`
- `PROFILES_PATTERN = os.path.join(BASE_DIR, 'players_profiles*.json')`
- `SEASONS_FILE = os.path.join(BASE_DIR, 'players_activity_78.json')`
- `TRANSFERS_FILE = os.path.join(BASE_DIR, 'transferhistory_78.json')`
- `OUTPUT_CSV_FILE = os.path.join('C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Filtered/Datacollection', 'player_information_78.csv')`

### Imports und interne Abhaengigkeiten

- `import glob`
- `import json`
- `import csv`
- `import os`
- `from datetime import datetime`
- `from apscheduler.schedulers.blocking import BlockingScheduler`
- `from apscheduler.triggers.cron import CronTrigger`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/Player Profiles/Filtered/Code/Players profiles.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `Exception`.
- Ein Scheduler oder eine Endlosschleife ist vorhanden; der Standardlauf kann dauerhaft aktiv bleiben.
