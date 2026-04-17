# `update_match_results_references.py`

Source: `Sports Api Data/Testruns/Code/update_match_results_references.py`

## Ueberblick

Dieses Hilfsskript synchronisiert die Referenzdatei `match_results_references.csv`
mit den tatsaechlich vorliegenden Resultaten aus
`match_statistics_filtered_78.csv`. Es ist bewusst als kleines CLI-Werkzeug
gebaut, damit der Referenzdatensatz fuer Auswertungen von
`AI_match_stats_prediction.py` schnell aktualisiert werden kann, ohne die
gesamte Modellpipeline zu starten.

Im Standardmodus werden nur MatchIDs aktualisiert, die bereits in der
Referenzdatei existieren. Damit bleibt das Referenzset kontrollierbar klein und
stabil. Optional kann das Skript mit `--add-missing` auch neue gespielte Matches
anhaengen.

## Zweck / Responsibilities

- Liest die bestehende Referenzdatei robust ein, auch wenn sie leer ist oder
  ohne Header gespeichert wurde.
- Liest die Match-Statistiken aus dem Bundesliga-Filtered-Datenbestand.
- Erkennt relevante Spalten tolerant gegen unterschiedliche Schreibweisen wie
  `MatchID`, `Match Id` oder `Match_ID`.
- Berechnet aus Heim- und Auswaertstoren das Ergebnislabel `H`, `D` oder `A`.
- Aktualisiert bestehende Referenzzeilen per `MatchID`.
- Fuegt bei Bedarf neue MatchIDs hinzu, wenn `--add-missing` gesetzt ist.
- Gibt vor dem Schreiben eine kompakte Zusammenfassung der verarbeiteten Zeilen
  auf `stdout` aus.
- Unterstuetzt einen `--dry-run`, um die Auswirkungen vor dem Schreiben zu
  pruefen.

## Ablauf In Kurzform

1. CLI-Argumente parsen.
2. Projektwurzel und Standardpfade aus dem Skriptstandort ableiten.
3. Vorhandene Referenzdatei tolerant laden.
4. Match-Statistiken laden und Zielspalten identifizieren.
5. Nur Zeilen mit gueltigen MatchIDs und Torwerten behalten.
6. Ergebnislabel aus den Toren berechnen.
7. Bestaende und Updates ueber `MatchID` zusammenfuehren.
8. Kennzahlen zu aktualisierten und neu hinzugefuegten IDs ausgeben.
9. Optional schreiben oder bei `--dry-run` ohne Dateiaenderung beenden.

## Wichtige Funktionen

### `_norm_col(name: str) -> str`

- Normalisiert Spaltennamen auf Kleinbuchstaben und entfernt alle Zeichen ausser
  Buchstaben und Ziffern.
- Wird verwendet, um uneinheitliche CSV-Header robust vergleichen zu koennen.

### `_find_col(df: pd.DataFrame, *candidates: str) -> str | None`

- Baut ein Lookup ueber normalisierte Spaltennamen.
- Gibt den ersten vorhandenen Kandidaten zurueck.
- Liefert `None`, wenn keine passende Spalte gefunden wird.

### `_outcome_from_goals(home_goals: float, away_goals: float) -> str`

- Wandelt Torwerte in das Ergebnissymbol um.
- `H` bedeutet Heimsieg, `A` Auswaertssieg, `D` Unentschieden.

### `load_existing_reference(path: Path) -> pd.DataFrame`

- Liest die bestehende Referenzdatei.
- Behandelt nicht vorhandene oder leere Dateien als leeren, aber gueltigen
  DataFrame mit den Zielspalten.
- Faellt auf einen Header-losen CSV-Import zurueck, wenn die erwarteten
  Spaltennamen fehlen.
- Erzwingt numerische `MatchID`, `HomeGoals` und `AwayGoals`.
- Bereinigt ungueltige `Result`-Werte auf `pd.NA`.

### `build_updates_from_match_stats(match_stats_path: Path) -> pd.DataFrame`

