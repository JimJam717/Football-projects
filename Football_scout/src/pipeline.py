"""
Phase 1: Data Pipeline
Pull and clean player data from FBref via soccerdata.
Merge stats, normalise to per-90, apply league-tier weights,
and save to data/players_cleaned.csv.
"""

import soccerdata as sd
import pandas as pd
import numpy as np
import re
import time
import os
import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# ── configuration ────────────────────────────────────────────────────────────

LEAGUES_CONFIG = {
    "NED-Eredivisie":       {"tier": 1.05, "display": "Eredivisie"},
    "ENG-Championship":     {"tier": 1.10, "display": "Championship"},
    "USA-MLS":              {"tier": 1.00, "display": "MLS"},
    "MEX-Liga MX":          {"tier": 0.95, "display": "Liga MX"},
    "BEL-First Division A": {"tier": 1.00, "display": "Belgian Pro League"},
}

STAT_TYPES = ["standard", "shooting", "passing", "possession", "defense", "misc"]

SEASON = 2024          # soccerdata maps 2024 -> 2024-25 for Euro leagues, 2024 for MLS
MIN_MINUTES = 900
REQUEST_DELAY = 4      # seconds between FBref requests

# FBref position codes → broad roles
POSITION_MAP = {
    "FW":    "Forward",
    "FW,MF": "Winger",
    "MF,FW": "Winger",
    "MF":    "Midfielder",
    "DF,MF": "Fullback",
    "MF,DF": "Fullback",
    "DF":    "Defender",
    "DF,FW": "Defender",
    "FW,DF": "Forward",
}

# Custom league entries that soccerdata may not ship with
CUSTOM_LEAGUES = {
    "NED-Eredivisie": {
        "FBref": "Eredivisie",
        "season_start": "Aug",
        "season_end": "May",
    },
    "ENG-Championship": {
        "FBref": "Championship",
        "season_start": "Aug",
        "season_end": "May",
    },
    "USA-MLS": {
        "FBref": "Major League Soccer",
        "season_start": "Feb",
        "season_end": "Dec",
    },
    "MEX-Liga MX": {
        "FBref": "Liga MX",
        "season_start": "Jul",
        "season_end": "Jun",
    },
    "BEL-First Division A": {
        "FBref": "Belgian First Division A",
        "season_start": "Jul",
        "season_end": "May",
    },
}

# Counting stats we want to normalise per 90
COUNTING_STATS = [
    "goals", "assists", "goals_minus_pk", "penalties",
    "xg", "npxg", "xag",
    "progressive_carries", "progressive_passes", "progressive_receptions",
    "shots", "shots_on_target", "npxg_shot",
    "passes_completed", "passes_attempted", "key_passes",
    "passes_into_penalty_area", "xa",
    "touches", "touches_att_pen",
    "dribbles_completed", "dribbles_attempted",
    "carries", "carries_progressive_distance",
    "tackles", "tackles_won", "interceptions", "clearances",
    "blocks", "pressures", "pressure_successes",
    "crosses", "aerials_won", "aerials_lost",
    "fouls", "fouled", "ball_recoveries",
]


# ── helpers ──────────────────────────────────────────────────────────────────

