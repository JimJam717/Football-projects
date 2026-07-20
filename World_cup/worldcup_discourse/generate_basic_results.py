import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

try:
    from collect_since_gw2 import MATCH_TARGETS
except Exception:
    MATCH_TARGETS = []


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORT_DIR = BASE_DIR / "reports" / "phase2_basic_results"


def read_jsonl(path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def count_lines(path):
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def load_match_ids():
    match_ids = set()
    schedule_path = BASE_DIR / "config" / "schedule.json"
    if schedule_path.exists():
        with schedule_path.open("r", encoding="utf-8") as handle:
            schedule = json.load(handle)
        match_ids.update(match["match_id"] for match in schedule)
    match_ids.update(match["match_id"] for match in MATCH_TARGETS)

    for path in PROCESSED_DIR.glob("*_lang.jsonl"):
        match_ids.add(path.stem[: -len("_lang")])
    for path in PROCESSED_DIR.glob("*_sentiment.jsonl"):
        match_ids.add(path.stem[: -len("_sentiment")])

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


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def slugify(value):
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")


def chart_color(index):
    palette = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c", "#0891b2", "#4f46e5"]
    return palette[index % len(palette)]


def write_horizontal_bar_svg(path, title, rows, label_key, value_key, width=980):
    rows = [row for row in rows if int(row[value_key]) > 0]
    rows = rows[:20]
    row_height = 34
    top = 74
    left_label_width = 250
    right_padding = 110
    bar_area = width - left_label_width - right_padding
    height = max(170, top + len(rows) * row_height + 38)
    max_value = max((int(row[value_key]) for row in rows), default=1)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="28" y="38" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<text x="28" y="60" font-family="Arial, sans-serif" font-size="13" fill="#6b7280">Generated from local Phase 2 JSONL outputs</text>',
    ]

    for index, row in enumerate(rows):
        y = top + index * row_height
        value = int(row[value_key])
        bar_width = max(2, int((value / max_value) * bar_area))
        label = str(row[label_key])
        parts.extend(
            [
                f'<text x="28" y="{y + 21}" font-family="Arial, sans-serif" font-size="13" fill="#111827">{html.escape(label)}</text>',
                f'<rect x="{left_label_width}" y="{y + 7}" width="{bar_width}" height="20" rx="3" fill="{chart_color(index)}"/>',
                f'<text x="{left_label_width + bar_width + 8}" y="{y + 22}" font-family="Arial, sans-serif" font-size="13" fill="#374151">{value:,}</text>',
            ]
        )

    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_stacked_bar_svg(path, title, rows, label_key, segment_keys, width=980):
    row_height = 42
    top = 86
    left_label_width = 250
    right_padding = 120
    bar_area = width - left_label_width - right_padding
    height = max(190, top + len(rows) * row_height + 62)
    max_total = max((sum(int(row[key]) for key in segment_keys) for row in rows), default=1)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="28" y="38" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<text x="28" y="60" font-family="Arial, sans-serif" font-size="13" fill="#6b7280">Posts and comments counted from raw JSONL files</text>',
    ]

    legend_x = left_label_width
    for index, key in enumerate(segment_keys):
        parts.extend(
            [
                f'<rect x="{legend_x}" y="68" width="12" height="12" fill="{chart_color(index)}"/>',
                f'<text x="{legend_x + 18}" y="79" font-family="Arial, sans-serif" font-size="12" fill="#374151">{html.escape(key.title())}</text>',
            ]
        )
        legend_x += 92

    for row_index, row in enumerate(rows):
        y = top + row_index * row_height
        total = sum(int(row[key]) for key in segment_keys)
        current_x = left_label_width
        parts.append(
            f'<text x="28" y="{y + 24}" font-family="Arial, sans-serif" font-size="13" fill="#111827">{html.escape(str(row[label_key]))}</text>'
        )
        for index, key in enumerate(segment_keys):
            value = int(row[key])
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


def collect_raw_counts(match_ids):
    raw_rows = []
    by_match = defaultdict(lambda: {"match_id": "", "posts": 0, "comments": 0, "records": 0, "total": 0})
    by_subreddit_comments = Counter()

    for path in sorted(RAW_DIR.rglob("*.jsonl")):
        parsed = parse_raw_filename(path, match_ids)
        if not parsed:
            continue

        match_id, source, record_type = parsed
        line_count = count_lines(path)
        raw_rows.append(
            {
                "file": str(path.relative_to(BASE_DIR)),
                "match_id": match_id,
                "source": source,
                "record_type": record_type,
                "records": line_count,
            }
        )

        by_match[match_id]["match_id"] = match_id
        by_match[match_id][record_type] += line_count
        by_match[match_id]["total"] += line_count
        if record_type == "comments":
            by_subreddit_comments[source] += line_count

    match_rows = sorted(by_match.values(), key=lambda row: row["total"], reverse=True)
    subreddit_rows = [
        {"source": source, "comments": count}
        for source, count in by_subreddit_comments.most_common()
    ]
    return raw_rows, match_rows, subreddit_rows


