import os
import json
import time
import random
import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

# Import pipeline components
from collectors.arctic_shift_collector import collect_from_arctic_shift
from processing.mention_extractor import extract_mentions
from processing.lang_detector import detect_language
from processing.sentiment import score_sentiment

def render_progress(label, current, total, suffix=""):
    total = max(total, 1)
    width = 28
    ratio = min(max(current / total, 0), 1)
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    message = f"\r{label} [{bar}] {current}/{total} ({ratio * 100:5.1f}%)"
    if suffix:
        message += f" {suffix}"
    sys.stdout.write(message)
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")
        sys.stdout.flush()

def count_lines(path):
    with open(path, 'r', encoding='utf-8') as file:
        return sum(1 for _ in file)

def iter_with_progress(path, label):
    total = count_lines(path)
    if total == 0:
        render_progress(label, 0, 0, "empty")
        return

    with open(path, 'r', encoding='utf-8') as file:
        for index, line in enumerate(file, start=1):
            render_progress(label, index, total)
            yield line

def iter_lines(path, label, show_progress):
    if show_progress:
        yield from iter_with_progress(path, label)
        return

    with open(path, 'r', encoding='utf-8') as file:
        for line in file:
            yield line

def run_france_morocco_smoke_test(show_progress=True):
    print("--- STEP 1: COLLECTION ---")
    match_id = "2022_france_morocco_qf"
    subreddits = ["soccer", "worldcup", "france", "morocco"]

    Path("data/raw").mkdir(parents=True, exist_ok=True)
    Path("data/processed").mkdir(parents=True, exist_ok=True)

    collected_files = []
    total_raw_records = 0
    for sub in subreddits:
        post_file = f"data/raw/{match_id}_{sub}_posts.jsonl"
        comment_file = f"data/raw/{match_id}_{sub}_comments.jsonl"
        for f in [post_file, comment_file]:
            if os.path.exists(f):
                collected_files.append(f)
                count = count_lines(f)
                print(f"{f}: {count} records")
                total_raw_records += count
            else:
                print(f"{f}: 0 records (file not found)")

    print("\n--- STEP 2: MENTION EXTRACTION ---")
    squads = {
        "france": [{"name": p.strip(), "aliases": [p.strip()]} for p in "Lloris, Varane, Upamecano, Kounde, Theo Hernandez, Tchouameni, Rabiot, Griezmann, Dembele, Giroud, Mbappe".split(",")],
        "morocco": [{"name": p.strip(), "aliases": [p.strip()]} for p in "Bounou, Hakimi, Aguerd, Saiss, Mazraoui, Amrabat, Ounahi, Ziyech, En-Nesyri, Boufal, Dari".split(",")]
    }

    mentions_out_file = f"data/processed/{match_id}_mentions.jsonl"
    player_mention_counts = Counter()
    total_mentioned_records = 0

    with open(mentions_out_file, 'w', encoding='utf-8') as out_f:
        for f in collected_files:
            label = f"Mentions {Path(f).name}"
            for line in iter_lines(f, label, show_progress):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    text = record.get('selftext', '') or record.get('body', '')
                    if not text:
                        continue

                    mentions = extract_mentions(text, squads)
                    if mentions:
                        total_mentioned_records += 1
                        record['mentions'] = mentions
                        out_f.write(json.dumps(record, ensure_ascii=False) + '\n')
                        for m in mentions:
                            player_mention_counts[m['name']] += 1
                except json.JSONDecodeError:
                    pass

    print("Mention extraction complete.")
    print("Top 10 mentioned players:")
    for player, count in player_mention_counts.most_common(10):
        print(f"  {player}: {count}")

    print("\n--- STEP 3: LANGUAGE DETECTION ---")
    lang_out_file = f"data/processed/{match_id}_lang.jsonl"
    lang_counts = Counter()
    
    with open(lang_out_file, 'w', encoding='utf-8') as out_f:
        for line in iter_lines(mentions_out_file, "Languages", show_progress):
            record = json.loads(line)
            text = record.get('selftext', '') or record.get('body', '')
            lang = detect_language(text)
            record['lang'] = lang
            lang_counts[lang] += 1
            out_f.write(json.dumps(record, ensure_ascii=False) + '\n')

    total_lang = sum(lang_counts.values())
    if total_lang > 0:
        print("Language distribution:")
        for lang, count in lang_counts.most_common():
            print(f"  {lang}: {count} ({count/total_lang*100:.1f}%)")

    print("\n--- STEP 4: SENTIMENT SCORING ---")
    sentiment_out_file = f"data/processed/{match_id}_sentiment.jsonl"
    
    # Read relevant records
    records_to_score = []
    with open(lang_out_file, 'r', encoding='utf-8') as in_f:
        for line in in_f:
            record = json.loads(line)
            if record['lang'] in ['en', 'fr', 'ar']:
                records_to_score.append(record)

    print(f"Scoring all {len(records_to_score)} eligible records.")

    sentiment_by_player = {}
    error_records = []

    with open(sentiment_out_file, 'w', encoding='utf-8') as out_f:
        for index, record in enumerate(records_to_score, start=1):
            if show_progress:
                render_progress("Sentiment", index, len(records_to_score))
            text = record.get('selftext', '') or record.get('body', '')
            # Trucate to a reasonable length for the pipeline explicitly just in case
            # The pipeline truncates automatically, but let's be safe
            text = text[:1000] 
            
            result = score_sentiment(text)
            record['sentiment_label'] = result['label']
            record['sentiment_score'] = result['score']
            
            if result['label'] == 'error':
                error_records.append(text[:100])
                
            for m in record['mentions']:
                p_name = m['name']
                if p_name not in sentiment_by_player:
                    sentiment_by_player[p_name] = {'positive': 0, 'neutral': 0, 'negative': 0, 'error': 0}
                sentiment_by_player[p_name][result['label']] += 1
            
            out_f.write(json.dumps(record, ensure_ascii=False) + '\n')
    if show_progress and records_to_score:
        sys.stdout.write("\n")
        sys.stdout.flush()

    print("\n--- STEP 5: SANITY CHECK ---")
    print(f"Total records collected across all subreddits: {total_raw_records}")
    print(f"Total records with at least one player mention: {total_mentioned_records}")
    if total_raw_records > 0:
        print(f"Mention rate: {total_mentioned_records/total_raw_records*100:.2f}%")
        
    print("\nTop 5 most mentioned players:")
    for player, count in player_mention_counts.most_common(5):
        print(f"  {player}: {count} total mentions")

    print("\nSentiment breakdown for Mbappe vs En-Nesyri:")
    for p in ['Mbappe', 'En-Nesyri']:
        if p in sentiment_by_player:
            counts = sentiment_by_player[p]
            total = sum(counts.values())
            print(f"  {p} ({total} scored mentions):")
            if total > 0:
                print(f"    Positive: {counts['positive']} ({counts['positive']/total*100:.1f}%)")
                print(f"    Neutral:  {counts['neutral']} ({counts['neutral']/total*100:.1f}%)")
                print(f"    Negative: {counts['negative']} ({counts['negative']/total*100:.1f}%)")
        else:
            print(f"  {p}: No scored mentions in the dataset.")

    if error_records:
        print(f"\nThere were {len(error_records)} records that errored during sentiment scoring.")
    else:
        print("\nNo records errored during sentiment scoring.")

    return {
        "match_id": match_id,
        "total_raw_records": total_raw_records,
        "total_mentioned_records": total_mentioned_records,
        "lang_counts": dict(lang_counts),
        "sentiment_scored_records": len(records_to_score),
        "sampled": False,
        "errors": len(error_records),
    }

def main():
    run_france_morocco_smoke_test(show_progress=True)

if __name__ == "__main__":
    main()
