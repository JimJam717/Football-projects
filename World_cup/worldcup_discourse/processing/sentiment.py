import sys
import random
from transformers import pipeline

# Load model once at module level
try:
    # We use truncation=True, max_length=512 for inference
    sentiment_pipeline = pipeline(
        "sentiment-analysis",
        model="cardiffnlp/twitter-xlm-roberta-base-sentiment",
        tokenizer="cardiffnlp/twitter-xlm-roberta-base-sentiment",
        truncation=True,
        max_length=512
    )
except Exception as e:
    print(f"[sentiment] model load failed: {e}", file=sys.stderr)
    sentiment_pipeline = None

# cardiffnlp/twitter-xlm-roberta-base-sentiment output mapping:
# LABEL_0: negative
# LABEL_1: neutral
# LABEL_2: positive

LABEL_MAPPING = {
    "LABEL_0": "negative",
    "LABEL_1": "neutral",
    "LABEL_2": "positive"
}

def sample_for_scoring(records: list) -> list:
    track_a_records = []
    track_b_records = []

    for record in records:
        track = record.get("track", "player") # Default to "player" if track is absent
        if track == "player":
            track_a_records.append(record)
        elif track == "discourse":
            track_b_records.append(record)
        else:
            # For now, let's assume they should go to Track A if not discourse
            track_a_records.append(record)


    # Track A sampling
    player_mentions = {} # {player_name: [records]}
    for record in track_a_records:
        for player in record.get("matched_players", []):
            player_name = player.get("name")
            if player_name:
                if player_name not in player_mentions:
                    player_mentions[player_name] = []
                player_mentions[player_name].append(record)

    sampled_track_a = []
    excluded_players = []
    
    # Sort players by mention count for proportional sampling
    sorted_players = sorted(player_mentions.items(), key=lambda item: len(item[1]), reverse=True)

    # Guaranteed floor and cap for Track A
    TRACK_A_CAP = 500
    MIN_MENTIONS_FLOOR = 15
    GUARANTEED_MIN_PER_PLAYER = 30

    # First, handle players meeting the floor threshold
    qualifying_players = []
    for player_name, player_records in sorted_players:
        if len(player_records) >= MIN_MENTIONS_FLOOR:
            qualifying_players.append((player_name, player_records))
        else:
            excluded_players.append((player_name, len(player_records)))

    # Collect guaranteed minimums and track remaining capacity
    current_track_a_size = 0
    temp_track_a_sample = [] # To hold records for qualifying players
    
    for player_name, player_records in qualifying_players:
        # Take min(total records, guaranteed_min)
        num_to_sample = min(len(player_records), GUARANTEED_MIN_PER_PLAYER)
        
        # Add 'sampled': True to these records
        for i in range(num_to_sample):
            player_records[i]["sampled"] = True
            temp_track_a_sample.append(player_records[i])
        current_track_a_size += num_to_sample

    # If already over cap, we need to trim. This part is not explicitly detailed in the prompt
    # but implicitly, total Track A records cannot exceed 500.
    # For simplicity, if guaranteed minimums exceed the cap, we just take the first 500.
    # A more sophisticated approach would be to proportionally reduce.
    if current_track_a_size > TRACK_A_CAP:
        sampled_track_a = temp_track_a_sample[:TRACK_A_CAP]
        # print(f"[sentiment] Warning: Track A guaranteed minimums exceeded cap. Truncating to {TRACK_A_CAP} records.", file=sys.stderr)
    else:
        sampled_track_a = temp_track_a_sample

        # Now, fill remaining slots proportionally up to cap
        remaining_cap = TRACK_A_CAP - len(sampled_track_a)
        
        if remaining_cap > 0:
            # Collect all remaining unsampled records from qualifying players
            unsampled_records = []
            for player_name, player_records in qualifying_players:
                # Add records beyond the guaranteed minimum, if any, and mark as sampled
                for i in range(GUARANTEED_MIN_PER_PLAYER, len(player_records)):
                    if player_records[i] not in sampled_track_a: # Avoid duplicates if some were already added
                        player_records[i]["sampled"] = True
                        unsampled_records.append(player_records[i])
            
            # Simple proportional filling: shuffle and take from remaining_cap
            random.shuffle(unsampled_records)
            sampled_track_a.extend(unsampled_records[:remaining_cap])

    # Track B sampling (uniform random sample up to 200 records)
    TRACK_B_CAP = 200
    sampled_track_b = []
    if len(track_b_records) > TRACK_B_CAP:
        sampled_track_b = random.sample(track_b_records, TRACK_B_CAP)
        for record in sampled_track_b:
            record["sampled"] = True
    else:
        sampled_track_b = track_b_records
        for record in sampled_track_b:
            record["sampled"] = True

    # Mark records not sampled as "sampled": False
    for record in records:
        if "sampled" not in record:
            record["sampled"] = False

    # Print sampling summary
    print("--- Sampling Summary ---")
    print(f"Total input records: {len(records)}")
    print(f"Track A (player) records: {len(track_a_records)}")
    print(f"Track B (discourse) records: {len(track_b_records)}")
    print(f"Players above floor threshold ({MIN_MENTIONS_FLOOR}): {len(qualifying_players)}")
    print(f"Players excluded: {len(excluded_players)}")
    if excluded_players:
        preview = ", ".join(
            f"{player} ({count})"
            for player, count in excluded_players[:10]
        )
        suffix = "..." if len(excluded_players) > 10 else ""
        print(
            f"Excluded low-mention players (<{MIN_MENTIONS_FLOOR} mentions): {preview}{suffix}"
        )
    print(f"Final Track A sample size: {len(sampled_track_a)}")
    print(f"Final Track B sample size: {len(sampled_track_b)}")
    print("------------------------")

    return sampled_track_a + sampled_track_b

def score_sentiment(text):
    if not sentiment_pipeline:
        return {"label": "error", "score": 0.0}
        
    try:
        # returns list of dicts: [{'label': 'LABEL_X', 'score': 0.99}]
        result = sentiment_pipeline(text)[0]
        label_raw = result['label']
        score = float(result['score'])
        
        label_mapped = LABEL_MAPPING.get(label_raw, label_raw.lower())
        if label_mapped not in ['positive', 'neutral', 'negative']:
            label_mapped = 'error'
        
        return {"label": label_mapped, "score": score}
    except Exception as e:
        print(f"[sentiment] scoring error: {e}", file=sys.stderr)
        return {"label": "error", "score": 0.0}

if __name__ == "__main__":
    print(score_sentiment("I love this!"))
    print(score_sentiment("I hate this!"))
    print(score_sentiment("This is a table."))
