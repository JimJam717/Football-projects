import argparse
from pathlib import Path

from swearing_pipeline import ATTRIBUTED_DIR, SCORED_DIR, count_swears, iter_jsonl, validate_phase_fields, write_jsonl


def parse_args():
    parser = argparse.ArgumentParser(description="Append swear_count and word_count to attributed comments.")
    parser.add_argument("--input-dir", default=ATTRIBUTED_DIR)
    parser.add_argument("--output-dir", default=SCORED_DIR)
    parser.add_argument("--match-id")
    return parser.parse_args()


def process_file(input_path, output_path):
    rows = []
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
            ],
            input_path,
        )
        output = dict(row)
        swear_count, word_count = count_swears(output.get("text"), output.get("detected_language"))
        output["swear_count"] = swear_count
        output["word_count"] = word_count
        rows.append(output)
    write_jsonl(output_path, rows)
    return len(rows)


def main():
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    files = sorted(input_dir.glob("*.jsonl"))
    if args.match_id:
        files = [input_dir / f"{args.match_id}.jsonl"]

    total = 0
    for input_path in files:
        if not input_path.exists():
            continue
        count = process_file(input_path, output_dir / input_path.name)
        total += count
        print(f"{input_path.name}: scored {count} comments")
    print(f"Total scored comments: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
