# Skills

Recurring project tasks. Each wraps existing scripts in `Sports Api Data/Testruns/Code/` (or the data-collection and website scripts) and defines how results are reported (median across runs, NLL/Brier first, per outcome H/D/A, uncertainty stated).

| Skill | Invocation | Wraps |
|---|---|---|
| `run-backtest` | manual `/run-backtest` | backtest_matchdays.py, analyze_backtest_results.py |
| `collect-matchday-data` | manual `/collect-matchday-data` | bundesliga_combined_pipeline_78.py, bwin_historical_odds_download.py |
| `compare-vs-bookie` | auto or manual | compare_models_vs_bookie.py, compare_worldcup_vs_bookie.py |
| `eval-dixon-coles` | auto or manual | eval_dixon_coles_all.py, eval_dixon_coles_draw_ratio_all.py, build_dixon_coles_backtest.py |
| `diagnose-draws` | auto or manual | diagnose_draws.py, probe_draw_signal.py, compare_draw_modes.py, backtest_draw_modes.py |
| `diagnose-weights` | auto or manual | diagnose_weight_transfer.py, inspect_surrogate_history.py, diagnose_ranker_signals.py |
| `update-results` | auto or manual | update_match_results_references.py |
| `refresh-dashboard` | auto or manual | build_dashboard_data.py, website/build_data*.py |
| `calibration-report` | auto or manual | calibration_report.py (in the skill folder) |
| `skillwriter` | auto or manual | writes new skills in this style when a task recurs (proposes first) |
