"""Kubernetes connector — official Python client wrapper with multi-cluster support.

Follows BaseConnector pattern. Uses `asyncio.to_thread` to wrap blocking
`kubernetes` client calls so the connector remains async-safe.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import kubernetes
import kubernetes.client
import kubernetes.config
import kubernetes.utils
from kubernetes.client.rest import ApiException

from backend.connectors.base import BaseConnector

log = logging.getLogger(__name__)

KUBECONFIG_PATH_ENV = "KUBECONFIG"
KUBECONFIG_DEFAULT = str(Path.home() / ".kube" / "config")
IN_CLUSTER_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRIES = 2


class KubernetesConnector(BaseConnector):
    """Connector to one or more Kubernetes clusters.

    Supports in-cluster (service-account) and out-of-cluster (kubeconfig) auth.
    Multi-cluster: if kubeconfig has multiple contexts, ``list_clusters()``
    returns them all and each method accepts an optional *context* parameter.
    """

    connector_name = "Kubernetes"
    connector_type = "kubernetes"

    def __init__(self) -> None:
        self._contexts: Dict[str, kubernetes.client.ApiClient] = {}
        self._default_context: str = ""
        self._available: bool = False

    # ---- Lifecycle ------------------------------------------------------------

    def configure(self, credentials: Dict[str, str]) -> None:
        super().configure(credentials)
        kc = credentials.get("kubeconfig_path", "")
        if kc:
            os.environ[KUBECONFIG_PATH_ENV] = kc

    async def initialize(self) -> bool:
        try:
            # Try in-cluster config first (running inside a K8s pod)
            kubernetes.config.load_incluster_config()
            self._default_context = "in-cluster"
            self._contexts["in-cluster"] = kubernetes.client.ApiClient()
            self._available = True
            log.info("Kubernetes connector initialized — in-cluster config")
            return True
        except kubernetes.config.ConfigException:
            pass

        # Fall back to kubeconfig
        kc_path = os.getenv(KUBECONFIG_PATH_ENV, KUBECONFIG_DEFAULT)
        try:
            kubernetes.config.load_kube_config(config_file=kc_path)
            contexts, active_context = kubernetes.config.list_kube_config_contexts(
                config_file=kc_path,
            )
            self._default_context = active_context.get("name", "default")
            for ctx in contexts:
                name = ctx.get("name", "default")
                try:
                    client = kubernetes.config.new_client_from_config(
                        config_file=kc_path, context=name,
                    )
                    self._contexts[name] = client
                except Exception as exc:
                    log.warning("K8s context %s failed: %s", name, exc)

            if self._contexts:
                self._available = True
                log.info(
                    "Kubernetes connector initialized — %d context(s) from %s",
                    len(self._contexts), kc_path,
                )
                return True
        except Exception as exc:
            log.warning("Kubernetes kubeconfig load failed: %s", exc)

        self._available = False
        log.warning("Kubernetes connector unavailable — no in-cluster or kubeconfig found")
        return False

    async def shutdown(self) -> bool:
        self._available = False
        for name, client in self._contexts.items():
            try:
                client.close()
            except Exception:
                pass
        self._contexts.clear()
        return True

    async def health(self) -> Dict[str, Any]:
        status = "available" if self._available else "unavailable"
        clusters = self._contexts if self._available else {}
        return {
            "status": status,
            "connector": self.connector_type,
            "clusters": list(clusters.keys()),
            "default_context": self._default_context,
            "auth_method": "in-cluster" if "in-cluster" in clusters else "kubeconfig",
        }

    # ---- Internal helpers -----------------------------------------------------

    def _client(self, context: str = "") -> kubernetes.client.ApiClient:
        ctx = context or self._default_context
        client = self._contexts.get(ctx)
        if not client:
            raise RuntimeError(f"Kubernetes context '{ctx}' not found")
        return client

    async def _api_call(self, func, *args, **kwargs):
        """Run a blocking kubernetes-client call in a thread pool."""
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

    # ---- Cluster discovery ----------------------------------------------------

    async def list_clusters(self) -> List[Dict[str, Any]]:
        return await self._execute(
            "list_clusters", "clusters",
            self._list_clusters,
        )

    async def _list_clusters(self) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for ctx_name in self._contexts:
            v1 = kubernetes.client.CoreV1Api(self._client(ctx_name))
            try:
                nodes = await self._api_call(v1.list_node)
                node_items = nodes.items if nodes else []
                ready = sum(
                    1 for n in node_items
                    if any(
                        c.status == "True" and c.type == "Ready"
                        for c in n.status.conditions or []
                    )
                )
                version = ""
                if node_items:
                    version = node_items[0].status.node_info.kubelet_version if node_items[0].status and node_items[0].status.node_info else ""
                results.append({
                    "name": ctx_name,
                    "context": ctx_name,
                    "provider": "kubernetes",
                    "version": version,
                    "nodes_total": len(node_items),
                    "nodes_ready": ready,
                    "status": "healthy" if ready == len(node_items) else "degraded",
                })
            except Exception as exc:
                results.append({
                    "name": ctx_name,
                    "context": ctx_name,
                    "provider": "kubernetes",
                    "version": "",
                    "nodes_total": 0,
                    "nodes_ready": 0,
                    "status": "unreachable",
                    "error": str(exc),
                })
        return results

    async def get_cluster(self, context: str = "") -> Dict[str, Any]:
        return await self._execute(
            "get_cluster", "clusters",
            self._get_cluster, context,
        )

    async def _get_cluster(self, context: str = "") -> Dict[str, Any]:
        clusters = await self._list_clusters()
        ctx = context or self._default_context
        for c in clusters:
            if c["context"] == ctx:
                return c
        return {"name": ctx, "status": "not_found"}

    # ---- Nodes ----------------------------------------------------------------

    async def list_nodes(self, context: str = "") -> List[Dict[str, Any]]:
        return await self._execute(
            "list_nodes", "nodes",
            self._list_nodes, context,
        )

    async def _list_nodes(self, context: str = "") -> List[Dict[str, Any]]:
        v1 = kubernetes.client.CoreV1Api(self._client(context))
        node_list = await self._api_call(v1.list_node)
        results: List[Dict[str, Any]] = []
        for n in node_list.items:
            ready = any(
                c.status == "True" and c.type == "Ready"
                for c in n.status.conditions or []
            )
            alloc = n.status.allocatable or {}
            cpu_total = self._parse_quantity(alloc.get("cpu", "0"))
            mem_total = self._parse_quantity(alloc.get("memory", "0"))
            cap = n.status.capacity or {}
            cpu_cap = self._parse_quantity(cap.get("cpu", "0"))
            mem_cap = self._parse_quantity(cap.get("memory", "0"))

            results.append({
                "name": n.metadata.name,
                "status": "ready" if ready else "not_ready",
                "kubernetes_status": n.status.conditions[-1].type if n.status.conditions else "Unknown",
                "cpu_capacity": cpu_cap,
                "cpu_allocatable": cpu_total,
                "memory_capacity_bytes": mem_cap,
                "memory_allocatable_bytes": mem_total,
                "kubelet_version": n.status.node_info.kubelet_version if n.status.node_info else "",
                "os_image": n.status.node_info.os_image if n.status.node_info else "",
                "architecture": n.status.node_info.architecture if n.status.node_info else "",
                "labels": n.metadata.labels or {},
                "created_at": n.metadata.creation_timestamp.isoformat() if n.metadata.creation_timestamp else "",
            })
        return results

    async def get_node(self, name: str, context: str = "") -> Dict[str, Any]:
        return await self._execute(
            "get_node", "nodes",
            self._get_node, name, context,
        )

    async def _get_node(self, name: str, context: str = "") -> Dict[str, Any]:
        v1 = kubernetes.client.CoreV1Api(self._client(context))
        n = await self._api_call(v1.read_node, name)
        ready = any(
            c.status == "True" and c.type == "Ready"
            for c in n.status.conditions or []
        )
        alloc = n.status.allocatable or {}
        cap = n.status.capacity or {}
        cpu_cap = self._parse_quantity(cap.get("cpu", "0"))
        mem_cap = self._parse_quantity(cap.get("memory", "0"))
        cpu_alloc = self._parse_quantity(alloc.get("cpu", "0"))
        mem_alloc = self._parse_quantity(alloc.get("memory", "0"))

        return {
            "name": n.metadata.name,
            "status": "ready" if ready else "not_ready",
            "cpu_capacity": cpu_cap,
            "cpu_allocatable": cpu_alloc,
            "memory_capacity_bytes": mem_cap,
            "memory_allocatable_bytes": mem_alloc,
            "kubelet_version": n.status.node_info.kubelet_version if n.status.node_info else "",
            "os_image": n.status.node_info.os_image if n.status.node_info else "",
            "architecture": n.status.node_info.architecture if n.status.node_info else "",
            "labels": n.metadata.labels or {},
            "annotations": n.metadata.annotations or {},
            "created_at": n.metadata.creation_timestamp.isoformat() if n.metadata.creation_timestamp else "",
            "conditions": [
                {"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
                for c in (n.status.conditions or [])
            ],
        }

    # ---- Pods -----------------------------------------------------------------

    async def list_pods(
        self, namespace: str = "", context: str = "", label_selector: str = "",
    ) -> List[Dict[str, Any]]:
        return await self._execute(
            "list_pods", "pods",
            self._list_pods, namespace, context, label_selector,
        )

    async def _list_pods(
        self, namespace: str = "", context: str = "", label_selector: str = "",
    ) -> List[Dict[str, Any]]:
        v1 = kubernetes.client.CoreV1Api(self._client(context))
        ns = namespace or None
        kwargs: Dict[str, Any] = {}
        if label_selector:
            kwargs["label_selector"] = label_selector

        if ns:
            pod_list = await self._api_call(v1.list_namespaced_pod, ns, **kwargs)
        else:
            pod_list = await self._api_call(v1.list_pod_for_all_namespaces, **kwargs)

        results: List[Dict[str, Any]] = []
        for p in pod_list.items:
            container_statuses = []
            oom = False
            crashloop = False
            restarts = 0
            if p.status.container_statuses:
                for cs in p.status.container_statuses:
                    c_info = {
                        "name": cs.name,
                        "ready": cs.ready,
                        "restart_count": cs.restart_count,
                        "state": self._container_state(cs.state) if cs.state else "unknown",
                    }
                    container_statuses.append(c_info)
                    restarts += cs.restart_count
                    if cs.last_state and cs.last_state.terminated and cs.last_state.terminated.reason == "OOMKilled":
                        oom = True
                    if cs.state and cs.state.waiting and cs.state.waiting.reason == "CrashLoopBackOff":
                        crashloop = True

            results.append({
                "name": p.metadata.name,
                "namespace": p.metadata.namespace,
                "phase": p.status.phase if p.status else "Unknown",
                "status": (p.status.phase or "unknown").lower(),
                "restarts": restarts,
                "node_name": p.spec.node_name if p.spec else "",
                "host_ip": p.status.host_ip if p.status else "",
                "pod_ip": p.status.pod_ip if p.status else "",
                "container_statuses": container_statuses,
                "oom_detected": oom,
                "crashloop_detected": crashloop,
                "labels": p.metadata.labels or {},
                "created_at": p.metadata.creation_timestamp.isoformat() if p.metadata.creation_timestamp else "",
            })
        return results

    async def get_pod(self, name: str, namespace: str = "default", context: str = "") -> Dict[str, Any]:
        return await self._execute(
            "get_pod", "pods",
            self._get_pod, name, namespace, context,
        )

    async def _get_pod(self, name: str, namespace: str = "default", context: str = "") -> Dict[str, Any]:
        v1 = kubernetes.client.CoreV1Api(self._client(context))
        p = await self._api_call(v1.read_namespaced_pod, name, namespace)
        container_statuses = []
        oom = False
        crashloop = False
        restarts = 0
        if p.status.container_statuses:
            for cs in p.status.container_statuses:
                c_info = {
                    "name": cs.name,
                    "ready": cs.ready,
                    "restart_count": cs.restart_count,
                    "state": self._container_state(cs.state) if cs.state else "unknown",
                    "image": cs.image,
                    "image_id": cs.image_id,
                }
                container_statuses.append(c_info)
                restarts += cs.restart_count
                if cs.last_state and cs.last_state.terminated and cs.last_state.terminated.reason == "OOMKilled":
                    oom = True
                if cs.state and cs.state.waiting and cs.state.waiting.reason == "CrashLoopBackOff":
                    crashloop = True

        return {
            "name": p.metadata.name,
            "namespace": p.metadata.namespace,
            "phase": p.status.phase if p.status else "Unknown",
            "status": (p.status.phase or "unknown").lower(),
            "restarts": restarts,
            "node_name": p.spec.node_name if p.spec else "",
            "host_ip": p.status.host_ip if p.status else "",
            "pod_ip": p.status.pod_ip if p.status else "",
            "container_statuses": container_statuses,
            "oom_detected": oom,
            "crashloop_detected": crashloop,
            "labels": p.metadata.labels or {},
            "annotations": p.metadata.annotations or {},
            "conditions": [
                {"type": c.type, "status": c.status, "reason": c.reason}
                for c in (p.status.conditions or [])
            ],
            "created_at": p.metadata.creation_timestamp.isoformat() if p.metadata.creation_timestamp else "",
        }

    async def get_pod_logs(
        self, name: str, namespace: str = "default",
        container: str = "", tail_lines: int = 100,
        context: str = "",
    ) -> str:
        return await self._execute(
            "get_pod_logs", "pods",
            self._get_pod_logs, name, namespace, container, tail_lines, context,
        )

    async def _get_pod_logs(
        self, name: str, namespace: str = "default",
        container: str = "", tail_lines: int = 100,
        context: str = "",
    ) -> str:
        v1 = kubernetes.client.CoreV1Api(self._client(context))
        kwargs: Dict[str, Any] = {"tail_lines": tail_lines}
        if container:
            kwargs["container"] = container
        return await self._api_call(v1.read_namespaced_pod_log, name, namespace, **kwargs)

    # ---- Deployments ----------------------------------------------------------

    async def list_deployments(
        self, namespace: str = "", context: str = "",
    ) -> List[Dict[str, Any]]:
        return await self._execute(
            "list_deployments", "deployments",
            self._list_deployments, namespace, context,
        )

    async def _list_deployments(
        self, namespace: str = "", context: str = "",
    ) -> List[Dict[str, Any]]:
        apps = kubernetes.client.AppsV1Api(self._client(context))
        ns = namespace or None
        dep_list = await self._api_call(
            apps.list_deployment_for_all_namespaces if not ns else apps.list_namespaced_deployment,
            *([ns] if ns else []),
        )

        results: List[Dict[str, Any]] = []
        for d in dep_list.items:
            replicas = d.spec.replicas or 0
            available = d.status.available_replicas or 0
            ready = d.status.ready_replicas or 0
            strategy = (d.spec.strategy.type or "RollingUpdate").lower() if d.spec.strategy else "rolling_update"
            condition = d.status.conditions[-1] if d.status.conditions else None
            rollout_status = "available"
            if condition:
                if condition.reason == "Progressing":
                    rollout_status = "progressing"
                elif condition.reason == "NewReplicaSetNotReady":
                    rollout_status = "pending"

            results.append({
                "name": d.metadata.name,
                "namespace": d.metadata.namespace,
                "replicas": replicas,
                "available": available,
                "ready": ready,
                "unavailable": replicas - ready,
                "status": "available" if available >= replicas and replicas > 0 else "degraded",
                "rollout_status": rollout_status,
                "strategy": strategy,
                "image": d.spec.template.spec.containers[0].image if d.spec.template.spec.containers else "",
                "labels": d.metadata.labels or {},
                "created_at": d.metadata.creation_timestamp.isoformat() if d.metadata.creation_timestamp else "",
            })
        return results

    async def get_deployment(self, name: str, namespace: str = "default", context: str = "") -> Dict[str, Any]:
        return await self._execute(
            "get_deployment", "deployments",
            self._get_deployment, name, namespace, context,
        )

    async def _get_deployment(self, name: str, namespace: str = "default", context: str = "") -> Dict[str, Any]:
        apps = kubernetes.client.AppsV1Api(self._client(context))
        d = await self._api_call(apps.read_namespaced_deployment, name, namespace)
        replicas = d.spec.replicas or 0
        available = d.status.available_replicas or 0
        ready = d.status.ready_replicas or 0
        strategy = (d.spec.strategy.type or "RollingUpdate").lower() if d.spec.strategy else "rolling_update"
        condition = d.status.conditions[-1] if d.status.conditions else None
        rollout_status = "available"
        if condition:
            if condition.reason == "Progressing":
                rollout_status = "progressing"
            elif condition.reason == "NewReplicaSetNotReady":
                rollout_status = "pending"

        return {
            "name": d.metadata.name,
            "namespace": d.metadata.namespace,
            "replicas": replicas,
            "available": available,
            "ready": ready,
            "unavailable": replicas - ready,
            "status": "available" if available >= replicas and replicas > 0 else "degraded",
            "rollout_status": rollout_status,
            "strategy": strategy,
            "image": d.spec.template.spec.containers[0].image if d.spec.template.spec.containers else "",
            "labels": d.metadata.labels or {},
            "annotations": d.metadata.annotations or {},
            "conditions": [
                {"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
                for c in (d.status.conditions or [])
            ],
            "created_at": d.metadata.creation_timestamp.isoformat() if d.metadata.creation_timestamp else "",
        }

    # ---- Persistent Volume Claims ---------------------------------------------

    async def list_pvcs(self, namespace: str = "", context: str = "") -> List[Dict[str, Any]]:
        return await self._execute(
            "list_pvcs", "pvcs",
            self._list_pvcs, namespace, context,
        )

    async def _list_pvcs(self, namespace: str = "", context: str = "") -> List[Dict[str, Any]]:
        v1 = kubernetes.client.CoreV1Api(self._client(context))
        ns = namespace or None
        pvc_list = await self._api_call(
            v1.list_persistent_volume_claim_for_all_namespaces if not ns
            else v1.list_namespaced_persistent_volume_claim,
            *([ns] if ns else []),
        )

        results: List[Dict[str, Any]] = []
        for pvc in pvc_list.items:
            cap = pvc.status.capacity or {}
            results.append({
                "name": pvc.metadata.name,
                "namespace": pvc.metadata.namespace,
                "status": (pvc.status.phase or "unknown").lower(),
                "capacity_bytes": self._parse_quantity(cap.get("storage", "0")),
                "volume_name": pvc.spec.volume_name if pvc.spec else "",
                "storage_class": pvc.spec.storage_class_name if pvc.spec else "",
                "access_modes": pvc.spec.access_modes or [],
                "labels": pvc.metadata.labels or {},
                "created_at": pvc.metadata.creation_timestamp.isoformat() if pvc.metadata.creation_timestamp else "",
            })
        return results

    # ---- Services -------------------------------------------------------------

    async def list_services(self, namespace: str = "", context: str = "") -> List[Dict[str, Any]]:
        return await self._execute(
            "list_services", "services",
            self._list_services, namespace, context,
        )

    async def _list_services(self, namespace: str = "", context: str = "") -> List[Dict[str, Any]]:
        v1 = kubernetes.client.CoreV1Api(self._client(context))
        ns = namespace or None
        svc_list = await self._api_call(
            v1.list_service_for_all_namespaces if not ns
            else v1.list_namespaced_service,
            *([ns] if ns else []),
        )
        results: List[Dict[str, Any]] = []
        for svc in svc_list.items:
            results.append({
                "name": svc.metadata.name,
                "namespace": svc.metadata.namespace,
                "type": svc.spec.type if svc.spec else "",
                "cluster_ip": svc.spec.cluster_ip if svc.spec else "",
                "ports": [
                    {"port": p.port, "target_port": str(p.target_port) if p.target_port else "", "protocol": p.protocol or "TCP"}
                    for p in (svc.spec.ports or [])
                ] if svc.spec else [],
                "labels": svc.metadata.labels or {},
                "created_at": svc.metadata.creation_timestamp.isoformat() if svc.metadata.creation_timestamp else "",
            })
        return results

    # ---- Events (cluster-level) -----------------------------------------------

    async def list_events(self, namespace: str = "", context: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        return await self._execute(
            "list_events", "events",
            self._list_events, namespace, context, limit,
        )

    async def _list_events(self, namespace: str = "", context: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        v1 = kubernetes.client.CoreV1Api(self._client(context))
        ns = namespace or None
        evt_list = await self._api_call(
            v1.list_event_for_all_namespaces if not ns
            else v1.list_namespaced_event,
            *([ns] if ns else []),
        )
        results: List[Dict[str, Any]] = []
        for e in (evt_list.items or [])[:limit]:
            results.append({
                "type": e.type,
                "reason": e.reason,
                "message": e.message,
                "source": e.source.component if e.source else "",
                "involved_object": {
                    "kind": e.involved_object.kind if e.involved_object else "",
                    "name": e.involved_object.name if e.involved_object else "",
                    "namespace": e.involved_object.namespace if e.involved_object else "",
                },
                "count": e.count,
                "first_timestamp": e.first_timestamp.isoformat() if e.first_timestamp else "",
                "last_timestamp": e.last_timestamp.isoformat() if e.last_timestamp else "",
            })
        return results

    # ---- Namespaces -----------------------------------------------------------

    async def list_namespaces(self, context: str = "") -> List[Dict[str, Any]]:
        return await self._execute(
            "list_namespaces", "namespaces",
            self._list_namespaces, context,
        )

    async def _list_namespaces(self, context: str = "") -> List[Dict[str, Any]]:
        v1 = kubernetes.client.CoreV1Api(self._client(context))
        ns_list = await self._api_call(v1.list_namespace)
        return [
            {
                "name": ns.metadata.name,
                "status": ns.status.phase if ns.status else "Active",
                "labels": ns.metadata.labels or {},
                "created_at": ns.metadata.creation_timestamp.isoformat() if ns.metadata.creation_timestamp else "",
            }
            for ns in ns_list.items
        ]

    # ---- Helpers --------------------------------------------------------------

    @staticmethod
    def _container_state(state) -> str:
        if state.running:
            return "running"
        if state.waiting:
            reason = state.waiting.reason or "waiting"
            return reason.lower()
        if state.terminated:
            reason = state.terminated.reason or "terminated"
            return reason.lower()
        return "unknown"

    @staticmethod
    def _parse_quantity(q: str) -> int:
        q = q.strip()
        if not q:
            return 0
        multipliers = {
            "Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4,
            "k": 1000, "M": 1000**2, "G": 1000**3, "T": 1000**4,
            "m": 1, "": 1,
        }
        unit = ""
        for u in sorted(multipliers, key=len, reverse=True):
            if q.endswith(u) and u:
                unit = u
                break
        try:
            num_str = q[: len(q) - len(unit)] if unit else q
            return int(float(num_str) * multipliers[unit])
        except (ValueError, TypeError):
            return 0
