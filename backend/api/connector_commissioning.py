"""Boot-time connector commissioning: a manifest in, durable capabilities out.

Phase 11.1-K (connector reality audit, section 11: "boot-time commissioning:
MISSING"). Before this module a governed process had no capabilities until a
harness script or an operator registered them by hand, and the signal worker
refused to start until someone had. Now the runtime commissions, at startup,
exactly the capabilities of every connector it composed:

    manifest capability  --(its provider's catalog is composed here?)-->
        register (full contract: schemas, permissions, timeout, retry,
        compensation) -> validate -> enable -> trust verified -> trusted
    manifest provider    --> admit the worker(s) serving it

Properties
------------
* **Idempotent.** The registry accepts an identical contract for an existing
  version and refuses a different one. Re-running commissioning on every boot,
  on every replica, is therefore safe and cheap.
* **No silent drift.** If a stored contract differs from the manifest for the
  same version, that capability is reported as a CONFLICT and left exactly as
  stored -- the fix is a version bump, a reviewed change -- and connector
  health reports MISCONFIGURED rather than running a contract nobody shipped.
* **Only what is composed.** A capability whose provider this process did not
  compose (no worker URL configured, no credential) is SKIPPED, with the reason,
  instead of being registered as usable.
* **Grants nothing.** Registering a capability authorizes no one to invoke it:
  authorization, approval and the gateway still decide every invocation.

Generic: nothing here knows about Kubernetes. The Kubernetes manifest lives in
``backend.api.kubernetes_connector``; GitHub will ship its own.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.api.connector_schema import input_schema_for, output_schema_for, schema_ref
from backend.contracts.connector_manifest import ConnectorManifest

__all__ = ["CommissioningReport", "commission_connector", "admit_worker", "commissioned_capability"]

log = logging.getLogger(__name__)

REGISTRAR_PRINCIPAL = "cortexprime.connector-registrar"


@dataclass
class CommissioningReport:
    connector_id: str
    commissioned: list = field(default_factory=list)
    already_current: list = field(default_factory=list)
    skipped: dict = field(default_factory=dict)
    conflicts: dict = field(default_factory=dict)
    failed: dict = field(default_factory=dict)
    workers_admitted: list = field(default_factory=list)

    @property
    def available(self) -> tuple:
        return tuple(self.commissioned + self.already_current)

    @property
    def ok(self) -> bool:
        return not self.conflicts and not self.failed and bool(self.available)

    def to_dict(self) -> dict:
        return {"connector": self.connector_id, "ok": self.ok,
                "available": list(self.available), "commissioned": list(self.commissioned),
                "already_current": list(self.already_current), "skipped": dict(self.skipped),
                "conflicts": dict(self.conflicts), "failed": dict(self.failed),
                "workers_admitted": list(self.workers_admitted)}


def _platform_context(reason: str) -> Any:
    from backend.platform.context import ExecutionContext

    return ExecutionContext.platform_internal(
        reason=reason, component="cortexprime.connector-registrar", source="lifecycle")


def admit_worker(runtime: Any, context: Any, worker_id: str) -> bool:
    """Validate, enable, trust and make available one composed worker.

    Process-local operational state (the worker directory lives in the
    process), not governance: the durable capability registry is untouched.
    Every step is idempotent; a step that refuses because the worker is
    already in that state is not an error.
    """
    # The one existing admission sequence (validate, enable, trust verified ->
    # trusted, available), reused rather than restated.
    from backend.signal.worker import _commission_connector_worker

    directory = runtime.connectivity.directory
    _commission_connector_worker(runtime, context, worker_id=worker_id)
    try:
        entry = directory.entry(context, worker_id=worker_id, tenant_id="")
    except Exception:  # noqa: BLE001
        return False
    return bool(getattr(entry, "accepts_work", False)) or bool(
        getattr(getattr(entry, "availability", None), "value", "") == "available")


def _register_command(capability: Any, spec: Any, environment: str, isolation_tier: str) -> Any:
    from backend.contexts.connectivity.application.commands import RegisterCapability

    profile = capability.profile
    return RegisterCapability(
        capability_id=capability.capability_id,
        version=capability.version,
        name=capability.operation,
        description=capability.description,
        provider=capability.provider,
        interface="connector",
        side_effect_class=profile.side_effect_class.value,
        effect_semantics=profile.effect_semantics.value,
        isolation_tier=isolation_tier,
        code_trust="fixed",
        owner_id=REGISTRAR_PRINCIPAL,
        owner_kind="platform",
        tenancy="platform",
        source="internal",
        supported_environments=(environment,),
        provider_operation=capability.operation,
        category=capability.category,
        input_schema=schema_ref(f"{capability.operation}.input", input_schema_for(spec)),
        output_schema=schema_ref(f"{capability.operation}.output", output_schema_for(spec)),
        required_permissions=tuple(capability.required_permissions),
        idempotency_supported=not capability.mutates,
        retryable=not capability.mutates,
        compensation_capability=getattr(profile, "compensation", None),
        timeout_seconds=int(max(1, round(float(profile.timeout_seconds)))),
    )


def commission_connector(
    runtime: Any,
    manifest: ConnectorManifest,
    *,
    environment: str,
    isolation_tier: str = "contained",
    context: Optional[Any] = None,
) -> CommissioningReport:
    """Commission ``manifest``'s capabilities that this process composed."""
    from backend.contexts.connectivity.application.commands import (
        EnableCapability,
        GetCapability,
        SetCapabilityTrust,
        ValidateCapability,
    )

    ctx = context or _platform_context(f"commission connector {manifest.connector_id}")
    report = CommissioningReport(connector_id=manifest.connector_id)
    catalogs = dict(getattr(runtime.connectivity, "catalogs", {}) or {})

    for capability in manifest.capabilities:
        cid = capability.capability_id
        catalog = catalogs.get(capability.provider)
        spec = catalog.get(capability.operation) if catalog is not None else None
        if spec is None:
            report.skipped[cid] = (
                f"provider {capability.provider!r} is not composed in this process"
                if catalog is None else
                f"{capability.provider} does not expose {capability.operation}")
            continue
        command = _register_command(capability, spec, environment, isolation_tier)
        try:
            existing = runtime.capabilities.get(ctx, GetCapability(capability_id=cid,
                                                                   version=capability.version))
        except Exception:  # noqa: BLE001 - absent
            existing = None
        try:
            runtime.capabilities.register(ctx, command)
        except Exception as exc:  # noqa: BLE001
            if existing is not None:
                report.conflicts[cid] = (
                    "a different contract is already registered for this version "
                    f"({type(exc).__name__}); bump the version to change it")
            else:
                report.failed[cid] = f"registration refused: {type(exc).__name__}: {exc}"[:300]
            continue
        for step in (
            lambda: runtime.capabilities.validate(ctx, ValidateCapability(
                capability_id=cid, version=capability.version)),
            lambda: runtime.capabilities.enable(ctx, EnableCapability(
                capability_id=cid, version=capability.version)),
            lambda: runtime.capabilities.set_trust(ctx, SetCapabilityTrust(
                capability_id=cid, version=capability.version, trust="verified",
                reason=f"shipped with connector {manifest.connector_id} {manifest.version}")),
            lambda: runtime.capabilities.set_trust(ctx, SetCapabilityTrust(
                capability_id=cid, version=capability.version, trust="trusted",
                reason=f"shipped with connector {manifest.connector_id} {manifest.version}")),
        ):
            try:
                step()
            except Exception as exc:  # noqa: BLE001 - already in that state
                log.debug("capability %s commissioning step: %s", cid, type(exc).__name__)
        stored = runtime.capabilities.get(ctx, GetCapability(capability_id=cid,
                                                             version=capability.version))
        usable = _is_usable(stored)
        if not usable:
            report.failed[cid] = f"stored but not usable ({_state_of(stored)})"
        elif existing is not None and _is_usable(existing):
            report.already_current.append(cid)
        else:
            report.commissioned.append(cid)

    directory = runtime.connectivity.directory
    try:
        entries = directory.all_entries(ctx, tenant_id="")
    except Exception:  # noqa: BLE001
        entries = ()
    wanted = set(manifest.providers)
    for entry in entries:
        providers = set(getattr(entry.implementation, "supported_providers", ()) or ())
        if providers & wanted and admit_worker(runtime, ctx, entry.worker_id):
            report.workers_admitted.append(entry.worker_id)
    log.info("connector %s commissioned: %s", manifest.connector_id, report.to_dict())
    return report


def commissioned_capability(runtime: Any, capability_id: str, version: int = 1) -> Any:
    """The stored definition of a commissioned capability, or ``None``."""
    from backend.contexts.connectivity.application.commands import GetCapability

    ctx = _platform_context(f"capability lookup {capability_id}")
    try:
        return runtime.capabilities.get(ctx, GetCapability(capability_id=capability_id,
                                                           version=version))
    except Exception:  # noqa: BLE001 - not commissioned
        return None


def _state_of(definition: Any) -> str:
    status = getattr(getattr(definition, "status", None), "value", None)
    trust = getattr(getattr(definition, "trust", None), "value", None)
    return f"status={status} trust={trust}"


def _is_usable(definition: Any) -> bool:
    if definition is None:
        return False
    status = getattr(getattr(definition, "status", None), "value", "")
    trust = getattr(getattr(definition, "trust", None), "value", "")
    return status == "enabled" and trust == "trusted"
