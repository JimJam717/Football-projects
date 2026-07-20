import csv
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

try:
    from collect_since_gw2 import MATCH_TARGETS
except Exception:
    MATCH_TARGETS = []

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
REPORT_DIR = BASE_DIR / "reports" / "phase2_basic_results"


PATTERNS = {
    "racism_or_discrimination_discussion": [
        r"\bracist\b",
        r"\bracism\b",
        r"\bxenophob(?:e|ia|ic)\b",
        r"\bdiscriminat(?:e|ed|ion|ory)\b",
        r"\bbigot(?:ry|ed)?\b",
    ],
    "severe_identity_slur": [
        r"\bn[i1]gg(?:a|er|as|ers)\b",
        r"\bch[i1]nk(?:s)?\b",
        r"\bp[a@]k[i1](?:s)?\b",
        r"\bsp[i1]c(?:s)?\b",
        r"\bk[i1]ke(?:s)?\b",
        r"\bcoon(?:s)?\b",
        r"\bgook(?:s)?\b",
    ],
    "identity_targeted_context": [
        r"\bimmigrant(?:s)?\b",
        r"\bforeign(?:er|ers)?\b",
        r"\brefugee(?:s)?\b",
        r"\barab(?:s)?\b",
        r"\bmuslim(?:s)?\b",
        r"\bafrican(?:s)?\b",
        r"\bblack(?:s)?\b",
        r"\bwhite(?:s)?\b",
        r"\basian(?:s)?\b",
    ],
    "abusive_or_hard_language": [
        r"\bfuck(?:ing|ed|s)?\b",
        r"\bshit(?:ty)?\b",
        r"\bcunt(?:s)?\b",
        r"\basshole(?:s)?\b",
        r"\bidiot(?:s|ic)?\b",
        r"\bmoron(?:s|ic)?\b",
        r"\btrash\b",
        r"\bgarbage\b",
        r"\bclown(?:s)?\b",
        r"\bpathetic\b",
        r"\bdisgrace(?:ful)?\b",
        r"\bdisgusting\b",
    ],
    "negative_match_tone": [
        r"\bhate(?:d|s)?\b",
        r"\bawful\b",
        r"\bterrible\b",
        r"\bhorrible\b",
        r"\bworst\b",
        r"\bfraud(?:s)?\b",
        r"\bcorrupt(?:ion|ed)?\b",
        r"\brigged\b",
        r"\brobbed\b",
    ],
}

COMPILED_PATTERNS = {
    category: [re.compile(pattern, flags=re.IGNORECASE) for pattern in patterns]
    for category, patterns in PATTERNS.items()
}


