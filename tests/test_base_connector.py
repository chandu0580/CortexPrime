from __future__ import annotations

import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.connectors.base_connector import (
    BaseConnector,
    CircuitBreaker,
    PaginatedResponse,
    TokenManager,
)


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker()
        assert cb.state == "closed"

    def test_successful_call_resets_failures(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.call(lambda: "ok")
        assert cb.state == "closed"
        assert cb._failures == 0

    def test_failure_tracks_count(self):
        cb = CircuitBreaker(failure_threshold=3)
        with pytest.raises(RuntimeError):
            cb.call(lambda: exec('raise RuntimeError("fail")'))
        assert cb._failures == 1
        assert cb.state == "closed"

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=2)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(lambda: exec('raise RuntimeError("fail")'))
        assert cb._state == "open"

    def test_open_state_raises_immediately(self):
        cb = CircuitBreaker(failure_threshold=1)
        with pytest.raises(RuntimeError):
            cb.call(lambda: exec('raise RuntimeError("fail")'))
        assert cb._state == "open"
        with pytest.raises(RuntimeError, match="Circuit breaker is OPEN"):
            cb.call(lambda: "should not run")

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        with pytest.raises(RuntimeError):
            cb.call(lambda: exec('raise RuntimeError("fail")'))
        assert cb._state == "open"
        time.sleep(0.02)
        assert cb.state == "half_open"

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        with pytest.raises(RuntimeError):
            cb.call(lambda: exec('raise RuntimeError("fail")'))
        time.sleep(0.02)
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb._state == "closed"
        assert cb._failures == 0

    def test_custom_threshold_and_timeout(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
        assert cb._failure_threshold == 5
        assert cb._recovery_timeout == 60.0


class TestTokenManager:
    def test_initial_state_expired(self):
        tm = TokenManager("cid", "secret", "https://token.url")
        assert tm.is_expired is True
        assert tm.valid_token is None

    def test_set_tokens(self):
        tm = TokenManager("cid", "secret", "https://token.url")
        tm.set_tokens("access123", "refresh123", expires_in=3600)
        assert tm._access_token == "access123"
        assert tm._refresh_token == "refresh123"
        assert tm._expires_at > time.time()

    def test_valid_token_when_not_expired(self):
        tm = TokenManager("cid", "secret", "https://token.url")
        tm.set_tokens("my_token", expires_in=3600)
        assert tm.valid_token == "my_token"

    @patch("backend.connectors.base_connector.httpx")
    def test_refresh_on_expired(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {
            "access_token": "new_token",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
        }
        mock_httpx.post.return_value = mock_resp

        tm = TokenManager("cid", "secret", "https://token.url")
        tm.set_tokens("old_token", "old_refresh", expires_in=-1)
        assert tm.is_expired is True
        token = tm.valid_token
        assert token == "new_token"
        mock_httpx.post.assert_called_once()

    @patch("backend.connectors.base_connector.httpx")
    def test_refresh_failure_returns_stale_token(self, mock_httpx):
        mock_httpx.post.side_effect = Exception("Network error")

        tm = TokenManager("cid", "secret", "https://token.url")
        tm.set_tokens("old_token", "old_refresh", expires_in=-1)
        assert tm.is_expired is True
        assert tm.valid_token == "old_token"

    def test_refresh_without_refresh_token_returns_stale(self):
        tm = TokenManager("cid", "secret", "https://token.url")
        tm.set_tokens("token", expires_in=-1)
        assert tm.is_expired is True
        assert tm.valid_token == "token"

    def test_scopes_stored(self):
        tm = TokenManager("cid", "secret", "https://token.url", scopes=["read", "write"])
        assert tm._scopes == ["read", "write"]

    def test_default_scopes_empty(self):
        tm = TokenManager("cid", "secret", "https://token.url")
        assert tm._scopes == []


class TestPaginatedResponse:
    def test_create_paginated_response(self):
        pr = PaginatedResponse(items=[1, 2, 3], next_page_token="abc", has_more=True, total=10)
        assert pr.items == [1, 2, 3]
        assert pr.next_page_token == "abc"
        assert pr.has_more is True
        assert pr.total == 10

    def test_paginated_response_no_more(self):
        pr = PaginatedResponse(items=[], next_page_token=None, has_more=False)
        assert pr.items == []
        assert pr.has_more is False
        assert pr.next_page_token is None
        assert pr.total is None

    def test_paginated_response_empty(self):
        pr = PaginatedResponse(items=[])
        assert pr.items == []
        assert pr.next_page_token is None
        assert pr.has_more is False
        assert pr.total is None


class MockConcrete(BaseConnector):
    async def health_check(self) -> bool:
        return True


class TestBaseConnector:
    @pytest.mark.asyncio
    async def test_set_auth_creates_token_manager(self):
        conn = MockConcrete("test", "https://api.example.com")
        conn.set_auth("cid", "secret", "https://auth.example.com/token")
        assert conn._token_manager is not None
        assert conn._token_manager._client_id == "cid"

    @pytest.mark.asyncio
    async def test_get_headers_without_auth(self):
        conn = MockConcrete("test", "https://api.example.com")
        headers = await conn._get_headers()
        assert headers == {"Accept": "application/json"}

    @pytest.mark.asyncio
    async def test_get_headers_with_auth(self):
        conn = MockConcrete("test", "https://api.example.com")
        conn.set_auth("cid", "secret", "https://auth.example.com/token")
        conn._token_manager.set_tokens("test_token", expires_in=3600)
        headers = await conn._get_headers()
        assert headers["Authorization"] == "Bearer test_token"

    @pytest.mark.asyncio
    async def test_close(self):
        conn = MockConcrete("test", "https://api.example.com")
        mock_client = AsyncMock()
        conn._client = mock_client
        await conn.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        mock_client = AsyncMock()
        async with MockConcrete("test", "https://api.example.com") as conn:
            conn._client = mock_client
        mock_client.aclose.assert_called_once()

    def test_base_url_strips_trailing_slash(self):
        conn = MockConcrete("test", "https://api.example.com/")
        assert conn.base_url == "https://api.example.com"
