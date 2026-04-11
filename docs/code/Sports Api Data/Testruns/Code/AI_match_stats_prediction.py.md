# `AI_match_stats_prediction.py`

Source: `Sports Api Data/Testruns/Code/AI_match_stats_prediction.py`

## Überblick
Erweitert ein Outcome‑Modell für Fußballspiele um eine leakage‑sichere, zweistufige Pipeline für Match‑Statistiken. Je nach Modus werden aktuelle Match‑Stats direkt verwendet, vorhergesagt oder komplett aus dem Outcome‑Modell entfernt.

## Zweck / Responsibilities
- Baut Pre‑Match‑Features (Teamstärke, Rolling‑Form, Head‑to‑Head, Kontext, Wetter).
- Optional: prognostiziert aktuelle Match‑Statistiken nur aus Pre‑Match‑Features (Out‑of‑Fold für Train, final für Predict).
- Trainiert ein Modell auf `GoalDiff = HomeGoals - AwayGoals` und leitet Win/Draw/Lose‑Wahrscheinlichkeiten ab.
- Führt mehrere Weight‑Runs aus, schreibt Run‑Outputs/Summaries und erzeugt eine Auswahl/Rangliste (Pareto bzw. Kandidatenranking).

## Wichtige Konfiguration (Top‑Level Konstanten)
- `PREDICTION_MODE`: Muss `'future'` oder `'reference'` sein (sonst `ValueError` beim Import/Start).
- `MATCH_STATS_MODE`: `'actual' | 'predicted' | 'off'` (in `future` ist `'actual'` verboten).
- Pfade: `DATA_PATH`, `TESTRUNS_PATH`, `FUTURE_OUTPUT_PATH`, `REFERENCE_OUTPUT_PATH`.
- Reproduzierbarkeit/Run‑Budget: `RANDOM_STATE`, `MAX_RUNS`.
- Match‑Stats‑Regressor: `MATCH_STATS_MODEL`, `MATCH_STATS_CV_SPLITS`, `MATCH_STATS_MIN_ROWS`.
- Surrogate‑Ranking: `SURROGATE_MODEL`, `SURROGATE_MIN_HISTORY`, `SURROGATE_CANDIDATES`, `SURROGATE_RANDOM_FRACTION`, `PARETO_TARGET_SIZE`.
- H2H‑Reliability‑Parameter: `H2H_K_RANGE`, `H2H_K_DEFAULT`.

## Wichtige Funktionen (Signaturen)
- `load_weather(path)`: Lädt/normalisiert Wetterdaten (spaltenbasiertes Rename) oder liefert leeres `DataFrame`.
- `coerce_numeric_columns(df_src, columns)`: Erzwingt numerische Typen für ausgewählte Spalten.
- `add_h2h_features(df_src)`, `apply_h2h_scaling(feature_df, k)`: Berechnet und skaliert Head‑to‑Head‑Features (Reliability‑Gewichtung).
- `add_team_asof_features(df_src, team_id_col, prefix)`: Erstellt as‑of Team‑Aggregationen (für Home/Away mit Prefix).
- `load_reference_results(primary_path, fallback_path=None)`, `try_backfill_reference_from_future(ref_results)`: Lädt/rekonstruiert Referenzergebnisse.
- `build_prediction_frame(df_src, ref_results, mode, future_limit=9, reference_limit=None)`: Baut das Trainings‑/Prediction‑Frame abhängig vom Modus.
- `make_match_stats_regressor()`, `build_match_stats_predictions(train_df, predict_df, feature_cols, target_cols)`: Modelliert Match‑Stats im Predicted‑Mode.
- `apply_match_stats_mode(train_df, predict_df, raw_predict_df)`: Schaltet zwischen `'actual'/'predicted'/'off'` um.
- `estimate_scoreline(match_row, predicted_goal_diff, predicted_result)`: Heuristik zur plausiblen Scoreline.
- `compute_pareto_front(df, nll_col='AvgNLL', acc_col='Accuracy')`, `build_pareto_decision_set(df, target_size=PARETO_TARGET_SIZE)`: Pareto‑Front/Decision‑Set (Reference‑Mode).
- `build_future_candidate_ranking(df, target_size=PARETO_TARGET_SIZE)`: Kandidatenranking (Future‑Mode, ggf. Surrogate‑Metriken).
- `load_run_history(path, weight_cols, match_stats_mode)`, `train_surrogate_model(history_df, feature_cols, target_col)`: Run‑History + Surrogate‑Training.

## Inputs / Outputs & Side‑Effects
**Inputs (Dateien)** – werden teils schon beim Import/Start gelesen:
- `DATA_PATH/match_statistics_filtered_78.csv`, `DATA_PATH/Stammdaten_78.csv`, `DATA_PATH/Teams_78.csv`
- Wetter: `WEATHER_HIST_PATH` (historisch) und `WEATHER_FUTURE_PATH` (wird im Output‑Verzeichnis geführt)
- Referenzergebnisse: `match_results_references.csv` (je nach Modus im Output‑Verzeichnis, mit Fallback in `DATA_PATH`)
- Run‑History: `surrogate_run_history.csv` (für Surrogate‑Ranking)

**Outputs (CSV im `OUTPUT_PATH`)**:
- `prediction_weight_runs.csv` (per‑Match‑Predictions pro Run)
- `prediction_weight_run_summary.csv` (Run‑Summary/Metriken)
- `surrogate_run_history.csv` (append/aktualisiert)
- `pareto_front.csv` (Reference) oder `future_candidate_ranking.csv` (Future)
- Optional: `future_outcome_table.csv`, `predicted_match_stats.csv`

**Side‑Effects**:
- Legt Output‑Ordner an, schreibt/überschreibt mehrere CSVs, nutzt Randomness (`random.seed(RANDOM_STATE)`), loggt in `stdout`.

## Interne Abhängigkeiten / Imports
- `pandas`
- `scikit-learn` (u.a. `GradientBoostingRegressor`, `MLPRegressor`, `KFold`, `SimpleImputer`, `StandardScaler`)
- `bartpy` (`bartpy.sklearnmodel.SklearnModel`)

## Beispiel (typischer Ablauf)
1) Oben in der Datei `PREDICTION_MODE` auf `'reference'` oder `'future'` setzen (und ggf. `MATCH_STATS_MODE` anpassen).
2) Script ausführen, z.B.: `python "Sports Api Data/Testruns/Code/AI_match_stats_prediction.py"`.

## Edge Cases / Notes
- Nicht import‑safe: liest Daten/legt Ordner an und wirft bei ungültigem `PREDICTION_MODE` sofort `ValueError`.
- `future` + `MATCH_STATS_MODE='actual'` ist explizit verboten (Match‑Stats vor Kickoff nicht verfügbar).
- Leere/fehlende Wetter‑ oder Referenzdaten werden über Fallbacks/Empty‑Frames gehandhabt; Match‑Stats‑Prediction benötigt eine Mindestanzahl Zeilen (`MATCH_STATS_MIN_ROWS`).

