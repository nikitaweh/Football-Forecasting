# `compare_models_vs_bookie.py`

Source: `Sports Api Data/Testruns/Code/compare_models_vs_bookie.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

compare_models_vs_bookie.py - compare all reproducible model variants vs BWIN.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `score_probs(exp_h, exp_a, rho)`
  Verwendet `max`, `float`, `poisson_pmf`, `enumerate`. Rueckgabe unter anderem: `(ph / t, pd_ / t, pa / t)`.
- `variants_for_row(bH, bD, bA, exp_h, exp_a)`
  Return {variant: (h,d,a)} for one match-run.
- `main()`
  Verwendet `base_matchday_dirs`, `agg.load_actual_results_by_matchday`, `dict`, `zip`. Rueckgabe unter anderem: `sum(x) / len(x) if x else float('nan')`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `pd.read_csv(rp)`
- `res_map.get(int(mid))`
- `res_map.get(mid)`

### Konfiguration und Environment

- `OUTCOMES = ['H', 'D', 'A']`

### Imports und interne Abhaengigkeiten

- `import math`
- `import sys`
- `from pathlib import Path`
- `import pandas as pd`
- `import analyze_backtest_results as agg`
- `from diagnose_draws import nll, load_bookie_forecasts`
- `from eval_dixon_coles_all import base_matchday_dirs, poisson_pmf`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/Testruns/Code/compare_models_vs_bookie.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Keine expliziten `except`-Handler im Modul; Fehler koennen an den Aufrufer weitergegeben werden.
- Auswertungen nur auf identischen MatchIDs, Zeitraeumen und Zieldefinitionen vergleichen.
- Nachtraegliche Wahrscheinlichkeitsvarianten ersetzen keinen zeitlich getrennten Validierungslauf.
- Fehlende Werte, Join-Verluste und Zahl der ausgewerteten Spiele gemeinsam mit Kennzahlen berichten.

### Ergaenzende Implementierungshinweise

Quellcode-Kommentare zu einzelnen Verarbeitungsschritten:

- accumulate per-match (actual, {variant: nll})
- per match: mean of each variant's probs over runs

Im Code explizit gepruefte Bedingungen (keine Zusicherung vollstaendiger Validierung):

- `__name__ == '__main__'`
- `not math.isfinite(t) or t <= 0`
- `dc`
- `po`
- `s > 0`
- `not rp.exists()`
- `not need.issubset(runs.columns)`
- `actual is None or mid not in {int(m) for f in dirs.values() for m in [mid]}`
- `actual is None`
- `rho`
- `hg > ag`
- `n == 0`
- `hg == 0 and ag == 0`
- `hg == ag`
- `hg == 0 and ag == 1`
- `v in vs`
- `hg == 1 and ag == 0`
- `hg == 1 and ag == 1`

### Nachvollziehbarer Implementierungsausschnitt

Die folgende Auswahl zeigt zentrale Berechnungen bzw. die Ausfuehrungsfolge direkt aus der Quelldatei.
Sie dient als Lesebeispiel und ist ohne Modulkontext nicht eigenstaendig ausfuehrbar.

```python
# main
def main():
    dirs = base_matchday_dirs()
    results = agg.load_actual_results_by_matchday()
    res_map = dict(zip(results['MatchID'].astype(int), results['Result']))
    bookie_df = load_bookie_forecasts()

    VARIANTS = ['base', 'dixon_full_a1.0', 'dixon_full_a0.4', 'dixon_draw_ratio', 'poisson_draw_ratio']
    # accumulate per-match (actual, {variant: nll})
    pooled = {v: {o: [] for o in OUTCOMES} for v in VARIANTS}
    pooled_all = {v: [] for v in VARIANTS}

    for md, folder in dirs.items():
        rp = folder / 'prediction_weight_runs.csv'
        if not rp.exists():
            continue
        runs = pd.read_csv(rp)
        need = {'MatchID', 'WinProb', 'DrawProb', 'LoseProb', 'ExpectedHomeGoals', 'ExpectedAwayGoals'}
        if not need.issubset(runs.columns):
            continue
        for c in ['WinProb', 'DrawProb', 'LoseProb', 'ExpectedHomeGoals', 'ExpectedAwayGoals']:
            runs[c] = pd.to_numeric(runs[c], errors='coerce')
        runs['MatchID'] = pd.to_numeric(runs['MatchID'], errors='coerce').astype('Int64')
        runs = runs.dropna(subset=list(need))
        # per match: mean of each variant's probs over runs
        for mid, grp in runs.groupby('MatchID'):
            actual = res_map.get(int(mid))
            if actual is None:
                continue
            acc = {v: [0.0, 0.0, 0.0] for v in VARIANTS}
            n = 0
            for _, r in grp.iterrows():
                vs = variants_for_row(r['WinProb'], r['DrawProb'], r['LoseProb'],
                                      r['ExpectedHomeGoals'], r['ExpectedAwayGoals'])
                for v in VARIANTS:
                    if v in vs:
                        for i in range(3):
                            acc[v][i] += vs[v][i]
                n += 1
            if n == 0:
                continue
            ai = {'H': 0, 'D': 1, 'A': 2}[actual]
            for v in VARIANTS:
                h, d, a = (x / n for x in acc[v])
                p = [h, d, a][ai]
                val = nll(p)
                pooled[v][actual].append(val)
                pooled_all[v].append(val)

    # bookie
    bk = {o: [] for o in OUTCOMES}
    bk_all = []
    for _, r in bookie_df.iterrows():
        mid = int(r['MatchID'])
        actual = res_map.get(mid)
        if actual is None or mid not in {int(m) for f in dirs.values()
                                          for m in [mid]}:  # cheap presence
            pass
        if actual is None:
            continue
        p = {'H': r['p_H'], 'D': r['p_D'], 'A': r['p_A']}[actual]
        bk[actual].append(nll(p)); bk_all.append(nll(p))

    def mean(x): return sum(x) / len(x) if x else float('nan')

    nH = len(pooled['base']['H']); nD = len(pooled['base']['D']); nA = len(pooled['base']['A'])
    nAll = len(pooled_all['base'])
    print('=' * 92)
    print(f'MODEL vs BOOKMAKER — {len(dirs)} matchdays, {nAll} matches  (H{nH}/D{nD}/A{nA})')
    print('Per-outcome & total mean NLL at the deployable floor. Lower = better.')
    print('=' * 92)
    base_all = mean(pooled_all['base'])
    bookie_all = mean(bk_all)
    hdr = f'{"Model":22} {"H":>8} {"D":>8} {"A":>8} {"TOTAL":>8} {"vsBookie":>9} {"vsBase":>8}'
    print(hdr); print('-' * len(hdr))
    for v in VARIANTS:
        H, D, A, T = mean(pooled[v]['H']), mean(pooled[v]['D']), mean(pooled[v]['A']), mean(pooled_all[v])
        print(f'{v:22} {agg.fmt(H):>8} {agg.fmt(D):>8} {agg.fmt(A):>8} {agg.fmt(T):>8} '
              f'{T-bookie_all:>+9.4f} {T-base_all:>+8.4f}')
    print(f'{"BWIN bookie":22} {agg.fmt(mean(bk["H"])):>8} {agg.fmt(mean(bk["D"])):>8} '
          f'{agg.fmt(mean(bk["A"])):>8} {agg.fmt(bookie_all):>8} {0.0:>+9.4f} {bookie_all-base_all:>+8.4f}')
    print('\nNote: vsBookie/vsBase are TOTAL-NLL gaps (negative = better than that reference).')

```
