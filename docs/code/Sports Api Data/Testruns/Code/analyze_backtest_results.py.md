# `analyze_backtest_results.py`

Source: `Sports Api Data/Testruns/Code/analyze_backtest_results.py`

## Ueberblick

Dieses Skript aggregiert bereits ausgefuehrte Matchday-Backtests zu einer Saisonperspektive.
Es vergleicht das beste Modell pro Spieltag mit historischen BWIN-Quoten, bewertet die Stabilitaet der Gewichte und prueft, ob Surrogate-Scores tatsaechlich kalibriert sind.
Der Fokus liegt auf Diagnose und Vergleichbarkeit, nicht auf dem Erzeugen neuer Vorhersagen.

## Zweck / Responsibilities

- Liest pro Matchday die Backtest-Artefakte unter `Datacollection backtest/MDxx/`.
- Ermittelt Modellleistung pro Spieltag.
- Berechnet eine Buchmacher-Baseline auf Match-Ebene.
- Fasst die Saison in `season_summary.csv` zusammen.
- Meldet besonders schwierige Spieltage.
- Analysiert, welche Gewichte ueber Matchdays stabil oder volatil sind.
- Bewertet die Korrelation zwischen vorhergesagter und tatsaechlicher NLL des Surrogates.

## Erwartete Vorbedingungen

- `backtest_matchdays.py` wurde bereits ausgefuehrt.
- In `Datacollection backtest/MDxx/` liegen mindestens Summary-Dateien.
- Eine historische BWIN-Datei kann vorhanden sein, muss aber nicht.
- `Stammdaten_78.csv` und `match_statistics_filtered_78.csv` sind konsistent.

## Hauptinputs

- `STAMMDATEN_PATH`
- `STATS_PATH`
- `ODDS_DIR`
- `BACKTEST_DIR`
- Pro Matchday:
  - `prediction_weight_run_summary.csv`
  - optional `prediction_weight_runs.csv`

## Hauptoutput

- `Datacollection backtest/season_summary.csv`
- Umfangreiche Textausgabe auf `stdout`

## Ablauf

### 1) Tatsae chliche Resultate pro Matchday laden

- `load_actual_results_by_matchday()` liest Stammdaten und Match-Stats.
- Es filtert auf:
  - `Season == SEASON`
  - `Gespielt == True`
- `Matchday` wird per Regex auf eine numerische `MD` reduziert.
- Nur Matches mit vorhandenen Match-Stats bleiben erhalten.
- Das Ergebnis enthaelt `MatchID`, `MD`, `Result`.

### 2) Buchmacher-Baseline laden

- `load_bookmaker_match_nll()` sucht die neueste Datei `bwin_historical_odds_*.csv`.
- Fehlende Dateien sind erlaubt.
- Dann faellt das Skript auf `NAIVE_PRIOR` zurueck.
- Wenn eine Datei vorhanden ist, werden aus Decimal Odds implizite Wahrscheinlichkeiten berechnet.
- Anschliessend werden diese auf den Overround normiert.
- Daraus entsteht fuer jedes Match eine Match-NLL auf dem tatsaechlichen Ergebnis.

### 3) Matchday-Ordner iterieren

- `main()` enumeriert alle `MD*`-Ordner.
- Nicht parsebare oder leere Ordner werden uebersprungen.
- Pro Spieltag werden Summary-Werte und optionale Per-Match-Werte geladen.

### 4) Modell gegen Buchmacher vergleichen

- `matchday_bookie_baseline(...)` liefert die mittlere Match-NLL des Buchmachers.
- Falls fuer ein Match keine Odds vorliegen, greift `NAIVE_PRIOR`.
- Das beste Modell eines Matchdays wird ueber minimale `AvgNLL` bestimmt.
- Zusaetzlich werden `BestAcc`, `MeanNLL`, `MeanAcc` und `GapVsBookie` berechnet.

### 5) Per-Match-Head-to-Head

- Falls `prediction_weight_runs.csv` existiert, wird die beste Run-ID bestimmt.
- Die Match-NLL dieser besten Run wird gegen die Buchmacher-Match-NLL gelegt.
- Das ergibt:
  - `MatchesBeatingBookie`
  - `MatchesCompared`
  - eine globale, matchuebergreifende Head-to-Head-Auswertung

### 6) Gewichtsstabilitaet

