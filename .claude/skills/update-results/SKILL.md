---
name: update-results
description: After a played matchday, refresh match_results_references.csv from match_statistics_filtered_78.csv so reference scoring and future-vs-reference metrics use actual results. Use when new results are in or the reference file is stale.
---

# Update Match Results

`update_match_results_references.py` fills `Datacollection reference/match_results_references.csv` from the filtered match statistics and trims it to the N most recent played matches (default 9 = one matchday).

## When to Use

- After a matchday was played and `collect-matchday-data` pulled the match statistics
- When reference scoring shows missing actual results

## Run

```bash
PY="C:/AI Projekt/.venv/Scripts/python.exe"
cd "Sports Api Data/Testruns/Code"
"$PY" update_match_results_references.py --dry-run    # show changes first
"$PY" update_match_results_references.py              # write; --recent 9 default, --recent 0 keeps all
```
Options: `--no-add-missing` only refreshes MatchIDs already present.

## Checks

- Dry run first; report added / updated / dropped MatchIDs.
- Do not run while a backtest is running: `backtest_matchdays.py` overwrites the same file.
- Result encoding is H/D/A from home/away goals; spot-check one match against the source CSV.

## Output Format

```text
Added: N  Updated: N  Dropped by cap: N  File now: N rows (MatchIDs a–b)
```
