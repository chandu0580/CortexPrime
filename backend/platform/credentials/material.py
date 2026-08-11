"""Credential material: the secret, and everything that stops it escaping.

The one object in CortexPrime that holds a secret
---------------------------------------------------
Everything else carries a ``CredentialRef``. This carries the actual token, key,
or assertion, and it exists for exactly as long as one invocation takes.

Leakage is not prevented by care
----------------------------------
A rule saying "do not log credentials" is obeyed until the day somebody adds a
debug line, formats an object into an error message, or serialises a request for
a bug report. So this type is built so that each of those does the safe thing on
its own:

``__repr__`` / ``__str__``   render ``<CredentialMaterial …redacted>``
``__format__``               the same, so f-strings cannot expand it
``__getstate__``             **raises** — blocks ``pickle``, ``copy``,
                             ``deepcopy``, and every serialiser built on them
``to_dict``                  **raises** — the codebase's universal "write this
                             down" method, and the one an audit path would reach
                             for by habit
``__eq__`` / ``__hash__``    disabled — a secret must not become a dict key or be
                             compared in a way that leaks timing

The secret comes out through one method, ``reveal()``, which is deliberately
ugly, deliberately greppable, and takes a stated purpose. `grep -rn "\\.reveal("`
is the whole audit of who touches secret material in this codebase.

Not a dataclass
-----------------
Deliberately. ``@dataclass`` generates a ``__repr__`` that prints every field,
and the one time somebody removes ``repr=False`` by accident is the one time the
token reaches a log aggregator.
"""

from __future__ import annotations

import hmac
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from backend.contracts.credential import CredentialRef, CredentialType
from backend.contracts.errors import ContractViolation

__all__ = ["CredentialMaterial", "REDACTED"]

REDACTED = "***redacted***"


class CredentialMaterial:
    """A secret, held for one invocation. Unserialisable by construction."""

    __slots__ = ("_secret", "_ref", "_type", "_expires_at", "_acquired_at", "_headers")

    def __init__(
        self,
        *,
        secret: str,
        ref: CredentialRef,
        credential_type: CredentialType,
        expires_at: datetime,
        acquired_at: Optional[datetime] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        if not isinstance(secret, str) or not secret:
            raise ContractViolation(
                "credential material must carry a secret; an empty one would be "
                "handed to a transport and fail as an authentication error rather "
                "than as the wiring mistake it is"
            )
        if not isinstance(ref, CredentialRef):
            raise ContractViolation("ref must be a CredentialRef")
        if not isinstance(credential_type, CredentialType):
            raise ContractViolation("credential_type must be a CredentialType")
        if expires_at.tzinfo is None:
            raise ContractViolation("expires_at must be timezone-aware")

        self._secret = secret
        self._ref = ref
        self._type = credential_type
        self._expires_at = expires_at
        self._acquired_at = acquired_at or datetime.now(timezone.utc)
        # Header *names* only. The values live in ``_secret`` and are assembled
        # at the transport boundary, so a header map cannot become a second
        # place a token sits in memory.
        self._headers = tuple(sorted(headers or ()))

    # ------------------------------------------------------------------
    # Safe metadata -- everything here is fine to log
    # ------------------------------------------------------------------

    @property
    def ref(self) -> CredentialRef:
        return self._ref

    @property
    def credential_type(self) -> CredentialType:
        return self._type

    @property
    def expires_at(self) -> datetime:
        return self._expires_at

    @property
    def acquired_at(self) -> datetime:
        return self._acquired_at

    @property
    def header_names(self) -> tuple:
        return self._headers

    def is_live_at(self, moment: datetime) -> bool:
        return moment < self._expires_at

    def remaining_seconds(self, now: datetime) -> int:
        """Whole seconds left, floored. Never rounded up past the expiry."""
        return max(0, int((self._expires_at - now).total_seconds()))

    def fingerprint(self) -> str:
        """A stable, non-reversible identifier for *this* secret value.

        For answering "is the credential the transport used the one we issued"
        without ever comparing secrets in the open. Truncated so it cannot be
        brute-forced back into the value, and salted with the reference so the
        same secret under two references does not fingerprint alike.
        """
        import hashlib

        digest = hashlib.sha256(
            f"cortexprime/credential-fingerprint/{self._ref.value}".encode("utf-8")
            + b"\x00"
            + self._secret.encode("utf-8")
        ).hexdigest()
        return digest[:16]

    def matches(self, other_secret: str) -> bool:
        """Constant-time comparison. Never ``==``, which leaks by timing."""
        return hmac.compare_digest(self._secret, other_secret)

    # ------------------------------------------------------------------
    # The one way out
    # ------------------------------------------------------------------

    def reveal(self, *, purpose: str) -> str:
        """Return the secret. **Every call site is a security decision.**

        Named to be greppable rather than convenient: ``grep -rn "\\.reveal("``
        enumerates every place in this codebase that touches secret material,
        and that list is short enough to read.

        ``purpose`` is required and must be non-blank. It is not logged here —
        logging at the point of reveal would put a line next to the secret in
        every trace — but it forces the caller to have a stated reason, and it
        makes an accidental reveal impossible to write by autocomplete.
        """
        if not isinstance(purpose, str) or not purpose.strip():
            raise ContractViolation(
                "revealing credential material requires a stated purpose; a "
                "reveal nobody had to justify is one nobody will notice"
            )
        return self._secret

    # ------------------------------------------------------------------
    # Everything that would otherwise leak
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"<CredentialMaterial ref={self._ref.value} "
            f"type={self._type.value} secret={REDACTED}>"
        )

    __str__ = __repr__

    def __format__(self, spec: str) -> str:
        # f"{material}" and "{}".format(material) both land here. Without this
        # they would fall through to __str__ -- which is safe -- but an explicit
        # override means a future __str__ change cannot silently unredact.
        return self.__repr__()

    def __getstate__(self) -> Any:
        raise ContractViolation(
            "credential material cannot be serialised. This blocks pickle, copy, "
            "deepcopy and every serialiser built on them -- a secret that can be "
            "copied into a record is a secret that will be. Persist the "
            "CredentialRef instead"
        )

    def __setstate__(self, state: Any) -> None:  # pragma: no cover - unreachable
        raise ContractViolation("credential material cannot be deserialised")

    def __reduce__(self) -> Any:
        raise ContractViolation("credential material cannot be pickled")

    def to_dict(self) -> dict:
        raise ContractViolation(
            "credential material has no dictionary form. Every other object in "
            "this codebase has to_dict and audit paths reach for it by habit; "
            "this one raises so that habit fails loudly instead of quietly"
        )

    def __eq__(self, other: object) -> bool:
        raise ContractViolation(
            "credential material is not comparable; use matches() for a "
            "constant-time check. Ordinary equality leaks the secret by timing"
        )

    # Unhashable on purpose: a secret must never become a dict key or a set
    # member, both of which are places things get enumerated and printed.
    __hash__ = None  # type: ignore[assignment]
