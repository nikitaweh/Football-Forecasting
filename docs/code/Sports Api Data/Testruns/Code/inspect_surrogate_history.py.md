# `inspect_surrogate_history.py`

Source: `Sports Api Data/Testruns/Code/inspect_surrogate_history.py`

## Ueberblick

Dieses Skript ist ein read-only Diagnosewerkzeug fuer `surrogate_run_history.csv`.
Es zerlegt die Historie nach `MatchStatsMode`, `SourcePredictionMode` und `FeatureSchemaVersion`, damit sichtbar wird, welche Run-Slices das Surrogatemodell tatsaechlich verwenden kann.
Optional schreibt es zusaetzliche Split-Dateien fuer visuelle Kontrolle, ohne die Ursprungshistorie anzufassen.

## Zweck / Responsibilities

- Liest die Surrogate-Historie aus Future- und/oder Reference-Ordnern.
- Fuegt fehlende Slice-Spalten defensiv als `unknown` ein.
- Erstellt per Slice Kennzahlen zu Zeilenanzahl, BatchIDs und NLL.
- Kennzeichnet, ob `SURROGATE_MIN_HISTORY` erreicht ist.
- Meldet Legacy-BatchID-Kollisionen zwischen Modi.
- Kann pro Slice eine abgeleitete CSV in `surrogate_history_split/` schreiben.

## Warum das Skript wichtig ist

- Die Hauptpipeline filtert Historie nur nach bestimmten Slice-Dimensionen.
- Ohne Diagnose bleibt oft unklar, warum das Surrogatemodell aktiv oder inaktiv ist.
- Das Skript macht genau diese implizite Datenlogik explizit sichtbar.

## Datenquellen

- `Datacollection reference/surrogate_run_history.csv`
- `Datacollection future/surrogate_run_history.csv`

## Konfiguration

- `FOLDERS`
  - Zuordnung von Label zu konkretem CSV-Pfad.
- `SURROGATE_MIN_HISTORY = 100`
  - Muss bewusst zur Hauptpipeline passen.

## Ablauf

### 1) Datei laden

- `load(path)` prueft zuerst die Existenz.
- Fehlende Datei liefert `None`.
- Leere CSV liefert einen leeren DataFrame.
- Fehlende Schluesselspalten werden mit `unknown` aufgefuellt:
  - `MatchStatsMode`
  - `SourcePredictionMode`
  - `FeatureSchemaVersion`

### 2) Slice-Summary berechnen

- `summarise(df)` gruppiert ueber drei Slice-Spalten.
- Pro Slice werden berechnet:
  - `Rows`
  - `Batches`
  - `SurrogateReady`
  - `BestAvgNLL`
  - `MeanAvgNLL`

### 3) Ausgabe aufbereiten

- `report_folder(...)` erstellt eine kompakte Anzeige.
- Batch-Listen werden optional im Detailmodus ausgegeben.
- Batch-Bereiche werden aus Minimum und Maximum der BatchIDs abgeleitet.

### 4) BatchID-Kollisionen pruefen

- Per Kreuztabelle `BatchID x MatchStatsMode` wird geprueft, ob dieselbe BatchID in mehreren Modi vorkommt.
- Solche Kollisionen sind historisch moeglich und werden explizit gemeldet.
- Das ist ein wichtiger Hinweis fuer alte Datenstaende.

### 5) Optionale Split-Dateien schreiben

- Mit `--split` erzeugt `write_split_files(...)` fuer jede Slice-Kombination eine eigene CSV.
- Die Dateinamen werden ueber `_sanitize(...)` dateisicher gemacht.
- Diese Exporte sind abgeleitet und nicht Teil der Hauptpipeline.

## Wichtige Funktionen

- `load(path)`
  - Liest die CSV robust und normalisiert fehlende Slice-Spalten.
- `summarise(df)`
  - Baut die Slice-Level-Auswertung.
- `_sanitize(value)`
  - Macht Slice-Werte dateinamenkompatibel.
- `write_split_files(df, source_path)`
  - Persistiert pro Slice eine separate CSV.
- `report_folder(label, path, detailed, split)`
  - Stellt Laden, Reporting und optionales Splitten je Ordner zusammen.
- `main()`
  - CLI-Einstiegspunkt fuer Referenz, Future oder beide.

## Funktionssignaturen im Code

- `load(path)`
  - liefert `None`, einen leeren DataFrame oder die normalisierte Historie.
- `summarise(df)`
  - gruppiert die Historie und liefert eine Slice-Summary als DataFrame.
- `_sanitize(value)`
  - normalisiert Slice-Werte fuer dateisichere Dateinamen.
- `write_split_files(df, source_path)`
  - schreibt abgeleitete CSVs und liefert `(out_dir, written)`.
- `report_folder(label, path, detailed, split)`
  - druckt den kompletten Report fuer genau eine Historien-Datei.
- `main()`
  - verarbeitet die CLI-Parameter und iteriert ueber die Zielordner.

## CLI-Optionen

- `--folder`
  - `reference`
  - `future`
  - `both`
- `--detailed`
  - gibt komplette Batch-Listen pro Slice aus.
- `--split`
  - schreibt zusaetzliche Split-Dateien.

## Inputs

- Eine oder zwei `surrogate_run_history.csv`-Dateien.

## Outputs

- Textreport auf `stdout`.
- Optional:
  - `surrogate_history_split/<slice>.csv`

## Inputs / Outputs genauer

Erwartete Kernspalten der Historie:

- `BatchID`
- `AvgNLL`
- `MatchStatsMode`
- `SourcePredictionMode`
- `FeatureSchemaVersion`

