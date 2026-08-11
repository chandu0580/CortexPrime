"""Governed delegation: ask, approve, issue, revoke. **Four steps, one path.**

What a delegation is, and why it needs a workflow
--------------------------------------------------
A delegation lets one principal act *as* another. That is identity borrowing,
and it is the single most dangerous grant this platform can make — which is why
Phase 4.4 refused every on-behalf-of invocation outright and Phase 5.1 gave the
grant a durable home without giving anyone a way to create one.

This is the way. It is deliberately four steps rather than one:

    request   somebody asks. Nothing is granted; the row is evidence of an ask.
    approve   somebody *else* decides. The decision binds to the request digest.
    issue     the grant appears — and only against an approval that exists.
    revoke    the grant stops working. Immediately, attributably, and without
              touching a single historical execution record.

The thing that makes this a governance boundary rather than a form is the second
step, and specifically the word *else*.

Privilege separation, and the honest state of it
--------------------------------------------------
The rule this enforces: **the actor gaining authority may not approve their own
request.** ``_DEFAULT_SEPARATION`` enforces exactly that and nothing more,
because that is exactly what can be enforced without a policy that does not yet
exist.

There is no approver *role* model in this codebase. ``backend/approval_center``
has workflow machinery, and ``PrincipalRef.can_approve`` states the human-only
rule, but nothing anywhere answers "is this person entitled to approve a
delegation of *this* scope in *this* tenant". That question needs an approver
policy, and inventing one here would be inventing governance.

So ``ApproverPolicy`` is a port. It has one implementation in this module, it
fails closed on everything it cannot answer, and the gap is written down in
ADR-046 rather than papered over. A deployment that needs role-based approver
selection supplies a policy; until then, delegation requires a distinct human
approver and nothing weaker.

What is deliberately reused, and what deliberately is not
-----------------------------------------------------------
Reused from ``backend.contracts.approval``: ``ApprovalOutcome``,
``PayloadDigest``, ``HashAlgorithm``, and the ``can_approve`` rule that
``ApprovalDecision`` enforces. That is the approval *vocabulary*, and there is
no second one here.

**Not** reused: ``ApprovalArtifact``. Its contract binds an ``ExecutionContract``
— it is the thing that proves a human approved *the run that will happen*. A
delegation is not a run. Manufacturing an empty ``ExecutionContract`` to fit a
delegation into that shape would produce an artifact whose digest covers a
fiction, and a fictional binding is worse than an honest absence. The delegation
approval binds to ``request_digest`` instead, which covers the real thing being
approved.

No caching. On purpose.
-------------------------
Nothing here memoises a grant, and ``DurableDelegationAuthority`` reads the
table on every check. A cache would mean a revoked delegation kept working for
the length of a TTL, and "revoked, effective in thirty seconds" is not
revocation. The cost is one indexed read per delegated invocation, which is the
correct thing to spend.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

from backend.contracts.approval import ApprovalOutcome, HashAlgorithm, PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contracts.identity import PrincipalKind, PrincipalRef
from backend.platform.observability.metrics import NullMetrics, SafeMetrics

__all__ = [
    "ApproverPolicy",
    "SeparationOfDutyPolicy",
    "DelegationRefused",
    "DelegationOutcome",
    "DelegationWorkflow",
    "MAX_DELEGATION_SECONDS",
    "DELEGATION_METRICS",
]

log = logging.getLogger(__name__)

MAX_DELEGATION_SECONDS = 24 * 60 * 60
"""A ceiling, not a default. A delegation that outlives the task it was granted
for is a standing identity transfer, and the whole reason the grant carries an
expiry is so that forgetting to revoke one is survivable."""

DELEGATION_METRICS = (
    "delegation.requested",
    "delegation.approved",
    "delegation.denied",
    "delegation.issued",
    "delegation.revoked",
    "delegation.refused",
)


class DelegationRefused(ContractViolation):
    """A delegation step was refused. Carries why, because an audit will ask."""

    def __init__(self, reason: str, code: str = "delegation_refused") -> None:
        super().__init__(reason)
        self.code = code


@runtime_checkable
class ApproverPolicy(Protocol):
    """May this principal approve this request? **Fail closed, always.**

    An implementation that cannot answer returns ``False``. There is no third
    value and no "unknown", because an unknown that reaches a caller becomes a
    permission the first time somebody writes ``if not policy.refuses(...)``.
    """

    def may_approve(
        self, context: Any, *, request: Any, approver: PrincipalRef
    ) -> bool: ...

    @property
    def policy_name(self) -> str: ...


class SeparationOfDutyPolicy:
    """The minimum defensible rule, and an honest statement of its limits.

    Refuses when the approver is the actor gaining authority, when the approver
    is the principal being borrowed, when the approver is the requester, and
    when the approver is not human. Permits everything else — which is not the
    same as "everything else is fine", it is "this policy has nothing to say
    about it".

    Naming it after what it enforces rather than something like
    ``DefaultApproverPolicy`` is deliberate: a reader deciding whether their
    deployment needs a real approver model should not have to open the file to
    discover that the default checks four identities and no entitlements.
    """

    policy_name = "separation-of-duty/1"

    def may_approve(self, context: Any, *, request: Any, approver: PrincipalRef) -> bool:
        if not isinstance(approver, PrincipalRef):
            return False
        if not approver.can_approve:
            # The platform must never authorize itself. Same rule
            # ``ApprovalDecision`` enforces, stated in one place and reused.
            return False
        forbidden = {
            getattr(request, "actor_principal_id", None),
            getattr(request, "delegated_principal_id", None),
            getattr(request, "requested_by", None),
        }
        return approver.principal_id not in forbidden


@dataclass(frozen=True)
class DelegationOutcome:
    """What one workflow step did. Facts, never a permission."""

    step: str
    request_id: str
    accepted: bool
    reason: str = ""
    delegation_id: Optional[str] = None
    digest: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "request_id": self.request_id,
            "accepted": self.accepted,
            "reason": self.reason,
            "delegation_id": self.delegation_id,
            "digest": self.digest,
        }


class DelegationWorkflow:
    """The only way a delegation grant comes into existence.

    "Only" is enforced a layer down, not here:
    ``SqlDelegationRepository.issue`` requires ``request_id``,
    ``approval_artifact_id`` and ``approved_by`` as keyword arguments with no
    defaults. This class is the only thing that can produce a matching set, so
    routing around it does not yield an unapproved grant — it yields a
    ``TypeError``.
    """

    def __init__(
        self,
        *,
        requests: Any,
        delegations: Any,
        store: Any,
        approver_policy: Optional[ApproverPolicy] = None,
        metrics: Optional[Any] = None,
        max_seconds: int = MAX_DELEGATION_SECONDS,
    ) -> None:
        self._requests = requests
        self._delegations = delegations
        self._store = store
        self._policy = approver_policy or SeparationOfDutyPolicy()
        self._metrics = SafeMetrics(metrics or NullMetrics())
        self._max_seconds = int(max_seconds)

    @property
    def policy_name(self) -> str:
        return self._policy.policy_name

    # ------------------------------------------------------------------
    # 1. Ask. This grants nothing.
    # ------------------------------------------------------------------

    def request(
        self,
        context: Any,
        *,
        request_id: str,
        requested_by: PrincipalRef,
        actor_principal_id: str,
        delegated_principal_id: str,
        scope: Sequence[Mapping[str, Any]],
        reason: str,
        validity_seconds: int,
        request_ttl_seconds: int = 3600,
    ) -> DelegationOutcome:
        """Record a delegation request. **A request is not authority.**

        Everything checkable about the *shape* of the eventual grant is checked
        now rather than at issuance, so an impossible request is refused while
        somebody is still looking at it — rather than approved by a human and
        then rejected by a machine, which teaches people that approvals do not
        mean anything.
        """
        if not isinstance(requested_by, PrincipalRef):
            raise DelegationRefused(
                "a delegation request must name who is asking",
                "requester_unattributed",
            )
        if actor_principal_id == delegated_principal_id:
            raise DelegationRefused(
                "an actor cannot be delegated its own identity",
                "self_delegation",
            )
        entries = self._checked_scope(scope)
        if not isinstance(reason, str) or len(reason.strip()) < 8:
            raise DelegationRefused(
                "a delegation request must state why, in enough words to be "
                "reviewable; identity borrowing approved on a blank reason is "
                "identity borrowing nobody actually reviewed",
                "reason_missing",
            )
        if not 0 < int(validity_seconds) <= self._max_seconds:
            raise DelegationRefused(
                f"a delegation may last between one second and "
                f"{self._max_seconds} seconds; anything longer is a standing "
                "identity transfer",
                "validity_out_of_range",
            )
        if requested_by.kind is PrincipalKind.PLATFORM:
            # No "system" delegation. A platform principal asking to borrow an
            # identity is the platform arranging its own authority, and there is
            # no human in that loop by construction. ``PrincipalKind`` names
            # this kind ``PLATFORM``; it is the same principal the Constitution
            # means when it says the platform must never authorize itself.
            raise DelegationRefused(
                "a platform principal may not request a delegation; the platform "
                "must never arrange its own authority",
                "system_requester",
            )

        with self._store.atomic() as unit:
            record = self._requests.open(
                context,
                request_id=request_id,
                requested_by=requested_by.principal_id,
                actor_principal_id=actor_principal_id,
                delegated_principal_id=delegated_principal_id,
                scope=entries,
                reason=reason,
                validity_seconds=int(validity_seconds),
                expires_at=unit.now + timedelta(seconds=int(request_ttl_seconds)),
                unit=unit,
            )
        self._metrics.increment("delegation.requested", labels={})
        log.info(
            "delegation requested: %s may act as %s (request %s, %d scope entries)",
            actor_principal_id,
            delegated_principal_id,
            request_id,
            len(entries),
        )
        return DelegationOutcome(
            step="request",
            request_id=request_id,
            accepted=True,
            digest=record.request_digest,
        )

    # ------------------------------------------------------------------
    # 2. Decide. Somebody else, and bound to what they were shown.
    # ------------------------------------------------------------------

    def approve(
        self,
        context: Any,
        *,
        request_id: str,
        approver: PrincipalRef,
        approved_digest: str,
        artifact_id: Optional[str] = None,
        note: Optional[str] = None,
    ) -> DelegationOutcome:
        """Approve a request, against the digest the approver was shown.

        ``approved_digest`` is not decoration. The approver's client computed or
        displayed it from what it rendered; if the stored request has changed
        since — a widened scope, a longer validity, a different delegated
        principal — the two do not match and the approval is refused. That is
        the defence against the attack that defeats human review in practice:
        show a human one thing, execute another.
        """
        record = self._load(context, request_id)
        if record.status != "pending":
            raise DelegationRefused(
                f"delegation request {request_id} is already {record.status}",
                "already_decided",
            )

        now = self._now()
        if record.is_expired_at(now):
            self._requests.decide(
                context,
                request_id=request_id,
                outcome="expired",
                decided_by=approver.principal_id
                if isinstance(approver, PrincipalRef)
                else "unknown",
                reason="the request expired before a decision was recorded",
            )
            raise DelegationRefused(
                f"delegation request {request_id} expired before it was decided",
                "request_expired",
            )

        if not self._policy.may_approve(context, request=record, approver=approver):
            self._metrics.increment(
                "delegation.refused", labels={"reason": "approver_not_permitted"}
            )
            log.warning(
                "delegation approval refused: %s may not approve request %s under "
                "policy %s",
                getattr(approver, "principal_id", "<none>"),
                request_id,
                self._policy.policy_name,
            )
            raise DelegationRefused(
                "this principal may not approve this delegation request",
                "approver_not_permitted",
            )

        # Constant-time, and through the contract vocabulary rather than ``==``.
        # The comparison is the security boundary, so it uses the type whose
        # whole job is comparing digests correctly.
        try:
            shown = PayloadDigest(algorithm=HashAlgorithm.SHA256, value=approved_digest)
        except ContractViolation as exc:
            raise DelegationRefused(
                f"the approved digest is malformed: {exc}", "digest_malformed"
            ) from None
        stored = PayloadDigest(
            algorithm=HashAlgorithm.SHA256, value=record.request_digest
        )
        if not stored.matches(shown):
            self._metrics.increment(
                "delegation.refused", labels={"reason": "digest_mismatch"}
            )
            log.error(
                "delegation approval refused for %s: the approver decided against "
                "a different version of the request than the one stored",
                request_id,
            )
            raise DelegationRefused(
                "the approved digest does not match the stored request; the "
                "request changed after it was shown",
                "digest_mismatch",
            )

        landed = self._requests.decide(
            context,
            request_id=request_id,
            outcome="approved",
            decided_by=approver.principal_id,
            approval_artifact_id=artifact_id or f"delapp-{request_id}",
            approval_digest=record.request_digest,
            reason=note,
        )
        if not landed:
            raise DelegationRefused(
                "another approver decided this request first", "already_decided"
            )
        self._metrics.increment("delegation.approved", labels={})
        return DelegationOutcome(
            step="approve",
            request_id=request_id,
            accepted=True,
            digest=record.request_digest,
        )

    def deny(
        self,
        context: Any,
        *,
        request_id: str,
        approver: PrincipalRef,
        reason: str,
    ) -> DelegationOutcome:
        """Refuse a request. A reason is required, as ``ApprovalDecision`` requires.

        No policy check and no digest check, deliberately. Both exist to stop
        authority being *granted* wrongly; applying them to a denial would mean
        a request that cannot be approved also cannot be closed, and pending
        requests that nobody can clear are how a queue stops being read.
        """
        if not isinstance(reason, str) or not reason.strip():
            raise DelegationRefused(
                "a denied delegation must record why", "reason_missing"
            )
        landed = self._requests.decide(
            context,
            request_id=request_id,
            outcome="denied",
            decided_by=getattr(approver, "principal_id", "unknown"),
            reason=reason,
        )
        if landed:
            self._metrics.increment("delegation.denied", labels={})
        return DelegationOutcome(
            step="deny",
            request_id=request_id,
            accepted=landed,
            reason="" if landed else "another decision landed first",
        )

    # ------------------------------------------------------------------
    # 3. Issue. Only against an approval.
    # ------------------------------------------------------------------

    def issue(
        self,
        context: Any,
        *,
        request_id: str,
        delegation_id: str,
        issued_by: PrincipalRef,
    ) -> DelegationOutcome:
        """Turn an approved request into a grant. One approval, one grant.

        The grant insert and the request transition happen in **one unit of
        work**, and the transition is conditional on the request still being
        approved-and-unissued. Two concurrent issuances therefore produce one
        grant and one refusal: the loser's ``mark_issued`` matches no row, this
        raises, and its transaction rolls the grant back with it.
        """
        record = self._load(context, request_id)
        if record.status == "issued":
            raise DelegationRefused(
                f"delegation request {request_id} has already been issued as "
                f"{record.issued_delegation_id}",
                "already_issued",
            )
        if record.status != "approved":
            raise DelegationRefused(
                f"delegation request {request_id} is {record.status}; only an "
                "approved request may produce a delegation",
                "not_approved",
            )
        if not record.approved_by or not record.approval_artifact_id:
            # Belt and braces: an approved row missing its evidence is a row
            # somebody wrote by hand, and it does not become a grant.
            raise DelegationRefused(
                f"delegation request {request_id} is marked approved but carries "
                "no approval evidence",
                "approval_evidence_missing",
            )

        with self._store.atomic() as unit:
            grant = self._delegations.issue(
                context,
                delegation_id=delegation_id,
                actor_principal_id=record.actor_principal_id,
                delegated_principal_id=record.delegated_principal_id,
                scope=record.scope,
                issued_by=issued_by.principal_id,
                expires_at=unit.now
                + timedelta(seconds=int(record.requested_validity_seconds)),
                request_id=request_id,
                approval_artifact_id=record.approval_artifact_id,
                approved_by=record.approved_by,
                unit=unit,
            )
            if not self._requests.mark_issued(
                context,
                request_id=request_id,
                delegation_id=delegation_id,
                unit=unit,
            ):
                # Rolls the grant back with it. A grant whose request cannot be
                # marked issued is a grant that could be issued again.
                raise DelegationRefused(
                    "the request was issued concurrently; this grant is rolled "
                    "back rather than left as a second grant for one approval",
                    "issue_raced",
                )

        self._metrics.increment("delegation.issued", labels={})
        log.info(
            "delegation %s issued: %s may act as %s until %s (approved by %s)",
            delegation_id,
            grant.actor_principal_id,
            grant.delegated_principal_id,
            grant.expires_at,
            record.approved_by,
        )
        return DelegationOutcome(
            step="issue",
            request_id=request_id,
            accepted=True,
            delegation_id=delegation_id,
            digest=grant.digest,
        )

    # ------------------------------------------------------------------
    # 4. Revoke. Immediately, and without rewriting the past.
    # ------------------------------------------------------------------

    def revoke(
        self,
        context: Any,
        *,
        delegation_id: str,
        revoked_by: PrincipalRef,
        reason: str,
    ) -> DelegationOutcome:
        """Withdraw a grant. Effective on the next check, which is every check.

        There is no cache to invalidate and no propagation delay, because
        nothing caches delegation authority: the next invocation reads the row
        and finds ``revoked_at`` set. An invocation already admitted keeps
        running — stopping it is cancellation, which is a different mechanism
        with different evidence, and conflating the two would mean revocation
        silently killed work without recording that it had.
        """
        if not isinstance(revoked_by, PrincipalRef):
            raise DelegationRefused(
                "a revocation must name who performed it", "revoker_unattributed"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise DelegationRefused(
                "a revocation must state why", "reason_missing"
            )
        landed = self._delegations.revoke(
            context,
            delegation_id=delegation_id,
            reason=reason,
            revoked_by=revoked_by.principal_id,
        )
        if landed:
            self._metrics.increment("delegation.revoked", labels={})
            log.warning(
                "delegation %s revoked by %s: %s",
                delegation_id,
                revoked_by.principal_id,
                reason,
            )
        return DelegationOutcome(
            step="revoke",
            request_id="",
            accepted=landed,
            delegation_id=delegation_id,
            reason="" if landed else "no live delegation with that id",
        )

    # ------------------------------------------------------------------

    def _load(self, context: Any, request_id: str) -> Any:
        record = self._requests.find(context, request_id)
        if record is None:
            raise DelegationRefused(
                f"no delegation request {request_id} in this tenant",
                "request_not_found",
            )
        return record

    def _checked_scope(self, scope: Sequence[Mapping[str, Any]]) -> list:
        entries = [dict(entry) for entry in scope]
        if not entries:
            raise DelegationRefused(
                "a delegation must state what it covers; an empty scope reads as "
                "a delegation of everything to the first query that treats a "
                "missing list as unconstrained",
                "scope_empty",
            )
        for entry in entries:
            capability = entry.get("capability_ref")
            operations = entry.get("operations")
            if not isinstance(capability, str) or not capability.strip():
                raise DelegationRefused(
                    "each delegation scope entry must name a capability",
                    "scope_malformed",
                )
            if not isinstance(operations, list) or not operations:
                raise DelegationRefused(
                    "each delegation scope entry must name at least one operation",
                    "scope_malformed",
                )
            if any(op in ("*", "") or not isinstance(op, str) for op in operations):
                raise DelegationRefused(
                    "a delegation scope may not contain a wildcard operation; "
                    "there is no shape here that means everything",
                    "scope_wildcard",
                )
        return entries

    def _now(self):
        with self._store.atomic() as unit:
            return unit.now


def approval_outcome_of(status: str) -> Optional[ApprovalOutcome]:
    """Map a stored request status onto the shared approval vocabulary.

    Present so that a reader of an audit trail sees the same four words the rest
    of the platform uses. ``pending`` and ``issued`` map to nothing on purpose:
    neither is an approval conclusion, and inventing an ``ApprovalOutcome`` for
    them would put states into that enum that governance never produced.
    """
    return {
        "approved": ApprovalOutcome.GRANTED,
        "denied": ApprovalOutcome.DENIED,
        "expired": ApprovalOutcome.EXPIRED,
        "withdrawn": ApprovalOutcome.WITHDRAWN,
    }.get(status)
