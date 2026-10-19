# `Stammdaten_international.py`

Source: `Sports Api Data/International/UEFA/Filtered/Code/Stammdaten_international.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Bereitet Stammdaten_international fuer die tabellarische Weiterverarbeitung auf.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `convert_stammdaten_to_csv()`
  Verwendet `open`, `json.load`, `print`, `datetime.now`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `open(INPUT_FILE, 'r', encoding='utf-8')`
- `json.load(f)`
- `data.get('response', [])`
- `fixture.get('fixture', {})`
- `fixture.get('league', {})`
- `fixture.get('teams', {})`
- `fixture_data.get('venue', {})`
- `fixture_data.get('id')`
- `league_data.get('id')`
- `league_data.get('name')`
- `league_data.get('season')`
- `league_data.get('round')`
- `fixture_data.get('date', '(kein Datum)')`
- `teams_data.get('home', {}).get('name', '')`
- `teams_data.get('home', {})`
- `teams_data.get('away', {}).get('name', '')`
- `teams_data.get('away', {})`
- `teams_data.get('home', {}).get('id')`
- `teams_data.get('away', {}).get('id')`
- `venue_data.get('name')`
- `fixture_data.get('referee')`
- `teams_data.get('home', {}).get('winner')`

### Konfiguration und Environment

- `INPUT_FILE = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International/UEFA/Unfiltered/Datacollection/fixtures_international.json'`
- `OUTPUT_FILE = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International/UEFA/Filtered/Datacollection/Stammdaten_international.csv'`

### Imports und interne Abhaengigkeiten

- `import json`
- `import csv`
- `import os`
- `from datetime import datetime`
- `from zoneinfo import ZoneInfo`
- `from apscheduler.schedulers.blocking import BlockingScheduler`
- `from apscheduler.triggers.cron import CronTrigger`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/International/UEFA/Filtered/Code/Stammdaten_international.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `Exception`.
- Ein Scheduler oder eine Endlosschleife ist vorhanden; der Standardlauf kann dauerhaft aktiv bleiben.
