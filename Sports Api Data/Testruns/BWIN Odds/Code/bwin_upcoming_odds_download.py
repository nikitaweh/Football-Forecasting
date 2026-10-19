#!/usr/bin/env python3
"""
Download BWIN 1X2 pre-match odds for the upcoming Bundesliga fixtures.

Source: football-data.co.uk/fixtures.csv (next round of all covered leagues,
columns BWH/BWD/BWA = BWIN pre-match odds). Same source and team mapping as
bwin_historical_odds_download.py, which only covers played matches.

Output (always the same name, overwritten on every run):
    bwin_upcoming_odds.csv
Before it is overwritten, the previous version is appended to:
    bwin_upcoming_odds_history.csv
Each row carries scraped_at_utc, so the history keeps every earlier snapshot
(useful for odds movement and for scoring against the odds that were live
before kickoff).

If the download yields no Bundesliga rows with BWIN odds, nothing is
overwritten.
"""
import os
import sys
from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from bwin_historical_odds_download import (
    FD_TO_API_TEAM_ID,
    OUTPUT_DIR,
    REQUEST_TIMEOUT_SECONDS,
    STAMMDATEN_PATH,
    USER_AGENT,
    now_utc_iso,
)

FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"
DIVISION = "D1"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "bwin_upcoming_odds.csv")
HISTORY_FILE = os.path.join(OUTPUT_DIR, "bwin_upcoming_odds_history.csv")

# football-data.co.uk kickoff times are UK local time.
SOURCE_TZ = ZoneInfo("Europe/London")
LOCAL_TZ = ZoneInfo("Europe/Berlin")

OUTPUT_COLUMNS = [
    "scraped_at_utc",
    "season",
    "match_id",
    "matchday",
    "match_date",
    "kickoff_local",
    "match_date_raw",
    "home_team",
    "away_team",
    "home_team_id",
    "away_team_id",
    "odd_home_win_1",
    "odd_draw_x",
    "odd_away_win_2",
    "overround",
    "market",
    "source",
    "source_url",
]


