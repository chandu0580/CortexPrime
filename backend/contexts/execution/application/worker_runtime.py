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
4. Select an implementation of that kind from the worker directory —
   deterministically, from declared fields. Zero eligible workers is a refusal;
   two is an *ambiguity* refusal, never a preference.
5. Re-read the selected worker's authoritative state and re-check the selection
   against it. A worker disabled, quarantined or rebuilt since selection is a
   refusal — never a substitution (Phase 3.3.2).
6. Confirm the caller holds the lease. Execution owns leases; a worker never
   takes one.
7. Validate the payload against the bound capability's contract. **No validator
   and a non-empty payload means refuse** — unvalidated input is not accepted
   because validation happens to be unavailable.
8. Invoke, once.
9. Classify whatever comes back, including whatever is raised.

Every one of those failures is a refusal. There is no branch that proceeds
because something was unavailable.

Why the worker is re-read between selecting it and calling it
---------------------------------------------------------------
The gap between "this worker is enabled and trusted" and "this worker is now
performing a production change" is the window an operator uses to stop something.
If the cached selection were trusted, disabling a compromised adapter would not
stop the invocation already on its way to it. So the authoritative entry is read
again, its implementation digest compared, and a mismatch refuses.

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
from backend.contexts.execution.domain.worker_directory import WorkerEntry
from backend.contexts.execution.domain.worker_selection import (
    DEFAULT_SELECTION_TTL_SECONDS,
    WorkerSelection,
    WorkerSelectionRefused,
    WorkerSelectionRequest,
    select_worker,
)
from backend.platform.identity import monotonic_ulid

