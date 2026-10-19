# `build_data_international.py`

Source: `website/build_data_international.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

build_data_international.py  --  Generates website/data.international.js from the World Cup 2026 backtesting snapshot.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `num(value, default=0.0)`
  Verwendet `float`. Rueckgabe unter anderem: `float(value)`.
- `latest_source()`
  Verwendet `sorted`, `glob.glob`, `SystemExit`, `'No wc_predictions_asof_*.csv snapshot found under {0}'.format`. Rueckgabe unter anderem: `candidates[-1]`.
- `load_matches(path)`
  Verwendet `Counter`, `open`, `csv.DictReader`, `(row.get('MatchID') or '').strip`. Rueckgabe unter anderem: `(matches, meta_bits)`.
- `build()`
  Verwendet `latest_source`, `load_matches`, `dict`, `min`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `open(path, 'r', encoding='utf-8-sig', newline='')`
- `row.get('MatchID')`
- `row.get('PredictedScore')`
- `row.get('WinProb')`
- `row.get('DrawProb')`
- `row.get('LoseProb')`
- `row.get('ActualHomeGoals')`
- `row.get('ActualAwayGoals')`
- `RESULT_TO_OUTCOME.get((row.get('ActualResult') or '').strip(), None)`
- `row.get('ActualResult')`
- `row.get('MatchDate')`
- `row.get('HomeTeam')`
- `row.get('AwayTeam')`
- `RESULT_TO_OUTCOME.get((row.get('PredictedResult') or '').strip(), None)`
- `row.get('PredictedResult')`
- `row.get('ExpectedHomeGoals')`
- `row.get('ExpectedAwayGoals')`
- `row.get('PredictedGoalDiff')`
- `row.get('Stage')`
- `row.get('Engine')`
- `row.get('OutcomeMode')`
- `open(OUTPUT_JS, 'w', encoding='utf-8')`

### Konfiguration und Environment

- `HERE = os.path.dirname(os.path.abspath(__file__))`
- `ROOT = os.path.dirname(HERE)`
- `SOURCE_GLOB = os.path.join(ROOT, 'Sports Api Data', 'International', 'FIFA', 'Backtesting', 'worldcup_2026', 'wc_predictions_asof_*.csv')`
- `OUTPUT_JS = os.path.join(HERE, 'data.international.js')`
- `RESULT_TO_OUTCOME = {'H': 'HomeWin', 'D': 'Draw', 'A': 'AwayWin'}`
- `SIGNALS_PER_MATCH = 16`
- `TEAMS = {'Brazil': {'abbr': 'BRA', 'color': '#009C3B'}, 'Norway': {'abbr': 'NOR', 'color': '#EF2B2D'}, 'Portugal': {'abbr': 'POR', 'color': '#D4213D'}, 'Spain': {'abbr': 'ESP', 'color': '#C60B1E'}, 'Mexico': {'abbr': 'MEX', 'color': '#006847'}, 'England': {...`

### Imports und interne Abhaengigkeiten

- `import csv`
- `import glob`
- `import logging`
- `import os`
- `from collections import Counter`
- `from datetime import datetime`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "website/build_data_international.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `(TypeError, ValueError)`.
