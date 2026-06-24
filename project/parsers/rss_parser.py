"""Async RSS parser module for Znews Telegram bot.

Fetches and parses RSS feeds from multiple news sources concurrently
using aiohttp and feedparser.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import aiohttp
import feedparser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RSS_SOURCES: dict[str, str] = {
    "CNN": "http://rss.cnn.com/rss/edition.rss",
    "BBC": "http://feeds.bbci.co.uk/news/rss.xml",
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "Reuters": (
        "https://www.reutersagency.com/feed/"
        "?taxonomy=markets&post_type=reuters-best"
    ),
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "Kun.uz": "https://kun.uz/news/rss",
    "Qalampir.uz": "https://qalampir.uz/rss",
    "Uznews.uz": "https://uznews.uz/rss",
}

REQUEST_TIMEOUT: int = 10  # seconds per source
MAX_SUMMARY_LENGTH: int = 500

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fetch_all_sources() -> list[dict]:
    """Parse all 8 RSS sources concurrently.

    Returns a list of news items. Each item is a dict with keys:
    ``title``, ``link``, ``summary``, ``published``, ``source``, ``image_url``.

    Sources that fail to respond or produce invalid data are logged and
    skipped so that the remaining sources still contribute results.
    """
    tasks = [
        fetch_rss(url, source_name)
        for source_name, url in RSS_SOURCES.items()
    ]
    results: list[list[dict]] = await asyncio.gather(*tasks, return_exceptions=True)

    all_news: list[dict] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error("RSS source failed: %s", result)
            continue
        all_news.extend(result)

    logger.info("Fetched %d total news items from %d sources", len(all_news), len(RSS_SOURCES))
    return all_news


async def fetch_rss(url: str, source_name: str) -> list[dict]:
    """Fetch and parse a single RSS feed.

    Args:
        url: The RSS feed URL.
        source_name: Human-readable source name (e.g. ``"BBC"``).

    Returns:
        A list of news item dicts. Empty list on any error.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                headers={"User-Agent": "ZnewsBot/1.0 (+https://t.me/znews)"},
            ) as response:
                response.raise_for_status()
                xml_data: str = await response.text()
    except aiohttp.ClientError as exc:
        logger.warning("Network error for %s (%s): %s", source_name, url, exc)
        return []
    except asyncio.TimeoutError:
        logger.warning("Timeout for %s (%s) after %ds", source_name, url, REQUEST_TIMEOUT)
        return []
    except Exception as exc:
        logger.error("Unexpected error for %s (%s): %s", source_name, url, exc)
        return []

    return _parse_feed(xml_data, source_name)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_feed(xml_data: str, source_name: str) -> list[dict]:
    """Parse XML string with feedparser and normalise entries."""
    feed = feedparser.parse(xml_data)

    if feed.bozo:
        logger.debug("Feed %s has parse warnings: %s", source_name, feed.bozo_exception)

    news_items: list[dict] = []
    for entry in feed.entries:
        item = _entry_to_dict(entry, source_name)
        if item:  # skip entries without title or link
            news_items.append(item)

    logger.info("Parsed %d items from %s", len(news_items), source_name)
    return news_items


def _entry_to_dict(entry, source_name: str) -> Optional[dict]:
    """Convert a single feedparser entry to a normalised dict.

    Returns *None* if the entry lacks required fields (title or link).
    """
    title: str = getattr(entry, "title", "").strip()
    link: str = getattr(entry, "link", "").strip()

    if not title or not link:
        return None

    summary: str = _extract_summary(entry)
    published: Optional[str] = _extract_published(entry)
    image_url: Optional[str] = _extract_image(entry)

    return {
        "title": title,
        "link": link,
        "summary": summary,
        "published": published or datetime.utcnow().isoformat(),
        "source": source_name,
        "image_url": image_url,
    }


def _extract_summary(entry) -> str:
    """Extract a text summary from a feed entry."""
    # 1. Prefer content[0].value (full HTML content)
    if hasattr(entry, "content") and entry.content:
        text: str = entry.content[0].value
        return _clean_html(text)[:MAX_SUMMARY_LENGTH]

    # 2. Fallback to description / summary
    for attr in ("summary", "description", "subtitle"):
        text = getattr(entry, attr, "")
        if text:
            return _clean_html(text)[:MAX_SUMMARY_LENGTH]

    return ""


def _extract_published(entry) -> Optional[str]:
    """Return ISO-formatted published date or *None*."""
    # feedparser provides published_parsed or updated_parsed as time tuples
    parsed = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )
    if parsed:
        try:
            dt = datetime(*parsed[:6])
            return dt.isoformat()
        except (ValueError, TypeError):
            pass

    # Fallback to raw string
    for attr in ("published", "updated", "date"):
        val = getattr(entry, attr, None)
        if val:
            return str(val)
    return None


def _extract_image(entry) -> Optional[str]:
    """Extract image URL from media:content or enclosure."""
    # media:content (used by CNN, NYT, etc.)
    media_content = getattr(entry, "media_content", [])
    if media_content:
        for media in media_content:
            url = media.get("url", "")
            medium = media.get("medium", "").lower()
            if url and (medium in ("image", "") or url.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))):
                return url

    # enclosure (podcasts / images)
    enclosures = getattr(entry, "enclosures", [])
    if enclosures:
        for enc in enclosures:
            url = enc.get("href", "")
            enc_type = enc.get("type", "").lower()
            if url and enc_type.startswith("image/"):
                return url

    # media:thumbnail (BBC, Reuters style)
    media_thumbnail = getattr(entry, "media_thumbnail", [])
    if media_thumbnail:
        return media_thumbnail[0].get("url", None)

    return None


def _clean_html(raw: str) -> str:
    """Very naive HTML tag stripper for summary text."""
    import re
    clean = re.sub(r"<[^>]+>", "", raw)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()
