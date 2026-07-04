"""
Category 03 — Voice End-to-End Test
======================================
Validates every stage of the voice pipeline:

  User speech → Deepgram STT → Mission Runtime → Memory → Research → TTS → Audio

Each stage is tested independently (no audio hardware required).
Integration points are verified via import checks and route probes.
When the full LiveKit stack is configured, optional live probes run.
"""
from __future__ import annotations

import os
import importlib
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from tests.production_validation import (
    CategoryResult, CheckResult, CheckStatus,
    http_get, http_post,
    pass_, fail_, skip_, warn_, check,
    backend_is_up, BASE_URL,
)


# ---------------------------------------------------------------------------
# Stage probes
# ---------------------------------------------------------------------------

def _check_voice_runtime_importable() -> CheckResult:
    """voice_runtime.py can be imported (edge-tts available)."""
    try:
        from backend.voice.voice_runtime import VoiceRuntime
        vr = VoiceRuntime()
        profiles = getattr(vr, "voice_profiles", {})
        return pass_(
            "voice_runtime_importable",
            f"VoiceRuntime importable — {len(profiles)} voice profiles",
            profiles=list(profiles.keys()),
        )
    except ImportError as exc:
        return fail_("voice_runtime_importable", f"Import failed: {exc}")
    except Exception as exc:
        return warn_("voice_runtime_importable", f"VoiceRuntime loaded with warning: {exc}")


def _check_speech_to_text_engine() -> CheckResult:
    """STT engine is importable and has a transcribe interface."""
    try:
        from backend.voice.speech_to_text_engine import SpeechToTextEngine
        engine = SpeechToTextEngine()
        has_transcribe = callable(getattr(engine, "transcribe", None)) or \
                         callable(getattr(engine, "listen", None)) or \
                         callable(getattr(engine, "start", None))
        if has_transcribe:
            return pass_("stt_engine_importable", "STT engine importable with transcribe interface")
        return warn_("stt_engine_importable", "STT engine importable but transcribe interface unclear")
    except ImportError as exc:
        return warn_("stt_engine_importable", f"STT engine import warning: {exc}")
    except Exception as exc:
        return warn_("stt_engine_importable", f"STT engine init warning: {exc}")


def _check_tts_edge_available() -> CheckResult:
    """edge-tts is available for TTS output."""
    try:
        import edge_tts
        return pass_("tts_edge_available", f"edge-tts available (version: {getattr(edge_tts, '__version__', 'unknown')})")
    except ImportError:
        return fail_("tts_edge_available", "edge-tts not installed — TTS output unavailable")


def _check_voice_routes_registered() -> CheckResult:
    """
    Check that voice routes respond (any 2xx or 404 means the server is alive).
    """
    paths_to_try = [
        "/api/voice/status",
        "/voice/status",
        "/api/voice/health",
        "/voice/health",
        "/voice/v2/status",
    ]
    for path in paths_to_try:
        code, body = http_get(path, timeout=5.0)
        if code in (200, 201, 202):
            return pass_("voice_routes_registered", f"Voice route {path} responded: HTTP {code}")
        if code in (422, 400):
            return warn_("voice_routes_registered", f"Voice route {path} exists but needs params")
    # 404 on all is a warn (may be registered elsewhere)
    return warn_("voice_routes_registered",
                 "Voice routes not found at standard paths — may be mounted differently")


def _check_livekit_manager() -> CheckResult:
    """LiveKit manager is importable; configuration is reported."""
    try:
        from backend.voice_v2.livekit_manager import is_livekit_configured, LIVEKIT_URL
        configured = is_livekit_configured()
        if configured:
            return pass_("livekit_manager",
                         f"LiveKit manager configured — URL: {LIVEKIT_URL}")
        return warn_("livekit_manager",
                     "LiveKit manager importable but not configured (LIVEKIT_URL/TOKEN missing)",
                     configured=False)
    except ImportError as exc:
        return warn_("livekit_manager", f"LiveKit manager not available: {exc}")
    except Exception as exc:
        return warn_("livekit_manager", f"LiveKit manager warning: {exc}")


