"""
Модуль для генерации мотивационных цитат и изображений.

Содержит коллекцию из 50+ цитат на тему трейдинга, успеха и дисциплины,
функции для выбора утренних/вечерних цитат и генерации изображений.
"""

import logging
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from services.watermark import (
    WATERMARK_TEXT,
    WATERMARK_FILL,
    WATERMARK_STROKE_FILL,
    STROKE_WIDTH,
)

logger = logging.getLogger(__name__)

# --- Коллекция мотивационных цитат ---
# Утренние цитаты — про начало дня, цели, мотивацию
# Вечерние цитаты — про подведение итогов, обучение на ошибках

MOTIVATIONAL_QUOTES: list[dict] = [
    # Утренние цитаты (morning=True)
    {"text": "Успех в трейдинге — это не результат одной сделки, а сумма тысячи правильных решений.", "author": "", "morning": True, "ru": True},
    {"text": "Каждое утро — это новая возможность стать лучше, чем вчера. Начни с плана.", "author": "", "morning": True, "ru": True},
    {"text": "Дисциплина — это мост между целями и их достижением. Перейди его сегодня.", "author": "", "morning": True, "ru": True},
    {"text": "The market is a device for transferring money from the impatient to the patient.", "author": "Warren Buffett", "morning": True, "ru": False},
    {"text": "Price is what you pay. Value is what you get.", "author": "Warren Buffett", "morning": True, "ru": False},
    {"text": "Рынок открыт — будь готов. Твоя подготовка определяет твой результат.", "author": "", "morning": True, "ru": True},
    {"text": "In trading, it's not about being right. It's about making money when you're right and losing little when you're wrong.", "author": "Michael Marcus", "morning": True, "ru": False},
    {"text": "The goal of a successful trader is to make the best trades. Money is secondary.", "author": "Alexander Elder", "morning": True, "ru": False},
    {"text": "Сегодняшний день — это твоя возможность. Не трать её на сомнения.", "author": "", "morning": True, "ru": True},
    {"text": "Risk comes from not knowing what you're doing.", "author": "Warren Buffett", "morning": True, "ru": False},
    {"text": "Letting losses run is the most serious mistake made by most investors.", "author": "William O'Neil", "morning": True, "ru": False},
    {"text": "Утро трейдера начинается не с графиков, а с правильного настроя.", "author": "", "morning": True, "ru": True},
    {"text": "The trend is your friend until the end when it bends.", "author": "Ed Seykota", "morning": True, "ru": False},
    {"text": "If you don't find a way to make money while you sleep, you will work until you die.", "author": "Warren Buffett", "morning": True, "ru": False},
    {"text": "Каждый день — это новый тренд. Успей войти первым.", "author": "", "morning": True, "ru": True},
    {"text": "What we fear doing most is usually what we most need to do.", "author": "Tim Ferriss", "morning": True, "ru": False},
    {"text": "The stock market is filled with individuals who know the price of everything, but the value of nothing.", "author": "Philip Fisher", "morning": True, "ru": False},
    {"text": "Планируй свои сделки и торгуй по плану — это золотое правило.", "author": "", "morning": True, "ru": True},
    {"text": "Opportunities come infrequently. When it rains gold, put out the bucket, not the thimble.", "author": "Warren Buffett", "morning": True, "ru": False},
    {"text": "Успех — это когда подготовка встречает возможность.", "author": "", "morning": True, "ru": True},
    {"text": "It's not whether you're right or wrong that's important, but how much money you make when you're right and how much you lose when you're wrong.", "author": "George Soros", "morning": True, "ru": False},
    {"text": "Маркет-мейкеры не спят — и ты не спи на деньгах. Анализируй.", "author": "", "morning": True, "ru": True},
    {"text": "The only way to do great work is to love what you do.", "author": "Steve Jobs", "morning": True, "ru": False},
    {"text": "Compound interest is the eighth wonder of the world. He who understands it, earns it.", "author": "Albert Einstein", "morning": True, "ru": False},
    {"text": "Сегодня ты можешь либо приближаться к своей цели, либо удаляться от неё. Выбор за тобой.", "author": "", "morning": True, "ru": True},
    {"text": "Markets can remain irrational longer than you can remain solvent.", "author": "John Maynard Keynes", "morning": True, "ru": False},
    {"text": "A good trader has to have three things: a chronic inability to accept things at face value, a healthy dose of skepticism, and an understanding of human nature.", "author": "Larry Hite", "morning": True, "ru": False},
    {"text": "Торгуй тем, что видишь, а не тем, что думаешь.", "author": "", "morning": True, "ru": True},
    {"text": "The secret to being successful from a trading perspective is to have an indefatigable and an undying and unquenchable thirst for information and knowledge.", "author": "Paul Tudor Jones", "morning": True, "ru": False},
    {"text": "Чем раньше ты начнёшь действовать, тем ближе будет результат.", "author": "", "morning": True, "ru": True},
    # Вечерние цитаты (morning=False)
    {"text": "Проанализируй сегодняшние сделки. Каждая ошибка — это урок, который приближает тебя к успеху.", "author": "", "morning": False, "ru": True},
    {"text": "Торговля — это марафон, а не спринт. Отдыхай и восстанавливай силы.", "author": "", "morning": False, "ru": True},
    {"text": "The most important thing in trading is not to lose money. The second most important is to remember the first rule.", "author": "Paul Tudor Jones", "morning": False, "ru": False},
    {"text": "Do more of what works and less of what doesn't.", "author": "", "morning": False, "ru": False},
    {"text": "Лучший трейдер — тот, кто умеет ждать. Сегодня ты проявил терпение?", "author": "", "morning": False, "ru": True},
    {"text": "You don't need to be a rocket scientist. Investing is not a game where the guy with the 160 IQ beats the guy with 130 IQ.", "author": "Warren Buffett", "morning": False, "ru": False},
    {"text": "The elements of good trading are: cutting losses, cutting losses, and cutting losses.", "author": "Ed Seykota", "morning": False, "ru": False},
    {"text": "Запиши сегодняшние выводы. Журнал сделок — твой лучший учитель.", "author": "", "morning": False, "ru": True},
    {"text": "In this business if you're good, you're right six times out of ten. You're never going to be right nine times out of ten.", "author": "Peter Lynch", "morning": False, "ru": False},
    {"text": "Ты не можешь контролировать рынок, но можешь контролировать себя. Сегодня ты держал эмоции в узде?", "author": "", "morning": False, "ru": True},
    {"text": "Every trader has strengths and weakness. Some are good holders of winners, but may hold their losers a little too long.", "author": "", "morning": False, "ru": False},
    {"text": "The four most dangerous words in investing are: 'this time it's different'.", "author": "John Templeton", "morning": False, "ru": False},
    {"text": "Сегодняшний день закончен, но учёба продолжается. Прочти одну страницу о рынке перед сном.", "author": "", "morning": False, "ru": True},
    {"text": "It's not the trade itself, but how you handle the trade that matters.", "author": "Mark Douglas", "morning": False, "ru": False},
    {"text": "The best investment you can make is in yourself.", "author": "Warren Buffett", "morning": False, "ru": False},
    {"text": "Отпусти сегодняшние убытки. Завтра — новый день и новые возможности.", "author": "", "morning": False, "ru": True},
    {"text": "In trading, you have to be defensive and aggressive at the same time.", "author": "Stanley Druckenmiller", "morning": False, "ru": False},
    {"text": "Трейдинг — это не про деньги. Это про принятие правильных решений под давлением.", "author": "", "morning": False, "ru": True},
    {"text": "The goal is not to predict the future, but to be prepared for it.", "author": "", "morning": False, "ru": False},
    {"text": "Don't focus on making money, focus on protecting what you have.", "author": "Paul Tudor Jones", "morning": False, "ru": False},
    {"text": "Подведи итоги дня. Что сработало? Что можно улучшить? Рост начинается с рефлексии.", "author": "", "morning": False, "ru": True},
    {"text": "If you personalize losses, you can't trade.", "author": "Bruce Kovner", "morning": False, "ru": False},
    {"text": "Successful trading is about finding your edge and exploiting it repeatedly.", "author": "", "morning": False, "ru": False},
    {"text": "Не сравнивай себя с другими трейдерами. Сравнивай себя с собой вчерашним.", "author": "", "morning": False, "ru": True},
    {"text": "The greatest enemy of knowledge is not ignorance, it is the illusion of knowledge.", "author": "Stephen Hawking", "morning": False, "ru": False},
]

