# `refresh_data.py`

Source: `website/refresh_data.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

refresh_data.py  --  Unattended website refresh (systemd timer on the VPS, or Windows Task Scheduler locally).

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `sha256_file(path)`
  Verwendet `os.path.exists`, `hashlib.sha256`, `open`, `iter`. Rueckgabe unter anderem: `h.hexdigest()`.
- `load_state()`
  Verwendet `os.path.exists`, `open`, `json.load`, `log.warning`. Rueckgabe unter anderem: `{}`.
- `save_state(state)`
  Verwendet `open`, `json.dump`.
- `publish(local_path)`
  Copy a rebuilt file into the nginx web root (ORAKEL_WEB_ROOT, set on the VPS). Unset means local-only mode. Copy + rename keeps readers from seeing a half-written file.
- `heartbeat(state)`
  At most one liveness line per day, so the log shows the task is alive without filling up with no-op entries.
- `main()`
  Verwendet `os.makedirs`, `logging.basicConfig`, `logging.FileHandler`, `logging.StreamHandler`. Rueckgabe unter anderem: `0`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `open(path, 'rb')`
- `open(STATE_FILE, 'r', encoding='utf-8')`
- `json.load(fh)`
- `open(STATE_FILE, 'w', encoding='utf-8')`
- `json.dump(state, fh, indent=2)`
- `shutil.copyfile(local_path, tmp)` + `os.replace(tmp, target)` into `ORAKEL_WEB_ROOT`
- `state.get('lastHeartbeat')`
- `state.get('hashes')`

### Konfiguration und Environment

- `HERE = os.path.dirname(os.path.abspath(__file__))`
- `ROOT = os.path.dirname(HERE)`
- `LOG_DIR = os.path.join(ROOT, 'logs')`
- `STATE_FILE = os.path.join(LOG_DIR, 'refresh_state.json')`
- `LOG_FILE = os.path.join(LOG_DIR, 'website_refresh.log')`
- Environment: `ORAKEL_WEB_ROOT` (optional, nginx web root on the VPS)
- `LEAGUE = 'bundesliga'`

### Imports und interne Abhaengigkeiten

- `import hashlib`
- `import json`
- `import logging`
- `import os`
- `import shutil`
- `import sys`
- `from datetime import datetime`
- `import build_data`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "website/refresh_data.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `(ValueError, OSError)`, `Exception`.
