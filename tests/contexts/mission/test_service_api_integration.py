"""Service, policy, repository, replay, concurrency, API, and Constitution compliance.

The integration section pins what PR-M1 claims: a mission runs its whole
lifecycle through the runtime, the runtime performs none of the work, and a
mission cannot be reported complete over work nobody verified.
"""

from __future__ import annotations

import ast
import pathlib
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import mission_runtime_routes as routes
from backend.contracts.errors import ContractViolation
from backend.contracts.mission import MissionState
from backend.contexts.mission import (
    AdvanceExecution,
    ArchiveMission,
    AUTHORISATION_PRECONDITION,
    CancelMission,
    CompleteMission,
    CreateMission,
    DeclarePrecondition,
    DuplicateMission,
    FailMission,
    GetMission,
    GetTimeline,
    InMemoryMissionRepository,
    ListMissions,
    MissionArchivedError,
    MissionKind,
    MissionNotFound,
    MissionService,
    MissionStatus,
    PauseMission,
    RecordCheckpoint,
    RecordPlan,
    ResumeMission,
    SatisfyPrecondition,
    StartMission,
    TransitionMission,
    TransitionRefused,
)
from backend.contexts.mission.infrastructure.persistence import (
    RECORD_SCHEMA_VERSION,
    from_record,
    to_record,
)
from backend.platform.context import ExecutionContext
from backend.platform.storage import MissingExecutionContext

TO_CONCLUDED = (
    "interpreted",
    "gathering",
    "reasoning",
    "planned",
    "executing",
    "verifying",
    "concluded",
)


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="mission-tests", component="tests", source="pytest"
    )


@pytest.fixture
def tenant_context() -> ExecutionContext:
    from backend.platform.context.identity import IdentityContext

    return ExecutionContext.for_tenant(
        tenant_id="tenant-a", identity=IdentityContext.platform("tests"), source="pytest"
    )


@pytest.fixture
def repository() -> InMemoryMissionRepository:
    return InMemoryMissionRepository()


@pytest.fixture
def service(repository) -> MissionService:
    return MissionService(repository=repository)


def _create(**overrides) -> CreateMission:
    fields = dict(
        stated_goal="Investigate sustained high CPU on prod-api",
        title="High CPU incident",
        kind="investigate",
        priority="urgent",
        target="prod-api",
    )
    fields.update(overrides)
    return CreateMission(**fields)


def _ready(service, context, **overrides) -> str:
    mission_id = str(service.create(context, _create(**overrides)).mission.mission_id)
    service.record_plan(context, RecordPlan(mission_id=mission_id, plan_id="PLAN-1"))
    service.transition(
        context,
        TransitionMission(
            mission_id=mission_id, to_status="planned", reason="plan recorded", actor="orch"
        ),
    )
    service.transition(
        context,
        TransitionMission(
            mission_id=mission_id, to_status="ready", reason="cleared", actor="orch"
        ),
    )
    return mission_id


def _running(service, context, **overrides) -> str:
    mission_id = _ready(service, context, **overrides)
    service.start(context, StartMission(mission_id=mission_id))
    return mission_id


def _verified(service, context, **overrides) -> str:
    mission_id = _running(service, context, **overrides)
    for state in TO_CONCLUDED:
        service.advance_execution(
            context,
            AdvanceExecution(mission_id=mission_id, to_state=state, reason=f"-> {state}"),
        )
    return mission_id


# ----------------------------------------------------------------------
# Mission creation
# ----------------------------------------------------------------------


def test_creating_a_mission_emits_one_event_and_keeps_the_goal(service, context) -> None:
    result = service.create(context, _create())
    assert result.event_types == ("mission.runtime.created",)
    assert result.mission.stated_goal == "Investigate sustained high CPU on prod-api"
    assert result.mission.status is MissionStatus.DRAFT


def test_a_mission_without_a_goal_is_refused_before_the_service() -> None:
    with pytest.raises(ContractViolation):
        _create(stated_goal="  ")


def test_the_security_context_comes_from_the_execution_context(service, context) -> None:
    """BC-9: every cross-context message carries a tenant-scoped security context."""
    mission = service.create(context, _create()).mission
    assert mission.intent.requested_by == context.security_context


