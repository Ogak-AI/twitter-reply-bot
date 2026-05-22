import logging
import time
from datetime import datetime, timedelta
import feedparser

logger = logging.getLogger(__name__)


def fetch_new_articles(feeds, seen_urls, max_age_hours=24):
    """
    Fetches RSS feeds of X accounts.
    Returns a list of parsed article/tweet dicts.
    """
    new_articles = []
    now = datetime.utcnow()
    cutoff_time = now - timedelta(hours=max_age_hours)

    for feed_info in feeds:
        username = feed_info.get("username")
        url = feed_info.get("rss_url")
        if not url or url.startswith("https://rss.app/feeds/example"):
            logger.warning(f"X account RSS url for @{username} is empty or placeholder. Skipping.")
            continue

        logger.info(f"Polling feed for @{username}...")
        try:
            feed = feedparser.parse(url)
            if feed.bozo:
                logger.debug(f"XML parsing note for @{username}: {feed.bozo_exception}")

            for entry in feed.entries:
                link = entry.get("link")
                if not link:
                    continue

                title = entry.get("title", "")

                published_parsed = entry.get("published_parsed")
                if published_parsed:
                    published_dt = datetime.fromtimestamp(time.mktime(published_parsed))
                else:
                    published_dt = now

                if published_dt < cutoff_time:
                    continue

                article = {
                    "url": link,
                    "title": title,
                    "source": username,
                    "published_at": published_dt.isoformat()
                }

                if link in seen_urls:
                    continue

                seen_urls.add(link)
                new_articles.append(article)

        except Exception as e:
            logger.error(f"Error fetching/parsing feed for @{username}: {e}", exc_info=True)

    return new_articles
