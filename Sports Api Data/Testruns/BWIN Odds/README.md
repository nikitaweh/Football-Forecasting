# BWIN Odds (1X2)

Ordnerpfad:

`C:\AI Projekt\KI-Projekt\Sports Api Data\Testruns\BWIN Odds`

Skript:

`C:\AI Projekt\KI-Projekt\Sports Api Data\Testruns\BWIN Odds\Code\bwin_historical_odds_download.py`

Output-Ordner:

`C:\AI Projekt\KI-Projekt\Sports Api Data\Testruns\BWIN Odds\Datacollection`

## Was wird geladen?

Historische 1X2-Quoten (`1`, `X`, `2`) von **football-data.co.uk** (keine
Over/Under-Maerkte). Das Skript erzeugt zwei Feeds:

### 1. Bundesliga (BWIN)

- Quelle: `mmz4281/<saison>/D1.csv` (Spalten `BWH`/`BWD`/`BWA` = echte BWIN-Quoten).
- Verknuepft auf die MatchIDs aus `Stammdaten_78.csv`.
- Output: `bwin_historical_odds_YYYYMMDD_HHMMSS.csv`
  (Diese Datei wird von den Backtest-Analysen gelesen – Spalten nicht aendern.)

### 2. World Cup 2026 (international)

- Quelle: `WorldCup2026.xlsx`.
- **Wichtig:** football-data.co.uk veroeffentlicht fuer Nationalmannschafts-
  spiele **keine BWIN- (und keine Tipico-) Quoten**. Verfuegbar sind nur
  `bet365`, Betfair Exchange sowie die Markt-Werte `Max`/`Avg`.
- Pro Buchmacher wird eine eigene CSV geschrieben:
  - `worldcup_odds_bet365_YYYYMMDD_HHMMSS.csv`
  - `worldcup_odds_betfair_exchange_YYYYMMDD_HHMMSS.csv`
  - `worldcup_odds_max_YYYYMMDD_HHMMSS.csv`
  - `worldcup_odds_avg_YYYYMMDD_HHMMSS.csv`
- Verknuepft auf die MatchIDs aus `Stammdaten_international.csv`
  (League ID 1, Season 2026). Nationen-Namen werden ueber
  `WORLD_CUP_TEAM_ALIASES` im Skript auf die api-football-Namen gemappt.
- football-data fuellt das XLSX erst **nach** Spielende, d.h. es erscheinen
  gespielte Partien (laufend ergaenzt), keine reinen Vorab-Fixtures.

## Start

Im Projektordner ausfuehren:

```powershell
.\Supportdateien\.venv\Scripts\python.exe "Sports Api Data\Testruns\BWIN Odds\Code\bwin_historical_odds_download.py"
```

## Abhaengigkeiten

Das Lesen der XLSX-Datei benoetigt `openpyxl`:

```powershell
.\Supportdateien\.venv\Scripts\python.exe -m pip install openpyxl
```
