# `AI_match_stats_prediction.py`

Source: `Sports Api Data/Testruns/Code/AI_match_stats_prediction.py`

## Überblick

Dieses Modul ist die umfangreichste Vorhersage-Pipeline im Testruns-Bereich. Es kombiniert historische Match-Statistiken, Team-Staerken, Formkurven, Head-to-Head-Merkmale, Wetterdaten und optional prognostizierte Match-Stats, um fuer Bundesliga-Spiele Ergebniswahrscheinlichkeiten und plausible Scorelines zu erzeugen.

Der Ablauf ist bewusst in zwei Ebenen getrennt: zuerst werden Pre-Match-Features gebaut, danach wird entweder mit echten Match-Statistiken, mit vorab prognostizierten Match-Statistiken oder ganz ohne Match-Stats ein Outcome-Modell trainiert. Fuer jede Kandidaten-Konfiguration werden Feature-Gewichte, ein H2H-Zuverlaessigkeitsparameter und Bewertungsmetriken protokolliert.

## Zweck / Responsibilities

- Laedt und vereinheitlicht mehrere CSV-Quellen aus dem Filtered-Datacollection-Ordner.
- Baut historische Team- und Gegner-Merkmale fuer Heim- und Auswaertsteams.
- Ergaenzt Wetterdaten aus historischen und zukuenftigen Quellen.
- Unterstuetzt zwei Zielmodi:
  - `reference` fuer Debugging und Bewertung gegen bekannte Ergebnisse.
  - `future` fuer echte Vorhersagen kommender Spiele.
- Unterstuetzt drei Match-Stats-Modi:
  - `actual` nutzt vorhandene aktuelle Match-Statistiken.
  - `predicted` schaetzt Match-Statistiken aus Pre-Match-Features.
  - `off` entfernt Match-Statistiken komplett aus dem Outcome-Modell.
- Trainiert pro Kandidatenlauf ein BART-Regressionsmodell auf `GoalDiff`.
- Leitet aus dem vorhergesagten GoalDiff Wahrscheinlichkeiten fuer `H`, `D` und `A` ab.
- Schaetzt ein plausibles Endergebnis ueber offensive und defensive Team-Baselines.
- Speichert Run-Historie, Pareto-Entscheidungssets, Kandidaten-Rankings und Ergebnisdateien.

## Pipeline In Kurzform

1. Stammdaten, Match-Statistiken und Teamdaten laden.
2. Spalten aus verschiedenen CSV-Layouts auf gemeinsame Namen bringen.
3. Team- und Wetterdaten in ein gemeinsames Match-DataFrame mergen.
4. Historische H2H-Features und letzte-5-Spiele-Formmerkmale berechnen.
5. Trainings- und Zielmenge je nach `PREDICTION_MODE` bilden.
6. Optional Match-Statistiken per Regressionsmodellen vorhersagen.
7. Fuer jeden Kandidatenlauf Feature-Gewichte und `H2H_K` sampeln.
8. H2H-Signale mit `alpha = MatchCount / (MatchCount + k)` abschwaechen.
9. Features imputieren, gewichten und BART auf `GoalDiff` trainieren.
10. `GoalDiff` in Ergebniswahrscheinlichkeiten und Scorelines umrechnen.
11. Laeufe gegen Referenzen bewerten oder fuer Future-Laeufe nach Confidence ranken.

## Wichtige Datenquellen

- `match_statistics_filtered_78.csv`: Match-spezifische Spielstatistiken.
- `Stammdaten_78.csv`: Basisinformationen pro Match, darunter Teams, Datum und `Played`.
- `Teams_78.csv`: Team-Metadaten wie IDs, Name und Stadionparameter.
- `historical_weather_data_78.csv`: historische Wettermerkmale pro Match.
- `weather_data.csv`: zusaetzliche Wetterdaten im jeweiligen Output-Ordner.
- `match_results_references.csv`: Referenzziele fuer Evaluation im Reference-Modus.
- `surrogate_run_history.csv`: Historie frueherer Laeufe fuer das Surrogate-Ranking.

## Wichtige Konstanten / Konfiguration

