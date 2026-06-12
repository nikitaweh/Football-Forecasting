"""
analyze_backtest_results.py - aggregate per-matchday backtest outputs into a
season-level summary and diagnostic report.

Reads every Datacollection backtest/MD{N}/ produced by backtest_matchdays.py
and produces:
  - Per-matchday performance table (best/mean NLL, accuracy, bookmaker baseline)
  - Hardest matchdays (bottom decile by best NLL) for investigation
  - Weight stability across each matchday's best run (which weights converge
    consistently vs. which jump around per matchday)
  - Surrogate calibration when Pred_AvgNLL is populated (Pearson per matchday)

Outputs:
  - Datacollection backtest/season_summary.csv (CSV with one row per matchday)
  - Printed text report on stdout

Usage:
    python analyze_backtest_results.py
"""

import math
from pathlib import Path

import pandas as pd

SEASON = 2025

TESTRUNS_PATH = Path(r'C:/AI Projekt/KI-Projekt/Sports Api Data/Testruns')
DATA_PATH = Path(r'C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection')
BACKTEST_DIR = TESTRUNS_PATH / 'Datacollection backtest'
STAMMDATEN_PATH = DATA_PATH / 'Stammdaten_78.csv'
STATS_PATH = DATA_PATH / 'match_statistics_filtered_78.csv'
ODDS_DIR = TESTRUNS_PATH / 'BWIN Odds' / 'Datacollection'
SUMMARY_OUT_PATH = BACKTEST_DIR / 'season_summary.csv'

# Naive priors used only as a last-resort fallback when bookmaker odds are
# missing for a match. Real bookmaker odds are loaded per match from ODDS_DIR.
NAIVE_PRIOR = {'H': 0.45, 'D': 0.25, 'A': 0.30}


def load_actual_results_by_matchday():
    """Return a DataFrame of all played, stats-covered matches: MatchID, MD, Result."""
    sd = pd.read_csv(STAMMDATEN_PATH, parse_dates=['Date'])
    sd = sd[(sd['Season'] == SEASON) & (sd['Gespielt'] == True)].copy()
    # Some entries (e.g. "Final") have no matchday number — drop them.
    sd['MD'] = pd.to_numeric(sd['Matchday'].str.extract(r'(\d+)')[0], errors='coerce')
    sd = sd.dropna(subset=['MD']).copy()
    sd['MD'] = sd['MD'].astype(int)
    ms = pd.read_csv(STATS_PATH)
    merged = sd.merge(ms[['MatchID', 'Home Goals', 'Away Goals']], on='MatchID', how='inner')
    merged['Result'] = merged.apply(
        lambda r: 'H' if r['Home Goals'] > r['Away Goals']
        else ('A' if r['Home Goals'] < r['Away Goals'] else 'D'),
        axis=1,
    )
    return merged[['MatchID', 'MD', 'Result']]


def load_bookmaker_match_nll():
    """Return {MatchID: bookie_match_nll} using the most recent BWIN odds file.

    Decimal odds are inverted, normalised to remove the bookmaker's overround,
    then converted to NLL on the actual result. If no odds file exists, returns
    an empty dict and the caller falls back to NAIVE_PRIOR per match.
    """
    if not ODDS_DIR.exists():
        return {}, None
    candidates = sorted(ODDS_DIR.glob('bwin_historical_odds_*.csv'))
    if not candidates:
        return {}, None
    latest = candidates[-1]  # filenames are timestamp-sortable
    df = pd.read_csv(latest)
    needed = {'match_id', 'odd_home_win_1', 'odd_draw_x', 'odd_away_win_2', 'result'}
    if not needed.issubset(df.columns):
        return {}, latest

    df = df.dropna(subset=['match_id', 'odd_home_win_1', 'odd_draw_x', 'odd_away_win_2', 'result']).copy()
    p_h = 1.0 / df['odd_home_win_1']
    p_d = 1.0 / df['odd_draw_x']
    p_a = 1.0 / df['odd_away_win_2']
    z = p_h + p_d + p_a  # overround
    p_h, p_d, p_a = p_h / z, p_d / z, p_a / z

    def nll_for_actual(row, ph, pd_, pa):
        r = row['result']
        if r == 'H': p = ph
        elif r == 'D': p = pd_
        elif r == 'A': p = pa
        else: return float('nan')
        return -math.log(max(float(p), 1e-12))

    df['MatchNLL_Bookie'] = [
        nll_for_actual(row, p_h.iloc[i], p_d.iloc[i], p_a.iloc[i])
        for i, row in enumerate(df.to_dict('records'))
    ]
    out = dict(zip(df['match_id'].astype(int), df['MatchNLL_Bookie']))
    return out, latest


