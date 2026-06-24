"""Tests for the parsers module.

Uses pytest-asyncio for async test support and monkey-patches
aiohttp responses to avoid real HTTP calls.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest

from parsers.rss_parser import fetch_all_sources, fetch_rss, _parse_feed
from parsers.news_filter import (
    KEYWORDS,
    filter_news,
    is_duplicate,
    categorize,
    mark_as_published,
    CATEGORY_PRIORITY,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_rss_xml() -> str:
    """Minimal valid RSS 2.0 XML with two items."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Federal Reserve Raises Interest Rates</title>
      <link>https://example.com/news/1</link>
      <description>The Fed announced a 0.25% rate hike today.</description>
      <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
      <enclosure url="https://example.com/img1.jpg" type="image/jpeg" length="0"/>
    </item>
    <item>
      <title>Local Sports Team Wins Game</title>
      <link>https://example.com/news/2</link>
      <description>A great victory for the local team.</description>
      <pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def _make_mock_response(text: str, raise_on_enter: bool = False):
    """Helper to build a mock aiohttp response that works as an async context manager."""
    mock_response = MagicMock()
    mock_response.text = AsyncMock(return_value=text)
    mock_response.raise_for_status = MagicMock()

    async_mock_response = AsyncMock()
    async_mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    async_mock_response.__aexit__ = AsyncMock(return_value=None)

    if raise_on_enter:
        async_mock_response.__aenter__ = AsyncMock(side_effect=Exception("HTTP 500"))

    return async_mock_response, mock_response


def _make_mock_session(sample_rss_xml: str, raise_on_enter: bool = False):
    """Helper to build a mock aiohttp ClientSession."""
    async_mock_response, mock_response = _make_mock_response(sample_rss_xml, raise_on_enter)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=async_mock_response)

    async_mock_session = AsyncMock()
    async_mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    async_mock_session.__aexit__ = AsyncMock(return_value=None)

    return async_mock_session, mock_session, mock_response


# ---------------------------------------------------------------------------
# rss_parser tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_rss_success(sample_rss_xml):
    """fetch_rss should parse entries from a valid RSS response."""
    async_mock_session, mock_session, mock_response = _make_mock_session(sample_rss_xml)

    with patch("parsers.rss_parser.aiohttp.ClientSession", return_value=async_mock_session):
        result = await fetch_rss("https://example.com/rss", "TestSource")

    assert isinstance(result, list)
    assert len(result) == 2

    first = result[0]
    assert first["title"] == "Federal Reserve Raises Interest Rates"
    assert first["link"] == "https://example.com/news/1"
    assert "Fed" in first["summary"]
    assert first["source"] == "TestSource"
    assert first["image_url"] == "https://example.com/img1.jpg"


@pytest.mark.asyncio
async def test_fetch_rss_timeout():
    """fetch_rss should return an empty list on network timeout."""
    mock_response = MagicMock()
    mock_response.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)

    async_mock_session = AsyncMock()
    async_mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    async_mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("parsers.rss_parser.aiohttp.ClientSession", return_value=async_mock_session):
        result = await fetch_rss("https://slow.example.com/rss", "SlowSource")
    assert result == []


@pytest.mark.asyncio
async def test_fetch_rss_http_error():
    """fetch_rss should return an empty list on HTTP error."""
    mock_response = MagicMock()
    mock_response.__aenter__ = AsyncMock(side_effect=Exception("HTTP 500"))
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)

    async_mock_session = AsyncMock()
    async_mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    async_mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("parsers.rss_parser.aiohttp.ClientSession", return_value=async_mock_session):
        result = await fetch_rss("https://error.example.com/rss", "ErrorSource")
    assert result == []


def test_parse_feed_empty():
    """_parse_feed should handle empty or malformed XML gracefully."""
    result = _parse_feed("", "EmptySource")
    assert result == []

    result = _parse_feed("<not>valid xml without rss", "BadSource")
    assert result == []


# ---------------------------------------------------------------------------
# news_filter tests
# ---------------------------------------------------------------------------


