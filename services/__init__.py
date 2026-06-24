"""
Services package for Znews Telegram Bot.

Provides functions for:
- Adding watermarks to images (watermark)
- Fetching exchange rates from Central Bank of Uzbekistan (cbu_api)
- Generating motivational quotes and images (motivator)
- Analyzing news importance for trading (analyzer)
- Formatting and sending posts to Telegram (poster)

Example::

    from services import add_watermark, get_exchange_rates, analyze_importance
"""

__version__ = "1.0.0"

from services.watermark import add_watermark, add_watermark_to_bytes
from services.cbu_api import get_exchange_rates, format_rates_message
from services.motivator import (
    get_daily_motivation,
    generate_motivation_image,
    MOTIVATIONAL_QUOTES,
)
from services.analyzer import analyze_importance, translate_to_russian
from services.poster import (
    format_news_post,
    send_to_channel,
    post_news,
)

__all__ = [
    # watermark
    "add_watermark",
    "add_watermark_to_bytes",
    # cbu_api
    "get_exchange_rates",
    "format_rates_message",
    # motivator
    "get_daily_motivation",
    "generate_motivation_image",
    "MOTIVATIONAL_QUOTES",
    # analyzer
    "analyze_importance",
    "translate_to_russian",
    # poster
    "format_news_post",
    "send_to_channel",
    "post_news",
]
