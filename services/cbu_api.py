"""
Модуль для получения курсов валют от Центрального Банка Узбекистана (ЦБУ).

Использует публичное API cbu.uz для получения актуальных курсов валют.
Поддерживает форматирование результатов для отправки в Telegram.
"""

import logging
from datetime import date
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# Базовый URL API ЦБ Узбекистана
CBU_BASE_URL = "https://cbu.uz/ru/arkhiv-kursov-valyut/json/"

# Валюты по умолчанию
DEFAULT_CURRENCIES = ["USD", "EUR", "RUB", "GBP", "CNY", "KZT", "TRY"]

# Флаги для валют
CURRENCY_FLAGS = {
    "USD": "🇺🇸",
    "EUR": "🇪🇺",
    "RUB": "🇷🇺",
    "GBP": "🇬🇧",
    "CNY": "🇨🇳",
    "KZT": "🇰🇿",
    "TRY": "🇹🇷",
    "JPY": "🇯🇵",
    "CHF": "🇨🇭",
    "AUD": "🇦🇺",
    "CAD": "🇨🇦",
    "KRW": "🇰🇷",
    "INR": "🇮🇳",
    "AED": "🇦🇪",
    "SAR": "🇸🇦",
    "UZS": "🇺🇿",
}

# Названия валют на русском
CURRENCY_NAMES_RU = {
    "USD": "Доллар США",
    "EUR": "Евро",
    "RUB": "Российский рубль",
    "GBP": "Фунт стерлингов",
    "CNY": "Китайский юань",
    "KZT": "Казахстанский тенге",
    "TRY": "Турецкая лира",
    "JPY": "Японская иена",
    "CHF": "Швейцарский франк",
    "AUD": "Австралийский доллар",
    "CAD": "Канадский доллар",
    "KRW": "Южнокорейская вона",
    "INR": "Индийская рупия",
    "AED": "Дирхам ОАЭ",
    "SAR": "Саудовский риал",
    "UZS": "Узбекский сум",
}


async def get_exchange_rates(
    currencies: Optional[list[str]] = None,
) -> dict[str, dict]:
    """
    Получает курсы валют от ЦБ Узбекистана.

    Args:
        currencies: Список кодов валют (например, ["USD", "EUR"]).
                    Если None, используются валюты по умолчанию.

    Returns:
        Словарь с курсами валют в формате:
        {
            "USD": {"rate": 12650.00, "date": "2026-06-17", "name": "Доллар США"},
            ...
        }

    Raises:
        ConnectionError: При проблемах с подключением к API.
        ValueError: При некорректном ответе от API.
    """
    target_currencies = currencies or DEFAULT_CURRENCIES
    target_currencies = [c.upper() for c in target_currencies]
    result: dict[str, dict] = {}
    today = date.today().isoformat()

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            for currency in target_currencies:
                try:
                    url = f"{CBU_BASE_URL}{currency}/{today}/"
                    async with session.get(url) as response:
                        if response.status != 200:
                            logger.warning(
                                "Ошибка получения курса %s: HTTP %s",
                                currency,
                                response.status,
                            )
                            continue

                        data = await response.json()

                        if not data or not isinstance(data, list):
                            logger.warning(
                                "Пустой ответ для валюты %s", currency
                            )
                            continue

                        rate_data = data[0]
                        rate = float(rate_data.get("Rate", 0))
                        rate_date = rate_data.get("Date", today)

                        if rate > 0:
                            result[currency] = {
                                "rate": rate,
                                "date": rate_date,
                                "name": CURRENCY_NAMES_RU.get(
                                    currency, currency
                                ),
                            }
                            logger.debug(
                                "Курс %s: %s", currency, rate
                            )

                except aiohttp.ClientError as e:
                    logger.warning(
                        "Ошибка запроса для %s: %s", currency, e
                    )
                    continue
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(
                        "Ошибка парсинга данных для %s: %s", currency, e
                    )
                    continue

        if not result:
            raise ValueError("Не удалось получить ни один курс валют")

        logger.info(
            "Получены курсы для %d валют: %s",
            len(result),
            ", ".join(result.keys()),
        )
        return result

    except aiohttp.ClientError as e:
        logger.error("Ошибка подключения к API ЦБУ: %s", e)
        raise ConnectionError(
            f"Не удалось подключиться к API ЦБУ: {e}"
        ) from e


async def format_rates_message(rates: dict[str, dict]) -> str:
    """
    Форматирует курсы валют в красивое сообщение для Telegram.

    Args:
        rates: Словарь с курсами валют от get_exchange_rates().

    Returns:
        Отформатированное сообщение с курсами валют.
    """
    if not rates:
        return "❌ Не удалось получить курсы валют."

    # Определяем дату из первой валюты
    first_rate = next(iter(rates.values()))
    rate_date = first_rate.get("date", "")

    lines = [
        "📊 <b>Курсы валют ЦБ Узбекистана</b>",
        f"📅 <i>{rate_date}</i>",
        "",
        "<code>┌──────────────────────────────┐</code>",
    ]

    # Сортируем валюты: сначала основные (USD, EUR), потом остальные
    priority_order = {"USD": 0, "EUR": 1, "RUB": 2, "GBP": 3}
    sorted_currencies = sorted(
        rates.keys(),
        key=lambda c: (priority_order.get(c, 99), c),
    )

    for i, currency in enumerate(sorted_currencies):
        data = rates[currency]
        flag = CURRENCY_FLAGS.get(currency, "🏳️")
        name = data.get("name", currency)
        rate = data["rate"]

        # Форматируем число
        if rate >= 100:
            rate_str = f"{rate:,.0f}"
        else:
            rate_str = f"{rate:,.2f}"

        # Разделитель между строками
        prefix = "<code>├</code>" if i < len(sorted_currencies) - 1 else "<code>└</code>"

        line = (
            f"{prefix} {flag} <b>{currency}</b> "
            f"<code>{rate_str:>12}</code> <i>сум</i>"
        )
        lines.append(line)

    lines.extend([
        "",
        "<i>Источник: cbu.uz</i>",
        "<i>1 единица иностранной валюты в узбекских сумах</i>",
    ])

    return "\n".join(lines)
