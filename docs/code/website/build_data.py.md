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
