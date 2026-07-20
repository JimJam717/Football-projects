import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _load_schedule():
    with open("config/schedule.json", "r", encoding="utf-8") as f:
        return json.load(f)


def get_match_kickoff_timestamp(match_id):
    try:
        schedule = _load_schedule()
    except Exception as e:
        logger.error(f"[{match_id}] Failed to load schedule.json: {e}")
        return None

    for match in schedule:
        if match["match_id"] == match_id:
            kickoff_dt = datetime.fromisoformat(match["kickoff_utc"].replace("Z", "+00:00"))
            return int(kickoff_dt.timestamp())

    logger.warning(f"[{match_id}] Match not found in schedule.json")
    return None


def get_match_events(match_id):
    kickoff_ts = get_match_kickoff_timestamp(match_id)
    if kickoff_ts is None:
        return []

    return [
        {
            "match_id": match_id,
            "event_type": "kickoff",
            "player": "unknown",
            "team": "unknown",
            "timestamp": kickoff_ts,
        }
    ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(get_match_events("sco_vs_hai_gd1"))