- Liest die Match-Statistikdatei.
- Sucht die benoetigten Spalten tolerant ueber alternative Namen.
- Bricht mit einem klaren `ValueError` ab, falls Pflichtspalten fehlen.
- Entfernt Zeilen ohne gueltige IDs oder Tore.
- Konvertiert Tore nach `int`, berechnet `Result` und dedupliziert per
  `MatchID`, wobei die letzte Zeile gewinnt.

### `merge_reference(existing: pd.DataFrame, updates: pd.DataFrame, *, add_missing: bool) -> pd.DataFrame`

- Fuehrt bestehende Referenzen und neue Resultate zusammen.
- Ueberschreibt fuer gemeinsame `MatchID`s die Spalten `HomeGoals`,
  `AwayGoals` und `Result`.
- Kann neue IDs optional anhaengen.
- Erzwingt am Ende wieder einen sauberen `MatchID`-Integerbestand.

### `parse_args(argv: list[str]) -> argparse.Namespace`

- Definiert die CLI-Optionen fuer Projektwurzel, Inputdatei, Outputdatei,
  `--add-missing` und `--dry-run`.

### `main(argv: list[str]) -> int`

- Verbindet alle Teilschritte zum eigentlichen CLI-Lauf.
- Leitet Standardpfade relativ zum Skriptstandort ab.
- Fuehrt Validierung, Zusammenfuehrung, Reporting und optionales Schreiben aus.

## Pfade Und Standardverhalten

- `script_dir = Path(__file__).resolve().parent`:
  Verzeichnis des Skripts selbst.
- `project_root = script_dir.parents[2]`:
  Standard-Projektwurzel, wenn `--project-root` nicht gesetzt ist.
- Standard-Match-Stats-Datei:
  `Sports Api Data/Bundesliga/Filtered/Datacollection/match_statistics_filtered_78.csv`
- Standard-Output:
  `Sports Api Data/Testruns/Datacollection reference/match_results_references.csv`

Diese Pfadlogik ist direkt auf das aktuelle Repo-Layout abgestimmt. Das Skript
bleibt trotzdem portabel, weil beide Hauptpfade per CLI ueberschrieben werden
koennen.

## CLI-Argumente

- `--project-root`:
  Erzwingt eine konkrete Projektwurzel statt der automatischen Ableitung.
- `--match-stats`:
  Alternative Quelle fuer die Match-Statistikdatei.
- `--out`:
  Alternative Zielpfad fuer die aktualisierte Referenzdatei.
- `--add-missing`:
  Fuegt neue gespielte MatchIDs hinzu, statt nur bestehende IDs zu aktualisieren.
- `--dry-run`:
  Berechnet und meldet Aenderungen, schreibt aber keine Datei.

## Inputs / Outputs / Side Effects

### Inputs

- Eine bestehende oder leere `match_results_references.csv`.
- Eine Match-Statistikdatei mit MatchID sowie Heim- und Auswaertstoren.
- Optionale CLI-Parameter fuer abweichende Projektpfade.

### Outputs

- Ein DataFrame mit den Spalten `MatchID`, `HomeGoals`, `AwayGoals`, `Result`.
- Konsolenmeldungen mit Anzahl gefundener Ergebnisse, aktualisierter IDs und
  neu hinzugefuegter IDs.
- Eine aktualisierte `match_results_references.csv`, sofern kein `--dry-run`
  aktiv ist.

### Side Effects

- Legt den Zielordner bei Bedarf mit `mkdir(parents=True, exist_ok=True)` an.
- Ueberschreibt die Ziel-CSV komplett mit dem neu gemergten Inhalt.
- Gibt Fehlermeldungen im Ausnahmefall auf `stderr` aus.

## Datenschema

### Erwartete Zielspalten

- `MatchID`: numerische Matchkennung.
- `HomeGoals`: Heimtore als Zahl.
- `AwayGoals`: Auswaertstore als Zahl.
- `Result`: `H`, `D` oder `A`.

