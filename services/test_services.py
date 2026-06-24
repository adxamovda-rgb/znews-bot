"""
Тесты для сервисных модулей Telegram бота Znews.

Запуск:
    pytest services/test_services.py -v
    или
    python -m pytest services/test_services.py -v
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

# Настройка логирования для тестов
logging.basicConfig(level=logging.DEBUG)

# --- Fixtures ---


@pytest.fixture
def sample_image_path():
    """Создает временное тестовое изображение."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img = Image.new("RGBA", (800, 600), (100, 150, 200, 255))
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, 750, 550], fill=(50, 100, 150, 255))
        img.save(f.name)
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def sample_image_bytes():
    """Создает тестовое изображение в виде bytes."""
    import io

    img = Image.new("RGBA", (600, 400), (200, 100, 50, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_news_low():
    """Новость низкой важности."""
    return {
        "title": "Local company opens new office downtown",
        "description": "A small local business expanded their workspace.",
        "source": "Local News",
        "url": "https://example.com/news/1",
    }


@pytest.fixture
def sample_news_trading():
    """Новость про трейдинг — высокая важность."""
    return {
        "title": "Bitcoin breaks $100k resistance level, crypto markets rally",
        "description": "Trading volumes surge as BTC futures positions increase dramatically.",
        "source": "CryptoDaily",
        "url": "https://example.com/news/2",
    }


@pytest.fixture
def sample_news_breaking():
    """Бreaking новость — критическая важность."""
    return {
        "title": "BREAKING: Fed announces emergency rate cut amid market crash",
        "description": "Stock markets plunge as recession fears trigger bank failures.",
        "source": "Reuters",
        "url": "https://example.com/news/3",
    }


@pytest.fixture
def temp_output_dir():
    """Временная директория для выходных файлов."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# --- Тесты watermark ---


@pytest.mark.asyncio
async def test_add_watermark(sample_image_path, temp_output_dir):
    """Тест наложения водяного знака на файл."""
    from services.watermark import add_watermark

    output_path = os.path.join(temp_output_dir, "watermarked.png")
    result = await add_watermark(sample_image_path, output_path)

    assert result == output_path
    assert os.path.exists(output_path)

    # Проверяем размеры изображения
    with Image.open(output_path) as img:
        assert img.size == (800, 600)


@pytest.mark.asyncio
async def test_add_watermark_to_bytes(sample_image_bytes):
    """Тест наложения водяного знака на bytes."""
    from services.watermark import add_watermark_to_bytes

    result = await add_watermark_to_bytes(sample_image_bytes)

    assert isinstance(result, bytes)
    assert len(result) > 0

    # Проверяем что результат — валидное изображение
    import io

    img = Image.open(io.BytesIO(result))
    assert img.size == (600, 400)


@pytest.mark.asyncio
async def test_add_watermark_file_not_found(temp_output_dir):
    """Тест ошибки при отсутствии файла."""
    from services.watermark import add_watermark

    with pytest.raises(FileNotFoundError):
        await add_watermark("/nonexistent/file.png", "/tmp/out.png")


# --- Тесты cbu_api ---


@pytest.mark.asyncio
async def test_get_exchange_rates():
    """Тест получения курсов валют."""
    from services.cbu_api import get_exchange_rates, DEFAULT_CURRENCIES

    rates = await get_exchange_rates()

    assert isinstance(rates, dict)
    assert len(rates) > 0

    # Проверяем структуру ответа
    for currency, data in rates.items():
        assert "rate" in data
        assert "date" in data
        assert isinstance(data["rate"], float)
        assert data["rate"] > 0


@pytest.mark.asyncio
async def test_get_exchange_rates_specific():
    """Тест получения курсов для конкретных валют."""
    from services.cbu_api import get_exchange_rates

    rates = await get_exchange_rates(["USD", "EUR"])

    assert isinstance(rates, dict)
    assert len(rates) <= 2

    if "USD" in rates:
        assert rates["USD"]["rate"] > 0


@pytest.mark.asyncio
async def test_format_rates_message():
    """Тест форматирования сообщения с курсами."""
    from services.cbu_api import format_rates_message

    sample_rates = {
        "USD": {"rate": 12650.00, "date": "2026-06-17", "name": "Доллар США"},
        "EUR": {"rate": 13800.50, "date": "2026-06-17", "name": "Евро"},
        "RUB": {"rate": 142.30, "date": "2026-06-17", "name": "Российский рубль"},
    }

    message = await format_rates_message(sample_rates)

    assert "Курсы валют" in message
    assert "USD" in message
    assert "12,650" in message or "12650" in message
    assert "🇺🇸" in message
    assert "cbu.uz" in message


@pytest.mark.asyncio
async def test_format_rates_message_empty():
    """Тест форматирования пустых курсов."""
    from services.cbu_api import format_rates_message

    message = await format_rates_message({})

    assert "❌" in message


# --- Тесты motivator ---


@pytest.mark.asyncio
async def test_get_daily_motivation_morning():
    """Тест получения утренней мотивации."""
    from services.motivator import get_daily_motivation

    quote = await get_daily_motivation(morning=True)

    assert isinstance(quote, dict)
    assert "text" in quote
    assert "author" in quote
    assert len(quote["text"]) > 0


@pytest.mark.asyncio
async def test_get_daily_motivation_evening():
    """Тест получения вечерней мотивации."""
    from services.motivator import get_daily_motivation

    quote = await get_daily_motivation(morning=False)

    assert isinstance(quote, dict)
    assert "text" in quote
    assert "author" in quote
    assert len(quote["text"]) > 0


def test_motivational_quotes_count():
    """Тест что цитат достаточно (50+)."""
    from services.motivator import MOTIVATIONAL_QUOTES

    assert len(MOTIVATIONAL_QUOTES) >= 50


def test_motivational_quotes_structure():
    """Тест структуры цитат."""
    from services.motivator import MOTIVATIONAL_QUOTES

    for quote in MOTIVATIONAL_QUOTES:
        assert "text" in quote
        assert "morning" in quote
        assert isinstance(quote["text"], str)
        assert len(quote["text"]) > 0
        assert isinstance(quote["morning"], bool)


def test_morning_evening_quotes_exist():
    """Тест что есть и утренние, и вечерние цитаты."""
    from services.motivator import MOTIVATIONAL_QUOTES

    morning = [q for q in MOTIVATIONAL_QUOTES if q.get("morning")]
    evening = [q for q in MOTIVATIONAL_QUOTES if not q.get("morning")]

    assert len(morning) > 0, "Должны быть утренние цитаты"
    assert len(evening) > 0, "Должны быть вечерние цитаты"


@pytest.mark.asyncio
async def test_generate_motivation_image(temp_output_dir):
    """Тест генерации мотивационного изображения."""
    from services.motivator import generate_motivation_image

    quote = {"text": "Тестовая цитата для успеха в трейдинге.", "author": "Тест", "morning": True}
    output_path = os.path.join(temp_output_dir, "motivation.png")

    result = await generate_motivation_image(quote, output_path)

    assert result == output_path
    assert os.path.exists(output_path)

    # Проверяем размеры
    with Image.open(output_path) as img:
        assert img.size == (1080, 1080)


# --- Тесты analyzer ---


@pytest.mark.asyncio
async def test_analyze_importance_low(sample_news_low):
    """Тест анализа новости низкой важности."""
    from services.analyzer import analyze_importance

    result = await analyze_importance(sample_news_low)

    assert isinstance(result, dict)
    assert "stars" in result
    assert "category" in result
    assert "summary_ru" in result

    # Новость низкой важности — 1-2 звезды
    assert 1 <= result["stars"] <= 2


@pytest.mark.asyncio
async def test_analyze_importance_trading(sample_news_trading):
    """Тест анализа новости про трейдинг."""
    from services.analyzer import analyze_importance

    result = await analyze_importance(sample_news_trading)

    assert result["stars"] >= 3  # Трейдинг + крипта = высокая важность
    assert result["category"] in ["trading", "breaking"]
    assert len(result["summary_ru"]) > 0
    assert "Криптовалюта" in result["summary_ru"] or "Трейдинг" in result["summary_ru"]


@pytest.mark.asyncio
async def test_analyze_importance_breaking(sample_news_breaking):
    """Тест анализа breaking новости."""
    from services.analyzer import analyze_importance

    result = await analyze_importance(sample_news_breaking)

    assert result["stars"] == 5  # Breaking + кризис = максимальная важность
    assert result["category"] == "breaking"
    assert "⚡" in result["summary_ru"]


@pytest.mark.asyncio
async def test_analyze_importance_empty():
    """Тест анализа пустой новости."""
    from services.analyzer import analyze_importance

    result = await analyze_importance({})

    assert result["stars"] == 1
    assert result["category"] == "general"


@pytest.mark.asyncio
async def test_translate_to_russian():
    """Тест перевода на русский."""
    from services.analyzer import translate_to_russian

    text = "Bitcoin trading crash alert market volatility"
    result = await translate_to_russian(text)

    assert "Биткоин" in result
    assert "Трейдинг" in result
    assert "Крах" in result
    assert "Тревога" in result
    assert "Волатильность" in result


@pytest.mark.asyncio
async def test_translate_to_russian_empty():
    """Тест перевода пустого текста."""
    from services.analyzer import translate_to_russian

    result = await translate_to_russian("")
    assert result == ""


# --- Тесты poster ---


@pytest.mark.asyncio
async def test_format_news_post(sample_news_trading):
    """Тест форматирования новостного поста."""
    from services.poster import format_news_post
    from services.analyzer import analyze_importance

    analysis = await analyze_importance(sample_news_trading)
    post = await format_news_post(sample_news_trading, analysis)

    assert "⭐" in post
    assert "📈" in post
    assert "#Znews" in post
    assert sample_news_trading["title"] in post


@pytest.mark.asyncio
async def test_format_news_post_with_url(sample_news_low):
    """Тест форматирования поста со ссылкой."""
    from services.poster import format_news_post
    from services.analyzer import analyze_importance

    analysis = await analyze_importance(sample_news_low)
    post = await format_news_post(sample_news_low, analysis)

    assert "https://example.com/news/1" in post


@pytest.mark.asyncio
async def test_format_news_post_html_escaping():
    """Тест экранирования HTML в посте."""
    from services.poster import format_news_post

    news = {
        "title": "Test <script>alert(1)</script> news",
        "source": "Test",
        "url": "",
    }
    analysis = {"stars": 3, "category": "general", "summary_ru": "Test"}
    post = await format_news_post(news, analysis)

    assert "<script>" not in post
    assert "&lt;script&gt;" in post


# --- Тесты parsers/news_filter ---


def test_categorize_trading():
    """Тест категоризации трейдинговой новости."""
    from parsers.news_filter import categorize

    text = "Bitcoin crypto trading signals forex market analysis"
    result = categorize(text)
    assert result == "trading"


def test_categorize_breaking():
    """Тест категоризации breaking новости."""
    from parsers.news_filter import categorize

    text = "BREAKING: market crash recession crisis alert"
    result = categorize(text)
    assert result == "breaking"


def test_categorize_economy():
    """Тест категоризации экономической новости."""
    from parsers.news_filter import categorize

    text = "GDP inflation unemployment rate consumer retail data"
    result = categorize(text)
    assert result == "economy"


def test_categorize_general():
    """Тест категоризации общей новости."""
    from parsers.news_filter import categorize

    text = "Local park opened for public use this weekend"
    result = categorize(text)
    assert result == "general"


def test_categorize_empty():
    """Тест категоризации пустого текста."""
    from parsers.news_filter import categorize

    assert categorize("") == "general"
    assert categorize(None) == "general"


# --- Тесты интеграционные ---


@pytest.mark.asyncio
async def test_full_pipeline(sample_news_trading, temp_output_dir):
    """Интеграционный тест полного pipeline: анализ → форматирование."""
    from services.analyzer import analyze_importance
    from services.poster import format_news_post

    analysis = await analyze_importance(sample_news_trading)
    post = await format_news_post(sample_news_trading, analysis)

    assert analysis["stars"] >= 3
    assert len(post) > 0
    assert "⭐" in post


@pytest.mark.asyncio
async def test_watermark_with_motivation(temp_output_dir):
    """Интеграционный тест: генерация мотивации + водяной знак."""
    from services.motivator import generate_motivation_image
    from services.watermark import add_watermark

    quote = {"text": "Интеграционный тест цитаты.", "author": "Test", "morning": True}
    motivation_path = os.path.join(temp_output_dir, "motivation.png")
    watermarked_path = os.path.join(temp_output_dir, "motivation_wm.png")

    img_path = await generate_motivation_image(quote, motivation_path)
    result = await add_watermark(img_path, watermarked_path)

    assert os.path.exists(result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
