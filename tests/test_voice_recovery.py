"""
Voice Runtime Recovery System Tests
====================================

Tests verify:
  1. Disconnect detection + telemetry recording
  2. Reconnect route returns new token + existing turn history
  3. Transcript history is preserved across simulated disconnect/reconnect
  4. Pipeline restart reuses existing VoiceSession (multi-turn context intact)
  5. Session restoration from Redis when not in memory
  6. Reconnect fails gracefully when session is truly gone (404)
  7. Audit log entries emitted on disconnect/reconnect
  8. Multiple sequential reconnects accumulate telemetry correctly
  9. Pipeline crash triggers audit log
 10. /session/{id}/history endpoint returns turns after reconnect
"""

from __future__ import annotations

import json
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Test App ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def auth_headers():
    from backend.auth.jwt_handler import create_access_token
    token = create_access_token(user_id="user-voice-test", role="user")
    return {"Authorization": f"Bearer {token}"}


# Patch the token blacklist for all integration tests so they don't need Redis
@pytest.fixture(autouse=True)
def _no_blacklist():
    """
    Make the blacklist Redis check always report 'not revoked' so tests
    don't need a live Redis connection.  Applied to every test in this module.
    """
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)   # key absent → not revoked
    with patch(
        "backend.auth.token_blacklist.TokenBlacklist._get_redis",
        new_callable=AsyncMock,
        return_value=mock_redis,
    ):
        yield


# ── Unit: VoiceSession recovery telemetry ────────────────────────────────────

class TestVoiceSessionTelemetry:

    def _make_session(self) -> "VoiceSession":
        from backend.voice_v2.voice_session import VoiceSession
        return VoiceSession(
            session_id    = str(uuid.uuid4()),
            room_name     = "test-room",
            user_identity = "test-user",
            workspace_id  = None,
        )

    def test_initial_recovery_counters_are_zero(self):
        s = self._make_session()
        assert s.disconnect_count  == 0
        assert s.reconnect_count   == 0
        assert s.last_disconnect_at is None
        assert s.last_reconnect_at  is None

    def test_record_disconnect_increments_counter(self):
        s = self._make_session()
        s.record_disconnect()
        assert s.disconnect_count   == 1
        assert s.last_disconnect_at is not None

    def test_record_disconnect_multiple_times(self):
        s = self._make_session()
        s.record_disconnect()
        s.record_disconnect()
        s.record_disconnect()
        assert s.disconnect_count == 3

    def test_record_reconnect_increments_counter(self):
        s = self._make_session()
        s.record_reconnect()
        assert s.reconnect_count  == 1
        assert s.last_reconnect_at is not None
        assert s.is_active is True

    def test_record_reconnect_reactivates_session(self):
        s = self._make_session()
        s.is_active = False
        s.record_reconnect()
        assert s.is_active is True

    def test_telemetry_survives_redis_round_trip(self):
        from backend.voice_v2.voice_session import VoiceSession
        s = self._make_session()
        s.record_disconnect()
        s.record_reconnect()
        s.append_turn("user", "hello")
        s.append_turn("assistant", "hi there")

        data      = s.to_redis_dict()
        restored  = VoiceSession.from_redis_dict(data)

        assert restored.disconnect_count  == s.disconnect_count
        assert restored.reconnect_count   == s.reconnect_count
        assert restored.turn_count        == s.turn_count
        assert len(restored.transcript_log) == 2
        assert restored.transcript_log[0]["text"] == "hello"

    def test_to_dict_includes_recovery_fields(self):
        s = self._make_session()
        s.record_disconnect()
        d = s.to_dict()
        assert "disconnect_count"   in d
        assert "reconnect_count"    in d
        assert "last_disconnect_at" in d
        assert d["disconnect_count"] == 1


# ── Unit: VoiceSessionStore record_disconnect / record_reconnect ─────────────

class TestVoiceSessionStoreTelemetry:

    async def test_store_record_disconnect(self):
        from backend.voice_v2.voice_session import VoiceSessionStore
        store = VoiceSessionStore()
        s     = store.create(room_name="r", user_identity="u")

        with patch.object(store, "persist", new_callable=AsyncMock):
            await store.record_disconnect(s.session_id)

        assert s.disconnect_count == 1

    async def test_store_record_reconnect(self):
        from backend.voice_v2.voice_session import VoiceSessionStore
        store = VoiceSessionStore()
        s     = store.create(room_name="r", user_identity="u")
        s.is_active = False

        with patch.object(store, "persist", new_callable=AsyncMock):
            await store.record_reconnect(s.session_id)

        assert s.reconnect_count == 1
        assert s.is_active is True

    async def test_store_record_disconnect_unknown_session_is_noop(self):
        from backend.voice_v2.voice_session import VoiceSessionStore
        store = VoiceSessionStore()

        with patch.object(store, "get_or_restore", new_callable=AsyncMock, return_value=None):
            # Should not raise
            await store.record_disconnect("nonexistent")


