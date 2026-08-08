"""Service, policy, repository, replay, concurrency, API, Constitution compliance.

The integration section pins what PR-M3 claims: the Planner turns an approved
mandate into an executable plan, refuses the plans that cannot be executed
safely, and executes nothing itself.
"""

from __future__ import annotations

import ast
import pathlib
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import planner_routes as routes
from backend.contracts.errors import ContractViolation
from backend.contexts.planner import (
    AddDependency,
    AddGoal,
    AddTask,
    ApprovePlan,
    AssessRisk,
    CyclicDependency,
    DeclareCriteria,
    DraftPlan,
    DuplicatePlan,
    GetGraph,
    GetPlan,
    InMemoryPlanRepository,
    ListPlans,
    PlanApprovedError,
    PlanNotFound,
    PlanRefused,
    PlanStatus,
    PlannerService,
    RejectPlan,
    RemoveTask,
    RevisePlan,
    RiskUnderstated,
    SetExecutionStrategy,
    SetRollbackStrategy,
    ValidatePlan,
)
from backend.contexts.planner.infrastructure.persistence import (
    RECORD_SCHEMA_VERSION,
    from_record,
    to_record,
)
from backend.platform.context import ExecutionContext
from backend.platform.storage import MissingExecutionContext

CRITERION = "CR-1"


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="planner-tests", component="tests", source="pytest"
    )


@pytest.fixture
def tenant_context() -> ExecutionContext:
    from backend.platform.context.identity import IdentityContext

    return ExecutionContext.for_tenant(
        tenant_id="tenant-a", identity=IdentityContext.platform("tests"), source="pytest"
    )


@pytest.fixture
def repository() -> InMemoryPlanRepository:
    return InMemoryPlanRepository()


@pytest.fixture
def service(repository) -> PlannerService:
    return PlannerService(repository=repository)


def _draft(**overrides) -> DraftPlan:
    fields = dict(
        mission_id="M-1",
        intent_id="I-1",
        intent_digest="9f2c1a7b",
        title="Cut AWS spend 20%",
    )
    fields.update(overrides)
    return DraftPlan(**fields)


def _scaffold(service, context, **overrides) -> tuple:
    """A plan with one criterion and one goal. Returns ``(plan_id, goal_id)``."""
    plan_id = str(service.draft(context, _draft(**overrides)).plan.plan_id)
    service.declare_criteria(context, DeclareCriteria(plan_id=plan_id, criteria=(CRITERION,)))
    result = service.add_goal(
        context,
        AddGoal(plan_id=plan_id, statement="Rightsize instances", satisfies=(CRITERION,)),
    )
    return plan_id, str(result.plan.goals[0].goal_id)


def _complete(service, context, **overrides) -> str:
    plan_id, goal_id = _scaffold(service, context, **overrides)
    service.add_task(
        context,
        AddTask(plan_id=plan_id, task_id="audit", purpose="list utilisation", goals=(goal_id,)),
    )
    service.add_task(
        context,
        AddTask(
            plan_id=plan_id,
            task_id="resize",
            purpose="resize the over-provisioned ones",
            goals=(goal_id,),
            depends_on=("audit",),
            side_effect="reversible_write",
            inverse_action="restore-previous-size",
        ),
    )
    service.set_rollback_strategy(
        context,
        SetRollbackStrategy(
            plan_id=plan_id, kind="compensating_tasks", description="restore sizes"
        ),
    )
    service.assess_risk(
        context,
        AssessRisk(
            plan_id=plan_id,
            overall="moderate",
            risks=({"statement": "resizing may throttle batch", "level": "moderate"},),
        ),
    )
    return plan_id


def _approved(service, context, **overrides) -> str:
    plan_id = _complete(service, context, **overrides)
    service.validate(context, ValidatePlan(plan_id=plan_id))
    service.approve(context, ApprovePlan(plan_id=plan_id, approved_by="sre-lead"))
    return plan_id


# ----------------------------------------------------------------------
# Drafting
# ----------------------------------------------------------------------


def test_drafting_emits_one_event_and_binds_the_mandate(service, context) -> None:
    result = service.draft(context, _draft())
    assert result.event_types == ("planner.runtime.created",)
    assert result.plan.intent_digest == "9f2c1a7b"
    assert result.plan.status is PlanStatus.DRAFT


