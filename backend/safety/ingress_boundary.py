"""The ingestion trust boundary — Phase 11.1 (ADR-121).

Where untrusted data becomes a trusted *event* without becoming a trusted
*instruction*.

    UNTRUSTED EXTERNAL WORLD
            |
            v
    authentication  -- a verified access token (``require_user``) for API
                       ingestion, or a provider secret for a webhook
    tenant          -- from the verified token, or the deployment's declared
                       V1 tenant for a webhook; never from the payload
    body bound      -- ``CORTEXPRIME_INGRESS_MAX_BODY_BYTES`` (1 MiB default)
    schema          -- the route's pydantic model; the payload must be a JSON
                       object, and it is DATA
    identity        -- a canonical event identity (source, type, id, digest)
    audit           -- every accept and reject, without the payload
            |
            v
    TRUSTED EVENT (an ``IngressEnvelope``)

Three things this module does **not** do, on purpose
------------------------------------------------------
* It does not read a tenant from the request body or the query string. The
  Phase 10.0 census found three V1 routes doing that; a caller-chosen tenant is
  the same as none.
* It does not claim exactly-once. Delivery is at-least-once: the GitHub and
  GitLab receivers deduplicate by provider delivery id within their own
  file-backed history; token-authenticated ingestion carries a canonical
  identity so a downstream consumer *can* deduplicate, and this phase records
  that no V1 consumer does.
* It does not sanitise payloads into instructions. An accepted payload is
  ``trust="untrusted_external"`` for its whole life. The only things that may
  act on it are the V1 correlators and dashboards (advice), never execution:
  every V1 execution surface sits behind ``guard_legacy_execution``.

The webhook rule
------------------
Signature verification happens **before** the body is parsed, before replay
detection, and before anything is recorded. An unverifiable delivery is refused
with 401; a deployment with no secret configured refuses with 503 rather than
accepting "unverified" deliveries as it did before this phase. Both refusals
are audited with the delivery id and never with the payload or the secret.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from fastapi import Depends, HTTPException, Request, status

from backend.auth.dependencies import require_user
from backend.safety.auth_perimeter import declared_v1_tenant, v1_tenant_verdict

log = logging.getLogger(__name__)

__all__ = [
    "INGRESS_MAX_BODY_ENV",
    "TRUST_UNTRUSTED_EXTERNAL",
    "IngressPrincipal",
    "IngressEnvelope",
    "ingress_max_body_bytes",
    "require_ingest_principal",
    "require_governed_ingest_principal",
    "bound_body",
    "audit_ingress",
    "verify_github_delivery",
    "verify_gitlab_delivery",
]

INGRESS_MAX_BODY_ENV = "CORTEXPRIME_INGRESS_MAX_BODY_BYTES"
_DEFAULT_MAX_BODY = 1_048_576  # 1 MiB; OTLP batches and alert groups fit comfortably

#: The trust class every externally supplied payload carries. There is no other
#: value: nothing that arrives through this boundary is ever promoted.
TRUST_UNTRUSTED_EXTERNAL = "untrusted_external"

#: Webhook tenant label when the deployment has not declared its V1 tenant.
#: Honest rather than invented: a webhook carries no tenant, and this phase does
#: not manufacture a mapping (ADR-121, "webhook tenant").
_TENANT_UNBOUND = "single-tenant-unbound"


def ingress_max_body_bytes() -> int:
    raw = os.environ.get(INGRESS_MAX_BODY_ENV, "").strip()
    try:
        value = int(raw) if raw else _DEFAULT_MAX_BODY
    except ValueError:
        value = _DEFAULT_MAX_BODY
    return value if value > 0 else _DEFAULT_MAX_BODY


@dataclass(frozen=True)
class IngressPrincipal:
    """Who delivered an event, established by the boundary and nothing else."""

    principal_id: str
    tenant_id: Optional[str]
    auth_kind: str  # "jwt" | "github_hmac" | "gitlab_token"
    source: str

    def to_dict(self) -> dict:
        return {
            "principal_id": self.principal_id,
            "tenant_id": self.tenant_id,
            "auth_kind": self.auth_kind,
            "source": self.source,
        }


@dataclass(frozen=True)
class IngressEnvelope:
    """A trusted event: what arrived, from whom, for which tenant, and its identity.

    ``identity`` is the canonical event identity -- a digest over
    ``(source, event_type, event_id)`` -- so two deliveries of the same event
    compare equal wherever a consumer chooses to deduplicate. ``payload_digest``
    is over the canonical JSON of the payload, so a *modified* redelivery is
    distinguishable from a repeated one.
    """

    identity: str
    source: str
    event_type: str
    event_id: str
    tenant_id: Optional[str]
    principal_id: str
    auth_kind: str
    received_at: str
    payload_digest: str
    payload_bytes: int
    trust: str = TRUST_UNTRUSTED_EXTERNAL

    @classmethod
    def build(
        cls,
        *,
        source: str,
        event_type: str,
        payload: Any,
        principal: IngressPrincipal,
        event_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> "IngressEnvelope":
        canonical = _canonical_bytes(payload)
        payload_digest = hashlib.sha256(canonical).hexdigest()
        resolved_id = (event_id or "").strip() or payload_digest[:32]
        identity = hashlib.sha256(
            f"{source}|{event_type}|{resolved_id}".encode("utf-8")
        ).hexdigest()
        stamp = (now or datetime.now(timezone.utc)).isoformat()
        return cls(
            identity=identity,
            source=source,
            event_type=event_type,
            event_id=resolved_id,
            tenant_id=principal.tenant_id,
            principal_id=principal.principal_id,
            auth_kind=principal.auth_kind,
            received_at=stamp,
            payload_digest=payload_digest,
            payload_bytes=len(canonical),
        )

    def to_dict(self) -> dict:
        return {
            "identity": self.identity,
            "source": self.source,
            "event_type": self.event_type,
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "principal_id": self.principal_id,
            "auth_kind": self.auth_kind,
            "received_at": self.received_at,
            "payload_digest": self.payload_digest,
            "payload_bytes": self.payload_bytes,
            "trust": self.trust,
            "delivery": "at-least-once",
        }


def _canonical_bytes(payload: Any) -> bytes:
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                          default=str).encode("utf-8")
    except (TypeError, ValueError):
        return repr(payload).encode("utf-8")


def _request_id(request: Request) -> Optional[str]:
    return getattr(request.state, "request_id", None)


def _client_host(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def audit_ingress(
    request: Request,
    *,
    outcome: str,
    reason: str,
    source: str,
    principal: Optional[IngressPrincipal] = None,
    envelope: Optional[IngressEnvelope] = None,
    event_id: Optional[str] = None,
) -> None:
    """Record one boundary decision. Never the payload, never a secret.

    Persistence is the audit logger's (best-effort to PostgreSQL, cached in
    process). A persistence failure does not reverse the decision: rejections
    are enforced before this is called, and an accepted V1 ingestion reaches
    only advisory stores. That limitation is stated in ADR-121 rather than
    hidden.
    """
    assert outcome in ("accepted", "rejected")
    try:
        from backend.safety.audit_logger import audit_logger

        # Fire-and-forget, like every other middleware-level audit in this
        # codebase: the entry is cached in process immediately and persisted
        # to PostgreSQL asynchronously. Awaiting persistence here would let an
        # unreachable database hold every ingestion request for the driver's
        # connect timeout, which is an availability hole, not an audit.

        resolved_event = (envelope.event_id if envelope else event_id) or "none"
        metadata = {
            "method": request.method,
            "path": request.url.path,
            "source": source,
            "tenant_id": (envelope.tenant_id if envelope else
                          principal.tenant_id if principal else None),
            "auth_kind": (envelope.auth_kind if envelope else
                          principal.auth_kind if principal else "none"),
            "event_id": resolved_event,
            "client": _client_host(request),
            "reason": reason,
        }
        if envelope is not None:
            metadata["identity"] = envelope.identity
            metadata["event_type"] = envelope.event_type
            metadata["payload_digest"] = envelope.payload_digest
            metadata["payload_bytes"] = envelope.payload_bytes
        audit_logger.log(
            execution_id=f"ingress:{resolved_event}",
            agent="ingress_boundary",
            user=(principal.principal_id if principal else "anonymous"),
            action=f"ingress.{outcome}",
            target=request.url.path,
            risk_level="low" if outcome == "accepted" else "medium",
            outcome="allowed" if outcome == "accepted" else "blocked",
            reason=reason,
            request_id=_request_id(request),
            metadata=metadata,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("ingress audit write failed (decision unchanged): %s", exc)


def _content_length(request: Request) -> Optional[int]:
    raw = request.headers.get("content-length")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def _refuse(request: Request, *, status_code: int, reason: str, source: str,
                  principal: Optional[IngressPrincipal] = None,
                  event_id: Optional[str] = None,
                  headers: Optional[dict] = None) -> HTTPException:
    await audit_ingress(request, outcome="rejected", reason=reason, source=source,
                        principal=principal, event_id=event_id)
    return HTTPException(status_code=status_code, detail=reason, headers=headers)


async def require_ingest_principal(
    request: Request,
    claims: dict = Depends(require_user),
) -> IngressPrincipal:
    """The identity behind a token-authenticated ingestion call.

    ``require_user`` has verified the signature, the revocation list and (when
    the token names one) that the tenant exists and is live. This dependency
    adds the V1 tenant fence -- so a router mounted without the perimeter (tests,
    a future split) still refuses a foreign tenant -- and the body bound.
    """
    source = request.url.path
    principal = IngressPrincipal(
        principal_id=str(claims.get("sub") or ""),
        tenant_id=(str(claims.get("tenant_id")).strip() if claims.get("tenant_id") else None),
        auth_kind="jwt",
        source=source,
    )
    if not principal.principal_id:
        raise await _refuse(request, status_code=status.HTTP_403_FORBIDDEN,
                            reason="the authenticated identity names no principal",
                            source=source)

    admitted, reason = v1_tenant_verdict(principal.tenant_id)
    if not admitted:
        raise await _refuse(request, status_code=status.HTTP_403_FORBIDDEN,
                            reason=reason, source=source, principal=principal)

    declared = _content_length(request)
    limit = ingress_max_body_bytes()
    if declared is not None and declared > limit:
        raise await _refuse(
            request, status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            reason=f"payload of {declared} bytes exceeds the ingestion bound of {limit} bytes",
            source=source, principal=principal)
    return principal


async def require_governed_ingest_principal(
    request: Request,
    claims: dict = Depends(require_user),
) -> IngressPrincipal:
    """The identity behind ingestion into a GOVERNED, tenant-scoped ledger.

    Phase 11.2. Differs from :func:`require_ingest_principal` in exactly two
    ways, both because the destination is the World Plane rather than a V1
    store: the V1 single-tenant fence does not apply (the ledger is scoped by
    tenant row, so a second tenant is isolated rather than refused), and a
    token WITHOUT a tenant is refused, because an observation without a
    tenant cannot exist. Everything else -- verified token, live tenant,
    body bound, audit -- is the same boundary.
    """
    source = request.url.path
    principal = IngressPrincipal(
        principal_id=str(claims.get("sub") or ""),
        tenant_id=(str(claims.get("tenant_id")).strip() if claims.get("tenant_id") else None),
        auth_kind="jwt",
        source=source,
    )
    if not principal.principal_id:
        raise await _refuse(request, status_code=status.HTTP_403_FORBIDDEN,
                            reason="the authenticated identity names no principal",
                            source=source)
    if not principal.tenant_id:
        raise await _refuse(request, status_code=status.HTTP_403_FORBIDDEN,
                            reason="governed signal ingestion requires a tenant-bound identity; "
                                   "this token carries no tenant",
                            source=source, principal=principal)
    declared = _content_length(request)
    limit = ingress_max_body_bytes()
    if declared is not None and declared > limit:
        raise await _refuse(
            request, status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            reason=f"payload of {declared} bytes exceeds the ingestion bound of {limit} bytes",
            source=source, principal=principal)
    return principal


async def bound_body(request: Request, *, source: str,
                     principal: Optional[IngressPrincipal] = None) -> bytes:
    """Read a raw body under the ingestion bound. For routes that parse bytes."""
    body = await request.body()
    limit = ingress_max_body_bytes()
    if len(body) > limit:
        raise await _refuse(
            request, status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            reason=f"payload of {len(body)} bytes exceeds the ingestion bound of {limit} bytes",
            source=source, principal=principal)
    return body


def _webhook_tenant() -> str:
    return declared_v1_tenant() or _TENANT_UNBOUND


def _header(headers: Mapping[str, str], name: str) -> str:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return ""


async def verify_github_delivery(request: Request, body: bytes) -> IngressPrincipal:
    """Verify a GitHub delivery **before** anything else happens to it.

    * no secret configured  -> 503 (the deployment cannot verify; it must not guess)
    * missing/invalid HMAC  -> 401 (audited with the delivery id)
    * verified              -> the webhook principal, bound to the declared V1 tenant
    """
    from backend.services.enterprise_github_integration import (
        GITHUB_WEBHOOK_SECRET_ENV,
        verify_github_signature,
    )

    source = "github.webhook"
    delivery_id = _header(request.headers, "X-GitHub-Delivery") or None
    secret = os.getenv(GITHUB_WEBHOOK_SECRET_ENV, "")
    if not secret:
        raise await _refuse(
            request, status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            reason=f"GitHub webhook secret is not configured ({GITHUB_WEBHOOK_SECRET_ENV}); "
                   "unverifiable deliveries are refused",
            source=source, event_id=delivery_id)
    signature = _header(request.headers, "X-Hub-Signature-256")
    if not verify_github_signature(body, signature, secret):
        raise await _refuse(
            request, status_code=status.HTTP_401_UNAUTHORIZED,
            reason="GitHub webhook signature missing or invalid",
            source=source, event_id=delivery_id)
    return IngressPrincipal(
        principal_id="github-webhook",
        tenant_id=_webhook_tenant(),
        auth_kind="github_hmac",
        source=source,
    )


async def verify_gitlab_delivery(request: Request) -> IngressPrincipal:
    """Verify a GitLab delivery by its shared token, with the same three outcomes."""
    from backend.services.enterprise_gitlab_integration import (
        GITLAB_WEBHOOK_SECRET_ENV,
        verify_gitlab_token,
    )

    source = "gitlab.webhook"
    delivery_id = _header(request.headers, "X-Gitlab-Event-UUID") or None
    secret = os.getenv(GITLAB_WEBHOOK_SECRET_ENV, "")
    if not secret:
        raise await _refuse(
            request, status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            reason=f"GitLab webhook token is not configured ({GITLAB_WEBHOOK_SECRET_ENV}); "
                   "unverifiable deliveries are refused",
            source=source, event_id=delivery_id)
    token = _header(request.headers, "X-Gitlab-Token")
    if not verify_gitlab_token(token, secret):
        raise await _refuse(
            request, status_code=status.HTTP_401_UNAUTHORIZED,
            reason="GitLab webhook token missing or invalid",
            source=source, event_id=delivery_id)
    return IngressPrincipal(
        principal_id="gitlab-webhook",
        tenant_id=_webhook_tenant(),
        auth_kind="gitlab_token",
        source=source,
    )
