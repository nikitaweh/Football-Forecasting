# ORAKEL — football prediction website

A minimalist single-page site that shows the AI model's **latest results**
and its **match predictions**. League/season/teams come from a config file —
the code itself is league-agnostic.

## View it

Just open [`index.html`](index.html) in any browser — double-click works,
no server needed.

For the cleanest experience (and to silence font/CORS warnings) you can
serve the folder instead:

```powershell
cd website
python -m http.server 8000
# then open http://localhost:8000
```

## Files

| File              | Purpose                                                       |
|-------------------|---------------------------------------------------------------|
| `index.html`      | Page structure                                                |
| `styles.css`      | Minimalist dark theme                                         |
| `app.js`          | Renders results & predictions from the data                   |
| `data.js`         | **Auto-generated** match data — do not edit by hand           |
| `build_data.py`   | Regenerates `data.js` from the model's CSV exports            |
| `refresh_data.py` | Unattended refresh (Task Scheduler) — rebuilds on CSV change  |
| `config/leagues/` | Per-league config: name, team map, CSV source paths           |
| `logos/`          | Club logos (`<team-id>.png`, from media.api-sports.io)        |
| `matchdays/`      | Saved per-matchday CSV snapshots (`md<N>_*.csv`)              |
| `mobile/`         | Phone-scale build (app-shell + bottom tab bar)                |

## Refreshing the data

### Automatic (recommended)

A Windows scheduled task runs `refresh_data.py` every 10 minutes. It hashes
the model's two source CSVs; when either changes (i.e. after a model run or
a results update) it rebuilds `data.js`, snapshots the inputs to
`matchdays/md<N>_*.csv`, and logs to `logs/website_refresh.log` at the repo
root. Unchanged sources are a quiet no-op (one heartbeat log line per day).

Register the task **once, on the main checkout** (PowerShell):

```powershell
$py = (Get-Command pythonw.exe).Source
$action  = New-ScheduledTaskAction -Execute $py `
           -Argument '"C:\AI Projekt\KI-Projekt\website\refresh_data.py"' `
           -WorkingDirectory "C:\AI Projekt\KI-Projekt"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
           -RepetitionInterval (New-TimeSpan -Minutes 10)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
            -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "ORAKEL Website Refresh" `
  -Action $action -Trigger $trigger -Settings $settings
```

Remove it with
`Unregister-ScheduledTask -TaskName "ORAKEL Website Refresh"`.
State lives in `logs/refresh_state.json`; delete it to force a rebuild on
the next run.

### Manual

```powershell
python website/build_data.py                 # live model output (auto-detects matchday)
python website/build_data.py --matchday 33   # rebuild from a saved snapshot
python website/build_data.py --league bundesliga   # explicit league (default)
```

Live mode reads two CSVs (paths from the league config) and joins them on
`MatchID`:

- `Sports Api Data/Testruns/Datacollection future/future_outcome_table.csv`
  — the predictions
- `Sports Api Data/Testruns/Datacollection reference/match_results_references.csv`
  — the actual results (when available)

The matchday number, its date, and the season are **derived automatically**
by joining the prediction `MatchID`s against the league's Stammdaten — no
manual switches. Live mode also snapshots both input CSVs to
`matchdays/md<N>_*.csv` so any past matchday can be rebuilt later with
`--matchday N`.

A match **with** a result shows up under *Latest results* with a
hit / miss verdict. A match **without** a result appears in the dedicated
*Upcoming fixtures* section, which stays hidden until at least one unplayed
match is present — no code changes needed.

## New season checklist

1. Edit `config/leagues/bundesliga.json` → `teams`: replace relegated clubs
   with the promoted ones (`name → {id, abbr, color}`; id = API-Football
   team id).
2. Drop the new clubs' logos into `logos/<id>.png`
   (from `media.api-sports.io/football/teams/<id>.png`).
3. Done — the season label is derived from the Stammdaten, not configured.

## Adding a league (later)

Create `config/leagues/<league>.json` with its own `leagueName`, `teams`,
`sources` (predictions/results/Stammdaten CSVs) and an `output` like
`data/<league>.js`, then run `build_data.py --league <league>`.
Use `"seasonLabelFormat": "single-year"` for tournaments (World Cup, Euros)
whose Stammdaten matchdays are stage strings like `Group Stage - 1` — the
site shows those labels verbatim.

## Mobile version

`mobile/index.html` is a phone-scale build using an app-shell layout:
a fixed top bar, a scrolling card feed, and a bottom tab bar
(Results / Predictions / Method).

It reuses `../data.js` and `../logos/`, so it always shows the same
matchday as the desktop site — no separate data step. On a phone it fills
the screen; on desktop it previews as a centred phone-width column.
