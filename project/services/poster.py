"""
Модуль для форматирования новостей в посты и отправки в Telegram канал.

Содержит функции для форматирования новостей с анализом важности,
отправки постов через aiogram и полного цикла публикации.
"""

import logging
import os
from typing import Optional

from aiogram import Bot
from aiogram.types import FSInputFile

from services.analyzer import analyze_importance
from services.watermark import add_watermark

logger = logging.getLogger(__name__)

# Хештеги по категориям
CATEGORY_TAGS = {
    "breaking": "#Срочно #Breaking",
    "trading": "#Трейдинг #Торговля",
    "finance": "#Финансы #Инвестиции",
    "economy": "#Экономика #Макро",
    "general": "#Новости",
}

# Эмодзи категорий
CATEGORY_EMOJI = {
    "breaking": "🔴",
    "trading": "📈",
    "finance": "💰",
    "economy": "🏛️",
    "general": "📰",
}


def _format_stars(count: int) -> str:
    """
    Форматирует количество звезд в строку.

    Args:
        count: Количество звезд (1-5).

    Returns:
        Строка со звездами и текстовым описанием.
    """
    stars = "⭐" * max(1, min(5, count))
    labels = {
        5: "Критическая важность",
        4: "Высокая важность",
        3: "Средняя важность",
        2: "Низкая важность",
        1: "Фоновая информация",
    }
    label = labels.get(count, "Не определено")
    return f"{stars} [{label}]"


def _format_category(category: str) -> str:
    """
    Форматирует категорию с эмодзи.

    Args:
        category: Код категории.

    Returns:
        Отформатированная строка категории.
    """
    emoji = CATEGORY_EMOJI.get(category, "📰")
    names = {
        "breaking": "Критически важно",
        "trading": "Трейдинг",
        "finance": "Финансы",
        "economy": "Экономика",
        "general": "Общие новости",
    }
    name = names.get(category, category)
    return f"{emoji} {name}"


def _format_source(source: str) -> str:
    """
    Форматирует источник с эмодзи.

    Args:
        source: Название или URL источника.

    Returns:
        Отформатированная строка источника.
    """
    if not source:
        return "🌍 Неизвестный источник"
    return f"🌍 {source}"


async def format_news_post(news: dict, analysis: dict) -> str:
    """
    Форматирует новость в готовый пост для Telegram.

    Формат поста:
        ⭐⭐⭐⭐⭐ [Важность]
        📰 [Категория]
        🌍 [Источник]

        [Заголовок]

        [Краткое резюме на русском]

        #Znews #Трейдинг #Финансы
        [Ссылка]

    Args:
        news: Словарь с данными новости.
              Ожидаемые ключи: title, source, url, description (опционально).
        analysis: Словарь с результатами анализа от analyze_importance().
                  Ожидаемые ключи: stars, category, summary_ru.

    Returns:
        Отформатированный текст поста для Telegram.
    """
    stars = analysis.get("stars", 1)
    category = analysis.get("category", "general")
    summary_ru = analysis.get("summary_ru", "")

    title = news.get("title", "Без заголовка")
    source = news.get("source", "")
    url = news.get("url", "")

    # Формируем хештеги
    category_tag = CATEGORY_TAGS.get(category, "#Znews")
    hashtags = f"#Znews {category_tag} #Финансы #Трейдинг"

    # Собираем пост
    lines = [
        _format_stars(stars),
        _format_category(category),
        _format_source(source),
        "",
        f"<b>{_escape_html(title)}</b>",
        "",
    ]

    # Добавляем описание если есть
    description = news.get("description", "")
    if description:
        # Ограничиваем длину описания
        if len(description) > 300:
            description = description[:297] + "..."
        lines.append(_escape_html(description))
        lines.append("")

    # Добавляем резюме на русском
    if summary_ru:
        lines.append(f"<i>📝 {_escape_html(summary_ru)}</i>")
        lines.append("")

    # Хештеги
    lines.append(hashtags)

    # Ссылка
    if url:
        lines.append("")
        lines.append(f"🔗 <a href='{url}'>Читать полностью</a>")

    return "\n".join(lines)


