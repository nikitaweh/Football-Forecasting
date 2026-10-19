# `backtest_matchdays.py`

Source: `Sports Api Data/Testruns/Code/backtest_matchdays.py`

## Ueberblick

Dieses Skript ist der historische Backtest-Treiber fuer die Matchday-Ebene.
Es simuliert fuer bereits gespielte Bundesliga-Spieltage einen damaligen Informationsstand, startet dafuer die Hauptpipeline und archiviert die erzeugten Outputs pro Spieltag in separaten Ordnern.
Die zentrale Schutzmassnahme ist ein Datums-Cutoff, damit das Modell keine spaeteren Spiele als Trainingsdaten sieht.

## Zweck / Responsibilities

- Waehlt Zielspieltage aus.
- Baut aus historischen Resultaten eine Referenzdatei fuer jeden Spieltag.
- Setzt Umgebungsvariablen fuer die Hauptpipeline.
- Startet `AI_match_stats_prediction.py` als Subprozess.
- Kopiert die wichtigsten Artefakte in `Datacollection backtest/MDxx/`.
- Ueberspringt bereits verarbeitete Spieltage.

## Warum das Skript existiert

- Die Hauptpipeline selbst ist auf einzelne Laeufe fokussiert.
- Fuer saisonweite Ruecktests braucht es ein separates Orchestrierungs-Skript.
- Das Treiberskript kapselt die wiederholte Vorbereitung und Archivierung.

## Hauptkonfiguration

- `SEASON = 2025`
- `SCRIPT_PATH`
  - Hauptpipeline, die je Matchday aufgerufen wird.
- `REFERENCE_DIR`
  - Ziel fuer die temporere Referenzdatei.
- `BACKTEST_DIR`
  - Archivordner pro Matchday.
- `OUTPUT_FILES`
  - Welche Artefakte aus dem Referenzordner kopiert werden.
- `DEFAULT_MAX_RUNS = 50`
  - Begrenzung der Laufzeit pro Matchday.
- `DEFAULT_MATCH_STATS_MODE = 'predicted'`
  - Verhindert Post-Match-Leakage ueber echte Match-Stats.

## Ablauf

### 1) Zielmenge bestimmen

- Die CLI erzwingt genau eine Auswahl:
  - `--all`
  - `--matchdays ...`
  - `--random N`
- Optionale Parameter:
  - `--seed`
  - `--max-runs`
  - `--match-stats-mode`

### 2) Matchday-Index laden

- `load_matchday_index()` liest Stammdaten und Match-Stats.
- Es filtert auf bereits gespielte Matches der Ziel-Saison.
- Matchdays werden aus Text in numerische `MD` ueberfuehrt.
- Nur Matches mit vorhandenen Stats bleiben.

### 3) Fixtures fuer einen Spieltag bauen

- `matchday_fixtures(sd, ms, matchday)` sammelt alle MatchIDs eines Spieltags.
- Es zieht `HomeGoals` und `AwayGoals` aus den Stats.
- Daraus wird direkt das Label `Result` abgeleitet.
- Rueckgabe:
  - DataFrame der Referenz-Matches
  - fruehestes Matchdatum als Cutoff-Anker

### 4) Referenzdatei schreiben

- `run_one_matchday(...)` speichert die Fixtures nach
  `Datacollection reference/match_results_references.csv`.
- Diese Datei wird in jeder Iteration ueberschrieben.
- Das ist bewusst so, damit die Hauptpipeline unveraendert bleiben kann.

### 5) Env-Overrides setzen

- `BACKTEST_DATE_CUTOFF`
  - reduziert das Trainingsset auf Spiele vor dem Spieltag.
- `MAX_RUNS_OVERRIDE`
  - begrenzt die Anzahl getesteter Gewichtskombinationen.
- `MATCH_STATS_MODE_OVERRIDE`
  - erzwingt den gewuenschten Match-Stats-Modus.

### 6) Hauptpipeline ausfuehren

- Subprozess:
  - `[sys.executable, str(SCRIPT_PATH)]`
- `capture_output=True`
  - `stdout` und `stderr` werden zentral gesammelt.
- Fehlerfall:
  - `stderr.log`
  - `stdout.log`
  - Rueckgabe `failed`