Abgeleitete Summary-Spalten:

- `Rows`
- `Batches`
- `SurrogateReady`
- `BestAvgNLL`
- `MeanAvgNLL`
- `BatchCount`
- `BatchRange`

## Side-Effects

- Ohne `--split` keine Dateiaenderung.
- Mit `--split` werden nur neue abgeleitete Dateien geschrieben.
- Die Originalhistorie bleibt unveraendert.

## Methodische Aussagekraft

- `SurrogateReady = True`
  - Der Slice hat mindestens `SURROGATE_MIN_HISTORY` Zeilen.
- Niedrige `Rows`
  - Das Surrogatemodell kann fuer diesen Slice nicht robust trainiert werden.
- Mehrere Slices mit unterschiedlichen `FeatureSchemaVersion`-Werten
  - Historie ist nicht homogen und sollte nicht blind zusammengeworfen werden.

## Warum die Slice-Dimensionen wichtig sind

- `MatchStatsMode` trennt Daten mit potenziell stark unterschiedlicher Informationsbasis.
- `SourcePredictionMode` trennt Future- und Reference-Logik.
- `FeatureSchemaVersion` verhindert, dass inhaltlich inkompatible Gewichtsschemata gemeinsam interpretiert werden.
- Ohne diese Dreiteilung waere eine scheinbar grosse Historie oft methodisch irrefuehrend.

## Beispielhafte Interpretation einer Ausgabe

- Viele Zeilen in `predicted / future / bases_v2_hybrid`
  - gutes Zeichen fuer ein konsistentes Future-Surrogate auf dem aktuellen Schema.
- Viele Zeilen in `actual / reference / unknown`
  - typisch fuer Alt-Historien oder fruehere Entwicklungsphasen.
- `Rows < SURROGATE_MIN_HISTORY`
  - der Slice ist sichtbar, aber noch nicht trainingsreif fuer das Surrogatemodell.
- Sehr breite `BatchRange` bei wenig `Rows`
  - Hinweis auf ausgeduennte Historie mit grossen Luecken.
- Gute `BestAvgNLL`, aber schwache `MeanAvgNLL`
  - einzelne gute Runs vorhanden, Slice insgesamt jedoch instabil.

## Typische Fragen, die das Skript beantwortet

- Warum ist das Surrogate in einem Lauf nicht angesprungen?
- Welche Modi dominieren die Historie?
- Gibt es alte BatchID-Kollisionen?
- Ist die Historie schon nach Schema-Versionen sauber getrennt?

## Edge Cases / Notes

- Eine fehlende Datei ist kein Fehler, sondern wird nur gemeldet.
- Eine leere Datei ebenfalls.
- Fehlende Slice-Spalten werden nicht als Schemafehler gewertet.
- Stattdessen wird defensiv auf `unknown` gesetzt, damit Alt-Historien lesbar bleiben.

## Interne Abhaengigkeiten / Imports

- `argparse`
  - CLI-Steuerung.
- `re`
  - Dateinamenbereinigung.
- `pandas`
  - Gruppierung, Crosstab, CSV-I/O.
- `Path`
  - Pfadarbeit.

## Beispiel

```bash
python "Sports Api Data/Testruns/Code/inspect_surrogate_history.py"
```

```bash
python "Sports Api Data/Testruns/Code/inspect_surrogate_history.py" --folder future --detailed
```

```bash
python "Sports Api Data/Testruns/Code/inspect_surrogate_history.py" --split
```

## Beziehung zur Hauptpipeline

- Das Skript trainiert kein Modell.
- Es veraendert keine Bewertungslogik.
- Es hilft nur zu verstehen, welche Historie die Hauptpipeline spaeter sieht.

## Wartungshinweise

- `SURROGATE_MIN_HISTORY` sollte synchron zur Hauptpipeline bleiben.
- Wenn dort der Schwellenwert geaendert wird, muss die Doku und dieses Skript mitziehen.
- Neue Slice-Dimensionen in der Hauptpipeline sollten auch hier sichtbar gemacht werden.

## Risiken und Grenzen

- Die Kollisionserkennung arbeitet nur ueber `BatchID` und `MatchStatsMode`.
- Wenn weitere Identitaetsdimensionen relevant werden, reicht diese Sicht moeglicherweise nicht mehr.
- Das Skript bewertet Datenqualitaet nur grob, nicht semantisch.
- Es gibt keine automatische Reparatur alter Historien.

## Praktische Pruefschritte nach einem Lauf

- Stimmen `Rows` und `BatchCount` grob mit der erwarteten Run-Historie ueberein?
- Tauchen neue `FeatureSchemaVersion`-Werte auf, die in der Hauptpipeline noch nicht aktiv sein sollten?
- Sind Batch-Kollisionen nur Legacy-Artefakte oder entstehen weiterhin neue?
- Entsteht durch `--split` wirklich nur abgeleitete Sicht und keine stillschweigende Quelle fuer andere Skripte?

## Praktischer Nutzen

- Sehr gut geeignet fuer Audits nach Schemawechseln.
- Hilfreich vor der Interpretation von Surrogate-Ergebnissen.
- Spart Zeit, weil sonst dieselben Fragen per ad-hoc CSV-Inspektion beantwortet werden muessten.

## Kurzfazit

- Kleine Codebasis, hoher Diagnosewert.
- Methodisch sauber, weil read-only.
- Besonders nuetzlich in einem Projekt, dessen Historie durch mehrere Modi und Schemawechsel gewachsen ist.
