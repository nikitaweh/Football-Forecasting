import os

import numpy as np
import pandas as pd


COMPETITIVE_INTERNATIONAL_LEAGUES = frozenset({
    'World Cup',
    'Euro Championship',
    'UEFA Nations League',
    'World Cup - Qualification Africa',
    'World Cup - Qualification Asia',
    'World Cup - Qualification CONCACAF',
    'World Cup - Qualification Europe',
    'World Cup - Qualification Oceania',
    'World Cup - Qualification South America',
    'World Cup - Qualification Intercontinental Play-offs',
    'Euro Championship - Qualification',
})

WORKLOAD_SHORT_DAYS = 14
WORKLOAD_LONG_DAYS = 30
WORKLOAD_SHORT_MINUTES_REFERENCE = 270.0
WORKLOAD_LONG_MINUTES_REFERENCE = 540.0
WORKLOAD_INDEX_CAP = 2.0


def _safe_read_csv(path):
    # Accept a single path or an iterable of paths. Competitive international data is
    # split across confederation branches (International/FIFA, International/UEFA), so
    # callers pass the branch files as a list and they are concatenated back together.
    if isinstance(path, (list, tuple)):
        frames = [_safe_read_csv(p) for p in path]
        frames = [f for f in frames if not f.empty]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not path or not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'true', '1', 'yes', 'y'}


def _normalise_event_rows(rows, source, priority):
    if rows.empty:
        return pd.DataFrame(columns=[
            'MatchID', 'PlayerID', 'MatchDate', 'MinutesPlayed', 'Source', 'Priority'
        ])

    out = rows.copy()
    for col in ['MatchID', 'PlayerID', 'MinutesPlayed']:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors='coerce')
    out['MatchDate'] = pd.to_datetime(out.get('MatchDate'), errors='coerce')
    out = out.dropna(subset=['MatchID', 'PlayerID', 'MatchDate', 'MinutesPlayed']).copy()
    out = out[out['MinutesPlayed'] > 0].copy()
    out['MinutesPlayed'] = out['MinutesPlayed'].clip(lower=0, upper=130)
    out['MatchID'] = out['MatchID'].astype(int)
    out['PlayerID'] = out['PlayerID'].astype(int)
    out['Source'] = source
    out['Priority'] = int(priority)
    return out[[
        'MatchID', 'PlayerID', 'MatchDate', 'MinutesPlayed', 'Source', 'Priority'
    ]]