def test_preconditions_declared_at_creation_start_unsatisfied(service, context) -> None:
    """One that defaults to met is one nobody notices they never checked."""
    mission = service.create(
        context, _create(preconditions=("access.prod-cluster",))
    ).mission
    assert mission.outstanding_preconditions == ("access.prod-cluster",)


def test_saving_the_same_mission_twice_is_refused(service, context, repository) -> None:
    mission = service.create(context, _create()).mission
    with pytest.raises(DuplicateMission):
        repository.save(context, mission)


# ----------------------------------------------------------------------
# Lifecycle transitions
# ----------------------------------------------------------------------


def test_the_policy_reports_every_failure_not_the_first(service, context) -> None:
    mission_id = str(service.create(context, _create()).mission.mission_id)
    report = service.evaluate(context, mission_id, "ready")
    rules = {f.rule for f in report.blocking}
    assert "P1-legal-transition" in rules
    assert not report.may_transition


def test_planning_without_a_plan_is_refused_with_its_rule(service, context) -> None:
    mission_id = str(service.create(context, _create()).mission.mission_id)
    with pytest.raises(TransitionRefused) as caught:
        service.transition(
            context,
            TransitionMission(
                mission_id=mission_id, to_status="planned", reason="planned", actor="o"
            ),
        )
    assert any(f.rule == "P2-plan-recorded" for f in caught.value.failures)


def test_readiness_is_refused_while_a_precondition_is_outstanding(service, context) -> None:
    mission_id = str(
        service.create(context, _create(preconditions=("access.prod",))).mission.mission_id
    )
    service.record_plan(context, RecordPlan(mission_id=mission_id, plan_id="P"))
    service.transition(
        context,
        TransitionMission(
            mission_id=mission_id, to_status="planned", reason="p", actor="o"
        ),
    )
    with pytest.raises(TransitionRefused) as caught:
        service.transition(
            context,
            TransitionMission(
                mission_id=mission_id, to_status="ready", reason="r", actor="o"
            ),
        )
    assert any(f.rule == "P3-preconditions-met" for f in caught.value.failures)


def test_an_acting_mission_needs_an_authorisation_precondition(service, context) -> None:
    """The cost of a wrong observation is a wrong answer; of a wrong action, an outage."""
    mission_id = str(service.create(context, _create(kind="remediate")).mission.mission_id)
    service.record_plan(context, RecordPlan(mission_id=mission_id, plan_id="P"))
    service.transition(
        context,
        TransitionMission(mission_id=mission_id, to_status="planned", reason="p", actor="o"),
    )
    with pytest.raises(TransitionRefused) as caught:
        service.transition(
            context,
            TransitionMission(
                mission_id=mission_id, to_status="ready", reason="r", actor="o"
            ),
        )
    assert any(f.rule == "P4-authorised-to-act" for f in caught.value.failures)


def test_an_authorised_acting_mission_may_become_ready(service, context) -> None:
    mission_id = str(service.create(context, _create(kind="remediate")).mission.mission_id)
    service.record_plan(context, RecordPlan(mission_id=mission_id, plan_id="P"))
    service.transition(
        context,
        TransitionMission(mission_id=mission_id, to_status="planned", reason="p", actor="o"),
    )
    service.declare_precondition(
        context, DeclarePrecondition(mission_id=mission_id, key=AUTHORISATION_PRECONDITION)
    )
    service.satisfy_precondition(
        context,
        SatisfyPrecondition(
            mission_id=mission_id, key=AUTHORISATION_PRECONDITION, satisfied_by="sre-lead"
        ),
    )
    result = service.transition(
        context,
        TransitionMission(mission_id=mission_id, to_status="ready", reason="authorised", actor="o"),
    )
    assert result.mission.status is MissionStatus.READY


def test_an_observing_mission_needs_no_authorisation(service, context) -> None:
    assert not MissionKind.INVESTIGATE.changes_the_world
    assert MissionKind.REMEDIATE.changes_the_world
    mission_id = _ready(service, context)
    assert service.get(context, GetMission(mission_id=mission_id)).status is MissionStatus.READY


def test_a_transition_without_a_reason_is_refused_by_the_command() -> None:
    with pytest.raises(ContractViolation):
        TransitionMission(mission_id="M", to_status="ready", reason="  ", actor="o")


def test_a_transition_without_an_actor_is_refused_by_the_command() -> None:
    with pytest.raises(ContractViolation):
        TransitionMission(mission_id="M", to_status="ready", reason="because", actor=" ")


