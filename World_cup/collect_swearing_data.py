import argparse
import json
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from swearing_pipeline import (
    DATA_COLLECTED_DIR,
    MATCH_CONFIG_PATH,
    TEAM_CONFIG_PATH,
    load_configs,
    match_subreddits,
    validate_configs,
    write_csv,
)


COMMENTS_URL = "https://arctic-shift.photon-reddit.com/api/comments/search"
REQUEST_TIMEOUT_SECONDS = 30
PAGE_LIMIT = 100
PAGE_SLEEP_SECONDS = (2, 3)
SUBREDDIT_SLEEP_SECONDS = (10, 15)
DEFAULT_WINDOW_HOURS = 36
MIN_ZERO_RESULT_WARNING_PAGES = 1


def parse_args():
    parser = argparse.ArgumentParser(description="Collect flat Reddit comment JSONL for swearing analysis.")
    parser.add_argument("--match-config", default=MATCH_CONFIG_PATH)
    parser.add_argument("--team-config", default=TEAM_CONFIG_PATH)
    parser.add_argument("--output-dir", default=DATA_COLLECTED_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--match-id")
    parser.add_argument("--window-hours", type=int, default=DEFAULT_WINDOW_HOURS)
    parser.add_argument("--per-subreddit-cap", type=int, default=5000)
    parser.add_argument("--status-path", default=Path(DATA_COLLECTED_DIR) / "collection_status.csv")
    parser.add_argument("--duplicates-path", default=Path(DATA_COLLECTED_DIR) / "duplicate_comment_ids.csv")
    parser.add_argument("--quiet-progress", action="store_true")
    return parser.parse_args()


def day_window(date_value, window_hours):
    start = datetime.fromisoformat(f"{date_value}T00:00:00+00:00")
    end = datetime.fromtimestamp(start.timestamp() + window_hours * 3600, tz=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


def iso_utc(timestamp):
    return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def format_elapsed(start_time):
    elapsed = int(time.monotonic() - start_time)
    minutes, seconds = divmod(elapsed, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{seconds:02d}s"
    return f"{minutes}m{seconds:02d}s"


def progress_line(enabled, message, final=False):
    if not enabled:
        return
    print(message.ljust(140), end="\n" if final else "\r", flush=True)


def request_page(params, max_attempts=3):
    url = f"{COMMENTS_URL}?{urlencode(params)}"
    for attempt in range(1, max_attempts + 1):
        try:
            request = Request(url, headers={"User-Agent": "swearing-world-cup/1.0"})
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8")), None
        except HTTPError as exc:
            body = exc.read(500).decode("utf-8", "replace")
            return None, f"HTTP {exc.code}: {body} ({url})"
        except (URLError, TimeoutError) as exc:
            if attempt == max_attempts:
                return None, f"connection_error: {exc}"
            time.sleep(2**attempt)
            continue
        except json.JSONDecodeError as exc:
            return None, f"json_error: {exc}"
    return None, "unknown_error"


def flat_comment(match_id, subreddit, record):
    comment_id = record.get("id") or str(record.get("name") or "").removeprefix("t1_")
    return {
        "match_id": match_id,
        "subreddit": subreddit,
        "comment_id": comment_id,
        "author": record.get("author"),
        "timestamp": record.get("created_utc"),
        "text": record.get("body") or "",
    }


def load_seen_comment_ids(output_path):
    seen = set()
    if not output_path.exists():
        return seen
    with output_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("comment_id"):
                seen.add(row["comment_id"])
    return seen


def collect_match_subreddit(
    match,
    subreddit,
    output_file,
    seen_ids,
    window_hours,
    cap,
    progress_enabled=True,
    subreddit_position=None,
    subreddit_total=None,
):
    after, before = day_window(match["date"], window_hours)
    current_after = after
    written = 0
    fetched = 0
    duplicates_in_file = 0
    pages = 0
    start_time = time.monotonic()

    while written < cap:
        params = {
            "subreddit": subreddit,
            "after": current_after,
            "before": before,
            "limit": PAGE_LIMIT,
            "sort": "asc",
        }
        data, error = request_page(params)
        pages += 1
        if error:
            progress_line(
                progress_enabled,
                (
                    f"{match['match_id']} r/{subreddit} {subreddit_position or '?'}/{subreddit_total or '?'} | "
                    f"page {pages} | new {written}/{cap} | fetched {fetched} | "
                    f"error | elapsed {format_elapsed(start_time)}"
                ),
                final=True,
            )
            return {
                "new_comments": written,
                "fetched_comments": fetched,
                "duplicates_in_match_file": duplicates_in_file,
                "pages": pages,
                "stop_reason": error,
                "window_start_utc": iso_utc(after),
                "window_end_utc": iso_utc(before),
            }

        records = data.get("data") or []
        fetched += len(records)
        progress_line(
            progress_enabled,
            (
                f"{match['match_id']} r/{subreddit} {subreddit_position or '?'}/{subreddit_total or '?'} | "
                f"page {pages} | new {written}/{cap} | fetched {fetched} | "
                f"dupes {duplicates_in_file} | elapsed {format_elapsed(start_time)}"
            ),
        )
        if not records:
            progress_line(
                progress_enabled,
                (
                    f"{match['match_id']} r/{subreddit} {subreddit_position or '?'}/{subreddit_total or '?'} | "
                    f"done exhaustion | pages {pages} | new {written} | fetched {fetched} | "
                    f"elapsed {format_elapsed(start_time)}"
                ),
                final=True,
            )
            return {
                "new_comments": written,
                "fetched_comments": fetched,
                "duplicates_in_match_file": duplicates_in_file,
                "pages": pages,
                "stop_reason": "exhaustion",
                "window_start_utc": iso_utc(after),
                "window_end_utc": iso_utc(before),
            }

        for record in records:
            row = flat_comment(match["match_id"], subreddit, record)
            comment_id = row.get("comment_id")
            if not comment_id:
                continue
            if comment_id in seen_ids:
                duplicates_in_file += 1
                continue
            seen_ids.add(comment_id)
            output_file.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1
            if written >= cap:
                progress_line(
                    progress_enabled,
                    (
                        f"{match['match_id']} r/{subreddit} {subreddit_position or '?'}/{subreddit_total or '?'} | "
                        f"done cap | pages {pages} | new {written} | fetched {fetched} | "
                        f"elapsed {format_elapsed(start_time)}"
                    ),
                    final=True,
                )
                return {
                    "new_comments": written,
                    "fetched_comments": fetched,
                    "duplicates_in_match_file": duplicates_in_file,
                    "pages": pages,
                    "stop_reason": "cap",
                    "window_start_utc": iso_utc(after),
                    "window_end_utc": iso_utc(before),
                }

        next_after = records[-1].get("created_utc", current_after)
        if int(next_after) == int(current_after):
            progress_line(
                progress_enabled,
                (
                    f"{match['match_id']} r/{subreddit} {subreddit_position or '?'}/{subreddit_total or '?'} | "
                    f"done exhaustion | pages {pages} | new {written} | fetched {fetched} | "
                    f"elapsed {format_elapsed(start_time)}"
                ),
                final=True,
            )
            return {
                "new_comments": written,
                "fetched_comments": fetched,
                "duplicates_in_match_file": duplicates_in_file,
                "pages": pages,
                "stop_reason": "exhaustion",
                "window_start_utc": iso_utc(after),
                "window_end_utc": iso_utc(before),
            }
        current_after = int(next_after)
        sleep_seconds = random.uniform(*PAGE_SLEEP_SECONDS)
        progress_line(
            progress_enabled,
            (
                f"{match['match_id']} r/{subreddit} {subreddit_position or '?'}/{subreddit_total or '?'} | "
                f"page {pages} | new {written}/{cap} | fetched {fetched} | "
                f"sleep {sleep_seconds:.1f}s | elapsed {format_elapsed(start_time)}"
            ),
        )
        time.sleep(sleep_seconds)

    progress_line(
        progress_enabled,
        (
            f"{match['match_id']} r/{subreddit} {subreddit_position or '?'}/{subreddit_total or '?'} | "
            f"done cap | pages {pages} | new {written} | fetched {fetched} | "
            f"elapsed {format_elapsed(start_time)}"
        ),
        final=True,
    )
    return {
        "new_comments": written,
        "fetched_comments": fetched,
        "duplicates_in_match_file": duplicates_in_file,
        "pages": pages,
        "stop_reason": "cap",
        "window_start_utc": iso_utc(after),
        "window_end_utc": iso_utc(before),
    }


def write_duplicate_report(output_dir, duplicates_path):
    comment_matches = defaultdict(set)
    for jsonl_path in sorted(Path(output_dir).glob("*.jsonl")):
        match_id = jsonl_path.stem
        with jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                comment_id = row.get("comment_id")
                if comment_id:
                    comment_matches[comment_id].add(match_id)

    duplicate_rows = [
        {
            "comment_id": comment_id,
            "match_count": len(match_ids),
            "match_ids": ";".join(sorted(match_ids)),
        }
        for comment_id, match_ids in sorted(comment_matches.items())
        if len(match_ids) > 1
    ]
    write_csv(duplicates_path, duplicate_rows, fieldnames=["comment_id", "match_count", "match_ids"])
    return len(duplicate_rows)


def main():
    args = parse_args()
    match_config, team_config = load_configs(args.match_config, args.team_config)
    errors, warnings, _coverage = validate_configs(match_config, team_config)
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    matches = match_config.get("matches") or []
    if args.match_id:
        matches = [match for match in matches if match.get("match_id") == args.match_id]
        if not matches:
            print(f"ERROR: unknown match_id {args.match_id}", file=sys.stderr)
            return 1

    expanded = [
        {
            "match_id": match["match_id"],
            "team_a": match["team_a"],
            "team_b": match["team_b"],
            "window_start_utc": iso_utc(day_window(match["date"], args.window_hours)[0]),
            "window_end_utc": iso_utc(day_window(match["date"], args.window_hours)[1]),
            "subreddits": ";".join(match_subreddits(match, match_config, team_config)),
        }
        for match in matches
    ]
    if args.dry_run:
        write_csv(Path(args.output_dir) / "collection_dry_run_subreddits.csv", expanded)
        print(f"Dry run wrote {len(expanded)} match subreddit expansions.")
        return 0

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    grand_total = 0
    status_rows = []
    try:
        for match_index, match in enumerate(matches, start=1):
            subreddits = match_subreddits(match, match_config, team_config)
            output_path = output_dir / f"{match['match_id']}.jsonl"
            seen_ids = load_seen_comment_ids(output_path)
            match_total = 0
            print(
                f"\n=== {match['match_id']} ({match_index}/{len(matches)}) | "
                f"{match['team_a']} vs {match['team_b']} | {len(subreddits)} subreddits ===",
                flush=True,
            )
            with output_path.open("a", encoding="utf-8") as output_file:
                for index, subreddit in enumerate(subreddits):
                    result = collect_match_subreddit(
                        match,
                        subreddit,
                        output_file,
                        seen_ids,
                        args.window_hours,
                        args.per_subreddit_cap,
                        progress_enabled=not args.quiet_progress,
                        subreddit_position=index + 1,
                        subreddit_total=len(subreddits),
                    )
                    output_file.flush()
                    written = result["new_comments"]
                    pages = result["pages"]
                    stop_reason = result["stop_reason"]
                    match_total += written
                    grand_total += written
                    status_row = {
                        "match_id": match["match_id"],
                        "team_a": match["team_a"],
                        "team_b": match["team_b"],
                        "subreddit": subreddit,
                        "window_start_utc": result["window_start_utc"],
                        "window_end_utc": result["window_end_utc"],
                        "pages": pages,
                        "fetched_comments": result["fetched_comments"],
                        "new_comments": written,
                        "duplicates_in_match_file": result["duplicates_in_match_file"],
                        "stop_reason": stop_reason,
                        "status": "ok",
                    }
                    if stop_reason not in ("exhaustion", "cap"):
                        status_row["status"] = "error"
                    elif written == 0 and pages >= MIN_ZERO_RESULT_WARNING_PAGES:
                        status_row["status"] = "empty"
                    status_rows.append(status_row)
                    write_csv(args.status_path, status_rows)
                    print(
                        f"{match['match_id']} | r/{subreddit} | pages={pages} | "
                        f"new_comments={written} | stop={stop_reason}",
                        flush=True,
                    )
                    if stop_reason not in ("exhaustion", "cap"):
                        print(f"WARNING: collection issue for {match['match_id']}/r/{subreddit}: {stop_reason}")
                    if index < len(subreddits) - 1:
                        sleep_seconds = random.uniform(*SUBREDDIT_SLEEP_SECONDS)
                        print(f"sleeping {sleep_seconds:.1f}s before next subreddit...", flush=True)
                        time.sleep(sleep_seconds)
            print(f"match total new comments: {match_total}", flush=True)
    except KeyboardInterrupt:
        if status_rows:
            write_csv(args.status_path, status_rows)
        print("\nInterrupted. Partial JSONL/status files were left in data/collected for resume or cleanup.")
        return 130

    duplicate_count = write_duplicate_report(output_dir, args.duplicates_path)
    print(f"Cross-match duplicate comment ids: {duplicate_count}")
    print(f"\nGrand total new comments: {grand_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
