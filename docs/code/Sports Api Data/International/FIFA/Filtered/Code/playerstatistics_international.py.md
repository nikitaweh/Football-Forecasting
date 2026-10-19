# `playerstatistics_international.py`

Source: `Sports Api Data/International/FIFA/Filtered/Code/playerstatistics_international.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Bereitet playerstatistics_international fuer die tabellarische Weiterverarbeitung auf.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `convert_player_statistics_to_csv()`
  Verwendet `open`, `json.load`, `print`, `datetime.now`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `open(input_file, 'r', encoding='utf-8')`
- `json.load(f)`
- `data.get('response', [])`
- `outer.get('parameters', {}).get('fixture')`
- `outer.get('fixture_id')`
- `outer.get('parameters', {})`
- `outer.get('response', [])`
- `entry.get('team', {})`
- `entry.get('players', [])`
- `team.get('id')`
- `team.get('name', '')`
- `p.get('player', {})`
- `p.get('statistics', [])`
- `stats.get('games', {})`
- `games.get('minutes')`
- `games.get('rating')`
- `games.get('captain')`
- `games.get('substitute')`
- `stats.get('offsides')`
- `stats.get('shots', {})`
- `shots.get('total')`
- `shots.get('on')`

### Konfiguration und Environment

- Keine expliziten globalen Konstanten oder Environment-Abfragen in der statischen Auswahl.

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
python "Sports Api Data/International/FIFA/Filtered/Code/playerstatistics_international.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `Exception`.
- Ein Scheduler oder eine Endlosschleife ist vorhanden; der Standardlauf kann dauerhaft aktiv bleiben.
