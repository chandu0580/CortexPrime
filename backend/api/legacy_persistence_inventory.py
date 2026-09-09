"""V1 SQLAlchemy models: what they are, who uses them, and what happens to them.

Why this is an inventory and not a migration
----------------------------------------------
Phase 5.1 built a durable system of record for the *execution and capability
fabric*. It said plainly that the pre-existing SQLAlchemy models were untouched
and unaudited. Phase 5.2 audits them and produces a decision per model — and
migrates none of them, because moving twenty-odd tables on the strength of an
architecture document is how a durability phase becomes an outage.

The decision is the deliverable. It turns "there is a lot of old schema" into a
list somebody can work through, with the reason attached to each entry.

What was actually checked, per model
--------------------------------------
    owner              which subsystem writes it
    callers            what reads it today, found by search rather than assumed
    tenant model       whether a row can be attributed to a tenant at all
    transaction        whether writes are transactional or fire-and-forget
    migration risk     what breaks if it moves

The finding that matters most
-------------------------------
**Almost none of these tables carry a tenant.** They predate ``ExecutionContext``
and the storage guard, so their repositories cannot narrow by tenant because
there is no column to narrow by. That is not a Phase 5.2 regression — it is the
state Phase 5.1 inherited and did not touch — and it is why none of them is on
the Phase 4 authority path: every route that reaches them is either read-only
reporting or already gated (ADR-039, ADR-043).

The exposure is therefore bounded by what is in front of them, not by anything in
the model. That is what makes them migratable in order rather than at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "PersistenceDecision",
    "LegacyPersistenceModel",
    "LEGACY_PERSISTENCE_MODELS",
    "by_decision",
    "hazards",
    "untenanted",
    "summary",
]


class PersistenceDecision(str, Enum):
    """What happens to a V1 model. Five answers, and none of them is 'later'."""

    KEEP = "keep"
    """Correct for what it does, in a subsystem that is not on the authority
    path. It stays, and it is not a migration target."""

    REPLACE = "replace"
    """Superseded by a Phase 5.1 durable table. The V1 model remains until its
    callers move; the replacement already exists."""

    STRANGLER = "strangler"
    """Stays behind an existing gate until the subsystem that owns it migrates.
    Not dangerous where it sits; not somewhere new work should be added."""

    REMOVE_LATER = "remove_later"
    """Provably unused, or fully superseded with no live caller. Deleting it is
    a separate decision with data attached to it."""

    SECURITY_HAZARD = "security_hazard"
    """Dangerous now, not merely unmigrated. Needs a decision before it needs a
    migration."""


@dataclass(frozen=True)
class LegacyPersistenceModel:
    """One pre-existing persistence model and the decision about it."""

    location: str
    owner: str
    callers: str
    tenant_model: str
    transaction_behaviour: str
    decision: PersistenceDecision
    migration_risk: str
    note: str = ""

    @property
    def tenant_aware(self) -> bool:
        return self.tenant_model.startswith("tenant")


LEGACY_PERSISTENCE_MODELS: tuple = (
    # ------------------------------------------------------------------
    # Superseded by the Phase 5.1 durable fabric
    # ------------------------------------------------------------------
    LegacyPersistenceModel(
        location="backend/database/models/workflow.py",
        owner="V1 workflow subsystem",
        callers="V1 workflow routes and services; **not** BC-6 Workflow",
        tenant_model="none — no tenant column",
        transaction_behaviour="per-call session, autocommit at the repository",
        decision=PersistenceDecision.REPLACE,
        migration_risk="low; the governed path does not read it",
        note="BC-6 Workflow and the Phase 5.1 ``cp_execution`` document are the "
        "authoritative representation of a run. This table is the V1 shape and "
        "shares no identity with it -- there is no correspondence to migrate, "
        "only callers to move.",
    ),
    LegacyPersistenceModel(
        location="backend/database/models/mission_replay.py",
        owner="V1 mission replay",
        callers="event bus (every V1 event), mission replay routes, "
        "enterprise replay routes, governance centre timeline",
        tenant_model="none",
        transaction_behaviour="per-call session",
        decision=PersistenceDecision.KEEP,
        migration_risk="none; migration 0025 owns the table",
        note="ADR-118 (Phase 10.25/10.26): PostgreSQL is the durable layer "
        "behind the 72 h Redis window and is owned by migration 0025. The "
        "earlier REPLACE verdict named a governed replay that serves none of "
        "the shipped replay routes; it is recorded there as superseded.",
    ),
    # ------------------------------------------------------------------
    # Keep — genuinely different subsystems, not on the authority path
    # ------------------------------------------------------------------
    LegacyPersistenceModel(
        location="backend/database/models/audit_log.py",
        owner="platform audit",
        callers="``platform/audit`` runtime and the audit routes",
        tenant_model="tenant column present",
        transaction_behaviour="append-only writes",
        decision=PersistenceDecision.KEEP,
        migration_risk="high — it is the audit trail",
        note="**Do not touch.** ADR-015 made this append-only and independently "
        "verifiable, and the whole platform records through it. Phase 5.1 "
        "deliberately reused it rather than building a second audit system, and "
        "Phase 5.2 does the same.",
    ),
    # Retired in Phase 10.29 (ADR-119): organization.py, department.py and
    # project.py -- the V1 organizational directory. Their KEEP entry rested on
    # IAM (retired, ADR-107) and on "defining tenancy" (rejected, ADR-103); no
    # migration ever created the tables, no client reached the routes, and no
    # runtime, governance or tenant path read them.
    LegacyPersistenceModel(
        location="backend/database/models/cost_tracking.py, cost_intelligence.py",
        owner="cost intelligence",
        callers="cost routes, analytics services",
        tenant_model="none on most rows",
        transaction_behaviour="per-call session, batch inserts",
        decision=PersistenceDecision.KEEP,
        migration_risk="low",
        note="Reporting over past activity. Not an authority input to anything, "
        "and nothing in the governed path reads it.",
    ),
    LegacyPersistenceModel(
        location="backend/database/models/semantic_memory.py, episodic_memory.py, "
        "embedding_cache.py",
        owner="cognitive memory",
        callers="memory services, retrieval",
        tenant_model="none",
        transaction_behaviour="per-call session",
        decision=PersistenceDecision.KEEP,
        migration_risk="low",
        note="Experiential memory. Constitution I7 already says it may propose "
        "and may never authorize, so it is structurally outside the authority "
        "path regardless of where it is stored.",
    ),
    LegacyPersistenceModel(
        # Phase 10.29 (ADR-119): health_status.py, maintenance_event.py and
        # operational_report.py were retired with the enterprise-operations API;
        # runtime_analytics.py stays.
        location="backend/database/models/runtime_analytics.py",
        owner="operations and reporting",
        callers="dashboards, analytics routes",
        tenant_model="none",
        transaction_behaviour="per-call session",
        decision=PersistenceDecision.KEEP,
        migration_risk="low",
        note="Observability. Explicitly not a system of record for anything the "
        "platform decides.",
    ),
    # ------------------------------------------------------------------
    # Strangler — behind an existing gate
    # ------------------------------------------------------------------
    LegacyPersistenceModel(
        location="backend/database/models/connector_activity.py",
        owner="V1 connectors",
        callers="``ConnectorActivityService``, reached from V1 connector routes",
        tenant_model="none — activity is recorded per connector, not per tenant",
        transaction_behaviour="fire-and-forget writes from ``BaseConnector._execute``",
        decision=PersistenceDecision.STRANGLER,
        migration_risk="low; the routes that reach it are gated",
        note="Follows the V1 connectors. Every route that writes it is behind "
        "``CORTEXPRIME_ENABLE_LEGACY_CONNECTIVITY`` (ADR-043), so it is inert by "
        "default. The governed path records provider operations through audit "
        "and the execution record instead.",
    ),
    LegacyPersistenceModel(
        location="backend/database/models/fleet.py",
        owner="V1 fleet management",
        callers="fleet routes",
        tenant_model="none",
        transaction_behaviour="per-call session",
        decision=PersistenceDecision.STRANGLER,
        migration_risk="low",
        note="A V1 notion of agents-as-fleet that predates the worker directory. "
        "``cp_worker`` is the authoritative record of what may perform work; this "
        "is not consulted by anything in the governed path.",
    ),
    LegacyPersistenceModel(
        location="backend/database/models/reflection_history.py",
        owner="V1 reflection",
        callers="reflection services",
        tenant_model="none",
        transaction_behaviour="per-call session",
        decision=PersistenceDecision.STRANGLER,
        migration_risk="low",
        note="Model-driven reflection output. Proposes, never authorizes.",
    ),
    # Retired in Phase 10.29 (ADR-119): backup_record.py and the enterprise
    # backup API. GA backup/DR is scripts/backup-database.sh and the Helm
    # backup CronJob (pg_dump), which never used this table.
    # ------------------------------------------------------------------
    # The one that needs a decision rather than a migration
    # ------------------------------------------------------------------
    LegacyPersistenceModel(
        location="backend/database/engine.py :: ``engine``, ``AsyncSessionLocal``",
        owner="V1 database access",
        callers="every V1 repository",
        tenant_model="n/a — it is the engine",
        transaction_behaviour="**module-level engine created at import**, with "
        "``init_db()`` calling ``create_all`` outside Alembic",
        decision=PersistenceDecision.SECURITY_HAZARD,
        migration_risk="medium; many callers",
        note="Two findings. (1) ``init_db()`` runs ``Base.metadata.create_all``, "
        "which builds a schema **outside the migration history** -- a deployment "
        "that calls it drifts from Alembic without anybody noticing, and Phase "
        "5.1's production config refuses exactly this for the durable store. (2) "
        "The engine is constructed at import from environment variables with a "
        "**default password-less DSN**, so an import in the wrong environment "
        "silently points at ``localhost``. Neither is exploitable on its own and "
        "neither is on the authority path -- the durable store has its own "
        "engine, built explicitly and verified before use -- but ``init_db`` "
        "should not be reachable in production. **Gate it; do not delete it**, "
        "because development and tests rely on it.",
    ),
    LegacyPersistenceModel(
        location="backend/database/repositories/*.py",
        owner="V1 repositories",
        callers="V1 services and routes",
        tenant_model="mixed; most take no context",
        transaction_behaviour="per-call session, commit inside the repository",
        decision=PersistenceDecision.STRANGLER,
        migration_risk="medium",
        note="They commit inside the repository, so a caller cannot compose two "
        "writes into one transaction -- the defect Phase 5.1's ``UnitOfWork`` "
        "exists to prevent. Not a hazard where they sit (none is on the "
        "authority path) and not a pattern to copy. ``TENANT-REPOSITORY-CONTEXT`` "
        "already grandfathers them, and that list may only shrink.",
    ),
    # ------------------------------------------------------------------
    # What the durable fabric actually uses
    # ------------------------------------------------------------------
    LegacyPersistenceModel(
        location="backend/database/migrations (Alembic)",
        owner="platform",
        callers="deployment",
        tenant_model="n/a",
        transaction_behaviour="forward-only migrations",
        decision=PersistenceDecision.KEEP,
        migration_risk="n/a",
        note="Reused by Phase 5.1 (0010) and Phase 5.2 (0011). Both additive, "
        "both chained onto the existing head, neither destructive on upgrade.",
    ),
)


def by_decision(decision: PersistenceDecision) -> tuple:
    return tuple(m for m in LEGACY_PERSISTENCE_MODELS if m.decision is decision)


def hazards() -> tuple:
    """Models needing a decision before a migration, rather than during one."""
    return by_decision(PersistenceDecision.SECURITY_HAZARD)


def untenanted() -> tuple:
    """Models that cannot attribute a row to a tenant. The dominant finding."""
    return tuple(m for m in LEGACY_PERSISTENCE_MODELS if not m.tenant_aware)


def summary() -> dict:
    """A queryable form, so the decision is inspectable rather than only readable."""
    return {
        "total": len(LEGACY_PERSISTENCE_MODELS),
        "by_decision": {
            decision.value: [m.location for m in by_decision(decision)]
            for decision in PersistenceDecision
        },
        "hazards": [m.location for m in hazards()],
        "untenanted": [m.location for m in untenanted()],
        "migrated_in_phase_5": 0,
        "note": (
            "None of these is on the Phase 4 authority path. Every route that "
            "writes one is either read-only reporting or already gated "
            "(ADR-039, ADR-043). Phase 5.2 audits and decides; it migrates "
            "nothing, because moving twenty tables on the strength of an "
            "architecture document is how a durability phase becomes an outage."
        ),
    }