### 7) Ergebnisse archivieren

- Erfolgsfall:
  - `prediction_weight_runs.csv`
  - `prediction_weight_run_summary.csv`
  - `pareto_front.csv`
  werden nach `MDxx/` kopiert.
- Ausserdem schreibt das Skript eine kleine `meta.txt`.

## Wichtige Funktionen

- `load_matchday_index()`
  - Liefert die Basis fuer alle spaeteren Matchday-Selektionen.
- `matchday_fixtures(sd, ms, matchday)`
  - Baut Referenz-Targets fuer genau einen Spieltag.
- `run_one_matchday(matchday, fixtures, cutoff_date, max_runs, match_stats_mode)`
  - Fuehrt einen isolierten Backtest-Lauf aus und archiviert die Outputs.
- `main()`
  - Verarbeitet CLI-Argumente und iteriert ueber alle Zielspieltage.

## Funktionssignaturen im Code

- `load_matchday_index()`
  - liefert `(sd, ms)` fuer bereits gespielte Saison-Matches mit Stats.
- `matchday_fixtures(sd, ms, matchday)`
  - liefert `(fixtures_df, cutoff_date)` oder `(None, None)`.
- `run_one_matchday(matchday, fixtures, cutoff_date, max_runs, match_stats_mode)`
  - fuehrt einen Matchday-Lauf aus und gibt `ran`, `skipped` oder `failed` zurueck.
- `main()`
  - parst die CLI, bestimmt Targets und orchestriert alle Einzellaeufe.

## Inputs

- `Stammdaten_78.csv`
- `match_statistics_filtered_78.csv`
- Hauptpipeline-Skript `AI_match_stats_prediction.py`

## Outputs

- Pro Matchday ein Ordner `Datacollection backtest/MDxx/`
- Darin typischerweise:
  - `prediction_weight_runs.csv`
  - `prediction_weight_run_summary.csv`
  - `pareto_front.csv`
  - `meta.txt`
  - bei Fehlern `stdout.log` und `stderr.log`

## Inputs / Outputs genauer

Temporer Input fuer die Hauptpipeline:

- `Datacollection reference/match_results_references.csv`
  - wird pro Matchday neu geschrieben.

Archivierte Kernartefakte je Matchday:

- `prediction_weight_runs.csv`
- `prediction_weight_run_summary.csv`
- `pareto_front.csv`
- `meta.txt`

Inhalt von `meta.txt`:

- Matchday-Nummer
- gesetzter Cutoff
- Anzahl Fixtures
- Anzahl kopierter Output-Dateien

## Side-Effects

- Ueberschreibt die aktive Datei `Datacollection reference/match_results_references.csv`.
- Startet rechenintensive Subprozesse.
- Legt Backtest-Unterordner an.
- Kopiert Artefakte in neue Ablagen.

## Prozess- und Dateisystemlogik

- Das Skript nutzt bewusst einen separaten Subprozess statt eines Imports der Hauptpipeline.
- Dadurch bleiben globale Modulzustande und Env-Overrides klar getrennt.
- Fehler eines Matchdays koennen so protokolliert werden, ohne die Python-Session zu kontaminieren.
- Resume funktioniert ueber die Existenz von `prediction_weight_run_summary.csv`.
- Das ist pragmatisch, aber kein vollstaendiger Integritaetscheck.

## Methodische Logik

- Historische Ruecktests sind nur sinnvoll, wenn spaetere Daten konsequent ausgeschlossen werden.
- Genau dafuer setzt das Skript `BACKTEST_DATE_CUTOFF`.
- Zusaetzlich erzwingt der Default `MATCH_STATS_MODE='predicted'`, damit keine echten Ist-Statistiken des Zielspiels in die Bewertung einfliessen.

## Warum `MAX_RUNS=50` sinnvoll ist

- Die Hauptpipeline kann sonst sehr lange laufen.
- Ein Backtest ueber viele Spieltage multipliziert diese Kosten.
- Das Skript priorisiert damit Serienfaehigkeit ueber maximale Suche pro Spieltag.

## Typische CLI-Beispiele

```bash
python "Sports Api Data/Testruns/Code/backtest_matchdays.py" --all
```

```bash
python "Sports Api Data/Testruns/Code/backtest_matchdays.py" --matchdays 5 10 15 --max-runs 25
```

