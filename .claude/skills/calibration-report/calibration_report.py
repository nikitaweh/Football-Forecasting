"""
calibration_report.py - read-only calibration report for the base backtest.

For every base matchday folder (Datacollection backtest/MD{NN}/) it builds the
deployable floor forecast (per-match mean of WinProb/DrawProb/LoseProb over all
runs), joins actual results and the overround-free BWIN probabilities, and
reports for model and bookmaker on the same matches:

  - multiclass Brier score and NLL, with a paired bootstrap CI of the gap
  - per outcome (H/D/A, one-vs-rest): ECE, Murphy decomposition
    (reliability - resolution + uncertainty = Brier), reliability-diagram bins

No BART runs, no writes outside Datacollection backtest/calibration_report/.

Usage:
    python calibration_report.py              # 10 quantile bins
    python calibration_report.py --bins 5 --bootstrap 2000
"""

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
CODE_DIR = REPO_ROOT / 'Sports Api Data' / 'Testruns' / 'Code'
sys.path.insert(0, str(CODE_DIR))

import analyze_backtest_results as agg  # noqa: E402
from diagnose_draws import load_bookie_forecasts  # noqa: E402
from eval_dixon_coles_all import base_matchday_dirs  # noqa: E402

OUTCOMES = ['H', 'D', 'A']
OUT_DIR = agg.BACKTEST_DIR / 'calibration_report'


def model_floor_forecasts():
    rows = []
    for md, folder in base_matchday_dirs().items():
        rp = folder / 'prediction_weight_runs.csv'
        if not rp.exists():
            continue
        runs = pd.read_csv(rp, usecols=lambda c: c in {'MatchID', 'WinProb', 'DrawProb', 'LoseProb'})
        for c in ['MatchID', 'WinProb', 'DrawProb', 'LoseProb']:
            runs[c] = pd.to_numeric(runs[c], errors='coerce')
        runs = runs.dropna()
        if runs.empty:
            continue
        fl = runs.groupby('MatchID')[['WinProb', 'DrawProb', 'LoseProb']].mean().reset_index()
        fl['MD'] = md
        fl['NRuns'] = runs.groupby('MatchID').size().values
        rows.append(fl)
    if not rows:
        return pd.DataFrame()
    df = pd.concat(rows, ignore_index=True).rename(columns={'WinProb': 'H', 'DrawProb': 'D', 'LoseProb': 'A'})
    df[OUTCOMES] = df[OUTCOMES].div(df[OUTCOMES].sum(axis=1), axis=0)
    df['MatchID'] = df['MatchID'].astype(int)
    return df


def onehot(actual):
    return np.array([[1.0 if a == o else 0.0 for o in OUTCOMES] for a in actual])


def brier(P, Y):
    return ((P - Y) ** 2).sum(axis=1)


def nll(P, Y):
    return -np.log(np.clip((P * Y).sum(axis=1), 1e-12, None))


def reliability_bins(p, y, n_bins):
    q = np.unique(np.quantile(p, np.linspace(0, 1, n_bins + 1)))
    idx = np.clip(np.searchsorted(q, p, side='right') - 1, 0, len(q) - 2)
    out = []
    for b in range(len(q) - 1):
        m = idx == b
        if m.sum() == 0:
            continue
        out.append({'Bin': b, 'N': int(m.sum()), 'MeanPred': p[m].mean(), 'ObsFreq': y[m].mean()})
    return pd.DataFrame(out)


def murphy(p, y, bins):
    n, base = len(p), y.mean()
    rel = (bins['N'] * (bins['MeanPred'] - bins['ObsFreq']) ** 2).sum() / n
    res = (bins['N'] * (bins['ObsFreq'] - base) ** 2).sum() / n
    unc = base * (1 - base)
    ece = (bins['N'] * (bins['MeanPred'] - bins['ObsFreq']).abs()).sum() / n
    return {'ECE': ece, 'Reliability': rel, 'Resolution': res, 'Uncertainty': unc,
            'BrierBinary': ((p - y) ** 2).mean()}


