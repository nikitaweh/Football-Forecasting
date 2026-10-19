# `compare_draw_modes.py`

Source: `Sports Api Data/Testruns/Code/compare_draw_modes.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

compare_draw_modes.py - compare base vs draw-mode backtests for given matchdays.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `floor_forecast(folder)`
  Per-match mean forecast (deployable floor), normalised. index=MatchID.
- `per_outcome_nll(g, res_map)`
  Verwendet `g.iterrows`, `res_map.get`, `int`, `recs.append`. Rueckgabe unter anderem: `out`.
- `bookie_per_outcome(match_ids, bookie_df, res_map)`
  Verwendet `bookie_df['MatchID'].isin`, `sub.iterrows`, `res_map.get`, `int`. Rueckgabe unter anderem: `out`.
- `label_for(folder_name, md)`
  Verwendet `len`, `re.sub`. Rueckgabe unter anderem: `re.sub('_\\d{8}_\\d{6}$', '', suffix)`.
- `main()`
  Verwendet `argparse.ArgumentParser`, `ap.add_argument`, `ap.parse_args`, `agg.load_actual_results_by_matchday`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `pd.read_csv(rp)`
- `res_map.get(int(mid))`
- `res_map.get(int(r['MatchID']))`

### Konfiguration und Environment

- `BACKTEST_DIR = agg.BACKTEST_DIR`
- `OUTCOMES = ['H', 'D', 'A']`
- `ap.add_argument('--matchdays', nargs='+', type=int, default=[8, 18])`

### Imports und interne Abhaengigkeiten

- `import argparse`
- `import re`
- `import sys`
- `from pathlib import Path`
- `import pandas as pd`
- `import analyze_backtest_results as agg`
- `from diagnose_draws import nll, load_bookie_forecasts`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/Testruns/Code/compare_draw_modes.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `Exception`.
- Auswertungen nur auf identischen MatchIDs, Zeitraeumen und Zieldefinitionen vergleichen.
- Nachtraegliche Wahrscheinlichkeitsvarianten ersetzen keinen zeitlich getrennten Validierungslauf.
- Fehlende Werte, Join-Verluste und Zahl der ausgewerteten Spiele gemeinsam mit Kennzahlen berichten.

### Ergaenzende Implementierungshinweise

Quellcode-Kommentare zu einzelnen Verarbeitungsschritten:

- shorten timestamp for readability

Im Code explizit gepruefte Bedingungen (keine Zusicherung vollstaendiger Validierung):

- `__name__ == '__main__'`
- `not rp.exists()`
- `not need.issubset(runs.columns) or runs.empty`
- `folder_name == base`
- `actual is None`
- `not folders`
- `g is None`
- `lbl not in ('base (normal)', 'BWIN bookie') and base_all is not None and pd.notna(o['ALL'])`

### Nachvollziehbarer Implementierungsausschnitt

Die folgende Auswahl zeigt zentrale Berechnungen bzw. die Ausfuehrungsfolge direkt aus der Quelldatei.
Sie dient als Lesebeispiel und ist ohne Modulkontext nicht eigenstaendig ausfuehrbar.

```python
# main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--matchdays', nargs='+', type=int, default=[8, 18])
    args = ap.parse_args()

    results = agg.load_actual_results_by_matchday()
    res_map = dict(zip(results['MatchID'].astype(int), results['Result']))
    bookie_df = load_bookie_forecasts()

    for md in args.matchdays:
        base = f'MD{md:02d}'
        folders = sorted([d for d in BACKTEST_DIR.iterdir()
                          if d.is_dir() and (d.name == base or d.name.startswith(base + '_'))])
        if not folders:
            print(f'\nMD{md:02d}: no folders found.')
            continue
        md_matches = results[results['MD'] == md]
        match_ids = set(md_matches['MatchID'].astype(int))
        mix = md_matches['Result'].tolist()
        print(f'\n{"="*96}')
        print(f'MD{md:02d}  (H{mix.count("H")}/D{mix.count("D")}/A{mix.count("A")})  per-outcome NLL at deployable floor')
        print("="*96)

        rows = []
        for f in folders:
            g = floor_forecast(f)
            if g is None:
                continue
            o = per_outcome_nll(g, res_map)
            rows.append((label_for(f.name, md), o))
        # bookie row
        b = bookie_per_outcome(match_ids, bookie_df, res_map)
        rows.append(('BWIN bookie', b))

        hdr = f'{"Variant":52} {"H":>8} {"D":>8} {"A":>8} {"ALL":>8} {"DrawP":>7}'
        print(hdr)
        print('-' * len(hdr))
        base_all = next((o['ALL'] for lbl, o in rows if lbl == 'base (normal)'), None)
        for lbl, o in rows:
            mark = ''
            if lbl not in ('base (normal)', 'BWIN bookie') and base_all is not None and pd.notna(o['ALL']):
                mark = f"  ({o['ALL']-base_all:+.4f} vs base)"
            print(f'{lbl:52} {agg.fmt(o["H"]):>8} {agg.fmt(o["D"]):>8} {agg.fmt(o["A"]):>8} '
                  f'{agg.fmt(o["ALL"]):>8} {o["MeanDrawProb"]:.3f}{mark}')

