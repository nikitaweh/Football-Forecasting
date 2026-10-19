# `build_dixon_coles_backtest.py`

Source: `Sports Api Data/Testruns/Code/build_dixon_coles_backtest.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

build_dixon_coles_backtest.py - generate the normal Dixon-Coles outcome data for every base matchday and persist it into Datacollection backtest/.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `_argmax_outcome(h, d, a)`
  Verwendet `max`, `range`. Rueckgabe unter anderem: `OUTCOMES[max(range(3), key=lambda i: vals[i])]`.
- `_teams_for(folder)`
  MatchID -> {MatchDate, HomeTeam, AwayTeam} from the folder's ensemble table.
- `per_md_table(folder, res_map)`
  Per-match base vs Dixon-Coles deployable-floor forecast for one matchday.
- `build_frames(res_map=None, bookie_nll_map=None)`
  Compute Dixon-Coles results for all base matchdays without writing anything.
- `main()`
  Verwendet `build_frames`, `per_md.items`, `tbl.to_csv`, `season.to_csv`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `pd.read_csv(p)`
- `pd.read_csv(rp)`
- `teams.get(mid, {})`
- `res_map.get(mid)`
- `info.get('MatchDate')`
- `info.get('HomeTeam')`
- `info.get('AwayTeam')`
- `bookie_nll_map.get(int(r['MatchID']))`
- `tbl.to_csv(folder / PER_MD_NAME, index=False)`
- `season.to_csv(BACKTEST_DIR / SEASON_NAME, index=False)`

### Konfiguration und Environment

- `BACKTEST_DIR = agg.BACKTEST_DIR`
- `OUTCOMES = ['H', 'D', 'A']`
- `PARAMS = dict(scale=dce.SCALE, rho=dce.RHO, max_goals=dce.MAX_GOALS, alpha=1.0)`
- `PER_MD_NAME = 'dixon_coles_outcome_table.csv'`
- `SEASON_NAME = 'dixon_coles_season.csv'`

### Imports und interne Abhaengigkeiten

- `import sys`
- `from pathlib import Path`
- `import pandas as pd`
- `import analyze_backtest_results as agg`
- `import eval_dixon_coles_all as dce`
- `from diagnose_draws import nll, load_bookie_forecasts`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/Testruns/Code/build_dixon_coles_backtest.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `(pd.errors.EmptyDataError, OSError)`.
- Auswertungen nur auf identischen MatchIDs, Zeitraeumen und Zieldefinitionen vergleichen.
- Nachtraegliche Wahrscheinlichkeitsvarianten ersetzen keinen zeitlich getrennten Validierungslauf.
- Fehlende Werte, Join-Verluste und Zahl der ausgewerteten Spiele gemeinsam mit Kennzahlen berichten.

### Ergaenzende Implementierungshinweise

Quellcode-Kommentare zu einzelnen Verarbeitungsschritten:

- pooled per-outcome (the H/D/A guardrail) + ALL row

Im Code explizit gepruefte Bedingungen (keine Zusicherung vollstaendiger Validierung):

- `__name__ == '__main__'`
- `not p.exists()`
- `'MatchID' not in e.columns or e.empty`
- `not rp.exists()`
- `not need.issubset(runs.columns) or runs.empty`
- `runs.empty`
- `res_map is None`
- `bookie_nll_map is None`
- `not pdf.empty`
- `not season.empty`
- `not per_outcome.empty`
- `pd.notna(r['MatchID'])`
- `tbl is None or tbl.empty`
- `scored.empty`

### Nachvollziehbarer Implementierungsausschnitt

Die folgende Auswahl zeigt zentrale Berechnungen bzw. die Ausfuehrungsfolge direkt aus der Quelldatei.
Sie dient als Lesebeispiel und ist ohne Modulkontext nicht eigenstaendig ausfuehrbar.

```python
# build_frames
def build_frames(res_map=None, bookie_nll_map=None):
    """Compute Dixon-Coles results for all base matchdays without writing anything.

    Returns (per_md: dict[md]->DataFrame, season: DataFrame, per_outcome: DataFrame).
    Reused by both this script's main() and build_dashboard_data.py.
    """
    if res_map is None:
        matches = agg.load_actual_results_by_matchday()
        res_map = dict(zip(matches['MatchID'].astype(int), matches['Result']))
    if bookie_nll_map is None:
        bdf = load_bookie_forecasts()
        bookie_nll_map = {
            int(r['MatchID']): nll({'H': r['p_H'], 'D': r['p_D'], 'A': r['p_A']}[res_map[int(r['MatchID'])]])
            for _, r in bdf.iterrows() if int(r['MatchID']) in res_map
        }

    per_md, season_rows, pooled = {}, [], []
    for md, folder in dce.base_matchday_dirs().items():
        tbl = per_md_table(folder, res_map)
        if tbl is None or tbl.empty:
            continue
        per_md[md] = tbl
        scored = tbl.dropna(subset=['ActualResult'])
        if scored.empty:
            continue
        bk = [bookie_nll_map[m] for m in scored['MatchID'].astype(int) if m in bookie_nll_map]
        for _, r in scored.iterrows():
            pooled.append({'Matchday': md, 'Outcome': r['ActualResult'],
                           'Base': r['Base_NLL'], 'Dixon': r['Dixon_NLL'],
                           'Bookie': bookie_nll_map.get(int(r['MatchID']))})
        base_nll, dixon_nll = scored['Base_NLL'].mean(), scored['Dixon_NLL'].mean()
        season_rows.append({
            'Matchday': md, 'N': len(scored),
            'BaseNLL': base_nll, 'DixonNLL': dixon_nll, 'Delta': dixon_nll - base_nll,
            'BaseAcc': (scored['Base_PredictedResult'] == scored['ActualResult']).mean(),
            'DixonAcc': (scored['Dixon_PredictedResult'] == scored['ActualResult']).mean(),
            'BookieNLL': (sum(bk) / len(bk)) if bk else float('nan'),
            'DixonGapVsBookie': (dixon_nll - (sum(bk) / len(bk))) if bk else float('nan'),
            'DixonImproves': bool(dixon_nll < base_nll),
        })

    season = pd.DataFrame(season_rows).sort_values('Matchday').reset_index(drop=True)

    # pooled per-outcome (the H/D/A guardrail) + ALL row
    pdf = pd.DataFrame(pooled)
    po_rows = []
    if not pdf.empty:
        for o in OUTCOMES:
            sub = pdf[pdf['Outcome'] == o]
            po_rows.append({'Outcome': o, 'N': len(sub),
                            'Base': sub['Base'].mean(), 'Dixon': sub['Dixon'].mean(),
                            'Bookie': sub['Bookie'].mean()})
        po_rows.append({'Outcome': 'ALL', 'N': len(pdf),
                        'Base': pdf['Base'].mean(), 'Dixon': pdf['Dixon'].mean(),
                        'Bookie': pdf['Bookie'].mean()})
    per_outcome = pd.DataFrame(po_rows)
    return per_md, season, per_outcome

