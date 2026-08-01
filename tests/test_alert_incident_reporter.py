from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_alert_incident_reporter import (
    build_correlated_comment,
    comment_correlated_signal,
)

class TestBuildCorrelatedComment:
    def test_includes_source_and_summary(self):
        comment = build_correlated_comment("flaky_test", "CI flaky on checkout")
        assert "flaky_test" in comment
        assert "CI flaky on checkout" in comment

    def test_omits_hypothesis_section_when_none(self):
        comment = build_correlated_comment("flaky_test", "x", hypothesis=None)
        assert "AI-generated" not in comment

    def test_includes_hypothesis_section_when_given(self):
        comment = build_correlated_comment("flaky_test", "x", hypothesis="Likely the same deploy.")
        assert "AI-generated hypothesis" in comment
        assert "unverified" in comment
        assert "Likely the same deploy." in comment


@pytest.mark.asyncio
class TestCommentCorrelatedSignal:
    async def test_returns_false_when_jira_not_registered(self):
        with patch("backend.connectors.registry.connector_registry.get", return_value=None):
            result = await comment_correlated_signal("OPS-1", "flaky_test", "x")
        assert result is False

    async def test_returns_false_when_jira_unavailable(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "unavailable"})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await comment_correlated_signal("OPS-1", "flaky_test", "x")
        assert result is False

    async def test_calls_add_comment_when_healthy(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.add_comment = AsyncMock(return_value={})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await comment_correlated_signal("OPS-1", "flaky_test", "CI flaky", hypothesis="same root cause")
        assert result is True
        fake_jira.add_comment.assert_awaited_once()
        args, _ = fake_jira.add_comment.call_args
        assert args[0] == "OPS-1"
        assert "CI flaky" in args[1]
        assert "same root cause" in args[1]

    async def test_returns_false_when_add_comment_raises(self):
        fake_jira = MagicMock()
        fake_jira.health = AsyncMock(return_value={"status": "available"})
        fake_jira.add_comment = AsyncMock(side_effect=RuntimeError("Jira API: HTTP 500"))
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_jira):
            result = await comment_correlated_signal("OPS-1", "flaky_test", "x")
        assert result is False
