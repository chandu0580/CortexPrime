"""The product API application. Its own app, deliberately.

Why not mount into ``backend.main``
-----------------------------------
Two measured reasons, both from Phase 10.0:

* ``backend/main.py`` registers **185 V1 routers**, of which **89 of 96 route
  modules contain no reference to tenant at all**. Mounting beside them is how a
  product surface inherits their tenant semantics by proximity.
* Its boot contacts real providers and auto-migrates -- a hazard recorded in this
  project's own notes long before this phase.

So this is a separate ASGI application that imports no V1 route module, no V1
execution code, and no connector. It mounts one router.

What it composes, and once
--------------------------
The governed runtime takes seconds to compose and opens durable connections, so
it is built once at startup and read from module state. There is no per-request
construction, and no route may build one.

Authority
---------
None. This module wires a router to a runtime and holds nothing else. Every
decision that matters -- authorization, approval, autonomy, execution -- happens
in the engine, reached through the contracts it already publishes.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import FastAPI

from backend.contexts.connectivity.infrastructure.sql_approval import (
    SqlApprovalRepository,
)

log = logging.getLogger(__name__)

__all__ = ["ProductEngine", "build_product_app", "current_engine", "set_engine"]

#: Module-level, set once at startup. Not a cache of tenant data -- it holds
#: repositories and query services, all of which take a tenant per call.
_ENGINE: Optional["ProductEngine"] = None


@dataclass(frozen=True)
class ProductEngine:
    """The read surfaces the product API is allowed to reach.

    Deliberately a **narrow, frozen, named** set rather than the whole runtime.
    Handing routes the full runtime would put the scheduler, the gateway, the
    worker runtime and the credential broker one attribute access away from a
    presentation layer. What is not here cannot be called from a route.

    Note what is absent: no gateway, no dispatcher, no worker runtime, no
    credential broker, no connector, no transport.
    """

    investigations: Any
    investigation_repository: Any
    world_query: Any
    verifications: Any
    #: Phase 10.2. Both are pure reads over the two ledgers already reachable
    #: above -- ``observations`` resolves one observation by id (so an evidence
    #: list can show what was observed rather than only that something was), and
    #: ``beliefs`` is the existing BeliefFormation, which is how CORRELATED stays
    #: distinguishable from INDEPENDENT. Neither is a new store.
    observations: Any = None
    beliefs: Any = None
    #: The SAME lineage policy the belief path uses, so a source's origin is
    #: described identically wherever it appears. Two lineage policies would be
    #: two answers to "are these sources independent".
    lineage_policy: Any = None
    #: Phase 10.3. The approval STORE (not a decider), the remediation assembler,
    #: the governed runtime the one execution door needs, and a factory for the
    #: caller's execution context. Adding these is what makes the product able to
    #: initiate a governed action -- and none of them decides anything: approval
    #: validity is still ApprovalFacts + the gateway, authorization is still the
    #: authorization service, and execution is still GovernedCapabilityWriter.
    approvals: Any = None
    remediation: Any = None
    runtime: Any = None
    execution_context_factory: Any = None
    #: Phase 10.8. The durable authority-grant STORE -- rows in, rows out. It
    #: decides nothing: whether a human may approve, execute or issue is still
    #: answered by ``resolve_scoped_authority``, and whether an issuer may
    #: create a grant is still answered by ``backend.auth.grants``. Before this
    #: phase the grants those functions read lived in a gitignored JSON file
    #: that nobody had to be authorized to write.
    grants: Any = None
    #: Phase 10.9. The durable membership STORE -- who belongs to this tenant.
    #: It decides nothing about what they may DO; that stays with the Phase
    #: 10.8 grants above. Before this phase the answer lived in a gitignored
    #: JSON file whose only mutation route took the tenant from the URL.
    memberships: Any = None
    #: Phase 10.10. The durable TENANT store -- does this boundary exist, and
    #: is it live. It confers nothing: membership is still cp_tenant_membership
    #: and authority is still cp_authority_grant. Before this phase the answer
    #: came from a gitignored JSON file that require_tenant read on every
    #: request.
    tenants: Any = None
    #: Phase 11.3. The reasoning ledger (cw_reasoning) -- detections and
    #: investigation assessments live there as reasoning artefacts, never as
    #: world truth -- and the harness trace store (cp_harness_trace), which is
    #: the only durable record of model spend. Both read-only here.
    reasoning: Any = None
    traces: Any = None


def current_engine() -> Optional[ProductEngine]:
    return _ENGINE


def set_engine(engine: Optional[ProductEngine]) -> None:
    """Install the composed engine. Used by startup and by the harness."""
    global _ENGINE  # noqa: PLW0603 - one process-wide composition, set at startup
    _ENGINE = engine


def compose_engine() -> Optional[ProductEngine]:
    """Compose the read surfaces from the existing governed runtime.

    Returns ``None`` when the platform is not configured, so the API starts and
    answers 503 on data endpoints rather than failing to start. A process that
    cannot reach its durable store should say so per request, not crash on boot.
    """
    try:
        from backend.api.application_runtime import build_governed_runtime
        from backend.harness.trace_sql import SqlTraceRecorder
        from backend.world.infrastructure.sql_reasoning import SqlReasoningRepository
        from backend.assurance.infrastructure import SqlVerificationRepository
        from backend.intelligence.application.investigation_service import (
            InvestigationService,
        )
        from backend.intelligence.infrastructure.sql_investigation import (
            SqlInvestigationRepository,
        )
        from backend.api.observability_evidence import (
            observability_authority_policy,
            observability_freshness_policy,
        )
        from backend.world.application import WorldQuery
        from backend.world.infrastructure import (
            SqlFactRepository,
            SqlObservationRepository,
        )

        from backend.api.observability_evidence import observability_lineage_policy
        from backend.world.application.belief import BeliefFormation

        from backend.contexts.connectivity.infrastructure.sql_approval import (
            SqlApprovalRepository,
        )
        from backend.contexts.connectivity.infrastructure.sql_authority_grant import (
            SqlAuthorityGrantRepository,
        )
        from backend.contexts.connectivity.infrastructure.sql_membership import (
            SqlMembershipRepository,
        )
        from backend.contexts.connectivity.infrastructure.sql_tenant import (
            SqlTenantRepository,
        )

        # The durable approval store, installed through the DECLARED seam. It
        # supplies storage; ApprovalFacts and the gateway still decide.
        runtime = build_governed_runtime(approvals_factory=SqlApprovalRepository)
        if runtime is None:
            log.warning("product API: no governed runtime; data endpoints will 503")
            return None

        lineage_policy = observability_lineage_policy()
        store = runtime.persistence.store
        investigation_repository = SqlInvestigationRepository(store)
        observations = SqlObservationRepository(store)
        authority_policy = observability_authority_policy()
        world_query = WorldQuery(
            facts=SqlFactRepository(store),
            observations=observations,
            authority_policy=authority_policy,
            freshness_policy=observability_freshness_policy())
        return ProductEngine(
            investigations=InvestigationService(repository=investigation_repository),
            investigation_repository=investigation_repository,
            world_query=world_query,
            verifications=SqlVerificationRepository(store),
            observations=observations,
            # Reuses the SAME query and the SAME policies. A second belief path
            # with its own policies would be a second answer to "what do we
            # believe", which is the one thing the World Plane may not have.
            beliefs=BeliefFormation(
                query=world_query,
                observations=observations,
                authority_policy=authority_policy,
                lineage_policy=lineage_policy),
            lineage_policy=lineage_policy,
            approvals=SqlApprovalRepository(store),
            grants=SqlAuthorityGrantRepository(store),
            memberships=SqlMembershipRepository(store),
            tenants=SqlTenantRepository(store),
            reasoning=SqlReasoningRepository(store),
            traces=SqlTraceRecorder(store),
            remediation=_compose_remediation(runtime),
            runtime=runtime,
            execution_context_factory=_execution_context,
        )
    except Exception:  # noqa: BLE001 - a failed composition must not crash boot
        log.warning("product API: engine composition failed", exc_info=True)
        return None



def _execution_context(tenant_id: str, principal_id: str):
    """The caller's authenticated context, for the governed chain.

    Built from values the SERVER resolved -- the tenant from the verified token
    and the principal from the stored approval. There is no code path by which a
    request body reaches this function.
    """
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    from backend.platform.context import ExecutionContext
    from backend.platform.context.identity import IdentityContext

    identity = IdentityContext(
        principal=PrincipalRef(principal_id=principal_id, kind=PrincipalKind.HUMAN),
        capabilities=("capability:invoke",),
    )
    return ExecutionContext.for_tenant(
        tenant_id=tenant_id, identity=identity, source="product-api")


def _compose_remediation(runtime):
    """The remediation assembler, or ``None`` when nothing is commissioned.

    Phase 9 closed with exactly ONE commissioned write capability. If it is not
    registered in this deployment, remediation is absent and the endpoints answer
    503 -- rather than offering an action that would be refused further down,
    which teaches an operator to expect capabilities that do not exist.
    """
    try:
        from backend.api.application_runtime import _platform_context
        from backend.api.product.approval_routes import COMMISSIONED_OPERATION
        from backend.api.product.remediation import RemediationService
        from backend.contexts.connectivity.application.commands import GetCapability
        from backend.contexts.connectivity.domain.authorization import (
            CapabilityOperation,
        )
        from backend.contracts.execution import ExecutionEnvironment

        definition = runtime.capabilities.get(_platform_context(), GetCapability(
            capability_id="platform.kubernetes.workload.rollout_restart", version=1))
        if definition is None:
            return None

        def writer_factory(rt, definitions, principal):
            from backend.api.capability_execution_composition import (
                GovernedCapabilityWriter,
            )
            return GovernedCapabilityWriter(
                runtime=rt, capability_definitions=definitions, principal=principal)

        return RemediationService(
            definitions={COMMISSIONED_OPERATION: definition},
            approvals=SqlApprovalRepository(runtime.persistence.store),
            writer_factory=writer_factory,
            environment=ExecutionEnvironment.DEVELOPMENT,
            # The verb AUTHORIZATION is asked about, named here in composition
            # because this is where the connectivity context is already in
            # scope. It is NOT the provider operation, and conflating the two
            # made every legitimate approval invalid earlier in this phase.
            authorization_operation=CapabilityOperation.INVOKE.value,
        )
    except Exception:  # noqa: BLE001 - an uncommissioned deployment is not broken
        log.info("product API: no commissioned remediation in this deployment",
                 exc_info=True)
        return None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    set_engine(compose_engine())
    try:
        yield
    finally:
        set_engine(None)


def build_product_app(*, engine: Optional[ProductEngine] = None) -> FastAPI:
    """The product API application.

    ``engine`` is for tests and the harness, which compose their own read
    surfaces against a known database. When it is given, startup composition is
    skipped -- the harness is then testing the same routes against the same
    contracts, without a second composition path in production code.
    """
    from backend.api.product.approval_routes import router as remediation_router
    from backend.api.product.routes import router

    app = FastAPI(
        title="CortexPrime Product API",
        version="1.0.0",
        description=(
            "Read-only, tenant-scoped access to the governed engine. This API "
            "holds no authority: it cannot execute, approve, authorize, promote "
            "autonomy, reach a provider, or modify World, Investigation or "
            "Assurance state."
        ),
        lifespan=None if engine is not None else lifespan,
    )
    if engine is not None:
        set_engine(engine)
    from backend.api.product.authority_routes import router as authority_router
    from backend.api.product.membership_routes import router as membership_router
    from backend.api.product.signal_routes import router as signal_router
    from backend.api.product.assessment_routes import router as assessment_router

    app.include_router(router)
    # The ONLY module carrying non-GET routes. Kept a separate include so the
    # product's mutation surface is one import a reviewer can find.
    app.include_router(remediation_router)
    # Phase 10.8. The second module carrying non-GET routes, and the reason it
    # is a separate include is the same: the product's mutation surface should
    # be a short list a reviewer can hold in their head. These routes issue and
    # revoke authority; they decide nothing about it.
    app.include_router(authority_router)
    # Phase 10.9. Membership administration: admit, activate, deactivate and
    # relabel. It confers no authority -- that is still the grant routes above.
    app.include_router(membership_router)
    # Phase 11.2: read-only signal fabric views (recent signals, candidates).
    app.include_router(signal_router)
    # Phase 11.3: read-only detection and assessment views (assessment, cost).
    app.include_router(assessment_router)
    return app
