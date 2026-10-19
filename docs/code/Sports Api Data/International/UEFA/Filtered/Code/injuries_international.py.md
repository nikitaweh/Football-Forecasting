# `injuries_international.py`

Source: `Sports Api Data/International/UEFA/Filtered/Code/injuries_international.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Bereitet injuries_international fuer die tabellarische Weiterverarbeitung auf.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `convert_injuries_to_csv()`
  Verwendet `open`, `json.load`, `data.get`, `os.makedirs`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `open(INPUT_JSON, 'r', encoding='utf-8')`
- `json.load(f)`
- `data.get('injuries_by_fixture', {})`
- `open(OUTPUT_CSV, 'w', encoding='utf-8', newline='')`
- `inj.get('no_data')`
- `inj.get('team', {}).get('name', '')`
- `inj.get('team', {})`
- `team_name_overrides.get(team_name, team_name)`
- `inj.get('player', {})`
- `player.get('reason')`
- `player.get('id')`
- `player.get('name')`
- `inj.get('team', {}).get('id')`
- `inj.get('league', {}).get('id')`
- `inj.get('league', {})`
- `inj.get('league', {}).get('name')`
- `convert_injuries_to_csv()`
- `sched.start()`

### Konfiguration und Environment

- `INPUT_JSON = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International/UEFA/Unfiltered/Datacollection/injuries_international.json'`
- `OUTPUT_CSV = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International/UEFA/Filtered/Datacollection/injuries_international.csv'`
- `NO_DATA_MARKER = 'NaN'`

### Imports und interne Abhaengigkeiten

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
python "Sports Api Data/International/UEFA/Filtered/Code/injuries_international.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Keine expliziten `except`-Handler im Modul; Fehler koennen an den Aufrufer weitergegeben werden.
- Ein Scheduler oder eine Endlosschleife ist vorhanden; der Standardlauf kann dauerhaft aktiv bleiben.
