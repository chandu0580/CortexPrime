"""
Tests for DockerConnector additions made for the container-health detector:
oom_killed/exit_code surfaced on list_containers()/get_container(), and the
new restart_container() action primitive (DockerConnector was 100%
read-only before this).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.connectors.docker import DockerConnector

pytestmark = pytest.mark.asyncio


def _fake_container(oom_killed=False, exit_code=0, restart_count=0, status="running"):
    c = MagicMock()
    c.id = "abcdef123456789"
    c.name = "test-container"
    c.image.tags = ["alpine:latest"]
    c.image.id = "sha256:xyz"
    c.status = status
    c.attrs = {
        "State": {
            "Status": status,
            "StartedAt": "2026-01-01T00:00:00Z",
            "FinishedAt": "",
            "OOMKilled": oom_killed,
            "ExitCode": exit_code,
        },
        "RestartCount": restart_count,
        "NetworkSettings": {"Ports": {}, "Networks": {}},
        "Config": {"Env": [], "Labels": {}, "Cmd": [], "Entrypoint": [], "WorkingDir": ""},
        "HostConfig": {"Memory": 0, "CpuShares": 0, "RestartPolicy": {"Name": "unless-stopped"}, "NetworkMode": ""},
        "Mounts": [],
        "Platform": "linux",
    }
    return c


def _connector_with_fake_client(container):
    connector = DockerConnector()
    fake_client = MagicMock()
    fake_client.containers.list.return_value = [container]
    fake_client.containers.get.return_value = container
    connector._client = fake_client
    return connector


class TestOomKilledAndExitCodeFields:
    async def test_list_containers_surfaces_oom_killed_and_exit_code(self):
        container = _fake_container(oom_killed=True, exit_code=137)
        connector = _connector_with_fake_client(container)
        result = await connector.list_containers()
        assert result[0]["oom_killed"] is True
        assert result[0]["exit_code"] == 137

    async def test_list_containers_defaults_when_healthy(self):
        container = _fake_container(oom_killed=False, exit_code=0)
        connector = _connector_with_fake_client(container)
        result = await connector.list_containers()
        assert result[0]["oom_killed"] is False
        assert result[0]["exit_code"] == 0

    async def test_get_container_surfaces_oom_killed_and_exit_code(self):
        container = _fake_container(oom_killed=True, exit_code=137)
        connector = _connector_with_fake_client(container)
        result = await connector.get_container("abcdef123456")
        assert result["oom_killed"] is True
        assert result["exit_code"] == 137


class TestRestartContainer:
    async def test_restart_container_calls_real_docker_restart(self):
        container = _fake_container()
        connector = _connector_with_fake_client(container)
        result = await connector.restart_container("abcdef123456", timeout=5)
        assert result is True
        container.restart.assert_called_once_with(timeout=5)

    async def test_restart_container_uses_default_timeout(self):
        container = _fake_container()
        connector = _connector_with_fake_client(container)
        await connector.restart_container("abcdef123456")
        container.restart.assert_called_once_with(timeout=10)
