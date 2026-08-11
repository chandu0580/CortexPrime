"""A deterministic provider adapter, for proving the architecture. Never production.

What it is for
----------------
Every gate in this fabric is exercised only up to the first refusal unless
something can answer. With no adapter that returns, the paths *after* a
successful authority check — result normalisation, effect comparison, evidence
digesting, ambiguity handling — stay unexercised, and an unexercised failure
path is a failure path nobody has read.

So this answers, from a script, with no network.

What it is not for
--------------------
It proves the **authority chain**, not the transport. It performs no dial, so it
demonstrates nothing about TLS, address policy, DNS pinning or resource budgets;
for those, wire a real ``ProviderChannel`` to Phase 4.2's ``DevelopmentTransport``,
which sits behind the broker and therefore goes through every one of them.

Saying that plainly matters more than the code below. A test double described as
"proving the adapter works" is how a deployment ends up believing a path was
checked that never was.

Why it still runs every gate
------------------------------
It is an ``AdapterSeam`` like any other, so it inherits the whole gate: it
refuses without gateway authority, refuses a stale or cancelled one, refuses
without credential material minted for this action's digest, refuses input the
operation does not declare, and its declared effect is compared against the
binding. A double that skipped those would be testing a different adapter than
the one production runs, which is worse than no double at all.

Named for what it is
----------------------
``TestProviderAdapter``, and it refuses ``PRODUCTION`` at construction and again
at every invocation. A scripted adapter reaching production would make every
provider look reachable and every action look performed — the most dangerous
possible failure for an execution engine, because it is silent.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Tuple

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionEnvironment
from backend.contracts.provider import ProviderDelivery, ProviderFailure, ProviderRef
from backend.contexts.execution.domain.provider_invocation import ProviderAuthority
from backend.contexts.execution.domain.provider_operation import (
    OperationCatalog,
    UnknownOperation,
)
from backend.contexts.execution.domain.worker import WorkerKind
from backend.contexts.execution.domain.worker_contract import WorkerExecutionRequest
from backend.contexts.execution.domain.worker_directory import (
    WorkerImplementation,
    WorkerInterface,
)
from backend.contexts.execution.infrastructure.adapters.base import (
    AdapterPreflight,
    AdapterSeam,
    ProviderOutcome,
)
from backend.platform.hashing import compute_digest

__all__ = ["TestProviderAdapter", "ScriptedResponse"]


class ScriptedResponse(dict):
    """What the script returns for one operation. A dict, so it stays obvious.

    Keys: ``body`` (mapping), ``failure`` (``ProviderFailure``), ``message``,
    ``observed_effect`` (``SideEffectClass``), ``ambiguous`` (bool). Anything
    absent takes the safe default, which for ``failure`` means success and for
    ``ambiguous`` means no.
    """


class TestProviderAdapter(AdapterSeam):
    """A scripted provider adapter. **Never registered in production.**"""

    WORKER_KIND = WorkerKind.CONNECTOR
    INTERFACE = WorkerInterface.CONNECTOR
    IMPLEMENTATION_VERSION = "0.0.0-test"

    REQUIRES_CREDENTIAL = True
    """Kept ``True`` deliberately. The point of this adapter is to exercise the
    chain, and an exercise that skipped the credential check would exercise a
    shorter chain than production runs."""

    def __init__(
        self,
        *,
        implementation: WorkerImplementation,
        provider: ProviderRef,
        catalog: OperationCatalog,
        allow_non_production: bool,
        responder: Optional[Callable[[ProviderAuthority], Mapping[str, Any]]] = None,
        environments: Optional[frozenset] = None,
        preflight: Optional[AdapterPreflight] = None,
        metrics: Optional[Any] = None,
    ) -> None:
        if allow_non_production is not True:
            raise ContractViolation(
                "TestProviderAdapter requires allow_non_production=True to be "
                "passed explicitly. A scripted adapter reaching production would "
                "make every action look performed, silently"
            )
        allowed = frozenset(
            environments
            or {ExecutionEnvironment.DEVELOPMENT, ExecutionEnvironment.STAGING}
        )
        if ExecutionEnvironment.PRODUCTION in allowed:
            raise ContractViolation(
                "TestProviderAdapter cannot serve PRODUCTION; it contacts nothing "
                "and answers from a script"
            )
        if ExecutionEnvironment.PRODUCTION in implementation.supported_environments:
            # The registration is what worker selection reads. A test adapter
            # registered for production would be *selected* for production work
            # regardless of what this object then refuses.
            raise ContractViolation(
                "a test adapter must not be registered for production; selection "
                "reads the registration, not this constructor's opinion of it"
            )
        super().__init__(
            implementation=implementation,
            provider=provider,
            # Its own script is its transport. Non-``None`` so the seam's
            # "nothing is wired" refusal does not fire, and deliberately not an
            # object that could reach a network.
            invoker=responder or (lambda authority: {}),
            preflight=preflight,
            metrics=metrics,
        )
        if catalog.provider_id != provider.provider_id:
            raise ContractViolation(
                "the catalog describes a different provider than this adapter serves"
            )
        self._catalog = catalog
        self._environments = allowed
        self._responder = responder
        self._calls: list = []

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    @property
    def calls(self) -> Tuple[dict, ...]:
        """What this adapter was asked to do. Attribution only, never payloads.

        Records ``audit_detail`` rather than the authority itself: holding the
        authority would hold the credential, and a test double accumulating
        credentials across a run is the one thing a test double must not do.
        """
        return tuple(self._calls)

    def supports_operation(self, operation: str) -> bool:
        return operation in self._catalog

    # ------------------------------------------------------------------
    # The scripted call
    # ------------------------------------------------------------------

    def _perform(
        self,
        context: Any,
        request: WorkerExecutionRequest,
        authority: ProviderAuthority,
    ) -> ProviderOutcome:
        # Asserted again at the point of use. A construction-time check alone is
        # bypassable by anything that mutates the attribute afterwards.
        if authority.environment is ExecutionEnvironment.PRODUCTION:
            return ProviderOutcome.refused(
                ProviderFailure.ADAPTER_UNAVAILABLE,
                "the test provider adapter does not serve production",
            )
        if authority.environment not in self._environments:
            return ProviderOutcome.refused(
                ProviderFailure.ADAPTER_UNAVAILABLE,
                "the test provider adapter is not registered for this environment",
            )

        try:
            spec = self._catalog.require(authority.operation)
        except UnknownOperation as unknown:
            return ProviderOutcome.refused(
                ProviderFailure.OPERATION_NOT_SUPPORTED, str(unknown)[:400]
            )

        drift = spec.contract_refusals(authority.binding)
        if drift:
            return ProviderOutcome.refused(
                ProviderFailure.CONTRACT_MISMATCH, "; ".join(drift)[:400]
            )
        problems = spec.input_problems(authority.payload)
        if problems:
            return ProviderOutcome.refused(
                ProviderFailure.VALIDATION_FAILURE, "; ".join(problems)[:400]
            )

        # Built and discarded. Constructing it proves the plan is buildable and
        # deterministic for this input, which is most of what a caller wants to
        # know before wiring a real channel.
        plan = spec.plan(authority.payload, idempotency_key=authority.idempotency_key)
        self._calls.append(
            {**authority.audit_detail(), **plan.to_dict(), "spec_digest": spec.digest}
        )

        scripted = dict(self._responder(authority)) if self._responder else {}

        failure = scripted.get("failure")
        if failure is not None:
            if not isinstance(failure, ProviderFailure):
                raise ContractViolation(
                    "a scripted failure must be a ProviderFailure; a string here "
                    "would make the double's vocabulary differ from production's"
                )
            return ProviderOutcome(
                provider_failure=failure,
                ambiguous=bool(scripted.get("ambiguous", failure.is_ambiguous)),
                error_message=str(scripted.get("message") or "scripted failure")[:400],
                delivery=(
                    ProviderDelivery.NOT_ATTEMPTED
                    if failure.is_definitely_not_applied
                    else ProviderDelivery.UNKNOWN
                ),
                metadata={"scripted": True},
            )

        body = scripted.get("body")
        body = dict(body) if isinstance(body, Mapping) else {}
        shape = spec.response_problems(body)
        if shape:
            # The double is held to the same response contract as a real
            # provider. A script that returns the wrong shape should fail here,
            # because that is what production would do.
            return ProviderOutcome(
                ambiguous=True,
                provider_failure=ProviderFailure.MALFORMED_RESPONSE,
                error_message="; ".join(shape)[:400],
                delivery=ProviderDelivery.DELIVERED,
                metadata={"scripted": True},
            )

        return ProviderOutcome(
            succeeded=True,
            output=body,
            evidence=spec.evidence(body),
            observed_effect=scripted.get("observed_effect", spec.side_effect_class),
            delivery=ProviderDelivery.DELIVERED,
            response_digest=compute_digest(body).value,
            status_code=int(scripted.get("status", 200)),
            metadata={"scripted": True},
        )

    def __repr__(self) -> str:
        return (
            f"<TestProviderAdapter {self.provider.provider_id} "
            f"operations={len(self._catalog)} NON-PRODUCTION>"
        )
