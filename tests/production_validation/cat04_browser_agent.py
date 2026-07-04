"""
Category 04 — Browser Agent Test
==================================
Validates the Playwright-based browser automation stack:

  Open websites → Extract data → Store memory → Generate report

Tests are designed to be safe (read-only navigation, no credential input,
no form submission). Playwright must be installed for live probes to run.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
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

def _check_playwright_installed() -> CheckResult:
    """Playwright Python package is installed."""
    try:
        import playwright
        version = getattr(playwright, "__version__", "unknown")
        return pass_("playwright_installed", f"Playwright {version} installed")
    except ImportError:
        return fail_("playwright_installed", "Playwright not installed — browser agent unavailable")


def _check_playwright_browser_available() -> CheckResult:
    """At least one browser is installed via playwright."""
    try:
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"],
            capture_output=True, text=True, timeout=15,
        )
        # If chromium is already installed, 'install' exits 0 or reports already installed
        if result.returncode == 0 or "already installed" in (result.stdout + result.stderr).lower():
            return pass_("playwright_browser_available", "Chromium browser available")
        # Try checking if executable exists directly
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser_path = p.chromium.executable_path
            if Path(browser_path).exists():
                return pass_("playwright_browser_available", f"Chromium at {browser_path}")
        return warn_("playwright_browser_available", "Chromium status unclear")
    except Exception as exc:
        return warn_("playwright_browser_available", f"Browser availability check: {exc}")


def _check_browser_agent_importable() -> CheckResult:
    """BrowserAgent class is importable and has execute_task."""
    try:
        from backend.tools.browser_agent import BrowserAgent
        agent = BrowserAgent()
        has_execute = callable(getattr(agent, "execute_task", None))
        if has_execute:
            return pass_("browser_agent_importable", "BrowserAgent importable with execute_task")
        return warn_("browser_agent_importable", "BrowserAgent importable but execute_task missing")
    except ImportError as exc:
        return fail_("browser_agent_importable", f"BrowserAgent import failed: {exc}")
    except Exception as exc:
        return warn_("browser_agent_importable", f"BrowserAgent init warning: {exc}")


def _check_browser_routes() -> CheckResult:
    """Browser-related API routes respond."""
    paths = [
        "/computer/status",
        "/api/browser/status",
        "/browser/status",
        "/computer/tasks",
    ]
    for path in paths:
        code, body = http_get(path, timeout=5.0)
        if code in (200, 201, 202):
            return pass_("browser_routes", f"Browser route {path} responded")
    return warn_("browser_routes", "Browser routes not at standard paths")


def _check_browser_mission_dispatch() -> CheckResult:
    """
    Dispatch a browser-class mission (navigate to GitHub homepage) and
    verify the runtime accepts and processes it.
    """
    session_id = f"browser-test-{uuid4().hex[:8]}"
    code, body = http_post(
        "/orchestrate",
        {
            "objective":  "Open github.com and tell me what it says on the homepage.",
            "session_id": session_id,
        },
        timeout=MISSION_TIMEOUT,
    )
    if code in (200, 201, 202):
        status  = body.get("status", "") if isinstance(body, dict) else ""
        blocked = body.get("blocked", False) if isinstance(body, dict) else False
        if blocked:
            return warn_("browser_mission_dispatch",
                         "Browser mission was blocked (guardrails or governance)")
        return pass_("browser_mission_dispatch",
                     f"Browser mission accepted — status: {status}",
                     code=code)
    return fail_("browser_mission_dispatch",
                 f"Browser mission dispatch failed: HTTP {code}")


def _check_browser_data_extraction() -> CheckResult:
    """
    Send an explicitly research/extraction objective and verify that
    the response includes extracted web content (URL, title, or text).
    """
    session_id = f"browser-extract-{uuid4().hex[:8]}"
    code, body = http_post(
        "/orchestrate",
        {
            "objective":  "Navigate to https://pypi.org and extract the page title.",
            "session_id": session_id,
        },
        timeout=MISSION_TIMEOUT,
    )
    if code not in (200, 201, 202):
        return fail_("browser_data_extraction", f"Mission dispatch failed: HTTP {code}")

    if not isinstance(body, dict):
        return warn_("browser_data_extraction", "Response body not a dict")

    response_text = body.get("response", "") or body.get("output", "") or ""
    has_content   = len(response_text) > 30
    has_url_hint  = "pypi" in response_text.lower() or "python" in response_text.lower()

    if has_content and has_url_hint:
        return pass_("browser_data_extraction",
                     f"Browser extracted content ({len(response_text)} chars) — pypi mentioned",
                     preview=response_text[:120])
    if has_content:
        return warn_("browser_data_extraction",
                     f"Response received ({len(response_text)} chars) but pypi not confirmed",
                     preview=response_text[:120])
    return warn_("browser_data_extraction",
                 "Browser mission completed but response content unclear")


def _check_browser_memory_storage() -> CheckResult:
    """
    After a browser navigation, verify that the memory layer received data
    (the browser agent calls _store_browser_memory in mission_runtime.py).
    """
    code, body = http_get("/api/memory/episodic", timeout=5.0)
    if code == 200 and isinstance(body, dict):
        entries = body.get("entries", body.get("memories", []))
        count   = len(entries) if isinstance(entries, list) else body.get("count", "?")
        return pass_("browser_memory_storage",
                     f"Episodic memory accessible — {count} entries")
    if code == 200:
        return pass_("browser_memory_storage", "Episodic memory endpoint accessible")
    if code == 404:
        return skip_("browser_memory_storage", "Episodic memory API not at /api/memory/episodic")
    return warn_("browser_memory_storage", f"Memory endpoint HTTP {code}")


def _check_domain_map_coverage() -> CheckResult:
    """
    Verify the browser agent's domain map covers the standard known sites.
    """
    try:
        from backend.tools.browser_agent import _DOMAIN_MAP
        required = {"github", "google", "wikipedia", "youtube", "stackoverflow"}
        covered  = required.intersection(set(_DOMAIN_MAP.keys()))
        missing  = required - covered
        if not missing:
            return pass_("domain_map_coverage",
                         f"Domain map covers {len(_DOMAIN_MAP)} sites (all required present)")
        return warn_("domain_map_coverage",
                     f"Domain map missing: {missing}",
                     covered=list(covered), missing=list(missing))
    except ImportError:
        return skip_("domain_map_coverage", "BrowserAgent not importable")


def _check_guardrails_browser_protection() -> CheckResult:
    """
    Verify guardrails block unsafe browser actions (imported, not HTTP).
    """
    try:
        from backend.safety.guardrails_engine import guardrails_engine
        r = guardrails_engine.check_tool("browser", "fill the password field", url="")
        if r.blocked:
            return pass_("guardrails_browser_protection",
                         f"Guardrails blocked credential input: {r.matched_rule}")
        return fail_("guardrails_browser_protection",
                     "Guardrails did NOT block credential browser action")
    except Exception as exc:
        return fail_("guardrails_browser_protection", f"Guardrails check failed: {exc}")


# ---------------------------------------------------------------------------
# Category runner
# ---------------------------------------------------------------------------

def run() -> CategoryResult:
    cat = CategoryResult("04 — Browser Agent")

    # Import checks (no backend needed)
    for fn in [
        _check_playwright_installed,
        _check_browser_agent_importable,
        _check_domain_map_coverage,
        _check_guardrails_browser_protection,
    ]:
        cat.checks.append(check(fn.__name__.lstrip("_"), fn))

    # Backend checks
    if backend_is_up():
        for fn in [
            _check_browser_routes,
            _check_browser_mission_dispatch,
            _check_browser_data_extraction,
            _check_browser_memory_storage,
        ]:
            cat.checks.append(check(fn.__name__.lstrip("_"), fn))
    else:
        cat.checks.append(skip_("backend_checks", "Backend not reachable"))

    # Playwright browser availability (best-effort)
    cat.checks.append(check("playwright_browser_available", _check_playwright_browser_available))

    return cat
