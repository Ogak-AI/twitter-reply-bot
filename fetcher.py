import logging
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# A standard browser User-Agent to bypass Cloudflare/WAF block (HTTP 403) on major sites
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def extract_article_image(url: str) -> str | None:
    """
    Fetches the article page and extracts the primary image URL from
    Open Graph (og:image) or Twitter Card (twitter:image) meta tags.
    Returns None on any failure — callers should handle gracefully.
    """
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
        if resp.status_code >= 400:
            logger.debug(f"[IMAGE] HTTP {resp.status_code} fetching {url}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Try og:image first (most widely supported)
        og_tag = soup.find("meta", property="og:image")
        if og_tag and og_tag.get("content", "").strip():
            image_url = og_tag["content"].strip()
            if image_url.startswith("http"):
                logger.debug(f"[IMAGE] Found og:image: {image_url[:80]}")
                return image_url

        # Fallback to twitter:image
        tw_tag = soup.find("meta", attrs={"name": "twitter:image"})
        if tw_tag and tw_tag.get("content", "").strip():
            image_url = tw_tag["content"].strip()
            if image_url.startswith("http"):
                logger.debug(f"[IMAGE] Found twitter:image: {image_url[:80]}")
                return image_url

        logger.debug(f"[IMAGE] No og:image or twitter:image found for {url[:60]}")
        return None

    except Exception as e:
        logger.debug(f"[IMAGE] Error extracting image from {url[:60]}: {e}")
        return None


def fetch_single_feed(feed_info, cutoff_time, now):
    """
    Worker function to fetch and parse a single RSS feed.
    Returns a list of parsed article dicts.
    """
    username = feed_info.get("username")
    url = feed_info.get("rss_url")
    category = feed_info.get("category", "general")

    # Skip placeholder / empty URLs
    if not url or url.startswith("https://rss.app/feeds/example"):
        logger.warning(f"[@{username}] RSS url is empty or placeholder. Skipping.")
        return []

    # Skip obviously broken placeholder patterns
    if "your_" in url and "_feed_url" in url:
        logger.warning(f"[@{username}] RSS url looks like a placeholder. Skipping.")
        return []

    logger.debug(f"Polling feed for @{username} [{category}]...")
    articles = []
    try:
        # Fetch feed content using requests with a real User-Agent
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code >= 400:
            logger.warning(f"[@{username}] Feed returned HTTP {response.status_code}. Skipping.")
            return []

        # Parse the XML content from response
        feed = feedparser.parse(response.text)

        if feed.bozo and not feed.entries:
            logger.debug(f"[@{username}] Feed parse error (no entries): {feed.bozo_exception}")
            return []
        elif feed.bozo:
            logger.debug(f"[@{username}] XML parsing note: {feed.bozo_exception}")

        for entry in feed.entries:
            link = entry.get("link")
            if not link:
                continue

            title = entry.get("title", "")

            published_parsed = entry.get("published_parsed")
            if published_parsed:
                try:
                    published_dt = datetime.fromtimestamp(time.mktime(published_parsed))
                except Exception:
                    published_dt = now
            else:
                published_dt = now

            if published_dt < cutoff_time:
                continue

            # Extract the article's primary image from the source page
            image_url = extract_article_image(link)

            articles.append({
                "url": link,
                "title": title,
                "source": username,
                "category": category,
                "published_at": published_dt.isoformat(),
                "image_url": image_url,
            })

    except Exception as e:
        logger.error(f"Error fetching/parsing feed for @{username}: {e}")

    return articles


def fetch_new_articles(feeds, seen_urls, max_age_hours=24):
    """
    Fetches RSS feeds of X accounts concurrently.
    Returns a list of parsed article/tweet dicts.
    Uses ThreadPoolExecutor for I/O concurrency to avoid blocking.
    """
    new_articles = []
    now = datetime.utcnow()
    cutoff_time = now - timedelta(hours=max_age_hours)

    # Use ThreadPoolExecutor to run requests in parallel
    max_workers = min(len(feeds), 25)
    if max_workers <= 0:
        return []

    logger.info(f"Scanning {len(feeds)} RSS feeds concurrently (using {max_workers} worker threads)...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_feed = {
            executor.submit(fetch_single_feed, feed_info, cutoff_time, now): feed_info
            for feed_info in feeds
        }

        for future in as_completed(future_to_feed):
            feed_info = future_to_feed[future]
            username = feed_info.get("username")
            try:
                articles = future.result()
                for article in articles:
                    link = article["url"]
                    if link in seen_urls:
                        continue
                    seen_urls.add(link)
                    new_articles.append(article)
            except Exception as e:
                logger.error(f"Error processing future result for @{username}: {e}")

    return new_articles
