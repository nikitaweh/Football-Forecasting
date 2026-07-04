"""
build_dashboard_data.py - export tidy CSVs for the R Shiny performance dashboard.

This is the *data layer* for `dashboard/` (R Shiny). It does NOT define any new
metrics: it reuses the existing, battle-tested logic in
`analyze_backtest_results.py` (NLL / accuracy / bookmaker baseline / ensemble) and
`compare_draw_modes.py` (per-outcome H/D/A NLL at the deployable floor), so the
dashboard can never drift from the numbers the rest of the pipeline reports.

Outputs (written to <repo>/dashboard/data/):
  - matchday_performance.csv      one row per Bundesliga matchday (= season_summary)
  - mode_performance.csv          one row per MD* folder (baseline + every variant)
  - per_outcome_nll.csv           long: Matchday x Mode x Outcome(H/D/A/ALL) NLL
  - run_distributions.csv         long: every run's AvgNLL / Accuracy per folder
  - international_performance.csv  per-match NLL / correctness for the Intl model
  - manifest.json                 generated_at, source_fingerprint, coverage counts

The R app calls this script (via system2) whenever it detects new outcome data or
new mode folders, then reloads the CSVs. Re-running is idempotent and safe.

Usage:
    python build_dashboard_data.py
"""

import contextlib
import io
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_backtest_results as agg
import compare_draw_modes as cdm
import build_dixon_coles_backtest as dcb

# ── Paths ───────────────────────────────────────────────────────────────────
ROOT = agg.TESTRUNS_PATH.parents[1]                       # C:/AI Projekt/KI-Projekt
BACKTEST_DIR = agg.BACKTEST_DIR
SEASON_SUMMARY = BACKTEST_DIR / 'season_summary.csv'
REFERENCE_RESULTS = agg.TESTRUNS_PATH / 'Datacollection reference' / 'match_results_references.csv'
INTL_VALIDATION = (ROOT / 'Sports Api Data' / 'International' / 'Model Output' /
                   'competitive' / 'international_competitive_validation.csv')
OUT_DIR = ROOT / 'dashboard' / 'data'

MD_FOLDER_RE = re.compile(r'^MD(\d+)')


# ── helpers ─────────────────────────────────────────────────────────────────
def _md_folders():
    """All MD* backtest folders, sorted, with their parsed matchday number."""
    out = []
    if not BACKTEST_DIR.exists():
        return out
    for d in sorted(BACKTEST_DIR.iterdir()):
        if not d.is_dir():
            continue
        m = MD_FOLDER_RE.match(d.name)
        if not m:
            continue
        out.append((int(m.group(1)), d))
    return out


def _read_meta(folder):
    """Parse a folder's meta.txt 'Key: Value' lines into a dict (empty if none)."""
    meta = {}
    p = folder / 'meta.txt'
    if not p.exists():
        return meta
    for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
        if ':' in line:
            k, _, v = line.partition(':')
            meta[k.strip()] = v.strip()
    return meta


def _mode_label(folder_name, md, meta):
    """Human mode name: 'baseline' for a plain MDNN folder, else the outcome mode."""
    base = f'MD{md:02d}'
    if folder_name == base or folder_name == f'MD{md}':
        return 'baseline'
    return meta.get('OUTCOME_PROBABILITY_MODE') or cdm.label_for(folder_name, md)


def _variant_label(folder_name, md):
    """Folder suffix with the timestamp stripped (disambiguates repeated runs)."""
    return cdm.label_for(folder_name, md)


def _safe_summary(folder):
    p = folder / 'prediction_weight_run_summary.csv'
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
    except (pd.errors.EmptyDataError, OSError):
        return None
    return df if not df.empty else None


def _floor_score(folder, res_map, bookie_baseline):
    """Deployable-floor metrics for a folder: NLL/accuracy of the per-match mean
    forecast over all runs (no hindsight best-run selection). Same basis as the
    Dixon 'Base floor' and compare_draw_modes, so the whole dashboard agrees.
    """
    g = cdm.floor_forecast(folder)  # index MatchID, normalised mean WinProb/DrawProb/LoseProb
    if g is None or g.empty:
        return None
    nlls, correct, n = [], 0, 0
    for mid, r in g.iterrows():
        actual = res_map.get(int(mid))
        if actual is None:
            continue
        probs = {'H': r['WinProb'], 'D': r['DrawProb'], 'A': r['LoseProb']}
        nlls.append(-math.log(max(float(probs[actual]), 1e-12)))
        correct += int(max(probs, key=probs.get) == actual)
        n += 1
    if not nlls:
        return None
    floor_nll = sum(nlls) / len(nlls)
    has_bk = bookie_baseline is not None and not (isinstance(bookie_baseline, float) and math.isnan(bookie_baseline))
    return {
        'FloorNLL': floor_nll,
        'FloorAcc': correct / n,
        'FloorN': n,
        'FloorGapVsBookie': (floor_nll - bookie_baseline) if has_bk else float('nan'),
        'FloorBeatsBookie': (bool(floor_nll < bookie_baseline) if has_bk else None),
    }


