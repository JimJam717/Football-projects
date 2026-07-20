"""
Phase 2: Percentile Ranking Engine
Rank players on role-specific metric bundles using percentile scores.
Saves data/players_ranked.csv.
"""

import pandas as pd
import numpy as np
from scipy.stats import percentileofscore
from pathlib import Path


# ── role-specific metric bundles ─────────────────────────────────────────────

ROLE_METRICS: dict[str, list[str]] = {
    "Forward": [
        "npxg_per90",
        "shots_per90",
        "xA_per90",
        "progressive_carries_per90",
        "touches_att_pen_per90",
    ],
    "Winger": [
        "xA_per90",
        "progressive_carries_per90",
        "dribbles_completed_per90",
        "crosses_per90",
        "progressive_passes_per90",
    ],
    "Midfielder": [
        "progressive_passes_per90",
        "progressive_carries_per90",
        "pressures_per90",
        "tackles_per90",
        "xA_per90",
        "pass_completion_pct",
    ],
    "Fullback": [
        "progressive_carries_per90",
        "crosses_per90",
        "tackles_per90",
        "interceptions_per90",
        "xA_per90",
    ],
    "Defender": [
        "aerials_won_per90",
        "tackles_per90",
        "interceptions_per90",
        "progressive_passes_per90",
        "clearances_per90",
    ],
}

# Human-friendly labels for each metric (used in dossier interpretation)
METRIC_LABELS: dict[str, str] = {
    "npxg_per90":                "Non-Penalty xG per 90",
    "shots_per90":               "Shots per 90",
    "xA_per90":                  "Expected Assists per 90",
    "progressive_carries_per90": "Progressive Carries per 90",
    "touches_att_pen_per90":     "Touches in Attacking Pen. Area per 90",
    "dribbles_completed_per90":  "Dribbles Completed per 90",
    "crosses_per90":             "Crosses per 90",
    "progressive_passes_per90":  "Progressive Passes per 90",
    "pressures_per90":           "Pressures per 90",
    "tackles_per90":             "Tackles per 90",
    "pass_completion_pct":       "Pass Completion %",
    "interceptions_per90":       "Interceptions per 90",
    "aerials_won_per90":         "Aerials Won per 90",
    "clearances_per90":          "Clearances per 90",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def _percentile(value: float, data: pd.Series) -> float:
    """Compute the percentile rank of *value* within *data* (0-100)."""
    clean = data.dropna()
    if len(clean) == 0 or pd.isna(value):
        return np.nan
    return percentileofscore(clean, value, kind="rank")


def compute_role_percentiles(
    df: pd.DataFrame,
    role: str,
    metrics: list[str],
) -> pd.DataFrame:
    """
    For every player whose tagged role == *role*, compute percentile ranks
    for each metric and a composite score (mean of percentiles).
    Returns the subset with new percentile + composite columns.
    """
    pool = df[df["role"] == role].copy()
    if pool.empty:
        return pool

    for metric in metrics:
        pct_col = f"{metric}_pctile"
        if metric in pool.columns:
            vals = pd.to_numeric(pool[metric], errors="coerce")
            pool[pct_col] = vals.apply(lambda v: _percentile(v, vals))
        else:
            pool[pct_col] = np.nan

    pctile_cols = [f"{m}_pctile" for m in metrics]
    pool["composite_score"] = pool[pctile_cols].mean(axis=1)

    return pool


# ── main entry point ─────────────────────────────────────────────────────────

def run_ranking(input_csv: str = "data/players_cleaned.csv") -> pd.DataFrame:
    """
    Load the cleaned data, compute percentile ranks for every role,
    concatenate, and save to data/players_ranked.csv.
    """
    df = pd.read_csv(input_csv)
    print(f"[Ranking] Loaded {len(df)} players from {input_csv}")

    # Ensure numeric types for all metric columns
    all_metric_cols = set()
    for metrics in ROLE_METRICS.values():
        all_metric_cols.update(metrics)
    for col in all_metric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    ranked_parts: list[pd.DataFrame] = []

    for role, metrics in ROLE_METRICS.items():
        missing = [m for m in metrics if m not in df.columns]
        if missing:
            print(f"  WARNING {role}: missing columns {missing} -- will produce NaN percentiles")
        part = compute_role_percentiles(df, role, metrics)
        if not part.empty:
            print(f"  [OK] {role:12s}  {len(part):>5} players ranked")
        ranked_parts.append(part)

    ranked = pd.concat(ranked_parts, ignore_index=True)
    print(f"[Ranking] Total ranked players: {len(ranked)}")

    # Save
    out_dir = Path("data")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "players_ranked.csv"
    ranked.to_csv(out_path, index=False)
    print(f"[Ranking] DONE Saved -> {out_path}")

    return ranked


# ── standalone ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_ranking()
