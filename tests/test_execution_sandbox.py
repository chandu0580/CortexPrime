from __future__ import annotations

import pytest

from backend.execution.sandbox.interfaces import HTTPSandbox, SandboxRegistry, ScriptSandbox, ShellSandbox


@pytest.mark.asyncio
async def test_shell_sandbox_validate_allowed():
    sandbox = ShellSandbox()
    assert await sandbox.validate("echo hello")
    assert await sandbox.validate("cat /etc/hostname")
    assert not await sandbox.validate("rm -rf /")
    assert not await sandbox.validate("sudo something")


@pytest.mark.asyncio
async def test_shell_sandbox_execute_echo():
    sandbox = ShellSandbox()
    result = await sandbox.execute('echo "hello world"')
    assert result.success
    assert "hello world" in result.stdout


@pytest.mark.asyncio
async def test_shell_sandbox_rejects_unauthorized():
    sandbox = ShellSandbox()
    result = await sandbox.execute("rm -rf /")
    assert not result.success
    assert "not in allowed list" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_shell_sandbox_custom_allowed():
    sandbox = ShellSandbox(allowed_commands=["git"])
    assert await sandbox.validate("git status")
    assert not await sandbox.validate("echo hello")


@pytest.mark.asyncio
async def test_http_sandbox_validate():
    sandbox = HTTPSandbox()
    assert await sandbox.validate("GET")
    assert await sandbox.validate("POST")
    assert await sandbox.validate("DELETE")
    assert not await sandbox.validate("INVALID")


@pytest.mark.asyncio
async def test_http_sandbox_invalid_url():
    sandbox = HTTPSandbox()
    result = await sandbox.execute("GET", inputs={"url": "not-a-valid-url"})
    assert not result.success


@pytest.mark.asyncio
async def test_script_sandbox_execute():
    sandbox = ScriptSandbox()
    result = await sandbox.execute("result = 42")
    assert result.success
    assert result.outputs.get("result") == 42


@pytest.mark.asyncio
async def test_script_sandbox_with_inputs():
    sandbox = ScriptSandbox()
    code = "output = inputs.get('x', 0) + inputs.get('y', 0)"
    result = await sandbox.execute(code, inputs={"x": 10, "y": 20})
    assert result.success
    assert result.outputs.get("output") == 30


@pytest.mark.asyncio
async def test_script_sandbox_handles_error():
    sandbox = ScriptSandbox()
    result = await sandbox.execute("1/0")
    assert not result.success
    assert "division by zero" in (result.error or "")


@pytest.mark.asyncio
async def test_sandbox_registry():
    registry = SandboxRegistry()
    shell = ShellSandbox()
    http = HTTPSandbox()
    script = ScriptSandbox()

    registry.register(shell)
    registry.register(http)
    registry.register(script)

    assert registry.is_supported("shell")
    assert registry.is_supported("http")
    assert registry.is_supported("script")
    assert not registry.is_supported("kubernetes")

    assert registry.get("shell") is shell
    assert registry.get("http") is http
    assert registry.get("script") is script
    assert registry.get("k8s") is None

    types = registry.list_types()
    assert "shell" in types
    assert "http" in types
    assert "script" in types


@pytest.mark.asyncio
async def test_sandbox_registry_default():
    from backend.execution.sandbox.interfaces import sandbox_registry as default_registry
    assert default_registry.is_supported("shell")
    assert default_registry.is_supported("http")
    assert default_registry.is_supported("script")
