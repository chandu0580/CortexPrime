"""Commissioning a worker: four decisions, four records, no side effects.

The problem this solves
-------------------------
``build_github_connector`` returns a ``WorkerEntry`` at
``REGISTERED``/``UNVERIFIED``/``UNAVAILABLE``, and the composition root
registers it. Nothing then moves it, which is correct — enabling a worker as a
side effect of constructing one is how a wiring change becomes an authority
change.

But "nothing moves it" also meant there was no *governed* way to move it. The
directory exposes ``validate``, ``enable``, ``set_trust`` and
``set_availability`` as four independent calls, and four independent calls with
no ordering between them is a lifecycle in name only: nothing stopped a caller
enabling a worker it had never validated, or trusting one nobody had looked at.

This is the ordering, and the evidence
----------------------------------------
    register    the implementation is recorded. Executes nothing.
    validate    the registered implementation is compared against the digest
                the validator says they reviewed. A flag would be a claim; a
                digest comparison is a check.
    trust       a separate act, by a separate decision, with its own record.
    enable      permitted only once the first three have happened.

``commission`` refuses to skip a step and refuses to compress them. Trust in
particular is not something ``enable`` can grant on the way past: an entry whose
trust is still ``UNVERIFIED`` cannot be enabled here, and establishing trust is a
call a person makes with a stated reason.

What validation actually checks, and what it cannot
-----------------------------------------------------
``WorkerEntry.worker_digest`` is a property that returns
``implementation.digest``, which is itself computed on access from
``identity_payload()``. There is **no stored digest to compare a fresh one
against** — so recomputing it here and checking it equals ``worker_digest``
would compare a value to itself and pass unconditionally. That is worse than no
check: it reads like tamper detection and detects nothing.

So validation takes ``expected_digest`` — what the person validating actually
reviewed. Supplying it makes this a real comparison: two independent sources,
one of them human, and a registered implementation that has changed since the
review no longer matches. Omitting it is permitted and is honestly labelled: the
step **pins** the digest into the returned ``CommissioningStep`` rather than
verifying it, so a later change is at least detectable against the record, and
``digest_verified`` on that step says ``False``.

The distinction is carried in the data rather than in a comment, because a
caller reading ``digest_verified`` is entitled to know which of the two happened.

What this does not do
-----------------------
It does not contact the provider. Validation here is identity validation, not a
health check: a worker that is *who it says it is* may still be unreachable, and
conflating the two would mean a provider outage silently invalidated a
registration. Reachability is ``availability``, which is a separate axis with a
separate call, exactly as ``worker_directory`` documents.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from hmac import compare_digest

from backend.contracts.errors import ContractViolation
from backend.contracts.identity import PrincipalRef
from backend.contexts.execution.domain.worker_directory import (
    WorkerAvailability,
    WorkerLifecycle,
    WorkerTrust,
)
from backend.platform.observability.metrics import NullMetrics, SafeMetrics

__all__ = [
    "CommissioningRefused",
    "CommissioningStep",
    "CommissioningReport",
    "WorkerCommissioning",
    "COMMISSIONING_METRICS",
]

log = logging.getLogger(__name__)

COMMISSIONING_METRICS = (
    "worker.validated",
    "worker.trusted",
    "worker.enabled",
    "worker.commission_refused",
)


class CommissioningRefused(ContractViolation):
    """A commissioning step was refused. Carries a code an operator can act on."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CommissioningStep:
    """One transition, and what it was based on. A fact."""

    step: str
    worker_id: str
    by: str
    reason: str
    detail: dict

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "worker_id": self.worker_id,
            "by": self.by,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class CommissioningReport:
    """What a commissioning run did, step by step."""

    worker_id: str
    tenant_id: str
    steps: tuple
    lifecycle: str
    trust: str
    availability: str
    executable: bool

    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "tenant_id": self.tenant_id,
            "steps": [step.to_dict() for step in self.steps],
            "lifecycle": self.lifecycle,
            "trust": self.trust,
            "availability": self.availability,
            "executable": self.executable,
        }


