# `backtest_draw_modes.py`

Source: `Sports Api Data/Testruns/Code/backtest_draw_modes.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

backtest_draw_modes.py - run draw outcome-probability modes on chosen matchdays WITHOUT overwriting existing backtest folders.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `_p(x)`
  Format a number for a folder name: 1.05 -> '1p05', -0.2 -> 'm0p20'.
- `folder_suffix(mode, max_runs)`
  Self-describing folder stem encoding the mode + its key params.
- `best_summary_row(summary_path)`
  Verwendet `summary_path.exists`, `pd.read_csv`, `pd.to_numeric`, `nll.notna().sum`. Rueckgabe unter anderem: `f"RunID={row.get('RunID', '?')}, AvgNLL={nll.min():.6f}, Accuracy={acc}"`.
- `run(matchday, fixtures, cutoff, mode, max_runs, match_stats_mode)`
  Verwendet `folder_suffix`, `target_dir.mkdir`, `(REFERENCE_DIR / 'match_results_references.csv').parent.mkdir`, `fixtures.to_csv`. Rueckgabe unter anderem: `('ran', stem, best)`.
- `main()`
  Verwendet `argparse.ArgumentParser`, `ap.add_argument`, `ap.parse_args`, `load_matchday_index`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `os.environ.get('DRAW_OVERLAY_ALPHA', '0.60')`
- `os.environ.get('DRAW_OVERLAY_MIN_PROB', '0.14')`
- `os.environ.get('DRAW_OVERLAY_MAX_PROB', '0.36')`
- `pd.read_csv(summary_path)`
- `row.get('Accuracy', 'n/a')`
- `row.get('RunID', '?')`
- `fixtures.to_csv(REFERENCE_DIR / 'match_results_references.csv', index=False)`
- `subprocess.run([sys.executable, str(SCRIPT_PATH)], env=env, capture_output=True, text=True)`
- `(target_dir / 'stderr.log').write_text(result.stderr or '', encoding='utf-8')`
- `(target_dir / 'stdout.log').write_text(result.stdout or '', encoding='utf-8')`
- `shutil.copy2(src, target_dir / fname)`
- `env.get(k, '(model default)')`
- `(target_dir / 'meta.txt').write_text('\n'.join(meta) + '\n', encoding='utf-8')`

### Konfiguration und Environment

- `SCORE_DEFAULTS = {'SCORE_PROBABILITY_TOTAL_SCALE': '1.05', 'SCORE_PROBABILITY_RHO': '-0.2', 'SCORE_PROBABILITY_ALPHA': '1.0', 'SCORE_PROBABILITY_MAX_GOALS': '10'}`
- `SCORE_MODES = {'score_dixon_coles', 'score_poisson_draw_ratio', 'score_dixon_coles_draw_ratio'}`
- `os.environ.get('DRAW_OVERLAY_ALPHA', '0.60')`
- `os.environ.get('DRAW_OVERLAY_MIN_PROB', '0.14')`
- `os.environ.get('DRAW_OVERLAY_MAX_PROB', '0.36')`
- `ap.add_argument('--matchdays', nargs='+', type=int, default=[8, 18])`
- `ap.add_argument('--modes', nargs='+', default=['draw_multilayer_overlay', 'score_dixon_coles'])`
- `ap.add_argument('--max-runs', type=int, default=50)`
- `ap.add_argument('--match-stats-mode', default='predicted', choices=['predicted', 'actual', 'off'])`

### Imports und interne Abhaengigkeiten

- `import argparse`
- `import os`
- `import shutil`
- `import subprocess`
- `import sys`
- `from datetime import datetime`
- `from pathlib import Path`
- `import pandas as pd`
- `from backtest_matchdays import BACKTEST_DIR, REFERENCE_DIR, SCRIPT_PATH, OUTPUT_FILES, load_matchday_index, matchday_fixtures`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/Testruns/Code/backtest_draw_modes.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `Exception`.
- Auswertungen nur auf identischen MatchIDs, Zeitraeumen und Zieldefinitionen vergleichen.
- Nachtraegliche Wahrscheinlichkeitsvarianten ersetzen keinen zeitlich getrennten Validierungslauf.
- Fehlende Werte, Join-Verluste und Zahl der ausgewerteten Spiele gemeinsam mit Kennzahlen berichten.

### Ergaenzende Implementierungshinweise

Quellcode-Kommentare zu einzelnen Verarbeitungsschritten:

- Defaults for the Dixon-Coles / Poisson score modes — chosen to match the
- existing MD18_score_dixon_coles_* folders for like-for-like comparison.
- Overlay mode uses the model's own env defaults (alpha 0.60, min 0.14, max 0.36,
- goaldiff-scale 0.90, signal-scale 1.00, total-goals-cap 2.60) — left unset here.
- Overwrite the live reference fixtures for this matchday (same as base driver).

Im Code explizit gepruefte Bedingungen (keine Zusicherung vollstaendiger Validierung):

- `__name__ == '__main__'`
- `mode in SCORE_MODES`
- `not summary_path.exists()`
- `df.empty or 'AvgNLL' not in df.columns`
- `nll.notna().sum() == 0`
- `result.returncode != 0`
- `mode == 'draw_multilayer_overlay'`
- `src.exists()`
- `md not in valid`
- `fixtures is None`

### Nachvollziehbarer Implementierungsausschnitt

Die folgende Auswahl zeigt zentrale Berechnungen bzw. die Ausfuehrungsfolge direkt aus der Quelldatei.
Sie dient als Lesebeispiel und ist ohne Modulkontext nicht eigenstaendig ausfuehrbar.

```python
# run
def run(matchday, fixtures, cutoff, mode, max_runs, match_stats_mode):
    stem = f'MD{matchday:02d}_{folder_suffix(mode, max_runs)}'
    target_dir = BACKTEST_DIR / stem
    target_dir.mkdir(parents=True, exist_ok=True)

    # Overwrite the live reference fixtures for this matchday (same as base driver).
    (REFERENCE_DIR / 'match_results_references.csv').parent.mkdir(parents=True, exist_ok=True)
    fixtures.to_csv(REFERENCE_DIR / 'match_results_references.csv', index=False)

    env = os.environ.copy()
    env['BACKTEST_DATE_CUTOFF'] = cutoff.strftime('%Y-%m-%d')
    env['MAX_RUNS_OVERRIDE'] = str(max_runs)
    env['MATCH_STATS_MODE_OVERRIDE'] = match_stats_mode
    env['OUTCOME_PROBABILITY_MODE'] = mode
    if mode in SCORE_MODES:
        env.update(SCORE_DEFAULTS)

    print(f'  {stem}: cutoff {env["BACKTEST_DATE_CUTOFF"]}, {len(fixtures)} fixtures, '
          f'mode={mode}, MAX_RUNS={max_runs} -> running...')
    result = subprocess.run([sys.executable, str(SCRIPT_PATH)], env=env,
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f'  {stem}: FAILED (rc={result.returncode})')
        (target_dir / 'stderr.log').write_text(result.stderr or '', encoding='utf-8')
        (target_dir / 'stdout.log').write_text(result.stdout or '', encoding='utf-8')
        return 'failed', stem, 'n/a'

    copied = 0
    for fname in OUTPUT_FILES:
        src = REFERENCE_DIR / fname
        if src.exists():
            shutil.copy2(src, target_dir / fname)
            copied += 1

    best = best_summary_row(target_dir / 'prediction_weight_run_summary.csv')
    meta = [
        f'Matchday: {matchday}', f'Cutoff: {cutoff.date()}', f'Fixtures: {len(fixtures)}',
        f'MAX_RUNS: {max_runs}', f'MATCH_STATS_MODE: {match_stats_mode}',
        f'OUTCOME_PROBABILITY_MODE: {mode}',
    ]
    if mode in SCORE_MODES:
        for k in ['SCORE_PROBABILITY_TOTAL_SCALE', 'SCORE_PROBABILITY_RHO',
                  'SCORE_PROBABILITY_ALPHA', 'SCORE_PROBABILITY_MAX_GOALS']:
            meta.append(f'{k}: {SCORE_DEFAULTS[k]}')
    elif mode == 'draw_multilayer_overlay':
        for k in ['DRAW_OVERLAY_ALPHA', 'DRAW_OVERLAY_MIN_PROB', 'DRAW_OVERLAY_MAX_PROB',
                  'DRAW_OVERLAY_GOALDIFF_SCALE', 'DRAW_OVERLAY_SIGNAL_SCALE', 'DRAW_OVERLAY_TOTAL_GOALS_CAP']:
            meta.append(f'{k}: {env.get(k, "(model default)")}')
    meta += [f'Pipeline return code: 0', f'Outputs copied: {copied}', f'Best summary row: {best}']
    (target_dir / 'meta.txt').write_text('\n'.join(meta) + '\n', encoding='utf-8')
    print(f'  {stem}: done, {copied} files. Best: {best}')
    return 'ran', stem, best

# best_summary_row
def best_summary_row(summary_path):
    if not summary_path.exists():
        return 'n/a'
    try:
        df = pd.read_csv(summary_path)
    except Exception:
        return 'n/a'
    if df.empty or 'AvgNLL' not in df.columns:
        return 'n/a'
    nll = pd.to_numeric(df['AvgNLL'], errors='coerce')
    if nll.notna().sum() == 0:
        return 'n/a'
    row = df.loc[nll.idxmin()]
    acc = row.get('Accuracy', 'n/a')
    return f"RunID={row.get('RunID', '?')}, AvgNLL={nll.min():.6f}, Accuracy={acc}"

# _p
def _p(x):
    """Format a number for a folder name: 1.05 -> '1p05', -0.2 -> 'm0p20'."""
    f = float(x)
    sign = 'm' if f < 0 else ''
    return sign + f'{abs(f):.2f}'.replace('.', 'p')

```
