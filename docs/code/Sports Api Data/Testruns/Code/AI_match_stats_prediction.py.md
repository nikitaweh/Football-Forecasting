# `AI_match_stats_prediction.py`

Source: `Sports Api Data/Testruns/Code/AI_match_stats_prediction.py`

## Ueberblick

Dieses Skript ist eine End-to-End-Pipeline fuer Bundesliga-Match-Vorhersagen.
Es erzeugt pro Match Wahrscheinlichkeiten fuer `H`/`D`/`A` und eine plausible Scoreline.

Wichtig: Das Outcome-Modell sagt nicht direkt Klassen voraus, sondern `GoalDiff = HomeGoals - AwayGoals`.
Aus dem vorhergesagten `GoalDiff` werden anschliessend Klassenwahrscheinlichkeiten abgeleitet.

Seit `FEATURE_SCHEMA_VERSION = 'bases_v3_player_workload'` ist die Outcome-Feature-Architektur so umgebaut, dass nicht mehr
ein flacher Feature-Vektor gewichtet wird, sondern 3 Basissignale (General/H2H/Player) plus Wetter als Kontext:

- `General_BaseSignal`: (Home - Away) aus Match-Stats-Subgruppen (inkl. xG), mit festen Subgruppen-Gewichten.
- `H2H_BaseSignal`: gewichtetes Signal aus H2H-Features (diese sind bereits relativ).
- `Player_BaseSignal`: gewichtetes Home-minus-Away Signal aus `Player_BaseDiff`, `Player_AbsencePenaltyDiff` und `Player_WorkloadDiff`.
- Wetter bleibt als Kontext (`Weather_*`) und wird direkt als gewichtete Input-Spalte in die Design-Matrix genommen.

## Ziele / Responsibilities

- Laedt und normalisiert Stammdaten, Match-Stats, Teamdaten und Wetterdaten.
- Baut Teamstaerke- und Form-Features (Baseline + Rolling L5) sowie H2H-Features (inkl. MatchCount).
- Unterstuetzt `PREDICTION_MODE`:
  - `reference`: bewertet Runs gegen Referenz-Ergebnisse.
  - `future`: erstellt Vorhersagen fuer kommende (ungespielte) Spiele.
- Unterstuetzt `MATCH_STATS_MODE`:
  - `actual`: nutzt vorhandene Match-Stats aus den Daten.
  - `predicted`: sagt Match-Stats aus Pre-Match-Features voraus (GBR pro Zielspalte).
  - `off`: entfernt Match-Stats aus dem Outcome-Signal (General-Signal wird 0; H2H/Wetter bleiben aktiv).
- Trainiert pro Kandidatenlauf ein BART-Regressionsmodell (bartpy) auf `GoalDiff`.
- Wandelt `GoalDiff` via Normalapproximation (Residual-Sigma) in `WinProb/DrawProb/LoseProb` um.
- Speichert Ergebnisse, Run-Summaries, Run-Historie und Entscheidungstabellen (Pareto/Ranking).
- Fuehrt eine Schema-Versionierung fuer Run-Historien ein, um alte und neue Gewichtsschemata sauber zu trennen.

## Datenquellen (Inputs)

Primaer (aus `DATA_PATH`):

- `match_statistics_filtered_78.csv`: Match-Statistiken (inkl. xG-Spalten).
- `Stammdaten_78.csv`: Match-Grunddaten (MatchID, Teams, Datum, Played).
- `Teams_78.csv`: Team-Metadaten.
- `historical_weather_data_78.csv`: historische Wetterdaten pro Match.
- optional im Output-Ordner: `weather_data.csv` (zusaetzliches Wetter, wird mit historischen Daten zusammengefuehrt).

Referenz-/Historieninputs (aus Output-Ordnern):

- `match_results_references.csv`: Referenz-Targets im `reference`-Modus.
- `surrogate_run_history.csv`: Historie frueherer Runs (Surrogate-Auswahl im `future`-Modus oder als Ranking-Basis).
- `prediction_weight_runs.csv` + `prediction_weight_run_summary.csv`: gespeicherte Future-Runs fuer spaeteres Backfill-Scoring.

## Outputs (Artefakte)

- `prediction_weight_runs.csv`: Pro Match und Run: Wahrscheinlichkeiten, PredictedGoalDiff, Scoreline, Gewichte, Basissignale.
- `prediction_weight_run_summary.csv`: Pro Run: AvgNLL, Accuracy, H2H_K, Confidence-Metriken, Gewichte.
- `surrogate_run_history.csv`: Append-only Historie fuer Surrogate (mit Dedupe).
- `predicted_match_stats.csv`: Export prognostizierter Match-Stats (nur bei `MATCH_STATS_MODE='predicted'`).
- `pareto_front.csv`: Pareto-/Decision-Set im `reference`-Modus.
- `future_candidate_ranking.csv`: Kandidatenranking und Empfehlungen im `future`-Modus.
- `future_outcome_table.csv`: komprimierte Empfehlung fuer die ausgewaehlte Run-Konfiguration (nur `future`).
- `future_vs_reference_metrics.csv`: Backfill-Auswertungen, wenn gespeicherte Future-Runs spaeter gegen Referenzen gescored werden.
  Die Datei enthaelt zusaetzlich Evaluations-Raenge (`EvalRank_*`) und markiert nur dann einen `EvalRank_Combined`,
  wenn sowohl NLL- als auch Accuracy-Raenge fuer den Snapshot wirklich bestimmbar sind.

## Konfiguration (Wichtigste Konstanten)

