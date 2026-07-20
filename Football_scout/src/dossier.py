"""
Phase 4: Dossier Generator
Produce structured markdown recommendation dossiers for individual players.
"""

import os
import re
import pandas as pd
import numpy as np
from pathlib import Path

from src.ranking import ROLE_METRICS, METRIC_LABELS
from src.similarity import get_similar_mls_players


# ── budget benchmarks (rough MLS salary ranges) ─────────────────────────────

BUDGET_BENCHMARKS = {
    "Forward":    {"starter": (150_000, 400_000), "designated": 500_000},
    "Winger":     {"starter": (150_000, 400_000), "designated": 500_000},
    "Midfielder": {"starter": (150_000, 400_000), "designated": 500_000},
    "Fullback":   {"starter": (150_000, 350_000), "designated": 500_000},
    "Defender":   {"starter": (150_000, 350_000), "designated": 500_000},
}


# ── plain-English interpretation for a percentile ────────────────────────────

def _interpret(metric_label: str, percentile: float) -> str:
    """Generate a one-line plain-English interpretation based on thresholds."""
    if pd.isna(percentile):
        return "Data unavailable for this metric"
    p = round(percentile)
    short = metric_label.split(" per 90")[0].split(" %")[0].strip()
    if p >= 90:
        return f"Elite-level {short.lower()} — ranks in the top 10% of the dataset"
    elif p >= 75:
        return f"Ranks among the top quartile in {short.lower()}"
    elif p >= 60:
        return f"Above-average {short.lower()} — comfortably in the upper half"
    elif p >= 40:
        return f"Average {short.lower()} — mid-range among peers"
    elif p >= 25:
        return f"Below-average {short.lower()} — lower quartile of the dataset"
    else:
        return f"Significant weakness in {short.lower()} — bottom 25%"


def _tier_label(score: float) -> str:
    if score >= 90:
        return "Elite"
    elif score >= 75:
        return "Strong Profile"
    elif score >= 60:
        return "Solid Option"
    else:
        return "Monitor Only"


def _budget_line(budget: int, role: str) -> str:
    """Generate the budget assessment line."""
    bench = BUDGET_BENCHMARKS.get(role, BUDGET_BENCHMARKS["Midfielder"])
    low, high = bench["starter"]
    dp = bench["designated"]

    if budget >= dp:
        return (f"At an estimated budget of ${budget:,}, this player is at "
                f"Designated Player level for a {role} in MLS.")
    elif budget >= high:
        return (f"At an estimated budget of ${budget:,}, this player exceeds "
                f"typical {role} market value in MLS but is below DP threshold.")
    elif budget >= low:
        return (f"At an estimated budget of ${budget:,}, this player fits "
                f"typical {role} market value in MLS.")
    else:
        return (f"At an estimated budget of ${budget:,}, this player is well within "
                f"typical {role} market value in MLS.")


def _slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


# ── main generator ───────────────────────────────────────────────────────────