```bash
python "Sports Api Data/Testruns/Code/backtest_matchdays.py" --random 8 --seed 42
```

## Edge Cases / Notes

- Wenn ein Spieltag schon einen Summary-Output hat, wird er uebersprungen.
- Fehlende oder nicht parsebare Matchdays werden nicht erzwungen.
- Wenn fuer einen Spieltag keine Stats vorhanden sind, entsteht kein Lauf.
- Das Skript nimmt an, dass `SCRIPT_PATH` mit den gesetzten Env-Variablen kompatibel bleibt.

## Risiken

- Die globale Referenzdatei im Live-Referenzordner wird pro Spieltag ersetzt.
- Wer parallel andere Referenzlaeufe plant, kann sich den Zustand unbeabsichtigt zerlegen.
- Subprozess-Fehler werden nur per Logdateien konserviert, nicht automatisch erneut versucht.
- Bereits vorhandene `MDxx/`-Ordner mit teilweiser oder veralteter Ausgabe gelten durch die Summary-Datei als erledigt.

## Methodische Hinweise zur Interpretation

- `MATCH_STATS_MODE='predicted'` ist fuer faire Ruecktests die robustere Voreinstellung.
- `actual` kann zwar bessere Kennzahlen erzeugen, mischt aber Post-Match-Information ein.
- Der frueheste Matchtermin eines Spieltags ist ein konservativer Cutoff.
- Das vermeidet Leakage, schliesst aber bei verteilten Spieltagsdaten unter Umstaenden auch zulaessige spaetere Vorinformationen aus.
- `MAX_RUNS` ist nicht nur Laufzeitsteuerung, sondern beeinflusst direkt die Stabilitaet des Vergleichs zwischen Matchdays.
- Kleine Run-Budgets koennen Matchdays mit hohem Suchrauschen systematisch benachteiligen.

## Interne Abhaengigkeiten / Imports

- `argparse`
  - CLI-Steuerung.
- `subprocess`
  - Start der Hauptpipeline.
- `shutil`
  - Kopieren der Artefakte.
- `random`
  - Zufallsauswahl bei `--random`.
- `pandas`
  - Datenvorbereitung fuer Referenzzeilen.
- `Path`, `os`, `sys`
  - Pfade und Prozessumgebung.

## Inputs / Outputs genauer

Input-Spalten aus Stats:

- `MatchID`
- `Home Goals`
- `Away Goals`

Output-Spalten in der temporeren Referenzdatei:

- `MatchID`
- `HomeGoals`
- `AwayGoals`
- `Result`

## Beziehung zur Hauptpipeline

- Das Skript veraendert die Modelllogik nicht.
- Es setzt nur Rahmenbedingungen fuer den Lauf.
- Die Qualitaet des Backtests haengt deshalb direkt von den Schutzmechanismen in `AI_match_stats_prediction.py` ab.
- Besonders wichtig sind:
  - Ausschluss der Zielmatches aus dem Training
  - Datums-Cutoff
  - Match-Stats-Modus

## Praktische Nachkontrollen

- Pruefen, ob jeder `MDxx`-Ordner eine `meta.txt` und Summary-Datei besitzt.
- Bei Fehlern zuerst `stderr.log` lesen.
- Danach kontrollieren, ob `BACKTEST_DATE_CUTOFF` im Pipeline-Log plausibel war.

## Verbesserungspotenzial

- Eine Sicherung und Rueckwiederherstellung der aktiven Referenzdatei waere robuster.
- Ein Resume-Mechanismus ueber Dateiintegritaet statt nur Datei-Existenz waere verlaesslicher.
- Parallelisierung waere moeglich, kollidiert aber derzeit mit der global ueberschriebenen Referenzdatei.
- Eine feste Manifest-Datei pro `MDxx` mit Hashes der Outputs waere fuer Reproduzierbarkeit noch besser.

## Kurzfazit

- Das Skript ist methodisch sinnvoll, weil es Leakage aktiv begrenzt.
- Es bleibt aber absichtlich pragmatisch und arbeitet mit globalen Dateien.
- Das macht es einfach einsetzbar, aber nicht vollstaendig nebenlaeufig oder transaktionssicher.

