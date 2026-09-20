"""The first production credential adapter: HashiCorp Vault, KV v2.

Why this does not wrap ``VaultClient``
----------------------------------------
Phase 4.1 named ``backend/infrastructure/vault/client.py`` as the natural first
production adapter. Reading it in Phase 4.4 says otherwise, and the reasons are
worth stating because "wrap the existing client" was the obvious move:

* It is an ``hvac.Client``, which does its own HTTP with its own TLS handling,
  its own proxy inheritance and its own timeouts. Wrapping it would put a second
  outbound path beside ``TransportBroker`` — no address policy, no DNS pinning,
  no budget — which is precisely what Phase 4.2 exists to prevent, and the
  credential path is the worst place to have it.
* It is a module-level singleton holding one ``VAULT_TOKEN`` from the process
  environment, with no tenant anywhere in the type.
* ``get_secret`` returns ``None`` on **every** exception, so "the secret is
  absent" and "Vault is unreachable" and "the token was rejected" are one
  answer. That is fail-open shaped: a caller cannot tell a missing secret from a
  broken authority.
* ``hvac`` is an optional import that may not be installed at all.

So this speaks Vault's HTTP API directly — one ``GET`` against KV v2 — through
the same broker every provider call goes through. The V1 client is untouched and
keeps serving whatever else uses it.

What this adapter does and does not decide
--------------------------------------------
It **retrieves material**. It does not decide whether the action is authorized:
the invocation gateway settled that before a ``CredentialRequest`` existed, and
the broker verifies afterwards that what came back is bounded by what was asked.

The only judgement here is *which secret path* corresponds to the request, and
that is a pure function of tenant, provider and environment — deliberately not a
lookup table somebody can edit into pointing at another tenant's path.

The tenant is in the path, structurally
-----------------------------------------
    <mount>/data/<prefix>/<tenant>/<environment>/<provider>

Tenant before environment before provider, and the tenant segment comes from
``request.tenant_id`` alone. There is no branch that omits it, no default, and
every segment is validated against a conservative character set — a tenant id
containing ``..`` would otherwise read a path belonging to somebody else.

Nothing is cached
-------------------
No secret, no lease, no token, no response. A credential is fetched for one
invocation and the material's lifetime is bounded by the authority window the
broker computed. Caching would mean holding a secret past the permission for it,
which is the property the whole fabric is arranged around.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from backend.contracts.credential import (
    CredentialRef,
    CredentialState,
    CredentialType,
)
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionEnvironment
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

__all__ = ["VaultCredentialAdapter", "VAULT_DEFAULT_MOUNT"]

log = logging.getLogger(__name__)

VAULT_DEFAULT_MOUNT = "secret"

#: Characters a path segment may contain. Deliberately narrow: everything that
#: reaches a Vault path here is an identifier the platform assigned, so a
#: segment that needs anything outside this set is a segment that is not an
#: identifier.
_SEGMENT_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)

_MAX_SECRET_BYTES = 64 * 1024


class VaultCredentialAdapter:
    """A ``CredentialAdapter`` reading KV v2 through the transport broker."""

    def __init__(
        self,
        *,
        provider_id: str,
        environments: frozenset,
        broker: Any,
        endpoint: Any,
        policy: Any,
        vault_token: CredentialMaterial,
        mount: str = VAULT_DEFAULT_MOUNT,
        path_prefix: str = "cortexprime/providers",
        secret_key: str = "token",
        credential_type: CredentialType = CredentialType.API_KEY,
        clock: Optional[Any] = None,
    ) -> None:
        from backend.platform.transport.broker import TransportBroker
        from backend.platform.transport.endpoint import TransportEndpoint
        from backend.platform.transport.policy import ConnectionPolicy

        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ContractViolation("an adapter must name the provider it serves")
        if not environments:
            raise ContractViolation(
                "a credential adapter must declare its environments; absence is "
                "not a wildcard, and an adapter entitled to nowhere would either "
                "never issue or -- read as 'anywhere' -- issue into production"
            )
        if not isinstance(broker, TransportBroker):
            raise ContractViolation(
                "the Vault adapter reaches Vault through the Phase 4.2 broker "
                "and through nothing else; a second outbound path on the "
                "credential route is the worst place to have one"
            )
        if not isinstance(endpoint, TransportEndpoint):
            raise ContractViolation("endpoint must be a TransportEndpoint")
        if not isinstance(policy, ConnectionPolicy):
            raise ContractViolation("policy must be a ConnectionPolicy")
        if endpoint.is_plaintext and any(
            e is ExecutionEnvironment.PRODUCTION for e in environments
        ):
            # ``VAULT_ADDR`` defaults to http://localhost:8200 in the V1 client.
            # A plaintext Vault in production exposes every secret it serves.
            raise ContractViolation(
                "a production Vault endpoint must be https; plaintext exposes "
                "the Vault token and every secret it returns"
            )
        if not isinstance(vault_token, CredentialMaterial) and not callable(
            getattr(vault_token, "material", None)
        ):
            raise ContractViolation(
                "the Vault token must arrive as CredentialMaterial (or a token "
                "source yielding it, Phase 11.1-K), not as a string read from the "
                "environment; it is a secret and the type is what stops it being "
                "written down"
            )
        for label, value in (("mount", mount), ("secret_key", secret_key)):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")

        self._provider_id = provider_id.strip()
        self._environments = frozenset(environments)
        self._broker = broker
        self._endpoint = endpoint
        self._policy = policy
        self._token = vault_token
        self._mount = mount.strip("/")
        self._prefix = path_prefix.strip("/")
        self._secret_key = secret_key.strip()
        self._type = credential_type
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # -- adapter contract ------------------------------------------------

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def environments(self) -> frozenset:
        return self._environments

    # ------------------------------------------------------------------
    # Acquisition
    # ------------------------------------------------------------------

    def acquire(
        self,
        request: CredentialRequest,
        *,
        expires_at: datetime,
        now: Optional[datetime] = None,
    ) -> IssuedCredential:
        """Read one secret for one action. Every refusal is explicit."""
        # Asserted again at the point of use. A construction-time environment
        # check alone is bypassable by anything that mutates the attribute.
        if request.environment not in self._environments:
            raise CredentialRefused(
                CredentialRefusal.ENVIRONMENT_MISMATCH,
                "this Vault adapter is not registered for that environment",
                correlation_id=request.correlation_id,
            )
        if request.provider != self._provider_id:
            raise CredentialRefused(
                CredentialRefusal.NO_PROVIDER,
                "this Vault adapter serves a different provider",
                correlation_id=request.correlation_id,
            )
        # Delegation, checked here too. The gateway refused it and the broker
        # refused it; a credential adapter is the last component that could
        # release material under a borrowed identity, so it checks as well.
        if request.on_behalf_of is not None and not request.delegation_authorized:
            raise CredentialRefused(
                CredentialRefusal.DELEGATION_NOT_AUTHORIZED,
                "no authorization sanctioned acting for the named principal",
                correlation_id=request.correlation_id,
            )

        moment = now or self._clock()
        if expires_at <= moment:
            raise CredentialRefused(
                CredentialRefusal.AUTHORITY_WINDOW_CLOSED,
                "no authority window remains for this action",
                correlation_id=request.correlation_id,
            )

        path = self._secret_path(request)
        payload, refusal = self._read(path, request, moment)
        if refusal is not None:
            raise refusal

        secret = payload.get(self._secret_key)
        if not isinstance(secret, str) or not secret:
            # A missing key is *not* "no secret configured, proceed": the whole
            # point of the path is that it names one, so an empty answer is a
            # refusal an operator can act on.
            raise CredentialRefused(
                CredentialRefusal.PROVIDER_MALFORMED,
                "the secret at this path carries no usable value",
                correlation_id=request.correlation_id,
            )
        if len(secret.encode("utf-8")) > _MAX_SECRET_BYTES:
            raise CredentialRefused(
                CredentialRefusal.PROVIDER_MALFORMED,
                "the stored value is implausibly large for a credential",
                correlation_id=request.correlation_id,
            )

        # The reference is random and tenant-qualified. Never derived from the
        # secret (which would leak it) and never from the path (which would
        # disclose the layout of the secret store in every audit record).
        from backend.platform.identity import monotonic_ulid

        ref = CredentialRef(
            tenant_id=request.tenant_id,
            credential_id=f"vault-{monotonic_ulid()}",
        )
        material = CredentialMaterial(
            secret=secret,
            ref=ref,
            credential_type=self._type,
            # The authority window, never a lease duration Vault suggests. A
            # credential must not outlive the permission that asked for it, and
            # a provider's opinion about its own lifetime cannot widen that.
            expires_at=expires_at,
            acquired_at=moment,
            headers=("Authorization",),
        )
        grant = CredentialGrant(
            ref=ref,
            credential_type=self._type,
            # Exactly what was requested. Returning anything broader would trip
            # the broker's SCOPE_BROADENED check, and a check that fires on
            # every ordinary issuance is a check that gets turned off.
            scope=request.scope,
            state=CredentialState.ACTIVE,
            issued_at=moment,
            expires_at=expires_at,
            tenant_id=request.tenant_id,
            action_digest=request.action_digest,
            binding_digest=request.binding_digest,
            provider=self._provider_id,
            environment=request.environment,
            fingerprint=material.fingerprint(),
            # A path is not secret, but it describes the layout of the secret
            # store and this field reaches audit. The mount alone is enough to
            # answer "where did this come from".
            provider_reference=f"vault:{self._mount}",
        )
        return IssuedCredential(grant, material)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def validate(self, ref: CredentialRef) -> CredentialState:
        """Vault KV v2 has no per-issuance state to read. Fails closed.

        A static secret read out of a KV store has no identity at Vault, so
        there is nothing to ask about *this* issuance. ``UNKNOWN`` is the honest
        answer and the broker treats it as unusable — which is right: this
        adapter's credentials are validated by their expiry and by the action
        digest they were bound to, not by asking Vault.
        """
        return CredentialState.UNKNOWN

    def revoke(self, ref: CredentialRef, *, reason: str) -> bool:
        """``False``, honestly. A KV secret does not stop working on request.

        Reporting success would leave an operator believing a live secret is
        dead. Revoking a static credential means rotating it in Vault, which is
        an operator action this adapter deliberately cannot perform — a
        credential *reader* that could write would be a much larger blast radius
        than the one it needs.
        """
        return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _platform_token(self, request: CredentialRequest) -> CredentialMaterial:
        """The platform's Vault token: fixed material, or a renewing source's
        current material (Vault Kubernetes auth, Phase 11.1-K). A source that
        cannot produce one refuses the acquisition; it never falls back."""
        if isinstance(self._token, CredentialMaterial):
            return self._token
        return self._token.material(correlation_id=request.correlation_id)

    def _secret_path(self, request: CredentialRequest) -> str:
        """``<prefix>/<tenant>/<environment>/<provider>``. Tenant first, always.

        Every segment is validated rather than trusted. A tenant id containing
        ``..`` or ``/`` would otherwise read a path belonging to another tenant,
        and this is the one string in the credential path that is derived from
        data rather than from configuration.
        """
        segments = [
            request.tenant_id,
            request.environment.value,
            self._provider_id,
        ]
        for segment in segments:
            if not segment or any(ch not in _SEGMENT_CHARS for ch in segment):
                raise CredentialRefused(
                    CredentialRefusal.REQUEST_INCOMPLETE,
                    "an identifier in this request is not usable as a secret "
                    "path segment",
                    correlation_id=request.correlation_id,
                )
        return "/".join([self._prefix, *segments])

    def _read(
        self, path: str, request: CredentialRequest, now: datetime
    ) -> tuple:
        """One GET through the broker. Returns ``(payload, refusal)``."""
        from dataclasses import replace

        from backend.platform.transport.request import (
            DeliveryState,
            TransportRefused,
            TransportRequest,
        )

        remaining = max(1.0, (request.effective_expiry(now) - now).total_seconds())
        try:
            platform_token = self._platform_token(request)
        except CredentialRefused as refused:
            # The platform's own Vault identity could not be established (a
            # Kubernetes-auth login refused). That refusal is the answer.
            return {}, refused
        endpoint = replace(
            self._endpoint,
            path=f"/v1/{self._mount}/data/{path}",
            query="",
        )
        try:
            transport_request = TransportRequest(
                endpoint=endpoint,
                policy=self._policy,
                tenant_id=request.tenant_id,
                # Vault is reached as the platform, not as the tenant's user:
                # the Vault token is CortexPrime's, and presenting a tenant
                # principal here would suggest Vault authenticated them.
                principal=PrincipalRef(
                    principal_id="cortexprime.credential-fabric",
                    kind=PrincipalKind.PLATFORM,
                ),
                method="GET",
                headers={"x-vault-request": "true"},
                execution_id=request.execution_id,
                node_id=request.node_id,
                attempt_id=request.attempt_id,
                correlation_id=request.correlation_id,
                authority_seconds_remaining=remaining,
                # The Vault token itself, handed to transport for the moment of
                # use exactly as a provider credential is.
                credential=platform_token,
            )
        except Exception as exc:  # noqa: BLE001
            return {}, CredentialRefused(
                CredentialRefusal.PROVIDER_UNAVAILABLE,
                f"the Vault request could not be formed ({type(exc).__name__})",
                correlation_id=request.correlation_id,
            )

        try:
            outcome = self._broker.dial(transport_request)
        except TransportRefused as refused:
            return {}, CredentialRefused(
                CredentialRefusal.PROVIDER_UNAVAILABLE,
                f"Vault could not be reached ({refused.reason_code})",
                correlation_id=request.correlation_id,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("vault read failed: %s", safe_exception_text(exc))
            return {}, CredentialRefused(
                CredentialRefusal.PROVIDER_UNAVAILABLE,
                f"Vault could not be reached ({type(exc).__name__})",
                correlation_id=request.correlation_id,
            )

        if outcome.delivery is not DeliveryState.DELIVERED:
            return {}, CredentialRefused(
                CredentialRefusal.PROVIDER_UNAVAILABLE,
                "the Vault read did not complete",
                correlation_id=request.correlation_id,
            )
        status = outcome.status_code
        if status in (401, 403):
            # Vault rejected *our* token. Not the tenant's problem and not a
            # missing secret: an operator needs to know these are different.
            return {}, CredentialRefused(
                CredentialRefusal.PROVIDER_REFUSED,
                "Vault refused the platform's own credential",
                correlation_id=request.correlation_id,
            )
        if status == 404:
            return {}, CredentialRefused(
                CredentialRefusal.NO_PROVIDER,
                "no credential is stored for this tenant, environment and "
                "provider",
                correlation_id=request.correlation_id,
            )
        if status != 200:
            return {}, CredentialRefused(
                CredentialRefusal.PROVIDER_UNAVAILABLE,
                f"Vault answered {status}",
                correlation_id=request.correlation_id,
            )
        if outcome.truncated or outcome.body is None:
            return {}, CredentialRefused(
                CredentialRefusal.PROVIDER_MALFORMED,
                "the Vault response was truncated or empty",
                correlation_id=request.correlation_id,
            )
        try:
            document = json.loads(outcome.body.decode("utf-8"))
            payload = document["data"]["data"]
        except Exception:  # noqa: BLE001 - an unreadable answer is not a secret
            return {}, CredentialRefused(
                CredentialRefusal.PROVIDER_MALFORMED,
                "the Vault response was not a KV v2 secret document",
                correlation_id=request.correlation_id,
            )
        if not isinstance(payload, Mapping):
            return {}, CredentialRefused(
                CredentialRefusal.PROVIDER_MALFORMED,
                "the Vault secret is not an object",
                correlation_id=request.correlation_id,
            )
        return dict(payload), None

    def __repr__(self) -> str:
        # Never the token, never the path prefix beyond the mount.
        return (
            f"<VaultCredentialAdapter provider={self._provider_id} "
            f"mount={self._mount} "
            f"environments={sorted(e.value for e in self._environments)}>"
        )
