"""The policy evaluation boundary. One seam, not four engines.

CortexPrime already has RBAC, ABAC and PBAC code, and OPA is on the roadmap.
This module does **not** add a fifth. It defines the single narrow Protocol that
capability authorization evaluates through, so an existing engine can be adapted
at the composition root without the context knowing which engine it is.

The Protocol takes a snapshot and returns a verdict. That is the entire surface.
An evaluator cannot query, cannot fetch, and cannot reach the registry — which is
what makes a decision reproducible from its recorded snapshot.

Fail closed, structurally
---------------------------
``GuardedPolicy`` wraps any evaluator so that an exception, a timeout, a ``None``,
or anything that is not a well-formed verdict becomes ``DENY`` with
``POLICY_UNAVAILABLE``. There is no configuration that changes this. "Policy
engine down, so allow" is the failure mode that turns an outage into a breach,
and the only way to be sure it cannot happen is to make the permissive branch
absent rather than optional.

The built-in evaluator
------------------------
``GrantBackedPolicy`` is deliberately minimal: it checks that the principal holds
the coarse grant for the operation, applies separation of duties, and escalates
by risk. It exists so the platform is governed *now* rather than open until an
external engine is wired, and it is designed to be replaced.

What it is not is an authorization model of its own. It has no roles, no rule
language, and no inheritance — anything richer belongs in the engine that already
exists, reached through this same Protocol.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

from backend.contracts.execution import EffectSemantics
from backend.contracts.policy import Obligation, ObligationKind, PolicyEffect, RiskLevel
from backend.contexts.connectivity.domain.authorization import (
    AuthorizationSnapshot,
    CapabilityOperation,
    DenialReason,
)

__all__ = [
    "PolicyVerdict",
    "CapabilityPolicy",
    "GuardedPolicy",
    "DenyAllPolicy",
    "GrantBackedPolicy",
    "default_policy",
]

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PolicyVerdict:
    """What an evaluator concluded. Reasons are mandatory unless allowing."""

    effect: PolicyEffect
    policy_version: str
    reasons: tuple = ()
    obligations: tuple = ()
    risk: Optional[RiskLevel] = None

    def __post_init__(self) -> None:
        if not isinstance(self.effect, PolicyEffect):
            raise ValueError("effect must be a PolicyEffect")
        if not self.policy_version.strip():
            raise ValueError("a verdict must name the policy version that produced it")


@runtime_checkable
class CapabilityPolicy(Protocol):
    """Decides from a snapshot. Holds nothing it could look anything up with."""

    @property
    def policy_version(self) -> str: ...

    def evaluate(self, snapshot: AuthorizationSnapshot) -> PolicyVerdict: ...


class DenyAllPolicy:
    """Refuses everything. The safe placeholder, and the test baseline.

    Named so that a deployment running it is obviously running it. The previous
    phase's ``OpenRegistration`` was the mirror image of this, and replacing one
    with the other is the point of Phase 3.2.3.
    """

    @property
    def policy_version(self) -> str:
        return "deny-all/1"

    def evaluate(self, snapshot: AuthorizationSnapshot) -> PolicyVerdict:
        return PolicyVerdict(
            effect=PolicyEffect.DENY,
            policy_version=self.policy_version,
            reasons=(DenialReason.POLICY_DENIED,),
        )


class GuardedPolicy:
    """Wraps an evaluator so that uncertainty becomes denial.

    Every failure mode collapses to the same answer: a policy engine that raises,
    returns nothing, or returns something malformed produces DENY with
    ``POLICY_UNAVAILABLE``. The permissive branch does not exist.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    @property
    def policy_version(self) -> str:
        try:
            return str(self._inner.policy_version)
        except Exception:  # noqa: BLE001 - an evaluator that cannot name itself
            return "unavailable/0"

    def evaluate(self, snapshot: AuthorizationSnapshot) -> PolicyVerdict:
        try:
            verdict = self._inner.evaluate(snapshot)
        except Exception:  # noqa: BLE001 - any failure is a denial, never an allow
            log.warning(
                "capability policy evaluation failed; denying", exc_info=True
            )
            return PolicyVerdict(
                effect=PolicyEffect.DENY,
                policy_version=self.policy_version,
                reasons=(DenialReason.POLICY_UNAVAILABLE,),
            )

        if not isinstance(verdict, PolicyVerdict):
            log.warning(
                "capability policy returned %r, which is not a PolicyVerdict; denying",
                type(verdict).__name__,
            )
            return PolicyVerdict(
                effect=PolicyEffect.DENY,
                policy_version=self.policy_version,
                reasons=(DenialReason.POLICY_UNAVAILABLE,),
            )
        if verdict.effect is not PolicyEffect.ALLOW and not verdict.reasons:
            # An unexplained non-allow is treated as unavailable rather than
            # passed through: a denial nobody can read is not auditable.
            return PolicyVerdict(
                effect=PolicyEffect.DENY,
                policy_version=verdict.policy_version,
                reasons=(DenialReason.POLICY_UNAVAILABLE,),
            )
        return verdict


