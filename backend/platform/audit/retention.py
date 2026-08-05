"""Audit retention.

Retention and tamper-evidence are in genuine tension, and the honest way to
handle that is to state it rather than quietly resolve it.

Deleting a record from the middle of a hash chain breaks the chain. It is
indistinguishable, to a verifier, from an attacker removing evidence -- which is
the entire point of chaining. So retention here is **archive-then-truncate from
the front**, never delete-in-place:

1. Export the records to be retired, with their manifest and head digest.
2. Record the archival itself as an audit event, so the trail explains its own
   gap.
3. Truncate the chain's prefix, leaving a checkpoint.

A chain truncated at the front still verifies, provided the verifier is told it
is a slice (``expect_origin=False``). A chain with a hole in the middle does
not, and this module will not create one.

``RetentionPolicy`` is an interface. Nothing is deleted automatically: the
default is :class:`KeepForever`, and any policy that discards evidence should be
a deliberate operator decision with a compliance rationale behind it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Protocol, runtime_checkable

from backend.contracts import AuditEvent

__all__ = [
    "RetentionPolicy",
    "KeepForever",
    "AgeBasedRetention",
    "RetentionDecision",
    "plan_retention",
]


@runtime_checkable
class RetentionPolicy(Protocol):
    """Decides whether a record must be retained.

    Implementations must be pure and deterministic: the same record and instant
    must always yield the same answer, or an audit trail becomes unreproducible.
    """

    name: str

    def must_retain(self, record: AuditEvent, now: datetime) -> bool: ...


class KeepForever:
    """Retain everything. The default, and the only policy that never loses evidence."""

    name = "keep-forever"

    def must_retain(self, record: AuditEvent, now: datetime) -> bool:
        return True


@dataclass(frozen=True)
class AgeBasedRetention:
    """Retain records for a fixed period, with a floor for security events.

    Security-relevant kinds -- refusals, integrity violations, break-glass,
    approvals, identity events -- get a longer minimum, because they are exactly
    the records a dispute will turn on. ``AuditEventKind.is_security_relevant``
    defines the set; this policy does not restate it.
    """

    retain_days: int
    security_retain_days: int = 2555  # ~7 years, a common compliance floor
    name: str = "age-based"

    def __post_init__(self) -> None:
        if self.retain_days < 1:
            raise ValueError("retain_days must be at least 1")
        if self.security_retain_days < self.retain_days:
            raise ValueError(
                "security_retain_days must be at least retain_days; security evidence "
                "cannot be retained for less time than routine records"
            )

    def must_retain(self, record: AuditEvent, now: datetime) -> bool:
        days = (
            self.security_retain_days
            if record.kind.is_security_relevant
            else self.retain_days
        )
        return record.recorded_at > now - timedelta(days=days)


@dataclass(frozen=True)
class RetentionDecision:
    """What a policy would retire, and where the chain would then start.

    ``safe`` is ``False`` when the retirable records are not a contiguous prefix.
    In that case archiving them would leave a hole, so the plan is refused
    rather than executed -- a chain with a hole cannot be distinguished from a
    tampered one.
    """

    policy_name: str
    total_records: int
    retirable_count: int
    retain_from_sequence: Optional[int]
    safe: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "policy": self.policy_name,
            "total_records": self.total_records,
            "retirable_count": self.retirable_count,
            "retain_from_sequence": self.retain_from_sequence,
            "safe": self.safe,
            "reason": self.reason,
        }


def plan_retention(
    records: list[AuditEvent], policy: RetentionPolicy, *, now: Optional[datetime] = None
) -> RetentionDecision:
    """Plan retention without performing it.

    Deliberately does not mutate anything. Producing a plan an operator reviews
    before archiving is the difference between retention and data loss.
    """
    moment = now or datetime.now(timezone.utc)
    if not records:
        return RetentionDecision(
            policy_name=policy.name,
            total_records=0,
            retirable_count=0,
            retain_from_sequence=None,
            safe=True,
            reason="no records",
        )

    ordered = sorted(records, key=lambda record: record.sequence)
    retirable = [record for record in ordered if not policy.must_retain(record, moment)]

    if not retirable:
        return RetentionDecision(
            policy_name=policy.name,
            total_records=len(ordered),
            retirable_count=0,
            retain_from_sequence=ordered[0].sequence,
            safe=True,
            reason="policy retains every record",
        )

    # Retirable records must form a contiguous prefix, or archiving leaves a hole.
    prefix_length = 0
    for record in ordered:
        if policy.must_retain(record, moment):
            break
        prefix_length += 1

    if prefix_length != len(retirable):
        return RetentionDecision(
            policy_name=policy.name,
            total_records=len(ordered),
            retirable_count=len(retirable),
            retain_from_sequence=ordered[0].sequence,
            safe=False,
            reason=(
                f"{len(retirable)} record(s) are retirable but only {prefix_length} form a "
                "contiguous prefix; archiving them would leave a hole in the chain, which "
                "is indistinguishable from tampering"
            ),
        )

    if prefix_length == len(ordered):
        return RetentionDecision(
            policy_name=policy.name,
            total_records=len(ordered),
            retirable_count=prefix_length,
            retain_from_sequence=None,
            safe=True,
            reason="every record is retirable; archive the whole chain and start a new one",
        )

    return RetentionDecision(
        policy_name=policy.name,
        total_records=len(ordered),
        retirable_count=prefix_length,
        retain_from_sequence=ordered[prefix_length].sequence,
        safe=True,
        reason=(
            f"archive sequences {ordered[0].sequence}-{ordered[prefix_length - 1].sequence}, "
            f"then verify the remainder with expect_origin=False"
        ),
    )
