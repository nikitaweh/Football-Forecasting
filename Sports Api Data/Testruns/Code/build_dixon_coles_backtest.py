"""
build_dixon_coles_backtest.py - generate the normal Dixon-Coles outcome data for
every base matchday and persist it into Datacollection backtest/.

Dixon-Coles is *post-hoc*: it only remaps BART's saved expected goals -> H/D/A, so
it is recomputed exactly from each base MD{NN}/prediction_weight_runs.csv with no
BART re-run. The "normal" params match the MD8/MD18 score_dixon_coles runs
(scale 1.05, rho -0.2, max_goals 10, alpha 1.0) - reused from eval_dixon_coles_all.

Writes:
  - Datacollection backtest/MD{NN}/dixon_coles_outcome_table.csv  (per matchday:
    per-match base vs Dixon probs, expected goals, predicted/actual result, NLL)
  - Datacollection backtest/dixon_coles_season.csv                (one row per MD)

The compute functions (build_frames) are imported by build_dashboard_data.py so
the dashboard shows the same numbers without touching the backtest folder.

Usage:
    python build_dixon_coles_backtest.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_backtest_results as agg
import eval_dixon_coles_all as dce          # dixon_coles_probs, SCALE/RHO/MAX_GOALS, base_matchday_dirs
from diagnose_draws import nll, load_bookie_forecasts

BACKTEST_DIR = agg.BACKTEST_DIR
OUTCOMES = ['H', 'D', 'A']
PARAMS = dict(scale=dce.SCALE, rho=dce.RHO, max_goals=dce.MAX_GOALS, alpha=1.0)
PER_MD_NAME = 'dixon_coles_outcome_table.csv'
SEASON_NAME = 'dixon_coles_season.csv'


def _argmax_outcome(h, d, a):
    vals = (h, d, a)
    return OUTCOMES[max(range(3), key=lambda i: vals[i])]


def _teams_for(folder):
    """MatchID -> {MatchDate, HomeTeam, AwayTeam} from the folder's ensemble table."""
    p = folder / 'future_outcome_table_ensemble.csv'
    if not p.exists():
        return {}
    try:
        e = pd.read_csv(p)
    except (pd.errors.EmptyDataError, OSError):
        return {}
    if 'MatchID' not in e.columns or e.empty:
        return {}
    e['MatchID'] = pd.to_numeric(e['MatchID'], errors='coerce')
    cols = [c for c in ('MatchDate', 'HomeTeam', 'AwayTeam') if c in e.columns]
    out = {}
    for _, r in e.iterrows():
        if pd.notna(r['MatchID']):
            out[int(r['MatchID'])] = {c: r[c] for c in cols}
    return out


def per_md_table(folder, res_map):
    """Per-match base vs Dixon-Coles deployable-floor forecast for one matchday."""
    rp = folder / 'prediction_weight_runs.csv'
    if not rp.exists():
        return None
    try:
        runs = pd.read_csv(rp)
    except (pd.errors.EmptyDataError, OSError):
        return None
    need = {'MatchID', 'WinProb', 'DrawProb', 'LoseProb', 'ExpectedHomeGoals', 'ExpectedAwayGoals'}
    if not need.issubset(runs.columns) or runs.empty:
        return None
    for c in ('WinProb', 'DrawProb', 'LoseProb', 'ExpectedHomeGoals', 'ExpectedAwayGoals'):
        runs[c] = pd.to_numeric(runs[c], errors='coerce')
    runs['MatchID'] = pd.to_numeric(runs['MatchID'], errors='coerce')
    runs = runs.dropna(subset=['MatchID', 'ExpectedHomeGoals', 'ExpectedAwayGoals'])
    if runs.empty:
        return None

    dc = runs.apply(lambda r: dce.dixon_coles_probs(r['ExpectedHomeGoals'], r['ExpectedAwayGoals']),
                    axis=1, result_type='expand')
    runs['dcH'], runs['dcD'], runs['dcA'] = dc[0], dc[1], dc[2]
    grp = runs.groupby('MatchID').agg(
        xH=('ExpectedHomeGoals', 'mean'), xA=('ExpectedAwayGoals', 'mean'),
        bH=('WinProb', 'mean'), bD=('DrawProb', 'mean'), bA=('LoseProb', 'mean'),
        dH=('dcH', 'mean'), dD=('dcD', 'mean'), dA=('dcA', 'mean'),
    )
    for pre in ('b', 'd'):  # normalise both forecasts to sum to 1
        s = grp[[pre + 'H', pre + 'D', pre + 'A']].sum(axis=1).replace(0, 1.0)
        for o in OUTCOMES:
            grp[pre + o] = grp[pre + o] / s

    teams = _teams_for(folder)
    rows = []
    for mid, r in grp.iterrows():
        mid = int(mid)
        info = teams.get(mid, {})
        actual = res_map.get(mid)
        base = {'H': r['bH'], 'D': r['bD'], 'A': r['bA']}
        dixon = {'H': r['dH'], 'D': r['dD'], 'A': r['dA']}
        rows.append({
            'MatchID': mid,
            'MatchDate': info.get('MatchDate'),
            'HomeTeam': info.get('HomeTeam'),
            'AwayTeam': info.get('AwayTeam'),
            'ExpectedHomeGoals': round(float(r['xH']), 4),
            'ExpectedAwayGoals': round(float(r['xA']), 4),
            'Base_WinProb': base['H'], 'Base_DrawProb': base['D'], 'Base_LoseProb': base['A'],
            'Dixon_WinProb': dixon['H'], 'Dixon_DrawProb': dixon['D'], 'Dixon_LoseProb': dixon['A'],
            'Base_PredictedResult': _argmax_outcome(base['H'], base['D'], base['A']),
            'Dixon_PredictedResult': _argmax_outcome(dixon['H'], dixon['D'], dixon['A']),
            'ActualResult': actual,
            'Base_NLL': nll(base[actual]) if actual in OUTCOMES else float('nan'),
            'Dixon_NLL': nll(dixon[actual]) if actual in OUTCOMES else float('nan'),
        })
    return pd.DataFrame(rows)


