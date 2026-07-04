#!/usr/bin/env python3
"""
Download historical 1X2 odds from football-data.co.uk.

Two feeds are produced:

1. Bundesliga (BWIN):
   BWIN's own website only exposes upcoming fixtures, so historical odds for
   already played matches are not scrapeable from sports.bwin.de.
   football-data.co.uk publishes a free CSV per season that includes BWIN's
   closing odds in the columns BWH (home), BWD (draw), BWA (away).
   Output: bwin_historical_odds_<stamp>.csv (schema consumed by the backtest
   analysis scripts -- do not change its columns).

2. World Cup 2026 (international):
   football-data.co.uk does NOT publish BWIN odds for national-team matches.
   The WorldCup2026.xlsx file only carries bet365, Betfair Exchange and the
   market Max/Average prices. Each available bookmaker is written to its own
   CSV (worldcup_odds_<bookmaker>_<stamp>.csv), mapped to the api-football
   MatchIDs from Stammdaten_international.csv.

Reading the xlsx needs openpyxl:  pip install openpyxl
"""
import os
import sys
import unicodedata
from datetime import datetime, timezone
from io import BytesIO, StringIO

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

# ---------------------------------------------------------------------------
# World Cup 2026 (international) configuration
# ---------------------------------------------------------------------------
INTL_STAMMDATEN_PATH = (
    r"C:/AI Projekt/KI-Projekt/Sports Api Data/International/"
    r"Filtered/Datacollection/Stammdaten_international.csv"
)

WORLD_CUP_XLSX_URL = "https://www.football-data.co.uk/WorldCup2026.xlsx"
WORLD_CUP_SHEET = "WorldCup2026"
WORLD_CUP_LEAGUE_ID = 1          # api-football League ID for the World Cup
WORLD_CUP_LEAGUE_NAME = "World Cup"
WORLD_CUP_API_SEASON = 2026      # Season value in Stammdaten_international.csv
WORLD_CUP_SEASON_LABEL = "2026"

# Bookmaker key -> (home_col, draw_col, away_col) in WorldCup2026.xlsx.
# football-data.co.uk does NOT publish BWIN (or Tipico) odds for the World
# Cup, so only the books actually present in the sheet are listed here.
WORLD_CUP_BOOKMAKERS = {
    "bet365": ("bet365-H", "bet365-D", "bet365-A"),
    "betfair_exchange": ("Betfair_Exch-H", "Betfair_Exch-D", "Betfair_Exch-A"),
    "max": ("H-Max", "D-Max", "A-Max"),
    "avg": ("H-Avg", "D-Avg", "A-Avg"),
}

# football-data.co.uk national-team names that differ from the api-football
# names in Stammdaten_international.csv. Keys/values are compared AFTER
# normalize_team_name(), so only genuinely different spellings need listing.
WORLD_CUP_TEAM_ALIASES = {
    "cape verde": "cape verde islands",
    "d.r. congo": "congo dr",
    "dr congo": "congo dr",
    "turkey": "turkiye",
}

WC_OUTPUT_COLUMNS = [
    "scraped_at_utc",
    "league",
    "season",
    "match_id",
    "match_date",
    "match_date_raw",
    "home_team",
    "away_team",
    "home_team_id",
    "away_team_id",
    "home_goals",
    "away_goals",
    "result",
    "bookmaker",
    "odd_home_win_1",
    "odd_draw_x",
    "odd_away_win_2",
    "market",
    "source",
    "source_url",
]

REQUEST_TIMEOUT_SECONDS = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)


def now_utc_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_local_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ===========================================================================
# Bundesliga (BWIN) feed
# ===========================================================================
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


def run_bundesliga():
    """Returns True if at least one Bundesliga odds row was written."""
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
        print("WARN: Keine BWIN-Quoten (Bundesliga) geladen.", file=sys.stderr)
        return False

    out_file, count = write_output(all_rows)
    print(f"OK: {count} Bundesliga-Spiele gespeichert in {out_file}")
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
    return True


# ===========================================================================
# World Cup 2026 (international) feed -- one CSV per bookmaker
# ===========================================================================
def normalize_team_name(name):
    s = str(name).strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    for a, b in (("&", "and"), (".", ""), ("-", " "), ("'", "")):
        s = s.replace(a, b)
    return " ".join(s.split())


def load_intl_team_index(intl_df):
    """normalized api-football team name -> Team ID (from all rows/seasons)."""
    name_to_id = {}
    for _, r in intl_df.iterrows():
        for name_col, id_col in (
            ("Home Team", "Home Team ID"),
            ("Away Team", "Away Team ID"),
        ):
            try:
                tid = int(r[id_col])
            except (ValueError, TypeError):
                continue
            name_to_id[normalize_team_name(r[name_col])] = tid
    return name_to_id


