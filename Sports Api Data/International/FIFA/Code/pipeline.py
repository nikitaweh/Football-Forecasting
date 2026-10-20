import argparse
import importlib.util
import re
import time
from pathlib import Path


# FIFA branch pipeline: this file lives at International/FIFA/Code/, one level deeper
# than the old International/Code/, so the project root is now parents[4].
PROJECT_ROOT = Path(__file__).resolve().parents[4]

PATHS = {
    "fixtures_unfiltered": r"Sports Api Data/International/FIFA/Unfiltered/Code/Fixtures International.py",
    "stammdaten_filtered": r"Sports Api Data/International/FIFA/Filtered/Code/Stammdaten_international.py",
    "injuries_unfiltered": r"Sports Api Data/International/FIFA/Unfiltered/Code/injuries_international.py",
    "injuries_filtered": r"Sports Api Data/International/FIFA/Filtered/Code/injuries_international.py",
    "lineups_unfiltered": r"Sports Api Data/International/FIFA/Unfiltered/Code/lineups_international.py",
    "lineups_filtered": r"Sports Api Data/International/FIFA/Filtered/Code/lineups_international.py",
    "matchstats_unfiltered": r"Sports Api Data/International/FIFA/Unfiltered/Code/match_statistics_international.py",
    "matchstats_filtered": r"Sports Api Data/International/FIFA/Filtered/Code/match_statistics_international.py",
    "playerstats_unfiltered": r"Sports Api Data/International/FIFA/Unfiltered/Code/player_statistics_international.py",
    "playerstats_filtered": r"Sports Api Data/International/FIFA/Filtered/Code/playerstatistics_international.py",
}

MODULE_CACHE = {}


def _load_module(path_key):
    if path_key in MODULE_CACHE:
        return MODULE_CACHE[path_key]

    rel = PATHS[path_key]
    abs_path = PROJECT_ROOT / rel
    if not abs_path.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {abs_path}")

    module_name = "international_" + re.sub(r"[^a-zA-Z0-9_]", "_", path_key)
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


def run_fixtures_pipeline(fixtures_mode):
    fixtures = _load_module("fixtures_unfiltered")
    stammdaten = _load_module("stammdaten_filtered")

    if fixtures_mode == "full":
        _run_step("API Pull: Fixtures International (full history)", fixtures.fetch_full_fixtures)
    else:
        _run_step("API Pull: Fixtures International (incremental)", fixtures.fetch_new_fixtures)

    _run_step("Filter: Stammdaten International -> CSV", stammdaten.convert_stammdaten_to_csv)


def run_injuries_pipeline():
    injuries_u = _load_module("injuries_unfiltered")
    injuries_f = _load_module("injuries_filtered")

    _run_step("API Pull: Injuries International", lambda: injuries_u.fetch_injuries(full_load=False))
    _run_step("Filter: Injuries International -> CSV", injuries_f.convert_injuries_to_csv)


def run_lineups_pipeline():
    lineups_u = _load_module("lineups_unfiltered")
    lineups_f = _load_module("lineups_filtered")

    _run_step("API Pull: Lineups International", lambda: lineups_u.collect_lineups(full_load=False))
    _run_step("Filter: Lineups International -> CSV", lineups_f.convert_lineups_to_csv)


def run_matchstats_pipeline():
    stats_u = _load_module("matchstats_unfiltered")
    stats_f = _load_module("matchstats_filtered")

    _run_step("API Pull: Match Statistics International", lambda: stats_u.collect_match_statistics(full_load=False))
    _run_step("Filter: Match Statistics International -> CSV", stats_f.convert_match_statistics_to_csv)


def run_playerstats_pipeline():
    players_u = _load_module("playerstats_unfiltered")
    players_f = _load_module("playerstats_filtered")

    _run_step("API Pull: Player Statistics International", players_u.collect_player_stats)
    _run_step("Filter: Player Statistics International -> CSV", players_f.convert_player_statistics_to_csv)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "FIFA-Pipeline (Weltmeisterschaft inkl. Qualifikation aller Konfoederationen): "
            "API-Abruf (Unfiltered) + direkte Filterausgabe (Filtered)"
        )
    )
    parser.add_argument(
        "--fixtures-mode",
        choices=["new", "full"],
        default="new",
        help="Fixtures-Abrufmodus: inkrementell (new) oder kompletter Verlauf ab 2017 (full).",
    )
    parser.add_argument(
        "--steps",
        nargs="+",
        choices=["fixtures", "injuries", "lineups", "matchstats", "playerstats"],
        default=["fixtures", "injuries", "lineups", "matchstats", "playerstats"],
        help="Auszufuehrende Pipeline-Bloecke in Reihenfolge.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Bei Fehlern mit dem naechsten Block weiterlaufen.",
    )
    args = parser.parse_args()

    runners = {
        "fixtures": lambda: run_fixtures_pipeline(fixtures_mode=args.fixtures_mode),
        "injuries": run_injuries_pipeline,
        "lineups": run_lineups_pipeline,
        "matchstats": run_matchstats_pipeline,
        "playerstats": run_playerstats_pipeline,
    }

    print("FIFA Pipeline gestartet")
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
