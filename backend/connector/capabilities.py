from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.connector.models import Capability

CAPABILITY_DESCRIPTIONS: dict[Capability, str] = {
    Capability.DEPLOY: "Deploy application or service to target environment",
    Capability.ROLLBACK: "Rollback to a previous deployment version",
    Capability.OBSERVE: "Observe and collect metrics, logs, or traces",
    Capability.SCALE: "Scale resources up or down",
    Capability.RESTART: "Restart a service, pod, or container",
    Capability.BUILD: "Build an artifact from source code",
    Capability.TEST: "Run tests against a target",
    Capability.NOTIFY: "Send a notification to a channel or user",
    Capability.PROVISION: "Provision new infrastructure resources",
    Capability.DESTROY: "Destroy or decommission infrastructure resources",
    Capability.SEARCH: "Search across data sources",
    Capability.EXECUTE: "Execute a command or script remotely",
    Capability.CONFIGURE: "Apply configuration changes to a target",
}


@dataclass
class CapabilityCatalog:
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)

    def register(self, connector_type: str, capabilities: list[Capability]) -> None:
        self.entries[connector_type] = {
            "connector_type": connector_type,
            "capabilities": capabilities,
            "capability_names": [c.value for c in capabilities],
        }

    def unregister(self, connector_type: str) -> None:
        self.entries.pop(connector_type, None)

    def find_by_capability(self, capability: Capability) -> list[str]:
        return [
            ct
            for ct, info in self.entries.items()
            if capability in info["capabilities"]
        ]

    def find_by_any_capability(self, capabilities: list[Capability]) -> list[str]:
        cap_set = set(capabilities)
        return [
            ct
            for ct, info in self.entries.items()
            if cap_set & set(info["capabilities"])
        ]

    def get_capabilities(self, connector_type: str) -> list[Capability]:
        info = self.entries.get(connector_type)
        return list(info["capabilities"]) if info else []

    def get_all_connectors(self) -> list[dict[str, Any]]:
        return list(self.entries.values())

    def get_capabilities_prompt(self) -> str:
        lines: list[str] = []
        for ct, info in sorted(self.entries.items(), key=lambda x: x[0]):
            names = ", ".join(sorted(info["capability_names"]))
            lines.append(f"  - {ct}: {names}")
        return "\n".join(lines) if lines else "  (no registered capabilities)"


@dataclass
class CapabilitySet:
    capabilities: set[Capability] = field(default_factory=set)

    def add(self, capability: Capability) -> None:
        self.capabilities.add(capability)

    def add_multiple(self, capabilities: list[Capability]) -> None:
        self.capabilities.update(capabilities)

    def has(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def has_any(self, capabilities: list[Capability]) -> bool:
        return bool(set(capabilities) & self.capabilities)

    def list(self) -> list[Capability]:
        return sorted(self.capabilities, key=lambda c: c.value)

    def to_entity_ids(self) -> list[str]:
        return [c.value for c in self.capabilities]

    def describe(self) -> str:
        return ", ".join(
            f"{c.value}: {CAPABILITY_DESCRIPTIONS.get(c, '')}"
            for c in self.list()
        )


capability_catalog = CapabilityCatalog()
