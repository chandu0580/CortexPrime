"""
OpenTelemetry tracing configuration.
Replaces legacy custom in-process tracers with OTel-compatible spans.
"""
from __future__ import annotations

import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


def configure_tracing(
    service_name: str = "cortexprime",
    otlp_endpoint: Optional[str] = None,
    console_export: bool = False,
) -> trace.Tracer:
    """Configure OpenTelemetry tracing with optional OTLP export."""
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    })

    provider = TracerProvider(resource=resource)

    # OTLP exporter (for production: Honeycomb, Grafana Tempo, etc.)
    endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    # Console exporter for local development
    if console_export:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)


# Singleton tracer
_tracer: Optional[trace.Tracer] = None


def get_tracer() -> trace.Tracer:
    global _tracer
    if _tracer is None:
        _tracer = configure_tracing()
    return _tracer
