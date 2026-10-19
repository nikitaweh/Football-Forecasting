# `player_statistics_international.py`

Source: `Sports Api Data/International/FIFA/Unfiltered/Code/player_statistics_international.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Sammelt API-Football-Rohdaten fuer player_statistics_international und speichert sie fuer die nachgelagerte Verarbeitung.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `remove_keys(obj, keys_to_remove)`
  Verwendet `isinstance`, `list`, `obj.keys`, `remove_keys`.
- `_current_season()`
  Verwendet `datetime.now`. Rueckgabe unter anderem: `datetime.now(timezone.utc).year`.
- `_seasons_to_refresh()`
  Verwendet `_current_season`. Rueckgabe unter anderem: `{season - 1, season}`.
- `_build_session()`
  Verwendet `Retry`, `frozenset`, `HTTPAdapter`, `requests.Session`. Rueckgabe unter anderem: `session`.
- `_api_get_json(session, endpoint, params=None)`
  Verwendet `session.get`, `response.raise_for_status`, `response.json`. Rueckgabe unter anderem: `response.json()`.
- `_atomic_write_json(file_path, payload)`
  Verwendet `os.path.dirname`, `os.path.basename`, `os.makedirs`, `tempfile.NamedTemporaryFile`.
- `collect_player_stats()`
  Verwendet `print`, `datetime.now`, `open`, `json.load`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `session.get(url, params=params, timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT))`
- `json.dump(payload, tmp, ensure_ascii=False, indent=4)`
- `open(INPUT_FILE_PATH, 'r', encoding='utf-8')`
- `json.load(f)`
- `fixtures_data.get('response', [])`
- `fixture.get('fixture', {}).get('id')`
- `fixture.get('fixture', {})`
- `fixture.get('league', {}).get('season')`
- `fixture.get('league', {})`
- `open(OUTPUT_FILE_PATH, 'r', encoding='utf-8')`
- `existing_stats_data.get('response', [])`
- `entry.get('fixture_id')`

### Konfiguration und Environment

- `INPUT_FILE_PATH = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International/FIFA/Unfiltered/Datacollection/fixtures_international.json'`
- `OUTPUT_FILE_PATH = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International/FIFA/Unfiltered/Datacollection/player_statistics_per_fixture_international.json'`
- `API_HOST = 'v3.football.api-sports.io'`
- `BASE_URL = f'https://{API_HOST}'`
- `HEADERS = <Zugangsdaten nicht abgebildet>`
- `REQUEST_CONNECT_TIMEOUT = 4`
- `REQUEST_READ_TIMEOUT = 12`
- `REQUEST_RETRIES = 2`
- `REQUEST_BACKOFF_SECONDS = 1.0`

### Imports und interne Abhaengigkeiten

- `import json`
- `import os`
- `import tempfile`
- `import time`
- `from datetime import datetime, timezone`
- `import requests`
- `import schedule`
- `from requests.adapters import HTTPAdapter`
- `from urllib3.util.retry import Retry`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/International/FIFA/Unfiltered/Code/player_statistics_international.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `OSError`, `FileNotFoundError`, `json.JSONDecodeError`, `PermissionError`, `Exception`.
- Ein Scheduler oder eine Endlosschleife ist vorhanden; der Standardlauf kann dauerhaft aktiv bleiben.
- Netzwerkzugriff haengt von API-Zugang, Antwortschema und Erreichbarkeit ab; leere Antworten sind nicht automatisch ein vollstaendiger Datenbestand.
