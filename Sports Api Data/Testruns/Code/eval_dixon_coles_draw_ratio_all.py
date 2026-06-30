"""
eval_dixon_coles_draw_ratio_all.py - exact post-hoc Dixon-Coles DRAW-RATIO
evaluation over all base matchdays.

Companion to eval_dixon_coles_all.py. That script evaluates the full
score_dixon_coles remap (H, D and A all taken from the Dixon-Coles score grid).
This one evaluates the score_dixon_coles_draw_ratio mode instead: take only the
Dixon-Coles DRAW probability, and keep BART's home:away ratio for the remaining
mass. That mirrors blend_outcome_probabilities(... mode='..._draw_ratio') in
AI_match_stats_prediction.py at alpha = 1.0.

Like eval_dixon_coles_all, Dixon-Coles only remaps expected goals -> H/D/A; it
does not touch BART's expected goals (saved in every base MD{NN}/
prediction_weight_runs.csv), so we recompute exactly from saved data — no BART,
no OOM — and get the season-wide verdict with the per-outcome H/A guardrail.

Params match the MD8/MD18 score_dixon_coles runs: scale 1.05, rho -0.2,
max_goals 10, alpha 1.0.

Usage:
    python eval_dixon_coles_draw_ratio_all.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_backtest_results as agg
import eval_dixon_coles_all as dcall
from diagnose_draws import nll, load_bookie_forecasts

OUTCOMES = ['H', 'D', 'A']
# alpha 1.0 -> deployable draw-ratio forecast is the candidate, no blend with base.
ALPHA = 1.0


def draw_ratio_probs(base_h, base_a, dc_draw):
    """Dixon-Coles draw prob, with the remaining mass split by BART's H:A ratio."""
    non_draw = base_h + base_a
    home_share = base_h / non_draw if non_draw > 0 else 0.5
    d = dc_draw
    h = (1.0 - d) * home_share
    a = (1.0 - d) * (1.0 - home_share)
    return h, d, a


