"""
Research Telemetry — in-process metrics for the live research pipeline.

Tracks per-search latency, source counts, success/failure rates, and a
rolling window of recent searches for the /health/research endpoint.

Thread-safe via asyncio (all mutations happen in the event loop).
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional


@dataclass
class SearchRecord:
    query:        str
    search_type:  str
    source_count: int
    latency_ms:   float
    success:      bool
    timestamp:    float = field(default_factory=time.time)
    error:        Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query":        self.query[:120],
            "search_type":  self.search_type,
            "source_count": self.source_count,
            "latency_ms":   round(self.latency_ms, 1),
            "success":      self.success,
            "error":        self.error,
            "timestamp":    self.timestamp,
        }


class ResearchTelemetry:
    """
    In-memory telemetry store for the live research subsystem.

    Call ``record()`` after every search.  ``snapshot()`` returns
    everything needed by ``GET /health/research``.
    """

    def __init__(self, max_history: int = 100) -> None:
        self._history: Deque[SearchRecord] = deque(maxlen=max_history)
        self._total_searches  = 0
        self._total_successes = 0
        self._total_latency   = 0.0
        self._total_sources   = 0

    def record(
        self,
        query:        str,
        search_type:  str,
        source_count: int,
        latency_ms:   float,
        success:      bool,
        error:        Optional[str] = None,
    ) -> None:
        rec = SearchRecord(
            query        = query,
            search_type  = search_type,
            source_count = source_count,
            latency_ms   = latency_ms,
            success      = success,
            error        = error,
        )
        self._history.append(rec)
        self._total_searches  += 1
        self._total_latency   += latency_ms
        self._total_sources   += source_count
        if success:
            self._total_successes += 1

    def snapshot(self, recent_n: int = 10) -> Dict[str, Any]:
        """Return a telemetry snapshot for the health endpoint."""
        success_rate = (
            round(self._total_successes / self._total_searches, 3)
            if self._total_searches > 0 else None
        )
        avg_latency = (
            round(self._total_latency / self._total_searches, 1)
            if self._total_searches > 0 else None
        )
        avg_sources = (
            round(self._total_sources / self._total_searches, 1)
            if self._total_searches > 0 else None
        )

        recent = list(self._history)[-recent_n:]
        recent.reverse()  # newest first

        return {
            "total_searches":   self._total_searches,
            "total_successes":  self._total_successes,
            "success_rate":     success_rate,
            "avg_latency_ms":   avg_latency,
            "avg_source_count": avg_sources,
            "recent_searches":  [r.to_dict() for r in recent],
        }


research_telemetry = ResearchTelemetry()