- `DATA_PATH`: Basispfad fuer gefilterte Bundesliga-Daten.
- `TESTRUNS_PATH`: Basispfad fuer Referenz- und Future-Ausgaben.
- `FUTURE_OUTPUT_PATH`: Ausgabeordner fuer Vorhersagen kommender Spiele.
- `REFERENCE_OUTPUT_PATH`: Ausgabeordner fuer Referenzbewertungen.
- `WEATHER_HIST_PATH`: historische Wetterdatei.
- `MAX_RUNS = 20`: maximale Kandidatenlaeufe pro Skriptstart.
- `RANDOM_STATE = 42`: Seed fuer Reproduzierbarkeit.
- `PREDICTION_MODE = 'reference'`: aktueller Modus im Stand `HEAD`.
- `MATCH_STATS_MODE = 'predicted' if PREDICTION_MODE == 'future' else 'actual'`: Standardlogik fuer Match-Stats.
- `MATCH_STATS_MODEL = 'gbr'`: Modell fuer Match-Stats-Schaetzung.
- `MATCH_STATS_CV_SPLITS = 5`: Cross-Validation-Splits fuer Out-of-Fold-Prognosen.
- `MATCH_STATS_MIN_ROWS = 25`: Mindestmenge fuer modellierte Match-Stats.
- `SURROGATE_MODEL = 'gbr'`: Modell fuer die spaetere Kandidatenbewertung.
- `SURROGATE_MIN_HISTORY = 100`: Mindesthistorie, bevor das Surrogate-Modell verwendet wird.
- `SURROGATE_CANDIDATES = 300`: Anzahl erzeugter Kandidaten fuer die Vorauswahl.
- `SURROGATE_RANDOM_FRACTION = 0.2`: Anteil explorativer Kandidaten.
- `PARETO_TARGET_SIZE = 20`: Zielgroesse fuer Entscheidungstabellen.
- `H2H_K_RANGE = (1, 10)`: Suchraum fuer die H2H-Abschwaechung.
- `H2H_K_DEFAULT = 2`: Fallback fuer fehlende historische Werte.

## Feature-Gruppen

### Outcome-Pre-Match-Features

- Team-Baselines: `Home_BaseAvgGoalsFor`, `Away_BaseAvgPoints` usw.
- Formmerkmale der letzten 5 Spiele fuer Tore, Gegentore und Punkte.
- Kombinierte H2H-Metriken ueber alle Begegnungen.
- Venue-spezifische H2H-Metriken fuer Heim/Auswaerts-Kontext.
- Wettermerkmale wie Temperatur, Druck, Luftfeuchtigkeit und Niederschlag.

### Match-Stats-Features

- Ballbesitz, Schuesse, Schuesse aufs Tor.
- Paesse und Passgenauigkeit.
- Fouls, Gelbe und Rote Karten.
- Abseits und Ecken.

### Team-Kontext-Features

- `HomeTeamID`
- `AwayTeamID`

## Zentrale Funktionen

### Datenvorbereitung

- `load_weather(path)`: liest Wetter-CSV, normalisiert Spaltennamen und erzwingt numerische Wetterspalten.
- `coerce_numeric_columns(df_src, columns)`: konvertiert definierte Feature-Spalten robust nach numerisch.
- `add_team_asof_features(df_src, team_id_col, prefix)`: fuegt pro Team die letzte bekannte L5-Form per `merge_asof` an.

### Head-to-Head-Logik

- `summarize_h2h(subset)`: erzeugt Mittelwerte und Match-Anzahl fuer direkte Duelle.
- `add_h2h_features(df_src)`: baut pro Match kombinierte und venue-spezifische H2H-Features.
- `apply_h2h_scaling(feature_df, k)`: schwacht H2H-Merkmale nach Verlaesslichkeit ab.

### Referenz- und Historienlogik

- `load_reference_results(primary_path, fallback_path=None)`: laedt Referenzziele aus mehreren moeglichen Pfaden.
- `read_optional_csv(path)`: toleranter CSV-Leser fuer optionale Artefakte.
- `prepare_run_summary(summary_df)`: bereitet Laufmetriken fuer Sortierung und Persistenz auf.
- `append_to_run_history(history_path, summary_df)`: haengt neue Ergebnisse an die Run-Historie an und dedupliziert.
- `try_backfill_reference_from_future(ref_results)`: nutzt bereits gespeicherte Future-Runs, um Referenzfaelle nachtraeglich zu scoren.

### Prediction- und Modelllogik