## Aktuelle Code-Referenz

### Ueberblick und Zweck

backtest_matchdays.py - historical matchday backtest harness.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `load_matchday_index()`
  Return Stammdaten rows for the season's played matches that have stats.
- `matchday_fixtures(sd, ms, matchday)`
  Build the (fixtures-with-results, earliest-date) tuple for a matchday.
- `run_one_matchday(matchday, fixtures, cutoff_date, max_runs, match_stats_mode)`
  Run the pipeline for one matchday, copying outputs to a per-matchday folder.
- `main()`
  Verwendet `argparse.ArgumentParser`, `parser.add_mutually_exclusive_group`, `group.add_argument`, `parser.add_argument`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `pd.read_csv(STAMMDATEN_PATH, parse_dates=['Date'])`
- `pd.read_csv(STATS_PATH)`
- `fixtures.to_csv(ref_path, index=False)`
- `subprocess.run([sys.executable, str(SCRIPT_PATH)], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')`
- `(target_dir / 'stderr.log').write_text(result.stderr or '', encoding='utf-8')`
- `(target_dir / 'stdout.log').write_text(result.stdout or '', encoding='utf-8')`
- `shutil.copy2(src, target_dir / fname)`
- `(target_dir / 'meta.txt').write_text(f'Matchday: {matchday}\nCutoff: {cutoff_date.date()}\nFixtures: {len(fixtures)}\nOutputs copied: {copied}\n', encoding='utf-8')`

### Konfiguration und Environment

- `SEASON = 2025`
- `TESTRUNS_PATH = Path('C:/AI Projekt/KI-Projekt/Sports Api Data/Testruns')`
- `DATA_PATH = Path('C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection')`
- `SCRIPT_PATH = TESTRUNS_PATH / 'Code' / 'AI_match_stats_prediction.py'`
- `REFERENCE_DIR = TESTRUNS_PATH / 'Datacollection reference'`
- `BACKTEST_DIR = TESTRUNS_PATH / 'Datacollection backtest'`
- `STAMMDATEN_PATH = DATA_PATH / 'Stammdaten_78.csv'`
- `STATS_PATH = DATA_PATH / 'match_statistics_filtered_78.csv'`
- `OUTPUT_FILES = ['prediction_weight_runs.csv', 'prediction_weight_run_summary.csv', 'pareto_front.csv', 'future_outcome_table_ensemble.csv']`
- `DEFAULT_MAX_RUNS = 50`
- `DEFAULT_MATCH_STATS_MODE = 'predicted'`
- `group.add_argument('--all', action='store_true', help='Backtest every played matchday in the season.')`
- `group.add_argument('--matchdays', nargs='+', type=int, help='Backtest specific matchdays (e.g. --matchdays 5 10 15).')`
- `group.add_argument('--random', type=int, metavar='N', help='Backtest N randomly chosen matchdays.')`
- `parser.add_argument('--seed', type=int, default=42, help='Random seed for --random.')`
- `parser.add_argument('--max-runs', type=int, default=DEFAULT_MAX_RUNS, help=f'BART weight-sample iterations per matchday (default: {DEFAULT_MAX_RUNS}).')`
- `parser.add_argument('--match-stats-mode', default=DEFAULT_MATCH_STATS_MODE, choices=['predicted', 'actual', 'off'], help=f'Match-stats mode for the outcome model (default: {DEFAULT_MATCH_STATS_MODE}). "predicted" avoids post-match leakage; "actual" uses rea...`

### Imports und interne Abhaengigkeiten

- `import argparse`
- `import os`
- `import random`
- `import shutil`
- `import subprocess`
- `import sys`
- `from pathlib import Path`
- `import pandas as pd`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "Sports Api Data/Testruns/Code/backtest_matchdays.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Keine expliziten `except`-Handler im Modul; Fehler koennen an den Aufrufer weitergegeben werden.
- Auswertungen nur auf identischen MatchIDs, Zeitraeumen und Zieldefinitionen vergleichen.
- Nachtraegliche Wahrscheinlichkeitsvarianten ersetzen keinen zeitlich getrennten Validierungslauf.
- Fehlende Werte, Join-Verluste und Zahl der ausgewerteten Spiele gemeinsam mit Kennzahlen berichten.