__all__ = [
    "BindingValidator",
    "WorkerKindPort",
    "WorkerDirectory",
    "InputValidator",
    "CredentialProvider",
    "WorkerAdmission",
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
    """The authoritative record of which implementations exist and their state.

    **Evolved in Phase 3.3.2.** ADR-036 defined this as a single
    ``adapter_for(kind)`` lookup — deliberately minimal, and insufficient once
    workers are real: it could not express a worker being disabled rather than
    absent, could not confine a tenant's registration to that tenant, and offered
    no way to re-read a worker's state between selecting it and calling it. Three
    methods replace it, and the narrow directory is gone rather than kept
    alongside, because two lookup paths is how one of them stops being checked.

    This is **not** a capability registry. It answers "what implementation can
    perform this?", never "what ability exists?" or "who may use it?" — those are
    Connectivity's, and nothing here is consulted about either.

    ``candidates`` returns entries; it does not rank them. ``entry`` is the
    authoritative re-read that closes the TOCTOU window. ``adapter_for`` returns
    the live object by worker id, never by kind — a kind can have several
    implementations and picking one from a kind is exactly the substitution this
    layer refuses.
    """

    def candidates(
        self, context: Any, *, worker_kind: WorkerKind, tenant_id: str
    ) -> tuple: ...

    def entry(
        self, context: Any, *, worker_id: str, tenant_id: str
    ) -> Optional[WorkerEntry]: ...

    def adapter_for(
        self, context: Any, *, worker_id: str, tenant_id: str
    ) -> Optional[Any]: ...


@runtime_checkable
class InputValidator(Protocol):
    """Validates a payload against the bound capability's input contract.

    A seam, not an engine — the platform's schema validation belongs elsewhere
    and this context does not add a second one. Every worker must reach it
    through here: an adapter that validated its own input would be deciding what
    the capability's contract meant, one provider at a time.

    **Absence fails closed.** A request carrying a payload with no validator
    wired is refused. Passing arbitrary caller data to a real provider because
    the checker has not been built yet is exactly the accident this seam exists
    to prevent. An empty payload has nothing to validate and proceeds.
    """

    def validate(
        self, binding: BoundCapability, payload: Mapping[str, Any]
    ) -> tuple: ...


@runtime_checkable
class CredentialProvider(Protocol):
    """The one seam credentials attach through. Implemented in Phase 4.1.

    A capability binding carries authority to *act*; it must never carry the
    secret that proves who is acting. This is where the second thing arrives, and
    it stays outside the worker so no adapter can acquire its own.

    **Widened in Phase 4.1.** It previously took ``(context, binding)``, which was
    not enough to prevent a confused deputy: a binding says which capability was
    chosen, not which *action* was authorized, so a provider given only that could
    return a credential for a different resource within the same capability. It
    now takes the invocation's full authority — the action digest, the
    authorization, the approval, the environment, the deadline — carried by
    ``CredentialRequest``.

    Nothing implemented the old shape, so widening it broke no caller.

    Returns ``IssuedCredential`` (grant + runtime material) or raises
    ``CredentialRefused``. Returning ``None`` is a refusal. There is no answer
    that means "I could not tell, proceed anyway".
    """

    def scoped_credential(self, context: Any, request: Any) -> Any: ...


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
# Admission
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class WorkerAdmission:
    """What passed the gate: one selection, and the adapter it names.

    Returned rather than the bare adapter so the caller records *which
    implementation* ran alongside the result. An audit trail that names only the
    binding cannot answer which build performed it, and that is the question
    asked first when two runs of the same capability behaved differently.
    """

    selection: WorkerSelection
    adapter: Any
    entry: WorkerEntry

    @property
    def worker_id(self) -> str:
        return self.selection.worker_id

    def audit_detail(self) -> dict:
        """Attribution for one invocation. No payload, no credential, no secret."""
        return {
            "selection_id": self.selection.selection_id,
            "selection_digest": self.selection.digest,
            "selection_policy_version": self.selection.policy_version,
            "worker_id": self.selection.worker_id,
            "worker_kind": self.selection.worker_kind.value,
            "worker_version": self.selection.worker_version,
            "worker_digest": self.selection.worker_digest,
            "binding_id": self.selection.binding_id,
            "binding_digest": self.selection.binding_digest,
            "capability_ref": self.selection.capability_ref,
            "capability_digest": self.selection.capability_digest,
            "provider": self.selection.provider,
            "operation": self.selection.operation,
            "environment": self.selection.environment.value,
            "tenant_id": self.selection.tenant_id,
            "principal_id": self.selection.principal_id,
            "execution_id": self.selection.execution_id,
            "node_id": self.selection.node_id,
        }


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
        selection_ttl_seconds: int = DEFAULT_SELECTION_TTL_SECONDS,
    ) -> None:
        self._binding_validator = binding_validator
        self._worker_kinds = worker_kinds
        self._directory = directory
        self._input_validator = input_validator
        self._observer = SafeObserver(observer or NullObserver())
        self._selection_ttl_seconds = selection_ttl_seconds

    # ------------------------------------------------------------------
    # The gate
    # ------------------------------------------------------------------

    def assert_invocable(
        self,
        context: Any,
        request: WorkerExecutionRequest,
        *,
        held_by: Optional[str] = None,
        selection: Optional[WorkerSelection] = None,
        now: Optional[datetime] = None,
    ) -> WorkerAdmission:
        """Every check that must pass before anything runs.

        ``selection`` may be supplied by a dispatcher that selected earlier. It
        is re-checked against the authoritative record either way — a selection
        handed in is a claim about the past, not a permission.
        """
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

        # 4. One implementation, chosen deterministically -- or a refusal.
        if self._directory is None:
            raise WorkerInvocationRefused(
                "worker_unavailable", "no worker directory is wired"
            )
        chosen = selection or self._select(context, kind, binding, now=moment)
        if chosen.worker_kind is not kind:
            raise WorkerInvocationRefused(
                "worker_selection_mismatch",
                f"the supplied selection names a {chosen.worker_kind.value} worker "
                f"but this binding resolves to {kind.value}",
            )

        # 5. TOCTOU. Re-read the authoritative entry; a worker disabled,
        #    quarantined, revoked or rebuilt since selection is a refusal.
        entry = self._directory.entry(
            context, worker_id=chosen.worker_id, tenant_id=request.tenant_id
        )
        stale = chosen.revalidate(entry, binding=binding, now=moment)
        if stale:
            raise WorkerInvocationRefused(
                "worker_selection_invalid",
                f"{chosen.worker_id}: {', '.join(r.value for r in stale)}; execution "
                "refuses rather than selecting another implementation",
            )
        assert entry is not None  # revalidate refuses a missing entry

        adapter = self._directory.adapter_for(
            context, worker_id=chosen.worker_id, tenant_id=request.tenant_id
        )
        if adapter is None:
            # Registered and governed, but nothing is actually wired behind it.
            raise WorkerInvocationRefused(
                "worker_adapter_unavailable",
                f"worker {chosen.worker_id} is enabled but no adapter is attached; "
                "there is no default worker and no substitution",
            )

        # 6. The lease belongs to Execution. A worker never holds one of its own.
        if held_by is not None and held_by != request.principal.principal_id:
            # Advisory identity check; the authoritative lease check lives on the
            # aggregate (Phase 3.1) and runs when the result is recorded.
            log.debug("worker invocation by %s under lease %s", request.principal, held_by)

        # 7. Input validation. Absence fails closed for anything carrying a
        #    payload -- see ``InputValidator``.
        if self._input_validator is None:
            if request.payload:
                raise WorkerInvocationRefused(
                    "input_unvalidatable",
                    "no input validator is wired and the request carries a payload; "
                    "Execution will not hand unchecked caller data to a provider "
                    "because the checker has not been built yet",
                )
        else:
            problems = self._input_validator.validate(binding, request.payload)
            if problems:
                raise WorkerInvocationRefused(
                    "input_invalid", "; ".join(str(p) for p in problems)
                )

        return WorkerAdmission(selection=chosen, adapter=adapter, entry=entry)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def kind_for(self, binding: BoundCapability) -> WorkerKind:
        """The authoritative worker kind for a binding, or a refusal.

        Public so a caller that must build a ``WorkerExecutionRequest`` can ask
        rather than guess. A guessed kind would be checked against this answer
        and refused, so guessing turns every capability of another kind into an
        unexplained refusal — and the caller that guesses is invariably the one
        least able to explain it.

        Resolution stays where ADR-030 put it. This only reaches the existing
        seam and converts what it says.
        """
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
            return WorkerKind(kind_name)
        except ValueError as exc:
            raise WorkerInvocationRefused(
                "worker_kind_unresolved", f"{kind_name!r} is not a worker kind"
            ) from exc

    def select(
        self,
        context: Any,
        binding: BoundCapability,
        *,
        now: Optional[datetime] = None,
    ) -> WorkerSelection:
        """Choose an implementation for a binding, without invoking anything.

        Public so a dispatcher can select before it leases, and so selection can
        be recorded as its own fact. Selecting does not entitle: the selection is
        re-checked against the authoritative record at invocation.
        """
        return self._select(context, self.kind_for(binding), binding, now=now)

    def _select(
        self,
        context: Any,
        kind: WorkerKind,
        binding: BoundCapability,
        *,
        now: Optional[datetime] = None,
    ) -> WorkerSelection:
        if self._directory is None:
            raise WorkerInvocationRefused(
                "worker_unavailable", "no worker directory is wired"
            )
        candidates = self._directory.candidates(
            context, worker_kind=kind, tenant_id=binding.tenant_id
        )
        request = WorkerSelectionRequest.for_binding(worker_kind=kind, binding=binding)
        try:
            return select_worker(
                candidates,
                request,
                selection_id=monotonic_ulid(),
                ttl_seconds=self._selection_ttl_seconds,
                now=now,
            )
        except WorkerSelectionRefused as refused:
            # Translated, never softened. An ambiguity keeps its own reason code
            # because "two workers matched" and "none did" need different fixes.
            raise WorkerInvocationRefused(
                "worker_ambiguous" if refused.is_ambiguous else "worker_unavailable",
                str(refused),
            ) from refused

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------

    def invoke(
        self,
        context: Any,
        request: WorkerExecutionRequest,
        *,
        held_by: Optional[str] = None,
        selection: Optional[WorkerSelection] = None,
        now: Optional[datetime] = None,
        authority: Optional[Any] = None,
    ) -> WorkerExecutionResult:
        """Gate, then invoke exactly once. Never retries, never substitutes.

        ``authority`` is the Phase 4.3 ``ProviderAuthority`` the invocation
        gateway built. It is threaded through rather than reconstructed here:
        this runtime cannot mint an action digest or acquire a credential, and
        an authority assembled at this layer would be one no downstream check
        accepts.

        Passing ``None`` is permitted and is **not** a bypass — a provider
        adapter refuses without one. That is the shape of ADR-042 §4: a caller
        that reaches this method directly, without the gateway, gets a refusal
        from the adapter rather than a provider call.
        """
        started = now or datetime.now(timezone.utc)
        admission = self.assert_invocable(
            context, request, held_by=held_by, selection=selection, now=started
        )
        adapter = admission.adapter

        self._observer.node_assigned(
            str(request.execution_id),
            request.node_id,
            admission.worker_id,
            request.attempt_number,
        )

        try:
            # A declared marker rather than signature probing: exception-driven
            # feature detection would turn a wiring mistake into an ambiguous
            # outcome, and an ambiguous outcome blocks retry on a node that
            # never left this process.
            if getattr(adapter, "CONSUMES_PROVIDER_AUTHORITY", False):
                result = adapter.run(context, request, authority=authority)
            else:
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
            {
                **admission.audit_detail(),
                "known": result.outcome_is_known,
                "result_digest": result.result_digest,
            },
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
