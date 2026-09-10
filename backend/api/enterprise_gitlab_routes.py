"""
Enterprise GitLab CI Integration — REST API.

Deliberately narrow — see enterprise_gitlab_integration.py's module
docstring. Just enough surface to receive real GitLab deployment webhooks
and feed them into the same deploy-regression pipeline GitHub uses.

Endpoints:
  POST  /api/gitlab/webhook   — Receive and verify a GitLab webhook
  GET   /api/gitlab/webhooks  — List webhook delivery history

Phase 11.1 (ADR-121): two routers on one prefix. The webhook authenticates
by the shared ``X-Gitlab-Token`` (verified by the ingress boundary before the
body is parsed; 401 when wrong, 503 when the deployment has no token
configured). The delivery-history read requires a verified access token.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.auth.dependencies import require_user
from backend.safety.ingress_boundary import (
    IngressEnvelope,
    audit_ingress,
    bound_body,
    verify_gitlab_delivery,
)
from backend.services.enterprise_gitlab_integration import (
    GITLAB_WEBHOOK_SECRET_ENV,
    gitlab_webhook_receiver,
)

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/gitlab",
    tags=["Enterprise GitLab Integration"],
    dependencies=[Depends(require_user)],
)
webhook_router = APIRouter(prefix="/api/gitlab", tags=["Enterprise GitLab Integration"])


@webhook_router.post("/webhook")
async def receive_webhook(request: Request):
    principal = await verify_gitlab_delivery(request)
    body = await bound_body(request, source="gitlab.webhook", principal=principal)
    headers = dict(request.headers)
    # Server-side configuration only — see module docstring for why
    # this is never read from the incoming request.
    secret = os.getenv(GITLAB_WEBHOOK_SECRET_ENV, "")
    try:
        result = await gitlab_webhook_receiver.receive(body, headers, secret)
    except Exception as exc:
        await audit_ingress(request, outcome="rejected", source="gitlab.webhook",
                            principal=principal,
                            event_id=headers.get("x-gitlab-event-uuid"),
                            reason=f"delivery could not be processed: {type(exc).__name__}")
        raise HTTPException(502, "Webhook processing failed")
    envelope = IngressEnvelope.build(
        source="gitlab.webhook",
        event_type=str(result.get("event_type") or headers.get("x-gitlab-event") or "unknown"),
        payload=result.get("payload", {}),
        principal=principal,
        event_id=str(result.get("delivery_id") or ""),
    )
    await audit_ingress(request, outcome="accepted", source="gitlab.webhook",
                        principal=principal, envelope=envelope,
                        reason=str(result.get("status") or "verified"))
    result["ingress"] = envelope.to_dict()
    return result


@router.get("/webhooks")
async def list_webhooks(limit: int = Query(20, ge=1, le=100)):
    try:
        return {"webhooks": gitlab_webhook_receiver.get_recent_deliveries(limit)}
    except Exception as exc:
        raise HTTPException(502, str(exc))
