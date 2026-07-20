import csv
import html
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
REPORT_DIR = BASE_DIR / "reports" / "phase2_basic_results"
FLAGGED_DIR = REPORT_DIR / "flagged_comments"
AUDIT_DIR = REPORT_DIR / "flagged_context_audit"
SQUADS_PATH = BASE_DIR / "config" / "squads.json"

FOCUS_LEVELS = {"identity_or_discrimination_context", "severe_identity_slur"}
PLAYER_WINDOW_TOKENS = 12
POSSIBLE_PLAYER_WINDOW_TOKENS = 30
ALIAS_STOPWORDS = {
    "black",
    "white",
    "brown",
    "green",
    "gold",
    "beach",
    "rice",
    "david",
    "curtis",
    "gray",
    "grey",
    "rose",
    "king",
    "young",
}

FALSE_POSITIVE_PATTERNS = [
    ("competition_or_region", re.compile(r"\basian\s+cup\b|\basian\s+champions?\s+league\b|\bafrican\s+cup\b|\bafcon\b", re.IGNORECASE)),
    ("kit_or_equipment", re.compile(r"\bwhite\s+(?:socks|shirt|kit|jersey|shorts)\b|\bblack\s+(?:socks|shirt|kit|jersey|shorts|face\s+guy)\b", re.IGNORECASE)),
    ("color_description", re.compile(r"\b(?:black|white)\s+(?:card|line|screen|text|flag|banner|boots)\b|#bar-\d+-white", re.IGNORECASE)),
]

RACISM_DISCUSSION_RE = re.compile(
    r"\bracist\b|\bracism\b|\bxenophob(?:e|ia|ic)\b|\bdiscriminat(?:e|ed|ion|ory)\b|\bbigot(?:ry|ed)?\b",
    re.IGNORECASE,
)

IDENTITY_GROUP_RE = re.compile(
    r"\bimmigrant(?:s)?\b|\bforeign(?:er|ers)?\b|\brefugee(?:s)?\b|\barab(?:s)?\b|\bmuslim(?:s)?\b|"
    r"\bafrican(?:s)?\b|\bblack(?:s)?\b|\bwhite(?:s)?\b|\basian(?:s)?\b",
    re.IGNORECASE,
)


def normalize_text(value):
    normalized = unicodedata.normalize("NFKD", str(value))
    return "".join(char for char in normalized if not unicodedata.combining(char))


