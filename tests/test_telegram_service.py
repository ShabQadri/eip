"""
Tests for TelegramService.
"""

import pytest
import asyncio
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.telegram_service import TelegramService

class MockResponse:
    def __init__(self, status, json_data=None, text_data=""):
        self.status = status
        self._json_data = json_data or {}
        self._text_data = text_data

    async def json(self):
        return self._json_data

    async def text(self):
        return self._text_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

def test_telegram_service_success() -> None:
    """Test 1: Successful send returns success dict with message_id."""
    service = TelegramService(bot_token="fake-token", channel_id="fake-channel")
    resp = MockResponse(status=200, json_data={"ok": True, "result": {"message_id": 99999}})

    with patch("aiohttp.ClientSession.post", return_value=resp) as mock_post:
        result = service.send_message("Hello World")
        assert result["success"] is True
        assert result["message_id"] == 99999
        assert result["error"] is None

        # Verify payload and url
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.telegram.org/botfake-token/sendMessage"
        assert kwargs["json"]["chat_id"] == "fake-channel"
        assert kwargs["json"]["text"] == "Hello World"
        assert kwargs["json"]["parse_mode"] == "MarkdownV2"

def test_telegram_service_http_failure() -> None:
    """Test 2: HTTP failure (500) retries 3 times and returns failure dict."""
    service = TelegramService(bot_token="fake-token", channel_id="fake-channel")
    resp = MockResponse(status=500, text_data="Internal Server Error")

    with patch("aiohttp.ClientSession.post", return_value=resp) as mock_post, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = service.send_message("Hello World")
        assert result["success"] is False
        assert result["message_id"] is None
        assert "HTTP 500" in result["error"]

        # 3 attempts
        assert mock_post.call_count == 3
        # 2 sleeps (1s, 2s)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)

def test_telegram_service_timeout() -> None:
    """Test 3: Timeout error on all attempts retries and returns failure dict."""
    service = TelegramService(bot_token="fake-token", channel_id="fake-channel")

    with patch("aiohttp.ClientSession.post", side_effect=asyncio.TimeoutError) as mock_post, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = service.send_message("Hello World")
        assert result["success"] is False
        assert result["message_id"] is None
        assert "Timeout error" in result["error"]

        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2

def test_telegram_service_retry_and_succeed() -> None:
    """Test 4: Failing twice then succeeding on 3rd attempt returns success."""
    service = TelegramService(bot_token="fake-token", channel_id="fake-channel")
    
    resp_fail = MockResponse(status=502, text_data="Bad Gateway")
    resp_ok = MockResponse(status=200, json_data={"ok": True, "result": {"message_id": 777}})

    # Sequence of returns/side-effects
    with patch("aiohttp.ClientSession.post", side_effect=[resp_fail, resp_fail, resp_ok]) as mock_post, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = service.send_message("Hello World")
        assert result["success"] is True
        assert result["message_id"] == 777
        assert result["error"] is None

        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2

def test_telegram_service_digest_send() -> None:
    """Test 5: send_digest correctly forwards call to send_message."""
    service = TelegramService(bot_token="fake-token", channel_id="fake-channel")
    resp = MockResponse(status=200, json_data={"ok": True, "result": {"message_id": 111}})

    with patch("aiohttp.ClientSession.post", return_value=resp) as mock_post:
        result = service.send_digest("Digest content")
        assert result["success"] is True
        assert result["message_id"] == 111
        mock_post.assert_called_once()
        assert mock_post.call_args[1]["json"]["text"] == "Digest content"

def test_telegram_service_breaking_alert_send() -> None:
    """Test 6: send_breaking_alert correctly forwards call to send_message."""
    service = TelegramService(bot_token="fake-token", channel_id="fake-channel")
    resp = MockResponse(status=200, json_data={"ok": True, "result": {"message_id": 222}})

    with patch("aiohttp.ClientSession.post", return_value=resp) as mock_post:
        result = service.send_breaking_alert("Breaking Alert!")
        assert result["success"] is True
        assert result["message_id"] == 222
        mock_post.assert_called_once()
        assert mock_post.call_args[1]["json"]["text"] == "Breaking Alert!"

def test_telegram_service_markdown_v2_payload_verification() -> None:
    """Test 7: Verify parse_mode is set to MarkdownV2 in JSON payload."""
    service = TelegramService(bot_token="t", channel_id="c")
    resp = MockResponse(status=200, json_data={"ok": True, "result": {"message_id": 1}})

    with patch("aiohttp.ClientSession.post", return_value=resp) as mock_post:
        service.send_message("Text")
        mock_post.assert_called_once()
        kwargs = mock_post.call_args[1]
        assert kwargs["json"]["parse_mode"] == "MarkdownV2"
