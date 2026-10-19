---
name: diagnose-weights
description: Check whether Weight_* configurations transfer across matchdays (LOMO), inspect surrogate_run_history.csv per mode and schema, and test whether pre-kickoff ranker signals pick good weights. Use for weight tuning, surrogate, Pareto or ranker questions.
---

# Diagnose Weights and Surrogate

Read-only diagnostics over the existing backtest. No new BART runs.

## When to Use

- Someone proposes more weight tuning, Pareto seeding or a new ranker signal
- The surrogate behaves strangely or uses fewer runs than expected
- Before freezing the live-season weight set

## Run

```bash
PY="C:/AI Projekt/.venv/Scripts/python.exe"
cd "Sports Api Data/Testruns/Code"
"$PY" diagnose_weight_transfer.py                 # LOMO Spearman(distance, demeaned NLL), cluster spread vs random
"$PY" inspect_surrogate_history.py --folder both  # per-mode / per-schema breakdown; --detailed, --split (writes derived copies only)
"$PY" diagnose_ranker_signals.py                  # do Pred_AvgNLL / MeanTopProb / MeanProbGap / MeanEntropy track true AvgNLL?
```

## How to Read It

- Reference value: LOMO Spearman ≈ 0.0016, i.e. weights do not transfer. Treat any proposal that relies on transfer as unsupported unless this number changes materially with more matchdays.
- NLL is demeaned per matchday so matchday difficulty does not fake transfer.
- Surrogate history must not mix `MatchStatsMode` or `FeatureSchemaVersion`; flag any slice that would.

## Output Format

```text
Transfer: LOMO Spearman X (N matchdays); best-centroid spread X vs random X
Surrogate history: rows per (mode, source, schema); usable rows for the current mode
Ranker: correlation of each signal with true AvgNLL; regret vs hindsight-best
Verdict: does this support further weight work? (default expectation: no)
```