def test_a_draft_without_an_intent_digest_is_refused_before_the_service() -> None:
    with pytest.raises(ContractViolation):
        _draft(intent_digest="  ")


def test_saving_the_same_plan_twice_is_refused(service, context, repository) -> None:
    plan = service.draft(context, _draft()).plan
    with pytest.raises(DuplicatePlan):
        repository.save(context, plan)


def test_a_goal_must_trace_to_a_criterion_at_the_command() -> None:
    with pytest.raises(ContractViolation):
        AddGoal(plan_id="P", statement="do a thing", satisfies=())


def test_a_task_must_serve_a_goal_at_the_command() -> None:
    with pytest.raises(ContractViolation):
        AddTask(plan_id="P", task_id="t", purpose="do a thing", goals=())


def test_a_mutating_task_without_a_way_back_is_refused_at_the_command() -> None:
    with pytest.raises(ContractViolation) as caught:
        AddTask(
            plan_id="P",
            task_id="t",
            purpose="write",
            goals=("g",),
            side_effect="destructive",
        )
    assert "P2" in str(caught.value)


# ----------------------------------------------------------------------
# The graph, through the service
# ----------------------------------------------------------------------


def test_adding_a_task_emits_and_records_reversibility(service, context) -> None:
    plan_id, goal_id = _scaffold(service, context)
    result = service.add_task(
        context,
        AddTask(plan_id=plan_id, task_id="audit", purpose="read", goals=(goal_id,)),
    )
    assert result.event_types == ("planner.runtime.task_added",)
    assert result.events[0].reversible


def test_a_dependency_reports_the_depth_it_cost(service, context) -> None:
    plan_id = _complete(service, context)
    result = service.add_dependency(
        context, AddDependency(plan_id=plan_id, task_id="resize", depends_on="audit")
    )
    assert result.event_types == ("planner.runtime.dependency_added",)
    assert result.events[0].graph_depth == 2


def test_a_cycle_is_refused_by_the_service(service, context) -> None:
    plan_id = _complete(service, context)
    with pytest.raises(CyclicDependency):
        service.add_dependency(
            context, AddDependency(plan_id=plan_id, task_id="audit", depends_on="resize")
        )


def test_the_graph_is_queryable(service, context) -> None:
    plan_id = _complete(service, context)
    graph = service.graph(context, GetGraph(plan_id=plan_id))
    assert graph.layers() == (("audit",), ("resize",))
    assert graph.blast_of("audit") == 1


# ----------------------------------------------------------------------
# Policy
# ----------------------------------------------------------------------


def test_the_policy_reports_every_failure_not_the_first(service, context) -> None:
    """A plan can have several problems, and one round-trip each is how planning
    becomes the slow part."""
    plan_id = str(service.draft(context, _draft()).plan.plan_id)
    report = service.evaluate(context, plan_id, "validated")
    rules = {f.rule for f in report.blocking}
    assert rules == {"L1-required-elements"}
    assert len(report.blocking) == 4


def test_validating_an_incomplete_plan_is_refused(service, context) -> None:
    plan_id = str(service.draft(context, _draft()).plan.plan_id)
    with pytest.raises(PlanRefused) as caught:
        service.validate(context, ValidatePlan(plan_id=plan_id))
    assert any(f.rule == "L1-required-elements" for f in caught.value.failures)


def test_a_complete_plan_validates_and_reports_its_shape(service, context) -> None:
    plan_id = _complete(service, context)
    result = service.validate(context, ValidatePlan(plan_id=plan_id))
    assert result.event_types == ("planner.runtime.validated",)
    assert result.events[0].graph_depth == 2
    assert result.events[0].tasks == 2


