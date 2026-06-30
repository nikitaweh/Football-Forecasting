"""
backtest_draw_modes.py - run draw outcome-probability modes on chosen matchdays
WITHOUT overwriting existing backtest folders.

Unlike backtest_matchdays.py (which writes to MD{N}/ and skips if present), this
driver writes each run to a fresh, self-describing, timestamped folder:

    MD{NN}_{mode}_{params}_{runs}runs_{YYYYMMDD_HHMMSS}/

so base MD{N}/ results and earlier draw-mode runs are always preserved. It sets
OUTCOME_PROBABILITY_MODE (+ the mode's params) via env, runs the pipeline once
per (matchday, mode), copies the outputs, and writes a rich meta.txt.

Reuses load_matchday_index() / matchday_fixtures() from backtest_matchdays.py.

Usage:
    python backtest_draw_modes.py                         # MD8+MD18, both modes
    python backtest_draw_modes.py --matchdays 8 18 --modes draw_multilayer_overlay score_dixon_coles
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backtest_matchdays import (
    BACKTEST_DIR, REFERENCE_DIR, SCRIPT_PATH, OUTPUT_FILES,
    load_matchday_index, matchday_fixtures,
)

# Defaults for the Dixon-Coles / Poisson score modes — chosen to match the
# existing MD18_score_dixon_coles_* folders for like-for-like comparison.
SCORE_DEFAULTS = {
    'SCORE_PROBABILITY_TOTAL_SCALE': '1.05',
    'SCORE_PROBABILITY_RHO': '-0.2',
    'SCORE_PROBABILITY_ALPHA': '1.0',
    'SCORE_PROBABILITY_MAX_GOALS': '10',
}
# Overlay mode uses the model's own env defaults (alpha 0.60, min 0.14, max 0.36,
# goaldiff-scale 0.90, signal-scale 1.00, total-goals-cap 2.60) — left unset here.

SCORE_MODES = {'score_dixon_coles', 'score_poisson_draw_ratio', 'score_dixon_coles_draw_ratio'}


def _p(x):
    """Format a number for a folder name: 1.05 -> '1p05', -0.2 -> 'm0p20'."""
    f = float(x)
    sign = 'm' if f < 0 else ''
    return sign + f'{abs(f):.2f}'.replace('.', 'p')


def folder_suffix(mode, max_runs):
    """Self-describing folder stem encoding the mode + its key params."""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    if mode in SCORE_MODES:
        s = SCORE_DEFAULTS
        params = f"s{_p(s['SCORE_PROBABILITY_TOTAL_SCALE'])}_r{_p(s['SCORE_PROBABILITY_RHO'])}_a{_p(s['SCORE_PROBABILITY_ALPHA'])}"
    elif mode == 'draw_multilayer_overlay':
        a = os.environ.get('DRAW_OVERLAY_ALPHA', '0.60')
        lo = os.environ.get('DRAW_OVERLAY_MIN_PROB', '0.14')
        hi = os.environ.get('DRAW_OVERLAY_MAX_PROB', '0.36')
        params = f"a{_p(a)}_min{_p(lo)}_max{_p(hi)}"
    else:
        params = 'default'
    return f"{mode}_{params}_{max_runs}runs_{ts}"


def best_summary_row(summary_path):
    if not summary_path.exists():
        return 'n/a'
    try:
        df = pd.read_csv(summary_path)
    except Exception:
        return 'n/a'
    if df.empty or 'AvgNLL' not in df.columns:
        return 'n/a'
    nll = pd.to_numeric(df['AvgNLL'], errors='coerce')
    if nll.notna().sum() == 0:
        return 'n/a'
    row = df.loc[nll.idxmin()]
    acc = row.get('Accuracy', 'n/a')
    return f"RunID={row.get('RunID', '?')}, AvgNLL={nll.min():.6f}, Accuracy={acc}"


def run(matchday, fixtures, cutoff, mode, max_runs, match_stats_mode):
    stem = f'MD{matchday:02d}_{folder_suffix(mode, max_runs)}'
    target_dir = BACKTEST_DIR / stem
    target_dir.mkdir(parents=True, exist_ok=True)

    # Overwrite the live reference fixtures for this matchday (same as base driver).
    (REFERENCE_DIR / 'match_results_references.csv').parent.mkdir(parents=True, exist_ok=True)
    fixtures.to_csv(REFERENCE_DIR / 'match_results_references.csv', index=False)

    env = os.environ.copy()
    env['BACKTEST_DATE_CUTOFF'] = cutoff.strftime('%Y-%m-%d')
    env['MAX_RUNS_OVERRIDE'] = str(max_runs)
    env['MATCH_STATS_MODE_OVERRIDE'] = match_stats_mode
    env['OUTCOME_PROBABILITY_MODE'] = mode
    if mode in SCORE_MODES:
        env.update(SCORE_DEFAULTS)

    print(f'  {stem}: cutoff {env["BACKTEST_DATE_CUTOFF"]}, {len(fixtures)} fixtures, '
          f'mode={mode}, MAX_RUNS={max_runs} -> running...')
    result = subprocess.run([sys.executable, str(SCRIPT_PATH)], env=env,
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f'  {stem}: FAILED (rc={result.returncode})')
        (target_dir / 'stderr.log').write_text(result.stderr or '', encoding='utf-8')
        (target_dir / 'stdout.log').write_text(result.stdout or '', encoding='utf-8')
        return 'failed', stem, 'n/a'

    copied = 0
    for fname in OUTPUT_FILES:
        src = REFERENCE_DIR / fname
        if src.exists():
            shutil.copy2(src, target_dir / fname)
            copied += 1

    best = best_summary_row(target_dir / 'prediction_weight_run_summary.csv')
    meta = [
        f'Matchday: {matchday}', f'Cutoff: {cutoff.date()}', f'Fixtures: {len(fixtures)}',
        f'MAX_RUNS: {max_runs}', f'MATCH_STATS_MODE: {match_stats_mode}',
        f'OUTCOME_PROBABILITY_MODE: {mode}',
    ]
    if mode in SCORE_MODES:
        for k in ['SCORE_PROBABILITY_TOTAL_SCALE', 'SCORE_PROBABILITY_RHO',
                  'SCORE_PROBABILITY_ALPHA', 'SCORE_PROBABILITY_MAX_GOALS']:
            meta.append(f'{k}: {SCORE_DEFAULTS[k]}')
    elif mode == 'draw_multilayer_overlay':
        for k in ['DRAW_OVERLAY_ALPHA', 'DRAW_OVERLAY_MIN_PROB', 'DRAW_OVERLAY_MAX_PROB',
                  'DRAW_OVERLAY_GOALDIFF_SCALE', 'DRAW_OVERLAY_SIGNAL_SCALE', 'DRAW_OVERLAY_TOTAL_GOALS_CAP']:
            meta.append(f'{k}: {env.get(k, "(model default)")}')
    meta += [f'Pipeline return code: 0', f'Outputs copied: {copied}', f'Best summary row: {best}']
    (target_dir / 'meta.txt').write_text('\n'.join(meta) + '\n', encoding='utf-8')
    print(f'  {stem}: done, {copied} files. Best: {best}')
    return 'ran', stem, best


def main():
    ap = argparse.ArgumentParser(description='Backtest draw modes into non-overwriting folders.')
    ap.add_argument('--matchdays', nargs='+', type=int, default=[8, 18])
    ap.add_argument('--modes', nargs='+',
                    default=['draw_multilayer_overlay', 'score_dixon_coles'])
    ap.add_argument('--max-runs', type=int, default=50)
    ap.add_argument('--match-stats-mode', default='predicted',
                    choices=['predicted', 'actual', 'off'])
    args = ap.parse_args()

    sd, ms = load_matchday_index()
    valid = set(sd['MD'].unique())
    results = []
    print(f'Draw-mode backtest: matchdays={args.matchdays}, modes={args.modes}, '
          f'MAX_RUNS={args.max_runs}\n')
    for md in args.matchdays:
        if md not in valid:
            print(f'  MD{md:02d}: no played/stats data, skipping.')
            continue
        fixtures, cutoff = matchday_fixtures(sd, ms, md)
        if fixtures is None:
            print(f'  MD{md:02d}: no fixtures, skipping.')
            continue
        for mode in args.modes:
            results.append(run(md, fixtures, cutoff, mode, args.max_runs, args.match_stats_mode))

    print('\n=== Summary ===')
    for status, stem, best in results:
        print(f'  [{status}] {stem}  |  {best}')


if __name__ == '__main__':
    main()
