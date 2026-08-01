"""
Tests for _track_build — feeds real GitHub webhook events into
BuildIntelligence (enterprise_cicd_intelligence.py) so its dashboard/
trend/timeline views get populated with real data. Previously that
service was only reachable via a standalone /api/cicd/pipeline-event
endpoint nothing in the real webhook flow ever called, leaving it
permanently empty.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.enterprise_github_integration import _track_build

pytestmark = pytest.mark.asyncio


class TestTrackBuild:
    async def test_calls_ingest_pipeline_event_with_event_type_and_payload(self):
        payload = {"workflow_run": {"id": 1, "status": "completed", "conclusion": "success"}}
        with patch(
            "backend.services.enterprise_cicd_intelligence.cicd_intelligence.ingest_pipeline_event",
            new=AsyncMock(return_value={}),
        ) as mock_ingest:
            await _track_build("workflow_run", payload)
        mock_ingest.assert_awaited_once_with("workflow_run", payload)

    async def test_never_raises_when_ingest_fails(self):
        with patch(
            "backend.services.enterprise_cicd_intelligence.cicd_intelligence.ingest_pipeline_event",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            await _track_build("workflow_run", {})  # must not raise
