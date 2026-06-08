# `bwin_historical_odds_download.py`

Source: `Sports Api Data/Testruns/BWIN Odds/Code/bwin_historical_odds_download.py`

## Ueberblick

Dieses Skript laedt historische Bundesliga-Quoten von `football-data.co.uk` und formatiert sie so, dass sie zur bestehenden BWIN-Output-Struktur passen.
Der Zweck ist nicht Scraping der BWIN-Seite selbst, sondern ein belastbarer CSV-Import fuer bereits gespielte Partien.
Dadurch lassen sich spaetere Backtests gegen echte historische Marktquoten fahren.

## Zweck / Responsibilities

- Laedt pro Saison eine CSV von `football-data.co.uk`.
- Mappt externe Teamnamen auf interne API-Football-Team-IDs.
- Verknuepft Quotenzeilen mit `MatchID` aus `Stammdaten_78.csv`.
- Normalisiert Datum, Uhrzeit und Ausgabeformat.
- Schreibt eine timestamped CSV in den BWIN-Datacollection-Ordner.
- Protokolliert Coverage, fehlende Mappings und nicht matchbare Fixtures.

## Einordnung im Projekt

- Das Skript ist ein Hilfswerkzeug fuer Backtests und Benchmarking.
- Es erzeugt keine Modellvorhersagen.
- Es liefert Input fuer Auswertungen wie `analyze_backtest_results.py`.
- Die Ausgabe kann die Live-Quote-Datei strukturell ergaenzen oder ersetzen.

## Datenquellen

- `STAMMDATEN_PATH`: interne Match-Tabelle mit `MatchID`, `Season`, Home/Away-Team-IDs.
- `TEAMS_PATH`: im aktuellen Skript definiert, aber nicht aktiv genutzt.
- `BASE_URL`: `https://www.football-data.co.uk/mmz4281/{season_code}/D1.csv`
- `SEASONS`: Zuordnung zwischen sprechendem Saisonlabel, football-data-Code und API-Saisonjahr.

## Ausgabedatei

- Zielordner: `Sports Api Data/Testruns/BWIN Odds/Datacollection`
- Dateiname: `bwin_historical_odds_<timestamp>.csv`
- Encoding: `utf-8-sig`
- Sortierung: `season`, `match_date`, `home_team`

## Kernlogik

### 1) Saisondownload

- `download_season(...)` baut die URL aus `BASE_URL`.
- Der Request verwendet einen festen Browser-`User-Agent`.
- Das Timeout ist mit `REQUEST_TIMEOUT_SECONDS = 30` bewusst konservativ.
- Die Antwort wird explizit auf `latin-1` gesetzt.
- Anschliessend wird die CSV ueber `pandas.read_csv(StringIO(...))` eingelesen.

### 2) Match-Lookup aufbauen

- `load_match_lookup()` liest `Stammdaten_78.csv`.
- Der Schluessel lautet `(api_season, home_team_id, away_team_id)`.
- Der Wert ist die interne `MatchID`.
- Dieser Lookup ist der zentrale Join-Mechanismus fuer die spaetere Verknuepfung.

### 3) Datum normalisieren

- `normalize_date(raw_date, raw_time)` akzeptiert `DD/MM/YYYY` und `DD/MM/YY`.
- Rueckgabe ist ein Tupel aus ISO-Datum und lesbarer Anzeigeform.
- Nicht parsebare Datumswerte werden nicht hart verworfen.
- Stattdessen wird `("", raw_date)` bzw. eine leere ISO-Komponente geliefert.

### 4) Output-Zeilen bauen

- `build_output_rows(...)` prueft zuerst die Pflichtspalten:
  - `HomeTeam`
  - `AwayTeam`
  - `BWH`
  - `BWD`
  - `BWA`
- Fehlende Pflichtspalten fuehren zu `RuntimeError`.
- Zeilen ohne vollstaendige BWIN-Quote werden gezaehlt und uebersprungen.
- Teamnamen werden ueber `FD_TO_API_TEAM_ID` auf IDs gemappt.
- Nur wenn beide IDs bekannt sind, versucht das Skript den `MatchID`-Lookup.
- Nicht gemappte Teamnamen und nicht gefundene Fixtures werden gesammelt.