# Параметры изображения
IMAGE_WIDTH = 1080
IMAGE_HEIGHT = 1080

# Цветовые схемы для градиентного фона
BACKGROUND_THEMES = [
    # Тёмно-синий градиент
    {"top": (15, 23, 42), "bottom": (30, 41, 59)},
    # Тёмно-фиолетовый
    {"top": (30, 15, 50), "bottom": (50, 25, 80)},
    # Тёмно-зелёный
    {"top": (10, 30, 20), "bottom": (20, 50, 35)},
    # Тёмно-бордовый
    {"top": (40, 10, 15), "bottom": (70, 20, 30)},
    # Графитовый
    {"top": (20, 20, 25), "bottom": (40, 40, 50)},
    # Тёмно-бирюзовый
    {"top": (10, 30, 40), "bottom": (20, 55, 65)},
]


def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """
    Возвращает шрифт заданного размера.

    Args:
        size: Размер шрифта в пикселях.
        bold: Использовать ли жирный шрифт.

    Returns:
        Объект шрифта Pillow.
    """
    font_names = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]

    for font_path in font_names:
        try:
            return ImageFont.truetype(font_path, size)
        except (OSError, IOError):
            continue

    logger.warning("Не найден подходящий шрифт для мотивации, используем дефолтный")
    return ImageFont.load_default()


