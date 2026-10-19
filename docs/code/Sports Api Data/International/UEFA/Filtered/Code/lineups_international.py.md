# `lineups_international.py`

Source: `Sports Api Data/International/UEFA/Filtered/Code/lineups_international.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Bereitet lineups_international fuer die tabellarische Weiterverarbeitung auf.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `load_fixture_team_map()`
  Verwendet `open`, `json.load(f).get`, `json.load`, `print`. Rueckgabe unter anderem: `fixture_team_map`.
- `convert_lineups_to_csv()`
  Verwendet `open`, `json.load`, `print`, `datetime.now`. Rueckgabe unter anderem: `out`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `open(FIXTURES_JSON, 'r', encoding='utf-8')`
- `json.load(f).get('response', [])`
- `json.load(f)`
- `fx.get('fixture', {}).get('id')`
- `fx.get('fixture', {})`
- `fx.get('teams', {})`
- `teams.get('home', {}).get('id')`
- `teams.get('home', {})`
- `teams.get('away', {}).get('id')`
- `teams.get('away', {})`
- `open(INPUT_JSON, 'r', encoding='utf-8')`
- `data.get('response', [])`
- `outer.get('parameters', {})`
- `parameters.get('fixture')`
- `p.get('fixture')`
- `outer.get('MatchID')`
- `outer.get('fixture_id')`
- `outer.get('response', [])`
- `fixture_team_map.get(match_key, {})`
- `expected.get('home')`
- `expected.get('away')`
- `e.get('team', {}).get('id')`

### Konfiguration und Environment

- `INPUT_JSON = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International/UEFA/Unfiltered/Datacollection/lineups_international.json'`
- `FIXTURES_JSON = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International/UEFA/Unfiltered/Datacollection/fixtures_international.json'`
- `OUTPUT_CSV = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International/UEFA/Filtered/Datacollection/lineups_international.csv'`

### Imports und interne Abhaengigkeiten

- `import csv`
- `import json`
- `import os`
- `from datetime import datetime`
- `from apscheduler.schedulers.blocking import BlockingScheduler`
- `from apscheduler.triggers.cron import CronTrigger`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/International/UEFA/Filtered/Code/lineups_international.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `Exception`.
- Ein Scheduler oder eine Endlosschleife ist vorhanden; der Standardlauf kann dauerhaft aktiv bleiben.
