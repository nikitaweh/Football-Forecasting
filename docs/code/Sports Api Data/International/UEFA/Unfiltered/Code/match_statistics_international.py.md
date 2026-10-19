# `match_statistics_international.py`

Source: `Sports Api Data/International/UEFA/Unfiltered/Code/match_statistics_international.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Sammelt API-Football-Rohdaten fuer match_statistics_international und speichert sie fuer die nachgelagerte Verarbeitung.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `remove_keys(obj, keys_to_remove)`
  Verwendet `isinstance`, `list`, `obj.keys`, `remove_keys`.
- `_build_session()`
  Verwendet `Retry`, `frozenset`, `HTTPAdapter`, `requests.Session`. Rueckgabe unter anderem: `session`.
- `_api_get_json(session, endpoint, params=None)`
  Verwendet `session.get`, `response.raise_for_status`, `response.json`. Rueckgabe unter anderem: `response.json()`.
- `collect_match_statistics(full_load=False)`
  Verwendet `print`, `datetime.now`, `open`, `json.load(f).get`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `session.get(url, params=params, timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT))`
- `open(INPUT_FILE, 'r', encoding='utf-8')`
- `json.load(f).get('response', [])`
- `json.load(f)`
- `open(OUTPUT_FILE, 'r', encoding='utf-8')`
- `stat.get('fixture_id')`
- `fx.get('fixture', {})`
- `fixture.get('status', {}).get('short')`
- `fixture.get('status', {})`
- `fixture.get('id')`
- `open(OUTPUT_FILE, 'w', encoding='utf-8')`
- `json.dump({'response': existing_stats}, f, ensure_ascii=False, indent=4)`

### Konfiguration und Environment

- `INPUT_FILE = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International/UEFA/Unfiltered/Datacollection/fixtures_international.json'`
- `OUTPUT_FILE = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International/UEFA/Unfiltered/Datacollection/match_statistics_international.json'`
- `API_HOST = 'v3.football.api-sports.io'`
- `BASE_URL = f'https://{API_HOST}'`
- `HEADERS = <Zugangsdaten nicht abgebildet>`
- `REQUEST_CONNECT_TIMEOUT = 4`
- `REQUEST_READ_TIMEOUT = 12`
- `REQUEST_RETRIES = 2`
- `REQUEST_BACKOFF_SECONDS = 1.0`
- `FINISHED_STATUSES = {'FT', 'AET', 'PEN'}`
- `parser.add_argument('--full-load', action='store_true', help='Alle beendeten Spiele neu abfragen (alte Daten werden geloescht)')`

### Imports und interne Abhaengigkeiten

- `import argparse`
- `import json`
- `import os`
- `import time`
- `from datetime import datetime`
- `import requests`
- `import schedule`
- `from requests.adapters import HTTPAdapter`
- `from urllib3.util.retry import Retry`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/International/UEFA/Unfiltered/Code/match_statistics_international.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `FileNotFoundError`, `(FileNotFoundError, json.JSONDecodeError)`, `Exception`.
- Ein Scheduler oder eine Endlosschleife ist vorhanden; der Standardlauf kann dauerhaft aktiv bleiben.
- Netzwerkzugriff haengt von API-Zugang, Antwortschema und Erreichbarkeit ab; leere Antworten sind nicht automatisch ein vollstaendiger Datenbestand.
