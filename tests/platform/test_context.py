"""Request context runtime: propagation, isolation, immutability, concurrency.

The property under test throughout: **an operation cannot execute without a
fully-populated, explicitly-supplied context, and cannot silently acquire the
wrong one.**
"""

from __future__ import annotations

import dataclasses
import threading
from datetime import datetime, timezone

import pytest

from backend.contracts import ContractViolation, PrincipalKind
from backend.platform.context import (
    PLATFORM_INTERNAL_TENANT_ID,
    CorrelationContext,
    ExecutionContext,
    FeatureFlagContext,
    IdentityContext,
    LocaleContext,
    MissionContext,
    OrganizationContext,
    RequestMetadata,
    TenantContext,
    TraceContext,
    WorkspaceContext,
)


@pytest.fixture
def identity() -> IdentityContext:
    return IdentityContext.human("user-42", capabilities=("mission:create",))


@pytest.fixture
def context(identity) -> ExecutionContext:
    return ExecutionContext.for_tenant(
        tenant_id="acme", identity=identity, source="http"
    )


# ======================================================================
# No default tenant, no implicit system tenant
# ======================================================================


class TestNoDefaultTenant:
    def test_tenant_context_cannot_be_constructed_without_a_tenant(self) -> None:
        with pytest.raises(TypeError):
            TenantContext()  # type: ignore[call-arg]

    def test_execution_context_requires_a_tenant(self, identity) -> None:
        with pytest.raises(TypeError):
            ExecutionContext.for_tenant(identity=identity, source="http")  # type: ignore[call-arg]

    def test_blank_tenant_id_is_refused(self) -> None:
        with pytest.raises(ContractViolation, match="must not be blank"):
            TenantContext.for_tenant("   ")

    def test_the_reserved_id_cannot_be_claimed_by_a_real_tenant(self) -> None:
        with pytest.raises(ContractViolation, match="reserved"):
            TenantContext.for_tenant(PLATFORM_INTERNAL_TENANT_ID)

    def test_platform_internal_requires_a_stated_reason(self) -> None:
        with pytest.raises(ContractViolation, match="requires a stated reason"):
            TenantContext.platform_internal("")

    def test_platform_internal_is_explicitly_marked(self) -> None:
        tenancy = TenantContext.platform_internal("scheduler tick has no tenant")
        assert tenancy.is_platform_internal
        assert tenancy.platform_internal_reason == "scheduler tick has no tenant"

    def test_a_real_tenant_is_not_platform_internal(self, context) -> None:
        assert not context.is_platform_internal

    def test_a_tenant_context_may_not_carry_a_platform_reason(self) -> None:
        from backend.contracts import TenantRef

        with pytest.raises(ContractViolation, match="must not carry a platform-internal reason"):
            TenantContext(tenant=TenantRef("acme"), platform_internal_reason="nope")

    def test_platform_internal_reason_reaches_audit_detail(self) -> None:
        ctx = ExecutionContext.platform_internal(
            reason="dispatch replays an untenanted event",
            component="dispatcher",
            source="eventbus",
        )
        assert ctx.audit_detail()["platform_internal_reason"] == (
            "dispatch replays an untenanted event"
        )


# ======================================================================
# Never partially populated
# ======================================================================


class TestNeverPartiallyPopulated:
    @pytest.mark.parametrize(
        "field", ["identity", "tenancy", "trace", "correlation", "request"]
    )
    def test_mandatory_members_cannot_be_omitted(self, context, field: str) -> None:
        with pytest.raises(TypeError):
            fields = {
                f.name: getattr(context, f.name)
                for f in dataclasses.fields(context)
                if f.name != field
            }
            ExecutionContext(**fields)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "field,wrong", [("identity", "x"), ("tenancy", "x"), ("trace", 1), ("request", None)]
    )
    def test_wrong_member_types_are_refused(self, context, field: str, wrong) -> None:
        with pytest.raises(ContractViolation, match="must be a"):
            dataclasses.replace(context, **{field: wrong})

    def test_there_is_no_builder(self) -> None:
        """A mutable staging object is how a half-built context gets passed."""
        for forbidden in ("builder", "Builder", "new", "empty", "blank"):
            assert not hasattr(ExecutionContext, forbidden)

    def test_workspace_requires_an_organization(self, identity) -> None:
        with pytest.raises(ContractViolation, match="requires organization_id"):
            ExecutionContext.for_tenant(
                tenant_id="acme", identity=identity, source="http", workspace_id="ws-1"
            )


# ======================================================================
# Cross-tenant isolation
# ======================================================================


