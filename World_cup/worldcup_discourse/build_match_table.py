"""
build_match_table.py
====================
Joins per-match CSVs from reports/phase2_basic_results/ into a single
analysis-ready table at reports/analysis/match_table.csv.

Input files
-----------
reports/phase2_basic_results/raw_volume_by_match.csv
    Columns: match_id, posts, comments, records, total

reports/phase2_basic_results/mention_rows_by_match.csv
    Columns: match_id, mention_rows

reports/phase2_basic_results/sentiment_by_match.csv
    Columns: match_id, negative, neutral, positive, error, total, ...

reports/phase2_basic_results/flagged_comments/abusive_or_hard_language.csv
reports/phase2_basic_results/flagged_comments/identity_or_discrimination_context.csv
reports/phase2_basic_results/flagged_comments/negative_match_tone.csv
reports/phase2_basic_results/flagged_comments/severe_identity_slur.csv
    All share columns: match_id, source, flag_level, ...
    flag_level values used as category keys:
        abusive_or_hard_language
        identity_targeted_context
        racism_or_discrimination_discussion
        negative_match_tone
        severe_identity_slur

Output
------
reports/analysis/match_table.csv
    One row per match_id with the columns listed below (see OUTPUT_COLUMNS).
"""

import csv
import os
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPORTS_DIR = SCRIPT_DIR / "reports" / "phase2_basic_results"
FLAGGED_DIR = REPORTS_DIR / "flagged_comments"
OUTPUT_DIR = SCRIPT_DIR / "reports" / "analysis"
OUTPUT_FILE = OUTPUT_DIR / "match_table.csv"

RAW_VOLUME_CSV = REPORTS_DIR / "raw_volume_by_match.csv"
MENTION_ROWS_CSV = REPORTS_DIR / "mention_rows_by_match.csv"
SENTIMENT_CSV = REPORTS_DIR / "sentiment_by_match.csv"

# Flagged-category CSVs: (filename, [flag_level values to count from this file])
FLAGGED_CSVS = [
    (FLAGGED_DIR / "abusive_or_hard_language.csv",
     ["abusive_or_hard_language"]),
    (FLAGGED_DIR / "identity_or_discrimination_context.csv",
     ["identity_targeted_context", "racism_or_discrimination_discussion"]),
    (FLAGGED_DIR / "negative_match_tone.csv",
     ["negative_match_tone"]),
    (FLAGGED_DIR / "severe_identity_slur.csv",
     ["severe_identity_slur"]),
]

# All flag-level category names (defines output column order)
FLAG_CATEGORIES = [
    "abusive_or_hard_language",
    "negative_match_tone",
    "identity_targeted_context",
    "racism_or_discrimination_discussion",
    "severe_identity_slur",
]

