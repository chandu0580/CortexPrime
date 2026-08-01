"""
Regression test for GitHubConnector._request_list's envelope-unwrapping.

Found via real end-to-end flaky-test validation: GET /actions/runs/{id}/jobs
returns {"total_count": N, "jobs": [...]}, not a bare array. _request_list's
generic unwrap-key list didn't include "jobs" (only had a special case for
"workflow_runs"), so it silently fell through to wrapping the *entire*
envelope dict as a single fake list item — every job's fields
(name/conclusion/steps) read back as missing, evidence collapsed to
"unknown"/"unknown" instead of real data.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.connectors.github import GitHubConnector

pytestmark = pytest.mark.asyncio


def _connector() -> GitHubConnector:
    return GitHubConnector()


class TestRequestListUnwrap:
    async def test_bare_array_response_returned_as_is(self):
        conn = _connector()
        conn._request = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        result = await conn._request_list("GET", "/some/path")
        assert result == [{"id": 1}, {"id": 2}]

    async def test_unwraps_jobs_envelope(self):
        conn = _connector()
        conn._request = AsyncMock(return_value={
            "total_count": 2,
            "jobs": [{"name": "build", "conclusion": "failure"}, {"name": "build", "conclusion": "success"}],
        })
        result = await conn._request_list("GET", "/repos/o/r/actions/runs/1/jobs")
        assert result == [{"name": "build", "conclusion": "failure"}, {"name": "build", "conclusion": "success"}]

    async def test_unwraps_workflow_runs_envelope(self):
        conn = _connector()
        conn._request = AsyncMock(return_value={
            "total_count": 1,
            "workflow_runs": [{"id": 42, "status": "completed"}],
        })
        result = await conn._request_list("GET", "/repos/o/r/actions/runs")
        assert result == [{"id": 42, "status": "completed"}]

    async def test_unwraps_generic_items_key(self):
        conn = _connector()
        conn._request = AsyncMock(return_value={"items": [{"id": 1}]})
        result = await conn._request_list("GET", "/some/path")
        assert result == [{"id": 1}]

    async def test_falls_back_to_wrapping_whole_dict_when_no_known_key_matches(self):
        conn = _connector()
        conn._request = AsyncMock(return_value={"unexpected_shape": True})
        result = await conn._request_list("GET", "/some/path")
        assert result == [{"unexpected_shape": True}]

    async def test_returns_empty_list_for_non_dict_non_list_response(self):
        conn = _connector()
        conn._request = AsyncMock(return_value=None)
        result = await conn._request_list("GET", "/some/path")
        assert result == []
