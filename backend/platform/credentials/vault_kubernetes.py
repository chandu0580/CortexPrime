"""Production Kubernetes credentials from Vault: dynamic, short-lived, per acquisition.

Phase 11.1-K. The connector reality audit found every working provider on the
``DevelopmentCredentialProvider`` (which refuses production) and the Vault
adapter never exercised. Kubernetes made the gap concrete: its operators were
minting ServiceAccount tokens by hand every two hours.

Vault is the platform's stated production credential architecture
(``ProductionConnectivityConfig`` demands it), so this does not introduce a
second secret system. It uses the part of Vault built for exactly this:

* **Vault's Kubernetes secrets engine** mints a Kubernetes TokenRequest token
  for a named, namespace-confined ServiceAccount, on every acquisition, with a
  short TTL. There is no long-lived Kubernetes secret anywhere: rotation is not
  a job somebody runs, it is how every credential is made.
* **Vault's Kubernetes auth method** gives CortexPrime its own Vault token from
  the pod's projected ServiceAccount token (which the kubelet rotates). No
  static ``VAULT_TOKEN`` is needed in the cluster; the Vault token is renewed
  by logging in again before it lapses.

Both calls go through the ``TransportBroker`` -- the one outbound path, with
address pinning and TLS verification -- exactly like the KV adapter.

Tenancy, structurally
-----------------------
The adapter is constructed with a mapping ``tenant -> (namespace, Vault role)``
from deployment configuration. A request for a tenant not in the mapping is
refused; there is no default role. The Vault role itself pins the ServiceAccount
and the namespace, and that ServiceAccount's RBAC is confined to the namespace,
so a credential minted for tenant A cannot act in tenant B's namespace even if
every platform-side check were bypassed.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from backend.contracts.credential import CredentialRef, CredentialState, CredentialType
from backend.contracts.errors import ContractViolation
from backend.contracts.identity import PrincipalKind, PrincipalRef
from backend.platform.credentials.broker import IssuedCredential
from backend.platform.credentials.material import CredentialMaterial
from backend.platform.credentials.redaction import safe_exception_text
from backend.platform.credentials.request import (
    CredentialGrant,
    CredentialRefusal,
    CredentialRefused,
    CredentialRequest,
)
from backend.platform.credentials.vault import VaultCredentialAdapter

__all__ = [
    "VaultKubernetesAuth",
    "VaultKubernetesCredentialAdapter",
    "PROJECTED_TOKEN_PATH",
]

log = logging.getLogger(__name__)

#: Where the kubelet mounts (and rotates) a pod's own ServiceAccount token.
PROJECTED_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"

_PLATFORM_TENANT = "cortexprime-platform"
_PLATFORM_PRINCIPAL = PrincipalRef(principal_id="cortexprime.credential-fabric",
                                   kind=PrincipalKind.PLATFORM)
_SEGMENT = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


def _segment(value: str, label: str) -> str:
    value = str(value or "").strip()
    if not value or any(ch not in _SEGMENT for ch in value):
        raise ContractViolation(f"{label} must be a plain identifier")
    return value


def _vault_call(broker: Any, endpoint: Any, policy: Any, *, method: str, path: str,
                body: Optional[dict], credential: Optional[CredentialMaterial],
                tenant_id: str, correlation_id: Optional[str], seconds: float) -> tuple:
    """One Vault request through the transport broker. Returns ``(status, document)``;
    raises ``CredentialRefused`` for anything that is not a readable answer."""
    from dataclasses import replace

    from backend.platform.transport.request import (
        DeliveryState,
        TransportRefused,
        TransportRequest,
    )

    try:
        request = TransportRequest(
            endpoint=replace(endpoint, path=path, query=""), policy=policy,
            tenant_id=tenant_id, principal=_PLATFORM_PRINCIPAL, method=method,
            headers={"x-vault-request": "true", "content-type": "application/json"},
            body=json.dumps(body).encode("utf-8") if body is not None else None,
            correlation_id=correlation_id, authority_seconds_remaining=max(1.0, seconds),
            credential=credential)
        outcome = broker.dial(request)
    except TransportRefused as refused:
        raise CredentialRefused(CredentialRefusal.PROVIDER_UNAVAILABLE,
                                f"Vault could not be reached ({refused.reason_code})",
                                correlation_id=correlation_id) from refused
    except CredentialRefused:
        raise
    except Exception as exc:  # noqa: BLE001
        log.warning("vault call failed: %s", safe_exception_text(exc))
        raise CredentialRefused(CredentialRefusal.PROVIDER_UNAVAILABLE,
                                f"Vault could not be reached ({type(exc).__name__})",
                                correlation_id=correlation_id) from exc
    if outcome.delivery is not DeliveryState.DELIVERED:
        raise CredentialRefused(CredentialRefusal.PROVIDER_UNAVAILABLE,
                                "the Vault request did not complete",
                                correlation_id=correlation_id)
    document: dict = {}
    if outcome.body and not outcome.truncated:
        try:
            document = json.loads(outcome.body.decode("utf-8"))
        except Exception:  # noqa: BLE001 - judged by status below
            document = {}
    return outcome.status_code, document


class VaultKubernetesAuth:
    """CortexPrime's own Vault token via Vault's Kubernetes auth method.

    Logs in with the pod's projected ServiceAccount token (read from the file
    every time, because the kubelet rotates it) and caches the resulting Vault
    token until ``renew_fraction`` of its lease has passed, then logs in again.
    The cached token never leaves this object except as ``CredentialMaterial``.
    """

    def __init__(self, *, broker: Any, endpoint: Any, policy: Any, role: str,
                 mount: str = "kubernetes", jwt_path: str = PROJECTED_TOKEN_PATH,
                 renew_fraction: float = 0.6, clock: Optional[Any] = None) -> None:
        self._broker = broker
        self._endpoint = endpoint
        self._policy = policy
        self._role = _segment(role, "the Vault auth role")
        self._mount = _segment(mount, "the Vault auth mount")
        self._jwt_path = jwt_path
        self._renew_fraction = min(0.9, max(0.1, renew_fraction))
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._cached: Optional[CredentialMaterial] = None
        self._renew_at: Optional[datetime] = None
        self.last_login_at: Optional[datetime] = None

    def invalidate(self, stale: Optional[CredentialMaterial] = None) -> bool:
        """Forget the cached login, but only if it is still ``stale``.

        Phase 11.1-K: Vault restarted (or revoked the token) and every request
        presented the dead login for the rest of its cached lifetime -- about 36
        minutes -- although a fresh login would have succeeded at once. The
        comparison keeps a concurrent caller from discarding a login another
        thread has just renewed.
        """
        with self._lock:
            if self._cached is None or (stale is not None and self._cached is not stale):
                return False
            self._cached, self._renew_at = None, None
            return True

    def material(self, *, correlation_id: Optional[str] = None) -> CredentialMaterial:
        with self._lock:
            now = self._clock()
            if self._cached is not None and self._renew_at is not None and now < self._renew_at:
                return self._cached
            try:
                with open(self._jwt_path, encoding="utf-8") as handle:
                    jwt = handle.read().strip()
            except OSError as exc:
                raise CredentialRefused(
                    CredentialRefusal.NO_PROVIDER,
                    "this process has no projected ServiceAccount token to log in to Vault with",
                    correlation_id=correlation_id) from exc
            status, document = _vault_call(
                self._broker, self._endpoint, self._policy, method="POST",
                path=f"/v1/auth/{self._mount}/login", body={"role": self._role, "jwt": jwt},
                credential=None, tenant_id=_PLATFORM_TENANT, correlation_id=correlation_id,
                seconds=30.0)
            del jwt
            if status in (400, 401, 403):
                raise CredentialRefused(
                    CredentialRefusal.PROVIDER_REFUSED,
                    "Vault refused this platform's Kubernetes identity (auth role or binding)",
                    correlation_id=correlation_id)
            auth = document.get("auth") if isinstance(document, Mapping) else None
            token = auth.get("client_token") if isinstance(auth, Mapping) else None
            lease = auth.get("lease_duration") if isinstance(auth, Mapping) else None
            if status != 200 or not isinstance(token, str) or not token:
                raise CredentialRefused(CredentialRefusal.PROVIDER_MALFORMED,
                                        f"Vault login answered {status} without a token",
                                        correlation_id=correlation_id)
            seconds = int(lease) if isinstance(lease, int) and lease > 0 else 300
            self._cached = CredentialMaterial(
                secret=token,
                ref=CredentialRef(tenant_id=_PLATFORM_TENANT, credential_id="vault-k8s-auth"),
                credential_type=CredentialType.BEARER, expires_at=now + timedelta(seconds=seconds),
                acquired_at=now, headers=("Authorization",))
            self._renew_at = now + timedelta(seconds=seconds * self._renew_fraction)
            self.last_login_at = now
            return self._cached


class VaultKubernetesCredentialAdapter(VaultCredentialAdapter):
    """A ``CredentialAdapter`` issuing Kubernetes ServiceAccount tokens from Vault.

    ``bindings`` maps tenant id to ``(namespace, vault_role)`` -- deployment
    configuration, never request input. Each acquisition asks Vault's Kubernetes
    secrets engine for a fresh token (``POST <mount>/creds/<role>``) whose
    lifetime is the shorter of the authority window and the Vault lease.
    """

    def __init__(self, *, bindings: Mapping[str, tuple], kubernetes_mount: str = "kubernetes",
                 token_ttl_seconds: int = 600, **kwargs: Any) -> None:
        kwargs.setdefault("credential_type", CredentialType.BEARER)
        super().__init__(**kwargs)
        if not bindings:
            raise ContractViolation(
                "a Kubernetes credential adapter must name the tenants it serves; "
                "an adapter that served any tenant would serve every tenant")
        self._bindings = {
            _segment(tenant, "a tenant id"): (_segment(ns, "a namespace"), _segment(role, "a Vault role"))
            for tenant, (ns, role) in dict(bindings).items()}
        self._k8s_mount = _segment(kubernetes_mount, "the Vault Kubernetes mount")
        # Kubernetes refuses a TokenRequest shorter than 10 minutes.
        self._ttl = max(600, int(token_ttl_seconds))

    def acquire(self, request: CredentialRequest, *, expires_at: datetime,
                now: Optional[datetime] = None) -> IssuedCredential:
        if request.environment not in self.environments:
            raise CredentialRefused(CredentialRefusal.ENVIRONMENT_MISMATCH,
                                    "this adapter is not registered for that environment",
                                    correlation_id=request.correlation_id)
        if request.provider != self.provider_id:
            raise CredentialRefused(CredentialRefusal.NO_PROVIDER,
                                    "this adapter serves a different provider",
                                    correlation_id=request.correlation_id)
        if request.on_behalf_of is not None and not request.delegation_authorized:
            raise CredentialRefused(CredentialRefusal.DELEGATION_NOT_AUTHORIZED,
                                    "no authorization sanctioned acting for the named principal",
                                    correlation_id=request.correlation_id)
        binding = self._bindings.get(request.tenant_id)
        if binding is None:
            # The structural tenant boundary: no binding, no credential.
            raise CredentialRefused(CredentialRefusal.NO_PROVIDER,
                                    "this tenant has no Kubernetes connection for this provider",
                                    correlation_id=request.correlation_id)
        namespace, role = binding
        moment = now or self._clock()
        if expires_at <= moment:
            raise CredentialRefused(CredentialRefusal.AUTHORITY_WINDOW_CLOSED,
                                    "no authority window remains for this action",
                                    correlation_id=request.correlation_id)
        remaining = (request.effective_expiry(moment) - moment).total_seconds()

        def mint(platform_token: CredentialMaterial) -> tuple:
            return _vault_call(
                self._broker, self._endpoint, self._policy, method="POST",
                path=f"/v1/{self._k8s_mount}/creds/{role}",
                body={"kubernetes_namespace": namespace, "ttl": f"{self._ttl}s"},
                credential=platform_token, tenant_id=request.tenant_id,
                correlation_id=request.correlation_id, seconds=remaining)

        platform_token = self._platform_token(request)
        status, document = mint(platform_token)
        invalidate = getattr(self._token, "invalidate", None)
        if status in (401, 403) and callable(invalidate) and invalidate(platform_token):
            # A refused LOGIN (restarted Vault, revoked token) is repaired by one
            # fresh login; a refused ROLE refuses again and is reported below. A
            # refused mint issued nothing, so asking once more duplicates nothing.
            status, document = mint(self._platform_token(request))
        if status in (401, 403):
            raise CredentialRefused(CredentialRefusal.PROVIDER_REFUSED,
                                    "Vault refused the platform's credential for this role",
                                    correlation_id=request.correlation_id)
        if status in (400, 404):
            raise CredentialRefused(CredentialRefusal.NO_PROVIDER,
                                    "Vault has no Kubernetes role for this tenant and provider "
                                    "(or it does not allow this namespace)",
                                    correlation_id=request.correlation_id)
        data = document.get("data") if isinstance(document, Mapping) else None
        token = data.get("service_account_token") if isinstance(data, Mapping) else None
        lease = document.get("lease_duration") if isinstance(document, Mapping) else None
        if status != 200 or not isinstance(token, str) or not token:
            raise CredentialRefused(CredentialRefusal.PROVIDER_MALFORMED,
                                    f"Vault answered {status} without a ServiceAccount token",
                                    correlation_id=request.correlation_id)
        lifetime = moment + timedelta(seconds=int(lease)) if isinstance(lease, int) and lease > 0 \
            else moment + timedelta(seconds=self._ttl)
        # The credential never outlives the permission that asked for it.
        until = min(expires_at, lifetime)
        from backend.platform.identity import monotonic_ulid

        ref = CredentialRef(tenant_id=request.tenant_id, credential_id=f"vault-k8s-{monotonic_ulid()}")
        material = CredentialMaterial(secret=token, ref=ref, credential_type=CredentialType.BEARER,
                                      expires_at=until, acquired_at=moment,
                                      headers=("Authorization",))
        grant = CredentialGrant(
            ref=ref, credential_type=CredentialType.BEARER, scope=request.scope,
            state=CredentialState.ACTIVE, issued_at=moment, expires_at=until,
            tenant_id=request.tenant_id, action_digest=request.action_digest,
            binding_digest=request.binding_digest, provider=self.provider_id,
            environment=request.environment, fingerprint=material.fingerprint(),
            provider_reference=f"vault-kubernetes:{self._k8s_mount}")
        return IssuedCredential(grant, material)

    def __repr__(self) -> str:
        return (f"<VaultKubernetesCredentialAdapter provider={self.provider_id} "
                f"tenants={len(self._bindings)} mount={self._k8s_mount}>")