# Output column order
OUTPUT_COLUMNS = (
    ["match_id", "total_rows", "mention_rows",
     "sentiment_neg", "sentiment_neu", "sentiment_pos"]
    + [f"flag_{c}" for c in FLAG_CATEGORIES]
    + ["source_breakdown", "subreddit_breakdown"]
    + ["outcome", "nation"]
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_csv(path: Path) -> list[dict]:
    """Read a CSV file and return a list of row dicts. Skips blank rows."""
    with open(path, newline="", encoding="utf-8") as fh:
        return [row for row in csv.DictReader(fh) if any(row.values())]


def int_or_zero(value: str) -> int:
    """Convert a string to int, returning 0 on empty/invalid input."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# Load base data
# ---------------------------------------------------------------------------

def load_raw_volume() -> dict[str, dict]:
    """Returns {match_id: {total_rows: int, ...}} from raw_volume_by_match."""
    data = {}
    for row in read_csv(RAW_VOLUME_CSV):
        mid = row["match_id"].strip()
        data[mid] = {"total_rows": int_or_zero(row.get("total", ""))}
    return data


def load_mention_rows() -> dict[str, int]:
    """Returns {match_id: mention_rows} from mention_rows_by_match."""
    return {
        row["match_id"].strip(): int_or_zero(row.get("mention_rows", ""))
        for row in read_csv(MENTION_ROWS_CSV)
    }


def load_sentiment() -> dict[str, dict]:
    """Returns {match_id: {sentiment_neg, sentiment_neu, sentiment_pos}}."""
    data = {}
    for row in read_csv(SENTIMENT_CSV):
        mid = row["match_id"].strip()
        data[mid] = {
            "sentiment_neg": int_or_zero(row.get("negative", "")),
            "sentiment_neu": int_or_zero(row.get("neutral", "")),
            "sentiment_pos": int_or_zero(row.get("positive", "")),
        }
    return data


# ---------------------------------------------------------------------------
# Load flagged-category counts
# ---------------------------------------------------------------------------

def load_flagged_counts() -> tuple[
    dict[str, dict[str, int]],   # flag_counts[match_id][category] = n
    dict[str, dict[str, int]],   # source_counts[match_id][source] = n
]:
    """
    Iterates over all flagged CSVs and accumulates per-match flag-level
    counts and per-match source counts.

    The ``flag_level`` column on each row carries the category name used
    for aggregation (e.g. ``abusive_or_hard_language``).  A single row may
    be multi-tagged in the ``categories`` column but we key on ``flag_level``
    which is the primary classification assigned during phase-2.
    """
    # {match_id: {flag_category: count}}
    flag_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # {match_id: {source: count}}
    source_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for csv_path, expected_levels in FLAGGED_CSVS:
        if not csv_path.exists():
            print(f"  [WARN] File not found, skipping: {csv_path}")
            continue

        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if not any(row.values()):
                    continue  # blank row

                mid = row.get("match_id", "").strip()
                if not mid:
                    continue

                flag_level = row.get("flag_level", "").strip()
                source = row.get("source", "").strip()

                # Count flag by its flag_level value
                if flag_level in expected_levels:
                    flag_counts[mid][flag_level] += 1

                # Count source presence regardless of category
                if source:
                    source_counts[mid][source] += 1

    return flag_counts, source_counts


# ---------------------------------------------------------------------------
# Build and write table
# ---------------------------------------------------------------------------

def format_breakdown(counter: dict[str, int]) -> str:
    """Format a {key: count} dict as 'key1=n1; key2=n2' sorted by count desc."""
    if not counter:
        return ""
    parts = sorted(counter.items(), key=lambda kv: kv[1], reverse=True)
    return "; ".join(f"{k}={v}" for k, v in parts)


def build_table() -> list[dict]:
    print("Loading raw_volume_by_match.csv …")
    raw_volume = load_raw_volume()

    print("Loading mention_rows_by_match.csv …")
    mention_rows = load_mention_rows()

    print("Loading sentiment_by_match.csv …")
    sentiment = load_sentiment()

    print("Loading flagged-category CSVs …")
    flag_counts, source_counts = load_flagged_counts()

    # Union of all match IDs seen across any input file
    all_match_ids: set[str] = (
        set(raw_volume)
        | set(mention_rows)
        | set(sentiment)
        | set(flag_counts)
    )

    rows = []
    for mid in sorted(all_match_ids):
        row: dict = {"match_id": mid}

        # Volume
        row["total_rows"] = raw_volume.get(mid, {}).get("total_rows", 0)

        # Mention rows
        row["mention_rows"] = mention_rows.get(mid, 0)

        # Sentiment
        sent = sentiment.get(mid, {})
        row["sentiment_neg"] = sent.get("sentiment_neg", "")
        row["sentiment_neu"] = sent.get("sentiment_neu", "")
        row["sentiment_pos"] = sent.get("sentiment_pos", "")

        # Flag counts per category
        fc = flag_counts.get(mid, {})
        for cat in FLAG_CATEGORIES:
            row[f"flag_{cat}"] = fc.get(cat, 0)

        # Source / subreddit breakdown (same data; subreddits *are* the sources)
        breakdown = format_breakdown(source_counts.get(mid, {}))
        row["source_breakdown"] = breakdown
        row["subreddit_breakdown"] = breakdown  # alias; fill same value

        # Blank columns for manual entry
        row["outcome"] = ""
        row["nation"] = ""

        rows.append(row)

    return rows


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = build_table()

    print(f"Writing {len(rows)} rows to {OUTPUT_FILE} …")
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print("Done.")
    print(f"  Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
