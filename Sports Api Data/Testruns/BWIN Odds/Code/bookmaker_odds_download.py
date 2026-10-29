#!/usr/bin/env python3
"""
Collect 1X2 pre-match odds of several bookmakers for the upcoming Bundesliga fixtures.

Sources:
  - API-Football /odds (league 78, current season, bet 1 = Match Winner): Bet365, Betano and
    Tipico. One call returns every bookmaker of a fixture; the API covered Bet365 and Betano
    for all upcoming fixtures in Oct 2026, Tipico and Bwin not at all -- Tipico is kept in the
    list so it shows up as soon as the API carries it. Costs 1 request per 10 fixtures.
  - Bwin from bwin_upcoming_odds.csv (football-data.co.uk, written by
    bwin_upcoming_odds_download.py; run that first).

Outputs (in Datacollection/):
  bookmaker_odds_latest.csv   one row per (match_id, bookmaker): the last odds scraped
                              before kickoff. Rows are never dropped, so played matches keep
                              their pre-match prices (the website reads this file).
  bookmaker_odds_history.csv  every scrape appended (odds movement, benchmark analysis).

Odds of fixtures that already kicked off are ignored, so a late run cannot replace the
pre-match prices with in-play or closing ones.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# The laptop venv's interpreter does not put the script folder on sys.path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bwin_historical_odds_download import (  # noqa: E402
    OUTPUT_DIR, PROJECT_ROOT, REQUEST_TIMEOUT_SECONDS, STAMMDATEN_PATH, now_utc_iso,
)

API_URL = "https://v3.football.api-sports.io/odds"
LEAGUE_ID = 78
MATCH_WINNER_BET_ID = 1
# API-Football bookmaker ids (GET /odds/bookmakers).
API_BOOKMAKERS = {8: "Bet365", 32: "Betano", 22: "Tipico"}

BWIN_FILE = os.path.join(OUTPUT_DIR, "bwin_upcoming_odds.csv")
LATEST_FILE = os.path.join(OUTPUT_DIR, "bookmaker_odds_latest.csv")
HISTORY_FILE = os.path.join(OUTPUT_DIR, "bookmaker_odds_history.csv")

COLUMNS = [
    "match_id", "bookmaker", "odd_home_win_1", "odd_draw_x", "odd_away_win_2", "overround",
    "kickoff_utc", "odds_updated_utc", "scraped_at_utc", "source",
]


def _secret(name):
    """API keys come from the environment (systemd EnvironmentFile on the VPS)
    or, failing that, from the gitignored .env at the repo root."""
    env_file = os.path.join(PROJECT_ROOT, ".env")
    if name not in os.environ and os.path.exists(env_file):
        with open(env_file, encoding="utf-8") as fh:
            for line in fh:
                key, sep, value = line.strip().partition("=")
                if sep and not key.startswith("#"):
                    os.environ.setdefault(key.strip(), value.strip().strip('"'))
    if not os.environ.get(name):
        raise RuntimeError(f"{name} is not set (environment or {env_file})")
    return os.environ[name]


def current_season():
    sd = pd.read_csv(STAMMDATEN_PATH, usecols=["Season"])
    return int(sd["Season"].max())


def odds_row(match_id, bookmaker, home, draw, away, kickoff_utc, updated_utc, scraped_at, source):
    home, draw, away = float(home), float(draw), float(away)
    return {
        "match_id": int(match_id), "bookmaker": bookmaker,
        "odd_home_win_1": home, "odd_draw_x": draw, "odd_away_win_2": away,
        "overround": round(1 / home + 1 / draw + 1 / away, 4),
        "kickoff_utc": kickoff_utc, "odds_updated_utc": updated_utc,
        "scraped_at_utc": scraped_at, "source": source,
    }


def fetch_api_football(season, now):
    key = _secret("API_FOOTBALL_KEY")
    scraped_at = now_utc_iso()
    rows, page, pages, requests_used = [], 1, 1, 0
    while page <= pages:
        response = requests.get(
            API_URL,
            params={"league": LEAGUE_ID, "season": season, "bet": MATCH_WINNER_BET_ID, "page": page},
            headers={"x-apisports-key": key},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        requests_used += 1
        if payload.get("errors"):
            raise RuntimeError(f"API-Football error: {payload['errors']}")
        pages = int(payload.get("paging", {}).get("total") or 1)
        for item in payload.get("response", []):
            kickoff = datetime.fromisoformat(item["fixture"]["date"]).astimezone(timezone.utc)
            if kickoff <= now:
                continue
            for book in item.get("bookmakers", []):
                name = API_BOOKMAKERS.get(book.get("id"))
                bet = next((b for b in book.get("bets", []) if b.get("id") == MATCH_WINNER_BET_ID), None)
                if name is None or bet is None:
                    continue
                values = {v.get("value"): v.get("odd") for v in bet.get("values", [])}
                if not all(values.get(k) for k in ("Home", "Draw", "Away")):
                    continue
                rows.append(odds_row(
                    item["fixture"]["id"], name, values["Home"], values["Draw"], values["Away"],
                    kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"), item.get("update", ""), scraped_at,
                    "API-Football /odds (pre-match)",
                ))
        page += 1
    return rows, requests_used


def read_bwin(now):
    """Bwin rows of the football-data.co.uk snapshot that were scraped before kickoff."""
    if not os.path.exists(BWIN_FILE):
        return []
    df = pd.read_csv(BWIN_FILE, encoding="utf-8-sig").dropna(subset=["match_id"])
    rows = []
    for _, r in df.iterrows():
        if not r.get("kickoff_local"):
            continue
        kickoff = pd.Timestamp(r["kickoff_local"]).tz_localize("Europe/Berlin").tz_convert("UTC")
        scraped = pd.Timestamp(r["scraped_at_utc"])
        if kickoff <= scraped or kickoff <= now:
            continue
        rows.append(odds_row(
            r["match_id"], "Bwin", r["odd_home_win_1"], r["odd_draw_x"], r["odd_away_win_2"],
            kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"), r["scraped_at_utc"], r["scraped_at_utc"],
            "football-data.co.uk (bwin, pre-match)",
        ))
    return rows


def merge_latest(new_rows):
    new = pd.DataFrame(new_rows, columns=COLUMNS)
    if os.path.exists(LATEST_FILE):
        old = pd.read_csv(LATEST_FILE, encoding="utf-8-sig")
        merged = pd.concat([old, new], ignore_index=True)
    else:
        merged = new
    merged = (merged.sort_values("scraped_at_utc")
                    .drop_duplicates(["match_id", "bookmaker"], keep="last")
                    .sort_values(["kickoff_utc", "match_id", "bookmaker"]))
    tmp = LATEST_FILE + ".tmp"
    merged.to_csv(tmp, index=False, encoding="utf-8-sig")
    os.replace(tmp, LATEST_FILE)

    write_header = not os.path.exists(HISTORY_FILE) or os.path.getsize(HISTORY_FILE) == 0
    new.to_csv(HISTORY_FILE, mode="a", header=write_header, index=False,
               encoding="utf-8-sig" if write_header else "utf-8")
    return len(merged)


def main():
    now = datetime.now(timezone.utc)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    season = current_season()
    api_rows, used = fetch_api_football(season, now)
    bwin_rows = read_bwin(now)
    rows = api_rows + bwin_rows
    if not rows:
        print(f"WARN: no pre-match odds for upcoming fixtures (season {season}); "
              f"{LATEST_FILE} unchanged.", file=sys.stderr)
        sys.exit(1)
    total = merge_latest(rows)
    per_book = pd.Series([r["bookmaker"] for r in rows]).value_counts().to_dict()
    print(f"OK: {len(rows)} odds rows {per_book} from {used} API requests; "
          f"{LATEST_FILE} now holds {total} rows")


if __name__ == "__main__":
    main()
