import argparse
import importlib.util
import re
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CITY_STEP_TIMEOUT_SECONDS_DEFAULT = 300

PATHS = {
    "league_unfiltered": r"Sports Api Data\Bundesliga\Unfiltered\Code\League General Info.py",
    "teams_unfiltered": r"Sports Api Data\Bundesliga\Unfiltered\Code\Team General Info.py",
    "teams_filtered": r"Sports Api Data\Bundesliga\Filtered\Code\teams general info.py",
    "city_coords_filtered": r"Sports Api Data\Bundesliga\Filtered\Code\City Coordinates.py",
    "fixtures_unfiltered": r"Sports Api Data\Bundesliga\Unfiltered\Code\Fixtures Bundesliga.py",
    "stammdaten_filtered": r"Sports Api Data\Bundesliga\Filtered\Code\Stammdaten_78.py",
    "injuries_unfiltered": r"Sports Api Data\Bundesliga\Unfiltered\Code\injuries_78.py",
    "injuries_filtered": r"Sports Api Data\Bundesliga\Filtered\Code\injuries_78.py",
    "lineups_unfiltered": r"Sports Api Data\Bundesliga\Unfiltered\Code\lineups_78.py",
    "lineups_filtered": r"Sports Api Data\Bundesliga\Filtered\Code\line ups_78.py",
    "matchstats_unfiltered": r"Sports Api Data\Bundesliga\Unfiltered\Code\match_statistics._78.py",
    "matchstats_filtered": r"Sports Api Data\Bundesliga\Filtered\Code\match statistics.py",
    "playerstats_unfiltered": r"Sports Api Data\Bundesliga\Unfiltered\Code\player individuel statistic_78.py",
    "playerstats_filtered": r"Sports Api Data\Bundesliga\Filtered\Code\playerstatistics.py",
    "weather_future_filtered": r"Sports Api Data\Bundesliga\Filtered\Code\future_weather_hourly_78.py",
    "weather_historic_filtered": r"Sports Api Data\Bundesliga\Filtered\Code\historic_weather_data_78.py",
}

MODULE_CACHE = {}


