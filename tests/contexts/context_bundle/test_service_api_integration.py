"""Service, repository, replay, concurrency, API, and the runtime wiring.

The integration section pins the claim this PR rests on: wiring Context unblocks
``assigned -> spec_tests -> implementation``, which is where the lifecycle
actually stalled, and stops precisely at Review.
"""

from __future__ import annotations

import ast
import pathlib
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import context_bundle_routes as routes
from backend.api.engineering_composition import (
    ContextBundleServiceAdapter,
    build_engineering_runtime,
)
from backend.contracts.errors import ContractViolation
from backend.contexts.context_bundle import (
    AssembleBundle,
    BundleId,
    BundleNotFound,
    ContextBundleService,
    ContextLayer,
    DecideExpansion,
    DuplicateBundle,
    ExpansionDenied,
    GetBundle,
    InMemoryContextRepository,
    InvalidateBundle,
    ListBundles,
    RequestExpansion,
    ResolveBundle,
    assemble,
    dependency,
    reference,
)
from backend.contexts.context_bundle.infrastructure.persistence import from_record, to_record
from backend.contexts.engineering import CollaboratorUnavailable, ContextPort, GetLifecycleCapability
from backend.platform.context import ExecutionContext
from backend.platform.storage import MissingExecutionContext

BASE = "abc123def456"


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="context-bundle-tests", component="tests", source="pytest"
    )


@pytest.fixture
def tenant_context() -> ExecutionContext:
    from backend.platform.context.identity import IdentityContext

    return ExecutionContext.for_tenant(
        tenant_id="tenant-a", identity=IdentityContext.platform("tests"), source="pytest"
    )


@pytest.fixture
def repository() -> InMemoryContextRepository:
    return InMemoryContextRepository()


@pytest.fixture
def service(repository) -> ContextBundleService:
    return ContextBundleService(repository=repository)


def _assemble_command(**overrides) -> AssembleBundle:
    fields = dict(
        work_id="WO-1",
        work_order_version=1,
        base_commit=BASE,
        blast_radius_allowed=("backend/contexts/context_bundle/**",),
        searchable=("**",),
        adr_references=("ADR-022",),
        dependencies=(("storage", ("backend/platform/storage",), ()),),
        references=(("backend/contexts/context_bundle/domain/bundle.py", "owned", "d1"),),
    )
    fields.update(overrides)
    return AssembleBundle(**fields)


def _bundle(work_id="WO-1"):
    return assemble(
        work_id=work_id, work_order_version=1, base_commit=BASE,
        blast_radius=["backend/contexts/context_bundle/**"], searchable=["**"],
        adr_references=["ADR-022"],
        dependencies=[dependency("storage", ["backend/platform/storage"])],
        references=[reference("backend/contexts/context_bundle/domain/bundle.py", ContextLayer.OWNED)],
    )


# ----------------------------------------------------------------------
# Service
# ----------------------------------------------------------------------


def test_assembly_persists_and_emits(service, context, repository):
    result = service.assemble(context, _assemble_command())
    assert result.event_types == ("engineering.context.bundle_created",)
    assert result.bundle.manifest_digest
    assert len(repository) == 1


def test_assembly_requires_a_base_commit(service, context):
    with pytest.raises(ContractViolation):
        _assemble_command(base_commit="   ")


def test_the_three_expansion_steps_are_separate(service, context):
    """A grant whose assembly then fails must not look like a denial."""
    created = service.assemble(context, _assemble_command())
    bundle_id = str(created.bundle.bundle_id)

    requested = service.request_expansion(
        context,
        RequestExpansion(
            bundle_id=bundle_id, requested_path="backend/services/x.py",
            question="does it write state?", requested_by="implementer",
        ),
    )
    request_id = str(requested.bundle.expansions[0].request_id)
    assert requested.bundle.pending_expansions

    decided = service.decide_expansion(
        context,
        DecideExpansion(
            bundle_id=bundle_id, request_id=request_id, grant=True, decided_by="architect"
        ),
    )
    assert not decided.bundle.pending_expansions
    assert decided.bundle.version == 1, "deciding must not widen"

    applied = service.apply_expansion(
        context, bundle_id, request_id,
        (("backend/services/x.py", "dependencies", "d2"),),
    )
    assert applied.bundle.version == 2
    assert set(applied.event_types) == {
        "engineering.context.expanded",
        "engineering.context.versioned",
        "engineering.context.superseded",
    }


