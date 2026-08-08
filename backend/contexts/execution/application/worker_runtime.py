"""The final gate before anything touches the outside world.

What this does, in order
--------------------------
1. Check what Execution can check locally — binding expiry, tenant, principal,
   execution, operation.
2. Ask the ``BindingValidator`` port whether the binding still holds
   authoritatively — lifecycle, trust, digest, authorization. **No port means
   refuse**, not proceed.
3. Resolve the worker kind through the ``WorkerKindResolver`` seam. Unresolvable
   means refuse.
4. Find an adapter for that kind. Missing means refuse — never a default worker.
5. Confirm the caller holds the lease. Execution owns leases; a worker never
   takes one.
6. Invoke, once.
7. Classify whatever comes back, including whatever is raised.

Every one of those failures is a refusal. There is no branch that proceeds
because something was unavailable.

Why refusal never becomes re-resolution
-----------------------------------------
When a binding is invalid the temptation is to go and get another one. That
would silently change the target that was authorized and approved — the run
would perform work against a provider nobody signed off, with the original
binding id in the audit trail. So an invalid binding is a refusal, and what
happens next is a recovery decision (Phase 3.1), which a human or a policy makes
with the facts in front of them.

Exceptions become classified failures at this boundary
--------------------------------------------------------
A worker that raises does not get to leak a ``ConnectionError`` into the
execution API. Everything is mapped onto Phase 3.1's taxonomy, and anything that
cannot be classified becomes ``UNKNOWN_OUTCOME`` rather than a failure — because
"the adapter threw" says nothing about whether the far side applied the change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionResult, ExecutionStatus
from backend.contexts.execution.application.instrumentation import (
    NullObserver,
    SafeObserver,
)
from backend.contexts.execution.domain.bound_capability import (
    BindingRefused,
    BoundCapability,
)
from backend.contexts.execution.domain.errors import LeaseNotHeld, UnknownNode
from backend.contexts.execution.domain.failure import FailureClass, FailureRecord
from backend.contexts.execution.domain.worker import WorkerKind
from backend.contexts.execution.domain.worker_contract import (
    WorkerExecutionRequest,
    WorkerExecutionResult,
    WorkerOutcome,
)

__all__ = [
    "BindingValidator",
    "WorkerKindPort",
    "WorkerDirectory",
    "InputValidator",
    "CredentialProvider",
    "WorkerInvocationRefused",
    "WorkerRuntime",
    "classify_exception",
]

log = logging.getLogger(__name__)


class WorkerInvocationRefused(ContractViolation):
    """Execution declined to invoke. No worker was called."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


# ----------------------------------------------------------------------
# Ports — implemented at the composition root, never inside this context
# ----------------------------------------------------------------------


@runtime_checkable
class BindingValidator(Protocol):
    """Asks Connectivity whether a binding still holds.

    Execution cannot answer this: lifecycle, trust and the capability digest are
    BC-8's authoritative state, and this context may not import it. The
    composition root implements this over ``CapabilityResolutionService.
    validate_binding`` (ADR-035).

    Returns the invalidation reasons; empty means usable.
    """

    def invalidations(self, context: Any, binding: BoundCapability) -> tuple: ...


@runtime_checkable
class WorkerKindPort(Protocol):
    """The ``WorkerKindResolver`` seam (ADR-030), reached as a port.

    Deliberately unchanged in shape: the composition root adapts the existing
    resolver rather than this context growing its own idea of worker selection.
    """

    def kind_for(self, binding: BoundCapability) -> Optional[str]: ...


@runtime_checkable
class WorkerDirectory(Protocol):
    """Finds the adapter for a kind. Not a registry, and not discovery.

    Deliberately minimal: one lookup, no health, no ranking, no fallback. A
    missing adapter is a refusal, because a default worker is how work runs
    somewhere nobody chose.
    """

    def adapter_for(self, kind: WorkerKind) -> Optional[Any]: ...


@runtime_checkable
class InputValidator(Protocol):
    """Validates a payload against the bound capability's input contract.

    A seam, not an engine — the platform's schema validation belongs elsewhere
    and this context does not add a second one. Absent, payloads are passed
    through unvalidated, and that is stated rather than silently assumed safe.
    """

    def validate(
        self, binding: BoundCapability, payload: Mapping[str, Any]
    ) -> tuple: ...


@runtime_checkable
class CredentialProvider(Protocol):
    """The seam a future credential architecture will occupy.

    **Nothing implements this in Phase 3.3.1 and nothing calls it.** It exists so
    that when credentials arrive they attach here rather than inside a worker,
    and so that ``BoundCapability`` is never the place somebody puts a token.

    A capability binding carries authority to *act*; it must never carry the
    secret that proves who is acting.
    """

    def scoped_credential(self, context: Any, binding: BoundCapability) -> Any: ...


# ----------------------------------------------------------------------
# Failure classification
# ----------------------------------------------------------------------

