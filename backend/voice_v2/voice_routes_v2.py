"""
Voice V2 API Routes for CortexPrime.
prefix: /api/voice/v2

Endpoints:
    POST   /api/voice/v2/token                        — generate LiveKit token for browser
    POST   /api/voice/v2/session                      — create voice session + start pipeline
    DELETE /api/voice/v2/session/{id}                 — end session + stop pipeline
    POST   /api/voice/v2/session/{id}/reconnect       — recover session after disconnect
    GET    /api/voice/v2/session/{id}/history         — transcript history (recovery restore)
    GET    /api/voice/v2/sessions                     — list active sessions
    GET    /api/voice/v2/health                       — service health check

The Pipecat pipeline runs in a background asyncio Task per session.
On reconnect the existing VoiceSession (including transcript history) is
reactivated and a new pipeline task is started against the same room.
"""

import asyncio
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.dependencies import require_user
from backend.voice_v2.livekit_manager import (
    generate_user_token,
    LIVEKIT_URL,
    is_livekit_configured,
)
from backend.voice_v2.voice_session import VoiceSession, voice_session_store

log    = logging.getLogger(__name__)
router = APIRouter(prefix="/api/voice/v2", tags=["Voice V2"])

# Apply to every protected route individually so /health stays open.
_SECURE = [Depends(require_user)]

# Active pipeline tasks: session_id → asyncio.Task
_pipeline_tasks: dict[str, asyncio.Task] = {}


# ── Audit helper ─────────────────────────────────────────────────────────────

def _audit_voice(event_type: str, session_id: str, message: str) -> None:
    """
    Fire-and-forget audit log entry for voice lifecycle events.

    Accepted event_type values:
        voice_session_started
        voice_disconnect
        voice_reconnect
        voice_reconnect_failed
        voice_recovered
    """
    try:
        from backend.safety.audit_logger import audit_logger
        audit_logger.log(
            execution_id = session_id,
            agent        = "voice_v2",
            action       = event_type,
            risk_level   = "low",
            outcome      = "info",
            reason       = message,
            session_id   = session_id,
        )
    except Exception:
        pass  # Never block voice path on audit failure


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    room_name:    Optional[str] = None
    identity:     Optional[str] = None
    display_name: Optional[str] = None


class TokenResponse(BaseModel):
    token:        str
    room_name:    str
    livekit_url:  str
    identity:     str


class SessionRequest(BaseModel):
    identity:     str
    room_name:    Optional[str] = None
    workspace_id: Optional[str] = None
    display_name: Optional[str] = None


class SessionResponse(BaseModel):
    session_id:  str
    room_name:   str
    token:       str
    livekit_url: str
    identity:    str


class ReconnectResponse(BaseModel):
    session_id:     str
    room_name:      str
    token:          str
    livekit_url:    str
    identity:       str
    turn_count:     int
    reconnect_count: int


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health")
async def voice_v2_health():
    """Check LiveKit configuration status."""
    configured = is_livekit_configured()
    return {
        "status":     "ok" if configured else "degraded",
        "livekit":    configured,
        "livekit_url": LIVEKIT_URL or "(not set)",
        "sessions":   len(voice_session_store.list_active()),
        "version":    "v2",
    }


@router.post("/token", response_model=TokenResponse, dependencies=_SECURE)
async def generate_token(req: TokenRequest):
    """
    Generate a LiveKit JWT for a browser participant.
    Use this to pre-join a room before starting a session.
    """
    if not is_livekit_configured():
        raise HTTPException(
            status_code=503,
            detail="LiveKit is not configured. Set LIVEKIT_URL, LIVEKIT_API_KEY, "
                   "LIVEKIT_API_SECRET in backend/.env",
        )

    room_name = req.room_name or f"cortex-{uuid.uuid4().hex[:8]}"
    identity  = req.identity  or f"user-{uuid.uuid4().hex[:6]}"

    try:
        token = generate_user_token(
            room_name    = room_name,
            identity     = identity,
            display_name = req.display_name or identity,
        )
    except Exception as exc:
        log.error("Token generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return TokenResponse(
        token       = token,
        room_name   = room_name,
        livekit_url = LIVEKIT_URL,
        identity    = identity,
    )


@router.post("/session", response_model=SessionResponse, dependencies=_SECURE)
async def start_session(req: SessionRequest):
    """
    Create a voice session and start the Pipecat pipeline in background.
    Returns the LiveKit token the browser needs to join the same room.

    On reconnect: pass the existing session_id as req.room_name to restore
    transcript history from Redis (the pipeline will pick up prior turns).
    """
    if not is_livekit_configured():
        raise HTTPException(
            status_code=503,
            detail="LiveKit is not configured.",
        )

    room_name = req.room_name or f"cortex-{uuid.uuid4().hex[:8]}"

    # Create session record
    session = voice_session_store.create(
        room_name     = room_name,
        user_identity = req.identity,
        workspace_id  = req.workspace_id,
    )

    # Generate user token
    try:
        user_token = generate_user_token(
            room_name    = room_name,
            identity     = req.identity,
            display_name = req.display_name or req.identity,
        )
    except Exception as exc:
        voice_session_store.remove(session.session_id)
        raise HTTPException(status_code=500, detail=f"Token generation failed: {exc}")

    # Start pipeline in background (non-blocking)
    try:
        task = asyncio.create_task(
            _run_pipeline_background(
                room_name    = room_name,
                session_id   = session.session_id,
                voice_session = session,
                workspace_id = req.workspace_id,
            ),
            name=f"voice-pipeline-{session.session_id[:8]}",
        )
        _pipeline_tasks[session.session_id] = task
        log.info("🎙️ Voice session started | id=%s | room=%s", session.session_id[:8], room_name)
        _audit_voice("voice_session_started", session.session_id,
                     f"Session started | room={room_name} | identity={req.identity}")
    except Exception as exc:
        voice_session_store.remove(session.session_id)
        raise HTTPException(status_code=500, detail=f"Pipeline startup failed: {exc}")

    return SessionResponse(
        session_id  = session.session_id,
        room_name   = room_name,
        token       = user_token,
        livekit_url = LIVEKIT_URL,
        identity    = req.identity,
    )