class GrantBackedPolicy:
    """Coarse grants, separation of duties, and risk escalation.

    Reads ``IdentityContext.capabilities`` (carried into the snapshot as
    ``principal_grants``) and looks for the grant naming the operation, e.g.
    ``capability:enable``. Grants are an input to this decision, never the
    decision itself -- Constitution I1 requires the decision to be recorded
    regardless of what the principal holds, which is what the service does with
    the verdict.
    """

    def __init__(
        self,
        *,
        require_approval_at: RiskLevel = RiskLevel.HIGH,
        platform_grant: str = "capability:platform-admin",
    ) -> None:
        self._require_approval_at = require_approval_at
        self._platform_grant = platform_grant

    @property
    def policy_version(self) -> str:
        return f"grant-backed/1(approval>={self._require_approval_at.value})"

    def evaluate(self, snapshot: AuthorizationSnapshot) -> PolicyVerdict:
        request = snapshot.request
        operation = request.operation
        grants = set(snapshot.principal_grants)
        risk = snapshot.implied_risk

        # 1. The principal must hold the grant for *this* operation. Holding
        #    'register' does not imply 'enable'; that is the separation the
        #    operation enum exists to express.
        if operation.required_grant not in grants and self._platform_grant not in grants:
            return PolicyVerdict(
                effect=PolicyEffect.DENY,
                policy_version=self.policy_version,
                reasons=(DenialReason.PRINCIPAL_NOT_AUTHORIZED,),
                risk=risk,
            )

        # 2. Separation of duties. Whoever owns a capability does not get to be
        #    the one who makes it available -- that is the whole reason owner and
        #    governor are different roles. A self-declared capability granting
        #    itself availability is the same failure with an extra step.
        if operation.grants_availability and snapshot.principal_is_owner:
            return PolicyVerdict(
                effect=PolicyEffect.DENY,
                policy_version=self.policy_version,
                reasons=(DenialReason.SEPARATION_OF_DUTIES,),
                risk=risk,
            )

        # 3. An undeclared effect never becomes usable by default. It is not a
        #    denial of the operation -- somebody may legitimately want to enable
        #    it -- but it is never allowed without a human saying so.
        if (
            operation.is_execution
            and snapshot.effect_semantics is EffectSemantics.UNKNOWN
        ):
            return PolicyVerdict(
                effect=PolicyEffect.REQUIRE_APPROVAL,
                policy_version=self.policy_version,
                reasons=(DenialReason.EFFECT_UNDECLARED,),
                risk=RiskLevel.CRITICAL,
                obligations=(
                    Obligation(
                        kind=ObligationKind.RECORD_JUSTIFICATION,
                        detail=(
                            "the capability does not declare whether repeating it "
                            "is safe; a human must state why running it is acceptable"
                        ),
                    ),
                ),
            )

        # 4. Risk escalation. High and critical work proceeds only with an
        #    approval behind it -- but only for operations that *increase*
        #    exposure. Disabling, quarantining or revoking a dangerous capability
        #    makes the platform safer, and requiring sign-off to shut something
        #    down would make the escalation work backwards at exactly the moment
        #    it matters.
        if (
            not operation.reduces_exposure
            and risk >= self._require_approval_at
            and not snapshot.approval_valid
        ):
            return PolicyVerdict(
                effect=PolicyEffect.REQUIRE_APPROVAL,
                policy_version=self.policy_version,
                reasons=(DenialReason.APPROVAL_REQUIRED,),
                risk=risk,
                obligations=(
                    Obligation(
                        kind=ObligationKind.POST_EXECUTION_REVIEW,
                        detail=f"{risk.value}-risk capability use",
                    ),
                ),
            )

        obligations: tuple = ()
        if snapshot.capability_is_self_declared:
            # Provenance is an input, and this is what it buys: not a refusal,
            # but a note that what was relied on was the thing's own account of
            # itself.
            obligations = (
                Obligation(
                    kind=ObligationKind.NOTIFY_OWNER,
                    detail="capability metadata is self-declared by its source",
                ),
            )

        return PolicyVerdict(
            effect=PolicyEffect.ALLOW,
            policy_version=self.policy_version,
            risk=risk,
            obligations=obligations,
        )


def default_policy() -> CapabilityPolicy:
    """What the platform runs unless something else is wired in.

    Guarded, so failure denies. Grant-backed rather than deny-all so the
    platform is *governed* rather than merely closed -- a registry nobody can
    use is safe and useless, and teams route around it by disabling the guard.
    """
    return GuardedPolicy(GrantBackedPolicy())