# main
def main():
    per_md, season, per_outcome = build_frames()
    n_written = 0
    for md, tbl in per_md.items():
        folder = BACKTEST_DIR / f'MD{md:02d}'
        tbl.to_csv(folder / PER_MD_NAME, index=False)
        n_written += 1
    season.to_csv(BACKTEST_DIR / SEASON_NAME, index=False)

    print(f'Dixon-Coles (scale {PARAMS["scale"]}, rho {PARAMS["rho"]}, '
          f'max_goals {PARAMS["max_goals"]}, alpha {PARAMS["alpha"]})')
    print(f'  wrote {n_written} per-matchday {PER_MD_NAME} files')
    print(f'  wrote season aggregate -> {SEASON_NAME}')
    if not season.empty:
        improved = int(season['DixonImproves'].sum())
        print(f'  matchdays improved by Dixon: {improved}/{len(season)}  '
              f'(mean delta {season["Delta"].mean():+.4f})')
    if not per_outcome.empty:
        allr = per_outcome[per_outcome['Outcome'] == 'ALL'].iloc[0]
        print(f'  pooled NLL  base {allr["Base"]:.4f} -> dixon {allr["Dixon"]:.4f} '
              f'(bookie {allr["Bookie"]:.4f})')

# _argmax_outcome
def _argmax_outcome(h, d, a):
    vals = (h, d, a)
    return OUTCOMES[max(range(3), key=lambda i: vals[i])]

```
