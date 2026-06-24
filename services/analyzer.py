"""
Модуль для анализа важности новостей для трейдинга.

Анализирует новости на основе ключевых слов (без внешнего AI API),
определяет рейтинг важности (1-5 звезд), категорию и создает
краткое резюме на русском языке.
"""

import logging
from typing import Optional

from parsers.news_filter import categorize, KEYWORDS

logger = logging.getLogger(__name__)

# Ключевые слова для определения важности
BREAKING_KEYWORDS = [
    "breaking", "urgent", "alert", "crash", "collapse", "surge",
    "spike", "plunge", "rally", "recession", "crisis", "emergency",
    "fed announces", " rate cut", " rate hike", "bank failure",
    "market halt", "trading suspended", "default", "bankruptcy",
    "meltdown", "war", "sanctions", "oil embargo", "currency crisis",
    "hyperinflation", "black swan",
    "обвал", "крах", "кризис", "война", "санкции", "дефолт",
    "банкротство", "гиперинфляция", "эмбарго", "рецессия",
]

TRADING_KEYWORDS = [
    "trading", "forex", "crypto", "bitcoin", "ethereum", "btc",
    "eth", "signal", "position", "long", "short", "leverage",
    "margin", "futures", "options", "volatility", "rsi", "macd",
    "breakout", "pump", "dump", "altcoin", "defi", "token",
    "трейдинг", "форекс", "крипто", "биткоин", "сигнал",
    "позиция", "лонг", "шорт", "плечо", "фьючерсы", "волатильность",
    "пробой", "альткоин", "токен", "блокчейн",
]

FINANCE_KEYWORDS = [
    "stock", "bond", "equity", "dividend", "earnings", "revenue",
    "profit", "loss", "ipo", "merger", "acquisition", "buyback",
    "shares", "market cap", "valuation", "portfolio", "etf",
    "акции", "облигации", "дивиденды", "доходы", "прибыль",
    "убыток", "ipo", "слияние", "поглощение", "капитализация",
    "портфель", "фонд", "индекс",
]

ECONOMY_KEYWORDS = [
    "gdp", "inflation", "cpi", "ppi", "unemployment", "jobs",
    "consumer", "retail", "manufacturing", "pmi", "trade",
    "import", "export", "deficit", "surplus", "budget",
    "fiscal", "monetary", "central bank", "treasury", "yield",
    "ввп", "инфляция", "безработица", "производство", "торговля",
    "импорт", "экспорт", "дефицит", "бюджет", "доходность",
]

# Словарь для базового перевода ключевых терминов
TRANSLATION_MAP = {
    "breaking": "Срочно",
    "urgent": "Срочно",
    "alert": "Тревога",
    "crash": "Крах",
    "collapse": "Коллапс",
    "surge": "Резкий рост",
    "spike": "Всплеск",
    "plunge": "Обвал",
    "rally": "Ралли",
    "recession": "Рецессия",
    "crisis": "Кризис",
    "fed": "ФРС",
    "rate cut": "Снижение ставки",
    "rate hike": "Повышение ставки",
    "interest rate": "Процентная ставка",
    "bankruptcy": "Банкротство",
    "default": "Дефолт",
    "sanctions": "Санкции",
    "war": "Война",
    "trading": "Трейдинг",
    "forex": "Форекс",
    "crypto": "Криптовалюта",
    "bitcoin": "Биткоин",
    "ethereum": "Эфириум",
    "volatility": "Волатильность",
    "futures": "Фьючерсы",
    "options": "Опционы",
    "stock": "Акции",
    "bond": "Облигации",
    "dividend": "Дивиденды",
    "earnings": "Отчетность",
    "ipo": "IPO",
    "merger": "Слияние",
    "acquisition": "Поглощение",
    "inflation": "Инфляция",
    "gdp": "ВВП",
    "unemployment": "Безработица",
    "market": "Рынок",
    "price": "Цена",
    "growth": "Рост",
    "decline": "Снижение",
    "record": "Рекорд",
    "high": "Максимум",
    "low": "Минимум",
    "data": "Данные",
    "report": "Отчет",
}


def _count_keywords(text: str, keywords: list[str]) -> int:
    """
    Подсчитывает количество вхождений ключевых слов в текст.

    Args:
        text: Текст для анализа.
        keywords: Список ключевых слов.

    Returns:
        Количество найденных ключевых слов.
    """
    text_lower = text.lower()
    count = 0
    for keyword in keywords:
        if keyword.lower() in text_lower:
            count += 1
    return count


