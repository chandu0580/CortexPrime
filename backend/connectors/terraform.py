"""Terraform CLI connector.

Executes terraform commands as subprocesses and returns structured results.

  - terraform init       — initialize a working directory
  - terraform validate   — validate configuration
  - terraform fmt        — format configuration
  - terraform plan       — generate execution plan
  - terraform apply      — apply changes
  - terraform destroy    — destroy infrastructure
  - terraform output     — read outputs
  - terraform state      — state management
  - terraform providers  — list providers
  - terraform version    — version info
  - terraform workspace  — workspace management
  - terraform show       — show plan/state

Follows BaseConnector pattern with graceful degradation.
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


class TerraformExecutionError(Exception):
    """Raised when a terraform command exits with a non-zero status."""

    def __init__(self, cmd: str, returncode: int, stdout: str, stderr: str) -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"terraform {cmd} exited {returncode}: {stderr[:500]}")


class TerraformResult:
    """Structured result from a terraform execution."""

    def __init__(
        self, success: bool, cmd: str, stdout: str, stderr: str,
        returncode: int, duration_seconds: float,
    ) -> None:
        self.success = success
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.duration_seconds = duration_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "cmd": self.cmd,
            "stdout": self.stdout[:5000],
            "stderr": self.stderr[:2000],
            "returncode": self.returncode,
            "duration_seconds": round(self.duration_seconds, 2),
        }


class TerraformConnector:
    """Terraform CLI connector — executes terraform commands as subprocesses.

    Manages workspace directories and terraform binary path.
    """

    connector_type = "terraform"
    connector_name = "Terraform IaC"

    def __init__(
        self,
        terraform_binary: str = "terraform",
        workspace_dir: str = "",
        timeout: int = 300,
    ) -> None:
        self._binary = terraform_binary
        self._workspace_dir = Path(workspace_dir) if workspace_dir else Path(tempfile.mkdtemp(prefix="cortex_terraform_"))
        self._timeout = timeout
        self._ready = False
        self._version: str = ""

    async def initialize(self) -> bool:
        try:
            result = await self._run("version", capture_output=True)
            if result.success:
                # Extract version from output like "Terraform v1.9.0"
                match = re.search(r"Terraform\s+v?(\d+\.\d+\.\d+)", result.stdout)
                self._version = match.group(1) if match else "unknown"
                log.info("Terraform connector active — v%s at %s", self._version, self._workspace_dir)
                self._ready = True
                return True
            else:
                log.warning("Terraform binary not functional: %s", result.stderr[:200])
                self._ready = False
                return False
        except FileNotFoundError:
            log.debug("Terraform binary '%s' not found", self._binary)
            self._ready = False
            return False
        except Exception as exc:
            log.debug("Terraform connector init failed: %s", exc)
            self._ready = False
            return False

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def version(self) -> str:
        return self._version

    @property
    def workspace_dir(self) -> Path:
        return self._workspace_dir

    def set_workspace_dir(self, path: str) -> None:
        self._workspace_dir = Path(path)
        self._workspace_dir.mkdir(parents=True, exist_ok=True)

    async def close(self) -> None:
        self._ready = False

    async def shutdown(self) -> bool:
        self._ready = False
        return True

    async def health(self) -> Dict[str, Any]:
        if self._ready:
            return {"connector": self.connector_type, "status": "available", "version": self._version, "workspace_dir": str(self._workspace_dir)}
        try:
            ok = await self.initialize()
            return {"connector": self.connector_type, "status": "available" if ok else "unavailable", "version": self._version}
        except Exception as exc:
            return {"connector": self.connector_type, "status": "unavailable", "error": str(exc)[:200]}

    async def _run(
        self, cmd_str: str, capture_output: bool = True, input_data: Optional[str] = None,
        env: Optional[Dict[str, str]] = None, cwd: Optional[str] = None,
    ) -> TerraformResult:
        full_cmd = f"{self._binary} {cmd_str}"
        import asyncio
        import time

        work_dir = cwd or str(self._workspace_dir)
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                self._binary, *cmd_str.split(),
                stdout=asyncio.subprocess.PIPE if capture_output else None,
                stderr=asyncio.subprocess.PIPE if capture_output else None,
                stdin=asyncio.subprocess.PIPE if input_data else None,
                cwd=work_dir,
                env={**os.environ, **(env or {})},
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=input_data.encode() if input_data else None),
                timeout=self._timeout,
            )
            duration = time.monotonic() - start
            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            success = proc.returncode == 0
            return TerraformResult(success, full_cmd, stdout, stderr, proc.returncode or -1, duration)
        except asyncio.TimeoutError:
            duration = time.monotonic() - start
            return TerraformResult(False, full_cmd, "", f"Command timed out after {self._timeout}s", -1, duration)
        except FileNotFoundError:
            return TerraformResult(False, full_cmd, "", f"Binary '{self._binary}' not found", -1, 0)
        except Exception as exc:
            duration = time.monotonic() - start
            return TerraformResult(False, full_cmd, "", str(exc), -1, duration)

    # ---- Core commands ----

    async def init(self, upgrade: bool = False) -> TerraformResult:
        cmd = "init -no-color -input=false"
        if upgrade:
            cmd += " -upgrade"
        return await self._run(cmd)

    async def validate(self) -> TerraformResult:
        return await self._run("validate -no-color -json")

    async def fmt(self, check: bool = False, recursive: bool = False) -> TerraformResult:
        cmd = "fmt -no-color"
        if check:
            cmd += " -check"
        if recursive:
            cmd += " -recursive"
        return await self._run(cmd)

    async def plan(
        self, out: str = "tfplan", destroy: bool = False,
        vars: Optional[Dict[str, str]] = None, var_file: str = "",
    ) -> TerraformResult:
        cmd = f"plan -no-color -input=false -out={out}"
        if destroy:
            cmd += " -destroy"
        if var_file:
            cmd += f" -var-file={var_file}"
        if vars:
            for k, v in vars.items():
                cmd += f' -var="{k}={v}"'
        return await self._run(cmd)

    async def apply(self, plan_file: str = "tfplan", auto_approve: bool = True) -> TerraformResult:
        cmd = "apply -no-color -input=false"
        if auto_approve:
            cmd += " -auto-approve"
        if plan_file:
            cmd += f" {plan_file}"
        return await self._run(cmd)

    async def destroy(self, auto_approve: bool = True, vars: Optional[Dict[str, str]] = None) -> TerraformResult:
        cmd = "destroy -no-color -input=false"
        if auto_approve:
            cmd += " -auto-approve"
        if vars:
            for k, v in vars.items():
                cmd += f' -var="{k}={v}"'
        return await self._run(cmd)

    async def output(self, name: str = "", json_format: bool = True) -> TerraformResult:
        cmd = "output -no-color"
        if json_format:
            cmd += " -json"
        if name:
            cmd += f" {name}"
        return await self._run(cmd)

    async def state_list(self) -> TerraformResult:
        return await self._run("state list -no-color")

    async def state_show(self, address: str) -> TerraformResult:
        return await self._run(f"state show -no-color {address}")

    async def state_rm(self, address: str) -> TerraformResult:
        return await self._run(f"state rm -no-color {address}")

    async def providers(self) -> TerraformResult:
        return await self._run("providers -no-color")

    async def get_version(self) -> TerraformResult:
        return await self._run("version", capture_output=True)

    async def show(self, plan_file: str = "tfplan") -> TerraformResult:
        return await self._run(f"show -no-color -json {plan_file}")

    async def workspace_list(self) -> TerraformResult:
        return await self._run("workspace list -no-color")

    async def workspace_new(self, name: str) -> TerraformResult:
        return await self._run(f"workspace new -no-color {name}")

    async def workspace_select(self, name: str) -> TerraformResult:
        return await self._run(f"workspace select -no-color {name}")

    async def workspace_delete(self, name: str) -> TerraformResult:
        return await self._run(f"workspace delete -no-color {name}")

    async def workspace_show(self) -> TerraformResult:
        return await self._run("workspace show -no-color")

    async def import_resource(self, address: str, resource_id: str) -> TerraformResult:
        return await self._run(f"import -no-color -input=false {address} {resource_id}")

    async def refresh(self) -> TerraformResult:
        return await self._run("refresh -no-color -input=false")


terraform_connector = TerraformConnector()