def build_frames(res_map=None, bookie_nll_map=None):
    """Compute Dixon-Coles results for all base matchdays without writing anything.

    Returns (per_md: dict[md]->DataFrame, season: DataFrame, per_outcome: DataFrame).
    Reused by both this script's main() and build_dashboard_data.py.
    """
    if res_map is None:
        matches = agg.load_actual_results_by_matchday()
        res_map = dict(zip(matches['MatchID'].astype(int), matches['Result']))
    if bookie_nll_map is None:
        bdf = load_bookie_forecasts()
        bookie_nll_map = {
            int(r['MatchID']): nll({'H': r['p_H'], 'D': r['p_D'], 'A': r['p_A']}[res_map[int(r['MatchID'])]])
            for _, r in bdf.iterrows() if int(r['MatchID']) in res_map
        }

    per_md, season_rows, pooled = {}, [], []
    for md, folder in dce.base_matchday_dirs().items():
        tbl = per_md_table(folder, res_map)
        if tbl is None or tbl.empty:
            continue
        per_md[md] = tbl
        scored = tbl.dropna(subset=['ActualResult'])
        if scored.empty:
            continue
        bk = [bookie_nll_map[m] for m in scored['MatchID'].astype(int) if m in bookie_nll_map]
        for _, r in scored.iterrows():
            pooled.append({'Matchday': md, 'Outcome': r['ActualResult'],
                           'Base': r['Base_NLL'], 'Dixon': r['Dixon_NLL'],
                           'Bookie': bookie_nll_map.get(int(r['MatchID']))})
        base_nll, dixon_nll = scored['Base_NLL'].mean(), scored['Dixon_NLL'].mean()
        season_rows.append({
            'Matchday': md, 'N': len(scored),
            'BaseNLL': base_nll, 'DixonNLL': dixon_nll, 'Delta': dixon_nll - base_nll,
            'BaseAcc': (scored['Base_PredictedResult'] == scored['ActualResult']).mean(),
            'DixonAcc': (scored['Dixon_PredictedResult'] == scored['ActualResult']).mean(),
            'BookieNLL': (sum(bk) / len(bk)) if bk else float('nan'),
            'DixonGapVsBookie': (dixon_nll - (sum(bk) / len(bk))) if bk else float('nan'),
            'DixonImproves': bool(dixon_nll < base_nll),
        })

    season = pd.DataFrame(season_rows).sort_values('Matchday').reset_index(drop=True)

    # pooled per-outcome (the H/D/A guardrail) + ALL row
    pdf = pd.DataFrame(pooled)
    po_rows = []
    if not pdf.empty:
        for o in OUTCOMES:
            sub = pdf[pdf['Outcome'] == o]
            po_rows.append({'Outcome': o, 'N': len(sub),
                            'Base': sub['Base'].mean(), 'Dixon': sub['Dixon'].mean(),
                            'Bookie': sub['Bookie'].mean()})
        po_rows.append({'Outcome': 'ALL', 'N': len(pdf),
                        'Base': pdf['Base'].mean(), 'Dixon': pdf['Dixon'].mean(),
                        'Bookie': pdf['Bookie'].mean()})
    per_outcome = pd.DataFrame(po_rows)
    return per_md, season, per_outcome


def main():
    per_md, season, per_outcome = build_frames()
    n_written = 0
    for md, tbl in per_md.items():
        folder = BACKTEST_DIR / f'MD{md:02d}'
        tbl.to_csv(folder / PER_MD_NAME, index=False)
        n_written += 1
    season.to_csv(BACKTEST_DIR / SEASON_NAME, index=False)

    print(f'Dixon-Coles (scale {PARAMS["scale"]}, rho {PARAMS["rho"]}, '
          f'max_goals {PARAMS["max_goals"]}, alpha {PARAMS["alpha"]})')
    print(f'  wrote {n_written} per-matchday {PER_MD_NAME} files')
    print(f'  wrote season aggregate -> {SEASON_NAME}')
    if not season.empty:
        improved = int(season['DixonImproves'].sum())
        print(f'  matchdays improved by Dixon: {improved}/{len(season)}  '
              f'(mean delta {season["Delta"].mean():+.4f})')
    if not per_outcome.empty:
        allr = per_outcome[per_outcome['Outcome'] == 'ALL'].iloc[0]
        print(f'  pooled NLL  base {allr["Base"]:.4f} -> dixon {allr["Dixon"]:.4f} '
              f'(bookie {allr["Bookie"]:.4f})')


if __name__ == '__main__':
    main()
