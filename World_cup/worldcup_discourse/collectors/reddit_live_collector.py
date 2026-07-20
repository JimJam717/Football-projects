import os
import sys
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def collect_live_reddit(match_id, subreddits, window_start, window_end):
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    user_agent = os.environ.get("REDDIT_USER_AGENT")

    if not all([client_id, client_secret, user_agent]):
        logger.warning(f"[{match_id}] Reddit credentials missing. Skipping reddit_live_collector.")
        return {"posts": 0, "comments": 0, "skipped": True, "reason": "missing_credentials"}

    try:
        import praw
    except ImportError:
        logger.error(f"[{match_id}] PRAW not installed. Skipping reddit_live_collector.")
        return {"posts": 0, "comments": 0, "skipped": True, "reason": "praw_missing"}

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent
    )

    Path("data/raw").mkdir(parents=True, exist_ok=True)
    total_posts = 0
    total_comments = 0

    for sub_name in subreddits:
        post_file = Path(f"data/raw/{match_id}_{sub_name}_live_posts.jsonl")
        comment_file = Path(f"data/raw/{match_id}_{sub_name}_live_comments.jsonl")
        
        logger.info(f"[{match_id}] Collecting live Reddit posts for r/{sub_name}")
        
        try:
            subreddit = reddit.subreddit(sub_name)
            
            with open(post_file, 'a', encoding='utf-8') as pf, open(comment_file, 'a', encoding='utf-8') as cf:
                # praw's .new() fetches up to 1000 items
                for submission in subreddit.new(limit=1000):
                    created = submission.created_utc
                    
                    # Stop if we've gone past the window start (since .new() is newest first)
                    if created < window_start:
                        break
                        
                    if window_start <= created <= window_end:
                        post_dict = {
                            "id": submission.id,
                            "subreddit": sub_name,
                            "created_utc": created,
                            "author": str(submission.author) if submission.author else "[deleted]",
                            "title": submission.title,
                            "selftext": submission.selftext,
                            "url": submission.url,
                            "score": submission.score
                        }
                        pf.write(json.dumps(post_dict, ensure_ascii=False) + '\n')
                        total_posts += 1
                        
                        # Fetch comments
                        submission.comments.replace_more(limit=0)
                        for comment in submission.comments.list():
                            c_created = comment.created_utc
                            if window_start <= c_created <= window_end:
                                comment_dict = {
                                    "id": comment.id,
                                    "subreddit": sub_name,
                                    "created_utc": c_created,
                                    "author": str(comment.author) if comment.author else "[deleted]",
                                    "body": comment.body,
                                    "parent_id": comment.parent_id,
                                    "link_id": comment.link_id,
                                    "score": comment.score
                                }
                                cf.write(json.dumps(comment_dict, ensure_ascii=False) + '\n')
                                total_comments += 1
        except Exception as e:
            logger.error(f"[{match_id}] Error collecting from r/{sub_name}: {e}")

    return {"posts": total_posts, "comments": total_comments, "skipped": False, "reason": None}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    collect_live_reddit("test_match", ["soccer"], 0, 9999999999)
