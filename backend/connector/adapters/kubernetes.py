from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

import kubernetes
import kubernetes.client
import kubernetes.config
from kubernetes.client.rest import ApiException

from backend.connector.adapter.interfaces import AdapterHealthStatus, AdapterResult, ConnectorAdapter
from backend.connector.models import Capability

log = logging.getLogger(__name__)

KUBECONFIG_PATH_ENV = "KUBECONFIG"
KUBECONFIG_DEFAULT = str(Path.home() / ".kube" / "config")
MAX_RETRIES = 2
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class KubernetesAdapter(ConnectorAdapter):

    @property
    def connector_type(self) -> str:
        return "kubernetes"

    @property
    def connector_name(self) -> str:
        return "Kubernetes"

    @property
    def adapter_version(self) -> str:
        return "1.0.0"

    def __init__(self) -> None:
        self._contexts: dict[str, kubernetes.client.ApiClient] = {}
        self._default_context: str = ""
        self._initialized: bool = False

    async def initialize(self) -> bool:
        try:
            kubernetes.config.load_incluster_config()
            self._default_context = "in-cluster"
            self._contexts["in-cluster"] = kubernetes.client.ApiClient()
            self._initialized = True
            log.info("Kubernetes adapter initialized — in-cluster config")
            return True
        except kubernetes.config.ConfigException:
            pass

        kc_path = os.getenv(KUBECONFIG_PATH_ENV, KUBECONFIG_DEFAULT)
        try:
            kubernetes.config.load_kube_config(config_file=kc_path)
            contexts, active_context = kubernetes.config.list_kube_config_contexts(config_file=kc_path)
            self._default_context = active_context.get("name", "default")
            for ctx in contexts:
                name = ctx.get("name", "default")
                try:
                    client = kubernetes.config.new_client_from_config(config_file=kc_path, context=name)
                    self._contexts[name] = client
                except Exception as exc:
                    log.warning("K8s context %s failed: %s", name, exc)
            if self._contexts:
                self._initialized = True
                log.info("Kubernetes adapter initialized — %d context(s) from %s", len(self._contexts), kc_path)
                return True
        except Exception as exc:
            log.warning("Kubernetes kubeconfig load failed: %s", exc)

        log.warning("Kubernetes adapter unavailable — no in-cluster or kubeconfig found")
        return False

    async def health_check(self) -> AdapterHealthStatus:
        if not self._initialized or not self._contexts:
            return AdapterHealthStatus.UNHEALTHY
        try:
            v1 = kubernetes.client.CoreV1Api(self._client(""))
            await self._api_call(v1.list_node, _request_timeout=10)
            return AdapterHealthStatus.HEALTHY
        except ApiException as e:
            if e.status in (401, 403):
                return AdapterHealthStatus.DEGRADED
            return AdapterHealthStatus.DEGRADED
        except Exception:
            return AdapterHealthStatus.UNHEALTHY

    async def capabilities(self) -> list[Capability]:
        return [
            Capability.OBSERVE,
            Capability.DEPLOY,
            Capability.SCALE,
            Capability.RESTART,
            Capability.EXECUTE,
        ]

    async def execute(self, capability: Capability, inputs: dict[str, Any],
                      timeout_seconds: Optional[int] = None) -> AdapterResult:
        start = time.monotonic()

        if capability == Capability.OBSERVE:
            return await self._observe(inputs, start)
        if capability == Capability.DEPLOY:
            return await self._deploy(inputs, start)
        if capability == Capability.SCALE:
            return await self._scale(inputs, start)
        if capability == Capability.RESTART:
            return await self._restart(inputs, start)
        if capability == Capability.EXECUTE:
            return await self._execute_action(inputs, start)

        return AdapterResult(
            success=False,
            error=f"Unsupported capability: {capability.value}",
            duration_ms=(time.monotonic() - start) * 1000,
        )

    async def shutdown(self) -> None:
        self._initialized = False
        for name, client in self._contexts.items():
            try:
                client.close()
            except Exception:
                pass
        self._contexts.clear()
        log.info("Kubernetes adapter shut down")

    async def metadata(self) -> dict[str, Any]:
        base = await super().metadata()
        base["contexts"] = list(self._contexts.keys())
        base["default_context"] = self._default_context
        return base

    def _client(self, context: str = "") -> kubernetes.client.ApiClient:
        ctx = context or self._default_context
        client = self._contexts.get(ctx)
        if not client:
            raise RuntimeError(f"Kubernetes context '{ctx}' not found")
        return client

    async def _api_call(self, func, *args, **kwargs):
        for attempt in range(MAX_RETRIES + 1):
            try:
                return await asyncio.to_thread(func, *args, **kwargs)
            except ApiException as e:
                if e.status in RETRYABLE_STATUSES and attempt < MAX_RETRIES:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                raise
            except Exception:
                raise

    async def _observe(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        namespace = inputs.get("namespace", "")
        context = inputs.get("context", "")
        try:
            v1 = kubernetes.client.CoreV1Api(self._client(context))
            ns = namespace or None
            if ns:
                pod_list = await self._api_call(v1.list_namespaced_pod, ns, _request_timeout=30)
            else:
                pod_list = await self._api_call(v1.list_pod_for_all_namespaces, _request_timeout=30)
            pods = [{"name": p.metadata.name, "namespace": p.metadata.namespace, "phase": p.status.phase if p.status else "Unknown"} for p in pod_list.items]
            node_list = await self._api_call(v1.list_node, _request_timeout=10)
            nodes = [{"name": n.metadata.name, "status": "ready" if any(c.status == "True" and c.type == "Ready" for c in (n.status.conditions or [])) else "not_ready"} for n in node_list.items]
            return AdapterResult(success=True, outputs={"pods_count": len(pods), "pods": pods[:50], "nodes_count": len(nodes), "nodes": nodes}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _deploy(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        namespace = inputs.get("namespace", "default")
        name = inputs.get("name")
        image = inputs.get("image")
        replicas = inputs.get("replicas", 1)
        context = inputs.get("context", "")
        if not name or not image:
            return AdapterResult(success=False, error="Missing 'name' or 'image'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            apps = kubernetes.client.AppsV1Api(self._client(context))
            body = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": name, "namespace": namespace}, "spec": {"replicas": replicas, "selector": {"matchLabels": {"app": name}}, "template": {"metadata": {"labels": {"app": name}}, "spec": {"containers": [{"name": name, "image": image}]}}}}
            dep = await self._api_call(apps.create_namespaced_deployment, namespace, body, _request_timeout=30)
            return AdapterResult(success=True, outputs={"name": dep.metadata.name, "namespace": namespace, "replicas": replicas}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _scale(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        namespace = inputs.get("namespace", "default")
        name = inputs.get("name")
        replicas = inputs.get("replicas")
        context = inputs.get("context", "")
        if not name or replicas is None:
            return AdapterResult(success=False, error="Missing 'name' or 'replicas'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            apps = kubernetes.client.AppsV1Api(self._client(context))
            body = {"spec": {"replicas": replicas}}
            dep = await self._api_call(apps.patch_namespaced_deployment_scale, name, namespace, body, _request_timeout=30)
            return AdapterResult(success=True, outputs={"name": name, "namespace": namespace, "replicas": dep.spec.replicas if dep.spec else replicas}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _restart(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        namespace = inputs.get("namespace", "default")
        name = inputs.get("name")
        context = inputs.get("context", "")
        if not name:
            return AdapterResult(success=False, error="Missing 'name'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            apps = kubernetes.client.AppsV1Api(self._client(context))
            dep = await self._api_call(apps.read_namespaced_deployment, name, namespace, _request_timeout=30)
            annotations = dep.metadata.annotations or {}
            from datetime import datetime, timezone
            annotations["kubectl.kubernetes.io/restartedAt"] = datetime.now(timezone.utc).isoformat()
            body = {"spec": {"template": {"metadata": {"annotations": annotations}}}}
            await self._api_call(apps.patch_namespaced_deployment, name, namespace, body, _request_timeout=30)
            return AdapterResult(success=True, outputs={"name": name, "namespace": namespace, "action": "restarted"}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _execute_action(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        namespace = inputs.get("namespace", "default")
        name = inputs.get("name")
        command = inputs.get("command")
        context = inputs.get("context", "")
        if not name or not command:
            return AdapterResult(success=False, error="Missing 'name' or 'command'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            v1 = kubernetes.client.CoreV1Api(self._client(context))
            pod = await self._api_call(v1.read_namespaced_pod, name, namespace, _request_timeout=10)
            return AdapterResult(success=True, outputs={"name": name, "namespace": namespace, "phase": pod.status.phase if pod.status else "Unknown", "node": pod.spec.node_name if pod.spec else ""}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)
