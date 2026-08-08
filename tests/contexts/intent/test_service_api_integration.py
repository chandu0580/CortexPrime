"""Service, policy, repository, replay, concurrency, API, Constitution compliance.

The integration section pins what PR-M2 claims: Intent turns a stated goal into a
mandate that can be acted on without guessing, refuses the ones that cannot, and
plans nothing.
"""

from __future__ import annotations

import ast
import pathlib
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import intent_routes as routes
from backend.contracts.errors import ContractViolation
from backend.contexts.intent import (
    AcknowledgeRisk,
    AddConstraint,
    AddSuccessCriterion,
    ApproveIntent,
    CaptureIntent,
    DuplicateIntent,
    GetIntent,
    InMemoryIntentRepository,
    IntentApprovedError,
    IntentNotFound,
    IntentPriority,
    IntentService,
    IntentStatus,
    ListIntents,
    RejectIntent,
    RemoveConstraint,
    SetObjective,
    SetPriority,
    SetRiskAppetite,
    SetScope,
    SupersedeIntent,
    ValidateIntent,
    ValidationRefused,
)
from backend.contexts.intent.infrastructure.persistence import (
    RECORD_SCHEMA_VERSION,
    from_record,
    to_record,
)
from backend.platform.context import ExecutionContext
from backend.platform.storage import MissingExecutionContext


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="intent-tests", component="tests", source="pytest"
    )


@pytest.fixture
def tenant_context() -> ExecutionContext:
    from backend.platform.context.identity import IdentityContext

    return ExecutionContext.for_tenant(
        tenant_id="tenant-a", identity=IdentityContext.platform("tests"), source="pytest"
    )


@pytest.fixture
def repository() -> InMemoryIntentRepository:
    return InMemoryIntentRepository()


@pytest.fixture
def service(repository) -> IntentService:
    return IntentService(repository=repository)


def _capture(**overrides) -> CaptureIntent:
    fields = dict(
        stated_goal="Our AWS bill is out of control, cut it",
        title="Reduce AWS cost",
    )
    fields.update(overrides)
    return CaptureIntent(**fields)


def _complete(service, context, *, environments=("staging",), kind="reduce") -> str:
    """An intent with all six elements, ready to validate."""
    intent_id = str(service.capture(context, _capture()).intent.intent_id)
    service.set_objective(
        context,
        SetObjective(
            intent_id=intent_id, outcome="Cut monthly AWS spend 20%", kind=kind, subject="aws"
        ),
    )
    service.set_scope(
        context,
        SetScope(intent_id=intent_id, included=("ec2", "rds"), environments=environments),
    )
    service.add_constraint(
        context,
        AddConstraint(
            intent_id=intent_id, kind="budget", statement="spend cap", limit="$500"
        ),
    )
    service.add_success_criterion(
        context,
        AddSuccessCriterion(
            intent_id=intent_id,
            statement="monthly spend drops 20%",
            measure="AWS Cost Explorer month-over-month",
            threshold="-20%",
            baseline="Jul 2026: $42k",
        ),
    )
    service.set_priority(context, SetPriority(intent_id=intent_id, priority="elevated"))
    return intent_id


def _approved(service, context) -> str:
    intent_id = _complete(service, context)
    service.validate(context, ValidateIntent(intent_id=intent_id))
    service.approve(context, ApproveIntent(intent_id=intent_id, approved_by="cfo"))
    return intent_id


# ----------------------------------------------------------------------
# Capture
# ----------------------------------------------------------------------


def test_capturing_emits_one_event_and_keeps_the_goal(service, context) -> None:
    result = service.capture(context, _capture())
    assert result.event_types == ("intent.runtime.created",)
    assert result.intent.stated_goal == "Our AWS bill is out of control, cut it"
    assert result.intent.status is IntentStatus.DRAFT


def test_a_capture_without_a_goal_is_refused_before_the_service() -> None:
    with pytest.raises(ContractViolation):
        _capture(stated_goal="  ")