- Pfade: `DATA_PATH`, `TESTRUNS_PATH`, `FUTURE_OUTPUT_PATH`, `REFERENCE_OUTPUT_PATH`.
- Modi: `PREDICTION_MODE` und `MATCH_STATS_MODE`.
- Match-Stats-Prediction: `MATCH_STATS_MODEL`, `MATCH_STATS_CV_SPLITS`, `MATCH_STATS_MIN_ROWS`.
- Sampling: `MAX_RUNS`, `RANDOM_STATE`.
- Surrogate: `SURROGATE_MODEL`, `SURROGATE_MIN_HISTORY`, `SURROGATE_CANDIDATES`, `SURROGATE_RANDOM_FRACTION`.
- H2H: `H2H_K_RANGE`, `H2H_K_DEFAULT`.
- Schema: `FEATURE_SCHEMA_VERSION` (wird in Outputs und Run-Historie geschrieben und gefiltert).

### Relevante Env-Overrides

- `MAX_RUNS_OVERRIDE`: ueberschreibt `MAX_RUNS`, damit der Backtest-Treiber die Anzahl getesteter Gewichtsläufe pro Matchday begrenzen kann.
- `BACKTEST_DATE_CUTOFF`: schneidet das Trainingsset auf Matches mit `MatchDate < cutoff` zurück und verhindert so Future-Leakage in historischen Matchday-Backtests.
- `MATCH_STATS_MODE_OVERRIDE`: erzwingt z. B. `predicted`, damit Referenz- oder Backtest-Laeufe keine Ist-Statistiken des vorherzusagenden Spiels verwenden.
- `OUTCOME_PROBABILITY_MODE=draw_multilayer_overlay`: aktiviert einen opt-in Draw-Overlay nach der normalen GoalDiff-Wahrscheinlichkeit.
- `DRAW_OVERLAY_ALPHA`, `DRAW_OVERLAY_MIN_PROB`, `DRAW_OVERLAY_MAX_PROB`, `DRAW_OVERLAY_GOALDIFF_SCALE`, `DRAW_OVERLAY_SIGNAL_SCALE`, `DRAW_OVERLAY_TOTAL_GOALS_CAP`: steuern Staerke, Grenzen und Skalen dieses Overlays.

Die Env-Overrides greifen frueh beim Modulimport. Falsche Werte fallen daher nicht erst spaet im Trainingsloop auf, sondern koennen bereits beim Start zu inkonsistentem Verhalten fuehren.

## Pipeline Schritt fuer Schritt

### 1) Laden, Umbenennen, Mergen

1. CSVs werden geladen.
2. Spalten werden auf ein gemeinsames Schema umbenannt.
3. Der Merge startet absichtlich bei `Stammdaten_78.csv`, damit auch ungespielte Matches erhalten bleiben.
4. Wetter wird aus historisch + optional zukuenftig zusammengefuehrt und per `MatchID` gemerged.

Wichtige Details:

- xG wird explizit auf `HomeXG` / `AwayXG` umbenannt. Fehlende Werte bleiben `NaN` und werden spaeter per Median-Imputation behandelt.
- `df['MatchDate']` wird zu `datetime` konvertiert, da viele Features (H2H, Rolling L5) zeitbasiert sind.

### 2) Pre-Match Features (Teamstaerke, Form, H2H)

Team-Features:

- Baseline-Staerke pro Team: Mittelwerte ueber alle historischen Spiele.
- Rolling-Form: L5-Mittelwerte mit `shift(1)` fuer Leakage-Sicherheit.

H2H-Features:

- Kombiniert und Venue-basiert (Home vs. Away), jeweils mit `MatchCount`.
- `apply_h2h_scaling` skaliert H2H-Werte im Outcome-Training mit `alpha = MatchCount / (MatchCount + k)`.

### 3) Split in Train vs. Predict

- Train: `Played == True`.
- Predict: je nach Modus:
  - `reference`: MatchIDs aus `match_results_references.csv`.
  - `future`: naechste ungespielte Matches nach Datum (Hard-Limit `future_limit=9` in `build_prediction_frame`).

Backtest-Schutz:

- Im `reference`-Modus werden die Ziel-MatchIDs zunaechst aus dem Trainingsset entfernt.
- Wenn `BACKTEST_DATE_CUTOFF` gesetzt ist, filtert das Skript anschliessend alle Trainingsmatches mit `MatchDate >= cutoff` heraus.
- Der Lauf schreibt dazu eine explizite Reduktion `before -> after` auf `stdout`; daran laesst sich sofort erkennen, ob der Cutoff versehentlich zu aggressiv war.

### 4) Match-Stats-Modus anwenden (actual/predicted/off)

Die Funktion `apply_match_stats_mode(...)` entscheidet, welche Input-Spalten fuer das Outcome-Signal zusaetzlich verfuegbar sind:

- `off`: keine Match-Stats; General-Signal wird spaeter 0.0.
- `actual`: Match-Stats-Spalten kommen aus `df` (soweit vorhanden).
- `predicted`: `build_match_stats_predictions(...)` sagt jede Match-Stats-Zielspalte via GBR voraus.

`build_match_stats_predictions(...)` Details:

- Pro Zielspalte wird nur dann ein Modell trainiert, wenn genug Beobachtungen und Varianz vorhanden sind.
- Out-of-Fold (KFold) wird genutzt, um Leakage im Train-Set zu vermeiden.
- Fallback fuer Rest/Edge-Cases ist der Median der beobachteten Zielwerte.
- `postprocess_match_stats(...)` normalisiert Prozentwerte (0..100) und rundet Count-Features; xG wird nicht gerundet.

### 5) Outcome-Architektur: 3 Basen + Kontext

Aus dem (imputierten) Input-DataFrame wird eine Design-Matrix gebaut:

- `General_BaseSignal`
- `H2H_BaseSignal`
- `Player_BaseSignal` (aus Player-Form, Absenz-Penalty und zeitnaher Spielerbelastung)
- plus Wetter-Kontextspalten `Weather_*`

