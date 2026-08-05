"""Audit vocabulary.

Owner: BC-6 Governance.

Constitution I3: the audit record is append-only and independently verifiable.
S8 adds that it "is designed for a hostile reader" -- it must survive a dispute
without the reader trusting the running system.

Two consequences shape this module:

* **Chaining is part of the record, not metadata.** ``AuditEvent`` carries the
  previous entry's digest and its own. A reader with only the exported rows can
  verify the chain.
* **Digests are declared, not computed here.** Canonical hashing is platform
  infrastructure (PR-02). This module defines the shape and the *link* check;
  PR-06 supplies the values.

``AuditEventKind`` deliberately includes refusals. A system that records only
what it did, and not what it declined to do, cannot demonstrate that its
controls fired.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts._contract import Contract, freeze_mapping
from backend.contracts.approval import PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contracts.identity import PrincipalRef
from backend.contracts.tenant import TenantScope

__all__ = ["AuditEventKind", "AuditEvent", "GENESIS_PREVIOUS_DIGEST"]

GENESIS_PREVIOUS_DIGEST = None
"""The first entry in a chain has no predecessor. Represented as ``None`` rather
than a sentinel digest so that "first entry" cannot be forged by supplying a
well-known value."""


class AuditEventKind(str, Enum):
    """Every kind of event the audit trail records."""

    MISSION_TRANSITIONED = "mission_transitioned"
    POLICY_EVALUATED = "policy_evaluated"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    APPROVAL_EXPIRED = "approval_expired"

    EXECUTION_STARTED = "execution_started"
    EXECUTION_SUCCEEDED = "execution_succeeded"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_COMPENSATED = "execution_compensated"

    EXECUTION_REFUSED = "execution_refused"
    """A control fired and blocked execution. The most important kind: it is the
    evidence that the system's safety properties are live rather than claimed."""

    INTEGRITY_VIOLATION_DETECTED = "integrity_violation_detected"
    """An approval digest mismatch or chain break was observed (I2 / I3)."""

    REPLAY_ATTEMPT_DETECTED = "replay_attempt_detected"
    """A previously-consumed authorization was presented again (I2)."""

    BREAK_GLASS_INVOKED = "break_glass_invoked"
    VERIFICATION_RECORDED = "verification_recorded"

    CONFIGURATION_CHANGED = "configuration_changed"
    """A policy, declaration, or platform setting was altered."""

    IDENTITY_EVENT = "identity_event"
    """Authentication, authorization, or credential lifecycle."""

    CONNECTOR_OPERATION = "connector_operation"
    """An external system was read from or written to."""

    @property
    def is_security_relevant(self) -> bool:
        """Kinds that must never be sampled, truncated, or rate-limited away."""
        return self in {
            AuditEventKind.EXECUTION_REFUSED,
            AuditEventKind.INTEGRITY_VIOLATION_DETECTED,
            AuditEventKind.REPLAY_ATTEMPT_DETECTED,
            AuditEventKind.BREAK_GLASS_INVOKED,
            AuditEventKind.APPROVAL_GRANTED,
            AuditEventKind.APPROVAL_DENIED,
            AuditEventKind.IDENTITY_EVENT,
        }


@dataclass(frozen=True)
class AuditEvent(Contract):
    """One immutable, chained entry in the audit trail.

    ``entry_digest`` covers this entry's content *including*
    ``previous_digest``. That is what makes the chain tamper-evident: altering
    any earlier entry invalidates every digest after it.

    ``actor`` is Optional because some entries are recorded by the platform with
    no principal in play (an approval expiring on a timer). ``sequence`` and
    ``recorded_at`` are always present so ordering never depends on clock
    resolution alone.
    """

    CONTRACT_NAME = "cortexprime.audit.event"

    event_id: str
    kind: AuditEventKind
    scope: TenantScope
    recorded_at: datetime
    sequence: int
    entry_digest: PayloadDigest
    previous_digest: Optional[PayloadDigest] = None
    actor: Optional[PrincipalRef] = None
    subject_reference: Optional[str] = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    correlation_id: Optional[str] = None
    """Constant across a causal chain, so a whole incident can be filtered.
    Added in PR-06; optional, so entries written before it remain decodable."""

    causation_id: Optional[str] = None
    """The audit event that directly caused this one. Null at a chain origin."""

    payload_digest: Optional[PayloadDigest] = None
    """Digest of the subject this entry describes -- the approved artifact, the
    executed action -- as distinct from ``entry_digest``, which covers the audit
    entry itself. Lets an auditor tie a record to the thing it is about without
    trusting the detail bag."""

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ContractViolation("event_id must be a non-blank string")
        if not isinstance(self.kind, AuditEventKind):
            raise ContractViolation("kind must be an AuditEventKind")
        if self.recorded_at.tzinfo is None:
            raise ContractViolation("recorded_at must be timezone-aware")
        if not isinstance(self.sequence, int) or self.sequence < 0:
            raise ContractViolation("sequence must be a non-negative integer")

        if self.sequence == 0 and self.previous_digest is not None:
            raise ContractViolation("the first entry in a chain must have no previous_digest")
        if self.sequence > 0 and self.previous_digest is None:
            raise ContractViolation(
                "only the first entry may omit previous_digest; a gap breaks verifiability"
            )
        if (
            self.previous_digest is not None
            and self.previous_digest.algorithm is not self.entry_digest.algorithm
        ):
            raise ContractViolation(
                "chain digests must use one algorithm; a mixed chain cannot be verified end to end"
            )

        if self.causation_id is not None and self.causation_id == self.event_id:
            raise ContractViolation("an audit event cannot be its own cause")

        object.__setattr__(self, "detail", freeze_mapping(self.detail))

    @property
    def is_genesis(self) -> bool:
        return self.sequence == 0

    def links_to(self, predecessor: "AuditEvent") -> bool:
        """Whether this entry correctly chains onto ``predecessor``.

        Verifying an entire chain is a platform concern (PR-06); this is the
        single-link check the vocabulary can express on its own.
        """
        if not isinstance(predecessor, AuditEvent):
            raise ContractViolation("predecessor must be an AuditEvent")
        if self.is_genesis:
            return False
        if self.sequence != predecessor.sequence + 1:
            return False
        assert self.previous_digest is not None  # guaranteed by __post_init__
        return self.previous_digest.matches(predecessor.entry_digest)
