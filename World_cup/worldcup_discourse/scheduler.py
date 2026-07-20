import sys
import json
import logging
import multiprocessing
import queue
from pathlib import Path
from datetime import datetime

from collectors.arctic_shift_collector import collect_from_arctic_shift
from collectors.bluesky_collector import search_posts
from collectors.reddit_live_collector import collect_live_reddit

COLLECTOR_TIMEOUT_SECONDS = 5 * 60

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_json(filepath):
    if isinstance(filepath, Path):
        filepath = str(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_squad_for_nation(nation, squads):
    nation_lower = nation.lower()
    for n, players in squads.items():
        if n.lower() == nation_lower:
            return players
    return []

def get_match_kickoff_timestamp(match_id):
    try:
        schedule_data = load_json(Path('config/schedule.json'))
    except Exception as e:
        logger.error(f"[{match_id}] Failed to load schedule.json: {e}", exc_info=True)
        return None

    for match in schedule_data:
        if match["match_id"] == match_id:
            kickoff_dt = datetime.fromisoformat(match["kickoff_utc"].replace('Z', '+00:00'))
            return int(kickoff_dt.timestamp())

    logger.warning(f"[{match_id}] Match not found in schedule.json")
    return None

def get_mapped_match_ids():
    try:
        match_map = load_json(Path('config/match_url_map.json'))
    except Exception as e:
        logger.error(f"Failed to load match_url_map.json: {e}", exc_info=True)
        return []

    return list(match_map.keys())

def _collector_worker(platform, result_queue, match_id, squad, subreddits, window_start, window_end):
    try:
        if platform == "bluesky":
            result = search_posts(match_id, squad, window_start, window_end)
        elif platform == "arctic_shift":
            result = collect_from_arctic_shift(match_id, after=window_start, before=window_end, subreddits=subreddits)
        elif platform == "reddit_live":
            result = collect_live_reddit(match_id, subreddits, window_start, window_end)
        else:
            result = {"error": f"unknown platform {platform}"}
        result_queue.put({"ok": True, "result": result})
    except Exception as e:
        logger.exception(f"[{match_id}] {platform} collector failed")
        result_queue.put({"ok": False, "error": str(e)})

def run_collector_with_timeout(platform, match_id, squad, subreddits, window_start, window_end, timeout=COLLECTOR_TIMEOUT_SECONDS):
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=_collector_worker,
        args=(platform, result_queue, match_id, squad, subreddits, window_start, window_end),
    )
    process.start()
    process.join(timeout)

    if process.is_alive():
        process.terminate()
        process.join(10)
        if process.is_alive():
            process.kill()
            process.join()
        logger.error(f"[{match_id}] {platform} collector timed out after {timeout} seconds")
        return {"timed_out": True, "posts": 0, "comments": 0}

    try:
        payload = result_queue.get_nowait()
    except queue.Empty:
        logger.error(f"[{match_id}] {platform} collector exited without returning a result")
        return {"error": "no_result", "posts": 0, "comments": 0}

    if not payload.get("ok"):
        logger.error(f"[{match_id}] {platform} collector error: {payload.get('error')}")
        return {"error": payload.get("error"), "posts": 0, "comments": 0}

    return payload.get("result") or {"posts": 0, "comments": 0}

def run_match_collection(match_id):
    kickoff_timestamp = get_match_kickoff_timestamp(match_id)
    if kickoff_timestamp is None:
        return

    run_event_collection(match_id, kickoff_timestamp)

def run_event_collection(match_id, event_timestamp):
    """
    Fires collection calls for a window of event_timestamp - 1hr to event_timestamp + 6hr.
    For match-level collection, pass the configured kickoff timestamp.
    """
    window_start = int(event_timestamp) - 3600
    window_end = int(event_timestamp) + (6 * 3600)
    
    logger.info(f"[{match_id}] Running event collection for window: {window_start} to {window_end}")
    
    try:
        schedule_data = load_json(Path('config/schedule.json'))
        squads_data = load_json(Path('config/squads.json'))
    except Exception as e:
        logger.error(f"[{match_id}] Failed to load config: {e}", exc_info=True)
        return
        
    subreddits = []
    nation = ""
    for match in schedule_data:
        if match["match_id"] == match_id:
            subreddits = match.get("subreddits", [])
            nation = match["nation"]
            break
            
    squad = get_squad_for_nation(nation, squads_data)
    
    # 1. Bluesky searchPosts API
    logger.info(f"[{match_id}] Starting Bluesky searchPosts...")
    bluesky_result = run_collector_with_timeout("bluesky", match_id, squad, subreddits, window_start, window_end)
    logger.info(f"[{match_id}] Bluesky result: {bluesky_result}")
        
    # 2. Arctic Shift query
    logger.info(f"[{match_id}] Starting Arctic Shift query...")
    arctic_result = run_collector_with_timeout("arctic_shift", match_id, squad, subreddits, window_start, window_end)
    logger.info(f"[{match_id}] Arctic Shift result: {arctic_result}")
        
    # 3. Reddit Live Collector
    logger.info(f"[{match_id}] Starting Reddit Live Collection...")
    reddit_live_result = run_collector_with_timeout("reddit_live", match_id, squad, subreddits, window_start, window_end)
    logger.info(f"[{match_id}] Reddit Live result: {reddit_live_result}")

    return {
        "bluesky": bluesky_result,
        "arctic_shift": arctic_result,
        "reddit_live": reddit_live_result,
    }

if __name__ == "__main__":
    for mapped_match_id in get_mapped_match_ids():
        run_match_collection(mapped_match_id)