class TestCategorize:
    """Tests for the categorize() function."""

    def test_categorize_finance(self):
        news = {"title": "Banking sector sees record profits", "summary": ""}
        assert categorize(news) == "finance"

    def test_categorize_economy(self):
        news = {"title": "GDP growth slows in Q4", "summary": "Inflation remains high."}
        assert categorize(news) == "economy"

    def test_categorize_trading(self):
        news = {"title": "Bitcoin hits new all-time high", "summary": "Crypto markets rally."}
        assert categorize(news) == "trading"

    def test_categorize_breaking(self):
        news = {"title": "Breaking: Central bank announces emergency measures", "summary": ""}
        assert categorize(news) == "breaking"

    def test_categorize_none(self):
        news = {"title": "Local sports team wins game", "summary": "A great victory."}
        assert categorize(news) is None

    def test_categorize_multi_keyword_highest_score_wins(self):
        """When multiple categories match, the one with more keyword hits wins."""
        # "crypto" = trading (1), "market" = trading (1), "bank" = finance (1)
        # trading score = 2, finance score = 1  => trading should win
        news = {
            "title": "Crypto market update: bank partnerships growing",
            "summary": "",
        }
        result = categorize(news)
        assert result == "trading"


class TestFilterNews:
    """Tests for the filter_news() function."""

    def test_filter_excludes_non_matching(self):
        """Items without matching keywords should be excluded."""
        items = [
            {"title": "Random sports news", "link": "https://example.com/sports", "summary": ""},
            {"title": "Bank profits rise", "link": "https://example.com/finance", "summary": ""},
        ]
        result = filter_news(items)
        assert len(result) == 1
        assert result[0]["link"] == "https://example.com/finance"
        assert result[0]["category"] == "finance"

    def test_filter_sorts_by_priority(self):
        """Results should be sorted: breaking > trading > finance > economy."""
        items = [
            {"title": "Economy growing slowly", "link": "https://example.com/e1", "summary": ""},
            {"title": "Stock market bullish", "link": "https://example.com/t1", "summary": ""},
            {"title": "Bank earnings up", "link": "https://example.com/f1", "summary": ""},
            {"title": "Breaking: war declared", "link": "https://example.com/b1", "summary": ""},
        ]
        result = filter_news(items)
        categories = [item["category"] for item in result]
        assert categories == ["breaking", "trading", "finance", "economy"]


class TestIsDuplicate:
    """Tests for the is_duplicate() function."""

    @patch("parsers.news_filter.SessionLocal")
    def test_is_duplicate_true(self, mock_session_local):
        """Should return True when link exists in DB."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = MagicMock()
        mock_session_local.return_value = mock_session

        assert is_duplicate("https://example.com/exists") is True
        mock_session.close.assert_called_once()

    @patch("parsers.news_filter.SessionLocal")
    def test_is_duplicate_false(self, mock_session_local):
        """Should return False when link does not exist in DB."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        mock_session_local.return_value = mock_session

        assert is_duplicate("https://example.com/new") is False
        mock_session.close.assert_called_once()


class TestMarkAsPublished:
    """Tests for the mark_as_published() function."""

    @patch("parsers.news_filter.SessionLocal")
    def test_mark_as_published(self, mock_session_local):
        """Should persist a news item to the DB."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        news = {
            "link": "https://example.com/new",
            "title": "New News",
            "category": "finance",
            "source": "Test",
        }
        mark_as_published(news)

        mock_session.merge.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# Integration-style test for fetch_all_sources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_all_sources_aggregates(sample_rss_xml):
    """fetch_all_sources should aggregate results from all 8 sources."""
    async_mock_session, mock_session, mock_response = _make_mock_session(sample_rss_xml)

    with patch("parsers.rss_parser.aiohttp.ClientSession", return_value=async_mock_session):
        result = await fetch_all_sources()

    # 8 sources x 2 items each = 16 items
    assert isinstance(result, list)
    assert len(result) == 16
    assert all(
        item["source"] in [
            "CNN", "BBC", "NYT", "Reuters",
            "Al Jazeera", "Kun.uz", "Qalampir.uz", "Uznews.uz",
        ]
        for item in result
    )
