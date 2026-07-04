"""
compare_models_vs_bookie.py - compare all reproducible model variants vs BWIN.

Across every completed base matchday (MD{NN}/), recompute each outcome-probability
variant EXACTLY post-hoc from the saved per-run expected goals + base probs
(no BART needed), build the deployable floor (per-match mean over runs), and score
per-outcome (H/D/A) NLL + total against actual results and the bookmaker.

Variants:
  base                  - the model's normal Gaussian-band probabilities
  dixon_full (a=1.0)    - full Poisson+Dixon-Coles replacement
  dixon_full (a=0.4)    - gentle blend of base and Dixon-Coles
  dixon_draw_ratio      - Dixon-Coles DRAW level only, base H/A ratio kept
  poisson_draw_ratio    - Poisson DRAW level only, base H/A ratio kept

(The draw_ratio family keeps the model's own H/A discrimination and only borrows
the draw level — the same shape as the draw_multilayer_overlay.)

Usage:
    python compare_models_vs_bookie.py
"""

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_backtest_results as agg
from diagnose_draws import nll, load_bookie_forecasts
from eval_dixon_coles_all import base_matchday_dirs, poisson_pmf

OUTCOMES = ['H', 'D', 'A']
SCALE, RHO, MAX_GOALS = 1.05, -0.2, 10


def score_probs(exp_h, exp_a, rho):
    lam_h = max(0.02, float(exp_h) * SCALE)
    lam_a = max(0.02, float(exp_a) * SCALE)
    hp, ap = poisson_pmf(lam_h, MAX_GOALS), poisson_pmf(lam_a, MAX_GOALS)
    ph = pd_ = pa = 0.0
    for hg, hpr in enumerate(hp):
        for ag, apr in enumerate(ap):
            j = hpr * apr
            if rho:
                if hg == 0 and ag == 0:   j *= max(1e-12, 1.0 - lam_h * lam_a * rho)
                elif hg == 0 and ag == 1: j *= max(1e-12, 1.0 + lam_h * rho)
                elif hg == 1 and ag == 0: j *= max(1e-12, 1.0 + lam_a * rho)
                elif hg == 1 and ag == 1: j *= max(1e-12, 1.0 - rho)
            if hg > ag: ph += j
            elif hg == ag: pd_ += j
            else: pa += j
    t = ph + pd_ + pa
    if not math.isfinite(t) or t <= 0:
        return None
    return ph / t, pd_ / t, pa / t


def variants_for_row(bH, bD, bA, exp_h, exp_a):
    """Return {variant: (h,d,a)} for one match-run."""
    out = {'base': (bH, bD, bA)}
    dc = score_probs(exp_h, exp_a, RHO)
    po = score_probs(exp_h, exp_a, 0.0)
    nd = bH + bA
    home_share = bH / nd if nd > 0 else 0.5

    if dc:
        out['dixon_full_a1.0'] = dc
        out['dixon_full_a0.4'] = tuple(0.6 * b + 0.4 * d for b, d in zip((bH, bD, bA), dc))
        dD = dc[1]
        out['dixon_draw_ratio'] = ((1 - dD) * home_share, dD, (1 - dD) * (1 - home_share))
    if po:
        pD = po[1]
        out['poisson_draw_ratio'] = ((1 - pD) * home_share, pD, (1 - pD) * (1 - home_share))
    # normalise defensively
    for k, (h, d, a) in list(out.items()):
        s = h + d + a
        if s > 0:
            out[k] = (h / s, d / s, a / s)
    return out


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


if __name__ == '__main__':
    main()
