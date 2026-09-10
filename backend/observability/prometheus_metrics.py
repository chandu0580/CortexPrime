"""
backend/observability/prometheus_metrics.py

Central Prometheus metrics registry for CortexPrime.

All metrics are registered here as module-level singletons.
Import the ``metrics`` object anywhere in the codebase to record observations.

Usage
-----
    from backend.observability.prometheus_metrics import metrics

    # Increment a counter
    metrics.missions_started.inc()

    # Record a histogram observation
    with metrics.mission_duration.time():
        await run_mission(...)

    # Set a gauge
    metrics.active_missions.set(n)
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        REGISTRY,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        multiprocess,
    )
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False


# ── Histogram buckets ─────────────────────────────────────────────────────────

_DURATION_BUCKETS    = (.05, .1, .25, .5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)
_LATENCY_BUCKETS_MS  = (10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)


class _NoopCounter:
    def inc(self, amount=1): pass
    def labels(self, **_): return self

class _NoopGauge:
    def inc(self, amount=1): pass
    def dec(self, amount=1): pass
    def set(self, value): pass
    def labels(self, **_): return self

class _NoopHistogram:
    def observe(self, amount): pass
    def labels(self, **_): return self
    @contextmanager
    def time(self): yield

class _NoopSummary:
    def observe(self, amount): pass
    def labels(self, **_): return self


def _counter(name: str, doc: str, labels=()) -> "Counter":
    if not _PROMETHEUS_AVAILABLE:
        return _NoopCounter()
    return Counter(name, doc, labels)

def _gauge(name: str, doc: str, labels=()) -> "Gauge":
    if not _PROMETHEUS_AVAILABLE:
        return _NoopGauge()
    return Gauge(name, doc, labels)

def _histogram(name: str, doc: str, labels=(), buckets=_DURATION_BUCKETS) -> "Histogram":
    if not _PROMETHEUS_AVAILABLE:
        return _NoopHistogram()
    return Histogram(name, doc, labels, buckets=buckets)


class _CortexMetrics:
    """
    All Prometheus metrics for CortexPrime.
    Instantiated once at module load; thread/process-safe.
    """

    def __init__(self):
        # ── Mission metrics ───────────────────────────────────────────────
        self.missions_started = _counter(
            "cortex_missions_started_total",
            "Total number of missions started",
            ["mission_type"],
        )
        self.missions_completed = _counter(
            "cortex_missions_completed_total",
            "Total number of missions completed successfully",
            ["mission_type"],
        )
        self.missions_failed = _counter(
            "cortex_missions_failed_total",
            "Total number of missions that failed",
            ["mission_type", "error_type"],
        )
        self.active_missions = _gauge(
            "cortex_active_missions",
            "Number of missions currently in-flight",
        )
        self.missions_by_agent = _counter(
            "cortex_missions_by_agent_total",
            "Total missions started, broken down by agent",
            ["agent", "mission_type"],
        )
        self.mission_queue_depth = _gauge(
            "cortex_mission_queue_depth",
            "Current number of missions waiting in the execution queue",
        )
        self.mission_failures = _counter(
            "cortex_mission_failures_total",
            "Total mission failures with error details",
            ["error_type"],
        )
        # ── Signal fabric (Phase 11.2, ADR-122) ───────────────────────────
        # Exported by the signal worker process and by the API process alike
        # (one registry per process). Labels are bounded vocabularies, never
        # tenant ids or subject names.
        self.signal_events_received = _counter(
            "cortex_signal_events_received_total",
            "Signal events received from a source, before any decision",
            ["source", "event_type"],
        )
        self.signal_events_rejected = _counter(
            "cortex_signal_events_rejected_total",
            "Signal events refused at the boundary or by validation",
            ["source", "reason"],
        )
        self.signal_events_persisted = _counter(
            "cortex_signal_events_persisted_total",
            "Signal events durably recorded as new observations",
            ["source"],
        )
        self.signal_events_deduplicated = _counter(
            "cortex_signal_events_deduplicated_total",
            "Signal events that collided on identity and were not recorded again",
            ["source"],
        )
        self.signal_events_dropped = _counter(
            "cortex_signal_events_dropped_total",
            "Signal events known to be lost (explicit loss, e.g. relist after a stall or expiry)",
            ["source", "reason"],
        )
        self.signal_cycles = _counter(
            "cortex_signal_cycles_total",
            "Watch cycles by outcome (observed, idle, follower, watch_failed, ...)",
            ["source", "outcome"],
        )
        self.signal_retries = _counter(
            "cortex_signal_retries_total",
            "Watch/list attempts retried after a failure",
            ["source"],
        )
        self.signal_reconnects = _counter(
            "cortex_signal_reconnects_total",
            "Watch positions re-established after expiry (410) or a stall",
            ["source", "reason"],
        )
        self.signal_provider_errors = _counter(
            "cortex_signal_provider_errors_total",
            "Errors returned by the signal source's API",
            ["source", "kind"],
        )
        self.signal_facts_derived = _counter(
            "cortex_signal_facts_derived_total",
            "Fact derivations from persisted signal observations, by outcome",
            ["outcome"],
        )
        self.signal_candidates = _gauge(
            "cortex_signal_incident_candidates",
            "Incident candidates currently projected for detection handoff",
            ["kind"],
        )
        self.signal_handoffs = _counter(
            "cortex_signal_handoffs_total",
            "Candidate projections handed to the detection boundary",
        )
        self.signal_cycle_seconds = _histogram(
            "cortex_signal_cycle_seconds",
            "Wall time of one watch cycle (window + enrichment + persistence)",
            ["source"],
        )
        self.signal_persist_seconds = _histogram(
            "cortex_signal_persist_seconds",
            "Time to persist one observation",
            ["source"],
        )
        self.signal_ingest_seconds = _histogram(
            "cortex_signal_ingest_seconds",
            "Time from HTTP receipt to durable observation for token/webhook ingestion",
            ["source"],
        )
        self.signal_event_lag_seconds = _histogram(
            "cortex_signal_event_lag_seconds",
            "Observed-at to recorded-at lag of persisted signal events",
            ["source"],
            buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300, 600),
        )
        self.signal_worker_leader = _gauge(
            "cortex_signal_worker_leader",
            "1 when this worker holds the stream role, else 0",
        )
        self.mission_duration = _histogram(
            "cortex_mission_duration_seconds",
            "Wall-clock duration of missions in seconds",
            ["mission_type"],
            buckets=_DURATION_BUCKETS,
        )

        # ── Agent metrics ─────────────────────────────────────────────────
        self.agent_executions = _counter(
            "cortex_agent_executions_total",
            "Total agent execution calls",
            ["agent", "event_type"],
        )
        self.agent_failures = _counter(
            "cortex_agent_failures_total",
            "Total agent execution failures",
            ["agent", "error_type"],
        )
        self.agent_duration = _histogram(
            "cortex_agent_duration_seconds",
            "Agent execution duration in seconds",
            ["agent"],
            buckets=_DURATION_BUCKETS,
        )
        self.active_agents = _gauge(
            "cortex_active_agents",
            "Number of agents currently registered",
        )

        # ── LLM metrics ───────────────────────────────────────────────────
        self.llm_requests = _counter(
            "cortex_llm_requests_total",
            "Total LLM API requests",
            ["provider", "model"],
        )
        self.llm_failures = _counter(
            "cortex_llm_failures_total",
            "Total LLM API failures",
            ["provider", "model", "error_type"],
        )
        self.llm_latency_ms = _histogram(
            "cortex_llm_latency_ms",
            "LLM request latency in milliseconds",
            ["provider", "model"],
            buckets=_LATENCY_BUCKETS_MS,
        )
        self.llm_prompt_tokens = _counter(
            "cortex_llm_prompt_tokens_total",
            "Total LLM prompt tokens consumed",
            ["provider", "model"],
        )
        self.llm_completion_tokens = _counter(
            "cortex_llm_completion_tokens_total",
            "Total LLM completion tokens produced",
            ["provider", "model"],
        )
        self.llm_cost_usd = _counter(
            "cortex_llm_cost_usd_total",
            "Total estimated LLM cost in USD",
            ["provider", "model"],
        )

        # ── Voice metrics ─────────────────────────────────────────────────
        self.voice_sessions = _counter(
            "cortex_voice_sessions_total",
            "Total voice sessions started",
        )
        self.active_voice_sessions = _gauge(
            "cortex_active_voice_sessions",
            "Number of active voice sessions",
        )
        self.voice_duration = _histogram(
            "cortex_voice_duration_seconds",
            "Voice session duration in seconds",
            buckets=_DURATION_BUCKETS,
        )
        self.stt_latency_ms = _histogram(
            "cortex_stt_latency_ms",
            "Speech-to-text transcription latency in milliseconds",
            buckets=_LATENCY_BUCKETS_MS,
        )
        self.tts_latency_ms = _histogram(
            "cortex_tts_latency_ms",
            "Text-to-speech synthesis latency in milliseconds",
            buckets=_LATENCY_BUCKETS_MS,
        )

        # ── Memory metrics ────────────────────────────────────────────────
        self.memory_reads = _counter(
            "cortex_memory_reads_total",
            "Total memory read operations",
            ["store"],   # episodic | semantic | vector | short_term
        )
        self.memory_writes = _counter(
            "cortex_memory_writes_total",
            "Total memory write operations",
            ["store"],
        )
        self.memory_latency_ms = _histogram(
            "cortex_memory_latency_ms",
            "Memory operation latency in milliseconds",
            ["store", "operation"],
            buckets=_LATENCY_BUCKETS_MS,
        )

        # ── WebSocket metrics ─────────────────────────────────────────────
        self.ws_connections = _gauge(
            "cortex_ws_connections",
            "Number of active WebSocket connections",
        )
        self.ws_messages_sent = _counter(
            "cortex_ws_messages_sent_total",
            "Total WebSocket messages sent to clients",
        )
        self.ws_events_published = _counter(
            "cortex_ws_events_published_total",
            "Total cognitive events published to the event bus",
            ["event_type"],
        )

        # ── HTTP metrics ──────────────────────────────────────────────────
        self.http_requests = _counter(
            "cortex_http_requests_total",
            "Total HTTP requests handled",
            ["method", "path", "status"],
        )
        self.http_latency_ms = _histogram(
            "cortex_http_latency_ms",
            "HTTP request latency in milliseconds",
            ["method", "path"],
            buckets=_LATENCY_BUCKETS_MS,
        )
        # Standard-convention duplicates of the two metrics above (name +
        # units + label set that enterprise_deploy_regression_detector's
        # PromQL actually queries: http_requests_total{service,status} and
        # http_request_duration_seconds_bucket{service}). The cortex_-
        # prefixed metrics above are CortexPrime's own naming convention;
        # these exist so CortexPrime's own backend can be monitored by its
        # own deploy-regression detector, the same way any other properly
        # RED-instrumented service would be.
        self.http_requests_standard = _counter(
            "http_requests_total",
            "Total HTTP requests handled (RED-method convention)",
            ["service", "method", "path", "status"],
        )
        self.http_request_duration_seconds = _histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds (RED-method convention)",
            ["service"],
        )
        self.rate_limit_hits = _counter(
            "cortex_rate_limit_hits_total",
            "Total requests blocked by rate limiter",
            ["endpoint"],
        )
        self.guardrail_blocks = _counter(
            "cortex_guardrail_blocks_total",
            "Total requests blocked by guardrails",
            ["violation_type"],
        )

        # ── Infrastructure metrics ────────────────────────────────────────
        self.db_query_latency_ms = _histogram(
            "cortex_db_query_latency_ms",
            "Database query latency in milliseconds",
            ["operation"],
            buckets=_LATENCY_BUCKETS_MS,
        )
        self.redis_operations = _counter(
            "cortex_redis_operations_total",
            "Total Redis operations",
            ["operation"],
        )

    # ── Convenience context managers ─────────────────────────────────────────

    @contextmanager
    def track_mission(self, mission_type: str = "autonomous"):
        """Context manager that records mission start/completion/failure + duration."""
        self.missions_started.labels(mission_type=mission_type).inc()
        self.active_missions.inc()
        t0 = time.monotonic()
        try:
            yield
            duration = time.monotonic() - t0
            self.mission_duration.labels(mission_type=mission_type).observe(duration)
            self.missions_completed.labels(mission_type=mission_type).inc()
        except Exception as exc:
            duration = time.monotonic() - t0
            self.mission_duration.labels(mission_type=mission_type).observe(duration)
            self.missions_failed.labels(
                mission_type=mission_type,
                error_type=type(exc).__name__,
            ).inc()
            raise
        finally:
            self.active_missions.dec()

    @contextmanager
    def track_agent(self, agent: str, event_type: str = "execution"):
        """Context manager for agent execution tracking."""
        t0 = time.monotonic()
        try:
            yield
            self.agent_executions.labels(agent=agent, event_type=event_type).inc()
            self.agent_duration.labels(agent=agent).observe(time.monotonic() - t0)
        except Exception as exc:
            self.agent_failures.labels(agent=agent, error_type=type(exc).__name__).inc()
            self.agent_duration.labels(agent=agent).observe(time.monotonic() - t0)
            raise

    def record_llm_call(
        self,
        provider: str,
        model: str,
        latency_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
        success: bool = True,
        error_type: str = "",
    ) -> None:
        """Record a completed LLM API call."""
        if success:
            self.llm_requests.labels(provider=provider, model=model).inc()
        else:
            self.llm_failures.labels(
                provider=provider, model=model, error_type=error_type or "unknown"
            ).inc()
        self.llm_latency_ms.labels(provider=provider, model=model).observe(latency_ms)
        if prompt_tokens:
            self.llm_prompt_tokens.labels(provider=provider, model=model).inc(prompt_tokens)
        if completion_tokens:
            self.llm_completion_tokens.labels(provider=provider, model=model).inc(completion_tokens)
        if cost_usd:
            self.llm_cost_usd.labels(provider=provider, model=model).inc(cost_usd)


# ── Module singleton ──────────────────────────────────────────────────────────
metrics = _CortexMetrics()


# ── Prometheus /metrics endpoint helper ──────────────────────────────────────

def generate_metrics_response():
    """
    Generate the Prometheus text exposition.
    Handles both single-process and multi-process (prometheus_multiproc_dir) modes.
    """
    if not _PROMETHEUS_AVAILABLE:
        return b"# prometheus_client not installed\n", "text/plain; charset=utf-8"

    multiproc_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR") or os.getenv("prometheus_multiproc_dir")
    if multiproc_dir:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        data = generate_latest(registry)
    else:
        data = generate_latest(REGISTRY)

    return data, CONTENT_TYPE_LATEST
