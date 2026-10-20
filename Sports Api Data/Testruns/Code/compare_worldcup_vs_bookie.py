"""
compare_worldcup_vs_bookie.py - compare the International model's variants vs bet365
on the played World Cup 2026 matches.

Joins international_competitive_predictions.csv to the bet365 World Cup odds file
on MatchID, recomputes each outcome-probability variant post-hoc from the saved
expected goals + base probs, and scores per-outcome (H/D/A) NLL + total against
actual results and the bookmaker.

Usage:
    python compare_worldcup_vs_bookie.py
"""

import glob
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_backtest_results as agg
from diagnose_draws import nll
from compare_models_vs_bookie import variants_for_row
import os

# Repo root: KI_PROJECT_ROOT if set (VPS), else derived from this file's location.
PROJECT_ROOT = Path(os.environ.get("KI_PROJECT_ROOT") or Path(__file__).resolve().parents[3]).as_posix()


ROOT = Path(rf'{PROJECT_ROOT}')
PRED = ROOT / 'Sports Api Data' / 'International' / 'Model Output' / 'competitive' / 'international_competitive_validation.csv'
ODDS_DIR = ROOT / 'Sports Api Data' / 'Testruns' / 'BWIN Odds' / 'Datacollection'
OUTCOMES = ['H', 'D', 'A']
VARIANTS = ['base', 'dixon_full_a1.0', 'dixon_full_a0.4', 'dixon_draw_ratio', 'poisson_draw_ratio']


def latest_worldcup_odds():
    files = sorted(glob.glob(str(ODDS_DIR / 'worldcup_odds_*.csv')))
    return files[-1] if files else None


def main():
    odds_path = latest_worldcup_odds()
    if not odds_path:
        print('No worldcup odds file found.')
        return
    odds = pd.read_csv(odds_path)
    odds.columns = [c.lstrip('﻿') for c in odds.columns]
    odds = odds.dropna(subset=['match_id', 'odd_home_win_1', 'odd_draw_x', 'odd_away_win_2', 'result'])
    odds['match_id'] = pd.to_numeric(odds['match_id'], errors='coerce').astype('Int64')

    pred = pd.read_csv(PRED)
    pred['MatchID'] = pd.to_numeric(pred['MatchID'], errors='coerce').astype('Int64')

    df = odds.merge(pred, left_on='match_id', right_on='MatchID', how='inner')
    n = len(df)
    if n == 0:
        print('No World Cup matches matched between predictions and odds (by MatchID).')
        print(f'  odds matches: {len(odds)} | prediction rows: {len(pred)}')
        return

    mix = df['result'].tolist()
    print('=' * 92)
    print(f'WORLD CUP 2026 — International model variants vs bet365  ({n} played matches)')
    print(f'Result mix: H{mix.count("H")}/D{mix.count("D")}/A{mix.count("A")}  ({odds_path.split(chr(92))[-1]})')
    print('=' * 92)

    pooled = {v: {o: [] for o in OUTCOMES} for v in VARIANTS}
    pooled_all = {v: [] for v in VARIANTS}
    bk = {o: [] for o in OUTCOMES}
    bk_all = []

    for _, r in df.iterrows():
        actual = r['result']
        if actual not in OUTCOMES:
            continue
        # model variants
        vs = variants_for_row(float(r['WinProb']), float(r['DrawProb']), float(r['LoseProb']),
                              float(r['ExpectedHomeGoals']), float(r['ExpectedAwayGoals']))
        for v in VARIANTS:
            if v in vs:
                p = {'H': vs[v][0], 'D': vs[v][1], 'A': vs[v][2]}[actual]
                pooled[v][actual].append(nll(p)); pooled_all[v].append(nll(p))
        # bookie (normalised)
        ph, pd_, pa = 1.0 / r['odd_home_win_1'], 1.0 / r['odd_draw_x'], 1.0 / r['odd_away_win_2']
        z = ph + pd_ + pa
        bp = {'H': ph / z, 'D': pd_ / z, 'A': pa / z}[actual]
        bk[actual].append(nll(bp)); bk_all.append(nll(bp))

    def mean(x): return sum(x) / len(x) if x else float('nan')

    hdr = f'{"Model":22} {"H":>8} {"D":>8} {"A":>8} {"TOTAL":>8} {"vsBookie":>9}'
    print(hdr); print('-' * len(hdr))
    bookie_all = mean(bk_all)
    for v in VARIANTS:
        H, D, A, T = mean(pooled[v]['H']), mean(pooled[v]['D']), mean(pooled[v]['A']), mean(pooled_all[v])
        print(f'{v:22} {agg.fmt(H):>8} {agg.fmt(D):>8} {agg.fmt(A):>8} {agg.fmt(T):>8} {T-bookie_all:>+9.4f}')
    print(f'{"bet365 bookie":22} {agg.fmt(mean(bk["H"])):>8} {agg.fmt(mean(bk["D"])):>8} '
          f'{agg.fmt(mean(bk["A"])):>8} {agg.fmt(bookie_all):>8} {0.0:>+9.4f}')
    print(f'\nMatches: H{len(pooled["base"]["H"])}/D{len(pooled["base"]["D"])}/A{len(pooled["base"]["A"])}  '
          f'(small N — exploratory).')


if __name__ == '__main__':
    main()
