import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from config.keywords import get_all_keywords


POSTS_URL = "https://arctic-shift.photon-reddit.com/api/posts/search"
COMMENTS_URL = "https://arctic-shift.photon-reddit.com/api/comments/search"
REQUEST_TIMEOUT = (10, 20)
PAGE_SLEEP_SECONDS = (2, 3)
SUBREDDIT_SLEEP_SECONDS = (10, 15)
PAGE_LIMIT = 100
SUBREDDIT_RECORD_CAP = 5000


MATCH_TARGETS = [
    

    {
        "match_id": "ger_vs_par_r32",
        "nation": "germany",
        "opponent": "Paraguay",
        "date_utc": "2026-06-29",
        "subreddits": ["soccer", "worldcup", "bundesliga"],
    },
    {
        "match_id": "ned_vs_mar_r32",
        "nation": "netherlands",
        "opponent": "Morocco",
        "date_utc": "2026-06-29",
        "subreddits": ["soccer", "worldcup", "Eredivisie"],
    },
    {
        "match_id": "fra_vs_swe_r32",
        "nation": "france",
        "opponent": "Sweden",
        "date_utc": "2026-06-30",
        "subreddits": ["soccer", "worldcup", "Ligue1"],
    },
    {
        "match_id": "eng_vs_cod_r32",
        "nation": "england",
        "opponent": "DR Congo",
        "date_utc": "2026-07-01",
        "subreddits": ["soccer", "worldcup", "ThreeLions"],
    },
]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def day_window(date_utc):
    start = datetime.fromisoformat(f"{date_utc}T00:00:00+00:00")
    end = datetime.fromtimestamp(start.timestamp() + 24 * 3600, tz=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


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
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "worldcup-discourse/1.0"},
            )
        except requests.RequestException as exc:
            if attempt == max_attempts:
                return None, f"connection_error: {exc}"
            backoff = 2 ** attempt
            print(f"  connection error on attempt {attempt}/3: {exc}; retrying in {backoff}s", flush=True)
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


def load_seen_ids(output_path):
    seen_ids = set()
    if not output_path.exists():
        return seen_ids

    with output_path.open("r", encoding="utf-8") as existing_file:
        for line in existing_file:
            if not line.strip():
                continue
            try:
                output = json.loads(line)
            except json.JSONDecodeError:
                continue
            endpoint_name = output.get("record_type")
            record = output.get("record") or {}
            record_id = record.get("id") or record.get("name")
            if endpoint_name and record_id:
                seen_ids.add(f"{endpoint_name}:{record_id}")
    return seen_ids


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
        print(
            f"  fetching {endpoint_name}s r/{subreddit} after={current_after} written={written}",
            flush=True,
        )
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


def collect_match_subreddit(match, subreddit, squads):
    after, before = day_window(match["date_utc"])
    keywords = build_keywords(match, squads)
    output_dir = Path("data/raw/reddit")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{match['match_id']}_{subreddit}.jsonl"
    done_path = output_dir / f"{match['match_id']}_{subreddit}.done"

    if done_path.exists():
        existing_count = sum(1 for line in output_path.open("r", encoding="utf-8") if line.strip()) if output_path.exists() else 0
        print(
            f"{match['match_id']} | r/{subreddit} | skipped completed file | records={existing_count}",
            flush=True,
        )
        return existing_count

    pages = 0
    seen_ids = load_seen_ids(output_path)
    written = len(seen_ids)
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
                print(f"  Arctic Shift 422 for {match['match_id']}/{subreddit}: {stop_reason}", flush=True)
                break
            if stop_reason not in ("exhaustion", "cap"):
                print(f"  Arctic Shift error for {match['match_id']}/{subreddit}: {stop_reason}", flush=True)
                break
            time.sleep(random.uniform(*PAGE_SLEEP_SECONDS))

    if stop_reason in ("exhaustion", "cap"):
        done_path.write_text(
            json.dumps(
                {
                    "match_id": match["match_id"],
                    "subreddit": subreddit,
                    "records": written,
                    "stop_reason": stop_reason,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    print(
        f"{match['match_id']} | r/{subreddit} | pages={pages} | "
        f"records={written} | stop={stop_reason}",
        flush=True,
    )
    return written


def main():
    squads = load_json("config/squads.json")
    grand_total = 0

    for match in MATCH_TARGETS:
        print(f"\n=== {match['match_id']} ===", flush=True)
        match_total = 0
        subreddit_totals = {}

        for index, subreddit in enumerate(match["subreddits"]):
            written = collect_match_subreddit(match, subreddit, squads)
            subreddit_totals[subreddit] = written
            match_total += written
            grand_total += written

            if index < len(match["subreddits"]) - 1:
                time.sleep(random.uniform(*SUBREDDIT_SLEEP_SECONDS))

        print(f"Summary for {match['match_id']}:", flush=True)
        for subreddit, total in subreddit_totals.items():
            print(f"  r/{subreddit}: {total} records", flush=True)
        print(f"  match total: {match_total} records", flush=True)

    print(f"\nGrand total across all matches: {grand_total} records", flush=True)


if __name__ == "__main__":
    main()
