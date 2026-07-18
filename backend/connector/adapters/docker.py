from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Optional

import docker
from docker.errors import APIError, DockerException, NotFound

from backend.connector.adapter.interfaces import AdapterHealthStatus, AdapterResult, ConnectorAdapter
from backend.connector.models import Capability

log = logging.getLogger(__name__)

DOCKER_HOST_ENV = "DOCKER_HOST"
DOCKER_TLS_VERIFY_ENV = "DOCKER_TLS_VERIFY"
DOCKER_CERT_PATH_ENV = "DOCKER_CERT_PATH"
DEFAULT_TIMEOUT = 60
MAX_RETRIES = 2


class DockerAdapter(ConnectorAdapter):

    @property
    def connector_type(self) -> str:
        return "docker"

    @property
    def connector_name(self) -> str:
        return "Docker"

    @property
    def adapter_version(self) -> str:
        return "1.0.0"

    def __init__(self) -> None:
        self._client: Optional[docker.DockerClient] = None
        self._initialized: bool = False
        self._host: str = ""

    async def initialize(self) -> bool:
        try:
            host = os.getenv(DOCKER_HOST_ENV, "")
            self._host = host or "unix:///var/run/docker.sock"
            kwargs: dict[str, Any] = {"timeout": DEFAULT_TIMEOUT, "version": "auto"}

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
            self._initialized = True
            info = await asyncio.to_thread(self._client.info)
            log.info("Docker adapter initialized — %s (%s)", self._host, info.get("OSType", "unknown"))
            return True
        except (DockerException, APIError, OSError) as exc:
            log.warning("Docker engine unreachable: %s", exc)
            return False

    async def health_check(self) -> AdapterHealthStatus:
        if not self._initialized or not self._client:
            return AdapterHealthStatus.UNHEALTHY
        try:
            await asyncio.to_thread(self._client.ping)
            return AdapterHealthStatus.HEALTHY
        except (DockerException, APIError, OSError):
            return AdapterHealthStatus.UNHEALTHY

    async def capabilities(self) -> list[Capability]:
        return [
            Capability.OBSERVE,
            Capability.EXECUTE,
            Capability.RESTART,
            Capability.DEPLOY,
        ]

    async def execute(self, capability: Capability, inputs: dict[str, Any],
                      timeout_seconds: Optional[int] = None) -> AdapterResult:
        start = time.monotonic()

        if capability == Capability.OBSERVE:
            return await self._observe(inputs, start)
        if capability == Capability.EXECUTE:
            return await self._execute_action(inputs, start)
        if capability == Capability.RESTART:
            return await self._restart_container(inputs, start)
        if capability == Capability.DEPLOY:
            return await self._deploy(inputs, start)

        return AdapterResult(
            success=False,
            error=f"Unsupported capability: {capability.value}",
            duration_ms=(time.monotonic() - start) * 1000,
        )

    async def shutdown(self) -> None:
        self._initialized = False
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        log.info("Docker adapter shut down")

    async def metadata(self) -> dict[str, Any]:
        base = await super().metadata()
        base["host"] = self._host
        return base

    def _ensure_client(self) -> docker.DockerClient:
        if not self._client:
            raise RuntimeError("Docker adapter not initialized")
        return self._client

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

    async def _observe(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        all_containers = inputs.get("all", True)
        try:
            client = self._ensure_client()
            containers = await self._api_call(client.containers.list, all=all_containers)
            info = await self._api_call(client.info)
            container_list = []
            for c in containers:
                attrs = c.attrs or {}
                container_list.append({
                    "id": c.id[:12] if c.id else "",
                    "name": (c.name or "").lstrip("/"),
                    "image": c.image.tags[0] if c.image and c.image.tags else (c.image.short_id if c.image else ""),
                    "status": c.status or "unknown",
                    "state": attrs.get("State", {}).get("Status", "unknown"),
                })
            return AdapterResult(success=True, outputs={
                "containers": container_list,
                "containers_total": info.get("Containers", 0),
                "containers_running": info.get("ContainersRunning", 0),
                "images_total": info.get("Images", 0),
                "server_version": info.get("ServerVersion", ""),
            }, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _execute_action(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        container_id = inputs.get("container_id")
        if not container_id:
            return AdapterResult(success=False, error="Missing 'container_id'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            client = self._ensure_client()
            c = await self._api_call(client.containers.get, container_id)
            attrs = c.attrs or {}
            return AdapterResult(success=True, outputs={
                "id": c.id[:12] if c.id else "",
                "name": (c.name or "").lstrip("/"),
                "status": c.status or "unknown",
                "state": attrs.get("State", {}).get("Status", "unknown"),
                "image": c.image.tags[0] if c.image and c.image.tags else "",
            }, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _restart_container(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        container_id = inputs.get("container_id")
        if not container_id:
            return AdapterResult(success=False, error="Missing 'container_id'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            client = self._ensure_client()
            c = await self._api_call(client.containers.get, container_id)
            await self._api_call(c.restart)
            return AdapterResult(success=True, outputs={"container_id": container_id, "action": "restarted"}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)

    async def _deploy(self, inputs: dict[str, Any], start: float) -> AdapterResult:
        image = inputs.get("image")
        name = inputs.get("name", "")
        command = inputs.get("command")
        detach = inputs.get("detach", True)
        if not image:
            return AdapterResult(success=False, error="Missing 'image'", duration_ms=(time.monotonic() - start) * 1000)
        try:
            client = self._ensure_client()
            await self._api_call(client.images.pull, image)
            kwargs: dict[str, Any] = {"image": image, "detach": detach}
            if name:
                kwargs["name"] = name
            if command:
                kwargs["command"] = command
            container = await self._api_call(client.containers.create, **kwargs)
            await self._api_call(container.start)
            return AdapterResult(success=True, outputs={"container_id": container.id[:12] if container.id else "", "name": (container.name or "").lstrip("/"), "image": image}, duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return AdapterResult(success=False, error=str(e), duration_ms=(time.monotonic() - start) * 1000)
