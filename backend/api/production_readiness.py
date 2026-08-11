"""Ten separate readiness answers. **Never collapsed into one boolean.**

Why ten and not one
---------------------
``ready = True`` is the most dangerous field a platform can publish, because it
is the field a load balancer reads. A process can be architecturally sound and
have no database; it can have a database three migrations behind; it can have a
credential adapter and no transport; it can have every one of those and no
enabled worker. Each of those is a different outage with a different fix, and a
single boolean turns all of them into "not ready" — or worse, into "ready"
because whichever check somebody remembered happens to pass.

So each dimension answers for itself, says *why* when the answer is no, and
``overall`` is the conjunction of the ones a deployment declared it needs.

What "ready" is allowed to mean here
--------------------------------------
Only what was actually checked. ``provider_ready`` does not mean a provider
answered — it means an adapter is registered, a credential adapter exists for
it, and a transport can carry it. Whether GitHub is up is not knowable without
calling GitHub, and calling a provider from a health check would mean every
liveness probe spent somebody's rate limit.

Where a dimension cannot be established, the honest value is ``False`` with a
reason, never ``True`` with a caveat in a docstring nobody reads at 3am.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

__all__ = [
    "ReadinessDimension",
    "ReadinessReport",
    "READINESS_DIMENSIONS",
    "assess_readiness",
]

log = logging.getLogger(__name__)

#: Every dimension, in the order an operator should read them: the ones that
#: make later ones meaningless come first. A database that is not ready makes
#: ``durability_ready`` unanswerable rather than false.
READINESS_DIMENSIONS = (
    "architecture_ready",
    "database_ready",
    "durability_ready",
    "scheduler_ready",
    "credential_ready",
    "transport_ready",
    "worker_ready",
    "provider_ready",
    "delegation_ready",
    "operational_ready",
)


@dataclass(frozen=True)
class ReadinessDimension:
    """One answer, and the reason behind it. A fact, never a recommendation."""

    name: str
    ready: bool
    reason: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "reason": self.reason,
            **({"detail": dict(self.detail)} if self.detail else {}),
        }


@dataclass(frozen=True)
class ReadinessReport:
    """Ten answers and their conjunction. The conjunction is derived, not stored."""

    dimensions: tuple
    required: frozenset

    @property
    def overall(self) -> bool:
        """True only when every **required** dimension is true.

        Derived on read rather than stored, for the same reason a delegation's
        status is derived: a stored copy of a computed truth is a second place
        for it to be wrong.
        """
        return all(d.ready for d in self.dimensions if d.name in self.required)

    @property
    def blocking(self) -> tuple:
        return tuple(
            d.name for d in self.dimensions if d.name in self.required and not d.ready
        )

    def to_dict(self) -> dict:
        return {
            "overall_ready": self.overall,
            "blocking": list(self.blocking),
            "dimensions": {d.name: d.to_dict() for d in self.dimensions},
        }


def _architecture() -> ReadinessDimension:
    """Whether the fitness functions pass in this build.

    Imported and run rather than trusted from a cached artifact: a build whose
    architecture drifted since the last CI run is exactly the build that would
    trust a stale artifact.
    """
    try:
        from backend.platform.architecture import analyze

        result = analyze()
        blocking = list(result.blocking_violations)
        return ReadinessDimension(
            "architecture_ready", result.gate_passed and not blocking,
            "no blocking architecture violations"
            if result.gate_passed and not blocking
            else f"{len(blocking)} blocking architecture violation(s)",
            {
                "passed": len(result.passed),
                "failed": len(result.failed),
                "skipped": len(result.skipped),
                "warnings": len(result.all_warnings),
            },
        )
    except Exception as exc:  # noqa: BLE001 - unverifiable is not ready
        return ReadinessDimension(
            "architecture_ready", False,
            f"architecture fitness could not be evaluated ({type(exc).__name__})",
        )


def _database(persistence: Optional[Any]) -> ReadinessDimension:
    if persistence is None:
        return ReadinessDimension(
            "database_ready", False, "no durable persistence is wired"
        )
    try:
        from backend.database.durable.config import verify_durability

        report = verify_durability(persistence.store)
        return ReadinessDimension(
            "database_ready", bool(report.ready),
            "the database is reachable, transactional and at the expected schema"
            if report.ready else "the database did not verify",
            {
                "dialect": report.to_dict().get("dialect"),
                "schema_version_ok": report.to_dict().get("schema_version_ok"),
                "missing_tables": report.to_dict().get("missing_tables"),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return ReadinessDimension(
            "database_ready", False,
            f"the database could not be verified ({type(exc).__name__})",
        )


def _durability(persistence: Optional[Any], database: ReadinessDimension) -> ReadinessDimension:
    if not database.ready:
        return ReadinessDimension(
            "durability_ready", False,
            "unanswerable while the database is not ready; durability is a "
            "property of the database, not a separate subsystem",
        )
    return ReadinessDimension(
        "durability_ready", True,
        "execution state, leases, idempotency and the outbox are durable",
    )


def _scheduler(persistence: Optional[Any], database: ReadinessDimension) -> ReadinessDimension:
    if persistence is None or not database.ready:
        return ReadinessDimension(
            "scheduler_ready", False,
            "the scheduler needs durable leadership, which needs the database",
        )
    try:
        roles = list(persistence.leadership.roles())
        return ReadinessDimension(
            "scheduler_ready", True,
            "durable leadership is available; holding a role is a runtime "
            "condition, not a readiness one",
            {"roles_held": roles},
        )
    except Exception as exc:  # noqa: BLE001
        return ReadinessDimension(
            "scheduler_ready", False,
            f"leadership state could not be read ({type(exc).__name__})",
        )


def _connectivity(connectivity: Optional[Any]) -> tuple:
    if connectivity is None:
        absent = "no connectivity graph is wired"
        return (
            ReadinessDimension("credential_ready", False, absent),
            ReadinessDimension("transport_ready", False, absent),
            ReadinessDimension("worker_ready", False, absent),
            ReadinessDimension("provider_ready", False, absent),
        )

    providers = tuple(getattr(connectivity.credential_broker, "providers", ()) or ())
    kinds = tuple(getattr(connectivity.transport_broker, "kinds", ()) or ())
    adapters = tuple(getattr(connectivity, "adapters", {}) or ())

    credential = ReadinessDimension(
        "credential_ready", bool(providers),
        "a credential adapter is registered" if providers
        else "no credential adapter is registered; every invocation would refuse "
             "with credential_no_provider",
        {"providers": list(providers)},
    )
    transport = ReadinessDimension(
        "transport_ready", bool(kinds),
        "a transport adapter is registered" if kinds
        else "no transport adapter is registered; nothing can reach a provider",
        {"kinds": [getattr(k, "value", str(k)) for k in kinds]},
    )

    # A registered worker is not an executable one. Phase 5.3 made the lifecycle
    # explicit, so readiness asks the directory rather than counting adapters.
    executable: list = []
    try:
        for worker_id in adapters:
            entry = connectivity.directory.entry(
                _PlatformContext(), worker_id=worker_id, tenant_id=""
            )
            if entry is not None and entry.is_executable:
                executable.append(worker_id)
    except Exception:  # noqa: BLE001 - an unreadable directory is not a ready one
        executable = []

    worker = ReadinessDimension(
        "worker_ready", bool(executable),
        "at least one worker is validated, trusted, enabled and available"
        if executable
        else "no worker is executable; workers are registered but not commissioned "
             "(REGISTERED -> VALIDATED -> ENABLED is three deliberate acts)",
        {"registered": list(adapters), "executable": executable},
    )
    provider = ReadinessDimension(
        "provider_ready",
        bool(executable) and bool(providers) and bool(transport.ready),
        "an executable worker, a credential adapter and a transport all exist. "
        "This does **not** mean a provider answered — that is not knowable "
        "without calling one, and a health check must not spend a rate limit",
        {"catalogs": sorted(getattr(connectivity, "catalogs", {}) or ())},
    )
    return credential, transport, worker, provider


def _delegation(persistence: Optional[Any], database: ReadinessDimension) -> ReadinessDimension:
    if persistence is None or not database.ready:
        return ReadinessDimension(
            "delegation_ready", False,
            "delegation authority is durable; without the database every "
            "on-behalf-of invocation refuses, which is safe but not ready",
        )
    workflow = getattr(persistence, "delegation_workflow", None)
    if workflow is None:
        return ReadinessDimension(
            "delegation_ready", False,
            "no delegation workflow is wired; grants cannot be issued at all",
        )
    return ReadinessDimension(
        "delegation_ready", True,
        "the request -> approve -> issue -> revoke path is wired",
        {"approver_policy": getattr(workflow, "policy_name", "unknown")},
    )


def _operational() -> ReadinessDimension:
    """Configuration that must not be set in a production process."""
    unsafe = [
        name
        for name in (
            "CORTEXPRIME_ENABLE_LEGACY_CONNECTIVITY",
            "CORTEXPRIME_ENABLE_LEGACY_EXECUTION",
            "CORTEXPRIME_ALLOW_SCHEMA_BOOTSTRAP",
            "CORTEXPRIME_ENABLE_UNCONTAINED_PROCESS_LAUNCH",
            "CORTEXPRIME_ENABLE_UNSANDBOXED_SCRIPT_EXECUTION",
        )
        if os.environ.get(name, "").strip().lower() in ("1", "true", "yes")
    ]
    return ReadinessDimension(
        "operational_ready", not unsafe,
        "no legacy or uncontained surface is enabled" if not unsafe
        else "a V1 or uncontained surface is enabled in this process",
        {"enabled_unsafe_flags": unsafe},
    )


class _PlatformContext:
    """The platform-scoped read context the worker directory expects."""

    tenant_id = ""
    is_platform_internal = True
    scope = None
    correlation = None
    identity = None

    def audit_detail(self) -> dict:
        return {"tenant_id": self.tenant_id}


def assess_readiness(
    *,
    persistence: Optional[Any] = None,
    connectivity: Optional[Any] = None,
    required: Optional[frozenset] = None,
) -> ReadinessReport:
    """Answer all ten dimensions. Nothing is assumed and nothing is cached.

    ``required`` lets a deployment declare which dimensions gate traffic. A
    read-only reporting instance legitimately does not need ``provider_ready``;
    an execution node does. Defaulting to *all* of them is deliberate — a
    deployment that has not thought about it gets the strict answer.
    """
    architecture = _architecture()
    database = _database(persistence)
    credential, transport, worker, provider = _connectivity(connectivity)
    dimensions = (
        architecture,
        database,
        _durability(persistence, database),
        _scheduler(persistence, database),
        credential,
        transport,
        worker,
        provider,
        _delegation(persistence, database),
        _operational(),
    )
    return ReadinessReport(
        dimensions=dimensions,
        required=required if required is not None else frozenset(READINESS_DIMENSIONS),
    )