def test_a_derived_capture_must_name_its_source() -> None:
    with pytest.raises(ContractViolation):
        _capture(origin="derived")


def test_saving_the_same_intent_twice_is_refused(service, context, repository) -> None:
    intent = service.capture(context, _capture()).intent
    with pytest.raises(DuplicateIntent):
        repository.save(context, intent)


# ----------------------------------------------------------------------
# Expansion
# ----------------------------------------------------------------------


def test_each_expansion_emits_an_event(service, context) -> None:
    intent_id = str(service.capture(context, _capture()).intent.intent_id)
    result = service.set_objective(
        context, SetObjective(intent_id=intent_id, outcome="Cut spend", kind="reduce")
    )
    assert result.event_types == ("intent.runtime.expanded",)
    assert result.events[0].element == "objective"
    assert not result.events[0].returned_to_draft


def test_expanding_a_validated_intent_reports_that_it_undid_the_validation(
    service, context
) -> None:
    """A consumer that missed this would act on a mandate nobody re-checked."""
    intent_id = _complete(service, context)
    service.validate(context, ValidateIntent(intent_id=intent_id))

    result = service.acknowledge_risk(
        context, AcknowledgeRisk(intent_id=intent_id, statement="batch may throttle")
    )
    assert result.events[0].returned_to_draft
    assert result.intent.status is IntentStatus.DRAFT


def test_removing_a_constraint_from_a_validated_intent_returns_it_to_draft(
    service, context
) -> None:
    intent_id = _complete(service, context)
    validated = service.validate(context, ValidateIntent(intent_id=intent_id)).intent
    target = str(validated.constraints[0].constraint_id)

    result = service.remove_constraint(
        context, RemoveConstraint(intent_id=intent_id, constraint_id=target)
    )
    assert result.intent.status is IntentStatus.DRAFT
    assert result.intent.constraints == ()


def test_an_unmeasurable_criterion_is_refused_by_the_command() -> None:
    with pytest.raises(ContractViolation):
        AddSuccessCriterion(intent_id="I", statement="be faster", measure="  ")


def test_an_unbounded_budget_constraint_is_refused_by_the_command() -> None:
    with pytest.raises(ContractViolation):
        AddConstraint(intent_id="I", kind="budget", statement="keep costs down")


def test_a_contradictory_scope_is_refused_by_the_command() -> None:
    with pytest.raises(ContractViolation):
        SetScope(intent_id="I", included=("a", "b"), excluded=("a",))


def test_an_empty_scope_is_refused_by_the_command() -> None:
    with pytest.raises(ContractViolation):
        SetScope(intent_id="I", included=())


# ----------------------------------------------------------------------
# Validation policy
# ----------------------------------------------------------------------


def test_the_policy_reports_every_failure_not_the_first(service, context) -> None:
    intent_id = str(service.capture(context, _capture()).intent.intent_id)
    report = service.evaluate(context, intent_id, "validated")
    rules = {f.rule for f in report.blocking}
    assert rules == {"I1-required-elements"}
    assert len([f for f in report.blocking if f.rule == "I1-required-elements"]) == 4


def test_validating_an_incomplete_intent_is_refused(service, context) -> None:
    intent_id = str(service.capture(context, _capture()).intent.intent_id)
    with pytest.raises(ValidationRefused) as caught:
        service.validate(context, ValidateIntent(intent_id=intent_id))
    assert any(f.rule == "I1-required-elements" for f in caught.value.failures)


def test_a_complete_intent_validates_and_emits(service, context) -> None:
    intent_id = _complete(service, context)
    result = service.validate(context, ValidateIntent(intent_id=intent_id))
    assert result.event_types == ("intent.runtime.validated",)
    assert result.intent.status is IntentStatus.VALIDATED


