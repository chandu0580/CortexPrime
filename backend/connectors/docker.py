"""Docker connector — official Docker SDK wrapper with multi-engine support.

Follows BaseConnector pattern. Uses `asyncio.to_thread` to wrap blocking
``docker`` SDK calls so the connector remains async-safe.

Supports:
  - Local socket, remote TCP, TLS
  - Container, Image, Volume, Network, Compose operations
  - Docker Events API streaming
  - Multi-registry intelligence (Docker Hub, GHCR, ACR, ECR, GAR)
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import docker
from docker.errors import APIError, DockerException, NotFound

from backend.connectors.base import BaseConnector

log = logging.getLogger(__name__)

DOCKER_HOST_ENV = "DOCKER_HOST"
DOCKER_TLS_VERIFY_ENV = "DOCKER_TLS_VERIFY"
DOCKER_CERT_PATH_ENV = "DOCKER_CERT_PATH"
DEFAULT_TIMEOUT = 60
MAX_RETRIES = 2

DOCKER_EVENT_TYPES = {
    "container_started": "docker.container.started",
    "container_stopped": "docker.container.stopped",
    "container_restarted": "docker.container.restarted",
    "container_failed": "docker.container.failed",
    "container_paused": "docker.container.paused",
    "container_unpaused": "docker.container.unpaused",
    "container_killed": "docker.container.killed",
    "container_oom": "docker.container.oom",
    "container_health_status": "docker.container.health_status",
    "image_pulled": "docker.image.pulled",
    "image_pushed": "docker.image.pushed",
    "image_removed": "docker.image.removed",
    "image_tagged": "docker.image.tagged",
    "network_created": "docker.network.created",
    "network_removed": "docker.network.removed",
    "volume_created": "docker.volume.created",
    "volume_removed": "docker.volume.removed",
    "plugin_installed": "docker.plugin.installed",
    "service_created": "docker.service.created",
    "service_updated": "docker.service.updated",
}

SUPPORTED_REGISTRIES = [
    "docker.io",
    "ghcr.io",
    "azurecr.io",
    "amazonaws.com",
    "gcr.io",
    "pkg.dev",
]


class DockerConnector(BaseConnector):
    """Connector to one or more Docker engines."""

    connector_name = "Docker"
    connector_type = "docker"

    def __init__(self) -> None:
        self._client: Optional[docker.DockerClient] = None
        self._available: bool = False
        self._host: str = ""

    def configure(self, credentials: Dict[str, str]) -> None:
        super().configure(credentials)
        host = credentials.get("host", "")
        if host:
            os.environ[DOCKER_HOST_ENV] = host
        tls_verify = credentials.get("tls_verify", "")
        if tls_verify:
            os.environ[DOCKER_TLS_VERIFY_ENV] = tls_verify
        cert_path = credentials.get("cert_path", "")
        if cert_path:
            os.environ[DOCKER_CERT_PATH_ENV] = cert_path

    async def initialize(self) -> bool:
        try:
            host = os.getenv(DOCKER_HOST_ENV, "")
            timeout = DEFAULT_TIMEOUT
            self._host = host or "unix:///var/run/docker.sock"

            kwargs: Dict[str, Any] = {
                "timeout": timeout,
                "version": "auto",
            }

            if host:
                kwargs["base_url"] = host
                if os.getenv(DOCKER_TLS_VERIFY_ENV):
                    kwargs["tls"] = docker.tls.TLSConfig(
                        client_cert=(
                            os.path.join(os.getenv(DOCKER_CERT_PATH_ENV, ""), "cert.pem"),
                            os.path.join(os.getenv(DOCKER_CERT_PATH_ENV, ""), "key.pem"),
                        ),
                        verify=True,
                    )

            self._client = docker.from_env(**kwargs) if not host else docker.DockerClient(**kwargs)
            await asyncio.to_thread(self._client.ping)
            self._available = True
            info = await asyncio.to_thread(self._client.info)
            log.info(
                "Docker connector initialized — %s (%s)",
                self._host, info.get("OSType", "unknown"),
            )
            return True
        except (DockerException, APIError, OSError) as exc:
            log.warning("Docker engine unreachable: %s", exc)
            self._available = False
            return False

    async def shutdown(self) -> bool:
        self._available = False
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        return True

    async def health(self) -> Dict[str, Any]:
        status = "available" if self._available else "unavailable"
        info: Dict[str, Any] = {}
        if self._available and self._client:
            try:
                info = await asyncio.to_thread(self._client.info)
            except Exception:
                pass
        return {
            "status": status,
            "connector": self.connector_type,
            "host": self._host,
            "server_version": info.get("ServerVersion", ""),
            "containers_total": info.get("Containers", 0),
            "containers_running": info.get("ContainersRunning", 0),
            "containers_paused": info.get("ContainersPaused", 0),
            "containers_stopped": info.get("ContainersStopped", 0),
            "images_total": info.get("Images", 0),
            "os": info.get("OperatingSystem", ""),
            "kernel": info.get("KernelVersion", ""),
            "driver": info.get("Driver", ""),
        }

    async def _api_call(self, func, *args, **kwargs):
        for attempt in range(MAX_RETRIES + 1):
            try:
                return await asyncio.to_thread(func, *args, **kwargs)
            except (NotFound, APIError) as e:
                if isinstance(e, NotFound):
                    raise
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                raise
            except Exception:
                raise

    def _ensure_client(self) -> docker.DockerClient:
        if not self._client:
            raise RuntimeError("Docker connector not initialized")
        return self._client

    # =========================================================================
    # Containers
    # =========================================================================

    async def list_containers(self, all: bool = True) -> List[Dict[str, Any]]:
        return await self._execute("list_containers", "containers", self._list_containers, all)

    async def _list_containers(self, all: bool = True) -> List[Dict[str, Any]]:
        client = self._ensure_client()
        containers = await self._api_call(client.containers.list, all=all)
        results: List[Dict[str, Any]] = []
        for c in containers:
            attrs = c.attrs or {}
            mounts = attrs.get("Mounts", [])
            port_data = attrs.get("NetworkSettings", {}).get("Ports", {}) if attrs.get("NetworkSettings") else {}
            ports = []
            for container_port, host_ports in port_data.items():
                if host_ports:
                    for hp in host_ports:
                        ports.append(f"{hp.get('HostIp', '0.0.0.0')}:{hp.get('HostPort', '')}->{container_port}")
                else:
                    ports.append(container_port)

            results.append({
                "container_id": c.id[:12] if c.id else "",
                "name": (c.name or "").lstrip("/"),
                "image": c.image.tags[0] if c.image and c.image.tags else (c.image.short_id if c.image else ""),
                "image_id": c.image.id if c.image else "",
                "status": c.status or "unknown",
                "state": attrs.get("State", {}).get("Status", "unknown"),
                "restart_count": attrs.get("RestartCount", 0),
                "ports": ports,
                "port_mappings": port_data,
                "host": self._host,
                "created_at": attrs.get("Created", ""),
                "started_at": attrs.get("State", {}).get("StartedAt", ""),
                "finished_at": attrs.get("State", {}).get("FinishedAt", ""),
                "health": attrs.get("State", {}).get("Health", {}).get("Status", ""),
                "platform": attrs.get("Platform", ""),
                "volumes": [
                    {
                        "source": m.get("Source", ""),
                        "destination": m.get("Destination", ""),
                        "mode": m.get("Mode", ""),
                        "rw": m.get("RW", True),
                    }
                    for m in mounts
                ],
                "networks": list(attrs.get("NetworkSettings", {}).get("Networks", {}).keys()) if attrs.get("NetworkSettings") else [],
                "environment": attrs.get("Config", {}).get("Env", []) if attrs.get("Config") else [],
                "labels": attrs.get("Config", {}).get("Labels", {}) if attrs.get("Config") else {},
                "command": attrs.get("Config", {}).get("Cmd", []) if attrs.get("Config") else [],
                "entrypoint": attrs.get("Config", {}).get("Entrypoint", []) if attrs.get("Config") else [],
                "working_dir": attrs.get("Config", {}).get("WorkingDir", "") if attrs.get("Config") else "",
                "host_config": {
                    "memory_limit": attrs.get("HostConfig", {}).get("Memory", 0),
                    "cpu_shares": attrs.get("HostConfig", {}).get("CpuShares", 0),
                    "restart_policy": attrs.get("HostConfig", {}).get("RestartPolicy", {}).get("Name", ""),
                    "network_mode": attrs.get("HostConfig", {}).get("NetworkMode", ""),
                },
            })
        return results

    async def get_container(self, container_id: str) -> Dict[str, Any]:
        return await self._execute("get_container", "containers", self._get_container, container_id)

    async def _get_container(self, container_id: str) -> Dict[str, Any]:
        client = self._ensure_client()
        c = await self._api_call(client.containers.get, container_id)
        attrs = c.attrs or {}
        mounts = attrs.get("Mounts", [])
        port_data = attrs.get("NetworkSettings", {}).get("Ports", {}) if attrs.get("NetworkSettings") else {}
        ports = []
        for container_port, host_ports in port_data.items():
            if host_ports:
                for hp in host_ports:
                    ports.append(f"{hp.get('HostIp', '0.0.0.0')}:{hp.get('HostPort', '')}->{container_port}")
            else:
                ports.append(container_port)

        return {
            "container_id": c.id[:12] if c.id else "",
            "name": (c.name or "").lstrip("/"),
            "image": c.image.tags[0] if c.image and c.image.tags else (c.image.short_id if c.image else ""),
            "image_id": c.image.id if c.image else "",
            "status": c.status or "unknown",
            "state": attrs.get("State", {}).get("Status", "unknown"),
            "restart_count": attrs.get("RestartCount", 0),
            "ports": ports,
            "port_mappings": port_data,
            "host": self._host,
            "created_at": attrs.get("Created", ""),
            "started_at": attrs.get("State", {}).get("StartedAt", ""),
            "finished_at": attrs.get("State", {}).get("FinishedAt", ""),
            "health": attrs.get("State", {}).get("Health", {}).get("Status", ""),
            "platform": attrs.get("Platform", ""),
            "volumes": [
                {"source": m.get("Source", ""), "destination": m.get("Destination", ""), "mode": m.get("Mode", ""), "rw": m.get("RW", True)}
                for m in mounts
            ],
            "networks": list(attrs.get("NetworkSettings", {}).get("Networks", {}).keys()) if attrs.get("NetworkSettings") else [],
            "environment": attrs.get("Config", {}).get("Env", []) if attrs.get("Config") else [],
            "labels": attrs.get("Config", {}).get("Labels", {}) if attrs.get("Config") else {},
            "command": attrs.get("Config", {}).get("Cmd", []) if attrs.get("Config") else [],
            "entrypoint": attrs.get("Config", {}).get("Entrypoint", []) if attrs.get("Config") else [],
            "working_dir": attrs.get("Config", {}).get("WorkingDir", "") if attrs.get("Config") else "",
            "host_config": {
                "memory_limit": attrs.get("HostConfig", {}).get("Memory", 0),
                "cpu_shares": attrs.get("HostConfig", {}).get("CpuShares", 0),
                "restart_policy": attrs.get("HostConfig", {}).get("RestartPolicy", {}).get("Name", ""),
                "network_mode": attrs.get("HostConfig", {}).get("NetworkMode", ""),
            },
            "log_path": attrs.get("LogPath", ""),
            "resolv_conf_path": attrs.get("ResolvConfPath", ""),
            "hostname_path": attrs.get("HostnamePath", ""),
            "hosts_path": attrs.get("HostsPath", ""),
        }

    async def get_container_logs(
        self, container_id: str, tail: int = 100, timestamps: bool = False,
    ) -> str:
        return await self._execute(
            "get_container_logs", "containers",
            self._get_container_logs, container_id, tail, timestamps,
        )

    async def _get_container_logs(
        self, container_id: str, tail: int = 100, timestamps: bool = False,
    ) -> str:
        client = self._ensure_client()
        c = await self._api_call(client.containers.get, container_id)
        logs = await self._api_call(c.logs, tail=tail, timestamps=timestamps)
        if isinstance(logs, bytes):
            return logs.decode("utf-8", errors="replace")
        return str(logs)

    async def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        return await self._execute(
            "get_container_stats", "containers",
            self._get_container_stats, container_id,
        )

    async def _get_container_stats(self, container_id: str) -> Dict[str, Any]:
        client = self._ensure_client()
        c = await self._api_call(client.containers.get, container_id)
        stats = await self._api_call(c.stats, stream=False)
        if not stats:
            return {}
        cpu_delta = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0) or 0
        system_cpu = stats.get("cpu_stats", {}).get("system_cpu_usage", 0) or 1
        precpu_delta = stats.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0) or 0
        presystem_cpu = stats.get("precpu_stats", {}).get("system_cpu_usage", 0) or 0
        cpu_delta_real = cpu_delta - precpu_delta
        system_delta = system_cpu - presystem_cpu
        cpu_percent = 0.0
        if cpu_delta_real > 0 and system_delta > 0:
            num_cpus = len(stats.get("cpu_stats", {}).get("cpu_usage", {}).get("percpu_usage", []) or [1])
            cpu_percent = round((cpu_delta_real / system_delta) * num_cpus * 100.0, 2)

        mem = stats.get("memory_stats", {})
        mem_usage = mem.get("usage", 0) or 0
        mem_limit = mem.get("limit", 0) or 1
        mem_percent = round((mem_usage / mem_limit) * 100.0, 2) if mem_limit else 0.0

        net = stats.get("networks", {})
        network_rx = sum(n.get("rx_bytes", 0) for n in net.values())
        network_tx = sum(n.get("tx_bytes", 0) for n in net.values())

        blk = stats.get("blkio_stats", {})
        blk_read = sum(
            d.get("value", 0) for d in (blk.get("io_service_bytes_recursive", []) or [])
            if d.get("op") == "read"
        )
        blk_write = sum(
            d.get("value", 0) for d in (blk.get("io_service_bytes_recursive", []) or [])
            if d.get("op") == "write"
        )

        return {
            "container_id": container_id,
            "cpu_percent": cpu_percent,
            "memory_usage_bytes": mem_usage,
            "memory_limit_bytes": mem_limit,
            "memory_percent": mem_percent,
            "network_rx_bytes": network_rx,
            "network_tx_bytes": network_tx,
            "block_read_bytes": blk_read,
            "block_write_bytes": blk_write,
            "pids_current": stats.get("pids_stats", {}).get("current", 0),
        }

    # =========================================================================
    # Images
    # =========================================================================

    async def list_images(self, all: bool = False) -> List[Dict[str, Any]]:
        return await self._execute("list_images", "images", self._list_images, all)

    async def _list_images(self, all: bool = False) -> List[Dict[str, Any]]:
        client = self._ensure_client()
        images = await self._api_call(client.images.list, all=all)
        results: List[Dict[str, Any]] = []
        for img in images:
            attrs = img.attrs or {}
            repo_digests = attrs.get("RepoDigests", [])
            results.append({
                "image_id": img.id or "",
                "short_id": img.short_id or "",
                "tags": img.tags or [],
                "repository": attrs.get("Repository", ""),
                "digests": repo_digests,
                "digest": repo_digests[0].split("@")[1] if repo_digests and "@" in repo_digests[0] else "",
                "created_at": attrs.get("Created", ""),
                "size_bytes": attrs.get("Size", 0),
                "virtual_size_bytes": attrs.get("VirtualSize", 0),
                "labels": attrs.get("Labels", {}),
                "architecture": attrs.get("Architecture", ""),
                "os": attrs.get("Os", ""),
                "os_version": attrs.get("OsVersion", ""),
                "author": attrs.get("Author", ""),
                "container": attrs.get("Container", ""),
                "container_config": {
                    "cmd": attrs.get("ContainerConfig", {}).get("Cmd", []),
                    "entrypoint": attrs.get("ContainerConfig", {}).get("Entrypoint", []),
                    "env": attrs.get("ContainerConfig", {}).get("Env", []),
                    "user": attrs.get("ContainerConfig", {}).get("User", ""),
                    "working_dir": attrs.get("ContainerConfig", {}).get("WorkingDir", ""),
                } if attrs.get("ContainerConfig") else {},
            })
        return results

    async def get_image(self, image_id: str) -> Dict[str, Any]:
        return await self._execute("get_image", "images", self._get_image, image_id)

    async def _get_image(self, image_id: str) -> Dict[str, Any]:
        client = self._ensure_client()
        img = await self._api_call(client.images.get, image_id)
        attrs = img.attrs or {}
        repo_digests = attrs.get("RepoDigests", [])
        return {
            "image_id": img.id or "",
            "short_id": img.short_id or "",
            "tags": img.tags or [],
            "repository": attrs.get("Repository", ""),
            "digests": repo_digests,
            "digest": repo_digests[0].split("@")[1] if repo_digests and "@" in repo_digests[0] else "",
            "created_at": attrs.get("Created", ""),
            "size_bytes": attrs.get("Size", 0),
            "virtual_size_bytes": attrs.get("VirtualSize", 0),
            "labels": attrs.get("Labels", {}),
            "architecture": attrs.get("Architecture", ""),
            "os": attrs.get("Os", ""),
            "container_config": {
                "cmd": attrs.get("ContainerConfig", {}).get("Cmd", []),
                "entrypoint": attrs.get("ContainerConfig", {}).get("Entrypoint", []),
                "env": attrs.get("ContainerConfig", {}).get("Env", []),
                "user": attrs.get("ContainerConfig", {}).get("User", ""),
                "working_dir": attrs.get("ContainerConfig", {}).get("WorkingDir", ""),
            } if attrs.get("ContainerConfig") else {},
            "rootfs": {
                "type": attrs.get("RootFS", {}).get("Type", ""),
                "layers": attrs.get("RootFS", {}).get("Layers", []),
            } if attrs.get("RootFS") else {},
            "history": await self._get_image_history(client, image_id),
        }

    async def get_image_history(self, image_id: str) -> List[Dict[str, Any]]:
        return await self._execute(
            "get_image_history", "images",
            self._get_image_history_cached, image_id,
        )

    async def _get_image_history_cached(self, image_id: str) -> List[Dict[str, Any]]:
        client = self._ensure_client()
        return await self._get_image_history(client, image_id)

    async def _get_image_history(self, client: docker.DockerClient, image_id: str) -> List[Dict[str, Any]]:
        try:
            img = await self._api_call(client.images.get, image_id)
            history = await self._api_call(img.history)
            return [
                {
                    "id": h.get("Id", "")[:12] if h.get("Id") else "<missing>",
                    "created_at": h.get("Created", ""),
                    "created_by": h.get("CreatedBy", ""),
                    "size_bytes": h.get("Size", 0),
                    "tags": h.get("Tags", []),
                    "comment": h.get("Comment", ""),
                }
                for h in (history or [])
            ]
        except Exception:
            return []

    async def pull_image(self, repository: str, tag: str = "latest", platform: str = "") -> Dict[str, Any]:
        return await self._execute(
            "pull_image", "images",
            self._pull_image, repository, tag, platform,
        )

    async def _pull_image(self, repository: str, tag: str = "latest", platform: str = "") -> Dict[str, Any]:
        client = self._ensure_client()
        kwargs: Dict[str, Any] = {"repository": repository, "tag": tag}
        if platform:
            kwargs["platform"] = platform
        img = await self._api_call(client.images.pull, **kwargs)
        return {
            "image_id": img.id or "",
            "short_id": img.short_id or "",
            "tags": img.tags or [],
            "status": "pulled",
        }

    async def remove_image(self, image_id: str, force: bool = False, noprune: bool = False) -> bool:
        return await self._execute(
            "remove_image", "images",
            self._remove_image, image_id, force, noprune,
        )

    async def _remove_image(self, image_id: str, force: bool = False, noprune: bool = False) -> bool:
        client = self._ensure_client()
        img = await self._api_call(client.images.get, image_id)
        await self._api_call(img.remove, force=force, noprune=noprune)
        return True

    async def prune_images(self, dangling: bool = True) -> Dict[str, Any]:
        return await self._execute("prune_images", "images", self._prune_images, dangling)

    async def _prune_images(self, dangling: bool = True) -> Dict[str, Any]:
        client = self._ensure_client()
        result = await self._api_call(client.images.prune, filters={"dangling": ["true"]} if dangling else None)
        return {
            "images_deleted": result.get("ImagesDeleted", []),
            "space_reclaimed_bytes": result.get("SpaceReclaimed", 0),
        }

    # =========================================================================
    # Volumes
    # =========================================================================

    async def list_volumes(self) -> List[Dict[str, Any]]:
        return await self._execute("list_volumes", "volumes", self._list_volumes)

    async def _list_volumes(self) -> List[Dict[str, Any]]:
        client = self._ensure_client()
        vols = await self._api_call(client.volumes.list)
        return [
            {
                "name": v.name,
                "driver": v.attrs.get("Driver", "local") if v.attrs else "local",
                "mountpoint": v.attrs.get("Mountpoint", "") if v.attrs else "",
                "labels": v.attrs.get("Labels", {}) if v.attrs else {},
                "scope": v.attrs.get("Scope", "local") if v.attrs else "local",
                "created_at": v.attrs.get("CreatedAt", "") if v.attrs else "",
                "size_bytes": v.attrs.get("UsageData", {}).get("Size", 0) if v.attrs else 0,
                "ref_count": v.attrs.get("UsageData", {}).get("RefCount", 0) if v.attrs else 0,
            }
            for v in vols
        ]

    async def get_volume(self, volume_name: str) -> Dict[str, Any]:
        return await self._execute("get_volume", "volumes", self._get_volume, volume_name)

    async def _get_volume(self, volume_name: str) -> Dict[str, Any]:
        client = self._ensure_client()
        v = await self._api_call(client.volumes.get, volume_name)
        return {
            "name": v.name,
            "driver": v.attrs.get("Driver", "local") if v.attrs else "local",
            "mountpoint": v.attrs.get("Mountpoint", "") if v.attrs else "",
            "labels": v.attrs.get("Labels", {}) if v.attrs else {},
            "scope": v.attrs.get("Scope", "local") if v.attrs else "local",
            "created_at": v.attrs.get("CreatedAt", "") if v.attrs else "",
            "options": v.attrs.get("Options", {}) if v.attrs else {},
            "status": v.attrs.get("Status", {}) if v.attrs else {},
        }

    # =========================================================================
    # Networks
    # =========================================================================

    async def list_networks(self) -> List[Dict[str, Any]]:
        return await self._execute("list_networks", "networks", self._list_networks)

    async def _list_networks(self) -> List[Dict[str, Any]]:
        client = self._ensure_client()
        nets = await self._api_call(client.networks.list)
        return [
            {
                "name": n.name,
                "id": n.id[:12] if n.id else "",
                "short_id": n.short_id or "",
                "driver": n.attrs.get("Driver", "bridge") if n.attrs else "bridge",
                "scope": n.attrs.get("Scope", "local") if n.attrs else "local",
                "internal": n.attrs.get("Internal", False) if n.attrs else False,
                "attachable": n.attrs.get("Attachable", False) if n.attrs else False,
                "ingress": n.attrs.get("Ingress", False) if n.attrs else False,
                "ipam_driver": n.attrs.get("IPAM", {}).get("Driver", "") if n.attrs else "",
                "subnet": (n.attrs.get("IPAM", {}).get("Config", []) or [{}])[0].get("Subnet", "") if n.attrs else "",
                "gateway": (n.attrs.get("IPAM", {}).get("Config", []) or [{}])[0].get("Gateway", "") if n.attrs else "",
                "labels": n.attrs.get("Labels", {}) if n.attrs else {},
                "containers": list(n.attrs.get("Containers", {}).keys()) if n.attrs else [],
                "created_at": n.attrs.get("Created", "") if n.attrs else "",
            }
            for n in nets
        ]

    # =========================================================================
    # Engine info / system
    # =========================================================================

    async def get_info(self) -> Dict[str, Any]:
        return await self._execute("get_info", "system", self._get_info)

    async def _get_info(self) -> Dict[str, Any]:
        client = self._ensure_client()
        info = await self._api_call(client.info)
        if isinstance(info, dict):
            return info
        return {"error": "unable to fetch info"}

    async def df(self) -> Dict[str, Any]:
        """Docker system df — disk usage for images, containers, volumes, build cache."""
        return await self._execute("df", "system", self._df)

    async def _df(self) -> Dict[str, Any]:
        client = self._ensure_client()
        return await self._api_call(client.df)

    async def get_version(self) -> Dict[str, Any]:
        return await self._execute("get_version", "system", self._get_version)

    async def _get_version(self) -> Dict[str, Any]:
        client = self._ensure_client()
        return await self._api_call(client.version)

    # =========================================================================
    # Events streaming
    # =========================================================================

    async def stream_events(self, since: str = "", filters: Optional[Dict[str, str]] = None) -> AsyncIterator[Dict[str, Any]]:
        """Yield Docker events as dicts.  Caller must iterate."""
        client = self._ensure_client()
        kwargs: Dict[str, Any] = {"decode": True}
        if since:
            kwargs["since"] = since
        if filters:
            kwargs["filters"] = filters
        try:
            for event in client.events(**kwargs):
                if isinstance(event, dict):
                    yield event
        except Exception as exc:
            log.warning("Docker event stream error: %s", exc)

    # =========================================================================
    # Registry Intelligence
    # =========================================================================

    async def search_registry(self, term: str, registry: str = "docker.io") -> List[Dict[str, Any]]:
        """Search for images on a registry."""
        return await self._execute(
            "search_registry", "registry",
            self._search_registry, term, registry,
        )

    async def _search_registry(self, term: str, registry: str = "docker.io") -> List[Dict[str, Any]]:
        client = self._ensure_client()
        results = await self._api_call(client.images.search, term)
        return [
            {
                "name": r.get("name", ""),
                "description": r.get("description", ""),
                "star_count": r.get("star_count", 0),
                "is_official": r.get("is_official", False),
                "is_automated": r.get("is_automated", False),
                "registry": registry,
            }
            for r in (results or [])
        ]

    async def get_registry_repositories(self, registry: str = "docker.io") -> List[Dict[str, Any]]:
        """List repositories from a registry.  Limited to what the Docker Hub API exposes."""
        return await self._execute(
            "get_registry_repositories", "registry",
            self._get_registry_repositories, registry,
        )

    async def _get_registry_repositories(self, registry: str = "docker.io") -> List[Dict[str, Any]]:
        """Stub — full registry API requires per-registry auth.  Returns local image repos."""
        client = self._ensure_client()
        images = await self._api_call(client.images.list)
        repos: Dict[str, List[str]] = {}
        for img in images:
            for tag in (img.tags or []):
                if "/" in tag:
                    repo = tag.rsplit(":", 1)[0] if ":" in tag else tag
                    tag_only = tag.split(":")[1] if ":" in tag else "latest"
                    repos.setdefault(repo, []).append(tag_only)
        return [
            {"repository": repo, "tags": tags, "registry": registry}
            for repo, tags in sorted(repos.items())
        ]

    # =========================================================================
    # Compose-like operations
    # =========================================================================

    async def list_compose_projects(self) -> List[Dict[str, Any]]:
        """List Docker Compose projects by inspecting containers with com.docker.compose labels."""
        return await self._execute(
            "list_compose_projects", "compose",
            self._list_compose_projects,
        )

    async def _list_compose_projects(self) -> List[Dict[str, Any]]:
        client = self._ensure_client()
        containers = await self._api_call(client.containers.list, all=True, filters={"label": "com.docker.compose.project"})
        projects: Dict[str, Dict[str, Any]] = {}
        for c in containers:
            labels = (c.attrs or {}).get("Config", {}).get("Labels", {}) or {}
            project = labels.get("com.docker.compose.project", "")
            service = labels.get("com.docker.compose.service", "")
            container_number = labels.get("com.docker.compose.container-number", "1")
            if project:
                if project not in projects:
                    projects[project] = {
                        "project_name": project,
                        "services": {},
                        "container_count": 0,
                    }
                projects[project]["services"].setdefault(service, {"service_name": service, "containers": []})
                projects[project]["services"][service]["containers"].append({
                    "container_id": c.id[:12] if c.id else "",
                    "name": (c.name or "").lstrip("/"),
                    "status": c.status or "unknown",
                    "container_number": container_number,
                    "image": c.image.tags[0] if c.image and c.image.tags else "",
                })
                projects[project]["container_count"] += 1
        return list(projects.values())
