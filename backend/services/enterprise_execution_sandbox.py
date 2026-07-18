"""
Enterprise Execution Sandbox — isolated, reproducible engineering environments
for every software engineering mission.

Parts:
  1. Sandbox Manager — lifecycle CRUD
  2. Repository Preparation — clone, checkout, restore, deps
  3. Execution — Python, Node, Java, .NET, Go, Rust, Shell
  4. Artifact Collection — logs, reports, files, metrics
  5. Resource Monitoring — CPU, memory, disk, time

Every execution occurs inside a managed Sandbox.
All artifacts are preserved before cleanup.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import resource
except ImportError:
    resource = None  # not available on Windows

from backend.events.enterprise_event_types import EnterpriseEventTypes as EET

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_SANDBOXES_FILE = _DATA_DIR / "sandboxes.json"

SANDBOX_ISOLATION_DIR = Path(tempfile.gettempdir()) / "cortexprime_sandboxes"

SANDBOX_STATUSES = [
    "creating", "ready", "running", "paused",
    "executing", "completed", "failed", "destroyed",
]

SUPPORTED_LANGUAGES = ["python", "node", "java", "dotnet", "go", "rust", "shell"]

LANGUAGE_EXTENSIONS: Dict[str, List[str]] = {
    "python": [".py", ".pyw"],
    "node": [".js", ".jsx", ".ts", ".tsx", ".mjs"],
    "java": [".java", ".kt", ".groovy"],
    "dotnet": [".cs", ".vb", ".fs", ".csproj", ".sln"],
    "go": [".go"],
    "rust": [".rs"],
    "shell": [".sh", ".bash", ".ps1"],
}


def _load_sandboxes() -> List[Dict[str, Any]]:
    try:
        if _SANDBOXES_FILE.exists():
            with open(_SANDBOXES_FILE) as f:
                return json.load(f)
    except Exception as exc:
        log.error("Failed to load sandboxes: %s", exc)
    return []


def _save_sandboxes(data: List[Dict[str, Any]]) -> None:
    _SANDBOXES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_SANDBOXES_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


# =============================================================================
# ExecutionResult
# =============================================================================

class ExecutionResult:
    """Captures the outcome of a single execution inside a sandbox."""

    def __init__(
        self,
        execution_id: str,
        command: str,
        exit_code: int,
        stdout: str,
        stderr: str,
        duration_ms: float,
        language: str = "",
        artifacts: Optional[List[Dict[str, Any]]] = None,
        resource_usage: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.execution_id = execution_id
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration_ms = duration_ms
        self.language = language
        self.artifacts = artifacts or []
        self.resource_usage = resource_usage or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def succeeded(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "language": self.language,
            "artifacts": self.artifacts,
            "resource_usage": self.resource_usage,
            "timestamp": self.timestamp,
        }


# =============================================================================
# Sandbox
# =============================================================================

class Sandbox:
    """An isolated execution environment for engineering work."""

    def __init__(
        self,
        name: str,
        repo_url: str = "",
        branch: str = "main",
        language: str = "python",
        sandbox_id: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.sandbox_id = sandbox_id or f"sbx-{uuid.uuid4().hex[:12]}"
        self.name = name
        self.repo_url = repo_url
        self.branch = branch
        self.language = language
        self.status = "creating"
        self.isolation_path: Optional[str] = None
        self.workspace_id: str = ""
        self.build_id: str = ""
        self.executions: List[Dict[str, Any]] = []
        self.artifacts: List[Dict[str, Any]] = []
        self.logs: List[Dict[str, Any]] = []
        self.resource_usage: Dict[str, Any] = {}
        self.timing: Dict[str, Any] = {}
        self.error: str = ""
        self.created_at = now
        self.updated_at = now
        self.destroyed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sandbox_id": self.sandbox_id,
            "name": self.name,
            "repo_url": self.repo_url,
            "branch": self.branch,
            "language": self.language,
            "status": self.status,
            "isolation_path": self.isolation_path,
            "workspace_id": self.workspace_id,
            "build_id": self.build_id,
            "executions": self.executions[-50:],
            "artifacts": self.artifacts,
            "logs": self.logs[-100:],
            "resource_usage": self.resource_usage,
            "timing": self.timing,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "destroyed_at": self.destroyed_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Sandbox:
        sbx = Sandbox(
            name=data.get("name", ""),
            repo_url=data.get("repo_url", ""),
            branch=data.get("branch", "main"),
            language=data.get("language", "python"),
            sandbox_id=data.get("sandbox_id"),
        )
        sbx.status = data.get("status", "creating")
        sbx.isolation_path = data.get("isolation_path")
        sbx.workspace_id = data.get("workspace_id", "")
        sbx.build_id = data.get("build_id", "")
        sbx.executions = data.get("executions", [])
        sbx.artifacts = data.get("artifacts", [])
        sbx.logs = data.get("logs", [])
        sbx.resource_usage = data.get("resource_usage", {})
        sbx.timing = data.get("timing", {})
        sbx.error = data.get("error", "")
        sbx.created_at = data.get("created_at", sbx.created_at)
        sbx.updated_at = data.get("updated_at", sbx.updated_at)
        sbx.destroyed_at = data.get("destroyed_at", "")
        return sbx


# =============================================================================
# Enterprise Execution Sandbox Engine
# =============================================================================

class EnterpriseExecutionSandbox:
    """
    Manages isolated sandbox environments for safe engineering execution.

    Every sandbox has its own temp directory, can clone repos, execute
    commands, and collect artifacts before cleanup.
    """

    def __init__(self) -> None:
        self._sandboxes: Dict[str, Sandbox] = {}
        self._isolation_root = SANDBOX_ISOLATION_DIR
        self._load_persisted()

    # ── Part 1: Sandbox Manager ──────────────────────────────────────────────

    async def create_sandbox(
        self,
        name: str,
        repo_url: str = "",
        branch: str = "main",
        language: str = "python",
    ) -> Sandbox:
        sbx = Sandbox(name=name, repo_url=repo_url, branch=branch, language=language)
        self._sandboxes[sbx.sandbox_id] = sbx
        self._persist()
        await self._emit(EET.SANDBOX_CREATED, sbx, {"language": language})

        # Create isolation directory
        try:
            iso_path = self._isolation_root / sbx.sandbox_id
            iso_path.mkdir(parents=True, exist_ok=True)
            sbx.isolation_path = str(iso_path)
        except Exception as exc:
            log.warning("Isolation path creation failed: %s", exc)
            sbx.isolation_path = str(self._isolation_root / sbx.sandbox_id)

        sbx.status = "ready"
        sbx.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        await self._emit(EET.SANDBOX_STARTED, sbx)
        log.info("Sandbox created: %s (%s)", sbx.name, sbx.sandbox_id)
        return sbx

    async def start_sandbox(self, sandbox_id: str) -> Optional[Sandbox]:
        sbx = self._sandboxes.get(sandbox_id)
        if not sbx:
            return None
        if sbx.status in ("destroyed",):
            return None
        iso_path = self._isolation_root / sbx.sandbox_id
        iso_path.mkdir(parents=True, exist_ok=True)
        sbx.isolation_path = str(iso_path)
        sbx.status = "ready"
        sbx.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        await self._emit(EET.SANDBOX_STARTED, sbx)
        return sbx

    async def pause_sandbox(self, sandbox_id: str) -> Optional[Sandbox]:
        sbx = self._sandboxes.get(sandbox_id)
        if not sbx or sbx.status != "running":
            return None
        sbx.status = "paused"
        sbx.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        await self._emit(EET.SANDBOX_PAUSED, sbx)
        return sbx

    async def resume_sandbox(self, sandbox_id: str) -> Optional[Sandbox]:
        sbx = self._sandboxes.get(sandbox_id)
        if not sbx or sbx.status != "paused":
            return None
        sbx.status = "running"
        sbx.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        await self._emit(EET.SANDBOX_RESUMED, sbx)
        return sbx

    async def destroy_sandbox(self, sandbox_id: str) -> Optional[Sandbox]:
        sbx = self._sandboxes.get(sandbox_id)
        if not sbx:
            return None
        sbx.status = "destroyed"
        sbx.destroyed_at = datetime.now(timezone.utc).isoformat()
        sbx.updated_at = sbx.destroyed_at
        self._persist()
        await self._emit(EET.SANDBOX_DESTROYED, sbx)
        log.info("Sandbox destroyed: %s", sbx.sandbox_id)
        return sbx

    async def get_sandbox(self, sandbox_id: str) -> Optional[Sandbox]:
        return self._sandboxes.get(sandbox_id)

    async def list_sandboxes(
        self,
        status: str = "",
        language: str = "",
    ) -> List[Dict[str, Any]]:
        results = list(self._sandboxes.values())
        if status:
            results = [s for s in results if s.status == status]
        if language:
            results = [s for s in results if s.language == language]
        results.sort(key=lambda s: s.created_at, reverse=True)
        return [s.to_dict() for s in results]

    # ── Part 2: Repository Preparation ────────────────────────────────────────

    async def prepare_repository(self, sandbox_id: str) -> Optional[Sandbox]:
        sbx = self._sandboxes.get(sandbox_id)
        if not sbx:
            return None

        iso_path = self._get_isolation_path(sbx)
        if not iso_path:
            return None

        repo_dir = iso_path / "repo"
        log_start = time.monotonic()

        try:
            if sbx.repo_url:
                result = await self._run_command(
                    ["git", "clone", "--depth", "1", "-b", sbx.branch, sbx.repo_url, str(repo_dir)],
                    iso_path,
                    timeout=120,
                )
                sbx.logs.append({
                    "type": "repo_prep",
                    "message": f"Cloned {sbx.repo_url} branch={sbx.branch}",
                    "exit_code": result.exit_code,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            else:
                repo_dir.mkdir(parents=True, exist_ok=True)
                sbx.logs.append({
                    "type": "repo_prep",
                    "message": "No repo URL — using empty directory",
                    "exit_code": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            await self._install_dependencies(sbx, repo_dir)
            await self._prepare_environment(sbx, repo_dir)
        except Exception as exc:
            sbx.error = f"Repository preparation failed: {exc}"
            sbx.status = "failed"
            sbx.logs.append({
                "type": "repo_prep",
                "message": sbx.error,
                "exit_code": -1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        elapsed = (time.monotonic() - log_start) * 1000
        if "repo_prep" not in sbx.timing:
            sbx.timing["repo_prep_ms"] = elapsed

        if sbx.status != "failed":
            sbx.status = "running"
        sbx.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        return sbx

    async def _install_dependencies(self, sbx: Sandbox, repo_dir: Path) -> None:
        lang = sbx.language.lower()
        dep_configs: Dict[str, List[str]] = {
            "python": ["pip", "install", "-r", "requirements.txt"],
            "node": ["npm", "install"],
            "java": ["mvn", "install", "-DskipTests"],
            "dotnet": ["dotnet", "restore"],
            "go": ["go", "mod", "download"],
            "rust": ["cargo", "fetch"],
        }
        cmd = dep_configs.get(lang)
        if not cmd:
            return

        dep_file_map: Dict[str, str] = {
            "python": "requirements.txt",
            "node": "package.json",
            "java": "pom.xml",
            "dotnet": "*.csproj",
            "go": "go.mod",
            "rust": "Cargo.toml",
        }
        dep_file = dep_file_map.get(lang, "")
        if dep_file and not list(repo_dir.glob(dep_file)):
            sbx.logs.append({
                "type": "dependencies",
                "message": f"No {dep_file} found — skipping dependency install",
                "exit_code": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return

        result = await self._run_command(cmd, repo_dir, timeout=180)
        sbx.logs.append({
            "type": "dependencies",
            "message": f"Dependency install: exit={result.exit_code} duration={result.duration_ms:.0f}ms",
            "exit_code": result.exit_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _prepare_environment(self, sbx: Sandbox, repo_dir: Path) -> None:
        env_file = repo_dir / ".env.sandbox"
        env_content = (
            f"SANDBOX_ID={sbx.sandbox_id}\n"
            f"SANDBOX_NAME={sbx.name}\n"
            f"SANDBOX_LANGUAGE={sbx.language}\n"
            f"SANDBOX_BRANCH={sbx.branch}\n"
            f"CI=true\n"
            f"CORTEXPRIME_SANDBOX=true\n"
        )
        try:
            env_file.write_text(env_content)
            sbx.logs.append({
                "type": "environment",
                "message": "Sandbox environment prepared",
                "exit_code": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            sbx.logs.append({
                "type": "environment",
                "message": f"Environment prep failed: {exc}",
                "exit_code": -1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    # ── Part 3: Execution ────────────────────────────────────────────────────

    async def execute(
        self,
        sandbox_id: str,
        command: str = "",
        language: str = "",
        timeout: int = 300,
    ) -> Optional[ExecutionResult]:
        sbx = self._sandboxes.get(sandbox_id)
        if not sbx:
            return None
        if sbx.status in ("destroyed", "creating"):
            return None

        iso_path = self._get_isolation_path(sbx)
        if not iso_path:
            return None

        repo_dir = iso_path / "repo"
        lang = language or sbx.language
        exec_id = f"exec-{uuid.uuid4().hex[:12]}"
        resolved_cmd = self._resolve_command(command, lang, repo_dir)

        sbx.status = "executing"
        sbx.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        await self._emit(EET.SANDBOX_EXECUTION_STARTED, sbx,
                         {"execution_id": exec_id, "command": resolved_cmd})

        cpu_start = _get_cpu_percent()
        mem_start = _get_memory_usage()
        disk_start = _get_disk_usage(iso_path)
        exec_start = time.monotonic()

        result = await self._run_command(resolved_cmd, repo_dir, timeout=timeout)
        exec_elapsed = (time.monotonic() - exec_start) * 1000

        cpu_end = _get_cpu_percent()
        mem_end = _get_memory_usage()
        disk_end = _get_disk_usage(iso_path)

        resource_usage = {
            "cpu_percent": {"start": cpu_start, "end": cpu_end, "peak": max(cpu_start, cpu_end)},
            "memory_mb": {"start": mem_start, "end": mem_end},
            "disk_mb": {"start": disk_start, "end": disk_end},
            "execution_time_ms": exec_elapsed,
        }

        artifacts = await self._collect_artifacts(sbx, iso_path, lang)

        exec_result = ExecutionResult(
            execution_id=exec_id,
            command=resolved_cmd,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=exec_elapsed,
            language=lang,
            artifacts=artifacts,
            resource_usage=resource_usage,
        )

        sbx.executions.append(exec_result.to_dict())
        sbx.resource_usage = resource_usage
        sbx.artifacts.extend(artifacts)
        if "execution" not in sbx.timing:
            sbx.timing["total_execution_ms"] = 0
        sbx.timing["total_execution_ms"] = sbx.timing.get("total_execution_ms", 0) + exec_elapsed

        sbx.logs.append({
            "type": "execution",
            "message": f"Executed: {resolved_cmd[:120]} -> exit={result.exit_code} duration={exec_elapsed:.0f}ms",
            "exit_code": result.exit_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        if exec_result.succeeded():
            sbx.status = "completed"
            status_tag = EET.SANDBOX_EXECUTION_COMPLETED
        else:
            sbx.status = "failed"
            sbx.error = result.stderr[:500]
            status_tag = EET.SANDBOX_EXECUTION_FAILED

        sbx.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        await self._emit(status_tag, sbx, {
            "execution_id": exec_id,
            "exit_code": result.exit_code,
            "duration_ms": exec_elapsed,
            "artifacts_count": len(artifacts),
        })
        await self._emit(EET.SANDBOX_ARTIFACTS_GENERATED, sbx, {
            "execution_id": exec_id,
            "artifacts": artifacts,
        })

        log.info("Sandbox execution: %s %s exit=%d %.0fms",
                 sbx.sandbox_id, resolved_cmd[:60], result.exit_code, exec_elapsed)
        return exec_result

    def _resolve_command(self, command: str, language: str, repo_dir: Path) -> List[str]:
        if command:
            import shlex
            return shlex.split(command)

        default_commands: Dict[str, List[str]] = {
            "python": [sys_executable(), "-m", "pytest"] if _has_file(repo_dir, "pytest.ini") or _has_file(repo_dir, "setup.cfg") or _has_file(repo_dir, "pyproject.toml") else [sys_executable(), "-c", "print('No test config found')"],
            "node": ["npx", "jest"] if _has_file(repo_dir, "jest.config.*") else ["npm", "test"],
            "java": ["mvn", "test"],
            "dotnet": ["dotnet", "test"],
            "go": ["go", "test", "./..."],
            "rust": ["cargo", "test"],
        }
        lang_lower = language.lower()
        if lang_lower in default_commands:
            return default_commands[lang_lower]
        return ["echo", f"No default command for language: {language}"]

    # ── Part 4: Artifact Collection ──────────────────────────────────────────

    async def _collect_artifacts(
        self,
        sbx: Sandbox,
        iso_path: Path,
        language: str,
    ) -> List[Dict[str, Any]]:
        artifacts: List[Dict[str, Any]] = []
        repo_dir = iso_path / "repo"

        artifact_patterns: Dict[str, List[str]] = {
            "python": ["pytest-report.xml", "coverage.xml", ".coverage", "htmlcov/*", "*.log"],
            "node": ["junit.xml", "coverage/*", "lcov.info", "test-results/*", "*.log"],
            "java": ["target/surefire-reports/*", "target/*.jar", "target/*.war", "*.log"],
            "dotnet": ["TestResults/*", "bin/Release/*", "*.log"],
            "go": ["coverage.out", "*.test", "*.log"],
            "rust": ["target/debug/*", "target/release/*", "*.log"],
            "shell": ["*.log", "*.out", "*.txt"],
        }

        patterns = artifact_patterns.get(language.lower(), ["*.log", "*.out", "*.xml", "*.json"])
        for pattern in patterns:
            matched = list(repo_dir.glob(pattern))
            for path in matched:
                if path.is_file():
                    try:
                        size = path.stat().st_size
                        artifact = {
                            "name": path.name,
                            "path": str(path.relative_to(repo_dir)) if repo_dir in path.parents else str(path),
                            "size_bytes": size,
                            "type": self._classify_artifact(path.name, language),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                        }
                        artifacts.append(artifact)
                    except Exception:
                        continue

        return artifacts

    def _classify_artifact(self, name: str, language: str) -> str:
        if name.endswith(".xml"):
            return "report"
        if name.endswith(".log"):
            return "log"
        if name.endswith((".jar", ".war", ".exe", ".dll")):
            return "binary"
        if name.endswith((".pyc", ".pyo")):
            return "compiled"
        if "coverage" in name or name == ".coverage":
            return "coverage"
        if "report" in name or "result" in name:
            return "report"
        return "generated"

    # ── Part 5: Resource Monitoring ──────────────────────────────────────────

    async def get_resource_usage(self, sandbox_id: str) -> Optional[Dict[str, Any]]:
        sbx = self._sandboxes.get(sandbox_id)
        if not sbx:
            return None
        iso_path = self._get_isolation_path(sbx)
        current = {
            "cpu_percent": _get_cpu_percent(),
            "memory_mb": _get_memory_usage(),
            "disk_mb": _get_disk_usage(iso_path) if iso_path else 0,
            "execution_count": len(sbx.executions),
            "artifact_count": len(sbx.artifacts),
            "total_artifact_size_bytes": sum(a.get("size_bytes", 0) for a in sbx.artifacts),
            "total_execution_time_ms": sbx.timing.get("total_execution_ms", 0),
        }
        return current

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _get_isolation_path(self, sbx: Sandbox) -> Optional[Path]:
        if sbx.isolation_path:
            return Path(sbx.isolation_path)
        iso_path = self._isolation_root / sbx.sandbox_id
        try:
            iso_path.mkdir(parents=True, exist_ok=True)
            sbx.isolation_path = str(iso_path)
        except Exception:
            return None
        return iso_path

    async def _run_command(
        self,
        cmd: List[str],
        cwd: Path,
        timeout: int = 120,
    ) -> ExecutionResult:
        exec_id = f"exec-{uuid.uuid4().hex[:12]}"
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                elapsed = (time.monotonic() - start) * 1000
                return ExecutionResult(
                    execution_id=exec_id,
                    command=" ".join(cmd),
                    exit_code=-1,
                    stdout="",
                    stderr=f"Command timed out after {timeout}s",
                    duration_ms=elapsed,
                )
            elapsed = (time.monotonic() - start) * 1000
            return ExecutionResult(
                execution_id=exec_id,
                command=" ".join(cmd),
                exit_code=proc.returncode or 0,
                stdout=stdout.decode("utf-8", errors="replace") if stdout else "",
                stderr=stderr.decode("utf-8", errors="replace") if stderr else "",
                duration_ms=elapsed,
            )
        except FileNotFoundError:
            elapsed = (time.monotonic() - start) * 1000
            return ExecutionResult(
                execution_id=exec_id,
                command=" ".join(cmd),
                exit_code=-1,
                stdout="",
                stderr=f"Command not found: {cmd[0]}",
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return ExecutionResult(
                execution_id=exec_id,
                command=" ".join(cmd),
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                duration_ms=elapsed,
            )

    # ── Logs ─────────────────────────────────────────────────────────────────

    async def get_logs(self, sandbox_id: str) -> List[Dict[str, Any]]:
        sbx = self._sandboxes.get(sandbox_id)
        if not sbx:
            return []
        return sbx.logs

    async def get_artifacts(self, sandbox_id: str) -> List[Dict[str, Any]]:
        sbx = self._sandboxes.get(sandbox_id)
        if not sbx:
            return []
        return sbx.artifacts

    # ── Events ──────────────────────────────────────────────────────────────

    async def _emit(
        self,
        event_type: str,
        sbx: Sandbox,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=event_type,
                agent="execution_sandbox",
                status=sbx.status,
                message=f"Sandbox {sbx.sandbox_id}: {event_type.split('.')[-1]}",
                execution_id=sbx.sandbox_id,
                metadata={
                    "sandbox_id": sbx.sandbox_id,
                    "sandbox_name": sbx.name,
                    "language": sbx.language,
                    "repo_url": sbx.repo_url,
                    "branch": sbx.branch,
                    "status": sbx.status,
                    "domain": "sandbox",
                    **(extra or {}),
                },
            )
        except Exception as exc:
            log.debug("Sandbox event emit failed: %s", exc)

    # ── Persistence ──────────────────────────────────────────────────────────

    def _persist(self) -> None:
        try:
            _save_sandboxes([s.to_dict() for s in self._sandboxes.values()])
        except Exception as exc:
            log.warning("Sandbox persistence failed: %s", exc)

    def _load_persisted(self) -> None:
        try:
            for item in _load_sandboxes():
                sbx = Sandbox.from_dict(item)
                self._sandboxes[sbx.sandbox_id] = sbx
            log.info("Loaded %d sandboxes", len(self._sandboxes))
        except Exception as exc:
            log.warning("Sandbox load failed: %s", exc)


# =============================================================================
# Helpers
# =============================================================================

def _get_cpu_percent() -> float:
    try:
        import psutil
        return psutil.cpu_percent(interval=0.1)
    except ImportError:
        return 0.0


def _get_memory_usage() -> float:
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        return proc.memory_info().rss / (1024 * 1024)
    except ImportError:
        if resource is not None:
            try:
                return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            except AttributeError:
                return 0.0
        return 0.0


def _get_disk_usage(path: Optional[Path]) -> float:
    if not path or not path.exists():
        return 0.0
    try:
        import psutil
        usage = psutil.disk_usage(str(path))
        return usage.used / (1024 * 1024)
    except ImportError:
        total = 0
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except Exception:
                    pass
        return total / (1024 * 1024)


def sys_executable() -> str:
    import sys
    return sys.executable


def _has_file(directory: Path, pattern: str) -> bool:
    return len(list(directory.glob(pattern))) > 0


# =============================================================================
# Singleton
# =============================================================================

execution_sandbox = EnterpriseExecutionSandbox()
