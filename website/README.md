# ORAKEL — Bundesliga prediction website

A minimalist single-page site that shows the AI model's **latest results**
and its **match predictions**.

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

| File            | Purpose                                                        |
|-----------------|----------------------------------------------------------------|
| `index.html`    | Page structure                                                 |
| `styles.css`    | Minimalist dark theme                                          |
| `app.js`        | Renders results & predictions from the data                    |
| `data.js`       | **Auto-generated** match data — do not edit by hand            |
| `build_data.py` | Regenerates `data.js` from the model's CSV exports             |
| `logos/`        | Club logos (`<team-id>.png`, from media.api-sports.io)         |
| `matchdays/`    | Saved per-matchday CSV snapshots used by the matchday switch    |
| `mobile/`       | Phone-scale build (app-shell + bottom tab bar)                 |

## Refreshing the data

After a new model run, regenerate the data file:

```powershell
python website/build_data.py
```

It reads two CSVs and joins them on `MatchID`:

- `Sports Api Data/Testruns/Datacollection future/future_outcome_table.csv`
  — the predictions
- `Sports Api Data/Testruns/Datacollection reference/match_results_references.csv`
  — the actual results (when available)

A match **with** a result shows up under *Latest results* with a
hit / miss verdict. A match **without** a result appears in the dedicated
*Upcoming fixtures* section, which stays hidden until at least one unplayed
match is present — no code changes needed.

To adjust the season / matchday labels, edit the `META` block at the top
of `build_data.py`.

## Switching matchday

`build_data.py` has a one-line `SOURCE` switch near the top:

- `SOURCE = "live"` — the model's current output (Matchday 34)
- `SOURCE = "md33"` — the saved Matchday 33 snapshot in `matchdays/`

Change the line, rerun `python website/build_data.py`, and reload the page.

## Mobile version

`mobile/index.html` is a phone-scale build using an app-shell layout:
a fixed top bar, a scrolling card feed, and a bottom tab bar
(Results / Predictions / Method).

It reuses `../data.js` and `../logos/`, so it always shows the same
matchday as the desktop site — no separate data step. On a phone it fills
the screen; on desktop it previews as a centred phone-width column.
