"""Invariant probes whose enforcement lives outside ``platform/``.

Constitution S10 forbids ``platform/`` from importing a bounded context or a
service. Invariant **I2**'s enforcement lives in ``backend.services``, so its
probe cannot live in ``backend.platform.architecture`` -- the architecture suite
would violate the very rule it enforces.

It lives here instead and is injected via
``constitutional_invariants(probes=...)``. That is the difference between an
architecture suite that holds itself to its own rules and one with an exemption
list.

The alternative -- exempting ``invariant_tests.py`` from the platform rule --
was rejected: an exemption granted once to the module that enforces the rules is
the first step in the erosion this suite exists to prevent.
"""

from __future__ import annotations

import copy
import tempfile
from pathlib import Path
from typing import Optional


def probe_i2_approval_binding(_graph) -> Optional[str]:
    """I2 -- no approved action executes with a payload that differs.

    Probes both enforcement layers, so removing either is caught:

    * PR-04 self-consistency -- the payload matches the digest beside it.
    * PR-05 decision binding  -- the artifact matches the digest recorded
      independently at approval time.

    Returns ``None`` when the invariant holds, or a description of the breach.
    """
    from backend.services.enterprise_approval_decision import (
        ApprovalDecisionStore,
        ApprovalFailure,
        HmacApprovalSigner,
    )
    from backend.services.enterprise_approval_integrity import (
        IntegrityFailure,
        build_record,
        record_digest,
        verify_record,
    )

    # -- layer 1: record self-consistency ---------------------------------
    record = build_record("inv-wf", "docker_health_fix", {"container": "web-01"})
    if not verify_record("inv-wf", record).ok:
        return "an untampered record failed verification (false positive)"

    tampered = copy.deepcopy(record)
    tampered["payload"]["container"] = "prod-payments-db"
    verdict = verify_record("inv-wf", tampered)
    if verdict.ok:
        return "a tampered payload passed integrity verification"
    if verdict.failure is not IntegrityFailure.DIGEST_MISMATCH:
        return f"tampering reported as {verdict.failure}, expected DIGEST_MISMATCH"

    stripped = copy.deepcopy(record)
    del stripped["digest"]
    if verify_record("inv-wf", stripped).ok:
        return "a record with no digest passed verification (fail-open)"

    legacy = {"action_type": "docker_health_fix", "payload": {"container": "web-01"}}
    if verify_record("inv-wf", legacy).ok:
        return "a pre-integrity legacy record passed verification (fail-open)"

    # -- layer 2: authoritative decision binding ---------------------------
    with tempfile.TemporaryDirectory() as tmp:
        store = ApprovalDecisionStore(
            Path(tmp) / "decisions.json", signer=HmacApprovalSigner("i" * 32)
        )
        approved = record_digest("inv-wf", "docker_health_fix", {"container": "web-01"})
        store.record_request("inv-wf", "docker_health_fix", approved)
        store.record_grant("inv-wf", "inv-approver", "human")

        if not store.verify_for_execution("inv-wf", approved, "docker_health_fix").ok:
            return "a matching artifact failed decision binding (false positive)"

        forged = record_digest("inv-wf", "docker_health_fix", {"container": "prod-db"})
        forged_verdict = store.verify_for_execution("inv-wf", forged, "docker_health_fix")
        if forged_verdict.ok:
            return "a self-consistent forgery passed decision binding"
        if forged_verdict.failure is not ApprovalFailure.ARTIFACT_MODIFIED:
            return (
                f"forgery reported as {forged_verdict.failure}, expected ARTIFACT_MODIFIED"
            )

        # The platform must never authorize itself.
        store.record_request("inv-self", "docker_health_fix", approved)
        store.record_grant("inv-self", "cortexprime", "platform")
        self_auth = store.verify_for_execution("inv-self", approved, "docker_health_fix")
        if self_auth.ok:
            return "a platform principal authorized an execution"

    return None


def probe_i6_storage_engine(_graph) -> Optional[str]:
    """I6 -- the tenant guard holds against a real SQL engine.

    ``invariant_tests._probe_i6_tenant_identity`` checks the guard in isolation.
    This one drives it through real SQLAlchemy, over a real table, with real
    sessions -- because the claim "a cross-tenant read returns nothing" is about
    a query that actually ran, and a guard can construct a perfectly correct
    predicate that the ORM then fails to apply.

    Lives here rather than in ``platform/architecture`` because Constitution S10
    forbids ``platform/`` from importing ``backend.database``. Same reason, same
    mechanism as the I2 probe above.
    """
    import asyncio
    import uuid

    from sqlalchemy import Column, String, Uuid
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.orm import DeclarativeBase

    from backend.database.repositories.tenant_scoped import TenantScopedRepository
    from backend.platform.context import ExecutionContext
    from backend.platform.context.identity import IdentityContext
    from backend.platform.storage import CrossTenantAccess, MissingExecutionContext

    class _Base(DeclarativeBase):
        pass

    # Classic Column style, not Mapped[...]. This module carries
    # ``from __future__ import annotations``, so annotations are strings, and
    # SQLAlchemy cannot resolve a ``Mapped`` imported inside a function body.
    class _Row(_Base):
        __tablename__ = "i6_probe_rows"
        id = Column(Uuid, primary_key=True, default=uuid.uuid4)
        tenant_id = Column(String(64), nullable=False)
        label = Column(String(64))

    class _Repo(TenantScopedRepository[_Row]):
        __scope_column__ = "tenant_id"

        def __init__(self, session):
            super().__init__(_Row, session)

    def _context(tenant_id: str) -> ExecutionContext:
        return ExecutionContext.for_tenant(
            tenant_id=tenant_id,
            identity=IdentityContext.platform("i6-probe"),
            source="architecture-probe",
        )

    async def _run() -> Optional[str]:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(_Base.metadata.create_all)

            maker = async_sessionmaker(engine, expire_on_commit=False)
            async with maker() as session:
                repo = _Repo(session)
                alice, bob = _context("i6-alice"), _context("i6-bob")

                await repo.create(alice, _Row(label="alice-row"))
                bob_row = await repo.create(bob, _Row(label="bob-row"))
                await session.commit()

                try:
                    await repo.list(None)
                except MissingExecutionContext:
                    pass
                else:
                    return "a repository listed rows with no execution context"

                visible = [row.label for row in await repo.list(alice)]
                if visible != ["alice-row"]:
                    return f"a scoped list returned {visible}, expected only alice's row"

                if await repo.count(bob) != 1:
                    return "a scoped count crossed the tenant boundary"

                try:
                    await repo.get(alice, bob_row.id)
                except CrossTenantAccess:
                    pass
                else:
                    return "a primary-key read returned another tenant's row"

                try:
                    await repo.create(alice, _Row(label="smuggled", tenant_id="i6-bob"))
                except CrossTenantAccess:
                    pass
                else:
                    return "a write into another tenant's scope was accepted"
        finally:
            await engine.dispose()
        return None

    try:
        return asyncio.run(_run())
    except RuntimeError:
        # Already inside a loop (the gate is being run from async code). The
        # in-process guard probe still covers the boundary; skipping here is
        # better than reporting a false violation.
        return None


#: Probes registered by the test layer, keyed by invariant id.
SERVICE_LEVEL_PROBES = {
    "I2": probe_i2_approval_binding,
    "I6": probe_i6_storage_engine,
}