### 5) Schreiben

- `write_output(rows)` legt den Zielordner bei Bedarf an.
- Die Daten werden in einen DataFrame ueberfuehrt.
- Vor dem Schreiben erfolgt eine deterministische Sortierung.
- Der Dateiname enthaelt den lokalen Zeitstempel aus `now_local_stamp()`.

## Wichtige Funktionen

- `now_utc_iso()`
  - Liefert einen UTC-Zeitstempel fuer `scraped_at_utc`.
- `now_local_stamp()`
  - Erzeugt den Dateinamensuffix fuer die Output-Datei.
- `download_season(season_label, season_code, api_season)`
  - Laedt und annotiert die Rohdaten je Saison.
- `load_match_lookup()`
  - Erstellt die interne Match-Zuordnung auf Basis der Stammdaten.
- `normalize_date(raw_date, raw_time)`
  - Vereinheitlicht Date/Time-Angaben aus dem Lieferformat.
- `build_output_rows(raw_df, match_lookup)`
  - Transformiert externe CSV-Zeilen in das projektspezifische Ausgabeschema.
- `write_output(rows)`
  - Persistiert die zusammengefuehrten Zeilen.
- `main()`
  - Orchestriert Download, Transformation, Logging und Schreiben.

## Funktionssignaturen im Code

- `now_utc_iso()`
  - liefert einen UTC-Zeitstempel als String.
- `now_local_stamp()`
  - liefert den lokalen Zeitstempel fuer Dateinamen.
- `download_season(season_label, season_code, api_season)`
  - laedt eine Saison-CSV und annotiert sie mit Metadaten.
- `load_match_lookup()`
  - erzeugt `{(season, home_team_id, away_team_id): MatchID}`.
- `normalize_date(raw_date, raw_time)`
  - liefert `(iso_date, display_date)`.
- `build_output_rows(raw_df, match_lookup)`
  - liefert `(rows, skipped_no_odds, unmapped_teams, unmatched_fixtures)`.
- `write_output(rows)`
  - schreibt die CSV und liefert `(out_file, row_count)`.
- `main()`
  - Einstiegspunkt fuer Download, Transformation und Logging.

## Inputs

- HTTP-Antworten pro definierter Saison.
- CSV-Tabellen aus `Stammdaten_78.csv`.
- Harte Mapping-Konstanten fuer Teamnamen.

## Outputs

- Historische Quote-Datei mit diesen zentralen Feldern:
  - `scraped_at_utc`
  - `season`
  - `match_id`
  - `match_date`
  - `match_date_raw`
  - `home_team`
  - `away_team`
  - `home_team_id`
  - `away_team_id`
  - `home_goals`
  - `away_goals`
  - `result`
  - `odd_home_win_1`
  - `odd_draw_x`
  - `odd_away_win_2`
  - `market`
  - `source`
  - `source_url`

## Inputs / Outputs genauer

Pflichtspalten der externen CSV:

- `HomeTeam`
- `AwayTeam`
- `BWH`
- `BWD`
- `BWA`

Nutzbare Zusatzspalten aus der Quelle:

- `Date`
- `Time`
- `FTHG`
- `FTAG`
- `FTR`

Interne Join-Schluessel:

- `Season`
- `Home Team ID`
- `Away Team ID`
- `MatchID`

## Side-Effects

- Erstellt neue CSV-Dateien im Datacollection-Ordner.
- Fuehrt Netzwerkanfragen gegen einen externen Datenanbieter aus.
- Schreibt Status- und Warnmeldungen auf `stdout` bzw. `stderr`.

## Konfiguration

- `OUTPUT_DIR`
  - Zielordner fuer die erzeugte CSV.
- `BASE_URL`
  - Quelle der historischen Quoten.
- `SEASONS`
  - Definiert, welche Saisons geladen werden.
- `FD_TO_API_TEAM_ID`
  - Kritische Mapping-Tabelle fuer die MatchID-Verknuepfung.
- `REQUEST_TIMEOUT_SECONDS`
  - Request-Laufzeitgrenze.