def test_destructive_work_without_a_checkpoint_is_refused(service, context) -> None:
    """A plan that destroys something and checkpoints nothing can only be
    restarted over a world that has already changed."""
    plan_id, goal_id = _scaffold(service, context)
    service.add_task(
        context,
        AddTask(
            plan_id=plan_id,
            task_id="purge",
            purpose="delete the old bucket",
            goals=(goal_id,),
            side_effect="destructive",
            irreversible_accepted_by="head-of-platform",
        ),
    )
    service.set_rollback_strategy(
        context,
        SetRollbackStrategy(
            plan_id=plan_id,
            kind="forward_fix_only",
            description="restore from backup archive",
            accepted_by="head-of-platform",
        ),
    )
    service.assess_risk(
        context,
        AssessRisk(
            plan_id=plan_id,
            overall="severe",
            risks=(
                {
                    "statement": "the bucket is gone",
                    "level": "severe",
                    "mitigation": "backup archive verified first",
                },
            ),
        ),
    )
    with pytest.raises(PlanRefused) as caught:
        service.validate(context, ValidatePlan(plan_id=plan_id))
    assert any(f.rule == "L3-destructive-checkpointed" for f in caught.value.failures)


def test_an_understated_risk_is_refused_by_the_service(service, context) -> None:
    plan_id = _complete(service, context)
    with pytest.raises(RiskUnderstated):
        service.assess_risk(context, AssessRisk(plan_id=plan_id, overall="low"))


def test_a_sequential_plan_that_could_be_parallel_is_flagged(service, context) -> None:
    plan_id, goal_id = _scaffold(service, context)
    for name in ("a", "b", "c"):
        service.add_task(
            context,
            AddTask(plan_id=plan_id, task_id=name, purpose="read", goals=(goal_id,)),
        )
    service.assess_risk(context, AssessRisk(plan_id=plan_id, overall="low"))

    report = service.evaluate(context, plan_id, "validated")
    assert report.may_proceed
    assert any(f.rule == "L6-unused-concurrency" for f in report.advisory)


def test_a_blast_radius_outlier_is_flagged(service, context) -> None:
    """One task whose failure strands most of the plan is worth knowing about."""
    plan_id, goal_id = _scaffold(service, context)
    service.add_task(
        context,
        AddTask(plan_id=plan_id, task_id="root", purpose="read", goals=(goal_id,)),
    )
    for name in ("a", "b", "c"):
        service.add_task(
            context,
            AddTask(
                plan_id=plan_id,
                task_id=name,
                purpose="read",
                goals=(goal_id,),
                depends_on=("root",),
            ),
        )
    service.assess_risk(context, AssessRisk(plan_id=plan_id, overall="low"))

    report = service.evaluate(context, plan_id, "validated")
    assert any(
        f.rule == "L5-blast-radius-outlier" and f.subject == "root"
        for f in report.advisory
    )


def test_accepted_irreversible_work_is_listed_as_advisory(service, context) -> None:
    plan_id, goal_id = _scaffold(service, context)
    service.add_task(
        context,
        AddTask(
            plan_id=plan_id,
            task_id="purge",
            purpose="delete",
            goals=(goal_id,),
            side_effect="destructive",
            irreversible_accepted_by="head-of-platform",
        ),
    )
    service.set_execution_strategy(
        context, SetExecutionStrategy(plan_id=plan_id, checkpoint_after=("purge",))
    )
    service.set_rollback_strategy(
        context,
        SetRollbackStrategy(
            plan_id=plan_id,
            kind="forward_fix_only",
            description="restore from archive",
            accepted_by="head-of-platform",
        ),
    )
    service.assess_risk(
        context,
        AssessRisk(
            plan_id=plan_id,
            overall="severe",
            risks=(
                {"statement": "irreversible", "level": "severe", "mitigation": "archive"},
            ),
        ),
    )
    report = service.evaluate(context, plan_id, "validated")
    assert report.may_proceed
    assert any(f.rule == "L7-accepted-irreversible" for f in report.advisory)


# ----------------------------------------------------------------------
# Approval and versioning
# ----------------------------------------------------------------------


def test_approving_seals_the_plan(service, context) -> None:
    plan_id = _complete(service, context)
    service.validate(context, ValidatePlan(plan_id=plan_id))
    result = service.approve(context, ApprovePlan(plan_id=plan_id, approved_by="sre-lead"))

    assert result.event_types == ("planner.runtime.approved",)
    assert result.events[0].rollback_kind == "compensating_tasks"
    result.plan.verify_digest()