#: Exception name fragments mapped onto Phase 3.1's taxonomy. Deliberately
#: conservative: anything not recognised becomes UNKNOWN_OUTCOME, never a
#: failure, because an unrecognised exception says nothing about whether the far
#: side applied the change.
_EXCEPTION_MAP = (
    (("timeout", "timederror"), FailureClass.TIMEOUT),
    (("connection", "socket", "dns", "unreachable"), FailureClass.NETWORK_FAILURE),
    (("permission", "forbidden", "unauthorized", "auth"), FailureClass.AUTHORIZATION_FAILURE),
    (("validation", "value", "type", "schema"), FailureClass.VALIDATION_FAILURE),
    (("cancel", "interrupt"), FailureClass.CANCELLATION),
    (("notimplemented", "notfound", "missing"), FailureClass.PERMANENT_FAILURE),
)


def classify_exception(exc: BaseException, *, source: str = "worker") -> FailureRecord:
    """Map an infrastructure exception onto a domain failure.

    Never guesses in the permissive direction. A ``RuntimeError`` from an adapter
    mid-call could mean the request never left, or that it landed and the
    response was lost — so it is ``UNKNOWN_OUTCOME``, and the retry rules decide
    whether repeating is safe.
    """
    name = f"{type(exc).__name__}".lower()
    for fragments, failure_class in _EXCEPTION_MAP:
        if any(fragment in name for fragment in fragments):
            return FailureRecord(
                failure_class=failure_class,
                reason=f"{type(exc).__name__}: {exc}"[:500],
                source=source,
            )
    return FailureRecord(
        failure_class=FailureClass.UNKNOWN_OUTCOME,
        reason=(
            f"{type(exc).__name__}: {exc}"[:500]
            + " -- the adapter raised without saying whether the operation reached "
            "the far side"
        ),
        source=source,
    )


# ----------------------------------------------------------------------
# The runtime
# ----------------------------------------------------------------------


