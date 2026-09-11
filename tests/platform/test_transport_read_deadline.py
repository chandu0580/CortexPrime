"""Phase 11.3 (ADR-123): the transport's TOTAL budget bounds a streaming body.

A body that keeps trickling bytes never trips the per-read socket timeout; a
Kubernetes watch that outlives its own ``timeoutSeconds`` read for as long as
the API server liked (the 11.2 F-6 stall's other half). ``_read_bounded`` now
raises ``httpx.ReadTimeout`` once the policy's total budget has elapsed."""
from __future__ import annotations

import time

import httpx
import pytest

from backend.platform.transport.httpx_adapter import _read_bounded


class _Trickle:
    def __init__(self, chunks, delay=0.0):
        self._chunks, self._delay = chunks, delay

    def iter_bytes(self):
        for chunk in self._chunks:
            if self._delay:
                time.sleep(self._delay)
            yield chunk


def test_a_body_inside_the_budget_is_read_whole():
    body, truncated = _read_bounded(_Trickle([b"ab", b"cd"]), 10, deadline=time.monotonic() + 5)
    assert body == b"abcd" and truncated is False


def test_the_size_bound_still_applies():
    body, truncated = _read_bounded(_Trickle([b"abc", b"def"]), 4, deadline=time.monotonic() + 5)
    assert body == b"abcd" and truncated is True


def test_a_body_still_arriving_past_the_deadline_is_a_read_timeout():
    with pytest.raises(httpx.ReadTimeout):
        _read_bounded(_Trickle([b"x"] * 50, delay=0.01), 10_000, deadline=time.monotonic() + 0.05)


def test_no_deadline_means_the_pre_existing_behaviour():
    body, truncated = _read_bounded(_Trickle([b"a", b"b"]), 10)
    assert body == b"ab" and truncated is False
