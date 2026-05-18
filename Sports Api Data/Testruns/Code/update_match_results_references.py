"""Update `match_results_references.csv` automatically from `match_statistics_filtered_78.csv`.

Default behavior
----------------
- The output CSV is always trimmed to the N most recent played matches
  (by descending MatchID, which tracks kickoff order on api-football).
  The cap is set by `--recent` (default 9). Rows that fall outside the
  top N are dropped on every run, so the file never grows beyond N.

Optional
--------
- Use `--no-add-missing` to restrict updates to MatchIDs already in the
  reference file (no new IDs are introduced, but the cap is still applied).
- Use `--recent 0` to disable the cap and keep every played MatchID.

Default paths match the ones used by `AI_match_stats_prediction.py`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

DEFAULT_RECENT_LIMIT = 9


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


def merge_reference(
    existing: pd.DataFrame,
    updates: pd.DataFrame,
    *,
    add_missing: bool,
    recent_limit: int | None = DEFAULT_RECENT_LIMIT,
) -> pd.DataFrame:
    existing = existing.copy()
    updates = updates.copy()

    if existing.empty:
        merged = updates.copy() if add_missing else existing
    else:
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

        merged = merged.reset_index(drop=True)

    if merged.empty:
        return merged[["MatchID", "HomeGoals", "AwayGoals", "Result"]].copy()

    merged["MatchID"] = pd.to_numeric(merged["MatchID"], errors="coerce")
    merged = merged.dropna(subset=["MatchID"]).copy()
    merged["MatchID"] = merged["MatchID"].astype(int)

    # Always trim the final result to the N most recent matches.
    if recent_limit and recent_limit > 0:
        merged = merged.sort_values("MatchID", ascending=False).head(recent_limit)

    merged = merged.sort_values("MatchID", ascending=True).reset_index(drop=True)
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
        dest="add_missing",
        action="store_true",
        default=True,
        help="Append all played MatchIDs from match_statistics_filtered_78.csv (default).",
    )
    parser.add_argument(
        "--no-add-missing",
        dest="add_missing",
        action="store_false",
        help="Only refresh MatchIDs already present in match_results_references.csv.",
    )
    parser.add_argument(
        "--recent",
        type=int,
        default=DEFAULT_RECENT_LIMIT,
        help=(
            "Trim the final output to the N most recent matches by descending "
            f"MatchID (default: {DEFAULT_RECENT_LIMIT}; 0 = no cap, keep all)."
        ),
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
    merged = merge_reference(
        existing,
        updates,
        add_missing=args.add_missing,
        recent_limit=args.recent,
    )

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
    merged_ids = (
        set(merged["MatchID"].astype(int).tolist()) if not merged.empty else set()
    )
    newly_added = merged_ids - existing_ids

    print(f"Match stats rows with results: {len(updates)}")
    print(f"Existing references before:    {len(existing)}")
    print(f"References after merge:        {len(merged)}")
    print(f"Updated existing MatchIDs:     {len(existing_ids & update_ids)}")
    print(f"Newly added MatchIDs:          {len(newly_added) if args.add_missing else 0}")
    if args.add_missing and args.recent and args.recent > 0:
        print(f"Recent cap applied:            {args.recent}")
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
