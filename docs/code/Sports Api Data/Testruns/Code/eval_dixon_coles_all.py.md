# `eval_dixon_coles_all.py`

Source: `Sports Api Data/Testruns/Code/eval_dixon_coles_all.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

eval_dixon_coles_all.py - exact post-hoc Dixon-Coles evaluation over all base matchdays.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `poisson_pmf(lam, max_goals)`
  Verwendet `max`, `min`, `float`, `math.exp`. Rueckgabe unter anderem: `probs`.
- `dixon_coles_probs(exp_home, exp_away)`
  Verwendet `max`, `float`, `poisson_pmf`, `enumerate`. Rueckgabe unter anderem: `(p_h / tot, p_d / tot, p_a / tot)`.
- `base_matchday_dirs()`
  Verwendet `sorted`, `BACKTEST_DIR.iterdir`, `d.is_dir`, `re.fullmatch`. Rueckgabe unter anderem: `out`.
- `floor_forecasts(folder)`
  Return per-match mean (base) and mean (dixon) forecasts. index=MatchID.
- `collect(rows_accumulator, g, res_map)`
  Verwendet `g.iterrows`, `res_map.get`, `int`, `rows_accumulator.append`.
- `outcome_means(df, col)`
  Verwendet `(df['Actual'] == o).any`, `df.loc[df['Actual'] == o, col].mean`, `float`, `df[col].mean`. Rueckgabe unter anderem: `out`.
- `main()`
  Verwendet `base_matchday_dirs`, `agg.load_actual_results_by_matchday`, `dict`, `zip`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `pd.read_csv(rp)`
- `res_map.get(int(mid))`
- `counts.get(o, len(df))`

### Konfiguration und Environment

- `BACKTEST_DIR = agg.BACKTEST_DIR`
- `OUTCOMES = ['H', 'D', 'A']`
- `SCALE = 1.05`
- `RHO = -0.2`
- `MAX_GOALS = 10`

### Imports und interne Abhaengigkeiten

- `import math`
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
python "Sports Api Data/Testruns/Code/eval_dixon_coles_all.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Keine expliziten `except`-Handler im Modul; Fehler koennen an den Aufrufer weitergegeben werden.
- Auswertungen nur auf identischen MatchIDs, Zeitraeumen und Zieldefinitionen vergleichen.
- Nachtraegliche Wahrscheinlichkeitsvarianten ersetzen keinen zeitlich getrennten Validierungslauf.
- Fehlende Werte, Join-Verluste und Zahl der ausgewerteten Spiele gemeinsam mit Kennzahlen berichten.

### Ergaenzende Implementierungshinweise

Quellcode-Kommentare zu einzelnen Verarbeitungsschritten:

- Match the params from the MD8/MD18 score_dixon_coles runs.

Im Code explizit gepruefte Bedingungen (keine Zusicherung vollstaendiger Validierung):

- `__name__ == '__main__'`
- `not math.isfinite(tot) or tot <= 0`
- `not rp.exists()`
- `not need.issubset(runs.columns) or runs.empty`
- `dAll < 0 and dH <= 0.005 and (dA <= 0.005)`
- `d.is_dir() and re.fullmatch('MD\\d{2}', d.name)`
- `actual is None`
- `g is None`
- `not local`
- `o in ('H', 'A')`
- `dAll < 0`
- `RHO`
- `hg > ag`
- `o == 'D'`
- `hg == 0 and ag == 0`
- `hg == ag`
- `hg == 0 and ag == 1`
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
    bookie_nll = {int(r['MatchID']): nll({'H': r['p_H'], 'D': r['p_D'], 'A': r['p_A']}[res_map[int(r['MatchID'])]])
                  for _, r in bookie_df.iterrows() if int(r['MatchID']) in res_map}

    pooled = []          # (Actual, base_nll, dc_nll)
    per_md = []          # per-matchday totals
    for md, folder in dirs.items():
        g = floor_forecasts(folder)
        if g is None:
            continue
        local = []
        collect(local, g, res_map)
        if not local:
            continue
        pooled.extend(local)
        ldf = pd.DataFrame(local, columns=['Actual', 'base', 'dc'])
        mids = [int(m) for m in g.index]
        bk = [bookie_nll[m] for m in mids if m in bookie_nll]
        per_md.append({
            'MD': md, 'N': len(ldf),
            'BaseNLL': ldf['base'].mean(), 'DixonNLL': ldf['dc'].mean(),
            'Delta': ldf['dc'].mean() - ldf['base'].mean(),
            'BookieNLL': (sum(bk) / len(bk)) if bk else float('nan'),
        })

    df = pd.DataFrame(pooled, columns=['Actual', 'base', 'dc'])
    base_o = outcome_means(df, 'base')
    dc_o = outcome_means(df, 'dc')

    print('=' * 80)
    print(f'POST-HOC DIXON-COLES over {len(per_md)} base matchdays, {len(df)} matches')
    print(f'(scale {SCALE}, rho {RHO}, max_goals {MAX_GOALS}, alpha 1.0) — deployable floor')
    print('=' * 80)
    print('\n=== Pooled per-outcome NLL: base (normal) vs Dixon-Coles ===')
    counts = {o: int((df["Actual"] == o).sum()) for o in OUTCOMES}
    print(f'{"Outcome":8} {"N":>4} {"Base":>9} {"Dixon":>9} {"Delta":>9}   guardrail')
    for o in OUTCOMES + ['ALL']:
        n = counts.get(o, len(df))
        d = dc_o[o] - base_o[o]
        flag = ''
        if o in ('H', 'A'):
            flag = 'OK' if d <= 0.005 else 'DEGRADED'
        elif o == 'D':
            flag = 'improved' if d < 0 else 'worse'
        print(f'{o:8} {n:>4} {agg.fmt(base_o[o]):>9} {agg.fmt(dc_o[o]):>9} {d:>+9.4f}   {flag}')

    bk_all = sum(bookie_nll.values()) / len(bookie_nll)
    print(f'\n  Bookie pooled NLL: {bk_all:.4f}')
    print(f'  Base   total vs bookie: {base_o["ALL"]-bk_all:+.4f}')
    print(f'  Dixon  total vs bookie: {dc_o["ALL"]-bk_all:+.4f}')

    md_df = pd.DataFrame(per_md).sort_values('MD')
    improved = int((md_df['Delta'] < 0).sum())
    print(f'\n=== Per-matchday (Dixon − base) ===')
    print(f'  Matchdays improved by Dixon: {improved}/{len(md_df)}')
    print(f'  Mean per-matchday delta: {md_df["Delta"].mean():+.4f}')
    disp = md_df.copy()
    for c in ['BaseNLL', 'DixonNLL', 'Delta', 'BookieNLL']:
        disp[c] = disp[c].apply(agg.fmt)
    print(disp.to_string(index=False))

    print('\n=== VERDICT ===')
    dH, dA, dAll = dc_o['H'] - base_o['H'], dc_o['A'] - base_o['A'], dc_o['ALL'] - base_o['ALL']
    if dAll < 0 and dH <= 0.005 and dA <= 0.005:
        print(f'Dixon-Coles improves total NLL ({dAll:+.4f}) AND holds the H/A guardrail -> adopt.')
    elif dAll < 0:
        print(f'Dixon-Coles improves total NLL ({dAll:+.4f}) but DEGRADES H/A '
              f'(H {dH:+.4f}, A {dA:+.4f}) -> net positive but violates the strict guardrail.')
    else:
        print(f'Dixon-Coles does NOT improve total NLL ({dAll:+.4f}) -> do not adopt.')

# poisson_pmf
def poisson_pmf(lam, max_goals):
    lam = max(0.02, min(8.0, float(lam)))
    probs = [math.exp(-lam)]
    for g in range(1, max_goals + 1):
        probs.append(probs[-1] * lam / float(g))
    return probs

```
