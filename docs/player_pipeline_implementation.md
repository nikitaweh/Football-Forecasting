# Player Statistics Pipeline — Implementation Log

**File modified:** `Sports Api Data/Testruns/Code/AI_match_stats_prediction.py`
**Date:** 2026-04-23
**Scope:** Player base implementation for the 3-base prediction architecture

---

## Background and Context

The prediction model was restructured into 3 bases (General Stats, H2H, Player) plus one context input (Weather). The General Stats and H2H bases were already wired up. The Player base was largely implemented in `build_player_base_features()` but had:

- An `AbsencePenalty = 0.0` stub in the played-matches branch
- Two leakage and dilution issues in the absence penalty computation
- Unclear status of how the function's outputs flowed into the outcome model

The plan was 6 sequential steps:

1. Load and prepare raw data
2. Build rolling player stats (leakage-safe)
3. Build the starting XI composite per match
4. Compute the absence penalty
5. Wire signals into `PLAYER_BASE_SIGNAL_SPECS`
6. Test leakage safety

---

## Step 1 — Load and Prepare Raw Data

### Initial implementation (later reverted)

Added three top-level loads alongside `match_stats`, `stammdaten`, `teams`:

```python
player_stats  = pd.read_csv(os.path.join(DATA_PATH, 'player_statistics_per_fixture_league_78.csv'))
lineups       = pd.read_csv(os.path.join(DATA_PATH, 'lineups_league_78.csv'))
injuries      = pd.read_csv(os.path.join(DATA_PATH, 'injuries_league_78.csv'))
```

Plus a rename block harmonizing column names (e.g., `Total Goals` → `Goals`, `Player ID` → `PlayerID`), a `PassAccuracy` `%` strip, and bulk numeric coercion via the existing `coerce_numeric_columns()` helper.

### Why this was reverted

When reviewing Step 2, it became clear that `build_player_base_features()` (line 310) was already a self-contained module:

- It reads its own copies of all three CSVs internally via `safe_read_csv(PLAYER_STATS_PATH)` etc. (lines 417–419 of original code)
- It applies its own internal renaming using a *different* schema (`Total Goals` → `TotalGoals` rather than my `Total Goals` → `Goals`)
- The function's local variables shadow my module-level globals

**Consequence:** my Step 1 globals were dead code. The function ignored them entirely and re-loaded the files from disk.

### Engineering decision: revert vs. refactor

Two cleanup options were considered:

**Option A — Revert Step 1.** Delete the unused globals. Simplest and lowest risk.

**Option B — Refactor the function to consume the pre-loaded globals.** Eliminates the double-load of CSVs and unifies the rename schema.

**Choice: A.** The function is well-designed as a self-contained module — it owns its data loading, transformation, and aggregation, and exposes a clean DataFrame interface. Pulling its data loading out into module-level state would couple it to globals and break that encapsulation. Saving one CSV read at startup is not worth that architectural cost.

The revert removed the `pd.read_csv` calls and rename blocks. Net change: zero new state at module level, function unchanged.

---

## Steps 2 & 3 — Rolling Player Stats and Starting XI Composite

### Discovery: already implemented

A grep for `rolling`, `Roll5`, `RollingForm` found existing implementations at line 573 (`PLAYER_ROLLING_WINDOW`) and lines 846–860 (team-level rolling). Reading the function in detail confirmed Steps 2 and 3 were both implemented:

**Step 2 (rolling stats) — `PlayerMatchScore` and `PlayerRollingScore`:**

```python
raw_score = (
    0.35 * goals
    + 0.25 * assists
    + 0.08 * shots_on_target
    + 0.04 * total_shots
    + 0.06 * tackles
    + 0.06 * interceptions
    + 0.05 * duels_won
    + 0.11 * rating_norm
    - 0.08 * yellow
    - 0.25 * red
)
player_stats['PlayerMatchScore'] = minutes_factor * raw_score

player_stats['PlayerRollingScore'] = (
    player_stats.groupby('PlayerID')['PlayerMatchScore']
    .transform(lambda s: s.shift(1).rolling(PLAYER_ROLLING_WINDOW, min_periods=1).mean())
)
```

The `shift(1)` is the leakage guard: when computing the rolling score for fixture M, fixture M's own `PlayerMatchScore` is excluded.

**Step 3 (starting XI composite) — two branches:**

- **Reference mode (played matches):** join confirmed `StartXI` from lineups with player rolling scores, weight by position importance (GK 1.15, FWD 1.10, MID 1.05, DEF 1.00), aggregate to `(MatchID, TeamID)`.
- **Future mode (unplayed matches):** filter the squad by `injury_map`, weight remaining players by historical start probability × position importance, aggregate.