def paired_bootstrap(diff, n_boot, seed=42):
    rng = np.random.default_rng(seed)
    means = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(n_boot)]
    return np.percentile(means, [5, 95])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bins', type=int, default=10)
    ap.add_argument('--bootstrap', type=int, default=2000)
    args = ap.parse_args()

    model = model_floor_forecasts()
    results = agg.load_actual_results_by_matchday()[['MatchID', 'Result']]
    bookie = load_bookie_forecasts()
    if model.empty or bookie.empty:
        print('No model or bookie forecasts found; nothing to report.')
        return 1
    bookie = bookie.rename(columns={'p_H': 'BK_H', 'p_D': 'BK_D', 'p_A': 'BK_A'})[['MatchID', 'BK_H', 'BK_D', 'BK_A']]
    df = model.merge(results, on='MatchID').merge(bookie, on='MatchID')
    if df.empty:
        print('No overlap between model forecasts, results and odds.')
        return 1

    Y = onehot(df['Result'])
    P_m = df[OUTCOMES].to_numpy()
    P_b = df[['BK_H', 'BK_D', 'BK_A']].to_numpy()

    summary, bins_all = [], []
    for name, P in [('model', P_m), ('bookie', P_b)]:
        row = {'Source': name, 'N': len(df), 'Brier': brier(P, Y).mean(), 'NLL': nll(P, Y).mean()}
        for i, o in enumerate(OUTCOMES):
            b = reliability_bins(P[:, i], Y[:, i], args.bins)
            b.insert(0, 'Outcome', o)
            b.insert(0, 'Source', name)
            bins_all.append(b)
            for k, v in murphy(P[:, i], Y[:, i], b).items():
                row[f'{o}_{k}'] = v
        summary.append(row)
    summary = pd.DataFrame(summary)
    bins_all = pd.concat(bins_all, ignore_index=True)

    gap_b = brier(P_m, Y) - brier(P_b, Y)
    gap_n = nll(P_m, Y) - nll(P_b, Y)
    ci_b, ci_n = paired_bootstrap(gap_b, args.bootstrap), paired_bootstrap(gap_n, args.bootstrap)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT_DIR / 'calibration_summary.csv', index=False)
    bins_all.to_csv(OUT_DIR / 'reliability_bins.csv', index=False)

    pd.set_option('display.width', 160)
    print(f'Matches: {len(df)} across {df["MD"].nunique()} matchdays '
          f'(median {int(df["NRuns"].median())} runs per match in the floor forecast)')
    print(summary[['Source', 'N', 'Brier', 'NLL'] + [f'{o}_ECE' for o in OUTCOMES]].round(4).to_string(index=False))
    print(f'\nModel - bookie, Brier: {gap_b.mean():+.4f}  90% CI [{ci_b[0]:+.4f}, {ci_b[1]:+.4f}]')
    print(f'Model - bookie, NLL:   {gap_n.mean():+.4f}  90% CI [{ci_n[0]:+.4f}, {ci_n[1]:+.4f}]')
    print('(negative = model better; a CI that contains 0 means no demonstrated difference)')

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
        for ax, o in zip(axes, OUTCOMES):
            for name, style in [('model', 'o-'), ('bookie', 's--')]:
                b = bins_all[(bins_all['Source'] == name) & (bins_all['Outcome'] == o)]
                ax.plot(b['MeanPred'], b['ObsFreq'], style, label=name)
            ax.plot([0, 1], [0, 1], color='grey', lw=0.8)
            ax.set_title(f'{o}  (N={len(df)})')
            ax.set_xlabel('Predicted probability')
        axes[0].set_ylabel('Observed frequency')
        axes[0].legend()
        fig.tight_layout()
        fig.savefig(OUT_DIR / 'reliability_diagram.png', dpi=130)
        print(f'\nWrote {OUT_DIR}')
    except ImportError:
        print(f'\nmatplotlib not installed; wrote CSVs only to {OUT_DIR}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