# ----------------------------------------------------------------------
# Running, pausing, resuming
# ----------------------------------------------------------------------


def test_starting_opens_an_execution_and_emits_started(service, context) -> None:
    mission_id = _ready(service, context)
    result = service.start(context, StartMission(mission_id=mission_id))
    assert result.event_types == ("mission.runtime.started",)
    assert result.mission.current_execution.attempt == 1


def test_pausing_records_where_it_can_resume_from(service, context) -> None:
    mission_id = _running(service, context)
    service.advance_execution(
        context, AdvanceExecution(mission_id=mission_id, to_state="interpreted", reason="i")
    )
    service.record_checkpoint(
        context, RecordCheckpoint(mission_id=mission_id, label="intent understood")
    )
    result = service.pause(
        context, PauseMission(mission_id=mission_id, reason="awaiting change window")
    )
    assert result.event_types == ("mission.runtime.paused",)
    assert result.mission.status is MissionStatus.PAUSED


def test_pausing_without_a_checkpoint_is_flagged_advisory(service, context) -> None:
    """Worth knowing before the pause, not after."""
    mission_id = _running(service, context)
    report = service.evaluate(context, mission_id, "paused")
    assert report.may_transition
    assert any(f.rule == "P7-resumable" for f in report.advisory)


def test_resuming_restores_the_state_the_checkpoint_captured(service, context) -> None:
    mission_id = _running(service, context)
    for state in ("interpreted", "gathering", "reasoning", "planned", "executing"):
        service.advance_execution(
            context, AdvanceExecution(mission_id=mission_id, to_state=state, reason="on")
        )
    service.record_checkpoint(
        context, RecordCheckpoint(mission_id=mission_id, label="mid-execution")
    )
    service.pause(context, PauseMission(mission_id=mission_id, reason="window closed"))

    result = service.resume(context, ResumeMission(mission_id=mission_id, reason="window open"))
    assert result.event_types == ("mission.runtime.resumed",)
    assert result.mission.execution_state is MissionState.EXECUTING
    assert result.mission.current_execution.attempt == 2
    assert result.mission.timeline_agrees()


def test_a_checkpoint_emits_its_own_event_with_a_digest(service, context) -> None:
    mission_id = _running(service, context)
    service.advance_execution(
        context, AdvanceExecution(mission_id=mission_id, to_state="interpreted", reason="i")
    )
    result = service.record_checkpoint(
        context, RecordCheckpoint(mission_id=mission_id, label="intent understood")
    )
    assert result.event_types == ("mission.runtime.checkpoint_reached",)
    assert result.mission.latest_checkpoint.digest


def test_a_checkpoint_outside_running_is_refused(service, context) -> None:
    mission_id = _ready(service, context)
    with pytest.raises(ContractViolation):
        service.record_checkpoint(
            context, RecordCheckpoint(mission_id=mission_id, label="too early")
        )


# ----------------------------------------------------------------------
# The verification gate
# ----------------------------------------------------------------------


def test_completion_is_refused_over_unverified_work(service, context) -> None:
    """The rule PR-M1's two-layer lifecycle exists to preserve."""
    mission_id = _running(service, context)
    for state in ("interpreted", "gathering", "reasoning", "planned", "executing"):
        service.advance_execution(
            context, AdvanceExecution(mission_id=mission_id, to_state=state, reason="on")
        )
    with pytest.raises(TransitionRefused) as caught:
        service.complete(context, CompleteMission(mission_id=mission_id))
    assert any(f.rule == "P5-verified-before-complete" for f in caught.value.failures)


def test_completion_succeeds_once_verified(service, context) -> None:
    mission_id = _verified(service, context)
    result = service.complete(context, CompleteMission(mission_id=mission_id))
    assert result.event_types == ("mission.runtime.completed",)
    assert result.mission.status is MissionStatus.COMPLETED


def test_the_completed_event_cannot_describe_unverified_work() -> None:
    """An event that could would make the log a worse record than the aggregate."""
    from backend.contexts.mission import MissionCompleted
    from backend.platform.events import EventMetadata
    from backend.contracts.tenant import TenantRef, TenantScope

    metadata = EventMetadata.create(
        aggregate_id="M-1",
        aggregate_type="mission",
        scope=TenantScope(tenant=TenantRef(tenant_id="t")),
    )
    with pytest.raises(ContractViolation):
        MissionCompleted(
            metadata=metadata,
            mission_id="M-1",
            execution_state="executing",
            reason="done",
        )


