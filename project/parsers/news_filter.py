"""News filtering and categorisation module for Znews Telegram bot.

Filters fetched news by keywords, deduplicates against a SQLite DB,
and assigns categories with priority-based sorting.
"""

import logging
from typing import Optional

from database.models import NewsItem, SessionLocal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword map
# ---------------------------------------------------------------------------

KEYWORDS: dict[str, list[str]] = {
    "breaking": [
        "breaking", "urgent", "alert", "crash", "collapse", "surge",
        "spike", "plunge", "rally", "recession", "crisis", "emergency",
        "fed announces", " rate cut", " rate hike", "interest rate",
        "bank failure", "market halt", "trading suspended", "default",
        "bankruptcy", "meltdown", "black swan", "war", "sanctions",
        "oil embargo", "currency crisis", "hyperinflation",
        "фед резерв", "цб рф", "банкротство", "кризис", "крах",
        "обвал", "взлет", "падение", "рецессия", "война", "санкции",
        "эмбарго", "дефолт", "гиперинфляция",
    ],
    "trading": [
        "trading", "forex", "crypto", "bitcoin", "ethereum", "btc",
        "eth", "signal", "position", "long", "short", "leverage",
        "margin", "futures", "options", "derivatives", "volatility",
        "rsi", "macd", "support", "resistance", "breakout", "pump",
        "dump", "altcoin", "defi", "nft", "token", "blockchain",
        "трейдинг", "форекс", "крипто", "биткоин", "эфириум",
        "сигнал", "позиция", "лонг", "шорт", "плечо", "маржа",
        "фьючерсы", "опционы", "волатильность", "пробой", "альткоин",
        "токен", "блокчейн", "дефи", "nft",
    ],
    "finance": [
        "finance", "financial", "banking", "bank", "investment",
        "stock", "bond", "dividend", "earnings", "revenue",
        "profit", "loss", "ipo", "merger", "acquisition", "buyback",
        "shares", "market cap", "valuation", "portfolio", "asset",
        "fund", "etf", "index", "s&p 500", "nasdaq", "dow",
        "фондовый рынок", "финансы", "банк", "инвестиция",
        "акции", "облигации", "дивиденды", "доходы", "прибыль",
        "убыток", "ipo", "слияние", "поглощение", "выкуп акций",
        "капитализация", "портфель", "актив", "фонд", "индекс",
    ],
    "economy": [
        "economy", "economic", "GDP", "inflation", "recession",
        "trade", "tariff",
        "gdp", "inflation", "cpi", "ppi", "unemployment", "jobs",
        "employment", "consumer", "retail", "manufacturing", "pmi",
        "import", "export", "deficit", "surplus", "budget",
        "fiscal", "monetary", "central bank", "treasury", "yield",
        "экономика", "экономический", "инфляция", "торговля",
        "ввп", "безработица", "работа", "потребитель",
        "розница", "производство", "импорт", "экспорт",
        "дефицит", "профицит", "бюджет", "казначейство", "доходность",
    ],
}

# Priority for sorting: higher number = more important
CATEGORY_PRIORITY: dict[str, int] = {
    "breaking": 4,
    "trading": 3,
    "finance": 2,
    "economy": 1,
}

# Emojis for categories
CATEGORY_EMOJI: dict[str, str] = {
    "breaking": "🔴",
    "trading": "📈",
    "finance": "💰",
    "economy": "🏛️",
    "general": "📰",
}

# Category names in Russian
CATEGORY_NAMES_RU: dict[str, str] = {
    "breaking": "Критически важно",
    "trading": "Трейдинг",
    "finance": "Финансы",
    "economy": "Экономика",
    "general": "Общее",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def filter_news(news_list: list[dict]) -> list[dict]:
    """Filter a list of news items by keywords and deduplicate.

    * Keeps only items whose ``title`` or ``summary`` contains at least
      one keyword from :data:`KEYWORDS` (case-insensitive).
    * Skips items whose ``link`` has already been published (checked via
      :func:`is_duplicate`).
    * Adds a ``category`` key to each kept item.
    * Sorts results by category priority (breaking > trading > finance > economy).

    Args:
        news_list: Raw news items from :func:`rss_parser.fetch_all_sources`.

    Returns:
        Filtered, categorised and sorted news items.
    """
    filtered: list[dict] = []

    for news in news_list:
        link: str = news.get("link", "")
        if not link:
            continue

        if is_duplicate(link):
            logger.debug("Skipping duplicate: %s", link)
            continue

        category = categorize_text(f"{news.get('title', '')} {news.get('summary', '')}")
        if category is None:
            continue  # no keyword matched

        news_copy = dict(news)
        news_copy["category"] = category
        filtered.append(news_copy)

    # Sort by priority descending
    filtered.sort(
        key=lambda item: CATEGORY_PRIORITY.get(item.get("category", ""), 0),
        reverse=True,
    )

    logger.info("Filtered %d items down to %d relevant news", len(news_list), len(filtered))
    return filtered


def is_duplicate(link: str) -> bool:
    """Check whether a news item with *link* has already been published.

    Queries the local SQLite DB via SQLAlchemy.
    """
    session = SessionLocal()
    try:
        exists = session.query(NewsItem).filter_by(link=link).first() is not None
        return exists
    except Exception:
        logger.exception("DB error while checking duplicate for %s", link)
        return False  # on DB error, assume not duplicate to avoid losing news
    finally:
        session.close()


def categorize_text(text: str) -> Optional[str]:
    """Determine the best matching category for a news text.

    Scans *text* for keywords defined in :data:`KEYWORDS`.
    Returns the category with the highest match count, or *None* if no
    keywords are found.

    Args:
        text: Combined title and summary of the news item.

    Returns:
        One of ``"breaking"``, ``"trading"``, ``"finance"``, ``"economy"``
        or *None*.
    """
    if not text:
        return None

    text_lower = text.lower()
    best_category: Optional[str] = None
    best_score: int = 0

    for category, keywords in KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > best_score:
            best_score = score
            best_category = category

    return best_category


def categorize(news: dict) -> str:
    """Determine the best matching category for a news item (compatibility wrapper).

    Scans ``title`` and ``summary`` for keywords defined in :data:`KEYWORDS`.

    Args:
        news: News item dict with at least ``title`` and ``summary`` keys.

    Returns:
        One of ``"breaking"``, ``"trading"``, ``"finance"``, ``"economy"``
        or ``"general"``.
    """
    text = f"{news.get('title', '')} {news.get('summary', '')}"
    result = categorize_text(text)
    return result if result is not None else "general"


def get_category_emoji(category: str) -> str:
    """Return emoji for a category.

    Args:
        category: Category name.

    Returns:
        Emoji string.
    """
    return CATEGORY_EMOJI.get(category, "📰")


def get_category_name_ru(category: str) -> str:
    """Return Russian name for a category.

    Args:
        category: Category name.

    Returns:
        Russian category name.
    """
    return CATEGORY_NAMES_RU.get(category, category)


def mark_as_published(news: dict) -> None:
    """Persist a news item to the DB so it is not republished later.

    Args:
        news: News item dict with ``link``, ``title``, ``category``,
            ``source`` keys.
    """
    session = SessionLocal()
    try:
        item = NewsItem(
            link=news["link"],
            title=news.get("title", "")[:1024],
            category=news.get("category"),
            source=news.get("source"),
        )
        session.merge(item)  # merge = insert or update
        session.commit()
        logger.debug("Marked as published: %s", news["link"])
    except Exception:
        logger.exception("Failed to mark item as published: %s", news.get("link"))
    finally:
        session.close()