def naive_match_nll(result):
    p = NAIVE_PRIOR.get(result)
    if p is None:
        return float('nan')
    return -math.log(p)


def matchday_bookie_baseline(match_ids, results, bookie_nll_map):
    """Mean per-match NLL using bookie odds where available, naive prior otherwise.

    Returns (mean_nll, num_with_odds, num_fallback).
    """
    per_match = []
    with_odds = 0
    fallback = 0
    for mid, res in zip(match_ids, results):
        v = bookie_nll_map.get(int(mid))
        if v is not None and not math.isnan(v):
            per_match.append(v)
            with_odds += 1
        else:
            per_match.append(naive_match_nll(res))
            fallback += 1
    valid = [v for v in per_match if not math.isnan(v)]
    if not valid:
        return float('nan'), with_odds, fallback
    return sum(valid) / len(valid), with_odds, fallback


def fmt(x, digits=4):
    if pd.isna(x):
        return 'NaN'
    return f'{x:.{digits}f}'


def main():
    if not BACKTEST_DIR.exists():
        print(f'No backtest folder found at {BACKTEST_DIR}. Run backtest_matchdays.py first.')
        return

    md_dirs = sorted([p for p in BACKTEST_DIR.iterdir() if p.is_dir() and p.name.startswith('MD')])
    if not md_dirs:
        print('No matchday subfolders found.')
        return

    matches_df = load_actual_results_by_matchday()
    bookie_nll_map, odds_source = load_bookmaker_match_nll()
    if odds_source:
        print(f'Using bookmaker odds from: {odds_source.name}')
        print(f'  Coverage: {len(bookie_nll_map)} matches with odds')
    else:
        print('No bookmaker odds file found; falling back to naive priors for every match.')
    print(f'Found {len(md_dirs)} backtested matchday folder(s).\n')

    summary_rows = []
    best_weight_rows = []
    surrogate_rows = []
    per_match_comparison_frames = []

    for md_dir in md_dirs:
        summary_path = md_dir / 'prediction_weight_run_summary.csv'
        runs_path = md_dir / 'prediction_weight_runs.csv'
        ensemble_path = md_dir / 'future_outcome_table_ensemble.csv'
        if not summary_path.exists():
            print(f'  {md_dir.name}: no summary file, skipping.')
            continue
        try:
            md_num = int(md_dir.name.replace('MD', ''))
        except ValueError:
            print(f'  {md_dir.name}: cannot parse matchday number, skipping.')
            continue

        summary = pd.read_csv(summary_path)
        if summary.empty:
            continue

        md_matches = matches_df[matches_df['MD'] == md_num]
        match_ids = md_matches['MatchID'].tolist()
        results = md_matches['Result'].tolist()
        result_by_match = dict(zip(md_matches['MatchID'].astype(int), md_matches['Result']))
        bookie_baseline, n_with_odds, n_fallback = matchday_bookie_baseline(
            match_ids, results, bookie_nll_map
        )

        avg_nll = pd.to_numeric(summary.get('AvgNLL'), errors='coerce') if 'AvgNLL' in summary.columns else pd.Series([], dtype=float)
        accuracy = pd.to_numeric(summary.get('Accuracy'), errors='coerce') if 'Accuracy' in summary.columns else pd.Series([], dtype=float)

        best_nll = avg_nll.min(skipna=True)
        mean_nll = avg_nll.mean(skipna=True)
        best_acc = accuracy.max(skipna=True)
        mean_acc = accuracy.mean(skipna=True)
        gap_vs_bookie = (best_nll - bookie_baseline) if pd.notna(best_nll) and pd.notna(bookie_baseline) else float('nan')
        beats_bookie = (best_nll < bookie_baseline) if pd.notna(best_nll) and pd.notna(bookie_baseline) else None

        # Per-match comparison: best run's per-match NLL vs bookie per-match NLL
        matches_beat = matches_total = None
        if runs_path.exists() and avg_nll.notna().any():
            best_run_id = summary.loc[avg_nll.idxmin(), 'RunID']
            runs = pd.read_csv(runs_path)
            if 'RunID' in runs.columns and 'MatchID' in runs.columns and 'MatchNLL' in runs.columns:
                best_run_matches = runs[runs['RunID'] == best_run_id][['MatchID', 'MatchNLL']].copy()
                best_run_matches['MatchID'] = pd.to_numeric(best_run_matches['MatchID'], errors='coerce').astype('Int64')
                best_run_matches['MatchNLL_Bookie'] = best_run_matches['MatchID'].map(
                    {int(k): v for k, v in bookie_nll_map.items()}
                )
                best_run_matches['MD'] = md_num
                cmp = best_run_matches.dropna(subset=['MatchNLL', 'MatchNLL_Bookie']).copy()
                if not cmp.empty:
                    cmp['ModelBeatsBookie'] = cmp['MatchNLL'] < cmp['MatchNLL_Bookie']
                    matches_beat = int(cmp['ModelBeatsBookie'].sum())
                    matches_total = int(len(cmp))
                    per_match_comparison_frames.append(cmp)

        # Top-K ensemble metrics: read the ensemble outcome table and score it
        # against actuals the same way the single-pick NLL is computed.
        ensemble_nll = ensemble_acc = float('nan')
        ensemble_size = None
        ensemble_matches_beat_bookie = ensemble_matches_compared = None
        if ensemble_path.exists():
            try:
                ensemble_df = pd.read_csv(ensemble_path)
            except pd.errors.EmptyDataError:
                ensemble_df = pd.DataFrame()
            needed = {'MatchID', 'WinProb', 'DrawProb', 'LoseProb'}
            if not ensemble_df.empty and needed.issubset(ensemble_df.columns):
                ensemble_df['MatchID'] = pd.to_numeric(ensemble_df['MatchID'], errors='coerce').astype('Int64')
                ensemble_df['ActualResult'] = ensemble_df['MatchID'].map(result_by_match)
                # Per-match NLL using ensemble probabilities.
                def _ens_nll(row):
                    r = row.get('ActualResult')
                    if r == 'H': p = row.get('WinProb')
                    elif r == 'D': p = row.get('DrawProb')
                    elif r == 'A': p = row.get('LoseProb')
                    else: return float('nan')
                    try:
                        return -math.log(max(float(p), 1e-12))
                    except (TypeError, ValueError):
                        return float('nan')
                ensemble_df['MatchNLL'] = ensemble_df.apply(_ens_nll, axis=1)
                if 'PredictedResult' in ensemble_df.columns:
                    correct = (ensemble_df['PredictedResult'] == ensemble_df['ActualResult']) & ensemble_df['ActualResult'].notna()
                    scored = ensemble_df.loc[ensemble_df['ActualResult'].notna()]
                    if not scored.empty:
                        ensemble_acc = float(correct.loc[scored.index].mean())
                valid_nll = ensemble_df['MatchNLL'].dropna()
                if not valid_nll.empty:
                    ensemble_nll = float(valid_nll.mean())
                if 'EnsembleSize' in ensemble_df.columns and ensemble_df['EnsembleSize'].notna().any():
                    ensemble_size = int(ensemble_df['EnsembleSize'].iloc[0])
                # Per-match comparison vs bookie for the ensemble.
                ensemble_df['MatchNLL_Bookie'] = ensemble_df['MatchID'].map(
                    {int(k): v for k, v in bookie_nll_map.items()}
                )
                ens_cmp = ensemble_df.dropna(subset=['MatchNLL', 'MatchNLL_Bookie'])
                if not ens_cmp.empty:
                    ensemble_matches_beat_bookie = int((ens_cmp['MatchNLL'] < ens_cmp['MatchNLL_Bookie']).sum())
                    ensemble_matches_compared = int(len(ens_cmp))
        ensemble_gap_vs_bookie = (
            ensemble_nll - bookie_baseline
            if pd.notna(ensemble_nll) and pd.notna(bookie_baseline) else float('nan')
        )
        ensemble_beats_bookie = (
            ensemble_nll < bookie_baseline
            if pd.notna(ensemble_nll) and pd.notna(bookie_baseline) else None
        )

        summary_rows.append({
            'Matchday': md_num,
            'NumFixtures': len(results),
            'ResultMix': f"H{results.count('H')}/D{results.count('D')}/A{results.count('A')}",
            'BookieNLL': bookie_baseline,
            'BookieOddsCoverage': f'{n_with_odds}/{n_with_odds + n_fallback}',
            'BestNLL': best_nll,
            'MeanNLL': mean_nll,
            'BestAcc': best_acc,
            'MeanAcc': mean_acc,
            'GapVsBookie': gap_vs_bookie,
            'BeatsBookie': beats_bookie,
            'MatchesBeatingBookie': matches_beat,
            'MatchesCompared': matches_total,
            'EnsembleSize': ensemble_size,
            'EnsembleNLL': ensemble_nll,
            'EnsembleAcc': ensemble_acc,
            'EnsembleGapVsBookie': ensemble_gap_vs_bookie,
            'EnsembleBeatsBookie': ensemble_beats_bookie,
            'EnsembleMatchesBeatingBookie': ensemble_matches_beat_bookie,
            'EnsembleMatchesCompared': ensemble_matches_compared,
            'NumRuns': len(summary),
        })

        # Weights from the best-NLL run of this matchday (for stability analysis)
        if avg_nll.notna().any():
            best_idx = avg_nll.idxmin()
            row = summary.loc[best_idx]
            weight_cols = [c for c in summary.columns if c.startswith('Weight_')]
            entry = {'Matchday': md_num}
            for c in weight_cols:
                entry[c] = pd.to_numeric(row.get(c), errors='coerce')
            best_weight_rows.append(entry)

        # Surrogate calibration: correlation between Pred_AvgNLL and actual AvgNLL within this matchday
        if 'Pred_AvgNLL' in summary.columns:
            pred = pd.to_numeric(summary['Pred_AvgNLL'], errors='coerce')
            sub = pd.concat([avg_nll, pred], axis=1).dropna()
            if len(sub) >= 5:
                corr = sub.iloc[:, 0].corr(sub.iloc[:, 1])
                surrogate_rows.append({
                    'Matchday': md_num,
                    'NumRuns': len(sub),
                    'Pearson_PredVsActual_NLL': corr,
                })

    if not summary_rows:
        print('No usable matchday data found.')
        return

    season = pd.DataFrame(summary_rows).sort_values('Matchday').reset_index(drop=True)
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    season.to_csv(SUMMARY_OUT_PATH, index=False)

    print('=' * 86)
    print('PER-MATCHDAY SUMMARY (model best run vs real BWIN bookmaker)')
    print('=' * 86)
    display_cols = ['Matchday', 'ResultMix', 'BookieNLL', 'BestNLL', 'GapVsBookie', 'BestAcc', 'MatchesBeatingBookie', 'MatchesCompared', 'BeatsBookie']
    display = season[display_cols].copy()
    for c in ['BookieNLL', 'BestNLL', 'GapVsBookie', 'BestAcc']:
        display[c] = display[c].apply(fmt)
    print(display.to_string(index=False))

    beats_mask = season['BeatsBookie'].fillna(False)
    print(f"\nMatchdays where best run beats bookmaker: {int(beats_mask.sum())} / {len(season)}")
    if season['BestNLL'].notna().any():
        print(f"Mean best-NLL across matchdays: {season['BestNLL'].mean():.4f}")
        print(f"Mean bookie NLL across matchdays: {season['BookieNLL'].mean():.4f}")
        print(f"Mean gap (model - bookie): {season['GapVsBookie'].mean():+.4f}  (negative = model better)")

    if per_match_comparison_frames:
        all_cmp = pd.concat(per_match_comparison_frames, ignore_index=True)
        total = len(all_cmp)
        wins = int(all_cmp['ModelBeatsBookie'].sum())
        diff = (all_cmp['MatchNLL'] - all_cmp['MatchNLL_Bookie'])
        print(f"\n=== Per-match head-to-head across all backtested matchdays ===")
        print(f"  Matches compared: {total}")
        print(f"  Best-run model beats bookmaker: {wins} / {total} = {wins/total:.1%}")
        print(f"  Mean model NLL:  {all_cmp['MatchNLL'].mean():.4f}")
        print(f"  Mean bookie NLL: {all_cmp['MatchNLL_Bookie'].mean():.4f}")
        print(f"  Mean per-match gap (model - bookie): {diff.mean():+.4f}")
        print(f"  Median per-match gap:                {diff.median():+.4f}")

    # Top-K ensemble vs single-pick comparison.
    if season['EnsembleNLL'].notna().any():
        ens_cols = ['Matchday', 'EnsembleSize', 'BestNLL', 'EnsembleNLL',
                    'EnsembleGapVsBookie', 'EnsembleAcc',
                    'EnsembleMatchesBeatingBookie', 'EnsembleMatchesCompared',
                    'EnsembleBeatsBookie']
        ens_display = season[ens_cols].copy()
        for c in ['BestNLL', 'EnsembleNLL', 'EnsembleGapVsBookie', 'EnsembleAcc']:
            ens_display[c] = ens_display[c].apply(fmt)
        print('\n=== Top-K ensemble vs single-pick (per matchday) ===')
        print(ens_display.to_string(index=False))

        valid_pairs = season.dropna(subset=['BestNLL', 'EnsembleNLL'])
        if not valid_pairs.empty:
            ens_wins = int((valid_pairs['EnsembleNLL'] < valid_pairs['BestNLL']).sum())
            mean_top1 = valid_pairs['BestNLL'].mean()
            mean_ens = valid_pairs['EnsembleNLL'].mean()
            print(f"\n  Matchdays where ensemble beats single-pick: {ens_wins} / {len(valid_pairs)}")
            print(f"  Mean single-pick NLL: {mean_top1:.4f}")
            print(f"  Mean ensemble NLL:    {mean_ens:.4f}")
            print(f"  Mean difference (ensemble - single-pick): {mean_ens - mean_top1:+.4f}  (negative = ensemble better)")
            print(f"  Mean ensemble gap vs bookie: {valid_pairs['EnsembleGapVsBookie'].mean():+.4f}")

    if len(season) >= 5:
        decile_size = max(1, len(season) // 10)
        hardest = season.nlargest(decile_size, 'BestNLL')
        print(f'\n=== Hardest matchday(s): worst best-NLL ({decile_size} of {len(season)}) ===')
        hd = hardest[display_cols].copy()
        for c in ['BookieNLL', 'BestNLL', 'GapVsBookie', 'BestAcc']:
            hd[c] = hd[c].apply(fmt)
        print(hd.to_string(index=False))

    # Weight stability across best runs
    if best_weight_rows:
        wb = pd.DataFrame(best_weight_rows).set_index('Matchday')
        weight_cols = [c for c in wb.columns if c.startswith('Weight_')]
        if weight_cols and len(wb) >= 2:
            rows = []
            for c in weight_cols:
                mean_v = wb[c].mean(skipna=True)
                std_v = wb[c].std(skipna=True)
                cv = (std_v / abs(mean_v)) if abs(mean_v) > 1e-9 else float('nan')
                rows.append({'Weight': c.replace('Weight_', ''), 'Mean': mean_v, 'Std': std_v, 'CV': cv})
            stab = pd.DataFrame(rows).sort_values('Std')
            print('\n=== Weight stability across matchdays (best-run weights) ===')
            print('Low Std = consistent across matchdays (robust signal).')
            print('High Std = matchday-dependent (possibly overfitting noise).\n')
            print('Most stable (top 10):')
            top = stab.head(10).copy()
            for c in ['Mean', 'Std', 'CV']:
                top[c] = top[c].apply(fmt)
            print(top.to_string(index=False))
            if len(stab) > 10:
                print('\nMost variable (bottom 10):')
                bot = stab.tail(10).copy()
                for c in ['Mean', 'Std', 'CV']:
                    bot[c] = bot[c].apply(fmt)
                print(bot.to_string(index=False))

    if surrogate_rows:
        sc = pd.DataFrame(surrogate_rows).sort_values('Matchday')
        print('\n=== Surrogate calibration (per-matchday) ===')
        print('Pearson r of Pred_AvgNLL vs actual AvgNLL within each matchday.')
        print('Positive = surrogate ranks correctly; near zero/negative = surrogate misleading.\n')
        out = sc.copy()
        out['Pearson_PredVsActual_NLL'] = out['Pearson_PredVsActual_NLL'].apply(fmt)
        print(out.to_string(index=False))
        valid = sc['Pearson_PredVsActual_NLL'].dropna()
        if not valid.empty:
            print(f'\nMean correlation across matchdays: {valid.mean():.3f}')
            print(f'Matchdays with positive correlation: {int((valid > 0).sum())} / {len(valid)}')
    else:
        print('\n=== Surrogate calibration ===')
        print('No matchdays had populated Pred_AvgNLL (surrogate inactive across all backtests).')

    print(f'\nSeason summary CSV written to: {SUMMARY_OUT_PATH}')


if __name__ == '__main__':
    main()