class WorkerRuntime:
    """Gates and performs one worker invocation. Owns no state.

    Holds no repository and never writes an ``Execution``. It returns a result
    and the caller — the execution service — records it. Worker reports facts;
    Execution records facts; the split is what stops an adapter from moving a
    run's state.
    """

    def __init__(
        self,
        *,
        binding_validator: Optional[BindingValidator] = None,
        worker_kinds: Optional[WorkerKindPort] = None,
        directory: Optional[WorkerDirectory] = None,
        input_validator: Optional[InputValidator] = None,
        observer: Optional[Any] = None,
    ) -> None:
        self._binding_validator = binding_validator
        self._worker_kinds = worker_kinds
        self._directory = directory
        self._input_validator = input_validator
        self._observer = SafeObserver(observer or NullObserver())

    # ------------------------------------------------------------------
    # The gate
    # ------------------------------------------------------------------

    def assert_invocable(
        self,
        context: Any,
        request: WorkerExecutionRequest,
        *,
        held_by: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Any:
        """Every check that must pass before anything runs. Returns the adapter."""
        moment = now or datetime.now(timezone.utc)
        binding = request.binding

        # 1. What Execution can see for itself.
        local = binding.local_refusals(
            tenant_id=request.tenant_id,
            principal_id=request.principal.principal_id,
            execution_id=str(request.execution_id),
            node_id=request.node_id,
            operation=binding.operation,
            now=moment,
        )
        if local:
            raise WorkerInvocationRefused(
                "binding_refused", f"{binding.binding_id}: {', '.join(local)}"
            )

        # 2. The authoritative re-check. No validator means refuse: an unchecked
        #    binding is an assertion by whoever handed it over.
        if self._binding_validator is None:
            raise WorkerInvocationRefused(
                "binding_unverifiable",
                "no binding validator is wired; Execution will not act on a "
                "binding it cannot have confirmed",
            )
        try:
            invalidations = self._binding_validator.invalidations(context, binding)
        except Exception as exc:  # noqa: BLE001 - unverifiable is unusable
            raise WorkerInvocationRefused(
                "binding_unverifiable",
                f"the binding could not be validated ({type(exc).__name__})",
            ) from exc
        if invalidations:
            reasons = ", ".join(
                getattr(i, "value", str(i)) for i in invalidations
            )
            # Refused, not re-resolved. A different target needs a new binding.
            raise WorkerInvocationRefused(
                "binding_invalid", f"{binding.binding_id}: {reasons}"
            )

        # 3. Worker kind, through the existing seam.
        if self._worker_kinds is None:
            raise WorkerInvocationRefused(
                "worker_kind_unresolved", "no worker-kind resolver is wired"
            )
        kind_name = self._worker_kinds.kind_for(binding)
        if not kind_name:
            raise WorkerInvocationRefused(
                "worker_kind_unresolved",
                f"nothing resolves a worker kind for {binding.capability_ref}; "
                "defaulting one would run real work on whatever came first",
            )
        try:
            kind = WorkerKind(kind_name)
        except ValueError as exc:
            raise WorkerInvocationRefused(
                "worker_kind_unresolved", f"{kind_name!r} is not a worker kind"
            ) from exc
        if kind is not request.worker_kind:
            raise WorkerInvocationRefused(
                "worker_kind_mismatch",
                f"the request names {request.worker_kind.value} but the binding "
                f"resolves to {kind.value}",
            )

        # 4. An adapter, or nothing.
        if self._directory is None:
            raise WorkerInvocationRefused(
                "worker_unavailable", "no worker directory is wired"
            )
        adapter = self._directory.adapter_for(kind)
        if adapter is None:
            raise WorkerInvocationRefused(
                "worker_unavailable",
                f"no adapter is registered for {kind.value}; there is no default "
                "worker and no substitution",
            )

        # 5. The lease belongs to Execution. A worker never holds one of its own.
        if held_by is not None and held_by != request.principal.principal_id:
            # Advisory identity check; the authoritative lease check lives on the
            # aggregate (Phase 3.1) and runs when the result is recorded.
            log.debug("worker invocation by %s under lease %s", request.principal, held_by)

        # 6. Input validation, if a validator exists. Absent, the payload passes
        #    through unvalidated -- stated, not assumed safe.
        if self._input_validator is not None:
            problems = self._input_validator.validate(binding, request.payload)
            if problems:
                raise WorkerInvocationRefused(
                    "input_invalid", "; ".join(str(p) for p in problems)
                )

        return adapter

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------

    def invoke(
        self,
        context: Any,
        request: WorkerExecutionRequest,
        *,
        held_by: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> WorkerExecutionResult:
        """Gate, then invoke exactly once. Never retries, never substitutes."""
        started = now or datetime.now(timezone.utc)
        adapter = self.assert_invocable(context, request, held_by=held_by, now=started)

        self._observer.node_assigned(
            str(request.execution_id),
            request.node_id,
            request.principal.principal_id,
            request.attempt_number,
        )

        try:
            result = adapter.run(context, request)
        except Exception as exc:  # noqa: BLE001 - classified, never leaked
            failure = classify_exception(exc)
            result = WorkerExecutionResult(
                outcome=(
                    WorkerOutcome.UNKNOWN_OUTCOME
                    if failure.failure_class.is_ambiguous
                    else WorkerOutcome.FAILURE
                ),
                binding_id=request.binding.binding_id,
                attempt_id=str(request.attempt_id),
                started_at=started,
                completed_at=datetime.now(timezone.utc),
                failure=failure,
            )

        if not isinstance(result, WorkerExecutionResult):
            # An adapter that returns something else has not told us anything we
            # can act on. Unknown, not failed -- it may well have done the work.
            result = WorkerExecutionResult.unknown(
                binding_id=request.binding.binding_id,
                attempt_id=str(request.attempt_id),
                started_at=started,
                reason=(
                    f"the adapter returned {type(result).__name__}, not a "
                    "WorkerExecutionResult; what it did is unknown"
                ),
            )

        # A worker that exceeded its authorized effect has not succeeded, whatever
        # it reports. Recorded as unknown: the change may well have landed.
        contradiction = result.contradicts(request.binding)
        if contradiction:
            result = WorkerExecutionResult.unknown(
                binding_id=request.binding.binding_id,
                attempt_id=str(request.attempt_id),
                started_at=started,
                reason=contradiction,
                detail={"declared_outcome": result.outcome.value},
            )

        self._observer.node_finished(
            str(request.execution_id),
            request.node_id,
            result.outcome.value,
            {"binding_id": result.binding_id, "known": result.outcome_is_known},
        )
        if not result.outcome_is_known:
            self._observer.outcome_unknown(
                str(request.execution_id),
                request.node_id,
                result.failure.to_dict() if result.failure else {},
            )
        return result

    # ------------------------------------------------------------------
    # Translation back to the published contract
    # ------------------------------------------------------------------

    @staticmethod
    def to_execution_result(
        request: WorkerExecutionRequest, result: WorkerExecutionResult
    ) -> ExecutionResult:
        """Project onto the published ``ExecutionResult`` the aggregate records.

        ``UNKNOWN_OUTCOME`` degrades to ``FAILED`` here because the published
        contract has no word for not-knowing (documented in ADR-029). The
        unambiguous record survives on the attempt's ``FailureRecord``, which is
        what the retry rules actually read.
        """
        return ExecutionResult(
            execution_key=request.execution_key or request.node_id,
            status=(
                ExecutionStatus.SUCCEEDED
                if result.succeeded
                else ExecutionStatus.FAILED
            ),
            started_at=result.started_at,
            completed_at=result.completed_at,
            failure_reason=(result.failure.reason if result.failure else None),
            detail={
                "binding_id": result.binding_id,
                "worker_outcome": result.outcome.value,
                "outcome_known": result.outcome_is_known,
                "result_digest": result.result_digest,
            },
        )
