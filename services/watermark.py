"""
Модуль для наложения водяного знака Znews на изображения.

Использует Pillow (PIL) для добавления текста "Znews" в нижний правый угол
изображения с прозрачностью 60%.
"""

import logging
import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

WATERMARK_TEXT = "Znews"
# Прозрачность 60% = 153 из 255
WATERMARK_ALPHA = 153
# Белый текст с черной обводкой
WATERMARK_FILL = (255, 255, 255, WATERMARK_ALPHA)
WATERMARK_STROKE_FILL = (0, 0, 0, WATERMARK_ALPHA)
STROKE_WIDTH = 2

# Отступ от краев изображения (в долях)
MARGIN_RATIO = 0.02


def _get_font(image_height: int) -> ImageFont.FreeTypeFont:
    """
    Возвращает шрифт для водяного знака подходящего размера.

    Размер шрифта составляет ~10% от высоты изображения.
    Пытается использовать DejaVu Sans Bold, иначе системный аналог.

    Args:
        image_height: Высота изображения в пикселях.

    Returns:
        Объект шрифта Pillow.
    """
    font_size = max(12, int(image_height * 0.1))

    # Список возможных шрифтов в порядке приоритета
    font_candidates = [
        "DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
        "LiberationSans-Bold.ttf",
        "LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "arial.ttf",
        "Arial.ttf",
    ]

    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, font_size)
        except (OSError, IOError):
            continue

    # Fallback на дефолтный шрифт
    logger.warning("Не найден подходящий шрифт, используем шрифт по умолчанию")
    return ImageFont.load_default()


def _find_watermark_position(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    image_width: int,
    image_height: int,
) -> tuple:
    """
    Вычисляет позицию для размещения водяного знака.

    Args:
        draw: Объект ImageDraw.
        text: Текст водяного знака.
        font: Шрифт для текста.
        image_width: Ширина изображения.
        image_height: Высота изображения.

    Returns:
        Кортеж (x, y) с координатами для текста.
    """
    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
        stroke_width=STROKE_WIDTH,
    )
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    margin_x = int(image_width * MARGIN_RATIO)
    margin_y = int(image_height * MARGIN_RATIO)

    x = image_width - text_width - margin_x - bbox[0]
    y = image_height - text_height - margin_y - bbox[1]

    return x, y


async def add_watermark(image_path: str, output_path: str) -> str:
    """
    Накладывает водяной знак 'Znews' на изображение.

    Водяной знак размещается в нижнем правом углу.
    Белый текст с черной обводкой, прозрачность 60%.

    Args:
        image_path: Путь к исходному изображению.
        output_path: Путь для сохранения результата.

    Returns:
        Путь к результирующему изображению.

    Raises:
        FileNotFoundError: Если исходное изображение не найдено.
        ValueError: Если изображение не может быть обработано.
    """
    try:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Изображение не найдено: {image_path}")

        with Image.open(image_path) as img:
            # Конвертируем в RGBA для поддержки прозрачности
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # Создаем отдельный слой для водяного знака
            watermark_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(watermark_layer)

            font = _get_font(img.height)
            x, y = _find_watermark_position(
                draw, WATERMARK_TEXT, font, img.width, img.height
            )

            draw.text(
                (x, y),
                WATERMARK_TEXT,
                font=font,
                fill=WATERMARK_FILL,
                stroke_width=STROKE_WIDTH,
                stroke_fill=WATERMARK_STROKE_FILL,
            )

            # Комбинируем слои
            result = Image.alpha_composite(img, watermark_layer)

            # Создаем директорию для выходного файла если нужно
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            # Сохраняем в формате исходного изображения или PNG
            if img.format and img.format.upper() in ("JPEG", "JPG"):
                result = result.convert("RGB")
                result.save(output_path, "JPEG", quality=95)
            else:
                result.save(output_path, img.format or "PNG")

        logger.info("Водяной знак наложен: %s -> %s", image_path, output_path)
        return output_path

    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error("Ошибка наложения водяного знака: %s", e)
        raise ValueError(f"Не удалось обработать изображение: {e}") from e


async def add_watermark_to_bytes(image_bytes: bytes) -> bytes:
    """
    Накладывает водяной знак на изображение из bytes.

    Args:
        image_bytes: Байты изображения.

    Returns:
        Байты изображения с водяным знаком.

    Raises:
        ValueError: Если изображение не может быть обработано.
    """
    try:
        input_buffer = BytesIO(image_bytes)

        with Image.open(input_buffer) as img:
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            watermark_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(watermark_layer)

            font = _get_font(img.height)
            x, y = _find_watermark_position(
                draw, WATERMARK_TEXT, font, img.width, img.height
            )

            draw.text(
                (x, y),
                WATERMARK_TEXT,
                font=font,
                fill=WATERMARK_FILL,
                stroke_width=STROKE_WIDTH,
                stroke_fill=WATERMARK_STROKE_FILL,
            )

            result = Image.alpha_composite(img, watermark_layer)

            output_buffer = BytesIO()

            # Определяем формат для сохранения
            if img.format and img.format.upper() in ("JPEG", "JPG"):
                result = result.convert("RGB")
                result.save(output_buffer, format="JPEG", quality=95)
            else:
                result.save(output_buffer, format=img.format or "PNG")

        output_buffer.seek(0)
        logger.info("Водяной знак наложен на изображение из bytes")
        return output_buffer.getvalue()

    except Exception as e:
        logger.error("Ошибка наложения водяного знака на bytes: %s", e)
        raise ValueError(f"Не удалось обработать изображение из bytes: {e}") from e
