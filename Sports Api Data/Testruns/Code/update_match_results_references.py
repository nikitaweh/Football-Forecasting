"""Update `match_results_references.csv` automatically from `match_statistics_filtered_78.csv`.

Default behavior
----------------
- Only updates MatchIDs that already exist in `match_results_references.csv`
  (so your reference set stays small).

Optional
--------
- Use `--add-missing` to also append every played MatchID found in
  `match_statistics_filtered_78.csv`.

Default paths match the ones used by `AI_match_stats_prediction.py`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


def _norm_col(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _find_col(df: pd.DataFrame, *candidates: str) -> str | None:
    normalized = {_norm_col(col): col for col in df.columns}
    for cand in candidates:
        key = _norm_col(cand)
        if key in normalized:
            return normalized[key]
    return None


def _outcome_from_goals(home_goals: float, away_goals: float) -> str:
    if home_goals > away_goals:
        return "H"
    if home_goals < away_goals:
        return "A"
    return "D"


def load_existing_reference(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["MatchID", "HomeGoals", "AwayGoals", "Result"])

    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=["MatchID", "HomeGoals", "AwayGoals", "Result"])

    required = {"MatchID", "HomeGoals", "AwayGoals"}
    if required.issubset(df.columns):
        out = df.copy()
    else:
        out = pd.read_csv(
            path,
            header=None,
            names=["MatchID", "HomeGoals", "AwayGoals", "Result"],
            usecols=[0, 1, 2, 3],
        )

    out["MatchID"] = pd.to_numeric(out["MatchID"], errors="coerce")
    out["HomeGoals"] = pd.to_numeric(out["HomeGoals"], errors="coerce")
    out["AwayGoals"] = pd.to_numeric(out["AwayGoals"], errors="coerce")
    out = out.dropna(subset=["MatchID"])

    if "Result" not in out.columns:
        out["Result"] = pd.NA

    out["Result"] = out["Result"].where(out["Result"].isin(["H", "D", "A"]), pd.NA)
    return out[["MatchID", "HomeGoals", "AwayGoals", "Result"]].copy()


def build_updates_from_match_stats(match_stats_path: Path) -> pd.DataFrame:
    df = pd.read_csv(match_stats_path)

    match_id_col = _find_col(df, "MatchID", "Match Id", "Match_ID")
    home_goals_col = _find_col(df, "HomeGoals", "Home Goals", "Home_Goals")
    away_goals_col = _find_col(df, "AwayGoals", "Away Goals", "Away_Goals")

    missing = [
        name
        for name, col in [
            ("MatchID", match_id_col),
            ("HomeGoals", home_goals_col),
            ("AwayGoals", away_goals_col),
        ]
        if col is None
    ]
    if missing:
        raise ValueError(
            f"Missing required columns in {match_stats_path.name}: {missing}. "
            f"Available columns: {list(df.columns)}"
        )

    updates = df[[match_id_col, home_goals_col, away_goals_col]].rename(
        columns={
            match_id_col: "MatchID",
            home_goals_col: "HomeGoals",
            away_goals_col: "AwayGoals",
        }
    )

    updates["MatchID"] = pd.to_numeric(updates["MatchID"], errors="coerce")
    updates["HomeGoals"] = pd.to_numeric(updates["HomeGoals"], errors="coerce")
    updates["AwayGoals"] = pd.to_numeric(updates["AwayGoals"], errors="coerce")

    updates = updates.dropna(subset=["MatchID", "HomeGoals", "AwayGoals"]).copy()
    if updates.empty:
        return pd.DataFrame(columns=["MatchID", "HomeGoals", "AwayGoals", "Result"])

    updates["HomeGoals"] = updates["HomeGoals"].astype(int)
    updates["AwayGoals"] = updates["AwayGoals"].astype(int)
    updates["Result"] = updates.apply(
        lambda r: _outcome_from_goals(r["HomeGoals"], r["AwayGoals"]), axis=1
    )
    updates = updates.drop_duplicates(subset=["MatchID"], keep="last")
    return updates[["MatchID", "HomeGoals", "AwayGoals", "Result"]].copy()


def merge_reference(existing: pd.DataFrame, updates: pd.DataFrame, *, add_missing: bool) -> pd.DataFrame:
    existing = existing.copy()
    updates = updates.copy()

    if existing.empty:
        return updates.copy() if add_missing else existing

    existing["MatchID"] = pd.to_numeric(existing["MatchID"], errors="coerce")
    updates["MatchID"] = pd.to_numeric(updates["MatchID"], errors="coerce")
    existing = existing.dropna(subset=["MatchID"])
    updates = updates.dropna(subset=["MatchID"])

    existing = existing.set_index("MatchID", drop=False)
    updates = updates.set_index("MatchID", drop=False)

    merged = existing.copy()
    intersect = merged.index.intersection(updates.index)
    if len(intersect) > 0:
        for col in ["HomeGoals", "AwayGoals", "Result"]:
            merged.loc[intersect, col] = updates.loc[intersect, col]

    if add_missing:
        new_ids = updates.index.difference(merged.index)
        if len(new_ids) > 0:
            merged = pd.concat([merged, updates.loc[new_ids]], axis=0)
            merged = merged.sort_index(ascending=True)

    merged = merged.reset_index(drop=True)
    merged["MatchID"] = pd.to_numeric(merged["MatchID"], errors="coerce")
    merged = merged.dropna(subset=["MatchID"]).copy()
    merged["MatchID"] = merged["MatchID"].astype(int)
    return merged[["MatchID", "HomeGoals", "AwayGoals", "Result"]].copy()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update match_results_references.csv from match_statistics_filtered_78.csv"
    )

    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root path. Defaults to resolving relative to this script location.",
    )
    parser.add_argument(
        "--match-stats",
        default=None,
        help="Path to match_statistics_filtered_78.csv. Defaults to Bundesliga/Filtered/Datacollection.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Path to match_results_references.csv to update. Defaults to Testruns/Datacollection reference.",
    )
    parser.add_argument(
        "--add-missing",
        action="store_true",
        help="Also append all played MatchIDs from match_statistics_filtered_78.csv.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute changes but do not write the output file.",
    )

    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    script_dir = Path(__file__).resolve().parent
    project_root = Path(args.project_root).resolve() if args.project_root else script_dir.parents[2]

    default_match_stats = (
        project_root
        / "Sports Api Data"
        / "Bundesliga"
        / "Filtered"
        / "Datacollection"
        / "match_statistics_filtered_78.csv"
    )
    default_out = (
        project_root
        / "Sports Api Data"
        / "Testruns"
        / "Datacollection reference"
        / "match_results_references.csv"
    )

    match_stats_path = Path(args.match_stats).resolve() if args.match_stats else default_match_stats
    out_path = Path(args.out).resolve() if args.out else default_out

    if not match_stats_path.exists():
        raise FileNotFoundError(f"Match stats file not found: {match_stats_path}")

    existing = load_existing_reference(out_path)
    updates = build_updates_from_match_stats(match_stats_path)
    merged = merge_reference(existing, updates, add_missing=args.add_missing)

    existing_ids = (
        set(pd.to_numeric(existing["MatchID"], errors="coerce").dropna().astype(int).tolist())
        if not existing.empty
        else set()
    )
    update_ids = (
        set(pd.to_numeric(updates["MatchID"], errors="coerce").dropna().astype(int).tolist())
        if not updates.empty
        else set()
    )

    print(f"Match stats rows with results: {len(updates)}")
    print(f"Existing references before:    {len(existing)}")
    print(f"References after merge:        {len(merged)}")
    print(f"Updated existing MatchIDs:     {len(existing_ids & update_ids)}")
    print(f"Newly added MatchIDs:          {len(update_ids - existing_ids) if args.add_missing else 0}")
    print(f"Output: {out_path}")

    if args.dry_run:
        print("Dry-run enabled: not writing file.")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