def _draw_gradient_background(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    theme: dict,
) -> None:
    """
    Рисует градиентный фон на изображении.

    Args:
        draw: Объект ImageDraw.
        width: Ширина изображения.
        height: Высота изображения.
        theme: Словарь с цветами {"top": (r,g,b), "bottom": (r,g,b)}.
    """
    top_color = theme["top"]
    bottom_color = theme["bottom"]

    for y in range(height):
        ratio = y / height
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    """
    Переносит текст по словам чтобы уместиться в заданную ширину.

    Args:
        text: Исходный текст.
        font: Шрифт для измерения.
        max_width: Максимальная ширина строки.
        draw: Объект ImageDraw.

    Returns:
        Список строк.
    """
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        text_width = bbox[2] - bbox[0]

        if text_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


async def get_daily_motivation(morning: bool = True) -> dict:
    """
    Возвращает мотивационную цитату для утра или вечера.

    Args:
        morning: Если True — возвращает утреннюю цитату,
                 если False — вечернюю.

    Returns:
        Словарь с цитатой {"text": "...", "author": "..."}.
    """
    # Фильтруем цитаты по времени суток
    filtered = [q for q in MOTIVATIONAL_QUOTES if q.get("morning") == morning]

    if not filtered:
        # Fallback: берем любую цитату
        filtered = MOTIVATIONAL_QUOTES

    quote = random.choice(filtered)

    result = {
        "text": quote["text"],
        "author": quote.get("author", ""),
        "morning": morning,
    }

    logger.info(
        "Выбрана %s мотивация: %s...",
        "утренняя" if morning else "вечерняя",
        quote["text"][:50],
    )
    return result


