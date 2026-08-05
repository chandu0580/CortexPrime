"""Approval integrity: the approved artifact is the executed artifact.

Constitution I2 and P3. Published penetration testing has defeated
human-in-the-loop review in shipping products by making what a human *saw*
differ from what the system *executed*. Before this module, CortexPrime had the
same gap: ``pending_action_store`` wrote ``{"action_type", "payload"}`` to a
JSON file and the dispatcher executed whatever it read back. Anything able to
touch that file between approval-request and approval-grant achieved arbitrary
*approved* execution.

What is bound
-------------
The digest covers the canonical form of ``record_version``, ``workflow_id``,
``action_type`` and ``payload`` together. Each element closes a distinct attack:

``payload``
    The obvious one -- change a container name, a branch, a provider.
``action_type``
    Without it, an approved ``docker_health_fix`` payload could be re-labelled
    ``rollback`` and dispatched to a different, more destructive handler.
``workflow_id``
    Without it, a record approved under a low-risk workflow could be moved onto
    another workflow's approval. This is the cross-workflow replay.
``record_version``
    Without it, a v2 record could be re-labelled v1 to trigger the legacy path.

The digest itself is excluded, as is ``created_at`` -- a field inside its own
digest is unverifiable, and a timestamp is not part of what was authorized.

Fail closed, always
-------------------
Every path that cannot *prove* integrity refuses. A missing record, a missing
digest, an unparsable digest, an unknown version, a workflow mismatch, an
already-consumed record: all refuse. There is no branch in this module that
executes on uncertainty.

That includes legacy records written before this PR. They carry no digest, so
their integrity cannot be established, so they do not run. This is a deliberate,
breaking, correct behavior change -- see the migration plan in
``docs/adr/ADR-013-approval-integrity.md``.

Scope
-----
This module verifies. It does not dispatch, persist, or decide policy. Durable
audit storage is PR-06; audit events here are hash-chained in process and
emitted as structured logs.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Mapping, Optional

from backend.contracts import HashAlgorithm, PayloadDigest
from backend.platform.hashing import compute_digest, digests_match

log = logging.getLogger(__name__)

__all__ = [
    "RECORD_VERSION",
    "IntegrityFailure",
    "IntegrityVerdict",
    "build_record",
    "record_digest",
    "verify_record",
    "ConsumedLedger",
    "consumed_ledger",
]

RECORD_VERSION = 2
"""Version 1 is the pre-integrity format: ``{"action_type", "payload"}`` with no
digest. Version 2 adds the binding. A record declaring a version this build does
not know is refused rather than guessed at."""

_DIGEST_ALGORITHM = HashAlgorithm.SHA256

#: Fields covered by the digest. Ordered irrelevantly -- canonicalization sorts.
_SIGNED_FIELDS = ("record_version", "workflow_id", "action_type", "payload")


class IntegrityFailure(str, Enum):
    """Why verification refused. Every value means "do not execute"."""

    MISSING_RECORD = "missing_record"
    MALFORMED_RECORD = "malformed_record"
    LEGACY_UNVERSIONED = "legacy_unversioned"
    UNSUPPORTED_VERSION = "unsupported_version"
    MISSING_DIGEST = "missing_digest"
    MALFORMED_DIGEST = "malformed_digest"
    DIGEST_MISMATCH = "digest_mismatch"
    WORKFLOW_MISMATCH = "workflow_mismatch"
    ALREADY_CONSUMED = "already_consumed"

    @property
    def is_tamper_evidence(self) -> bool:
        """Whether this failure indicates deliberate modification.

        Distinguishes "someone changed the payload" from "this record predates
        the integrity check". Both refuse; only the former should page anyone.
        """
        return self in {
            IntegrityFailure.DIGEST_MISMATCH,
            IntegrityFailure.WORKFLOW_MISMATCH,
            IntegrityFailure.ALREADY_CONSUMED,
            IntegrityFailure.MALFORMED_DIGEST,
        }


@dataclass(frozen=True)
class IntegrityVerdict:
    """The result of verifying a stored approval record.

    ``ok`` is the only field a caller should branch on, and it is ``True`` only
    when every check passed. The rest exists so a refusal can be explained in an
    audit record rather than merely logged.
    """

    ok: bool
    workflow_id: str
    action_type: Optional[str] = None
    payload: Optional[Mapping[str, Any]] = None
    failure: Optional[IntegrityFailure] = None
    expected_digest: Optional[str] = None
    actual_digest: Optional[str] = None
    detail: Optional[str] = None

    @property
    def refused(self) -> bool:
        return not self.ok

    def reason(self) -> str:
        """Human-readable refusal reason, for logs and audit records."""
        if self.ok:
            return "integrity verified"
        base = self.failure.value if self.failure else "unknown"
        return f"{base}: {self.detail}" if self.detail else base


def _signed_view(
    workflow_id: str, action_type: str, payload: Mapping[str, Any], record_version: int
) -> Dict[str, Any]:
    """The exact structure the digest is taken over."""
    return {
        "record_version": record_version,
        "workflow_id": workflow_id,
        "action_type": action_type,
        "payload": dict(payload),
    }


def record_digest(
    workflow_id: str,
    action_type: str,
    payload: Mapping[str, Any],
    record_version: int = RECORD_VERSION,
) -> PayloadDigest:
    """Compute the binding digest for an approval record.

    Uses PR-02 canonical serialization, so key insertion order, JSON
    round-tripping, and dict rebuild order cannot change the result.
    """
    return compute_digest(
        _signed_view(workflow_id, action_type, payload, record_version), _DIGEST_ALGORITHM
    )


def build_record(
    workflow_id: str, action_type: str, payload: Mapping[str, Any]
) -> Dict[str, Any]:
    """Build a digest-bound, storable approval record.

    Called by the store rather than by executors. A caller that had to remember
    to compute a digest would eventually forget, and the failure would be
    silent -- so the only way to stash an action is to stash a bound one.
    """
    if not isinstance(workflow_id, str) or not workflow_id.strip():
        raise ValueError("workflow_id must be a non-blank string")
    if not isinstance(action_type, str) or not action_type.strip():
        raise ValueError("action_type must be a non-blank string")
    if not isinstance(payload, Mapping):
        raise ValueError(f"payload must be a mapping, received {type(payload).__name__}")

    digest = record_digest(workflow_id, action_type, payload)
    return {
        "record_version": RECORD_VERSION,
        "workflow_id": workflow_id,
        "action_type": action_type,
        "payload": dict(payload),
        "digest": {"algorithm": digest.algorithm.value, "value": digest.value},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


class ConsumedLedger:
    """Records which workflows have already had their action dispatched.

    Popping a record from the store makes ordinary replay impossible, but an
    attacker who can write the store can also *re-insert* a record that already
    executed. The ledger closes that: a workflow id is single-use for the life
    of the process.

    In-process only. A restart clears it, which is a real limitation stated
    plainly rather than hidden -- durable replay protection arrives with PR-11,
    when the store itself moves to the database.
    """

    __slots__ = ("_lock", "_consumed")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._consumed: set[str] = set()

    def is_consumed(self, workflow_id: str) -> bool:
        with self._lock:
            return workflow_id in self._consumed

    def mark_consumed(self, workflow_id: str) -> bool:
        """Mark a workflow dispatched. Returns ``False`` if it already was.

        Atomic: two threads racing the same workflow will see exactly one
        ``True``, so a concurrent double-dispatch is impossible.
        """
        with self._lock:
            if workflow_id in self._consumed:
                return False
            self._consumed.add(workflow_id)
            return True

    def clear(self) -> None:
        """Drop every entry. Intended for test isolation."""
        with self._lock:
            self._consumed.clear()


consumed_ledger = ConsumedLedger()


def verify_record(
    workflow_id: str,
    record: Optional[Mapping[str, Any]],
    *,
    ledger: Optional[ConsumedLedger] = None,
) -> IntegrityVerdict:
    """Verify a stored approval record against its digest.

    Returns a verdict; never raises for an integrity problem, because a refusal
    is an expected outcome that must be audited rather than an exception to be
    swallowed by a broad handler somewhere upstream.

    Checks run in order of certainty: structural problems first, then version,
    then digest, then replay. Each returns immediately, so the reported failure
    is the first thing actually wrong.
    """
    checker = ledger if ledger is not None else consumed_ledger

    if record is None:
        return IntegrityVerdict(
            ok=False, workflow_id=workflow_id, failure=IntegrityFailure.MISSING_RECORD
        )

    if not isinstance(record, Mapping):
        return IntegrityVerdict(
            ok=False,
            workflow_id=workflow_id,
            failure=IntegrityFailure.MALFORMED_RECORD,
            detail=f"expected a mapping, found {type(record).__name__}",
        )

    version = record.get("record_version")
    if version is None:
        # Pre-PR-04 format. No digest exists, so integrity cannot be
        # established. Constitution: fail closed.
        return IntegrityVerdict(
            ok=False,
            workflow_id=workflow_id,
            action_type=record.get("action_type"),
            failure=IntegrityFailure.LEGACY_UNVERSIONED,
            detail=(
                "record predates approval-integrity enforcement and carries no digest; "
                "re-request approval to obtain a bound record"
            ),
        )

    if not isinstance(version, int) or version > RECORD_VERSION or version < 1:
        return IntegrityVerdict(
            ok=False,
            workflow_id=workflow_id,
            failure=IntegrityFailure.UNSUPPORTED_VERSION,
            detail=f"record declares version {version!r}; this build supports {RECORD_VERSION}",
        )

    action_type = record.get("action_type")
    payload = record.get("payload")
    if not isinstance(action_type, str) or not action_type.strip():
        return IntegrityVerdict(
            ok=False,
            workflow_id=workflow_id,
            failure=IntegrityFailure.MALFORMED_RECORD,
            detail="action_type is missing or not a string",
        )
    if not isinstance(payload, Mapping):
        return IntegrityVerdict(
            ok=False,
            workflow_id=workflow_id,
            action_type=action_type,
            failure=IntegrityFailure.MALFORMED_RECORD,
            detail="payload is missing or not a mapping",
        )

    stored_workflow = record.get("workflow_id")
    if stored_workflow != workflow_id:
        # The record was authorized under a different workflow. Executing it
        # here would apply one approval's authority to another's action.
        return IntegrityVerdict(
            ok=False,
            workflow_id=workflow_id,
            action_type=action_type,
            failure=IntegrityFailure.WORKFLOW_MISMATCH,
            detail=f"record is bound to workflow {stored_workflow!r}",
        )

    raw_digest = record.get("digest")
    if raw_digest is None:
        return IntegrityVerdict(
            ok=False,
            workflow_id=workflow_id,
            action_type=action_type,
            failure=IntegrityFailure.MISSING_DIGEST,
            detail="versioned record carries no digest",
        )

    try:
        expected = PayloadDigest(
            algorithm=HashAlgorithm(raw_digest["algorithm"]), value=raw_digest["value"]
        )
    except Exception as exc:  # noqa: BLE001 - any malformation refuses identically
        return IntegrityVerdict(
            ok=False,
            workflow_id=workflow_id,
            action_type=action_type,
            failure=IntegrityFailure.MALFORMED_DIGEST,
            detail=f"stored digest is unusable: {exc}",
        )

    actual = record_digest(workflow_id, action_type, payload, version)

    if not digests_match(actual, expected):
        return IntegrityVerdict(
            ok=False,
            workflow_id=workflow_id,
            action_type=action_type,
            failure=IntegrityFailure.DIGEST_MISMATCH,
            expected_digest=expected.value,
            actual_digest=actual.value,
            detail="stored content does not match the approved digest",
        )

    if checker.is_consumed(workflow_id):
        return IntegrityVerdict(
            ok=False,
            workflow_id=workflow_id,
            action_type=action_type,
            failure=IntegrityFailure.ALREADY_CONSUMED,
            expected_digest=expected.value,
            detail="this workflow's action has already been dispatched",
        )

    return IntegrityVerdict(
        ok=True,
        workflow_id=workflow_id,
        action_type=action_type,
        payload=payload,
        expected_digest=expected.value,
        actual_digest=actual.value,
    )