def resolve_intl_team_id(fd_name, name_to_id):
    key = normalize_team_name(fd_name)
    key = WORLD_CUP_TEAM_ALIASES.get(key, key)
    return name_to_id.get(key)


def load_intl_match_lookup(intl_df, league_id):
    """(Season, home_team_id, away_team_id) -> MatchID for one competition."""
    lookup = {}
    sub = intl_df[intl_df["League ID"] == league_id]
    for _, r in sub.iterrows():
        try:
            key = (int(r["Season"]), int(r["Home Team ID"]), int(r["Away Team ID"]))
        except (ValueError, TypeError):
            continue
        lookup[key] = int(r["MatchID"])
    return lookup


def normalize_wc_date(raw_date, raw_time):
    if pd.isna(raw_date):
        return "", ""
    ts = pd.to_datetime(raw_date, errors="coerce")
    if pd.isna(ts):
        return "", str(raw_date)
    iso_date = ts.strftime("%Y-%m-%d")
    time_str = ""
    if not (raw_time is None or (not isinstance(raw_time, str) and pd.isna(raw_time))):
        if hasattr(raw_time, "strftime"):
            time_str = raw_time.strftime("%H:%M")
        else:
            time_str = str(raw_time).strip()[:5]
    display = f"{ts.strftime('%d.%m.%y')} {time_str}".strip()
    return iso_date, display


def result_from_goals(hg, ag):
    if pd.isna(hg) or pd.isna(ag):
        return ""
    if hg > ag:
        return "H"
    if hg < ag:
        return "A"
    return "D"


