# -*- coding: utf-8 -*-
"""
build_data.py  --  Generates website/data.js from the model's CSV exports.

Run this after each model run to refresh the website:

    python website/build_data.py

It joins:
  - future_outcome_table.csv      (the AI predictions)
  - match_results_references.csv  (the actual results, when available)

Matches without a known result are still written out and the website
renders them as "upcoming" automatically.
"""

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TESTRUNS = os.path.join(ROOT, "Sports Api Data", "Testruns")

# --- Matchday selection ----------------------------------------------------
# Switch this ONE line to change which matchday the website shows:
#   "live" -> the model's current output (the newest matchday it produced)
#   "md33" -> the saved Matchday 33 snapshot in website/matchdays/
SOURCE = "md33"

SOURCES = {
    "live": {
        "matchday": 34,
        "matchdayDate": "2026-05-16",
        "predictions": os.path.join(TESTRUNS, "Datacollection future", "future_outcome_table.csv"),
        "results": os.path.join(TESTRUNS, "Datacollection reference", "match_results_references.csv"),
    },
    "md33": {
        "matchday": 33,
        "matchdayDate": "2026-05-09",
        "predictions": os.path.join(HERE, "matchdays", "md33_predictions.csv"),
        "results": os.path.join(HERE, "matchdays", "md33_results.csv"),
    },
}

ACTIVE = SOURCES[SOURCE]
PREDICTIONS_CSV = ACTIVE["predictions"]
RESULTS_CSV = ACTIVE["results"]
OUTPUT_JS = os.path.join(HERE, "data.js")

# --- Static reference data -------------------------------------------------

META = {
    "league": "Bundesliga",
    "season": "2025/26",
    "matchday": ACTIVE["matchday"],
    "matchdayDate": ACTIVE["matchdayDate"],
    "model": "Gradient-boosted match-stat simulation",
    "configuration": "",          # derived from the prediction file in main()
    "signalsPerMatch": 34,
    "generated": "2026-05-23",
}

# Official short code, brand colour and API-Football team id per club.
# Logos live in website/logos/<id>.png (downloaded from media.api-sports.io).
TEAMS = {
    "Bayern München":           {"id": 157, "abbr": "FCB", "color": "#DC052D"},
    "1. FC Köln":               {"id": 192, "abbr": "KOE", "color": "#E2001A"},
    "SC Freiburg":              {"id": 160, "abbr": "SCF", "color": "#E2001A"},
    "RB Leipzig":               {"id": 173, "abbr": "RBL", "color": "#DD0741"},
    "Werder Bremen":            {"id": 162, "abbr": "SVW", "color": "#1D9053"},
    "Borussia Dortmund":        {"id": 165, "abbr": "BVB", "color": "#F4C400"},
    "Borussia Mönchengladbach": {"id": 163, "abbr": "BMG", "color": "#00A94F"},
    "1899 Hoffenheim":          {"id": 167, "abbr": "TSG", "color": "#1C63B7"},
    "Bayer Leverkusen":         {"id": 168, "abbr": "B04", "color": "#E32219"},
    "Hamburger SV":             {"id": 175, "abbr": "HSV", "color": "#1F5BB5"},
    "Eintracht Frankfurt":      {"id": 169, "abbr": "SGE", "color": "#E1000F"},
    "VfB Stuttgart":            {"id": 172, "abbr": "VFB", "color": "#D8000C"},
    "1. FC Heidenheim":         {"id": 180, "abbr": "FCH", "color": "#1B4F9C"},
    "FSV Mainz 05":             {"id": 164, "abbr": "M05", "color": "#C3141E"},
    "Union Berlin":             {"id": 182, "abbr": "FCU", "color": "#EB1923"},
    "FC Augsburg":              {"id": 170, "abbr": "FCA", "color": "#BA3733"},
    "FC St. Pauli":             {"id": 186, "abbr": "STP", "color": "#A07A53"},
    "VfL Wolfsburg":            {"id": 161, "abbr": "WOB", "color": "#65B32E"},
}

for _name, _meta in TEAMS.items():
    _meta["logo"] = "logos/{0}.png".format(_meta["id"])

RESULT_TO_OUTCOME = {"H": "HomeWin", "D": "Draw", "A": "AwayWin"}


def num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_results():
    """MatchID -> {homeGoals, awayGoals, outcome}"""
    results = {}
    if not os.path.exists(RESULTS_CSV):
        return results
    with open(RESULTS_CSV, "r", encoding="utf-8-sig", newline="") as fh:
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


def load_matches(results):
    """Returns (matches, configuration_label)."""
    matches = []
    config = ""
    with open(PREDICTIONS_CSV, "r", encoding="utf-8-sig", newline="") as fh:
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


def main():
    results = load_results()
    matches, config = load_matches(results)
    if config:
        META["configuration"] = config

    payload = {"meta": META, "teams": TEAMS, "matches": matches}
    body = json.dumps(payload, ensure_ascii=False, indent=2)

    with open(OUTPUT_JS, "w", encoding="utf-8") as fh:
        fh.write("/* data.js -- auto-generated by build_data.py. Do not edit by hand. */\n")
        fh.write("window.ORAKEL_DATA = ")
        fh.write(body)
        fh.write(";\n")

    played = sum(1 for m in matches if m["result"])
    print("Wrote {0}  [source: {1}]".format(OUTPUT_JS, SOURCE))
    print("  Matchday {0}  --  {1} matches ({2} with results, {3} upcoming)".format(
        META["matchday"], len(matches), played, len(matches) - played))


if __name__ == "__main__":
    main()
