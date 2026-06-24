"""Parsers package for Znews Telegram Bot.

Provides RSS fetching, news filtering, categorisation and deduplication.

Example::

    from parsers import fetch_all_sources, filter_news, categorize

    raw_news = await fetch_all_sources()
    relevant = filter_news(raw_news)
"""

from parsers.rss_parser import fetch_all_sources, fetch_rss
from parsers.news_filter import (
    filter_news,
    categorize,
    categorize_text,
    is_duplicate,
    mark_as_published,
    get_category_emoji,
    get_category_name_ru,
    KEYWORDS,
    CATEGORY_PRIORITY,
    CATEGORY_EMOJI,
    CATEGORY_NAMES_RU,
)

__all__ = [
    "fetch_all_sources",
    "fetch_rss",
    "filter_news",
    "categorize",
    "categorize_text",
    "is_duplicate",
    "mark_as_published",
    "get_category_emoji",
    "get_category_name_ru",
    "KEYWORDS",
    "CATEGORY_PRIORITY",
    "CATEGORY_EMOJI",
    "CATEGORY_NAMES_RU",
]