def test_an_illegal_execution_move_is_refused_through_the_service(service, context) -> None:
    mission_id = _running(service, context)
    from backend.contexts.mission import IllegalExecutionTransition

    with pytest.raises(IllegalExecutionTransition):
        service.advance_execution(
            context,
            AdvanceExecution(mission_id=mission_id, to_state="concluded", reason="skip"),
        )


# ----------------------------------------------------------------------
# Failure, cancellation, archival
# ----------------------------------------------------------------------


def test_failing_records_why_and_counts_attempts(service, context) -> None:
    mission_id = _running(service, context)
    result = service.fail(
        context, FailMission(mission_id=mission_id, reason="the host was rebuilt mid-run")
    )
    assert result.event_types == ("mission.runtime.failed",)
    assert result.mission.outcome_note == "the host was rebuilt mid-run"


def test_a_mission_that_never_ran_cannot_fail(service, context) -> None:
    mission_id = _ready(service, context)
    with pytest.raises(TransitionRefused):
        service.fail(context, FailMission(mission_id=mission_id, reason="never started"))


def test_cancelling_records_where_it_was_cancelled_from(service, context) -> None:
    mission_id = _ready(service, context)
    result = service.cancel(
        context,
        CancelMission(mission_id=mission_id, reason="incident resolved itself", actor="sre"),
    )
    assert result.event_types == ("mission.runtime.cancelled",)
    assert result.mission.status is MissionStatus.CANCELLED


def test_archiving_seals_the_record_and_binds_a_digest(service, context) -> None:
    mission_id = _verified(service, context)
    service.complete(context, CompleteMission(mission_id=mission_id))
    result = service.archive(context, ArchiveMission(mission_id=mission_id))
    assert result.event_types == ("mission.runtime.archived",)
    result.mission.verify_digest()


def test_an_archived_mission_refuses_further_movement(service, context) -> None:
    mission_id = _verified(service, context)
    service.complete(context, CompleteMission(mission_id=mission_id))
    service.archive(context, ArchiveMission(mission_id=mission_id))
    with pytest.raises(MissionArchivedError):
        service.record_checkpoint(
            context, RecordCheckpoint(mission_id=mission_id, label="late")
        )


def test_archiving_a_live_mission_is_refused(service, context) -> None:
    mission_id = _running(service, context)
    with pytest.raises(TransitionRefused):
        service.archive(context, ArchiveMission(mission_id=mission_id))


# ----------------------------------------------------------------------
# Queries
# ----------------------------------------------------------------------


def test_the_timeline_is_readable_and_ordered(service, context) -> None:
    mission_id = _running(service, context)
    timeline = service.timeline(context, GetTimeline(mission_id=mission_id))
    assert [e.sequence for e in timeline] == list(range(1, len(timeline) + 1))
    assert all(e.reason.strip() for e in timeline)


def test_listing_filters_by_status_kind_and_liveness(service, context) -> None:
    _running(service, context)
    _ready(service, context, title="second", kind="monitor")

    assert len(service.list(context, ListMissions())) == 2
    assert len(service.list(context, ListMissions(status="running"))) == 1
    assert len(service.list(context, ListMissions(kind="monitor"))) == 1
    assert len(service.list(context, ListMissions(live_only=True))) == 1


def test_an_unknown_mission_is_reported_as_missing(service, context) -> None:
    from backend.contexts.mission import MissionId

    with pytest.raises(MissionNotFound):
        service.get(context, GetMission(mission_id=str(MissionId.new())))


# ----------------------------------------------------------------------
# Repository
# ----------------------------------------------------------------------


def test_every_repository_method_requires_an_execution_context(repository) -> None:
    from backend.contexts.mission import MissionId

    for call in (
        lambda: repository.find(None, MissionId.new()),
        lambda: repository.all(None),
    ):
        with pytest.raises(MissingExecutionContext):
            call()


