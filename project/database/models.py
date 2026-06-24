"""
SQLAlchemy async database models for Znews Bot.

Defines ORM models for news items, posted news tracking,
motivation quotes log, and exchange rates log.
Provides async init_db() for table creation.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    select,
    func,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base, relationship

logger = logging.getLogger(__name__)

Base = declarative_base()


class NewsItem(Base):
    """News article fetched from RSS sources."""

    __tablename__ = "news_items"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    link = Column(String(1000), unique=True, nullable=False)
    source = Column(String(100), nullable=False)
    category = Column(String(50))
    importance = Column(Integer, default=1)
    summary_ru = Column(Text)
    image_url = Column(String(1000))
    created_at = Column(DateTime, default=datetime.utcnow)
    posted_at = Column(DateTime, nullable=True)

    # Relationship to posted tracking
    posted_entries = relationship(
        "PostedNews",
        back_populates="news_item",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<NewsItem(id={self.id}, title='{self.title[:50]}...')>"

    def to_dict(self) -> dict:
        """Serialize news item to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "source": self.source,
            "category": self.category,
            "importance": self.importance,
            "summary_ru": self.summary_ru,
            "image_url": self.image_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
        }


class PostedNews(Base):
    """Tracking record for news already posted to the channel."""

    __tablename__ = "posted_news"

    id = Column(Integer, primary_key=True)
    news_id = Column(Integer, ForeignKey("news_items.id"), nullable=False)
    posted_at = Column(DateTime, default=datetime.utcnow)

    news_item = relationship("NewsItem", back_populates="posted_entries")

    def __repr__(self) -> str:
        return f"<PostedNews(id={self.id}, news_id={self.news_id})>"


class MotivationLog(Base):
    """Log of posted motivation quotes."""

    __tablename__ = "motivation_log"

    id = Column(Integer, primary_key=True)
    quote_text = Column(Text, nullable=False)
    author = Column(String(200))
    posted_at = Column(DateTime, default=datetime.utcnow)
    is_morning = Column(Integer, default=1)

    def __repr__(self) -> str:
        period = "morning" if self.is_morning else "evening"
        return f"<MotivationLog(id={self.id}, period={period})>"


class RateLog(Base):
    """Log of posted exchange rates."""

    __tablename__ = "rate_log"

    id = Column(Integer, primary_key=True)
    rates_json = Column(Text, nullable=False)
    posted_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<RateLog(id={self.id}, posted_at={self.posted_at})>"


# --- Database engine and session factory ---
_engine = None
_async_session_maker = None


async def init_db(db_path: str) -> None:
    """
    Initialize async database engine and create all tables.

    Args:
        db_path: Path to SQLite database file.
    """
    global _engine, _async_session_maker

    db_url = f"sqlite+aiosqlite:///{db_path}"
    logger.info(f"Initializing database at: {db_path}")

    _engine = create_async_engine(db_url, echo=False)
    _async_session_maker = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized successfully")


async def get_session() -> AsyncSession:
    """
    Get a new async database session.

    Returns:
        AsyncSession instance.

    Raises:
        RuntimeError: If init_db() was not called before.
    """
    if _async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _async_session_maker()


async def save_news_item(
    session: AsyncSession,
    title: str,
    link: str,
    source: str,
    category: Optional[str] = None,
    importance: int = 1,
    summary_ru: Optional[str] = None,
    image_url: Optional[str] = None,
) -> Optional[NewsItem]:
    """
    Save a news item to the database if link is not already present.

    Args:
        session: Active async database session.
        title: News title.
        link: Unique news URL.
        source: Source name (e.g., 'CNN', 'BBC').
        category: Optional news category.
        importance: Importance score (1-5).
        summary_ru: Optional Russian summary.
        image_url: Optional image URL.

    Returns:
        Created NewsItem or None if link already exists.
    """
    try:
        # Check for duplicate
        result = await session.execute(select(NewsItem).where(NewsItem.link == link))
        existing = result.scalar_one_or_none()
        if existing:
            logger.debug(f"News with link already exists: {link[:60]}...")
            return None

        news = NewsItem(
            title=title,
            link=link,
            source=source,
            category=category,
            importance=importance,
            summary_ru=summary_ru,
            image_url=image_url,
        )
        session.add(news)
        await session.commit()
        logger.info(f"Saved news item: {title[:60]}...")
        return news
    except Exception as e:
        await session.rollback()
        logger.error(f"Error saving news item: {e}")
        return None


async def get_unposted_news(session: AsyncSession, limit: int = 50) -> list[NewsItem]:
    """
    Retrieve news items that haven't been posted yet.

    Args:
        session: Active async database session.
        limit: Maximum number of items to return.

    Returns:
        List of unposted NewsItem ordered by importance desc, created_at desc.
    """
    result = await session.execute(
        select(NewsItem)
        .where(NewsItem.posted_at.is_(None))
        .order_by(NewsItem.importance.desc(), NewsItem.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def mark_news_as_posted(session: AsyncSession, news_id: int) -> bool:
    """
    Mark a news item as posted and create tracking record.

    Args:
        session: Active async database session.
        news_id: ID of the news item.

    Returns:
        True if successful, False otherwise.
    """
    try:
        result = await session.execute(
            select(NewsItem).where(NewsItem.id == news_id)
        )
        news = result.scalar_one_or_none()
        if not news:
            logger.warning(f"News item {news_id} not found for marking as posted")
            return False

        news.posted_at = datetime.utcnow()
        posted = PostedNews(news_id=news_id)
        session.add(posted)
        await session.commit()
        logger.info(f"Marked news {news_id} as posted")
        return True
    except Exception as e:
        await session.rollback()
        logger.error(f"Error marking news as posted: {e}")
        return False


async def get_stats(session: AsyncSession) -> dict:
    """
    Get database statistics for admin /stats command.

    Args:
        session: Active async database session.

    Returns:
        Dictionary with news counts and other stats.
    """
    total_news = await session.execute(select(func.count(NewsItem.id)))
    posted_news = await session.execute(
        select(func.count(NewsItem.id)).where(NewsItem.posted_at.isnot(None))
    )
    unposted_news = await session.execute(
        select(func.count(NewsItem.id)).where(NewsItem.posted_at.is_(None))
    )
    total_motivation = await session.execute(select(func.count(MotivationLog.id)))
    total_rates = await session.execute(select(func.count(RateLog.id)))

    return {
        "total_news": total_news.scalar(),
        "posted_news": posted_news.scalar(),
        "unposted_news": unposted_news.scalar(),
        "total_motivation": total_motivation.scalar(),
        "total_rates": total_rates.scalar(),
    }