- Aus jeder Matchday-Summary wird die beste Gewichtszeile extrahiert.
- Fuer jedes `Weight_*` berechnet das Skript Mittelwert, Standardabweichung und Variationskoeffizient.
- Niedrige Standardabweichung bedeutet stabileres Signal.
- Hohe Streuung deutet auf Matchday-Abhaengigkeit oder Overfitting hin.

### 7) Surrogate-Kalibrierung

- Wenn `Pred_AvgNLL` in der Summary vorhanden ist, vergleicht das Skript diese Vorhersage mit der echten `AvgNLL`.
- Voraussetzung sind mindestens 5 gueltige Punkte innerhalb eines Matchdays.
- Als Kennzahl wird die Pearson-Korrelation ausgegeben.

## Wichtige Funktionen

- `load_actual_results_by_matchday()`
  - Baut die tatsaechlichen Matchday-Ergebnisse aus Stammdaten und Stats.
- `load_bookmaker_match_nll()`
  - Liefert `{MatchID: MatchNLL_Bookie}` aus der neuesten historischen Quote-Datei.
- `naive_match_nll(result)`
  - Fallback-NLL aus den festen Priors.
- `matchday_bookie_baseline(match_ids, results, bookie_nll_map)`
  - Aggregiert Buchmacher- oder Fallback-NLL ueber einen Spieltag.
- `fmt(x, digits=4)`
  - Konsistente Formatierung fuer Reports.
- `main()`
  - Orchestriert Laden, Aggregation, Reporting und CSV-Export.

## Funktionssignaturen im Code

- `load_actual_results_by_matchday()`
  - keine Parameter; liefert einen DataFrame mit `MatchID`, `MD`, `Result`.
- `load_bookmaker_match_nll()`
  - keine Parameter; liefert `(bookie_nll_map, odds_source)`.
- `naive_match_nll(result)`
  - nimmt ein Resultatlabel `H`/`D`/`A` und berechnet die Fallback-NLL.
- `matchday_bookie_baseline(match_ids, results, bookie_nll_map)`
  - aggregiert Match-NLLs und liefert `(mean_nll, num_with_odds, num_fallback)`.
- `fmt(x, digits=4)`
  - formatiert numerische Kennzahlen fuer die Konsolenausgabe.
- `main()`
  - Einstiegspunkt fuer saisonweite Aggregation und Report-Erstellung.

## Inputs / Outputs & Side-Effects

Inputs:

- Saison- und Match-Stats-Daten.
- Historische BWIN-Datei, wenn vorhanden.
- Backtest-Ausgabedateien pro Matchday.

Outputs:

- `season_summary.csv`
- Report mit Tabellen fuer:
  - Per-Matchday Summary
  - schwierigste Spieltage
  - Gewichts-Stabilitaet
  - Surrogate-Korrelation

Side-Effects:

- Legt `BACKTEST_DIR` bei Bedarf an.
- Ueberschreibt `season_summary.csv`.
- Schreibt keine Eingabedatei um.

## Konfiguration

- `SEASON`
  - Welche Bundesliga-Saison ausgewertet wird.
- `NAIVE_PRIOR`
  - Fallback-Wahrscheinlichkeiten fuer Matches ohne Buchmacherquote.
- `SUMMARY_OUT_PATH`
  - Zielpfad der Saisonaggregation.

## Inputs / Outputs genauer

Wichtige Eingabespalten aus `Stammdaten_78.csv`:

- `Season`
- `Gespielt`
- `Matchday`
- `Date`
- `MatchID`

Wichtige Eingabespalten aus `match_statistics_filtered_78.csv`:

- `MatchID`
- `Home Goals`
- `Away Goals`

Erwartete Summary-Spalten pro Matchday-Ordner:

- `RunID`
- `AvgNLL`
- `Accuracy`
- optional `Pred_AvgNLL`
- optional mehrere `Weight_*`-Spalten

Persistierter Saisonoutput in `season_summary.csv`:

- `Matchday`
- `NumFixtures`
- `ResultMix`
- `BookieNLL`
- `BookieOddsCoverage`
- `BestNLL`
- `MeanNLL`
- `BestAcc`
- `MeanAcc`
- `GapVsBookie`
- `BeatsBookie`
- `MatchesBeatingBookie`
- `MatchesCompared`
- `NumRuns`

## Wichtige interne Abhaengigkeiten

- `pandas`
  - Aggregation, Merge, Statistik.
- `math`
  - Logarithmus und `NaN`-Handhabung.
- `pathlib.Path`
  - Dateisystempfade.

## Fachliche Interpretation

- `GapVsBookie < 0`
  - Das beste Modell des Spieltags war im Mittel besser als der Buchmacher.
