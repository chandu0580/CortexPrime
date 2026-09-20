"""GitHub App installation credentials: the production GitHub credential path.

Phase 11.2 (ADR-126). The Kubernetes connector takes a short-lived, namespace-
confined ServiceAccount token from Vault per action. GitHub's equivalent is a
**GitHub App installation access token**: minted per action, expiring in an hour,
and -- this is the part that matters for tenancy -- restrictable to *named
repositories* and to a subset of the App's permissions at mint time.

    App private key (Vault KV, never the environment)
        -> JWT, RS256, <= 10 minutes, iss = App id        (GitHub docs)
        -> POST /app/installations/{id}/access_tokens
           { repositories: [...], permissions: {...} }
        -> installation token, expires_at, repository_selection

Why this module is in ``backend/api`` and not ``backend/platform``
-------------------------------------------------------------------
Signing an RS256 assertion needs a real crypto implementation, and
``backend/platform`` is required to import nothing outside the standard library
(the dependency-isolation gate). The Vault *Kubernetes* adapter could live there
because it only speaks HTTP. This one cannot, so it lives in the composition
layer, where third-party imports are already the rule, and keeps the same
discipline in every other respect: every request goes through the transport
broker (TLS, SSRF and address policy), the material is never logged, never
returned in a capability response, and never reaches the model.

What a deployment provides (all deployment configuration, never request input):
the App id, the installation id, the connected repositories, and the private key
**in Vault**. The key never appears in an environment variable, a ConfigMap, an
image or a log line.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from backend.contracts.credential import CredentialRef, CredentialState, CredentialType
from backend.contracts.errors import ContractViolation
from backend.platform.credentials.material import CredentialMaterial
from backend.platform.credentials.request import (
    CredentialGrant,
    CredentialRefusal,
    CredentialRefused,
)
from backend.platform.credentials.http_json import json_call
from backend.contracts.identity import PrincipalKind, PrincipalRef

__all__ = [
    "GITHUB_API_BASE",
    "GitHubAppIdentity",
    "GitHubAppTokenSource",
    "GitHubAppCredentialAdapter",
    "read_vault_kv",
]

log = logging.getLogger(__name__)

#: The fabric's own identity for credential acquisition: the same principal the
#: Vault adapters dial as, because this is the same act.
_PLATFORM_PRINCIPAL = PrincipalRef(principal_id="cortexprime.credential-fabric",
                                   kind=PrincipalKind.PLATFORM)

GITHUB_API_BASE = "https://api.github.com"

#: GitHub refuses a JWT whose ``exp`` is more than ten minutes ahead, and
#: recommends backdating ``iat`` by sixty seconds against clock drift.
_JWT_LIFETIME_SECONDS = 540
_JWT_BACKDATE_SECONDS = 60
#: An installation token lives an hour; it is replaced before the end of it so a
#: long action never starts with a credential that expires mid-flight.
_RENEW_FRACTION = 0.8
_MIN_REMAINING_SECONDS = 120


def _segment(value: str, label: str) -> str:
    text = str(value or "").strip()
    if not text or "/" in text or ".." in text:
        raise ContractViolation(f"{label} must be a single path segment")
    return text


def read_vault_kv(*, broker: Any, endpoint: Any, policy: Any, token: Any, mount: str,
                  path: str, correlation_id: Optional[str] = None) -> Mapping[str, Any]:
    """One KV v2 secret, as a mapping. Raises ``CredentialRefused`` if Vault says no."""
    status, document = json_call(
        broker, endpoint, policy, method="GET",
        path=f"/v1/{_segment(mount, 'the Vault mount')}/data/{path.strip('/')}",
        credential=token, tenant_id="cortexprime-platform", principal=_PLATFORM_PRINCIPAL,
        correlation_id=correlation_id, seconds=30.0,
        headers={"x-vault-request": "true"}, provider_label="Vault")
    if status in (401, 403):
        raise CredentialRefused(CredentialRefusal.PROVIDER_REFUSED,
                                "Vault refused this platform's identity for the GitHub App secret",
                                correlation_id=correlation_id)
    if status == 404:
        raise CredentialRefused(CredentialRefusal.NO_PROVIDER,
                                "Vault holds no GitHub App secret at the configured path",
                                correlation_id=correlation_id)
    data = (document or {}).get("data") if isinstance(document, Mapping) else None
    inner = data.get("data") if isinstance(data, Mapping) else None
    if status != 200 or not isinstance(inner, Mapping):
        raise CredentialRefused(CredentialRefusal.PROVIDER_MALFORMED,
                                f"Vault answered {status} without a KV v2 secret",
                                correlation_id=correlation_id)
    return inner


class GitHubAppIdentity:
    """The App's own identity, read from Vault once and kept in memory only."""

    __slots__ = ("app_id", "_private_key")

    def __init__(self, *, app_id: str, private_key_pem: str) -> None:
        if not str(app_id or "").strip():
            raise ContractViolation("a GitHub App identity needs the App id (JWT 'iss')")
        if "PRIVATE KEY" not in str(private_key_pem or ""):
            raise ContractViolation(
                "a GitHub App identity needs its PEM private key; GitHub signs the "
                "assertion with RS256 and nothing else can stand in for it")
        self.app_id = str(app_id).strip()
        self._private_key = private_key_pem

    def assertion(self, *, now: datetime) -> str:
        """A JWT GitHub will accept, signed RS256, valid for under ten minutes."""
        import jwt  # PyJWT; RS256 needs the cryptography backend

        issued = int(now.timestamp()) - _JWT_BACKDATE_SECONDS
        claims = {"iat": issued, "exp": issued + _JWT_LIFETIME_SECONDS, "iss": self.app_id}
        token = jwt.encode(claims, self._private_key, algorithm="RS256")
        return token if isinstance(token, str) else token.decode("utf-8")

    def __repr__(self) -> str:  # never the key
        return f"<GitHubAppIdentity app_id={self.app_id}>"

    __str__ = __repr__


