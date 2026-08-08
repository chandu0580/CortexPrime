"""The Verification application service.

Where the aggregate's per-claim invariants meet the policy's whole-record
judgement and the repository's facts.

Events are returned, never published. This context owns no bus, and reaching for
one would couple it to infrastructure it has no business knowing about -- the
same arrangement as the WorkOrder context in ADR-019.

The outcome is **derived, never chosen**
----------------------------------------
``close`` asks the policy what the record has earned and closes as that. A caller
cannot pass the outcome it would prefer. The single exception is
``invalidated``, which policy cannot see: it means an approved premise turned out
false, which is a fact about the WorkOrder rather than about any claim.

That asymmetry is the whole point. If a caller could close a verification as
complete, "verification" would be a field someone sets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantRef, TenantScope
from backend.contexts.engineering_verification.application.commands import (
    AddEvidence,
    CloseVerification,
    GetOutcome,
    GetVerification,
    ListVerifications,
    MarkStale,
    RecordClaimResult,
    RequestVerification,
    StartVerification,
    SupersedeVerification,
)
from backend.contexts.engineering_verification.domain.claim import (
    Claim,
    ClaimType,
    Determinism,
    ReproductionMethod,
    ReproductionStep,
)
from backend.contexts.engineering_verification.domain.errors import (
    VerificationNotFound,
)
from backend.contexts.engineering_verification.domain.events import (
    AGGREGATE_TYPE,
    VerificationEvidenceAdded,
    VerificationFailed,
    VerificationRequested,
    VerificationStarted,
    VerificationSucceeded,
    VerificationSuperseded,
)
from backend.contexts.engineering_verification.domain.evidence import (
    AssertedEvidenceRef,
    EvidenceKind,
    TrustLevel,
    VerifiedEvidence,
)
from backend.contexts.engineering_verification.domain.identifiers import (
    ClaimId,
    VerificationId,
)
from backend.contexts.engineering_verification.domain.policy import (
    VerificationPolicy,
    default_policy,
)
from backend.contexts.engineering_verification.domain.record import (
    VerificationRecord,
    VerificationRequest as DomainRequest,
    VerificationStatus,
)
from backend.contexts.engineering_verification.domain.results import (
    ClaimResult,
    ClaimVerdict,
)
from backend.platform.events import EventMetadata

__all__ = ["VerificationService", "CommandResult"]


@dataclass(frozen=True)
class CommandResult:
    record: VerificationRecord
    events: tuple

    @property
    def event_types(self) -> tuple:
        return tuple(getattr(type(e), "EVENT_TYPE", "?") for e in self.events)


class VerificationService:
    def __init__(self, repository: Any, policy: Optional[VerificationPolicy] = None) -> None:
        self._repository = repository
        self._policy = policy or default_policy()

    @property
    def policy(self) -> VerificationPolicy:
        return self._policy

    # ------------------------------------------------------------------

    @staticmethod
    def _metadata(context: Any, record: VerificationRecord, **attributes: Any) -> EventMetadata:
        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=context.tenant_id))
        return EventMetadata.create(
            aggregate_id=str(record.verification_id),
            aggregate_type=AGGREGATE_TYPE,
            scope=scope,
            attributes=attributes or None,
        )

    def _load(self, context: Any, verification_id: str) -> VerificationRecord:
        found = self._repository.find(context, VerificationId(verification_id))
        if found is None:
            raise VerificationNotFound(verification_id)
        return found

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def request(self, context: Any, command: RequestVerification) -> CommandResult:
        claims = tuple(
            Claim.create(
                item.statement,
                ClaimType(item.claim_type),
                asserted_evidence=tuple(item.asserted_evidence),
                reproduction_hint=item.hint,
            )
            for item in command.claims
        )
        record = VerificationRecord(
            verification_id=VerificationId.new(),
            request=DomainRequest(
                work_id=command.work_id,
                attempt=command.attempt,
                claims=claims,
                base_commit=command.base_commit,
                requested_by=command.requested_by,
            ),
        )
        self._repository.save(context, record)
        return CommandResult(
            record=record,
            events=(
                VerificationRequested(
                    metadata=self._metadata(context, record),
                    verification_id=str(record.verification_id),
                    work_id=record.work_id,
                    attempt=record.attempt,
                    claim_count=len(claims),
                    base_commit=record.base_commit,
                ),
            ),
        )

    def start(self, context: Any, command: StartVerification) -> CommandResult:
        record = self._load(context, command.verification_id).start(command.verifier)
        self._repository.replace(context, record)
        return CommandResult(
            record=record,
            events=(
                VerificationStarted(
                    metadata=self._metadata(context, record),
                    verification_id=str(record.verification_id),
                    work_id=record.work_id,
                    attempt=record.attempt,
                    verifier=record.verifier or "",
                ),
            ),
        )

    def record_result(self, context: Any, command: RecordClaimResult) -> CommandResult:
        """Record one verdict, building the verifier's own evidence as it goes."""
        record = self._load(context, command.verification_id)

        claim_id = ClaimId(command.claim_id)
        target = next(
            (c for c in record.request.claims if c.claim_id == claim_id), None
        )
        if target is None:
            from backend.contexts.engineering_verification.domain.errors import (
                ClaimNotRequested,
            )

            raise ClaimNotRequested(
                claim_id=command.claim_id, verification_id=command.verification_id
            )

        verdict = ClaimVerdict(command.verdict)

        if verdict is ClaimVerdict.OUT_OF_SCOPE:
            result = ClaimResult(
                claim=target,
                reproduction=ReproductionStep(
                    method=ReproductionMethod.SOURCE_INSPECTION,
                    specification=command.specification or "not examined",
                ),
                observed=command.observed,
                verdict=verdict,
                note=command.note,
            )
            evidence = None
        else:
            evidence = VerifiedEvidence.create(
                EvidenceKind(command.evidence_kind),
                TrustLevel(command.evidence_trust),
                command.evidence_summary,
                collected_by=command.collected_by,
                base_commit=command.evidence_base_commit or record.base_commit,
            )
            result = ClaimResult(
                claim=target,
                reproduction=ReproductionStep(
                    method=ReproductionMethod(command.method),
                    specification=command.specification,
                    determinism=Determinism(command.determinism),
                    runs=command.runs,
                ),
                observed=command.observed,
                verdict=verdict,
                verdict_evidence=evidence,
                note=command.note,
            )

        updated = record.record(result)
        self._repository.replace(context, updated)

        events: list = []
        if evidence is not None:
            events.append(
                VerificationEvidenceAdded(
                    metadata=self._metadata(context, updated),
                    verification_id=str(updated.verification_id),
                    work_id=updated.work_id,
                    evidence_id=str(evidence.evidence_id),
                    kind=evidence.kind.value,
                    trust=evidence.trust.value,
                    claim_id=str(target.claim_id),
                )
            )
        return CommandResult(record=updated, events=tuple(events))

    def add_evidence(self, context: Any, command: AddEvidence) -> CommandResult:
        record = self._load(context, command.verification_id)
        evidence = VerifiedEvidence.create(
            EvidenceKind(command.kind),
            TrustLevel(command.trust),
            command.summary,
            collected_by=command.collected_by,
            base_commit=command.base_commit or record.base_commit,
            detail=command.detail,
        )
        updated = record.add_evidence(evidence)
        self._repository.replace(context, updated)
        return CommandResult(
            record=updated,
            events=(
                VerificationEvidenceAdded(
                    metadata=self._metadata(context, updated),
                    verification_id=str(updated.verification_id),
                    work_id=updated.work_id,
                    evidence_id=str(evidence.evidence_id),
                    kind=evidence.kind.value,
                    trust=evidence.trust.value,
                    claim_id="",
                ),
            ),
        )

    def close(self, context: Any, command: CloseVerification) -> CommandResult:
        """Close with the outcome the record has earned.

        The outcome is derived from policy, not supplied. A caller able to close a
        verification as complete would make "verification" a field someone sets.
        """
        record = self._load(context, command.verification_id)
        report = self._policy.evaluate(record, current_commit=command.current_commit)

        if command.force_outcome == "invalidated":
            outcome = VerificationStatus.INVALIDATED
            note = command.note
        else:
            outcome = report.outcome
            note = command.note or (
                "; ".join(f.detail for f in report.blocking[:3]) if report.blocking else None
            )

        closed = record.close(outcome, note)
        self._repository.replace(context, closed)

        if outcome is VerificationStatus.COMPLETE:
            weakest = closed.weakest_trust
            event = VerificationSucceeded(
                metadata=self._metadata(context, closed),
                verification_id=str(closed.verification_id),
                work_id=closed.work_id,
                attempt=closed.attempt,
                claims_reproduced=closed.count(ClaimVerdict.REPRODUCED),
                claims_out_of_scope=closed.count(ClaimVerdict.OUT_OF_SCOPE),
                weakest_trust=weakest.value if weakest else "",
            )
        else:
            event = VerificationFailed(
                metadata=self._metadata(context, closed),
                verification_id=str(closed.verification_id),
                work_id=closed.work_id,
                attempt=closed.attempt,
                outcome=outcome.value,
                contradicted=len(closed.contradicted),
                unreproducible=len(closed.unreproducible),
                outstanding=len(closed.outstanding_claims),
                reason=note or f"closed as {outcome.value}",
            )

        return CommandResult(record=closed, events=(event,))

    def mark_stale(self, context: Any, command: MarkStale) -> CommandResult:
        record = self._load(context, command.verification_id)
        updated = record.mark_stale(command.current_commit)
        self._repository.replace(context, updated)
        return CommandResult(record=updated, events=())

    def supersede(self, context: Any, command: SupersedeVerification) -> CommandResult:
        record = self._load(context, command.verification_id)
        updated = record.supersede(VerificationId(command.successor_id))
        self._repository.replace(context, updated)
        return CommandResult(
            record=updated,
            events=(
                VerificationSuperseded(
                    metadata=self._metadata(context, updated),
                    verification_id=str(updated.verification_id),
                    work_id=updated.work_id,
                    superseded_by=command.successor_id,
                    reason=command.reason,
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, context: Any, query: GetVerification) -> VerificationRecord:
        return self._load(context, query.verification_id)

    def evaluate(
        self, context: Any, verification_id: str, current_commit: Optional[str] = None
    ):
        """Run policy without closing. What a verifier checks before finishing."""
        return self._policy.evaluate(
            self._load(context, verification_id), current_commit=current_commit
        )

    def list(self, context: Any, query: ListVerifications) -> tuple:
        if query.work_id:
            found = self._repository.for_work_order(context, query.work_id)
        else:
            found = self._repository.all(context)
        if query.status:
            wanted = VerificationStatus(query.status)
            found = tuple(r for r in found if r.status is wanted)
        if query.open_only:
            found = tuple(r for r in found if r.status.is_open)
        return tuple(found)

    def outcome(self, context: Any, query: GetOutcome) -> Optional[VerificationRecord]:
        """The current record for a WorkOrder attempt.

        Superseded records are skipped: a superseded outcome is not the current
        answer whatever it says.
        """
        candidates = [
            r
            for r in self._repository.for_work_order(context, query.work_id)
            if r.attempt == query.attempt and r.superseded_by is None
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.verification_id.value)
