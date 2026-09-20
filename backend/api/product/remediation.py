"""Governed remediation for the product surface — Phase 10.3 (ADR-096).

The one rule this module exists to hold
---------------------------------------
**Nothing a browser sends is authority.** A client can name an investigation and
say why it wants to act. Everything else -- which capability, which provider,
which namespace, which workload, which payload, the environment, the principal,
the side-effect class, the code trust, the isolation tier, the reversibility,
both digests -- is reconstructed here from what the platform already knows.

That is not a stylistic preference. Phase 9.9C found a live hole where an
approval granted for ``billing-api`` successfully restarted ``payments-api``,
because a check that should have compared the action digest never ran. A product
API is a **new caller** into that same path, and the way a new caller
reintroduces such a defect is by being trusted with a value it should have had
to derive.

What this module does NOT do
----------------------------
It does not decide whether an approval is valid (``ApprovalFacts.is_valid_for``
and the gateway do), it does not authorize (``CapabilityAuthorizationService``
does), it does not execute (``GovernedCapabilityWriter`` does), it does not set
autonomy (``AutonomyPolicy`` does), and it does not verify an outcome (Assurance
does). It assembles a proposal from governed facts, records a human's decision,
and then calls the one execution door that already exists.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

log = logging.getLogger(__name__)

__all__ = [
    "RemediationProposal",
    "RemediationService",
    "RemediationUnavailable",
    "APPROVAL_TTL_MINUTES",
]

#: How long a granted approval stays usable. An approval that never expires is a
#: standing authorization nobody consciously granted, so there is no "no expiry"
#: option -- only a value.
APPROVAL_TTL_MINUTES = 30

#: Subjects the platform writes into ``incident_ref``. The workload name is
#: parsed from a reference the PLATFORM produced, never from a client string.
_SUBJECT = re.compile(
    r"^kubernetes:(?P<kind>pod|deployment):(?P<namespace>[a-z0-9][a-z0-9.-]{0,62})/"
    r"(?P<name>[a-z0-9][a-z0-9.-]{0,62})$"
)

#: A pod name carries the ReplicaSet and pod suffixes that a Deployment name does
#: not. Restarting a *deployment* is the governed operation, so a pod subject is
#: reduced to its owning deployment by dropping the two generated segments.
_POD_SUFFIX = re.compile(r"-[a-z0-9]{6,10}-[a-z0-9]{5}$|-[a-z0-9]{8,10}$")


class RemediationUnavailable(Exception):
    """No governed remediation exists for this subject.

    Raised rather than returning something plausible. Phase 9 closed with
    exactly ONE commissioned write capability; offering anything else would be
    offering an action the platform would refuse, which teaches an operator to
    expect capabilities that do not exist.
    """


@dataclass(frozen=True)
class RemediationProposal:
    """What the platform would do, and every governed fact about it.

    Every field is read from a capability contract, a policy, or a digest
    function. None is computed by a presentation layer and none may be.
    """

    investigation_ref: str
    capability_ref: str
    capability_digest: str
    capability_version: int
    operation: str
    provider: str
    tenant_id: str
    principal_id: str
    environment: str
    namespace: str
    workload: str
    payload: Mapping[str, Any]
    side_effect_class: str
    effect_semantics: Optional[str]
    code_trust: str
    isolation_tier: str
    reversible: bool
    approval_required: bool
    autonomy_ceiling: str
    #: ADR-090. The digest a human is asked about, and the one the gateway
    #: compares against. Computed here with the platform's own function.
    approval_digest: str
    evidence_refs: tuple[str, ...] = ()
    diagnosis: Optional[str] = None


class RemediationService:
    """Assembles proposals, records decisions, and calls the existing writer."""

    def __init__(
        self, *, definitions: Mapping[str, Any], approvals: Any, writer_factory: Any,
        environment: Any, authorization_operation: str,
        autonomy_ceiling: str = "a3_approved_action",
    ) -> None:
        self._definitions = dict(definitions or {})
        self._approvals = approvals
        self._writer_factory = writer_factory
        self._environment = environment
        # Supplied by composition rather than imported. This module already
        # imports the execution context for the digest function; importing the
        # connectivity context as well would make it a second composition root,
        # which the architecture forbids for good reason -- a module that
        # reaches into two contexts is a module that can wire them together
        # without anybody having decided that it should.
        self._authorization_operation = authorization_operation
        self._autonomy_ceiling = autonomy_ceiling

    # -- proposal ----------------------------------------------------------

    def target_of(self, incident_ref: Optional[str]) -> Optional[tuple[str, str]]:
        """``(namespace, deployment)`` from a platform-written subject reference.

        Returns ``None`` for anything that does not match. A subject this does
        not understand yields no proposal, rather than a guess about what the
        operator probably meant.
        """
        # Phase 11.4: one implementation, shared with the remediation planner.
        from backend.api.remediation_planning import workload_of

        return workload_of(incident_ref)

    def propose(
        self, *, investigation: Any, tenant_id: str, principal_id: str,
        operation: str,
    ) -> RemediationProposal:
        """The governed proposal for one investigation.

        ``operation`` is checked against the definitions this service was given,
        so a client naming an operation the platform has not commissioned gets
        nothing -- it cannot introduce one by asking.
        """
        from backend.contexts.execution.domain.invocation import (
            canonical_approval_digest,
        )

        definition = self._definitions.get(operation)
        if definition is None:
            raise RemediationUnavailable(
                f"{operation!r} is not a commissioned capability")

        target = self.target_of(getattr(investigation, "incident_ref", None))
        if target is None:
            raise RemediationUnavailable(
                "this investigation's subject is not a Kubernetes workload this "
                "platform has a commissioned remediation for")
        namespace, workload = target

        contract = getattr(definition, "contract", None)
        # The validated input. This exact mapping goes into the digest and into
        # the execution, so the thing approved and the thing done are one object.
        payload: Mapping[str, Any] = {"namespace": namespace, "name": workload}

        side_effect = _value(getattr(contract, "side_effect_class", None))
        return RemediationProposal(
            investigation_ref=_text(getattr(investigation, "investigation_ref", "")),
            capability_ref=_text(getattr(getattr(definition, "reference", None), "value", "")),
            capability_digest=_text(getattr(definition, "digest", "")),
            # ``version`` is a CapabilityVersion value object, not an int.
            capability_version=_version_of(definition),
            operation=operation,
            provider=_text(getattr(contract, "provider", None)
                           or getattr(definition, "provider", None)),
            tenant_id=tenant_id,
            principal_id=principal_id,
            environment=_value(self._environment),
            namespace=namespace,
            workload=workload,
            payload=payload,
            side_effect_class=side_effect,
            effect_semantics=_value(getattr(contract, "effect_semantics", None)),
            code_trust=_value(getattr(contract, "code_trust", None)),
            isolation_tier=_value(getattr(contract, "isolation_tier", None)),
            # Read from the contract, never inferred from the operation's name.
            reversible=bool(getattr(
                getattr(contract, "side_effect_class", None), "is_reversible", False)),
            # An irreversible write requires a human. This is reported, not
            # decided: the authorization policy re-decides it at dispatch and
            # the gateway re-checks it again after that.
            approval_required=True,
            autonomy_ceiling=self._autonomy_ceiling,
            approval_digest=canonical_approval_digest(
                capability_ref=_text(getattr(getattr(definition, "reference", None), "value", "")),
                capability_digest=_text(getattr(definition, "digest", "")),
                operation=operation,
                tenant_id=tenant_id,
                principal_id=principal_id,
                environment=self._environment,
                payload=payload,
            ),
            evidence_refs=tuple(
                _text(r) for r in (getattr(investigation, "evidence_refs", ()) or ())),
            diagnosis=_value(getattr(investigation, "conclusion", None)),
        )

    # -- approval ----------------------------------------------------------

    def request_approval(
        self, *, proposal: RemediationProposal, requested_by: str,
        justification: Optional[str], now: datetime,
    ) -> str:
        """Record a PENDING approval for exactly this proposal.

        ``requested_by`` comes from the authenticated session. The approval id is
        derived from the approval digest and the requester, so re-submitting the
        same request returns the same approval instead of creating a second one
        that could be decided differently from the first.
        """
        from backend.platform.identity.generators import prefixed_id

        # The investigation is part of the identity on purpose. Two different
        # investigations of the same workload are two different human intents,
        # even though the action they would take is identical -- and an approval
        # granted while investigating one incident should not silently satisfy a
        # request raised while investigating another.
        identity = (f"{proposal.approval_digest}:{requested_by}:"
                    f"{proposal.investigation_ref}")
        approval_id = prefixed_id("appr")
        created = self._approvals.request(
            approval_id=approval_id,
            identity_digest=identity[:128],
            tenant_id=proposal.tenant_id,
            capability_ref=proposal.capability_ref,
            capability_digest=proposal.capability_digest,
            operation=proposal.operation,
            # What authorization is asked about. Kept distinct from the provider
            # operation above so the operation check in ApprovalFacts actually
            # compares like with like.
            authorization_operation=self._authorization_operation,
            environment=proposal.environment,
            principal_id=proposal.principal_id,
            payload=dict(proposal.payload),
            approval_digest=proposal.approval_digest,
            requested_by=requested_by,
            expires_at=now + timedelta(minutes=APPROVAL_TTL_MINUTES),
            requested_at=now,
            investigation_ref=proposal.investigation_ref,
            justification=justification,
        )
        if created:
            return approval_id
        # Idempotent: the same request already exists. Look it up by the
        # IDENTITY that caused the collision, not by the approval digest.
        #
        # This distinction is not academic. Several approvals can share an
        # approval digest -- same action, same tenant, same principal -- while
        # having different outcomes. Matching on the digest returned "an
        # approval for this action", which during this phase's own negative
        # matrix turned out to be an already-decided one, and a pending request
        # silently became a decided approval belonging to something else.
        existing = self._approvals.get_by_identity(
            tenant_id=proposal.tenant_id, identity_digest=identity[:128])
        if existing is not None:
            return existing.approval_id
        raise RemediationUnavailable(
            "an approval for this exact request already exists but could not be "
            "read back; refusing to create a second one")

    # -- execution ---------------------------------------------------------

    def execute(
        self, *, runtime: Any, context: Any, approval_record: Any,
        principal: Any,
    ) -> Any:
        """Run the approved action through the ONE existing execution door.

        The payload comes from the stored approval row, not from the caller.
        That is what makes the approval and the execution the same action: there
        is no second place for a target to be supplied, so there is no gap for
        one to differ.
        """
        writer = self._writer_factory(runtime, self._definitions, principal)
        return writer.write(
            context,
            operation=approval_record.operation,
            payload=dict(approval_record.payload or {}),
            approval_artifact_id=approval_record.approval_id,
        )

    def submit(
        self, *, runtime: Any, context: Any, approval_record: Any,
        principal: Any,
    ) -> Any:
        """``execute``, returning once the execution is durable.

        The same door, the same payload from the same stored row, the same
        governance. The only difference is that the caller is not required to
        stay for the provider call -- which was never something governance
        depended on.
        """
        writer = self._writer_factory(runtime, self._definitions, principal)
        return writer.submit(
            context,
            operation=approval_record.operation,
            payload=dict(approval_record.payload or {}),
            approval_artifact_id=approval_record.approval_id,
        )


def _version_of(definition: Any) -> int:
    """The capability's contract version as an integer.

    ``reference.version`` is a ``CapabilityVersion`` value object. It is
    unwrapped rather than stringified because an approver comparing "version 1"
    against "version 2" needs a number, and because the capability digest --
    which already covers the version -- is what actually binds the approval.
    """
    version = getattr(getattr(definition, "reference", None), "version", None)
    for attribute in ("value", "number", "version"):
        inner = getattr(version, attribute, None)
        if isinstance(inner, int):
            return inner
    try:
        return int(str(version))
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value))[:400]


def _value(value: Any) -> Optional[str]:
    if value is None:
        return None
    inner = getattr(value, "value", value)
    return str(inner)[:200]
