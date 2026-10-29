# -*- coding: utf-8 -*-
"""
build_data.py  --  Generates website/data.js from the model's CSV exports.

Live mode (default) reads the model's current output, derives the matchday
by joining MatchIDs against the league's Stammdaten, snapshots the input
CSVs to website/matchdays/ and rewrites data.js:

    python website/build_data.py

Rebuild from a saved snapshot instead (no snapshot writing):

    python website/build_data.py --matchday 33

League settings (team map, CSV paths, display name) live in
website/config/leagues/<league>.json:

    python website/build_data.py --league bundesliga

Matches without a known result are still written out and the website
renders them as "upcoming" automatically.
"""

import argparse
import csv
import json
import logging
import os
import shutil
from collections import Counter
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG_DIR = os.path.join(HERE, "config", "leagues")
SNAPSHOT_DIR = os.path.join(HERE, "matchdays")

log = logging.getLogger("orakel.build")

RESULT_TO_OUTCOME = {"H": "HomeWin", "D": "Draw", "A": "AwayWin"}


def num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# --- League config -----------------------------------------------------------

def load_config(league):
    path = os.path.join(CONFIG_DIR, league + ".json")
    if not os.path.exists(path):
        available = sorted(f[:-5] for f in os.listdir(CONFIG_DIR) if f.endswith(".json"))
        raise SystemExit("Unknown league '{0}' (no {1}). Available: {2}".format(
            league, path, ", ".join(available) or "none"))
    with open(path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    # Logos live in website/logos/<id>.png (downloaded from media.api-sports.io).
    for _name, _meta in cfg["teams"].items():
        _meta["logo"] = "logos/{0}.png".format(_meta["id"])
    return cfg


# --- Stammdaten join: MatchID -> matchday / season ---------------------------

def load_stammdaten(path):
    """MatchID -> {"matchday": raw string, "season": year string}"""
    index = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            mid = (row.get("MatchID") or "").strip()
            if not mid:
                continue
            index[mid] = {
                "matchday": (row.get("Matchday") or "").strip(),
                "season": (row.get("Season") or "").strip(),
            }
    return index


def matchday_number(raw):
    """Trailing integer of a Stammdaten matchday string, or None.
    'Regular Season - 34' -> 34, 'Group Stage - 1' -> 1."""
    tail = raw.rsplit("-", 1)[-1].strip()
    return int(tail) if tail.isdigit() else None


def matchday_label(raw):
    """'Regular Season - N' renders as 'Matchday N'; anything else
    (cup stages like 'Group Stage - 1') passes through verbatim."""
    if raw.startswith("Regular Season -"):
        n = matchday_number(raw)
        if n is not None:
            return "Matchday {0}".format(n)
    return raw


def season_label(year, fmt):
    """'cross-year': 2025 -> '2025/26' (club seasons); 'single-year': '2026'."""
    if fmt == "cross-year" and year.isdigit():
        return "{0}/{1:02d}".format(year, (int(year) + 1) % 100)
    return year


def derive_meta_fields(matches, stammdaten):
    """Vote the matchday/season for this batch of predictions via the
    Stammdaten join. Mixed or missing MatchIDs are warned, not fatal."""
    votes = Counter()
    for m in matches:
        info = stammdaten.get(str(m["id"]))
        if info is None:
            log.warning("MatchID %s not found in Stammdaten -- excluded from matchday derivation", m["id"])
            continue
        votes[(info["matchday"], info["season"])] += 1
    if not votes:
        raise SystemExit("No prediction MatchID could be resolved against the Stammdaten -- cannot derive matchday.")
    if len(votes) > 1:
        log.warning("Predictions span mixed matchdays %s -- using the most frequent",
                    sorted(set(k[0] for k in votes)))
    raw_matchday, season_year = votes.most_common(1)[0][0]
    return raw_matchday, season_year


# --- CSV loading (unchanged transform) ----------------------------------------

def load_results(path):
    """MatchID -> {homeGoals, awayGoals, outcome}"""
    results = {}
    if not os.path.exists(path):
        return results
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            mid = (row.get("MatchID") or "").strip()
            if not mid:
                continue
            results[mid] = {
                "homeGoals": int(num(row.get("HomeGoals"))),
                "awayGoals": int(num(row.get("AwayGoals"))),
                "outcome": RESULT_TO_OUTCOME.get((row.get("Result") or "").strip(), None),
            }
    return results


BOOKMAKER_ORDER = ["Bwin", "Bet365", "Betano", "Tipico"]


def load_odds(path):
    """MatchID -> [{bookmaker, home, draw, away}] from bookmaker_odds_latest.csv
    (last pre-kickoff 1X2 odds per bookmaker). Missing file -> no odds shown."""
    odds = {}
    if not path or not os.path.exists(path):
        return odds
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            mid = (row.get("match_id") or "").strip()
            prices = [num(row.get(c), None) for c in ("odd_home_win_1", "odd_draw_x", "odd_away_win_2")]
            if not mid or None in prices:
                continue
            odds.setdefault(mid, []).append({
                "bookmaker": (row.get("bookmaker") or "").strip(),
                "home": prices[0], "draw": prices[1], "away": prices[2],
            })
    rank = {name: i for i, name in enumerate(BOOKMAKER_ORDER)}
    for books in odds.values():
        books.sort(key=lambda b: rank.get(b["bookmaker"], len(rank)))
    return odds


def load_matches(path, results):
    """Returns (matches, configuration_label)."""
    matches = []
    config = ""
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            mid = (row.get("MatchID") or "").strip()
            if not mid:
                continue
            if not config:
                label = (row.get("RecommendationLabel") or "").strip()
                run = (row.get("RecommendedRunID") or "").strip()
                config = "{0} (Run {1})".format(label, run) if run else label
            matches.append({
                "id": int(mid),
                "date": (row.get("MatchDate") or "").strip(),
                "home": (row.get("HomeTeam") or "").strip(),
                "away": (row.get("AwayTeam") or "").strip(),
                "prediction": {
                    "outcome": (row.get("MostLikelyOutcome") or "").strip(),
                    "homeWinProb": num(row.get("WinProb")),
                    "drawProb": num(row.get("DrawProb")),
                    "awayWinProb": num(row.get("LoseProb")),
                    "confidence": num(row.get("MostLikelyOutcomeProbability")),
                    "homeGoals": int(num(row.get("PredictedHomeGoals"))),
                    "awayGoals": int(num(row.get("PredictedAwayGoals"))),
                    "scoreline": (row.get("PredictedScoreline") or "").strip(),
                    "xgHome": num(row.get("ExpectedHomeGoals")),
                    "xgAway": num(row.get("ExpectedAwayGoals")),
                    "goalDiff": num(row.get("PredictedGoalDiff")),
                    "label": (row.get("RecommendationLabel") or "").strip(),
                },
                "result": results.get(mid),
            })
    # Strongest calls first.
    matches.sort(key=lambda m: m["prediction"]["confidence"], reverse=True)
    return matches, config


# --- Snapshots ----------------------------------------------------------------

def _files_identical(a, b):
    with open(a, "rb") as fa, open(b, "rb") as fb:
        return fa.read() == fb.read()


def write_snapshot(md_number, predictions_csv, results_csv):
    """Copy the live source CSVs to matchdays/md{N}_*.csv.
    Results always win (they trickle in over a weekend); a differing
    predictions snapshot is replaced but loudly, since it means the
    model was re-run for a matchday we already archived."""
    if md_number is None:
        log.warning("Matchday has no numeric part -- snapshot skipped")
        return
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    pred_dst = os.path.join(SNAPSHOT_DIR, "md{0}_predictions.csv".format(md_number))
    if os.path.exists(pred_dst) and not _files_identical(predictions_csv, pred_dst):
        log.warning("md%s_predictions.csv replaced (model was re-run)", md_number)
    if not os.path.exists(pred_dst) or not _files_identical(predictions_csv, pred_dst):
        shutil.copyfile(predictions_csv, pred_dst)

    if os.path.exists(results_csv):
        shutil.copyfile(results_csv, os.path.join(
            SNAPSHOT_DIR, "md{0}_results.csv".format(md_number)))


# --- Build --------------------------------------------------------------------

def build(league="bundesliga", matchday=None):
    """Build data.js for a league. matchday=None -> live model output
    (snapshots the inputs); matchday=N -> rebuild from matchdays/md{N}_*.csv.
    Returns a summary dict for callers that log (refresh_data.py)."""
    cfg = load_config(league)

    if matchday is None:
        predictions_csv = os.path.join(ROOT, *cfg["sources"]["predictions"].split("/"))
        results_csv = os.path.join(ROOT, *cfg["sources"]["results"].split("/"))
    else:
        predictions_csv = os.path.join(SNAPSHOT_DIR, "md{0}_predictions.csv".format(matchday))
        results_csv = os.path.join(SNAPSHOT_DIR, "md{0}_results.csv".format(matchday))
        if not os.path.exists(predictions_csv):
            raise SystemExit("No snapshot for matchday {0} ({1} missing)".format(matchday, predictions_csv))

    stammdaten = load_stammdaten(os.path.join(ROOT, *cfg["sources"]["stammdaten"].split("/")))
    results = load_results(results_csv)
    matches, configuration = load_matches(predictions_csv, results)
    # The odds file keeps played matches too, so snapshot rebuilds read the live one.
    odds_rel = cfg["sources"].get("odds")
    odds = load_odds(os.path.join(ROOT, *odds_rel.split("/")) if odds_rel else None)
    for m in matches:
        m["odds"] = odds.get(str(m["id"]), [])

    raw_matchday, season_year = derive_meta_fields(matches, stammdaten)
    md_number = matchday_number(raw_matchday)

    meta = {
        "league": cfg["leagueName"],
        "season": season_label(season_year, cfg.get("seasonLabelFormat", "cross-year")),
        "matchday": md_number,
        "matchdayLabel": matchday_label(raw_matchday),
        "matchdayDate": min(m["date"] for m in matches),
        "model": cfg["model"],
        "configuration": configuration,
        "signalsPerMatch": cfg["signalsPerMatch"],
        "generated": datetime.now().strftime("%Y-%m-%d"),
    }

    if matchday is None:
        write_snapshot(md_number, predictions_csv, results_csv)

    output_js = os.path.join(HERE, *cfg["output"].split("/"))
    os.makedirs(os.path.dirname(output_js) or HERE, exist_ok=True)
    payload = {"meta": meta, "teams": cfg["teams"], "matches": matches}
    with open(output_js, "w", encoding="utf-8") as fh:
        fh.write("/* data.js -- auto-generated by build_data.py. Do not edit by hand. */\n")
        fh.write("window.ORAKEL_DATA = ")
        fh.write(json.dumps(payload, ensure_ascii=False, indent=2))
        fh.write(";\n")

    played = sum(1 for m in matches if m["result"])
    summary = {
        "league": cfg["leagueName"],
        "season": meta["season"],
        "matchday": meta["matchdayLabel"],
        "matches": len(matches),
        "played": played,
        "upcoming": len(matches) - played,
        "output": output_js,
    }
    log.info("Wrote %s  [%s]", output_js, "snapshot md{0}".format(matchday) if matchday else "live")
    log.info("%s %s -- %s: %d matches (%d with results, %d upcoming)",
             summary["league"], summary["season"], summary["matchday"],
             summary["matches"], summary["played"], summary["upcoming"])
    return summary


def main():
    parser = argparse.ArgumentParser(description="Generate website/data.js from the model's CSV exports.")
    parser.add_argument("--league", default="bundesliga",
                        help="league config name in website/config/leagues/ (default: bundesliga)")
    parser.add_argument("--matchday", type=int, default=None,
                        help="rebuild from a saved snapshot in website/matchdays/ instead of the live model output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build(league=args.league, matchday=args.matchday)


if __name__ == "__main__":
    main()
