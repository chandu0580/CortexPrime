"""
Enterprise GitLab CI Integration — REST API.

Deliberately narrow — see enterprise_gitlab_integration.py's module
docstring. Just enough surface to receive real GitLab deployment webhooks
and feed them into the same deploy-regression pipeline GitHub uses.

Endpoints:
  POST  /api/gitlab/webhook   — Receive and verify a GitLab webhook
  GET   /api/gitlab/webhooks  — List webhook delivery history
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Query, Request

from backend.services.enterprise_gitlab_integration import (
    GITLAB_WEBHOOK_SECRET_ENV,
    gitlab_webhook_receiver,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gitlab", tags=["Enterprise GitLab Integration"])


@router.post("/webhook")
async def receive_webhook(request: Request):
    try:
        body = await request.body()
        headers = dict(request.headers)
        # Server-side configuration only — see module docstring for why
        # this is never read from the incoming request.
        secret = os.getenv(GITLAB_WEBHOOK_SECRET_ENV, "")
        result = await gitlab_webhook_receiver.receive(body, headers, secret)
        return result
    except Exception as exc:
        raise HTTPException(502, f"Webhook processing failed: {exc}")


@router.get("/webhooks")
async def list_webhooks(limit: int = Query(20, ge=1, le=100)):
    try:
        return {"webhooks": gitlab_webhook_receiver.get_recent_deliveries(limit)}
    except Exception as exc:
        raise HTTPException(502, str(exc))
