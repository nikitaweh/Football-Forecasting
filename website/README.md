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

| File                            | Purpose                                                       |
|----------------------------------|---------------------------------------------------------------|
| `select.html`                    | Competition picker — choose Bundesliga or World Cup 2026      |
| `index.html`                     | Bundesliga dashboard page                                     |
| `international.html`             | World Cup 2026 dashboard page                                 |
| `styles.css`                     | Minimalist dark theme (shared by all pages)                   |
| `app.js`                         | Renders results & predictions from the data (shared)          |
| `data.js`                        | **Auto-generated** Bundesliga match data — do not edit by hand |
| `data.international.js`          | **Auto-generated** World Cup match data — do not edit by hand |
| `build_data.py`                  | Regenerates `data.js` from the Bundesliga model's CSV exports  |
| `build_data_international.py`    | Regenerates `data.international.js` from the WC 2026 snapshot |
| `refresh_data.py`                | Unattended refresh (Task Scheduler) — rebuilds on CSV change  |
| `config/leagues/`                | Per-league config: name, team map, CSV source paths           |
| `logos/`                         | Club logos (`<team-id>.png`, from media.api-sports.io)        |
| `matchdays/`                     | Saved per-matchday CSV snapshots (`md<N>_*.csv`)              |
| `mobile/`                        | Phone-scale build (app-shell + bottom tab bar)                |

### World Cup 2026 dashboard

`international.html` is a second dashboard, reusing the same `app.js` and
`styles.css`, but reading `data.international.js` instead of `data.js`.
It's reached by choosing "World Cup 2026" on `select.html` (or the
"Change competition" link in either dashboard's nav).

Unlike the Bundesliga pipeline, it does **not** go through
`build_data.py` / `config/leagues/` — the source CSV
(`Sports Api Data/International/FIFA/Backtesting/worldcup_2026/wc_predictions_asof_*.csv`)
already carries its own Stage/Season columns, so no Stammdaten join is
needed. National-team badge colours/abbreviations are hardcoded in
`build_data_international.py` (no flag images yet, so teams fall back to
a coloured abbreviation crest). Rebuild after a newer snapshot appears:

```powershell
python website/build_data_international.py
```

This is **not** wired into `refresh_data.py` yet — no scheduled
auto-refresh for the international data, rebuild manually for now.

## Refreshing the data

### Automatic (recommended)

On the VPS, `orakel-website-refresh.timer` runs `refresh_data.py` every
10 minutes (locally: a Windows scheduled task, see below). It hashes
the model's two source CSVs; when either changes (i.e. after a model run or
a results update) it rebuilds `data.js`, snapshots the inputs to
`matchdays/md<N>_*.csv`, and logs to `logs/website_refresh.log` at the repo
root. Unchanged sources are a quiet no-op (one heartbeat log line per day).

### Live site (oracle-stats.io on the VPS)

nginx serves `/var/www/orakel`, a copied allow-list of this folder (never
`website/` itself, because `website/config/` may hold credential files).
With `ORAKEL_WEB_ROOT=/var/www/orakel` set, `refresh_data.py` copies every
rebuilt `data.js` there. Everything else (`index.html`, `logos/`, `mobile/`,
...) is published with `ops/bin/publish_website.sh` after a layout change.
Setup and operation: `ops/README.md`.

### Locally (Windows)

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