Signaldefinition:

- General-Signal: Home-minus-Away Differenzen pro Subgruppe, dann Blend:
  - `GoalCreation` (xG, ShotsOnTarget, Shots)
  - `GameControl` (Possession, Passes, PassAccuracy)
  - `DisciplineSetPiece` (Fouls, Karten, Corners, Offsides; teils invertiert, weil mehr Fouls/Karten meist negativ sind)
- H2H-Signal: gewichtete Kombination der vorhandenen relativen H2H-Features.
- Player-Signal: gewichtete Kombination aus:
  - `Player_BaseDiff` (Home-PlayerScore minus Away-PlayerScore)
  - `Player_AbsencePenaltyDiff` (Away-Absenzpenalty minus Home-Absenzpenalty)
  - `Player_WorkloadDiff` (Away-Belastung minus Home-Belastung; Bundesliga-Minuten plus Pflichtspiel-Minuten der Nationalmannschaft)
- Wetter: bleibt absolut (keine Home/Away Differenz).

### 5a) Player-Base im aktuellen Stand

- `build_player_base_features(df_src)` verarbeitet Lineups, Injuries und Player-Stats in einem eigenen Teilgraphen.
- `PlayerMatchScore` wird aus Toren, Assists, Schuessen, Defensivaktionen, Karten und Rating aufgebaut.
- Die Rolling-Logik nutzt `shift(1)` und ist damit auf Spieler-Ebene leakage-sicher.
- Fuer gespielte Matches wird die tatsaechliche Startelf aus `lineups_league_78.csv` verwendet.
- Fuer ungespielte Matches wird ein Kaderprofil mit historischen Startwahrscheinlichkeiten approximiert.
- Die Absenzkomponente ist als echte Hilfsfunktion `compute_absence_penalty(...)` zentralisiert.
- Dadurch nutzen Played- und Future-Zweig dieselbe Bewertungslogik fuer verletzte Spieler.
- Fallbacks laufen gestuft ueber Team-Positions-Median, Team-Median, Positions-Median und globalen Median.
- Diese Fallback-Kaskade macht den Player-Zweig robust gegen duenne Spielerhistorien, reduziert aber die Interpretierbarkeit einzelner Scores.

### 6) Gewichtsschema (Hybrid)

Das Skript sampelt nicht mehr `Weight_<jede Feature-Spalte>`, sondern Gewichte fuer:

1. Subgruppen-Features in `GENERAL_SIGNAL_GROUP_SPECS` (z.B. `General_GoalCreation_XG`).
2. H2H-Features in `H2H_SIGNAL_SPECS` (z.B. `H2H_H2H_Combined_AvgGoalDiff`).
3. Wetter-Kontext in `WEATHER_CONTEXT_SPECS` (z.B. `WeatherContext_Weather_Temperature_C`).
4. Base-Multiplikatoren:
   - `BaseMultiplier_General`
   - `BaseMultiplier_H2H`
   - `BaseMultiplier_Player`

Diese Parameterliste kommt aus `collect_weight_parameter_names(MATCH_STATS_MODE)`.
Im `MATCH_STATS_MODE='off'` werden die General-Parameter nicht gesampelt/verwendet.

### 7) Training pro Run

Pro Kandidatenlauf:

1. `k` wird gesampelt bzw. aus Kandidaten gesetzt.
2. `apply_h2h_scaling` skaliert H2H-Inputs mit `k`.
3. Median-Imputation auf alle Input-Spalten.
4. `build_outcome_design_matrix(...)` baut die finalen Features (Basissignale + Wetter-Kontext) und wendet Gewichte an.
5. BART-Regression auf `GoalDiff` mit `SklearnModel(n_trees=200, n_jobs=1)`.
6. Residual-Sigma wird aus Train-Residuals geschaetzt.
7. Vorhersage `mu` (GoalDiff) -> `WinProb/DrawProb/LoseProb` via Normalapproximation.
8. Optionaler Probability-Overlay:
   - Score-Distribution-Modi koennen H/D/A aus Expected Goals ableiten.
   - `draw_multilayer_overlay` hebt DrawProb nur dann an, wenn GoalDiff/Basissignale, Score-Erwartung, Match-Stats-Gaps und Disziplin-Layer ausreichend aehnlich sind. Die bestehende Home/Away-Ratio wird dabei erhalten.

Warum `n_jobs=1`:

- Das Skript vermeidet damit Multiprocessing-/Pipe-Probleme auf restriktiven Hosts.
- Die Erhoehung von `n_trees` auf `200` verbessert die Modellkapazitaet, erhoeht aber die Laufzeit pro Run entsprechend. Bei Backtests ist deshalb `MAX_RUNS_OVERRIDE` der naheliegende Gegenhebel.

### 8) Bewertung und Auswahl

Reference-Modus:

- `AvgNLL` und `Accuracy` werden gegen Referenz-Resultate berechnet.
- Entscheidungstabelle ueber `build_pareto_decision_set(...)`.

Future-Modus:

- Wenn genug Historie vorhanden ist: Surrogate-Modell schaetzt NLL/Accuracy fuer Kandidaten.
- Sonst: Confidence-Fallback-Ranking ueber TopProb/Gap/Entropy.
- `future_outcome_table.csv` wird fuer den ausgewaehlten Run erstellt.
- `append_future_vs_reference_metrics(...)` fuegt spaetere Referenz-Scores an vorhandene Future-Runs an und berechnet
  kombinierte Eval-Raenge nur fuer Snapshots mit nutzbaren Einzelraengen.

### Spezifisch zu `append_future_vs_reference_metrics(...)`

