"""
test_nn_surrogate.py - does the NN surrogate rank candidates better than GBR?

The surrogate predicts a candidate's AvgNLL from its weight vector. Its job is
cross-matchday: learn on past matchdays, rank candidates on a new one. This test
does leave-one-matchday-out on the 34-matchday backtest weights->demeaned-AvgNLL
data with BOTH the GBR (current default) and the MLPRegressor (the 'nn' switch,
same 64-32 architecture as the pipeline), and reports Spearman calibration +
gap-captured. Exact, read-only, no BART.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.neural_network import MLPRegressor

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_backtest_results as agg
from diagnose_ranker_signals import matchday_dirs, load_matchday_summaries
from diagnose_weight_transfer import build_pooled, spearman

RANDOM_STATE = 42


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


if __name__ == '__main__':
    main()
