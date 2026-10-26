"""
backtest_matchdays.py - historical matchday backtest harness.

For each target matchday in the just-ended Bundesliga season, this driver writes
that matchday's fixtures to match_results_references.csv, sets BACKTEST_DATE_CUTOFF
to the matchday's earliest fixture date (so training data excludes that date
onward), invokes AI_match_stats_prediction.py, and copies the per-matchday
outputs to Datacollection backtest/MD{N}/ for later aggregation.

The driver is resumable: matchdays whose output folder already contains the run
summary are skipped.

WARNING: overwrites Datacollection reference/match_results_references.csv on
each iteration. Save a copy of your active reference file before running.

Usage:
    python backtest_matchdays.py --all
    python backtest_matchdays.py --matchdays 5 10 15 20 25 30
    python backtest_matchdays.py --random 8
"""

import argparse
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

# Repo root: KI_PROJECT_ROOT if set (VPS), else derived from this file's location.
PROJECT_ROOT = Path(os.environ.get("KI_PROJECT_ROOT") or Path(__file__).resolve().parents[3]).as_posix()


SEASON = 2025

TESTRUNS_PATH = Path(rf'{PROJECT_ROOT}/Sports Api Data/Testruns')
DATA_PATH = Path(rf'{PROJECT_ROOT}/Sports Api Data/Bundesliga/Filtered/Datacollection')
SCRIPT_PATH = TESTRUNS_PATH / 'Code' / 'AI_match_stats_prediction.py'
REFERENCE_DIR = TESTRUNS_PATH / 'Datacollection reference'
BACKTEST_DIR = TESTRUNS_PATH / 'Datacollection backtest'
STAMMDATEN_PATH = DATA_PATH / 'Stammdaten_78.csv'
STATS_PATH = DATA_PATH / 'match_statistics_filtered_78.csv'

# Files in the live reference output folder that we copy out after each run.
OUTPUT_FILES = [
    'prediction_weight_runs.csv',
    'prediction_weight_run_summary.csv',
    'pareto_front.csv',
    'future_outcome_table_ensemble.csv',
]

# Defaults the driver passes to the pipeline. MAX_RUNS=50 keeps each matchday
# tractable (~30-60 min instead of ~10h). MATCH_STATS_MODE='predicted' forces
# the GBR-predicted stats path so the outcome model doesn't see post-match
# leakage. Both can be overridden via CLI flags.
DEFAULT_MAX_RUNS = 50
DEFAULT_MATCH_STATS_MODE = 'predicted'


def load_matchday_index():
    """Return Stammdaten rows for the season's played matches that have stats."""
    sd = pd.read_csv(STAMMDATEN_PATH, parse_dates=['Date'])
    sd = sd[(sd['Season'] == SEASON) & (sd['Gespielt'] == True)].copy()
    # Some entries (e.g. "Final") have no matchday number — drop them.
    sd['MD'] = pd.to_numeric(sd['Matchday'].str.extract(r'(\d+)')[0], errors='coerce')
    sd = sd.dropna(subset=['MD']).copy()
    sd['MD'] = sd['MD'].astype(int)
    ms = pd.read_csv(STATS_PATH)
    sd = sd[sd['MatchID'].isin(ms['MatchID'])].copy()
    return sd, ms


def matchday_fixtures(sd, ms, matchday):
    """Build the (fixtures-with-results, earliest-date) tuple for a matchday."""
    md = sd[sd['MD'] == matchday].sort_values('Date')
    if md.empty:
        return None, None
    rows = ms[ms['MatchID'].isin(md['MatchID'])][['MatchID', 'Home Goals', 'Away Goals']].copy()
    if rows.empty:
        return None, None
    rows = rows.rename(columns={'Home Goals': 'HomeGoals', 'Away Goals': 'AwayGoals'})
    rows['HomeGoals'] = rows['HomeGoals'].astype(int)
    rows['AwayGoals'] = rows['AwayGoals'].astype(int)
    rows['Result'] = rows.apply(
        lambda r: 'H' if r['HomeGoals'] > r['AwayGoals']
        else ('A' if r['HomeGoals'] < r['AwayGoals'] else 'D'),
        axis=1,
    )
    return rows[['MatchID', 'HomeGoals', 'AwayGoals', 'Result']], md['Date'].min()


