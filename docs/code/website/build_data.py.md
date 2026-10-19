# `build_data.py`

Source: `website/build_data.py`

## Ueberblick

Dieses Skript transformiert Modell-CSV-Dateien in `website/data.js`, damit die Webansicht ohne eigenen Backend-Call laden kann.
Es verbindet Vorhersagen mit ggf. bereits bekannten Ergebnissen und schreibt ein fertiges JavaScript-Payload in das Frontend-Verzeichnis.

## Zweck / Responsibilities

- Waehlt eine Datenquelle ueber `SOURCE`.
- Liest Vorhersage-CSV und optional Ergebnis-CSV.
- Baut ein JSON-artiges Payload aus Meta, Teams und Matches.
- Schreibt `window.ORAKEL_DATA = ...` nach `website/data.js`.

## Datenquellen

- `SOURCES['live']`
  - aktueller Export aus `Datacollection future` plus Referenzresultate
- `SOURCES['md33']`
  - statischer Snapshot unter `website/matchdays/`

## Wichtige Konstanten

- `SOURCE`
  - schaltet zwischen Live-Daten und Snapshot.
- `META`
  - statische Metadaten fuer Liga, Saison, Matchday und Modellbeschreibung.
- `TEAMS`
  - Zuordnung von Teamname zu Team-ID, Kuerzel, Farbe und Logo.
- `RESULT_TO_OUTCOME`
  - Mapping von `H/D/A` auf Web-Outcome-Bezeichner.

## Wichtige Funktionen

- `num(value, default=0.0)`
  - robustes Float-Coercion fuer CSV-Felder.
- `load_results()`
  - liest tatsaechliche Ergebnisse per `MatchID`.
- `load_matches(results)`
  - baut die Matchliste samt Prediction-Block und optionalem Resultat.
- `main()`
  - orchestriert Laden, Payload-Bau und Schreiben.

## Inputs / Outputs

Inputs:

- `future_outcome_table.csv` oder Snapshot-Predictions
- `match_results_references.csv` oder Snapshot-Results

Output:

- `website/data.js`

## Side-Effects

- Ueberschreibt `website/data.js`.
- Aendert keine CSV-Quelldatei.

## Datenlogik

- `load_results()` liefert ein Dict `MatchID -> Ergebnisobjekt`.
- `load_matches()` liest Predictions zeilenweise.
- Jedes Match enthaelt:
  - Identitaet und Teams
  - Vorhersagewahrscheinlichkeiten
  - prognostizierte Tore / Scoreline
  - optional das echte Ergebnis
- Anschliessend wird nach `confidence` absteigend sortiert.

## Konfiguration / Notes

- `SOURCE = "md33"` bedeutet aktuell: Snapshot statt Live-Modelloutput.
- `META["configuration"]` wird dynamisch aus der ersten Prediction-Zeile gezogen.
- Teamnamen muessen exakt zu `TEAMS` passen, sonst fehlen im Frontend Branding-Informationen.

## Interne Abhaengigkeiten

- `csv`
  - zeilenweises Lesen.
- `json`
  - Serialisierung des Payloads.
- `os`
  - Pfadaufloesung.

## Beispiel

```bash
python website/build_data.py
```

## Edge Cases / Risiken

- Die Datei mischt statische Metadaten mit dynamischer CSV-Logik.
- Falsch kodierte Teamnamen koennen zu fehlenden Logos oder Farben fuehren.
- Wenn `SOURCE` auf einen Snapshot zeigt, ist die Website bewusst nicht live.

## Aktuelle Code-Referenz

### Ueberblick und Zweck

build_data.py  --  Generates website/data.js from the model's CSV exports.

Diese Referenz beschreibt den vorhandenen Code statisch; sie ist kein Nachweis eines erfolgreichen Daten- oder Modelllaufs.

### Wichtige Klassen und Funktionen

- `num(value, default=0.0)`
  Verwendet `float`. Rueckgabe unter anderem: `float(value)`.
- `load_config(league)`
  Verwendet `os.path.join`, `os.path.exists`, `sorted`, `os.listdir`. Rueckgabe unter anderem: `cfg`.
- `load_stammdaten(path)`
  MatchID -> {"matchday": raw string, "season": year string}
