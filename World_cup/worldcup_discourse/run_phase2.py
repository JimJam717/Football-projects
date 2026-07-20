import os
import sys
import json
import glob
from pathlib import Path
from datetime import datetime, timezone
import collections

from processing.match_events import get_match_events
from scheduler import run_event_collection
from processing.mention_extractor import extract_mentions
from processing.lang_detector import detect_language
from processing.sentiment import sample_for_scoring, score_sentiment

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_phase_2():
    schedule = load_json('config/schedule.json')
    squads = load_json('config/squads.json')
    tracked_countries = load_json('config/tracked_countries.json')
    tracked_lower = [c.lower() for c in tracked_countries]

    # 1. Sort unique kickoff dates
    dates = set()
    for match in schedule:
        dt = datetime.fromisoformat(match['kickoff_utc'].replace('Z', '+00:00'))
        dates.add(dt.date())
    
    sorted_dates = sorted(list(dates))
    if len(sorted_dates) >= 3:
        day_3_date = sorted_dates[2]
    else:
        print("Less than 3 dates found. Taking the last one as Day 3 fallback.")
        day_3_date = sorted_dates[-1] if sorted_dates else None

    print(f"Identified Day 3 as: {day_3_date}")

    now_utc = datetime.now(timezone.utc)
    
    qualifying_matches = []
    
    for match in schedule:
        dt = datetime.fromisoformat(match['kickoff_utc'].replace('Z', '+00:00'))
        match_id = match['match_id']
        nation = match['nation'].lower()
        opponent = match['opponent'].lower()
        
        # 2. Kickoff >= Day 3 AND finished (kickoff + 2hrs < now)
        if day_3_date and dt.date() >= day_3_date:
            finished_time = dt.timestamp() + (2 * 3600)
            if finished_time < now_utc.timestamp():
                # 3. Tracked country involved
                if nation in tracked_lower or opponent in tracked_lower:
                    qualifying_matches.append(match)

    print(f"Found {len(qualifying_matches)} qualifying matches.")

    # Track summary stats
    summary = {
        "matches_processed": 0,
        "events_found": collections.defaultdict(int),
        "posts_collected": collections.defaultdict(int),
        "players_covered": set()
    }

    # Process qualifying matches
    for match in qualifying_matches:
        match_id = match['match_id']
        nation = match['nation']
        
        print(f"\n--- Processing Match: {match_id} ---")
        summary["matches_processed"] += 1
        
        # 4. Fetch events
        events_file = Path(f"data/events/{match_id}.json")
        events = []
        if events_file.exists():
            print(f"Loaded existing events for {match_id}")
            events = load_json(events_file)
        else:
            print(f"Fetching events for {match_id}...")
            events = get_match_events(match_id)
            
        summary["events_found"][match_id] = len(events)
        
        if not events:
            print(f"Skipping collection for {match_id} - no events found.")
            continue
            
        # Run collection for each event
        for ev in events:
            run_event_collection(match_id, ev['timestamp'])

    # 5. Process all newly collected raw data
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    
    for match in qualifying_matches:
        match_id = match['match_id']
        squad_dict = {match['nation']: squads.get(match['nation'].lower(), [])}
        
        raw_files = glob.glob(f"data/raw/{match_id}_*.jsonl") + glob.glob(f"data/matches/{match_id}/raw/{match_id}_*.jsonl")
        
        if not raw_files:
            continue
            
        print(f"\n--- NLP Processing for {match_id} ---")
        mentions_file = f"data/processed/{match_id}_mentions.jsonl"
        
        # Step 5a: Mentions
        mentions_records = []
        with open(mentions_file, 'w', encoding='utf-8') as out_f:
            for f in raw_files:
                platform = "reddit" if "reddit" in f or "posts.jsonl" in f or "comments.jsonl" in f else "bluesky"
                with open(f, 'r', encoding='utf-8') as rf:
                    for line in rf:
                        if not line.strip(): continue
                        try:
                            record = json.loads(line)
                            summary["posts_collected"][platform] += 1
                            
                            # Standardize text field
                            text = record.get('text', '') or record.get('selftext', '') or record.get('body', '')
                            if not text:
                                continue
                                
                            mentions = extract_mentions(text, squad_dict)
                            if mentions:
                                record['mentions'] = mentions
                                record['platform'] = record.get('platform', platform)
                                record['text'] = text
                                out_f.write(json.dumps(record, ensure_ascii=False) + '\n')
                                mentions_records.append(record)
                                
                                for m in mentions:
                                    summary["players_covered"].add(m['name'])
                        except json.JSONDecodeError:
                            pass
                            
        # Step 5b: Language detection
        lang_file = f"data/processed/{match_id}_lang.jsonl"
        lang_records = []
        with open(lang_file, 'w', encoding='utf-8') as out_f:
            for record in mentions_records:
                lang = detect_language(record['text'])
                record['lang'] = lang
                out_f.write(json.dumps(record, ensure_ascii=False) + '\n')
                if lang in ['en', 'fr', 'nl', 'de']: # filter to supported languages
                    lang_records.append(record)
                    
        # Step 5c: Sentiment Sampling & Scoring
        sentiment_file = f"data/processed/{match_id}_sentiment.jsonl"
        
        sampled_records = sample_for_scoring(lang_records)
        with open(sentiment_file, 'w', encoding='utf-8') as out_f:
            for record in sampled_records:
                if record.get('sampled', False):
                    text = record['text'][:1000] # safety limit
                    result = score_sentiment(text)
                    record['sentiment_label'] = result['label']
                    record['sentiment_score'] = result['score']
                    out_f.write(json.dumps(record, ensure_ascii=False) + '\n')

    # 6. Summary
    print("\n" + "="*40)
    print("PHASE 2 SUMMARY REPORT")
    print("="*40)
    print(f"Matches Processed: {summary['matches_processed']}")
    print("\nEvents Found per Match:")
    for m, c in summary['events_found'].items():
        print(f"  {m}: {c} events")
    print("\nPosts Collected per Platform:")
    for p, c in summary['posts_collected'].items():
        print(f"  {p}: {c} posts")
    print(f"\nUnique Players Covered: {len(summary['players_covered'])}")
    print("="*40)

if __name__ == "__main__":
    run_phase_2()
