# `player activity.py`

Source: `Sports Api Data/Player Profiles/Unfiltered/Code/player activity.py`

## Überblick

Dieses Skript verarbeitet Spieler- oder Profilinformationen und bereitet sie fuer die weitere Nutzung auf.

## Zweck / Responsibilities

- Liest Quelldaten aus konfigurierten Eingabedateien oder Datenordnern ein.
- Schreibt aufbereitete Ergebnisse in Projektdateien oder Zieltabellen.
- Kommuniziert mit externen APIs und verarbeitet deren Antworten weiter.
- Kann als geplanter Job ueber einen Scheduler ausgefuehrt werden.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `fetch_player_activity()`: Ruft Quelldaten ab und verarbeitet die Antwort fuer die weitere Nutzung.

## Inputs / Outputs & Side-effects

**Inputs**
- `INPUT_JSON`: `r"C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection/players_profiles_78.json"`

**Outputs**
- `OUTPUT_JSON`: `r"C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection/players_activity_78.json"`

**Side-effects**
- Schreibt Dateien im Projektverzeichnis oder aktualisiert bestehende Artefakte.
- Fuehrt Netzwerkzugriffe auf externe APIs aus.
- Kann als lang laufender Scheduler-Prozess gestartet werden.
- Schreibt Laufzeit- und Fehlerhinweise auf ``stdout``.
- Legt Zielordner bei Bedarf automatisch an.

## Konfiguration / Env

- `API_URL`: `"https://v3.football.api-sports.io/players/seasons"`
- `HEADERS`: `{`
- Keine offensichtliche Nutzung von Umgebungsvariablen erkannt.

## Interne Abhaengigkeiten / Imports

- `apscheduler.schedulers.blocking.BlockingScheduler`
- `apscheduler.triggers.cron.CronTrigger`
- `json`
- `os`
- `requests`
- `time`

## Beispiel

- Typischer Aufruf: ``python "Sports Api Data/Player Profiles/Unfiltered/Code/player activity.py"``

## Edge Cases / Notes

- Netzwerkfehler, Timeouts oder API-Limits koennen den Lauf unterbrechen oder zu leeren Ergebnissen fuehren.
- Beim Direktstart kann das Skript nach der ersten Verarbeitung im Scheduler weiterlaufen.
- Unerwartete oder leere Quelldateien fuehren typischerweise zu fruehen Fehlern oder leeren DataFrames oder Listen.
- Bestehende Zieldateien koennen bei jedem Lauf ueberschrieben oder ergaenzt werden.

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Sammelt API-Football-Rohdaten fuer player activity und speichert sie fuer die nachgelagerte Verarbeitung.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `fetch_player_activity(refresh_existing=False)`
  Verwendet `set`, `sorted`, `glob.glob`, `open`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `open(path, 'r', encoding='utf-8')`
- `json.load(f)`
- `data.get('players', [])`
- `p.get('player_id')`
- `open(OUTPUT_JSON, 'r', encoding='utf-8')`
- `json.load(f).get('players_seasons', {})`
- `seasons_by_player.get(str(pid))`
- `requests.get(API_URL, params={'player': pid}, headers=HEADERS, timeout=10)`
- `body.get('response', [])`
- `open(OUTPUT_JSON, 'w', encoding='utf-8')`
- `json.dump({'generated_at': generated_at, 'players_seasons': seasons_by_player}, f, ensure_ascii=False, indent=2)`
- `sched.start()`

### Konfiguration und Environment

- `INPUT_DIR = 'C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection'`
- `INPUT_PATTERN = os.path.join(INPUT_DIR, 'players_profiles*.json')`
- `OUTPUT_JSON = 'C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection/players_activity_78.json'`
- `API_URL = 'https://v3.football.api-sports.io/players/seasons'`
- `HEADERS = <Zugangsdaten nicht abgebildet>`

### Imports und interne Abhaengigkeiten

- `import glob`
- `import json`
- `import os`
- `import time`
- `import requests`
- `from apscheduler.schedulers.blocking import BlockingScheduler`
- `from apscheduler.triggers.cron import CronTrigger`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/Player Profiles/Unfiltered/Code/player activity.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `Exception`.
- Ein Scheduler oder eine Endlosschleife ist vorhanden; der Standardlauf kann dauerhaft aktiv bleiben.
- Netzwerkzugriff haengt von API-Zugang, Antwortschema und Erreichbarkeit ab; leere Antworten sind nicht automatisch ein vollstaendiger Datenbestand.