def read_jsonl(path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def load_match_ids():
    match_ids = set()
    with (BASE_DIR / "config" / "schedule.json").open("r", encoding="utf-8") as handle:
        schedule = json.load(handle)
    match_ids.update(match["match_id"] for match in schedule)
    match_ids.update(match["match_id"] for match in MATCH_TARGETS)
    return sorted(match_ids, key=len, reverse=True)


def parse_raw_filename(path, match_ids):
    stem = path.stem
    match_id = next((candidate for candidate in match_ids if stem.startswith(candidate + "_")), None)
    if not match_id:
        return None

    remainder = stem[len(match_id) + 1 :]
    if remainder.endswith("_comments"):
        return match_id, remainder[: -len("_comments")], "comments"
    if remainder.endswith("_posts"):
        return match_id, remainder[: -len("_posts")], "posts"
    return match_id, remainder, "records"


def text_from_record(record):
    if isinstance(record.get("record"), dict):
        nested = record["record"]
        return (
            nested.get("text")
            or nested.get("body")
            or nested.get("selftext")
            or nested.get("title")
            or ""
        )
    return record.get("text") or record.get("body") or record.get("selftext") or record.get("title") or ""


def matched_categories(text):
    matches = []
    for category, patterns in COMPILED_PATTERNS.items():
        if any(pattern.search(text) for pattern in patterns):
            matches.append(category)
    return matches


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def chart_color(index):
    palette = ["#dc2626", "#ea580c", "#9333ea", "#2563eb", "#16a34a", "#0891b2"]
    return palette[index % len(palette)]


def write_horizontal_bar_svg(path, title, rows, label_key, value_key, width=980):
    row_height = 34
    top = 74
    left_label_width = 315
    right_padding = 110
    bar_area = width - left_label_width - right_padding
    height = max(170, top + len(rows) * row_height + 38)
    max_value = max((int(row[value_key]) for row in rows), default=1)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="28" y="38" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#111827">{html.escape(title)}</text>',
        '<text x="28" y="60" font-family="Arial, sans-serif" font-size="13" fill="#6b7280">Conservative keyword scan; flags are not classifier labels</text>',
    ]

    for index, row in enumerate(rows):
        y = top + index * row_height
        value = int(row[value_key])
        bar_width = max(2, int((value / max_value) * bar_area))
        label = str(row[label_key]).replace("_", " ")
        parts.extend(
            [
                f'<text x="28" y="{y + 21}" font-family="Arial, sans-serif" font-size="13" fill="#111827">{html.escape(label)}</text>',
                f'<rect x="{left_label_width}" y="{y + 7}" width="{bar_width}" height="20" rx="3" fill="{chart_color(index)}"/>',
                f'<text x="{left_label_width + bar_width + 8}" y="{y + 22}" font-family="Arial, sans-serif" font-size="13" fill="#374151">{value:,}</text>',
            ]
        )

    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    match_ids = load_match_ids()

    total_records = 0
    flagged_records = 0
    category_counts = Counter()
    match_counts = defaultdict(lambda: {"match_id": "", "total_records": 0, "flagged_records": 0})
    source_counts = defaultdict(lambda: {"source": "", "total_records": 0, "flagged_records": 0})

    for path in sorted(RAW_DIR.rglob("*.jsonl")):
        parsed = parse_raw_filename(path, match_ids)
        if not parsed:
            continue

        match_id, source, record_type = parsed
        for record in read_jsonl(path):
            text = text_from_record(record)
            if not text:
                continue

            total_records += 1
            match_counts[match_id]["match_id"] = match_id
            match_counts[match_id]["total_records"] += 1
            source_counts[source]["source"] = source
            source_counts[source]["total_records"] += 1

            categories = matched_categories(text)
            if not categories:
                continue

            flagged_records += 1
            match_counts[match_id]["flagged_records"] += 1
            source_counts[source]["flagged_records"] += 1
            for category in categories:
                category_counts[category] += 1

    summary_rows = [
        {
            "category": category,
            "flagged_records": count,
            "share_of_all_records_pct": round((count / total_records) * 100, 3) if total_records else 0,
        }
        for category, count in category_counts.most_common()
    ]
    match_rows = []
    for row in match_counts.values():
        total = row["total_records"]
        flagged = row["flagged_records"]
        match_rows.append(
            {
                **row,
                "flagged_share_pct": round((flagged / total) * 100, 3) if total else 0,
            }
        )
    match_rows.sort(key=lambda row: row["flagged_records"], reverse=True)

    source_rows = []
    for row in source_counts.values():
        total = row["total_records"]
        flagged = row["flagged_records"]
        source_rows.append(
            {
                **row,
                "flagged_share_pct": round((flagged / total) * 100, 3) if total else 0,
            }
        )
    source_rows.sort(key=lambda row: row["flagged_records"], reverse=True)

    overview_rows = [
        {"metric": "total_records_scanned", "value": total_records},
        {"metric": "records_with_any_flag", "value": flagged_records},
        {
            "metric": "records_with_any_flag_share_pct",
            "value": round((flagged_records / total_records) * 100, 3) if total_records else 0,
        },
    ]

    write_csv(REPORT_DIR / "sensitive_language_overview.csv", overview_rows, ["metric", "value"])
    write_csv(REPORT_DIR / "sensitive_language_by_category.csv", summary_rows, ["category", "flagged_records", "share_of_all_records_pct"])
    write_csv(REPORT_DIR / "sensitive_language_by_match.csv", match_rows, ["match_id", "total_records", "flagged_records", "flagged_share_pct"])
    write_csv(REPORT_DIR / "sensitive_language_by_source.csv", source_rows, ["source", "total_records", "flagged_records", "flagged_share_pct"])

    write_horizontal_bar_svg(
        REPORT_DIR / "sensitive_language_by_category.svg",
        "Sensitive / Hard Language Flags by Category",
        summary_rows,
        "category",
        "flagged_records",
    )
    write_horizontal_bar_svg(
        REPORT_DIR / "sensitive_language_by_match.svg",
        "Sensitive / Hard Language Flags by Match",
        match_rows,
        "match_id",
        "flagged_records",
    )

    notes = f"""# Sensitive Language Scan

This is a conservative keyword scan over raw JSONL text. It is useful for an early distribution slide, but it is not a hate-speech classifier and it does not replace sentiment analysis.

## Headline

- Total records scanned: {total_records:,}
- Records with at least one flag: {flagged_records:,}
- Share with at least one flag: {(flagged_records / total_records * 100) if total_records else 0:.3f}%

## Use in the meeting

- Say: "We ran a preliminary keyword scan for hostile, abusive, and identity-targeted terms."
- Say: "The scan finds flags, but these are context-dependent and need manual review before being treated as racist incidents."
- Say: "Sentiment scoring is separate and still needs to be regenerated."
"""
    (REPORT_DIR / "sensitive_language_notes.md").write_text(notes, encoding="utf-8")

    print(f"Scanned {total_records:,} records")
    print(f"Flagged {flagged_records:,} records")
    print(f"Wrote sensitive-language outputs to {REPORT_DIR}")


if __name__ == "__main__":
    main()
