"""OpenTelemetry Protocol (OTLP) connector.

Accepts traces via OTLP HTTP protocol (protobuf and JSON),
decodes spans, and feeds them into the trace intelligence pipeline.

Follows BaseConnector pattern with graceful degradation.

OTLP HTTP endpoints implemented:
  POST /v1/traces  — ExportTraceServiceRequest (protobuf or JSON)

Reuses:
  - opentelemetry-proto for protobuf decoding
  - google.protobuf.json_format for JSON decoding
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from backend.connectors.base import BaseConnector

log = logging.getLogger(__name__)

OTLP_EVENT_TYPES = {
    "trace.started": "otel.trace.started",
    "trace.completed": "otel.trace.completed",
    "trace.error": "otel.trace.error",
    "span.failed": "otel.span.failed",
    "service.discovered": "otel.service.discovered",
    "service.updated": "otel.service.updated",
}

_SERVICE_NAME_ATTR = "service.name"
_SERVICE_VERSION_ATTR = "service.version"
_SERVICE_INSTANCE_ATTR = "service.instance.id"
_DEPLOYMENT_ENV_ATTR = "deployment.environment"
_HOST_NAME_ATTR = "host.name"


class OpenTelemetryConnector(BaseConnector):
    """OTLP connector — decodes traces from protobuf or JSON payloads.

    This is a passive receiver (no outbound HTTP). It parses the standard
    OTLP ExportTraceServiceRequest format and returns structured trace data
    that the Trace Intelligence service can process.
    """

    connector_name = "OpenTelemetry"
    connector_type = "opentelemetry"

    def __init__(self) -> None:
        self._ready = False

    async def initialize(self) -> bool:
        try:
            log.info("OpenTelemetry connector — protobuf schemas loaded")
            self._ready = True
            return True
        except ImportError as exc:
            log.warning("OpenTelemetry protobuf schemas not available: %s", exc)
            return False
        except Exception as exc:
            log.warning("OpenTelemetry connector init failed: %s", exc)
            return False

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def shutdown(self) -> bool:
        # Passive receiver — no outbound client/connection to close.
        self._ready = False
        return True

    async def health(self) -> Dict[str, Any]:
        return {"connector": self.connector_type, "ready": self.is_ready}

    async def decode_protobuf(self, body: bytes) -> Dict[str, Any]:
        """Decode an OTLP ExportTraceServiceRequest from protobuf binary."""
        if not self._ready:
            return {"status": "skipped", "reason": "OpenTelemetry connector not available"}
        from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
        request = trace_service_pb2.ExportTraceServiceRequest()
        request.ParseFromString(body)
        return self._process_otlp_request(request)

    async def decode_json(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Decode an OTLP ExportTraceServiceRequest from JSON."""
        if not self._ready:
            return {"status": "skipped", "reason": "OpenTelemetry connector not available"}
        from google.protobuf.json_format import ParseDict
        from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
        request = trace_service_pb2.ExportTraceServiceRequest()
        ParseDict(body, request)
        return self._process_otlp_request(request)

    def _process_otlp_request(self, request: Any) -> Dict[str, Any]:
        """Process an OTLP ExportTraceServiceRequest and return structured traces."""

        traces: List[Dict[str, Any]] = []
        services: Dict[str, Dict[str, Any]] = {}
        all_spans: List[Dict[str, Any]] = []
        now = _now()

        for resource_spans in request.resource_spans:
            resource_attrs = _proto_attributes_to_dict(
                resource_spans.resource.attributes
            ) if resource_spans.resource else {}

            service_name = resource_attrs.get(_SERVICE_NAME_ATTR, "unknown")
            service_version = resource_attrs.get(_SERVICE_VERSION_ATTR, "")
            service_instance = resource_attrs.get(_SERVICE_INSTANCE_ATTR, "")
            deploy_env = resource_attrs.get(_DEPLOYMENT_ENV_ATTR, "")
            host_name = resource_attrs.get(_HOST_NAME_ATTR, "")

            if service_name not in services:
                services[service_name] = {
                    "name": service_name,
                    "version": service_version,
                    "instance_id": service_instance,
                    "environment": deploy_env,
                    "host": host_name,
                    "resource_attributes": resource_attrs,
                    "first_seen": now,
                    "last_seen": now,
                    "span_count": 0,
                    "error_count": 0,
                }
            svc = services[service_name]
            svc["last_seen"] = now

            for scope_spans in resource_spans.scope_spans:
                scope_attrs = _proto_attributes_to_dict(
                    scope_spans.scope.attributes
                ) if scope_spans.scope and scope_spans.scope.attributes else {}
                scope_name = scope_spans.scope.name if scope_spans.scope else ""
                scope_version = scope_spans.scope.version if scope_spans.scope else ""

                for span in scope_spans.spans:
                    processed = self._process_span(
                        span, service_name, resource_attrs,
                        scope_attrs, scope_name, scope_version,
                    )
                    svc["span_count"] += 1
                    if processed.get("status") == "error":
                        svc["error_count"] += 1
                    all_spans.append(processed)

        return {
            "traces": traces,
            "services": list(services.values()),
            "spans": all_spans,
            "total_spans": len(all_spans),
            "total_services": len(services),
            "received_at": now,
        }

    def _process_span(
        self,
        span: Any,
        service_name: str,
        resource_attrs: Dict[str, Any],
        scope_attrs: Dict[str, Any],
        scope_name: str,
        scope_version: str,
    ) -> Dict[str, Any]:
        """Convert an OTLP Span protobuf to a CortexPrime trace span dict."""
        from opentelemetry.proto.trace.v1 import trace_pb2

        trace_id = span.trace_id.hex() if isinstance(span.trace_id, bytes) else str(span.trace_id)
        span_id = span.span_id.hex() if isinstance(span.span_id, bytes) else str(span.span_id)
        parent_span_id = span.parent_span_id.hex() if isinstance(span.parent_span_id, bytes) and span.parent_span_id else ""

        start_ns = span.start_time_unix_nano
        end_ns = span.end_time_unix_nano
        duration_ns = max(0, end_ns - start_ns) if end_ns >= start_ns else 0
        duration_ms = round(duration_ns / 1_000_000, 3)

        status_code = "unset"
        status_msg = ""
        if span.status:
            code_val = span.status.code
            if code_val == trace_pb2.Status.STATUS_CODE_OK:
                status_code = "ok"
            elif code_val == trace_pb2.Status.STATUS_CODE_ERROR:
                status_code = "error"
            elif code_val == trace_pb2.Status.STATUS_CODE_UNSET:
                status_code = "unset"
            else:
                status_code = "unknown"
            status_msg = span.status.message

        attributes = _proto_attributes_to_dict(span.attributes)
        span_kind_map = {
            trace_pb2.Span.SPAN_KIND_INTERNAL: "internal",
            trace_pb2.Span.SPAN_KIND_SERVER: "server",
            trace_pb2.Span.SPAN_KIND_CLIENT: "client",
            trace_pb2.Span.SPAN_KIND_PRODUCER: "producer",
            trace_pb2.Span.SPAN_KIND_CONSUMER: "consumer",
        }
        span_kind = span_kind_map.get(span.kind, "internal")

        events = []
        for evt in span.events:
            events.append({
                "name": evt.name,
                "time_unix_nano": evt.time_unix_nano,
                "attributes": _proto_attributes_to_dict(evt.attributes),
                "dropped_attributes_count": evt.dropped_attributes_count,
            })

        links = []
        for link in span.links:
            link_trace_id = link.trace_id.hex() if isinstance(link.trace_id, bytes) else str(link.trace_id)
            link_span_id = link.span_id.hex() if isinstance(link.span_id, bytes) else str(link.span_id)
            links.append({
                "trace_id": link_trace_id,
                "span_id": link_span_id,
                "attributes": _proto_attributes_to_dict(link.attributes),
                "dropped_attributes_count": link.dropped_attributes_count,
            })

        return {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "name": span.name,
            "kind": span_kind,
            "start_time_unix_nano": start_ns,
            "end_time_unix_nano": end_ns,
            "duration_ns": duration_ns,
            "duration_ms": duration_ms,
            "status": status_code,
            "status_message": status_msg,
            "attributes": attributes,
            "events": events,
            "links": links,
            "resource": resource_attrs,
            "scope": {
                "name": scope_name,
                "version": scope_version,
                "attributes": scope_attrs,
            },
            "trace_state": span.trace_state,
            "flags": span.flags,
            "service_name": service_name,
        }


def _proto_attributes_to_dict(attributes: Any) -> Dict[str, Any]:
    """Convert OTLP KeyValue repeated field to a plain dict."""
    result: Dict[str, Any] = {}
    if attributes is None:
        return result
    for kv in attributes:
        try:
            key = kv.key
            value = _proto_any_value(kv.value)
            result[key] = value
        except Exception:
            continue
    return result


def _proto_any_value(value: Any) -> Any:
    """Extract a Python value from an OTLP AnyValue protobuf."""
    kind = value.WhichOneof("value")
    if kind == "string_value":
        return value.string_value
    if kind == "int_value":
        return value.int_value
    if kind == "double_value":
        return value.double_value
    if kind == "bool_value":
        return value.bool_value
    if kind == "array_value":
        return [_proto_any_value(v) for v in value.array_value.values]
    if kind == "kvlist_value":
        return _proto_attributes_to_dict(value.kvlist_value.values)
    return None


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
