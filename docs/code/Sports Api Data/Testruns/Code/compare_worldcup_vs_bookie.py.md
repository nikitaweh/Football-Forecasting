# `compare_worldcup_vs_bookie.py`

Source: `Sports Api Data/Testruns/Code/compare_worldcup_vs_bookie.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

compare_worldcup_vs_bookie.py - compare the International model's variants vs bet365 on the played World Cup 2026 matches.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `latest_worldcup_odds()`
  Verwendet `sorted`, `glob.glob`, `str`. Rueckgabe unter anderem: `files[-1] if files else None`.
- `main()`
  Verwendet `latest_worldcup_odds`, `print`, `pd.read_csv`, `c.lstrip`. Rueckgabe unter anderem: `sum(x) / len(x) if x else float('nan')`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `pd.read_csv(odds_path)`
- `pd.read_csv(PRED)`

### Konfiguration und Environment

- `ROOT = Path('C:/AI Projekt/KI-Projekt')`
- `PRED = ROOT / 'Sports Api Data' / 'International' / 'Model Output' / 'competitive' / 'international_competitive_validation.csv'`
- `ODDS_DIR = ROOT / 'Sports Api Data' / 'Testruns' / 'BWIN Odds' / 'Datacollection'`
- `OUTCOMES = ['H', 'D', 'A']`
- `VARIANTS = ['base', 'dixon_full_a1.0', 'dixon_full_a0.4', 'dixon_draw_ratio', 'poisson_draw_ratio']`

### Imports und interne Abhaengigkeiten

- `import glob`
- `import math`
- `import sys`
- `from pathlib import Path`
- `import pandas as pd`
- `import analyze_backtest_results as agg`
- `from diagnose_draws import nll`
- `from compare_models_vs_bookie import variants_for_row`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/Testruns/Code/compare_worldcup_vs_bookie.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Keine expliziten `except`-Handler im Modul; Fehler koennen an den Aufrufer weitergegeben werden.
- Auswertungen nur auf identischen MatchIDs, Zeitraeumen und Zieldefinitionen vergleichen.
- Nachtraegliche Wahrscheinlichkeitsvarianten ersetzen keinen zeitlich getrennten Validierungslauf.
- Fehlende Werte, Join-Verluste und Zahl der ausgewerteten Spiele gemeinsam mit Kennzahlen berichten.

### Ergaenzende Implementierungshinweise

Quellcode-Kommentare zu einzelnen Verarbeitungsschritten:


Im Code explizit gepruefte Bedingungen (keine Zusicherung vollstaendiger Validierung):

- `__name__ == '__main__'`
- `not odds_path`
- `n == 0`
- `actual not in OUTCOMES`
- `v in vs`

### Nachvollziehbarer Implementierungsausschnitt

Die folgende Auswahl zeigt zentrale Berechnungen bzw. die Ausfuehrungsfolge direkt aus der Quelldatei.
Sie dient als Lesebeispiel und ist ohne Modulkontext nicht eigenstaendig ausfuehrbar.

```python
# main
def main():
    odds_path = latest_worldcup_odds()
    if not odds_path:
        print('No worldcup odds file found.')
        return
    odds = pd.read_csv(odds_path)
    odds.columns = [c.lstrip('﻿') for c in odds.columns]
    odds = odds.dropna(subset=['match_id', 'odd_home_win_1', 'odd_draw_x', 'odd_away_win_2', 'result'])
    odds['match_id'] = pd.to_numeric(odds['match_id'], errors='coerce').astype('Int64')

    pred = pd.read_csv(PRED)
    pred['MatchID'] = pd.to_numeric(pred['MatchID'], errors='coerce').astype('Int64')

    df = odds.merge(pred, left_on='match_id', right_on='MatchID', how='inner')
    n = len(df)
    if n == 0:
        print('No World Cup matches matched between predictions and odds (by MatchID).')
        print(f'  odds matches: {len(odds)} | prediction rows: {len(pred)}')
        return

    mix = df['result'].tolist()
    print('=' * 92)
    print(f'WORLD CUP 2026 — International model variants vs bet365  ({n} played matches)')
    print(f'Result mix: H{mix.count("H")}/D{mix.count("D")}/A{mix.count("A")}  ({odds_path.split(chr(92))[-1]})')
    print('=' * 92)

    pooled = {v: {o: [] for o in OUTCOMES} for v in VARIANTS}
    pooled_all = {v: [] for v in VARIANTS}
    bk = {o: [] for o in OUTCOMES}
    bk_all = []

    for _, r in df.iterrows():
        actual = r['result']
        if actual not in OUTCOMES:
            continue
        # model variants
        vs = variants_for_row(float(r['WinProb']), float(r['DrawProb']), float(r['LoseProb']),
                              float(r['ExpectedHomeGoals']), float(r['ExpectedAwayGoals']))
        for v in VARIANTS:
            if v in vs:
                p = {'H': vs[v][0], 'D': vs[v][1], 'A': vs[v][2]}[actual]
                pooled[v][actual].append(nll(p)); pooled_all[v].append(nll(p))
        # bookie (normalised)
        ph, pd_, pa = 1.0 / r['odd_home_win_1'], 1.0 / r['odd_draw_x'], 1.0 / r['odd_away_win_2']
        z = ph + pd_ + pa
        bp = {'H': ph / z, 'D': pd_ / z, 'A': pa / z}[actual]
        bk[actual].append(nll(bp)); bk_all.append(nll(bp))

    def mean(x): return sum(x) / len(x) if x else float('nan')

    hdr = f'{"Model":22} {"H":>8} {"D":>8} {"A":>8} {"TOTAL":>8} {"vsBookie":>9}'
    print(hdr); print('-' * len(hdr))
    bookie_all = mean(bk_all)
    for v in VARIANTS:
        H, D, A, T = mean(pooled[v]['H']), mean(pooled[v]['D']), mean(pooled[v]['A']), mean(pooled_all[v])
        print(f'{v:22} {agg.fmt(H):>8} {agg.fmt(D):>8} {agg.fmt(A):>8} {agg.fmt(T):>8} {T-bookie_all:>+9.4f}')
    print(f'{"bet365 bookie":22} {agg.fmt(mean(bk["H"])):>8} {agg.fmt(mean(bk["D"])):>8} '
          f'{agg.fmt(mean(bk["A"])):>8} {agg.fmt(bookie_all):>8} {0.0:>+9.4f}')
    print(f'\nMatches: H{len(pooled["base"]["H"])}/D{len(pooled["base"]["D"])}/A{len(pooled["base"]["A"])}  '
          f'(small N — exploratory).')

# latest_worldcup_odds
def latest_worldcup_odds():
    files = sorted(glob.glob(str(ODDS_DIR / 'worldcup_odds_*.csv')))
    return files[-1] if files else None

```
