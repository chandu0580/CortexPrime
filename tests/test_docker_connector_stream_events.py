"""
Tests for DockerConnector.stream_events() — specifically a regression test
for a real bug found while running a live integration test: iterating
docker-py's blocking client.events() generator directly inside an async
function monopolizes the entire asyncio event loop for the duration of
each blocking socket read, starving every other coroutine (including the
ASGI server itself, which never got a chance to start accepting
connections during a live test run).
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from backend.connectors.docker import DockerConnector

pytestmark = pytest.mark.asyncio


def _blocking_event_generator(events, delay=0.01):
    """Simulates docker-py's client.events() — a real generator whose
    next() call blocks the calling thread for `delay` seconds, the way a
    real blocking socket read would."""
    def gen():
        for e in events:
            time.sleep(delay)
            yield e
    return gen()


def _connector_with_fake_client(events, delay=0.01):
    connector = DockerConnector()
    fake_client = MagicMock()
    fake_client.events.return_value = _blocking_event_generator(events, delay=delay)
    connector._client = fake_client
    return connector


class TestStreamEvents:
    async def test_yields_dict_events_in_order(self):
        events = [{"Type": "container", "Action": "start"}, {"Type": "container", "Action": "stop"}]
        connector = _connector_with_fake_client(events)
        received = [e async for e in connector.stream_events()]
        assert received == events

    async def test_filters_out_non_dict_events(self):
        connector = _connector_with_fake_client([b"raw bytes", {"Type": "container"}, "also not a dict"])
        received = [e async for e in connector.stream_events()]
        assert received == [{"Type": "container"}]

    async def test_stops_cleanly_when_iterator_exhausted(self):
        connector = _connector_with_fake_client([{"a": 1}])
        count = 0
        async for _ in connector.stream_events():
            count += 1
        assert count == 1

    async def test_since_and_filters_passed_through(self):
        connector = _connector_with_fake_client([])
        async for _ in connector.stream_events(since="12345", filters={"type": "container"}):
            pass
        connector._client.events.assert_called_once_with(
            decode=True, since="12345", filters={"type": "container"},
        )

    async def test_exception_opening_stream_is_caught_and_logged(self):
        connector = DockerConnector()
        fake_client = MagicMock()
        fake_client.events.side_effect = RuntimeError("boom")
        connector._client = fake_client

        received = [e async for e in connector.stream_events()]
        assert received == []

    async def test_does_not_block_the_event_loop(self):
        """The actual regression test.

        5 events at 0.05s of blocking "read" time each = 0.25s of genuine
        blocking work. A concurrently-running ticker records how many times
        it gets to run during that window. With the bug (plain `for event
        in client.events(...)` with no asyncio.to_thread), each blocking
        read freezes the whole event loop, so the ticker barely runs at
        all during those 0.25s. With the fix (each read dispatched via
        asyncio.to_thread), the ticker keeps ticking throughout.
        """
        connector = _connector_with_fake_client([{"n": i} for i in range(5)], delay=0.05)

        tick_count = 0

        async def ticker():
            nonlocal tick_count
            while True:
                tick_count += 1
                await asyncio.sleep(0.01)

        async def consume():
            async for _ in connector.stream_events():
                pass

        ticker_task = asyncio.create_task(ticker())
        await consume()
        ticker_task.cancel()

        # ~0.25s of blocking work / 0.01s tick interval == ~25 ticks if truly
        # concurrent. The bug would starve the ticker down to a handful of
        # ticks (one opportunity per yielded event, at best). 10 is a
        # generous floor that still clearly distinguishes fixed from broken.
        assert tick_count >= 10, f"only {tick_count} ticks — event loop was blocked"
