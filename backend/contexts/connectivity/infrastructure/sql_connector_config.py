"""Tenant-scoped connector configuration. **A reference store, not a secret store.**

What this replaces
--------------------
V1 configured a connector by posting its credentials::

    POST /api/connectors/{id}/connect
    {"credentials": {"token": "ghp_..."}}

into a process-wide store with no tenant. Three things were wrong with that and
all three are structural rather than a matter of care: the material travelled
through a request body, it was held for the whole process, and one authenticated
user's configuration was every user's configuration.

Phase 4.4 gated the route off. This is the shape that replaces it: the tenant is
part of the primary key, the material never arrives, and what is stored is a
*reference* the credential broker resolves at invocation time.

The refusal is a check, not a convention
------------------------------------------
``_refuse_secret_material`` walks everything about to be written and refuses on
two grounds:

* a field **named** like a secret — token, password, api_key, client_secret;
* a value **shaped** like one — the recognisable prefixes real providers issue,
  and anything long enough and dense enough to be a bearer token.

The second exists because the first is defeated by calling the field ``value``.
Neither is a complete defence and neither is claimed to be: what they buy is that
a secret cannot arrive here *accidentally*, which is how secrets actually arrive
in configuration tables.

A refusal raises before the write and the exception message quotes the field name
and never the value — an error that echoed the token it was refusing would put it
in the log, which is the outcome this module exists to prevent.

Scope of the digest
---------------------
Covers the endpoint, the credential reference, the credential scope and the
policy. It does not cover ``updated_at`` — a configuration re-saved unchanged has
the same digest, which is what makes "did this change?" answerable at all.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

import sqlalchemy as sa

from backend.contracts.errors import ContractViolation
from backend.contracts.storage import StorageBinding, StorageOperation
from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import (
    DurableStore,
    NoDurableStore,
    UnitOfWork,
    enlisted,
)
from backend.database.durable.tables import connector_config_table
from backend.platform.hashing import compute_digest
from backend.platform.storage import RepositoryGuard

__all__ = [
    "SqlConnectorConfigRepository",
    "ConnectorConfigRecord",
    "SecretMaterialRefused",
    "CONNECTOR_CONFIG_BINDING",
    "CREDENTIAL_REF_PATTERN",
]

CONNECTOR_CONFIG_BINDING = StorageBinding(
    record_type="ConnectorConfiguration",
    scope_column="tenant_id",
    platform_internal_allowed=True,
)

CREDENTIAL_REF_PATTERN = re.compile(r"^(cred|vault|kms|secretref)://[A-Za-z0-9._\-/]{1,200}$")
"""What a credential *reference* looks like. A scheme, a path, nothing else.