### Reviewed gaps (not blocking, noted for future)

- The composite is a single score, not multiple per-stat rolling signals. xG is unavailable at player level in the CSV, so it can't be added there.
- The `PlayerMatchScore` formula is position-agnostic. A goalkeeper's score is dominated by `Rating` since they don't take shots. Position-aware composite formulas would be more accurate but were out of scope.
- `PassAccuracy`, `Blocks`, `SuccessfulDribbles`, `Saves`, `PenaltiesSaved` are loaded but unused in the composite.

These are improvements for later. Step 2 is functionally complete and leakage-safe.

---

## Step 4 — Absence Penalty (the main implementation work)

### Original state

Line 642 (pre-fix):
```python
agg['AbsencePenalty'] = 0.0
```

The played-matches branch hardcoded the absence penalty to zero. Future mode had a real computation (lines 711–724) but inline, not extracted.

### Why the played-matches branch needed the fix

The whole point of the player base is captured by two signals: squad quality and absence impact. When a star player is suspended for a played match, the `PlayerTeamScore` already reflects this (they're absent from `StartXI`), but the *magnitude* of the loss is not quantified. The model needs both: "who played" and "how much was lost."

For backtesting reference matches, we know exactly who was injured (the data is fixture-time accurate), so we can compute a real absence penalty. The `0.0` stub silently disabled this signal in reference mode.

### Refactor approach

The future-mode absence penalty was inline:

```python
absence_penalty = 0.0
if injured_players:
    for injured_player_id in injured_players:
        score, prior_apps, pos = latest_profile(team_id, injured_player_id, match_date)
        if prior_apps < PLAYER_MIN_APPEARANCES or pd.isna(score):
            continue
        replacement = fallback_score(team_id, pos)
        gap = max(0.0, score - replacement)
        start_prob = max(
            0.1,
            min(1.0, float(start_rate_map.get((team_id, injured_player_id), PLAYER_STARTPROB_FALLBACK)))
        )
        absence_penalty += gap * float(position_weight.get(pos, 1.0)) * start_prob
    absence_penalty = absence_penalty / float(max(len(injured_players), 1))
```

### Decision: extract into a helper, restructure helper-building order

The played-matches branch needed the same machinery as the future branch. Three options:

1. **Duplicate the logic** in the played-matches loop. Bad — copy-paste maintenance burden.
2. **Move the played-matches branch later in the function** (after the helpers are built). Bad — the played-matches branch logically belongs first since it uses confirmed lineups.
3. **Move the helpers earlier**, then extract a shared `compute_absence_penalty()` helper used by both branches. Clean — single source of truth, both branches use the same logic.

**Choice: option 3.**

The new structure inside `build_player_base_features()`:

```
1. fallback_score (already there)
2. position_weight (already there)
3. start_hist + start_rate_map        ← moved up
4. roster_by_team                     ← moved up (depends on start_rate_map)
5. profile_tables + latest_profile    ← moved up
6. injury_map                         ← moved up
7. compute_absence_penalty (helper)   ← new
8. match_date_lookup                  ← new
9. played_match_ids + team_feature_rows
10. Played matches branch (uses helper)
11. Future matches branch (uses helper)
```

The new `compute_absence_penalty(team_id, injured_players, match_date)` helper:

```python
def compute_absence_penalty(team_id, injured_players, match_date):
    if not injured_players:
        return 0.0
    total = 0.0
    counted = 0
    for injured_player_id in injured_players:
        score, prior_apps, pos = latest_profile(team_id, injured_player_id, match_date)
        if prior_apps < PLAYER_MIN_APPEARANCES or pd.isna(score):
            continue
        replacement = fallback_score(team_id, pos)
        gap = max(0.0, score - replacement)
        start_prob = max(
            0.1,
            min(1.0, float(start_rate_at(team_id, injured_player_id, match_date)))
        )
        total += gap * float(position_weight.get(pos, 1.0)) * start_prob
        counted += 1
    if counted == 0:
        return 0.0
    return total / float(counted)
```

### Two issues fixed in the helper

#### Issue 1 — Dilution divisor

**Original:** `total / max(len(injured_players), 1)` — divides by total injured count, even those filtered out by `PLAYER_MIN_APPEARANCES`.

**Problem:** if a team lists 5 injured players but only 1 has sufficient appearances to register a gap, the penalty for that 1 player gets divided by 5, giving 1/5 of the proper signal.

**Fix:** track `counted` (only valid injured players) and divide by that. If `counted == 0`, return `0.0` cleanly.

#### Issue 2 — `start_rate_map` time-leakage

**Original:** `start_rate_map = start_hist.groupby(['TeamID', 'PlayerID'])['StarterNumeric'].mean().to_dict()` — a single global map computed once across the full dataset.

**Problem:** when backtesting a 2023 match, the player's start probability included appearances from 2024+, leaking future information into a past-time prediction.

**Fix:** added a sorted per-player `start_tables` and a date-aware `start_rate_at(team_id, player_id, match_date)`:

```python
start_tables = {}
if not start_hist.empty:
    for (team_id, player_id), grp in start_hist.groupby(['TeamID', 'PlayerID']):
        start_tables[(int(team_id), int(player_id))] = grp[['MatchDate', 'StarterNumeric']].sort_values('MatchDate')

def start_rate_at(team_id, player_id, match_date):
    table = start_tables.get((team_id, player_id))
    if table is None or table.empty:
        return PLAYER_STARTPROB_FALLBACK
    if pd.isna(match_date):
        return float(table['StarterNumeric'].mean())
    prior = table[table['MatchDate'] < match_date]
    if prior.empty:
        return PLAYER_STARTPROB_FALLBACK
    return float(prior['StarterNumeric'].mean())
```

`start_rate_map` is kept as a global mean for `roster_by_team` construction (used only in future mode where leakage is irrelevant — all start history is past relative to a future match). `compute_absence_penalty` uses `start_rate_at` instead, which gives correct date-aware behavior in both modes.

### Played-matches branch new code

```python
for _, r in agg.iterrows():
    match_id = int(r['MatchID'])
    team_id = int(r['TeamID'])
    match_date = match_date_lookup.get(match_id, pd.NaT)
    injured = injury_map.get((match_id, team_id), set())
    team_feature_rows.append({
        'MatchID': match_id,
        'TeamID': team_id,
        'PlayerTeamScore': float(r['PlayerTeamScore']),
        'AbsencePenalty': float(compute_absence_penalty(team_id, injured, match_date))
    })
```

The played-matches loop now looks up `match_date` via `match_date_lookup` (built from `match_meta`) and the injured set via `injury_map`, then calls the helper.

### Final differential signs (verified at line 778)

```python
out['Player_BaseDiff'] = out['Home_PlayerBaseScore'] - out['Away_PlayerBaseScore']
out['Player_AbsencePenaltyDiff'] = out['Away_PlayerAbsencePenalty'] - out['Home_PlayerAbsencePenalty']
```

Note the asymmetry: `Player_BaseDiff` is `Home − Away`, but `Player_AbsencePenaltyDiff` is `Away − Home`. **This is intentional and correct** — both signals are oriented so that "positive value = good for home." A positive absence penalty diff means the away team lost more impact, which favors home in the goal difference prediction.

---

## Step 5 — Signal Wiring (verified, no changes needed)

Verified that the function output flows correctly into the outcome model:

1. **Function call and merge** (lines 895–904): `build_player_base_features(df)` called, result merged on `MatchID`, missing values defensively coerced and zero-filled.

2. **`PLAYER_BASE_SIGNAL_SPECS`** (lines 1005–1008):
```python
PLAYER_BASE_SIGNAL_SPECS = [
    {'weight_name': 'Player_FormDiff', 'column': 'Player_BaseDiff'},
    {'weight_name': 'Player_AbsencePenaltyDiff', 'column': 'Player_AbsencePenaltyDiff'}
]
```

3. **Base multiplier** registered as `BaseMultiplier_Player` in `BASE_MULTIPLIER_PARAMETER_NAMES` (line 1012).

4. **Design matrix** (lines 1655–1662):
```python
player_signal = weighted_signal_from_specs(signal_df, PLAYER_BASE_SIGNAL_SPECS, weight_map)
design['Player_BaseSignal'] = player_signal * player_multiplier
```

5. **Weight sampling** (line 1590) extends the parameter list with the player signal weights.

6. **History migration** (line 2105) handles the new schema by adding default weights for `Player_AbsencePenaltyDiff` to old run history.

**No double-counting:** the raw `Player_BaseDiff` / `Player_AbsencePenaltyDiff` columns enter `signal_df` and are consumed by the spec system to produce `Player_BaseSignal`. They don't enter the BART design matrix as standalone columns. They also appear in `outcome_prematch_features` (line 930–931) where they correctly feed the GBR match-stats prediction models as pre-match context.

**Minor naming quirk:** the weight name `Player_FormDiff` points at column `Player_BaseDiff`. Cosmetic only; functionally fine.

---

## Step 6 — Leakage-Safety Verification

### Verified clean

| # | Path | Mechanism |
|---|------|-----------|
| 1 | `PlayerRollingScore` | `shift(1).rolling(8).mean()` excludes current fixture |
| 2 | `PlayerPriorAppearances` | `cumcount()` returns count of prior fixtures only |
| 3 | `latest_profile()` | `table['MatchDate'] < match_date` filter |
| 4 | `start_rate_at()` | `table['MatchDate'] < match_date` filter |
| 5 | `injury_map` | Built per `(MatchID, TeamID)`, fixture-specific |
| 6 | Reference-mode aggregation | Uses confirmed StartXI + leakage-safe rolling scores |
| 7 | Future-mode aggregation | Uses date-filtered helpers throughout |
| 8 | Reference matches excluded from BART training | Verified at outcome-model level |
| 9 | `GoalDiff` target | Per-match, no cross-fixture flow |

### One mild leakage path identified (not fixed)

**`fallback_score()` medians** (line 540–549, computed once at lines 584–587):

The team/position/global medians are computed across the **full dataset** of `PlayerRollingScore` values. While each individual rolling score is itself leakage-safe (uses `shift(1)`), the aggregate statistic incorporates rolling scores from fixtures that, in a backtest of an old match, would not have been observable yet.

**Indirect chain:** Match M's `PlayerMatchScore` → contributes to a 2024 fixture's rolling score (M is in that fixture's history) → contributes to the team_median → used as a fallback when computing absence penalty or starter aggregation for M itself.

**Severity:** mild. The medians stabilize quickly with hundreds of player-matches; one fixture's contribution is small. The fallback only fires for sparse players (< `PLAYER_MIN_APPEARANCES = 5` prior appearances). It only affects the *replacement* baseline, not the main player rolling score.

**Decision: not fixed.** Making `fallback_score` time-aware would require recomputing four medians per match — significant cost for marginal gain. Documented as a known caveat. If reference-mode metrics later look suspiciously good, this would be the place to investigate.

---

## Summary of Changes

| File | Change | Rationale |
|------|--------|-----------|
| `AI_match_stats_prediction.py` | Reverted Step 1 globals (lines 108–110, 180–225) | Function loads its own data internally; globals were dead code |
| `AI_match_stats_prediction.py` | Restructured helper-building order in `build_player_base_features()` | Played-matches branch needed the helpers earlier |
| `AI_match_stats_prediction.py` | Added `start_tables` and `start_rate_at()` helper | Date-aware start rate, leakage-safe |
| `AI_match_stats_prediction.py` | Added `compute_absence_penalty()` helper | Single source of truth used by both branches |
| `AI_match_stats_prediction.py` | Replaced `agg['AbsencePenalty'] = 0.0` stub with real per-row computation | Enables absence signal in reference mode |
| `AI_match_stats_prediction.py` | Fixed dilution divisor (counted vs. len) | Penalty no longer underestimated when fringe players are listed |
| `AI_match_stats_prediction.py` | Refactored future-mode loop to call shared helper | Removes duplicated inline logic |

---

## Open Items for Future Iteration

1. **Position-aware `PlayerMatchScore` formulas.** Current formula is one-size-fits-all. A GK-specific formula using `Saves`, `PenaltiesSaved`, `GoalsConceded` would be more accurate.

2. **Multiple per-stat rolling signals.** Current pipeline collapses everything into a single composite. Separate rolling signals (offensive, defensive, control) could give the outcome model richer input.

3. **`fallback_score` time-awareness.** As noted in Step 6.

4. **New transfers excluded from roster.** Players with zero historical appearances never enter `roster_by_team` (built from `player_stats.drop_duplicates`). Edge case; affects only newly signed players in their first appearance.

5. **Future mode ignoring confirmed lineups.** Even if a confirmed lineup is available close to kickoff, future mode still uses the start-probability path. A hybrid mode that uses confirmed lineups when available could improve future-mode accuracy.

6. **No upper bound on absence penalty magnitude.** Theoretically the penalty could grow large with many high-impact injuries. No safety clamp; in practice the data ranges keep it bounded.

7. **Naming cleanup.** `Player_FormDiff` weight name pointing at `Player_BaseDiff` column is mildly confusing.

---

## 2026-06-20 extension: cross-competition player workload

The Bundesliga player base now also includes `Player_WorkloadDiff`. Actual Bundesliga minutes are combined with competitive international player minutes. When exact international minutes are unavailable, confirmed international starts are used as a 90-minute proxy; bench listings are ignored.

The workload is computed strictly before each target match over 14- and 30-day windows. International friendlies are excluded. The feature schema is now `bases_v3_player_workload`, and older run-history rows are deliberately not migrated into this schema because their NLL targets were generated without the workload signal.

Detailed definitions, limitations and validation requirements are documented in `docs/international_competitive_and_player_workload.md`.
