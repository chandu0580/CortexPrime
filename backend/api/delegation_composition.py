"""The delegation authority: a durable fact, consumed by the existing engine.

The gap this closes, and the one it does not
----------------------------------------------
Phase 4.4 found that `AuthorizationRequest` has no delegation concept, so
nothing authoritative could answer "may this actor act for that principal". It
made the safe choice: **every** on-behalf-of invocation is refused, because
absence is not permission.

Phase 5.1 gave that answer somewhere durable to live. This reads it.

What it deliberately is **not** is a second authorization engine.
`CapabilityAuthorizationService` still decides whether the action is permitted;
this answers one narrower question — *is there a durable, live, scoped grant
letting this actor borrow that identity* — and hands the answer to the gateway as
a fact. The gateway's `_check_delegation` does the comparing, exactly as it has
since 4.4.

Nine ways to be refused, and no way to be defaulted
-----------------------------------------------------
    no store wired            → refuse
    no grant                  → refuse
    wrong tenant              → refuse (the query is tenant-scoped)
    wrong actor               → refuse
    wrong delegated principal → refuse
    expired                   → refuse
    revoked                   → refuse
    operation out of scope    → refuse
    digest mismatch           → refuse
    lookup raised             → refuse

There is no branch that returns permission on an unrecognised state. `None` is
the answer in an empty database, and `None` is what keeps delegation refused.

Never from the request
------------------------
The actor is the **authenticated** principal from the context, and the delegated
principal is compared against the durable grant. A request body cannot introduce
a delegation, cannot widen one, and cannot name an actor — it can only state
which delegated principal it believes it is using, which the gateway then checks
against what this returns.

Revocation is immediate, because nothing is cached
----------------------------------------------------
Every check reads the durable row. A revoked grant stops authorizing the next
invocation, not the next cache expiry.

That costs one query per delegated invocation, and the trade is deliberate: a
cache here would need authoritative invalidation across every instance to be
correct, and a delegation that keeps working for thirty seconds after somebody
revoked it is the exact failure revocation exists to prevent.

**Already-running work is not touched.** An execution admitted under a grant that
was live at admission keeps its authority window; revocation stops new
invocations. Retroactively rewriting what was authorized would falsify the
historical evidence, which is a different and worse problem.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Sequence

from backend.contracts.errors import ContractViolation
from backend.platform.hashing import compute_digest

__all__ = [
    "DelegationRef",
    "DelegationStatus",
    "DelegationDecision",
    "DurableDelegationAuthority",
    "build_delegation_authority",
    "build_delegation_workflow",
    "build_connector_configuration",
]

log = logging.getLogger(__name__)


class DelegationStatus(str, Enum):
    """Where a grant is in its life. **Derived, never a stored column.**

    ``revoked_at`` and ``expires_at`` already determine this completely. A
    ``status`` column beside them would be a second copy of the same fact, and
    the first time the two disagree the query that reads the column authorizes
    something the timestamps say is dead.
    """

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"

    @property
    def permits_use(self) -> bool:
        return self is DelegationStatus.ACTIVE

    @classmethod
    def of(cls, grant: Any, now: datetime) -> "DelegationStatus":
        if getattr(grant, "revoked_at", None) is not None:
            return cls.REVOKED
        return cls.ACTIVE if grant.is_live_at(now) else cls.EXPIRED


@dataclass(frozen=True)
class DelegationRef:
    """An opaque handle to a delegation grant. Safe to log and audit.

    Rendered ``delegation://<tenant>/<id>`` so anything printing it shows a
    reference rather than a grant, and so it greps as one. Tenant-qualified in
    the identity itself for the same reason `CredentialRef` is: a handle whose
    tenant could be changed by editing a neighbouring field is one that
    eventually names another tenant's grant.
    """

    tenant_id: str
    delegation_id: str

    def __post_init__(self) -> None:
        for label in ("tenant_id", "delegation_id"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
            if "/" in value:
                raise ContractViolation(
                    f"{label} must not contain a separator; a reference that does "
                    "not round-trip is one that eventually names something else"
                )

    @property
    def value(self) -> str:
        return f"delegation://{self.tenant_id}/{self.delegation_id}"

    def __str__(self) -> str:
        return self.value

    def to_dict(self) -> dict:
        return {
            "ref": self.value,
            "tenant_id": self.tenant_id,
            "delegation_id": self.delegation_id,
        }


@dataclass(frozen=True)
class DelegationDecision:
    """What the authority answers with. Two fields, and both are required.

    Shaped to the port the composition root already reads (`permitted` plus
    `delegated_principal_id`), so the gateway is unchanged. `reason` carries why
    a refusal happened, for audit — never back to the caller as a hint about
    whether a grant exists, which would be a disclosure.
    """

    permitted: bool
    delegated_principal_id: Optional[str] = None
    delegation_ref: Optional[str] = None
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "permitted": self.permitted,
            "delegated_principal_id": self.delegated_principal_id,
            "delegation_ref": self.delegation_ref,
            "reason": self.reason,
        }


class DurableDelegationAuthority:
    """Reads durable delegation state. Decides nothing else."""

    def __init__(
        self,
        delegations: Any,
        *,
        metrics: Optional[Any] = None,
    ) -> None:
        self._delegations = delegations
        self._metrics = metrics

    # ------------------------------------------------------------------

    def delegation_for(self, context: Any, request: Any) -> DelegationDecision:
        """The port the gateway's authority adapter calls. Refuses on any doubt.

        The actor comes from `request.principal` — which `_check_identity` has
        already proved is the **authenticated** principal, not one the request
        named. The delegated principal comes from `request.on_behalf_of` and is
        used only to *look up* a grant; whether it matches is the gateway's
        comparison, and doing it here as well would put the decision in two
        places.
        """
        declared = getattr(request, "on_behalf_of", None)
        if declared is None:
            # Not a delegated invocation. Nothing to permit, and saying
            # "permitted: False" here is correct rather than unhelpful -- the
            # gateway reads a delegated principal of None as "no delegation",
            # which is the safe reading.
            return DelegationDecision(permitted=False, reason="not_delegated")

        if self._delegations is None:
            return self._refuse("no_delegation_store")

        actor = getattr(getattr(request, "principal", None), "principal_id", None)
        if not actor:
            return self._refuse("no_authenticated_actor")

        try:
            grant = self._delegations.grant_for(
                context,
                actor_principal_id=actor,
                delegated_principal_id=declared.principal_id,
            )
        except Exception:  # noqa: BLE001 - an unreadable grant is no grant
            log.warning("delegation lookup failed", exc_info=False)
            return self._refuse("lookup_failed")

        if grant is None:
            # The ordinary answer in an empty database, and the one that keeps
            # every on-behalf-of invocation refused.
            return self._refuse("no_grant")

        problems = self._invalid(context, grant, request, declared.principal_id)
        if problems:
            return self._refuse(problems[0])

        self._count("delegation.permitted")
        return DelegationDecision(
            permitted=True,
            delegated_principal_id=grant.delegated_principal_id,
            delegation_ref=DelegationRef(
                tenant_id=grant.tenant_id, delegation_id=grant.delegation_id
            ).value,
        )

    # ------------------------------------------------------------------

    def _invalid(
        self, context: Any, grant: Any, request: Any, declared_principal: str
    ) -> Sequence[str]:
        """Every reason this grant does not authorize this request.

        Returns all of them rather than the first: an operator fixing one and
        rediscovering the next has been told half the truth twice. Only the first
        reaches audit, so a caller cannot enumerate a grant's shape by probing.
        """
        problems: list = []
        tenant = getattr(context, "tenant_id", None)

        if not tenant or grant.tenant_id != tenant:
            # The repository is tenant-scoped, so this should be unreachable.
            # Checked anyway: it is the isolation boundary, and a check that is
            # unreachable today is what catches tomorrow's wiring change.
            problems.append("tenant_mismatch")
        if grant.actor_principal_id != getattr(
            getattr(request, "principal", None), "principal_id", None
        ):
            problems.append("actor_mismatch")
        if grant.delegated_principal_id != declared_principal:
            problems.append("delegated_principal_mismatch")

        now = self._now(context)
        if not grant.is_live_at(now):
            problems.append("revoked" if grant.revoked_at is not None else "expired")

        operation = getattr(request, "operation", None)
        capability_ref = getattr(request, "capability_ref", None)
        if not capability_ref or not operation:
            problems.append("unscoped_request")
        elif not grant.permits(capability_ref, operation):
            problems.append("operation_out_of_scope")

        if not self._digest_matches(grant):
            # A grant whose stored digest no longer matches its own fields has
            # been edited outside the application. Refused rather than honoured:
            # this is the artifact that lets one principal act as another.
            problems.append("digest_mismatch")
        return problems

    @staticmethod
    def _digest_matches(grant: Any) -> bool:
        """Recompute the grant's digest from its fields and compare.

        The one place recomputation is correct: the digest was computed *over
        these fields* at issue time, so recomputing and comparing detects an
        edited row. Restoring it without comparing — as is right for a capability
        contract, where the payload is not fully reconstructible — would make the
        check unable to fail.

        The payload builder is **shared with the repository that issued it**.
        Two definitions of the same bytes is two things to keep in step, and the
        first divergence makes every grant fail its own digest — which would look
        exactly like tamper detection working.
        """
        from backend.contexts.connectivity.infrastructure.sql_authority import (
            delegation_digest_payload,
        )

        try:
            payload = delegation_digest_payload(
                delegation_id=grant.delegation_id,
                tenant_id=grant.tenant_id,
                actor_principal_id=grant.actor_principal_id,
                delegated_principal_id=grant.delegated_principal_id,
                scope=grant.scope,
                issued_by=grant.issued_by,
                issued_at=grant.issued_at,
                expires_at=grant.expires_at,
            )
            return compute_digest(payload).value == grant.digest
        except Exception:  # noqa: BLE001 - an undigestable grant is not a valid one
            return False

    def _refuse(self, reason: str) -> DelegationDecision:
        self._count("delegation.refused", reason=reason)
        return DelegationDecision(permitted=False, reason=reason)

    @staticmethod
    def _now(context: Any) -> datetime:
        """The authority clock, or the wall clock as a last resort.

        Threaded from the context where one is available so that the delegation
        window and the invocation's other expiries are judged against one
        reading. A second clock here would be the Phase 4.4 two-clock defect
        wearing a different hat.
        """
        from datetime import timezone

        clock = getattr(context, "now", None)
        if callable(clock):
            moment = clock()
            if isinstance(moment, datetime):
                return moment
        return datetime.now(timezone.utc)

    def _count(self, name: str, **labels: str) -> None:
        if self._metrics is None:
            return
        try:
            self._metrics.increment(name, labels=labels)
        except Exception:  # noqa: BLE001 - measurement never changes an outcome
            log.debug("delegation metric failed", exc_info=False)


def build_delegation_authority(
    delegations: Any, *, metrics: Optional[Any] = None
) -> DurableDelegationAuthority:
    """Wire the authority over the durable delegation repository.

    Passing ``None`` produces an authority that refuses everything, which is the
    correct behaviour for a deployment with no delegation store — and is exactly
    what the platform did before this existed.
    """
    return DurableDelegationAuthority(delegations, metrics=metrics)


def build_delegation_workflow(
    store: Any,
    *,
    approver_policy: Optional[Any] = None,
    metrics: Optional[Any] = None,
) -> Any:
    """Wire the Phase 5.3 request → approve → issue → revoke workflow.

    The workflow is the **only** assembler of the evidence
    ``SqlDelegationRepository.issue`` requires, so wiring it is what makes
    delegation possible at all — and not wiring it leaves the platform where
    Phase 4.4 left it, refusing every on-behalf-of invocation.

    ``approver_policy`` defaults to ``SeparationOfDutyPolicy``, which enforces
    that the actor gaining authority cannot approve their own request and that
    the approver is human. It enforces no entitlement model, because this
    codebase has none; a deployment with an approver directory supplies its own
    policy here. See ADR-046 for the gap, stated rather than implied.
    """
    from backend.contexts.connectivity.application.delegation import DelegationWorkflow
    from backend.contexts.connectivity.infrastructure.sql_authority import (
        SqlDelegationRepository,
        SqlDelegationRequestRepository,
    )

    return DelegationWorkflow(
        requests=SqlDelegationRequestRepository(store),
        delegations=SqlDelegationRepository(store),
        store=store,
        approver_policy=approver_policy,
        metrics=metrics,
    )


def build_connector_configuration(store: Any) -> Any:
    """Wire the tenant-scoped connector configuration repository.

    Separate from the credential broker on purpose. This holds *references*; the
    broker resolves them to material at invocation time and hands it straight to
    transport. A single component doing both would be a component that has, at
    some moment, both the configuration and the secret — which is the shape the
    V1 credential store had.
    """
    from backend.contexts.connectivity.infrastructure.sql_connector_config import (
        SqlConnectorConfigRepository,
    )

    return SqlConnectorConfigRepository(store)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()