async def generate_motivation_image(quote: dict, output_path: str) -> str:
    """
    Создает изображение с цитатой и водяным знаком.

    Создает квадратное изображение (1080x1080) с темным градиентным фоном,
    текстом цитаты по центру и водяным знаком Znews.

    Args:
        quote: Словарь с цитатой {"text": "...", "author": "..."}.
        output_path: Путь для сохранения изображения.

    Returns:
        Путь к созданному изображению.

    Raises:
        ValueError: Если не удалось создать изображение.
    """
    try:
        # Создаем изображение с альфа-каналом
        img = Image.new("RGBA", (IMAGE_WIDTH, IMAGE_HEIGHT), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)

        # Рисуем градиентный фон
        theme = random.choice(BACKGROUND_THEMES)
        _draw_gradient_background(draw, IMAGE_WIDTH, IMAGE_HEIGHT, theme)

        # --- Рисуем декоративные элементы ---
        # Линия сверху
        draw.rectangle(
            [(IMAGE_WIDTH // 2 - 150, 80), (IMAGE_WIDTH // 2 + 150, 84)],
            fill=(255, 255, 255, 100),
        )

        # --- Подготавливаем текст ---
        quote_text = quote.get("text", "")
        author = quote.get("author", "")

        # Размер шрифта для цитаты (зависит от длины)
        if len(quote_text) < 80:
            quote_font_size = 48
        elif len(quote_text) < 150:
            quote_font_size = 40
        else:
            quote_font_size = 32

        quote_font = _get_font(quote_font_size, bold=True)
        author_font = _get_font(28, bold=False)

        # Максимальная ширина текста (80% от ширины изображения)
        max_text_width = int(IMAGE_WIDTH * 0.8)

        # Переносим текст
        lines = _wrap_text(quote_text, quote_font, max_text_width, draw)

        # --- Вычисляем позицию текста ---
        line_height = quote_font_size + 12
        total_text_height = len(lines) * line_height

        if author:
            total_text_height += 40  # Отступ перед автором
            total_text_height += 32  # Высота строки автора

        # Центрируем блок текста
        start_y = (IMAGE_HEIGHT - total_text_height) // 2

        # Рисуем кавычки
        quote_mark_font = _get_font(80, bold=True)
        draw.text(
            (IMAGE_WIDTH // 2, start_y - 50),
            "\"",
            font=quote_mark_font,
            fill=(255, 255, 255, 80),
            anchor="mm",
        )

        # Рисуем строки цитаты
        current_y = start_y
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=quote_font)
            line_width = bbox[2] - bbox[0]
            x = (IMAGE_WIDTH - line_width) // 2
            draw.text(
                (x, current_y),
                line,
                font=quote_font,
                fill=(255, 255, 255, 230),
            )
            current_y += line_height

        # Рисуем автора
        if author:
            current_y += 20
            author_text = f"— {author}"
            bbox = draw.textbbox((0, 0), author_text, font=author_font)
            author_width = bbox[2] - bbox[0]
            x = (IMAGE_WIDTH - author_width) // 2
            draw.text(
                (x, current_y),
                author_text,
                font=author_font,
                fill=(200, 200, 200, 200),
            )

        # --- Рисуем водяной знак Znews ---
        wm_font_size = max(20, int(IMAGE_HEIGHT * 0.06))
        wm_font = _get_font(wm_font_size, bold=True)
        wm_bbox = draw.textbbox(
            (0, 0), WATERMARK_TEXT, font=wm_font, stroke_width=STROKE_WIDTH
        )
        wm_width = wm_bbox[2] - wm_bbox[0]
        wm_margin = int(IMAGE_WIDTH * 0.03)
        wm_x = IMAGE_WIDTH - wm_width - wm_margin - wm_bbox[0]
        wm_y = IMAGE_HEIGHT - wm_font_size - wm_margin

        draw.text(
            (wm_x, wm_y),
            WATERMARK_TEXT,
            font=wm_font,
            fill=WATERMARK_FILL,
            stroke_width=STROKE_WIDTH,
            stroke_fill=WATERMARK_STROKE_FILL,
        )

        # --- Рисуем метку времени ---
        time_label = "Доброе утро ☀️" if quote.get("morning", True) else "Добрый вечер 🌙"
        time_font = _get_font(22, bold=False)
        draw.text(
            (IMAGE_WIDTH // 2, IMAGE_HEIGHT - 60),
            time_label,
            font=time_font,
            fill=(255, 255, 255, 120),
            anchor="mm",
        )

        # --- Сохраняем ---
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        img.save(output_path, "PNG")
        logger.info("Мотивационное изображение создано: %s", output_path)
        return output_path

    except Exception as e:
        logger.error("Ошибка создания мотивационного изображения: %s", e)
        raise ValueError(f"Не удалось создать изображение: {e}") from e
