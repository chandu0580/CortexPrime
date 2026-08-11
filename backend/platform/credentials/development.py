"""The development credential adapter. Named so nobody can mistake it.

Why it is called what it is called
------------------------------------
``DevelopmentCredentialProvider``. Not ``InMemoryProvider``, not
``SimpleProvider``, not ``DefaultProvider``. A name that reads as harmless is a
name that ends up in a production composition root, and the person reviewing that
diff sees "Simple" and moves on.

Four refusals that make production use impossible rather than discouraged
--------------------------------------------------------------------------
1. It refuses to construct with ``PRODUCTION`` in its environments.
2. It refuses to construct without ``allow_non_production=True`` passed
   explicitly, so registering one is a deliberate sentence rather than a default.
3. It refuses to issue for a production request at acquisition time as well —
   construction-time checks are bypassable by a mutated attribute, so the
   invariant is asserted again where it matters.
4. It holds **no secrets of its own**. Every value is supplied by the caller that
   constructed it, so there are no hard-coded API keys to leak, to be copied into
   a fixture, or to be found in this file by a scraper.

What it is genuinely for
--------------------------
Exercising the fabric — the broker's verification, the gateway's ordering, the
redaction — without a network, a vault, or a real secret. That is a real need:
the whole authority chain is testable end-to-end only if something can answer
``acquire``.

What it is not
----------------
Secret storage. Values live in process memory for as long as the object does,
are lost on restart, and are protected by nothing. Stated here so no deployment
can adopt it by assuming otherwise.
"""

from __future__ import annotations

import secrets as _secrets
from datetime import datetime, timezone
from typing import Mapping, Optional

from backend.contracts.credential import (
    CredentialRef,
    CredentialScope,
    CredentialState,
    CredentialType,
)
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionEnvironment
from backend.platform.credentials.broker import IssuedCredential
from backend.platform.credentials.material import CredentialMaterial
from backend.platform.credentials.request import (
    CredentialGrant,
    CredentialRefusal,
    CredentialRefused,
    CredentialRequest,
)

__all__ = ["DevelopmentCredentialProvider"]