- `matchday_number(raw)`
  Trailing integer of a Stammdaten matchday string, or None. 'Regular Season - 34' -> 34, 'Group Stage - 1' -> 1.
- `matchday_label(raw)`
  'Regular Season - N' renders as 'Matchday N'; anything else (cup stages like 'Group Stage - 1') passes through verbatim.
- `season_label(year, fmt)`
  'cross-year': 2025 -> '2025/26' (club seasons); 'single-year': '2026'.
- `derive_meta_fields(matches, stammdaten)`
  Vote the matchday/season for this batch of predictions via the Stammdaten join. Mixed or missing MatchIDs are warned, not fatal.
- `load_results(path)`
  MatchID -> {homeGoals, awayGoals, outcome}
- `load_matches(path, results)`
  Returns (matches, configuration_label).
- `_files_identical(a, b)`
  Verwendet `open`, `fa.read`, `fb.read`. Rueckgabe unter anderem: `fa.read() == fb.read()`.
- `write_snapshot(md_number, predictions_csv, results_csv)`
  Copy the live source CSVs to matchdays/md{N}_*.csv. Results always win (they trickle in over a weekend); a differing predictions snapshot is replaced but loudly, since it means the model was re-run for a matchday we already archived.
- `build(league='bundesliga', matchday=None)`
  Build data.js for a league. matchday=None -> live model output (snapshots the inputs); matchday=N -> rebuild from matchdays/md{N}_*.csv. Returns a summary dict for callers that log (refresh_data.py).
- `main()`
  Verwendet `argparse.ArgumentParser`, `parser.add_argument`, `parser.parse_args`, `logging.basicConfig`.

### Inputs, Outputs und Seiteneffekte

Direkt im Modul vorkommende Daten- und Prozessoperationen (Ausdruecke behalten lokale Variablennamen):

- `open(path, 'r', encoding='utf-8')`
- `json.load(fh)`
- `open(path, 'r', encoding='utf-8-sig', newline='')`
- `row.get('MatchID')`
- `row.get('Matchday')`
- `row.get('Season')`
- `stammdaten.get(str(m['id']))`
- `row.get('HomeGoals')`
- `row.get('AwayGoals')`
- `RESULT_TO_OUTCOME.get((row.get('Result') or '').strip(), None)`
- `row.get('Result')`
- `row.get('RecommendationLabel')`
- `row.get('RecommendedRunID')`
- `row.get('MatchDate')`
- `row.get('HomeTeam')`
- `row.get('AwayTeam')`
- `row.get('MostLikelyOutcome')`
- `row.get('WinProb')`
- `row.get('DrawProb')`
- `row.get('LoseProb')`
- `row.get('MostLikelyOutcomeProbability')`
- `row.get('PredictedHomeGoals')`

### Konfiguration und Environment

- `HERE = os.path.dirname(os.path.abspath(__file__))`
- `ROOT = os.path.dirname(HERE)`
- `CONFIG_DIR = os.path.join(HERE, 'config', 'leagues')`
- `SNAPSHOT_DIR = os.path.join(HERE, 'matchdays')`
- `RESULT_TO_OUTCOME = {'H': 'HomeWin', 'D': 'Draw', 'A': 'AwayWin'}`
- `parser.add_argument('--league', default='bundesliga', help='league config name in website/config/leagues/ (default: bundesliga)')`
- `parser.add_argument('--matchday', type=int, default=None, help='rebuild from a saved snapshot in website/matchdays/ instead of the live model output')`

### Imports und interne Abhaengigkeiten

- `import argparse`
- `import csv`
- `import json`
- `import logging`
- `import os`
- `import shutil`
- `from collections import Counter`
- `from datetime import datetime`

Lokale Imports benoetigen den passenden Modul-Suchpfad; dynamische Imports koennen weitere Dateien laden.

### Kurzes Beispiel

Aufruf aus dem Repository-Hauptverzeichnis mit eingerichteter Python-Umgebung:

```powershell
python "website/build_data.py"
```

Der Aufruf verwendet die im Skript gesetzten Defaults; die oben genannten Schreib-, Netzwerk- oder Scheduler-Operationen koennen dabei ausgefuehrt werden.

### Edge Cases und Hinweise

- Explizit behandelte Fehler: `(TypeError, ValueError)`.