@router.delete("/session/{session_id}", dependencies=_SECURE)
async def end_session(session_id: str):
    """Stop a voice session and cancel its pipeline."""
    session = voice_session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    voice_session_store.close(session_id)

    task = _pipeline_tasks.pop(session_id, None)
    if task and not task.done():
        task.cancel()
        log.info("🔇 Voice session ended | id=%s", session_id[:8])

    _audit_voice("voice_disconnect", session_id, "Session ended by client")
    return {"status": "closed", "session_id": session_id}


@router.post("/session/{session_id}/reconnect",
             response_model=ReconnectResponse, dependencies=_SECURE)
async def reconnect_session(session_id: str):
    """
    Reconnect a disconnected voice session.

    Restores the session from Redis if it has fallen out of the in-memory
    store, generates a fresh LiveKit token for the same room, cancels any
    stale pipeline task, and starts a new pipeline that picks up the existing
    transcript history so the conversation continues seamlessly.

    Returns the same shape as POST /session so the frontend can use the same
    connection logic.
    """
    if not is_livekit_configured():
        raise HTTPException(status_code=503, detail="LiveKit is not configured.")

    # Try memory first, then Redis
    session = await voice_session_store.get_or_restore(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found or expired. Start a new session.",
        )

    # Mark reconnect in session telemetry (non-fatal)
    await voice_session_store.record_reconnect(session_id)

    # Reactivate session
    session.is_active = True
    session.touch()

    # Cancel stale pipeline if still running
    stale_task = _pipeline_tasks.pop(session_id, None)
    if stale_task and not stale_task.done():
        stale_task.cancel()
        log.info("Voice stale pipeline cancelled before reconnect | id=%s", session_id[:8])

    # Fresh LiveKit token for the existing room
    try:
        new_token = generate_user_token(
            room_name    = session.room_name,
            identity     = session.user_identity,
            display_name = session.user_identity,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {exc}")

    # Restart pipeline (picks up transcript_log for multi-turn context)
    try:
        task = asyncio.create_task(
            _run_pipeline_background(
                room_name     = session.room_name,
                session_id    = session_id,
                voice_session = session,
                workspace_id  = session.workspace_id,
            ),
            name=f"voice-reconnect-{session_id[:8]}",
        )
        _pipeline_tasks[session_id] = task
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline restart failed: {exc}")

    log.info(
        "🔄 Voice session reconnected | id=%s | room=%s | turns=%d | reconnects=%d",
        session_id[:8], session.room_name, session.turn_count, session.reconnect_count,
    )
    _audit_voice("voice_reconnect", session_id,
                 f"Session reconnected | turns={session.turn_count} "
                 f"reconnects={session.reconnect_count}")

    return ReconnectResponse(
        session_id      = session_id,
        room_name       = session.room_name,
        token           = new_token,
        livekit_url     = LIVEKIT_URL,
        identity        = session.user_identity,
        turn_count      = session.turn_count,
        reconnect_count = session.reconnect_count,
    )


@router.get("/sessions", dependencies=_SECURE)
async def list_sessions():
    """List all active voice sessions."""
    voice_session_store.prune_stale(max_idle_secs=1800)
    return {
        "sessions": voice_session_store.list_active(),
        "pipeline_count": len(_pipeline_tasks),
    }


@router.get("/session/{session_id}/history", dependencies=_SECURE)
async def get_session_history(session_id: str):
    """
    Return the transcript history for a session.

    Used by the frontend on reconnect to restore conversation context.
    Falls back to Redis when the session is no longer in memory.
    """
    history = await voice_session_store.get_history(session_id)
    session = await voice_session_store.get_or_restore(session_id)
    return {
        "session_id":          session_id,
        "turn_count":          session.turn_count          if session else len(history),
        "memory_recall_count": session.memory_recall_count if session else 0,
        "history":             history,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Internal: background pipeline runner
# ─────────────────────────────────────────────────────────────────────────────

async def _run_pipeline_background(
    room_name:     str,
    session_id:    str,
    voice_session: "VoiceSession",
    workspace_id:  Optional[str],
) -> None:
    """Run pipecat pipeline until session ends or an error occurs."""
    try:
        from backend.voice_v2.pipeline_factory import build_pipeline
        runner, task = build_pipeline(
            room_name     = room_name,
            session_id    = session_id,
            voice_session = voice_session,
            workspace_id  = workspace_id,
        )
        await runner.run(task)
    except asyncio.CancelledError:
        log.info("Voice pipeline cancelled | session=%s", session_id[:8])
    except Exception as exc:
        log.error("Voice pipeline crashed | session=%s | %s", session_id[:8], exc)
        _audit_voice("voice_reconnect_failed", session_id,
                     f"Pipeline crashed: {str(exc)[:120]}")
    finally:
        voice_session_store.close(session_id)
        _pipeline_tasks.pop(session_id, None)
