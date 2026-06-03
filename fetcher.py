import logging
import time
import re as _re
import base64
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# A standard browser User-Agent to bypass Cloudflare/WAF block (HTTP 403) on major sites
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _decode_google_news_url(url: str) -> str | None:
    """
    Attempts to decode the actual article URL from a Google News RSS link.
    Google News encodes the real URL in base64 within the path.
    """
    try:
        # Extract the encoded segment after /articles/
        match = _re.search(r"/articles/([A-Za-z0-9_-]+)", url)
        if not match:
            return None
        encoded = match.group(1)
        # Add padding for base64
        padded = encoded + "=" * (4 - len(encoded) % 4)
        decoded = base64.urlsafe_b64decode(padded)
        # Find all http(s) URLs embedded in the decoded protobuf bytes
        decoded_str = decoded.decode("latin-1")
        urls = _re.findall(r"https?://[^\s\x00-\x1f\"'<>\x7f-\x9f]+", decoded_str)
        # Return the first non-Google URL
        for u in urls:
            if "google.com" not in u and "google.co." not in u:
                return u.rstrip(".,;")
    except Exception:
        pass
    return None


def resolve_google_news_url(url: str) -> str:
    """
    Resolves a Google News redirect URL to the actual article URL.
    Uses base64 decoding first (instant), then HTTP redirect fallback.
    Returns the original URL if resolution fails.
    """
    if "news.google.com" not in url:
        return url

    # Strategy 1: Decode the base64-encoded URL from the path (fastest, no HTTP)
    decoded = _decode_google_news_url(url)
    if decoded:
        logger.debug(f"[RESOLVE] Decoded Google News URL → {decoded[:80]}")
        return decoded

    # Strategy 2: Follow HTTP redirects
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        final = resp.url
        if "news.google.com" not in final and "google.com/rss" not in final:
            logger.debug(f"[RESOLVE] Redirected Google News URL → {final[:80]}")
            return final

        # Strategy 3: Parse the Google News page for the actual link
        soup = BeautifulSoup(resp.text, "html.parser")
        # Check <a> tags linking to external articles
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("http") and "google.com" not in href:
                logger.debug(f"[RESOLVE] Found article link in page → {href[:80]}")
                return href
    except Exception as e:
        logger.debug(f"[RESOLVE] HTTP resolution failed: {e}")

    logger.debug(f"[RESOLVE] Could not resolve Google News URL: {url[:60]}")
    return url


def extract_article_image(url: str) -> str | None:
    """
    Resolves Google News URLs to the actual article page, then extracts
    the primary image from Open Graph (og:image) or Twitter Card (twitter:image) meta tags.
    Returns None on any failure — callers should handle gracefully.
    """
    # Resolve Google News redirect to actual article URL
    resolved_url = resolve_google_news_url(url)

    try:
        headers = {"User-Agent": USER_AGENT}
        # Only fetch the page if we haven't already (i.e. URL was decoded, not HTTP-fetched)
        resp = requests.get(resolved_url, headers=headers, timeout=5, allow_redirects=True)
        if resp.status_code >= 400:
            logger.debug(f"[IMAGE] HTTP {resp.status_code} fetching {resolved_url[:60]}")
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

        logger.debug(f"[IMAGE] No og:image or twitter:image found for {resolved_url[:60]}")
        return None

    except Exception as e:
        logger.debug(f"[IMAGE] Error extracting image from {resolved_url[:60]}: {e}")
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
        response = requests.get(url, headers=headers, timeout=6)

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

            # Image extraction is deferred to process_article() — only
            # fetched for articles that pass viral scoring (saves seconds
            # per article during the feed-scan hot path).
            articles.append({
                "url": link,
                "title": title,
                "source": username,
                "category": category,
                "published_at": published_dt.isoformat(),
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
