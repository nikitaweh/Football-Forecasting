# `Player Gerneral Information.py`

Source: `Sports Api Data/Player Profiles/Unfiltered/Code/Player Gerneral Information.py`

## Überblick

Dieses Skript verarbeitet Spieler- oder Profilinformationen und bereitet sie fuer die weitere Nutzung auf.

## Zweck / Responsibilities

- Schreibt aufbereitete Ergebnisse in Projektdateien oder Zieltabellen.
- Kommuniziert mit externen APIs und verarbeitet deren Antworten weiter.
- Kann als geplanter Job ueber einen Scheduler ausgefuehrt werden.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `get_with_retry(url, params, headers)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `fetch_player_profiles()`: Ruft Quelldaten ab und verarbeitet die Antwort fuer die weitere Nutzung.

## Inputs / Outputs & Side-effects

**Inputs**
- Keine klar benannten Eingabepfade erkannt; Details stehen im Quelltext.

**Outputs**
- `OUTPUT_JSON`: `r"C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection/players_profiles"`

**Side-effects**
- Schreibt Dateien im Projektverzeichnis oder aktualisiert bestehende Artefakte.
- Fuehrt Netzwerkzugriffe auf externe APIs aus.
- Kann als lang laufender Scheduler-Prozess gestartet werden.
- Schreibt Laufzeit- und Fehlerhinweise auf ``stdout``.
- Legt Zielordner bei Bedarf automatisch an.

## Konfiguration / Env

- `API_KEY`: `"5fa2372f2bfcbedb8ef7b85c86f0a27a"`
- `RETRY_LIMIT`: `3`
- Keine offensichtliche Nutzung von Umgebungsvariablen erkannt.

## Interne Abhaengigkeiten / Imports

- `apscheduler.schedulers.blocking.BlockingScheduler`
- `apscheduler.triggers.cron.CronTrigger`
- `json`
- `os`
- `requests`
- `requests.exceptions.ConnectionError`
- `requests.exceptions.HTTPError`
- `requests.exceptions.RequestException`
- `time`

## Beispiel

- Typischer Aufruf: ``python "Sports Api Data/Player Profiles/Unfiltered/Code/Player Gerneral Information.py"``

## Edge Cases / Notes

- Netzwerkfehler, Timeouts oder API-Limits koennen den Lauf unterbrechen oder zu leeren Ergebnissen fuehren.
- Beim Direktstart kann das Skript nach der ersten Verarbeitung im Scheduler weiterlaufen.
- Bestehende Zieldateien koennen bei jedem Lauf ueberschrieben oder ergaenzt werden.

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Sammelt API-Football-Rohdaten fuer Player Gerneral Information und speichert sie fuer die nachgelagerte Verarbeitung.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `get_with_retry(url, params, headers)`
  Verwendet `range`, `requests.get`, `resp.raise_for_status`, `resp.json`. Rueckgabe unter anderem: `resp.json()`.
- `fetch_player_profiles()`
  Verwendet `print`, `time.strftime`, `get_with_retry`, `leagues_data.get`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `requests.get(url, params=params, headers=headers, timeout=10)`
- `leagues_data.get('response', [])`
- `league_info.get('seasons', [])`
- `season_entry.get('year')`
- `body.get('response', [])`
- `p.get('player', {})`
- `pl.get('id')`
- `pl.get('name')`
- `pl.get('firstname')`
- `pl.get('lastname')`
- `pl.get('age')`
- `pl.get('birth', {}).get('date')`
- `pl.get('birth', {})`
- `pl.get('birth', {}).get('place')`
- `pl.get('birth', {}).get('country')`
- `pl.get('nationality')`
- `pl.get('height')`
- `pl.get('weight')`
- `body.get('paging', {}).get('total', 1)`
- `body.get('paging', {})`
- `open(out_path, 'w', encoding='utf-8')`
- `json.dump({'league_id': league_id, 'seasons': [s['year'] for s in seasons if s.get('year') >= 2017], 'count': len(basic_players), 'players': basic_players}, f, ensure_ascii=False, indent=2)`

### Konfiguration und Environment

- `API_HOST = 'https://v3.football.api-sports.io'`
- `API_KEY = <Zugangsdaten nicht abgebildet>`
- `OUTPUT_JSON = 'C:/AI Projekt/KI-Projekt/Sports Api Data/Player Profiles/Unfiltered/Datacollection/players_profiles'`
- `LEAGUE_IDS = [78, 1, 4, 5, 10]`
- `RETRY_LIMIT = 3`
- `RETRY_DELAY = 5`

### Imports und interne Abhaengigkeiten

- `import json`
- `import os`
- `import time`
- `import requests`
- `from requests.exceptions import RequestException, HTTPError, ConnectionError`
- `from apscheduler.schedulers.blocking import BlockingScheduler`
- `from apscheduler.triggers.cron import CronTrigger`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/Player Profiles/Unfiltered/Code/Player Gerneral Information.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `(ConnectionError, HTTPError, RequestException)`.
- Ein Scheduler oder eine Endlosschleife ist vorhanden; der Standardlauf kann dauerhaft aktiv bleiben.
- Netzwerkzugriff haengt von API-Zugang, Antwortschema und Erreichbarkeit ab; leere Antworten sind nicht automatisch ein vollstaendiger Datenbestand.