def test_applying_a_denied_expansion_raises(service, context):
    """Silently no-op'ing would let a caller believe the bundle grew."""
    created = service.assemble(context, _assemble_command())
    bundle_id = str(created.bundle.bundle_id)
    requested = service.request_expansion(
        context,
        RequestExpansion(
            bundle_id=bundle_id, requested_path="backend/services/x.py",
            question="why?", requested_by="impl",
        ),
    )
    request_id = str(requested.bundle.expansions[0].request_id)
    service.decide_expansion(
        context,
        DecideExpansion(
            bundle_id=bundle_id, request_id=request_id, grant=False,
            decided_by="architect", reason="outside the declared boundary",
        ),
    )

    with pytest.raises(ExpansionDenied):
        service.apply_expansion(context, bundle_id, request_id, ())


def test_auto_grant_beats_an_explicit_denial(service, context):
    """Denying an ADR the bundle's own index names would make it self-inconsistent."""
    created = service.assemble(context, _assemble_command())
    bundle_id = str(created.bundle.bundle_id)
    requested = service.request_expansion(
        context,
        RequestExpansion(
            bundle_id=bundle_id, requested_path="docs/adr/ADR-022-x.md",
            question="what did it decide?", requested_by="impl", target_layer="adr_bundle",
        ),
    )
    request_id = str(requested.bundle.expansions[0].request_id)

    decided = service.decide_expansion(
        context,
        DecideExpansion(
            bundle_id=bundle_id, request_id=request_id, grant=False,
            decided_by="architect", reason="no",
        ),
    )
    assert decided.bundle.expansions[0].disposition.value == "auto_granted"


def test_expansion_supersedes_the_previous_version(service, context, repository):
    created = service.assemble(context, _assemble_command())
    bundle_id = str(created.bundle.bundle_id)
    requested = service.request_expansion(
        context,
        RequestExpansion(bundle_id=bundle_id, requested_path="backend/services/x.py",
                         question="why?", requested_by="impl"),
    )
    request_id = str(requested.bundle.expansions[0].request_id)
    service.decide_expansion(
        context, DecideExpansion(bundle_id=bundle_id, request_id=request_id,
                                 grant=True, decided_by="architect")
    )
    service.apply_expansion(
        context, bundle_id, request_id, (("backend/services/x.py", "dependencies", "d2"),)
    )

    retired = service.get(context, GetBundle(bundle_id=bundle_id))
    assert retired.status.value == "superseded"
    assert service.current_for(context, "WO-1").version == 2


def test_current_for_skips_invalidated_bundles(service, context):
    created = service.assemble(context, _assemble_command())
    service.invalidate(
        context,
        InvalidateBundle(bundle_id=str(created.bundle.bundle_id), reason="the tree moved"),
    )
    assert service.current_for(context, "WO-1") is None


def test_resolution_emits_and_returns_the_agent_view(service, context):
    created = service.assemble(context, _assemble_command())
    resolved, events = service.resolve(
        context,
        ResolveBundle(
            bundle_id=str(created.bundle.bundle_id),
            resolved_for="implementer",
            current_commit=BASE,
        ),
    )
    assert resolved.writable == ("backend/contexts/context_bundle/domain/bundle.py",)
    assert [e.EVENT_TYPE for e in events] == ["engineering.context.resolved"]


def test_boundary_signals_surface_across_work_orders(service, context):
    for index in range(3):
        created = service.assemble(context, _assemble_command(work_id=f"WO-{index}"))
        service.request_expansion(
            context,
            RequestExpansion(
                bundle_id=str(created.bundle.bundle_id),
                requested_path="backend/services/shared.py",
                question=f"question {index}", requested_by="impl",
            ),
        )
    signals = service.boundary_signals(context)
    assert signals and signals[0].crosses_work_orders


# ----------------------------------------------------------------------
# Repository
# ----------------------------------------------------------------------


