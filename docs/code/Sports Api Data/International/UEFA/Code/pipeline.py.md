# `pipeline.py`

Source: `Sports Api Data/International/UEFA/Code/pipeline.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Orchestriert die Sammlung und CSV-Aufbereitung von Fixtures, Verletzungen, Aufstellungen sowie Spiel- und Spielerstatistiken.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `_load_module(path_key)`
  Verwendet `abs_path.exists`, `FileNotFoundError`, `re.sub`, `importlib.util.spec_from_file_location`. Rueckgabe unter anderem: `module`.
- `_run_step(step_name, fn)`
  Verwendet `print`, `time.time`, `fn`.
- `run_fixtures_pipeline(fixtures_mode)`
  Verwendet `_load_module`, `_run_step`.
- `run_injuries_pipeline()`
  Verwendet `_load_module`, `_run_step`, `injuries_u.fetch_injuries`.
- `run_lineups_pipeline()`
  Verwendet `_load_module`, `_run_step`, `lineups_u.collect_lineups`.
- `run_matchstats_pipeline()`
  Verwendet `_load_module`, `_run_step`, `stats_u.collect_match_statistics`.
- `run_playerstats_pipeline()`
  Verwendet `_load_module`, `_run_step`.
- `main()`
  Verwendet `argparse.ArgumentParser`, `parser.add_argument`, `parser.parse_args`, `run_fixtures_pipeline`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- Keine der erfassten direkten Datei-/Prozessoperationen; Datenfluss erfolgt ueber Funktionsargumente oder aufgerufene Hilfsmodule.

### Konfiguration und Environment

- `PROJECT_ROOT = Path(__file__).resolve().parents[4]`
- `PATHS = {'fixtures_unfiltered': 'Sports Api Data\\International\\UEFA\\Unfiltered\\Code\\Fixtures International.py', 'stammdaten_filtered': 'Sports Api Data\\International\\UEFA\\Filtered\\Code\\Stammdaten_international.py', 'injuries_unfiltered': 'Sports A...`
- `MODULE_CACHE = {}`
- `parser.add_argument('--fixtures-mode', choices=['new', 'full'], default='new', help='Fixtures-Abrufmodus: inkrementell (new) oder kompletter Verlauf ab 2017 (full).')`
- `parser.add_argument('--steps', nargs='+', choices=['fixtures', 'injuries', 'lineups', 'matchstats', 'playerstats'], default=['fixtures', 'injuries', 'lineups', 'matchstats', 'playerstats'], help='Auszufuehrende Pipeline-Bloecke in Reihenfolge.')`
- `parser.add_argument('--continue-on-error', action='store_true', help='Bei Fehlern mit dem naechsten Block weiterlaufen.')`

### Imports und interne Abhaengigkeiten

- `import argparse`
- `import importlib.util`
- `import re`
- `import time`
- `from pathlib import Path`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/International/UEFA/Code/pipeline.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `KeyboardInterrupt`, `Exception`.
