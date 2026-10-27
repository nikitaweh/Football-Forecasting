#!/usr/bin/env python3
"""
kickoff_guard.py  --  Decide whether a prediction run is due right now.

    python ops/bin/kickoff_guard.py bundesliga [--window-hours 36] [--min-lead-hours 3]
    python ops/bin/kickoff_guard.py international [...]

Exit code 0 = run now, 10 = skip (reason on stdout), 1 = error.

Rules (kickoff times in the Stammdaten CSVs are Europe/Berlin):
- bundesliga: the target set is what AI_match_stats_prediction.py predicts in
  future mode, i.e. the 9 earliest unplayed matches (build_prediction_frame).
  Run when the earliest upcoming kickoff in that set is between min-lead and
  window hours away, and future_outcome_table.csv does not already hold
  exactly that set. One run per matchday, so the surrogate history only grows
  by one search per matchday and a published table is never replaced after
  kickoff.
- international: run when a competitive match (FIFA + UEFA branches) kicks off
  between min-lead and window hours from now and is missing from
  international_competitive_predictions.csv.

min-lead covers the prediction runtime (about 1 h for 30 runs locally; measure
on the VPS) plus a margin, so predictions exist before the first kickoff.
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(os.environ.get("KI_PROJECT_ROOT") or Path(__file__).resolve().parents[2])
DATA = ROOT / "Sports Api Data"
BERLIN = ZoneInfo("Europe/Berlin")
SKIP = 10
FUTURE_LIMIT = 9  # AI_match_stats_prediction.build_prediction_frame(future_limit=9)


def load_fixtures(paths):
    frames = [pd.read_csv(p, dtype={"MatchID": "Int64"}) for p in paths if p.exists()]
    if not frames:
        raise FileNotFoundError(", ".join(str(p) for p in paths))
    df = pd.concat(frames, ignore_index=True).drop_duplicates("MatchID")
    df["Played"] = df["Gespielt"].astype(str).str.lower().eq("true")
    kickoff = pd.to_datetime(df["Date"].astype(str) + " " + df["Time"].fillna("00:00:00").astype(str),
                             errors="coerce")
    df["Kickoff"] = kickoff.dt.tz_localize(BERLIN, ambiguous="NaT", nonexistent="NaT")
    return df


def predicted_ids(path):
    if not path.exists():
        return set()
    return set(pd.read_csv(path, usecols=["MatchID"])["MatchID"].dropna().astype(int))


def in_window(kickoff, now, args):
    lead = (kickoff - now).total_seconds() / 3600
    return args.min_lead_hours <= lead <= args.window_hours, lead


def guard_bundesliga(now, args):
    df = load_fixtures([DATA / "Bundesliga/Filtered/Datacollection/Stammdaten_78.csv"])
    unplayed = df[~df["Played"]].sort_values(["Date", "Kickoff"]).head(FUTURE_LIMIT)
    if unplayed.empty:
        return SKIP, "no unplayed Bundesliga matches"
    upcoming = unplayed[unplayed["Kickoff"] > now]
    stale = len(unplayed) - len(upcoming)
    if upcoming.empty:
        return SKIP, f"all {len(unplayed)} target matches have a past kickoff (stale fixtures?)"
    first = upcoming["Kickoff"].min()
    ok, lead = in_window(first, now, args)
    target = set(unplayed["MatchID"].astype(int))
    table = DATA / "Testruns/Datacollection future/future_outcome_table.csv"
    note = f" ({stale} target matches already past kickoff: postponed?)" if stale else ""
    if not ok:
        return SKIP, f"first kickoff {first:%a %Y-%m-%d %H:%M} is {lead:.1f} h away{note}"
    if predicted_ids(table) == target:
        return SKIP, f"future_outcome_table.csv already covers this matchday{note}"
    return 0, f"run: {len(target)} matches, first kickoff in {lead:.1f} h{note}"


def guard_international(now, args):
    branches = [DATA / f"International/{b}/Filtered/Datacollection/Stammdaten_international.csv"
                for b in ("FIFA", "UEFA")]
    df = load_fixtures(branches)
    soon = df[~df["Played"] & df["Kickoff"].notna()]
    soon = soon[soon["Kickoff"].apply(lambda k: in_window(k, now, args)[0])]
    if soon.empty:
        return SKIP, "no competitive international match in the window"
    preds = DATA / "International/Model Output/competitive/international_competitive_predictions.csv"
    missing = set(soon["MatchID"].astype(int)) - predicted_ids(preds)
    if not missing:
        return SKIP, f"all {len(soon)} matches in the window are already predicted"
    first = soon["Kickoff"].min()
    return 0, f"run: {len(missing)} unpredicted matches, first kickoff {first:%a %Y-%m-%d %H:%M}"


def main():
    parser = argparse.ArgumentParser(description="Exit 0 if a prediction run is due, 10 if not.")
    parser.add_argument("league", choices=["bundesliga", "international"])
    parser.add_argument("--window-hours", type=float, default=36.0)
    parser.add_argument("--min-lead-hours", type=float, default=3.0)
    parser.add_argument("--now", help="Override 'now' (Europe/Berlin, 'YYYY-MM-DD HH:MM') for testing.")
    args = parser.parse_args()

    now = (datetime.strptime(args.now, "%Y-%m-%d %H:%M").replace(tzinfo=BERLIN)
           if args.now else datetime.now(BERLIN))
    guard = guard_bundesliga if args.league == "bundesliga" else guard_international
    code, reason = guard(now, args)
    print(f"[kickoff_guard {args.league}] {reason}")
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # unreadable CSV etc. -> visible failure, not a silent skip
        print(f"[kickoff_guard] error: {exc}", file=sys.stderr)
        sys.exit(1)
