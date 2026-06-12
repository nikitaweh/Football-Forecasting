"""
diagnose_ranker_signals.py - read-only diagnostic over the existing backtest.

Answers one question before we touch any ranker code: of the signals available
to the future-mode ranker BEFORE kickoff (the surrogate Pred_AvgNLL and the
confidence proxies MeanTopProb / MeanProbGap / MeanEntropy), does any of them
correlate with the true BART-scored AvgNLL well enough to pick a good weight
combination? And if used to pick, would it land closer to the hindsight-best
(ceiling) than a random pick (floor)?

Three analyses, all on the existing Datacollection backtest/MD{N}/ summaries:
  1. Signal calibration  - Spearman/Pearson of each signal vs actual AvgNLL/Accuracy.
  2. Floor vs ceiling     - BookieNLL / MeanNLL (floor) / BestNLL (ceiling) per matchday.
  3. Simulated pick       - what each ranking strategy WOULD pick, scored on actuals.

No pipeline changes, no new backtest runs. Reuses helpers from
analyze_backtest_results.py.

Usage:
    python diagnose_ranker_signals.py
"""

import sys
from pathlib import Path

import pandas as pd

# Reuse the aggregator's data-loading + formatting helpers.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_backtest_results as agg

BACKTEST_DIR = agg.BACKTEST_DIR
OUT_PATH = BACKTEST_DIR / 'ranker_signal_diagnostic.csv'

# Signals the future-mode ranker can see before kickoff, and the sign of the
# correlation-with-AvgNLL we'd expect if the signal is calibrated. +1 means
# "higher signal should mean higher (worse) NLL"; -1 means "higher signal should
# mean lower (better) NLL". 'pick' is the direction that selects the best run.
SIGNALS = {
    'Pred_AvgNLL': {'expect_sign_vs_nll': +1, 'pick': 'min'},   # surrogate: predicts NLL directly
    'MeanTopProb': {'expect_sign_vs_nll': -1, 'pick': 'max'},   # more confident -> expect lower NLL
    'MeanProbGap': {'expect_sign_vs_nll': -1, 'pick': 'max'},   # bigger top-2 gap -> expect lower NLL
    'MeanEntropy': {'expect_sign_vs_nll': +1, 'pick': 'min'},   # higher entropy -> expect higher NLL
}


def matchday_dirs():
    if not BACKTEST_DIR.exists():
        return []
    out = []
    for d in sorted(BACKTEST_DIR.iterdir()):
        if d.is_dir() and d.name.startswith('MD') and not d.name.startswith('_'):
            out.append(d)
    return out


def corr_pair(x, y, method):
    """Correlation of two Series, NaN-safe; needs >=5 varying pairs."""
    sub = pd.concat([x, y], axis=1).dropna()
    if len(sub) < 5:
        return float('nan')
    a, b = sub.iloc[:, 0], sub.iloc[:, 1]
    if a.nunique() < 2 or b.nunique() < 2:
        return float('nan')
    return a.corr(b, method=method)


def load_matchday_summaries(dirs):
    """Return {md_num: summary_df} for folders that have a non-empty summary."""
    out = {}
    for d in dirs:
        sp = d / 'prediction_weight_run_summary.csv'
        if not sp.exists():
            continue
        try:
            df = pd.read_csv(sp)
        except pd.errors.EmptyDataError:
            continue
        if df.empty or 'AvgNLL' not in df.columns:
            continue
        try:
            md = int(d.name.replace('MD', ''))
        except ValueError:
            continue
        for c in ['AvgNLL', 'Accuracy'] + list(SIGNALS):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        out[md] = df
    return dict(sorted(out.items()))


def analysis_calibration(summaries):
    """Per-matchday correlation of each signal vs actual AvgNLL and Accuracy."""
    rows = []
    for md, df in summaries.items():
        nll = df['AvgNLL']
        acc = df['Accuracy'] if 'Accuracy' in df.columns else pd.Series(dtype=float)
        for sig, cfg in SIGNALS.items():
            if sig not in df.columns:
                continue
            s = df[sig]
            sp_nll = corr_pair(s, nll, 'spearman')
            pe_nll = corr_pair(s, nll, 'pearson')
            sp_acc = corr_pair(s, acc, 'spearman') if not acc.empty else float('nan')
            # Aligned: positive => calibrated in the useful direction.
            aligned = sp_nll * cfg['expect_sign_vs_nll'] if pd.notna(sp_nll) else float('nan')
            rows.append({
                'Matchday': md, 'Signal': sig, 'NumRuns': int(s.notna().sum()),
                'Spearman_vs_NLL': sp_nll, 'Pearson_vs_NLL': pe_nll,
                'Spearman_vs_Acc': sp_acc, 'Aligned_Spearman': aligned,
            })
    return pd.DataFrame(rows)