def test_an_acting_objective_needs_a_hard_constraint(service, context) -> None:
    """Soft boundaries can be traded away, which makes the mandate unbounded."""
    intent_id = str(service.capture(context, _capture()).intent.intent_id)
    service.set_objective(
        context, SetObjective(intent_id=intent_id, outcome="Cut spend", kind="reduce")
    )
    service.set_scope(context, SetScope(intent_id=intent_id, included=("ec2",)))
    service.add_constraint(
        context,
        AddConstraint(
            intent_id=intent_id,
            kind="availability",
            statement="prefer no downtime",
            enforcement="soft",
        ),
    )
    service.add_success_criterion(
        context,
        AddSuccessCriterion(
            intent_id=intent_id, statement="spend drops", measure="Cost Explorer"
        ),
    )
    with pytest.raises(ValidationRefused) as caught:
        service.validate(context, ValidateIntent(intent_id=intent_id))
    assert any(f.rule == "I2-acting-objective-bounded" for f in caught.value.failures)


def test_production_work_that_acts_needs_an_approval_constraint(service, context) -> None:
    """Without one, the first human to see the change is whoever notices it."""
    intent_id = _complete(service, context, environments=("production",))
    with pytest.raises(ValidationRefused) as caught:
        service.validate(context, ValidateIntent(intent_id=intent_id))
    assert any(f.rule == "I3-production-approval" for f in caught.value.failures)


def test_production_work_with_an_approval_constraint_validates(service, context) -> None:
    intent_id = _complete(service, context, environments=("production",))
    service.add_constraint(
        context,
        AddConstraint(intent_id=intent_id, kind="approval", statement="FinOps signs off"),
    )
    result = service.validate(context, ValidateIntent(intent_id=intent_id))
    assert result.intent.status is IntentStatus.VALIDATED


def test_observing_production_work_needs_no_approval(service, context) -> None:
    """The cost of a wrong observation is a wrong answer, not an outage."""
    intent_id = _complete(
        service, context, environments=("production",), kind="understand"
    )
    result = service.validate(context, ValidateIntent(intent_id=intent_id))
    assert result.intent.status is IntentStatus.VALIDATED


def test_an_unaccepted_high_risk_cannot_be_constructed_at_all(service, context) -> None:
    """The value object refuses it, so the policy rule is a second net.

    ``AcknowledgedRisk`` will not construct a ``HIGH`` risk with nobody accepting
    it -- which means rule ``I4`` is currently unreachable through every path
    that exists. That is the right order of defence and worth stating: the rule
    is kept for a record assembled by some future path that bypasses
    construction, not because anything reaches it today.
    """
    from backend.contexts.intent import ImpactLevel, risk as make_risk

    with pytest.raises(ContractViolation):
        make_risk("could break checkout", ImpactLevel.HIGH)


def test_the_policy_still_catches_an_unaccepted_high_risk_that_reached_it(
    service, context
) -> None:
    """The second net, exercised by bypassing the first.

    ``object.__setattr__`` is how a record that skipped construction would look.
    Nothing in the codebase produces one, and the rule exists so that if
    something ever does, validation refuses rather than passing it through.
    """
    import dataclasses

    from backend.contexts.intent import ImpactLevel, risk as make_risk

    intent_id = _complete(service, context)
    stored = service.get(context, GetIntent(intent_id=intent_id))

    smuggled = make_risk("could break checkout", ImpactLevel.HIGH, accepted_by="vp")
    object.__setattr__(smuggled, "accepted_by", None)

    tampered = dataclasses.replace(stored, acknowledged_risks=(smuggled,))
    report = service.policy.evaluate(tampered, IntentStatus.VALIDATED)
    assert any(f.rule == "I4-risk-accepted" for f in report.blocking)


def test_a_comparative_criterion_without_a_baseline_is_advisory(service, context) -> None:
    intent_id = str(service.capture(context, _capture()).intent.intent_id)
    service.set_objective(
        context, SetObjective(intent_id=intent_id, outcome="fewer errors", kind="protect")
    )
    service.set_scope(context, SetScope(intent_id=intent_id, included=("api",)))
    service.add_constraint(
        context, AddConstraint(intent_id=intent_id, kind="safety", statement="no data loss")
    )
    service.add_success_criterion(
        context,
        AddSuccessCriterion(
            intent_id=intent_id,
            statement="30% fewer errors",
            measure="error rate",
            threshold="-30%",
        ),
    )
    report = service.evaluate(context, intent_id, "validated")
    assert report.may_proceed
    assert any(f.rule == "I6-baseline-recorded" for f in report.advisory)


