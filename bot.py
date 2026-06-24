"""
Znews Telegram Bot — main entry point.

An aiogram 3.x based bot that:
- Handles admin commands
- Runs scheduled background jobs (news fetching, auto-posting, motivation, rates)
- Manages SQLite database for news storage

Usage:
    python bot.py
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import Optional

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from config import Config, config
from scheduler import (
    setup_scheduler,
    start_scheduler,
    shutdown_scheduler,
    get_scheduler_status,
    check_news_job,
    auto_post_job,
    exchange_rates_job,
    morning_motivation_job,
    evening_motivation_job,
    news_queue,
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Reduce noise from third-party libraries
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Aiogram components
# ---------------------------------------------------------------------------
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()
router = Router()

# Global scheduler reference for command handlers
_scheduler: Optional[object] = None


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def is_admin(user_id: int) -> bool:
    """Check if user ID is in the admin list."""
    return user_id in config.ADMIN_IDS


def admin_only(handler):
    """Decorator to restrict command to admin users only."""
    async def wrapper(message: Message, **kwargs):
        if not is_admin(message.from_user.id):
            await message.answer("⛔ У вас нет доступа к этой команде.")
            return
        return await handler(message, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Admin command handlers
# ---------------------------------------------------------------------------

@router.message(Command("start"))
@admin_only
async def cmd_start(message: Message) -> None:
    """
    Handle /start command — show welcome message and bot status.

    Available to admin users only.
    """
    welcome_text = (
        f"👋 Привет, <b>{message.from_user.full_name}</b>!\n\n"
        f"🤖 <b>Znews Bot</b> — автоматический постер новостей\n\n"
        f"📊 <b>Статус:</b>\n"
        f"  • Проверка новостей: каждые <b>{config.CHECK_INTERVAL} мин</b>\n"
        f"  • Автопостинг: каждые <b>{config.POST_INTERVAL} мин</b>\n"
        f"  • Утренняя мотивация: <b>07:00</b>\n"
        f"  • Вечерняя мотивация: <b>19:00</b>\n"
        f"  • Курс валют: <b>09:00</b>\n\n"
        f"💡 Используйте /help для списка команд."
    )
    await message.answer(welcome_text, parse_mode="HTML")


@router.message(Command("help"))
@admin_only
async def cmd_help(message: Message) -> None:
    """
    Handle /help command — show available admin commands.
    """
    help_text = (
        "📋 <b>Доступные команды:</b>\n\n"
        "<code>/start</code> — Приветствие и статус бота\n"
        "<code>/stats</code> — Статистика базы данных\n"
        "<code>/force_post</code> — Принудительная публикация следующей новости\n"
        "<code>/motivation</code> — Отправить мотивацию вручную\n"
        "<code>/rates</code> — Отправить курс валют вручную\n"
        "<code>/set_interval &lt;мин&gt;</code> — Изменить интервал автопостинга\n"
        "<code>/status</code> — Статус планировщика и очереди\n"
        "<code>/check</code> — Принудительная проверка новостей\n"
        "<code>/help</code> — Эта справка\n\n"
        "⚙️ <b>Конфигурация:</b>\n"
        f"  • Channel: <code>{config.CHANNEL_ID}</code>\n"
        f"  • Timezone: <code>{config.TIMEZONE}</code>\n"
        f"  • Admins: <code>{len(config.ADMIN_IDS)}</code>"
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("stats"))
@admin_only
async def cmd_stats(message: Message) -> None:
    """
    Handle /stats command — show database statistics.
    """
    try:
        from database.models import get_session, get_stats

        session = await get_session()
        try:
            stats = await get_stats(session)
        finally:
            await session.close()

        stats_text = (
            "📊 <b>Статистика базы данных:</b>\n\n"
            f"  📰 Всего новостей: <b>{stats['total_news']}</b>\n"
            f"  ✅ Опубликовано: <b>{stats['posted_news']}</b>\n"
            f"  ⏳ В очереди: <b>{stats['unposted_news']}</b>\n"
            f"  💬 Мотиваций отправлено: <b>{stats['total_motivation']}</b>\n"
            f"  💱 Курсов отправлено: <b>{stats['total_rates']}</b>\n\n"
            f"  📥 Текущий размер очереди: <b>{len(news_queue)}</b>"
        )
        await message.answer(stats_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in /stats: {e}")
        await message.answer(f"❌ Ошибка получения статистики: {e}")


@router.message(Command("force_post"))
@admin_only
async def cmd_force_post(message: Message) -> None:
    """
    Handle /force_post command — immediately post next news from queue.
    """
    if not news_queue:
        await message.answer(
            "⚠️ Очередь новостей пуста. "
            "Используйте /check для принудительной проверки источников."
        )
        return

    await message.answer("🚀 Принудительная публикация следующей новости...")

    try:
        await auto_post_job(bot, config)
        await message.answer("✅ Новость опубликована!")
    except Exception as e:
        logger.error(f"Error in /force_post: {e}")
        await message.answer(f"❌ Ошибка публикации: {e}")


@router.message(Command("motivation"))
@admin_only
async def cmd_motivation(message: Message) -> None:
    """
    Handle /motivation command — send motivation manually.

    Sends morning motivation by default. Add 'evening' argument for evening version.
    """
    args = message.text.split(maxsplit=1)
    is_morning = True
    if len(args) > 1 and args[1].lower() in ("evening", "вечер"):
        is_morning = False

    await message.answer(
        f"💬 Отправка {'вечерней' if not is_morning else 'утренней'} мотивации..."
    )

    try:
        if is_morning:
            await morning_motivation_job(bot, config)
        else:
            await evening_motivation_job(bot, config)
        await message.answer("✅ Мотивация отправлена!")
    except Exception as e:
        logger.error(f"Error in /motivation: {e}")
        await message.answer(f"❌ Ошибка отправки мотивации: {e}")


@router.message(Command("rates"))
@admin_only
async def cmd_rates(message: Message) -> None:
    """
    Handle /rates command — send exchange rates manually.
    """
    await message.answer("💱 Запрос курса валют...")

    try:
        await exchange_rates_job(bot, config)
        await message.answer("✅ Курс валют отправлен!")
    except Exception as e:
        logger.error(f"Error in /rates: {e}")
        await message.answer(f"❌ Ошибка отправки курса: {e}")


@router.message(Command("set_interval"))
@admin_only
async def cmd_set_interval(message: Message, command: CommandObject) -> None:
    """
    Handle /set_interval command — change auto-post interval.

    Usage: /set_interval <minutes>
    """
    if not command.args:
        await message.answer(
            "⚠️ Укажите интервал в минутах.\n"
            "Пример: <code>/set_interval 15</code>",
            parse_mode="HTML",
        )
        return

    try:
        minutes = int(command.args.strip())
        if minutes < 1:
            await message.answer("❌ Интервал должен быть не менее 1 минуты.")
            return
        if minutes > 1440:
            await message.answer("❌ Интервал не может превышать 1440 минут (24 часа).")
            return
    except ValueError:
        await message.answer("❌ Укажите число в минутах.")
        return

    # Update config and reschedule job
    try:
        config.POST_INTERVAL = minutes
        if _scheduler is not None:
            _scheduler.reschedule_job(
                "auto_post",
                trigger={"type": "interval", "minutes": minutes},
            )
        logger.info(f"Post interval changed to {minutes} minutes by admin")
        await message.answer(
            f"✅ Интервал автопостинга изменён на <b>{minutes}</b> минут.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Error rescheduling job: {e}")
        await message.answer(f"❌ Ошибка изменения интервала: {e}")


@router.message(Command("status"))
@admin_only
async def cmd_status(message: Message) -> None:
    """
    Handle /status command — show scheduler and queue status.
    """
    try:
        if _scheduler is None:
            await message.answer("❌ Планировщик не инициализирован.")
            return

        status = get_scheduler_status(_scheduler)

        status_text = (
            f"⚙️ <b>Статус планировщика:</b>\n\n"
            f"  Состояние: <b>{'Работает' if status['running'] else 'Остановлен'}</b>\n"
            f"  Таймзона: <code>{status['timezone']}</code>\n"
            f"  Активных задач: <b>{status['jobs_count']}</b>\n"
            f"  Новостей в очереди: <b>{status['queue_size']}</b>\n\n"
            f"📋 <b>Задачи:</b>\n"
        )

        for job in status["jobs"]:
            next_run = job["next_run"] or "N/A"
            status_text += (
                f"  • <b>{job['name']}</b>\n"
                f"    Следующий запуск: <code>{next_run}</code>\n"
            )

        await message.answer(status_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in /status: {e}")
        await message.answer(f"❌ Ошибка получения статуса: {e}")


@router.message(Command("check"))
@admin_only
async def cmd_check(message: Message) -> None:
    """
    Handle /check command — force news check from all sources.
    """
    await message.answer("🔍 Принудительная проверка новостных источников...")

    try:
        await check_news_job(bot, config)
        await message.answer(
            f"✅ Проверка завершена! Новостей в очереди: <b>{len(news_queue)}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Error in /check: {e}")
        await message.answer(f"❌ Ошибка проверки: {e}")


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------

@router.errors()
async def error_handler(event: types.ErrorEvent) -> None:
    """Handle unhandled exceptions in handlers."""
    logger.error(f"Unhandled exception: {event.exception}", exc_info=True)


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

async def on_startup() -> None:
    """Execute on bot startup."""
    logger.info("=" * 50)
    logger.info("Znews Bot starting up...")
    logger.info(f"Admin IDs: {config.ADMIN_IDS}")
    logger.info(f"Channel: {config.CHANNEL_ID}")
    logger.info(f"Timezone: {config.TIMEZONE}")
    logger.info("=" * 50)


async def on_shutdown() -> None:
    """Execute on bot shutdown."""
    logger.info("Shutting down Znews Bot...")
    if _scheduler is not None:
        shutdown_scheduler(_scheduler)
    await bot.session.close()
    logger.info("Bot stopped gracefully")


def setup_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """Setup OS signal handlers for graceful shutdown."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(on_shutdown()))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    """
    Main async entry point.

    Initializes database, sets up scheduler, registers handlers,
    and starts aiogram polling.
    """
    global _scheduler

    # Validate configuration
    errors = config.validate()
    if errors:
        logger.error("Configuration validation failed:")
        for err in errors:
            logger.error(f"  - {err}")
        sys.exit(1)

    # Initialize database
    try:
        from database.models import init_db
        await init_db(config.DB_PATH)
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)

    # Setup and start scheduler
    _scheduler = setup_scheduler(bot, config)
    start_scheduler(_scheduler)

    # Register router
    dp.include_router(router)

    # Startup notification
    await on_startup()

    # Start polling
    logger.info("Starting aiogram polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
