"""Database package for Znews Telegram Bot.

Provides async SQLAlchemy models, session management and CRUD helpers.
"""

from database.models import (
    Base,
    NewsItem,
    PostedNews,
    MotivationLog,
    RateLog,
    init_db,
    get_session,
    save_news_item,
    get_unposted_news,
    mark_news_as_posted,
    get_stats,
)

__all__ = [
    "Base",
    "NewsItem",
    "PostedNews",
    "MotivationLog",
    "RateLog",
    "init_db",
    "get_session",
    "save_news_item",
    "get_unposted_news",
    "mark_news_as_posted",
    "get_stats",
]
