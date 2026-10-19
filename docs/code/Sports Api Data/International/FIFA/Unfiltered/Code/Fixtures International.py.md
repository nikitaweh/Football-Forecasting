# `Fixtures International.py`

Source: `Sports Api Data/International/FIFA/Unfiltered/Code/Fixtures International.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Sammelt API-Football-Rohdaten fuer Fixtures International und speichert sie fuer die nachgelagerte Verarbeitung.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `remove_keys(obj, keys_to_remove)`
  Verwendet `isinstance`, `list`, `obj.keys`, `remove_keys`.
- `_build_session()`
  Verwendet `Retry`, `frozenset`, `HTTPAdapter`, `requests.Session`. Rueckgabe unter anderem: `session`.
- `_api_get_json(session, endpoint, params=None)`
  Verwendet `session.get`, `response.raise_for_status`, `response.json`. Rueckgabe unter anderem: `response.json()`.
- `fetch_fixtures_by_league_season(session, league_id, season)`
  Verwendet `print`, `LEAGUE_IDS.get`, `_api_get_json`, `data.get`. Rueckgabe unter anderem: `fixtures`.
- `save_all(fixtures)`
  Verwendet `datetime.now(timezone.utc).strftime`, `datetime.now`, `os.makedirs`, `os.path.dirname`.
- `_current_season()`
  Verwendet `datetime.now`. Rueckgabe unter anderem: `datetime.now(timezone.utc).year`.
- `_seasons_to_refresh()`
  Verwendet `_current_season`. Rueckgabe unter anderem: `[season - 1, season]`.
- `fetch_full_fixtures()`
  Verwendet `_current_season`, `list`, `range`, `set`.
- `fetch_new_fixtures()`
  Verwendet `open`, `json.load`, `data.get`, `fixture.get('fixture', {}).get`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `session.get(url, params=params, timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT))`
- `LEAGUE_IDS.get(league_id, '?')`
- `data.get('response', [])`
- `open(OUTPUT_FILE, 'w', encoding='utf-8')`
- `json.dump(out, f, ensure_ascii=False, indent=4)`
- `fixture.get('fixture', {}).get('id')`
- `fixture.get('fixture', {})`
- `open(OUTPUT_FILE, 'r', encoding='utf-8')`
- `json.load(f)`
- `sched.start()`

### Konfiguration und Environment

- `OUTPUT_FILE = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International/FIFA/Unfiltered/Datacollection/fixtures_international.json'`
- `API_HOST = 'v3.football.api-sports.io'`
- `BASE_URL = f'https://{API_HOST}'`
- `API_KEY = <Zugangsdaten nicht abgebildet>`
- `HEADERS = <Zugangsdaten nicht abgebildet>`
- `REQUEST_CONNECT_TIMEOUT = 4`
- `REQUEST_READ_TIMEOUT = 12`
- `REQUEST_RETRIES = 2`
- `REQUEST_BACKOFF_SECONDS = 1.0`
- `LEAGUE_IDS = {1: 'World Cup', 29: 'World Cup - Qualification Africa', 30: 'World Cup - Qualification Asia', 31: 'World Cup - Qualification CONCACAF', 32: 'World Cup - Qualification Europe', 33: 'World Cup - Qualification Oceania', 34: 'World Cup - Qualifica...`
- `START_SEASON = 2017`

### Imports und interne Abhaengigkeiten

- `import json`
- `import os`
- `from datetime import datetime, timezone`
- `import requests`
- `from apscheduler.schedulers.blocking import BlockingScheduler`
- `from apscheduler.triggers.cron import CronTrigger`
- `from requests.adapters import HTTPAdapter`
- `from urllib3.util.retry import Retry`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/International/FIFA/Unfiltered/Code/Fixtures International.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `Exception`, `(FileNotFoundError, json.JSONDecodeError)`.
- Ein Scheduler oder eine Endlosschleife ist vorhanden; der Standardlauf kann dauerhaft aktiv bleiben.
- Netzwerkzugriff haengt von API-Zugang, Antwortschema und Erreichbarkeit ab; leere Antworten sind nicht automatisch ein vollstaendiger Datenbestand.