def run_one_matchday(matchday, fixtures, cutoff_date, max_runs, match_stats_mode):
    """Run the pipeline for one matchday, copying outputs to a per-matchday folder."""
    target_dir = BACKTEST_DIR / f'MD{matchday:02d}'
    summary_path = target_dir / 'prediction_weight_run_summary.csv'
    if summary_path.exists():
        print(f'  MD{matchday:02d}: already has output, skipping.')
        return 'skipped'

    target_dir.mkdir(parents=True, exist_ok=True)
    ref_path = REFERENCE_DIR / 'match_results_references.csv'
    fixtures.to_csv(ref_path, index=False)

    env = os.environ.copy()
    env['BACKTEST_DATE_CUTOFF'] = cutoff_date.strftime('%Y-%m-%d')
    env['MAX_RUNS_OVERRIDE'] = str(max_runs)
    env['MATCH_STATS_MODE_OVERRIDE'] = match_stats_mode
    # The pipeline's live default is 'future'; a backtest scores the reference matchday.
    env['PREDICTION_MODE_OVERRIDE'] = 'reference'
    print(f'  MD{matchday:02d}: cutoff {env["BACKTEST_DATE_CUTOFF"]}, '
          f'{len(fixtures)} fixtures, MAX_RUNS={max_runs}, stats_mode={match_stats_mode}, '
          f'invoking pipeline...')

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        env=env,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    if result.returncode != 0:
        print(f'  MD{matchday:02d}: FAILED (rc={result.returncode})')
        tail = (result.stderr or '')[-2000:]
        if tail:
            print(tail)
        (target_dir / 'stderr.log').write_text(result.stderr or '', encoding='utf-8')
        (target_dir / 'stdout.log').write_text(result.stdout or '', encoding='utf-8')
        return 'failed'

    copied = 0
    for fname in OUTPUT_FILES:
        src = REFERENCE_DIR / fname
        if src.exists():
            shutil.copy2(src, target_dir / fname)
            copied += 1
    (target_dir / 'meta.txt').write_text(
        f'Matchday: {matchday}\n'
        f'Cutoff: {cutoff_date.date()}\n'
        f'Fixtures: {len(fixtures)}\n'
        f'Outputs copied: {copied}\n',
        encoding='utf-8',
    )
    print(f'  MD{matchday:02d}: done, {copied} files saved to {target_dir.name}/')
    return 'ran'


def main():
    parser = argparse.ArgumentParser(description='Backtest historical matchdays.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all', action='store_true', help='Backtest every played matchday in the season.')
    group.add_argument('--matchdays', nargs='+', type=int,
                       help='Backtest specific matchdays (e.g. --matchdays 5 10 15).')
    group.add_argument('--random', type=int, metavar='N',
                       help='Backtest N randomly chosen matchdays.')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for --random.')
    parser.add_argument('--max-runs', type=int, default=DEFAULT_MAX_RUNS,
                        help=f'BART weight-sample iterations per matchday (default: {DEFAULT_MAX_RUNS}).')
    parser.add_argument('--match-stats-mode', default=DEFAULT_MATCH_STATS_MODE,
                        choices=['predicted', 'actual', 'off'],
                        help=f'Match-stats mode for the outcome model (default: {DEFAULT_MATCH_STATS_MODE}). '
                             '"predicted" avoids post-match leakage; "actual" uses real stats (leakage).')
    args = parser.parse_args()

    sd, ms = load_matchday_index()
    all_matchdays = sorted(sd['MD'].unique())
    print(f'Season {SEASON}: {len(all_matchdays)} played matchdays with stats.')

    if args.all:
        targets = all_matchdays
    elif args.matchdays:
        targets = [m for m in args.matchdays if m in all_matchdays]
        missing = sorted(set(args.matchdays) - set(all_matchdays))
        if missing:
            print(f'  Note: matchdays without played/stats data ignored: {missing}')
    else:
        rng = random.Random(args.seed)
        targets = sorted(rng.sample(all_matchdays, min(args.random, len(all_matchdays))))

    print(f'Targets ({len(targets)}): {targets}')
    print(f'Settings: MAX_RUNS={args.max_runs}, MATCH_STATS_MODE={args.match_stats_mode}\n')
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)

    counts = {'ran': 0, 'skipped': 0, 'failed': 0}
    for md in targets:
        fixtures, cutoff = matchday_fixtures(sd, ms, md)
        if fixtures is None:
            print(f'  MD{md:02d}: no fixtures found, skipping.')
            counts['skipped'] += 1
            continue
        counts[run_one_matchday(md, fixtures, cutoff, args.max_runs, args.match_stats_mode)] += 1

    print(f"\nDone. Ran: {counts['ran']}, skipped: {counts['skipped']}, failed: {counts['failed']}")


if __name__ == '__main__':
    main()