def test_a_derived_intent_is_flagged_for_a_closer_look(service, context) -> None:
    """Nobody chose its words, which is when a weak mandate passes unnoticed."""
    intent_id = str(
        service.capture(
            context, _capture(origin="derived", derived_from="INT-1")
        ).intent.intent_id
    )
    service.set_objective(
        context, SetObjective(intent_id=intent_id, outcome="do a thing", kind="protect")
    )
    service.set_scope(context, SetScope(intent_id=intent_id, included=("api",)))
    service.add_constraint(
        context, AddConstraint(intent_id=intent_id, kind="safety", statement="be careful")
    )
    service.add_success_criterion(
        context,
        AddSuccessCriterion(intent_id=intent_id, statement="it holds", measure="a check"),
    )
    report = service.evaluate(context, intent_id, "validated")
    assert any(f.rule == "I7-derived-intent" for f in report.advisory)


def test_a_critical_intent_awaiting_approval_is_flagged(service, context) -> None:
    intent_id = _complete(service, context)
    service.set_priority(context, SetPriority(intent_id=intent_id, priority="critical"))
    service.add_constraint(
        context, AddConstraint(intent_id=intent_id, kind="approval", statement="CTO signs")
    )
    report = service.evaluate(context, intent_id, "validated")
    assert any(f.rule == "I8-critical-awaiting-approval" for f in report.advisory)


def test_an_averse_appetite_over_a_broad_scope_is_flagged(service, context) -> None:
    from backend.contexts.intent import BROAD_SCOPE_THRESHOLD

    intent_id = str(service.capture(context, _capture()).intent.intent_id)
    service.set_objective(
        context, SetObjective(intent_id=intent_id, outcome="audit everything", kind="prove")
    )
    service.set_scope(
        context,
        SetScope(
            intent_id=intent_id,
            included=tuple(f"svc-{i}" for i in range(BROAD_SCOPE_THRESHOLD + 1)),
        ),
    )
    service.add_constraint(
        context, AddConstraint(intent_id=intent_id, kind="safety", statement="read only")
    )
    service.add_success_criterion(
        context,
        AddSuccessCriterion(intent_id=intent_id, statement="all audited", measure="report"),
    )
    service.set_risk_appetite(context, SetRiskAppetite(intent_id=intent_id, appetite="averse"))

    report = service.evaluate(context, intent_id, "validated")
    assert any(f.rule == "I5-appetite-matches-breadth" for f in report.advisory)


# ----------------------------------------------------------------------
# Approval
# ----------------------------------------------------------------------


def test_approving_seals_the_mandate(service, context) -> None:
    intent_id = _complete(service, context)
    service.validate(context, ValidateIntent(intent_id=intent_id))
    result = service.approve(context, ApproveIntent(intent_id=intent_id, approved_by="cfo"))

    assert result.event_types == ("intent.runtime.approved",)
    assert result.intent.digest
    result.intent.verify_digest()


def test_approving_a_draft_is_refused(service, context) -> None:
    intent_id = _complete(service, context)
    with pytest.raises(ValidationRefused) as caught:
        service.approve(context, ApproveIntent(intent_id=intent_id, approved_by="cfo"))
    assert any(f.rule == "I0-legal-transition" for f in caught.value.failures)


def test_an_approved_intent_refuses_further_expansion(service, context) -> None:
    intent_id = _approved(service, context)
    with pytest.raises(IntentApprovedError):
        service.set_priority(context, SetPriority(intent_id=intent_id, priority="critical"))


def test_only_approved_intents_are_planable(service, context) -> None:
    """What a planner would ask for. It reads this and nothing else from here."""
    _complete(service, context)
    approved_id = _approved(service, context)

    planable = service.planable(context)
    assert [str(i.intent_id) for i in planable] == [approved_id]