def test_a_tenant_cannot_see_another_tenants_mission(repository, tenant_context) -> None:
    from backend.platform.context.identity import IdentityContext
    from backend.platform.storage import CrossTenantAccess

    service = MissionService(repository=repository)
    mission = service.create(tenant_context, _create()).mission

    other = ExecutionContext.for_tenant(
        tenant_id="tenant-b", identity=IdentityContext.platform("tests"), source="pytest"
    )
    assert repository.find(other, mission.mission_id) is None
    with pytest.raises(CrossTenantAccess):
        repository.replace(other, mission)


def test_the_repository_is_not_grandfathered() -> None:
    from backend.platform.architecture.tenancy_rules import GRANDFATHERED_REPOSITORIES

    offenders = [
        entry
        for entry in GRANDFATHERED_REPOSITORIES
        if "contexts.mission" in entry or "contexts/mission" in entry
    ]
    assert offenders == []


# ----------------------------------------------------------------------
# Replay
# ----------------------------------------------------------------------


def test_a_mission_survives_the_round_trip_unchanged(service, context) -> None:
    mission_id = _verified(service, context)
    service.complete(context, CompleteMission(mission_id=mission_id))
    archived = service.archive(context, ArchiveMission(mission_id=mission_id)).mission

    restored = from_record(to_record(archived, tenant_id="tenant-a"))
    assert restored == archived


def test_the_timeline_survives_replay_entry_for_entry(service, context) -> None:
    mission_id = _running(service, context)
    mission = service.get(context, GetMission(mission_id=mission_id))
    restored = from_record(to_record(mission, tenant_id="tenant-a"))

    assert len(restored.timeline) == len(mission.timeline)
    assert [e.reason for e in restored.timeline] == [e.reason for e in mission.timeline]
    assert restored.timeline_agrees()


def test_replay_reconstructs_the_status_from_the_timeline(service, context) -> None:
    """The check that makes the timeline authoritative rather than decorative."""
    mission_id = _verified(service, context)
    mission = service.get(context, GetMission(mission_id=mission_id))
    assert mission.replayed_status() is mission.status
    assert mission.replayed_execution_state() is mission.execution_state


def test_the_digest_is_restored_not_recomputed(service, context) -> None:
    """Recomputing on load would make verification always pass."""
    from backend.contexts.mission import DigestMismatch

    mission_id = _verified(service, context)
    service.complete(context, CompleteMission(mission_id=mission_id))
    archived = service.archive(context, ArchiveMission(mission_id=mission_id)).mission

    stored = to_record(archived, tenant_id="tenant-a")
    stored["outcome_note"] = "something else entirely"
    with pytest.raises(DigestMismatch):
        from_record(stored).verify_digest()


def test_a_mission_from_an_unknown_schema_version_is_refused(service, context) -> None:
    mission = service.create(context, _create()).mission
    stored = to_record(mission, tenant_id="tenant-a")
    stored["schema_version"] = RECORD_SCHEMA_VERSION + 1
    with pytest.raises(ContractViolation):
        from_record(stored)


def test_a_mission_stored_without_a_tenant_is_refused(service, context) -> None:
    mission = service.create(context, _create()).mission
    with pytest.raises(ContractViolation):
        to_record(mission, tenant_id="  ")


# ----------------------------------------------------------------------
# Concurrency
# ----------------------------------------------------------------------


def test_concurrent_mission_creation_all_persists(service, context) -> None:
    errors: list = []

    def create_one(index: int) -> None:
        try:
            service.create(context, _create(title=f"mission-{index}"))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=create_one, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(service.list(context, ListMissions())) == 8