def build_player_workload_index(
    domestic_player_stats,
    international_fixtures_path,
    international_lineups_path,
    international_player_stats_path=None,
):
    """Build a leakage-safe per-player minute index.

    Domestic rows use actual minutes. Competitive international rows use actual
    minutes when the player-statistics CSV is available. Missing fixture-player
    rows fall back to confirmed starters from lineups with a conservative
    90-minute proxy. Bench listings are deliberately ignored because lineups do
    not establish whether a substitute actually entered the match.
    """
    domestic = domestic_player_stats.rename(columns={
        'Player ID': 'PlayerID',
        'Minutes Played': 'MinutesPlayed',
    }).copy()
    domestic_events = _normalise_event_rows(domestic, 'bundesliga_minutes', 3)

    fixtures = _safe_read_csv(international_fixtures_path)
    if fixtures.empty:
        all_events = domestic_events
    else:
        fixtures = fixtures.rename(columns={
            'Date': 'MatchDate',
            'League Name': 'Competition',
        })
        for col in ['MatchID', 'MatchDate', 'Competition']:
            if col not in fixtures.columns:
                fixtures[col] = np.nan
        fixtures['MatchID'] = pd.to_numeric(fixtures['MatchID'], errors='coerce')
        fixtures['MatchDate'] = pd.to_datetime(fixtures['MatchDate'], errors='coerce')
        fixtures = fixtures[
            fixtures['Competition'].isin(COMPETITIVE_INTERNATIONAL_LEAGUES)
        ].dropna(subset=['MatchID', 'MatchDate']).copy()
        fixtures['MatchID'] = fixtures['MatchID'].astype(int)
        fixture_dates = fixtures[['MatchID', 'MatchDate']].drop_duplicates('MatchID')

        international_stats = _safe_read_csv(international_player_stats_path)
        if not international_stats.empty:
            international_stats = international_stats.rename(columns={
                'Player ID': 'PlayerID',
                'Minutes Played': 'MinutesPlayed',
            })
            international_stats = international_stats.merge(fixture_dates, on='MatchID', how='inner')
            international_exact = _normalise_event_rows(
                international_stats,
                'international_minutes',
                3,
            )
            exact_key_rows = international_stats[['MatchID', 'PlayerID']].copy()
            exact_key_rows['MatchID'] = pd.to_numeric(exact_key_rows['MatchID'], errors='coerce')
            exact_key_rows['PlayerID'] = pd.to_numeric(exact_key_rows['PlayerID'], errors='coerce')
            exact_key_rows = exact_key_rows.dropna(subset=['MatchID', 'PlayerID'])
            exact_keys = set(zip(
                exact_key_rows['MatchID'].astype(int),
                exact_key_rows['PlayerID'].astype(int),
            ))
        else:
            international_exact = _normalise_event_rows(pd.DataFrame(), 'international_minutes', 3)
            exact_keys = set()

        lineups = _safe_read_csv(international_lineups_path)
        if not lineups.empty:
            lineups = lineups.rename(columns={'Player ID': 'PlayerID'})
            if 'StartXI' not in lineups.columns:
                lineups['StartXI'] = False
            lineups = lineups[lineups['StartXI'].apply(_parse_bool)].copy()
            lineups = lineups.merge(fixture_dates, on='MatchID', how='inner')
            lineups['MinutesPlayed'] = 90.0
            if exact_keys:
                lineup_keys = list(zip(
                    pd.to_numeric(lineups['MatchID'], errors='coerce'),
                    pd.to_numeric(lineups['PlayerID'], errors='coerce'),
                ))
                lineups = lineups[[key not in exact_keys for key in lineup_keys]].copy()
            international_proxy = _normalise_event_rows(
                lineups,
                'international_start_proxy',
                1,
            )
        else:
            international_proxy = _normalise_event_rows(
                pd.DataFrame(),
                'international_start_proxy',
                1,
            )

        event_parts = [
            part
            for part in [domestic_events, international_exact, international_proxy]
            if not part.empty
        ]
        all_events = (
            pd.concat(event_parts, ignore_index=True)
            if event_parts
            else pd.DataFrame(columns=domestic_events.columns)
        )

    if all_events.empty:
        return {}, {
            'event_count': 0,
            'player_count': 0,
            'international_exact_events': 0,
            'international_proxy_events': 0,
        }

    all_events = all_events.sort_values(
        ['MatchID', 'PlayerID', 'Priority'],
        ascending=[True, True, False],
    ).drop_duplicates(['MatchID', 'PlayerID'], keep='first')
    all_events = all_events.sort_values(['PlayerID', 'MatchDate', 'MatchID']).copy()

    workload_index = {}
    for player_id, group in all_events.groupby('PlayerID', sort=False):
        dates = group['MatchDate'].to_numpy(dtype='datetime64[ns]')
        minutes = group['MinutesPlayed'].to_numpy(dtype='float64')
        cumulative_minutes = np.concatenate(([0.0], np.cumsum(minutes)))
        workload_index[int(player_id)] = (dates, cumulative_minutes)

    metadata = {
        'event_count': int(len(all_events)),
        'player_count': int(all_events['PlayerID'].nunique()),
        'international_exact_events': int(
            (all_events['Source'] == 'international_minutes').sum()
        ),
        'international_proxy_events': int(
            (all_events['Source'] == 'international_start_proxy').sum()
        ),
    }
    return workload_index, metadata


def player_workload_at(workload_index, player_id, match_date):
    """Return normalised pre-match workload and its two minute components."""
    try:
        player_key = int(float(player_id))
    except (TypeError, ValueError):
        return 0.0, 0.0, 0.0

    table = workload_index.get(player_key)
    timestamp = pd.to_datetime(match_date, errors='coerce')
    if table is None or pd.isna(timestamp):
        return 0.0, 0.0, 0.0

    dates, cumulative_minutes = table
    cutoff = np.datetime64(timestamp.to_datetime64(), 'ns')
    right = int(np.searchsorted(dates, cutoff, side='left'))

    def minutes_in_window(days):
        left_cutoff = cutoff - np.timedelta64(int(days), 'D')
        left = int(np.searchsorted(dates, left_cutoff, side='left'))
        return float(cumulative_minutes[right] - cumulative_minutes[left])

    minutes_14 = minutes_in_window(WORKLOAD_SHORT_DAYS)
    minutes_30 = minutes_in_window(WORKLOAD_LONG_DAYS)
    short_load = min(WORKLOAD_INDEX_CAP, minutes_14 / WORKLOAD_SHORT_MINUTES_REFERENCE)
    long_load = min(WORKLOAD_INDEX_CAP, minutes_30 / WORKLOAD_LONG_MINUTES_REFERENCE)
    workload = 0.65 * short_load + 0.35 * long_load
    return float(workload), minutes_14, minutes_30