# floor_forecast
def floor_forecast(folder):
    """Per-match mean forecast (deployable floor), normalised. index=MatchID."""
    rp = folder / 'prediction_weight_runs.csv'
    if not rp.exists():
        return None
    try:
        runs = pd.read_csv(rp)
    except Exception:
        return None
    need = {'MatchID', 'WinProb', 'DrawProb', 'LoseProb'}
    if not need.issubset(runs.columns) or runs.empty:
        return None
    for c in ['WinProb', 'DrawProb', 'LoseProb']:
        runs[c] = pd.to_numeric(runs[c], errors='coerce')
    runs['MatchID'] = pd.to_numeric(runs['MatchID'], errors='coerce').astype('Int64')
    g = runs.groupby('MatchID')[['WinProb', 'DrawProb', 'LoseProb']].mean()
    s = g.sum(axis=1).replace(0, 1.0)
    return g.div(s, axis=0)

# bookie_per_outcome
def bookie_per_outcome(match_ids, bookie_df, res_map):
    sub = bookie_df[bookie_df['MatchID'].isin(match_ids)]
    recs = []
    for _, r in sub.iterrows():
        actual = res_map.get(int(r['MatchID']))
        if actual is None:
            continue
        p = {'H': r['p_H'], 'D': r['p_D'], 'A': r['p_A']}[actual]
        recs.append((actual, nll(p), r['p_D']))
    df = pd.DataFrame(recs, columns=['Actual', 'NLL', 'DrawProb'])
    out = {o: (df.loc[df['Actual'] == o, 'NLL'].mean() if (df['Actual'] == o).any() else float('nan'))
           for o in OUTCOMES}
    out['ALL'] = df['NLL'].mean() if len(df) else float('nan')
    out['MeanDrawProb'] = df['DrawProb'].mean() if len(df) else float('nan')
    return out

# per_outcome_nll
def per_outcome_nll(g, res_map):
    recs = []
    for mid, row in g.iterrows():
        actual = res_map.get(int(mid))
        if actual is None:
            continue
        p = {'H': row['WinProb'], 'D': row['DrawProb'], 'A': row['LoseProb']}[actual]
        recs.append((actual, nll(p), row['DrawProb']))
    df = pd.DataFrame(recs, columns=['Actual', 'NLL', 'DrawProb'])
    out = {o: (df.loc[df['Actual'] == o, 'NLL'].mean() if (df['Actual'] == o).any() else float('nan'))
           for o in OUTCOMES}
    out['ALL'] = df['NLL'].mean() if len(df) else float('nan')
    out['MeanDrawProb'] = df['DrawProb'].mean() if len(df) else float('nan')
    return out

```