def collect_processed_counts():
    lang_counts = Counter()
    mentions_by_match = []
    player_counts = Counter()
    platform_counts = Counter()

    for path in sorted(PROCESSED_DIR.glob("*_lang.jsonl")):
        match_id = path.stem[: -len("_lang")]
        if match_id.startswith("2022_"):
            continue
        row_count = 0
        for record in read_jsonl(path):
            row_count += 1
            lang_counts[record.get("lang") or "unknown"] += 1
            platform_counts[record.get("platform") or "unknown"] += 1
            for mention in record.get("mentions", []):
                player = mention.get("name")
                if player:
                    player_counts[player] += 1
        mentions_by_match.append({"match_id": match_id, "mention_rows": row_count})

    mentions_by_match.sort(key=lambda row: row["mention_rows"], reverse=True)
    language_rows = [{"language": key, "rows": value} for key, value in lang_counts.most_common()]
    platform_rows = [{"platform": key, "rows": value} for key, value in platform_counts.most_common()]
    player_rows = [{"player": key, "mentions": value} for key, value in player_counts.most_common(25)]
    return mentions_by_match, language_rows, platform_rows, player_rows


def collect_sentiment_counts():
    by_match = defaultdict(lambda: {"match_id": "", "negative": 0, "neutral": 0, "positive": 0, "error": 0, "total": 0})
    by_track = defaultdict(lambda: {"track": "", "negative": 0, "neutral": 0, "positive": 0, "error": 0, "total": 0})
    overall = Counter()

    for path in sorted(PROCESSED_DIR.glob("*_sentiment.jsonl")):
        if path.stat().st_size == 0:
            continue
        match_id = path.stem[: -len("_sentiment")]
        if match_id.startswith("2022_"):
            continue

        for record in read_jsonl(path):
            label = record.get("sentiment_label") or "unknown"
            if label not in {"negative", "neutral", "positive", "error"}:
                label = "error"
            track = record.get("track") or "unknown"

            by_match[match_id]["match_id"] = match_id
            by_match[match_id][label] += 1
            by_match[match_id]["total"] += 1

            by_track[track]["track"] = track
            by_track[track][label] += 1
            by_track[track]["total"] += 1

            overall[label] += 1

    match_rows = []
    for row in by_match.values():
        total = row["total"]
        match_rows.append(
            {
                **row,
                "negative_pct": round((row["negative"] / total) * 100, 2) if total else 0,
                "neutral_pct": round((row["neutral"] / total) * 100, 2) if total else 0,
                "positive_pct": round((row["positive"] / total) * 100, 2) if total else 0,
            }
        )
    match_rows.sort(key=lambda row: row["total"], reverse=True)

    track_rows = []
    for row in by_track.values():
        total = row["total"]
        track_rows.append(
            {
                **row,
                "negative_pct": round((row["negative"] / total) * 100, 2) if total else 0,
                "neutral_pct": round((row["neutral"] / total) * 100, 2) if total else 0,
                "positive_pct": round((row["positive"] / total) * 100, 2) if total else 0,
            }
        )
    track_rows.sort(key=lambda row: row["total"], reverse=True)

    overall_rows = [
        {"sentiment": label, "rows": overall[label]}
        for label in ("negative", "neutral", "positive", "error")
        if overall[label] > 0
    ]
    return match_rows, track_rows, overall_rows


def load_sensitive_summary():
    path = REPORT_DIR / "sensitive_language_overview.csv"
    if not path.exists():
        return []

    values = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            values[row["metric"]] = row["value"]

    total = values.get("total_records_scanned")
    flagged = values.get("records_with_any_flag")
    share = values.get("records_with_any_flag_share_pct")
    if not total or not flagged or share is None:
        return []

    try:
        label = f"{int(float(flagged)):,} of {int(float(total)):,} scanned records ({float(share):.3f}%)"
    except ValueError:
        label = f"{flagged} of {total} scanned records ({share}%)"
    return [("Sensitive-language flags", label)]


def read_csv_rows(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value):
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return str(value)


def percent(value):
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def split_flagged_words(value):
    if not value:
        return []
    text = str(value).strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None

    words = []
    if isinstance(parsed, dict):
        for values in parsed.values():
            if isinstance(values, list):
                words.extend(str(item).strip().lower() for item in values)
            elif values:
                words.append(str(values).strip().lower())
    elif isinstance(parsed, list):
        words.extend(str(item).strip().lower() for item in parsed)
    else:
        for part in text.replace(";", ",").split(","):
            words.append(part.strip().lower())

    return [word for word in words if word]


