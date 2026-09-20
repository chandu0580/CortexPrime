"""JSON Schemas for connector capabilities, derived from their operation specs.

Phase 11.1-K. The capability registry stores a schema by reference (name plus
content digest); the product API serves the schema itself. Both are derived here
from the ``ProviderOperationSpec`` the gateway validates against, never written
by hand, so the published contract cannot drift from the enforced one.

Lives beside the composition code rather than in ``backend.contracts``: it needs
``json`` and ``hashlib``, which the contracts package deliberately does not
depend on (DEP-CONTRACTS-LEAF).
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Mapping

__all__ = ["input_schema_for", "output_schema_for", "schema_ref"]

_JSON_TYPES = {
    "string": "string", "text": "string", "resource_segment": "string", "enum": "string",
    "integer": "integer", "boolean": "boolean", "string_list": "array",
}


def input_schema_for(spec: Any) -> dict:
    """A JSON Schema for an operation's input, derived from its parameter specs.

    Derived, never hand-written: the catalog is what the gateway validates
    against, so a schema written separately would diverge on the first change.
    """
    properties: dict = {}
    required: list = []
    for parameter in spec.parameters:
        kind = getattr(parameter.kind, "value", str(parameter.kind))
        prop: dict = {"type": _JSON_TYPES.get(kind, "string")}
        if kind == "string_list":
            prop["items"] = {"type": "string"}
        if parameter.max_length is not None:
            prop["maxLength"] = parameter.max_length
        if parameter.min_value is not None:
            prop["minimum"] = parameter.min_value
        if parameter.max_value is not None:
            prop["maximum"] = parameter.max_value
        if parameter.allowed_values:
            prop["enum"] = list(parameter.allowed_values)
        if kind == "resource_segment":
            prop["pattern"] = "^[a-z0-9]([-a-z0-9.]*[a-z0-9])?$"
        properties[parameter.name] = prop
        if parameter.required:
            required.append(parameter.name)
    return {"type": "object", "properties": properties, "required": sorted(required),
            "additionalProperties": False}


def output_schema_for(spec: Any) -> dict:
    """The normalized evidence an operation returns (declared scalars and records)."""
    properties = {name: {} for name in spec.response_evidence_fields}
    records = getattr(spec, "response_evidence_records", None)
    if records is not None:
        properties[records.field_name] = {
            "type": "array", "maxItems": records.max_records,
            "items": {"type": "object", "properties": {f: {} for f in records.fields}},
        }
    return {"type": "object", "properties": properties,
            "required": sorted(spec.response_required_fields)}


def schema_ref(name: str, schema: Mapping[str, Any]) -> dict:
    """The registry stores a schema by reference: name plus content digest."""
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    return {"name": name, "digest": sha256(canonical.encode("utf-8")).hexdigest(),
            "media_type": "application/schema+json"}