# ── exporters ───────────────────────────────────────────────────────────────
def export_matchday_performance(res_map, bookie_nll_map, matches_df):
    """season_summary.csv (best-run metrics) enriched with deployable-floor metrics.

    The dashboard uses the Floor* columns as its headline baseline; Best* are kept
    only as a faint hindsight reference.
    """
    if not SEASON_SUMMARY.exists():
        print('  ! season_summary.csv missing; matchday_performance will be empty')
        cols = ['Matchday', 'NumFixtures', 'ResultMix', 'BookieNLL', 'BestNLL', 'MeanNLL',
                'BestAcc', 'MeanAcc', 'GapVsBookie', 'BeatsBookie', 'EnsembleNLL',
                'EnsembleAcc', 'EnsembleGapVsBookie', 'NumRuns',
                'FloorNLL', 'FloorAcc', 'FloorGapVsBookie', 'FloorBeatsBookie']
        pd.DataFrame(columns=cols).to_csv(OUT_DIR / 'matchday_performance.csv', index=False)
        return 0
    df = pd.read_csv(SEASON_SUMMARY).sort_values('Matchday')

    floor_rows = []
    for md in df['Matchday']:
        md = int(md)
        folder = BACKTEST_DIR / f'MD{md:02d}'
        mdm = matches_df[matches_df['MD'] == md]
        bb, _, _ = agg.matchday_bookie_baseline(
            mdm['MatchID'].tolist(), mdm['Result'].tolist(), bookie_nll_map)
        fs = _floor_score(folder, res_map, bb) or {}
        floor_rows.append({'Matchday': md, **fs})
    df = df.merge(pd.DataFrame(floor_rows), on='Matchday', how='left')
    df.to_csv(OUT_DIR / 'matchday_performance.csv', index=False)
    return len(df)


def export_mode_and_runs(res_map, bookie_nll_map, matches_df):
    """mode_performance.csv (one row per folder) + run_distributions.csv (every run)."""
    mode_rows, run_rows = [], []
    for md, folder in _md_folders():
        summary = _safe_summary(folder)
        if summary is None or 'AvgNLL' not in summary.columns:
            continue
        meta = _read_meta(folder)
        mode = _mode_label(folder.name, md, meta)
        variant = _variant_label(folder.name, md)
        stats_mode = meta.get('MATCH_STATS_MODE')
        if not stats_mode and 'MatchStatsMode' in summary.columns and not summary.empty:
            stats_mode = str(summary['MatchStatsMode'].iloc[0])

        avg_nll = pd.to_numeric(summary['AvgNLL'], errors='coerce')
        acc = pd.to_numeric(summary.get('Accuracy'), errors='coerce') if 'Accuracy' in summary.columns else pd.Series(dtype=float)

        # bookie baseline for this matchday (reuse agg logic)
        md_matches = matches_df[matches_df['MD'] == md]
        bookie_baseline, _, _ = agg.matchday_bookie_baseline(
            md_matches['MatchID'].tolist(), md_matches['Result'].tolist(), bookie_nll_map)

        best_nll = avg_nll.min(skipna=True)
        best_idx = avg_nll.idxmin() if avg_nll.notna().any() else None
        best_acc = acc.loc[best_idx] if (best_idx is not None and best_idx in acc.index) else (acc.max(skipna=True) if not acc.empty else float('nan'))
        best_run_id = summary.loc[best_idx, 'RunID'] if (best_idx is not None and 'RunID' in summary.columns) else None
        gap = (best_nll - bookie_baseline) if pd.notna(best_nll) and pd.notna(bookie_baseline) else float('nan')

        # deployable-floor metrics (the dashboard's headline baseline)
        fs = _floor_score(folder, res_map, bookie_baseline) or {}

        mode_rows.append({
            'Matchday': md,
            'Mode': mode,
            'Variant': variant,
            'ModeFolder': folder.name,
            'MatchStatsMode': stats_mode,
            'BestRunID': best_run_id,
            'BestAvgNLL': best_nll,
            'BestAccuracy': best_acc,
            'MeanAvgNLL': avg_nll.mean(skipna=True),
            'FloorAvgNLL': fs.get('FloorNLL'),
            'FloorAccuracy': fs.get('FloorAcc'),
            'FloorGapVsBookie': fs.get('FloorGapVsBookie'),
            'FloorBeatsBookie': fs.get('FloorBeatsBookie'),
            'NumRuns': int(avg_nll.notna().sum()),
            'BookieNLL': bookie_baseline,
            'GapVsBookie': gap,
            'BeatsBookie': (bool(best_nll < bookie_baseline)
                           if pd.notna(best_nll) and pd.notna(bookie_baseline) else None),
        })

        run_id_col = summary['RunID'] if 'RunID' in summary.columns else pd.Series(range(len(summary)))
        for rid, nll_v, acc_v in zip(run_id_col, avg_nll, (acc if not acc.empty else [float('nan')] * len(summary))):
            if pd.isna(nll_v):
                continue
            run_rows.append({'Matchday': md, 'Mode': mode, 'Variant': variant,
                             'RunID': rid, 'AvgNLL': nll_v, 'Accuracy': acc_v})

    pd.DataFrame(mode_rows).to_csv(OUT_DIR / 'mode_performance.csv', index=False)
    pd.DataFrame(run_rows).to_csv(OUT_DIR / 'run_distributions.csv', index=False)
    return len(mode_rows), len(run_rows)


