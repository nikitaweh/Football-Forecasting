# -*- coding: utf-8 -*-
"""
build_data_international.py  --  Generates website/data.international.js
from the World Cup 2026 backtesting snapshot.

Unlike build_data.py (Bundesliga), this reads the international model's
snapshot CSV directly -- there is no separate results file yet and no
Stammdaten join is needed since the Stage is already a column:

    Sports Api Data/International/FIFA/Backtesting/worldcup_2026/wc_predictions_asof_*.csv

Run manually whenever a newer wc_predictions_asof_*.csv snapshot appears
(picks the most recent by filename date, no scheduled refresh yet):

    python website/build_data_international.py
"""

import csv
import glob
import logging
import os
from collections import Counter
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE_GLOB = os.path.join(
    ROOT, "Sports Api Data", "International", "FIFA", "Backtesting", "worldcup_2026",
    "wc_predictions_asof_*.csv")
OUTPUT_JS = os.path.join(HERE, "data.international.js")

log = logging.getLogger("orakel.build_international")

RESULT_TO_OUTCOME = {"H": "HomeWin", "D": "Draw", "A": "AwayWin"}
SIGNALS_PER_MATCH = 16  # FEATURE_COLUMNS in AI_international_competitive_prediction.py

# National-team badge colours (no logo files yet -- app.js falls back to a
# coloured abbreviation crest when a team has no "logo" key).
TEAMS = {
    "Brazil":      {"abbr": "BRA", "color": "#009C3B"},
    "Norway":      {"abbr": "NOR", "color": "#EF2B2D"},
    "Portugal":    {"abbr": "POR", "color": "#D4213D"},
    "Spain":       {"abbr": "ESP", "color": "#C60B1E"},
    "Mexico":      {"abbr": "MEX", "color": "#006847"},
    "England":     {"abbr": "ENG", "color": "#1E3A8A"},
    "Argentina":   {"abbr": "ARG", "color": "#75AADB"},
    "Egypt":       {"abbr": "EGY", "color": "#C09A5B"},
    "USA":         {"abbr": "USA", "color": "#0A3161"},
    "Belgium":     {"abbr": "BEL", "color": "#ED2939"},
    "Switzerland": {"abbr": "SUI", "color": "#D52B1E"},
    "Colombia":    {"abbr": "COL", "color": "#FCD116"},
    "France":      {"abbr": "FRA", "color": "#002395"},
    "Morocco":     {"abbr": "MAR", "color": "#C1272D"},
}


def num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def latest_source():
    candidates = sorted(glob.glob(SOURCE_GLOB))
    if not candidates:
        raise SystemExit("No wc_predictions_asof_*.csv snapshot found under {0}".format(SOURCE_GLOB))
    return candidates[-1]


def load_matches(path):
    matches = []
    engines, outcomes, stages = Counter(), Counter(), Counter()
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            mid = (row.get("MatchID") or "").strip()
            if not mid:
                continue
            score = (row.get("PredictedScore") or "0:0").split(":")
            home_goals, away_goals = int(num(score[0])), int(num(score[1]))
            win_p, draw_p, lose_p = num(row.get("WinProb")), num(row.get("DrawProb")), num(row.get("LoseProb"))

            result = None
            if (row.get("ActualHomeGoals") or "").strip() and (row.get("ActualAwayGoals") or "").strip():
                result = {
                    "homeGoals": int(num(row.get("ActualHomeGoals"))),
                    "awayGoals": int(num(row.get("ActualAwayGoals"))),
                    "outcome": RESULT_TO_OUTCOME.get((row.get("ActualResult") or "").strip(), None),
                }

            matches.append({
                "id": int(mid),
                "date": (row.get("MatchDate") or "").strip(),
                "home": (row.get("HomeTeam") or "").strip(),
                "away": (row.get("AwayTeam") or "").strip(),
                "prediction": {
                    "outcome": RESULT_TO_OUTCOME.get((row.get("PredictedResult") or "").strip(), None),
                    "homeWinProb": win_p,
                    "drawProb": draw_p,
                    "awayWinProb": lose_p,
                    "confidence": max(win_p, draw_p, lose_p) / 100.0,
                    "homeGoals": home_goals,
                    "awayGoals": away_goals,
                    "scoreline": (row.get("PredictedScore") or "").strip(),
                    "xgHome": num(row.get("ExpectedHomeGoals")),
                    "xgAway": num(row.get("ExpectedAwayGoals")),
                    "goalDiff": num(row.get("PredictedGoalDiff")),
                    "label": (row.get("Stage") or "").strip(),
                },
                "result": result,
            })
            engines[(row.get("Engine") or "").strip()] += 1
            outcomes[(row.get("OutcomeMode") or "").strip()] += 1
            stages[(row.get("Stage") or "").strip()] += 1

    if not matches:
        raise SystemExit("No matches found in {0}".format(path))

    matches.sort(key=lambda m: m["prediction"]["confidence"], reverse=True)
    meta_bits = {
        "engine": engines.most_common(1)[0][0] if engines else "",
        "outcome_mode": outcomes.most_common(1)[0][0] if outcomes else "",
        "stage": stages.most_common(1)[0][0] if stages else "",
    }
    if len(stages) > 1:
        log.warning("Snapshot spans mixed stages %s -- using the most frequent for the matchday label",
                    sorted(stages))
    return matches, meta_bits


def build():
    source_csv = latest_source()
    matches, meta_bits = load_matches(source_csv)

    teams = {}
    for m in matches:
        for side in ("home", "away"):
            name = m[side]
            if name in TEAMS and name not in teams:
                teams[name] = dict(TEAMS[name])

    meta = {
        "league": "World Cup",
        "season": "2026",
        "matchday": None,
        "matchdayLabel": meta_bits["stage"] or "Knockout stage",
        "matchdayDate": min(m["date"] for m in matches),
        "model": "BART (200-tree Bayesian regression) on regulation goal difference",
        "configuration": "{0} engine, {1} calibration".format(meta_bits["engine"] or "bart",
                                                                meta_bits["outcome_mode"] or "normal"),
        "signalsPerMatch": SIGNALS_PER_MATCH,
        "generated": datetime.now().strftime("%Y-%m-%d"),
    }

    payload_matches = matches
    with open(OUTPUT_JS, "w", encoding="utf-8") as fh:
        fh.write("/* data.international.js -- auto-generated by build_data_international.py. Do not edit by hand. */\n")
        fh.write("window.ORAKEL_DATA = ")
        import json
        fh.write(json.dumps({"meta": meta, "teams": teams, "matches": payload_matches}, ensure_ascii=False, indent=2))
        fh.write(";\n")

    played = sum(1 for m in matches if m["result"])
    log.info("Wrote %s  [source: %s]", OUTPUT_JS, os.path.basename(source_csv))
    log.info("World Cup 2026 -- %s: %d matches (%d with results, %d upcoming)",
              meta["matchdayLabel"], len(matches), played, len(matches) - played)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build()