- Die Funktion haengt pro Evaluationslauf einen Snapshot mit `EvaluationTimestamp` und Delta-Metriken an.
- `Delta_AvgNLL_vs_Pred` und `Delta_Accuracy_vs_Pred` vergleichen spaetere Realwerte mit der zuvor geschaetzten Surrogate-Prognose.
- `Delta_Resolved*`-Spalten messen die Abweichung zwischen aufgeloesten/aggregierten Kennzahlen und den tatsaechlich beobachteten Kennzahlen.
- Die kombinierte Bewertung `EvalRank_Combined` wird nur noch dann berechnet, wenn sowohl NLL- als auch Accuracy-Raenge eine verwertbare Maximalzahl besitzen.
- Falls eine der Rangspalten komplett leer ist, markiert die Funktion den kombinierten Rang bewusst als `NaN` statt per `fillna(max+1)` kuenstlich gueltige Sieger zu erzeugen.

## Run-Historie und Schema-Versionierung

Warum:

- Das neue Weight-Schema ist nicht kompatibel zu aelteren `Weight_<Feature>`-Runs.

Wie:

- `FeatureSchemaVersion` wird in:
  - `prediction_weight_runs.csv` (pro Match/Run),
  - `prediction_weight_run_summary.csv` (pro Run),
  - `surrogate_run_history.csv` (Historie)
  geschrieben.
- `load_run_history(...)` kann nach `FeatureSchemaVersion` filtern, und der Main-Loop uebergibt `FEATURE_SCHEMA_VERSION`.
- `append_to_run_history(...)` dedupliziert u.a. auch nach `FeatureSchemaVersion`.

## Troubleshooting / typische Stolperfallen

- xG ist oft teilweise leer: das ist ok, solange Imputation aktiv ist.
- `future` + `MATCH_STATS_MODE='actual'` ist nicht erlaubt (keine echten Match-Stats vor Anpfiff).
- Wenn `match_results_references.csv` MatchIDs enthaelt, die nicht in `df` vorkommen: `build_prediction_frame` wirft einen Fehler.
- Player-Features haengen von `lineups_league_78.csv`, `injuries_league_78.csv` und `player_statistics_per_fixture_league_78.csv` ab.
- Falls ein Backfill-Snapshot nur `AvgNLL` oder nur `Accuracy` liefern kann, bleibt `EvalRank_Combined = NaN` und
  `EvalIsBestCombined = False`; das verhindert kuenstlich erzeugte Sieger durch `fillna(max+1)` auf komplett leeren Rangspalten.
- Ein zu frueher `BACKTEST_DATE_CUTOFF` kann das Trainingsset bis auf wenige Zeilen reduzieren; dann verschlechtern sich Match-Stats-Prognose, Sigma-Schaetzung und Outcome-Stabilitaet gleichzeitig.
- `MATCH_STATS_MODE_OVERRIDE='predicted'` ist fuer Backtests sinnvoll, kann aber die Vergleichbarkeit zu aelteren Runs mit `actual` verschieben; die Auswertung sollte deshalb immer `MatchStatsMode` und `FeatureSchemaVersion` gemeinsam betrachten.
- Durch `n_trees=200` steigen Laufzeit und CPU-Bedarf pro Kandidatenlauf. Wenn ein Host knapp dimensioniert ist, ist eine Begrenzung der Run-Anzahl sauberer als wieder kleinere Modelle einzubauen.

## Wichtige Funktionen (gezielt)

- `apply_match_stats_mode(train_df, predict_df, raw_predict_df)`: waehlt und erzeugt die Match-Stats-Inputs fuer den Outcome-Teil der Pipeline.
- `build_match_stats_predictions(...)`: trainiert pro Zielspalte ein separates Prognosemodell mit Out-of-Fold-Schutz fuer das Trainingsset.
- `build_player_base_features(df_src)`: baut Spielerstaerke und Absenz-Signale aus Lineups, Injuries und per-Player-Rolling-Scores.
- `build_outcome_design_matrix(X, weights, match_stats_mode)`: verdichtet Rohfeatures in das hybride Basissignal-Schema plus Wetterkontext.
- `append_to_run_history(history_path, summary_df)`: fuegt Run-Summaries mit Deduplizierung und Schema-Versionierung an die Historie an.
- `append_future_vs_reference_metrics(metrics_path, summary_df)`: fuegt Backfill-/Evaluationsmetriken an und berechnet robuste Eval-Raenge.
- `try_backfill_reference_from_future(ref_results)`: nimmt gespeicherte Future-Predictions, matched sie gegen spaetere Referenzen und verhindert Doppelimporte ueber einen robusteren Identitaetsschluessel aus `BatchID`, `RunID`, `MatchID` sowie - falls vorhanden - `FeatureSchemaVersion` und `MatchStatsMode`.
- `build_prediction_frame(...)`: bestimmt die Zielmatches fuer `reference` oder `future` und ist die zentrale Guard-Stelle fuer fehlende MatchIDs.

## Inputs / Outputs & Side-Effects

Inputs:

- CSV-Dateien unter `Sports Api Data/Bundesliga/Filtered/Datacollection`.
- Referenz- und Historienartefakte unter `Sports Api Data/Testruns/Datacollection reference` bzw. `... future`.
- Optionale Env-Overrides fuer Backtests und Match-Stats-Modus.

Outputs:

- Mehrere CSV-Artefakte fuer Predictions, Run-Summaries, Historie, Entscheidungstabellen und Backfill-Metriken.
- Konsolenlogs fuer Training, Datenfilterung, Modellguete und Backfill-Ergebnisse.

Side-Effects:

- Legt Output-Ordner automatisch an.
- Ueberschreibt bzw. erweitert bestehende CSV-Dateien.
- Fuehrt potentiell lange Modelllaeufe mit zufallsbasiertem Sampling aus, allerdings reproduzierbar über `RANDOM_STATE`.

## Ausfuehren (Beispiel)

