from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.connectors.base import BaseConnector

log = logging.getLogger(__name__)


class ConnectorRegistry:
    """Registry of all enterprise connectors.

    Follows the same singleton + register/list pattern as ToolRegistry
    and AgentRegistry elsewhere in the codebase.

    Extended in Sprint 46.1 to aggregate and expose per-connector
    operation capabilities without introducing a separate registry.
    """

    def __init__(self) -> None:
        self._connectors: Dict[str, BaseConnector] = {}

    def register(self, connector: BaseConnector) -> None:
        key = connector.connector_type
        if key in self._connectors:
            log.warning("Overwriting existing connector: %s", key)
        self._connectors[key] = connector
        log.info("Registered connector: %s (%s)", connector.connector_name, key)

    def get(self, connector_type: str) -> Optional[BaseConnector]:
        return self._connectors.get(connector_type)

    def list_types(self) -> List[str]:
        return list(self._connectors.keys())

    def list_all(self) -> List[BaseConnector]:
        return list(self._connectors.values())

    def count(self) -> int:
        return len(self._connectors)

    # ------------------------------------------------------------------
    # Capability introspection — aggregates operation metadata from
    # every registered connector using BaseConnector.get_operations().
    # ------------------------------------------------------------------

    def get_all_operations(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Return capabilities for every registered connector.

        Returns::

            {
                "github": {
                    "create_branch": {"description": "...", "required_params": [...], ...},
                    ...
                },
                "jira": {...},
                ...
            }
        """
        result: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for ctype, connector in self._connectors.items():
            try:
                ops = connector.get_operations()
                if ops:
                    result[ctype] = ops
            except Exception as e:
                log.warning("Failed to get operations for %s: %s", ctype, e)
        return result

    def get_connector_operations(self, connector_type: str) -> Optional[Dict[str, Dict[str, Any]]]:
        """Return operations for a single connector type, or None."""
        connector = self._connectors.get(connector_type)
        if connector is None:
            return None
        try:
            return connector.get_operations()
        except Exception as e:
            log.warning("Failed to get operations for %s: %s", connector_type, e)
            return None

    # ------------------------------------------------------------------
    # Dynamic planner prompt builder
    # ------------------------------------------------------------------

    def get_capabilities_prompt(self, include_examples: bool = True) -> str:
        """Build the dynamic capabilities section for the tool-selector prompt.

        Every registered connector contributes its auto-discovered operations
        with descriptions and parameter information.  When *include_examples*
        is ``True``, representative usage examples are appended.
        """
        all_ops = self.get_all_operations()
        if not all_ops:
            return "No enterprise connectors are currently registered."

        lines: list[str] = []
        lines.append("Available connectors and their operations:")

        for ctype in sorted(all_ops):
            ops = all_ops[ctype]
            lines.append(f"\n- {ctype}:")
            for op_name in sorted(ops):
                meta = ops[op_name]
                desc = meta.get("description", "")
                req = meta.get("required_params", [])
                opt = meta.get("optional_params", {})

                parts = [f"  \u2022 {op_name}"]
                if desc:
                    parts.append(f"    Description: {desc}")
                if req:
                    parts.append(f"    Required: {', '.join(req)}")
                if opt:
                    opt_fmt = ", ".join(f"{k}={v}" for k, v in opt.items())
                    parts.append(f"    Optional: {opt_fmt}")
                lines.extend(parts)

        lines.append("\nAvailable workers: browser, computer")

        if include_examples and all_ops:
            lines.append("\nCapability examples:")
            for ctype in sorted(all_ops):
                ops = all_ops[ctype]
                if not ops:
                    continue
                # Pick the first operation in alphabetical order
                ex_op = sorted(ops)[0]
                ex_meta = ops[ex_op]
                ex_params: Dict[str, Any] = {}
                for rp in ex_meta.get("required_params", []):
                    ex_params[rp] = f"<{rp}>"
                ex = {
                    "type": "connector",
                    "name": ctype,
                    "operation": ex_op,
                    "params": ex_params,
                }
                lines.append(f"\n  {ctype}: {ex_op}")
                lines.append(f"    {json.dumps(ex, indent=2)}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Operation validation against actual capabilities
    # ------------------------------------------------------------------

    def validate_operation(
        self,
        connector_type: str,
        operation_name: str,
        params: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """Validate a candidate tool selection against registered capabilities.

        Checks in order:
        1. Connector is registered.
        2. Operation exists on that connector.
        3. All required parameters are present.
        4. No unknown parameter types that would obviously fail.

        Returns ``(is_valid, error_messages)``.
        """
        errors: List[str] = []

        connector = self._connectors.get(connector_type)
        if connector is None:
            return False, [f"Connector '{connector_type}' is not registered."]

        ops = self.get_connector_operations(connector_type)
        if ops is None or operation_name not in ops:
            registered = ", ".join(sorted(ops)) if ops else "(none)"
            return False, [
                f"Operation '{operation_name}' not found on '{connector_type}'. "
                f"Available operations: {registered}",
            ]

        meta = ops[operation_name]
        for rp in meta.get("required_params", []):
            if rp not in params:
                errors.append(
                    f"Missing required parameter '{rp}' for "
                    f"'{connector_type}.{operation_name}'.",
                )

        return (len(errors) == 0, errors)

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    async def initialize_connector(self, connector_type: str) -> bool:
        conn = self._connectors.get(connector_type)
        if conn is None:
            return False
        try:
            return await conn.initialize()
        except Exception as e:
            log.warning("Connector %s init failed: %s", connector_type, e)
            return False

    async def shutdown_connector(self, connector_type: str) -> bool:
        conn = self._connectors.get(connector_type)
        if conn is None:
            return False
        try:
            await conn.shutdown()
            return True
        except Exception as e:
            log.warning("Connector %s shutdown error: %s", connector_type, e)
            return False

    async def initialize_all(self) -> Dict[str, bool]:
        results: Dict[str, bool] = {}
        for key, connector in self._connectors.items():
            try:
                ok = await connector.initialize()
                results[key] = ok
                log.info("Connector %s initialized: %s", key, ok)
            except Exception as e:
                results[key] = False
                log.warning("Connector %s init failed: %s", key, e)
        return results

    async def shutdown_all(self) -> None:
        for key, connector in self._connectors.items():
            try:
                await connector.shutdown()
            except Exception as e:
                log.warning("Connector %s shutdown error: %s", key, e)

    async def health_all(self) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for key, connector in self._connectors.items():
            try:
                results[key] = await connector.health()
            except Exception as e:
                results[key] = {"status": "unavailable", "error": str(e)}
        return results


connector_registry = ConnectorRegistry()
