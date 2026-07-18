"""
LiveKit room and token management for CortexPrime Voice V2.
"""

import datetime
import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

# ── Env ───────────────────────────────────────────────────────────────────────
LIVEKIT_URL        = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY    = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

_livekit_available = bool(LIVEKIT_URL and LIVEKIT_API_KEY and LIVEKIT_API_SECRET)


def is_livekit_configured() -> bool:
    return _livekit_available


def generate_user_token(
    room_name:    str,
    identity:     str,
    display_name: Optional[str] = None,
    ttl_minutes:  int = 60,
) -> str:
    """Generate a LiveKit JWT for a browser participant."""
    if not _livekit_available:
        raise RuntimeError(
            "LiveKit not configured. Set LIVEKIT_URL, LIVEKIT_API_KEY, "
            "LIVEKIT_API_SECRET in .env"
        )
    from livekit.api import AccessToken, VideoGrants

    token = (
        AccessToken(api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(display_name or identity)
        .with_ttl(datetime.timedelta(minutes=ttl_minutes))
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
    )
    return token.to_jwt()


def generate_agent_token(room_name: str, agent_identity: str = "cortex-agent") -> str:
    """Generate a LiveKit JWT for the Pipecat agent participant."""
    if not _livekit_available:
        raise RuntimeError("LiveKit not configured.")
    from livekit.api import AccessToken, VideoGrants

    token = (
        AccessToken(api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
        .with_identity(agent_identity)
        .with_name("CortexPrime AI")
        .with_ttl(datetime.timedelta(hours=2))
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
                hidden=True,
            )
        )
    )
    return token.to_jwt()
