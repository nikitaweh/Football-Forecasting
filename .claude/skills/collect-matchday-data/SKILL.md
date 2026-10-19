---
name: collect-matchday-data
description: Pull Bundesliga fixtures, injuries, lineups, match and player statistics, weather and BWIN odds before or after a matchday. Manual only, because every run uses API-Football quota.
disable-model-invocation: true
---

# Collect Matchday Data

Wraps the combined Bundesliga pipeline (API fetch into Unfiltered, direct filtered output) and the BWIN odds download.

## When to Use

- Before a matchday: fixtures, injuries, lineups (when announced), weather forecast, odds
- After a matchday: match statistics and player statistics, then `update-results`

## Before Running

- Confirm which steps are needed; each step costs API calls. Prefer `--fixtures-mode new` (incremental).
- Never print the API key. If a step fails with 429/quota, stop; do not retry in a loop.

## Run

```bash
PY="C:/AI Projekt/.venv/Scripts/python.exe"
# Default steps: fixtures injuries lineups matchstats playerstats
"$PY" "Sports Api Data/Bundesliga/Code/bundesliga_combined_pipeline_78.py" --fixtures-mode new
# Selected steps, e.g. before kickoff:
"$PY" "Sports Api Data/Bundesliga/Code/bundesliga_combined_pipeline_78.py" --steps fixtures injuries lineups weather
# Odds
"$PY" "Sports Api Data/Testruns/BWIN Odds/Code/bwin_historical_odds_download.py"
```
`--continue-on-error` keeps going after a failed block; report which block failed.

## Checks

- Row counts before/after per output CSV in `Sports Api Data/Bundesliga/Filtered/Datacollection/`.
- New MatchIDs present for the target matchday; no duplicated MatchIDs.
- Odds file has a new timestamped `bwin_historical_odds_*.csv` with home/draw/away odds for every fixture.

## Output Format

```text
Steps run: [...]  Failed: [...]
Per file: rows before -> after
Target matchday coverage: fixtures N/9, lineups N/9, odds N/9
API calls used (if logged)
```