def _escape_html(text: str) -> str:
    """
    Экранирует HTML-символы в тексте.

    Args:
        text: Исходный текст.

    Returns:
        Экранированный текст.
    """
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


async def send_to_channel(
    bot: Bot,
    channel_id: str,
    post_text: str,
    image_path: Optional[str] = None,
) -> None:
    """
    Отправляет пост в канал Znews через aiogram Bot.

    Args:
        bot: Экземпляр aiogram Bot.
        channel_id: ID канала (например, "@znews" или "-1001234567890").
        post_text: Текст поста (HTML-разметка).
        image_path: Опциональный путь к изображению для прикрепления.

    Raises:
        ConnectionError: При проблемах с подключением к Telegram API.
        ValueError: При некорректных параметрах.
    """
    try:
        if image_path and os.path.exists(image_path):
            # Отправляем фото с подписью
            photo = FSInputFile(image_path)
            await bot.send_photo(
                chat_id=channel_id,
                photo=photo,
                caption=post_text,
                parse_mode="HTML",
            )
            logger.info(
                "Пост с изображением отправлен в канал %s", channel_id
            )
        else:
            # Отправляем текстовый пост
            await bot.send_message(
                chat_id=channel_id,
                text=post_text,
                parse_mode="HTML",
                disable_web_page_preview=False,
            )
            logger.info("Текстовый пост отправлен в канал %s", channel_id)

    except Exception as e:
        logger.error("Ошибка отправки поста в канал %s: %s", channel_id, e)
        raise ConnectionError(
            f"Не удалось отправить пост в канал {channel_id}: {e}"
        ) from e


async def post_news(
    bot: Bot,
    channel_id: str,
    news: dict,
    temp_image_dir: str = "/tmp/znews_images",
) -> None:
    """
    Полный цикл публикации новости: анализ → форматирование → водяной знак → отправка.

    Args:
        bot: Экземпляр aiogram Bot.
        channel_id: ID канала для публикации.
        news: Словарь с данными новости.
              Ожидаемые ключи: title, source, url, image_url (опц.), description (опц.).
        temp_image_dir: Директория для временных файлов изображений.

    Raises:
        ConnectionError: При проблемах с отправкой в Telegram.
        ValueError: При некорректных данных новости.
    """
    try:
        # Шаг 1: Анализ важности
        logger.info("Начинаем анализ новости: %s", news.get("title", "N/A")[:50])
        analysis = await analyze_importance(news)

        # Шаг 2: Форматирование поста
        post_text = await format_news_post(news, analysis)

        # Шаг 3: Подготовка изображения
        image_path = None
        original_image = news.get("image_path") or news.get("local_image")

        if original_image and os.path.exists(original_image):
            # Накладываем водяной знак
            os.makedirs(temp_image_dir, exist_ok=True)
            filename = os.path.basename(original_image)
            watermarked_path = os.path.join(
                temp_image_dir, f"wm_{filename}"
            )
            try:
                image_path = await add_watermark(
                    original_image, watermarked_path
                )
            except Exception as e:
                logger.warning(
                    "Не удалось наложить водяной знак: %s. "
                    "Отправляем без водяного знака.",
                    e,
                )
                image_path = original_image

        # Шаг 4: Отправка
        await send_to_channel(bot, channel_id, post_text, image_path)

        logger.info(
            "Новость успешно опубликована: stars=%s, category=%s",
            analysis.get("stars"),
            analysis.get("category"),
        )

    except ConnectionError:
        raise
    except Exception as e:
        logger.error("Ошибка в цикле публикации новости: %s", e)
        raise ValueError(f"Не удалось опубликовать новость: {e}") from e
