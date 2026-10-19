# `test_nn_surrogate.py`

Source: `Sports Api Data/Testruns/Code/test_nn_surrogate.py`

## Aktuelle Code-Referenz

### Ueberblick und Zweck

test_nn_surrogate.py - does the NN surrogate rank candidates better than GBR?

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `lomo(pooled, cols, make_model)`
  Verwendet `sorted`, `pooled['MD'].unique`, `len`, `make_model`. Rueckgabe unter anderem: `pd.DataFrame(rows)`.
- `main()`
  Verwendet `load_matchday_summaries`, `matchday_dirs`, `build_pooled`, `print`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- Keine der erfassten direkten Datei-/Prozessoperationen; Datenfluss erfolgt ueber Funktionsargumente oder aufgerufene Hilfsmodule.

### Konfiguration und Environment

- `RANDOM_STATE = 42`

### Imports und interne Abhaengigkeiten

- `import sys`
- `from pathlib import Path`
- `import numpy as np`
- `import pandas as pd`
- `from sklearn.ensemble import GradientBoostingRegressor`
- `from sklearn.neural_network import MLPRegressor`
- `import analyze_backtest_results as agg`
- `from diagnose_ranker_signals import matchday_dirs, load_matchday_summaries`
- `from diagnose_weight_transfer import build_pooled, spearman`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/Testruns/Code/test_nn_surrogate.py"
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
- `len(tr) < 30 or len(te) < 5`

### Nachvollziehbarer Implementierungsausschnitt

Die folgende Auswahl zeigt zentrale Berechnungen bzw. die Ausfuehrungsfolge direkt aus der Quelldatei.
Sie dient als Lesebeispiel und ist ohne Modulkontext nicht eigenstaendig ausfuehrbar.

```python
# main
def main():
    summaries = load_matchday_summaries(matchday_dirs())
    pooled, feat_cols, z_cols = build_pooled(summaries)
    print(f'Pooled runs: {len(pooled)} across {pooled["MD"].nunique()} matchdays, {len(z_cols)} features\n')

    models = {
        'GBR (current)': lambda: GradientBoostingRegressor(random_state=RANDOM_STATE),
        'NN MLP(64,32)': lambda: MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=500,
                                              random_state=RANDOM_STATE),
    }
    print(f'{"Surrogate":16} {"MeanSpearman":>13} {"PosMDs":>8} {"MeanGapCaptured":>16}')
    print('-' * 56)
    for name, make in models.items():
        r = lomo(pooled, z_cols, make)
        msp = r['Spearman'].mean(skipna=True)
        pos = f"{int((r['Spearman'] > 0).sum())}/{int(r['Spearman'].notna().sum())}"
        mcap = r['GapCaptured'].mean(skipna=True)
        print(f'{name:16} {agg.fmt(msp):>13} {pos:>8} {agg.fmt(mcap):>16}')
    print('\nSpearman ~0 or negative = surrogate cannot rank a new matchday.')
    print('GapCaptured <0 = the surrogate\'s top pick is worse than a random pick.')

# lomo
def lomo(pooled, cols, make_model):
    rows = []
    for held in sorted(pooled['MD'].unique()):
        tr = pooled[pooled['MD'] != held]
        te = pooled[pooled['MD'] == held]
        if len(tr) < 30 or len(te) < 5:
            continue
        m = make_model()
        m.fit(tr[cols].values, tr['DemeanedNLL'].values)
        pred = m.predict(te[cols].values)
        sp = spearman(pred, te['DemeanedNLL'].values)
        actual = te['AvgNLL'].values
        floor, ceil = float(np.mean(actual)), float(np.min(actual))
        picked = float(actual[int(np.argmin(pred))])
        cap = (floor - picked) / (floor - ceil) if (floor - ceil) > 1e-9 else float('nan')
        rows.append({'MD': held, 'Spearman': sp, 'GapCaptured': cap})
    return pd.DataFrame(rows)

```