def generate_dossier(
    player_name: str,
    role: str,
    df: pd.DataFrame,
    budget_usd: int,
) -> str | None:
    """
    Generate and save a markdown dossier for *player_name* assessed as *role*.
    Returns the dossier text, or None if the player is not found.
    """
    role = role.strip().title()

    # ── locate player ────────────────────────────────────────────────────
    mask = df["player"].str.lower() == player_name.strip().lower()
    if mask.sum() == 0:
        mask = df["player"].str.lower().str.contains(player_name.strip().lower(), na=False)
    if mask.sum() == 0:
        print(f"[Dossier] Player '{player_name}' not found.")
        return None

    row = df.loc[mask].iloc[0]

    # ── basic info ───────────────────────────────────────────────────────
    club    = row.get("team", "N/A")
    league  = row.get("league", "N/A")
    age     = row.get("age", "N/A")
    minutes = row.get("minutes", "N/A")
    try:
        minutes_num = float(minutes)
    except (ValueError, TypeError):
        minutes_num = 0
    composite = row.get("composite_score", np.nan)
    try:
        composite = float(composite)
    except (ValueError, TypeError):
        composite = np.nan

    tier = _tier_label(composite) if not pd.isna(composite) else "N/A"

    # ── metric breakdown ─────────────────────────────────────────────────
    metrics = ROLE_METRICS.get(role, [])
    metric_lines = []
    for m in metrics:
        label = METRIC_LABELS.get(m, m)
        raw   = row.get(m, np.nan)
        pct   = row.get(f"{m}_pctile", np.nan)
        try:
            raw_str = f"{float(raw):.2f}"
        except (ValueError, TypeError):
            raw_str = "N/A"
        try:
            pct_str = f"{float(pct):.0f}th percentile"
            interp = _interpret(label, float(pct))
        except (ValueError, TypeError):
            pct_str = "N/A"
            interp = "Data unavailable"
        metric_lines.append(f"| {label} | {raw_str} | {pct_str} | \"{interp}\" |")

    # ── similar MLS players ──────────────────────────────────────────────
    similar = get_similar_mls_players(player_name, role, df)
    sim_lines = []
    if similar is not None and not similar.empty:
        for _, srow in similar.head(3).iterrows():
            sname  = srow.get("player", "?")
            steam  = srow.get("team", "?")
            scomp  = srow.get("composite_score", "?")
            try:
                scomp = f"{float(scomp):.1f}"
            except (ValueError, TypeError):
                scomp = "N/A"
            ssim   = srow.get("similarity_pct", "?")
            sim_lines.append(f"- **{sname}** — {ssim}% similar | Composite {scomp} | {steam}")
    else:
        sim_lines.append("- _No suitable MLS comparisons found._")

    # ── risk flags ───────────────────────────────────────────────────────
    risk_flags = []
    try:
        age_num = int(str(age).split("-")[0]) if "-" in str(age) else int(age)
    except (ValueError, TypeError):
        age_num = None
    if age_num and age_num > 28:
        risk_flags.append(f"⚠ **Age risk**: Player is {age_num} — depreciating asset for transfer value")
    if minutes_num < 1500:
        risk_flags.append(f"⚠ **Sample size risk**: Only {int(minutes_num)} minutes played — limited evaluation window")
    league_tier = row.get("league_tier", 1.0)
    try:
        league_tier = float(league_tier)
    except (ValueError, TypeError):
        league_tier = 1.0
    if league_tier < 1.0:
        risk_flags.append(
            f"⚠ **League discount**: {league} has a tier weight of {league_tier:.2f} — "
            f"adjust expectations for step-up in competition"
        )
    if not risk_flags:
        risk_flags.append("✅ No major risk flags identified")

    # Determine how many major flags there are (excluding the "no flags" line)
    major_flag_count = sum(1 for f in risk_flags if f.startswith("⚠"))

    # ── recommendation verdict ───────────────────────────────────────────
    if pd.isna(composite):
        verdict = "MONITOR for next window — insufficient data to evaluate"
    elif composite >= 75 and major_flag_count == 0:
        verdict = "**RECOMMEND for acquisition**"
    elif 60 <= composite < 75 or major_flag_count == 1:
        flag_detail = ""
        if major_flag_count > 0:
            # Pull out the first flag keyword
            first_flag = risk_flags[0]
            if "Age" in first_flag:
                flag_detail = " — verify age trajectory and resale value before proceeding"
            elif "Sample" in first_flag:
                flag_detail = " — verify sample size with additional scouting data before proceeding"
            elif "League" in first_flag:
                flag_detail = " — verify performance translates at a higher competition level"
        if composite >= 75 and major_flag_count == 1:
            verdict = f"**CONDITIONAL recommendation**{flag_detail}"
        else:
            verdict = f"**CONDITIONAL recommendation**{flag_detail}"
    else:
        verdict = "**MONITOR for next window**"

    budget_line = _budget_line(budget_usd, role)

    # ── assemble dossier ─────────────────────────────────────────────────
    dossier = f"""---

# PLAYER DOSSIER

| Field | Value |
|-------|-------|
| **Player** | {row.get('player', player_name)} |
| **Club** | {club} |
| **League** | {league} |
| **Age** | {age} |
| **Role Assessed** | {role} |
| **Minutes Played** | {int(minutes_num) if minutes_num else 'N/A'} |

---

## COMPOSITE SCORE: {composite:.1f}/100 — {tier}

---

## METRIC BREAKDOWN

| Metric | Per-90 Value | Percentile | Interpretation |
|--------|-------------|------------|----------------|
{chr(10).join(metric_lines)}

---

## SIMILAR MLS PLAYERS

{chr(10).join(sim_lines)}

---

## RISK FLAGS

{chr(10).join(risk_flags)}

---

## RECOMMENDATION

{verdict}

{budget_line}

---
"""

    # ── save to file ─────────────────────────────────────────────────────
    out_dir = Path("output") / "dossiers"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(row.get("player", player_name))
    out_path = out_dir / f"{slug}.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(dossier)
    print(f"[Dossier] ✓ Saved → {out_path}")

    return dossier


# ── standalone test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    csv_path = "data/players_ranked.csv"
    df = pd.read_csv(csv_path)
    name   = sys.argv[1] if len(sys.argv) > 1 else df["player"].iloc[0]
    role   = sys.argv[2] if len(sys.argv) > 2 else "Forward"
    budget = int(sys.argv[3]) if len(sys.argv) > 3 else 250_000

    text = generate_dossier(name, role, df, budget)
    if text:
        print(text)