def download_world_cup_sheet():
    print(f"Lade {WORLD_CUP_LEAGUE_NAME} {WORLD_CUP_SEASON_LABEL} von {WORLD_CUP_XLSX_URL} ...")
    response = requests.get(
        WORLD_CUP_XLSX_URL,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    try:
        df = pd.read_excel(BytesIO(response.content), sheet_name=WORLD_CUP_SHEET)
    except ImportError as exc:
        raise RuntimeError(
            "openpyxl wird zum Lesen der XLSX benoetigt. Installiere es mit: "
            "pip install openpyxl"
        ) from exc
    return df


def build_world_cup_rows(wc_df, name_to_id, match_lookup):
    required = {"Home", "Away"}
    missing = required - set(wc_df.columns)
    if missing:
        raise RuntimeError(
            f"WorldCup2026.xlsx-Spalten fehlen: {sorted(missing)}. "
            "football-data.co.uk hat das Format moeglicherweise geaendert."
        )

    available_books = {
        bk: cols
        for bk, cols in WORLD_CUP_BOOKMAKERS.items()
        if set(cols) <= set(wc_df.columns)
    }
    missing_books = [bk for bk in WORLD_CUP_BOOKMAKERS if bk not in available_books]

    scraped_at = now_utc_iso()
    per_book = {bk: [] for bk in available_books}
    skipped_no_odds = {bk: 0 for bk in available_books}
    unmapped_teams = set()
    unmatched_fixtures = []
    swapped = 0

    for _, r in wc_df.iterrows():
        home_fd = r["Home"]
        away_fd = r["Away"]
        home_id = resolve_intl_team_id(home_fd, name_to_id)
        away_id = resolve_intl_team_id(away_fd, name_to_id)
        if home_id is None:
            unmapped_teams.add(home_fd)
        if away_id is None:
            unmapped_teams.add(away_fd)

        match_id = None
        if home_id is not None and away_id is not None:
            match_id = match_lookup.get((WORLD_CUP_API_SEASON, home_id, away_id))
            if match_id is None:
                # Neutral-venue tournaments: api-football may store the pairing
                # in the opposite home/away order. Match the fixture either way;
                # the 1X2 odds stay tied to football-data's home/away labels.
                swap_id = match_lookup.get((WORLD_CUP_API_SEASON, away_id, home_id))
                if swap_id is not None:
                    match_id = swap_id
                    swapped += 1
                else:
                    unmatched_fixtures.append((WORLD_CUP_SEASON_LABEL, home_fd, away_fd))

        iso_date, display_date = normalize_wc_date(r.get("Date"), r.get("Time"))
        hg, ag = r.get("HGFT"), r.get("AGFT")
        result = result_from_goals(hg, ag)

        base = {
            "scraped_at_utc": scraped_at,
            "league": WORLD_CUP_LEAGUE_NAME,
            "season": WORLD_CUP_SEASON_LABEL,
            "match_id": match_id,
            "match_date": iso_date,
            "match_date_raw": display_date,
            "home_team": home_fd,
            "away_team": away_fd,
            "home_team_id": home_id,
            "away_team_id": away_id,
            "home_goals": hg,
            "away_goals": ag,
            "result": result,
            "market": "match_winner_1x2",
        }

        for bk, (hc, dc, ac) in available_books.items():
            oh, od, oa = r.get(hc), r.get(dc), r.get(ac)
            if pd.isna(oh) or pd.isna(od) or pd.isna(oa):
                skipped_no_odds[bk] += 1
                continue
            row = dict(base)
            row.update(
                {
                    "bookmaker": bk,
                    "odd_home_win_1": float(oh),
                    "odd_draw_x": float(od),
                    "odd_away_win_2": float(oa),
                    "source": f"football-data.co.uk ({bk})",
                    "source_url": WORLD_CUP_XLSX_URL,
                }
            )
            per_book[bk].append(row)

    return (
        per_book,
        available_books,
        missing_books,
        unmapped_teams,
        unmatched_fixtures,
        swapped,
        skipped_no_odds,
    )


def write_world_cup_outputs(per_book):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stamp = now_local_stamp()
    written = []
    for bk, rows in per_book.items():
        if not rows:
            continue
        df = pd.DataFrame(rows, columns=WC_OUTPUT_COLUMNS)
        df = df.sort_values(["match_date", "home_team"], na_position="last")
        out_file = os.path.join(OUTPUT_DIR, f"worldcup_odds_{bk}_{stamp}.csv")
        df.to_csv(out_file, index=False, encoding="utf-8-sig")
        written.append((bk, out_file, len(df)))
    return written


def run_world_cup():
    """Returns True if at least one World Cup bookmaker CSV was written."""
    intl = pd.read_csv(INTL_STAMMDATEN_PATH, encoding="utf-8")
    name_to_id = load_intl_team_index(intl)
    match_lookup = load_intl_match_lookup(intl, WORLD_CUP_LEAGUE_ID)
    print(
        f"International-Stammdaten geladen: {len(name_to_id)} Teamnamen, "
        f"{len(match_lookup)} {WORLD_CUP_LEAGUE_NAME}-Matches im Lookup"
    )

    try:
        wc_df = download_world_cup_sheet()
    except requests.HTTPError as exc:
        print(f"WARN: WorldCup2026.xlsx nicht verfuegbar ({exc}).", file=sys.stderr)
        return False

    (
        per_book,
        _available_books,
        missing_books,
        unmapped_teams,
        unmatched_fixtures,
        swapped,
        skipped_no_odds,
    ) = build_world_cup_rows(wc_df, name_to_id, match_lookup)

    if missing_books:
        print(
            "Hinweis: Diese Buchmacher fehlen im XLSX und werden uebersprungen: "
            f"{missing_books}"
        )

    written = write_world_cup_outputs(per_book)
    if not written:
        print("WARN: Keine World-Cup-Quoten geschrieben (keine Buchmacher-Spalten gefuellt).", file=sys.stderr)
        return False

    for bk, out_file, count in written:
        with_match_id = sum(1 for r in per_book[bk] if r["match_id"] is not None)
        print(
            f"OK: {count} World-Cup-Spiele ({bk}) gespeichert in {out_file} "
            f"(davon {with_match_id} mit MatchID, ohne Quote: {skipped_no_odds[bk]})"
        )

    if swapped:
        print(
            f"Hinweis: {swapped} Begegnung(en) waren in Stammdaten mit vertauschter "
            "Heim/Auswaerts-Reihenfolge hinterlegt (MatchID dennoch zugeordnet)."
        )
    if unmapped_teams:
        print(
            "WARN: Diese FD-Nationen sind nicht auf eine Team-ID gemappt "
            "(ggf. WORLD_CUP_TEAM_ALIASES ergaenzen): "
            f"{sorted(unmapped_teams)}"
        )
    if unmatched_fixtures:
        print(
            f"WARN: {len(unmatched_fixtures)} Spiele ohne MatchID-Match in "
            "Stammdaten_international (erste 5):"
        )
        for season, home, away in unmatched_fixtures[:5]:
            print(f"   {season}: {home} vs {away}")
    return True


def main():
    wrote_any = False
    print("=== Bundesliga (BWIN) ===")
    try:
        wrote_any |= run_bundesliga()
    except Exception as exc:  # noqa: BLE001 - keep World Cup feed independent
        print(f"FEHLER Bundesliga-Feed: {exc}", file=sys.stderr)

    print("\n=== World Cup 2026 (international) ===")
    try:
        wrote_any |= run_world_cup()
    except Exception as exc:  # noqa: BLE001 - keep Bundesliga result independent
        print(f"FEHLER World-Cup-Feed: {exc}", file=sys.stderr)

    if not wrote_any:
        raise RuntimeError("Keine Quoten geladen (weder Bundesliga noch World Cup).")


if __name__ == "__main__":
    main()