class TestCrossTenantIsolation:
    def test_a_context_spanning_two_tenants_is_refused(self, context, identity) -> None:
        """The leak this check exists to prevent."""
        other = TenantContext.for_tenant("other-corp")
        foreign_org = OrganizationContext.create(other, "org-1")
        with pytest.raises(ContractViolation, match="different tenant"):
            dataclasses.replace(context, organization=foreign_org)

    def test_organization_from_another_tenant_is_refused(self) -> None:
        from backend.contracts import OrganizationRef, TenantRef

        with pytest.raises(ContractViolation, match="different tenant"):
            OrganizationContext(
                tenancy=TenantContext.for_tenant("acme"),
                organization=OrganizationRef(
                    tenant=TenantRef("other"), organization_id="o"
                ),
            )

    def test_workspace_from_another_organization_is_refused(self) -> None:
        from backend.contracts import ProjectRef

        tenancy = TenantContext.for_tenant("acme")
        org_a = OrganizationContext.create(tenancy, "org-a")
        org_b = OrganizationContext.create(tenancy, "org-b")
        with pytest.raises(ContractViolation, match="different organization"):
            WorkspaceContext(
                organization=org_a,
                project=ProjectRef(organization=org_b.organization, project_id="ws"),
            )

    def test_isolates_from_distinguishes_tenants(self) -> None:
        acme = TenantContext.for_tenant("acme")
        other = TenantContext.for_tenant("other")
        assert acme.isolates_from(other)
        assert not acme.isolates_from(TenantContext.for_tenant("acme"))

    def test_scope_carries_the_tenant_to_the_boundary(self, context) -> None:
        assert context.scope.tenant.tenant_id == "acme"

    def test_security_context_carries_tenant_and_principal(self, context) -> None:
        security = context.security_context
        assert security.scope.tenant.tenant_id == "acme"
        assert security.principal.principal_id == "user-42"
        assert security.capabilities == ("mission:create",)


# ======================================================================
# Immutability
# ======================================================================


class TestImmutability:
    @pytest.mark.parametrize(
        "context_type",
        [
            ExecutionContext, IdentityContext, TenantContext, OrganizationContext,
            WorkspaceContext, MissionContext, TraceContext, CorrelationContext,
            FeatureFlagContext, LocaleContext, RequestMetadata,
        ],
    )
    def test_every_context_type_is_a_frozen_dataclass(self, context_type) -> None:
        assert dataclasses.is_dataclass(context_type)
        assert context_type.__dataclass_params__.frozen

    def test_assignment_raises(self, context) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            context.tenancy = TenantContext.for_tenant("other")  # type: ignore[misc]

    def test_flags_mapping_is_read_only(self, identity) -> None:
        context = ExecutionContext.for_tenant(
            tenant_id="acme", identity=identity, source="http", flags={"beta": True}
        )
        with pytest.raises(TypeError):
            context.features.flags["beta"] = False  # type: ignore[index]

    def test_mutating_the_source_flags_does_not_affect_the_context(self, identity) -> None:
        flags = {"beta": True}
        context = ExecutionContext.for_tenant(
            tenant_id="acme", identity=identity, source="http", flags=flags
        )
        flags["beta"] = False
        assert context.features.enabled("beta") is True

    def test_derivation_returns_a_new_instance(self, context) -> None:
        assert context.with_mission("msn-1") is not context
        assert context.child_operation() is not context
        assert context.mission is None, "the original context was mutated"


# ======================================================================
# Propagation and nesting
# ======================================================================


class TestPropagation:
    def test_child_operation_preserves_tenant_and_identity(self, context) -> None:
        child = context.child_operation()
        assert child.tenancy == context.tenancy
        assert child.identity == context.identity

    def test_child_operation_preserves_correlation(self, context) -> None:
        """The whole point: one incident stays one chain across nesting."""
        child = context.child_operation()
        assert child.correlation.correlation_id == context.correlation.correlation_id

    def test_child_operation_advances_causation(self, context) -> None:
        child = context.child_operation()
        assert child.correlation.causation_id == context.request.request_id
        assert context.correlation.is_chain_origin

    def test_child_operation_creates_a_child_span(self, context) -> None:
        child = context.child_operation()
        assert child.trace.trace_id == context.trace.trace_id
        assert child.trace.parent_span_id == context.trace.span_id
        assert child.trace.span_id != context.trace.span_id

    def test_deep_nesting_preserves_one_correlation(self, context) -> None:
        current = context
        for _ in range(10):
            current = current.child_operation()
        assert current.correlation.correlation_id == context.correlation.correlation_id
        assert current.trace.trace_id == context.trace.trace_id

    def test_explicit_causation_is_honoured(self, context) -> None:
        child = context.child_operation(caused_by="op-99")
        assert child.correlation.causation_id == "op-99"

    def test_joining_an_existing_chain(self, identity) -> None:
        context = ExecutionContext.for_tenant(
            tenant_id="acme",
            identity=identity,
            source="eventbus",
            correlation=CorrelationContext.join("incident-1", "event-7"),
        )
        assert context.correlation.correlation_id == "incident-1"
        assert context.correlation.causation_id == "event-7"

    def test_correlation_and_causation_must_differ(self) -> None:
        with pytest.raises(ContractViolation, match="different questions"):
            CorrelationContext(correlation_id="same", causation_id="same")

    def test_delegated_identity_records_both_principals(self, context) -> None:
        from backend.contracts import PrincipalRef

        platform = PrincipalRef(principal_id="dispatcher", kind=PrincipalKind.PLATFORM)
        delegated = context.identity.delegating_to(platform)
        assert delegated.principal_id == "dispatcher"
        assert delegated.effective_principal.principal_id == "user-42"
        assert context.with_identity(delegated).audit_detail()["on_behalf_of"] == "user-42"