def test_concurrent_reads_during_writes_do_not_tear(service, context) -> None:
    seen: list = []
    errors: list = []
    stop = threading.Event()

    def write() -> None:
        try:
            for index in range(6):
                service.create(context, _create(title=f"m-{index}"))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)
        finally:
            stop.set()

    def read() -> None:
        while not stop.is_set():
            try:
                seen.append(len(service.list(context, ListMissions())))
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
        routes, "_service", MissionService(repository=InMemoryMissionRepository())
    )
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def _create_via_api(client, **overrides) -> str:
    payload = dict(
        stated_goal="Investigate sustained high CPU on prod-api",
        title="High CPU incident",
        kind="investigate",
        priority="urgent",
    )
    payload.update(overrides)
    response = client.post("/api/v1/missions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["mission"]["mission_id"]


def _ready_via_api(client, **overrides) -> str:
    mission_id = _create_via_api(client, **overrides)
    client.post(f"/api/v1/missions/{mission_id}/plan", json={"plan_id": "PLAN-1"})
    client.post(
        f"/api/v1/missions/{mission_id}/transition",
        json={"to_status": "planned", "reason": "plan recorded", "actor": "orch"},
    )
    client.post(
        f"/api/v1/missions/{mission_id}/transition",
        json={"to_status": "ready", "reason": "cleared", "actor": "orch"},
    )
    return mission_id


def test_the_api_creates_and_fetches_a_mission(client) -> None:
    mission_id = _create_via_api(client)
    body = client.get(f"/api/v1/missions/{mission_id}").json()
    assert body["status"] == "draft"
    assert body["execution_state"] == "received"
    assert set(body["permitted_transitions"]) == {"planned", "cancelled"}


def test_the_api_runs_a_mission_to_archival(client) -> None:
    mission_id = _ready_via_api(client)
    assert client.post(f"/api/v1/missions/{mission_id}/start", json={}).status_code == 200

    for state in TO_CONCLUDED:
        response = client.post(
            f"/api/v1/missions/{mission_id}/execution/advance",
            json={"to_state": state, "reason": f"-> {state}"},
        )
        assert response.status_code == 200, response.text

    completed = client.post(
        f"/api/v1/missions/{mission_id}/complete",
        json={"reason": "objective achieved", "actor": "orch"},
    )
    assert completed.status_code == 200
    assert completed.json()["mission"]["status"] == "completed"

    archived = client.post(
        f"/api/v1/missions/{mission_id}/archive",
        json={"reason": "sealed", "actor": "operator"},
    )
    assert archived.status_code == 200
    assert archived.json()["mission"]["digest"]


def test_the_api_refuses_completion_over_unverified_work(client) -> None:
    mission_id = _ready_via_api(client)
    client.post(f"/api/v1/missions/{mission_id}/start", json={})
    response = client.post(
        f"/api/v1/missions/{mission_id}/complete",
        json={"reason": "looks done", "actor": "orch"},
    )
    assert response.status_code == 422
    rules = {f["rule"] for f in response.json()["detail"]["failures"]}
    assert "P5-verified-before-complete" in rules


def test_the_api_refuses_an_illegal_transition_with_what_is_permitted(client) -> None:
    mission_id = _create_via_api(client)
    response = client.post(
        f"/api/v1/missions/{mission_id}/transition",
        json={"to_status": "running", "reason": "go", "actor": "orch"},
    )
    assert response.status_code == 422
    assert any(
        f["rule"] == "P1-legal-transition" for f in response.json()["detail"]["failures"]
    )


def test_the_api_reports_the_timeline(client) -> None:
    mission_id = _ready_via_api(client)
    body = client.get(f"/api/v1/missions/{mission_id}/timeline").json()
    assert body["count"] >= 2
    assert [e["sequence"] for e in body["entries"]] == list(range(1, body["count"] + 1))
    assert all(e["reason"] for e in body["entries"])


def test_the_policy_endpoint_reports_without_transitioning(client) -> None:
    mission_id = _create_via_api(client)
    body = client.get(f"/api/v1/missions/{mission_id}/policy?to_status=ready").json()
    assert not body["may_transition"]
    assert client.get(f"/api/v1/missions/{mission_id}").json()["status"] == "draft"


def test_the_api_records_a_checkpoint_and_resumes_from_it(client) -> None:
    mission_id = _ready_via_api(client)
    client.post(f"/api/v1/missions/{mission_id}/start", json={})
    for state in ("interpreted", "gathering", "reasoning", "planned", "executing"):
        client.post(
            f"/api/v1/missions/{mission_id}/execution/advance",
            json={"to_state": state, "reason": "on"},
        )
    checkpoint = client.post(
        f"/api/v1/missions/{mission_id}/checkpoints", json={"label": "mid-execution"}
    )
    assert checkpoint.status_code == 200

    client.post(
        f"/api/v1/missions/{mission_id}/pause",
        json={"reason": "window closed", "actor": "sre"},
    )
    resumed = client.post(
        f"/api/v1/missions/{mission_id}/resume",
        json={"reason": "window open", "actor": "sre"},
    )
    assert resumed.status_code == 200
    body = resumed.json()["mission"]
    assert body["execution_state"] == "executing"
    assert body["current_execution"]["attempt"] == 2


def test_the_api_returns_409_on_an_archived_mission(client) -> None:
    mission_id = _ready_via_api(client)
    client.post(
        f"/api/v1/missions/{mission_id}/cancel",
        json={"reason": "no longer needed", "actor": "sre"},
    )
    client.post(
        f"/api/v1/missions/{mission_id}/archive", json={"reason": "sealed", "actor": "op"}
    )
    response = client.post(
        f"/api/v1/missions/{mission_id}/checkpoints", json={"label": "late"}
    )
    assert response.status_code == 409


def test_the_api_returns_404_for_an_unknown_mission(client) -> None:
    from backend.contexts.mission import MissionId

    assert client.get(f"/api/v1/missions/{MissionId.new()}").status_code == 404


def test_the_api_lists_and_filters(client) -> None:
    _create_via_api(client)
    _create_via_api(client, title="monitor", kind="monitor")
    assert client.get("/api/v1/missions").json()["count"] == 2
    assert client.get("/api/v1/missions?kind=monitor").json()["count"] == 1


def test_the_api_rejects_an_unknown_kind(client) -> None:
    response = client.post(
        "/api/v1/missions",
        json={"stated_goal": "g", "title": "t", "kind": "teleport"},
    )
    assert response.status_code == 422


# ----------------------------------------------------------------------
# Constitution compliance
# ----------------------------------------------------------------------


def _modules() -> list:
    root = pathlib.Path("backend/contexts/mission")
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
    permitted = ("backend.contracts", "backend.platform", "backend.contexts.mission")
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.") and not imported.startswith(permitted)
    ]
    assert offences == [], offences