def export_per_outcome_nll(res_map, bookie_df):
    """Per-outcome (H/D/A/ALL) NLL at the deployable floor, for every MD* folder.

    Reuses compare_draw_modes.floor_forecast / per_outcome_nll so the guardrail
    view (does a draw mode help D without hurting H/A) matches compare_draw_modes.
    """
    rows = []
    matches = agg.load_actual_results_by_matchday()
    for md, folder in _md_folders():
        g = cdm.floor_forecast(folder)
        if g is None:
            continue
        meta = _read_meta(folder)
        mode = _mode_label(folder.name, md, meta)
        variant = _variant_label(folder.name, md)
        o = cdm.per_outcome_nll(g, res_map)
        for outcome in ('H', 'D', 'A', 'ALL'):
            rows.append({'Matchday': md, 'Mode': mode, 'Variant': variant,
                         'Outcome': outcome, 'NLL': o.get(outcome),
                         'MeanDrawProb': o.get('MeanDrawProb')})
    # one bookie reference row per matchday (per outcome)
    for md in sorted({md for md, _ in _md_folders()}):
        md_matches = matches[matches['MD'] == md]
        match_ids = set(md_matches['MatchID'].astype(int))
        if not match_ids:
            continue
        b = cdm.bookie_per_outcome(match_ids, bookie_df, res_map)
        for outcome in ('H', 'D', 'A', 'ALL'):
            rows.append({'Matchday': md, 'Mode': 'BWIN bookie', 'Variant': 'BWIN bookie',
                         'Outcome': outcome, 'NLL': b.get(outcome),
                         'MeanDrawProb': b.get('MeanDrawProb')})
    pd.DataFrame(rows).to_csv(OUT_DIR / 'per_outcome_nll.csv', index=False)
    return len(rows)


def export_international():
    """Per-match NLL / correctness for the International validation set."""
    cols = ['MatchID', 'MatchDate', 'Competition', 'Season', 'Stage', 'HomeTeam', 'AwayTeam',
            'Outcome', 'PredictedResult', 'Correct', 'NLL', 'WinProb', 'DrawProb', 'LoseProb']
    if not INTL_VALIDATION.exists():
        pd.DataFrame(columns=cols).to_csv(OUT_DIR / 'international_performance.csv', index=False)
        return 0
    df = pd.read_csv(INTL_VALIDATION)
    need = {'HomeGoals', 'AwayGoals', 'WinProb', 'DrawProb', 'LoseProb'}
    if not need.issubset(df.columns) or df.empty:
        pd.DataFrame(columns=cols).to_csv(OUT_DIR / 'international_performance.csv', index=False)
        return 0
    for c in ('HomeGoals', 'AwayGoals', 'WinProb', 'DrawProb', 'LoseProb'):
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['HomeGoals', 'AwayGoals'])

    def outcome(r):
        if r['HomeGoals'] > r['AwayGoals']: return 'H'
        if r['HomeGoals'] < r['AwayGoals']: return 'A'
        return 'D'

    df['Outcome'] = df.apply(outcome, axis=1)
    prob_for = {'H': 'WinProb', 'D': 'DrawProb', 'A': 'LoseProb'}
    df['NLL'] = df.apply(
        lambda r: -math.log(max(float(r[prob_for[r['Outcome']]]), 1e-12))
        if pd.notna(r[prob_for[r['Outcome']]]) else float('nan'), axis=1)
    if 'PredictedResult' in df.columns:
        df['Correct'] = (df['PredictedResult'] == df['Outcome'])
    else:
        df['Correct'] = pd.NA
    keep = [c for c in cols if c in df.columns]
    df[keep].to_csv(OUT_DIR / 'international_performance.csv', index=False)
    return len(df)


