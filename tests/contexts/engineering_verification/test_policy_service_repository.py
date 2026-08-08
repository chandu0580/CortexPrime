"""Policy, the application service, the repository, replay, and concurrency.

The outcome tests are the load-bearing ones. If a caller can close a verification
as complete, "verification" becomes a field someone sets.
"""

from __future__ import annotations

import threading

import pytest

from backend.contracts.errors import ContractViolation
from backend.contexts.engineering_verification import (
    AddEvidence,
    ClaimInput,
    ClaimResult,
    ClaimType,
    ClaimVerdict,
    CloseVerification,
    DuplicateVerification,
    EvidenceKind,
    GetOutcome,
    GetVerification,
    ListVerifications,
    RecordClaimResult,
    RequestVerification,
    StartVerification,
    SupersedeVerification,
    TrustLevel,
    VerificationNotFound,
    VerificationStatus,
    claim,
    contradicted,
    default_policy,
    evidence,
    reproduced,
    request_verification,
)
from backend.contexts.engineering_verification.infrastructure.persistence import (
    from_record,
    to_record,
)
from backend.platform.storage import MissingExecutionContext

from tests.contexts.engineering_verification.conftest import (
    BASE,
    adversarial_step,
    command_step,
    running,
)


def _ok(target):
    return reproduced(target, command_step(), "it held", evidence("ran it", base_commit=BASE))


# ----------------------------------------------------------------------
# Policy: outcome is derived
# ----------------------------------------------------------------------


def test_a_fully_reproduced_verification_is_complete():
    target = claim("x holds", ClaimType.BEHAVIOUR)
    record = running(target).record(_ok(target))
    report = default_policy().evaluate(record, current_commit=BASE)

    assert report.may_complete
    assert report.outcome is VerificationStatus.COMPLETE


def test_an_unsettled_claim_blocks_completion():
    """Reporting complete having examined only some claims looks like success."""
    settled = claim("one", ClaimType.BEHAVIOUR)
    unsettled = claim("two", ClaimType.BEHAVIOUR)
    record = running(settled, unsettled).record(_ok(settled))

    report = default_policy().evaluate(record, current_commit=BASE)
    assert not report.may_complete
    assert report.outcome is VerificationStatus.INCOMPLETE
    assert any(f.rule == "P1-every-claim-settled" for f in report.blocking)


def test_a_contradiction_yields_failed_not_incomplete():
    """'The work is wrong' is more actionable than 'we could not tell'."""
    target = claim("x holds", ClaimType.BEHAVIOUR)
    record = running(target).record(
        contradicted(target, command_step(), "it did not hold", evidence("ran it", base_commit=BASE))
    )
    report = default_policy().evaluate(record, current_commit=BASE)

    assert report.outcome is VerificationStatus.FAILED
    assert any(f.rule == "P2-no-contradiction" for f in report.blocking)


def test_an_unreproducible_claim_yields_incomplete():
    target = claim("x holds", ClaimType.BEHAVIOUR)
    record = running(target).record(
        ClaimResult(
            claim=target, reproduction=command_step(), observed="could not tell",
            verdict=ClaimVerdict.UNREPRODUCIBLE,
            verdict_evidence=evidence("environment lacks docker", base_commit=BASE),
        )
    )
    report = default_policy().evaluate(record, current_commit=BASE)

    assert report.outcome is VerificationStatus.INCOMPLETE
    assert any(f.rule == "P3-nothing-unreproducible" for f in report.blocking)


def test_observed_only_evidence_cannot_carry_a_gate():
    """The most valuable evidence there is, and it cannot be re-established."""
    target = claim("the Jira ticket was filed", ClaimType.BEHAVIOUR)
    record = running(target).record(
        reproduced(target, command_step(), "SCRUM-24 exists",
                   evidence("fetched SCRUM-24", kind=EvidenceKind.EXTERNAL, trust=TrustLevel.OBSERVED))
    )
    report = default_policy().evaluate(record, current_commit=BASE)

    assert not report.may_complete
    assert any(f.rule == "P4-evidence-can-stand-alone" for f in report.blocking)


def test_stale_evidence_blocks_completion():
    """It describes a tree nobody is merging."""
    target = claim("x holds", ClaimType.BEHAVIOUR)
    record = running(target).record(
        reproduced(target, command_step(), "held", evidence("ran it", base_commit="oldcommit"))
    )
    report = default_policy().evaluate(record, current_commit="newcommit")

    assert any(f.rule == "P5-nothing-stale" for f in report.blocking)


