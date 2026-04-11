# `line ups_78.py`

Source: `Sports Api Data/Bundesliga/Filtered/Code/line ups_78.py`

## Überblick
Konvertiert Lineups‑JSON (API‑Antworten) in eine flache CSV‑Tabelle mit Spielern (Startelf + Bank) pro Match. Kann beim direkten Start einmal ausführen und anschließend per APScheduler automatisch zu festen Zeiten laufen.

## Zweck / Responsibilities
- Lädt Lineups aus `INPUT_JSON` und (optional) Fixtures aus `FIXTURES_JSON`.
- Bestimmt Home/Away bevorzugt über Fixtures‑Mapping (Fixture‑ID → Home/Away‑Team‑ID), sonst Fallback über Listenindex.
- Extrahiert Spieler‑Zeilen für `startXI` und `substitutes` inkl. Team/Coach/Formation.
- Schreibt die CSV nach `OUTPUT_CSV`.

## Konfiguration
- `INPUT_JSON`: Lineups‑Quelle (JSON mit `response`).
- `FIXTURES_JSON`: Fixtures‑Quelle (für robustes Home/Away‑Mapping).
- `OUTPUT_CSV`: Ziel‑CSV.
- `team_name_overrides`: Normalisiert einige Teamnamen (Achtung: aktuell teils Mojibake wie `MÃ¼nchen`).

## Wichtige Funktionen (Signaturen)
- `load_fixture_team_map()`: Lädt Fixtures und erzeugt `{fixture_id: {home, away}}`; bei Fehlern Rückgabe `{}` + Hinweislog.
- `convert_lineups_to_csv()`: Hauptlogik für JSON‑Parsing, Zeilenbau und CSV‑Write.
  - Nested Helper: `add_player_rows(entry, is_start, side)` (baut Zeilen für Startelf/Bank).

## Inputs / Outputs & Side‑Effects
**Inputs**:
- `INPUT_JSON`: erwartet `data["response"]` als Liste; jeder Eintrag enthält `parameters.fixture` (oder `MatchID`/`fixture_id`) sowie `response` (Lineups pro Team).
- `FIXTURES_JSON`: optional; wird genutzt, um die zwei Teams sicher Home/Away zuzuordnen.

**Output**:
- `OUTPUT_CSV` mit Spalten:
  - `MatchID`, `Home Team ID`, `Away Team ID`, `Team Name`, `Coach ID`, `Coach Name`, `Formation`,
    `Player ID`, `Player Name`, `Pos`, `Grid`, `StartXI`

**Side‑Effects**:
- Legt Zielordner an (`os.makedirs(dirname(OUTPUT_CSV))`), schreibt CSV, loggt Status in `stdout`.

## Beispiel
- Direkt ausführen: `python "Sports Api Data/Bundesliga/Filtered/Code/line ups_78.py"`
  - Führt `convert_lineups_to_csv()` einmal aus und startet dann einen Scheduler:
    - `CronTrigger(day_of_week="sat,sun,mon", hour="3", minute="0")` (Timezone: `Europe/Berlin`)

## Edge Cases / Notes
- Wenn `FIXTURES_JSON` fehlt/kaputt ist, wird Home/Away per Index (`lineups[0]`/`lineups[1]`) zugewiesen.
- Bei unerwartetem JSON‑Format wird abgebrochen (mit Log).
- Wenn ein Match keine ID hat oder weniger als zwei Teams liefert, wird es übersprungen.