def floor_forecasts(folder):
    """Per-match mean base (normal) and mean Dixon-Coles draw-ratio forecasts."""
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

    dc = runs.apply(lambda r: dcall.dixon_coles_probs(r['ExpectedHomeGoals'], r['ExpectedAwayGoals']),
                    axis=1, result_type='expand')
    runs['dcD'] = dc[1]
    # Per-run draw-ratio blend (alpha 1.0): DC draw, BART H:A split.
    dr = runs.apply(lambda r: draw_ratio_probs(r['WinProb'], r['LoseProb'], r['dcD']),
                    axis=1, result_type='expand')
    runs['drH'], runs['drD'], runs['drA'] = dr[0], dr[1], dr[2]

    g = runs.groupby('MatchID').agg(
        bH=('WinProb', 'mean'), bD=('DrawProb', 'mean'), bA=('LoseProb', 'mean'),
        dH=('drH', 'mean'), dD=('drD', 'mean'), dA=('drA', 'mean'),
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
        dr_p = {'H': r['dH'], 'D': r['dD'], 'A': r['dA']}[actual]
        rows_accumulator.append((actual, nll(base_p), nll(dr_p)))


def outcome_means(df, col):
    out = {o: (df.loc[df['Actual'] == o, col].mean() if (df['Actual'] == o).any() else float('nan'))
           for o in OUTCOMES}
    out['ALL'] = df[col].mean()
    return out


def main():
    dirs = dcall.base_matchday_dirs()
    results = agg.load_actual_results_by_matchday()
    res_map = dict(zip(results['MatchID'].astype(int), results['Result']))
    bookie_df = load_bookie_forecasts()
    bookie_nll = {int(r['MatchID']): nll({'H': r['p_H'], 'D': r['p_D'], 'A': r['p_A']}[res_map[int(r['MatchID'])]])
                  for _, r in bookie_df.iterrows() if int(r['MatchID']) in res_map}

    pooled = []          # (Actual, base_nll, dr_nll)
    per_md = []
    for md, folder in dirs.items():
        g = floor_forecasts(folder)
        if g is None:
            continue
        local = []
        collect(local, g, res_map)
        if not local:
            continue
        pooled.extend(local)
        ldf = pd.DataFrame(local, columns=['Actual', 'base', 'dr'])
        mids = [int(m) for m in g.index]
        bk = [bookie_nll[m] for m in mids if m in bookie_nll]
        per_md.append({
            'MD': md, 'N': len(ldf),
            'BaseNLL': ldf['base'].mean(), 'DrawRatioNLL': ldf['dr'].mean(),
            'Delta': ldf['dr'].mean() - ldf['base'].mean(),
            'BookieNLL': (sum(bk) / len(bk)) if bk else float('nan'),
        })

    df = pd.DataFrame(pooled, columns=['Actual', 'base', 'dr'])
    base_o = outcome_means(df, 'base')
    dr_o = outcome_means(df, 'dr')

    print('=' * 84)
    print(f'POST-HOC DIXON-COLES DRAW-RATIO over {len(per_md)} base matchdays, {len(df)} matches')
    print(f'(scale {dcall.SCALE}, rho {dcall.RHO}, max_goals {dcall.MAX_GOALS}, alpha {ALPHA}) — deployable floor')
    print('  DrawProb = Dixon-Coles draw; remaining mass keeps BART home:away ratio')
    print('=' * 84)
    print('\n=== Pooled per-outcome NLL: base (normal) vs Dixon-Coles draw-ratio ===')
    counts = {o: int((df["Actual"] == o).sum()) for o in OUTCOMES}
    print(f'{"Outcome":8} {"N":>4} {"Base":>9} {"DrawRatio":>10} {"Delta":>9}   guardrail')
    for o in OUTCOMES + ['ALL']:
        n = counts.get(o, len(df))
        d = dr_o[o] - base_o[o]
        flag = ''
        if o in ('H', 'A'):
            flag = 'OK' if d <= 0.005 else 'DEGRADED'
        elif o == 'D':
            flag = 'improved' if d < 0 else 'worse'
        print(f'{o:8} {n:>4} {agg.fmt(base_o[o]):>9} {agg.fmt(dr_o[o]):>10} {d:>+9.4f}   {flag}')

    if bookie_nll:
        bk_all = sum(bookie_nll.values()) / len(bookie_nll)
        print(f'\n  Bookie pooled NLL: {bk_all:.4f}')
        print(f'  Base      total vs bookie: {base_o["ALL"]-bk_all:+.4f}')
        print(f'  DrawRatio total vs bookie: {dr_o["ALL"]-bk_all:+.4f}')

    md_df = pd.DataFrame(per_md).sort_values('MD')
    improved = int((md_df['Delta'] < 0).sum())
    print(f'\n=== Per-matchday (DrawRatio - base) ===')
    print(f'  Matchdays improved by Dixon-Coles draw-ratio: {improved}/{len(md_df)}')
    print(f'  Mean per-matchday delta: {md_df["Delta"].mean():+.4f}')
    disp = md_df.copy()
    for c in ['BaseNLL', 'DrawRatioNLL', 'Delta', 'BookieNLL']:
        disp[c] = disp[c].apply(agg.fmt)
    print(disp.to_string(index=False))

    print('\n=== VERDICT ===')
    dH, dA, dAll = dr_o['H'] - base_o['H'], dr_o['A'] - base_o['A'], dr_o['ALL'] - base_o['ALL']
    if dAll < 0 and dH <= 0.005 and dA <= 0.005:
        print(f'Dixon-Coles draw-ratio improves total NLL ({dAll:+.4f}) AND holds the H/A guardrail -> adopt.')
    elif dAll < 0:
        print(f'Dixon-Coles draw-ratio improves total NLL ({dAll:+.4f}) but DEGRADES H/A '
              f'(H {dH:+.4f}, A {dA:+.4f}) -> net positive but violates the strict guardrail.')
    else:
        print(f'Dixon-Coles draw-ratio does NOT improve total NLL ({dAll:+.4f}) -> do not adopt.')


if __name__ == '__main__':
    main()