def test_every_repository_method_refuses_a_missing_context(repository):
    bundle = _bundle()
    with pytest.raises(MissingExecutionContext):
        repository.save(None, bundle)
    with pytest.raises(MissingExecutionContext):
        repository.find(None, BundleId.new())
    with pytest.raises(MissingExecutionContext):
        repository.for_work_order(None, "WO-1")
    with pytest.raises(MissingExecutionContext):
        repository.all(None)
    with pytest.raises(MissingExecutionContext):
        repository.clear(None)


def test_a_tenant_context_does_not_see_another_tenants_bundles(repository, tenant_context):
    from backend.platform.context.identity import IdentityContext

    other = ExecutionContext.for_tenant(
        tenant_id="tenant-b", identity=IdentityContext.platform("tests"), source="pytest"
    )
    repository.save(tenant_context, _bundle())
    assert len(repository.all(tenant_context)) == 1
    assert repository.all(other) == ()


def test_saving_the_same_bundle_twice_is_refused(repository, context):
    """A version is immutable: its digest is what makes it checkable."""
    bundle = _bundle()
    repository.save(context, bundle)
    with pytest.raises(DuplicateBundle):
        repository.save(context, bundle)


def test_replace_requires_the_bundle_to_exist(repository, context):
    with pytest.raises(BundleNotFound):
        repository.replace(context, _bundle())


# ----------------------------------------------------------------------
# Round trip and replay
# ----------------------------------------------------------------------


def test_record_round_trip_preserves_everything():
    assert from_record(to_record(_bundle(), tenant_id="t")) == _bundle.__wrapped__() if False else True
    bundle = _bundle()
    assert from_record(to_record(bundle, tenant_id="t")) == bundle


def test_round_trip_preserves_expansion_history():
    from backend.contexts.context_bundle import ExpansionRequest

    bundle = _bundle()
    request = ExpansionRequest.create("backend/services/x.py", "why?", "impl")
    staged = bundle.request_expansion(request)
    decided = staged.decide_expansion(
        request.request_id, request.deny("architect", "outside the boundary")
    )
    assert from_record(to_record(decided, tenant_id="t")) == decided


def test_the_manifest_digest_is_restored_not_recomputed():
    """Recomputing would make the digest always match -- a check that cannot fail."""
    from dataclasses import replace

    bundle = _bundle()
    stored = to_record(bundle, tenant_id="t")
    stored["references"].append(
        {"path": "backend/smuggled.py", "layer": "dependencies", "content_digest": "x", "note": None}
    )

    restored = from_record(stored)
    from backend.contexts.context_bundle import ManifestMismatch

    with pytest.raises(ManifestMismatch):
        restored.verify_manifest()


def test_an_unknown_record_schema_is_refused():
    stored = to_record(_bundle(), tenant_id="t")
    stored["schema_version"] = 99
    with pytest.raises(ContractViolation):
        from_record(stored)


def test_replay_reproduces_the_same_manifest(repository, context):
    """Persist, reload, verify: the digest must still hold."""
    bundle = _bundle()
    repository.save(context, bundle)
    reloaded = repository.find(context, bundle.bundle_id)

    reloaded.verify_manifest()
    assert reloaded.manifest_digest == bundle.manifest_digest
    assert reloaded.resolve(current_commit=BASE).writable == (
        bundle.resolve(current_commit=BASE).writable
    )


# ----------------------------------------------------------------------
# Concurrency
# ----------------------------------------------------------------------


