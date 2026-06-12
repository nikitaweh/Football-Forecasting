"""
diagnose_weight_transfer.py - read-only test of the Pareto-seeding premise.

Pareto-seeding (seed new candidate weights near the empirically-best weight
vectors from past matchdays) only helps if the GOOD REGION of weight space is
stable across matchdays. We measure that directly on the existing 8-matchday
backtest, with ZERO new BART runs.

Three analyses, all on per-matchday-DEMEANED AvgNLL (so matchday difficulty
offsets, e.g. MD8~0.5 vs MD18~1.2, don't masquerade as transfer):

  1. Leave-one-matchday-out generalization - fit GBR on the other 7 matchdays'
     (weights -> demeaned AvgNLL), predict the held-out one. Spearman + gap captured.
  2. Proximity-to-others'-best - is a run that sits near OTHER matchdays' best
     region actually better on the held-out matchday? Spearman(distance, NLL).
  3. Best-region spread (descriptive) - do the per-matchday best-run centroids
     cluster, or scatter as much as random?

Decision: both (1) and (2) positive & >~0.15 -> region transfers -> Pareto-seeding
worth a backtest. Either ~0 -> region does not transfer -> seeding predicted to
fail (same root cause as the surrogate); skip the sweep.

Usage:
    python diagnose_weight_transfer.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

# Reuse loaders/formatters from the sibling diagnostics.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_backtest_results as agg
from diagnose_ranker_signals import matchday_dirs, load_matchday_summaries

BACKTEST_DIR = agg.BACKTEST_DIR
OUT_PATH = BACKTEST_DIR / 'weight_transfer_diagnostic.csv'

TOP_FRAC = 0.20      # "good region" = top 20% of runs by AvgNLL
KNN = 5              # nearest good-region points for the proximity distance
TOP_CENTROID_N = 10  # runs per matchday for the best-region centroid


def spearman(a, b):
    sub = pd.concat([pd.Series(a).reset_index(drop=True),
                     pd.Series(b).reset_index(drop=True)], axis=1).dropna()
    if len(sub) < 5 or sub.iloc[:, 0].nunique() < 2 or sub.iloc[:, 1].nunique() < 2:
        return float('nan')
    return sub.iloc[:, 0].corr(sub.iloc[:, 1], method='spearman')


def build_pooled(summaries):
    """Stack all matchdays' runs into one frame with z-scored weight features
    and per-matchday-demeaned AvgNLL. Returns (pooled_df, feature_cols)."""
    frames = []
    for md, df in summaries.items():
        sub = df.copy()
        sub = sub[pd.to_numeric(sub['AvgNLL'], errors='coerce').notna()].copy()
        if sub.empty:
            continue
        sub['MD'] = md
        sub['AvgNLL'] = pd.to_numeric(sub['AvgNLL'], errors='coerce')
        sub['DemeanedNLL'] = sub['AvgNLL'] - sub['AvgNLL'].mean()
        frames.append(sub)
    pooled = pd.concat(frames, ignore_index=True)

    feat_cols = [c for c in pooled.columns if c.startswith('Weight_')]
    if 'H2H_K' in pooled.columns:
        feat_cols = feat_cols + ['H2H_K']
    for c in feat_cols:
        pooled[c] = pd.to_numeric(pooled[c], errors='coerce')
    # Drop all-constant / all-NaN feature columns.
    feat_cols = [c for c in feat_cols if pooled[c].notna().any() and pooled[c].nunique() > 1]
    pooled[feat_cols] = pooled[feat_cols].fillna(pooled[feat_cols].mean())

    # Z-score features across the whole pool.
    mu = pooled[feat_cols].mean()
    sd = pooled[feat_cols].std(ddof=0).replace(0, 1.0)
    for c in feat_cols:
        pooled[f'z_{c}'] = (pooled[c] - mu[c]) / sd[c]
    z_cols = [f'z_{c}' for c in feat_cols]
    return pooled, feat_cols, z_cols


def analysis_lomo(pooled, feat_cols):
    """Leave-one-matchday-out GBR generalization on demeaned AvgNLL."""
    rows = []
    mds = sorted(pooled['MD'].unique())
    for held in mds:
        train = pooled[pooled['MD'] != held]
        test = pooled[pooled['MD'] == held]
        if len(train) < 30 or len(test) < 5:
            continue
        model = GradientBoostingRegressor(random_state=0)
        model.fit(train[feat_cols].values, train['DemeanedNLL'].values)
        pred = model.predict(test[feat_cols].values)
        sp = spearman(pred, test['DemeanedNLL'].values)

        # Gap captured if we picked the run the model rates best (lowest pred NLL).
        actual = test['AvgNLL'].values
        floor, ceiling = float(np.mean(actual)), float(np.min(actual))
        picked = float(actual[int(np.argmin(pred))])
        gap = floor - ceiling
        capture = (floor - picked) / gap if gap > 1e-9 else float('nan')
        rows.append({'Matchday': held, 'NumRuns': len(test),
                     'LOMO_Spearman': sp, 'GapCaptured': capture})
    return pd.DataFrame(rows)


def analysis_proximity(pooled, z_cols):
    """Does proximity to OTHER matchdays' best region predict quality on the held-out one?"""
    rows = []
    mds = sorted(pooled['MD'].unique())
    for held in mds:
        others = pooled[pooled['MD'] != held]
        test = pooled[pooled['MD'] == held]
        if test.empty or others.empty:
            continue
        # Good region = top TOP_FRAC of OTHER matchdays' runs by AvgNLL.
        n_good = max(KNN, int(len(others) * TOP_FRAC))
        good = others.nsmallest(n_good, 'AvgNLL')
        good_pts = good[z_cols].values
        centroid = good_pts.mean(axis=0)

        test_pts = test[z_cols].values
        dist_centroid = np.linalg.norm(test_pts - centroid, axis=1)
        # Mean distance to KNN nearest good points.
        knn_dist = []
        for p in test_pts:
            d = np.linalg.norm(good_pts - p, axis=1)
            knn_dist.append(np.mean(np.sort(d)[:KNN]))
        knn_dist = np.array(knn_dist)

        rows.append({
            'Matchday': held, 'NumRuns': len(test),
            'Spearman_CentroidDist': spearman(dist_centroid, test['DemeanedNLL'].values),
            'Spearman_KNNDist': spearman(knn_dist, test['DemeanedNLL'].values),
        })
    return pd.DataFrame(rows)