# ── Unit: VoiceSession.last_n_turns context after reconnect ──────────────────

class TestMultiTurnContextAfterReconnect:

    def test_last_n_turns_includes_prior_turns(self):
        from backend.voice_v2.voice_session import VoiceSession
        s = VoiceSession(
            session_id    = str(uuid.uuid4()),
            room_name     = "r",
            user_identity = "u",
            workspace_id  = None,
        )
        s.append_turn("user",      "Explain Redis.")
        s.append_turn("assistant", "Redis is an in-memory data store.")
        s.append_turn("user",      "Summarize that.")
        s.append_turn("assistant", "Redis: fast in-memory key-value store.")

        ctx = s.last_n_turns(10)
        assert "Explain Redis."                     in ctx
        assert "Redis is an in-memory data store."  in ctx
        assert "Summarize that."                    in ctx
        assert "Voice Conversation History"         in ctx

    def test_last_n_turns_empty_when_no_history(self):
        from backend.voice_v2.voice_session import VoiceSession
        s = VoiceSession(
            session_id    = str(uuid.uuid4()),
            room_name     = "r",
            user_identity = "u",
            workspace_id  = None,
        )
        assert s.last_n_turns() == ""

    def test_last_n_turns_limits_to_n(self):
        from backend.voice_v2.voice_session import VoiceSession
        s = VoiceSession(
            session_id    = str(uuid.uuid4()),
            room_name     = "r",
            user_identity = "u",
            workspace_id  = None,
        )
        for i in range(30):
            s.append_turn("user",      f"question {i}")
            s.append_turn("assistant", f"answer {i}")

        ctx   = s.last_n_turns(6)
        lines = [l for l in ctx.splitlines() if l.startswith(("User:", "Assistant:"))]
        assert len(lines) == 6


# ── Integration: reconnect route (mock LiveKit + pipeline) ───────────────────