def test_concurrent_assembly_loses_nothing(service, context, repository):
    errors: list = []

    def worker(index: int) -> None:
        try:
            for version in range(1, 6):
                service.assemble(
                    context,
                    _assemble_command(work_id=f"WO-{index}", work_order_version=version),
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(repository) == 40


def test_concurrent_expansions_of_distinct_bundles_do_not_interfere(service, context):
    errors: list = []

    def worker(index: int) -> None:
        try:
            created = service.assemble(context, _assemble_command(work_id=f"WO-{index}"))
            bundle_id = str(created.bundle.bundle_id)
            requested = service.request_expansion(
                context,
                RequestExpansion(bundle_id=bundle_id, requested_path="backend/services/x.py",
                                 question="why?", requested_by="impl"),
            )
            request_id = str(requested.bundle.expansions[0].request_id)
            service.decide_expansion(
                context, DecideExpansion(bundle_id=bundle_id, request_id=request_id,
                                         grant=True, decided_by="architect")
            )
            widened = service.apply_expansion(
                context, bundle_id, request_id,
                (("backend/services/x.py", "dependencies", "d2"),),
            )
            if widened.bundle.version != 2:
                errors.append((index, widened.bundle.version))
        except Exception as exc:  # noqa: BLE001
            errors.append((index, exc))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(
        routes, "_service", ContextBundleService(repository=InMemoryContextRepository())
    )
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def _body(**overrides) -> dict:
    body = {
        "work_id": "WO-1",
        "base_commit": BASE,
        "blast_radius_allowed": ["backend/contexts/context_bundle/**"],
        "searchable": ["**"],
        "adr_references": ["ADR-022"],
        "references": [
            {
                "path": "backend/contexts/context_bundle/domain/bundle.py",
                "layer": "owned",
                "content_digest": "d1",
            }
        ],
    }
    body.update(overrides)
    return body


def test_assemble_returns_201(client):
    response = client.post("/api/v1/engineering/context", json=_body())
    assert response.status_code == 201
    assert response.json()["bundle"]["manifest_digest"]


def test_a_bundle_with_no_blast_radius_is_422(client):
    assert client.post(
        "/api/v1/engineering/context", json=_body(blast_radius_allowed=[])
    ).status_code == 422


def test_a_bundle_with_no_search_scope_is_422(client):
    assert client.post(
        "/api/v1/engineering/context", json=_body(searchable=[])
    ).status_code == 422


def test_a_stale_resolve_is_410(client):
    """Gone, in the sense that matters: what it described no longer exists."""
    created = client.post("/api/v1/engineering/context", json=_body()).json()
    bundle_id = created["bundle"]["bundle_id"]

    response = client.post(
        f"/api/v1/engineering/context/{bundle_id}/resolve",
        json={"resolved_for": "implementer", "current_commit": "a-different-commit"},
    )
    assert response.status_code == 410
    assert response.json()["detail"]["error"] == "stale_base_commit"


def test_applying_a_denied_expansion_is_409(client):
    created = client.post("/api/v1/engineering/context", json=_body()).json()
    bundle_id = created["bundle"]["bundle_id"]

    requested = client.post(
        f"/api/v1/engineering/context/{bundle_id}/expansions",
        json={"requested_path": "backend/services/x.py", "question": "why?",
              "requested_by": "impl"},
    ).json()
    request_id = requested["bundle"]["expansions"][0]["request_id"]

    client.post(
        f"/api/v1/engineering/context/{bundle_id}/expansions/{request_id}/decide",
        json={"grant": False, "decided_by": "architect", "reason": "outside the boundary"},
    )
    response = client.post(
        f"/api/v1/engineering/context/{bundle_id}/expansions/{request_id}/apply",
        json={"references": []},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "expansion_denied"


def test_smuggling_a_path_outside_the_grant_is_400(client):
    created = client.post("/api/v1/engineering/context", json=_body()).json()
    bundle_id = created["bundle"]["bundle_id"]
    requested = client.post(
        f"/api/v1/engineering/context/{bundle_id}/expansions",
        json={"requested_path": "backend/services/allowed", "question": "why?",
              "requested_by": "impl"},
    ).json()
    request_id = requested["bundle"]["expansions"][0]["request_id"]
    client.post(
        f"/api/v1/engineering/context/{bundle_id}/expansions/{request_id}/decide",
        json={"grant": True, "decided_by": "architect"},
    )

    response = client.post(
        f"/api/v1/engineering/context/{bundle_id}/expansions/{request_id}/apply",
        json={"references": [{"path": "backend/services/other.py", "layer": "dependencies",
                              "content_digest": "d"}]},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "implicit_expansion"


def test_a_request_without_a_question_is_refused(client):
    created = client.post("/api/v1/engineering/context", json=_body()).json()
    bundle_id = created["bundle"]["bundle_id"]
    response = client.post(
        f"/api/v1/engineering/context/{bundle_id}/expansions",
        json={"requested_path": "a/b.py", "question": "   ", "requested_by": "impl"},
    )
    assert response.status_code in (400, 422)


def test_an_unknown_bundle_is_404(client):
    assert client.get(
        f"/api/v1/engineering/context/{BundleId.new()}"
    ).status_code == 404


def test_a_malformed_id_is_400(client):
    assert client.get("/api/v1/engineering/context/not-a-ulid").status_code == 400


def test_signals_endpoint_reports_repeated_requests(client):
    for index in range(2):
        created = client.post(
            "/api/v1/engineering/context", json=_body(work_id=f"WO-{index}")
        ).json()
        client.post(
            f"/api/v1/engineering/context/{created['bundle']['bundle_id']}/expansions",
            json={"requested_path": "backend/services/shared.py", "question": "why?",
                  "requested_by": "impl"},
        )
    body = client.get("/api/v1/engineering/context/signals").json()
    assert body["count"] == 1
    assert body["signals"][0]["crosses_work_orders"] is True


def test_every_route_is_versioned(client):
    for route in client.app.routes:
        path = getattr(route, "path", "")
        if "engineering" in path:
            assert path.startswith("/api/v1/engineering/context"), path


def test_openapi_documents_every_endpoint(client):
    schema = client.app.openapi()
    paths = [p for p in schema["paths"] if "context" in p]
    assert len(paths) == 8
    for path in paths:
        for operation in schema["paths"][path].values():
            assert operation.get("summary"), f"{path} has no summary"


# ----------------------------------------------------------------------
# Runtime wiring
# ----------------------------------------------------------------------


def test_the_adapter_satisfies_the_port():
    stack = build_engineering_runtime()
    adapter = ContextBundleServiceAdapter(stack.context_service, object())
    assert isinstance(adapter, ContextPort)


def test_wiring_context_unblocks_the_stalled_transitions():
    """The claim this PR rests on, asserted rather than described.

    ``wire_review=False`` holds PR-E4's world fixed. Review was built in PR-E6,
    so a stack with everything wired reports nothing missing -- which would make
    this test assert PR-E6's claim rather than PR-E4's.
    """
    stack = build_engineering_runtime(wire_review=False)
    capability = stack.queries.capability(GetLifecycleCapability())

    assert set(capability["missing"]) == {"review"}
    for unblocked in ("spec_tests", "implementation"):
        assert unblocked in capability["reachable_phases"]
    assert "review" not in capability["reachable_phases"]


def test_the_lifecycle_now_runs_to_implementation_and_stops_at_review():
    from backend.contexts.workorder import (
        ApproveWorkOrder, BlastRadius, DraftWorkOrder, InMemoryWorkOrderRepository,
        StaticReferenceResolver, WorkOrderService,
    )

    work_orders = WorkOrderService(
        repository=InMemoryWorkOrderRepository(),
        resolver=StaticReferenceResolver(
            known_adrs=frozenset({"ADR-022"}), known_evidence=frozenset({"EV-1"}),
            enforceable_constraints=frozenset({"I6"}),
        ),
    )
    stack = build_engineering_runtime(service=work_orders, wire_review=False)
    ctx = ExecutionContext.platform_internal(
        reason="tests", component="tests", source="pytest"
    )

    drafted = work_orders.draft(ctx, DraftWorkOrder(
        intent="The bundle grows only through a recorded expansion",
        acceptance_criteria=("Implicit expansion is refused",),
        blast_radius=BlastRadius.of(["backend/contexts/context_bundle/**"]),
        adr_references=("ADR-022",), evidence=("EV-1",), constraints=("I6",),
    ))
    work_id = str(drafted.work_order.work_id)
    work_orders.approve(ctx, ApproveWorkOrder(work_id=work_id, approved_by="founder"))

    for phase in ("assigned", "spec_tests", "implementation"):
        result = stack.runtime.transition(ctx, work_id, phase, actor="orchestrator")
    assert result.snapshot.phase.value == "implementation"

    with pytest.raises(CollaboratorUnavailable) as caught:
        stack.runtime.transition(ctx, work_id, "review", actor="x")
    assert caught.value.port == "review"


def test_the_adapter_assembles_from_the_declared_blast_radius():
    """It reads the snapshot, not the aggregate -- ADR-020's boundary holds.

    Assembly happens entering *implementation*, not spec_tests. PR-E2 requires the
    context port for both phases but only calls ``on_entering_implementation``, so
    a WorkOrder in spec_tests has a port available and no bundle assembled. Noted
    in ADR-022 as a PR-E2 inconsistency rather than patched here -- the brief
    forbids changing the runtime beyond wiring.
    """
    from backend.contexts.workorder import (
        ApproveWorkOrder, BlastRadius, DraftWorkOrder, InMemoryWorkOrderRepository,
        StaticReferenceResolver, WorkOrderService,
    )
    from backend.contexts.context_bundle import ListBundles

    work_orders = WorkOrderService(
        repository=InMemoryWorkOrderRepository(),
        resolver=StaticReferenceResolver(
            known_adrs=frozenset({"ADR-022"}), known_evidence=frozenset({"EV-1"}),
            enforceable_constraints=frozenset({"I6"}),
        ),
    )
    stack = build_engineering_runtime(service=work_orders)
    ctx = ExecutionContext.platform_internal(
        reason="tests", component="tests", source="pytest"
    )
    drafted = work_orders.draft(ctx, DraftWorkOrder(
        intent="A stated outcome",
        acceptance_criteria=("something is refused",),
        blast_radius=BlastRadius.of(["backend/contexts/context_bundle/**"]),
        adr_references=("ADR-022",), evidence=("EV-1",), constraints=("I6",),
    ))
    work_id = str(drafted.work_order.work_id)
    work_orders.approve(ctx, ApproveWorkOrder(work_id=work_id, approved_by="founder"))
    for phase in ("assigned", "spec_tests", "implementation"):
        stack.runtime.transition(ctx, work_id, phase, actor="o")

    bundles = stack.context_service.list(ctx, ListBundles(work_id=work_id))
    assert bundles
    assert bundles[0].blast_radius.allowed == ("backend/contexts/context_bundle/**",)


def test_the_previous_behaviour_is_still_testable():
    stack = build_engineering_runtime(wire_context=False)
    capability = stack.queries.capability(GetLifecycleCapability())
    assert "context" in capability["missing"]


# ----------------------------------------------------------------------
# Architecture compliance
# ----------------------------------------------------------------------


def _imports(path: pathlib.Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
    return found


def _modules() -> list:
    root = pathlib.Path("backend/contexts/context_bundle")
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def test_the_context_imports_only_contracts_and_platform():
    permitted = ("backend.contracts", "backend.platform", "backend.contexts.context_bundle")
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.") and not imported.startswith(permitted)
    ]
    assert offences == [], offences


def test_the_context_imports_no_other_bounded_context():
    offences = [
        f"{path}: {imported}"
        for path in _modules()
        for imported in _imports(path)
        if imported.startswith("backend.contexts.")
        and not imported.startswith("backend.contexts.context_bundle")
    ]
    assert offences == [], offences


def test_the_domain_layer_does_no_io():
    banned = {"pathlib", "os", "socket", "requests", "httpx", "sqlite3", "json"}
    root = pathlib.Path("backend/contexts/context_bundle/domain")
    offences = [
        f"{path}: {imported}"
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
        for imported in _imports(path)
        if imported.split(".")[0] in banned
    ]
    assert offences == [], offences


def test_the_repository_is_not_grandfathered():
    from backend.platform.architecture.tenancy_rules import GRANDFATHERED_REPOSITORIES

    for name in ("ContextRepository", "InMemoryContextRepository"):
        assert name not in GRANDFATHERED_REPOSITORIES


def test_it_does_not_collide_with_the_platform_execution_context():
    """Two things called 'context' one layer apart would be genuinely confusing."""
    assert pathlib.Path("backend/platform/context").is_dir()
    assert not pathlib.Path("backend/contexts/context").exists()
    assert pathlib.Path("backend/contexts/context_bundle").is_dir()


def test_event_types_are_namespaced_and_disjoint():
    from backend.contexts.context_bundle import CONTEXT_EVENT_TYPES
    from backend.contexts.engineering import RUNTIME_EVENT_TYPES
    from backend.contexts.engineering_verification import VERIFICATION_EVENT_TYPES

    ours = {e.EVENT_TYPE for e in CONTEXT_EVENT_TYPES}
    assert all(e.startswith("engineering.context.") for e in ours)
    assert ours.isdisjoint({e.EVENT_TYPE for e in RUNTIME_EVENT_TYPES})
    assert ours.isdisjoint({e.EVENT_TYPE for e in VERIFICATION_EVENT_TYPES})
