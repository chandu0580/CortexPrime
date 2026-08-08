"""The authorized capability, as Execution is allowed to see it.

Why this is primitives and not the real thing
-----------------------------------------------
``CapabilityBinding`` lives in BC-8 Connectivity (ADR-035). Execution may not
import it — Constitution S2 — and should not want to: a binding is Connectivity's
aggregate, with its own lifecycle, and pulling it in here would make the
execution runtime depend on how capability selection happens to be modelled.

So the composition root projects a binding into this value object: flat
primitives, no behaviour that belongs to the other side, and nothing Execution
could use to *make* a binding. Execution can read what was authorized and check
what it can check locally. It cannot mint one.

What Execution can and cannot verify
--------------------------------------
Locally verifiable here: expiry, that the binding names this tenant, principal,
execution and operation, and that the fields it needs are present. That is
enough to refuse most stale or misdirected work without asking anybody.

*Not* verifiable here: whether the capability is still enabled, still trusted,
and still has that digest. Those are authoritative reads that belong to
Connectivity, so they arrive through the ``BindingValidator`` port. Execution
refuses when the port says so and refuses when there is no port — never the
reverse.

The rule this object exists to make unbreakable
-------------------------------------------------
**There is no constructor path that produces a usable binding from nothing.**
Every field is required, and the digests are opaque strings Execution cannot
compute. A worker, an adapter, or a caller cannot fabricate authority by
building one of these, because the only thing that makes it real is a validator
that lives on the other side of the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics, SideEffectClass

__all__ = ["BoundCapability", "BindingRefused"]


class BindingRefused(ContractViolation):
    """A binding was presented and Execution will not act on it."""

    def __init__(self, binding_id: str, *reasons: str) -> None:
        listed = ", ".join(reasons) or "unspecified"
        super().__init__(
            f"binding {binding_id} was refused: {listed}. Execution does not "
            "re-resolve; a different target requires a new binding"
        )
        self.binding_id = binding_id
        self.reasons = tuple(reasons)


@dataclass(frozen=True)
class BoundCapability:
    """What was authorized, projected for the runtime that will perform it."""

    binding_id: str
    binding_digest: str
    capability_ref: str
    """Rendered ``namespace.provider.capability[.operation]@version``. A string
    here on purpose: Execution never parses it, never compares its parts, and
    never reasons about versions. It carries it and hands it back."""

    capability_digest: str
    provider: str
    operation: str
    authorization_digest: str
    tenant_id: str
    principal_id: str
    expires_at: datetime

    side_effect_class: SideEffectClass
    effect_semantics: EffectSemantics

    execution_id: Optional[str] = None
    node_id: Optional[str] = None
    workflow_id: Optional[str] = None
    mission_id: Optional[str] = None
    resolution_policy_version: Optional[str] = None
    authorization_policy_version: Optional[str] = None

    def __post_init__(self) -> None:
        for label in (
            "binding_id",
            "binding_digest",
            "capability_ref",
            "capability_digest",
            "provider",
            "operation",
            "authorization_digest",
            "tenant_id",
            "principal_id",
        ):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"{label} must be non-blank text; a binding missing it cannot "
                    "be checked, and an uncheckable binding is not authority"
                )
        if self.expires_at.tzinfo is None:
            raise ContractViolation("expires_at must be timezone-aware")
        if not isinstance(self.side_effect_class, SideEffectClass):
            raise ContractViolation("side_effect_class must be a SideEffectClass")
        if not isinstance(self.effect_semantics, EffectSemantics):
            raise ContractViolation("effect_semantics must be an EffectSemantics")

    # ------------------------------------------------------------------
    # What Execution can check on its own
    # ------------------------------------------------------------------

    def is_live_at(self, moment: datetime) -> bool:
        return moment < self.expires_at

    @property
    def mutates(self) -> bool:
        return self.side_effect_class.mutates

    @property
    def is_repeatable(self) -> bool:
        """Whether running this again is safe. UNKNOWN is not."""
        return self.effect_semantics.is_repeatable

    def local_refusals(
        self,
        *,
        tenant_id: str,
        principal_id: str,
        execution_id: Optional[str],
        node_id: Optional[str] = None,
        operation: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> tuple:
        """Everything wrong that Execution can see without asking anybody.

        Returns every reason rather than the first: an operator fixing one and
        rediscovering the next has been told half the truth twice.
        """
        moment = now or datetime.now(timezone.utc)
        reasons: list = []

        if not self.is_live_at(moment):
            reasons.append("binding_expired")
        if self.tenant_id != tenant_id:
            # A binding for another tenant is not a weaker binding; it is
            # somebody else's authority presented here.
            reasons.append("tenant_mismatch")
        if self.principal_id != principal_id:
            reasons.append("principal_mismatch")
        if (self.execution_id or None) != (execution_id or None):
            reasons.append("execution_mismatch")
        if node_id is not None and (self.node_id or None) != (node_id or None):
            reasons.append("node_mismatch")
        if operation is not None and self.operation != operation:
            reasons.append("operation_mismatch")
        return tuple(reasons)

    def assert_locally_usable(self, **checks: Any) -> None:
        reasons = self.local_refusals(**checks)
        if reasons:
            raise BindingRefused(self.binding_id, *reasons)

    def to_dict(self) -> dict:
        return {
            "binding_id": self.binding_id,
            "binding_digest": self.binding_digest,
            "capability_ref": self.capability_ref,
            "capability_digest": self.capability_digest,
            "provider": self.provider,
            "operation": self.operation,
            "authorization_digest": self.authorization_digest,
            "tenant_id": self.tenant_id,
            "principal_id": self.principal_id,
            "expires_at": self.expires_at.isoformat(),
            "side_effect_class": self.side_effect_class.value,
            "effect_semantics": self.effect_semantics.value,
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "workflow_id": self.workflow_id,
            "mission_id": self.mission_id,
            "resolution_policy_version": self.resolution_policy_version,
            "authorization_policy_version": self.authorization_policy_version,
        }