def to_snake_case(name: str) -> str:
    """Convert an arbitrary header string to snake_case."""
    s = str(name)
    s = s.replace("%", "pct").replace("+", "_plus_").replace("-", "_")
    s = re.sub(r"[/]", "_per_", s)
    s = re.sub(r"[^a-zA-Z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_").lower()


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns into snake_case strings."""
    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for col_tuple in df.columns:
            parts = [
                str(c).strip()
                for c in col_tuple
                if str(c).strip() and "Unnamed" not in str(c)
            ]
            new_cols.append("_".join(parts) if parts else "unknown")
        df.columns = new_cols
    df.columns = [to_snake_case(c) for c in df.columns]
    return df


def find_col(df: pd.DataFrame, patterns: list[str], exclude: list[str] | None = None) -> str | None:
    """Return the first column whose name matches any pattern (exact then substring)."""
    cols_lower = {c.lower(): c for c in df.columns}
    # exact match first
    for p in patterns:
        if p.lower() in cols_lower:
            candidate = cols_lower[p.lower()]
            if exclude and any(e.lower() in candidate.lower() for e in exclude):
                continue
            return candidate
    # substring match
    for p in patterns:
        for cl, original in cols_lower.items():
            if p.lower() in cl:
                if exclude and any(e.lower() in original.lower() for e in exclude):
                    continue
                return original
    return None


def map_position(pos) -> str | None:
    """Map FBref position codes to a broad role; returns None for GK."""
    if pd.isna(pos):
        return None
    pos = str(pos).strip()
    if "GK" in pos:
        return None  # exclude goalkeepers
    return POSITION_MAP.get(pos, "Midfielder")


# ── soccerdata league setup ─────────────────────────────────────────────────

def setup_custom_leagues():
    """Ensure all target leagues exist in soccerdata's league_dict.json."""
    sd_dir = Path.home() / "soccerdata"
    config_dir = sd_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    league_dict_path = config_dir / "league_dict.json"

    existing: dict = {}
    if league_dict_path.exists():
        with open(league_dict_path, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = {}

    changed = False
    for key, entry in CUSTOM_LEAGUES.items():
        if key not in existing:
            existing[key] = entry
            changed = True

    if changed:
        with open(league_dict_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
    print(f"[Pipeline] League config OK -> {league_dict_path}")


# ── scraping ─────────────────────────────────────────────────────────────────

def scrape_league(league_name: str, season: int) -> dict[str, pd.DataFrame]:
    """Scrape all stat types for one league / season from FBref."""
    print(f"\n[Pipeline] Scraping {league_name} (season {season}) ...")
    fbref = sd.FBref(leagues=league_name, seasons=season)
    stat_dfs: dict[str, pd.DataFrame] = {}

    for stat_type in STAT_TYPES:
        time.sleep(REQUEST_DELAY)
        try:
            df = fbref.read_player_season_stats(stat_type=stat_type)
            df = df.reset_index()
            df = flatten_columns(df)
            stat_dfs[stat_type] = df
            print(f"  [OK] {stat_type:12s}  {len(df):>5} rows  {len(df.columns):>3} cols")
        except Exception as exc:
            print(f"  [FAIL] {stat_type:12s}  FAILED - {exc}")

    return stat_dfs


# ── column extraction per stat-type ──────────────────────────────────────────

# Each dict maps *our* canonical name → list of candidate column patterns
_STD_MAP = {
    "player":               ["player"],
    "team":                 ["team"],
    "season":               ["season"],
    "league":               ["league"],
    "nation":               ["nation"],
    "pos":                  ["pos"],
    "age":                  ["age"],
    "born":                 ["born"],
    "minutes":              ["playing_time_min", "min"],
    "nineties":             ["playing_time_90s", "90s"],
    "matches_played":       ["playing_time_mp", "mp"],
    "starts":               ["playing_time_starts", "starts"],
    "goals":                ["performance_gls", "gls"],
    "assists":              ["performance_ast", "ast"],
    "goals_minus_pk":       ["performance_g_pk", "g_pk"],
    "penalties":            ["performance_pk", "pk"],
    "xg":                   ["expected_xg", "xg"],
    "npxg":                 ["expected_npxg", "npxg"],
    "xag":                  ["expected_xag", "xag"],
    "progressive_carries":  ["progression_prgc", "prgc"],
    "progressive_passes":   ["progression_prgp", "prgp"],
    "progressive_receptions": ["progression_prgr", "prgr"],
}

_SHOOT_MAP = {
    "shots":            ["standard_sh", "sh"],
    "shots_on_target":  ["standard_sot", "sot"],
    "npxg_shot":        ["expected_npxg_per_sh", "npxg_sh", "npxg_per_sh"],
}

_PASS_MAP = {
    "passes_completed":         ["total_cmp", "cmp"],
    "passes_attempted":         ["total_att", "att"],
    "pass_completion_pct":      ["total_cmp_pct", "cmp_pct"],
    "xa":                       ["expected_xa", "xa"],
    "key_passes":               ["kp"],
    "passes_into_penalty_area": ["ppa"],
    # progressive passes may appear here too; we prefer the standard one
}

_POSS_MAP = {
    "touches":                      ["touches_touches", "touches"],
    "touches_att_pen":              ["touches_att_pen", "att_pen"],
    "dribbles_completed":           ["take_ons_succ", "succ"],
    "dribbles_attempted":           ["take_ons_att", "take_ons_attempted"],
    "carries":                      ["carries_carries", "carries"],
    "carries_progressive_distance": ["carries_prgdist", "prgdist"],
}

_DEF_MAP = {
    "tackles":            ["tackles_tkl", "tkl"],
    "tackles_won":        ["tackles_tklw", "tklw"],
    "interceptions":      ["int"],
    "clearances":         ["clr"],
    "blocks":             ["blocks_blocks", "blocks"],
    "pressures":          ["press", "pressures"],
    "pressure_successes": ["succ", "pressure_succ"],
}

_MISC_MAP = {
    "crosses":          ["performance_crs", "crs"],
    "aerials_won":      ["aerial_duels_won", "won"],
    "aerials_lost":     ["aerial_duels_lost", "lost"],
    "fouls":            ["performance_fls", "fls"],
    "fouled":           ["performance_fld", "fld"],
    "ball_recoveries":  ["performance_recov", "recov"],
}


def _extract(df: pd.DataFrame, col_map: dict, merge_keys: list[str]) -> pd.DataFrame:
    """Pull columns described by *col_map* out of *df*."""
    out: dict[str, pd.Series] = {}
    for target, patterns in col_map.items():
        if target in merge_keys:
            continue
        col = find_col(df, patterns)
        if col is not None:
            out[target] = pd.to_numeric(df[col], errors="coerce") if target not in ("player", "team", "season", "league", "nation", "pos", "age", "born") else df[col]
    result = pd.DataFrame(out)
    for mk in merge_keys:
        c = find_col(df, [mk])
        if c is not None:
            result[mk] = df[c]
    return result


# ── merge all stat types ─────────────────────────────────────────────────────

def merge_stat_dfs(stat_dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge the six stat-type DataFrames into one player-level table."""
    merge_keys = ["league", "season", "team", "player"]

    if "standard" not in stat_dfs:
        raise ValueError("Standard stats are required but missing.")

    base = _extract(stat_dfs["standard"], _STD_MAP, merge_keys)
    print(f"  [merge] base from standard: {len(base)} rows")

    type_map = {
        "shooting":   _SHOOT_MAP,
        "passing":    _PASS_MAP,
        "possession": _POSS_MAP,
        "defense":    _DEF_MAP,
        "misc":       _MISC_MAP,
    }

    for stype, cmap in type_map.items():
        if stype not in stat_dfs:
            continue
        part = _extract(stat_dfs[stype], cmap, merge_keys)
        available_keys = [k for k in merge_keys if k in base.columns and k in part.columns]
        if not available_keys:
            print(f"  [merge] WARNING skipping {stype}: no common keys")
            continue
        # drop columns already present in base (except merge keys)
        drop = [c for c in part.columns if c in base.columns and c not in available_keys]
        part = part.drop(columns=drop, errors="ignore")
        base = base.merge(part, on=available_keys, how="left")
        print(f"  [merge] + {stype:12s} -> {len(base)} rows, {len(base.columns)} cols")

    return base


# ── per-90 normalisation & league-tier adjustment ────────────────────────────

def compute_per90(df: pd.DataFrame) -> pd.DataFrame:
    """Add *_per90 columns for every counting stat that exists."""
    nineties_col = "nineties"
    if nineties_col not in df.columns:
        if "minutes" in df.columns:
            df[nineties_col] = pd.to_numeric(df["minutes"], errors="coerce") / 90.0
        else:
            print("  WARNING Cannot compute per-90: no minutes/nineties column")
            return df

    nineties = pd.to_numeric(df[nineties_col], errors="coerce").replace(0, np.nan)
    for stat in COUNTING_STATS:
        if stat in df.columns:
            df[f"{stat}_per90"] = pd.to_numeric(df[stat], errors="coerce") / nineties
    return df


def apply_league_tier(df: pd.DataFrame) -> pd.DataFrame:
    """Multiply per-90 metrics by each player's league_tier."""
    per90_cols = [c for c in df.columns if c.endswith("_per90")]
    if "league_tier" not in df.columns:
        return df
    tier = pd.to_numeric(df["league_tier"], errors="coerce").fillna(1.0)
    for col in per90_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce") * tier
    return df


# ── deduplication & position tagging ─────────────────────────────────────────

def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the row with the most minutes if a player appears more than once."""
    df["_min_num"] = pd.to_numeric(df.get("minutes", 0), errors="coerce").fillna(0)
    df = df.sort_values("_min_num", ascending=False).drop_duplicates(subset=["player"], keep="first")
    df = df.drop(columns=["_min_num"])
    return df


def tag_positions(df: pd.DataFrame) -> pd.DataFrame:
    """Add a 'role' column by mapping FBref position codes."""
    if "pos" in df.columns:
        df["role"] = df["pos"].apply(map_position)
    else:
        df["role"] = "Midfielder"
    return df


# ── main entry point ─────────────────────────────────────────────────────────

def run_pipeline() -> pd.DataFrame:
    """Full Phase-1 pipeline: scrape -> merge -> normalise -> save."""
    setup_custom_leagues()

    all_frames: list[pd.DataFrame] = []

    for league, config in LEAGUES_CONFIG.items():
        try:
            stat_dfs = scrape_league(league, SEASON)
            if not stat_dfs:
                print(f"  WARNING No data returned for {league}, skipping.")
                continue
            merged = merge_stat_dfs(stat_dfs)
            merged["league"] = config["display"]
            merged["league_tier"] = config["tier"]
            all_frames.append(merged)
            print(f"  [OK] {league}: {len(merged)} players extracted")
        except Exception as exc:
            print(f"  [FAIL] {league} failed: {exc}")

    if not all_frames:
        raise RuntimeError("No data was scraped from any league.  Check connection & rate limits.")

    df = pd.concat(all_frames, ignore_index=True)
    print(f"\n[Pipeline] Combined dataset: {len(df)} rows")

    # Ensure minutes is numeric
    df["minutes"] = pd.to_numeric(df.get("minutes", 0), errors="coerce").fillna(0)

    # Filter minimum minutes
    df = df[df["minutes"] >= MIN_MINUTES].copy()
    print(f"[Pipeline] After {MIN_MINUTES}-minute filter: {len(df)} rows")

    # Deduplicate transfers
    df = deduplicate(df)
    print(f"[Pipeline] After deduplication: {len(df)} rows")

    # Tag positions
    df = tag_positions(df)

    # Remove goalkeepers (role == None)
    df = df[df["role"].notna()].copy()
    print(f"[Pipeline] After GK removal: {len(df)} outfield players")

    # Per-90 normalisation
    df = compute_per90(df)

    # League-tier adjustment
    df = apply_league_tier(df)

    # ── fallback: if pressures is missing, use ball_recoveries ──
    if "pressures_per90" not in df.columns and "ball_recoveries_per90" in df.columns:
        df["pressures_per90"] = df["ball_recoveries_per90"]
        print("[Pipeline] WARNING Pressures not found - using ball_recoveries as proxy")

    # ── fallback: if xa is missing, use xag ──
    if "xa_per90" not in df.columns and "xag_per90" in df.columns:
        df["xa_per90"] = df["xag_per90"]
        print("[Pipeline] WARNING xA not found - using xAG as proxy")

    # Rename xa → xA for consistency with spec metric names
    if "xa_per90" in df.columns:
        df.rename(columns={"xa_per90": "xA_per90"}, inplace=True)

    # Save
    out_dir = Path("data")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "players_cleaned.csv"
    df.to_csv(out_path, index=False)
    print(f"\n[Pipeline] DONE Saved {len(df)} players -> {out_path}")

    # Print available per-90 columns for debugging
    per90_cols = sorted(c for c in df.columns if c.endswith("_per90"))
    print(f"[Pipeline] Per-90 columns available: {per90_cols}")

    return df


# ── CLI shortcut ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_pipeline()