```bash
python "Sports Api Data/Testruns/Code/AI_match_stats_prediction.py"
```

Empfohlener Check nach einem Lauf:

1. `Sports Api Data/Testruns/Datacollection reference/prediction_weight_run_summary.csv` (Reference-Run-Metriken).
2. `Sports Api Data/Testruns/Datacollection reference/pareto_front.csv` (Decision-Set).
3. `Sports Api Data/Testruns/Datacollection reference/surrogate_run_history.csv` (Historie inkl. `FeatureSchemaVersion`).

## Aktuelle Code-Referenz

### Ueberblick und Zweck

Erzeugt Spielprognosen und bewertet Ergebniswahrscheinlichkeiten anhand der konfigurierten Modell- und Datenpfade.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `load_weather(path)`
  Verwendet `os.path.exists`, `pd.DataFrame`, `pd.read_csv`, `w.rename`. Rueckgabe unter anderem: `w`.
- `coerce_numeric_columns(df_src, columns)`
  Verwendet `pd.to_numeric`.
- `summarize_h2h(subset)`
  Verwendet `float`, `goal_diff.mean`, `subset['GoalsFor'].mean`, `subset['GoalsAgainst'].mean`. Rueckgabe unter anderem: `{'AvgGoalDiff': float(goal_diff.mean()), 'AvgGoalsFor': float(subset['GoalsFor'].mean()), 'AvgGoa...`.
- `add_h2h_features(df_src)`
  Verwendet `df_src[df_src['MatchDate'].notna()].copy`, `df_src['MatchDate'].notna`, `base.iterrows`, `pd.isna`. Rueckgabe unter anderem: `pd.DataFrame(out_rows)`.
- `apply_h2h_scaling(feature_df, k)`
  Verwendet `feature_df.copy`. Rueckgabe unter anderem: `df_scaled`.
- `build_player_base_features(df_src)`
  Verwendet `df_src[['MatchID', 'MatchDate', 'HomeTeamID', 'AwayTeamID', 'HomeTe...`, `os.path.exists`, `pd.DataFrame`, `pd.read_csv`. Rueckgabe unter anderem: `out[result_cols]`.
- `add_team_asof_features(df_src, team_id_col, prefix)`
  Verwendet `df_src[df_src['MatchDate'].notna()].copy`, `df_src['MatchDate'].notna`, `base.groupby`, `grp[['MatchID']].copy`. Rueckgabe unter anderem: `out`.
- `load_reference_results(primary_path, fallback_path=None)`
  Verwendet `os.path.exists`, `pd.read_csv`, `{'MatchID', 'HomeGoals', 'AwayGoals'}.issubset`, `required.issubset`. Rueckgabe unter anderem: `None`.
- `read_optional_csv(path)`
  Verwendet `os.path.exists`, `pd.DataFrame`, `pd.read_csv`. Rueckgabe unter anderem: `pd.DataFrame()`.
- `first_non_null_value(values, default_value=float('nan'))`
  Verwendet `float`, `pd.notna`. Rueckgabe unter anderem: `default_value`.
- `ensure_outcome_probability_metadata(df, mode_default='normal')`
  Verwendet `df['OutcomeProbabilityMode'].fillna(mode_default).astype`, `df['OutcomeProbabilityMode'].fillna`, `SCORE_PROBABILITY_PARAM_DEFAULTS.items`, `pd.to_numeric(df[col], errors='coerce').fillna`. Rueckgabe unter anderem: `df`.
- `filter_outcome_probability_config(df, outcome_mode, score_total_scale, score_rho, score_alpha, draw_overlay_alpha=None, draw_overlay_min_prob=None, draw_overlay_max_prob=None, draw_overlay_goaldiff_scale=None, draw_overlay_signal_scale=None, draw_overlay_total_goals_cap=None)`
  Verwendet `ensure_outcome_probability_metadata`, `df.copy`, `filtered[filtered['OutcomeProbabilityMode'] == outcome_mode].copy`, `pd.to_numeric`. Rueckgabe unter anderem: `filtered`.
- `outcome_from_goals(home_goals, away_goals)`
  Verwendet `pd.isna`, `float`. Rueckgabe unter anderem: `'D'`.
- `prepare_run_summary(summary_df)`
  Verwendet `summary_df.copy`, `pd.to_numeric`, `prepared['MatchedReferenceCount'].fillna`, `pd.Series`. Rueckgabe unter anderem: `prepared`.
- `append_to_run_history(history_path, summary_df)`
  Verwendet `read_optional_csv`, `ensure_outcome_probability_metadata`, `summary_df.copy`, `new_summary.copy`. Rueckgabe unter anderem: `history_updated`.
- `append_future_vs_reference_metrics(metrics_path, summary_df)`
  Append a per-run evaluation snapshot when saved future predictions are scored against reference results (AvgNLL/Accuracy). Creates the CSV if missing.
- `try_backfill_reference_from_future(ref_results)`
  Verwendet `pd.DataFrame`, `read_optional_csv`, `future_runs.copy`, `ensure_outcome_probability_metadata`. Rueckgabe unter anderem: `(all_pred_df, summary_df)`.
- `build_prediction_frame(df_src, ref_results, mode, future_limit=9, reference_limit=None)`
  Verwendet `ValueError`, `pd.Index`, `df_src[df_src['MatchID'].isin(ref_ids)].copy`, `df_src['MatchID'].isin`. Rueckgabe unter anderem: `pred`.
- `make_match_stats_regressor()`
  Verwendet `ValueError`, `GradientBoostingRegressor`. Rueckgabe unter anderem: `GradientBoostingRegressor(random_state=RANDOM_STATE)`.
- `fit_match_stats_estimator(x_train, y_train)`
  Verwendet `SimpleImputer`, `imputer.fit_transform`, `make_match_stats_regressor`, `model.fit`. Rueckgabe unter anderem: `(imputer, model)`.