def test_an_approval_must_name_who_gave_it() -> None:
    with pytest.raises(ContractViolation):
        ApproveIntent(intent_id="I", approved_by="  ")


# ----------------------------------------------------------------------
# Rejection and supersession
# ----------------------------------------------------------------------


def test_rejecting_records_the_reason_and_where_it_came_from(service, context) -> None:
    intent_id = _complete(service, context)
    result = service.reject(
        context,
        RejectIntent(intent_id=intent_id, reason="duplicates INT-4", rejected_by="architect"),
    )
    assert result.event_types == ("intent.runtime.rejected",)
    assert result.events[0].rejected_from == "draft"
    assert result.intent.rejection_reason == "duplicates INT-4"


def test_rejecting_without_a_reason_is_refused_by_the_command() -> None:
    with pytest.raises(ContractViolation):
        RejectIntent(intent_id="I", reason="   ")


def test_superseding_links_the_replacement(service, context) -> None:
    first = _approved(service, context)
    second = _complete(service, context)
    result = service.supersede(
        context, SupersedeIntent(intent_id=first, successor_id=second)
    )
    assert result.event_types == ("intent.runtime.superseded",)
    assert str(result.intent.superseded_by) == second


def test_a_superseded_intent_is_no_longer_planable(service, context) -> None:
    first = _approved(service, context)
    second = _complete(service, context)
    service.supersede(context, SupersedeIntent(intent_id=first, successor_id=second))
    assert service.planable(context) == ()


# ----------------------------------------------------------------------
# Repository
# ----------------------------------------------------------------------


def test_every_repository_method_requires_an_execution_context(repository) -> None:
    from backend.contexts.intent import IntentId

    for call in (
        lambda: repository.find(None, IntentId.new()),
        lambda: repository.all(None),
    ):
        with pytest.raises(MissingExecutionContext):
            call()


def test_a_tenant_cannot_see_another_tenants_intent(repository, tenant_context) -> None:
    from backend.platform.context.identity import IdentityContext
    from backend.platform.storage import CrossTenantAccess

    service = IntentService(repository=repository)
    intent = service.capture(tenant_context, _capture()).intent

    other = ExecutionContext.for_tenant(
        tenant_id="tenant-b", identity=IdentityContext.platform("tests"), source="pytest"
    )
    assert repository.find(other, intent.intent_id) is None
    with pytest.raises(CrossTenantAccess):
        repository.replace(other, intent)


def test_the_repository_is_not_grandfathered() -> None:
    from backend.platform.architecture.tenancy_rules import GRANDFATHERED_REPOSITORIES

    offenders = [
        entry
        for entry in GRANDFATHERED_REPOSITORIES
        if "contexts.intent" in entry or "contexts/intent" in entry
    ]
    assert offenders == []


def test_an_unknown_intent_is_reported_as_missing(service, context) -> None:
    from backend.contexts.intent import IntentId

    with pytest.raises(IntentNotFound):
        service.get(context, GetIntent(intent_id=str(IntentId.new())))


# ----------------------------------------------------------------------
# Replay
# ----------------------------------------------------------------------


def test_an_intent_survives_the_round_trip_unchanged(service, context) -> None:
    intent_id = _approved(service, context)
    approved = service.get(context, GetIntent(intent_id=intent_id))
    assert from_record(to_record(approved, tenant_id="tenant-a")) == approved


def test_a_draft_with_partial_structure_survives_the_round_trip(service, context) -> None:
    """Replay has to work before the intent is complete, not only after."""
    intent_id = str(service.capture(context, _capture()).intent.intent_id)
    service.set_objective(
        context, SetObjective(intent_id=intent_id, outcome="do a thing", kind="detect")
    )
    partial = service.get(context, GetIntent(intent_id=intent_id))

    restored = from_record(to_record(partial, tenant_id="tenant-a"))
    assert restored == partial
    assert restored.scope is None