def export_dixon(res_map, bookie_nll_map):
    """Season-wide post-hoc Dixon-Coles: per-matchday table + pooled per-outcome.

    Reuses build_dixon_coles_backtest.build_frames so the dashboard shows exactly
    the same numbers as the persisted backtest files. Reads base runs only - it
    does NOT write into the backtest folders (that is the standalone script's job),
    so it never disturbs the source fingerprint / triggers a refresh loop.
    """
    try:
        _, season, per_outcome = dcb.build_frames(res_map, bookie_nll_map)
    except Exception as e:  # noqa: BLE001
        print(f'  ! dixon export failed ({e}); writing empty tables')
        season, per_outcome = pd.DataFrame(), pd.DataFrame()
    season.to_csv(OUT_DIR / 'dixon_performance.csv', index=False)
    per_outcome.to_csv(OUT_DIR / 'dixon_per_outcome.csv', index=False)
    return len(season)


SCHEMA_SHORT = {'bases_v2_hybrid': 'v2', 'bases_v3_player_workload': 'v3-workload'}


def _first_val(summary, col):
    if summary is not None and col in summary.columns:
        vals = [str(v) for v in summary[col].dropna().unique()]
        return vals[0] if vals else None
    return None


def _mode_key(folder, md, summary, meta):
    """Composite mode label = FeatureSchemaVersion x OutcomeProbabilityMode.

    Captures both what feeds the model (v2 hybrid vs v3 player-workload) and how
    probabilities are derived (normal / draw overlay / dixon). The v2 'normal'
    runs are one 'baseline (v2)' series whether or not they recorded the outcome
    -mode column (same config, only pipeline vintage differs). Any new schema or
    outcome mode automatically becomes its own labelled series.
    """
    opm = meta.get('OUTCOME_PROBABILITY_MODE') or _first_val(summary, 'OutcomeProbabilityMode')
    fs = meta.get('FEATURE_SCHEMA_VERSION') or _first_val(summary, 'FeatureSchemaVersion')
    schema = SCHEMA_SHORT.get(fs, fs)
    outcome = opm or 'normal'
    if outcome == 'normal':
        return 'baseline (v2)' if schema in (None, 'v2') else f'normal ({schema})'
    return outcome if schema in (None, 'v2') else f'{outcome} ({schema})'


def export_mode_curve(res_map, bookie_nll_map, matches_df, bookie_df):
    """Long table Matchday x Mode of deployable-floor NLL/accuracy for the Mode
    explorer page: every outcome mode (grouped by OutcomeProbabilityMode) + the
    season-wide Dixon-Coles + the BWIN bookie, all on the same floor basis.
    """
    rows = []
    bk_pred = {}
    for _, r in bookie_df.iterrows():
        probs = {'H': r['p_H'], 'D': r['p_D'], 'A': r['p_A']}
        bk_pred[int(r['MatchID'])] = max(probs, key=probs.get)

    for md, folder in _md_folders():
        summary = _safe_summary(folder)
        if summary is None or 'AvgNLL' not in summary.columns:
            continue
        mdm = matches_df[matches_df['MD'] == md]
        bb, _, _ = agg.matchday_bookie_baseline(mdm['MatchID'].tolist(), mdm['Result'].tolist(), bookie_nll_map)
        fs = _floor_score(folder, res_map, bb)
        if not fs:
            continue
        mode = _mode_key(folder, md, summary, _read_meta(folder))
        rows.append({'Matchday': md, 'Mode': mode, 'NLL': fs['FloorNLL'], 'Acc': fs['FloorAcc'],
                     'N': fs['FloorN'], 'GapVsBookie': fs['FloorGapVsBookie']})

    # season-wide post-hoc Dixon-Coles
    try:
        _, season, _ = dcb.build_frames(res_map, bookie_nll_map)
        for _, r in season.iterrows():
            rows.append({'Matchday': int(r['Matchday']), 'Mode': 'dixon_coles',
                         'NLL': r['DixonNLL'], 'Acc': r['DixonAcc'], 'N': r['N'],
                         'GapVsBookie': r['DixonGapVsBookie']})
    except Exception as e:  # noqa: BLE001
        print(f'  ! mode_curve dixon rows skipped ({e})')

    # BWIN bookie
    for md in sorted(pd.to_numeric(matches_df['MD'], errors='coerce').dropna().unique()):
        md = int(md)
        mdm = matches_df[matches_df['MD'] == md]
        bb, _, _ = agg.matchday_bookie_baseline(mdm['MatchID'].tolist(), mdm['Result'].tolist(), bookie_nll_map)
        if bb is None or (isinstance(bb, float) and math.isnan(bb)):
            continue
        preds = [(bk_pred.get(int(m)), res_map.get(int(m))) for m in mdm['MatchID'].astype(int)]
        preds = [(p, a) for p, a in preds if p is not None and a is not None]
        acc = (sum(p == a for p, a in preds) / len(preds)) if preds else float('nan')
        rows.append({'Matchday': md, 'Mode': 'bookie', 'NLL': bb, 'Acc': acc,
                     'N': len(preds), 'GapVsBookie': 0.0})

    df = pd.DataFrame(rows)
    if not df.empty:
        # collapse repeated (matchday, mode) - e.g. MD18's three score_dixon reruns
        df = (df.groupby(['Matchday', 'Mode'], as_index=False)
                .agg(NLL=('NLL', 'mean'), Acc=('Acc', 'mean'), N=('N', 'mean'),
                     GapVsBookie=('GapVsBookie', 'mean')))
        df['BeatsBookie'] = df['GapVsBookie'] < 0
        df = df.sort_values(['Mode', 'Matchday'])
    df.to_csv(OUT_DIR / 'mode_curve.csv', index=False)
    return df['Mode'].nunique() if not df.empty else 0


