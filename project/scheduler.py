"""
APScheduler-based task scheduler for Znews Bot.

Manages 5 background jobs:
1. check_news — fetches and filters news from RSS sources
2. auto_post — publishes queued news to the channel
3. morning_motivation — sends morning motivation at 07:00
4. evening_motivation — sends evening motivation at 19:00
5. exchange_rates — sends CBU exchange rates at 09:00
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import Config

logger = logging.getLogger(__name__)

# Global in-memory queue for news awaiting publication
news_queue: List[Dict[str, Any]] = []


async def check_news_job(bot: Bot, config: Config) -> None:
    """
    Fetch news from all configured RSS sources and add filtered items to queue.

    Runs every CHECK_INTERVAL minutes (default: 5).

    Args:
        bot: Aiogram Bot instance.
        config: Application configuration.
    """
    global news_queue
    logger.info("Starting news check job...")

    try:
        from parsers.rss_parser import fetch_all_sources
        from parsers.news_filter import filter_news
        from database.models import get_session, save_news_item

        raw_news = await fetch_all_sources()
        logger.info(f"Fetched {len(raw_news)} raw news items from sources")

        filtered = filter_news(raw_news)
        logger.info(f"Filtered down to {len(filtered)} relevant news items")

        # Persist to database and add to queue
        session = await get_session()
        try:
            newly_added = 0
            for item in filtered:
                # Save to DB (skips duplicates by link)
                saved = await save_news_item(
                    session=session,
                    title=item.get("title", "Untitled"),
                    link=item.get("link", ""),
                    source=item.get("source", "unknown"),
                    category=item.get("category"),
                    importance=item.get("importance", 1),
                    summary_ru=item.get("summary_ru"),
                    image_url=item.get("image_url"),
                )
                if saved is not None:
                    newly_added += 1
                    news_queue.append(item)

            logger.info(
                f"Added {newly_added} new items to queue. "
                f"Queue size: {len(news_queue)}"
            )
        finally:
            await session.close()

    except ImportError as e:
        logger.warning(f"Parser modules not available yet: {e}")
    except Exception as e:
        logger.error(f"Error in check_news_job: {e}", exc_info=True)


async def auto_post_job(bot: Bot, config: Config) -> None:
    """
    Publish the next news item from the queue to the Telegram channel.

    Runs every POST_INTERVAL minutes (default: 10).

    Args:
        bot: Aiogram Bot instance.
        config: Application configuration.
    """
    global news_queue

    if not news_queue:
        logger.debug("News queue is empty, skipping auto-post")
        return

    logger.info(f"Auto-posting next item. Queue size: {len(news_queue)}")

    try:
        from services.poster import post_news
        from database.models import get_session, mark_news_as_posted

        news = news_queue.pop(0)
        news_title = news.get("title", "Untitled")[:80]

        await post_news(bot, config.CHANNEL_ID, news)
        logger.info(f"Posted news: {news_title}...")

        # Mark as posted in database if it has an ID
        if "db_id" in news:
            session = await get_session()
            try:
                await mark_news_as_posted(session, news["db_id"])
            finally:
                await session.close()

    except ImportError as e:
        logger.warning(f"Poster module not available yet: {e}")
    except Exception as e:
        logger.error(f"Error in auto_post_job: {e}", exc_info=True)
        # Put the item back in queue on failure
        news_queue.insert(0, news)
        logger.info("Requeued failed news item")


async def morning_motivation_job(bot: Bot, config: Config) -> None:
    """
    Send morning motivation image with quote at 07:00.

    Args:
        bot: Aiogram Bot instance.
        config: Application configuration.
    """
    logger.info("Sending morning motivation...")

    try:
        from services.motivator import get_daily_motivation, generate_motivation_image

        quote = await get_daily_motivation(morning=True)
        image_path = "/tmp/morning_motivation.jpg"

        await generate_motivation_image(quote, image_path)

        caption = (
            f"☀️ Доброе утро, трейдеры!\n\n"
            f"💬 {quote.get('text', '')}\n\n"
            f"— {quote.get('author', 'Unknown')}\n\n"
            f"#Znews #Мотивация"
        )

        # Ensure image exists before sending
        if os.path.exists(image_path):
            with open(image_path, "rb") as photo:
                await bot.send_photo(
                    config.CHANNEL_ID,
                    photo=photo,
                    caption=caption,
                )
            logger.info("Morning motivation sent successfully")
        else:
            # Fallback to text-only message
            await bot.send_message(config.CHANNEL_ID, caption)
            logger.warning("Motivation image not found, sent text-only")

        # Clean up temp file
        try:
            os.remove(image_path)
        except OSError:
            pass

    except ImportError as e:
        logger.warning(f"Motivator module not available yet: {e}")
    except Exception as e:
        logger.error(f"Error in morning_motivation_job: {e}", exc_info=True)


async def evening_motivation_job(bot: Bot, config: Config) -> None:
    """
    Send evening motivation image with quote at 19:00.

    Args:
        bot: Aiogram Bot instance.
        config: Application configuration.
    """
    logger.info("Sending evening motivation...")

    try:
        from services.motivator import get_daily_motivation, generate_motivation_image

        quote = await get_daily_motivation(morning=False)
        image_path = "/tmp/evening_motivation.jpg"

        await generate_motivation_image(quote, image_path)

        caption = (
            f"🌙 Подведение итогов дня\n\n"
            f"💬 {quote.get('text', '')}\n\n"
            f"— {quote.get('author', 'Unknown')}\n\n"
            f"#Znews #Мотивация"
        )

        if os.path.exists(image_path):
            with open(image_path, "rb") as photo:
                await bot.send_photo(
                    config.CHANNEL_ID,
                    photo=photo,
                    caption=caption,
                )
            logger.info("Evening motivation sent successfully")
        else:
            await bot.send_message(config.CHANNEL_ID, caption)
            logger.warning("Motivation image not found, sent text-only")

        # Clean up temp file
        try:
            os.remove(image_path)
        except OSError:
            pass

    except ImportError as e:
        logger.warning(f"Motivator module not available yet: {e}")
    except Exception as e:
        logger.error(f"Error in evening_motivation_job: {e}", exc_info=True)


async def exchange_rates_job(bot: Bot, config: Config) -> None:
    """
    Send CBU exchange rates message at 09:00.

    Args:
        bot: Aiogram Bot instance.
        config: Application configuration.
    """
    logger.info("Sending exchange rates...")

    try:
        from services.cbu_api import get_exchange_rates, format_rates_message

        rates = await get_exchange_rates()
        message = await format_rates_message(rates)

        await bot.send_message(config.CHANNEL_ID, message)
        logger.info("Exchange rates sent successfully")

    except ImportError as e:
        logger.warning(f"CBU API module not available yet: {e}")
    except Exception as e:
        logger.error(f"Error in exchange_rates_job: {e}", exc_info=True)


def setup_scheduler(bot: Bot, config: Config) -> AsyncIOScheduler:
    """
    Configure and return APScheduler with all background tasks.

    Sets up 5 jobs:
        1. check_news — every CHECK_INTERVAL minutes
        2. auto_post — every POST_INTERVAL minutes
        3. morning_motivation — cron at 07:00
        4. evening_motivation — cron at 19:00
        5. exchange_rates — cron at 09:00

    Args:
        bot: Aiogram Bot instance.
        config: Application configuration.

    Returns:
        Configured AsyncIOScheduler instance.
    """
    scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)

    # Job 1: Check news from RSS sources
    scheduler.add_job(
        check_news_job,
        IntervalTrigger(minutes=config.CHECK_INTERVAL),
        args=[bot, config],
        id="check_news",
        name="Check news from RSS sources",
        replace_existing=True,
    )
    logger.info(
        f"Scheduled check_news every {config.CHECK_INTERVAL} minutes"
    )

    # Job 2: Auto-post queued news
    scheduler.add_job(
        auto_post_job,
        IntervalTrigger(minutes=config.POST_INTERVAL),
        args=[bot, config],
        id="auto_post",
        name="Auto-post news to channel",
        replace_existing=True,
    )
    logger.info(
        f"Scheduled auto_post every {config.POST_INTERVAL} minutes"
    )

    # Job 3: Morning motivation at 07:00
    scheduler.add_job(
        morning_motivation_job,
        CronTrigger(hour=7, minute=0),
        args=[bot, config],
        id="morning_motivation",
        name="Morning motivation (07:00)",
        replace_existing=True,
    )
    logger.info("Scheduled morning_motivation at 07:00")

    # Job 4: Evening motivation at 19:00
    scheduler.add_job(
        evening_motivation_job,
        CronTrigger(hour=19, minute=0),
        args=[bot, config],
        id="evening_motivation",
        name="Evening motivation (19:00)",
        replace_existing=True,
    )
    logger.info("Scheduled evening_motivation at 19:00")

    # Job 5: Exchange rates at 09:00
    scheduler.add_job(
        exchange_rates_job,
        CronTrigger(hour=9, minute=0),
        args=[bot, config],
        id="exchange_rates",
        name="CBU exchange rates (09:00)",
        replace_existing=True,
    )
    logger.info("Scheduled exchange_rates at 09:00")

    return scheduler


def start_scheduler(scheduler: AsyncIOScheduler) -> None:
    """
    Start the APScheduler event loop.

    Args:
        scheduler: Configured AsyncIOScheduler instance.
    """
    scheduler.start()
    logger.info("Scheduler started successfully")

    # Log all scheduled jobs
    jobs = scheduler.get_jobs()
    logger.info(f"Active jobs: {len(jobs)}")
    for job in jobs:
        logger.info(f"  - {job.id}: next run at {job.next_run_time}")


def shutdown_scheduler(scheduler: AsyncIOScheduler) -> None:
    """
    Gracefully shutdown the scheduler.

    Args:
        scheduler: Running AsyncIOScheduler instance.
    """
    scheduler.shutdown(wait=True)
    logger.info("Scheduler shutdown complete")


def get_scheduler_status(scheduler: AsyncIOScheduler) -> dict:
    """
    Get current scheduler status for admin /status command.

    Args:
        scheduler: AsyncIOScheduler instance.

    Returns:
        Dictionary with scheduler state and job information.
    """
    jobs_info = []
    for job in scheduler.get_jobs():
        jobs_info.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return {
        "running": scheduler.running,
        "state": str(scheduler.state),
        "timezone": str(scheduler.timezone),
        "jobs_count": len(jobs_info),
        "jobs": jobs_info,
        "queue_size": len(news_queue),
    }
