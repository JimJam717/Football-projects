"""
Phase 5: CLI Interface
Entry point for the Soccer Recruitment Decision Engine.

Usage
-----
  # Generate a single player dossier
  python main.py --player "Player Name" --role winger --budget 250000

  # Show top N targets for a role
  python main.py --top-targets --role midfielder --budget 300000 --n 5

  # Run the full scraping pipeline (Phase 1)
  python main.py --scrape

  # Run the ranking engine (Phase 2)
  python main.py --rank
"""

import argparse
import sys
import pandas as pd
from pathlib import Path

from src.ranking import ROLE_METRICS, METRIC_LABELS
from src.dossier import generate_dossier, _tier_label


RANKED_CSV = Path("data/players_ranked.csv")


# ── helpers ──────────────────────────────────────────────────────────────────

def load_ranked_data() -> pd.DataFrame:
    if not RANKED_CSV.exists():
        print(f"[Error] {RANKED_CSV} not found.  Run the pipeline first:")
        print("   python main.py --scrape")
        print("   python main.py --rank")
        sys.exit(1)
    return pd.read_csv(RANKED_CSV)


def handle_player(args):
    """Generate a dossier for a single player."""
    df = load_ranked_data()
    role = args.role.strip().title()
    budget = int(args.budget)

    text = generate_dossier(args.player, role, df, budget)
    if text:
        print(text)
    else:
        # Try fuzzy search and suggest close names
        matches = df[df["player"].str.lower().str.contains(args.player.lower(), na=False)]
        if not matches.empty:
            print(f"\nDid you mean one of these?")
            for _, r in matches.head(10).iterrows():
                print(f"  • {r['player']}  ({r.get('team','?')}, {r.get('league','?')})")


def handle_top_targets(args):
    """Print a ranked shortlist of top N players for a role."""
    df = load_ranked_data()
    role = args.role.strip().title()
    n = int(args.n)
    budget = int(args.budget)

    if role not in ROLE_METRICS:
        print(f"[Error] Unknown role '{role}'. Choose from: {list(ROLE_METRICS)}")
        sys.exit(1)

    pool = df[df["role"] == role].copy()
    pool["composite_score"] = pd.to_numeric(pool["composite_score"], errors="coerce")
    pool = pool.dropna(subset=["composite_score"])
    pool = pool.sort_values("composite_score", ascending=False).head(n)

    if pool.empty:
        print(f"No players found for role '{role}'.")
        return

    # Header
    print(f"\n{'='*72}")
    print(f"  TOP {n} {role.upper()} TARGETS")
    print(f"  Budget: ${budget:,}")
    print(f"{'='*72}\n")

    for rank, (_, row) in enumerate(pool.iterrows(), 1):
        name  = row.get("player", "?")
        club  = row.get("team", "?")
        league = row.get("league", "?")
        score = row["composite_score"]
        tier  = _tier_label(score)
        age   = row.get("age", "?")

        # One-line summary
        print(f"  {rank}. {name}")
        print(f"     {club} | {league} | Age {age}")
        print(f"     Composite: {score:.1f}/100 ({tier})")

        # Key metrics quick peek
        metrics = ROLE_METRICS[role]
        highlights = []
        for m in metrics[:3]:
            pct = row.get(f"{m}_pctile", None)
            label = METRIC_LABELS.get(m, m).split(" per 90")[0]
            if pct is not None and not pd.isna(pct):
                highlights.append(f"{label}: P{int(pct)}")
        if highlights:
            print(f"     Key: {' | '.join(highlights)}")
        print()

    print(f"{'='*72}")
    print(f"  Run  python main.py --player \"<name>\" --role {role.lower()} --budget {budget}")
    print(f"  to generate a full dossier for any of these targets.")
    print(f"{'='*72}\n")


def handle_scrape(_args):
    """Run Phase 1: Data Pipeline."""
    from src.pipeline import run_pipeline
    run_pipeline()


def handle_rank(_args):
    """Run Phase 2: Ranking Engine."""
    from src.ranking import run_ranking
    run_ranking()


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Soccer Recruitment Decision Engine — CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --scrape                                       # Phase 1: scrape FBref
  python main.py --rank                                         # Phase 2: compute rankings
  python main.py --player "Luuk de Jong" --role forward --budget 300000
  python main.py --top-targets --role midfielder --budget 300000 --n 5
        """,
    )

    # Mode flags
    parser.add_argument("--scrape", action="store_true",
                        help="Run the data pipeline (Phase 1: scrape FBref)")
    parser.add_argument("--rank", action="store_true",
                        help="Run the ranking engine (Phase 2)")
    parser.add_argument("--player", type=str, default=None,
                        help="Player name to generate a dossier for")
    parser.add_argument("--top-targets", action="store_true",
                        help="Show the top N targets for a role")

    # Shared arguments
    parser.add_argument("--role", type=str, default="Forward",
                        help="Role: Forward, Winger, Midfielder, Fullback, Defender")
    parser.add_argument("--budget", type=int, default=250_000,
                        help="Budget in USD")
    parser.add_argument("--n", type=int, default=5,
                        help="Number of top targets to show (used with --top-targets)")

    args = parser.parse_args()

    # Dispatch
    if args.scrape:
        handle_scrape(args)
    elif args.rank:
        handle_rank(args)
    elif args.player:
        handle_player(args)
    elif args.top_targets:
        handle_top_targets(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