def test_an_approved_plan_refuses_further_edits(service, context) -> None:
    plan_id = _approved(service, context)
    with pytest.raises(PlanApprovedError):
        service.remove_task(context, RemoveTask(plan_id=plan_id, task_id="audit"))


def test_revising_opens_a_version_and_supersedes_the_original(service, context) -> None:
    plan_id = _approved(service, context)
    result = service.revise(context, RevisePlan(plan_id=plan_id))

    assert result.event_types == ("planner.runtime.versioned",)
    assert result.plan.version == 2
    original = service.get(context, GetPlan(plan_id=plan_id))
    assert original.status is PlanStatus.SUPERSEDED
    assert original.superseded_by == result.plan.plan_id


def test_only_approved_plans_are_executable(service, context) -> None:
    """What Execution would ask for. It reads this and nothing else from here."""
    _complete(service, context)
    approved_id = _approved(service, context)

    executable = service.executable_for(context, "M-1")
    assert executable is not None
    assert str(executable.plan_id) == approved_id


def test_a_superseded_plan_is_no_longer_executable(service, context) -> None:
    plan_id = _approved(service, context)
    service.revise(context, RevisePlan(plan_id=plan_id))
    assert service.executable_for(context, "M-1") is None


def test_rejecting_records_where_it_came_from(service, context) -> None:
    plan_id = _complete(service, context)
    result = service.reject(
        context, RejectPlan(plan_id=plan_id, reason="the graph is wrong", rejected_by="sre")
    )
    assert result.event_types == ("planner.runtime.rejected",)
    assert result.events[0].rejected_from == "draft"


def test_rejecting_without_a_reason_is_refused_by_the_command() -> None:
    with pytest.raises(ContractViolation):
        RejectPlan(plan_id="P", reason="  ")


# ----------------------------------------------------------------------
# Queries
# ----------------------------------------------------------------------


def test_listing_filters_by_mission_status_and_executability(service, context) -> None:
    _complete(service, context)
    _approved(service, context)

    assert len(service.list(context, ListPlans())) == 2
    assert len(service.list(context, ListPlans(mission_id="M-1"))) == 2
    assert len(service.list(context, ListPlans(status="approved"))) == 1
    assert len(service.list(context, ListPlans(executable_only=True))) == 1


def test_an_unknown_plan_is_reported_as_missing(service, context) -> None:
    from backend.contexts.planner import PlanId

    with pytest.raises(PlanNotFound):
        service.get(context, GetPlan(plan_id=str(PlanId.new())))


# ----------------------------------------------------------------------
# Repository
# ----------------------------------------------------------------------


def test_every_repository_method_requires_an_execution_context(repository) -> None:
    from backend.contexts.planner import PlanId

    for call in (
        lambda: repository.find(None, PlanId.new()),
        lambda: repository.all(None),
    ):
        with pytest.raises(MissingExecutionContext):
            call()


def test_a_tenant_cannot_see_another_tenants_plan(repository, tenant_context) -> None:
    from backend.platform.context.identity import IdentityContext
    from backend.platform.storage import CrossTenantAccess

    service = PlannerService(repository=repository)
    plan = service.draft(tenant_context, _draft()).plan

    other = ExecutionContext.for_tenant(
        tenant_id="tenant-b", identity=IdentityContext.platform("tests"), source="pytest"
    )
    assert repository.find(other, plan.plan_id) is None
    with pytest.raises(CrossTenantAccess):
        repository.replace(other, plan)


def test_the_repository_is_not_grandfathered() -> None:
    from backend.platform.architecture.tenancy_rules import GRANDFATHERED_REPOSITORIES

    offenders = [
        entry
        for entry in GRANDFATHERED_REPOSITORIES
        if "contexts.planner" in entry or "contexts/planner" in entry
    ]
    assert offenders == []


# ----------------------------------------------------------------------
# Replay
# ----------------------------------------------------------------------


def test_a_plan_survives_the_round_trip_unchanged(service, context) -> None:
    plan_id = _approved(service, context)
    approved = service.get(context, GetPlan(plan_id=plan_id))
    assert from_record(to_record(approved, tenant_id="tenant-a")) == approved