Anything that is not this is refused — including a bare identifier, because a
bare identifier is indistinguishable from a short token and this column is the
last place to notice the difference.
"""

#: Field names that carry secrets often enough that a value under one of them is
#: refused without looking at it.
_SECRET_NAMES = (
    "token", "secret", "password", "passwd", "api_key", "apikey", "access_key",
    "private_key", "client_secret", "authorization", "auth", "bearer",
    "credential", "credentials", "session_key", "refresh_token", "signature",
)

#: Prefixes real providers issue. Present because naming a field ``value``
#: defeats the check above, and a GitHub PAT is recognisable regardless of what
#: it is called.
_SECRET_PREFIXES = (
    "ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_", "sk-", "sk_live_",
    "pk_live_", "xoxb-", "xoxp-", "xapp-", "AKIA", "ASIA", "AIza", "ya29.",
    "eyJ", "Bearer ", "Basic ", "-----BEGIN",
)

_DENSE = re.compile(r"^[A-Za-z0-9+/_\-=.]{40,}$")


class SecretMaterialRefused(ContractViolation):
    """Something that looked like secret material was about to be stored.

    Carries the *field* and never the value. An exception message that quoted
    the token it was refusing would write it to the log, which is the specific
    outcome this check exists to prevent.
    """

    def __init__(self, field: str, why: str) -> None:
        super().__init__(
            f"refusing to store connector configuration: field {field!r} {why}. "
            "Connector configuration holds a credential *reference*; the material "
            "stays in the credential broker and is fetched at invocation time"
        )
        self.field = field


def _refuse_secret_material(value: Any, *, path: str = "") -> None:
    """Walk a configuration document and refuse anything secret-shaped."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            name = str(key)
            where = f"{path}.{name}" if path else name
            if any(marker in name.lower() for marker in _SECRET_NAMES):
                raise SecretMaterialRefused(where, "is named like secret material")
            _refuse_secret_material(item, path=where)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _refuse_secret_material(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        text = value.strip()
        if any(text.startswith(prefix) for prefix in _SECRET_PREFIXES):
            raise SecretMaterialRefused(
                path or "<root>", "starts with a known credential prefix"
            )
        if _DENSE.match(text) and not CREDENTIAL_REF_PATTERN.match(text):
            raise SecretMaterialRefused(
                path or "<root>",
                "is long and dense enough to be a bearer token; store a "
                "cred:// reference instead",
            )


class ConnectorConfigRecord:
    """One connector configuration, as read back. Contains no secret by design."""

    __slots__ = (
        "tenant_id",
        "provider_id",
        "environment",
        "endpoint",
        "credential_ref",
        "credential_scope",
        "policy",
        "status",
        "digest",
        "configured_by",
        "created_at",
        "updated_at",
    )

    def __init__(self, **fields: Any) -> None:
        for name in self.__slots__:
            setattr(self, name, fields.get(name))

    @property
    def is_enabled(self) -> bool:
        return self.status == "enabled"

    def to_dict(self) -> dict:
        """Safe to log, safe to return, safe to put in an event.

        True because there is nothing here that could be unsafe — not because
        anything is redacted on the way out. A configuration that needed
        redacting would already have failed ``_refuse_secret_material``.
        """
        return {
            "tenant_id": self.tenant_id,
            "provider_id": self.provider_id,
            "environment": self.environment,
            "endpoint": self.endpoint,
            "credential_ref": self.credential_ref,
            "credential_scope": self.credential_scope,
            "policy": self.policy,
            "status": self.status,
            "digest": self.digest,
            "configured_by": self.configured_by,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }


class SqlConnectorConfigRepository:
    """Reads and writes connector configuration. Resolves no credential."""

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise NoDurableStore("a durable connector configuration store requires a store")
        self._store = store
        self._guard = RepositoryGuard(CONNECTOR_CONFIG_BINDING)

    def configure(
        self,
        context: Any,
        *,
        provider_id: str,
        environment: str,
        endpoint: str,
        credential_ref: Optional[str],
        credential_scope: Sequence[str] = (),
        policy: Optional[Mapping[str, Any]] = None,
        configured_by: str,
        status: str = "configured",
        unit: Optional[UnitOfWork] = None,
    ) -> ConnectorConfigRecord:
        """Save a configuration for one tenant. Upserts by (tenant, provider, env).

        Upsert rather than insert-only because a rotated credential reference is
        the same configuration pointing somewhere new, not a second
        configuration — and two rows for one provider is how a tenant ends up
        with a connector nobody can say the state of.
        """
        if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
            raise ContractViolation(
                "a connector endpoint must be https; plaintext transport would "
                "carry the credential the broker is about to mint"
            )
        if credential_ref is not None and not CREDENTIAL_REF_PATTERN.match(credential_ref):
            raise SecretMaterialRefused(
                "credential_ref",
                "is not a credential reference (expected cred:// or vault://)",
            )
        scope = [str(entry) for entry in credential_scope]
        rules = dict(policy or {})
        _refuse_secret_material(rules, path="policy")
        _refuse_secret_material(scope, path="credential_scope")
        _refuse_secret_material(endpoint, path="endpoint")

        access = self._guard.authorize(StorageOperation.WRITE, context)
        digest = compute_digest(
            {
                "tenant_id": access.tenant_id,
                "provider_id": provider_id,
                "environment": environment,
                "endpoint": endpoint,
                "credential_ref": credential_ref,
                "credential_scope": scope,
                "policy": rules,
            }
        ).value

        with self._scope(unit) as work:
            values = dict(
                endpoint=endpoint,
                credential_ref=credential_ref,
                credential_scope=scope,
                policy=rules,
                status=status,
                digest=digest,
                configured_by=configured_by,
                updated_at=work.now,
            )
            updated = work.execute(
                sa.update(connector_config_table)
                .where(
                    connector_config_table.c.tenant_id == access.tenant_id,
                    connector_config_table.c.provider_id == provider_id,
                    connector_config_table.c.environment == environment,
                )
                .values(**values)
            )
            created_at = work.now
            if updated.rowcount == 0:
                try:
                    work.execute(
                        sa.insert(connector_config_table).values(
                            tenant_id=access.tenant_id,
                            provider_id=provider_id,
                            environment=environment,
                            created_at=work.now,
                            **values,
                        )
                    )
                except ConstraintConflict:
                    # Somebody configured the same provider between the update
                    # and the insert. Their write is as valid as this one; the
                    # loser reports rather than forcing.
                    raise ContractViolation(
                        f"connector configuration for {provider_id}/{environment} "
                        "was written concurrently; re-read and retry"
                    ) from None
            else:
                row = work.execute(
                    sa.select(connector_config_table.c.created_at).where(
                        connector_config_table.c.tenant_id == access.tenant_id,
                        connector_config_table.c.provider_id == provider_id,
                        connector_config_table.c.environment == environment,
                    )
                ).scalar_one_or_none()
                created_at = row or work.now

        return ConnectorConfigRecord(
            tenant_id=access.tenant_id,
            provider_id=provider_id,
            environment=environment,
            created_at=created_at,
            **values,
        )

    def find(
        self,
        context: Any,
        *,
        provider_id: str,
        environment: str,
        unit: Optional[UnitOfWork] = None,
    ) -> Optional[ConnectorConfigRecord]:
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            row = work.execute(
                sa.select(connector_config_table).where(
                    connector_config_table.c.provider_id == provider_id,
                    connector_config_table.c.environment == environment,
                    *self._predicate(access),
                )
            ).mappings().first()
        if row is None:
            return None
        return ConnectorConfigRecord(
            **{k: row[k] for k in ConnectorConfigRecord.__slots__}
        )

    def enable(
        self,
        context: Any,
        *,
        provider_id: str,
        environment: str,
        expected_digest: str,
        unit: Optional[UnitOfWork] = None,
    ) -> bool:
        """Turn a configuration on, **against the digest that was reviewed**.

        Conditional on the digest, so a configuration edited between review and
        enablement is not the one that gets enabled: the predicate matches
        nothing and this returns ``False``.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            result = work.execute(
                sa.update(connector_config_table)
                .where(
                    connector_config_table.c.provider_id == provider_id,
                    connector_config_table.c.environment == environment,
                    connector_config_table.c.digest == expected_digest,
                    *self._predicate(access),
                )
                .values(status="enabled", updated_at=work.now)
            )
            return result.rowcount == 1

    def disable(
        self,
        context: Any,
        *,
        provider_id: str,
        environment: str,
        unit: Optional[UnitOfWork] = None,
    ) -> bool:
        """Turn a configuration off. Unconditional, because turning something
        off is always safe and requiring a digest match would mean a
        configuration that had drifted could not be stopped."""
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            result = work.execute(
                sa.update(connector_config_table)
                .where(
                    connector_config_table.c.provider_id == provider_id,
                    connector_config_table.c.environment == environment,
                    *self._predicate(access),
                )
                .values(status="disabled", updated_at=work.now)
            )
            return result.rowcount == 1

    def for_tenant(
        self, context: Any, *, limit: int = 100, unit: Optional[UnitOfWork] = None
    ) -> Sequence[ConnectorConfigRecord]:
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            rows = work.execute(
                sa.select(connector_config_table)
                .where(*self._predicate(access))
                .order_by(connector_config_table.c.provider_id)
                .limit(limit)
            ).mappings().all()
        return tuple(
            ConnectorConfigRecord(**{k: row[k] for k in ConnectorConfigRecord.__slots__})
            for row in rows
        )

    def _predicate(self, access: Any) -> tuple:
        scope = self._guard.scope_filter(access)
        if scope is None:
            return ()
        column, value = scope
        return (connector_config_table.c[column] == value,)

    def _scope(self, unit: Optional[UnitOfWork]):
        return enlisted(self._store, unit)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
