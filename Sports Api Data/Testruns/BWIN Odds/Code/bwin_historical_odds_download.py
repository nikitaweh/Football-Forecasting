#!/usr/bin/env python3
"""
Download historical BWIN 1X2 odds for the Bundesliga from football-data.co.uk.

BWIN's own website only exposes upcoming fixtures, so historical odds for already
played matches are not scrapeable from sports.bwin.de. football-data.co.uk
publishes a free CSV per season that includes BWIN's closing odds in the columns
BWH (home), BWD (draw), BWA (away).

Output schema is aligned with the live scraper
(bwin_match_winner_odds_scraper.py) so the files are interchangeable, plus a few
extra columns that only make sense for historical data (season, final score).
"""
import os
import sys
from datetime import datetime, timezone
from io import StringIO

import pandas as pd
import requests


OUTPUT_DIR = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Testruns/BWIN Odds/Datacollection"
BASE_URL = "https://www.football-data.co.uk/mmz4281/{season_code}/D1.csv"

STAMMDATEN_PATH = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/Stammdaten_78.csv"
TEAMS_PATH = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/Teams_78.csv"

# Map a human-readable season label to football-data.co.uk's season code
# and to the api-football season integer used in Stammdaten_78.csv
# (api-football uses the starting year of the season).
SEASONS = {
    "2024/25": {"fd_code": "2425", "api_season": 2024},
    "2025/26": {"fd_code": "2526", "api_season": 2025},
}

# football-data.co.uk uses short / English team names. Map them to the
# api-football Team IDs from Teams_78.csv so we can join on Stammdaten.
FD_TO_API_TEAM_ID = {
    "Augsburg": 170,
    "Bayern Munich": 157,
    "Bochum": 176,
    "Dortmund": 165,
    "Ein Frankfurt": 169,
    "FC Koln": 192,
    "Freiburg": 160,
    "Hamburg": 175,
    "Heidenheim": 180,
    "Hoffenheim": 167,
    "Holstein Kiel": 191,
    "Leverkusen": 168,
    "M'gladbach": 163,
    "Mainz": 164,
    "RB Leipzig": 173,
    "St Pauli": 186,
    "Stuttgart": 172,
    "Union Berlin": 182,
    "Werder Bremen": 162,
    "Wolfsburg": 161,
}

REQUEST_TIMEOUT_SECONDS = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)


def now_utc_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_local_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def download_season(season_label, season_code, api_season):
    url = BASE_URL.format(season_code=season_code)
    print(f"Lade {season_label} von {url} ...")
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    # football-data.co.uk serves latin-1 encoded CSVs with German umlauts.
    response.encoding = "latin-1"
    df = pd.read_csv(StringIO(response.text))
    df["__season__"] = season_label
    df["__api_season__"] = api_season
    df["__source_url__"] = url
    return df


def load_match_lookup():
    """
    Build a lookup: (api_season, home_team_id, away_team_id) -> MatchID
    from Stammdaten_78.csv.
    """
    sd = pd.read_csv(STAMMDATEN_PATH, encoding="utf-8")
    lookup = {}
    for _, r in sd.iterrows():
        key = (int(r["Season"]), int(r["Home Team ID"]), int(r["Away Team ID"]))
        lookup[key] = int(r["MatchID"])
    return lookup


def normalize_date(raw_date, raw_time):
    # football-data.co.uk uses DD/MM/YYYY or DD/MM/YY for the Date column
    # and HH:MM for Time (when present).
    if not isinstance(raw_date, str) or not raw_date.strip():
        return "", ""
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            parsed = datetime.strptime(raw_date.strip(), fmt)
            break
        except ValueError:
            parsed = None
    if parsed is None:
        return "", raw_date

    iso_date = parsed.strftime("%Y-%m-%d")
    time_str = raw_time.strip() if isinstance(raw_time, str) else ""
    display = f"{parsed.strftime('%d.%m.%y')} {time_str}".strip()
    return iso_date, display


