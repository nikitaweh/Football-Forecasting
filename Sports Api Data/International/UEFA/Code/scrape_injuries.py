#!/usr/bin/env python3
"""Standalone UEFA injuries scraper.

Scrapes ONLY injuries for the UEFA branch (no fixtures, lineups, match- or
player-statistics). Runs the api-football injuries pull and the CSV conversion
once, then exits -- no blocking scheduler.

    python "Sports Api Data/International/UEFA/Code/scrape_injuries.py"
"""
import importlib.util
import re
from pathlib import Path

BRANCH_DIR = Path(__file__).resolve().parents[1]  # .../International/UEFA

INJURIES_UNFILTERED = BRANCH_DIR / "Unfiltered" / "Code" / "injuries_international.py"
INJURIES_FILTERED = BRANCH_DIR / "Filtered" / "Code" / "injuries_international.py"


def _load_module(path):
    module_name = "uefa_" + re.sub(r"[^a-zA-Z0-9_]", "_", path.stem + "_" + path.parent.parent.name)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Kann Modul nicht laden: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    print("UEFA Injuries-Scraper (nur Injuries, keine weiteren Statistiken)")
    injuries_u = _load_module(INJURIES_UNFILTERED)
    injuries_f = _load_module(INJURIES_FILTERED)

    print("[1/2] API Pull: Injuries (UEFA)")
    injuries_u.fetch_injuries(full_load=False)

    print("[2/2] Filter: Injuries -> CSV (UEFA)")
    injuries_f.convert_injuries_to_csv()

    print("Fertig.")


if __name__ == "__main__":
    main()
