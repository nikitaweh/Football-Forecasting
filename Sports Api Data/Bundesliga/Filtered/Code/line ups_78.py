import csv
import json
import os
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------
# Pfade anpassen
# ---------------------------
INPUT_JSON = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/lineups_league_78.json"
FIXTURES_JSON = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Unfiltered/Datacollection/fixtures_league_78.json"
OUTPUT_CSV = r"C:/AI Projekt/KI-Projekt/Sports Api Data/Bundesliga/Filtered/Datacollection/lineups_league_78.csv"

# ---------------------------
# Teamnamen-Overrides
# ---------------------------
team_name_overrides = {
    "Bayern Munich": "Bayern M\u00fcnchen",
    "Hertha Berlin": "Hertha BSC",
    "Borussia Monchengladbach": "Borussia M\u00f6nchengladbach",
    "FC Nurnberg": "1. FC N\u00fcrnberg",
    "Fortuna Dusseldorf": "Fortuna D\u00fcsseldorf",
    "FC Heidenheim": "1. FC Heidenheim",
    "Vfl Bochum": "VfL Bochum",
    "SpVgg Greuther Furth": "SpVgg Greuther F\u00fcrth",
}


def load_fixture_team_map():
    try:
        with open(FIXTURES_JSON, "r", encoding="utf-8") as f:
            fixtures = json.load(f).get("response", [])
    except Exception as exc:
        print(
            f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Hinweis: Fixtures konnten nicht geladen werden ({exc}). "
            "Home/Away wird per Index zugewiesen."
        )
        return {}

    fixture_team_map = {}
    for fx in fixtures:
        if not isinstance(fx, dict):
            continue

        fixture_id = fx.get("fixture", {}).get("id")
        teams = fx.get("teams", {})
        home_id = teams.get("home", {}).get("id")
        away_id = teams.get("away", {}).get("id")

        if fixture_id is None or home_id is None or away_id is None:
            continue

        fixture_team_map[str(fixture_id)] = {"home": home_id, "away": away_id}

    return fixture_team_map


# ---------------------------
# Funktion: JSON zu CSV konvertieren
# ---------------------------
def convert_lineups_to_csv():
    try:
        with open(INPUT_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Fehler beim Laden der JSON: {exc}")
        return

    rows = []
    fixture_team_map = load_fixture_team_map()

    outer_list = data.get("response", [])
    if not isinstance(outer_list, list):
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Unerwartetes Format: 'response' ist keine Liste.")
        return

    for outer in outer_list:
        if not isinstance(outer, dict):
            continue

        parameters = outer.get("parameters", {})
        if isinstance(parameters, dict):
            fixture_from_parameters = parameters.get("fixture")
        elif isinstance(parameters, list):
            fixture_from_parameters = next(
                (
                    p.get("fixture")
                    for p in parameters
                    if isinstance(p, dict) and p.get("fixture") is not None
                ),
                None,
            )
        else:
            fixture_from_parameters = None

        match_id = fixture_from_parameters or outer.get("MatchID") or outer.get("fixture_id")
        if match_id is None:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Match ohne ID gefunden, uebersprungen.")
            continue

        match_key = str(match_id)
        lineups = outer.get("response", [])

        if not isinstance(lineups, list) or len(lineups) < 2:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Weniger als zwei Teams fuer Match {match_id}, uebersprungen.")
            continue

        expected = fixture_team_map.get(match_key, {})
        home_id_expected = expected.get("home")
        away_id_expected = expected.get("away")

        home_entry = next(
            (
                e
                for e in lineups
                if isinstance(e, dict) and e.get("team", {}).get("id") == home_id_expected
            ),
            None,
        )
        away_entry = next(
            (
                e
                for e in lineups
                if isinstance(e, dict) and e.get("team", {}).get("id") == away_id_expected
            ),
            None,
        )

        if home_entry is None or away_entry is None:
            home_entry = lineups[0]
            away_entry = lineups[1]

        def add_player_rows(entry, is_start, side):
            if not isinstance(entry, dict):
                return []

            team = entry.get("team", {})
            coach = entry.get("coach", {})
            formation = entry.get("formation", "")

            if not isinstance(team, dict) or "id" not in team:
                return []

            team_id = team.get("id")
            raw_name = team.get("name", "")
            team_name = team_name_overrides.get(raw_name, raw_name)

            coach_id = coach.get("id", "") if isinstance(coach, dict) else ""
            coach_name = coach.get("name", "") if isinstance(coach, dict) else ""

            home_id = team_id if side == "home" else ""
            away_id = team_id if side == "away" else ""

            out = []
            players = entry.get("startXI", []) if is_start else entry.get("substitutes", [])
            if not isinstance(players, list):
                return out

            for p in players:
                if not isinstance(p, dict):
                    continue

                pl = p.get("player", {})
                if not isinstance(pl, dict) or "id" not in pl or "name" not in pl:
                    continue

                out.append(
                    {
                        "MatchID": match_id,
                        "Home Team ID": home_id,
                        "Away Team ID": away_id,
                        "Team Name": team_name,
                        "Coach ID": coach_id,
                        "Coach Name": coach_name,
                        "Formation": formation,
                        "Player ID": pl["id"],
                        "Player Name": pl["name"],
                        "Pos": pl.get("pos", p.get("pos", "")),
                        "Grid": pl.get("grid", p.get("grid", "")),
                        "StartXI": is_start,
                    }
                )
            return out

        rows += add_player_rows(home_entry, True, "home")
        rows += add_player_rows(away_entry, True, "away")
        rows += add_player_rows(home_entry, False, "home")
        rows += add_player_rows(away_entry, False, "away")

    if rows:
        os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "MatchID",
                "Home Team ID",
                "Away Team ID",
                "Team Name",
                "Coach ID",
                "Coach Name",
                "Formation",
                "Player ID",
                "Player Name",
                "Pos",
                "Grid",
                "StartXI",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] CSV-Datei erstellt: {OUTPUT_CSV}")
    else:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Keine Daten extrahiert.")


if __name__ == "__main__":
    convert_lineups_to_csv()

    sched = BlockingScheduler(timezone="Europe/Berlin")
    sched.add_job(
        convert_lineups_to_csv,
        trigger=CronTrigger(day_of_week="sat,sun,mon", hour="3", minute="0"),
    )
    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scheduler gestartet - "
        "laeuft samstags, sonntags & montags um 03:00 Uhr (Europe/Berlin)"
    )
    sched.start()
