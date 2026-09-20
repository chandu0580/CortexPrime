"""Start the governed plane in this process: loops, connector health, metrics.

Phase 11.1-K. Until now the governed loops (signal fabric, investigator,
remediator) started only inside ``backend.main`` -- the V1 monolith, whose image
carries torch, Playwright and a browser -- so the governed product could not be
deployed without it. This module is the one place the plane starts, called by
both ``backend.main`` (unchanged behaviour) and the product server
(``backend.api.product.server``, the slim governed runtime a Helm chart runs).

It also absorbs configuration the operator should never have had to repeat:
the signal, investigation and remediation loops each read their own tenant,
namespace and environment variables, and all of them must equal the one
connection. ``apply_connection_defaults`` derives them from the connection
(``CORTEX_KUBERNETES_TENANT`` / ``_NAMESPACE``) and the runtime environment,
and only where the operator did not set them explicitly.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

__all__ = ["GovernedPlane", "apply_connection_defaults", "start_governed_plane",
           "validate_governed_environment"]

log = logging.getLogger(__name__)


def apply_connection_defaults(environ: Optional[dict] = None) -> dict:
    """Fill the per-loop variables from the one connection. Returns what it set."""
    env = os.environ if environ is None else environ
    tenant = (env.get("CORTEX_KUBERNETES_TENANT") or "").strip()
    namespace = (env.get("CORTEX_KUBERNETES_NAMESPACE") or "").strip()
    runtime_env = (env.get("CORTEX_DURABLE_ENV") or "development").strip().lower()
    derived = {}
    if tenant and namespace:
        derived.update({"CORTEX_SIGNAL_TENANT_ID": tenant, "CORTEX_SIGNAL_NAMESPACE": namespace})
    derived["CORTEX_REMEDIATION_ENVIRONMENT"] = runtime_env
    applied = {}
    for key, value in derived.items():
        if not (env.get(key) or "").strip():
            env[key] = value
            applied[key] = value
    return applied


def validate_governed_environment(environ: Optional[dict] = None) -> list:
    """Every configuration problem, each naming the exact variable to fix.

    Empty means the configuration is coherent; it does not mean every provider
    is reachable (that is connector health's job).
    """
    env = os.environ if environ is None else environ
    problems = []
    runtime_env = (env.get("CORTEX_DURABLE_ENV") or "development").strip().lower()
    if not (env.get("CORTEX_DURABLE_URL") or "").strip():
        problems.append("CORTEX_DURABLE_URL is required: the governed runtime has no durable store")
    if runtime_env not in ("development", "staging", "production"):
        problems.append("CORTEX_DURABLE_ENV must be development, staging or production")
    secret = (env.get("JWT_SECRET_KEY") or "").strip()
    if len(secret) < 32:
        problems.append("JWT_SECRET_KEY (32+ characters) is required: the product API cannot "
                        "verify a caller without it")
    tenant = (env.get("CORTEX_KUBERNETES_TENANT") or "").strip()
    namespace = (env.get("CORTEX_KUBERNETES_NAMESPACE") or "").strip()
    if bool(tenant) != bool(namespace):
        problems.append("CORTEX_KUBERNETES_TENANT and CORTEX_KUBERNETES_NAMESPACE are set together "
                        "(one names who, the other where)")
    for key, want in (("CORTEX_SIGNAL_TENANT_ID", tenant), ("CORTEX_SIGNAL_NAMESPACE", namespace)):
        have = (env.get(key) or "").strip()
        if want and have and have != want:
            problems.append(f"{key}={have!r} contradicts the connection ({want!r}); unset it")
    if tenant:
        mode = (env.get("CORTEX_KUBERNETES_CREDENTIALS") or "vault").strip().lower()
        if mode == "vault":
            if not (env.get("CORTEX_VAULT_ADDR") or "").strip():
                problems.append("CORTEX_VAULT_ADDR is required when Kubernetes credentials come from Vault")
            if not ((env.get("VAULT_TOKEN") or "").strip()
                    or (env.get("CORTEX_VAULT_AUTH_ROLE") or "").strip()):
                problems.append("set CORTEX_VAULT_AUTH_ROLE (Vault Kubernetes auth) or VAULT_TOKEN")
        elif runtime_env == "production":
            problems.append("CORTEX_KUBERNETES_CREDENTIALS=static is refused in production")
        for prefix in ("CORTEX_ROLLBACK", "CORTEX_RESTART"):
            url = (env.get(f"{prefix}_WORKER_URL") or "").strip()
            digest = (env.get(f"{prefix}_IMPL_DIGEST") or "").strip()
            if bool(url) != bool(digest):
                problems.append(f"{prefix}_WORKER_URL and {prefix}_IMPL_DIGEST are set together")
    if any(k.startswith("CORTEX_RATE_LIMIT_") for k in env):
        # Built later, inside the connectivity graph, so an incoherent budget
        # used to surface as a boot traceback and a CrashLoopBackOff (11.1-K).
        from backend.contexts.execution.infrastructure.rate_limiting import RateLimitPolicy

        try:
            RateLimitPolicy.from_env(env)
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            problems.append(f"CORTEX_RATE_LIMIT_*: {exc}")
    for prefix in ("CORTEX_INVESTIGATION", "CORTEX_REMEDIATION"):
        provider = (env.get(f"{prefix}_MODEL_PROVIDER") or "").strip()
        if provider == "openai-compatible":
            missing = [k for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL") if not (env.get(k) or "").strip()]
            if missing:
                # Without these the adapter reports "not configured" and every
                # proposal silently degrades to recommendation-only (11.1-K run 11).
                problems.append(f"{prefix}_MODEL_PROVIDER=openai-compatible needs "
                                + ", ".join(missing))
    for key in ("CORTEX_TLS_CA_BUNDLE", "CORTEX_KUBERNETES_CA_BUNDLE", "CORTEX_WORKER_CA_BUNDLE",
                "CORTEX_VAULT_CA_BUNDLE"):
        path = (env.get(key) or "").strip()
        if path and not os.path.exists(path):
            problems.append(f"{key} names {path}, which does not exist")
    return problems


@dataclass
class GovernedPlane:
    runtime: Any
    remediator: Any = None
    investigator: Any = None
    signal_worker: Any = None
    health: Any = None


def start_governed_plane(runtime: Any) -> GovernedPlane:
    """Start the loops and connector health over an already-started runtime."""
    from backend.api.application_runtime import runtime_metrics
    from backend.api.connector_health import ConnectorHealth, ConnectorHealthMonitor
    from backend.api.investigation_runtime import start_embedded_investigator
    from backend.api.remediation_runtime import start_embedded_remediator
    from backend.signal.worker import start_embedded

    plane = GovernedPlane(runtime=runtime)
    plane.remediator = start_embedded_remediator(runtime)
    plane.investigator = start_embedded_investigator(
        runtime, on_outcome=plane.remediator.offer if plane.remediator else None)
    plane.signal_worker = start_embedded(
        runtime, handoff=plane.investigator.handoff if plane.investigator else None)

    monitor = ConnectorHealthMonitor(
        interval_seconds=float(os.getenv("CORTEX_CONNECTOR_HEALTH_INTERVAL", "600")),
        metrics=runtime_metrics())
    for manifest in getattr(runtime, "manifests", ()):
        factory = getattr(runtime, "health_probe_factories", {}).get(manifest.connector_id)
        probe = factory(runtime) if factory is not None else None
        if probe is None:
            monitor.set_static(ConnectorHealth.disabled(
                manifest.connector_id, "no health probe is composed for this connector"))
        else:
            monitor.register(manifest.connector_id, probe)
    monitor.start()
    runtime.connector_health = monitor
    plane.health = monitor

    port = int(os.getenv("CORTEX_METRICS_PORT", "0") or 0)
    if port:
        try:
            from prometheus_client import start_http_server

            start_http_server(port)
            log.info("governed plane metrics on :%s", port)
        except Exception:  # noqa: BLE001 - metrics never stop the plane
            log.warning("metrics endpoint could not start on :%s", port, exc_info=True)
    log.info("governed plane started: remediator=%s investigator=%s signal=%s connectors=%s",
             bool(plane.remediator), bool(plane.investigator), bool(plane.signal_worker),
             [m.connector_id for m in getattr(runtime, "manifests", ())])
    return plane