def analysis_spread(pooled, z_cols):
    """Are per-matchday best-run centroids tighter than the overall run scatter?"""
    mds = sorted(pooled['MD'].unique())
    centroids = []
    for md in mds:
        sub = pooled[pooled['MD'] == md].nsmallest(TOP_CENTROID_N, 'AvgNLL')
        if sub.empty:
            continue
        centroids.append(sub[z_cols].mean().values)
    centroids = np.array(centroids)
    if len(centroids) < 2:
        return float('nan'), float('nan')
    # Mean pairwise distance between matchday best-centroids.
    pair = []
    for i in range(len(centroids)):
        for j in range(i + 1, len(centroids)):
            pair.append(np.linalg.norm(centroids[i] - centroids[j]))
    best_centroid_spread = float(np.mean(pair))
    # Reference: mean distance between random runs (z-scored, so ~sqrt(2*d)).
    all_pts = pooled[z_cols].values
    rng = np.random.default_rng(0)
    idx = rng.choice(len(all_pts), size=min(400, len(all_pts)), replace=False)
    samp = all_pts[idx]
    rpair = []
    for i in range(0, len(samp), 2):
        if i + 1 < len(samp):
            rpair.append(np.linalg.norm(samp[i] - samp[i + 1]))
    random_spread = float(np.mean(rpair)) if rpair else float('nan')
    return best_centroid_spread, random_spread


