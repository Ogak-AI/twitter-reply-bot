"""
main.py — X/Twitter Reply Bot.
Polls X account RSS feeds. On new tweet -> generate human reply -> post via Buffer API.
Loads secrets from environment variables / .env file.
"""

import logging
import logging.handlers
import sys
import time
import yaml
import os
import re
import random
import colorlog
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]",
    flags=re.UNICODE,
)

def strip_emojis(text: str) -> str:
    if not text:
        return text
    text = _EMOJI_PATTERN.sub("", text)
    text = re.sub(r"[\ufe00-\ufe0f]", "", text)
    return text


def load_config(path="config.yaml") -> dict:
    with open(path) as f:
        raw = f.read()

    def expand(match):
        var, _, default = match.group(1).partition(":-")
        return os.environ.get(var, default) if default else os.environ.get(var, "")

    raw = re.sub(r"\$\{([^}]+)\}", expand, raw)
    return yaml.safe_load(raw)


def setup_logging(config: dict):
    Path("logs").mkdir(exist_ok=True)
    level = getattr(logging, config["logging"]["level"], logging.INFO)

    console = colorlog.StreamHandler()
    if hasattr(console.stream, "reconfigure"):
        try:
            console.stream.reconfigure(encoding="utf-8", errors="replace")
        except TypeError:
            console.stream.reconfigure(errors="replace")
    console.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s] %(levelname)s%(reset)s — %(message)s",
        datefmt="%H:%M:%S",
        log_colors={"DEBUG": "cyan", "INFO": "green",
                    "WARNING": "yellow", "ERROR": "red", "CRITICAL": "bold_red"}
    ))
    file_handler = logging.handlers.RotatingFileHandler(
        config["logging"]["log_file"], maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s — %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(file_handler)


logger = logging.getLogger(__name__)


def resolve_channel_id(channel_id: str | None) -> str | None:
    if not channel_id:
        return None
    normalized = channel_id.strip()
    if normalized.lower().startswith("your_") or normalized.lower().endswith("_here"):
        return None
    return normalized


def process_article(article: dict, config: dict):
    from generator import generate_tweet
    from buffer_client import post_to_buffer
    from database import mark_seen, save_post, update_post

    api_key    = config["buffer"]["api_key"]
    api_url    = config["buffer"].get("api_url", "https://api.buffer.com")
    channel_id = resolve_channel_id(config["buffer"]["channel_id"])
    mode       = config["buffer"].get("mode", "addToQueue")

    logger.info("")
    category = article.get('category', 'general')
    logger.info(f"[NEW] [{article['source']}] [{category}] {article['title'][:75]}")

    try:
        reply_text = generate_tweet(article, config["ai"])
        reply_text = strip_emojis(reply_text).strip()
        # Format the final post to Twitter: @username [reply] [link to tweet]
        author = article.get("source", "user").replace("@", "").strip()
        tweet = f"@{author} {reply_text} {article['url']}"
        tweet = strip_emojis(tweet)
        tweet = re.sub(r"\s+", " ", tweet).strip()
    except Exception as e:
        logger.error(f"Tweet generation failed: {e}")
        return

    logger.info(f"[REPLY] ({len(tweet)} chars): {tweet}")

    post_id = save_post(article["url"], tweet)
    mark_seen(article["url"], article["title"], article["source"])

    if not channel_id:
        logger.info("BUFFER_CHANNEL_ID not configured — skipping Buffer post.")
        update_post(post_id, "no_channel")
        return

    time.sleep(random.uniform(2.0, 5.0))
    result = post_to_buffer(tweet, channel_id, api_key, api_url=api_url, mode=mode)

    if result["success"]:
        update_post(post_id, "posted", buffer_post_id=result["post_id"])
        logger.info(f"[OK] Posted | Buffer ID: {result['post_id']} | Due: {result['due_at']}")
    else:
        update_post(post_id, "failed", error=result["error"])
        logger.error(f"[FAIL] Buffer post failed: {result['error']}")


def run():
    from fetcher import fetch_new_articles
    from database import init_db, is_seen, get_stats, mark_seen

    config      = load_config()
    poll_secs   = config["listener"]["poll_interval_seconds"]
    max_age_hrs = config["listener"]["max_article_age_hours"]
    feeds       = config.get("x_accounts", [])

    Path("logs").mkdir(exist_ok=True)
    setup_logging(config)
    init_db()

    logger.info("=" * 58)
    logger.info("X/Twitter Reply Bot — Buffer API Edition")
    logger.info(f"Accounts : {len(feeds)} sources")
    # Show category breakdown
    from collections import Counter
    cats = Counter(f.get('category', 'general') for f in feeds)
    for cat, count in sorted(cats.items()):
        logger.info(f"           {cat}: {count}")
    logger.info(f"Poll     : every {poll_secs}s ({poll_secs // 60}min)")
    logger.info(f"AI       : {config['ai']['provider']} / {config['ai']['model']}")
    channel_id = resolve_channel_id(config['buffer']['channel_id'])
    logger.info(f"Channel  : {channel_id or 'NOT SET'}")
    logger.info(f"Mode     : {config['buffer']['mode']}")
    logger.info("=" * 58)

    if not config["buffer"]["api_key"]:
        logger.error("BUFFER_API_KEY not set. Add it to .env and restart.")
        return
    if not channel_id:
        logger.warning("BUFFER_CHANNEL_ID not set or still placeholder. Buffer posting will be skipped.")

    session_count = 0
    seen_urls: set = set()
    logger.info("Init pass — scanning existing articles...")
    
    # Fetch all articles currently in the RSS feeds
    temp_seen = set()
    existing_articles = fetch_new_articles(feeds, temp_seen, max_age_hours=max_age_hrs)
    
    # Find unseen articles
    unseen_articles = [art for art in existing_articles if not is_seen(art["url"])]
    
    if unseen_articles:
        logger.info(f"Found {len(unseen_articles)} unseen article(s) in feeds.")
        # Sort oldest to newest
        unseen_articles.sort(key=lambda x: x.get("published_at", ""))
        latest_unseen = unseen_articles[-1]
        
        # Process the single most recent unseen article
        logger.info(f"Processing latest unseen article on startup: {latest_unseen['title']}")
        process_article(latest_unseen, config)
        session_count = 1
        
        # Mark all other unseen articles as seen in DB to avoid backlog spam
        for art in unseen_articles[:-1]:
            mark_seen(art["url"], art["title"], art["source"])
            
    # Populate the in-memory seen_urls set with all current articles to prevent future checks
    for art in existing_articles:
        seen_urls.add(art["url"])
        
    logger.info(f"Tracking {len(seen_urls)} existing articles. Listening for NEW ones...\n")

    while True:
        try:
            new_articles = fetch_new_articles(feeds, seen_urls, max_age_hours=max_age_hrs)

            if new_articles:
                logger.info(f"[NEW] {len(new_articles)} new article(s)")
                for article in new_articles:
                    if is_seen(article["url"]):
                        continue
                    process_article(article, config)
                    session_count += 1
                    stats = get_stats()
                    logger.info(f"[STATS] Session: {session_count} | Total posted: {stats['posted']} | Failed: {stats['failed']}")
                    if len(new_articles) > 1:
                        time.sleep(random.uniform(4, 10))
            else:
                logger.debug(f"No new articles. Next check in {poll_secs}s")

            time.sleep(poll_secs)

        except KeyboardInterrupt:
            stats = get_stats()
            logger.info(f"\nStopped. Session: {session_count} | Total: {stats['posted']}")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            logger.info("Recovering in 60s...")
            time.sleep(60)


if __name__ == "__main__":
    run()
