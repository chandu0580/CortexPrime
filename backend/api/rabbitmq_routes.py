"""
RabbitMQ Observability Routes
------------------------------
Lightweight REST API for runtime inspection of the message bus.

Endpoints
---------
GET  /api/rabbitmq/health           — connection status
GET  /api/rabbitmq/trace/recent     — recent message traces
GET  /api/rabbitmq/trace/stats      — aggregate trace statistics
GET  /api/rabbitmq/trace/{exec_id}  — traces for a specific execution
GET  /api/rabbitmq/dlq              — inspect DLQ (non-destructive)
POST /api/rabbitmq/dlq/replay/{id}  — replay a DLQ message
DELETE /api/rabbitmq/dlq            — purge DLQ (admin)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from backend.auth.dependencies import require_admin, require_user

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/rabbitmq",
    tags=["rabbitmq"],
    dependencies=[Depends(require_user)],
)

_ADMIN = [Depends(require_admin)]


# =========================================================
# HEALTH
# =========================================================

@router.get("/health")
async def rabbitmq_health() -> Dict[str, Any]:
    """Return RabbitMQ connection status and basic stats."""
    try:
        from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
        from backend.infrastructure.rabbitmq.tracing    import message_tracer
        return {
            "status":     "connected" if rabbitmq_connection.is_available else "disconnected",
            "available":  rabbitmq_connection.is_available,
            "trace_stats": message_tracer.stats(),
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


# =========================================================
# TRACING
# =========================================================

@router.get("/trace/recent")
async def trace_recent(
    limit: int = Query(default=100, ge=1, le=2000),
) -> List[Dict[str, Any]]:
    """Return the most recent N message trace entries."""
    from backend.infrastructure.rabbitmq.tracing import message_tracer
    return message_tracer.recent(limit=limit)


@router.get("/trace/stats")
async def trace_stats() -> Dict[str, Any]:
    """Return aggregate publish/consume statistics."""
    from backend.infrastructure.rabbitmq.tracing import message_tracer
    return message_tracer.stats()


@router.get("/trace/{execution_id}")
async def trace_by_execution(execution_id: str) -> List[Dict[str, Any]]:
    """Return all trace entries for a specific execution_id."""
    from backend.infrastructure.rabbitmq.tracing import message_tracer
    return message_tracer.by_execution(execution_id)


# =========================================================
# DLQ
# =========================================================

@router.get("/dlq")
async def dlq_inspect(
    limit: int = Query(default=50, ge=1, le=500),
) -> List[Dict[str, Any]]:
    """
    Non-destructively peek at messages in the dead-letter queue.
    Messages are nack-requeued after inspection.
    """
    from backend.infrastructure.rabbitmq.retry_policy import dlq_manager
    return await dlq_manager.inspect(limit=limit)


@router.post("/dlq/replay/{message_id}", dependencies=_ADMIN)
async def dlq_replay(message_id: str) -> Dict[str, Any]:
    """
    Republish a dead-letter message back to the orchestration exchange.
    Resets retry_count to 0 (fresh attempt).
    """
    from backend.infrastructure.rabbitmq.retry_policy import dlq_manager
    success = await dlq_manager.replay(message_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Message {message_id} not found in DLQ",
        )
    return {"replayed": True, "message_id": message_id}


@router.delete("/dlq", dependencies=_ADMIN)
async def dlq_purge() -> Dict[str, Any]:
    """
    Purge all messages from the dead-letter queue.
    **Irreversible — use with caution.**
    """
    from backend.infrastructure.rabbitmq.retry_policy import dlq_manager
    count = await dlq_manager.purge()
    return {"purged": count}