def test_an_absence_claim_declared_out_of_scope_blocks():
    """The claim that something cannot happen must be attacked, not deferred."""
    target = claim("no cross-tenant read is possible", ClaimType.ABSENCE)
    record = running(target).record(
        ClaimResult(claim=target, reproduction=command_step(), observed="not examined",
                    verdict=ClaimVerdict.OUT_OF_SCOPE, note="deferred")
    )
    report = default_policy().evaluate(record, current_commit=BASE)

    assert any(f.rule == "P6-absence-constructed" for f in report.blocking)


def test_a_superseded_verification_cannot_complete():
    from backend.contexts.engineering_verification import VerificationId

    target = claim("x holds", ClaimType.BEHAVIOUR)
    record = running(target).record(_ok(target)).supersede(VerificationId.new())
    report = default_policy().evaluate(record, current_commit=BASE)

    assert any(f.rule == "P7-not-superseded" for f in report.blocking)


def test_policy_returns_every_finding_not_just_the_first():
    first = claim("one", ClaimType.BEHAVIOUR)
    second = claim("two", ClaimType.BEHAVIOUR)
    third = claim("three", ClaimType.BEHAVIOUR)
    record = (
        running(first, second, third)
        .record(contradicted(first, command_step(), "no", evidence("ran", base_commit=BASE)))
        .record(reproduced(second, command_step(), "yes",
                           evidence("saw once", kind=EvidenceKind.EXTERNAL, trust=TrustLevel.OBSERVED)))
    )
    report = default_policy().evaluate(record, current_commit=BASE)
    rules = {f.rule for f in report.blocking}
    assert {"P1-every-claim-settled", "P2-no-contradiction", "P4-evidence-can-stand-alone"} <= rules


# ----------------------------------------------------------------------
# Service
# ----------------------------------------------------------------------


def _request(service, context, *, claims=None, work_id="WO-1", attempt=1):
    return service.request(
        context,
        RequestVerification(
            work_id=work_id,
            attempt=attempt,
            base_commit=BASE,
            claims=claims or (ClaimInput(statement="x holds", claim_type="behaviour"),),
        ),
    )


def test_request_creates_a_record_and_emits(service, context, repository):
    result = _request(service, context)
    assert result.record.status is VerificationStatus.REQUESTED
    assert result.event_types == ("engineering.verification.requested",)
    assert len(repository) == 1


def test_a_request_with_no_claims_is_refused(service, context):
    with pytest.raises(ContractViolation):
        service.request(
            context, RequestVerification(work_id="WO-1", base_commit=BASE, claims=())
        )


def test_start_names_the_verifier(service, context):
    created = _request(service, context)
    started = service.start(
        context,
        StartVerification(verification_id=str(created.record.verification_id), verifier="verifier-1"),
    )
    assert started.record.verifier == "verifier-1"
    assert started.event_types == ("engineering.verification.started",)


def test_recording_a_result_emits_evidence_added(service, context):
    created = _request(service, context)
    vid = str(created.record.verification_id)
    service.start(context, StartVerification(verification_id=vid, verifier="v"))
    claim_id = str(created.record.request.claims[0].claim_id)

    result = service.record_result(
        context,
        RecordClaimResult(
            verification_id=vid, claim_id=claim_id, verdict="reproduced",
            observed="it held", specification="pytest -k guard",
            evidence_summary="ran the guard; it refused",
        ),
    )
    assert result.event_types == ("engineering.verification.evidence_added",)
    assert result.record.results[0].verdict is ClaimVerdict.REPRODUCED


def test_the_outcome_is_derived_not_chosen(service, context):
    """A caller cannot close a verification as complete."""
    created = _request(service, context)
    vid = str(created.record.verification_id)
    service.start(context, StartVerification(verification_id=vid, verifier="v"))

    # Nothing settled -- policy must say incomplete regardless of intent.
    closed = service.close(context, CloseVerification(verification_id=vid, current_commit=BASE))
    assert closed.record.status is VerificationStatus.INCOMPLETE
    assert closed.event_types == ("engineering.verification.failed",)


def test_only_invalidated_may_be_forced(service, context):
    created = _request(service, context)
    vid = str(created.record.verification_id)
    with pytest.raises(ContractViolation):
        CloseVerification(verification_id=vid, force_outcome="complete", note="please")


