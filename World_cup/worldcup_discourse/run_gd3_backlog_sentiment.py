import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RAW_REDDIT_DIR = BASE_DIR / "data" / "raw" / "reddit"


GD3_BACKLOG_MATCHES = {
    "ecu_vs_ger_gd3": {
        "match_id": "ecu_vs_ger_gd3",
        "nation": "germany",
        "opponent": "Ecuador",
        "date_utc": "2026-06-25",
        "subreddits": ["soccer", "worldcup", "bundesliga"],
    },
    "sco_vs_bra_gd3": {
        "match_id": "sco_vs_bra_gd3",
        "nation": "scotland",
        "opponent": "Brazil",
        "date_utc": "2026-06-24",
        "subreddits": ["soccer", "worldcup", "ScottishFootball"],
    },
    "sui_vs_can_gd3": {
        "match_id": "sui_vs_can_gd3",
        "nation": "switzerland",
        "opponent": "Canada",
        "date_utc": "2026-06-24",
        "subreddits": ["soccer", "worldcup", "SwissFootball", "CanadaSoccer"],
    },
    "tun_vs_ned_gd3": {
        "match_id": "tun_vs_ned_gd3",
        "nation": "netherlands",
        "opponent": "Tunisia",
        "date_utc": "2026-06-25",
        "subreddits": ["soccer", "worldcup", "Eredivisie"],
    },
}


def raw_files_for_match(match_id):
    return sorted(RAW_REDDIT_DIR.glob(f"{match_id}_*.jsonl"))


def raw_file_bytes(match_id):
    return sum(path.stat().st_size for path in raw_files_for_match(match_id))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the sentiment pipeline for raw GD3 backlog matches that do not have processed outputs yet."
    )
    parser.add_argument(
        "--match",
        action="append",
        choices=sorted(GD3_BACKLOG_MATCHES),
        help="Limit to one GD3 backlog match ID. Can be passed more than once.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing processed outputs for selected matches.",
    )
    parser.add_argument(
        "--include-empty",
        action="store_true",
        help="Run matches whose raw files exist but are all empty.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    match_ids = args.match or sorted(GD3_BACKLOG_MATCHES)

    print("Running sentiment pipeline for GD3 backlog matches:", flush=True)
    for match_id in match_ids:
        raw_files = raw_files_for_match(match_id)
        raw_bytes = raw_file_bytes(match_id)
        print(f"  - {match_id}: raw_files={len(raw_files)} raw_bytes={raw_bytes}", flush=True)

    summaries = []
    runnable_match_ids = []
    for match_id in match_ids:
        if raw_file_bytes(match_id) == 0 and not args.include_empty:
            print(f"\n{match_id}: skipped, raw files are empty. Use --include-empty to write empty outputs.", flush=True)
            summaries.append({"match_id": match_id, "skipped_empty": True})
            continue
        runnable_match_ids.append(match_id)

    if runnable_match_ids:
        from run_new_games_sentiment import load_json, process_match

        squads = load_json(BASE_DIR / "config" / "squads.json")

    for match_id in runnable_match_ids:
        summaries.append(
            process_match(
                match_id,
                GD3_BACKLOG_MATCHES[match_id],
                squads,
                force=args.force,
            )
        )

    print("\nSummary", flush=True)
    for summary in summaries:
        if summary.get("skipped_empty"):
            print(f"  {summary['match_id']}: skipped empty raw files", flush=True)
            continue
        if summary.get("skipped_existing"):
            print(f"  {summary['match_id']}: skipped existing sentiment output", flush=True)
            continue
        print(
            f"  {summary['match_id']}: raw_files={summary['raw_files']} "
            f"mentions={summary['mentions']} lang={summary['lang']} sentiment={summary['sentiment']}",
            flush=True,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
