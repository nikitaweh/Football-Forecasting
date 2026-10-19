# `build_dashboard_data.py`

Source: `Sports Api Data/Testruns/Code/build_dashboard_data.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

build_dashboard_data.py - export tidy CSVs for the R Shiny performance dashboard.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `_md_folders()`
  All MD* backtest folders, sorted, with their parsed matchday number.
- `_read_meta(folder)`
  Parse a folder's meta.txt 'Key: Value' lines into a dict (empty if none).
- `_mode_label(folder_name, md, meta)`
  Human mode name: 'baseline' for a plain MDNN folder, else the outcome mode.
- `_variant_label(folder_name, md)`
  Folder suffix with the timestamp stripped (disambiguates repeated runs).
- `_safe_summary(folder)`
  Verwendet `p.exists`, `pd.read_csv`. Rueckgabe unter anderem: `df if not df.empty else None`.
- `_floor_score(folder, res_map, bookie_baseline)`
  Deployable-floor metrics for a folder: NLL/accuracy of the per-match mean forecast over all runs (no hindsight best-run selection). Same basis as the Dixon 'Base floor' and compare_draw_modes, so the whole dashboard agrees.
- `export_matchday_performance(res_map, bookie_nll_map, matches_df)`
  season_summary.csv (best-run metrics) enriched with deployable-floor metrics.
- `export_mode_and_runs(res_map, bookie_nll_map, matches_df)`
  mode_performance.csv (one row per folder) + run_distributions.csv (every run).
- `export_per_outcome_nll(res_map, bookie_df)`
  Per-outcome (H/D/A/ALL) NLL at the deployable floor, for every MD* folder.
- `export_international()`
  Per-match NLL / correctness for the International validation set.
- `export_international_odds()`
  Long per (game x bookmaker) table of international odds for the Intl-games tab: implied 1X2 probs (overround removed) + bookie NLL/pick vs the actual result. Reads the newest worldcup_odds_<book>_*.csv per bookmaker, so freshly downloaded odds flow straight into the dashboard on the next refresh.
- `export_dixon(res_map, bookie_nll_map)`
  Season-wide post-hoc Dixon-Coles: per-matchday table + pooled per-outcome.
- `_first_val(summary, col)`
  Verwendet `str`, `summary[col].dropna().unique`, `summary[col].dropna`. Rueckgabe unter anderem: `None`.
- `_mode_key(folder, md, summary, meta)`
  Composite mode label = FeatureSchemaVersion x OutcomeProbabilityMode.
- `export_mode_curve(res_map, bookie_nll_map, matches_df, bookie_df)`
  Long table Matchday x Mode of deployable-floor NLL/accuracy for the Mode explorer page: every outcome mode (grouped by OutcomeProbabilityMode) + the season-wide Dixon-Coles + the BWIN bookie, all on the same floor basis.
- `source_fingerprint()`
  A cheap (count, max-mtime) signature of every input the dashboard depends on.
- `main()`
  Verwendet `OUT_DIR.mkdir`, `print`, `contextlib.redirect_stdout`, `io.StringIO`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `p.read_text(encoding='utf-8', errors='ignore').splitlines()`
- `p.read_text(encoding='utf-8', errors='ignore')`
- `meta.get('OUTCOME_PROBABILITY_MODE')`
- `pd.read_csv(p)`
- `res_map.get(int(mid))`
- `pd.DataFrame(columns=cols).to_csv(OUT_DIR / 'matchday_performance.csv', index=False)`
- `pd.read_csv(SEASON_SUMMARY).sort_values('Matchday')`
- `pd.read_csv(SEASON_SUMMARY)`
- `df.to_csv(OUT_DIR / 'matchday_performance.csv', index=False)`
- `meta.get('MATCH_STATS_MODE')`
- `summary.get('Accuracy')`
- `fs.get('FloorNLL')`
- `fs.get('FloorAcc')`
- `fs.get('FloorGapVsBookie')`
- `fs.get('FloorBeatsBookie')`
- `pd.DataFrame(mode_rows).to_csv(OUT_DIR / 'mode_performance.csv', index=False)`
- `pd.DataFrame(run_rows).to_csv(OUT_DIR / 'run_distributions.csv', index=False)`
- `o.get(outcome)`
- `o.get('MeanDrawProb')`
- `b.get(outcome)`
- `b.get('MeanDrawProb')`
- `pd.DataFrame(rows).to_csv(OUT_DIR / 'per_outcome_nll.csv', index=False)`

### Konfiguration und Environment

- `ROOT = agg.TESTRUNS_PATH.parents[1]`
- `BACKTEST_DIR = agg.BACKTEST_DIR`
- `SEASON_SUMMARY = BACKTEST_DIR / 'season_summary.csv'`
- `REFERENCE_RESULTS = agg.TESTRUNS_PATH / 'Datacollection reference' / 'match_results_references.csv'`
- `INTL_VALIDATION = ROOT / 'Sports Api Data' / 'International' / 'Model Output' / 'competitive' / 'international_competitive_validation.csv'`
- `OUT_DIR = ROOT / 'dashboard' / 'data'`
- `MD_FOLDER_RE = re.compile('^MD(\\d+)')`
- `SCHEMA_SHORT = {'bases_v2_hybrid': 'v2', 'bases_v3_player_workload': 'v3-workload'}`

### Imports und interne Abhaengigkeiten

- `import contextlib`
- `import io`
- `import json`
- `import math`
- `import os`
- `import re`
- `import sys`
- `from datetime import datetime, timezone`
- `from pathlib import Path`
- `import pandas as pd`
- `import analyze_backtest_results as agg`
- `import compare_draw_modes as cdm`
- `import build_dixon_coles_backtest as dcb`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/Testruns/Code/build_dashboard_data.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `(pd.errors.EmptyDataError, OSError)`, `Exception`, `OSError`.
- Auswertungen nur auf identischen MatchIDs, Zeitraeumen und Zieldefinitionen vergleichen.
- Nachtraegliche Wahrscheinlichkeitsvarianten ersetzen keinen zeitlich getrennten Validierungslauf.
- Fehlende Werte, Join-Verluste und Zahl der ausgewerteten Spiele gemeinsam mit Kennzahlen berichten.

### Ergaenzende Implementierungshinweise

Quellcode-Kommentare zu einzelnen Verarbeitungsschritten:

- ── Paths ───────────────────────────────────────────────────────────────────
- ── helpers ─────────────────────────────────────────────────────────────────
- ── exporters ───────────────────────────────────────────────────────────────
- bookie baseline for this matchday (reuse agg logic)
- deployable-floor metrics (the dashboard's headline baseline)
- one bookie reference row per matchday (per outcome)
- season-wide post-hoc Dixon-Coles
- collapse repeated (matchday, mode) - e.g. MD18's three score_dixon reruns
- 1) regenerate season_summary.csv from current outcome data (quietly).
- Suppress agg's verbose stdout, but surface any failure on the REAL stdout
- so a stale season_summary can never pass silently.

Im Code explizit gepruefte Bedingungen (keine Zusicherung vollstaendiger Validierung):

- `__name__ == '__main__'`
- `not BACKTEST_DIR.exists()`
- `not p.exists()`
- `folder_name == base or folder_name == f'MD{md}'`
- `g is None or g.empty`
- `not nlls`
- `not SEASON_SUMMARY.exists()`
- `not INTL_VALIDATION.exists()`
- `not need.issubset(df.columns) or df.empty`
- `'PredictedResult' in df.columns`
- `summary is not None and col in summary.columns`
- `outcome == 'normal'`
- `not df.empty`
- `odds`
- `not d.is_dir()`
- `not m`
- `':' in line`
- `actual is None`
- `summary is None or 'AvgNLL' not in summary.columns`
- `not stats_mode and 'MatchStatsMode' in summary.columns and (not summary.empty)`
- `g is None`
- `not match_ids`
- `r['HomeGoals'] > r['AwayGoals']`
- `r['HomeGoals'] < r['AwayGoals']`
- `not files`
- `not fs`
- `bb is None or (isinstance(bb, float) and math.isnan(bb))`
- `pd.isna(nll_v)`
- `pd.isna(mid)`
- `pd.isna(oh) or pd.isna(od) or pd.isna(oa) or (min(oh, od, oa) <= 0)`
- `res in probs`

### Nachvollziehbarer Implementierungsausschnitt

Die folgende Auswahl zeigt zentrale Berechnungen bzw. die Ausfuehrungsfolge direkt aus der Quelldatei.
Sie dient als Lesebeispiel und ist ohne Modulkontext nicht eigenstaendig ausfuehrbar.

```python
# _md_folders
def _md_folders():
    """All MD* backtest folders, sorted, with their parsed matchday number."""
    out = []
    if not BACKTEST_DIR.exists():
        return out
    for d in sorted(BACKTEST_DIR.iterdir()):
        if not d.is_dir():
            continue
        m = MD_FOLDER_RE.match(d.name)
        if not m:
            continue
        out.append((int(m.group(1)), d))
    return out

```
