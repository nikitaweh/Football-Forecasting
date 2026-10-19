# `match_statistics_international.py`

Source: `Sports Api Data/International/UEFA/Filtered/Code/match_statistics_international.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Bereitet match_statistics_international fuer die tabellarische Weiterverarbeitung auf.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `parse_int(value)`
  Verwendet `int`. Rueckgabe unter anderem: `int(value) if value is not None else None`.
- `parse_float(value)`
  Verwendet `float`. Rueckgabe unter anderem: `float(value) if value is not None else None`.
- `parse_percentage(value)`
  Verwendet `isinstance`, `int`, `value.replace('%', '').strip`, `value.replace`. Rueckgabe unter anderem: `None`.
- `get_stat_value(stat_list, stat_type)`
  Verwendet `item.get`. Rueckgabe unter anderem: `None`.
- `convert_match_statistics_to_csv()`
  Verwendet `open`, `json.load`, `print`, `datetime.now`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `item.get('type')`
- `item.get('value')`
- `open(fixtures_file, 'r', encoding='utf-8')`
- `json.load(f)`
- `fixtures_data.get('response', [])`
- `fx.get('fixture', {})`
- `fixture.get('status', {}).get('short')`
- `fixture.get('status', {})`
- `fixture.get('id')`
- `fx.get('teams', {})`
- `fx.get('goals', {})`
- `fx.get('score', {}).get('fulltime', {})`
- `fx.get('score', {})`
- `regulation_goals.get('home')`
- `regulation_goals.get('away')`
- `goals.get('home')`
- `goals.get('away')`
- `teams.get('home', {}).get('id')`
- `teams.get('home', {})`
- `teams.get('away', {}).get('id')`
- `teams.get('away', {})`
- `open(stats_file, 'r', encoding='utf-8')`

### Konfiguration und Environment

- `FINISHED_STATUSES = {'FT', 'AET', 'PEN'}`

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
python "Sports Api Data/International/UEFA/Filtered/Code/match_statistics_international.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `alle Exceptions`, `Exception`.
- Ein Scheduler oder eine Endlosschleife ist vorhanden; der Standardlauf kann dauerhaft aktiv bleiben.