def test_the_digest_is_restored_not_recomputed(service, context) -> None:
    """Recomputing on load would make verification always pass."""
    from backend.contexts.intent import DigestMismatch

    intent_id = _approved(service, context)
    approved = service.get(context, GetIntent(intent_id=intent_id))

    stored = to_record(approved, tenant_id="tenant-a")
    stored["priority"] = "critical"
    with pytest.raises(DigestMismatch):
        from_record(stored).verify_digest()


def test_an_intent_from_an_unknown_schema_version_is_refused(service, context) -> None:
    intent = service.capture(context, _capture()).intent
    stored = to_record(intent, tenant_id="tenant-a")
    stored["schema_version"] = RECORD_SCHEMA_VERSION + 1
    with pytest.raises(ContractViolation):
        from_record(stored)


def test_an_intent_stored_without_a_tenant_is_refused(service, context) -> None:
    intent = service.capture(context, _capture()).intent
    with pytest.raises(ContractViolation):
        to_record(intent, tenant_id="  ")


# ----------------------------------------------------------------------
# Concurrency
# ----------------------------------------------------------------------


def test_concurrent_capture_all_persists(service, context) -> None:
    errors: list = []

    def capture_one(index: int) -> None:
        try:
            service.capture(context, _capture(title=f"intent-{index}"))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=capture_one, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(service.list(context, ListIntents())) == 8


