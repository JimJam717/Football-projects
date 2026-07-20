"""
Phase 3: Similarity Model
For a given target player, find the 5 most similar *successful* MLS players
using a cosine-distance KNN model fitted on role-specific metrics.
"""

import pandas as pd
import numpy as np
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
from src.ranking import ROLE_METRICS


# ── constants ────────────────────────────────────────────────────────────────

MLS_MIN_COMPOSITE = 60      # composite score threshold for "successful"
MLS_MIN_MINUTES   = 1800    # minutes threshold for MLS anchors
K_NEIGHBORS       = 5


# ── core function ────────────────────────────────────────────────────────────

def get_similar_mls_players(
    player_name: str,
    role: str,
    df: pd.DataFrame,
) -> pd.DataFrame | None:
    """
    Return a DataFrame of the *K_NEIGHBORS* most similar successful MLS
    players for the given *player_name* assessed under *role*.

    Columns returned:
        player, team, league, composite_score, similarity_pct

    Returns None if the query player or role is not found, or if there
    are fewer than 1 MLS anchor to compare against.
    """
    role = role.strip().title()
    if role not in ROLE_METRICS:
        print(f"[Similarity] Unknown role '{role}'. Choose from: {list(ROLE_METRICS)}")
        return None

    metrics = ROLE_METRICS[role]

    # --- locate query player ------------------------------------------------
    mask = df["player"].str.lower() == player_name.strip().lower()
    if mask.sum() == 0:
        # try substring match
        mask = df["player"].str.lower().str.contains(player_name.strip().lower(), na=False)
    if mask.sum() == 0:
        print(f"[Similarity] Player '{player_name}' not found in dataset.")
        return None

    query_row = df.loc[mask].iloc[0]

    # --- build MLS anchor pool -----------------------------------------------
    minutes_col = "minutes"
    mls_mask = (
        (df["league"].str.lower() == "mls")
        & (pd.to_numeric(df.get("composite_score", 0), errors="coerce") >= MLS_MIN_COMPOSITE)
        & (pd.to_numeric(df.get(minutes_col, 0), errors="coerce") >= MLS_MIN_MINUTES)
    )
    anchors = df.loc[mls_mask].copy()

    if len(anchors) < 1:
        print("[Similarity] Not enough MLS anchors (composite ≥ 60, min 1800′). "
              "Relaxing composite threshold to 50.")
        mls_mask = (
            (df["league"].str.lower() == "mls")
            & (pd.to_numeric(df.get("composite_score", 0), errors="coerce") >= 50)
            & (pd.to_numeric(df.get(minutes_col, 0), errors="coerce") >= MLS_MIN_MINUTES)
        )
        anchors = df.loc[mls_mask].copy()
        if len(anchors) < 1:
            print("[Similarity] Still not enough MLS anchors. Cannot compute similarity.")
            return None

    # --- prepare feature matrices --------------------------------------------
    available = [m for m in metrics if m in df.columns]
    if not available:
        print(f"[Similarity] No metric columns available for role '{role}'.")
        return None

    X_anchor = anchors[available].apply(pd.to_numeric, errors="coerce").fillna(0).values
    x_query  = pd.to_numeric(query_row[available], errors="coerce").fillna(0).values.reshape(1, -1)

    # Scale features before cosine distance for better stability
    scaler = StandardScaler()
    X_anchor_scaled = scaler.fit_transform(X_anchor)
    x_query_scaled  = scaler.transform(x_query)

    # --- fit KNN (cosine) ----------------------------------------------------
    k = min(K_NEIGHBORS, len(anchors))
    knn = NearestNeighbors(n_neighbors=k, metric="cosine")
    knn.fit(X_anchor_scaled)

    distances, indices = knn.kneighbors(x_query_scaled)

    # Convert cosine distance → similarity percentage (0-100)
    similarities = (1 - distances[0]) * 100

    results = anchors.iloc[indices[0]].copy()
    results = results[["player", "team", "league", "composite_score"]].copy()
    results["similarity_pct"] = similarities.round(1)
    results = results.sort_values("similarity_pct", ascending=False).reset_index(drop=True)

    return results


# ── standalone test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    csv_path = "data/players_ranked.csv"
    df = pd.read_csv(csv_path)
    name = sys.argv[1] if len(sys.argv) > 1 else df["player"].iloc[0]
    role = sys.argv[2] if len(sys.argv) > 2 else "Forward"

    result = get_similar_mls_players(name, role, df)
    if result is not None:
        print(f"\nTop {len(result)} similar MLS players for {name} ({role}):")
        print(result.to_string(index=False))