def source_fingerprint():
    """A cheap (count, max-mtime) signature of every input the dashboard depends on.

    The R app recomputes the SAME rule on each poll; a change means new outcome
    data or a new mode folder, which triggers a re-export. Keep this rule simple
    and in sync with load_data.R::source_fingerprint().
    """
    folders = [d for _, d in _md_folders()]
    paths = folders + [REFERENCE_RESULTS, agg.STAMMDATEN_PATH, agg.STATS_PATH, INTL_VALIDATION]
    odds = sorted(agg.ODDS_DIR.glob('bwin_historical_odds_*.csv')) if agg.ODDS_DIR.exists() else []
    if odds:
        paths.append(odds[-1])
    max_mtime = 0
    for p in paths:
        try:
            max_mtime = max(max_mtime, int(os.path.getmtime(p)))
        except OSError:
            continue
    return f'{len(folders)}:{max_mtime}'


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f'Exporting dashboard data -> {OUT_DIR}')

    # 1) regenerate season_summary.csv from current outcome data (quietly).
    #    Suppress agg's verbose stdout, but surface any failure on the REAL stdout
    #    so a stale season_summary can never pass silently.
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            agg.main()
    except Exception as e:  # noqa: BLE001 - never let aggregation crash the export
        print(f'  ! agg.main() FAILED ({type(e).__name__}: {e}); '
              f'season_summary.csv may be STALE. Fix the source, then re-run.')

    # shared inputs
    matches_df = agg.load_actual_results_by_matchday()
    res_map = dict(zip(matches_df['MatchID'].astype(int), matches_df['Result']))
    bookie_nll_map, odds_src = agg.load_bookmaker_match_nll()
    bookie_df = cdm.load_bookie_forecasts()

    n_md = export_matchday_performance(res_map, bookie_nll_map, matches_df)
    n_mode, n_runs = export_mode_and_runs(res_map, bookie_nll_map, matches_df)
    n_outcome = export_per_outcome_nll(res_map, bookie_df)
    n_intl = export_international()
    n_dixon = export_dixon(res_map, bookie_nll_map)
    n_modes = export_mode_curve(res_map, bookie_nll_map, matches_df, bookie_df)

    manifest = {
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'source_fingerprint': source_fingerprint(),
        'odds_source': getattr(odds_src, 'name', None),
        'counts': {
            'matchdays': n_md, 'mode_folders': n_mode, 'run_rows': n_runs,
            'per_outcome_rows': n_outcome, 'international_matches': n_intl,
            'dixon_matchdays': n_dixon, 'mode_curve_modes': n_modes,
        },
    }
    (OUT_DIR / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    print(f'  matchdays={n_md}  mode_folders={n_mode}  runs={n_runs}  '
          f'per_outcome={n_outcome}  international={n_intl}  dixon={n_dixon}  modes={n_modes}')
    print(f'  manifest fingerprint = {manifest["source_fingerprint"]}')
    print('Done.')


if __name__ == '__main__':
    main()
