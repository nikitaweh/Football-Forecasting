"""
compare_md19_20.py - MD19/MD20 variant comparison (post-hoc, exact).

Shows, for MD19+MD20, per-outcome NLL at the deployable floor for:
  v2_normal   - workload OFF, normal probs      (MD{NN}/)
  v3_normal   - workload ON,  normal probs      (MD{NN}_bases_v3_player_workload/)
  v3_dixon a1 - workload ON + Dixon-Coles (post-hoc from the v3 runs' expected goals)
  v3_dixon a.4- gentle blend
vs bet365/BWIN bookie.

Answers: does the workload feature help (v2_normal -> v3_normal), and does
Dixon-Coles stack on top of it (v3_normal -> v3_dixon)?
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_backtest_results as agg
from diagnose_draws import nll, load_bookie_forecasts
from compare_models_vs_bookie import variants_for_row

BT = agg.BACKTEST_DIR
OUT = ['H', 'D', 'A']
MDS = [19, 20]


def per_match_means(folder):
    rp = folder / 'prediction_weight_runs.csv'
    if not rp.exists():
        return None
    runs = pd.read_csv(rp)
    need = {'MatchID', 'WinProb', 'DrawProb', 'LoseProb', 'ExpectedHomeGoals', 'ExpectedAwayGoals'}
    if not need.issubset(runs.columns):
        return None
    for c in ['WinProb', 'DrawProb', 'LoseProb', 'ExpectedHomeGoals', 'ExpectedAwayGoals']:
        runs[c] = pd.to_numeric(runs[c], errors='coerce')
    runs['MatchID'] = pd.to_numeric(runs['MatchID'], errors='coerce').astype('Int64')
    return runs.dropna(subset=list(need))


def main():
    results = agg.load_actual_results_by_matchday()
    res_map = dict(zip(results['MatchID'].astype(int), results['Result']))
    bookie_df = load_bookie_forecasts()
    bk_map = {int(r.MatchID): {'H': r.p_H, 'D': r.p_D, 'A': r.p_A} for r in bookie_df.itertuples()}

    ROWS = ['v2_normal', 'v3_normal', 'v3_dixon_a1.0', 'v3_dixon_a0.4', 'bookie']
    acc = {r: {o: [] for o in OUT} for r in ROWS}
    acc_all = {r: [] for r in ROWS}

    for md in MDS:
        v2_folder = BT / f'MD{md:02d}'
        v3_folder = BT / f'MD{md:02d}_bases_v3_player_workload'
        v2 = per_match_means(v2_folder)
        v3 = per_match_means(v3_folder)
        if v2 is None or v3 is None:
            print(f'MD{md}: missing folder(s) — v2={v2 is not None}, v3={v3 is not None}')
            continue

        # v2_normal: mean of base probs per match
        for mid, g in v2.groupby('MatchID'):
            actual = res_map.get(int(mid))
            if actual is None:
                continue
            h, d, a = g['WinProb'].mean(), g['DrawProb'].mean(), g['LoseProb'].mean()
            s = h + d + a
            p = {'H': h, 'D': d, 'A': a}[actual] / (s if s else 1)
            acc['v2_normal'][actual].append(nll(p)); acc_all['v2_normal'].append(nll(p))

        # v3_normal + v3_dixon variants: build per-run variants, average per match
        for mid, g in v3.groupby('MatchID'):
            actual = res_map.get(int(mid))
            if actual is None:
                continue
            sums = {'v3_normal': [0.0, 0.0, 0.0], 'v3_dixon_a1.0': [0.0, 0.0, 0.0], 'v3_dixon_a0.4': [0.0, 0.0, 0.0]}
            n = 0
            for _, r in g.iterrows():
                vs = variants_for_row(r['WinProb'], r['DrawProb'], r['LoseProb'],
                                      r['ExpectedHomeGoals'], r['ExpectedAwayGoals'])
                for key, vkey in [('v3_normal', 'base'), ('v3_dixon_a1.0', 'dixon_full_a1.0'), ('v3_dixon_a0.4', 'dixon_full_a0.4')]:
                    if vkey in vs:
                        for i in range(3):
                            sums[key][i] += vs[vkey][i]
                n += 1
            if n == 0:
                continue
            ai = {'H': 0, 'D': 1, 'A': 2}[actual]
            for key in sums:
                h, d, a = (x / n for x in sums[key])
                p = [h, d, a][ai]
                acc[key][actual].append(nll(p)); acc_all[key].append(nll(p))

        # bookie
        for mid in v3['MatchID'].unique():
            mid = int(mid)
            actual = res_map.get(mid)
            if actual is None or mid not in bk_map:
                continue
            p = bk_map[mid][actual]
            acc['bookie'][actual].append(nll(p)); acc_all['bookie'].append(nll(p))

    def mean(x): return sum(x) / len(x) if x else float('nan')

    nAll = len(acc_all['v2_normal'])
    nH, nD, nA = len(acc['v2_normal']['H']), len(acc['v2_normal']['D']), len(acc['v2_normal']['A'])
    print('=' * 78)
    print(f'MD19 + MD20 — {nAll} matches (H{nH}/D{nD}/A{nA}), deployable floor NLL')
    print('=' * 78)
    hdr = f'{"Variant":16} {"H":>8} {"D":>8} {"A":>8} {"TOTAL":>8} {"vsBookie":>9}'
    print(hdr); print('-' * len(hdr))
    bk_all = mean(acc_all['bookie'])
    for r in ROWS:
        H, D, A, T = mean(acc[r]['H']), mean(acc[r]['D']), mean(acc[r]['A']), mean(acc_all[r])
        vb = '' if r == 'bookie' else f'{T-bk_all:>+9.4f}'
        print(f'{r:16} {agg.fmt(H):>8} {agg.fmt(D):>8} {agg.fmt(A):>8} {agg.fmt(T):>8} {vb:>9}')
    print('\nWorkload effect: v2_normal -> v3_normal | Dixon-on-v3: v3_normal -> v3_dixon')


if __name__ == '__main__':
    main()
