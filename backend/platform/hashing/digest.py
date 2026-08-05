"""Content digests over canonical bytes.

Delivers the computation that ``backend.contracts.approval.PayloadDigest``
describes. Contracts declare the shape of a digest; this module produces the
value. That split exists because contracts do no work -- see ADR-010.

Domain separation
-----------------
Every digest is computed over::

    b"cortexprime/digest/v<CANONICAL_VERSION>\\x00" + canonical_bytes(value)

The prefix is standard cryptographic hygiene and buys two concrete things:

1. A digest computed under canonicalization v1 differs from one computed under
   v2 for the same value. A ruleset change becomes a detectable mismatch rather
   than a silent, unverifiable difference.
2. A CortexPrime digest of some bytes can never equal a bare hash of the same
   bytes computed elsewhere, so digests from another system cannot be replayed
   into ours.

Purity and thread safety
------------------------
Every function here is a pure function of its arguments. There is no shared
mutable state, no cache, no clock, and no randomness, so all of it is safe to
call concurrently from any number of threads.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, Callable, Final, Mapping

from backend.contracts.approval import HashAlgorithm, PayloadDigest
from backend.platform.hashing.canonical import CANONICAL_VERSION, canonical_bytes

__all__ = [
    "DIGEST_DOMAIN_PREFIX",
    "DEFAULT_ALGORITHM",
    "compute_digest",
    "digest_hex",
    "digests_match",
    "verify_digest",
]

DEFAULT_ALGORITHM: Final[HashAlgorithm] = HashAlgorithm.SHA256
"""SHA-256 unless a caller states otherwise. Sufficient for integrity binding,
and cheap enough that the approval path adds no measurable latency."""

DIGEST_DOMAIN_PREFIX: Final[bytes] = f"cortexprime/digest/v{CANONICAL_VERSION}".encode("ascii")

_CONSTRUCTORS: Final[Mapping[HashAlgorithm, Callable[[bytes], "hashlib._Hash"]]] = {
    HashAlgorithm.SHA256: hashlib.sha256,
    HashAlgorithm.SHA512: hashlib.sha512,
}


def _domain_separated(payload: bytes) -> bytes:
    return DIGEST_DOMAIN_PREFIX + b"\x00" + payload


def digest_hex(value: Any, algorithm: HashAlgorithm = DEFAULT_ALGORITHM) -> str:
    """Return the lowercase hex digest of ``value``'s canonical form."""
    constructor = _CONSTRUCTORS.get(algorithm)
    if constructor is None:
        raise ValueError(f"unsupported hash algorithm: {algorithm!r}")
    return constructor(_domain_separated(canonical_bytes(value))).hexdigest()


def compute_digest(value: Any, algorithm: HashAlgorithm = DEFAULT_ALGORITHM) -> PayloadDigest:
    """Compute a :class:`PayloadDigest` over ``value``.

    ``value`` is normally the output of ``Contract.to_dict()``. Returning the
    contract type rather than a bare string means the algorithm always travels
    with the digest, so verification never has to guess.
    """
    return PayloadDigest(algorithm=algorithm, value=digest_hex(value, algorithm))


def digests_match(left: PayloadDigest, right: PayloadDigest) -> bool:
    """Constant-time comparison of two digests.

    Delegates to :meth:`PayloadDigest.matches`, which already compares in
    constant time. Exposed here so that call sites reaching for platform code
    are not tempted to write ``left.value == right.value``.
    """
    return left.matches(right)


def verify_digest(
    value: Any, expected: PayloadDigest, algorithm: HashAlgorithm | None = None
) -> bool:
    """Recompute the digest of ``value`` and compare it against ``expected``.

    This is the operation invariant I2 rests on: dispatch recomputes the digest
    of the stored artifact and refuses to proceed unless it matches what was
    approved.

    The algorithm defaults to ``expected.algorithm`` so a caller cannot
    accidentally verify a SHA-512 digest using SHA-256 and always get ``False``.
    A mismatch here must mean the *content* differs, never that the caller
    picked the wrong algorithm.
    """
    resolved = algorithm or expected.algorithm
    recomputed = compute_digest(value, resolved)
    return hmac.compare_digest(recomputed.value, expected.value) and (
        recomputed.algorithm is expected.algorithm
    )
