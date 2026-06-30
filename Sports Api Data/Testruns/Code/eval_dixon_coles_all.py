"""
eval_dixon_coles_all.py - exact post-hoc Dixon-Coles evaluation over all base matchdays.

Dixon-Coles only remaps expected goals -> H/D/A; it does not change BART's expected
goals, which are saved in every base MD{NN}/prediction_weight_runs.csv. So we can
recompute the Dixon-Coles probabilities exactly from saved data (no BART, no OOM)
and get the season-wide verdict with the per-outcome H/A guardrail.

Replicates score_distribution_outcome_probs (mode=score_dixon_coles, alpha=1.0)
with the params used in the MD8/MD18 runs: scale 1.05, rho -0.2, max_goals 10.

Usage:
    python eval_dixon_coles_all.py
"""

import math
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_backtest_results as agg
from diagnose_draws import nll, load_bookie_forecasts

BACKTEST_DIR = agg.BACKTEST_DIR
OUTCOMES = ['H', 'D', 'A']

# Match the params from the MD8/MD18 score_dixon_coles runs.
SCALE = 1.05
RHO = -0.2
MAX_GOALS = 10


def poisson_pmf(lam, max_goals):
    lam = max(0.02, min(8.0, float(lam)))
    probs = [math.exp(-lam)]
    for g in range(1, max_goals + 1):
        probs.append(probs[-1] * lam / float(g))
    return probs


def dixon_coles_probs(exp_home, exp_away):
    lam_h = max(0.02, float(exp_home) * SCALE)
    lam_a = max(0.02, float(exp_away) * SCALE)
    hp, ap = poisson_pmf(lam_h, MAX_GOALS), poisson_pmf(lam_a, MAX_GOALS)
    p_h = p_d = p_a = 0.0
    for hg, hpr in enumerate(hp):
        for ag, apr in enumerate(ap):
            joint = hpr * apr
            if RHO:
                if hg == 0 and ag == 0:
                    joint *= max(1e-12, 1.0 - lam_h * lam_a * RHO)
                elif hg == 0 and ag == 1:
                    joint *= max(1e-12, 1.0 + lam_h * RHO)
                elif hg == 1 and ag == 0:
                    joint *= max(1e-12, 1.0 + lam_a * RHO)
                elif hg == 1 and ag == 1:
                    joint *= max(1e-12, 1.0 - RHO)
            if hg > ag:
                p_h += joint
            elif hg == ag:
                p_d += joint
            else:
                p_a += joint
    tot = p_h + p_d + p_a
    if not math.isfinite(tot) or tot <= 0:
        return float('nan'), float('nan'), float('nan')
    return p_h / tot, p_d / tot, p_a / tot


def base_matchday_dirs():
    out = {}
    for d in sorted(BACKTEST_DIR.iterdir()):
        if d.is_dir() and re.fullmatch(r'MD\d{2}', d.name):
            out[int(d.name[2:])] = d
    return out


def floor_forecasts(folder):
    """Return per-match mean (base) and mean (dixon) forecasts. index=MatchID."""
    rp = folder / 'prediction_weight_runs.csv'
    if not rp.exists():
        return None
    runs = pd.read_csv(rp)
    need = {'MatchID', 'WinProb', 'DrawProb', 'LoseProb', 'ExpectedHomeGoals', 'ExpectedAwayGoals'}
    if not need.issubset(runs.columns) or runs.empty:
        return None
    for c in ['WinProb', 'DrawProb', 'LoseProb', 'ExpectedHomeGoals', 'ExpectedAwayGoals']:
        runs[c] = pd.to_numeric(runs[c], errors='coerce')
    runs['MatchID'] = pd.to_numeric(runs['MatchID'], errors='coerce').astype('Int64')
    runs = runs.dropna(subset=['ExpectedHomeGoals', 'ExpectedAwayGoals'])
    dc = runs.apply(lambda r: dixon_coles_probs(r['ExpectedHomeGoals'], r['ExpectedAwayGoals']),
                    axis=1, result_type='expand')
    runs['dcH'], runs['dcD'], runs['dcA'] = dc[0], dc[1], dc[2]
    g = runs.groupby('MatchID').agg(
        bH=('WinProb', 'mean'), bD=('DrawProb', 'mean'), bA=('LoseProb', 'mean'),
        dH=('dcH', 'mean'), dD=('dcD', 'mean'), dA=('dcA', 'mean'),
    )
    for pre in ['b', 'd']:
        s = g[[pre + 'H', pre + 'D', pre + 'A']].sum(axis=1).replace(0, 1.0)
        for o in OUTCOMES:
            g[pre + o] = g[pre + o] / s
    return g


def collect(rows_accumulator, g, res_map):
    for mid, r in g.iterrows():
        actual = res_map.get(int(mid))
        if actual is None:
            continue
        base_p = {'H': r['bH'], 'D': r['bD'], 'A': r['bA']}[actual]
        dc_p = {'H': r['dH'], 'D': r['dD'], 'A': r['dA']}[actual]
        rows_accumulator.append((actual, nll(base_p), nll(dc_p)))


def outcome_means(df, col):
    out = {o: (df.loc[df['Actual'] == o, col].mean() if (df['Actual'] == o).any() else float('nan'))
           for o in OUTCOMES}
    out['ALL'] = df[col].mean()
    return out


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


if __name__ == '__main__':
    main()