def collect_flagged_word_rows():
    path = REPORT_DIR / "flagged_comments" / "flagged_comments_preview.csv"
    if not path.exists():
        return []

    word_counts = Counter()
    category_counts = Counter()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            word_value = (
                row.get("word flagged")
                or row.get("word_flagged")
                or row.get("flagged_word")
                or row.get("matched_terms")
                or ""
            )
            categories = [category.strip() for category in (row.get("categories") or "").split(";") if category.strip()]
            for word in split_flagged_words(word_value):
                word_counts[word] += 1
            for category in categories:
                category_counts[category] += 1

    rows = []
    for word, count in word_counts.most_common(20):
        rows.append(
            {
                "word_flagged": word,
                "flagged_records": count,
                "category": next(
                    (
                        category
                        for category in category_counts
                        if category in word
                    ),
                    "",
                ),
            }
        )
    return rows


def write_index(chart_files, summary):
    raw_rows = read_csv_rows(REPORT_DIR / "raw_volume_by_match.csv")
    source_rows = read_csv_rows(REPORT_DIR / "comment_volume_by_source.csv")
    player_rows = read_csv_rows(REPORT_DIR / "top_player_mentions.csv")
    sentiment_rows = read_csv_rows(REPORT_DIR / "sentiment_by_match.csv")
    sentiment_track_rows = read_csv_rows(REPORT_DIR / "sentiment_by_track.csv")
    sentiment_distribution = read_csv_rows(REPORT_DIR / "sentiment_distribution.csv")
    sensitive_category_rows = read_csv_rows(REPORT_DIR / "sensitive_language_by_category.csv")
    sensitive_match_rows = read_csv_rows(REPORT_DIR / "sensitive_language_by_match.csv")
    flagged_word_rows = collect_flagged_word_rows()
    if flagged_word_rows:
        write_csv(REPORT_DIR / "flagged_words_summary.csv", flagged_word_rows, ["word_flagged", "flagged_records", "category"])

    summary_values = dict(summary)
    top_source = summary_values.get("Top source by comments", "n/a").replace("soccer", "r/soccer")
    max_raw = max((int(row["total"]) for row in raw_rows), default=1)
    max_source = max((int(row["comments"]) for row in source_rows), default=1)
    max_player = max((int(row["mentions"]) for row in player_rows), default=1)
    max_sensitive_category = max((int(row["flagged_records"]) for row in sensitive_category_rows), default=1)
    max_sensitive_match = max((int(row["flagged_records"]) for row in sensitive_match_rows), default=1)
    max_flagged_word = max((int(row["flagged_records"]) for row in flagged_word_rows), default=1)
    sentiment_counts = {row["sentiment"]: int(row["rows"]) for row in sentiment_distribution}
    sentiment_total = sum(sentiment_counts.values()) or 1
    negative_stop = sentiment_counts.get("negative", 0) / sentiment_total * 100
    neutral_stop = negative_stop + sentiment_counts.get("neutral", 0) / sentiment_total * 100

    def raw_chart():
        rows = []
        for row in raw_rows[:5]:
            total = int(row["total"]) or 1
            width = total / max_raw * 100
            posts = int(row["posts"]) / total * 100
            comments = int(row["comments"]) / total * 100
            records = int(row["records"]) / total * 100
            rows.append(
                f'<div class="bar-row" style="--total:{width:.1f}%;--posts:{posts:.1f}%;--comments:{comments:.1f}%;--records:{records:.1f}%">'
                f'<span class="label">{html.escape(row["match_id"])}</span><div class="track"><div class="stack">'
                '<span class="posts"></span><span class="comments"></span><span class="records"></span>'
                '</div></div></div>'
            )
        return "\n".join(rows)

    def source_chart():
        rows = []
        for row in source_rows[:6]:
            width = int(row["comments"]) / max_source * 100
            rows.append(
                f'<div class="bar-row"><span class="label">r/{html.escape(row["source"])}</span>'
                f'<span class="single-bar" style="--w:{width:.1f}%"></span></div>'
            )
        return "\n".join(rows)

    def player_chart():
        rows = []
        for row in player_rows[:9]:
            width = int(row["mentions"]) / max_player * 100
            rows.append(
                f'<div class="bar-row"><span class="label">{html.escape(row["player"])}</span>'
                f'<span class="single-bar yellow" style="--w:{width:.1f}%"></span></div>'
            )
        return "\n".join(rows)

    def sensitive_category_chart():
        rows = []
        for row in sensitive_category_rows[:8]:
            width = int(row["flagged_records"]) / max_sensitive_category * 100
            rows.append(
                f'<div class="bar-row detail-row"><span class="label">{html.escape(row["category"].replace("_", " "))}</span>'
                f'<span class="single-bar red" style="--w:{width:.1f}%"></span><span class="count">{number(row["flagged_records"])}</span></div>'
            )
        return "\n".join(rows) or '<p class="empty">No flagged category data found.</p>'

    def flagged_word_chart():
        rows = []
        for row in flagged_word_rows[:12]:
            width = int(row["flagged_records"]) / max_flagged_word * 100
            rows.append(
                f'<div class="bar-row detail-row"><span class="label">{html.escape(row["word_flagged"])}</span>'
                f'<span class="single-bar amber" style="--w:{width:.1f}%"></span><span class="count">{number(row["flagged_records"])}</span></div>'
            )
        return "\n".join(rows) or '<p class="empty">No flagged word data found.</p>'

    def flagged_match_chart():
        rows = []
        for row in sensitive_match_rows[:8]:
            width = int(row["flagged_records"]) / max_sensitive_match * 100
            rows.append(
                f'<div class="bar-row detail-row"><span class="label">{html.escape(row["match_id"])}</span>'
                f'<span class="single-bar" style="--w:{width:.1f}%"></span><span class="count">{number(row["flagged_records"])}</span></div>'
            )
        return "\n".join(rows) or '<p class="empty">No flagged match data found.</p>'

    def flagged_word_table():
        rows = []
        for row in flagged_word_rows[:10]:
            rows.append(
                '<tr>'
                f'<td>{html.escape(row["word_flagged"])}</td>'
                f'<td>{number(row["flagged_records"])}</td>'
                '</tr>'
            )
        if not rows:
            rows.append('<tr><td colspan="2">No flagged word data found.</td></tr>')
        return "\n".join(rows)

    def sentiment_match_chart():
        rows = []
        for row in sentiment_rows[:4]:
            rows.append(
                f'<div class="sentiment-row" style="--neg:{row["negative_pct"]}%;--neu:{row["neutral_pct"]}%;--pos:{row["positive_pct"]}%">'
                f'<span class="label">{html.escape(row["match_id"])}</span><div class="sentiment-stack">'
                '<span class="neg"></span><span class="neu"></span><span class="pos"></span>'
                f'</div><span class="pct">{percent(row["negative_pct"])}</span></div>'
            )
        return "\n".join(rows)

    def track_chart():
        rows = sentiment_track_rows[:2]
        if not rows:
            return ""
        labels = "".join(f'<span class="track-label">{html.escape(row["track"]).title()}</span>' for row in rows)
        bars = "".join(
            '<div class="mini-bars">'
            f'<div style="--h:{row["negative_pct"]}%;--c:var(--red)"></div>'
            f'<div style="--h:{row["neutral_pct"]}%;--c:var(--yellow)"></div>'
            f'<div style="--h:{row["positive_pct"]}%;--c:var(--green)"></div>'
            '</div>'
            for row in rows
        )
        axis = "".join(f'<span class="axis-title">{html.escape(row["track"]).title()}</span>' for row in rows)
        return f'<div class="track-labels">{labels}</div><div class="track-bars">{bars}</div><div class="track-axis">{axis}</div>'

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Data Collection Overview</title>
  <style>
    :root {{
      --bg:#0d121a; --rail:#121b2d; --panel:#1a1f29; --line:#333b4b;
      --muted:#9aa4b5; --text:#f7f8fc; --teal:#4fc0b4; --blue:#4d82ba;
      --steel:#778496; --green:#58c878; --yellow:#f2c34f; --red:#ef5757;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; min-height:100vh; color:var(--text);
      font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:linear-gradient(135deg,#111827 0%,var(--bg) 55%,#090d13 100%);
    }}
    .dashboard {{ display:grid; grid-template-columns:140px minmax(0,1fr); min-height:100vh; }}
    .sidebar {{ padding:18px 10px; background:linear-gradient(180deg,#142038,#101828); border-right:1px solid rgba(255,255,255,.06); }}
    .brand {{ display:grid; grid-template-columns:repeat(2,7px); gap:3px; width:17px; margin:0 auto 28px; }}
    .brand span {{ width:7px; height:7px; border-radius:50%; }}
    .brand span:nth-child(1) {{ background:#ff5f68; }} .brand span:nth-child(2) {{ background:#7b5cff; }}
    .brand span:nth-child(3) {{ background:#48c2bd; }} .brand span:nth-child(4) {{ background:#f3c24f; }}
    .nav {{ display:grid; gap:7px; }}
    .nav a {{ display:grid; grid-template-columns:20px 1fr; align-items:center; gap:8px; min-height:34px; padding:0 10px; color:#c7cfdd; text-decoration:none; border-radius:7px; font-size:13px; }}
    .nav a::before {{ content:attr(data-icon); display:grid; place-items:center; width:18px; height:18px; border:1px solid rgba(214,219,230,.65); border-radius:5px; font-size:12px; }}
    .nav a.active {{ color:#fff; background:rgba(255,255,255,.1); box-shadow:inset 0 0 0 1px rgba(255,255,255,.05); }}
    main {{ padding:18px 22px 24px; overflow:hidden; }}
    .topbar {{ display:flex; align-items:center; justify-content:space-between; gap:18px; margin-bottom:16px; }}
    h1 {{ margin:0; font-size:clamp(23px,3vw,30px); line-height:1.05; letter-spacing:0; }}
    .filters {{ display:flex; flex-wrap:wrap; justify-content:flex-end; gap:8px; }}
    .control {{ min-height:32px; padding:0 12px; border:1px solid #465064; border-radius:7px; color:#eef2f8; background:linear-gradient(180deg,#51596b,#343b49); font-size:13px; }}
    .kpis {{ display:grid; grid-template-columns:repeat(6,minmax(118px,1fr)); gap:14px; margin-bottom:14px; }}
    .kpi {{ position:relative; min-height:72px; padding:15px 13px 12px; overflow:hidden; background:linear-gradient(180deg,#1d222d,#141820); border:1px solid var(--line); border-radius:8px; box-shadow:0 14px 30px rgba(0,0,0,.24); }}
    .kpi::before {{ content:""; position:absolute; inset:0 0 auto; height:3px; background:var(--accent,var(--teal)); box-shadow:0 0 14px var(--accent,var(--teal)); }}
    .kpi span {{ display:block; color:var(--muted); font-size:13px; white-space:nowrap; }}
    .kpi strong {{ display:block; margin-top:4px; color:#fff; font-size:clamp(20px,2vw,26px); line-height:1; text-shadow:0 2px 0 rgba(0,0,0,.55); white-space:nowrap; }}
    .view[hidden] {{ display:none; }}
    .cards {{ display:grid; grid-template-columns:1.05fr 1.05fr 1fr; gap:14px; }}
    .card {{ min-width:0; padding:13px; background:linear-gradient(180deg,#1b202a,#141820); border:1px solid var(--line); border-radius:8px; box-shadow:0 18px 34px rgba(0,0,0,.26); }}
    .card.wide {{ grid-column:span 2; }}
    .card.full {{ grid-column:1 / -1; }}
    .card h2 {{ margin:0 0 13px; color:#fff; font-size:16px; line-height:1.1; letter-spacing:0; }}
    .stacked-chart,.source-chart,.player-chart,.sentiment-bars {{ display:grid; gap:9px; }}
    .bar-row {{ display:grid; grid-template-columns:minmax(92px,140px) minmax(0,1fr); align-items:center; gap:10px; min-height:18px; }}
    .bar-row.detail-row {{ grid-template-columns:minmax(120px,190px) minmax(0,1fr) 54px; }}
    .label {{ min-width:0; color:#fff; font-size:12px; line-height:1.15; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .track {{ height:17px; overflow:hidden; border-radius:3px; background:repeating-linear-gradient(90deg,rgba(255,255,255,.08) 0 1px,transparent 1px 25%),rgba(255,255,255,.04); }}
    .stack {{ display:flex; width:var(--total); height:100%; border-radius:3px; overflow:hidden; }}
    .posts {{ width:var(--posts); background:var(--teal); }} .comments {{ width:var(--comments); background:var(--blue); }} .records {{ width:var(--records); background:var(--steel); }}
    .legend {{ display:flex; flex-wrap:wrap; align-items:center; justify-content:center; gap:14px; margin-top:12px; color:#d9dee9; font-size:12px; }}
    .legend span {{ display:inline-flex; align-items:center; gap:5px; }} .swatch {{ width:8px; height:8px; border-radius:2px; background:var(--c); }}
    .single-bar {{ display:block; width:var(--w); height:17px; border-radius:3px; background:var(--teal); }} .single-bar.yellow,.single-bar.amber {{ background:var(--yellow); }} .single-bar.red {{ background:var(--red); }}
    .count {{ color:#e9eef8; font-size:12px; text-align:right; }}
    .table-wrap {{ overflow-x:auto; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th,td {{ padding:9px 8px; border-bottom:1px solid rgba(255,255,255,.08); text-align:left; }}
    th {{ color:#aeb8c8; font-weight:700; }}
    td:last-child,th:last-child {{ text-align:right; }}
    .empty {{ margin:0; color:var(--muted); font-size:13px; }}
    .donut-wrap {{ display:grid; justify-items:center; gap:14px; padding:10px 0 4px; }}
    .donut {{ position:relative; width:min(210px,70vw); aspect-ratio:1; border-radius:50%; background:conic-gradient(var(--red) 0 {negative_stop:.2f}%,var(--yellow) {negative_stop:.2f}% {neutral_stop:.2f}%,var(--green) {neutral_stop:.2f}% 100%); box-shadow:0 14px 28px rgba(0,0,0,.35); }}
    .donut::before {{ content:""; position:absolute; inset:27%; border-radius:50%; background:#181c25; box-shadow:inset 0 0 0 1px rgba(255,255,255,.05); }}
    .donut-value {{ position:absolute; inset:0; display:grid; place-content:center; text-align:center; font-weight:800; font-size:24px; line-height:1.05; text-shadow:0 2px 0 rgba(0,0,0,.65); }}
    .donut-value small {{ display:block; margin-top:4px; font-size:13px; color:#d8deea; font-weight:700; }}
    .sentiment-row {{ display:grid; grid-template-columns:minmax(105px,140px) minmax(0,1fr) 44px; align-items:center; gap:8px; min-height:21px; }}
    .sentiment-stack {{ display:flex; height:18px; overflow:hidden; border-radius:3px; background:rgba(255,255,255,.05); }}
    .neg {{ width:var(--neg); background:var(--red); }} .neu {{ width:var(--neu); background:#9aa4b3; }} .pos {{ width:var(--pos); background:var(--green); }}
    .pct {{ color:#e9eef8; font-size:12px; text-align:right; }}
    .track-labels,.track-bars,.track-axis {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }}
    .track-labels {{ color:#fff; font-size:12px; margin:4px 0 8px; }}
    .mini-bars {{ display:grid; grid-template-columns:repeat(3,1fr); align-items:end; gap:8px; min-height:76px; border-bottom:1px solid rgba(255,255,255,.12); padding-bottom:1px; }}
    .mini-bars div {{ height:var(--h); min-height:10px; border-radius:3px 3px 0 0; background:var(--c); }}
    .axis-title {{ color:#d9dee9; text-align:center; font-size:12px; margin-top:5px; }}
    @media (max-width:1100px) {{ .dashboard{{grid-template-columns:118px minmax(0,1fr)}} .kpis{{grid-template-columns:repeat(3,minmax(0,1fr))}} .cards{{grid-template-columns:repeat(2,minmax(0,1fr))}} .card.wide{{grid-column:span 2}} }}
    @media (max-width:760px) {{ .dashboard{{grid-template-columns:1fr}} .sidebar{{position:sticky;top:0;z-index:3;display:flex;align-items:center;gap:14px;padding:10px 12px;overflow-x:auto}} .brand{{flex:0 0 auto;margin:0}} .nav{{display:flex;gap:6px}} .nav a{{grid-template-columns:20px;width:38px;padding:0 9px}} .nav a span{{display:none}} main{{padding:16px 12px 20px}} .topbar{{align-items:flex-start;flex-direction:column}} .filters{{justify-content:flex-start}} .kpis,.cards{{grid-template-columns:1fr}} .card.wide{{grid-column:auto}} .bar-row,.sentiment-row{{grid-template-columns:1fr;gap:5px}} .pct{{text-align:left}} }}
  </style>
</head>
<body>
  <div class="dashboard">
    <aside class="sidebar" aria-label="Dashboard navigation">
      <div class="brand" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
      <nav class="nav">
        <a class="active" href="#overview" data-icon="H" data-view="overview"><span>Overview</span></a>
        <a href="#sentiment-analysis" data-icon="S" data-view="sentiment-analysis"><span>Sentiment</span></a>
        <a href="#players" data-icon="P" data-view="overview"><span>Players</span></a>
        <a href="#sources" data-icon="R" data-view="overview"><span>Sources</span></a>
        <a href="#language" data-icon="L" data-view="overview"><span>Language</span></a>
        <a href="#matches" data-icon="M" data-view="overview"><span>Matches</span></a>
      </nav>
    </aside>
    <main id="overview">
      <header class="topbar">
        <h1>Data Collection Overview</h1>
        <div class="filters">
          <button class="control" type="button" onclick="location.href='../research_explorer/index.html'">Research Explorer</button>
          <button class="control" type="button">Match Filter</button>
          <button class="control" type="button">Date - Range 20</button>
        </div>
      </header>
      <section class="kpis" aria-label="Summary metrics">
        <div class="kpi" style="--accent:var(--teal)"><span>Raw Records</span><strong>{html.escape(summary_values.get("Raw JSONL records", "0"))}</strong></div>
        <div class="kpi" style="--accent:var(--yellow)"><span>Raw Comments</span><strong>{html.escape(summary_values.get("Raw comments", "0"))}</strong></div>
        <div class="kpi" style="--accent:var(--blue)"><span>Mention Rows</span><strong>{html.escape(summary_values.get("Processed mention rows", "0"))}</strong></div>
        <div class="kpi" style="--accent:var(--teal)"><span>Matches Tracked</span><strong>{html.escape(summary_values.get("Matches with processed mentions", "0"))}</strong></div>
        <div class="kpi" style="--accent:var(--red)"><span>Sentiment Scored</span><strong>{html.escape(summary_values.get("Sentiment-scored rows", "0"))}</strong></div>
        <div class="kpi" style="--accent:var(--steel)"><span>Top Source</span><strong>{html.escape(top_source)}</strong></div>
      </section>
      <section class="cards view" id="overview-view" aria-label="Analytics charts">
        <article class="card wide" id="matches">
          <h2>Raw Volume by Match</h2>
          <div class="stacked-chart">{raw_chart()}</div>
          <div class="legend"><span><i class="swatch" style="--c:var(--teal)"></i>Posts</span><span><i class="swatch" style="--c:var(--blue)"></i>Comments</span><span><i class="swatch" style="--c:var(--steel)"></i>Combined records</span></div>
        </article>
        <article class="card" id="sources"><h2>Comment Volume by Source</h2><div class="source-chart">{source_chart()}</div></article>
        <article class="card">
          <h2>Sentiment Distribution</h2>
          <div class="donut-wrap">
            <div class="donut" role="img" aria-label="Sentiment distribution"><div class="donut-value">{number(sentiment_total)}<small>Total</small></div></div>
            <div class="legend"><span><i class="swatch" style="--c:var(--red)"></i>negative</span><span><i class="swatch" style="--c:var(--yellow)"></i>neutral</span><span><i class="swatch" style="--c:var(--green)"></i>positive</span></div>
          </div>
        </article>
        <article class="card" id="players"><h2>Top Player Mentions</h2><div class="player-chart">{player_chart()}</div></article>
        <article class="card wide"><h2>Sentiment by Match</h2><div class="sentiment-bars">{sentiment_match_chart()}</div></article>
        <article class="card wide"><h2>Sentiment by Track</h2>{track_chart()}</article>
      </section>
      <section class="cards view" id="sentiment-analysis-view" aria-label="Sentiment flagged word analysis" hidden>
        <article class="card wide">
          <h2>Flagged Words</h2>
          <div class="player-chart">{flagged_word_chart()}</div>
        </article>
        <article class="card">
          <h2>Flagged Categories</h2>
          <div class="source-chart">{sensitive_category_chart()}</div>
        </article>
        <article class="card wide">
          <h2>Flags by Match</h2>
          <div class="source-chart">{flagged_match_chart()}</div>
        </article>
        <article class="card">
          <h2>Flagged Word Data</h2>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Word flagged</th><th>Records</th></tr></thead>
              <tbody>{flagged_word_table()}</tbody>
            </table>
          </div>
        </article>
      </section>
    </main>
  </div>
  <script>
    const navLinks = document.querySelectorAll(".nav a[data-view]");
    const views = document.querySelectorAll(".view");
    function showView(viewName, activeLink = null) {{
      views.forEach((view) => {{
        view.hidden = view.id !== `${{viewName}}-view`;
      }});
      navLinks.forEach((link) => {{
        link.classList.toggle("active", activeLink ? link === activeLink : link.dataset.view === viewName);
      }});
    }}
    navLinks.forEach((link) => {{
      link.addEventListener("click", (event) => {{
        const viewName = link.dataset.view;
        if (!viewName) return;
        event.preventDefault();
        showView(viewName, link);
        history.replaceState(null, "", link.getAttribute("href"));
      }});
    }});
    if (location.hash === "#sentiment-analysis") {{
      showView("sentiment-analysis");
    }}
  </script>
</body>
</html>
"""
    (REPORT_DIR / "index.html").write_text(page, encoding="utf-8")


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    match_ids = load_match_ids()
    raw_rows, match_rows, subreddit_rows = collect_raw_counts(match_ids)
    mention_rows, language_rows, platform_rows, player_rows = collect_processed_counts()
    sentiment_match_rows, sentiment_track_rows, sentiment_overall_rows = collect_sentiment_counts()

    write_csv(REPORT_DIR / "raw_file_counts.csv", raw_rows, ["file", "match_id", "source", "record_type", "records"])
    write_csv(REPORT_DIR / "raw_volume_by_match.csv", match_rows, ["match_id", "posts", "comments", "records", "total"])
    write_csv(REPORT_DIR / "comment_volume_by_source.csv", subreddit_rows, ["source", "comments"])
    write_csv(REPORT_DIR / "mention_rows_by_match.csv", mention_rows, ["match_id", "mention_rows"])
    write_csv(REPORT_DIR / "language_distribution.csv", language_rows, ["language", "rows"])
    write_csv(REPORT_DIR / "platform_distribution.csv", platform_rows, ["platform", "rows"])
    write_csv(REPORT_DIR / "top_player_mentions.csv", player_rows, ["player", "mentions"])
    write_csv(
        REPORT_DIR / "sentiment_by_match.csv",
        sentiment_match_rows,
        ["match_id", "negative", "neutral", "positive", "error", "total", "negative_pct", "neutral_pct", "positive_pct"],
    )
    write_csv(
        REPORT_DIR / "sentiment_by_track.csv",
        sentiment_track_rows,
        ["track", "negative", "neutral", "positive", "error", "total", "negative_pct", "neutral_pct", "positive_pct"],
    )
    write_csv(REPORT_DIR / "sentiment_distribution.csv", sentiment_overall_rows, ["sentiment", "rows"])

    charts = [
        ("Raw Volume by Match", REPORT_DIR / "raw_volume_by_match.svg"),
        ("Comment Volume by Source", REPORT_DIR / "comment_volume_by_source.svg"),
        ("Mention Rows by Match", REPORT_DIR / "mention_rows_by_match.svg"),
        ("Language Distribution", REPORT_DIR / "language_distribution.svg"),
        ("Top Player Mentions", REPORT_DIR / "top_player_mentions.svg"),
        ("Sentiment by Match", REPORT_DIR / "sentiment_by_match.svg"),
        ("Sentiment Distribution", REPORT_DIR / "sentiment_distribution.svg"),
        ("Sentiment by Track", REPORT_DIR / "sentiment_by_track.svg"),
    ]
    for title, filename in (
        ("Sensitive / Hard Language by Category", "sensitive_language_by_category.svg"),
        ("Sensitive / Hard Language by Match", "sensitive_language_by_match.svg"),
    ):
        path = REPORT_DIR / filename
        if path.exists():
            charts.append((title, path))

    write_stacked_bar_svg(charts[0][1], charts[0][0], match_rows, "match_id", ["comments", "posts", "records"])
    write_horizontal_bar_svg(charts[1][1], charts[1][0], subreddit_rows, "source", "comments")
    write_horizontal_bar_svg(charts[2][1], charts[2][0], mention_rows, "match_id", "mention_rows")
    write_horizontal_bar_svg(charts[3][1], charts[3][0], language_rows, "language", "rows")
    write_horizontal_bar_svg(charts[4][1], charts[4][0], player_rows, "player", "mentions")
    write_stacked_bar_svg(charts[5][1], charts[5][0], sentiment_match_rows, "match_id", ["negative", "neutral", "positive", "error"])
    write_horizontal_bar_svg(charts[6][1], charts[6][0], sentiment_overall_rows, "sentiment", "rows")
    write_stacked_bar_svg(charts[7][1], charts[7][0], sentiment_track_rows, "track", ["negative", "neutral", "positive", "error"])

    total_raw = sum(row["total"] for row in match_rows)
    total_comments = sum(row["comments"] for row in match_rows)
    total_mention_rows = sum(row["mention_rows"] for row in mention_rows)
    total_sentiment_rows = sum(row["total"] for row in sentiment_match_rows)
    summary = [
        ("Raw JSONL records", f"{total_raw:,}"),
        ("Raw comments", f"{total_comments:,}"),
        ("Processed mention rows", f"{total_mention_rows:,}"),
        ("Matches with processed mentions", f"{len(mention_rows):,}"),
        ("Sentiment-scored rows", f"{total_sentiment_rows:,}"),
        ("Matches with sentiment", f"{len(sentiment_match_rows):,}"),
        ("Top source by comments", f"{subreddit_rows[0]['source']} ({subreddit_rows[0]['comments']:,})" if subreddit_rows else "n/a"),
        ("Top mentioned player", f"{player_rows[0]['player']} ({player_rows[0]['mentions']:,})" if player_rows else "n/a"),
    ]
    summary.extend(load_sensitive_summary())
    write_index(charts, summary)

    print(f"Wrote report to {REPORT_DIR}")
    for title, path in charts:
        print(f"- {title}: {path}")


if __name__ == "__main__":
    main()
