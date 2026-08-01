"""
Enterprise Flaky Test Detection — REST API.

Provider-neutral on purpose: flaky-test occurrences are recorded by the
same shared history store regardless of whether they came from a GitHub
workflow_run or a GitLab pipeline webhook (see
backend.services.enterprise_flaky_test_detector), so this lives at its
own path rather than under /api/github or /api/gitlab.

Endpoints:
  GET /api/flaky-tests  — pending retries + recent confirmed-flaky occurrences
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/flaky-tests", tags=["Enterprise Flaky Test Detection"])


@router.get("")
async def list_flaky_tests(limit: int = Query(20, ge=1, le=100)):
    try:
        from backend.services.enterprise_flaky_test_detector import (
            flaky_test_history_store,
            pending_retry_store,
        )
        return {
            "pending": pending_retry_store.list_pending(),
            "recent": flaky_test_history_store.list_recent(limit),
        }
    except Exception as exc:
        raise HTTPException(502, str(exc))
