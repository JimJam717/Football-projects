import sys
import json
import os
import urllib.request
import urllib.parse
import urllib.error
import time
from datetime import datetime, timezone
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

DISCOURSE_KEYWORDS = [
    "immigrant",
    "immigration",
    "foreign",
    "foreigner",
    "not really",
    "doesn't represent",
    "belong here",
    "go back",
    "heritage",
    "ancestry",
    "roots",
    "second generation",
    "naturalized",
    "dual national",
]

def _get_bluesky_credentials():
    identifier = (
        os.environ.get("BSKY_IDENTIFIER")
        or os.environ.get("BLUESKY_IDENTIFIER")
        or os.environ.get("BSKY_HANDLE")
        or os.environ.get("BLUESKY_USERNAME")
    )
    password = os.environ.get("BSKY_PASSWORD") or os.environ.get("BLUESKY_PASSWORD")
    return identifier, password

def _create_session(timeout=30):
    identifier, password = _get_bluesky_credentials()
    if not identifier or not password:
        logger.warning(
            "Bluesky credentials missing. Set BSKY_IDENTIFIER and BSKY_PASSWORD "
            "or BLUESKY_IDENTIFIER and BLUESKY_PASSWORD. Skipping Bluesky collector."
        )
        return None

    payload = json.dumps({"identifier": identifier, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.warning(f"Bluesky auth failed: {e.code} {e.reason}. Skipping Bluesky collector.")
        return None
    except Exception as e:
        logger.warning(f"Bluesky auth failed: {e}. Skipping Bluesky collector.")
        return None

    access_jwt = data.get("accessJwt")
    if not access_jwt:
        logger.warning("Bluesky auth response did not include accessJwt. Skipping Bluesky collector.")
        return None

    return access_jwt

def search_posts(match_id: str, squads: list, start_time: int, end_time: int):
    access_jwt = _create_session()
    if not access_jwt:
        return {"posts": 0, "skipped": True, "reason": "missing_or_invalid_credentials"}

    # Convert timestamps to ISO 8601 strings
    since_str = datetime.fromtimestamp(start_time, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    until_str = datetime.fromtimestamp(end_time, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    terms = []
    # Add player names and aliases
    for player in squads:
        if not isinstance(player, dict):
            continue
        player_name = player.get("name")
        if player_name:
            terms.append(player_name)
        aliases = player.get("aliases") or []
        for alias in aliases:
            if alias and alias not in terms:
                terms.append(alias)
                
    # Add keywords
    for keyword in DISCOURSE_KEYWORDS:
        if keyword not in terms:
            terms.append(keyword)

    output_path = Path("data") / "raw" / f"{match_id}_bluesky_posts.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    seen_posts = set()
    matched_count = 0

    with output_path.open("a", encoding="utf-8") as output_file:
        for term in terms:
            cursor = ""
            while True:
                params = {
                    "q": term,
                    "since": since_str,
                    "until": until_str,
                    "limit": 100
                }
                if cursor:
                    params["cursor"] = cursor

                url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?{urllib.parse.urlencode(params)}"
                
                req = urllib.request.Request(
                    url,
                    headers={
                        'User-Agent': 'Mozilla/5.0',
                        'Authorization': f'Bearer {access_jwt}',
                    },
                )
                try:
                    with urllib.request.urlopen(req, timeout=30) as response:
                        if response.status == 200:
                            data = json.loads(response.read().decode('utf-8'))
                            posts = data.get("posts", [])
                            
                            for post in posts:
                                uri = post.get("uri")
                                if uri in seen_posts:
                                    continue
                                seen_posts.add(uri)
                                
                                record = post.get("record", {})
                                text = record.get("text", "")
                                author = post.get("author", {})
                                
                                # Check if it matches player or discourse track
                                text_lower = text.lower()
                                matched_players = [p for p in terms if p in squads and p.lower() in text_lower] # simplified
                                matched_keywords = [k for k in DISCOURSE_KEYWORDS if k.lower() in text_lower]
                                
                                output_record = {
                                    "match_id": match_id,
                                    "platform": "bluesky",
                                    "track": "player" if matched_players else "discourse",
                                    "post_id": uri,
                                    "author_did": author.get("did", ""),
                                    "text": text,
                                    "created_at": record.get("createdAt", ""),
                                    "matched_players": matched_players,
                                    "matched_keywords": [] if matched_players else matched_keywords,
                                    "collected_at": datetime.now(timezone.utc).isoformat(),
                                }
                                output_file.write(json.dumps(output_record, ensure_ascii=False) + "\n")
                                matched_count += 1
                                
                            cursor = data.get("cursor")
                            if not cursor:
                                break
                            time.sleep(0.5) # Basic rate limiting
                except urllib.error.HTTPError as e:
                    logger.error(f"[{match_id}] HTTP error fetching Bluesky search for term '{term}': {e.code} {e.reason}")
                    break
                except Exception as e:
                    logger.error(f"[{match_id}] Error fetching Bluesky search for term '{term}': {e}")
                    break

    logger.info(f"[{match_id}] Bluesky collector stopped. Total matched records: {matched_count}")
    return {"posts": matched_count, "skipped": False, "reason": None}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    search_posts("test_match", [{"name": "Mbappe", "aliases": ["Mbappe"]}], int(time.time()) - 3600, int(time.time()))
