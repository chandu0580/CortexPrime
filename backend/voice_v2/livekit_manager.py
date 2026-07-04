"""
LiveKit room and token management for CortexPrime Voice V2.
"""

import calendar
import datetime
import logging
import os
from typing import Optional

import jwt

log = logging.getLogger(__name__)

# ── Env ───────────────────────────────────────────────────────────────────────
LIVEKIT_URL        = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY    = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
LIVEKIT_NBF_SKEW_SECONDS = int(os.getenv("LIVEKIT_NBF_SKEW_SECONDS", "300"))

_livekit_available = bool(LIVEKIT_URL and LIVEKIT_API_KEY and LIVEKIT_API_SECRET)


def is_livekit_configured() -> bool:
    return _livekit_available


def _encode_token(token, ttl: datetime.timedelta) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    jwt_claims = token.claims.asdict()
    jwt_claims.update(
        {
            "sub": token.identity,
            "iss": token.api_key,
            "nbf": calendar.timegm(
                (now - datetime.timedelta(seconds=LIVEKIT_NBF_SKEW_SECONDS)).utctimetuple()
            ),
            "exp": calendar.timegm((now + ttl).utctimetuple()),
        }
    )
    return jwt.encode(jwt_claims, token.api_secret, algorithm="HS256")


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

    ttl = datetime.timedelta(minutes=ttl_minutes)
    token = (
        AccessToken(api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(display_name or identity)
        .with_ttl(ttl)
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
    return _encode_token(token, ttl)


def generate_agent_token(room_name: str, agent_identity: str = "cortex-agent") -> str:
    """Generate a LiveKit JWT for the Pipecat agent participant."""
    if not _livekit_available:
        raise RuntimeError("LiveKit not configured.")
    from livekit.api import AccessToken, VideoGrants

    ttl = datetime.timedelta(hours=2)
    token = (
        AccessToken(api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
        .with_identity(agent_identity)
        .with_name("CortexPrime AI")
        .with_ttl(ttl)
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
    return _encode_token(token, ttl)