def _load_module(path_key):
    if path_key in MODULE_CACHE:
        return MODULE_CACHE[path_key]

    rel = PATHS[path_key]
    abs_path = PROJECT_ROOT / rel
    if not abs_path.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {abs_path}")

    module_name = "bundesliga_" + re.sub(r"[^a-zA-Z0-9_]", "_", path_key)
    spec = importlib.util.spec_from_file_location(module_name, abs_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Kann Modul nicht laden: {abs_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    MODULE_CACHE[path_key] = module
    return module


def _run_step(step_name, fn):
    print(f"[START] {step_name}")
    t0 = time.time()
    fn()
    dt = time.time() - t0
    print(f"[DONE]  {step_name} ({dt:.1f}s)")


def _run_city_coordinates_script(timeout_seconds=CITY_STEP_TIMEOUT_SECONDS_DEFAULT, strict=False):
    script_path = PROJECT_ROOT / PATHS["city_coords_filtered"]
    cmd = [sys.executable, str(script_path)]
    if strict:
        cmd.append("--strict")

    try:
        subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"City-Coordinates Schritt hat Timeout nach {timeout_seconds}s erreicht. "
            "Nutze --without-city oder erhoehe --city-timeout-seconds."
        ) from exc


def run_teams_pipeline(include_city=True, city_timeout_seconds=CITY_STEP_TIMEOUT_SECONDS_DEFAULT, city_strict=False):
    league = _load_module("league_unfiltered")
    teams = _load_module("teams_unfiltered")
    teams_csv = _load_module("teams_filtered")

    _run_step("API Pull: League General Info", league.fetch_bundesliga)
    _run_step("API Pull: Team General Info", teams.fetch_all_teams)
    _run_step("Filter: teams general info -> CSV", teams_csv.convert_teams_to_csv)

    if include_city:
        _run_step(
            "Filter: City Coordinates -> CSV",
            lambda: _run_city_coordinates_script(
                timeout_seconds=city_timeout_seconds,
                strict=city_strict,
            ),
        )


def run_fixtures_pipeline(fixtures_mode):
    fixtures = _load_module("fixtures_unfiltered")
    stammdaten = _load_module("stammdaten_filtered")

    if fixtures_mode == "full":
        _run_step("API Pull: Fixtures (full history)", fixtures.fetch_full_fixtures)
    else:
        _run_step("API Pull: Fixtures (incremental)", fixtures.fetch_new_fixtures)

    _run_step("Filter: Stammdaten -> CSV", stammdaten.convert_stammdaten_to_csv)


def run_injuries_pipeline():
    injuries_u = _load_module("injuries_unfiltered")
    injuries_f = _load_module("injuries_filtered")

    _run_step("API Pull: Injuries", lambda: injuries_u.fetch_injuries(full_load=False))
    _run_step("Filter: Injuries -> CSV", injuries_f.convert_injuries_to_csv)


def run_lineups_pipeline():
    lineups_u = _load_module("lineups_unfiltered")
    lineups_f = _load_module("lineups_filtered")

    _run_step("API Pull: Lineups", lambda: lineups_u.collect_lineups(full_load=False))
    _run_step("Filter: Lineups -> CSV", lineups_f.convert_lineups_to_csv)


def run_matchstats_pipeline():
    stats_u = _load_module("matchstats_unfiltered")
    stats_f = _load_module("matchstats_filtered")

    _run_step("API Pull: Match Statistics", lambda: stats_u.collect_match_statistics(full_load=False))
    _run_step("Filter: Match Statistics -> CSV", stats_f.convert_match_statistics_to_csv)


def run_playerstats_pipeline():
    players_u = _load_module("playerstats_unfiltered")
    players_f = _load_module("playerstats_filtered")

    _run_step("API Pull: Player Statistics", players_u.collect_player_stats)
    _run_step("Filter: Player Statistics -> CSV", players_f.convert_player_statistics_to_csv)


def run_weather_pipeline():
    weather_hist = _load_module("weather_historic_filtered")
    weather_future = _load_module("weather_future_filtered")

    _run_step("Filter/API: Historic Weather -> CSV", lambda: weather_hist.main(overwrite=False))
    _run_step("Filter/API: Future Weather -> CSV", weather_future.main)


def main():
    parser = argparse.ArgumentParser(
        description="Kombinierte Bundesliga-Pipeline: API-Abruf (Unfiltered) + direkte Filterausgabe (Filtered)"
    )
    parser.add_argument(
        "--fixtures-mode",
        choices=["new", "full"],
        default="new",
        help="Fixtures-Abrufmodus: inkrementell (new) oder kompletter Verlauf (full).",
    )
    parser.add_argument(
        "--steps",
        nargs="+",
        choices=["teams", "fixtures", "injuries", "lineups", "matchstats", "playerstats", "weather"],
        default=["teams", "fixtures", "injuries", "lineups", "matchstats", "playerstats"],
        help="Auszufuehrende Pipeline-Bloecke in Reihenfolge.",
    )
    parser.add_argument(
        "--without-city",
        action="store_true",
        help="City-Coordinates-Schritt im Team-Block ueberspringen.",
    )
    parser.add_argument(
        "--city-timeout-seconds",
        type=int,
        default=CITY_STEP_TIMEOUT_SECONDS_DEFAULT,
        help="Maximale Laufzeit fuer City-Coordinates-Schritt.",
    )
    parser.add_argument(
        "--city-strict",
        action="store_true",
        help="Pipeline bricht ab, wenn City-Coordinates nicht alle Teams aufloesen kann.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Bei Fehlern mit dem naechsten Block weiterlaufen.",
    )
    args = parser.parse_args()

    runners = {
        "teams": lambda: run_teams_pipeline(
            include_city=not args.without_city,
            city_timeout_seconds=max(1, args.city_timeout_seconds),
            city_strict=args.city_strict,
        ),
        "fixtures": lambda: run_fixtures_pipeline(fixtures_mode=args.fixtures_mode),
        "injuries": run_injuries_pipeline,
        "lineups": run_lineups_pipeline,
        "matchstats": run_matchstats_pipeline,
        "playerstats": run_playerstats_pipeline,
        "weather": run_weather_pipeline,
    }

    print("Bundesliga Combined Pipeline gestartet")
    print(f"Projekt: {PROJECT_ROOT}")
    print(f"Schritte: {args.steps}")
    print(f"Fixtures-Modus: {args.fixtures_mode}")

    errors = []
    for step in args.steps:
        try:
            runners[step]()
        except KeyboardInterrupt:
            print("\n[ABORT] Pipeline manuell unterbrochen (KeyboardInterrupt).")
            raise SystemExit(130)
        except Exception as exc:
            msg = f"[ERROR] Schritt '{step}' fehlgeschlagen: {exc}"
            print(msg)
            errors.append(msg)
            if not args.continue_on_error:
                break

    if errors:
        print("\nPipeline mit Fehlern beendet.")
        for err in errors:
            print(err)
        raise SystemExit(1)

    print("\nPipeline erfolgreich abgeschlossen.")


if __name__ == "__main__":
    main()