def download_fixtures():
    print(f"Lade {FIXTURES_URL} ...")
    response = requests.get(
        FIXTURES_URL,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    response.encoding = "latin-1"
    df = pd.read_csv(StringIO(response.text))
    # The file starts with a UTF-8 BOM that latin-1 decodes into the first header.
    df.columns = [c.replace("﻿", "").replace("ï»¿", "").strip() for c in df.columns]
    return df


def load_upcoming_lookup():
    """(home_team_id, away_team_id) -> Stammdaten row for unplayed matches."""
    sd = pd.read_csv(STAMMDATEN_PATH, encoding="utf-8")
    sd = sd[sd["Gespielt"] == False]  # noqa: E712 - column holds booleans
    lookup = {}
    for _, r in sd.iterrows():
        lookup[(int(r["Home Team ID"]), int(r["Away Team ID"]))] = r
    return lookup


def parse_kickoff(raw_date, raw_time):
    """Returns (iso_date_local, kickoff_local 'YYYY-MM-DD HH:MM', raw display)."""
    raw_date = str(raw_date).strip()
    raw_time = str(raw_time).strip() if isinstance(raw_time, str) else ""
    display = f"{raw_date} {raw_time}".strip()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M"):
        try:
            dt = datetime.strptime(f"{raw_date} {raw_time}", fmt).replace(tzinfo=SOURCE_TZ)
            local = dt.astimezone(LOCAL_TZ)
            return local.strftime("%Y-%m-%d"), local.strftime("%Y-%m-%d %H:%M"), display
        except ValueError:
            continue
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d"), "", display
        except ValueError:
            continue
    return "", "", display


def build_rows(raw_df, lookup):
    required = {"Div", "Date", "HomeTeam", "AwayTeam", "BWH", "BWD", "BWA"}
    missing = required - set(raw_df.columns)
    if missing:
        raise RuntimeError(
            f"CSV-Spalten fehlen: {sorted(missing)}. "
            "football-data.co.uk hat das Format moeglicherweise geaendert."
        )

    d1 = raw_df[raw_df["Div"] == DIVISION]
    scraped_at = now_utc_iso()
    rows = []
    skipped_no_odds = 0
    unmapped_teams = set()
    unmatched_fixtures = []

    for _, r in d1.iterrows():
        bwh, bwd, bwa = r.get("BWH"), r.get("BWD"), r.get("BWA")
        if pd.isna(bwh) or pd.isna(bwd) or pd.isna(bwa):
            skipped_no_odds += 1
            continue

        home_fd, away_fd = r["HomeTeam"], r["AwayTeam"]
        home_id = FD_TO_API_TEAM_ID.get(home_fd)
        away_id = FD_TO_API_TEAM_ID.get(away_fd)
        if home_id is None:
            unmapped_teams.add(home_fd)
        if away_id is None:
            unmapped_teams.add(away_fd)

        sd_row = None
        if home_id is not None and away_id is not None:
            sd_row = lookup.get((home_id, away_id))
            if sd_row is None:
                unmatched_fixtures.append((home_fd, away_fd))

        iso_date, kickoff_local, display = parse_kickoff(r.get("Date"), r.get("Time"))
        bwh, bwd, bwa = float(bwh), float(bwd), float(bwa)
        rows.append(
            {
                "scraped_at_utc": scraped_at,
                "season": int(sd_row["Season"]) if sd_row is not None else None,
                "match_id": int(sd_row["MatchID"]) if sd_row is not None else None,
                "matchday": sd_row["Matchday"] if sd_row is not None else None,
                "match_date": iso_date,
                "kickoff_local": kickoff_local,
                "match_date_raw": display,
                "home_team": home_fd,
                "away_team": away_fd,
                "home_team_id": home_id,
                "away_team_id": away_id,
                "odd_home_win_1": bwh,
                "odd_draw_x": bwd,
                "odd_away_win_2": bwa,
                "overround": round(1 / bwh + 1 / bwd + 1 / bwa, 4),
                "market": "match_winner_1x2",
                "source": "football-data.co.uk (bwin, pre-match)",
                "source_url": FIXTURES_URL,
            }
        )

    return rows, skipped_no_odds, unmapped_teams, unmatched_fixtures


def archive_previous_version():
    """Append the current output file to the history file. Returns rows archived."""
    if not os.path.exists(OUTPUT_FILE):
        return 0
    try:
        prev = pd.read_csv(OUTPUT_FILE, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return 0
    if prev.empty:
        return 0
    write_header = not os.path.exists(HISTORY_FILE) or os.path.getsize(HISTORY_FILE) == 0
    prev.to_csv(HISTORY_FILE, mode="a", header=write_header, index=False, encoding="utf-8-sig" if write_header else "utf-8")
    return len(prev)


def write_output(rows):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    df = df.sort_values(["kickoff_local", "home_team"], na_position="last")
    tmp_file = OUTPUT_FILE + ".tmp"
    df.to_csv(tmp_file, index=False, encoding="utf-8-sig")
    archived = archive_previous_version()
    os.replace(tmp_file, OUTPUT_FILE)
    return len(df), archived


def main():
    lookup = load_upcoming_lookup()
    print(f"Stammdaten geladen: {len(lookup)} ungespielte Matches im Lookup")

    raw = download_fixtures()
    rows, skipped, unmapped, unmatched = build_rows(raw, lookup)

    if not rows:
        print(
            f"WARN: Keine {DIVISION}-Spiele mit BWIN-Quote in fixtures.csv "
            f"(ohne Quote: {skipped}). {OUTPUT_FILE} bleibt unveraendert.",
            file=sys.stderr,
        )
        sys.exit(1)

    count, archived = write_output(rows)
    with_match_id = sum(1 for r in rows if r["match_id"] is not None)
    print(f"OK: {count} kommende Bundesliga-Spiele gespeichert in {OUTPUT_FILE} (davon {with_match_id} mit MatchID)")
    if archived:
        print(f"Vorherige Version ({archived} Zeilen) angehaengt an {HISTORY_FILE}")
    else:
        print("Keine vorherige Version vorhanden - nichts archiviert.")
    if skipped:
        print(f"Hinweis: {skipped} Spiele ohne BWIN-Quote uebersprungen.")
    if unmapped:
        print(
            "WARN: Diese FD-Teamnamen sind nicht in FD_TO_API_TEAM_ID gemappt "
            f"(in bwin_historical_odds_download.py ergaenzen): {sorted(unmapped)}"
        )
    if unmatched:
        print(f"WARN: {len(unmatched)} Spiele ohne ungespieltes Gegenstueck in Stammdaten:")
        for home, away in unmatched:
            print(f"   {home} vs {away}")


if __name__ == "__main__":
    main()
