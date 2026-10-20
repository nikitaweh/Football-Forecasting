import json
import csv
import os
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from pathlib import Path

# Repo root: KI_PROJECT_ROOT if set (VPS), else derived from this file's location.
PROJECT_ROOT = Path(os.environ.get("KI_PROJECT_ROOT") or Path(__file__).resolve().parents[4]).as_posix()


# ----------------------------
# Pfade zu den Input- und Output-Dateien
# ----------------------------
fixtures_file = rf"{PROJECT_ROOT}/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"
stats_file    = rf"{PROJECT_ROOT}/Sports Api Data/Bundesliga/Unfiltered/Datacollection/match_statistics_league_78.json"
output_csv    = rf"{PROJECT_ROOT}/Sports Api Data/Bundesliga/Filtered/Datacollection/match_statistics_filtered_78.csv"

# ----------------------------
# Hilfsfunktionen
# ----------------------------
def parse_int(value):
    try:
        return int(value) if value is not None else None
    except:
        return None

def parse_float(value):
    try:
        return float(value) if value is not None else None
    except:
        return None

def parse_percentage(value):
    if isinstance(value, str) and '%' in value:
        try:
            return int(value.replace('%','').strip())
        except:
            return None
    return None

def get_stat_value(stat_list, stat_type):
    for item in stat_list:
        if item.get("type") == stat_type:
            return item.get("value")
    return None

# ----------------------------
# Conversion-Funktion
# ----------------------------
def convert_match_statistics_to_csv():
    now = datetime.utcnow().timestamp()

    # 1) Fixtures einlesen und nur gespeilte Spiele übernehmen
    try:
        with open(fixtures_file, "r", encoding="utf-8") as f:
            fixtures_data = json.load(f)
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Fehler beim Laden der Fixtures: {e}")
        return

    fixtures_dict = {}
    for fx in fixtures_data.get("response", []):
        fixture = fx.get("fixture", {})
        if fixture.get("status", {}).get("short") != "FT":
            continue
        fid = fixture.get("id")
        teams = fx.get("teams", {})
        goals = fx.get("goals", {})
        if fid is not None:
            fixtures_dict[fid] = {
                "home_id": teams.get("home", {}).get("id"),
                "away_id": teams.get("away", {}).get("id"),
                "home_goals": goals.get("home"),
                "away_goals": goals.get("away")
            }

    # 2) Statistiken einlesen
    try:
        with open(stats_file, "r", encoding="utf-8") as f:
            stats_data = json.load(f)
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Fehler beim Laden der Statistiken: {e}")
        return

    stats_dict = {}
    for item in stats_data.get("response", []):
        fid = item.get("fixture_id")
        if fid not in fixtures_dict:
            continue
        home_id = fixtures_dict[fid]["home_id"]
        away_id = fixtures_dict[fid]["away_id"]
        stats_dict[fid] = {"home": {}, "away": {}}
        for team_stats in item.get("response", []):
            team_id = team_stats.get("team", {}).get("id")
            stat_items = team_stats.get("statistics", [])
            side = None
            if team_id == home_id:
                side = "home"
            elif team_id == away_id:
                side = "away"
            if side is None:
                continue

            so_target = parse_int(get_stat_value(stat_items, "Shots on Goal"))
            so_off = parse_int(get_stat_value(stat_items, "Shots off Goal"))
            total_shots = None
            if so_target is not None and so_off is not None:
                total_shots = so_target + so_off
            elif so_target is not None:
                total_shots = so_target
            elif so_off is not None:
                total_shots = so_off

            possession = parse_percentage(get_stat_value(stat_items, "Ball Possession"))
            fouls = parse_int(get_stat_value(stat_items, "Fouls"))
            yellow = parse_int(get_stat_value(stat_items, "Yellow Cards"))
            red = parse_int(get_stat_value(stat_items, "Red Cards"))
            offsides = parse_int(get_stat_value(stat_items, "Offsides"))
            corners = parse_int(get_stat_value(stat_items, "Corner Kicks"))
            passes = parse_int(get_stat_value(stat_items, "Total passes"))
            pass_acc = parse_percentage(get_stat_value(stat_items, "Passes %"))
            xg = parse_float(get_stat_value(stat_items, "expected_goals"))

            stats_dict[fid][side] = {
                "shots_on_target": so_target,
                "shots": total_shots,
                "possession": possession,
                "fouls": fouls,
                "yellow": yellow,
                "red": red,
                "offsides": offsides,
                "corners": corners,
                "passes": passes,
                "pass_accuracy": pass_acc,
                "xg": xg
            }

    # 3) CSV schreiben
    fieldnames = [
        "MatchID", "Home Goals", "Away Goals",
        "Home Possession", "Away Possession",
        "Home Shots", "Away Shots",
        "Home Shots on Target", "Away Shots on Target",
        "Home Passes", "Away Passes",
        "Home Pass Accuracy", "Away Pass Accuracy",
        "Home Fouls", "Away Fouls",
        "Home Yellow Card", "Away Yellow Card",
        "Home Red Card", "Away Red Card",
        "Home Offsides", "Away Offsides",
        "Home Corners", "Away Corners",
        "Expected Goals (xG) Home", "Expected Goals (xG) Away"
    ]
    rows = []
    for fid, fx in fixtures_dict.items():
        if fid not in stats_dict:
            continue
        home = stats_dict[fid]["home"]
        away = stats_dict[fid]["away"]
        rows.append({
            "MatchID": fid,
            "Home Goals": fx["home_goals"], "Away Goals": fx["away_goals"],
            "Home Possession": home.get("possession"), "Away Possession": away.get("possession"),
            "Home Shots": home.get("shots"), "Away Shots": away.get("shots"),
            "Home Shots on Target": home.get("shots_on_target"), "Away Shots on Target": away.get("shots_on_target"),
            "Home Passes": home.get("passes"), "Away Passes": away.get("passes"),
            "Home Pass Accuracy": home.get("pass_accuracy"), "Away Pass Accuracy": away.get("pass_accuracy"),
            "Home Fouls": home.get("fouls"), "Away Fouls": away.get("fouls"),
            "Home Yellow Card": home.get("yellow"), "Away Yellow Card": away.get("yellow"),
            "Home Red Card": home.get("red"), "Away Red Card": away.get("red"),
            "Home Offsides": home.get("offsides"), "Away Offsides": away.get("offsides"),
            "Home Corners": home.get("corners"), "Away Corners": away.get("corners"),
            "Expected Goals (xG) Home": home.get("xg"), "Expected Goals (xG) Away": away.get("xg")
        })
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Match-Statistiken als CSV gespeichert: {output_csv}")

if __name__ == "__main__":
    # Sofortige Ausführung vor Scheduler
    convert_match_statistics_to_csv()

    # Scheduler starten
    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(
        convert_match_statistics_to_csv,
        trigger=CronTrigger(day_of_week="sat,sun,mon", hour="3", minute="0")
    )
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scheduler gestartet – läuft samstags, sonntags & montags um 03:00 Uhr (Europe/Berlin)")
    sched.start()