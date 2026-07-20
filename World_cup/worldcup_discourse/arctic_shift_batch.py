import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from config.keywords import get_all_keywords


POSTS_URL = "https://arctic-shift.photon-reddit.com/api/posts/search"
COMMENTS_URL = "https://arctic-shift.photon-reddit.com/api/comments/search"
REQUEST_TIMEOUT_SECONDS = 30
PAGE_SLEEP_SECONDS = (2, 3)
SUBREDDIT_SLEEP_SECONDS = (10, 15)
PAGE_LIMIT = 100
SUBREDDIT_RECORD_CAP = 5000

# Only the World Cup match/subreddit pairs that were not already scraped in the
# prior Arctic Shift run.
MATCH_TARGETS = {
    "ger_vs_cur_gd1": ["worldcup", "bundesliga"],
    "fra_vs_sen_gd1": ["worldcup", "Ligue1"],
    "eng_vs_cro_gd1": ["ThreeLions"],
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_schedule_by_match():
    return {match["match_id"]: match for match in load_json("config/schedule.json")}


def load_squads():
    return load_json("config/squads.json")


def kickoff_window(match):
    kickoff = datetime.fromisoformat(match["kickoff_utc"].replace("Z", "+00:00"))
    kickoff_ts = int(kickoff.timestamp())
    return kickoff_ts - 3600, kickoff_ts + (6 * 3600)


def build_keywords(match, squads):
    keywords = {
        match["match_id"],
        match["nation"],
        match["opponent"],
        "world cup",
        "worldcup",
    }

    nation_squad = squads.get(match["nation"].lower(), [])
    for player in nation_squad:
        if not isinstance(player, dict):
            continue
        name = player.get("name")
        if name:
            keywords.add(name)
        for alias in player.get("aliases") or []:
            if alias:
                keywords.add(alias)

    for keyword in get_all_keywords("en"):
        if keyword and len(keyword) >= 3:
            keywords.add(keyword)

    return sorted({kw.lower() for kw in keywords if kw and kw.strip()})


def record_text(record, record_type):
    if record_type == "post":
        return " ".join(
            str(record.get(field) or "")
            for field in ("title", "selftext", "url", "permalink")
        ).lower()

    return str(record.get("body") or "").lower()


def matches_keywords(record, record_type, keywords):
    text = record_text(record, record_type)
    return any(keyword in text for keyword in keywords)


def request_page(url, params, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
                headers={"User-Agent": "worldcup-discourse/1.0"},
            )
        except requests.RequestException as exc:
            if attempt == max_attempts:
                return None, f"connection_error: {exc}"
            backoff = 2 ** attempt
            print(f"  connection error on attempt {attempt}/3: {exc}; retrying in {backoff}s")
            time.sleep(backoff)
            continue

        if response.status_code == 422:
            return None, f"422: {response.text[:500]}"
        if response.status_code >= 400:
            return None, f"HTTP {response.status_code}: {response.text[:500]}"

        try:
            return response.json(), None
        except ValueError as exc:
            return None, f"json_error: {exc}"

    return None, "unknown_error"


def fetch_endpoint(endpoint_name, url, subreddit, after, before, keywords, output_file, seen_ids, written, pages):
    current_after = after
    exhausted = False

    while written < SUBREDDIT_RECORD_CAP:
        params = {
            "subreddit": subreddit,
            "after": current_after,
            "before": before,
            "limit": PAGE_LIMIT,
            "sort": "asc",
        }
        data, error = request_page(url, params)
        pages += 1

        if error:
            return written, pages, error

        records = data.get("data") or []
        if not records:
            exhausted = True
            break

        for record in records:
            record_id = record.get("id") or record.get("name")
            seen_key = f"{endpoint_name}:{record_id}"
            if record_id and seen_key in seen_ids:
                continue
            if record_id:
                seen_ids.add(seen_key)

            if not matches_keywords(record, endpoint_name, keywords):
                continue

            output = {
                "record_type": endpoint_name,
                "subreddit": subreddit,
                "source": "arctic_shift",
                "record": record,
            }
            output_file.write(json.dumps(output, ensure_ascii=False) + "\n")
            written += 1
            if written >= SUBREDDIT_RECORD_CAP:
                return written, pages, "cap"

        next_after = records[-1].get("created_utc", current_after)
        if next_after == current_after:
            exhausted = True
            break
        current_after = int(next_after)
        time.sleep(random.uniform(*PAGE_SLEEP_SECONDS))

    if written >= SUBREDDIT_RECORD_CAP:
        return written, pages, "cap"
    if exhausted:
        return written, pages, "exhaustion"
    return written, pages, "cap"


def collect_match_subreddit(match_key, subreddit, match, squads):
    after, before = kickoff_window(match)
    keywords = build_keywords(match, squads)
    output_dir = Path("data/raw/reddit")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{match_key}_{subreddit}.jsonl"

    pages = 0
    written = 0
    seen_ids = set()
    stop_reason = "exhaustion"

    with output_path.open("a", encoding="utf-8") as output_file:
        for endpoint_name, url in (("post", POSTS_URL), ("comment", COMMENTS_URL)):
            written, pages, stop_reason = fetch_endpoint(
                endpoint_name,
                url,
                subreddit,
                after,
                before,
                keywords,
                output_file,
                seen_ids,
                written,
                pages,
            )
            output_file.flush()
            if stop_reason == "cap":
                break
            if stop_reason.startswith("422"):
                print(f"  Arctic Shift 422 for {match_key}/{subreddit}: {stop_reason}")
                break
            if stop_reason not in ("exhaustion", "cap"):
                print(f"  Arctic Shift error for {match_key}/{subreddit}: {stop_reason}")
                break
            time.sleep(random.uniform(*PAGE_SLEEP_SECONDS))

    print(
        f"{match_key} | r/{subreddit} | pages={pages} | "
        f"records={written} | stop={stop_reason}"
    )
    return written


def main():
    schedule_by_match = load_schedule_by_match()
    squads = load_squads()
    grand_total = 0

    for match_key, subreddits in MATCH_TARGETS.items():
        match = schedule_by_match.get(match_key)
        if not match:
            print(f"{match_key} | skipped | missing schedule metadata")
            continue

        print(f"\n=== {match_key} ===")
        match_total = 0
        subreddit_totals = {}

        for index, subreddit in enumerate(subreddits):
            written = collect_match_subreddit(match_key, subreddit, match, squads)
            subreddit_totals[subreddit] = written
            match_total += written
            grand_total += written

            if index < len(subreddits) - 1:
                time.sleep(random.uniform(*SUBREDDIT_SLEEP_SECONDS))

        print(f"Summary for {match_key}:")
        for subreddit, total in subreddit_totals.items():
            print(f"  r/{subreddit}: {total} records")
        print(f"  match total: {match_total} records")

    print(f"\nGrand total across all matches: {grand_total} records")


if __name__ == "__main__":
    main()
