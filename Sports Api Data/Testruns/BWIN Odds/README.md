# BWIN Odds (1X2)

Neuer Ordnerpfad:

`C:\AI Projekt\KI-Projekt\Sports Api Data\Testruns\BWIN Odds`

Skript:

`C:\AI Projekt\KI-Projekt\Sports Api Data\Testruns\BWIN Odds\Code\bwin_match_winner_odds_scraper.py`

Output-Ordner:

`C:\AI Projekt\KI-Projekt\Sports Api Data\Testruns\BWIN Odds\Datacollection`

## Was wird gescraped?

- Nur Match-Siegerquoten (`1`, `X`, `2`)
- Keine Over/Under-Maerkte wie `2.5`, `3.5` usw.

## Start

Im Projektordner ausfuehren:

```powershell
.\.venv\Scripts\python.exe "Sports Api Data\Testruns\BWIN Odds\Code\bwin_match_winner_odds_scraper.py"
```

Das Skript speichert pro Lauf eine neue CSV mit Zeitstempel im Dateinamen:

- `bwin_match_winner_odds_YYYYMMDD_HHMMSS.csv`

## Hinweis zu WebDriver

Das Skript versucht automatisch:

- lokalen `msedgedriver` (WinGet-Installation)
- lokalen `chromedriver` aus Selenium-Cache
- danach Selenium-Manager

Wenn Selenium den Browser-Driver trotzdem nicht starten kann, setze den Pfad manuell:

```powershell
$env:BWIN_WEBDRIVER_PATH="C:\Pfad\zu\chromedriver.exe"
.\.venv\Scripts\python.exe "Sports Api Data\Testruns\BWIN Odds\Code\bwin_match_winner_odds_scraper.py"
```

EdgeDriver einmalig per Winget installieren:

```powershell
winget install --id Microsoft.EdgeDriver --exact --accept-package-agreements --accept-source-agreements
```
