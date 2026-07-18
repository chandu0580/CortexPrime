from __future__ import annotations

import pytest

from backend.ai.correlation import EventCorrelator
from backend.ai.models import RuntimeTarget


class TestEventCorrelator:
    @pytest.fixture
    def correlator(self):
        return EventCorrelator()

    @pytest.mark.asyncio
    async def test_record_event(self, correlator):
        event = await correlator.record(
            correlation_id="corr-1",
            source_runtime="knowledge_runtime",
            event_type="search",
            status="success",
            message="Knowledge search completed",
        )
        assert event.correlation_id == "corr-1"
        assert event.source_runtime == "knowledge_runtime"
        assert event.event_type == "search"
        assert event.event_id != ""

    @pytest.mark.asyncio
    async def test_get_by_correlation(self, correlator):
        await correlator.record("corr-a", "mission", "create")
        await correlator.record("corr-a", "governance", "check")
        await correlator.record("corr-b", "execution", "run")
        events = correlator.get_by_correlation("corr-a")
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_get_by_runtime(self, correlator):
        await correlator.record("c1", "knowledge_runtime", "search")
        await correlator.record("c2", "execution_runtime", "run")
        events = correlator.get_by_runtime(RuntimeTarget.KNOWLEDGE)
        assert len(events) == 1
        assert events[0].source_runtime == "knowledge_runtime"

    @pytest.mark.asyncio
    async def test_get_timeline_ordered(self, correlator):
        await correlator.record("c1", "mission", "create")
        await correlator.record("c1", "governance", "check")
        await correlator.record("c1", "execution", "run")
        timeline = correlator.get_timeline("c1")
        assert len(timeline) == 3
        assert timeline[0].event_type == "create"
        assert timeline[-1].event_type == "run"

    @pytest.mark.asyncio
    async def test_get_events_without_correlation(self, correlator):
        await correlator.record("c1", "mission", "create")
        await correlator.record("c2", "execution", "run")
        all_events = correlator.get_events()
        assert len(all_events) == 2

    @pytest.mark.asyncio
    async def test_get_events_with_correlation(self, correlator):
        await correlator.record("c1", "mission", "create")
        await correlator.record("c1", "governance", "check")
        await correlator.record("c2", "execution", "run")
        events = correlator.get_events(correlation_id="c1")
        assert len(events) == 2
