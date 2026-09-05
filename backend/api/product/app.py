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

        runtime = build_governed_runtime()
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
        )
    except Exception:  # noqa: BLE001 - a failed composition must not crash boot
        log.warning("product API: engine composition failed", exc_info=True)
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
    app.include_router(router)
    return app