- `postprocess_match_stats(pred_df)`
  Verwendet `pred_df.copy`, `pd.to_numeric(processed[col], errors='coerce').clip`, `pd.to_numeric`, `{'HomePossession', 'AwayPossession'}.issubset`. Rueckgabe unter anderem: `processed`.
- `build_match_stats_predictions(train_df, predict_df, feature_cols, target_cols)`
  Verwendet `pd.DataFrame`, `pd.to_numeric`, `y_full.notna`, `int`. Rueckgabe unter anderem: `(train_pred, predict_pred, summary_df)`.
- `apply_match_stats_mode(train_df, predict_df, raw_predict_df)`
  Verwendet `train_df.copy`, `predict_df.copy`, `pd.DataFrame`, `build_match_stats_predictions`. Rueckgabe unter anderem: `(train_enriched, predict_enriched, outcome_features_with_match_stats, predicted_stats_output, mat...`.
- `resolve_weight_value(weight_map, key, default_value=1.0)`
  Verwendet `weight_map.get`, `float`, `math.isfinite`. Rueckgabe unter anderem: `value`.
- `collect_weight_parameter_names(match_stats_mode)`
  Verwendet `GENERAL_SIGNAL_GROUP_SPECS.values`, `params.extend`. Rueckgabe unter anderem: `params`.
- `weighted_signal_from_specs(signal_df, specs, weight_map)`
  Verwendet `pd.Series`, `resolve_weight_value`, `pd.to_numeric`, `spec.get`. Rueckgabe unter anderem: `weighted_sum / total_weight`.
- `build_outcome_design_matrix(signal_df, weight_map, match_stats_mode)`
  Verwendet `pd.DataFrame`, `pd.Series`, `GENERAL_SIGNAL_GROUP_SPECS.items`, `weighted_signal_from_specs`. Rueckgabe unter anderem: `design`.
- `mean_available(values, default_value=1.25)`
  Verwendet `float`, `pd.notna`, `sum`, `len`. Rueckgabe unter anderem: `float(sum(valid) / len(valid))`.
- `estimate_scoreline(match_row, predicted_goal_diff, predicted_result)`
  Verwendet `mean_available`, `match_row.get`, `max`, `int`. Rueckgabe unter anderem: `(float(exp_home), float(exp_away), int(pred_home_goals), int(pred_away_goals))`.
- `poisson_goal_pmf(lam, max_goals)`
  Verwendet `max`, `min`, `float`, `math.exp`. Rueckgabe unter anderem: `probs`.
- `score_distribution_outcome_probs(expected_home_goals, expected_away_goals, mode)`
  Verwendet `max`, `float`, `poisson_goal_pmf`, `enumerate`. Rueckgabe unter anderem: `(p_home / total, p_draw / total, p_away / total)`.
- `blend_outcome_probabilities(base_h, base_d, base_a, score_h, score_d, score_a, mode)`
  Verwendet `any`, `math.isfinite`, `mode.endswith`. Rueckgabe unter anderem: `(p_h / total, p_d / total, p_a / total)`.
- `apply_score_distribution_probabilities(pred_df)`
  Verwendet `pred_df.copy`, `adjusted.iterrows`, `score_distribution_outcome_probs`, `blend_outcome_probabilities`. Rueckgabe unter anderem: `adjusted`.
- `draw_overlay_float(value, default_value=float('nan'))`
  Verwendet `float`, `math.isfinite`. Rueckgabe unter anderem: `num`.
- `draw_overlay_clamp(value, low=0.0, high=1.0)`
  Verwendet `draw_overlay_float`, `max`, `float`, `min`. Rueckgabe unter anderem: `max(float(low), min(float(high), num))`.
- `draw_overlay_similarity(value, scale)`
  Verwendet `max`, `draw_overlay_float`, `math.exp`, `abs`. Rueckgabe unter anderem: `math.exp(-abs(draw_overlay_float(value, 0.0)) / scale_value)`.
- `draw_overlay_weighted_mean(parts, default_value=0.5)`
  Verwendet `draw_overlay_float`, `math.isfinite`, `float`, `draw_overlay_clamp`. Rueckgabe unter anderem: `draw_overlay_clamp(weighted_sum / total_weight)`.
- `draw_overlay_pair_similarity(row, home_col, away_col, scale)`
  Verwendet `row.get`, `float`, `pd.isna`, `draw_overlay_similarity`. Rueckgabe unter anderem: `draw_overlay_similarity(draw_overlay_float(home_value, 0.0) - draw_overlay_float(away_value, 0.0)...`.
- `draw_overlay_signal_scales(pred_df)`
  Verwendet `pd.to_numeric(pred_df[col], errors='coerce').abs().dropna`, `pd.to_numeric(pred_df[col], errors='coerce').abs`, `pd.to_numeric`, `float`. Rueckgabe unter anderem: `scales`.
- `draw_overlay_strength_layer(row, signal_scales)`
  Verwendet `draw_overlay_similarity`, `row.get`, `parts.append`, `signal_scales.get`. Rueckgabe unter anderem: `draw_overlay_weighted_mean(parts, default_value=0.5)`.
- `draw_overlay_score_layer(row)`
  Verwendet `draw_overlay_float`, `row.get`, `math.isfinite`, `draw_overlay_similarity`. Rueckgabe unter anderem: `draw_overlay_weighted_mean([(goal_gap_similarity, 0.7), (high_total_penalty, 0.3)])`.
- `draw_overlay_stats_layer(row)`
  Verwendet `draw_overlay_weighted_mean`, `draw_overlay_pair_similarity`. Rueckgabe unter anderem: `draw_overlay_weighted_mean([(draw_overlay_pair_similarity(row, 'HomeXG', 'AwayXG', 0.8), 0.25), (...`.