def test_concurrent_reads_during_writes_do_not_tear(service, context) -> None:
    seen: list = []
    errors: list = []
    stop = threading.Event()

    def write() -> None:
        try:
            for index in range(6):
                service.capture(context, _capture(title=f"i-{index}"))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)
        finally:
            stop.set()

    def read() -> None:
        while not stop.is_set():
            try:
                seen.append(len(service.list(context, ListIntents())))
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

    writer, reader = threading.Thread(target=write), threading.Thread(target=read)
    writer.start()
    reader.start()
    writer.join()
    reader.join()

    assert errors == []
    assert seen == sorted(seen)


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(
        routes, "_service", IntentService(repository=InMemoryIntentRepository())
    )
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def _capture_via_api(client, **overrides) -> str:
    payload = dict(
        stated_goal="Our AWS bill is out of control, cut it", title="Reduce AWS cost"
    )
    payload.update(overrides)
    response = client.post("/api/v1/intents", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["intent"]["intent_id"]


def _complete_via_api(client, environments=("staging",), kind="reduce") -> str:
    intent_id = _capture_via_api(client)
    client.put(
        f"/api/v1/intents/{intent_id}/objective",
        json={"outcome": "Cut monthly AWS spend 20%", "kind": kind, "subject": "aws"},
    )
    client.put(
        f"/api/v1/intents/{intent_id}/scope",
        json={"included": ["ec2", "rds"], "environments": list(environments)},
    )
    client.post(
        f"/api/v1/intents/{intent_id}/constraints",
        json={"kind": "budget", "statement": "spend cap", "limit": "$500"},
    )
    client.post(
        f"/api/v1/intents/{intent_id}/success-criteria",
        json={
            "statement": "monthly spend drops 20%",
            "measure": "Cost Explorer MoM",
            "threshold": "-20%",
            "baseline": "Jul: $42k",
        },
    )
    return intent_id


def test_the_api_captures_and_fetches(client) -> None:
    intent_id = _capture_via_api(client)
    body = client.get(f"/api/v1/intents/{intent_id}").json()
    assert body["status"] == "draft"
    assert not body["is_complete"]
    assert set(body["missing_elements"]) == {
        "objective",
        "constraints",
        "scope",
        "success criteria",
    }


def test_the_api_runs_an_intent_to_approval(client) -> None:
    intent_id = _complete_via_api(client)
    validated = client.post(f"/api/v1/intents/{intent_id}/validate")
    assert validated.status_code == 200, validated.text
    assert validated.json()["intent"]["status"] == "validated"

    approved = client.post(
        f"/api/v1/intents/{intent_id}/approve", json={"approved_by": "cfo"}
    )
    assert approved.status_code == 200
    body = approved.json()["intent"]
    assert body["status"] == "approved"
    assert body["digest"]
    assert body["is_planable"]


def test_the_api_refuses_an_unmeasurable_criterion(client) -> None:
    """400, not 422: the schema accepts an empty string and the *domain* refuses it.

    Worth pinning rather than tightening the schema. The rule belongs to the
    context -- a criterion nobody can check is a wish -- and a client that got a
    generic schema error would learn the field was empty rather than why it
    matters.
    """
    intent_id = _capture_via_api(client)
    response = client.post(
        f"/api/v1/intents/{intent_id}/success-criteria",
        json={"statement": "be faster", "measure": ""},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "unmeasurable_criterion"
    assert "wish" in response.json()["detail"]["message"]


def test_the_api_refuses_an_unbounded_budget_constraint(client) -> None:
    """Refused at the *command*, before anything is loaded -- with the domain's
    own error, so failing fast does not cost the caller the structured body."""
    intent_id = _capture_via_api(client)
    response = client.post(
        f"/api/v1/intents/{intent_id}/constraints",
        json={"kind": "budget", "statement": "keep costs down"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "unbounded_constraint"
    assert response.json()["detail"]["kind"] == "budget"


def test_the_api_refuses_a_contradictory_scope(client) -> None:
    intent_id = _capture_via_api(client)
    response = client.put(
        f"/api/v1/intents/{intent_id}/scope",
        json={"included": ["a", "b"], "excluded": ["a"]},
    )
    assert response.status_code == 400


def test_the_api_reports_every_validation_failure(client) -> None:
    intent_id = _capture_via_api(client)
    response = client.post(f"/api/v1/intents/{intent_id}/validate")
    assert response.status_code == 422
    rules = {f["rule"] for f in response.json()["detail"]["failures"]}
    assert rules == {"I1-required-elements"}


def test_the_api_refuses_production_action_without_approval(client) -> None:
    intent_id = _complete_via_api(client, environments=("production",))
    response = client.post(f"/api/v1/intents/{intent_id}/validate")
    assert response.status_code == 422
    rules = {f["rule"] for f in response.json()["detail"]["failures"]}
    assert "I3-production-approval" in rules


def test_the_policy_endpoint_reports_without_transitioning(client) -> None:
    intent_id = _capture_via_api(client)
    body = client.get(f"/api/v1/intents/{intent_id}/policy?to_status=validated").json()
    assert not body["may_proceed"]
    assert client.get(f"/api/v1/intents/{intent_id}").json()["status"] == "draft"


def test_the_api_returns_409_on_an_approved_intent(client) -> None:
    intent_id = _complete_via_api(client)
    client.post(f"/api/v1/intents/{intent_id}/validate")
    client.post(f"/api/v1/intents/{intent_id}/approve", json={"approved_by": "cfo"})
    response = client.put(
        f"/api/v1/intents/{intent_id}/priority", json={"priority": "critical"}
    )
    assert response.status_code == 409


def test_the_api_returns_404_for_an_unknown_intent(client) -> None:
    from backend.contexts.intent import IntentId

    assert client.get(f"/api/v1/intents/{IntentId.new()}").status_code == 404


def test_the_api_lists_and_filters(client) -> None:
    _capture_via_api(client)
    approved = _complete_via_api(client)
    client.post(f"/api/v1/intents/{approved}/validate")
    client.post(f"/api/v1/intents/{approved}/approve", json={"approved_by": "cfo"})

    assert client.get("/api/v1/intents").json()["count"] == 2
    assert client.get("/api/v1/intents?planable_only=true").json()["count"] == 1
    assert client.get("/api/v1/intents?status=draft").json()["count"] == 1


def test_the_api_removes_a_constraint(client) -> None:
    intent_id = _complete_via_api(client)
    body = client.get(f"/api/v1/intents/{intent_id}").json()
    constraint_id = body["constraints"][0]["constraint_id"]

    response = client.delete(
        f"/api/v1/intents/{intent_id}/constraints/{constraint_id}"
    )
    assert response.status_code == 200
    assert response.json()["intent"]["constraints"] == []


def test_the_api_rejects_an_unknown_constraint_kind(client) -> None:
    intent_id = _capture_via_api(client)
    response = client.post(
        f"/api/v1/intents/{intent_id}/constraints",
        json={"kind": "vibes", "statement": "good vibes only"},
    )
    assert response.status_code == 422


# ----------------------------------------------------------------------
# Constitution compliance
# ----------------------------------------------------------------------


def _modules() -> list:
    root = pathlib.Path("backend/contexts/intent")
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def _imports(path: pathlib.Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def test_the_context_imports_only_contracts_and_platform() -> None:
    permitted = ("backend.contracts", "backend.platform", "backend.contexts.intent")
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.") and not imported.startswith(permitted)
    ]
    assert offences == [], offences


def test_the_context_imports_no_other_bounded_context() -> None:
    """S2. The priority mirror is a drift test, not an import."""
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.contexts.")
        and not imported.startswith("backend.contexts.intent")
    ]
    assert offences == [], offences


def test_intent_never_plans_and_never_executes() -> None:
    """The rule the whole context rests on, asserted against the import graph."""
    forbidden = (
        "backend.execution",
        "backend.orchestrator",
        "backend.orchestration",
        "backend.llm",
        "backend.ai",
        "backend.agents",
        "backend.agent_sdk",
        "backend.connector",
        "backend.connectors",
        "backend.knowledge",
        "backend.services",
        "backend.workflow_designer",
        "backend.database",
    )
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith(forbidden)
    ]
    assert offences == [], offences


def test_the_domain_layer_does_no_io() -> None:
    banned = {"pathlib", "os", "socket", "requests", "httpx", "sqlite3", "json"}
    root = pathlib.Path("backend/contexts/intent/domain")
    offences = [
        f"{path}: {imported}"
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
        for imported in _imports(path)
        if imported.split(".")[0] in banned
    ]
    assert offences == [], offences


def test_the_context_reuses_the_published_mission_intent_contract() -> None:
    """The requester's verbatim words already have a published home.

    Duplicating ``MissionIntent`` would give the codebase two answers to "what
    did the requester actually say", and BC-9's security-context requirement
    would have to be re-enforced in the copy.
    """
    users = [
        path.name
        for path in _modules()
        if any(i == "backend.contracts.mission" for i in _imports(path))
    ]
    assert "intent.py" in users


def test_event_types_are_namespaced_and_disjoint() -> None:
    from backend.contexts.context_bundle import CONTEXT_EVENT_TYPES
    from backend.contexts.engineering import RUNTIME_EVENT_TYPES
    from backend.contexts.engineering_verification import VERIFICATION_EVENT_TYPES
    from backend.contexts.implementation_record import IMPLEMENTATION_EVENT_TYPES
    from backend.contexts.intent import INTENT_EVENT_TYPES
    from backend.contexts.mission import MISSION_EVENT_TYPES
    from backend.contexts.review import REVIEW_EVENT_TYPES

    ours = {e.EVENT_TYPE for e in INTENT_EVENT_TYPES}
    assert all(e.startswith("intent.runtime.") for e in ours)
    assert len(ours) == 6
    for other in (
        CONTEXT_EVENT_TYPES,
        RUNTIME_EVENT_TYPES,
        VERIFICATION_EVENT_TYPES,
        IMPLEMENTATION_EVENT_TYPES,
        MISSION_EVENT_TYPES,
        REVIEW_EVENT_TYPES,
    ):
        assert ours.isdisjoint({e.EVENT_TYPE for e in other})


def test_the_route_module_does_not_import_a_second_context() -> None:
    path = pathlib.Path("backend/api/intent_routes.py")
    contexts = {
        imported.split(".")[2]
        for imported in _imports(path)
        if imported.startswith("backend.contexts.") and len(imported.split(".")) > 2
    }
    assert contexts == {"intent"}, contexts
