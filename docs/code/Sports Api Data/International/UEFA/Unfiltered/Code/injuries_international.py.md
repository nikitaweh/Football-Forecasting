# `injuries_international.py`

Source: `Sports Api Data/International/UEFA/Unfiltered/Code/injuries_international.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Sammelt API-Football-Rohdaten fuer injuries_international und speichert sie fuer die nachgelagerte Verarbeitung.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `_current_season()`
  Verwendet `datetime.now`. Rueckgabe unter anderem: `datetime.now(timezone.utc).year`.
- `_seasons_to_refresh()`
  Verwendet `_current_season`. Rueckgabe unter anderem: `{season - 1, season}`.
- `_build_session()`
  Verwendet `Retry`, `frozenset`, `HTTPAdapter`, `requests.Session`. Rueckgabe unter anderem: `session`.
- `fetch_injuries(full_load=False)`
  Verwendet `datetime.now().strftime`, `datetime.now`, `print`, `open`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `open(INPUT_FILE, 'r', encoding='utf-8')`
- `json.load(f)`
- `data.get('response', [])`
- `item.get('league', {}).get('season')`
- `item.get('league', {})`
- `item.get('fixture', {}).get('id')`
- `item.get('fixture_id')`
- `item.get('fixture', {})`
- `open(OUTPUT_FILE, 'r', encoding='utf-8')`
- `json.load(f).get('injuries_by_fixture', {})`
- `session.get(API_URL, params={'fixture': fid}, timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT))`
- `resp.json().get('response', [])`
- `inj.get('player')`
- `inj.get('team')`
- `inj.get('league')`
- `open(OUTPUT_FILE, 'w', encoding='utf-8')`
- `json.dump({'injuries_by_fixture': existing}, f, ensure_ascii=False, indent=2)`
- `sched.start()`

### Konfiguration und Environment

- `INPUT_FILE = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International/UEFA/Unfiltered/Datacollection/fixtures_international.json'`
- `OUTPUT_FILE = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International/UEFA/Unfiltered/Datacollection/injuries_international.json'`
- `API_HOST = 'v3.football.api-sports.io'`
- `API_URL = f'https://{API_HOST}/injuries'`
- `HEADERS = <Zugangsdaten nicht abgebildet>`
- `REQUEST_CONNECT_TIMEOUT = 4`
- `REQUEST_READ_TIMEOUT = 12`
- `REQUEST_RETRIES = 2`
- `REQUEST_BACKOFF_SECONDS = 1.0`
- `parser.add_argument('--full-load', action='store_true', help='Deaktiviert: wird ignoriert, es laeuft immer inkrementell')`

### Imports und interne Abhaengigkeiten

- `import argparse`
- `import json`
- `import os`
- `import time`
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
python "Sports Api Data/International/UEFA/Unfiltered/Code/injuries_international.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `Exception`.
- Ein Scheduler oder eine Endlosschleife ist vorhanden; der Standardlauf kann dauerhaft aktiv bleiben.
- Netzwerkzugriff haengt von API-Zugang, Antwortschema und Erreichbarkeit ab; leere Antworten sind nicht automatisch ein vollstaendiger Datenbestand.
