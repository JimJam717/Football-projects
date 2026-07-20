import argparse
from collections import Counter
from pathlib import Path

from swearing_pipeline import (
    ATTRIBUTED_DIR,
    LANGUAGE_DIR,
    MATCH_CONFIG_PATH,
    REPORT_DIR,
    TEAM_CONFIG_PATH,
    build_subreddit_to_country,
    build_unique_language_to_country,
    canonical_language_code,
    iter_jsonl,
    load_configs,
    normalize_subreddit,
    validate_configs,
    validate_phase_fields,
    write_csv,
    write_json,
    write_jsonl,
)


UNATTRIBUTED_BLOCK_THRESHOLD = 0.30


def parse_args():
    parser = argparse.ArgumentParser(description="Attribute comment speaker country using subreddit then language.")
    parser.add_argument("--match-config", default=MATCH_CONFIG_PATH)
    parser.add_argument("--team-config", default=TEAM_CONFIG_PATH)
    parser.add_argument("--input-dir", default=LANGUAGE_DIR)
    parser.add_argument("--output-dir", default=ATTRIBUTED_DIR)
    parser.add_argument("--match-id")
    parser.add_argument("--allow-high-unattributed", action="store_true")
    return parser.parse_args()


def attribute_row(row, subreddit_to_country, unique_language_to_country):
    output = dict(row)
    subreddit_country = subreddit_to_country.get(normalize_subreddit(row.get("subreddit")))
    if subreddit_country:
        output["attributed_country"] = subreddit_country
        output["attribution_tier"] = "tier1_subreddit"
        return output

    language_country = unique_language_to_country.get(canonical_language_code(row.get("detected_language")))
    if language_country:
        output["attributed_country"] = language_country
        output["attribution_tier"] = "tier2_language"
        return output

    output["attributed_country"] = None
    output["attribution_tier"] = None
    return output


def process_file(input_path, output_path, subreddit_to_country, unique_language_to_country):
    rows = []
    counts = Counter()
    country_counts = Counter()
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
            ],
            input_path,
        )
        output = attribute_row(row, subreddit_to_country, unique_language_to_country)
        rows.append(output)
        counts["total_comments"] += 1
        if output["attributed_country"]:
            counts["attributed_comments"] += 1
            counts[output["attribution_tier"]] += 1
            country_counts[output["attributed_country"]] += 1
        else:
            counts["unattributed_comments"] += 1

    write_jsonl(output_path, rows)
    return counts, country_counts


def main():
    args = parse_args()
    match_config, team_config = load_configs(args.match_config, args.team_config)
    errors, warnings, coverage = validate_configs(match_config, team_config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    for warning in warnings:
        print(f"WARNING: {warning}")

    subreddit_to_country = build_subreddit_to_country(team_config)
    unique_language_to_country = build_unique_language_to_country(match_config, team_config)
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    files = sorted(input_dir.glob("*.jsonl"))
    if args.match_id:
        files = [input_dir / f"{args.match_id}.jsonl"]

    total_counts = Counter()
    total_country_counts = Counter()
    for input_path in files:
        if not input_path.exists():
            continue
        counts, country_counts = process_file(
            input_path,
            output_dir / input_path.name,
            subreddit_to_country,
            unique_language_to_country,
        )
        total_counts.update(counts)
        total_country_counts.update(country_counts)
        print(
            f"{input_path.name}: attributed {counts['attributed_comments']} of "
            f"{counts['total_comments']} comments"
        )

    total = total_counts["total_comments"]
    unattributed = total_counts["unattributed_comments"]
    unattributed_rate = (unattributed / total) if total else 0.0

    summary = {
        "total_comments": total,
        "attributed_comments": total_counts["attributed_comments"],
        "unattributed_comments": unattributed,
        "unattributed_rate": unattributed_rate,
        "tier1_subreddit_comments": total_counts["tier1_subreddit"],
        "tier2_language_comments": total_counts["tier2_language"],
        "country_counts": dict(sorted(total_country_counts.items())),
        "coverage": coverage,
    }
    write_json(REPORT_DIR / "attribution_summary.json", summary)
    write_csv(
        REPORT_DIR / "attribution_country_counts.csv",
        [
            {"country_name": country, "attributed_comments": count}
            for country, count in sorted(total_country_counts.items())
        ],
    )

    print(f"Overall unattributed rate: {unattributed_rate:.1%}")
    if total and unattributed_rate >= UNATTRIBUTED_BLOCK_THRESHOLD and not args.allow_high_unattributed:
        print(
            "ERROR: unattributed rate is at or above 30%; review attribution_summary.json "
            "before scoring/ranking."
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