class GitHubAppTokenSource:
    """Mints installation access tokens, scoped to the connected repositories.

    One source per installation. Tokens are cached until ``_RENEW_FRACTION`` of
    their life has passed and re-minted after that, or immediately after GitHub
    refuses one (a rotated App key, a suspended installation, a permission the
    operator removed).
    """

    def __init__(self, *, broker: Any, endpoint: Any, policy: Any, identity: GitHubAppIdentity,
                 installation_id: str, repositories: Sequence[str] = (),
                 permissions: Optional[Mapping[str, str]] = None,
                 clock: Optional[Any] = None) -> None:
        self._broker = broker
        self._endpoint = endpoint
        self._policy = policy
        self._identity = identity
        self._installation = _segment(installation_id, "the GitHub installation id")
        #: Only the repository NAME is sent; GitHub scopes within the installation's owner.
        self._repositories = tuple(sorted({str(r).split("/")[-1] for r in repositories if str(r).strip()}))
        self._permissions = dict(permissions or {})
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._expires_at: Optional[datetime] = None
        self._renew_at: Optional[datetime] = None
        self.last_minted_at: Optional[datetime] = None
        self.repository_selection: Optional[str] = None

    # -- the cached token ----------------------------------------------------

    def token(self, *, correlation_id: Optional[str] = None) -> tuple:
        """``(token, expires_at)``; minted if absent or due for renewal."""
        with self._lock:
            now = self._clock()
            if (self._token is not None and self._renew_at is not None and now < self._renew_at
                    and self._expires_at is not None
                    and (self._expires_at - now).total_seconds() > _MIN_REMAINING_SECONDS):
                return self._token, self._expires_at
            return self._mint(now, correlation_id)

    def invalidate(self, stale: Optional[str] = None) -> bool:
        """Forget the cached token, if it is still the one that failed.

        The Kubernetes connector learned this the hard way (11.1-K F-9): a
        credential cached past the point the provider stopped accepting it locks
        the connector out for the rest of its lifetime although one fresh mint
        would work.
        """
        with self._lock:
            if self._token is None or (stale is not None and self._token != stale):
                return False
            self._token, self._expires_at, self._renew_at = None, None, None
            return True

    def _mint(self, now: datetime, correlation_id: Optional[str]) -> tuple:
        body: dict = {}
        if self._repositories:
            body["repositories"] = list(self._repositories)
        if self._permissions:
            body["permissions"] = dict(self._permissions)
        assertion = CredentialMaterial(
            secret=self._identity.assertion(now=now),
            ref=CredentialRef(tenant_id="cortexprime-platform", credential_id="github-app-jwt"),
            credential_type=CredentialType.BEARER,
            expires_at=now + timedelta(seconds=_JWT_LIFETIME_SECONDS),
            acquired_at=now, headers=("Authorization",))
        status, document = json_call(
            self._broker, self._endpoint, self._policy, method="POST",
            path=f"/app/installations/{self._installation}/access_tokens",
            body=body or None, credential=assertion, tenant_id="cortexprime-platform",
            principal=_PLATFORM_PRINCIPAL, correlation_id=correlation_id, seconds=30.0,
            headers={"accept": "application/vnd.github+json",
                     "x-github-api-version": "2022-11-28"},
            provider_label="GitHub")
        if status in (401, 403):
            raise CredentialRefused(
                CredentialRefusal.PROVIDER_REFUSED,
                "GitHub refused this App's assertion (App id, private key or installation)",
                correlation_id=correlation_id)
        if status == 404:
            raise CredentialRefused(
                CredentialRefusal.NO_PROVIDER,
                "GitHub has no such installation for this App",
                correlation_id=correlation_id)
        if status == 422:
            raise CredentialRefused(
                CredentialRefusal.PROVIDER_REFUSED,
                "GitHub refused the requested token scope; a repository or permission "
                "asked for exceeds what the installation was granted",
                correlation_id=correlation_id)
        token = document.get("token") if isinstance(document, Mapping) else None
        expiry = document.get("expires_at") if isinstance(document, Mapping) else None
        if status != 201 or not isinstance(token, str) or not token:
            raise CredentialRefused(
                CredentialRefusal.PROVIDER_MALFORMED,
                f"GitHub answered {status} without an installation token",
                correlation_id=correlation_id)
        expires_at = _parse_timestamp(expiry) or (now + timedelta(hours=1))
        lifetime = max(1.0, (expires_at - now).total_seconds())
        self._token, self._expires_at = token, expires_at
        self._renew_at = now + timedelta(seconds=lifetime * _RENEW_FRACTION)
        self.last_minted_at = now
        selection = document.get("repository_selection") if isinstance(document, Mapping) else None
        self.repository_selection = selection if isinstance(selection, str) else None
        return token, expires_at

    def __repr__(self) -> str:  # never the token
        return (f"<GitHubAppTokenSource installation={self._installation} "
                f"repositories={len(self._repositories)}>")

    __str__ = __repr__


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GitHubAppCredentialAdapter:
    """A ``CredentialAdapter`` issuing GitHub App installation tokens.

    Standalone rather than a Vault adapter subclass: Vault is read once, at
    composition, for the App's private key. At acquisition time the only
    provider this talks to is GitHub, so inheriting a Vault read path would
    describe a request this adapter never makes.

    ``bindings`` maps a CortexPrime tenant to its ``GitHubAppTokenSource`` --
    deployment configuration, never request input. A tenant with no binding gets
    no credential, which is the structural half of the tenancy boundary; the
    other half is that the token itself is minted for named repositories only.
    """

    def __init__(self, *, provider_id: str, environments: frozenset,
                 bindings: Mapping[str, GitHubAppTokenSource],
                 clock: Optional[Any] = None, **_ignored: Any) -> None:
        if not str(provider_id or "").strip():
            raise ContractViolation("an adapter must name the provider it serves")
        if not environments:
            raise ContractViolation(
                "a credential adapter must declare its environments; absence is not a "
                "wildcard, and an adapter entitled to nowhere would either never issue "
                "or -- read as 'anywhere' -- issue into production")
        if not bindings:
            raise ContractViolation(
                "a GitHub credential adapter must name the tenants it serves; one that "
                "served any tenant would serve every tenant")
        self._provider_id = str(provider_id).strip()
        self._environments = frozenset(environments)
        self._sources = dict(bindings)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def environments(self) -> frozenset:
        return self._environments

    def acquire(self, request: Any, *, expires_at: datetime,
                now: Optional[datetime] = None) -> Any:
        from backend.platform.credentials.broker import IssuedCredential

        if request.environment not in self._environments:
            raise CredentialRefused(CredentialRefusal.ENVIRONMENT_MISMATCH,
                                    "this adapter is not registered for that environment",
                                    correlation_id=request.correlation_id)
        if request.provider != self._provider_id:
            raise CredentialRefused(CredentialRefusal.NO_PROVIDER,
                                    "this adapter serves a different provider",
                                    correlation_id=request.correlation_id)
        if request.on_behalf_of is not None and not request.delegation_authorized:
            raise CredentialRefused(CredentialRefusal.DELEGATION_NOT_AUTHORIZED,
                                    "no authorization sanctioned acting for the named principal",
                                    correlation_id=request.correlation_id)
        source = self._sources.get(request.tenant_id)
        if source is None:
            raise CredentialRefused(CredentialRefusal.NO_PROVIDER,
                                    "this tenant has no GitHub connection for this provider",
                                    correlation_id=request.correlation_id)
        moment = now or self._clock()
        if expires_at <= moment:
            raise CredentialRefused(CredentialRefusal.AUTHORITY_WINDOW_CLOSED,
                                    "no authority window remains for this action",
                                    correlation_id=request.correlation_id)
        token, token_expiry = source.token(correlation_id=request.correlation_id)
        until = min(expires_at, token_expiry)
        from backend.platform.identity import monotonic_ulid

        ref = CredentialRef(tenant_id=request.tenant_id,
                            credential_id=f"github-app-{monotonic_ulid()}")
        material = CredentialMaterial(secret=token, ref=ref, credential_type=CredentialType.BEARER,
                                      expires_at=until, acquired_at=moment,
                                      headers=("Authorization",))
        grant = CredentialGrant(
            ref=ref, credential_type=CredentialType.BEARER, scope=request.scope,
            state=CredentialState.ACTIVE, issued_at=moment, expires_at=until,
            tenant_id=request.tenant_id, action_digest=request.action_digest,
            binding_digest=request.binding_digest, provider=self._provider_id,
            environment=request.environment, fingerprint=material.fingerprint(),
            provider_reference="github-app-installation")
        return IssuedCredential(grant, material)

    def __repr__(self) -> str:
        return (f"<GitHubAppCredentialAdapter provider={self._provider_id} "
                f"tenants={len(self._sources)}>")

    __str__ = __repr__