def analysis_floor_ceiling(summaries, bookie_map, results_by_md):
    rows = []
    for md, df in summaries.items():
        nll = df['AvgNLL'].dropna()
        if nll.empty:
            continue
        md_matches = results_by_md[results_by_md['MD'] == md]
        bookie, n_odds, n_fb = agg.matchday_bookie_baseline(
            md_matches['MatchID'].tolist(), md_matches['Result'].tolist(), bookie_map
        )
        floor = float(nll.mean())   # random pick (broken ranker)
        ceiling = float(nll.min())  # hindsight best
        rows.append({
            'Matchday': md, 'NumRuns': int(nll.count()),
            'BookieNLL': bookie, 'FloorNLL_Mean': floor, 'CeilingNLL_Best': ceiling,
            'Floor_vs_Bookie': floor - bookie, 'Ceiling_vs_Bookie': ceiling - bookie,
            'Floor_to_Ceiling_Gap': floor - ceiling,
        })
    return pd.DataFrame(rows)


def analysis_simulated_pick(summaries):
    """For each strategy, the actual AvgNLL of the run it would pick per matchday."""
    strat_rows = []
    detail_rows = []
    for md, df in summaries.items():
        valid = df.dropna(subset=['AvgNLL'])
        if valid.empty:
            continue
        floor = float(valid['AvgNLL'].mean())
        ceiling = float(valid['AvgNLL'].min())
        gap = floor - ceiling
        detail = {'Matchday': md, 'FloorNLL': floor, 'CeilingNLL': ceiling}

        # Individual signals.
        strategies = {}
        for sig, cfg in SIGNALS.items():
            if sig not in valid.columns or valid[sig].notna().sum() < 2:
                strategies[sig] = float('nan')
                continue
            sub = valid.dropna(subset=[sig])
            idx = sub[sig].idxmin() if cfg['pick'] == 'min' else sub[sig].idxmax()
            strategies[sig] = float(sub.loc[idx, 'AvgNLL'])

        # Confidence blend: average rank across the three proxies (best=rank 1).
        proxies = ['MeanTopProb', 'MeanProbGap', 'MeanEntropy']
        if all(p in valid.columns and valid[p].notna().sum() >= 2 for p in proxies):
            sub = valid.dropna(subset=proxies).copy()
            rank_sum = pd.Series(0.0, index=sub.index)
            for p in proxies:
                asc = (SIGNALS[p]['pick'] == 'min')  # ascending rank if lower is better
                rank_sum = rank_sum + sub[p].rank(ascending=asc)
            best_idx = rank_sum.idxmin()
            strategies['ConfidenceBlend'] = float(sub.loc[best_idx, 'AvgNLL'])
        else:
            strategies['ConfidenceBlend'] = float('nan')

        for name, picked in strategies.items():
            capture = (floor - picked) / gap if (gap > 1e-9 and pd.notna(picked)) else float('nan')
            strat_rows.append({
                'Matchday': md, 'Strategy': name, 'PickedNLL': picked,
                'vs_Floor': (picked - floor) if pd.notna(picked) else float('nan'),
                'GapCaptured': capture,
            })
            detail[name] = picked
        detail_rows.append(detail)
    return pd.DataFrame(strat_rows), pd.DataFrame(detail_rows)


