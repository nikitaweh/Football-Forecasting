"""
diagnose_draws.py - read-only diagnostic of the draw-prediction weakness.

Uses the existing 8-matchday backtest (per-match predictions in each MD folder's
prediction_weight_runs.csv) plus the BWIN odds. No new BART runs.

The deployable per-match forecast = mean of WinProb/DrawProb/LoseProb across all
runs of that matchday (the "floor" estimate, what you'd actually act on).

Three sections:
  1. PRIZE MAP        - per-outcome NLL (H/D/A), model vs bookie. Where do we lose?
  2. DRAW CALIBRATION - mean predicted draw prob vs actual draw rate; median-split
                        discrimination; model vs bookie. Calibration or discrimination?
  3. RECAL PREVIEW    - simulate the safe post-hoc draw multiplier c (p_d *= c,
                        renormalise). In-sample and leave-one-matchday-out optimum,
                        with the per-outcome breakdown so H/A degradation is visible.

Usage:
    python diagnose_draws.py
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_backtest_results as agg
from diagnose_ranker_signals import matchday_dirs

BACKTEST_DIR = agg.BACKTEST_DIR
OUT_PATH = BACKTEST_DIR / 'draw_diagnostic.csv'
OUTCOMES = ['H', 'D', 'A']


def nll(p):
    return -math.log(max(float(p), 1e-12))


def load_model_forecasts():
    """Per-match deployable forecast (mean over runs) + actual result, per matchday."""
    rows = []
    results = agg.load_actual_results_by_matchday()
    res_map = dict(zip(results['MatchID'].astype(int), results['Result']))
    for d in matchday_dirs():
        runs_path = d / 'prediction_weight_runs.csv'
        if not runs_path.exists():
            continue
        try:
            md = int(d.name.replace('MD', ''))
        except ValueError:
            continue
        runs = pd.read_csv(runs_path)
        need = {'MatchID', 'WinProb', 'DrawProb', 'LoseProb'}
        if not need.issubset(runs.columns):
            continue
        for c in ['WinProb', 'DrawProb', 'LoseProb']:
            runs[c] = pd.to_numeric(runs[c], errors='coerce')
        runs['MatchID'] = pd.to_numeric(runs['MatchID'], errors='coerce').astype('Int64')
        grp = runs.groupby('MatchID')[['WinProb', 'DrawProb', 'LoseProb']].mean()
        for mid, r in grp.iterrows():
            mid = int(mid)
            actual = res_map.get(mid)
            if actual is None:
                continue
            s = r['WinProb'] + r['DrawProb'] + r['LoseProb']
            s = s if s > 0 else 1.0
            rows.append({
                'Matchday': md, 'MatchID': mid, 'Actual': actual,
                'p_H': r['WinProb'] / s, 'p_D': r['DrawProb'] / s, 'p_A': r['LoseProb'] / s,
            })
    return pd.DataFrame(rows)


def load_bookie_forecasts():
    """Per-match normalised implied probs + actual result from the latest odds file."""
    if not agg.ODDS_DIR.exists():
        return pd.DataFrame()
    cands = sorted(agg.ODDS_DIR.glob('bwin_historical_odds_*.csv'))
    if not cands:
        return pd.DataFrame()
    df = pd.read_csv(cands[-1])
    need = {'match_id', 'odd_home_win_1', 'odd_draw_x', 'odd_away_win_2', 'result'}
    if not need.issubset(df.columns):
        return pd.DataFrame()
    df = df.dropna(subset=list(need)).copy()
    ph, pd_, pa = 1.0 / df['odd_home_win_1'], 1.0 / df['odd_draw_x'], 1.0 / df['odd_away_win_2']
    z = ph + pd_ + pa
    out = pd.DataFrame({
        'MatchID': df['match_id'].astype(int), 'Actual': df['result'],
        'p_H': ph / z, 'p_D': pd_ / z, 'p_A': pa / z,
    })
    return out


def per_outcome_nll(fc):
    """Mean NLL grouped by actual outcome, plus overall."""
    fc = fc.copy()
    fc['NLL'] = fc.apply(lambda r: nll({'H': r['p_H'], 'D': r['p_D'], 'A': r['p_A']}[r['Actual']]), axis=1)
    rows = []
    for o in OUTCOMES:
        sub = fc[fc['Actual'] == o]
        rows.append({'Outcome': o, 'N': len(sub), 'MeanNLL': sub['NLL'].mean() if len(sub) else float('nan')})
    rows.append({'Outcome': 'ALL', 'N': len(fc), 'MeanNLL': fc['NLL'].mean()})
    return pd.DataFrame(rows), fc


def recal_total_nll(fc, c):
    """Total mean NLL after multiplying draw prob by c and renormalising."""
    pH, pD, pA = fc['p_H'].values, fc['p_D'].values * c, fc['p_A'].values
    z = pH + pD + pA
    pH, pD, pA = pH / z, pD / z, pA / z
    probs = {'H': pH, 'D': pD, 'A': pA}
    idx = {'H': 0, 'D': 1, 'A': 2}
    stack = np.vstack([pH, pD, pA])
    actual_idx = fc['Actual'].map(idx).values
    p_act = stack[actual_idx, np.arange(len(fc))]
    return float(np.mean(-np.log(np.clip(p_act, 1e-12, None))))


def recal_per_outcome(fc, c):
    pH, pD, pA = fc['p_H'].values, fc['p_D'].values * c, fc['p_A'].values
    z = pH + pD + pA
    pH, pD, pA = pH / z, pD / z, pA / z
    out = {}
    for o, col in zip(OUTCOMES, [pH, pD, pA]):
        mask = (fc['Actual'] == o).values
        out[o] = float(np.mean(-np.log(np.clip(col[mask], 1e-12, None)))) if mask.sum() else float('nan')
    out['ALL'] = recal_total_nll(fc, c)
    return out


def main():
    model = load_model_forecasts()
    bookie = load_bookie_forecasts()
    if model.empty:
        print('No model forecasts found.')
        return
    # Restrict to matches present for both, for fair comparison.
    common = set(model['MatchID'])
    if not bookie.empty:
        common &= set(bookie['MatchID'])
    model = model[model['MatchID'].isin(common)].copy()
    bookie = bookie[bookie['MatchID'].isin(common)].copy() if not bookie.empty else bookie

    n = len(model)
    draw_rate = (model['Actual'] == 'D').mean()
    print('=' * 84)
    print(f'DRAW DIAGNOSTIC  ({n} matches across {model["Matchday"].nunique()} matchdays)')
    print(f'Actual draw rate: {draw_rate:.1%}  ({(model["Actual"]=="D").sum()} of {n})')
    print('Forecast = per-match mean over runs (deployable floor estimate).')
    print('=' * 84)

    # ---- 1. PRIZE MAP ----
    m_po, model_scored = per_outcome_nll(model)
    print('\n=== 1. PRIZE MAP: per-outcome NLL (model vs bookie) ===')
    if not bookie.empty:
        b_po, _ = per_outcome_nll(bookie)
        merged = m_po.merge(b_po, on='Outcome', suffixes=('_Model', '_Bookie'))
        merged['Gap(Model-Bookie)'] = merged['MeanNLL_Model'] - merged['MeanNLL_Bookie']
        disp = merged[['Outcome', 'N_Model', 'MeanNLL_Model', 'MeanNLL_Bookie', 'Gap(Model-Bookie)']]
        disp = disp.rename(columns={'N_Model': 'N'})
        for c in ['MeanNLL_Model', 'MeanNLL_Bookie', 'Gap(Model-Bookie)']:
            disp[c] = disp[c].apply(agg.fmt)
        print(disp.to_string(index=False))
        print('\n  Negative gap = model better on that outcome. This shows WHERE the edge lives.')
    else:
        disp = m_po.copy()
        disp['MeanNLL'] = disp['MeanNLL'].apply(agg.fmt)
        print(disp.to_string(index=False))

    # ---- 2. DRAW CALIBRATION & DISCRIMINATION ----
    print('\n=== 2. DRAW CALIBRATION & DISCRIMINATION ===')
    print(f"  Model mean predicted draw prob : {model['p_D'].mean():.3f}")
    if not bookie.empty:
        print(f"  Bookie mean implied draw prob  : {bookie['p_D'].mean():.3f}")
    print(f"  Actual draw rate               : {draw_rate:.3f}")
    gap = draw_rate - model['p_D'].mean()
    print(f"  Model under(+)/over(-)-prices draws by: {gap:+.3f}")

    # Discrimination: split matches by model draw prob, compare actual draw rate.
    print('\n  Discrimination (do higher draw-prob matches actually draw more?):')
    mm = model.copy()
    mm['is_draw'] = (mm['Actual'] == 'D').astype(int)
    try:
        mm['bin'] = pd.qcut(mm['p_D'], 3, labels=['low', 'mid', 'high'], duplicates='drop')
        tbl = mm.groupby('bin', observed=True).agg(
            N=('is_draw', 'size'), MeanPredDraw=('p_D', 'mean'), ActualDrawRate=('is_draw', 'mean')
        ).reset_index()
        for c in ['MeanPredDraw', 'ActualDrawRate']:
            tbl[c] = tbl[c].apply(lambda x: f'{x:.3f}')
        print(tbl.to_string(index=False))
        print('  If ActualDrawRate rises low->high, the model CAN discriminate draws (fix is effective).')
    except ValueError:
        print('  (not enough spread in draw probs to bin)')

    # ---- 3. RECALIBRATION PREVIEW (safe post-hoc draw multiplier) ----
    print('\n=== 3. RECALIBRATION PREVIEW: draw multiplier c (p_D *= c, renormalise) ===')
    cs = np.round(np.linspace(0.7, 2.5, 37), 3)
    base_total = recal_total_nll(model, 1.0)
    totals = [(c, recal_total_nll(model, c)) for c in cs]
    c_star, best_total = min(totals, key=lambda t: t[1])
    print(f'  Baseline (c=1.0) total NLL: {base_total:.4f}')
    print(f'  In-sample optimum c*={c_star:.2f} -> total NLL {best_total:.4f}  '
          f'(improvement {base_total - best_total:+.4f})')
    base_po = recal_per_outcome(model, 1.0)
    star_po = recal_per_outcome(model, c_star)
    print('  Per-outcome NLL at c=1.0 vs c*:  (H/A must not degrade meaningfully)')
    for o in OUTCOMES + ['ALL']:
        print(f'    {o}: {base_po[o]:.4f} -> {star_po[o]:.4f}  ({star_po[o]-base_po[o]:+.4f})')

    # Leave-one-matchday-out: honest out-of-sample c.
    mds = sorted(model['Matchday'].unique())
    lomo_nll, lomo_cs = [], []
    for held in mds:
        tr = model[model['Matchday'] != held]
        te = model[model['Matchday'] == held]
        if tr.empty or te.empty:
            continue
        c_tr = min(cs, key=lambda c: recal_total_nll(tr, c))
        lomo_cs.append(c_tr)
        # Score held-out matches at the train-chosen c (collect per-match NLL).
        pH, pD, pA = te['p_H'].values, te['p_D'].values * c_tr, te['p_A'].values
        z = pH + pD + pA
        stack = np.vstack([pH / z, pD / z, pA / z])
        idx = te['Actual'].map({'H': 0, 'D': 1, 'A': 2}).values
        p_act = stack[idx, np.arange(len(te))]
        lomo_nll.extend((-np.log(np.clip(p_act, 1e-12, None))).tolist())
    if lomo_nll:
        lomo_mean = float(np.mean(lomo_nll))
        print(f'\n  LOMO (honest) mean c={np.mean(lomo_cs):.2f}, total NLL {lomo_mean:.4f}  '
              f'(vs baseline {base_total:.4f} = {base_total - lomo_mean:+.4f})')
        print('  LOMO improvement is the realistic, non-overfit prize of the safe recal layer.')

    # ---- Persist ----
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8', newline='') as f:
        f.write('# Per-outcome NLL (model)\n')
        m_po.to_csv(f, index=False)
        f.write('\n# Recalibration sweep (c, total_nll)\n')
        pd.DataFrame(totals, columns=['c', 'total_nll']).to_csv(f, index=False)
    print(f'\nDiagnostic CSV written to: {OUT_PATH}')


if __name__ == '__main__':
    main()
