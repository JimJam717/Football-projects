import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from generate_sensitive_language_scan import PATTERNS, parse_raw_filename, read_jsonl, text_from_record

try:
    from collect_since_gw2 import MATCH_TARGETS
except Exception:
    MATCH_TARGETS = []

try:
    from run_gd3_backlog_sentiment import GD3_BACKLOG_MATCHES
except Exception:
    GD3_BACKLOG_MATCHES = {}


BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
REPORT_DIR = BASE_DIR / "reports" / "phase2_basic_results"
EXPORT_DIR = REPORT_DIR / "flagged_comments"


COMPILED_PATTERNS = {
    category: [re.compile(pattern, flags=re.IGNORECASE) for pattern in patterns]
    for category, patterns in PATTERNS.items()
}


def load_match_ids():
    match_ids = set()
    with (BASE_DIR / "config" / "schedule.json").open("r", encoding="utf-8") as handle:
        schedule = json.load(handle)
    match_ids.update(match["match_id"] for match in schedule)
    match_ids.update(match["match_id"] for match in MATCH_TARGETS)
    match_ids.update(GD3_BACKLOG_MATCHES)
    return sorted(match_ids, key=len, reverse=True)


def csv_safe(value):
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    if text.startswith(("=", "+", "-", "@", "\t")):
        return "'" + text
    return text


def text_preview(text, max_chars=500):
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "..."


def match_details(text):
    category_to_terms = defaultdict(set)
    for category, patterns in COMPILED_PATTERNS.items():
        for pattern in patterns:
            for match in pattern.finditer(text):
                category_to_terms[category].add(match.group(0).lower())

    categories = sorted(category_to_terms)
    matched_terms = {
        category: sorted(terms)
        for category, terms in category_to_terms.items()
    }
    return categories, matched_terms


def flag_level(categories):
    category_set = set(categories)
    if "severe_identity_slur" in category_set:
        return "severe_identity_slur"
    if category_set & {"racism_or_discrimination_discussion", "identity_targeted_context"}:
        return "identity_or_discrimination_context"
    if "negative_match_tone" in category_set:
        return "negative_match_tone"
    return "abusive_or_hard_language"


def record_url(record):
    payload = record_payload(record)
    permalink = payload.get("permalink") or record.get("permalink")
    if permalink and permalink.startswith("/"):
        return "https://www.reddit.com" + permalink
    return permalink or payload.get("url") or record.get("url") or ""


def record_payload(record):
    return record.get("record") if isinstance(record.get("record"), dict) else record


def record_id(record):
    payload = record_payload(record)
    return (
        payload.get("id")
        or payload.get("name")
        or payload.get("record_id")
        or payload.get("uri")
        or payload.get("cid")
        or record.get("id")
        or record.get("uri")
        or ""
    )


def record_value(record, key, default=""):
    payload = record_payload(record)
    return payload.get(key) or record.get(key) or default


def export_rows(rows):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = dedupe_rows(rows)

    jsonl_path = EXPORT_DIR / "flagged_comments_full.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    csv_fields = [
        "match_id",
        "source",
        "record_type",
        "flag_level",
        "categories",
        "matched_terms",
        "created_utc",
        "score",
        "author",
        "record_id",
        "url",
        "text_preview",
    ]
    csv_path = EXPORT_DIR / "flagged_comments_preview.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "match_id": csv_safe(row["match_id"]),
                    "source": csv_safe(row["source"]),
                    "record_type": csv_safe(row["record_type"]),
                    "flag_level": csv_safe(row["flag_level"]),
                    "categories": csv_safe("; ".join(row["categories"])),
                    "matched_terms": csv_safe(json.dumps(row["matched_terms"], ensure_ascii=False)),
                    "created_utc": row.get("created_utc", ""),
                    "score": row.get("score", ""),
                    "author": csv_safe(row.get("author", "")),
                    "record_id": csv_safe(row.get("record_id", "")),
                    "url": csv_safe(row.get("url", "")),
                    "text_preview": csv_safe(text_preview(row.get("text", ""))),
                }
            )

    by_level = defaultdict(list)
    for row in rows:
        by_level[row["flag_level"]].append(row)

    for level, level_rows in by_level.items():
        path = EXPORT_DIR / f"{level}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=csv_fields)
            writer.writeheader()
            for row in level_rows:
                writer.writerow(
                    {
                        "match_id": csv_safe(row["match_id"]),
                        "source": csv_safe(row["source"]),
                        "record_type": csv_safe(row["record_type"]),
                        "flag_level": csv_safe(row["flag_level"]),
                        "categories": csv_safe("; ".join(row["categories"])),
                        "matched_terms": csv_safe(json.dumps(row["matched_terms"], ensure_ascii=False)),
                        "created_utc": row.get("created_utc", ""),
                        "score": row.get("score", ""),
                        "author": csv_safe(row.get("author", "")),
                        "record_id": csv_safe(row.get("record_id", "")),
                        "url": csv_safe(row.get("url", "")),
                        "text_preview": csv_safe(text_preview(row.get("text", ""))),
                    }
                )

    return jsonl_path, csv_path


def dedupe_rows(rows):
    seen = set()
    deduped = []
    for row in rows:
        key = (
            row.get("match_id", ""),
            row.get("created_utc", ""),
            " ".join(str(row.get("text", "")).split()).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def main():
    match_ids = load_match_ids()
    flagged_rows = []

    for path in sorted(RAW_DIR.rglob("*.jsonl")):
        parsed = parse_raw_filename(path, match_ids)
        if not parsed:
            continue

        match_id, source, record_type = parsed
        for record in read_jsonl(path):
            text = text_from_record(record)
            if not text:
                continue

            categories, matched_terms = match_details(text)
            if not categories:
                continue

            flagged_rows.append(
                {
                    "match_id": match_id,
                    "source": source,
                    "record_type": record_type,
                    "flag_level": flag_level(categories),
                    "categories": categories,
                    "matched_terms": matched_terms,
                    "created_utc": record_value(record, "created_utc") or record.get("createdAt") or "",
                    "score": record_value(record, "score") or record_value(record, "ups"),
                    "author": record_value(record, "author") or record.get("author_handle") or "",
                    "record_id": record_id(record),
                    "url": record_url(record),
                    "text": text,
                    "source_file": str(path.relative_to(BASE_DIR)),
                }
            )

    jsonl_path, csv_path = export_rows(flagged_rows)
    print(f"Exported {len(flagged_rows):,} flagged records")
    print(f"Full JSONL: {jsonl_path}")
    print(f"Preview CSV: {csv_path}")
    print(f"Category files: {EXPORT_DIR}")


if __name__ == "__main__":
    main()
