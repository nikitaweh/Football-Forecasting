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



