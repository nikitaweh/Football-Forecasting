# `transferdata.py`

Source: `Sports Api Data/Player Profiles/Unfiltered/Code/transferdata.py`

## Überblick

Dieses Skript kapselt mehrere Verarbeitungsschritte in Funktionen und dient als Datenpipeline innerhalb des Repos.

## Zweck / Responsibilities

- Liest Quelldaten aus konfigurierten Eingabedateien oder Datenordnern ein.
- Schreibt aufbereitete Ergebnisse in Projektdateien oder Zieltabellen.
- Kann als geplanter Job ueber einen Scheduler ausgefuehrt werden.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `fetch_transfer_history()`: Ruft Quelldaten ab und verarbeitet die Antwort fuer die weitere Nutzung.

## Inputs / Outputs & Side-effects

**Inputs**
- `INPUT_JSON`: `r"C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection/players_profiles_78.json"`

**Outputs**
- `OUTPUT_JSON`: `r"C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection/transferhistory_78.json"`

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
- `http.client`
- `json`
- `os`
- `time`

## Beispiel

- Typischer Aufruf: ``python "Sports Api Data/Player Profiles/Unfiltered/Code/transferdata.py"``

## Edge Cases / Notes

- Beim Direktstart kann das Skript nach der ersten Verarbeitung im Scheduler weiterlaufen.
- Unerwartete oder leere Quelldateien fuehren typischerweise zu fruehen Fehlern oder leeren DataFrames oder Listen.
- Bestehende Zieldateien koennen bei jedem Lauf ueberschrieben oder ergaenzt werden.

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Sammelt API-Football-Rohdaten fuer transferdata und speichert sie fuer die nachgelagerte Verarbeitung.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `fetch_transfer_history(refresh_existing=False)`
  Verwendet `set`, `sorted`, `glob.glob`, `open`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `open(path, 'r', encoding='utf-8')`
- `json.load(f)`
- `data.get('players', [])`
- `p.get('player_id')`
- `open(OUTPUT_JSON, 'r', encoding='utf-8')`
- `json.load(f).get('transfers_by_player', {})`
- `all_transfers.get(pid)`
- `json.loads(raw)`
- `obj.get('response', [])`
- `entry.get('transfers', [])`
- `move.get('teams', {})`
- `teams.get('in')`
- `teams.get('out')`
- `entry.get('team')`
- `entry.get('league')`
- `open(OUTPUT_JSON, 'w', encoding='utf-8')`
- `json.dump({'generated_at': generated_at, 'transfers_by_player': all_transfers}, f, ensure_ascii=False, indent=2)`
- `sched.start()`

### Konfiguration und Environment

- `INPUT_DIR = 'C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection'`
- `INPUT_PATTERN = os.path.join(INPUT_DIR, 'players_profiles*.json')`
- `OUTPUT_JSON = 'C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection/transferhistory_78.json'`
- `API_HOST = 'v3.football.api-sports.io'`
- `API_KEY = <Zugangsdaten nicht abgebildet>`
- `HEADERS = <Zugangsdaten nicht abgebildet>`

### Imports und interne Abhaengigkeiten

- `import glob`
- `import json`
- `import os`
- `import time`
- `import http.client`
- `from datetime import datetime`
- `from apscheduler.schedulers.blocking import BlockingScheduler`
- `from apscheduler.triggers.cron import CronTrigger`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/Player Profiles/Unfiltered/Code/transferdata.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `Exception`, `json.JSONDecodeError`.
- Ein Scheduler oder eine Endlosschleife ist vorhanden; der Standardlauf kann dauerhaft aktiv bleiben.