### Unterstuetzte Varianten in der Match-Stats-Quelle

- Match-ID:
  `MatchID`, `Match Id`, `Match_ID`
- Heimtore:
  `HomeGoals`, `Home Goals`, `Home_Goals`
- Auswaertstore:
  `AwayGoals`, `Away Goals`, `Away_Goals`

## Interne Abhaengigkeiten / Imports

- `argparse`: CLI-Interface.
- `sys`: Rueckgabe des Exit-Status und Ausgabe von Fehlern.
- `pathlib.Path`: robuste Pfadverarbeitung ohne manuelles String-Basteln.
- `pandas`: CSV-I/O und tabellarische Transformationen.
- `__future__.annotations`: erlaubt moderne Typannotationen ohne String-Literale
  fuer Vorwaertsreferenzen.

## Beispiel

Standardlauf:

```bash
python "Sports Api Data/Testruns/Code/update_match_results_references.py"
```

Nur pruefen, ohne zu schreiben:

```bash
python "Sports Api Data/Testruns/Code/update_match_results_references.py" --dry-run
```

Bestehende IDs aktualisieren und alle neuen gespielten Matches anhaengen:

```bash
python "Sports Api Data/Testruns/Code/update_match_results_references.py" --add-missing
```

Alternative Pfade verwenden:

```bash
python "Sports Api Data/Testruns/Code/update_match_results_references.py" ^
  --project-root "C:/AI Projekt/KI-Projekt" ^
  --match-stats "C:/tmp/match_statistics_filtered_78.csv" ^
  --out "C:/tmp/match_results_references.csv"
```

## Typische Konsolenausgabe

- `Match stats rows with results: ...`
- `Existing references before: ...`
- `References after merge: ...`
- `Updated existing MatchIDs: ...`
- `Newly added MatchIDs: ...`
- `Output: ...`

Diese Ausgabe ist bewusst operational gehalten und eignet sich fuer schnelle
Pruefungen in einer lokalen Testrun-Schleife oder in Automationen.

## Edge Cases / Notes

- Wenn die Output-Datei nicht existiert, liefert `load_existing_reference` einen
  leeren Bestand. Ohne `--add-missing` fuehrt das zu einer leeren Ausgabe.
- Header-lose CSV-Dateien werden weiter unterstuetzt, solange die ersten vier
  Spalten dem erwarteten Schema entsprechen.
- Doppelte `MatchID`s in den Match-Statistiken werden per `keep='last'`
  aufgeloest. Spaetere Zeilen haben also Vorrang.
- Nicht numerische oder unvollstaendige Torwerte werden verworfen und gelangen
  nicht in das Ergebnis.
- `merge_reference` sortiert neue IDs nur beim Anhaengen ueber den Index; die
  Reihenfolge bestehender Daten bleibt ansonsten weitgehend erhalten.
- Der Rueckgabewert ist `0`, solange keine Ausnahme auftritt; Fehler werden
  nicht intern geschluckt.
- Das Skript aktualisiert bewusst nur Ergebnisdaten und keine weiteren
  Match-Metadaten wie Teams oder Datum.

## Zusammenspiel Mit `AI_match_stats_prediction.py`

- Die Ausgabedatei entspricht dem Referenzformat, das die
  Outcome-Pipeline im `reference`-Modus erwartet.
- Damit laesst sich der Bewertungsdatensatz pflegen, ohne die grosse
  Vorhersagepipeline anzufassen.
- Besonders nuetzlich ist der `--dry-run`, wenn zunaechst nur geprueft werden
  soll, ob neue Match-Ergebnisse fuer Referenztests vorliegen.

## Letzte beobachtete Aenderung

Im aktuellen Stand ist dieses Skript neu hinzugekommen. Es trennt die Pflege von
`match_results_references.csv` aus der Hauptpipeline heraus und bietet dafuer
ein eigenes, wiederverwendbares CLI-Werkzeug mit optionalem `--add-missing` und
`--dry-run`.