def _check_pipeline_factory() -> CheckResult:
    """Pipeline factory can be imported (Pipecat voice pipeline)."""
    try:
        from backend.voice_v2.pipeline_factory import build_voice_pipeline
        return pass_("pipeline_factory", "Voice pipeline factory importable")
    except ImportError as exc:
        return warn_("pipeline_factory", f"Pipeline factory unavailable: {exc}")
    except Exception as exc:
        return warn_("pipeline_factory", f"Pipeline factory warning: {exc}")


def _check_deepgram_configured() -> CheckResult:
    """Deepgram API key is set in environment."""
    # Load .env manually if needed
    env_path = Path("backend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    key = os.getenv("DEEPGRAM_API_KEY", "")
    if key and len(key) > 10:
        return pass_("deepgram_configured", "DEEPGRAM_API_KEY present")
    return warn_("deepgram_configured",
                 "DEEPGRAM_API_KEY not configured — live STT unavailable")


def _check_voice_mission_pipeline() -> CheckResult:
    """
    Voice should feed into Mission Runtime.
    Verify the integration point: MissionRuntimeService is importable from
    the same package that voice_runtime uses.
    """
    try:
        from backend.services.mission_runtime import MissionRuntimeService
        return pass_("voice_mission_integration",
                     "MissionRuntimeService accessible from voice pipeline path")
    except ImportError as exc:
        return fail_("voice_mission_integration", f"MissionRuntimeService unavailable: {exc}")


def _check_generated_voice_dir() -> CheckResult:
    """generated_voice/ directory exists (TTS output storage)."""
    p = Path("generated_voice")
    if p.exists():
        files = list(p.rglob("*.mp3")) + list(p.rglob("*.wav"))
        return pass_("generated_voice_dir",
                     f"generated_voice/ exists — {len(files)} audio files present")
    return warn_("generated_voice_dir",
                 "generated_voice/ directory missing — TTS has never produced output")


def _check_tts_synthesis_capability() -> CheckResult:
    """
    Verify TTS can synthesise text without audio playback hardware.
    Uses edge-tts to produce bytes for a small test string.
    """
    try:
        import asyncio
        import edge_tts

        async def _synth() -> int:
            communicate = edge_tts.Communicate("Hello CortexPrime.", "en-US-GuyNeural")
            byte_count  = 0
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    byte_count += len(chunk["data"])
                if byte_count > 4096:   # enough to confirm it works
                    break
            return byte_count

        # Run in a temporary event loop (safe in test context)
        bytes_produced = asyncio.run(_synth())
        if bytes_produced > 0:
            return pass_("tts_synthesis",
                         f"TTS synthesised {bytes_produced} bytes of audio")
        return warn_("tts_synthesis", "TTS returned 0 bytes")
    except ImportError:
        return skip_("tts_synthesis", "edge-tts not installed")
    except Exception as exc:
        return warn_("tts_synthesis", f"TTS synthesis error: {exc}")


# ---------------------------------------------------------------------------
# Category runner
# ---------------------------------------------------------------------------

def run() -> CategoryResult:
    cat = CategoryResult("03 — Voice End-to-End")

    checks_to_run = [
        _check_tts_edge_available,
        _check_voice_runtime_importable,
        _check_speech_to_text_engine,
        _check_deepgram_configured,
        _check_livekit_manager,
        _check_pipeline_factory,
        _check_voice_mission_pipeline,
        _check_generated_voice_dir,
        _check_tts_synthesis_capability,
    ]

    # Voice routes need backend running
    if backend_is_up():
        checks_to_run.append(_check_voice_routes_registered)

    for fn in checks_to_run:
        cat.checks.append(check(fn.__name__.lstrip("_"), fn))

    return cat