class WorkerCommissioning:
    """Drives a registered worker to executable. Refuses every shortcut."""

    def __init__(self, *, directory: Any, metrics: Optional[Any] = None) -> None:
        self._directory = directory
        self._metrics = SafeMetrics(metrics or NullMetrics())

    # ------------------------------------------------------------------

    def validate(
        self,
        context: Any,
        *,
        worker_id: str,
        tenant_id: str,
        by: PrincipalRef,
        reason: str,
        expected_digest: Optional[str] = None,
    ) -> CommissioningStep:
        """Move a REGISTERED worker to VALIDATED, against what was reviewed.

        ``expected_digest`` is the digest of the implementation the validator
        actually looked at. When supplied this is a genuine two-source
        comparison and a mismatch refuses; when omitted the step records the
        digest it saw and reports ``digest_verified: False``, because pinning a
        value is not the same as checking one and the record must not imply it
        was.
        """
        entry = self._entry(context, worker_id, tenant_id)
        if entry.lifecycle is not WorkerLifecycle.REGISTERED:
            raise CommissioningRefused(
                "not_registered",
                f"worker {worker_id} is {entry.lifecycle.value}; validation "
                "moves a REGISTERED worker and nothing else",
            )
        self._assert_attributed(by, "validate")

        registered = entry.worker_digest
        verified = False
        if expected_digest is not None:
            if not compare_digest(str(expected_digest), registered):
                self._metrics.increment(
                    "worker.commission_refused", labels={"reason": "digest_mismatch"}
                )
                log.error(
                    "worker %s failed validation: the registered implementation "
                    "is not the one that was reviewed",
                    worker_id,
                )
                raise CommissioningRefused(
                    "digest_mismatch",
                    f"worker {worker_id} hashes to {registered[:12]}..., which is "
                    "not the implementation that was reviewed; validating it "
                    "would attest to something nobody looked at",
                )
            verified = True

        self._directory.validate(context, worker_id=worker_id, tenant_id=tenant_id)
        self._metrics.increment("worker.validated", labels={})
        log.info(
            "worker %s validated by %s: implementation digest %s (%s) -- %s",
            worker_id,
            by.principal_id,
            registered[:12],
            "confirmed against the reviewed digest" if verified
            else "recorded, NOT confirmed against a reviewed digest",
            reason,
        )
        return CommissioningStep(
            step="validate",
            worker_id=worker_id,
            by=by.principal_id,
            reason=reason,
            detail={"digest": registered, "digest_verified": verified},
        )

    def establish_trust(
        self,
        context: Any,
        *,
        worker_id: str,
        tenant_id: str,
        trust: WorkerTrust,
        by: PrincipalRef,
        reason: str,
    ) -> CommissioningStep:
        """Record a trust decision. **Separate from validation, on purpose.**

        Validation says the worker is what it claims. Trust says the platform is
        willing to give it real work. They are different questions with different
        evidence — a correctly-registered connector to a provider nobody has
        reviewed is validated and untrusted, and that state has to be
        expressible.

        Trust is refused on an unvalidated worker: trusting something whose
        identity has not been confirmed is trusting the claim rather than the
        thing.
        """
        entry = self._entry(context, worker_id, tenant_id)
        if entry.lifecycle is WorkerLifecycle.REGISTERED:
            raise CommissioningRefused(
                "not_validated",
                f"worker {worker_id} has not been validated; trusting an "
                "unvalidated worker is trusting its claim about itself",
            )
        if not isinstance(trust, WorkerTrust):
            raise CommissioningRefused("trust_invalid", "trust must be a WorkerTrust")
        self._assert_attributed(by, "establish trust for")
        if not isinstance(reason, str) or len(reason.strip()) < 8:
            raise CommissioningRefused(
                "reason_missing",
                "a trust decision must record why, in enough words to be "
                "reviewable later",
            )

        self._directory.set_trust(
            context,
            worker_id=worker_id,
            tenant_id=tenant_id,
            trust=trust,
            reason=reason,
        )
        self._metrics.increment("worker.trusted", labels={"trust": trust.value})
        log.info(
            "worker %s trust set to %s by %s: %s",
            worker_id,
            trust.value,
            by.principal_id,
            reason,
        )
        return CommissioningStep(
            step="trust",
            worker_id=worker_id,
            by=by.principal_id,
            reason=reason,
            detail={"trust": trust.value},
        )

    def enable(
        self,
        context: Any,
        *,
        worker_id: str,
        tenant_id: str,
        by: PrincipalRef,
        reason: str,
        available: bool = True,
    ) -> CommissioningStep:
        """Make a validated, trusted worker executable. Grants no trust itself.

        The trust check here is the one that makes the four steps four steps: an
        entry whose trust is still withheld cannot be enabled, and this method
        has no argument that would let a caller supply trust on the way past.
        """
        entry = self._entry(context, worker_id, tenant_id)
        if entry.lifecycle is not WorkerLifecycle.VALIDATED:
            raise CommissioningRefused(
                "not_validated",
                f"worker {worker_id} is {entry.lifecycle.value}; only a "
                "VALIDATED worker may be enabled",
            )
        if not entry.trust.permits_execution:
            raise CommissioningRefused(
                "trust_withheld",
                f"worker {worker_id} is {entry.trust.value}; trust is a separate "
                "decision and enabling does not grant it",
            )
        self._assert_attributed(by, "enable")

        self._directory.enable(context, worker_id=worker_id, tenant_id=tenant_id)
        if available:
            # Availability is the third axis and it is set explicitly. A worker
            # that is enabled but unavailable is a correct, reachable state --
            # "allowed to run, currently not answering" -- and enabling must not
            # silently assert reachability it has not observed.
            self._directory.set_availability(
                context,
                worker_id=worker_id,
                tenant_id=tenant_id,
                availability=WorkerAvailability.AVAILABLE,
            )
        self._metrics.increment("worker.enabled", labels={})
        log.info("worker %s enabled by %s: %s", worker_id, by.principal_id, reason)
        return CommissioningStep(
            step="enable",
            worker_id=worker_id,
            by=by.principal_id,
            reason=reason,
            detail={"available": available},
        )

    # ------------------------------------------------------------------

    def commission(
        self,
        context: Any,
        *,
        worker_id: str,
        tenant_id: str,
        trust: WorkerTrust,
        by: PrincipalRef,
        reason: str,
        available: bool = True,
        expected_digest: Optional[str] = None,
    ) -> CommissioningReport:
        """Run all three steps in order. A convenience, not a shortcut.

        Every check each individual step makes still runs, in the same order,
        with the same refusals. What this saves is three call sites, not three
        decisions — and the report names each step separately so an audit sees
        three records rather than one.
        """
        steps = [
            self.validate(
                context,
                worker_id=worker_id,
                tenant_id=tenant_id,
                by=by,
                reason=reason,
                expected_digest=expected_digest,
            ),
            self.establish_trust(
                context,
                worker_id=worker_id,
                tenant_id=tenant_id,
                trust=trust,
                by=by,
                reason=reason,
            ),
            self.enable(
                context,
                worker_id=worker_id,
                tenant_id=tenant_id,
                by=by,
                reason=reason,
                available=available,
            ),
        ]
        entry = self._entry(context, worker_id, tenant_id)
        return CommissioningReport(
            worker_id=worker_id,
            tenant_id=tenant_id,
            steps=tuple(steps),
            lifecycle=entry.lifecycle.value,
            trust=entry.trust.value,
            availability=entry.availability.value,
            executable=entry.is_executable,
        )

    def status(self, context: Any, *, worker_id: str, tenant_id: str) -> dict:
        entry = self._entry(context, worker_id, tenant_id)
        return {
            "worker_id": worker_id,
            "tenant_id": tenant_id,
            "lifecycle": entry.lifecycle.value,
            "trust": entry.trust.value,
            "availability": entry.availability.value,
            "executable": entry.is_executable,
            # The digest as registered. There is deliberately no
            # ``digest_verified`` here: whether it matches what a human reviewed
            # is answered by the validation step that compared them, and
            # recomputing it at read time would compare the value to itself.
            "digest": entry.worker_digest,
        }

    # ------------------------------------------------------------------

    def _entry(self, context: Any, worker_id: str, tenant_id: str) -> Any:
        entry = self._directory.entry(
            context, worker_id=worker_id, tenant_id=tenant_id
        )
        if entry is None:
            raise CommissioningRefused(
                "not_registered",
                f"no worker {worker_id} is registered for {tenant_id}",
            )
        return entry

    @staticmethod
    def _assert_attributed(by: Any, verb: str) -> None:
        if not isinstance(by, PrincipalRef):
            raise CommissioningRefused(
                "unattributed",
                f"a decision to {verb} a worker must name who made it; an "
                "unattributed commissioning is one nobody can be asked about",
            )