def main():
    summaries = load_matchday_summaries(matchday_dirs())
    if not summaries:
        print('No usable matchday summaries found.')
        return
    pooled, feat_cols, z_cols = build_pooled(summaries)

    print('=' * 88)
    print(f'WEIGHT-TRANSFER DIAGNOSTIC  ({len(summaries)} matchdays: {list(summaries)})')
    print(f'Pooled runs: {len(pooled)}  |  feature dims: {len(feat_cols)}')
    counts = pooled.groupby('MD').size().to_dict()
    print(f'Runs per matchday: {counts}')
    print('All correlations use per-matchday-DEMEANED AvgNLL.')
    print('=' * 88)

    # ---- 1. LOMO ----
    lomo = analysis_lomo(pooled, feat_cols)
    print('\n=== 1. LEAVE-ONE-MATCHDAY-OUT GENERALIZATION ===')
    print('Fit weights->demeaned AvgNLL on 7 matchdays, predict the 8th.')
    print('Spearman > 0 means the cross-matchday model ranks the held-out runs correctly.\n')
    disp = lomo.copy()
    for c in ['LOMO_Spearman', 'GapCaptured']:
        disp[c] = disp[c].apply(agg.fmt)
    print(disp.to_string(index=False))
    mean_lomo = lomo['LOMO_Spearman'].mean(skipna=True)
    pos_lomo = int((lomo['LOMO_Spearman'] > 0).sum())
    print(f"\n  Mean LOMO Spearman: {agg.fmt(mean_lomo)}   "
          f"(positive on {pos_lomo}/{lomo['LOMO_Spearman'].notna().sum()} matchdays)")
    print(f"  Mean gap captured by cross-matchday pick: {agg.fmt(lomo['GapCaptured'].mean(skipna=True))}")

    # ---- 2. Proximity ----
    prox = analysis_proximity(pooled, z_cols)
    print('\n=== 2. PROXIMITY TO OTHER MATCHDAYS\' BEST REGION ===')
    print('Distance from each run to the top-20% region of the OTHER matchdays.')
    print('Positive Spearman = closer-to-past-good predicts better-on-held-out = transfer.\n')
    disp = prox.copy()
    for c in ['Spearman_CentroidDist', 'Spearman_KNNDist']:
        disp[c] = disp[c].apply(agg.fmt)
    print(disp.to_string(index=False))
    mean_cen = prox['Spearman_CentroidDist'].mean(skipna=True)
    mean_knn = prox['Spearman_KNNDist'].mean(skipna=True)
    print(f"\n  Mean Spearman (centroid distance): {agg.fmt(mean_cen)}")
    print(f"  Mean Spearman (kNN distance):      {agg.fmt(mean_knn)}")

    # ---- 3. Spread ----
    best_spread, rand_spread = analysis_spread(pooled, z_cols)
    print('\n=== 3. BEST-REGION SPREAD (descriptive) ===')
    print(f"  Mean pairwise distance between matchday best-centroids: {agg.fmt(best_spread)}")
    print(f"  Reference random run-to-run distance:                   {agg.fmt(rand_spread)}")
    if pd.notna(best_spread) and pd.notna(rand_spread) and rand_spread > 0:
        ratio = best_spread / rand_spread
        print(f"  Ratio (best-centroid spread / random spread): {agg.fmt(ratio)}")
        print("  Ratio << 1 => best regions cluster (transfer plausible); ~1 => scatter like random.")

    # ---- Verdict ----
    print('\n' + '=' * 88)
    transfers = (pd.notna(mean_lomo) and mean_lomo > 0.15 and
                 pd.notna(mean_knn) and mean_knn > 0.15)
    if transfers:
        print('VERDICT: Signal of transfer (both core metrics > 0.15). Pareto-seeding')
        print('         is plausible -> worth implementing and backtesting.')
    else:
        print('VERDICT: No usable transfer (a core metric is ~0). Pareto-seeding shares the')
        print("         surrogate's root failure and is predicted NOT to beat random.")
        print('         Recommend skipping the sweep; pivot to the draw problem.')
    print('=' * 88)

    # ---- Persist ----
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8', newline='') as f:
        f.write('# Leave-one-matchday-out generalization\n')
        lomo.to_csv(f, index=False)
        f.write('\n# Proximity to other matchdays best region\n')
        prox.to_csv(f, index=False)
        f.write('\n# Best-region spread\n')
        pd.DataFrame([{'BestCentroidSpread': best_spread, 'RandomSpread': rand_spread}]).to_csv(f, index=False)
    print(f'\nDiagnostic CSV written to: {OUT_PATH}')


if __name__ == '__main__':
    main()
