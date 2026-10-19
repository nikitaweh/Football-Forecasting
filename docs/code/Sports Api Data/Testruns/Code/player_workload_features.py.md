# `player_workload_features.py`

Source: `Sports Api Data/Testruns/Code/player_workload_features.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Berechnet zeitlich vorgelagerte Spielerbelastung aus Bundesliga- und kompetitiven internationalen Spielminuten.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `_safe_read_csv(path)`
  Verwendet `isinstance`, `_safe_read_csv`, `pd.concat`, `pd.DataFrame`. Rueckgabe unter anderem: `pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()`.
- `_parse_bool(value)`
  Verwendet `isinstance`, `str(value).strip().lower`, `str(value).strip`, `str`. Rueckgabe unter anderem: `str(value).strip().lower() in {'true', '1', 'yes', 'y'}`.
- `_normalise_event_rows(rows, source, priority)`
  Verwendet `pd.DataFrame`, `rows.copy`, `pd.to_numeric`, `pd.to_datetime`. Rueckgabe unter anderem: `out[['MatchID', 'PlayerID', 'MatchDate', 'MinutesPlayed', 'Source', 'Priority']]`.
- `build_player_workload_index(domestic_player_stats, international_fixtures_path, international_lineups_path, international_player_stats_path=None)`
  Build a leakage-safe per-player minute index.
- `player_workload_at(workload_index, player_id, match_date)`
  Return normalised pre-match workload and its two minute components.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `_safe_read_csv(p)`
- `pd.read_csv(path)`
- `out.get('MatchDate')`
- `_safe_read_csv(international_fixtures_path)`
- `_safe_read_csv(international_player_stats_path)`
- `_safe_read_csv(international_lineups_path)`
- `workload_index.get(player_key)`

### Konfiguration und Environment

- `COMPETITIVE_INTERNATIONAL_LEAGUES = frozenset({'World Cup', 'Euro Championship', 'UEFA Nations League', 'World Cup - Qualification Africa', 'World Cup - Qualification Asia', 'World Cup - Qualification CONCACAF', 'World Cup - Qualification Europe', 'World Cu...`
- `WORKLOAD_SHORT_DAYS = 14`
- `WORKLOAD_LONG_DAYS = 30`
- `WORKLOAD_SHORT_MINUTES_REFERENCE = 270.0`
- `WORKLOAD_LONG_MINUTES_REFERENCE = 540.0`
- `WORKLOAD_INDEX_CAP = 2.0`

### Imports und interne Abhaengigkeiten

- `import os`
- `import numpy as np`
- `import pandas as pd`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Das Modul wird von der Pipeline importiert. Schnittstellenbeispiel (Signatur, keine ausfuehrbaren Beispieldaten):

```text
_safe_read_csv(path)
```

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `(pd.errors.EmptyDataError, OSError)`, `(TypeError, ValueError)`.
- Auswertungen nur auf identischen MatchIDs, Zeitraeumen und Zieldefinitionen vergleichen.
- Nachtraegliche Wahrscheinlichkeitsvarianten ersetzen keinen zeitlich getrennten Validierungslauf.
- Fehlende Werte, Join-Verluste und Zahl der ausgewerteten Spiele gemeinsam mit Kennzahlen berichten.

### Ergaenzende Implementierungshinweise

Quellcode-Kommentare zu einzelnen Verarbeitungsschritten:

- Accept a single path or an iterable of paths. Competitive international data is
- split across confederation branches (International/FIFA, International/UEFA), so
- callers pass the branch files as a list and they are concatenated back together.

Im Code explizit gepruefte Bedingungen (keine Zusicherung vollstaendiger Validierung):

- `isinstance(path, (list, tuple))`
- `not path or not os.path.exists(path)`
- `isinstance(value, bool)`
- `rows.empty`
- `fixtures.empty`
- `all_events.empty`
- `table is None or pd.isna(timestamp)`
- `col not in out.columns`
- `not international_stats.empty`
- `not lineups.empty`
- `col not in fixtures.columns`
- `'StartXI' not in lineups.columns`
- `exact_keys`

### Nachvollziehbarer Implementierungsausschnitt

Die folgende Auswahl zeigt zentrale Berechnungen bzw. die Ausfuehrungsfolge direkt aus der Quelldatei.
Sie dient als Lesebeispiel und ist ohne Modulkontext nicht eigenstaendig ausfuehrbar.

```python
# player_workload_at
def player_workload_at(workload_index, player_id, match_date):
    """Return normalised pre-match workload and its two minute components."""
    try:
        player_key = int(float(player_id))
    except (TypeError, ValueError):
        return 0.0, 0.0, 0.0

    table = workload_index.get(player_key)
    timestamp = pd.to_datetime(match_date, errors='coerce')
    if table is None or pd.isna(timestamp):
        return 0.0, 0.0, 0.0

    dates, cumulative_minutes = table
    cutoff = np.datetime64(timestamp.to_datetime64(), 'ns')
    right = int(np.searchsorted(dates, cutoff, side='left'))

    def minutes_in_window(days):
        left_cutoff = cutoff - np.timedelta64(int(days), 'D')
        left = int(np.searchsorted(dates, left_cutoff, side='left'))
        return float(cumulative_minutes[right] - cumulative_minutes[left])

    minutes_14 = minutes_in_window(WORKLOAD_SHORT_DAYS)
    minutes_30 = minutes_in_window(WORKLOAD_LONG_DAYS)
    short_load = min(WORKLOAD_INDEX_CAP, minutes_14 / WORKLOAD_SHORT_MINUTES_REFERENCE)
    long_load = min(WORKLOAD_INDEX_CAP, minutes_30 / WORKLOAD_LONG_MINUTES_REFERENCE)
    workload = 0.65 * short_load + 0.35 * long_load
    return float(workload), minutes_14, minutes_30

# _normalise_event_rows
def _normalise_event_rows(rows, source, priority):
    if rows.empty:
        return pd.DataFrame(columns=[
            'MatchID', 'PlayerID', 'MatchDate', 'MinutesPlayed', 'Source', 'Priority'
        ])

    out = rows.copy()
    for col in ['MatchID', 'PlayerID', 'MinutesPlayed']:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors='coerce')
    out['MatchDate'] = pd.to_datetime(out.get('MatchDate'), errors='coerce')
    out = out.dropna(subset=['MatchID', 'PlayerID', 'MatchDate', 'MinutesPlayed']).copy()
    out = out[out['MinutesPlayed'] > 0].copy()
    out['MinutesPlayed'] = out['MinutesPlayed'].clip(lower=0, upper=130)
    out['MatchID'] = out['MatchID'].astype(int)
    out['PlayerID'] = out['PlayerID'].astype(int)
    out['Source'] = source
    out['Priority'] = int(priority)
    return out[[
        'MatchID', 'PlayerID', 'MatchDate', 'MinutesPlayed', 'Source', 'Priority'
    ]]

# _safe_read_csv
def _safe_read_csv(path):
    # Accept a single path or an iterable of paths. Competitive international data is
    # split across confederation branches (International/FIFA, International/UEFA), so
    # callers pass the branch files as a list and they are concatenated back together.
    if isinstance(path, (list, tuple)):
        frames = [_safe_read_csv(p) for p in path]
        frames = [f for f in frames if not f.empty]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not path or not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()

# _parse_bool
def _parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'true', '1', 'yes', 'y'}

```
