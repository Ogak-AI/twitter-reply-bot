import logging
import time
from datetime import datetime, timedelta
import feedparser
import requests

logger = logging.getLogger(__name__)

# A standard browser User-Agent to bypass Cloudflare/WAF block (HTTP 403) on major sites
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def fetch_new_articles(feeds, seen_urls, max_age_hours=24):
    """
    Fetches RSS feeds of X accounts.
    Returns a list of parsed article/tweet dicts.
    Supports both native RSS feeds and RSSHub/RSSBridge feeds.
    Uses requests with a custom User-Agent to bypass HTTP 403 Forbidden blocks.
    """
    new_articles = []
    now = datetime.utcnow()
    cutoff_time = now - timedelta(hours=max_age_hours)

    for feed_info in feeds:
        username = feed_info.get("username")
        url = feed_info.get("rss_url")
        category = feed_info.get("category", "general")

        # Skip placeholder / empty URLs
        if not url or url.startswith("https://rss.app/feeds/example"):
            logger.warning(f"[@{username}] RSS url is empty or placeholder. Skipping.")
            continue

        # Skip obviously broken placeholder patterns
        if "your_" in url and "_feed_url" in url:
            logger.warning(f"[@{username}] RSS url looks like a placeholder. Skipping.")
            continue

        logger.debug(f"Polling feed for @{username} [{category}]...")
        try:
            # Fetch feed content using requests with a real User-Agent
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code >= 400:
                logger.warning(f"[@{username}] Feed returned HTTP {response.status_code}. Skipping.")
                continue

            # Parse the XML content from response
            feed = feedparser.parse(response.text)

            if feed.bozo and not feed.entries:
                logger.debug(f"[@{username}] Feed parse error (no entries): {feed.bozo_exception}")
                continue
            elif feed.bozo:
                logger.debug(f"[@{username}] XML parsing note: {feed.bozo_exception}")

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
                    "category": category,
                    "published_at": published_dt.isoformat()
                }

                if link in seen_urls:
                    continue

                seen_urls.add(link)
                new_articles.append(article)

        except Exception as e:
            logger.error(f"Error fetching/parsing feed for @{username}: {e}", exc_info=True)

    return new_articles