- `draw_overlay_discipline_layer(row)`
  Verwendet `draw_overlay_weighted_mean`, `draw_overlay_pair_similarity`, `row.get`, `float`. Rueckgabe unter anderem: `draw_overlay_weighted_mean([(balance_layer, 0.7), (load_layer, 0.3)])`.
- `draw_overlay_candidate(row, signal_scales)`
  Verwendet `draw_overlay_strength_layer`, `draw_overlay_score_layer`, `draw_overlay_stats_layer`, `draw_overlay_discipline_layer`. Rueckgabe unter anderem: `{'DrawOverlay_StrengthLayer': strength_layer, 'DrawOverlay_ScoreLayer': score_layer, 'DrawOverlay...`.
- `apply_draw_multilayer_overlay(pred_df)`
  Verwendet `pred_df.copy`, `draw_overlay_signal_scales`, `adjusted.iterrows`, `draw_overlay_float`. Rueckgabe unter anderem: `adjusted`.
- `apply_outcome_probability_adjustment(pred_df)`
  Verwendet `apply_score_distribution_probabilities`, `apply_draw_multilayer_overlay`. Rueckgabe unter anderem: `pred_df`.
- `compute_pareto_front(df, nll_col='AvgNLL', acc_col='Accuracy')`
  Verwendet `df.dropna(subset=[nll_col, acc_col]).copy`, `df.dropna`, `base.sort_values`, `float`. Rueckgabe unter anderem: `pd.DataFrame(pareto_rows)`.
- `build_pareto_decision_set(df, target_size=PARETO_TARGET_SIZE)`
  Verwendet `compute_pareto_front`, `df.copy`, `float`, `pd.to_numeric`. Rueckgabe unter anderem: `decision`.
- `rank_component(series, smaller_is_better=False)`
  Verwendet `pd.to_numeric`, `pd.Series`, `float`, `values.notna`. Rueckgabe unter anderem: `ranked`.
- `build_future_candidate_ranking(df, target_size=PARETO_TARGET_SIZE)`
  Verwendet `df.copy`, `float`, `pd.to_numeric`, `ranked['Pred_AvgNLL'].notna`. Rueckgabe unter anderem: `decision`.
- `build_ensemble_outcome_table(all_pred_df, ensemble_run_ids, k_used)`
  Average top-K runs' per-match predictions into one ensemble outcome table.
- `drop_empty_weight_columns(df)`
  Verwendet `df.copy`, `c.startswith`, `cleaned[col].notna().sum`, `cleaned[col].notna`. Rueckgabe unter anderem: `cleaned`.
- `persist_decision_table(decision_df, output_path)`
  Verwendet `pd.DataFrame`, `read_optional_csv`, `print`, `decision_df.to_csv`. Rueckgabe unter anderem: `cleaned`.
- `_safe_float(value, default_value=float('nan'))`
  Verwendet `float`, `math.isfinite`. Rueckgabe unter anderem: `num`.
- `_mean_valid(values, default_value=1.0)`
  Verwendet `float`, `pd.notna`, `sum`, `len`. Rueckgabe unter anderem: `float(sum(valid) / len(valid))`.
- `_legacy_weight(row, suffix, default_value=float('nan'))`
  Verwendet `float`, `_safe_float`, `row.get`. Rueckgabe unter anderem: `_safe_float(row.get(f'Weight_{suffix}'), default_value)`.
- `_history_row_key(row, key_cols)`
  Verwendet `row.get`, `float`, `pd.isna`, `key.append`. Rueckgabe unter anderem: `tuple(key)`.
- `migrate_legacy_history_to_hybrid(history_df, target_schema_version)`
  Verwendet `history_df.copy`, `ensure_outcome_probability_metadata`, `_history_row_key`, `existing_target.iterrows`. Rueckgabe unter anderem: `(updated, len(migrated_rows))`.
- `ensure_migrated_history_schema(history_path, target_schema_version)`
  Verwendet `read_optional_csv`, `ensure_outcome_probability_metadata`, `migrate_legacy_history_to_hybrid`, `migrated_history.to_csv`. Rueckgabe unter anderem: `migrated_count`.
- `load_run_history(path, weight_cols, match_stats_mode, source_prediction_mode=None, feature_schema_version=None, outcome_probability_mode=None, score_probability_total_scale=None, score_probability_rho=None, score_probability_alpha=None, draw_overlay_alpha=None, draw_overlay_min_prob=None, draw_overlay_max_prob=None, draw_overlay_goaldiff_scale=None, draw_overlay_signal_scale=None, draw_overlay_total_goals_cap=None)`
  Verwendet `os.path.exists`, `pd.DataFrame`, `pd.read_csv`, `ensure_outcome_probability_metadata`. Rueckgabe unter anderem: `hist`.
- `train_surrogate_model(history_df, feature_cols, target_col)`
  Verwendet `make_pipeline`, `StandardScaler`, `MLPRegressor`, `GradientBoostingRegressor`. Rueckgabe unter anderem: `model`.
- `generate_candidate_df(num, weight_parameter_names, k_range)`
  Verwendet `range`, `random.random`, `random.randint`, `int`. Rueckgabe unter anderem: `pd.DataFrame(rows)`.
- `select_candidates_with_surrogate(candidates_df, pred_nll, pred_acc, max_runs, random_frac)`
  Verwendet `candidates_df.copy`, `compute_pareto_front`, `pareto.sort_values`, `int`. Rueckgabe unter anderem: `selected.reset_index(drop=True)`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `os.environ.get('MAX_RUNS_OVERRIDE', '')`
