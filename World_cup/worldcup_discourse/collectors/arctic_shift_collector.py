import json
import logging
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 30


def fetch_json(url, timeout=REQUEST_TIMEOUT_SECONDS):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                return json.loads(response.read().decode("utf-8")), None

            return None, f"HTTP {response.status}"
    except urllib.error.HTTPError as e:
        body = e.read(1000).decode("utf-8", "replace")
        logger.warning(f"[arctic_shift] HTTP {e.code} {e.reason} for {url}. Body: {body}")
        return None, f"HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
        logger.warning(f"[arctic_shift] request timed out or failed for {url}: {e}")
        return None, "timeout_or_url_error"
    except json.JSONDecodeError as e:
        logger.warning(f"[arctic_shift] JSON decode error for {url}: {e}")
        return None, "json_decode_error"
    except Exception as e:
        logger.warning(f"[arctic_shift] unexpected error for {url}: {e}")
        return None, "unexpected_error"


def build_search_url(base_url, subreddit, after, before):
    params = {
        "subreddit": subreddit,
        "after": int(after),
        "before": int(before),
        "limit": 100,
        "sort": "asc",
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def collect_from_arctic_shift(match_id, after, before, subreddits):
    base_url_posts = "https://arctic-shift.photon-reddit.com/api/posts/search"
    base_url_comments = "https://arctic-shift.photon-reddit.com/api/comments/search"

    Path("data/raw").mkdir(parents=True, exist_ok=True)

    total_posts = 0
    total_comments = 0
    failures = 0

    for subreddit in subreddits:
        logger.info(f"[{match_id}] Arctic Shift collecting posts for r/{subreddit}")
        post_file = Path(f"data/raw/{match_id}_{subreddit}_posts.jsonl")
        comment_file = Path(f"data/raw/{match_id}_{subreddit}_comments.jsonl")

        current_after = int(after)
        with open(post_file, "a", encoding="utf-8") as f:
            while True:
                url = build_search_url(base_url_posts, subreddit, current_after, before)
                data, error = fetch_json(url)
                if error:
                    failures += 1
                    break
                if not data or not data.get("data"):
                    break

                records = data["data"]
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    total_posts += 1

                next_after = records[-1].get("created_utc", current_after)
                if next_after == current_after or len(records) < 100:
                    break
                current_after = int(next_after)

        logger.info(f"[{match_id}] Arctic Shift collecting comments for r/{subreddit}")
        current_after = int(after)
        with open(comment_file, "a", encoding="utf-8") as f:
            while True:
                url = build_search_url(base_url_comments, subreddit, current_after, before)
                data, error = fetch_json(url)
                if error:
                    failures += 1
                    break
                if not data or not data.get("data"):
                    break

                records = data["data"]
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    total_comments += 1

                next_after = records[-1].get("created_utc", current_after)
                if next_after == current_after or len(records) < 100:
                    break
                current_after = int(next_after)

    return {"posts": total_posts, "comments": total_comments, "failures": failures}


if __name__ == "__main__":
    from datetime import datetime, timezone

    logging.basicConfig(level=logging.INFO)
    after_dt = int(datetime(2022, 12, 14, 14, 0, tzinfo=timezone.utc).timestamp())
    before_dt = int(datetime(2022, 12, 15, 2, 0, tzinfo=timezone.utc).timestamp())
    print(collect_from_arctic_shift("test_match", after=after_dt, before=before_dt, subreddits=["testsubreddit"]))