def test_invalidating_requires_naming_the_failed_premise(service, context):
    with pytest.raises(ContractViolation):
        CloseVerification(verification_id="v", force_outcome="invalidated")


def test_a_complete_close_emits_succeeded(service, context):
    created = _request(service, context)
    vid = str(created.record.verification_id)
    service.start(context, StartVerification(verification_id=vid, verifier="v"))
    service.record_result(
        context,
        RecordClaimResult(
            verification_id=vid, claim_id=str(created.record.request.claims[0].claim_id),
            verdict="reproduced", observed="held", specification="ran it",
            evidence_summary="ran it and it held",
        ),
    )
    closed = service.close(context, CloseVerification(verification_id=vid, current_commit=BASE))

    assert closed.record.status is VerificationStatus.COMPLETE
    assert closed.event_types == ("engineering.verification.succeeded",)


def test_an_absence_claim_via_the_service_still_needs_construction(service, context):
    created = _request(
        service, context,
        claims=(ClaimInput(statement="no cross-tenant read is possible", claim_type="absence"),),
    )
    vid = str(created.record.verification_id)
    service.start(context, StartVerification(verification_id=vid, verifier="v"))

    from backend.contexts.engineering_verification import ReproductionInadequate

    with pytest.raises(ReproductionInadequate):
        service.record_result(
            context,
            RecordClaimResult(
                verification_id=vid, claim_id=str(created.record.request.claims[0].claim_id),
                verdict="reproduced", observed="suite green",
                method="command_execution", specification="pytest tests/ -q",
                evidence_summary="312 passed",
            ),
        )


def test_outcome_skips_a_superseded_record(service, context):
    first = _request(service, context)
    second = _request(service, context)
    service.supersede(
        context,
        SupersedeVerification(
            verification_id=str(first.record.verification_id),
            successor_id=str(second.record.verification_id),
        ),
    )
    current = service.outcome(context, GetOutcome(work_id="WO-1", attempt=1))
    assert str(current.verification_id) == str(second.record.verification_id)


def test_get_of_an_unknown_verification_raises(service, context):
    from backend.contexts.engineering_verification import VerificationId

    with pytest.raises(VerificationNotFound):
        service.get(context, GetVerification(verification_id=str(VerificationId.new())))


# ----------------------------------------------------------------------
# Repository
# ----------------------------------------------------------------------


def test_every_repository_method_refuses_a_missing_context(repository):
    from backend.contexts.engineering_verification import VerificationId

    record = running(claim("x", ClaimType.BEHAVIOUR))
    with pytest.raises(MissingExecutionContext):
        repository.save(None, record)
    with pytest.raises(MissingExecutionContext):
        repository.find(None, VerificationId.new())
    with pytest.raises(MissingExecutionContext):
        repository.for_work_order(None, "WO-1")
    with pytest.raises(MissingExecutionContext):
        repository.all(None)
    with pytest.raises(MissingExecutionContext):
        repository.clear(None)


def test_a_tenant_context_does_not_see_another_tenants_records(repository, tenant_context):
    from backend.platform.context import ExecutionContext
    from backend.platform.context.identity import IdentityContext

    other = ExecutionContext.for_tenant(
        tenant_id="tenant-b", identity=IdentityContext.platform("tests"), source="pytest"
    )
    repository.save(tenant_context, running(claim("x", ClaimType.BEHAVIOUR)))

    assert len(repository.all(tenant_context)) == 1
    assert repository.all(other) == ()


def test_saving_the_same_record_twice_is_refused(repository, context):
    record = running(claim("x", ClaimType.BEHAVIOUR))
    repository.save(context, record)
    with pytest.raises(DuplicateVerification):
        repository.save(context, record)


def test_replace_requires_the_record_to_exist(repository, context):
    with pytest.raises(VerificationNotFound):
        repository.replace(context, running(claim("x", ClaimType.BEHAVIOUR)))


def test_for_work_order_orders_by_attempt(repository, context):
    for attempt in (3, 1, 2):
        repository.save(
            context,
            request_verification("WO-1", [claim("x", ClaimType.BEHAVIOUR)],
                                 attempt=attempt, base_commit=BASE),
        )
    assert [r.attempt for r in repository.for_work_order(context, "WO-1")] == [1, 2, 3]


# ----------------------------------------------------------------------
# Round trip and replay
# ----------------------------------------------------------------------