def test_the_context_imports_no_other_bounded_context() -> None:
    """BND-CONTEXT-ISOLATION. ``mission`` is BC-1, one of the Constitution's nine."""
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.contexts.")
        and not imported.startswith("backend.contexts.mission")
    ]
    assert offences == [], offences


def test_mission_runtime_performs_no_work() -> None:
    """The rule the whole context rests on, asserted against the import graph.

    A runtime that could reach an executor, a planner, an LLM, or a connector
    would stop being an orchestrator the first time someone found it convenient.
    """
    forbidden = (
        "backend.execution",
        "backend.orchestrator",
        "backend.orchestration",
        "backend.llm",
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
    root = pathlib.Path("backend/contexts/mission/domain")
    offences = [
        f"{path}: {imported}"
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
        for imported in _imports(path)
        if imported.split(".")[0] in banned
    ]
    assert offences == [], offences


def test_the_context_uses_the_published_mission_contract() -> None:
    """S4's lifecycle is not this context's to redefine, so it is imported.

    The alternative -- a second copy of the transition table -- would drift with
    nothing catching the drift, which is exactly what ADR-023 refused elsewhere.
    """
    users = [
        path.name
        for path in _modules()
        if any(i == "backend.contracts.mission" for i in _imports(path))
    ]
    assert "execution.py" in users, "the S4 table must be enforced through the contract"


def test_event_types_are_namespaced_and_disjoint() -> None:
    from backend.contexts.context_bundle import CONTEXT_EVENT_TYPES
    from backend.contexts.engineering import RUNTIME_EVENT_TYPES
    from backend.contexts.engineering_verification import VERIFICATION_EVENT_TYPES
    from backend.contexts.implementation_record import IMPLEMENTATION_EVENT_TYPES
    from backend.contexts.mission import MISSION_EVENT_TYPES
    from backend.contexts.review import REVIEW_EVENT_TYPES

    ours = {e.EVENT_TYPE for e in MISSION_EVENT_TYPES}
    assert all(e.startswith("mission.runtime.") for e in ours)
    assert len(ours) == 9
    for other in (
        CONTEXT_EVENT_TYPES,
        RUNTIME_EVENT_TYPES,
        VERIFICATION_EVENT_TYPES,
        IMPLEMENTATION_EVENT_TYPES,
        REVIEW_EVENT_TYPES,
    ):
        assert ours.isdisjoint({e.EVENT_TYPE for e in other})


def test_the_route_module_does_not_import_a_second_context() -> None:
    path = pathlib.Path("backend/api/mission_runtime_routes.py")
    contexts = {
        imported.split(".")[2]
        for imported in _imports(path)
        if imported.startswith("backend.contexts.") and len(imported.split(".")) > 2
    }
    assert contexts == {"mission"}, contexts