- `build_prediction_frame(df_src, ref_results, mode, future_limit=9, reference_limit=None)`: waehlt die Zielmenge fuer Reference- oder Future-Laeufe.
- `make_match_stats_regressor()`: erstellt derzeit einen `GradientBoostingRegressor`.
- `fit_match_stats_estimator(x_train, y_train)`: imputiert Eingaben und trainiert das Match-Stats-Modell.
- `postprocess_match_stats(pred_df)`: begrenzt Prozentwerte auf 0 bis 100 und rundet Count-Features sinnvoll.
- `build_match_stats_predictions(train_df, predict_df, feature_cols, target_cols)`: erzeugt Out-of-Fold- und Inferenz-Prognosen fuer jede Match-Stats-Zielspalte.
- `apply_match_stats_mode(train_df, predict_df, raw_predict_df)`: integriert je nach Modus echte, prognostizierte oder keine Match-Stats.
- `mean_available(values, default_value=1.25)`: bildet robuste Mittelwerte ueber optionale Signale.
- `estimate_scoreline(match_row, predicted_goal_diff, predicted_result)`: baut aus GoalDiff und Team-Baselines ein plausibles Ergebnis.

### Auswahl und Ranking

- `compute_pareto_front(df, nll_col='AvgNLL', acc_col='Accuracy')`: bestimmt nicht-dominierte Kandidaten.
- `build_pareto_decision_set(df, target_size=PARETO_TARGET_SIZE)`: erweitert das strenge Pareto-Set zu einer arbeitsfaehigen Shortlist.
- `rank_component(series, smaller_is_better=False)`: wandelt Metriken in relative Ranking-Komponenten um.
- `build_future_candidate_ranking(df, target_size=PARETO_TARGET_SIZE)`: erzeugt Empfehlungen fuer `Balanced`, `Conservative` und `Aggressive`.
- `load_run_history(path, weight_cols, match_stats_mode)`: filtert historische Runs passend zum aktuellen Match-Stats-Modus.
- `train_surrogate_model(history_df, feature_cols, target_col)`: trainiert die Meta-Bewertung ueber historische Resultate.
- `generate_candidate_df(num, features, k_range)`: sampelt zufaellige Gewichtungs-Kandidaten.
- `select_candidates_with_surrogate(candidates_df, pred_nll, pred_acc, max_runs, random_frac)`: mischt exploitative und explorative Kandidaten.

## Inputs / Outputs / Side Effects

### Inputs

- CSV-Dateien im `DATA_PATH`-Ordner.
- Optionale Wetterdatei aus dem aktiven Output-Ordner.
- Referenzdateien fuer Match-Ergebnisse.
- Historische Ergebnisdateien frueherer Testruns.

### Outputs

- `prediction_weight_runs.csv`: Detailergebnisse je Match und Run.
- `prediction_weight_run_summary.csv`: aggregierte Laufmetriken.
- `surrogate_run_history.csv`: fortlaufende Modellhistorie.
- `pareto_front.csv`: Entscheidungsmenge im Reference-Modus.
- `future_candidate_ranking.csv`: Kandidatenranking im Future-Modus.
- `future_outcome_table.csv`: komprimierte Empfehlung fuer kommende Spiele.
- `predicted_match_stats.csv`: prognostizierte Match-Statistiken im `predicted`-Modus.

### Side Effects

- Erstellt Zielordner automatisch via `os.makedirs`.
- Schreibt mehrere CSV-Artefakte pro Lauf.
- Nutzt Zufallsstichproben fuer Gewichtungen, aber mit festem Seed.
- Gibt viele Debug- und Statusmeldungen auf `stdout` aus.
- Beendet den Prozess frueh mit `SystemExit(0)`, wenn Reference-Backfill erfolgreich war.

## Inputs Und Outputs Pro Funktionsgruppe

### `load_weather(path)`

- Input: Pfad zu Wetter-CSV.
- Output: DataFrame mit `MatchID` plus normalisierten Wetterspalten.
- Besonderheit: liefert leeres DataFrame bei fehlender oder leerer Datei.

### `build_match_stats_predictions(train_df, predict_df, feature_cols, target_cols)`

- Input: Trainings- und Zielmenge plus Feature- und Zielspalten.
- Output: prognostizierte Trainingswerte, Zielwerte und eine Summary-Tabelle.
- Besonderheit: nutzt OOF-Splits nur, wenn genug Beobachtungen und Varianz vorliegen.