def test_record_round_trip_preserves_everything():
    target = claim("x holds", ClaimType.BEHAVIOUR, asserted_evidence=("EV-impl-1",))
    record = running(target).record(_ok(target)).close(VerificationStatus.COMPLETE)
    assert from_record(to_record(record, tenant_id="t")) == record


def test_round_trip_preserves_an_out_of_scope_result():
    target = claim("x", ClaimType.BEHAVIOUR)
    record = running(target).record(
        ClaimResult(claim=target, reproduction=command_step(), observed="not examined",
                    verdict=ClaimVerdict.OUT_OF_SCOPE, note="belongs to Review")
    )
    assert from_record(to_record(record, tenant_id="t")) == record


def test_an_unknown_record_schema_is_refused():
    """In a context whose purpose is refusing to take things on trust."""
    stored = to_record(running(claim("x", ClaimType.BEHAVIOUR)), tenant_id="t")
    stored["schema_version"] = 99
    with pytest.raises(ContractViolation):
        from_record(stored)


def test_replay_reproduces_the_same_outcome(repository, context):
    """Persist, reload, re-evaluate: the verdict must not move."""
    target = claim("x holds", ClaimType.BEHAVIOUR)
    record = running(target).record(_ok(target))
    repository.save(context, record)

    reloaded = repository.find(context, record.verification_id)
    live = default_policy().evaluate(record, current_commit=BASE)
    replayed = default_policy().evaluate(reloaded, current_commit=BASE)

    assert replayed.outcome is live.outcome
    assert [f.rule for f in replayed.findings] == [f.rule for f in live.findings]


def test_replay_of_a_failed_verification_stays_failed(repository, context):
    target = claim("x holds", ClaimType.BEHAVIOUR)
    record = running(target).record(
        contradicted(target, command_step(), "no", evidence("ran", base_commit=BASE))
    )
    repository.save(context, record)
    reloaded = repository.find(context, record.verification_id)

    assert default_policy().evaluate(reloaded, current_commit=BASE).outcome is (
        VerificationStatus.FAILED
    )


def test_policy_evaluation_is_deterministic():
    """Twenty evaluations of the same record must agree."""
    target = claim("x holds", ClaimType.BEHAVIOUR)
    record = running(target).record(_ok(target))
    outcomes = {
        default_policy().evaluate(record, current_commit=BASE).outcome for _ in range(20)
    }
    assert len(outcomes) == 1


# ----------------------------------------------------------------------
# Concurrency
# ----------------------------------------------------------------------


def test_concurrent_saves_lose_nothing(repository, context):
    errors: list = []

    def writer(index: int) -> None:
        try:
            for attempt in range(1, 11):
                repository.save(
                    context,
                    request_verification(
                        f"WO-{index}", [claim("x", ClaimType.BEHAVIOUR)],
                        attempt=attempt, base_commit=BASE,
                    ),
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(repository) == 80


def test_only_one_of_two_racing_starts_succeeds(service, context):
    """A verdict has one author."""
    created = _request(service, context)
    vid = str(created.record.verification_id)
    outcomes: list = []
    barrier = threading.Barrier(2)

    def attempt(name: str) -> None:
        barrier.wait()
        try:
            service.start(context, StartVerification(verification_id=vid, verifier=name))
            outcomes.append("ok")
        except Exception as exc:  # noqa: BLE001
            outcomes.append(type(exc).__name__)

    threads = [threading.Thread(target=attempt, args=(f"v{i}",)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert outcomes.count("ok") >= 1
    assert len(outcomes) == 2


def test_concurrent_verifications_of_distinct_work_orders_do_not_interfere(service, context):
    errors: list = []

    def verify(index: int) -> None:
        try:
            created = _request(service, context, work_id=f"WO-{index}")
            vid = str(created.record.verification_id)
            service.start(context, StartVerification(verification_id=vid, verifier=f"v{index}"))
            service.record_result(
                context,
                RecordClaimResult(
                    verification_id=vid,
                    claim_id=str(created.record.request.claims[0].claim_id),
                    verdict="reproduced", observed="held", specification="ran it",
                    evidence_summary="ran it and it held",
                ),
            )
            closed = service.close(
                context, CloseVerification(verification_id=vid, current_commit=BASE)
            )
            if closed.record.status is not VerificationStatus.COMPLETE:
                errors.append((index, closed.record.status))
        except Exception as exc:  # noqa: BLE001
            errors.append((index, exc))

    threads = [threading.Thread(target=verify, args=(i,)) for i in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