- `USER_AGENT`
  - Header gegen simple Blocklisten bzw. Default-Client-Verhalten.

## Interne Abhaengigkeiten / Imports

- `pandas`
  - CSV-Einlesen, Transformation, Sortierung.
- `requests`
  - HTTP-Download.
- `datetime`, `timezone`
  - Zeitstempel fuer Dateninhalt und Dateinamen.
- `StringIO`
  - Einlesen des Response-Texts als CSV-Stream.
- `os`, `sys`
  - Dateisystemoperationen und Fehlerausgabe.

## Methodische Staerken

- Historische Quoten werden aus einer strukturierten Quelle bezogen statt aus schwer reproduzierbarem HTML.
- Das Ausgabeschema bleibt kompatibel zum Live-Quotenformat.
- Der Join ueber interne `MatchID` macht die Daten downstream einfacher nutzbar.

## Join- und Mapping-Qualitaet

- Der kritischste Teil des Skripts ist nicht der Download, sondern die Teamzuordnung.
- `FD_TO_API_TEAM_ID` ist ein harter Wissensspeicher ueber Namensvarianten.
- Bereits kleine Abweichungen wie andere Schreibweisen, Auf- oder Abstiege oder Lieferantenwechsel fuehren zu Coverage-Verlust.
- Das Skript verwirft solche Faelle nicht still.
- Stattdessen werden ungemappte Teams und unmatched Fixtures gesammelt und gemeldet.
- Diese Transparenz ist wichtig, weil sonst die spaetere Benchmark-Basis unbemerkt schrumpfen koennte.

## Wichtige Risiken

- `FD_TO_API_TEAM_ID` ist hart codiert.
- Neue oder abweichende Teamnamen fuehren zu fehlenden Mappings.
- Wenn `football-data.co.uk` das CSV-Schema aendert, bricht das Skript frueh.
- `TEAMS_PATH` ist derzeit ungenutzt; diese Konstante kann falsche Sicherheit vermitteln.

## Edge Cases / Notes

- Saisondateien koennen zeitweise noch nicht veroeffentlicht sein.
- In diesem Fall meldet `main()` einen `requests.HTTPError` als Warnung und macht mit anderen Saisons weiter.
- Zeilen ohne Quoten werden bewusst ausgeschlossen.
- Spiele ohne `MatchID` bleiben dennoch als Output-Zeilen erhalten, nur eben mit leerem Join.
- Das ist fuer Coverage-Analysen sinnvoller als stilles Verwerfen.

## Beispiel

```bash
python "Sports Api Data/Testruns/BWIN Odds/Code/bwin_historical_odds_download.py"
```

Typische Konsolenausgabe:

- Anzahl geladener Stammdaten-Matches
- Coverage pro Saison
- Anzahl Spiele ohne Quote
- Hinweise auf ungemappte Teams
- Hinweise auf Fixtures ohne `MatchID`
- Zielpfad der geschriebenen CSV

## Praktische Nutzung danach

- Die erzeugte CSV kann im BWIN-Datacollection-Ordner liegen bleiben.
- `analyze_backtest_results.py` zieht automatisch die neueste passende Datei heran.
- Damit ist kein weiterer manueller Umbau im Analysepfad noetig.

## Wartungshinweise

- Bei Mapping-Problemen zuerst `FD_TO_API_TEAM_ID` pruefen.
- Bei Join-Luecken danach `Stammdaten_78.csv` auf Saison- oder Team-ID-Inkonsistenzen pruefen.
- Wenn mehrere Ligen oder weitere Saisons noetig werden, sollte `SEASONS` nicht blind erweitert werden.
- Sinnvoller waere dann eine kleine Konfigurationsdatei statt weiterer Hardcodings.

## Sinnvolle Nachkontrollen

- Ist die Anzahl `mit MatchID verknuepft` fuer jede Saison plausibel?
- Enthalten die neuesten Exporte mehr ungemappte Teams als fruehere Laeufe?
- Passen Datum und Ergebnisfelder zur intern erwarteten Saisonlogik?
- Greift `analyze_backtest_results.py` anschliessend wirklich die neueste historische Odds-Datei?
