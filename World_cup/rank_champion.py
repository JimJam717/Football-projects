import argparse
from collections import Counter, defaultdict
from pathlib import Path

from swearing_pipeline import (
    LEADERBOARD_DIR,
    MATCH_CONFIG_PATH,
    SCORED_DIR,
    TEAM_CONFIG_PATH,
    iter_jsonl,
    load_configs,
    validate_configs,
    validate_phase_fields,
    write_csv,
    write_json,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Build the Swearing World Cup leaderboard.")
    parser.add_argument("--match-config", default=MATCH_CONFIG_PATH)
    parser.add_argument("--team-config", default=TEAM_CONFIG_PATH)
    parser.add_argument("--input-dir", default=SCORED_DIR)
    parser.add_argument("--output-dir", default=LEADERBOARD_DIR)
    parser.add_argument("--min-comments", type=int, default=1000)
    parser.add_argument("--min-words", type=int, default=10000)
    return parser.parse_args()


def main():
    args = parse_args()
    match_config, team_config = load_configs(args.match_config, args.team_config)
    errors, _warnings, coverage = validate_configs(match_config, team_config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    coverage_by_country = {row["country_name"]: row for row in coverage}
    totals = defaultdict(Counter)
    attributed_comments = Counter()

    for input_path in sorted(Path(args.input_dir).glob("*.jsonl")):
        for row in iter_jsonl(input_path):
            validate_phase_fields(
                row,
                [
                    "match_id",
                    "subreddit",
                    "comment_id",
                    "author",
                    "timestamp",
                    "text",
                    "detected_language",
                    "attributed_country",
                    "swear_count",
                    "word_count",
                ],
                input_path,
            )
            country = row.get("attributed_country")
            if country:
                attributed_comments[country] += 1
            if not country:
                continue
            coverage_row = coverage_by_country.get(country)
            if not coverage_row or coverage_row["status"] != "eligible":
                continue
            totals[country]["comments"] += 1
            totals[country]["words"] += int(row.get("word_count") or 0)
            totals[country]["swear_hits"] += int(row.get("swear_count") or 0)

    total_attributed_comments = sum(attributed_comments.values())
    rows = []
    for country, counts in totals.items():
        comments = counts["comments"]
        words = counts["words"]
        swear_hits = counts["swear_hits"]
        coverage_row = coverage_by_country.get(country, {})
        rows.append(
            {
                "country_name": country,
                "team_code": coverage_row.get("team_code"),
                "eligibility_status": coverage_row.get("status"),
                "comments": comments,
                "words": words,
                "swear_hits": swear_hits,
                "swears_per_1000_words": round((swear_hits / words) * 1000, 6) if words else 0.0,
                "swears_per_100_comments": round((swear_hits / comments) * 100, 6) if comments else 0.0,
                "attributed_share": round(
                    (attributed_comments[country] / total_attributed_comments), 6
                )
                if total_attributed_comments
                else 0.0,
            }
        )

    for row in rows:
        low_comments = row["comments"] < args.min_comments
        low_words = row["words"] < args.min_words
        row["qualified_for_rank"] = not low_comments and not low_words
        if low_comments and low_words:
            row["sample_status"] = "low_comments_and_words"
        elif low_comments:
            row["sample_status"] = "low_comments"
        elif low_words:
            row["sample_status"] = "low_words"
        else:
            row["sample_status"] = "qualified"
        row["rank"] = ""

    qualified_rows = [row for row in rows if row["qualified_for_rank"]]
    qualified_rows.sort(
        key=lambda row: (row["swears_per_1000_words"], row["swears_per_100_comments"]),
        reverse=True,
    )
    for index, row in enumerate(qualified_rows, start=1):
        row["rank"] = index

    rows.sort(
        key=lambda row: (
            row["qualified_for_rank"],
            row["swears_per_1000_words"],
            row["swears_per_100_comments"],
        ),
        reverse=True,
    )

    output_dir = Path(args.output_dir)
    write_csv(
        output_dir / "swearing_leaderboard.csv",
        rows,
        fieldnames=[
            "rank",
            "qualified_for_rank",
            "sample_status",
            "country_name",
            "team_code",
            "eligibility_status",
            "comments",
            "words",
            "swear_hits",
            "swears_per_1000_words",
            "swears_per_100_comments",
            "attributed_share",
        ],
    )
    write_json(output_dir / "swearing_leaderboard.json", rows)
    print(f"Wrote {len(rows)} leaderboard rows to {output_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
