import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from collect_since_gw2 import MATCH_TARGETS
from config.keywords import get_all_keywords
from processing.lang_detector import detect_language
from processing.mention_extractor import extract_mentions
from processing.sentiment import score_sentiment


BASE_DIR = Path(__file__).resolve().parent
RAW_REDDIT_DIR = BASE_DIR / "data" / "raw" / "reddit"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
SUPPORTED_SENTIMENT_LANGS = {"en", "fr", "nl", "de", "es", "pt", "ar"}
NEW_MATCHES = {match["match_id"]: match for match in MATCH_TARGETS}


def read_jsonl(path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def text_from_raw_record(raw_record):
    record = raw_record.get("record") if isinstance(raw_record.get("record"), dict) else raw_record
    record_type = raw_record.get("record_type") or record.get("record_type")

    if record_type == "post":
        parts = [
            record.get("title"),
            record.get("selftext"),
        ]
        return " ".join(str(part) for part in parts if part).strip()

    return (
        record.get("body")
        or record.get("text")
        or record.get("selftext")
        or record.get("title")
        or ""
    ).strip()


def normalize_record(raw_record, source_file, match_id):
    record = raw_record.get("record") if isinstance(raw_record.get("record"), dict) else raw_record
    text = text_from_raw_record(raw_record)
    if not text:
        return None

    return {
        "match_id": match_id,
        "record_type": raw_record.get("record_type") or record.get("record_type") or "record",
        "subreddit": raw_record.get("subreddit") or record.get("subreddit") or "",
        "source": raw_record.get("source") or "reddit",
        "record_id": record.get("id") or record.get("name") or "",
        "created_utc": record.get("created_utc") or "",
        "author": record.get("author") or "",
        "score": record.get("score") or "",
        "permalink": record.get("permalink") or "",
        "source_file": str(source_file.relative_to(BASE_DIR)),
        "text": text,
    }


def raw_files_for_match(match_id):
    return sorted(RAW_REDDIT_DIR.glob(f"{match_id}_*.jsonl"))


def squad_for_match(match, squads):
    selected = {}
    for country in (match["nation"], match["opponent"]):
        players = squads.get(country.lower())
        if players:
            selected[country.lower()] = players
    return selected


def discourse_keywords():
    return {keyword.lower() for keyword in get_all_keywords("en") if keyword and len(keyword) >= 3}


def is_discourse_record(text, keywords):
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in keywords)


def process_match(match_id, match, squads, force=False):
    raw_files = raw_files_for_match(match_id)
    if not raw_files:
        print(f"{match_id}: skipped, no raw reddit files found", flush=True)
        return {"match_id": match_id, "raw_files": 0, "mentions": 0, "lang": 0, "sentiment": 0}

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    mentions_path = PROCESSED_DIR / f"{match_id}_mentions.jsonl"
    lang_path = PROCESSED_DIR / f"{match_id}_lang.jsonl"
    sentiment_path = PROCESSED_DIR / f"{match_id}_sentiment.jsonl"

    if sentiment_path.exists() and sentiment_path.stat().st_size > 0 and not force:
        print(f"{match_id}: skipped, sentiment output already exists ({sentiment_path.name})", flush=True)
        return {"match_id": match_id, "skipped_existing": True}

    match_squad = squad_for_match(match, squads)
    keywords = discourse_keywords()
    mention_rows = []
    lang_rows = []
    counts = Counter()

    print(f"\n=== {match_id} ===", flush=True)
    print(f"raw files: {len(raw_files)}", flush=True)

    with mentions_path.open("w", encoding="utf-8") as mentions_out:
        for raw_file in raw_files:
            print(f"  mentions: {raw_file.name}", flush=True)
            for raw_record in read_jsonl(raw_file):
                counts["raw_records"] += 1
                normalized = normalize_record(raw_record, raw_file, match_id)
                if not normalized:
                    continue

                mentions = extract_mentions(normalized["text"], match_squad)
                if not mentions and not is_discourse_record(normalized["text"], keywords):
                    continue

                normalized["mentions"] = mentions
                normalized["matched_players"] = mentions
                normalized["track"] = "player" if mentions else "discourse"
                mentions_out.write(json.dumps(normalized, ensure_ascii=False) + "\n")
                mention_rows.append(normalized)
                counts["mention_or_discourse_rows"] += 1

    with lang_path.open("w", encoding="utf-8") as lang_out:
        for index, record in enumerate(mention_rows, start=1):
            if index % 1000 == 0:
                print(f"  language rows: {index}/{len(mention_rows)}", flush=True)
            record["lang"] = detect_language(record["text"])
            lang_out.write(json.dumps(record, ensure_ascii=False) + "\n")
            if record["lang"] in SUPPORTED_SENTIMENT_LANGS:
                lang_rows.append(record)
                counts["sentiment_eligible_rows"] += 1

    with sentiment_path.open("w", encoding="utf-8") as sentiment_out:
        total_to_score = len(lang_rows)
        for index, record in enumerate(lang_rows, start=1):
            record["sampled"] = False
            record["scored_all_eligible"] = True
            if index % 50 == 0 or index == 1:
                print(f"  sentiment rows: {index}/{total_to_score}", flush=True)
            result = score_sentiment(record["text"][:1000])
            record["sentiment_label"] = result["label"]
            record["sentiment_score"] = result["score"]
            sentiment_out.write(json.dumps(record, ensure_ascii=False) + "\n")
            counts["sentiment_rows"] += 1

    print(
        f"{match_id}: raw={counts['raw_records']} "
        f"mentions_or_discourse={counts['mention_or_discourse_rows']} "
        f"eligible={counts['sentiment_eligible_rows']} "
        f"sentiment={counts['sentiment_rows']}",
        flush=True,
    )
    return {
        "match_id": match_id,
        "raw_files": len(raw_files),
        "mentions": counts["mention_or_discourse_rows"],
        "lang": counts["sentiment_eligible_rows"],
        "sentiment": counts["sentiment_rows"],
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run mention extraction, language detection, and sentiment only for post-GW2 collected games."
    )
    parser.add_argument(
        "--match",
        action="append",
        choices=sorted(NEW_MATCHES),
        help="Limit to one new match ID. Can be passed more than once.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing processed outputs for selected new matches.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    squads = load_json(BASE_DIR / "config" / "squads.json")
    match_ids = args.match or sorted(NEW_MATCHES)

    print("Running sentiment pipeline only for new post-GW2 matches:", flush=True)
    for match_id in match_ids:
        print(f"  - {match_id}", flush=True)

    summaries = []
    for match_id in match_ids:
        summaries.append(process_match(match_id, NEW_MATCHES[match_id], squads, force=args.force))

    print("\nSummary", flush=True)
    for summary in summaries:
        if summary.get("skipped_existing"):
            print(f"  {summary['match_id']}: skipped existing sentiment output", flush=True)
            continue
        print(
            f"  {summary['match_id']}: raw_files={summary['raw_files']} "
            f"mentions={summary['mentions']} lang={summary['lang']} sentiment={summary['sentiment']}",
            flush=True,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
