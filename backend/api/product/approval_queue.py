"""The approval queue projection — Phase 10.4 (ADR-097).

What this is
------------
A **read model** over ``cp_approval``. It answers "what is waiting for a human,
across every investigation in this tenant, and what would each one actually do".

What it is not
--------------
It is not an approval authority, and there is nothing in this module that could
become one. It has no write path at all: it reads rows, resolves the capability
contract those rows already name, and projects. The decision still goes to
``POST /api/v1/approvals/{id}/decision``, which is the same conditional update
Phase 10.3 shipped -- so there remains exactly one place an approval is decided.

The two things it deliberately refuses to compute
-------------------------------------------------
**Autonomy.** ``AutonomyPolicy.evaluate`` needs reliability estimates, drift
status, world freshness, emergency-stop state, breaker state and a policy
config. A queue that supplied plausible values for those and called it would be
making an autonomy decision, which is a stop condition. So the queue reports the
platform-set **ceiling** and, where an ``AutonomyDecision`` was actually
recorded, that decision -- and where none was, it says none was.

**The ADR-038 action digest.** It includes ``binding_digest``, which resolution
creates *inside* the execution the approval authorizes. For a pending approval
it does not exist yet; that is precisely why ADR-090 introduced the canonical
approval digest. The queue projects the digest that is real and reports the
other as not yet in existence, rather than inventing a value that would look
like a binding nobody made.

Risk
----
Reused, not invented: ``implied_risk_for`` is the platform's own derivation,
extracted from ``AuthorizationSnapshot.implied_risk`` so there is one
implementation. An undeclared effect is CRITICAL, not LOW.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger(__name__)

__all__ = [
    "QueueState",
    "ACTIONABLE_STATES",
    "project_queue_item",
    "order_queue",
    "queue_state_of",
]

#: The states a queue row can be in. Every one is DERIVED from ``cp_approval``
#: -- there is no stored queue status, because a second stored status is a
#: second thing that can disagree with the approval about whether it is live.
class QueueState:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"
    EXPIRED = "expired"
    CONSUMED = "consumed"
    INVALID = "invalid"


#: The only state in which a decision can still be taken. Everything else is
#: history, and the UI must not offer a button for it.
ACTIONABLE_STATES = (QueueState.PENDING,)

#: Highest risk first. Uses the platform's RiskLevel ranks, not a local scale.
_RISK_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def queue_state_of(record: Any, now: datetime) -> str:
    """The authoritative approval state, projected.

    Order matters, and it is the order of finality:

    * a **consumed** approval is consumed however it was decided -- it already
      authorized an execution, and that is the most important thing to say
      about it;
    * a **decided** approval keeps its decision, expiry notwithstanding: an
      approval that was rejected and then passed its expiry was still rejected,
      and relabelling it EXPIRED would lose who refused it and why;
    * only a still-**pending** request can become EXPIRED, because expiry is
      what happens to a request nobody answered.
    """
    outcome = (getattr(record, "outcome", "") or "").strip().lower()
    if getattr(record, "consumed_by_execution", None):
        return QueueState.CONSUMED
    if outcome == "granted":
        # A grant that ran out of time authorizes nothing; the gateway refuses
        # it and the queue must not show it as actionable.
        return QueueState.EXPIRED if record.is_expired_at(now) else QueueState.APPROVED
    if outcome == "denied":
        return QueueState.REJECTED
    if outcome == "withdrawn":
        return QueueState.REVOKED
    if outcome == "pending":
        return QueueState.EXPIRED if record.is_expired_at(now) else QueueState.PENDING
    # An outcome this projection does not recognise is not treated as pending.
    # Fail closed: an unknown state is never actionable.
    return QueueState.INVALID


@dataclass(frozen=True)
class _Governance:
    """What the capability contract says this action is."""

    provider: Optional[str] = None
    side_effect_class: Optional[str] = None
    effect_semantics: Optional[str] = None
    code_trust: Optional[str] = None
    isolation_tier: Optional[str] = None
    reversible: bool = False
    risk: str = "critical"
    capability_version: int = 0


def _governance_of(definition: Any) -> _Governance:
    """Read the declared facts, and default to the safe end when absent.

    An approval whose capability cannot be resolved is not shown as low risk.
    ``implied_risk_for(None, None)`` is CRITICAL and that is the answer used --
    the queue would rather over-state an unresolvable action than under-state it.
    """
    from backend.contexts.connectivity.domain.authorization import implied_risk_for

    contract = getattr(definition, "contract", None)
    side_effect = getattr(contract, "side_effect_class", None)
    semantics = getattr(contract, "effect_semantics", None)
    version = 0
    reference = getattr(definition, "reference", None)
    raw_version = getattr(reference, "version", None)
    for attribute in ("value", "number", "version"):
        inner = getattr(raw_version, attribute, None)
        if isinstance(inner, int):
            version = inner
            break
    else:
        try:
            version = int(str(raw_version))
        except (TypeError, ValueError):
            version = 0

    return _Governance(
        # The provider id lives on the contract for some definitions and on the
        # definition itself for others. Both are read rather than assuming one.
        provider=_text(getattr(contract, "provider", None)
                       or getattr(definition, "provider", None)) or None,
        side_effect_class=_text(side_effect),
        effect_semantics=_text(semantics),
        code_trust=_text(getattr(contract, "code_trust", None)),
        isolation_tier=_text(getattr(contract, "isolation_tier", None)),
        reversible=bool(getattr(side_effect, "is_reversible", False)),
        risk=implied_risk_for(semantics, side_effect).value,
        capability_version=version,
    )


def project_queue_item(
    record: Any, *, definition: Any, now: datetime,
    investigation: Any = None, autonomy_ceiling: str = "a3_approved_action",
    authority: Any = None,
) -> dict:
    """One queue row. Every governed value comes from a contract or a column.

    ``investigation`` is optional and used only for context a responder needs to
    triage -- the incident reference, how much evidence the investigation rests
    on, and whether Assurance has ruled. None of it is authority, and its
    absence degrades the row's context, never its safety.
    """
    governance = _governance_of(definition)
    payload = getattr(record, "payload", None) or {}
    state = queue_state_of(record, now)

    verification_refs = tuple(
        _text(r) for r in (getattr(investigation, "verification_refs", ()) or ()))
    evidence_refs = tuple(
        _text(r) for r in (getattr(investigation, "evidence_refs", ()) or ()))

    return {
        "approval_id": _text(getattr(record, "approval_id", "")),
        "investigation_ref": _text(getattr(record, "investigation_ref", None)) or None,
        "incident_ref": _text(getattr(investigation, "incident_ref", None)) or None,
        "requested_by": _text(getattr(record, "requested_by", "")),
        "decided_by": _text(getattr(record, "decided_by", None)) or None,
        "requested_at": _iso(getattr(record, "requested_at", None)),
        "decided_at": _iso(getattr(record, "decided_at", None)),
        "expires_at": _iso(getattr(record, "expires_at", None)),
        "capability_ref": _text(getattr(record, "capability_ref", "")),
        "capability_version": governance.capability_version,
        "capability_digest": _text(getattr(record, "capability_digest", "")),
        "operation": _text(getattr(record, "operation", "")),
        "provider": governance.provider,
        "environment": _text(getattr(record, "environment", "")),
        "namespace": str(payload.get("namespace") or ""),
        "workload": str(payload.get("name") or ""),
        "parameters": dict(payload),
        # ADR-090's digest, which is real for a pending approval.
        "approval_digest": _text(getattr(record, "approval_digest", "")),
        # ADR-038's digest, which is NOT. Reported as absent with the reason,
        # never synthesised.
        "action_digest": None,
        "action_digest_note": (
            "The ADR-038 action digest covers the binding, which resolution "
            "creates inside the execution this approval authorizes. It does not "
            "exist yet and is not invented here; the canonical approval digest "
            "above is what binds this approval to this exact action."),
        "side_effect_class": governance.side_effect_class,
        "effect_semantics": governance.effect_semantics,
        "code_trust": governance.code_trust,
        "isolation_tier": governance.isolation_tier,
        "reversible": governance.reversible,
        "risk": governance.risk,
        "blast_radius": (
            f"one Deployment ({payload.get('name')}) in one namespace "
            f"({payload.get('namespace')}); its pods are replaced"
            if payload.get("name") else "not determinable from the stored action"),
        "autonomy_ceiling": autonomy_ceiling,
        "autonomy_requested": _text(
            getattr(investigation, "autonomy_level", None)) or None,
        "autonomy_allowed": None,
        "autonomy_note": (
            "Platform-set ceiling. No autonomy decision is computed here: the "
            "autonomy policy needs calibration, drift, world freshness, stop and "
            "breaker state, and a queue that supplied plausible values for those "
            "would be deciding autonomy rather than reporting it."),
        "assurance_status": (
            "verified" if verification_refs else "not_verified"),
        "assurance_note": (
            "Assurance has recorded a verification for this investigation."
            if verification_refs else
            "Assurance has NOT verified this investigation. That is not a "
            "refutation -- support and verification are separate gates."),
        "verification_refs": verification_refs,
        "evidence_count": len(evidence_refs),
        "evidence_refs": evidence_refs[:20],
        "state": state,
        # Whether the approval CAN still be decided by anyone. A property of the
        # approval, not of the viewer.
        "actionable": state in ACTIONABLE_STATES,
        # Whether THIS caller may decide it: the approval's own state AND the
        # caller's authority, resolved server-side. Two different questions,
        # kept as two fields, because collapsing them would make "you may not"
        # and "nobody may" indistinguishable to a responder.
        #
        # This is a PROJECTION. The decision route re-resolves the same
        # authority from the same store and enforces it; a client that flipped
        # this to true would change what a button looks like and nothing else.
        "can_approve": bool(
            state in ACTIONABLE_STATES
            and authority is not None and getattr(authority, "permitted", False)),
        "authority_reason": _text(getattr(authority, "reason", None)) or "unknown",
        "expired": bool(record.is_expired_at(now)),
        "consumed_by_execution": _text(
            getattr(record, "consumed_by_execution", None)) or None,
        "justification": _text(getattr(record, "justification", None)) or None,
    }


def order_queue(items: list) -> list:
    """Deterministic ordering: actionable first, then risk, then oldest first.

    Every term is a fact already on the row. There is no score, no model and no
    learned ranking -- a responder who reloads the page must see the same order,
    and a queue whose order nobody can predict is a queue nobody can hand over
    at the end of a shift.

    Oldest first within a risk band on purpose: the approval that has been
    waiting longest is the one closest to expiring unanswered.
    """
    def key(item: dict):
        return (
            0 if item.get("actionable") else 1,
            _RISK_ORDER.get(str(item.get("risk") or "").lower(), 0),
            item.get("requested_at") or "",
            item.get("approval_id") or "",
        )

    return sorted(items, key=key)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value))[:400]


def _iso(moment: Any) -> Optional[str]:
    return moment.isoformat() if isinstance(moment, datetime) else None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
