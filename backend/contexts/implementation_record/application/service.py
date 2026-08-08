"""The ImplementationRecord application service.

Where the aggregate's per-item invariants meet the completion policy and the
repository's facts. Events are returned, never published -- this context owns no
bus, the same arrangement as every other engineering context.

Completion is gated, not asserted
----------------------------------
``complete`` runs the policy first and refuses with **every** failure rather
than the first. A completion that refuses one reason at a time takes six attempts
to land, and the sixth is made by someone who has stopped reading the refusals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantRef, TenantScope
from backend.contexts.implementation_record.application.commands import (
    AbandonImplementation,
    AddClaim,
    CompleteImplementation,
    DeclareRisk,
    GetImplementation,
    ListImplementations,
    NoteDeviation,
    RecordBuild,
    RecordCoverage,
    RecordFile,
    RecordTests,
    ResolveAssumption,
    StartImplementation,
    SupersedeImplementation,
)
from backend.contexts.implementation_record.domain.changes import ChangeKind
from backend.contexts.implementation_record.domain.claims import (
    AssumptionOutcome,
    ClaimType,
    RiskLevel,
)
from backend.contexts.implementation_record.domain.errors import (
    IncompleteRecord,
    RecordNotFound,
)
from backend.contexts.implementation_record.domain.events import (
    AGGREGATE_TYPE,
    AssumptionResolved,
    ClaimAdded,
    DigestComputed,
    ImplementationCompleted,
    ImplementationStarted,
    ImplementationSuperseded,
    ImplementationUpdated,
    RiskDeclared,
)
from backend.contexts.implementation_record.domain.factory import (
    build,
    changed,
    claim,
    coverage,
    resolution,
    risk,
    start_implementation,
    test_run,
)
from backend.contexts.implementation_record.domain.identifiers import ImplementationId
from backend.contexts.implementation_record.domain.outcomes import ExecutionStatus
from backend.contexts.implementation_record.domain.policy import (
    CompletionPolicy,
    default_policy,
)
from backend.contexts.implementation_record.domain.record import (
    ImplementationRecord,
    ImplementationStatus,
)
from backend.platform.events import EventMetadata

__all__ = ["ImplementationRecordService", "CommandResult"]


@dataclass(frozen=True)
class CommandResult:
    record: ImplementationRecord
    events: tuple

    @property
    def event_types(self) -> tuple:
        return tuple(getattr(type(e), "EVENT_TYPE", "?") for e in self.events)


class ImplementationRecordService:
    def __init__(
        self, repository: Any, policy: Optional[CompletionPolicy] = None
    ) -> None:
        self._repository = repository
        self._policy = policy or default_policy()

    @property
    def policy(self) -> CompletionPolicy:
        return self._policy

    @staticmethod
    def _metadata(context: Any, record: ImplementationRecord) -> EventMetadata:
        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=context.tenant_id))
        return EventMetadata.create(
            aggregate_id=str(record.implementation_id),
            aggregate_type=AGGREGATE_TYPE,
            scope=scope,
        )

    def _load(self, context: Any, implementation_id: str) -> ImplementationRecord:
        found = self._repository.find(context, ImplementationId(implementation_id))
        if found is None:
            raise RecordNotFound(implementation_id)
        return found

    def _updated(
        self, context: Any, record: ImplementationRecord, what: str, detail: str = ""
    ) -> ImplementationUpdated:
        return ImplementationUpdated(
            metadata=self._metadata(context, record),
            implementation_id=str(record.implementation_id),
            work_id=record.work_id,
            what=what,
            detail=detail,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, context: Any, command: StartImplementation) -> CommandResult:
        record = start_implementation(
            work_id=command.work_id,
            round=command.round,
            context_bundle_id=command.context_bundle_id,
            context_bundle_version=command.context_bundle_version,
            revision=command.revision,
            blast_radius=command.blast_radius_allowed,
            forbidden=command.blast_radius_forbidden,
            read_only=command.blast_radius_read_only,
            adr_references=command.adr_references,
            expected_assumptions=command.expected_assumptions,
            implementer=command.implementer,
        )
        self._repository.save(context, record)
        return CommandResult(
            record=record,
            events=(
                ImplementationStarted(
                    metadata=self._metadata(context, record),
                    implementation_id=str(record.implementation_id),
                    work_id=record.work_id,
                    round=record.round,
                    context_bundle_id=record.context_bundle_id,
                    context_bundle_version=record.context_bundle_version,
                    revision=record.revision,
                ),
            ),
        )

    def complete(self, context: Any, command: CompleteImplementation) -> CommandResult:
        """Seal the record, or refuse with every failure at once."""
        record = self._load(context, command.implementation_id)
        report = self._policy.evaluate(record)
        if not report.may_complete:
            raise IncompleteRecord(
                record_id=command.implementation_id, failures=report.blocking
            )

        sealed = record.complete()
        self._repository.replace(context, sealed)

        return CommandResult(
            record=sealed,
            events=(
                DigestComputed(
                    metadata=self._metadata(context, sealed),
                    implementation_id=str(sealed.implementation_id),
                    work_id=sealed.work_id,
                    digest=sealed.digest or "",
                    algorithm="sha256",
                    canonical_form=1,
                ),
                ImplementationCompleted(
                    metadata=self._metadata(context, sealed),
                    implementation_id=str(sealed.implementation_id),
                    work_id=sealed.work_id,
                    round=sealed.round,
                    digest=sealed.digest or "",
                    claim_count=len(sealed.claims),
                    files_changed=len(sealed.changes.files),
                    revision=sealed.revision,
                ),
            ),
        )

    def abandon(self, context: Any, command: AbandonImplementation) -> CommandResult:
        record = self._load(context, command.implementation_id).abandon(command.reason)
        self._repository.replace(context, record)
        return CommandResult(
            record=record,
            events=(self._updated(context, record, "abandoned", command.reason),),
        )

    def supersede(self, context: Any, command: SupersedeImplementation) -> CommandResult:
        record = self._load(context, command.implementation_id)
        superseded = record.supersede(ImplementationId(command.successor_id))
        self._repository.replace(context, superseded)
        return CommandResult(
            record=superseded,
            events=(
                ImplementationSuperseded(
                    metadata=self._metadata(context, superseded),
                    implementation_id=str(superseded.implementation_id),
                    work_id=superseded.work_id,
                    superseded_by=command.successor_id,
                    reason=command.reason,
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_file(self, context: Any, command: RecordFile) -> CommandResult:
        record = self._load(context, command.implementation_id)
        updated = record.record_file(
            changed(
                command.path,
                ChangeKind(command.kind),
                digest=command.content_digest,
                previous_path=command.previous_path,
                added=command.lines_added,
                removed=command.lines_removed,
            )
        )
        self._repository.replace(context, updated)
        return CommandResult(
            record=updated,
            events=(
                self._updated(context, updated, "file", f"{command.kind}:{command.path}"),
            ),
        )

    def add_claim(self, context: Any, command: AddClaim) -> CommandResult:
        record = self._load(context, command.implementation_id)
        new_claim = claim(
            command.statement,
            ClaimType(command.claim_type),
            tuple(command.evidence),
            hint=command.reproduction_hint,
        )
        updated = record.add_claim(new_claim)
        self._repository.replace(context, updated)
        return CommandResult(
            record=updated,
            events=(
                ClaimAdded(
                    metadata=self._metadata(context, updated),
                    implementation_id=str(updated.implementation_id),
                    work_id=updated.work_id,
                    claim_id=str(new_claim.claim_id),
                    claim_type=new_claim.claim_type.value,
                    statement=new_claim.statement,
                    evidence_count=len(new_claim.evidence),
                ),
            ),
        )

    def resolve_assumption(self, context: Any, command: ResolveAssumption) -> CommandResult:
        record = self._load(context, command.implementation_id)
        resolved = resolution(
            command.assumption_id,
            command.statement,
            AssumptionOutcome(command.outcome),
            tuple(command.evidence),
            note=command.note,
        )
        updated = record.resolve_assumption(resolved)
        self._repository.replace(context, updated)
        return CommandResult(
            record=updated,
            events=(
                AssumptionResolved(
                    metadata=self._metadata(context, updated),
                    implementation_id=str(updated.implementation_id),
                    work_id=updated.work_id,
                    assumption_id=command.assumption_id,
                    outcome=command.outcome,
                    evidence_count=len(resolved.evidence),
                ),
            ),
        )

    def declare_risk(self, context: Any, command: DeclareRisk) -> CommandResult:
        record = self._load(context, command.implementation_id)
        declared = risk(
            command.statement,
            RiskLevel(command.level),
            mitigation=command.mitigation,
            affected_paths=tuple(command.affected_paths),
        )
        updated = record.declare_risk(declared)
        self._repository.replace(context, updated)
        return CommandResult(
            record=updated,
            events=(
                RiskDeclared(
                    metadata=self._metadata(context, updated),
                    implementation_id=str(updated.implementation_id),
                    work_id=updated.work_id,
                    risk_id=str(declared.risk_id),
                    level=declared.level.value,
                    statement=declared.statement,
                    mitigated=bool(declared.mitigation),
                ),
            ),
        )

    def record_tests(self, context: Any, command: RecordTests) -> CommandResult:
        record = self._load(context, command.implementation_id)
        updated = record.record_tests(
            test_run(
                command.command,
                command.revision or record.revision,
                status=ExecutionStatus(command.status),
                passed=command.passed,
                failed=command.failed,
                skipped=command.skipped,
                errors=command.errors,
                suite=command.suite,
            )
        )
        self._repository.replace(context, updated)
        return CommandResult(
            record=updated,
            events=(self._updated(context, updated, "tests", command.command),),
        )

    def record_build(self, context: Any, command: RecordBuild) -> CommandResult:
        record = self._load(context, command.implementation_id)
        updated = record.record_build(
            build(
                command.name,
                command.command,
                command.revision or record.revision,
                status=ExecutionStatus(command.status),
                detail=command.detail,
            )
        )
        self._repository.replace(context, updated)
        return CommandResult(
            record=updated,
            events=(self._updated(context, updated, "build", command.name),),
        )

    def record_coverage(self, context: Any, command: RecordCoverage) -> CommandResult:
        record = self._load(context, command.implementation_id)
        updated = record.record_coverage(
            coverage(
                command.criterion,
                tuple(command.covering_tests),
                negative_check=command.negative_check,
            )
        )
        self._repository.replace(context, updated)
        return CommandResult(
            record=updated,
            events=(self._updated(context, updated, "coverage", command.criterion[:50]),),
        )

    def note_deviation(self, context: Any, command: NoteDeviation) -> CommandResult:
        record = self._load(context, command.implementation_id)
        updated = record.note_deviation(command.deviation)
        self._repository.replace(context, updated)
        return CommandResult(
            record=updated,
            events=(self._updated(context, updated, "deviation", command.deviation[:50]),),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, context: Any, query: GetImplementation) -> ImplementationRecord:
        return self._load(context, query.implementation_id)

    def evaluate(self, context: Any, implementation_id: str):
        """Run the completion policy without completing.

        What an implementer checks before submitting. Discovering eight failures
        one refusal at a time is how a submission takes eight attempts.
        """
        return self._policy.evaluate(self._load(context, implementation_id))

    def list(self, context: Any, query: ListImplementations) -> tuple:
        found = (
            self._repository.for_work_order(context, query.work_id)
            if query.work_id
            else self._repository.all(context)
        )
        if query.status:
            wanted = ImplementationStatus(query.status)
            found = tuple(r for r in found if r.status is wanted)
        return tuple(found)

    def current_for(
        self, context: Any, work_id: str
    ) -> Optional[ImplementationRecord]:
        """The latest non-superseded record for a WorkOrder.

        Superseded records are skipped: a replaced round is not the artifact
        Review and Verification should consume.
        """
        live = [
            r
            for r in self._repository.for_work_order(context, work_id)
            if r.status is not ImplementationStatus.SUPERSEDED
        ]
        if not live:
            return None
        return max(live, key=lambda r: (r.round, r.implementation_id.value))

    def completed_for(
        self, context: Any, work_id: str, round: Optional[int] = None
    ) -> Optional[ImplementationRecord]:
        """The completed record Review and Verification consume.

        Only ``COMPLETED`` qualifies. An in-progress record is not an artifact --
        it is work in flight, and consuming it would mean reviewing something
        that can still change.
        """
        candidates = [
            r
            for r in self._repository.for_work_order(context, work_id)
            if r.status is ImplementationStatus.COMPLETED
            and (round is None or r.round == round)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda r: (r.round, r.implementation_id.value))
