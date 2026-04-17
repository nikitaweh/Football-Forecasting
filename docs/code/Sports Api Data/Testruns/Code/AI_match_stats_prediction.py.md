# `AI_match_stats_prediction.py`

Source: `Sports Api Data/Testruns/Code/AI_match_stats_prediction.py`

## Überblick

Model overview ============== This script extends the original outcome model with a leakage-safe, two-stage pipeline for match statistics: 1. Build pre-match features from historical team strength, rolling last-5 form...

## Zweck / Responsibilities

- Liest Quelldaten aus konfigurierten Eingabedateien oder Datenordnern ein.
- Schreibt aufbereitete Ergebnisse in Projektdateien oder Zieltabellen.
- Transformiert tabellarische Daten ueber DataFrames und CSV-Operationen.
- Fuehrt Modelltraining, Bewertung oder Vorhersagen fuer Analysezwecke aus.
- Kapselt die Hauptlogik in wiederverwendbaren Funktionen fuer Parsing, Bereinigung oder Export.

## Wichtige Klassen/Funktionen

- `load_weather(path)`: Laedt Eingabedaten und gibt die aufbereitete Struktur zurueck.
- `coerce_numeric_columns(df_src, columns)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `summarize_h2h(subset)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `add_h2h_features(df_src)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `apply_h2h_scaling(feature_df, k)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `add_team_asof_features(df_src, team_id_col, prefix)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `load_reference_results(primary_path, fallback_path=None)`: Laedt Eingabedaten und gibt die aufbereitete Struktur zurueck.
- `read_optional_csv(path)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `first_non_null_value(values, default_value=float('nan'))`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `outcome_from_goals(home_goals, away_goals)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `prepare_run_summary(summary_df)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `append_to_run_history(history_path, summary_df)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `try_backfill_reference_from_future(ref_results)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `prob_for_actual(row)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `build_prediction_frame(df_src, ref_results, mode, future_limit=9, reference_limit=None)`: Erzeugt eine abgeleitete Struktur oder ein Ergebnisobjekt aus vorhandenen Daten.
- `make_match_stats_regressor()`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `fit_match_stats_estimator(x_train, y_train)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `postprocess_match_stats(pred_df)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `build_match_stats_predictions(train_df, predict_df, feature_cols, target_cols)`: Erzeugt eine abgeleitete Struktur oder ein Ergebnisobjekt aus vorhandenen Daten.
- `apply_match_stats_mode(train_df, predict_df, raw_predict_df)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `mean_available(values, default_value=1.25)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `estimate_scoreline(match_row, predicted_goal_diff, predicted_result)`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `compute_pareto_front(df, nll_col='AvgNLL', acc_col='Accuracy')`: Erfuellt einen zentralen Verarbeitungsschritt innerhalb des Moduls.
- `build_pareto_decision_set(df, target_size=PARETO_TARGET_SIZE)`: Erzeugt eine abgeleitete Struktur oder ein Ergebnisobjekt aus vorhandenen Daten.

## Inputs / Outputs & Side-effects

**Inputs**
- `DATA_PATH`: `r'C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection'`
- `WEATHER_HIST_PATH`: `os.path.join(DATA_PATH, 'historical_weather_data_78.csv')`
- `RESULTS_PATH`: `os.path.join(FUTURE_OUTPUT_PATH, 'match_results_references.csv')`
- `FALLBACK_RESULTS_PATH`: `None`
- `RUN_HISTORY_SOURCE_PATH`: `os.path.join(REFERENCE_OUTPUT_PATH, 'surrogate_run_history.csv')`
- `RESULTS_PATH`: `os.path.join(REFERENCE_OUTPUT_PATH, 'match_results_references.csv')`
- `FALLBACK_RESULTS_PATH`: `os.path.join(DATA_PATH, 'match_results_references.csv')`
- `RUN_HISTORY_PATH`: `os.path.join(OUTPUT_PATH, 'surrogate_run_history.csv')`
- `FUTURE_PREDICTION_SOURCE_PATH`: `os.path.join(FUTURE_OUTPUT_PATH, 'prediction_weight_runs.csv')`
- `FUTURE_RUN_SUMMARY_SOURCE_PATH`: `os.path.join(FUTURE_OUTPUT_PATH, 'prediction_weight_run_summary.csv')`

**Outputs**
- `FUTURE_OUTPUT_PATH`: `os.path.join(TESTRUNS_PATH, 'Datacollection future')`
- `REFERENCE_OUTPUT_PATH`: `os.path.join(TESTRUNS_PATH, 'Datacollection reference')`
- `OUTPUT_PATH`: `FUTURE_OUTPUT_PATH`
- `DECISION_OUT_PATH`: `os.path.join(FUTURE_OUTPUT_PATH, 'future_candidate_ranking.csv')`
- `OUTPUT_PATH`: `REFERENCE_OUTPUT_PATH`
- `DECISION_OUT_PATH`: `os.path.join(REFERENCE_OUTPUT_PATH, 'pareto_front.csv')`
- `PREDICTION_OUT_PATH`: `os.path.join(OUTPUT_PATH, 'prediction_weight_runs.csv')`
- `RUN_SUMMARY_OUT_PATH`: `os.path.join(OUTPUT_PATH, 'prediction_weight_run_summary.csv')`
- `PARETO_OUT_PATH`: `DECISION_OUT_PATH`
- `PREDICTED_MATCH_STATS_OUT_PATH`: `os.path.join(OUTPUT_PATH, 'predicted_match_stats.csv')`

**Side-effects**
- Schreibt Dateien im Projektverzeichnis oder aktualisiert bestehende Artefakte.
- Schreibt Laufzeit- und Fehlerhinweise auf ``stdout``.
- Legt Zielordner bei Bedarf automatisch an.

## Konfiguration / Env

- `TESTRUNS_PATH`: `r'C:/AI Projekt/KI-Projekt/Sports Api Data/Testruns'`
- `MAX_RUNS`: `20`
- `RANDOM_STATE`: `42`
- `PREDICTION_MODE`: `'reference'`
- `REFERENCE_PREDICTION_LIMIT`: `None`
- `MATCH_STATS_MODE`: `'predicted' if PREDICTION_MODE == 'future' else 'actual'`
- `MATCH_STATS_MODEL`: `'gbr'`
- `MATCH_STATS_CV_SPLITS`: `5`
- `FUTURE_OUTCOME_TABLE_PATH`: `os.path.join(OUTPUT_PATH, 'future_outcome_table.csv')`
- `WEATHER_FUTURE_PATH`: `os.path.join(OUTPUT_PATH, 'weather_data.csv')`
- `SURROGATE_MODEL`: `'gbr'`
- `H2H_K_RANGE`: `(1, 10)`
- Keine offensichtliche Nutzung von Umgebungsvariablen erkannt.

## Interne Abhaengigkeiten / Imports

- `bartpy.sklearnmodel.SklearnModel`
- `math`
- `os`
- `pandas`
- `random`
- `sklearn.ensemble.GradientBoostingRegressor`
- `sklearn.impute.SimpleImputer`
- `sklearn.model_selection.KFold`
- `sklearn.model_selection.train_test_split`
- `sklearn.neural_network.MLPRegressor`
- `sklearn.pipeline.make_pipeline`
- `sklearn.preprocessing.StandardScaler`

## Beispiel

- Typischer Aufruf: ``python "Sports Api Data/Testruns/Code/AI_match_stats_prediction.py"``

## Edge Cases / Notes

- Unerwartete oder leere Quelldateien fuehren typischerweise zu fruehen Fehlern oder leeren DataFrames oder Listen.
- Bestehende Zieldateien koennen bei jedem Lauf ueberschrieben oder ergaenzt werden.

