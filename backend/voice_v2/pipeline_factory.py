"""
Pipecat pipeline factory for CortexPrime Voice V2.

Pipeline:
    LiveKitTransport (audio in)
        → DeepgramSTTService  (speech → text)
        → CortexLLMProcessor  (multi-turn context → mission → response text)
        → OpenAITTSService    (text → speech, using Azure OpenAI endpoint)
    LiveKitTransport (audio out)

Barge-in: UserStartedSpeakingFrame suppresses concurrent mission dispatch.
Multi-turn: CortexLLMProcessor receives the VoiceSession and builds
            conversation context from the last N turns before each mission call.
"""

import logging
import os
from typing import Optional
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport

from backend.voice_v2.cortex_llm_processor import CortexLLMProcessor
from backend.voice_v2.livekit_manager import generate_agent_token, LIVEKIT_URL
from backend.voice_v2.voice_session import VoiceSession

log = logging.getLogger(__name__)

# ── Env ───────────────────────────────────────────────────────────────────────
DEEPGRAM_API_KEY      = os.getenv("DEEPGRAM_API_KEY", "")
AZURE_OPENAI_KEY      = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
MODEL_TTS             = os.getenv("MODEL_TTS", "gpt-4o-mini-tts")

# Standard voice that works well with conversational AI
_TTS_VOICE = "alloy"


def build_pipeline(
    room_name:     str,
    session_id:    str,
    voice_session: VoiceSession,
    workspace_id:  Optional[str] = None,
) -> tuple[PipelineRunner, PipelineTask]:
    """
    Build and return a (runner, task) for the CortexPrime voice pipeline.

    voice_session is the live VoiceSession object — the LLM processor reads
    its transcript_log to build multi-turn conversation context.

    Call runner.run(task) from an asyncio task to start it.
    """
    if not LIVEKIT_URL:
        raise RuntimeError("LIVEKIT_URL not configured in .env")
    if not DEEPGRAM_API_KEY:
        raise RuntimeError("DEEPGRAM_API_KEY not configured in .env")
    if not AZURE_OPENAI_KEY:
        raise RuntimeError("AZURE_OPENAI_API_KEY not configured in .env")

    agent_token = generate_agent_token(room_name)

    # ── Transport ─────────────────────────────────────────────────────────────
    transport = LiveKitTransport(
        url       = LIVEKIT_URL,
        token     = agent_token,
        room_name = room_name,
        params    = LiveKitParams(
            audio_in_enabled       = True,
            audio_in_sample_rate   = 16000,
            audio_out_enabled      = True,
            audio_out_sample_rate  = 24000,
        ),
    )

    # ── STT ───────────────────────────────────────────────────────────────────
    from pipecat.services.deepgram.stt import DeepgramSTTService
    stt = DeepgramSTTService(
        api_key     = DEEPGRAM_API_KEY,
        encoding    = "linear16",
        sample_rate = 16000,
        channels    = 1,
    )

    # ── LLM — multi-turn aware ─────────────────────────────────────────────────
    llm = CortexLLMProcessor(
        session_id    = session_id,
        voice_session = voice_session,
        workspace_id  = workspace_id,
    )

    # ── TTS ───────────────────────────────────────────────────────────────────
    # OpenAITTSService supports base_url override → works with Azure OpenAI
    from pipecat.services.openai.tts import OpenAITTSService
    tts = OpenAITTSService(
        api_key      = AZURE_OPENAI_KEY,
        base_url     = f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/",
        voice        = _TTS_VOICE,
        model        = MODEL_TTS,
        sample_rate  = 24000,
    )

    # ── Pipeline ──────────────────────────────────────────────────────────────
    pipeline = Pipeline([
        transport.input(),
        stt,
        llm,
        tts,
        transport.output(),
    ])

    task   = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))
    runner = PipelineRunner()

    log.info(
        "✅ Voice pipeline built | room=%s | session=%s | prior_turns=%d",
        room_name, session_id[:8], len(voice_session.transcript_log),
    )
    return runner, task