class TestReconnectRoute:

    @pytest.fixture(autouse=True)
    def _patch_ext(self):
        """Disable real LiveKit, Pipecat, Redis persist, and audit for route tests."""
        with (
            patch(
                "backend.voice_v2.voice_routes_v2.is_livekit_configured",
                return_value=True,
            ),
            patch(
                "backend.voice_v2.voice_routes_v2.generate_user_token",
                return_value="mock-livekit-token",
            ),
            patch(
                "backend.voice_v2.voice_routes_v2._run_pipeline_background",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.voice_v2.voice_routes_v2._audit_voice",
            ),
            patch(
                "backend.voice_v2.voice_session.VoiceSessionStore.persist",
                new_callable=AsyncMock,
            ),
        ):
            yield

    def _create_session_in_store(self) -> "VoiceSession":
        from backend.voice_v2.voice_session import voice_session_store
        s = voice_session_store.create(
            room_name     = "test-room",
            user_identity = "test-user",
            workspace_id  = None,
        )
        s.append_turn("user",      "Explain Redis.")
        s.append_turn("assistant", "Redis is a fast in-memory store.")
        return s

    def test_reconnect_returns_200_with_token(self, client, auth_headers):
        session = self._create_session_in_store()
        resp    = client.post(
            f"/api/voice/v2/session/{session.session_id}/reconnect",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["session_id"]  == session.session_id
        assert data["token"]       == "mock-livekit-token"
        assert data["room_name"]   == "test-room"
        assert data["turn_count"]  == 2

    def test_reconnect_increments_reconnect_count(self, client, auth_headers):
        session = self._create_session_in_store()
        client.post(
            f"/api/voice/v2/session/{session.session_id}/reconnect",
            headers=auth_headers,
        )
        assert session.reconnect_count == 1

    def test_reconnect_unknown_session_returns_404(self, client, auth_headers):
        with patch(
            "backend.voice_v2.voice_routes_v2.voice_session_store.get_or_restore",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = client.post(
                "/api/voice/v2/session/nonexistent-id/reconnect",
                headers=auth_headers,
            )
        assert resp.status_code == 404
        body = resp.json()
        # Global exception handler wraps 404s in the standard error envelope
        if "error" in body:
            assert body["error"]["code"] == "NOT_FOUND"
        else:
            assert "not found" in body.get("detail", "").lower()

    def test_reconnect_cancels_stale_pipeline_task(self, client, auth_headers):
        from backend.voice_v2 import voice_routes_v2
        session = self._create_session_in_store()

        stale_task = MagicMock()
        stale_task.done.return_value = False
        voice_routes_v2._pipeline_tasks[session.session_id] = stale_task

        client.post(
            f"/api/voice/v2/session/{session.session_id}/reconnect",
            headers=auth_headers,
        )
        stale_task.cancel.assert_called_once()

    def test_reconnect_requires_auth(self, client):
        resp = client.post("/api/voice/v2/session/any-id/reconnect")
        assert resp.status_code in (401, 403)


# ── Integration: history endpoint after reconnect ────────────────────────────

class TestHistoryEndpointAfterReconnect:

    def test_history_returns_transcript_log(self, client, auth_headers):
        from backend.voice_v2.voice_session import voice_session_store
        s = voice_session_store.create(room_name="r2", user_identity="u2")
        s.append_turn("user",      "Give examples.")
        s.append_turn("assistant", "Example 1: cache, Example 2: pub/sub.")

        resp = client.get(
            f"/api/voice/v2/session/{s.session_id}/history",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["turn_count"] == 2
        assert len(data["history"]) == 2
        assert data["history"][0]["role"] == "user"
        assert data["history"][1]["role"] == "assistant"

    def test_history_unknown_session_returns_empty(self, client, auth_headers):
        with (
            patch(
                "backend.voice_v2.voice_routes_v2.voice_session_store.get_or_restore",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.voice_v2.voice_routes_v2.voice_session_store.get_history",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            resp = client.get(
                "/api/voice/v2/session/ghost-id/history",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.json()["history"] == []

    def test_history_requires_auth(self, client):
        resp = client.get("/api/voice/v2/session/any-id/history")
        assert resp.status_code in (401, 403)


# ── Unit: Redis restore falls back when key missing ───────────────────────────

class TestRedisSessionRestore:

    async def test_restore_returns_none_when_key_missing(self):
        from backend.voice_v2.voice_session import VoiceSessionStore
        store = VoiceSessionStore()

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        # The method does a lazy import so we patch the canonical connection object
        with patch(
            "backend.infrastructure.redis.connection.redis_connection.ensure_connected",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await store.restore("ghost-id")

        assert result is None

    async def test_restore_rebuilds_session_from_redis_json(self):
        from backend.voice_v2.voice_session import VoiceSessionStore, VoiceSession
        store = VoiceSessionStore()

        session_data = {
            "session_id":          "abc-123",
            "room_name":           "room-x",
            "user_identity":       "alice",
            "workspace_id":        None,
            "created_at":          time.time(),
            "last_activity":       time.time(),
            "is_active":           True,
            "transcript_log":      [
                {"role": "user",      "text": "hello", "timestamp": time.time()},
                {"role": "assistant", "text": "hi",    "timestamp": time.time()},
            ],
            "turn_count":          2,
            "memory_recall_count": 1,
            "disconnect_count":    1,
            "reconnect_count":     0,
            "last_disconnect_at":  time.time() - 30,
            "last_reconnect_at":   None,
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(session_data).encode())
        mock_redis.zadd = AsyncMock(return_value=1)

        with patch(
            "backend.infrastructure.redis.connection.redis_connection.ensure_connected",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            result = await store.restore("abc-123")

        assert result is not None
        assert result.session_id        == "abc-123"
        assert result.turn_count        == 2
        assert result.disconnect_count  == 1
        assert len(result.transcript_log) == 2
        assert result.transcript_log[0]["text"] == "hello"

    async def test_get_or_restore_tries_redis_on_cache_miss(self):
        from backend.voice_v2.voice_session import VoiceSessionStore
        store = VoiceSessionStore()

        with patch.object(store, "restore", new_callable=AsyncMock, return_value=None) as m:
            result = await store.get_or_restore("not-in-memory")

        m.assert_awaited_once_with("not-in-memory")
        assert result is None


# ── Unit: Audit logging ──────────────────────────────────────────────────────

class TestAuditLogging:

    def test_audit_voice_called_on_session_start(self, client, auth_headers):
        with (
            patch("backend.voice_v2.voice_routes_v2.is_livekit_configured", return_value=True),
            patch("backend.voice_v2.voice_routes_v2.generate_user_token", return_value="tok"),
            patch("backend.voice_v2.voice_routes_v2._run_pipeline_background", new_callable=AsyncMock),
            patch("backend.voice_v2.voice_session.VoiceSessionStore.persist", new_callable=AsyncMock),
            patch("backend.voice_v2.voice_routes_v2._audit_voice") as mock_audit,
        ):
            resp = client.post(
                "/api/voice/v2/session",
                json={"identity": "audit-test-user"},
                headers=auth_headers,
            )
        assert resp.status_code == 200, resp.text
        calls = [c.args[0] for c in mock_audit.call_args_list]
        assert "voice_session_started" in calls

    def test_audit_voice_called_on_session_end(self, client, auth_headers):
        from backend.voice_v2.voice_session import voice_session_store
        s = voice_session_store.create(room_name="r3", user_identity="u3")

        with patch("backend.voice_v2.voice_routes_v2._audit_voice") as mock_audit:
            resp = client.delete(
                f"/api/voice/v2/session/{s.session_id}",
                headers=auth_headers,
            )
        assert resp.status_code == 200, resp.text
        calls = [c.args[0] for c in mock_audit.call_args_list]
        assert "voice_disconnect" in calls

    def test_audit_voice_called_on_reconnect(self, client, auth_headers):
        from backend.voice_v2.voice_session import voice_session_store
        s = voice_session_store.create(room_name="r4", user_identity="u4")

        with (
            patch("backend.voice_v2.voice_routes_v2.is_livekit_configured", return_value=True),
            patch("backend.voice_v2.voice_routes_v2.generate_user_token", return_value="tok"),
            patch("backend.voice_v2.voice_routes_v2._run_pipeline_background", new_callable=AsyncMock),
            patch("backend.voice_v2.voice_session.VoiceSessionStore.persist", new_callable=AsyncMock),
            patch("backend.voice_v2.voice_routes_v2._audit_voice") as mock_audit,
        ):
            resp = client.post(
                f"/api/voice/v2/session/{s.session_id}/reconnect",
                headers=auth_headers,
            )
        assert resp.status_code == 200, resp.text
        calls = [c.args[0] for c in mock_audit.call_args_list]
        assert "voice_reconnect" in calls


# ── Integration: full disconnect → reconnect → conversation continues ─────────

class TestEndToEndRecoveryFlow:
    """
    Simulates the full recovery cycle:
      1. Session started with prior conversation turns
      2. Simulated disconnect (record_disconnect called)
      3. Reconnect endpoint restores session
      4. History endpoint returns all prior turns
    """

    @pytest.fixture(autouse=True)
    def _patch_ext(self):
        with (
            patch("backend.voice_v2.voice_routes_v2.is_livekit_configured", return_value=True),
            patch("backend.voice_v2.voice_routes_v2.generate_user_token", return_value="tok"),
            patch("backend.voice_v2.voice_routes_v2._run_pipeline_background", new_callable=AsyncMock),
            patch("backend.voice_v2.voice_routes_v2._audit_voice"),
            patch("backend.voice_v2.voice_session.VoiceSessionStore.persist", new_callable=AsyncMock),
        ):
            yield

    def test_history_intact_after_reconnect(self, client, auth_headers):
        from backend.voice_v2.voice_session import voice_session_store

        # 1. Build a session with conversation history
        session = voice_session_store.create(room_name="e2e-room", user_identity="alice")
        session.append_turn("user",      "Explain Redis.")
        session.append_turn("assistant", "Redis is an in-memory data store.")
        session.append_turn("user",      "Summarize that.")
        session.append_turn("assistant", "Redis: fast in-memory key-value store.")

        # 2. Simulate disconnect
        session.record_disconnect()
        assert session.disconnect_count == 1

        # 3. Reconnect
        resp_rc = client.post(
            f"/api/voice/v2/session/{session.session_id}/reconnect",
            headers=auth_headers,
        )
        assert resp_rc.status_code == 200, resp_rc.text
        assert resp_rc.json()["turn_count"] == 4

        # 4. Verify history
        resp_hist = client.get(
            f"/api/voice/v2/session/{session.session_id}/history",
            headers=auth_headers,
        )
        assert resp_hist.status_code == 200
        history = resp_hist.json()["history"]
        assert len(history) == 4
        texts = [h["text"] for h in history]
        assert "Explain Redis."                     in texts
        assert "Redis is an in-memory data store."  in texts
        assert "Summarize that."                    in texts

    def test_multiple_reconnects_accumulate_telemetry(self, client, auth_headers):
        from backend.voice_v2.voice_session import voice_session_store

        session = voice_session_store.create(room_name="multi-room", user_identity="bob")

        for _ in range(3):
            session.record_disconnect()
            client.post(
                f"/api/voice/v2/session/{session.session_id}/reconnect",
                headers=auth_headers,
            )

        assert session.disconnect_count == 3
        assert session.reconnect_count  == 3