def read_jsonl(path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            yield json.loads(line)


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def csv_safe(value):
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    if text.startswith(("=", "+", "-", "@", "\t")):
        return "'" + text
    return text


def text_preview(text, max_chars=360):
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "..."


def flatten_matched_terms(matched_terms):
    terms = []
    if isinstance(matched_terms, dict):
        for category, values in matched_terms.items():
            for value in values:
                terms.append((category, str(value).lower()))
    return terms


def alias_variants(alias):
    variants = {alias}
    ascii_alias = normalize_text(alias)
    variants.add(ascii_alias)
    return sorted(variant for variant in variants if variant.strip())


def load_player_patterns():
    with SQUADS_PATH.open("r", encoding="utf-8") as handle:
        squads = json.load(handle)

    players = []
    seen_aliases = set()
    for nation, roster in squads.items():
        for player in roster:
            name = player.get("name", "")
            aliases = [name] + player.get("aliases", [])
            patterns = []
            for alias in aliases:
                alias = str(alias).strip()
                if not alias:
                    continue
                is_full_name = alias.lower() == name.lower()
                if not is_full_name and alias.lower() in ALIAS_STOPWORDS:
                    continue
                for variant in alias_variants(alias):
                    key = (nation, name, normalize_text(variant).lower())
                    if key in seen_aliases:
                        continue
                    seen_aliases.add(key)
                    patterns.append(re.compile(r"\b" + re.escape(normalize_text(variant)) + r"\b", re.IGNORECASE))
            players.append({"nation": nation, "name": name, "patterns": patterns})
    return players


def token_index_at(text, char_index):
    return len(re.findall(r"\b\w+\b", text[:char_index]))


def extract_player_mentions(text, player_patterns):
    normalized_text = normalize_text(text)
    mentions = []
    seen = set()
    for player in player_patterns:
        for pattern in player["patterns"]:
            for match in pattern.finditer(normalized_text):
                key = (player["nation"], player["name"])
                if key in seen:
                    continue
                seen.add(key)
                mentions.append(
                    {
                        "nation": player["nation"],
                        "name": player["name"],
                        "start": match.start(),
                        "end": match.end(),
                        "token_index": token_index_at(normalized_text, match.start()),
                    }
                )
    return sorted(mentions, key=lambda item: item["start"])


def find_term_positions(text, terms):
    normalized_text = normalize_text(text)
    positions = []
    for category, term in terms:
        pattern = re.compile(r"\b" + re.escape(normalize_text(term)) + r"\b", re.IGNORECASE)
        for match in pattern.finditer(normalized_text):
            positions.append(
                {
                    "category": category,
                    "term": term,
                    "start": match.start(),
                    "end": match.end(),
                    "token_index": token_index_at(normalized_text, match.start()),
                }
            )
    return sorted(positions, key=lambda item: item["start"])


def closest_player_distance(term_positions, player_mentions):
    if not term_positions or not player_mentions:
        return None
    distances = []
    for term in term_positions:
        for mention in player_mentions:
            distances.append(abs(term["token_index"] - mention["token_index"]))
    return min(distances) if distances else None


def review_priority(likely_about_player, target_type):
    if likely_about_player == "yes":
        return 1
    if likely_about_player == "possible" or target_type == "severe_slur_no_player_mention":
        return 2
    if target_type in {"identity_group_or_nation_context", "needs_manual_review"}:
        return 3
    return 4


def classify_context(text, categories, matched_terms, player_mentions, term_positions):
    terms = {term for _, term in matched_terms}
    category_set = set(categories)
    distance = closest_player_distance(term_positions, player_mentions)

    for label, pattern in FALSE_POSITIVE_PATTERNS:
        if pattern.search(text):
            return "no", label, distance

    if (
        "racism_or_discrimination_discussion" in category_set
        or RACISM_DISCUSSION_RE.search(text)
        or any(RACISM_DISCUSSION_RE.search(term) for term in terms)
    ):
        return "no", "racism_discussion_or_callout", distance

    if distance is not None and distance <= PLAYER_WINDOW_TOKENS:
        return "yes", "player_mentioned_near_flag", distance
    if distance is not None and distance <= POSSIBLE_PLAYER_WINDOW_TOKENS:
        return "possible", "player_mentioned_within_wide_window", distance
    if player_mentions:
        return "possible", "player_mentioned_elsewhere", distance

    if "severe_identity_slur" in category_set:
        return "unclear", "severe_slur_no_player_mention", distance

    if IDENTITY_GROUP_RE.search(text):
        return "unclear", "identity_group_or_nation_context", distance

    return "unclear", "needs_manual_review", distance


def chart_color(index):
    palette = ["#dc2626", "#2563eb", "#16a34a", "#ea580c", "#9333ea", "#0891b2", "#64748b"]
    return palette[index % len(palette)]


def write_horizontal_bar_svg(path, title, rows, label_key, value_key, subtitle, width=980):
    rows = [row for row in rows if int(row[value_key]) > 0][:20]
    row_height = 34
    top = 78
    left_label_width = 300
    right_padding = 120
    bar_area = width - left_label_width - right_padding
    height = max(180, top + len(rows) * row_height + 40)
    max_value = max((int(row[value_key]) for row in rows), default=1)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="28" y="38" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<text x="28" y="60" font-family="Arial, sans-serif" font-size="13" fill="#6b7280">{html.escape(subtitle)}</text>',
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


def write_stacked_svg(path, title, rows, label_key, segment_keys, subtitle, width=980):
    rows = rows[:18]
    row_height = 38
    top = 98
    left_label_width = 300
    right_padding = 120
    bar_area = width - left_label_width - right_padding
    height = max(210, top + len(rows) * row_height + 42)
    max_total = max((sum(int(row.get(key, 0)) for key in segment_keys) for row in rows), default=1)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="28" y="38" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<text x="28" y="60" font-family="Arial, sans-serif" font-size="13" fill="#6b7280">{html.escape(subtitle)}</text>',
    ]

    legend_x = left_label_width
    for index, key in enumerate(segment_keys):
        label = key.replace("_", " ")
        parts.extend(
            [
                f'<rect x="{legend_x}" y="72" width="12" height="12" rx="2" fill="{chart_color(index)}"/>',
                f'<text x="{legend_x + 18}" y="83" font-family="Arial, sans-serif" font-size="12" fill="#374151">{html.escape(label)}</text>',
            ]
        )
        legend_x += 140

    for row_index, row in enumerate(rows):
        y = top + row_index * row_height
        total = sum(int(row.get(key, 0)) for key in segment_keys)
        current_x = left_label_width
        parts.append(
            f'<text x="28" y="{y + 23}" font-family="Arial, sans-serif" font-size="13" fill="#111827">{html.escape(str(row[label_key]).replace("_", " "))}</text>'
        )
        for index, key in enumerate(segment_keys):
            value = int(row.get(key, 0))
            segment_width = 0 if total == 0 else int((value / max_total) * bar_area)
            if segment_width > 0:
                parts.append(
                    f'<rect x="{current_x}" y="{y + 8}" width="{segment_width}" height="22" rx="3" fill="{chart_color(index)}"/>'
                )
            current_x += segment_width
        parts.append(
            f'<text x="{left_label_width + int((total / max_total) * bar_area) + 8}" y="{y + 24}" font-family="Arial, sans-serif" font-size="13" fill="#374151">{total:,}</text>'
        )

    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main():
    flagged_path = FLAGGED_DIR / "flagged_comments_full.jsonl"
    if not flagged_path.exists():
        raise FileNotFoundError(f"Missing flagged export: {flagged_path}")

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    player_patterns = load_player_patterns()

    audit_rows = []
    target_counts = Counter()
    review_bucket_counts = Counter()
    review_priority_counts = Counter()
    player_link_counts = Counter()
    term_counts = Counter()
    category_player_link_counts = defaultdict(Counter)
    match_counts = Counter()
    match_player_counts = defaultdict(Counter)
    player_counts = Counter()
    seen_records = set()

    for row in read_jsonl(flagged_path):
        if row.get("flag_level") not in FOCUS_LEVELS:
            continue

        text = row.get("text", "")
        record_key = (
            row.get("match_id", ""),
            row.get("record_id", ""),
            " ".join(text.split()).lower(),
        )
        if record_key in seen_records:
            continue
        seen_records.add(record_key)

        categories = row.get("categories", [])
        matched_terms = flatten_matched_terms(row.get("matched_terms", {}))
        term_positions = find_term_positions(text, matched_terms)
        player_mentions = extract_player_mentions(text, player_patterns)
        likely_about_player, target_type, distance = classify_context(
            text, categories, matched_terms, player_mentions, term_positions
        )
        priority = review_priority(likely_about_player, target_type)

        matched_words = sorted({term for _, term in matched_terms})
        players = sorted({mention["name"] for mention in player_mentions})
        player_nations = sorted({mention["nation"] for mention in player_mentions})

        audit_rows.append(
            {
                "match_id": csv_safe(row.get("match_id", "")),
                "source": csv_safe(row.get("source", "")),
                "record_type": csv_safe(row.get("record_type", "")),
                "flag_level": csv_safe(row.get("flag_level", "")),
                "categories": csv_safe("; ".join(categories)),
                "matched_words": csv_safe("; ".join(matched_words)),
                "likely_about_player": likely_about_player,
                "target_type": target_type,
                "review_priority": priority,
                "closest_flag_to_player_tokens": "" if distance is None else distance,
                "players_mentioned": csv_safe("; ".join(players)),
                "player_nations": csv_safe("; ".join(player_nations)),
                "created_utc": row.get("created_utc", ""),
                "score": row.get("score", ""),
                "author": csv_safe(row.get("author", "")),
                "record_id": csv_safe(row.get("record_id", "")),
                "url": csv_safe(row.get("url", "")),
                "text_preview": csv_safe(text_preview(text)),
            }
        )

        target_counts[target_type] += 1
        review_bucket_counts[target_type] += 1
        review_priority_counts[priority] += 1
        player_link_counts[likely_about_player] += 1
        match_counts[row.get("match_id", "unknown")] += 1
        match_player_counts[row.get("match_id", "unknown")][likely_about_player] += 1
        for category in categories:
            category_player_link_counts[category][likely_about_player] += 1
        for word in matched_words:
            term_counts[word] += 1
        for player in players:
            player_counts[player] += 1

    audit_rows.sort(key=lambda item: (item["likely_about_player"] != "yes", item["match_id"], item["record_id"]))
    write_csv(
        AUDIT_DIR / "flagged_context_audit.csv",
        audit_rows,
        [
            "match_id",
            "source",
            "record_type",
            "flag_level",
            "categories",
            "matched_words",
            "likely_about_player",
            "target_type",
            "review_priority",
            "closest_flag_to_player_tokens",
            "players_mentioned",
            "player_nations",
            "created_utc",
            "score",
            "author",
            "record_id",
            "url",
            "text_preview",
        ],
    )

    target_rows = [{"target_type": key, "records": value} for key, value in target_counts.most_common()]
    review_bucket_rows = [{"review_bucket": key, "records": value} for key, value in review_bucket_counts.most_common()]
    review_priority_rows = [
        {"review_priority": key, "records": review_priority_counts[key]}
        for key in sorted(review_priority_counts)
    ]
    player_link_rows = [
        {"likely_about_player": key, "records": player_link_counts[key]}
        for key in ("yes", "possible", "unclear", "no")
        if player_link_counts[key]
    ]
    term_rows = [{"matched_word": key, "records": value} for key, value in term_counts.most_common(25)]
    match_rows = [{"match_id": key, "records": value} for key, value in match_counts.most_common()]
    player_rows = [{"player": key, "records": value} for key, value in player_counts.most_common(25)]
    category_rows = []
    for category, counts in category_player_link_counts.items():
        category_rows.append(
            {
                "category": category,
                "yes": counts["yes"],
                "possible": counts["possible"],
                "unclear": counts["unclear"],
                "no": counts["no"],
                "total": sum(counts.values()),
            }
        )
    category_rows.sort(key=lambda item: item["total"], reverse=True)
    match_player_rows = []
    for match_id, counts in match_player_counts.items():
        match_player_rows.append(
            {
                "match_id": match_id,
                "yes": counts["yes"],
                "possible": counts["possible"],
                "unclear": counts["unclear"],
                "no": counts["no"],
                "total": sum(counts.values()),
            }
        )
    match_player_rows.sort(key=lambda item: item["total"], reverse=True)

    write_csv(AUDIT_DIR / "target_type_summary.csv", target_rows, ["target_type", "records"])
    write_csv(AUDIT_DIR / "review_bucket_summary.csv", review_bucket_rows, ["review_bucket", "records"])
    write_csv(AUDIT_DIR / "review_priority_summary.csv", review_priority_rows, ["review_priority", "records"])
    write_csv(AUDIT_DIR / "likely_about_player_summary.csv", player_link_rows, ["likely_about_player", "records"])
    write_csv(AUDIT_DIR / "matched_word_summary.csv", term_rows, ["matched_word", "records"])
    write_csv(AUDIT_DIR / "match_summary.csv", match_rows, ["match_id", "records"])
    write_csv(AUDIT_DIR / "category_player_link_summary.csv", category_rows, ["category", "yes", "possible", "unclear", "no", "total"])
    write_csv(AUDIT_DIR / "match_player_link_summary.csv", match_player_rows, ["match_id", "yes", "possible", "unclear", "no", "total"])
    write_csv(AUDIT_DIR / "players_in_flagged_context_summary.csv", player_rows, ["player", "records"])

    manual_review_rows = sorted(
        audit_rows,
        key=lambda item: (
            int(item["review_priority"]),
            -(int(item["score"]) if str(item["score"]).isdigit() else 0),
            item["match_id"],
            item["record_id"],
        ),
    )[:250]
    write_csv(
        AUDIT_DIR / "manual_review_priority_sample.csv",
        manual_review_rows,
        [
            "match_id",
            "source",
            "record_type",
            "flag_level",
            "categories",
            "matched_words",
            "likely_about_player",
            "target_type",
            "review_priority",
            "closest_flag_to_player_tokens",
            "players_mentioned",
            "player_nations",
            "created_utc",
            "score",
            "author",
            "record_id",
            "url",
            "text_preview",
        ],
    )

    subtitle = "Focused on identity/discrimination-context and severe-slur keyword flags; not confirmed labels"
    write_horizontal_bar_svg(AUDIT_DIR / "context_audit_target_type.svg", "Why Identity-Context Rows Were Flagged", target_rows, "target_type", "records", subtitle)
    write_horizontal_bar_svg(AUDIT_DIR / "context_audit_review_buckets.svg", "Manual Review Buckets", review_bucket_rows, "review_bucket", "records", subtitle)
    write_horizontal_bar_svg(AUDIT_DIR / "context_audit_review_priority.svg", "Manual Review Priority", review_priority_rows, "review_priority", "records", subtitle)
    write_horizontal_bar_svg(AUDIT_DIR / "context_audit_likely_about_player.svg", "Were Flagged Rows About a Player?", player_link_rows, "likely_about_player", "records", subtitle)
    write_horizontal_bar_svg(AUDIT_DIR / "context_audit_top_matched_terms.svg", "Top Matched Identity-Context Terms", term_rows, "matched_word", "records", subtitle)
    write_horizontal_bar_svg(AUDIT_DIR / "context_audit_by_match.svg", "Identity-Context Flags by Match", match_rows, "match_id", "records", subtitle)
    write_horizontal_bar_svg(AUDIT_DIR / "context_audit_top_players.svg", "Players Mentioned in Flagged Context", player_rows, "player", "records", subtitle)
    write_stacked_svg(
        AUDIT_DIR / "context_audit_category_by_player_link.svg",
        "Player Link by Flag Category",
        category_rows,
        "category",
        ["yes", "possible", "unclear", "no"],
        subtitle,
    )
    write_stacked_svg(
        AUDIT_DIR / "context_audit_match_by_player_link.svg",
        "Player Link by Match",
        match_player_rows,
        "match_id",
        ["yes", "possible", "unclear", "no"],
        subtitle,
    )

    yes = player_link_counts["yes"]
    possible = player_link_counts["possible"]
    total = len(audit_rows)
    notes = f"""# Flagged Context Audit

This audit focuses on identity/discrimination-context and severe-slur keyword flags.

## Headline

- Focus rows audited: {total:,}
- Likely about a player: {yes:,}
- Possibly about a player: {possible:,}
- Not about a player / contextual false positive: {player_link_counts["no"]:,}
- Unclear without manual review: {player_link_counts["unclear"]:,}

## Manual Review Priority

- Priority 1: likely player-related rows, where a player mention appears within {PLAYER_WINDOW_TOKENS} tokens of a flagged word.
- Priority 2: possible player-related rows or severe-slur rows without an identified player mention.
- Priority 3: broader identity group/nation context or rows that still need manual review.
- Priority 4: contextual false positives and racism/discrimination discussion or callouts.

## Method

- Extracted exact matched words from the existing keyword scan.
- Detected player mentions from `config/squads.json` using exact alias matching with accent-insensitive variants.
- Marked rows as likely player-related when a player mention appears within {PLAYER_WINDOW_TOKENS} tokens of a flagged word.
- Marked rows as possibly player-related when a player mention appears within {POSSIBLE_PLAYER_WINDOW_TOKENS} tokens of a flagged word or elsewhere in the same record.
- Marked obvious contextual cases such as `Asian Cup` or kit/color descriptions separately.
- Excluded a small set of ambiguous one-word aliases such as color words and common nouns/names when they are not full-name matches.

## Caveat

These are audit heuristics, not final labels. Player detection does not use fuzzy matching, dependency parsing, or full conversation context, so it can miss nicknames, misspellings, and indirect references. Use this to prioritize manual review and to describe the scope of potential player-directed identity discourse carefully.
"""
    (AUDIT_DIR / "README.md").write_text(notes, encoding="utf-8")

    print(f"Audited {total:,} focused flagged rows")
    print(f"Wrote audit outputs to {AUDIT_DIR}")


if __name__ == "__main__":
    main()
