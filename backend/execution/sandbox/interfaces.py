from __future__ import annotations

import asyncio
import logging
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    success: bool
    outputs: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: Optional[float] = None


class ExecutionSandbox(ABC):
    @abstractmethod
    async def execute(
        self,
        command: str,
        inputs: Optional[dict[str, Any]] = None,
        environment: Optional[dict[str, Any]] = None,
        timeout_seconds: int = 300,
        working_directory: Optional[str] = None,
    ) -> SandboxResult:
        ...

    @abstractmethod
    async def validate(self, command: str) -> bool:
        ...

    @property
    @abstractmethod
    def sandbox_type(self) -> str:
        ...


class ShellSandbox(ExecutionSandbox):
    def __init__(self, allowed_commands: Optional[list[str]] = None) -> None:
        self._allowed_commands = allowed_commands or [
            "echo", "cat", "ls", "pwd", "whoami",
            "date", "env", "head", "tail", "sort",
            "uniq", "wc", "cut", "tr", "grep",
            "find", "which", "python3", "python",
            "node", "npm", "git",
        ]

    @property
    def sandbox_type(self) -> str:
        return "shell"

    async def validate(self, command: str) -> bool:
        cmd = command.strip().split()[0] if command.strip() else ""
        return cmd in self._allowed_commands

    async def execute(
        self,
        command: str,
        inputs: Optional[dict[str, Any]] = None,
        environment: Optional[dict[str, Any]] = None,
        timeout_seconds: int = 300,
        working_directory: Optional[str] = None,
    ) -> SandboxResult:
        if not await self.validate(command):
            return SandboxResult(
                success=False,
                error=f"Command '{command.split()[0] if command else ''}' not in allowed list",
                exit_code=-1,
            )
        start = datetime.now(timezone.utc)
        try:
            cmd_parts = shlex.split(command)
            proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_directory,
                env={**(environment or {}), **(inputs or {})} if inputs or environment else None,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                proc.kill()
                elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                return SandboxResult(
                    success=False,
                    error=f"Command timed out after {timeout_seconds}s",
                    exit_code=-1,
                    duration_ms=elapsed,
                )
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            return SandboxResult(
                success=proc.returncode == 0,
                outputs={"stdout": stdout.decode() if stdout else "", "returncode": proc.returncode},
                error=stderr.decode() if stderr and proc.returncode != 0 else None,
                exit_code=proc.returncode or 0,
                stdout=stdout.decode() if stdout else "",
                stderr=stderr.decode() if stderr else "",
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            return SandboxResult(
                success=False,
                error=str(exc),
                exit_code=-1,
                duration_ms=elapsed,
            )


class HTTPSandbox(ExecutionSandbox):
    @property
    def sandbox_type(self) -> str:
        return "http"

    async def validate(self, command: str) -> bool:
        return command.strip().lower() in ("get", "post", "put", "delete", "patch", "head", "options")

    async def execute(
        self,
        command: str,
        inputs: Optional[dict[str, Any]] = None,
        environment: Optional[dict[str, Any]] = None,
        timeout_seconds: int = 300,
        working_directory: Optional[str] = None,
    ) -> SandboxResult:
        import httpx
        method = command.strip().lower()
        url = (inputs or {}).get("url", "")
        headers = (inputs or {}).get("headers", {})
        body = (inputs or {}).get("body", None)
        start = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.request(
                    method=method, url=url, headers=headers,
                    json=body if isinstance(body, dict) else None,
                    content=body if not isinstance(body, dict) else None,
                )
                elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                content = response.text
                return SandboxResult(
                    success=response.is_success,
                    outputs={
                        "status_code": response.status_code,
                        "body": content,
                        "headers": dict(response.headers),
                    },
                    error=None if response.is_success else f"HTTP {response.status_code}: {content[:500]}",
                    exit_code=response.status_code,
                    stdout=content,
                    stderr="" if response.is_success else content,
                    duration_ms=elapsed,
                )
        except Exception as exc:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            return SandboxResult(
                success=False,
                error=str(exc),
                exit_code=-1,
                duration_ms=elapsed,
            )


_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs, "all": all, "any": any, "ascii": ascii,
    "bin": bin, "bool": bool, "bytes": bytes, "chr": chr,
    "dict": dict, "dir": dir, "divmod": divmod, "enumerate": enumerate,
    "filter": filter, "float": float, "format": format, "frozenset": frozenset,
    "getattr": getattr, "hasattr": hasattr, "hash": hash, "hex": hex,
    "id": id, "int": int, "isinstance": isinstance, "issubclass": issubclass,
    "iter": iter, "len": len, "list": list, "map": map, "max": max,
    "min": min, "next": next, "object": object, "oct": oct,
    "ord": ord, "pow": pow, "print": print, "range": range,
    "repr": repr, "reversed": reversed, "round": round,
    "set": set, "slice": slice, "sorted": sorted, "str": str,
    "sum": sum, "super": super, "tuple": tuple, "type": type,
    "vars": vars, "zip": zip,
}

_MAX_SCRIPT_LENGTH = 65536
_DENIED_PATTERNS = [
    "import", "__import__", "exec", "eval", "compile",
    "open", "file", "input(", "__file__", "__loader__",
    "os.", "subprocess", "sys.", "shutil", "pathlib",
    "ctypes", "socket", "requests", "urllib",
]


class ScriptSandbox(ExecutionSandbox):
    @property
    def sandbox_type(self) -> str:
        return "script"

    async def validate(self, command: str) -> bool:
        if not command or len(command) > _MAX_SCRIPT_LENGTH:
            return False
        for pattern in _DENIED_PATTERNS:
            if pattern in command:
                return False
        return True

    async def execute(
        self,
        command: str,
        inputs: Optional[dict[str, Any]] = None,
        environment: Optional[dict[str, Any]] = None,
        timeout_seconds: int = 300,
        working_directory: Optional[str] = None,
    ) -> SandboxResult:
        if not await self.validate(command):
            return SandboxResult(
                success=False,
                error="Script rejected by sandbox validation",
                exit_code=-1,
            )
        start = datetime.now(timezone.utc)
        try:
            local_ns: dict[str, Any] = {"__builtins__": _SAFE_BUILTINS}
            local_ns.update({
                "inputs": inputs or {},
                "environment": environment or {},
            })
            exec_globals: dict[str, Any] = {}
            exec(command, exec_globals, local_ns)
            outputs = {k: v for k, v in local_ns.items()
                       if not k.startswith("_") and k not in ("inputs", "environment", "__builtins__")}
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            return SandboxResult(
                success=True,
                outputs=outputs or {"result": "executed"},
                exit_code=0,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            return SandboxResult(
                success=False,
                error=str(exc),
                exit_code=-1,
                duration_ms=elapsed,
            )


class SandboxRegistry:
    def __init__(self) -> None:
        self._sandboxes: dict[str, ExecutionSandbox] = {}

    def register(self, sandbox: ExecutionSandbox) -> None:
        self._sandboxes[sandbox.sandbox_type] = sandbox

    def get(self, sandbox_type: str) -> Optional[ExecutionSandbox]:
        return self._sandboxes.get(sandbox_type)

    def list_types(self) -> list[str]:
        return list(self._sandboxes.keys())

    def is_supported(self, sandbox_type: str) -> bool:
        return sandbox_type in self._sandboxes


sandbox_registry = SandboxRegistry()
sandbox_registry.register(ShellSandbox())
sandbox_registry.register(HTTPSandbox())
sandbox_registry.register(ScriptSandbox())