def test_the_graph_is_revalidated_on_load(service, context) -> None:
    """A stored plan edited into a cycle refuses to load rather than stalling later."""
    plan_id = _complete(service, context)
    plan = service.get(context, GetPlan(plan_id=plan_id))

    stored = to_record(plan, tenant_id="tenant-a")
    for entry in stored["tasks"]:
        if entry["task_id"] == "audit":
            entry["depends_on"] = ["resize"]

    with pytest.raises(CyclicDependency):
        from_record(stored)


def test_a_partial_draft_survives_the_round_trip(service, context) -> None:
    plan_id, _ = _scaffold(service, context)
    partial = service.get(context, GetPlan(plan_id=plan_id))
    restored = from_record(to_record(partial, tenant_id="tenant-a"))
    assert restored == partial
    assert restored.tasks == ()


def test_the_digest_is_restored_not_recomputed(service, context) -> None:
    from backend.contexts.planner import DigestMismatch

    plan_id = _approved(service, context)
    approved = service.get(context, GetPlan(plan_id=plan_id))

    stored = to_record(approved, tenant_id="tenant-a")
    stored["title"] = "something else entirely"
    with pytest.raises(DigestMismatch):
        from_record(stored).verify_digest()


def test_a_plan_from_an_unknown_schema_version_is_refused(service, context) -> None:
    plan = service.draft(context, _draft()).plan
    stored = to_record(plan, tenant_id="tenant-a")
    stored["schema_version"] = RECORD_SCHEMA_VERSION + 1
    with pytest.raises(ContractViolation):
        from_record(stored)


def test_a_plan_stored_without_a_tenant_is_refused(service, context) -> None:
    plan = service.draft(context, _draft()).plan
    with pytest.raises(ContractViolation):
        to_record(plan, tenant_id="  ")


# ----------------------------------------------------------------------
# Concurrency
# ----------------------------------------------------------------------


def test_concurrent_drafting_all_persists(service, context) -> None:
    errors: list = []

    def draft_one(index: int) -> None:
        try:
            service.draft(context, _draft(title=f"plan-{index}"))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=draft_one, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(service.list(context, ListPlans())) == 8