### `apply_match_stats_mode(train_df, predict_df, raw_predict_df)`

- Input: vorbereitete Trainings- und Ziel-Frames.
- Output: angereicherte Frames, aktive Featureliste, optionales Export-DataFrame und Summary.
- Besonderheit: entscheidet die gesamte weitere Modellarchitektur.

### `estimate_scoreline(match_row, predicted_goal_diff, predicted_result)`

- Input: Match-Merkmale plus Ergebnis des GoalDiff-Modells.
- Output: erwartete Heim- und Auswaertstore sowie gerundete Scoreline.
- Besonderheit: korrigiert nachtraeglich, falls die gerundete Scoreline dem Klassenergebnis widerspricht.

## Wichtige Validierungen Und Schutzmechanismen

- Ungueltige `PREDICTION_MODE`-Werte loesen sofort `ValueError` aus.
- `future` plus `MATCH_STATS_MODE='actual'` ist explizit verboten.
- Fehlende Pflichtspalten nach dem Merge fuehren zu einem harten Fehler.
- Leere Referenzdateien werden toleriert, aber begrenzen die Auswertung.
- Leere Trainingsmengen nach Modusumschaltung loesen einen `ValueError` aus.
- Prozentwerte werden nach Prognose auf einen gueltigen Bereich zurueckgesetzt.
- Count-Features werden auf nichtnegative ganze Zahlen gekappt.

## Interne Abhaengigkeiten / Imports

- `pandas`: DataFrame-Verarbeitung und CSV-I/O.
- `math`: Normalverteilungsnahe CDF-Umrechnung und Logarithmen.
- `os`: Pfadbau und Dateiexistenzpruefung.
- `random`: Sampling fuer Feature-Gewichte und H2H-Kandidaten.
- `bartpy.sklearnmodel.SklearnModel`: Kernmodell fuer GoalDiff.
- `sklearn.impute.SimpleImputer`: Median-Imputation.
- `sklearn.model_selection.KFold`: OOF-Prognosen fuer Match-Stats.
- `sklearn.model_selection.train_test_split`: Split fuer Outcome-Training.
- `sklearn.ensemble.GradientBoostingRegressor`: Match-Stats- und Surrogate-Modell.
- `sklearn.pipeline.make_pipeline`: Pipeline fuer den optionalen NN-Surrogate.
- `sklearn.preprocessing.StandardScaler`: Skalierung fuer das NN-Surrogate.
- `sklearn.neural_network.MLPRegressor`: alternativ vorgesehenes Surrogate-Modell.

## Beispiel

```bash
python "Sports Api Data/Testruns/Code/AI_match_stats_prediction.py"
```

Typischer Ablauf:

1. Modus ueber `PREDICTION_MODE` und `MATCH_STATS_MODE` festlegen.
2. Skript starten.
3. Danach die erzeugten CSV-Dateien im passenden Output-Ordner pruefen.
4. Im Future-Modus zusaetzlich `future_candidate_ranking.csv` und `future_outcome_table.csv` auswerten.

## Edge Cases / Notes

- Wenn `match_results_references.csv` zwar existiert, aber MatchIDs nicht im Hauptdatensatz vorkommen, wird der Lauf abgebrochen.
- Im `predicted`-Modus koennen einzelne Match-Stats-Ziele mangels Daten nur auf Median-Fallbacks basieren.
- Das Skript nutzt viele `copy()`-Operationen; bei grossen Datenmengen ist der Speicherbedarf entsprechend hoch.
- Die Future-Auswahl ist hart auf die naechsten 9 ungespielten Matches begrenzt.
- Die Balance zwischen NLL und Accuracy wird ueber verschiedene Ranking-Strategien geloest, nicht ueber ein einzelnes Ziel.
- `reference` kann vorhandene Future-Ergebnisse wiederverwenden, statt jedes Mal alle Modelle neu zu rechnen.
- Wegen des Seedings sind Sampling-Ergebnisse reproduzierbar, aber nur solange sich Featureliste und Datenbasis nicht aendern.

## Letzte beobachtete Aenderung

Im aktuellen Commit wurde `PREDICTION_MODE` auf `reference` gesetzt. Dadurch liegt der Fokus dieses Skriptstands auf Debugging, Evaluation und dem Schreiben von `pareto_front.csv` im Referenz-Ausgabeordner statt auf produktiven Future-Vorhersagen.
