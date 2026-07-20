"""
aggregate_results.py
Step 5: Produce aggregate_results.parquet from comment_flags.parquet.

All breakdowns use only aggregate rates — no per-comment rows in output.
Every cell includes denominator 'n' so the dashboard can suppress thin samples.

Output (public):
    data/processed/identity_flags/aggregate_results.parquet
        Contains multiple breakdown tables stored as separate tidy DataFrames,
        serialised as a single parquet with a 'breakdown' discriminator column.

Breakdowns:
    headline     — overall flagged counts and rates
    by_match     — flagged rate per match_id
    by_stage     — flagged rate by tournament stage
    by_subreddit — flagged rate by subreddit
    by_language  — flagged rate by detected language (incl. model_unsupported share)
    overlap      — profanity x identity flag 2x2 counts

USER RUNS THIS:
    python aggregate_results.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from identity_common import (
    OUTPUT_DIR,
    MATCH_CONFIG_PATH,
    load_match_config,
    build_stage_map,
    log,
    log_stage,
    abort,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_flags(flags_path: Path) -> pd.DataFrame:
    if not flags_path.exists():
        abort(f"comment_flags.parquet not found at {flags_path}. Run flag_detection.py first.")
    df = pd.read_parquet(flags_path)
    log_stage("flags_loaded", len(df))
    return df


def _rate(hit: int, n: int) -> float:
    return round(hit / n, 6) if n > 0 else 0.0


def compute_breakdown(group: pd.DataFrame) -> dict:
    n = len(group)
    racial_ethnic = int((group["bucket"] == "racial_ethnic_flagged").sum())
    nationality = int((group["bucket"] == "nationality_flagged").sum())
    model_unsupported = int((group["bucket"] == "model_unsupported").sum())
    unflagged = int((group["bucket"] == "unflagged").sum())
    any_flagged = racial_ethnic + nationality
    return {
        "n": n,
        "racial_ethnic_flagged_n": racial_ethnic,
        "nationality_flagged_n": nationality,
        "model_unsupported_n": model_unsupported,
        "unflagged_n": unflagged,
        "any_flagged_n": any_flagged,
        "racial_ethnic_rate": _rate(racial_ethnic, n),
        "nationality_rate": _rate(nationality, n),
        "model_unsupported_rate": _rate(model_unsupported, n),
        "any_flagged_rate": _rate(any_flagged, n),
    }


def build_breakdown_df(df: pd.DataFrame, group_col: str, breakdown_name: str) -> pd.DataFrame:
    rows = []
    for key, group in df.groupby(group_col, dropna=False):
        rec = compute_breakdown(group)
        rec[group_col] = str(key) if key is not None else "unknown"
        rec["breakdown"] = breakdown_name
        rows.append(rec)
    out = pd.DataFrame(rows)
    # Sort by any_flagged_rate descending for readability
    if "any_flagged_rate" in out.columns:
        out = out.sort_values("any_flagged_rate", ascending=False).reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
# Individual breakdown builders
# ---------------------------------------------------------------------------

def headline(df: pd.DataFrame) -> pd.DataFrame:
    rec = compute_breakdown(df)
    rec["breakdown"] = "headline"
    rec["group"] = "all"
    return pd.DataFrame([rec])


def by_match(df: pd.DataFrame) -> pd.DataFrame:
    result = build_breakdown_df(df, "match_id", "by_match")
    result = result.rename(columns={"match_id": "group"})
    return result


def by_stage(df: pd.DataFrame, stage_map: dict) -> pd.DataFrame:
    df = df.copy()
    df["stage_label"] = df["match_id"].map(lambda m: stage_map.get(m, {}).get("stage_label", "unknown"))
    result = build_breakdown_df(df, "stage_label", "by_stage")
    result = result.rename(columns={"stage_label": "group"})
    return result


def by_subreddit(df: pd.DataFrame) -> pd.DataFrame:
    result = build_breakdown_df(df, "subreddit", "by_subreddit")
    result = result.rename(columns={"subreddit": "group"})
    return result


def by_language(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["lang_group"] = df["detected_language"].fillna("unknown")
    result = build_breakdown_df(df, "lang_group", "by_language")
    result = result.rename(columns={"lang_group": "group"})
    return result


def overlap(df: pd.DataFrame) -> pd.DataFrame:
    """Profanity (swear_count > 0) × any identity flag 2×2."""
    df = df.copy()
    df["has_profanity"] = (df["swear_count"].fillna(0) > 0)
    df["has_identity_flag"] = (df["bucket"].isin(["racial_ethnic_flagged", "nationality_flagged"]))

    rows = []
    for has_prof in [True, False]:
        for has_ident in [True, False]:
            n = int(((df["has_profanity"] == has_prof) & (df["has_identity_flag"] == has_ident)).sum())
            rows.append(
                {
                    "breakdown": "overlap",
                    "profanity": has_prof,
                    "identity_flag": has_ident,
                    "n": n,
                    "rate": _rate(n, len(df)),
                    "group": f"profanity={'yes' if has_prof else 'no'}_identity={'yes' if has_ident else 'no'}",
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate aggregate_results.parquet from comment flags.")
    p.add_argument(
        "--flags", default=str(OUTPUT_DIR / "comment_flags.parquet"),
    )
    p.add_argument(
        "--out", default=str(OUTPUT_DIR / "aggregate_results.parquet"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    flags_path = Path(args.flags)
    out_path = Path(args.out)

    df = load_flags(flags_path)

    log("[aggregate] Loading match config for stage map ...")
    match_config = load_match_config()
    stage_map = build_stage_map(match_config)

    log("[aggregate] Computing breakdowns ...")
    parts = [
        headline(df),
        by_match(df),
        by_stage(df, stage_map),
        by_subreddit(df),
        by_language(df),
        overlap(df),
    ]

    combined = pd.concat(parts, ignore_index=True)

    # Ensure breakdown column is first
    cols = ["breakdown", "group"] + [c for c in combined.columns if c not in ("breakdown", "group")]
    combined = combined[[c for c in cols if c in combined.columns]]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(out_path, index=False)
    log(f"[aggregate] Wrote {len(combined)} rows ({combined['breakdown'].nunique()} breakdowns) -> {out_path}")

    # Print summary
    h = combined[combined["breakdown"] == "headline"].iloc[0]
    log("")
    log("=== Headline ===")
    log(f"  Total comments:          {int(h['n']):,}")
    log(f"  Racial/ethnic flagged:   {int(h['racial_ethnic_flagged_n']):,} ({h['racial_ethnic_rate']:.2%})")
    log(f"  Nationality flagged:     {int(h['nationality_flagged_n']):,} ({h['nationality_rate']:.2%})")
    log(f"  Any flagged:             {int(h['any_flagged_n']):,} ({h['any_flagged_rate']:.2%})")
    log(f"  Model unsupported:       {int(h['model_unsupported_n']):,} ({h['model_unsupported_rate']:.2%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