- `os.environ.get('BACKTEST_DATE_CUTOFF', '')`
- `os.environ.get('MATCH_STATS_MODE_OVERRIDE', '')`
- `os.environ.get('FUTURE_ENSEMBLE_ENABLED', '')`
- `os.environ.get('FUTURE_ENSEMBLE_K_OVERRIDE', '')`
- `os.environ.get('DISABLE_PLAYER_WORKLOAD', '')`
- `os.environ.get('OUTCOME_PROBABILITY_MODE', 'normal')`
- `os.environ.get('SCORE_PROBABILITY_TOTAL_SCALE', '1.0')`
- `os.environ.get('SCORE_PROBABILITY_RHO', '0.0')`
- `os.environ.get('SCORE_PROBABILITY_ALPHA', '1.0')`
- `os.environ.get('SCORE_PROBABILITY_MAX_GOALS', '10')`
- `os.environ.get('DRAW_OVERLAY_ALPHA', '0.60')`
- `os.environ.get('DRAW_OVERLAY_MIN_PROB', '0.14')`
- `os.environ.get('DRAW_OVERLAY_MAX_PROB', '0.36')`
- `os.environ.get('DRAW_OVERLAY_GOALDIFF_SCALE', '0.90')`
- `os.environ.get('DRAW_OVERLAY_SIGNAL_SCALE', '1.00')`
- `os.environ.get('DRAW_OVERLAY_TOTAL_GOALS_CAP', '2.60')`
- `pd.read_csv(os.path.join(DATA_PATH, 'match_statistics_filtered_78.csv'))`
- `pd.read_csv(os.path.join(DATA_PATH, 'Stammdaten_78.csv'))`
- `pd.read_csv(os.path.join(DATA_PATH, 'Teams_78.csv'))`
- `pd.read_csv(path)`
- `safe_read_csv(LINEUPS_PATH)`

### Konfiguration und Environment

- `SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))`
- `DATA_PATH = 'C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection'`
- `TESTRUNS_PATH = 'C:/AI Projekt/KI-Projekt/Sports Api Data/Testruns'`
- `FUTURE_OUTPUT_PATH = os.path.join(TESTRUNS_PATH, 'Datacollection future')`
- `REFERENCE_OUTPUT_PATH = os.path.join(TESTRUNS_PATH, 'Datacollection reference')`
- `WEATHER_HIST_PATH = os.path.join(DATA_PATH, 'historical_weather_data_78.csv')`
- `LINEUPS_PATH = os.path.join(DATA_PATH, 'lineups_league_78.csv')`
- `INJURIES_PATH = os.path.join(DATA_PATH, 'injuries_league_78.csv')`
- `PLAYER_STATS_PATH = os.path.join(DATA_PATH, 'player_statistics_per_fixture_league_78.csv')`
- `INTERNATIONAL_BASE = 'C:/AI Projekt/KI-Projekt/Sports Api Data/International'`
- `INTERNATIONAL_BRANCHES = ('FIFA', 'UEFA')`
- `INTERNATIONAL_FIXTURES_PATH = [os.path.join(INTERNATIONAL_BASE, b, 'Filtered', 'Datacollection', 'Stammdaten_international.csv') for b in INTERNATIONAL_BRANCHES]`
- `INTERNATIONAL_LINEUPS_PATH = [os.path.join(INTERNATIONAL_BASE, b, 'Filtered', 'Datacollection', 'lineups_international.csv') for b in INTERNATIONAL_BRANCHES]`
- `INTERNATIONAL_PLAYER_STATS_PATH = [os.path.join(INTERNATIONAL_BASE, b, 'Filtered', 'Datacollection', 'player_statistics_per_fixture_international.csv') for b in INTERNATIONAL_BRANCHES]`
- `MAX_RUNS = 30`
- `RANDOM_STATE = 42`
- `BACKTEST_DATE_CUTOFF = pd.to_datetime(_backtest_cutoff_raw) if _backtest_cutoff_raw else None`
- `PREDICTION_MODE = 'reference'`
- `REFERENCE_PREDICTION_LIMIT = None`
- `MATCH_STATS_MODE = 'predicted' if PREDICTION_MODE == 'future' else 'actual'`
- `MATCH_STATS_MODEL = 'gbr'`
- `MATCH_STATS_CV_SPLITS = 5`
- `MATCH_STATS_MIN_ROWS = 25`
- `PREDICTION_OUT_PATH = os.path.join(OUTPUT_PATH, 'prediction_weight_runs.csv')`
- `RUN_SUMMARY_OUT_PATH = os.path.join(OUTPUT_PATH, 'prediction_weight_run_summary.csv')`

### Imports und interne Abhaengigkeiten

- `import math`
- `import os`
- `import random`
- `import sys`
- `from datetime import datetime`
- `import pandas as pd`
- `from bartpy.sklearnmodel import SklearnModel`
- `from player_workload_features import build_player_workload_index, player_workload_at`
- `from sklearn.ensemble import GradientBoostingRegressor`
- `from sklearn.impute import SimpleImputer`
- `from sklearn.model_selection import KFold, train_test_split`
- `from sklearn.neural_network import MLPRegressor`
- `from sklearn.pipeline import make_pipeline`
- `from sklearn.preprocessing import StandardScaler`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Das Modul wird von der Pipeline importiert. Schnittstellenbeispiel (Signatur, keine ausfuehrbaren Beispieldaten):

```text
load_weather(path)
```

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `pd.errors.EmptyDataError`, `(TypeError, ValueError)`.
- Auswertungen nur auf identischen MatchIDs, Zeitraeumen und Zieldefinitionen vergleichen.
- Nachtraegliche Wahrscheinlichkeitsvarianten ersetzen keinen zeitlich getrennten Validierungslauf.
- Fehlende Werte, Join-Verluste und Zahl der ausgewerteten Spiele gemeinsam mit Kennzahlen berichten.