def _generate_summary_ru(text: str, stars: int, category: str) -> str:
    """
    Генерирует краткое резюме на русском языке.

    Args:
        text: Исходный текст новости.
        stars: Рейтинг важности (1-5).
        category: Категория новости.

    Returns:
        Краткое резюме на русском.
    """
    # Находим ключевые слова в тексте и пытаемся перевести
    found_terms = []
    text_lower = text.lower()

    for en_term, ru_term in sorted(
        TRANSLATION_MAP.items(), key=lambda x: -len(x[0])
    ):
        if en_term.lower() in text_lower and ru_term not in found_terms:
            found_terms.append(ru_term)

    # Формируем резюме
    category_names = {
        "breaking": "Важная новость",
        "trading": "Новость для трейдеров",
        "finance": "Финансовая новость",
        "economy": "Экономическая новость",
        "general": "Новость",
    }

    summary_parts = [category_names.get(category, "Новость")]

    if stars >= 4:
        summary_parts.append("высокой важности")
    elif stars >= 2:
        summary_parts.append("средней важности")

    if found_terms:
        # Берем первые 3-4 термина
        terms_str = ", ".join(found_terms[:4])
        summary_parts.append(f"влияет на: {terms_str}")

    # Добавляем краткое описание по количеству звезд
    if stars == 5:
        summary_parts.append("⚡ Требует немедленного внимания!")
    elif stars == 4:
        summary_parts.append("🔔 Рекомендуется отслеживать")
    elif stars == 3:
        summary_parts.append("📌 Полезная информация для инвесторов")
    elif stars == 2:
        summary_parts.append("📋 Общая информация")
    else:
        summary_parts.append("ℹ️ Фоновая информация")

    return " ".join(summary_parts)


async def analyze_importance(news: dict) -> dict:
    """
    Анализирует важность новости для трейдинга.

    Анализ выполняется на основе ключевых слов без использования
    внешнего AI API.

    Args:
        news: Словарь с данными новости.
              Ожидается наличие ключей "title" и/или "description".

    Returns:
        Словарь с результатами анализа:
        {
            "stars": int (1-5),
            "category": str,
            "summary_ru": str,
            "raw_scores": dict,  # отладочная информация
        }
    """
    # Извлекаем текст для анализа
    title = news.get("title", "")
    description = news.get("description", "")
    text = f"{title} {description}".strip()

    if not text:
        logger.warning("Пустой текст новости для анализа")
        return {
            "stars": 1,
            "category": "general",
            "summary_ru": "Новость без описания.",
            "raw_scores": {},
        }

    # Подсчитываем ключевые слова по категориям
    breaking_count = _count_keywords(text, BREAKING_KEYWORDS)
    trading_count = _count_keywords(text, TRADING_KEYWORDS)
    finance_count = _count_keywords(text, FINANCE_KEYWORDS)
    economy_count = _count_keywords(text, ECONOMY_KEYWORDS)

    raw_scores = {
        "breaking": breaking_count,
        "trading": trading_count,
        "finance": finance_count,
        "economy": economy_count,
    }

    logger.debug("Оценки ключевых слов: %s", raw_scores)

    # Определяем рейтинг (1-5 звезд)
    if breaking_count > 0 and trading_count > 0:
        stars = 5
    elif breaking_count > 0:
        stars = 5
    elif trading_count >= 2:
        stars = 4
    elif trading_count == 1:
        stars = 4
    elif finance_count >= 2:
        stars = 3
    elif finance_count == 1:
        stars = 3
    elif economy_count >= 2:
        stars = 2
    elif economy_count == 1:
        stars = 2
    else:
        stars = 1

    # Определяем категорию через news_filter
    category = categorize(text)

    # Генерируем резюме на русском
    summary_ru = _generate_summary_ru(text, stars, category)

    # Формируем строку звезд
    stars_str = "⭐" * stars

    logger.info(
        "Анализ новости: stars=%d, category=%s, title=%s",
        stars,
        category,
        title[:60] if title else "N/A",
    )

    return {
        "stars": stars,
        "category": category,
        "summary_ru": summary_ru,
        "stars_str": stars_str,
        "raw_scores": raw_scores,
    }


async def translate_to_russian(text: str) -> str:
    """
    Переводит текст на русский язык (базовый метод).

    Выполняет простой перевод ключевых терминов из английского
    на русский на основе встроенного словаря.

    Args:
        text: Текст для перевода.

    Returns:
        Текст с переведенными терминами.
    """
    if not text:
        return ""

    result = text
    for en_term, ru_term in sorted(
        TRANSLATION_MAP.items(), key=lambda x: -len(x[0])
    ):
        # Заменяем термин с сохранением регистра первой буквы
        if en_term.lower() in result.lower():
            result = result.replace(en_term, ru_term)
            result = result.replace(en_term.capitalize(), ru_term)
            result = result.replace(en_term.upper(), ru_term.upper())

    logger.debug("Перевод: '%s' -> '%s'", text[:50], result[:50])
    return result
