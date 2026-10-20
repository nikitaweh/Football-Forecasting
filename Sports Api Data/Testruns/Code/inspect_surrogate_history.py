"""
inspect_surrogate_history.py - read-only summary of surrogate_run_history.csv.

The surrogate-history file mixes runs from different modes (predicted/actual),
sources (reference/future), and schemas — and historically BatchIDs collided
across modes because the counter was mode-relative. This tool inspects the
file(s) without modifying them and prints a per-mode breakdown so it's clear
which runs the surrogate would actually consume in each mode.

The original surrogate_run_history.csv is never modified. With --split, the
tool ALSO writes one CSV per mode slice into a sibling 'surrogate_history_split/'
folder for visual confirmation; those files are derived and ignored by the
main pipeline.

Usage:
    python inspect_surrogate_history.py                 # both folders, summary
    python inspect_surrogate_history.py --folder future # only future folder
    python inspect_surrogate_history.py --detailed      # also list batches
    python inspect_surrogate_history.py --split         # also write per-slice CSVs
"""

import argparse
import re
from pathlib import Path

import pandas as pd
import os

# Repo root: KI_PROJECT_ROOT if set (VPS), else derived from this file's location.
PROJECT_ROOT = Path(os.environ.get("KI_PROJECT_ROOT") or Path(__file__).resolve().parents[3]).as_posix()


TESTRUNS_PATH = Path(rf'{PROJECT_ROOT}/Sports Api Data/Testruns')
FOLDERS = {
    'reference': TESTRUNS_PATH / 'Datacollection reference' / 'surrogate_run_history.csv',
    'future': TESTRUNS_PATH / 'Datacollection future' / 'surrogate_run_history.csv',
}
SURROGATE_MIN_HISTORY = 100  # matches the constant in AI_match_stats_prediction.py


def load(path):
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    for col in ('MatchStatsMode', 'SourcePredictionMode', 'FeatureSchemaVersion'):
        if col not in df.columns:
            df[col] = 'unknown'
    return df


def summarise(df):
    if df is None:
        return None
    rows = []
    group_cols = ['MatchStatsMode', 'SourcePredictionMode', 'FeatureSchemaVersion']
    for (mode, source, schema), grp in df.groupby(group_cols, dropna=False):
        nll = pd.to_numeric(grp.get('AvgNLL'), errors='coerce')
        batches = sorted(pd.to_numeric(grp.get('BatchID'), errors='coerce').dropna().unique().astype(int).tolist())
        rows.append({
            'MatchStatsMode': mode,
            'SourcePredictionMode': source,
            'FeatureSchemaVersion': schema,
            'Rows': len(grp),
            'Batches': batches,
            'SurrogateReady': len(grp) >= SURROGATE_MIN_HISTORY,
            'BestAvgNLL': nll.min(skipna=True) if not nll.empty else float('nan'),
            'MeanAvgNLL': nll.mean(skipna=True) if not nll.empty else float('nan'),
        })
    return pd.DataFrame(rows).sort_values(
        ['MatchStatsMode', 'SourcePredictionMode', 'FeatureSchemaVersion']
    ).reset_index(drop=True)


def _sanitize(value):
    """Make a slice-tuple value safe to use in a filename."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 'unknown'
    return re.sub(r'[^A-Za-z0-9._-]+', '-', str(value)).strip('-') or 'unknown'


def write_split_files(df, source_path):
    """Write one CSV per (MatchStatsMode, SourcePredictionMode, FeatureSchemaVersion).

    Files go into <source_path.parent>/surrogate_history_split/ and are derived;
    the main pipeline reads only the original surrogate_run_history.csv.
    Returns the output folder and the list of written file names.
    """
    out_dir = source_path.parent / 'surrogate_history_split'
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    group_cols = ['MatchStatsMode', 'SourcePredictionMode', 'FeatureSchemaVersion']
    for (mode, source, schema), grp in df.groupby(group_cols, dropna=False):
        fname = f'{_sanitize(mode)}__{_sanitize(source)}__{_sanitize(schema)}.csv'
        out_path = out_dir / fname
        grp.to_csv(out_path, index=False)
        written.append((fname, len(grp)))
    return out_dir, written


def report_folder(label, path, detailed, split):
    print('=' * 78)
    print(f'FOLDER: {label}  ({path})')
    print('=' * 78)
    df = load(path)
    if df is None:
        print('  (file does not exist)\n')
        return
    if df.empty:
        print('  (file is empty)\n')
        return

    print(f'Total rows: {len(df)}')
    print(f'Surrogate activates per slice when Rows >= {SURROGATE_MIN_HISTORY}.\n')

    summary = summarise(df)
    display = summary.copy()
    display['BatchCount'] = display['Batches'].apply(len)
    display['BatchRange'] = display['Batches'].apply(
        lambda b: f'{min(b)}-{max(b)}' if b else '-'
    )
    display['BestAvgNLL'] = display['BestAvgNLL'].apply(lambda x: f'{x:.4f}' if pd.notna(x) else 'NaN')
    display['MeanAvgNLL'] = display['MeanAvgNLL'].apply(lambda x: f'{x:.4f}' if pd.notna(x) else 'NaN')
    cols = ['MatchStatsMode', 'SourcePredictionMode', 'FeatureSchemaVersion',
            'Rows', 'BatchCount', 'BatchRange', 'SurrogateReady', 'BestAvgNLL', 'MeanAvgNLL']
    print('Per-slice summary:')
    print(display[cols].to_string(index=False))

    if detailed:
        print('\nPer-slice batch listings:')
        for _, row in summary.iterrows():
            slice_label = f"{row['MatchStatsMode']} / {row['SourcePredictionMode']} / {row['FeatureSchemaVersion']}"
            print(f"  {slice_label}: {row['Batches']}")

    # BatchID collision check — only meaningful within a single SourcePredictionMode.
    if 'BatchID' in df.columns and 'MatchStatsMode' in df.columns:
        ctab = pd.crosstab(df['BatchID'], df['MatchStatsMode'])
        collisions = ctab[(ctab > 0).sum(axis=1) > 1]
        if not collisions.empty:
            print(f'\nLegacy BatchID collisions (same BatchID used across modes):')
            print(collisions.to_string())
            print('Going forward these stop being created — fix lives at line ~2473 of the main script.')
        else:
            print('\nNo cross-mode BatchID collisions in this file.')

    if split:
        out_dir, written = write_split_files(df, path)
        print(f'\nWrote {len(written)} per-slice file(s) to: {out_dir}')
        for fname, n in written:
            print(f'  {fname}  ({n} rows)')
    print()


def main():
    parser = argparse.ArgumentParser(description='Read-only summary of surrogate run history.')
    parser.add_argument('--folder', choices=['reference', 'future', 'both'], default='both',
                        help='Which surrogate history folder to inspect (default: both).')
    parser.add_argument('--detailed', action='store_true',
                        help='Also print the full BatchID list per slice.')
    parser.add_argument('--split', action='store_true',
                        help='Also write one CSV per slice into '
                             '<folder>/surrogate_history_split/. Read-only on the source file.')
    args = parser.parse_args()

    targets = list(FOLDERS.items()) if args.folder == 'both' else [(args.folder, FOLDERS[args.folder])]
    for label, path in targets:
        report_folder(label, path, args.detailed, args.split)


if __name__ == '__main__':
    main()
