"""
probe_draw_signal.py - read-only probe: does ANY signal separate draws?

The draw diagnostic showed a level (calibration) fix is a wash because the model
can't tell WHICH matches draw. Before building a draw-discrimination feature, test
whether draw-proneness is predictable AT ALL from available signals:

  - Model draw prob          (does the model's own p_D rank draws?)
  - Model evenness  -|pH-pA|  (does "the model sees an even match" predict draws?)
  - Bookie draw prob          (does the efficient market rank draws, or only level?)
  - Bookie evenness -|pH-pA|  (does the market's evenness predict draws?)

Headline metric: ROC-AUC for separating draw vs non-draw (0.5 = no signal). The
BOOKIE draw-prob AUC is the key number: if the market itself can't rank draws
(AUC ~ 0.5), draws are irreducible from pre-match info and we should stop. A
bootstrap 90% CI shows whether AUC>0.5 is real at N=72.

Usage:
    python probe_draw_signal.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_backtest_results as agg
from diagnose_draws import load_model_forecasts, load_bookie_forecasts


def auc_ci(y, score, n_boot=2000, seed=0):
    """AUC + 90% bootstrap CI. AUC>0.5 => higher score on draws."""
    y = np.asarray(y)
    score = np.asarray(score)
    if len(np.unique(y)) < 2:
        return float('nan'), float('nan'), float('nan')
    auc = roc_auc_score(y, score)
    rng = np.random.default_rng(seed)
    boots = []
    idx = np.arange(len(y))
    for _ in range(n_boot):
        b = rng.choice(idx, size=len(idx), replace=True)
        if len(np.unique(y[b])) < 2:
            continue
        boots.append(roc_auc_score(y[b], score[b]))
    lo, hi = np.percentile(boots, [5, 95]) if boots else (float('nan'), float('nan'))
    return auc, lo, hi


def tertile_table(df, signal_col, label):
    d = df.copy()
    d['is_draw'] = (d['Actual'] == 'D').astype(int)
    try:
        d['bin'] = pd.qcut(d[signal_col], 3, labels=['low', 'mid', 'high'], duplicates='drop')
    except ValueError:
        return None
    t = d.groupby('bin', observed=True).agg(
        N=('is_draw', 'size'), MeanSignal=(signal_col, 'mean'), ActualDrawRate=('is_draw', 'mean')
    ).reset_index()
    t.insert(0, 'Signal', label)
    return t


def main():
    model = load_model_forecasts()
    bookie = load_bookie_forecasts()
    if model.empty or bookie.empty:
        print('Need both model and bookie forecasts.')
        return

    m = model.rename(columns={'p_H': 'm_H', 'p_D': 'm_D', 'p_A': 'm_A'})
    b = bookie.rename(columns={'p_H': 'b_H', 'p_D': 'b_D', 'p_A': 'b_A'})[['MatchID', 'b_H', 'b_D', 'b_A']]
    df = m.merge(b, on='MatchID', how='inner')
    df['is_draw'] = (df['Actual'] == 'D').astype(int)

    df['Model_DrawProb'] = df['m_D']
    df['Model_Evenness'] = -(df['m_H'] - df['m_A']).abs()
    df['Bookie_DrawProb'] = df['b_D']
    df['Bookie_Evenness'] = -(df['b_H'] - df['b_A']).abs()

    n, nd = len(df), int(df['is_draw'].sum())
    print('=' * 78)
    print(f'DRAW-SIGNAL PROBE  ({n} matches, {nd} draws = {nd/n:.1%})')
    print('AUC = P(signal ranks a random draw above a random non-draw). 0.5 = no signal.')
    print('=' * 78)

    signals = ['Bookie_DrawProb', 'Bookie_Evenness', 'Model_DrawProb', 'Model_Evenness']
    rows = []
    for s in signals:
        auc, lo, hi = auc_ci(df['is_draw'].values, df[s].values)
        rows.append({'Signal': s, 'AUC': auc, 'CI90_low': lo, 'CI90_high': hi,
                     'Real(>0.5)?': 'yes' if lo > 0.5 else 'no'})
    res = pd.DataFrame(rows)
    disp = res.copy()
    for c in ['AUC', 'CI90_low', 'CI90_high']:
        disp[c] = disp[c].apply(agg.fmt)
    print('\n=== Draw-discrimination AUC ===')
    print(disp.to_string(index=False))

    print('\n=== Tertile draw rates (key signals) ===')
    for s, lbl in [('Bookie_DrawProb', 'Bookie draw prob'), ('Model_Evenness', 'Model evenness')]:
        t = tertile_table(df, s, lbl)
        if t is not None:
            tt = t.copy()
            for c in ['MeanSignal', 'ActualDrawRate']:
                tt[c] = tt[c].apply(lambda x: f'{x:.3f}')
            print(tt.to_string(index=False))
            print()

    # ---- Verdict ----
    bookie_auc = res.loc[res['Signal'] == 'Bookie_DrawProb'].iloc[0]
    any_real = (res['CI90_low'] > 0.5).any()
    print('=' * 78)
    if bookie_auc['CI90_low'] > 0.5:
        print(f"VERDICT: The MARKET ranks draws (Bookie_DrawProb AUC={bookie_auc['AUC']:.3f}, "
              f"CI [{bookie_auc['CI90_low']:.3f}, {bookie_auc['CI90_high']:.3f}]).")
        print("         Draw signal EXISTS -> a draw-discrimination feature is justified.")
    elif any_real:
        print("VERDICT: The bookie's draw prob shows no clear ranking power at N=72, but another")
        print("         signal does. Weak/uncertain - more matchdays would sharpen this.")
    else:
        print("VERDICT: No signal (incl. the efficient market) reliably ranks draws at N=72.")
        print("         Draws look near-irreducible from pre-match info -> recommend accept-as-is")
        print("         unless a larger sample later reveals a signal.")
    print('=' * 78)


if __name__ == '__main__':
    main()
