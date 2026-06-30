"""
compare_draw_modes.py - compare base vs draw-mode backtests for given matchdays.

For each matchday it gathers the base MD{NN}/ folder and every MD{NN}_<mode>_.../
variant, computes the deployable floor forecast (per-match mean over runs), and
reports per-outcome (H/D/A) NLL + total + gap vs the BWIN bookie. This is the
guardrail view: a draw mode should improve D without degrading H/A.

Usage:
    python compare_draw_modes.py                 # MD8 and MD18
    python compare_draw_modes.py --matchdays 8 18 24
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_backtest_results as agg
from diagnose_draws import nll, load_bookie_forecasts

BACKTEST_DIR = agg.BACKTEST_DIR
OUTCOMES = ['H', 'D', 'A']


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


def label_for(folder_name, md):
    base = f'MD{md:02d}'
    if folder_name == base:
        return 'base (normal)'
    suffix = folder_name[len(base) + 1:]
    # shorten timestamp for readability
    return re.sub(r'_\d{8}_\d{6}$', '', suffix)


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


if __name__ == '__main__':
    main()
