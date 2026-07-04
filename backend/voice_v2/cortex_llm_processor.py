"""
CortexPrime LLM Processor for Pipecat Voice Pipeline.

Receives TranscriptionFrame, injects multi-turn conversation history from
VoiceSession, calls mission_runtime with full voice context, and emits
TextFrame responses.

Multi-turn memory flow:
  1. TranscriptionFrame arrives (speech recognised)
  2. User turn appended to VoiceSession.transcript_log
  3. last_n_turns(CONTEXT_TURNS) formatted as voice_context string
  4. mission_runtime.execute_mission(voice_context=...) called
  5. Response appended as assistant turn
  6. Session persisted to Redis (recovery-safe)
  7. Telemetry events emitted
"""

import asyncio
import logging
import time
from typing import Optional

from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    TextFrame,
    EndFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

from backend.voice_v2.voice_session import VoiceSession, voice_session_store, CONTEXT_TURNS

log = logging.getLogger(__name__)

# Minimum spoken text length to trigger mission execution
_MIN_TRANSCRIPT_CHARS = 3
# Filler phrases that should not trigger a full mission
_FILLER_PHRASES = {"um", "uh", "hmm", "hm", "okay", "ok", "yeah", "yes", "no"}


class CortexLLMProcessor(FrameProcessor):
    """
    Pipecat frame processor that bridges voice transcriptions to the
    CortexPrime mission runtime with full multi-turn memory.

    Flow:
        TranscriptionFrame
          → append user turn to VoiceSession
          → build voice_context from last N turns
          → execute_mission(voice_context=...)
          → append assistant response to VoiceSession
          → persist session to Redis
          → TextFrame (response text for TTS)
    """

    def __init__(
        self,
        session_id:    str,
        voice_session: VoiceSession,
        workspace_id:  Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._session_id    = session_id
        self._voice_session = voice_session
        self._workspace_id  = workspace_id
        # Barge-in guard: suppress mission dispatch while agent is speaking
        self._is_speaking   = False

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, UserStartedSpeakingFrame):
            self._is_speaking = True
            await self.push_frame(frame, direction)

        elif isinstance(frame, UserStoppedSpeakingFrame):
            self._is_speaking = False
            await self.push_frame(frame, direction)

        elif isinstance(frame, TranscriptionFrame):
            # Only process when agent is not mid-speech (barge-in guard)
            if not self._is_speaking:
                await self._handle_transcript(frame)
            else:
                log.debug("Barge-in: suppressing transcript dispatch while agent speaking")

        elif isinstance(frame, EndFrame):
            await self.push_frame(frame, direction)

        else:
            await self.push_frame(frame, direction)

    async def _handle_transcript(self, frame: TranscriptionFrame) -> None:
        text = (frame.text or "").strip()

        # Skip empty / too-short / filler utterances
        if len(text) < _MIN_TRANSCRIPT_CHARS:
            return
        if text.lower() in _FILLER_PHRASES:
            return

        turn_start = time.monotonic()
        log.info("🎤 Voice transcript [%s]: %s", self._session_id[:8], text[:80])

        # ── 1. Store user turn ────────────────────────────────────────────
        self._voice_session.append_turn("user", text)

        # ── 2. Build multi-turn voice context ────────────────────────────
        voice_context = self._voice_session.last_n_turns(CONTEXT_TURNS)

        # ── 3. Emit voice_transcript telemetry ────────────────────────────
        await self._emit_event(
            event_type = "voice_transcript",
            agent      = "voice_stt",
            status     = "running",
            message    = f"Heard: {text[:80]}",
            payload    = {
                "transcript":  text,
                "turn_count":  self._voice_session.turn_count,
                "has_history": bool(voice_context),
            },
        )

        # ── 4. Execute mission with voice context ─────────────────────────
        response_text = ""
        confidence    = 0.0
        try:
            from backend.services.mission_runtime import mission_runtime
            result = await mission_runtime.execute_mission(
                objective     = text,
                session_id    = self._session_id,
                workspace_id  = self._workspace_id,
                voice_context = voice_context or None,
            )
            response_text = (
                result.get("response") or result.get("message") or ""
            )
            confidence = result.get("confidence_score", 0.0)
            if not response_text:
                response_text = (
                    "I've processed your request. "
                    "Check the mission stream for details."
                )

            elapsed = time.monotonic() - turn_start
            log.info(
                "🤖 Voice response [%s]: %d chars in %.1fs",
                self._session_id[:8], len(response_text), elapsed,
            )

        except Exception as exc:
            log.error("Voice mission execution failed: %s", exc)
            response_text = "I encountered an issue processing that. Please try again."
            elapsed       = time.monotonic() - turn_start

        # ── 5. Store assistant turn ───────────────────────────────────────
        self._voice_session.append_turn("assistant", response_text)

        # ── 6. Persist to Redis (non-fatal, fire-and-forget) ──────────────
        asyncio.ensure_future(
            voice_session_store.persist(self._voice_session)
        )

        # ── 7. Emit voice_response telemetry ──────────────────────────────
        # Also track memory recalls (memory_context_service calls per mission)
        self._voice_session.memory_recall_count += 1
        await self._emit_event(
            event_type = "voice_response",
            agent      = "voice_llm",
            status     = "completed",
            message    = response_text[:200],
            payload    = {
                "transcript":          text,
                "response":            response_text[:500],
                "confidence":          confidence,
                "turn_count":          self._voice_session.turn_count,
                "memory_recall_count": self._voice_session.memory_recall_count,
                "context_turns":       len(self._voice_session.transcript_log),
                "latency_ms":          round((time.monotonic() - turn_start) * 1000),
            },
        )

        # ── 8. Push text response downstream to TTS ───────────────────────
        await self.push_frame(TextFrame(text=response_text))

    # ── Helpers ───────────────────────────────────────────────────────────

    async def _emit_event(
        self,
        event_type: str,
        agent:      str,
        status:     str,
        message:    str,
        payload:    dict,
    ) -> None:
        """Fire-and-forget CognitionEvent onto the event bus."""
        try:
            from backend.events.event_bus import event_bus
            from backend.events.event_models import CognitionEvent
            await event_bus.emit(CognitionEvent(
                event_type = event_type,
                agent      = agent,
                status     = status,
                message    = message,
                session_id = self._session_id,
                payload    = payload,
            ))
        except Exception:
            pass