- Hohe `BestAcc` bei schlechter `BestNLL`
  - Das Modell trifft Gewinner, ist aber schlecht kalibriert.
- Positive Pearson-Korrelation des Surrogates
  - Das Surrogate ordnet Kandidaten in etwa sinnvoll.
- Hohe Gewichtsvolatilitaet
  - Die optimale Parametrisierung ist nicht robust ueber Matchdays.

## Datenqualitaet und Validierungslogik

- Die Matchday-Definition kommt aus `Stammdaten_78.csv`, nicht aus dem Backtest-Ordner selbst.
- Dadurch koennen falsch benannte oder unvollstaendige `MDxx`-Ordner die Saisonlogik nicht direkt verbiegen.
- Der Buchmachervergleich arbeitet auf Match-Ebene und mittelt erst danach.
- Das ist methodisch sauberer als ein direkter Vergleich von Matchday-Mittelwerten aus heterogenen Matchmengen.
- Wenn Odds fehlen, greift ein fester Prior.
- Diese Rueckfalllogik verhindert Totalausfall, verwischt aber den eigentlichen Marktvergleich.
- `Pred_AvgNLL` wird nur ausgewertet, wenn innerhalb eines Spieltags genug gueltige Werte vorhanden sind.
- Die Korrelation ist damit bewusst konservativ statt vollstaendig.

## Typische Stolperfallen

- Die neueste BWIN-Datei wird nur per Dateiname bestimmt.
- Ein spaeter erzeugter, aber inhaltlich schlechterer Export kann also bevorzugt werden.
- Fehlende `Pred_AvgNLL`-Spalten sind kein Fehler, sondern bedeuten meist, dass das Surrogate in diesen Runs nicht aktiv war.
- `Matchday`-Strings wie `Final` fallen bewusst heraus.
- Wenn `prediction_weight_runs.csv` fehlt, entfaellt nur der Match-Level-Vergleich, nicht die Saisonzusammenfassung.

## Edge Cases / Notes

- Leere Matchday-Summaries werden still ignoriert.
- Nicht parsebare `MD`-Ordner werden mit Hinweis uebersprungen.
- Falls gar keine nutzbaren Matchdays gefunden werden, endet das Skript frueh.
- Wenn fuer alle Spiele nur Fallback-Priors vorliegen, ist der Buchmachervergleich methodisch deutlich schwaecher.

## Beispiel

```bash
python "Sports Api Data/Testruns/Code/analyze_backtest_results.py"
```

## Sinnvolle Nachkontrollen

- `season_summary.csv` auf fehlende `BestNLL`- oder `BookieNLL`-Werte pruefen.
- Report-Abschnitt `Per-match head-to-head` auf ausreichende Matchanzahl pruefen.
- Gewichts-Stabilitaet nicht isoliert interpretieren:
  - stabile Gewichte sind nur dann gut, wenn die Leistung ebenfalls tragfaehig ist.

## Warum dieses Skript sinnvoll ist

- Es trennt Training und Diagnose sauber.
- Es liefert nicht nur einen Mittelwert, sondern mehrere Blickwinkel auf die Backtests.
- Es deckt methodische Schwaechen auf:
  - Kalibrierungsprobleme
  - inkonsistente Gewichte
  - mangelnde Konkurrenzfaehigkeit gegen Marktpreise

## Grenzen

- Es betrachtet pro Matchday nur das beste Modell besonders detailliert.
- Es nutzt Pearson statt robusterer Rangkorrelationen.
- Die naive Fallback-Baseline kann bei duennen Odds-Daten den Buchmachervergleich verzerren.
- Es gibt keinen eingebauten Signifikanztest fuer Unterschiede gegen den Buchmacher.

## Sinnvolle Erweiterungen

- Zusaeztlich Median-NLL pro Matchday ausweisen, damit einzelne Ausreisser weniger dominieren.
- Unsicherheit des Buchmachervergleichs ueber Bootstrap oder einfache Konfidenzintervalle schaetzen.
- Coverage von `prediction_weight_runs.csv` explizit pro Matchday protokollieren.
- Surrogate-Kalibrierung optional auch mit Spearman-Korrelation reporten.

## Pflegehinweise

- Wenn weitere Kennzahlen relevant werden, sollten sie zuerst in `season_summary.csv` geschrieben werden.
- Danach ist eine textuelle Ausgabe sinnvoll.
- Umgekehrt waere es schlechter wartbar, nur neue `print()`-Zeilen zu ergaenzen.
