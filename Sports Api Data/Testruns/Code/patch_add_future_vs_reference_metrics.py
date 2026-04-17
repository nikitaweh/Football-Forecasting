from __future__ import annotations

from pathlib import Path


FILE_PATH = Path(r"Sports Api Data/Testruns/Code/AI_match_stats_prediction.py")


def patch_text(text: str) -> str:
    # 1) Import datetime
    if "from datetime import datetime" not in text:
        text = text.replace(
            "import random\nimport pandas as pd\n",
            "import random\nfrom datetime import datetime\nimport pandas as pd\n",
            1,
        )

    # 2) New output path for evaluation log
    const_line = "FUTURE_VS_REFERENCE_METRICS_PATH = os.path.join(FUTURE_OUTPUT_PATH, 'future_vs_reference_metrics.csv')\n"
    if "FUTURE_VS_REFERENCE_METRICS_PATH" not in text:
        needle = "FUTURE_RUN_SUMMARY_SOURCE_PATH = os.path.join(FUTURE_OUTPUT_PATH, 'prediction_weight_run_summary.csv')\n"
        if needle not in text:
            raise RuntimeError("Could not find FUTURE_RUN_SUMMARY_SOURCE_PATH line")
        text = text.replace(needle, needle + const_line, 1)

    # 3) Append helper before try_backfill_reference_from_future
    if "def append_future_vs_reference_metrics(" not in text:
        marker = "def try_backfill_reference_from_future(ref_results):"
        idx = text.find(marker)
        if idx == -1:
            raise RuntimeError("Could not find insertion marker for append_future_vs_reference_metrics")

        function_block = r'''

def append_future_vs_reference_metrics(metrics_path, summary_df):
    """Append a per-run evaluation snapshot when saved future predictions are scored
    against reference results (AvgNLL/Accuracy). Creates the CSV if missing.

    The CSV is stored in the future output folder so that future runs keep their
    evaluation history close to the generated predictions.
    """
    if summary_df is None or summary_df.empty:
        return read_optional_csv(metrics_path)

    evaluation_ts = datetime.now().isoformat(timespec='seconds')
    snapshot = summary_df.copy()
    snapshot['EvaluationTimestamp'] = evaluation_ts
    snapshot['EvaluationType'] = 'future_vs_reference'

    if 'AvgNLL' in snapshot.columns and 'Pred_AvgNLL' in snapshot.columns:
        snapshot['Delta_AvgNLL_vs_Pred'] = snapshot['AvgNLL'] - snapshot['Pred_AvgNLL']
    if 'Accuracy' in snapshot.columns and 'Pred_Accuracy' in snapshot.columns:
        snapshot['Delta_Accuracy_vs_Pred'] = snapshot['Accuracy'] - snapshot['Pred_Accuracy']
    if 'ResolvedAvgNLL' in snapshot.columns and 'AvgNLL' in snapshot.columns:
        snapshot['Delta_ResolvedAvgNLL_vs_Actual'] = snapshot['ResolvedAvgNLL'] - snapshot['AvgNLL']
    if 'ResolvedAccuracy' in snapshot.columns and 'Accuracy' in snapshot.columns:
        snapshot['Delta_ResolvedAccuracy_vs_Actual'] = snapshot['ResolvedAccuracy'] - snapshot['Accuracy']

    if 'Ranking_AvgNLL' in snapshot.columns:
        snapshot['EvalRank_AvgNLL'] = pd.to_numeric(snapshot['Ranking_AvgNLL'], errors='coerce').rank(method='min', ascending=True)
    if 'Ranking_Accuracy' in snapshot.columns:
        snapshot['EvalRank_Accuracy'] = pd.to_numeric(snapshot['Ranking_Accuracy'], errors='coerce').rank(method='min', ascending=False)
    if {'EvalRank_AvgNLL', 'EvalRank_Accuracy'}.issubset(snapshot.columns):
        a = snapshot['EvalRank_AvgNLL'].fillna(snapshot['EvalRank_AvgNLL'].max(skipna=True) + 1)
        b = snapshot['EvalRank_Accuracy'].fillna(snapshot['EvalRank_Accuracy'].max(skipna=True) + 1)
        snapshot['EvalRank_Combined'] = a + b
        best = snapshot['EvalRank_Combined'].min(skipna=True)
        snapshot['EvalIsBestCombined'] = snapshot['EvalRank_Combined'] == best

    existing = read_optional_csv(metrics_path)
    if existing.empty:
        updated = snapshot
    else:
        updated = pd.concat([existing, snapshot], ignore_index=True, sort=False)

    dedupe_cols = [c for c in [
        'EvaluationTimestamp', 'EvaluationType',
        'PredictionSource', 'SourcePredictionMode', 'MatchStatsMode',
        'BatchID', 'RunID'
    ] if c in updated.columns]
    if dedupe_cols:
        updated = updated.drop_duplicates(subset=dedupe_cols, keep='last')

    sort_cols = [c for c in ['EvaluationTimestamp', 'EvalIsBestCombined', 'Ranking_AvgNLL', 'Ranking_Accuracy'] if c in updated.columns]
    if sort_cols:
        ascending = [False] * len(sort_cols)
        if 'EvalIsBestCombined' in sort_cols:
            ascending[sort_cols.index('EvalIsBestCombined')] = False
        if 'Ranking_AvgNLL' in sort_cols:
            ascending[sort_cols.index('Ranking_AvgNLL')] = True
        if 'Ranking_Accuracy' in sort_cols:
            ascending[sort_cols.index('Ranking_Accuracy')] = False
        updated = updated.sort_values(sort_cols, ascending=ascending)

    updated.to_csv(metrics_path, index=False)
    return updated
'''

        text = text[:idx] + function_block + text[idx:]

    # 4) Call helper after backfill summary write
    call_snippet = "append_future_vs_reference_metrics(FUTURE_VS_REFERENCE_METRICS_PATH, backfill_summary_df)"
    if call_snippet not in text:
        anchor = (
            "        backfill_pred_df.to_csv(PREDICTION_OUT_PATH, index=False)\n"
            "        backfill_summary_df.to_csv(RUN_SUMMARY_OUT_PATH, index=False)\n"
        )
        if anchor not in text:
            raise RuntimeError("Could not find backfill CSV write anchor")

        insert = anchor + (
            "        evaluation_history = append_future_vs_reference_metrics(FUTURE_VS_REFERENCE_METRICS_PATH, backfill_summary_df)\n"
            "        print(f\"Updated future-vs-reference evaluation log: {FUTURE_VS_REFERENCE_METRICS_PATH}\")\n"
            "        if not evaluation_history.empty:\n"
            "            eval_cols = [c for c in [\n"
            "                'EvaluationTimestamp', 'RunID', 'BatchID', 'MatchStatsMode',\n"
            "                'AvgNLL', 'Accuracy', 'Pred_AvgNLL', 'Pred_Accuracy',\n"
            "                'Delta_AvgNLL_vs_Pred', 'Delta_Accuracy_vs_Pred',\n"
            "                'EvalRank_Combined', 'EvalIsBestCombined'\n"
            "            ] if c in evaluation_history.columns]\n"
            "            if eval_cols:\n"
            "                print(evaluation_history[eval_cols].head(10))\n\n"
        )

        text = text.replace(anchor, insert, 1)

    return text


def main() -> None:
    original = FILE_PATH.read_text(encoding="utf-8")
    patched = patch_text(original)
    if patched == original:
        print("No changes needed.")
        return
    FILE_PATH.write_text(patched, encoding="utf-8")
    print(f"Patched: {FILE_PATH}")


if __name__ == "__main__":
    main()
