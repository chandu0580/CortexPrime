"""Construction helpers.

The aggregate's constructor takes strongly-typed values and enforces every
invariant, which is correct and verbose. These are the ergonomic paths in, and
they exist so the common cases cannot be built wrong: a claim always gets its
evidence, a changed file always gets its digest, and a record always gets the
four references every record must carry.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

from backend.contexts.implementation_record.domain.changes import (
    ChangedFile,
    ChangeKind,
    CodeChangeSet,
)
from backend.contexts.implementation_record.domain.claims import (
    AssumptionOutcome,
    AssumptionResolution,
    Claim,
    ClaimType,
    CriterionCoverage,
    RiskDeclaration,
    RiskLevel,
)
from backend.contexts.implementation_record.domain.identifiers import ImplementationId
from backend.contexts.implementation_record.domain.outcomes import (
    BuildResult,
    ExecutionStatus,
    TestExecution,
)
from backend.contexts.implementation_record.domain.paths import BlastRadiusScope
from backend.contexts.implementation_record.domain.record import ImplementationRecord

__all__ = [
    "start_implementation",
    "changed",
    "claim",
    "resolution",
    "risk",
    "coverage",
    "test_run",
    "build",
]


def start_implementation(
    *,
    work_id: str,
    context_bundle_id: str,
    revision: str,
    blast_radius: Sequence[str],
    round: int = 1,
    context_bundle_version: int = 1,
    adr_references: Iterable[str] = (),
    forbidden: Sequence[str] = (),
    read_only: Sequence[str] = (),
    expected_assumptions: Iterable[str] = (),
    implementer: str = "implementer",
) -> ImplementationRecord:
    """An open record with the four mandatory references bound."""
    return ImplementationRecord(
        implementation_id=ImplementationId.new(),
        work_id=work_id,
        round=round,
        context_bundle_id=context_bundle_id,
        context_bundle_version=context_bundle_version,
        revision=revision,
        blast_radius=BlastRadiusScope.of(
            blast_radius, forbidden=forbidden, read_only=read_only
        ),
        adr_references=frozenset(adr_references),
        changes=CodeChangeSet.empty(revision),
        expected_assumptions=frozenset(expected_assumptions),
        implementer=implementer,
    )


def changed(
    path: str,
    kind: ChangeKind = ChangeKind.MODIFIED,
    *,
    digest: Optional[str] = None,
    previous_path: Optional[str] = None,
    added: int = 0,
    removed: int = 0,
) -> ChangedFile:
    """A changed file, with a placeholder digest where one is required.

    Real recording supplies the real digest -- the composition root hashes the
    file. The default keeps a caller from having to hash something just to
    express intent in a test.
    """
    if kind.requires_content_digest and digest is None:
        digest = f"unhashed:{path}"
    return ChangedFile(
        path=path,
        kind=kind,
        content_digest=digest,
        previous_path=previous_path,
        lines_added=added,
        lines_removed=removed,
    )


def claim(
    statement: str,
    claim_type: ClaimType = ClaimType.BEHAVIOUR,
    evidence: Sequence[str] = (),
    *,
    hint: Optional[str] = None,
) -> Claim:
    return Claim.create(statement, claim_type, evidence, reproduction_hint=hint)


def resolution(
    assumption_id: str,
    statement: str,
    outcome: AssumptionOutcome,
    evidence: Sequence[str],
    *,
    note: Optional[str] = None,
) -> AssumptionResolution:
    return AssumptionResolution.create(
        assumption_id, statement, outcome, evidence, note=note
    )


def risk(
    statement: str,
    level: RiskLevel = RiskLevel.LOW,
    *,
    mitigation: Optional[str] = None,
    affected_paths: Sequence[str] = (),
) -> RiskDeclaration:
    return RiskDeclaration.create(
        statement, level, mitigation=mitigation, affected_paths=affected_paths
    )


def coverage(
    criterion: str, tests: Sequence[str], *, negative_check: Optional[str] = None
) -> CriterionCoverage:
    return CriterionCoverage(
        criterion=criterion, covering_tests=tuple(tests), negative_check=negative_check
    )


def test_run(
    command: str,
    revision: str,
    *,
    status: ExecutionStatus = ExecutionStatus.PASSED,
    passed: int = 0,
    failed: int = 0,
    skipped: int = 0,
    errors: int = 0,
    suite: Optional[str] = None,
) -> TestExecution:
    return TestExecution(
        command=command,
        status=status,
        revision=revision,
        passed=passed,
        failed=failed,
        skipped=skipped,
        errors=errors,
        suite=suite,
    )


#: pytest collects any module-level callable named ``test_*``. ``test_run`` is a
#: domain factory, not a test, and without this marker every test module that
#: imports it fails at collection with "fixture 'command' not found". Renaming it
#: would be bending the domain vocabulary around a test runner; this states the
#: fact instead.
test_run.__test__ = False


def build(
    name: str,
    command: str,
    revision: str,
    *,
    status: ExecutionStatus = ExecutionStatus.PASSED,
    detail: Optional[str] = None,
) -> BuildResult:
    return BuildResult(
        name=name, command=command, status=status, revision=revision, detail=detail
    )