def main():
    dirs = matchday_dirs()
    summaries = load_matchday_summaries(dirs)
    if not summaries:
        print('No usable matchday summaries found.')
        return
    bookie_map, odds_file = agg.load_bookmaker_match_nll()
    results_by_md = agg.load_actual_results_by_matchday()

    print('=' * 88)
    print(f'RANKER-SIGNAL DIAGNOSTIC  ({len(summaries)} matchdays: {list(summaries)})')
    if odds_file is not None:
        print(f'Bookmaker odds: {odds_file.name}')
    print('=' * 88)

    # ---- Analysis 1: signal calibration ----
    cal = analysis_calibration(summaries)
    print('\n=== 1. SIGNAL CALIBRATION (per matchday, vs actual AvgNLL) ===')
    print('Spearman is the headline (ranking is ordinal). Aligned_Spearman > 0 means')
    print('the signal is calibrated in the useful direction; ~0 means noise.\n')
    show = cal.copy()
    for c in ['Spearman_vs_NLL', 'Pearson_vs_NLL', 'Spearman_vs_Acc', 'Aligned_Spearman']:
        show[c] = show[c].apply(agg.fmt)
    print(show.to_string(index=False))

    print('\n--- Calibration summary (mean across matchdays) ---')
    agg_rows = []
    for sig in SIGNALS:
        sub = cal[cal['Signal'] == sig]
        if sub.empty:
            continue
        aligned = sub['Aligned_Spearman']
        agg_rows.append({
            'Signal': sig,
            'Mean_Aligned_Spearman': aligned.mean(skipna=True),
            'Mean_Spearman_vs_NLL': sub['Spearman_vs_NLL'].mean(skipna=True),
            'Calibrated_MDs': f"{int((aligned > 0).sum())}/{int(aligned.notna().sum())}",
        })
    cal_summary = pd.DataFrame(agg_rows)
    disp = cal_summary.copy()
    for c in ['Mean_Aligned_Spearman', 'Mean_Spearman_vs_NLL']:
        disp[c] = disp[c].apply(agg.fmt)
    print(disp.to_string(index=False))

    # ---- Analysis 2: floor vs ceiling ----
    fc = analysis_floor_ceiling(summaries, bookie_map, results_by_md)
    print('\n=== 2. FLOOR vs CEILING (deployable vs hindsight) ===')
    print('Floor = mean run NLL (what a random/r~=0 ranker delivers).')
    print('Ceiling = best run NLL (hindsight). The ranker competes for the gap between them.\n')
    disp = fc.copy()
    for c in ['BookieNLL', 'FloorNLL_Mean', 'CeilingNLL_Best',
              'Floor_vs_Bookie', 'Ceiling_vs_Bookie', 'Floor_to_Ceiling_Gap']:
        disp[c] = disp[c].apply(agg.fmt)
    print(disp.to_string(index=False))
    if not fc.empty:
        print(f"\n  Mean BookieNLL : {fc['BookieNLL'].mean():.4f}")
        print(f"  Mean Floor     : {fc['FloorNLL_Mean'].mean():.4f}  "
              f"(vs bookie {fc['Floor_vs_Bookie'].mean():+.4f})")
        print(f"  Mean Ceiling   : {fc['CeilingNLL_Best'].mean():.4f}  "
              f"(vs bookie {fc['Ceiling_vs_Bookie'].mean():+.4f})")
        print(f"  Mean floor->ceiling gap the ranker is chasing: {fc['Floor_to_Ceiling_Gap'].mean():.4f}")

    # ---- Analysis 3: simulated pick ----
    strat, detail = analysis_simulated_pick(summaries)
    print('\n=== 3. SIMULATED RANKER PICK (each strategy scored on actuals) ===')
    print('PickedNLL = actual AvgNLL of the run the strategy would choose pre-kickoff.')
    print('GapCaptured: 0 = no better than random (floor); 1 = perfect (ceiling); <0 = worse than random.\n')
    summ_rows = []
    for name in list(SIGNALS) + ['ConfidenceBlend']:
        sub = strat[strat['Strategy'] == name]
        if sub.empty:
            continue
        summ_rows.append({
            'Strategy': name,
            'MeanPickedNLL': sub['PickedNLL'].mean(skipna=True),
            'Mean_vs_Floor': sub['vs_Floor'].mean(skipna=True),
            'Mean_GapCaptured': sub['GapCaptured'].mean(skipna=True),
            'MDs': int(sub['PickedNLL'].notna().sum()),
        })
    strat_summary = pd.DataFrame(summ_rows)
    if not fc.empty:
        floor_mean = fc['FloorNLL_Mean'].mean()
        ceil_mean = fc['CeilingNLL_Best'].mean()
        book_mean = fc['BookieNLL'].mean()
        print(f"Reference: Floor {floor_mean:.4f} | Ceiling {ceil_mean:.4f} | Bookie {book_mean:.4f}\n")
    disp = strat_summary.copy()
    for c in ['MeanPickedNLL', 'Mean_vs_Floor', 'Mean_GapCaptured']:
        disp[c] = disp[c].apply(agg.fmt)
    print(disp.to_string(index=False))

    # ---- Persist a tidy CSV (calibration summary + strategy summary) ----
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8', newline='') as f:
        f.write('# Signal calibration (mean across matchdays)\n')
        cal_summary.to_csv(f, index=False)
        f.write('\n# Floor vs ceiling (per matchday)\n')
        fc.to_csv(f, index=False)
        f.write('\n# Simulated ranker pick (strategy summary)\n')
        strat_summary.to_csv(f, index=False)
    print(f'\nDiagnostic CSV written to: {OUT_PATH}')


if __name__ == '__main__':
    main()