def test_concurrent_reads_during_writes_do_not_tear(service, context) -> None:
    seen: list = []
    errors: list = []
    stop = threading.Event()

    def write() -> None:
        try:
            for index in range(6):
                service.draft(context, _draft(title=f"p-{index}"))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)
        finally:
            stop.set()

    def read() -> None:
        while not stop.is_set():
            try:
                seen.append(len(service.list(context, ListPlans())))
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
        routes, "_service", PlannerService(repository=InMemoryPlanRepository())
    )
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def _draft_via_api(client, **overrides) -> str:
    payload = dict(
        mission_id="M-1",
        intent_id="I-1",
        intent_digest="9f2c1a7b",
        title="Cut AWS spend 20%",
    )
    payload.update(overrides)
    response = client.post("/api/v1/plans", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["plan"]["plan_id"]


def _complete_via_api(client) -> str:
    plan_id = _draft_via_api(client)
    client.post(f"/api/v1/plans/{plan_id}/criteria", json={"criteria": [CRITERION]})
    goal = client.post(
        f"/api/v1/plans/{plan_id}/goals",
        json={"statement": "Rightsize instances", "satisfies": [CRITERION]},
    ).json()
    goal_id = goal["plan"]["goals"][0]["goal_id"]

    client.post(
        f"/api/v1/plans/{plan_id}/tasks",
        json={"task_id": "audit", "purpose": "list utilisation", "goals": [goal_id]},
    )
    client.post(
        f"/api/v1/plans/{plan_id}/tasks",
        json={
            "task_id": "resize",
            "purpose": "resize instances",
            "goals": [goal_id],
            "depends_on": ["audit"],
            "side_effect": "reversible_write",
            "inverse_action": "restore-previous-size",
        },
    )
    client.put(
        f"/api/v1/plans/{plan_id}/rollback-strategy",
        json={"kind": "compensating_tasks", "description": "restore sizes"},
    )
    client.put(
        f"/api/v1/plans/{plan_id}/risk",
        json={
            "overall": "moderate",
            "risks": [{"statement": "may throttle batch", "level": "moderate"}],
        },
    )
    return plan_id


def test_the_api_drafts_and_fetches(client) -> None:
    plan_id = _draft_via_api(client)
    body = client.get(f"/api/v1/plans/{plan_id}").json()
    assert body["status"] == "draft"
    assert not body["is_complete"]
    assert body["version"] == 1


def test_the_api_runs_a_plan_to_approval(client) -> None:
    plan_id = _complete_via_api(client)
    validated = client.post(f"/api/v1/plans/{plan_id}/validate")
    assert validated.status_code == 200, validated.text

    approved = client.post(
        f"/api/v1/plans/{plan_id}/approve", json={"approved_by": "sre-lead"}
    )
    assert approved.status_code == 200
    body = approved.json()["plan"]
    assert body["status"] == "approved"
    assert body["digest"]
    assert body["is_executable"]


def test_the_api_exposes_the_graph(client) -> None:
    plan_id = _complete_via_api(client)
    body = client.get(f"/api/v1/plans/{plan_id}/graph").json()
    assert body["layers"] == [["audit"], ["resize"]]
    assert body["depth"] == 2
    assert body["roots"] == ["audit"]
    assert body["blast_radius"]["audit"] == 1


def test_the_api_refuses_a_cycle_and_names_it(client) -> None:
    plan_id = _complete_via_api(client)
    response = client.post(
        f"/api/v1/plans/{plan_id}/tasks/audit/dependencies", json={"depends_on": "resize"}
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "cyclic_dependency"
    assert set(response.json()["detail"]["cycle"]) == {"audit", "resize"}


def test_the_api_refuses_an_understated_risk(client) -> None:
    plan_id = _complete_via_api(client)
    response = client.put(f"/api/v1/plans/{plan_id}/risk", json={"overall": "low"})
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "risk_understated"
    assert response.json()["detail"]["implied"] == "moderate"


def test_the_api_reports_every_validation_failure(client) -> None:
    plan_id = _draft_via_api(client)
    response = client.post(f"/api/v1/plans/{plan_id}/validate")
    assert response.status_code == 422
    rules = {f["rule"] for f in response.json()["detail"]["failures"]}
    assert rules == {"L1-required-elements"}


def test_the_policy_endpoint_reports_without_transitioning(client) -> None:
    plan_id = _draft_via_api(client)
    body = client.get(f"/api/v1/plans/{plan_id}/policy?to_status=validated").json()
    assert not body["may_proceed"]
    assert client.get(f"/api/v1/plans/{plan_id}").json()["status"] == "draft"


def test_the_api_refuses_a_duplicate_task_id(client) -> None:
    plan_id = _complete_via_api(client)
    body = client.get(f"/api/v1/plans/{plan_id}").json()
    goal_id = body["goals"][0]["goal_id"]
    response = client.post(
        f"/api/v1/plans/{plan_id}/tasks",
        json={"task_id": "audit", "purpose": "again", "goals": [goal_id]},
    )
    assert response.status_code == 409


def test_the_api_returns_409_on_an_approved_plan(client) -> None:
    plan_id = _complete_via_api(client)
    client.post(f"/api/v1/plans/{plan_id}/validate")
    client.post(f"/api/v1/plans/{plan_id}/approve", json={"approved_by": "sre-lead"})
    response = client.delete(f"/api/v1/plans/{plan_id}/tasks/audit")
    assert response.status_code == 409


def test_the_api_returns_404_for_an_unknown_plan(client) -> None:
    from backend.contexts.planner import PlanId

    assert client.get(f"/api/v1/plans/{PlanId.new()}").status_code == 404


def test_the_api_revises_into_a_new_version(client) -> None:
    plan_id = _complete_via_api(client)
    client.post(f"/api/v1/plans/{plan_id}/validate")
    client.post(f"/api/v1/plans/{plan_id}/approve", json={"approved_by": "sre-lead"})

    response = client.post(f"/api/v1/plans/{plan_id}/revise", json={})
    assert response.status_code == 200
    assert response.json()["plan"]["version"] == 2
    assert client.get(f"/api/v1/plans/{plan_id}").json()["status"] == "superseded"


def test_the_api_reports_the_implied_risk_floor(client) -> None:
    plan_id = _complete_via_api(client)
    body = client.get(f"/api/v1/plans/{plan_id}").json()
    assert body["implied_risk_floor"]["level"] == "moderate"
    assert body["implied_risk_floor"]["driver"]


def test_the_api_rejects_an_unknown_side_effect(client) -> None:
    plan_id = _draft_via_api(client)
    response = client.post(
        f"/api/v1/plans/{plan_id}/tasks",
        json={"task_id": "t", "purpose": "p", "goals": ["g"], "side_effect": "vandalise"},
    )
    assert response.status_code == 422


def test_the_api_lists_and_filters(client) -> None:
    _draft_via_api(client)
    _draft_via_api(client, mission_id="M-2")
    assert client.get("/api/v1/plans").json()["count"] == 2
    assert client.get("/api/v1/plans?mission_id=M-2").json()["count"] == 1


# ----------------------------------------------------------------------
# Constitution compliance
# ----------------------------------------------------------------------


def _modules() -> list:
    root = pathlib.Path("backend/contexts/planner")
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
    permitted = ("backend.contracts", "backend.platform", "backend.contexts.planner")
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.") and not imported.startswith(permitted)
    ]
    assert offences == [], offences


def test_the_context_imports_no_other_bounded_context() -> None:
    """S2. Planner never modifies missions -- it cannot even see one."""
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.contexts.")
        and not imported.startswith("backend.contexts.planner")
    ]
    assert offences == [], offences


