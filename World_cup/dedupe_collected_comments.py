import argparse
import json
from collections import defaultdict
from pathlib import Path

from swearing_pipeline import DATA_COLLECTED_DIR, MATCH_CONFIG_PATH, load_json, write_csv, write_json


def parse_args():
    parser = argparse.ArgumentParser(description="Remove duplicate Reddit comment IDs from collected match JSONLs.")
    parser.add_argument("--match-config", default=MATCH_CONFIG_PATH)
    parser.add_argument("--input-dir", default=DATA_COLLECTED_DIR)
    parser.add_argument("--report-path", default=Path(DATA_COLLECTED_DIR) / "dedupe_report.json")
    parser.add_argument("--duplicates-path", default=Path(DATA_COLLECTED_DIR) / "duplicate_comment_ids.csv")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def ordered_match_files(match_config, input_dir):
    input_dir = Path(input_dir)
    files = []
    for match in match_config.get("matches") or []:
        path = input_dir / f"{match['match_id']}.jsonl"
        if path.exists():
            files.append(path)
    extra_files = sorted(
        path
        for path in input_dir.glob("*.jsonl")
        if path not in files
    )
    return files + extra_files


def read_jsonl(path):
    with Path(path).open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} invalid JSON: {exc}") from exc


def write_rows(path, rows):
    path = Path(path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp_path.replace(path)


def build_duplicate_report(input_dir, duplicates_path):
    comment_matches = defaultdict(set)
    for path in sorted(Path(input_dir).glob("*.jsonl")):
        for row in read_jsonl(path):
            comment_id = row.get("comment_id")
            if comment_id:
                comment_matches[comment_id].add(path.stem)

    rows = [
        {
            "comment_id": comment_id,
            "match_count": len(match_ids),
            "match_ids": ";".join(sorted(match_ids)),
        }
        for comment_id, match_ids in sorted(comment_matches.items())
        if len(match_ids) > 1
    ]
    write_csv(duplicates_path, rows, fieldnames=["comment_id", "match_count", "match_ids"])
    return len(rows)


def dedupe_collected(match_config, input_dir, dry_run=False):
    seen_comment_ids = set()
    file_summaries = []
    total_before = 0
    total_after = 0
    total_removed = 0

    for path in ordered_match_files(match_config, input_dir):
        rows_to_keep = []
        before = 0
        removed = 0
        for row in read_jsonl(path):
            before += 1
            comment_id = row.get("comment_id")
            if not comment_id:
                rows_to_keep.append(row)
                continue
            if comment_id in seen_comment_ids:
                removed += 1
                continue
            seen_comment_ids.add(comment_id)
            rows_to_keep.append(row)

        after = len(rows_to_keep)
        total_before += before
        total_after += after
        total_removed += removed
        file_summaries.append(
            {
                "file": path.name,
                "rows_before": before,
                "rows_after": after,
                "duplicates_removed": removed,
            }
        )
        if not dry_run:
            write_rows(path, rows_to_keep)

    return {
        "rows_before": total_before,
        "rows_after": total_after,
        "duplicates_removed": total_removed,
        "dry_run": dry_run,
        "files": file_summaries,
    }


def main():
    args = parse_args()
    match_config = load_json(args.match_config)
    summary = dedupe_collected(match_config, args.input_dir, dry_run=args.dry_run)
    if not args.dry_run:
        remaining_duplicate_ids = build_duplicate_report(args.input_dir, args.duplicates_path)
        summary["remaining_cross_match_duplicate_comment_ids"] = remaining_duplicate_ids
    write_json(args.report_path, summary)
    print(
        f"Rows before={summary['rows_before']} after={summary['rows_after']} "
        f"removed={summary['duplicates_removed']}"
    )
    if not args.dry_run:
        print(f"Remaining duplicate comment ids: {summary['remaining_cross_match_duplicate_comment_ids']}")
    print(f"Wrote report: {args.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
