# `scrape_injuries.py`

Source: `Sports Api Data/International/UEFA/Code/scrape_injuries.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Standalone UEFA injuries scraper.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `_load_module(path)`
  Verwendet `re.sub`, `importlib.util.spec_from_file_location`, `RuntimeError`, `importlib.util.module_from_spec`. Rueckgabe unter anderem: `module`.
- `main()`
  Verwendet `print`, `_load_module`, `injuries_u.fetch_injuries`, `injuries_f.convert_injuries_to_csv`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `injuries_f.convert_injuries_to_csv()`

### Konfiguration und Environment

- `BRANCH_DIR = Path(__file__).resolve().parents[1]`
- `INJURIES_UNFILTERED = BRANCH_DIR / 'Unfiltered' / 'Code' / 'injuries_international.py'`
- `INJURIES_FILTERED = BRANCH_DIR / 'Filtered' / 'Code' / 'injuries_international.py'`

### Imports und interne Abhaengigkeiten

- `import importlib.util`
- `import re`
- `from pathlib import Path`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/International/UEFA/Code/scrape_injuries.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Keine expliziten `except`-Handler im Modul; Fehler koennen an den Aufrufer weitergegeben werden.
