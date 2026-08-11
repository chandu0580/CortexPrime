"""Durable audit runtime — compliance-grade evidence, not logging.

The single source of truth for every security-critical decision CortexPrime
makes. Constitution I3: append-only and independently verifiable. S8: designed
for a hostile reader.

    from backend.platform.audit import AuditRuntime, JsonlAuditStore, verify_chain

    runtime = AuditRuntime(JsonlAuditStore(Path("backend/data/audit.jsonl")))
    runtime.record(
        AuditEventKind.EXECUTION_REFUSED,
        scope,
        subject_reference=workflow_id,
        detail={"failure": "digest_mismatch"},
        correlation_id=incident_id,
    )

    report = verify_chain(runtime)
    assert report.ok, report.summary()

What belongs here
-----------------
Approvals, executions, policy decisions, verification results, integrity
failures, replay attempts, configuration changes, identity events, connector
operations.

What does not
-------------
Application logging, metrics, traces, debug output. Those are observability:
sampled, expired, and mutable. Mixing them into an evidence trail devalues both.

Storage is abstract
-------------------
``AuditStore`` is a Protocol with no update and no delete — not by convention,
but because the operations do not exist to call. ``JsonlAuditStore`` is the
durable interim; PostgreSQL arrives in PR-11 behind the same interface.

See ``docs/adr/ADR-015-durable-audit-runtime.md``.
"""

from __future__ import annotations

from backend.platform.audit.exceptions import (
    AuditChainError,
    AuditCorruptionError,
    AuditWriterNotOwned,
    AuditError,
    AuditRetentionError,
    AuditStorageError,
    StaleAuditWriter,
)
from backend.platform.audit.retention import (
    AgeBasedRetention,
    KeepForever,
    RetentionDecision,
    RetentionPolicy,
    plan_retention,
)
from backend.platform.audit.runtime import AUDIT_SCHEMA_VERSION, AuditRuntime
from backend.platform.audit.store import (
    AuditQuery,
    AuditStore,
    InMemoryAuditStore,
    JsonlAuditStore,
)
from backend.platform.audit.verification import (
    ChainDefect,
    DefectKind,
    IntegrityReport,
    export_chain,
    verify_chain,
    verify_export,
)

__all__ = [
    "AUDIT_SCHEMA_VERSION",
    # runtime
    "AuditRuntime",
    # store
    "AuditStore",
    "AuditQuery",
    "InMemoryAuditStore",
    "JsonlAuditStore",
    # verification
    "verify_chain",
    "verify_export",
    "export_chain",
    "IntegrityReport",
    "ChainDefect",
    "DefectKind",
    # retention
    "RetentionPolicy",
    "KeepForever",
    "AgeBasedRetention",
    "RetentionDecision",
    "plan_retention",
    # errors
    "AuditError",
    "AuditStorageError",
    "AuditCorruptionError",
    "AuditWriterNotOwned",
    "StaleAuditWriter",
    "AuditChainError",
    "AuditRetentionError",
]
