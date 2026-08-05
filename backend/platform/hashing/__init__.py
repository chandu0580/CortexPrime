"""Canonical serialization and content hashing.

The single source of truth for deterministic hashing across CortexPrime. Every
bounded context uses these functions; none may implement its own.

    from backend.platform.hashing import compute_digest, verify_digest

    digest = compute_digest(contract.to_dict())      # -> PayloadDigest
    ok = verify_digest(contract.to_dict(), digest)   # -> bool

Why one implementation
----------------------
A survey of the repository found 152 files performing ad-hoc hashing or
identifier generation. Where two call sites hash "the same" structure by
different routes, their digests diverge and any integrity check between them
silently fails open. Constitution I2 depends on exactly this not happening.

See ``docs/adr/ADR-011-canonical-hashing.md``.
"""

from __future__ import annotations

from backend.platform.hashing.canonical import (
    CANONICAL_VERSION,
    CanonicalizationError,
    canonical_bytes,
    canonical_text,
)
from backend.platform.hashing.digest import (
    DEFAULT_ALGORITHM,
    DIGEST_DOMAIN_PREFIX,
    compute_digest,
    digest_hex,
    digests_match,
    verify_digest,
)

__all__ = [
    "CANONICAL_VERSION",
    "CanonicalizationError",
    "canonical_bytes",
    "canonical_text",
    "DEFAULT_ALGORITHM",
    "DIGEST_DOMAIN_PREFIX",
    "compute_digest",
    "digest_hex",
    "digests_match",
    "verify_digest",
]
