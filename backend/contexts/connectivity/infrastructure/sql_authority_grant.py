"""The durable authority-grant store — Phase 10.8 (ADR-101).

What this is
------------
Phases 10.5-10.7 built scoped approver and executor authority, and then read the
grants backing it out of ``data/tenants/tenant_users.json``: a gitignored file
of bare strings with no issuer, no timestamps, no digest and no audit event.
Enforcement was governed. Creation was not.

This module supplies **storage and attribution**. It supplies no judgement:

* whether a human may act on an approval is still decided by
  ``resolve_scoped_authority`` -- capability, environment, risk ceiling;
* whether an issuer may create a grant at all is decided by
  ``backend.auth.grants``, which owns that policy.

Neither is reimplemented here, and this module must never grow a second opinion
about either. It reads rows and writes rows.

Why the digest is recomputed on read
------------------------------------
``digest`` covers every authority-bearing field. ``live_grants_for`` recomputes
it from the row it just read and drops any row that does not match. That is the
whole tamper story: an operator with a psql prompt can widen ``environment`` or
raise ``max_risk``, and the row stops authorizing rather than authorizing
something nobody issued. It is detection, not prevention -- a database
administrator can also recompute the digest -- and the honest claim is that
silent mutation is what becomes impossible.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

import sqlalchemy as sa

from backend.database.durable.session import DurableStore
from backend.database.durable.tables import authority_grant_table as T

__all__ = [
    "SqlAuthorityGrantRepository",
    "AuthorityGrantRecord",
    "GrantPersistenceError",
    "grant_digest",
    "SCHEMA_VERSION",
]

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1


class GrantPersistenceError(RuntimeError):
    """A grant could not be persisted (a genuine store failure)."""


def grant_digest(
    *, tenant_id: str, subject_principal_id: str, authority_type: str,
    capability_ref: str, capability_version: str, environment: str,
    max_risk: Optional[str],
) -> str:
    """Deterministic identity over every authority-bearing field.

    Deliberately excludes ``issued_by``, ``issued_at``, ``issue_reason`` and the
    revocation columns: those describe the *provenance* of the authority, not
    the authority itself. Two grants of the same power issued by different
    people are the same power, and an auditor comparing digests is asking "is
    this the same authority?", not "was it issued twice?".

    Never includes a token, secret, credential or DSN -- there is no field here
    that could carry one.
    """
    canonical = json.dumps(
        {
            "tenant_id": tenant_id,
            "subject_principal_id": subject_principal_id,
            "authority_type": authority_type,
            "capability_ref": capability_ref,
            "capability_version": capability_version,
            "environment": environment,
            "max_risk": max_risk or "",
        },
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AuthorityGrantRecord:
    """One stored grant. A read model that decides nothing."""

    __slots__ = (
        "grant_id", "tenant_id", "subject_principal_id", "authority_type",
        "capability_ref", "capability_version", "environment", "max_risk",
        "issued_by", "issued_at", "issue_reason", "revoked_at", "revoked_by",
        "revocation_reason", "digest",
    )

    def __init__(self, **fields: Any) -> None:
        for name in self.__slots__:
            setattr(self, name, fields.get(name))

    @property
    def revoked(self) -> bool:
        return self.revoked_at is not None

    def digest_matches(self) -> bool:
        """Does this row still hash to the identity it was issued with?"""
        return self.digest == grant_digest(
            tenant_id=self.tenant_id,
            subject_principal_id=self.subject_principal_id,
            authority_type=self.authority_type,
            capability_ref=self.capability_ref,
            capability_version=self.capability_version,
            environment=self.environment,
            max_risk=self.max_risk,
        )

    def to_dict(self) -> dict:
        return {
            "grant_id": self.grant_id,
            "tenant_id": self.tenant_id,
            "subject_principal_id": self.subject_principal_id,
            "authority_type": self.authority_type,
            "capability_ref": self.capability_ref,
            "capability_version": self.capability_version,
            "environment": self.environment,
            "max_risk": self.max_risk,
            "issued_by": self.issued_by,
            "issued_at": self.issued_at.isoformat() if self.issued_at else None,
            "revoked_at": (self.revoked_at.isoformat()
                           if self.revoked_at else None),
            "revoked_by": self.revoked_by,
            "digest": self.digest,
        }


class SqlAuthorityGrantRepository:
    """Rows in, rows out. The authority policy lives in ``backend.auth.grants``."""

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise GrantPersistenceError(
                "the authority grant repository requires a DurableStore")
        self._store = store
        self._tampered: list = []

    # -- writes ------------------------------------------------------------

    def issue(
        self, *, grant_id: str, tenant_id: str, subject_principal_id: str,
        authority_type: str, capability_ref: str, capability_version: str,
        environment: str, max_risk: Optional[str], issued_by: str,
        issue_reason: str, now: Optional[datetime] = None,
    ) -> AuthorityGrantRecord:
        """Store one grant.

        ``issued_by`` and ``issue_reason`` are required keyword arguments with
        no defaults, so an unattributed grant is a ``TypeError`` rather than a
        row nobody can explain. The column is also ``NOT NULL``, so the same
        rule holds for anything that reaches the table another way.
        """
        if not issued_by or not str(issued_by).strip():
            raise GrantPersistenceError("a grant must name who issued it")
        if not issue_reason or len(str(issue_reason).strip()) < 8:
            raise GrantPersistenceError(
                "a grant must state why, in enough words to be reviewable")

        moment = now or datetime.now(timezone.utc)
        digest = grant_digest(
            tenant_id=tenant_id, subject_principal_id=subject_principal_id,
            authority_type=authority_type, capability_ref=capability_ref,
            capability_version=capability_version, environment=environment,
            max_risk=max_risk)
        values = {
            "grant_id": grant_id, "tenant_id": tenant_id,
            "subject_principal_id": subject_principal_id,
            "authority_type": authority_type, "capability_ref": capability_ref,
            "capability_version": capability_version,
            "environment": environment, "max_risk": max_risk,
            "issued_by": issued_by, "issued_at": moment,
            "issue_reason": issue_reason, "digest": digest,
            "schema_version": SCHEMA_VERSION,
        }
        with self._store.atomic() as work:
            work.execute(sa.insert(T).values(**values))
        return AuthorityGrantRecord(**values)

    def revoke(self, *, tenant_id: str, grant_id: str, revoked_by: str,
               reason: str, now: Optional[datetime] = None) -> bool:
        """Withdraw one grant. Tenant-scoped, and a set rather than a delete.

        The ``revoked_at IS NULL`` predicate makes a second revocation return
        ``False`` instead of overwriting who revoked it first. Two racing
        revocations are both correct about the outcome; only one of them is the
        one that happened.
        """
        moment = now or datetime.now(timezone.utc)
        with self._store.atomic() as work:
            result = work.execute(
                sa.update(T).where(
                    T.c.grant_id == grant_id,
                    T.c.tenant_id == tenant_id,
                    T.c.revoked_at.is_(None),
                ).values(revoked_at=moment, revoked_by=revoked_by,
                         revocation_reason=reason))
        return bool(getattr(result, "rowcount", 0))

    # -- reads -------------------------------------------------------------

    def live_grants_for(
        self, *, tenant_id: str, subject_principal_id: str,
        authority_type: str, now: Optional[datetime] = None,
    ) -> tuple:
        """Every live, untampered grant this subject holds for one authority.

        Three filters, each of which is a refusal rather than a convenience:
        the tenant (isolation), ``revoked_at IS NULL`` (revocation is
        authoritative on the next check, with nothing cached), and the digest
        recomputation (a mutated row is not the authority it claims to be).
        """
        with self._store.atomic() as work:
            rows = work.execute(
                sa.select(T).where(
                    T.c.tenant_id == tenant_id,
                    T.c.subject_principal_id == subject_principal_id,
                    T.c.authority_type == authority_type,
                    T.c.revoked_at.is_(None),
                )
            ).mappings().fetchall()
        live = []
        for row in rows:
            record = self._record(row)
            if record.digest_matches():
                live.append(record)
                continue
            # A row whose digest no longer covers its own fields. Dropping it
            # is the fail-closed half; saying so is the other half, because a
            # tampered grant that merely stops working looks identical to a
            # grant nobody ever issued -- and those need very different
            # responses from whoever is on call.
            log.error(
                "authority grant %s in tenant %s does not match its own digest "
                "and has been refused: an authority-bearing field was changed "
                "after issuance",
                record.grant_id, tenant_id)
            self._tampered.append(record.grant_id)
        return tuple(live)

    @property
    def tampered_grants(self) -> tuple:
        """Grant ids seen this process that failed their digest check.

        Read by the harness to prove detection happened rather than inferring
        it from an absence. Not authority state, and never consulted by a
        decision.
        """
        return tuple(self._tampered)

    def get(self, *, tenant_id: str,
            grant_id: str) -> Optional[AuthorityGrantRecord]:
        """One grant, only if it belongs to this tenant. Fails closed."""
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T).where(T.c.grant_id == grant_id,
                                   T.c.tenant_id == tenant_id)
            ).mappings().fetchone()
        return self._record(row) if row else None

    def list_for_tenant(self, *, tenant_id: str,
                        limit: int = 200) -> Sequence[AuthorityGrantRecord]:
        """Every grant in ONE tenant, revoked ones included.

        Revoked grants are returned deliberately: a list that hides them cannot
        answer "who used to be able to approve this?", which is the question an
        incident review actually asks.
        """
        with self._store.atomic() as work:
            rows = work.execute(
                sa.select(T).where(T.c.tenant_id == tenant_id)
                .order_by(T.c.issued_at.desc()).limit(int(limit))
            ).mappings().fetchall()
        return tuple(self._record(row) for row in rows)

    def count_all(self) -> int:
        with self._store.atomic() as work:
            return int(work.execute(
                sa.select(sa.func.count()).select_from(T)).scalar() or 0)

    @staticmethod
    def _record(row) -> AuthorityGrantRecord:
        return AuthorityGrantRecord(**{
            name: row[name] for name in AuthorityGrantRecord.__slots__
        })