def test_planner_never_executes_and_never_invokes_tools() -> None:
    """The rule the whole context rests on, asserted against the import graph.

    ``backend.contracts.execution`` is permitted and is not an exception: that
    module says of itself "these are declarations, not invocations. Nothing here
    performs work." ``backend.execution`` -- the thing that performs work -- is
    what must stay unreachable.
    """
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
        "backend.tools",
        "backend.mcp",
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
    root = pathlib.Path("backend/contexts/planner/domain")
    offences = [
        f"{path}: {imported}"
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
        for imported in _imports(path)
        if imported.split(".")[0] in banned
    ]
    assert offences == [], offences


def test_the_context_uses_the_published_task_and_execution_vocabularies() -> None:
    """The cycle check was delegated here by the published contract itself.

    ``TaskRef`` says so: *"detecting them requires the whole graph, so that check
    belongs to BC-1."* Reusing the vocabulary rather than inventing a second one
    is what makes the delegation coherent instead of a coincidence.
    """
    users = {
        path.name: set(_imports(path))
        for path in _modules()
    }
    assert any("backend.contracts.mission" in imports for imports in users.values())
    assert "backend.contracts.execution" in users["tasks.py"]


def test_event_types_are_namespaced_and_disjoint() -> None:
    from backend.contexts.context_bundle import CONTEXT_EVENT_TYPES
    from backend.contexts.engineering import RUNTIME_EVENT_TYPES
    from backend.contexts.engineering_verification import VERIFICATION_EVENT_TYPES
    from backend.contexts.implementation_record import IMPLEMENTATION_EVENT_TYPES
    from backend.contexts.intent import INTENT_EVENT_TYPES
    from backend.contexts.mission import MISSION_EVENT_TYPES
    from backend.contexts.planner import PLAN_EVENT_TYPES
    from backend.contexts.review import REVIEW_EVENT_TYPES

    ours = {e.EVENT_TYPE for e in PLAN_EVENT_TYPES}
    assert all(e.startswith("planner.runtime.") for e in ours)
    assert len(ours) == 8
    for other in (
        CONTEXT_EVENT_TYPES,
        RUNTIME_EVENT_TYPES,
        VERIFICATION_EVENT_TYPES,
        IMPLEMENTATION_EVENT_TYPES,
        INTENT_EVENT_TYPES,
        MISSION_EVENT_TYPES,
        REVIEW_EVENT_TYPES,
    ):
        assert ours.isdisjoint({e.EVENT_TYPE for e in other})


def test_the_route_module_does_not_import_a_second_context() -> None:
    path = pathlib.Path("backend/api/planner_routes.py")
    contexts = {
        imported.split(".")[2]
        for imported in _imports(path)
        if imported.startswith("backend.contexts.") and len(imported.split(".")) > 2
    }
    assert contexts == {"planner"}, contexts