# ======================================================================
# No global mutable state
# ======================================================================


class TestNoAmbientContext:
    def test_the_package_exposes_no_ambient_accessor(self) -> None:
        """An operation that can obtain a context without being given one can
        also obtain the wrong one."""
        import backend.platform.context as package

        for forbidden in (
            "current_context", "get_context", "set_context", "current",
            "bind", "context_var", "_current",
        ):
            assert not hasattr(package, forbidden), f"ambient accessor {forbidden!r} exists"

    def test_no_contextvar_is_imported_by_the_package(self) -> None:
        """Checked by import analysis, not text search.

        The module docstrings *mention* ContextVar to explain why the package
        does not use one; a substring check would flag the explanation.
        """
        import ast
        from pathlib import Path

        package_dir = Path(__file__).resolve().parents[2] / "backend" / "platform" / "context"
        forbidden = {"contextvars", "threading", "_thread"}

        for module in package_dir.glob("*.py"):
            tree = ast.parse(module.read_text(encoding="utf-8"))
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            leaked = imported & forbidden
            assert not leaked, f"{module.name} imports ambient-state module(s): {sorted(leaked)}"


# ======================================================================
# Concurrency
# ======================================================================


class TestConcurrentExecution:
    def test_contexts_do_not_leak_between_threads(self, identity) -> None:
        """Explicit passing means concurrent tenants cannot cross."""
        observed: list[tuple[str, str]] = []
        lock = threading.Lock()

        def worker(tenant_id: str) -> None:
            context = ExecutionContext.for_tenant(
                tenant_id=tenant_id, identity=identity, source="http"
            )
            for _ in range(50):
                child = context.child_operation()
                with lock:
                    observed.append((tenant_id, child.tenant_id))

        threads = [
            threading.Thread(target=worker, args=(f"tenant-{index}",)) for index in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(observed) == 400
        assert all(expected == actual for expected, actual in observed), (
            "a context leaked across threads"
        )

    def test_concurrent_contexts_have_unique_request_ids(self, identity) -> None:
        ids: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            produced = [
                ExecutionContext.for_tenant(
                    tenant_id="acme", identity=identity, source="http"
                ).request.request_id
                for _ in range(100)
            ]
            with lock:
                ids.extend(produced)

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(set(ids)) == 600


# ======================================================================
# Audit integration
# ======================================================================


class TestAuditIntegration:
    def test_audit_detail_carries_every_attribution_field(self, identity) -> None:
        context = ExecutionContext.for_tenant(
            tenant_id="acme",
            identity=identity,
            source="http",
            organization_id="org-1",
            workspace_id="ws-1",
            mission_id="msn-1",
        )
        detail = context.audit_detail()
        for field in (
            "tenant_id", "principal_id", "principal_kind", "request_id",
            "request_source", "trace_id", "span_id", "organization_id",
            "workspace_id", "mission_id",
        ):
            assert field in detail, f"audit detail is missing {field}"

    def test_recording_in_context_attributes_the_entry(self, context) -> None:
        from backend.contracts import AuditEventKind
        from backend.platform.audit import AuditRuntime, InMemoryAuditStore

        runtime = AuditRuntime(InMemoryAuditStore())
        entry = runtime.record_in_context(
            AuditEventKind.EXECUTION_STARTED, context, subject_reference="wf-1"
        )
        assert entry.scope.tenant.tenant_id == "acme"
        assert entry.actor is not None and entry.actor.principal_id == "user-42"
        assert entry.correlation_id == context.correlation.correlation_id
        assert entry.detail["trace_id"] == context.trace.trace_id

    def test_dispatcher_context_is_explicitly_platform_internal(self) -> None:
        """The former TenantRef("system") placeholder is gone."""
        from backend.services.enterprise_integrity_audit import SYSTEM_SCOPE

        assert SYSTEM_SCOPE.tenant.tenant_id == PLATFORM_INTERNAL_TENANT_ID
        assert SYSTEM_SCOPE.tenant.tenant_id != "system"

    def test_integrity_audit_records_carry_the_reason(self) -> None:
        from backend.platform.audit import AuditRuntime, InMemoryAuditStore
        from backend.services.enterprise_integrity_audit import IntegrityAuditLog

        audit = IntegrityAuditLog(AuditRuntime(InMemoryAuditStore()))
        entry = audit.record_refusal(
            workflow_id="wf-1", action_type="rollback", reason="r", failure="f"
        )
        assert "platform_internal_reason" in entry.detail
        assert entry.detail["tenant_id"] == PLATFORM_INTERNAL_TENANT_ID