def build_output_rows(raw_df, match_lookup):
    required = {"HomeTeam", "AwayTeam", "BWH", "BWD", "BWA"}
    missing = required - set(raw_df.columns)
    if missing:
        raise RuntimeError(
            f"CSV-Spalten fehlen: {sorted(missing)}. "
            "football-data.co.uk hat das Format moeglicherweise geaendert."
        )

    scraped_at = now_utc_iso()
    rows = []
    skipped_no_odds = 0
    unmapped_teams = set()
    unmatched_fixtures = []

    for _, r in raw_df.iterrows():
        bwh, bwd, bwa = r.get("BWH"), r.get("BWD"), r.get("BWA")
        if pd.isna(bwh) or pd.isna(bwd) or pd.isna(bwa):
            skipped_no_odds += 1
            continue

        iso_date, display_date = normalize_date(r.get("Date", ""), r.get("Time", ""))

        home_fd = r["HomeTeam"]
        away_fd = r["AwayTeam"]
        home_id = FD_TO_API_TEAM_ID.get(home_fd)
        away_id = FD_TO_API_TEAM_ID.get(away_fd)
        if home_id is None:
            unmapped_teams.add(home_fd)
        if away_id is None:
            unmapped_teams.add(away_fd)

        match_id = None
        if home_id is not None and away_id is not None:
            match_id = match_lookup.get((int(r["__api_season__"]), home_id, away_id))
            if match_id is None:
                unmatched_fixtures.append((r["__season__"], home_fd, away_fd))

        rows.append(
            {
                "scraped_at_utc": scraped_at,
                "season": r["__season__"],
                "match_id": match_id,
                "match_date": iso_date,
                "match_date_raw": display_date,
                "home_team": home_fd,
                "away_team": away_fd,
                "home_team_id": home_id,
                "away_team_id": away_id,
                "home_goals": r.get("FTHG"),
                "away_goals": r.get("FTAG"),
                "result": r.get("FTR"),
                "odd_home_win_1": float(bwh),
                "odd_draw_x": float(bwd),
                "odd_away_win_2": float(bwa),
                "market": "match_winner_1x2",
                "source": "football-data.co.uk (bwin)",
                "source_url": r["__source_url__"],
            }
        )

    return rows, skipped_no_odds, unmapped_teams, unmatched_fixtures


def write_output(rows):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stamp = now_local_stamp()
    out_file = os.path.join(OUTPUT_DIR, f"bwin_historical_odds_{stamp}.csv")
    df = pd.DataFrame(rows)
    df = df.sort_values(["season", "match_date", "home_team"], na_position="last")
    df.to_csv(out_file, index=False, encoding="utf-8-sig")
    return out_file, len(df)


def main():
    match_lookup = load_match_lookup()
    print(f"Stammdaten geladen: {len(match_lookup)} Matches im Lookup")

    all_rows = []
    total_skipped = 0
    all_unmapped_teams = set()
    all_unmatched_fixtures = []

    for season_label, cfg in SEASONS.items():
        try:
            df = download_season(season_label, cfg["fd_code"], cfg["api_season"])
        except requests.HTTPError as exc:
            print(f"WARN: {season_label} nicht verfuegbar ({exc}).", file=sys.stderr)
            continue

        rows, skipped, unmapped, unmatched = build_output_rows(df, match_lookup)
        with_match_id = sum(1 for r in rows if r["match_id"] is not None)
        print(
            f"  {season_label}: {len(rows)} Spiele mit BWIN-Quoten, "
            f"davon {with_match_id} mit MatchID verknuepft "
            f"(uebersprungen ohne Quote: {skipped})"
        )
        all_rows.extend(rows)
        total_skipped += skipped
        all_unmapped_teams.update(unmapped)
        all_unmatched_fixtures.extend(unmatched)

    if not all_rows:
        raise RuntimeError("Keine BWIN-Quoten geladen.")

    out_file, count = write_output(all_rows)
    print(f"OK: {count} Spiele gespeichert in {out_file}")
    if total_skipped:
        print(f"Hinweis: {total_skipped} Spiele ohne BWIN-Quote uebersprungen.")
    if all_unmapped_teams:
        print(
            "WARN: Diese FD-Teamnamen sind nicht in FD_TO_API_TEAM_ID gemappt: "
            f"{sorted(all_unmapped_teams)}"
        )
    if all_unmatched_fixtures:
        print(
            f"WARN: {len(all_unmatched_fixtures)} Spiele ohne MatchID-Match in Stammdaten "
            "(erste 5):"
        )
        for season, home, away in all_unmatched_fixtures[:5]:
            print(f"   {season}: {home} vs {away}")


if __name__ == "__main__":
    main()