class DevelopmentCredentialProvider:
    """A non-production credential adapter. Refuses production, four ways over."""

    def __init__(
        self,
        *,
        provider_id: str,
        secrets: Mapping[str, str],
        allow_non_production: bool,
        environments: Optional[frozenset] = None,
        credential_type: CredentialType = CredentialType.API_KEY,
        scope: Optional[CredentialScope] = None,
    ) -> None:
        if allow_non_production is not True:
            raise ContractViolation(
                "DevelopmentCredentialProvider requires allow_non_production=True "
                "to be passed explicitly. Registering a development credential "
                "source must be a sentence somebody wrote, not a default somebody "
                "inherited"
            )
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ContractViolation("provider_id must be non-blank text")

        allowed = frozenset(
            environments
            or {ExecutionEnvironment.DEVELOPMENT, ExecutionEnvironment.STAGING}
        )
        for environment in allowed:
            if not isinstance(environment, ExecutionEnvironment):
                raise ContractViolation(
                    "environments must contain ExecutionEnvironment values"
                )
        if ExecutionEnvironment.PRODUCTION in allowed:
            raise ContractViolation(
                "DevelopmentCredentialProvider cannot serve PRODUCTION. It holds "
                "secrets in process memory with no storage, no rotation and no "
                "revocation; a production deployment needs an adapter that has "
                "those, not a name that says it does"
            )
        if not secrets:
            raise ContractViolation(
                "a development provider must be given the values it will hand "
                "out; this module ships none, so that there is no hard-coded key "
                "here to leak or to be copied into a fixture"
            )
        for tenant_key, value in dict(secrets).items():
            if not isinstance(tenant_key, str) or not isinstance(value, str) or not value:
                raise ContractViolation(
                    "development secrets must be a mapping of tenant id to a "
                    "non-empty string"
                )

        self._provider_id = provider_id.strip()
        self._environments = allowed
        self._type = credential_type
        self._scope = scope
        # Keyed by tenant. Even here there is no shared bucket: a development
        # provider that returned one tenant's value to another would teach the
        # rest of the system that cross-tenant reads are survivable.
        self._secrets = dict(secrets)
        self._issued: dict = {}
        self._revoked: set = set()

    # -- adapter contract ------------------------------------------------

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def environments(self) -> frozenset:
        return self._environments

    def acquire(
        self,
        request: CredentialRequest,
        *,
        expires_at: datetime,
        now: Optional[datetime] = None,
    ) -> IssuedCredential:
        # Asserted again at the point of use. A construction-time check alone is
        # bypassable by anything that mutates the attribute afterwards, and this
        # is the invariant least survivable to get wrong.
        if request.environment is ExecutionEnvironment.PRODUCTION:
            raise CredentialRefused(
                CredentialRefusal.ENVIRONMENT_MISMATCH,
                "the development credential provider does not serve production",
                correlation_id=request.correlation_id,
            )
        if request.environment not in self._environments:
            raise CredentialRefused(
                CredentialRefusal.ENVIRONMENT_MISMATCH,
                "the development credential provider is not registered for this "
                "environment",
                correlation_id=request.correlation_id,
            )

        secret = self._secrets.get(request.tenant_id)
        if secret is None:
            # No fallback to another tenant's value, and no default. The absence
            # is the answer.
            raise CredentialRefused(
                CredentialRefusal.NO_PROVIDER,
                "no development credential is configured for this tenant",
                correlation_id=request.correlation_id,
            )

        # The broker's clock, never our own. It already established that a
        # window remains; re-deriving "now" here is how one component decides a
        # request is live and the next decides it is not.
        moment = now or datetime.now(timezone.utc)

        ref = CredentialRef(
            tenant_id=request.tenant_id,
            # Random, not derived: an id derived from the secret would leak it,
            # and one derived from the action would collide across attempts.
            credential_id=f"dev-{_secrets.token_hex(8)}",
        )
        material = CredentialMaterial(
            secret=secret,
            ref=ref,
            credential_type=self._type,
            expires_at=expires_at,
            acquired_at=moment,
            headers=("Authorization",),
        )
        grant = CredentialGrant(
            ref=ref,
            credential_type=self._type,
            # Exactly what was asked for. A development provider that granted
            # more would be training the broker's broadening check to fire, and
            # a check that always fires gets turned off.
            scope=self._scope or request.scope,
            state=CredentialState.ACTIVE,
            issued_at=moment,
            expires_at=expires_at,
            tenant_id=request.tenant_id,
            action_digest=request.action_digest,
            binding_digest=request.binding_digest,
            provider=self._provider_id,
            environment=request.environment,
            fingerprint=material.fingerprint(),
            provider_reference="development",
        )
        self._issued[ref.credential_id] = grant
        return IssuedCredential(grant, material)

    def validate(self, ref: CredentialRef) -> CredentialState:
        if ref.credential_id in self._revoked:
            return CredentialState.REVOKED
        grant = self._issued.get(ref.credential_id)
        if grant is None:
            # Not "active because we have no record of a problem". An unknown
            # reference is unknown, and unknown fails closed at the broker.
            return CredentialState.UNKNOWN
        if grant.expires_at <= datetime.now(timezone.utc):
            return CredentialState.EXPIRED
        return CredentialState.ACTIVE

    def revoke(self, ref: CredentialRef, *, reason: str) -> bool:
        if ref.credential_id not in self._issued:
            return False
        self._revoked.add(ref.credential_id)
        return True

    def __repr__(self) -> str:
        # Never the secrets, and never their count in a way that hints at content.
        return (
            f"<DevelopmentCredentialProvider provider={self._provider_id} "
            f"environments={sorted(e.value for e in self._environments)} "
            "NON-PRODUCTION>"
        )
