"""The adapter that reaches CortexPrime's first out-of-process worker (ADR-089).

Why this exists
---------------
Phase 9.9 Part A made ``CONTAINED`` mean something specific: *a separate worker
with per-execution credentials.* It then left the tier with zero occupants,
because every connector in this repository runs in the platform's own process
and now honestly declares ``AMBIENT``. This adapter is how the tier gets its
first genuine occupant.

What it is, and what it is emphatically not
-------------------------------------------
It is an ``AdapterSeam`` subclass implementing ``_perform`` and nothing else. It
is **not** a second executor, gateway, scheduler, approval system, authorization
system, credential authority, audit system, replay system or World ingestion
path. It is reached the same way every other adapter is reached --
``InvocationGateway.invoke`` → ``WorkerRuntime.invoke`` → ``adapter.run`` -- and
it decides nothing. It builds one envelope, sends it once, and reports what came
back.

The credential does not travel in the envelope
----------------------------------------------
There is exactly **one** ``reveal()`` call site in this codebase
(``httpx_adapter.py``), where credential material becomes a transport
authorization header. This adapter deliberately does not add a second. The
envelope it builds carries no secret at all; the credential reaches the worker
the way it reaches any other provider, through the existing transport, and the
worker reads it from the header.

That is why the envelope is safe to digest, log and persist: there is nothing in
it to redact.

What the worker is trusted to do, and what it is not
----------------------------------------------------
The worker is trusted to *perform* the declared operation. It is not trusted to
say whether the operation was correct, authorized, or effective. Its answer is a
``ProviderOutcome`` -- what the far side said -- and the World and Assurance
planes decide what actually happened, from an independent read. A worker
reporting ``succeeded`` proves only that the API server returned 2xx.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from backend.contracts.errors import ContractViolation
from backend.contexts.execution.domain.provider_invocation import ProviderAuthority
from backend.contexts.execution.domain.worker import WorkerKind
from backend.contexts.execution.domain.worker_directory import WorkerInterface
from backend.contexts.execution.infrastructure.adapters.base import (
    AdapterSeam,
    ProviderFailure,
    ProviderOutcome,
)
from backend.contexts.execution.infrastructure.adapters.channel import (
    ProviderChannel,
    ProviderDelivery,
    ProviderRequestPlan,
)

__all__ = [
    "ContainedWorkerAdapter", "CONTAINED_WORKER_ENVELOPE_FIELDS",
    "ContainedRollbackWorkerAdapter", "CONTAINED_ROLLBACK_ENVELOPE_FIELDS",
    "ROLLBACK_ARGUMENTS",
]


#: The envelope's exact shape. The worker refuses anything else, and this tuple
#: is the platform's half of that agreement. ``credential`` is deliberately
#: absent: see the module docstring.
CONTAINED_WORKER_ENVELOPE_FIELDS = (
    "tenant",
    "execution_id",
    "capability_id",
    "capability_version",
    "provider",
    "operation",
    "implementation_digest",
    "arguments",
    "authorization_ref",
    "approval_ref",
    "autonomy_decision",
    "worker_identity",
    "execution_digest",
    "idempotency_key",
)


class ContainedWorkerAdapter(AdapterSeam):
    """Dispatches one authorized execution to one out-of-process worker."""

    # CONNECTOR, not KUBERNETES. The runtime's kind resolver answers
    # "connector" for every governed capability in this composition, and worker
    # selection compares that against this field -- so a worker declaring the
    # provider's own name is never selected at all. The worker's Kubernetes-ness
    # is expressed by supported_providers and supported_operations, which is
    # where selection actually reads it.
    WORKER_KIND = WorkerKind.CONNECTOR
    INTERFACE = WorkerInterface.CONNECTOR
    IMPLEMENTATION_VERSION = "1.0.0"
    CONSUMES_PROVIDER_AUTHORITY = True
    REQUIRES_CREDENTIAL = True

    #: The single operation this adapter will dispatch. Declared here as well as
    #: in the worker image: a mismatch between the two is a wiring mistake, and
    #: the adapter refuses rather than letting the worker be the only check.
    OPERATION = "kubernetes.workload.rollout_restart"

    #: The worker's one endpoint. Not configurable, not derived from the
    #: payload, and not something a caller can influence.
    PATH = "/execute"

    def __init__(
        self,
        *,
        implementation: Any,
        provider: Any,
        channel: ProviderChannel,
        capability_id: str,
        capability_version: int,
        implementation_digest: str,
        preflight: Optional[Any] = None,
        metrics: Optional[Any] = None,
    ) -> None:
        super().__init__(
            implementation=implementation,
            provider=provider,
            # The channel IS this adapter's transport. Without it the seam
            # reports LOST and refuses before sending anything -- which is the
            # correct default (there is no fallback transport), and is what a
            # missing wiring should look like.
            invoker=channel,
            preflight=preflight,
            metrics=metrics,
        )
        if not isinstance(channel, ProviderChannel):
            raise ContractViolation(
                "a contained worker adapter needs the governed channel; it has "
                "no other way to reach the worker and must not acquire one"
            )
        for label, value in (
            ("capability_id", capability_id),
            ("implementation_digest", implementation_digest),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"a contained worker adapter must be bound to a {label}; "
                    "an unbound adapter would dispatch to whatever answered"
                )
        if not isinstance(capability_version, int) or capability_version < 1:
            raise ContractViolation("capability_version must be a positive integer")

        self._channel = channel
        self._capability_id = capability_id.strip()
        self._capability_version = capability_version
        self._implementation_digest = implementation_digest.strip()

    # ------------------------------------------------------------------

    def _envelope(self, authority: ProviderAuthority) -> Mapping[str, Any]:
        """Everything the worker is allowed to know, and nothing else.

        Every value here comes from the authority the gateway built. None of it
        comes from a model, and none of it is a destination: the worker's
        Kubernetes address is its own deployment configuration, and the worker's
        own address is the channel's, fixed at composition.
        """
        payload = dict(authority.payload)
        return {
            "tenant": authority.tenant_id,
            "execution_id": authority.execution_id,
            "capability_id": self._capability_id,
            "capability_version": self._capability_version,
            "provider": authority.provider.provider_id,
            "operation": authority.operation,
            "implementation_digest": self._implementation_digest,
            "arguments": {
                "namespace": payload.get("namespace"),
                "name": payload.get("name"),
            },
            # References, never the artifacts themselves. The worker has no
            # business re-deciding any of these, and carrying the decisions
            # would invite it to try.
            "authorization_ref": authority.authorization_digest,
            "approval_ref": authority.approval_ref or "",
            "autonomy_decision": authority.policy_version,
            "worker_identity": authority.worker_id,
            "execution_digest": authority.action_digest,
            # Empty for this operation, and correctly so: a rollout restart is
            # non-idempotent, so the platform derives no key. Kept in the
            # envelope because the worker's field set is exact.
            "idempotency_key": authority.idempotency_key or "",
        }

    def _perform(
        self,
        context: Any,
        request: Any,
        authority: ProviderAuthority,
    ) -> ProviderOutcome:
        # The adapter checks the operation itself rather than trusting the
        # worker's compiled binding to be the only gate. Two independent checks
        # of the same fact is the point: one of them is in an image that may be
        # rebuilt, and the other is in the code review path.
        if authority.operation != self.OPERATION:
            return ProviderOutcome.refused(
                ProviderFailure.OPERATION_NOT_SUPPORTED,
                f"this contained worker performs {self.OPERATION!r} and was "
                f"asked for {authority.operation!r}",
            )

        envelope = self._envelope(authority)
        missing = [
            field for field in ("namespace", "name")
            if not envelope["arguments"].get(field)
        ]
        if missing:
            return ProviderOutcome.refused(
                ProviderFailure.VALIDATION_FAILURE,
                f"the authorized payload does not name a target: missing {missing}",
            )
        if not envelope["execution_digest"]:
            return ProviderOutcome.refused(
                ProviderFailure.VALIDATION_FAILURE,
                "an irreversible write without an action digest is one nothing "
                "can attribute afterwards",
            )

        plan = ProviderRequestPlan(
            method="POST",
            path=self.PATH,
            body=envelope,
            headers={"content-type": "application/json"},
        )

        exchange = self._channel.send(
            authority, plan, provider_timeout_seconds=45,
            max_response_bytes=1024 * 1024
        )

        if exchange.delivery is not ProviderDelivery.DELIVERED:
            # The worker may well have performed the write. Never SUCCESS, and
            # never FAILURE either -- this side cannot tell.
            return ProviderOutcome(
                succeeded=False,
                ambiguous=True,
                delivery=exchange.delivery,
                status_code=exchange.status_code,
                provider_failure=exchange.failure or ProviderFailure.UNKNOWN_OUTCOME,
                error_message=(
                    "the envelope did not complete; whether the worker performed "
                    "the restart is unknown from here"
                ),
            )

        body, decode_error = exchange.json()
        if decode_error or not isinstance(body, Mapping):
            return ProviderOutcome(
                succeeded=False,
                ambiguous=True,
                delivery=exchange.delivery,
                status_code=exchange.status_code,
                provider_failure=ProviderFailure.UNKNOWN_OUTCOME,
                error_message=(
                    "the worker's answer could not be read; what it did is unknown"
                ),
            )

        if body.get("refused"):
            # A refusal by the worker is a refusal, not a failed write: the
            # worker states that it contacted no provider.
            return ProviderOutcome.refused(
                ProviderFailure.VALIDATION_FAILURE,
                f"the contained worker refused: "
                f"{body.get('reason_code')}: {str(body.get('detail'))[:240]}",
            )

        evidence = body.get("evidence") or {}
        if body.get("ambiguous"):
            return ProviderOutcome(
                succeeded=False,
                ambiguous=True,
                delivery=exchange.delivery,
                status_code=body.get("status"),
                provider_failure=ProviderFailure.UNKNOWN_OUTCOME,
                error_message=str(body.get("provider_message") or "")[:240],
                evidence=dict(evidence),
            )

        succeeded = bool(body.get("succeeded"))
        return ProviderOutcome(
            succeeded=succeeded,
            ambiguous=False,
            delivery=exchange.delivery,
            status_code=body.get("status"),
            provider_failure=None if succeeded else _failure_for_status(body.get("status")),
            error_message=(
                None if succeeded else str(body.get("provider_message") or "")[:240]
            ),
            evidence=dict(evidence),
            output={"worker_response_bytes": len(json.dumps(dict(body)))},
        )


def _failure_for_status(status: Any) -> ProviderFailure:
    """The provider-neutral class of a DEFINITE failure the worker reported.

    Phase 11.4 run 8: this used a ``PROVIDER_ERROR`` member the
    enum never had (since Phase 9.9C). Every honest provider-side failure -- a
    401 for a bad credential, a 403 from RBAC, a 422 from a lost
    ``test resourceVersion`` race -- raised AttributeError here and was recorded
    as an UNKNOWN outcome instead of the failure the worker established.

    The worker marks a failure definite only when the API server answered with
    an error status, or when its own pre-write check refused (no status). A
    status this mapping does not know stays UNKNOWN_OUTCOME: never claim more
    certainty about a write than the answer carries.
    """
    if status is None:
        return ProviderFailure.PRECONDITION_FAILED
    return {
        400: ProviderFailure.VALIDATION_FAILURE,
        401: ProviderFailure.AUTHENTICATION_FAILURE,
        403: ProviderFailure.AUTHORIZATION_FAILURE,
        404: ProviderFailure.NOT_FOUND,
        409: ProviderFailure.CONFLICT,
        412: ProviderFailure.PRECONDITION_FAILED,
        422: ProviderFailure.PRECONDITION_FAILED,
        429: ProviderFailure.RATE_LIMITED,
        503: ProviderFailure.UNAVAILABLE,
    }.get(status if isinstance(status, int) else -1, ProviderFailure.UNKNOWN_OUTCOME)


#: Phase 11.4 (ADR-124): the rollback envelope is the restart envelope plus the
#: one fact a rollback worker needs that a restart worker never did -- when the
#: authority it was admitted under stops being valid, so a worker holding a
#: lapsed lease refuses to write.
CONTAINED_ROLLBACK_ENVELOPE_FIELDS = CONTAINED_WORKER_ENVELOPE_FIELDS + ("authority_expires_at",)

#: Exactly the arguments the rollback operation takes. Every one is a typed
#: scalar the platform reconstructed; none is a template, a patch, a path or a
#: selector. The worker reads the template itself from the Deployment's own
#: ReplicaSet and writes it only if its digest is the approved one.
ROLLBACK_ARGUMENTS = (
    "namespace", "name", "uid", "expected_generation", "expected_revision",
    "expected_template_digest", "target_revision", "target_template_digest",
    "plan_id", "policy_version",
)


class ContainedRollbackWorkerAdapter(ContainedWorkerAdapter):
    """Dispatches one authorized Deployment rollback to the rollback worker.

    The same seam, the same channel, the same refusal and ambiguity mapping as
    the restart adapter; only the operation, the argument set and the authority
    window differ. A sibling rather than a generalisation: an adapter that could
    carry either operation would be one binding away from carrying both.
    """

    OPERATION = "kubernetes.deployment.rollback"

    def _envelope(self, authority: ProviderAuthority) -> Mapping[str, Any]:
        envelope = dict(super()._envelope(authority))
        payload = dict(authority.payload)
        envelope["arguments"] = {name: payload.get(name) for name in ROLLBACK_ARGUMENTS}
        expires = authority.authority_expires_at
        envelope["authority_expires_at"] = expires.isoformat() if expires is not None else ""
        return envelope

    def _perform(
        self,
        context: Any,
        request: Any,
        authority: ProviderAuthority,
    ) -> ProviderOutcome:
        if authority.operation == self.OPERATION:
            payload = dict(authority.payload)
            missing = [name for name in ROLLBACK_ARGUMENTS
                       if payload.get(name) is None or payload.get(name) == ""]
            if missing:
                return ProviderOutcome.refused(
                    ProviderFailure.VALIDATION_FAILURE,
                    f"the authorized payload does not bind the rollback completely: missing {missing}",
                )
            if authority.authority_expires_at is None:
                return ProviderOutcome.refused(
                    ProviderFailure.VALIDATION_FAILURE,
                    "an execution with no authority window is one no worker could fence",
                )
        return super()._perform(context, request, authority)
