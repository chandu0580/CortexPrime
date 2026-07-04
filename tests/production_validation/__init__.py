"""
CortexPrime Production Validation Suite
========================================
Shared infrastructure: result types, probe helpers, constants.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.request
import urllib.error

# ── Base URL ────────────────────────────────────────────────────────────────
BASE_URL = os.getenv("VALIDATION_BASE_URL", "http://localhost:8000")
WS_URL   = BASE_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws"

# ── Timeouts ────────────────────────────────────────────────────────────────
HTTP_TIMEOUT   = float(os.getenv("HTTP_TIMEOUT",   "10"))
WS_TIMEOUT     = float(os.getenv("WS_TIMEOUT",     "20"))
MISSION_TIMEOUT = float(os.getenv("MISSION_TIMEOUT", "45"))

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class CheckStatus(str, Enum):
    PASS    = "pass"
    FAIL    = "fail"
    SKIP    = "skip"
    WARN    = "warn"


@dataclass
class CheckResult:
    name:      str
    status:    CheckStatus
    message:   str
    duration:  float = 0.0
    detail:    Optional[Dict[str, Any]] = None

    def passed(self) -> bool:
        return self.status == CheckStatus.PASS

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name":     self.name,
            "status":   self.status.value,
            "message":  self.message,
            "duration": round(self.duration, 3),
            "detail":   self.detail,
        }


@dataclass
class CategoryResult:
    name:    str
    checks:  List[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.FAIL)

    @property
    def skipped(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.SKIP)

    @property
    def warned(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.WARN)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def score(self) -> float:
        """0–100 score: passes count full, warns count half, fails count zero."""
        if self.total == 0:
            return 0.0
        pts = sum(
            1.0 if c.status == CheckStatus.PASS else
            0.5 if c.status == CheckStatus.WARN else
            1.0 if c.status == CheckStatus.SKIP else   # skips are neutral
            0.0
            for c in self.checks
        )
        eligible = sum(
            1 for c in self.checks if c.status != CheckStatus.SKIP
        )
        if eligible == 0:
            return 100.0
        return round(pts / eligible * 100, 1)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name":    self.name,
            "score":   self.score,
            "passed":  self.passed,
            "failed":  self.failed,
            "skipped": self.skipped,
            "warned":  self.warned,
            "total":   self.total,
            "checks":  [c.as_dict() for c in self.checks],
        }


# ---------------------------------------------------------------------------
# HTTP helpers (no external deps — stdlib only)
# ---------------------------------------------------------------------------

def http_get(path: str, timeout: float = HTTP_TIMEOUT) -> Tuple[int, Any]:
    """Return (status_code, parsed_json_or_None)."""
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
            return e.code, json.loads(body)
        except Exception:
            return e.code, None
    except Exception as exc:
        return 0, {"error": str(exc)}


def http_post(path: str, payload: Dict[str, Any], timeout: float = HTTP_TIMEOUT) -> Tuple[int, Any]:
    """Return (status_code, parsed_json_or_None)."""
    url     = f"{BASE_URL}{path}"
    data    = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
            return e.code, json.loads(body)
        except Exception:
            return e.code, None
    except Exception as exc:
        return 0, {"error": str(exc)}


# ---------------------------------------------------------------------------
# Timed check wrapper
# ---------------------------------------------------------------------------

def timed(name: str):
    """Decorator: wraps a function that returns CheckResult to track duration."""
    def decorator(fn: Callable[[], CheckResult]) -> Callable[[], CheckResult]:
        def wrapper() -> CheckResult:
            t0 = time.perf_counter()
            result = fn()
            result.duration = time.perf_counter() - t0
            return result
        return wrapper
    return decorator


def check(name: str, fn: Callable[[], CheckResult]) -> CheckResult:
    """Run a check function and return a CheckResult, capturing any exceptions."""
    t0 = time.perf_counter()
    try:
        result = fn()
        result.duration = time.perf_counter() - t0
        return result
    except Exception as exc:
        return CheckResult(
            name     = name,
            status   = CheckStatus.FAIL,
            message  = f"Check raised exception: {exc}",
            duration = time.perf_counter() - t0,
            detail   = {"exception": type(exc).__name__},
        )


def pass_(name: str, message: str = "OK", **detail) -> CheckResult:
    return CheckResult(name, CheckStatus.PASS, message, detail=detail or None)


def fail_(name: str, message: str, **detail) -> CheckResult:
    return CheckResult(name, CheckStatus.FAIL, message, detail=detail or None)


def skip_(name: str, message: str = "Skipped — infrastructure unavailable") -> CheckResult:
    return CheckResult(name, CheckStatus.SKIP, message)


def warn_(name: str, message: str, **detail) -> CheckResult:
    return CheckResult(name, CheckStatus.WARN, message, detail=detail or None)


# ---------------------------------------------------------------------------
# Backend availability probe
# ---------------------------------------------------------------------------

def backend_is_up() -> bool:
    code, _ = http_get("/health", timeout=3.0)
    return code == 200
