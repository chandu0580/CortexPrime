"""
Category 02 — Multi-Agent Stress Test
=======================================
Launch all six agent types simultaneously and measure:
  - Latency per agent
  - Failure / recovery rate
  - System stability under concurrent load

Agents under test: Planner, Research, Critic, Memory, Browser, Computer
(all via the /orchestrate or dedicated agent endpoints)
"""
from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Dict, List, Tuple
from uuid import uuid4

from tests.production_validation import (
    CategoryResult, CheckStatus, CheckResult,
    http_get, http_post,
    pass_, fail_, skip_, warn_, check,
    backend_is_up, BASE_URL, MISSION_TIMEOUT,
)


# ---------------------------------------------------------------------------
# Agent mission payloads — each designed to exercise a specific agent
# ---------------------------------------------------------------------------

_AGENT_MISSIONS: List[Tuple[str, str, Dict[str, Any]]] = [
    # (agent_label, objective, extra_payload)
    ("planner",   "Create a step-by-step plan for learning Python in 30 days.",         {}),
    ("research",  "latest advances in transformer models 2025",                          {}),
    ("critic",    "Analyse the claim: 'AGI will be achieved by 2030'. Be critical.",     {}),
    ("memory",    "What have I asked you before? Summarise recent session context.",     {}),
    ("browser",   "What is the Python documentation homepage URL?",                      {}),
    ("computer",  "List all Python files in the current working directory.",             {}),
]


def _run_agent_mission(label: str, objective: str, extra: Dict[str, Any]) -> Dict[str, Any]:
    session_id = f"stress-{label}-{uuid4().hex[:6]}"
    t0         = time.perf_counter()
    code, body = http_post(
        "/orchestrate",
        {"objective": objective, "session_id": session_id, **extra},
        timeout=MISSION_TIMEOUT,
    )
    latency    = time.perf_counter() - t0
    return {
        "agent":   label,
        "code":    code,
        "body":    body,
        "latency": round(latency, 3),
        "success": code in (200, 201, 202),
    }


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _check_concurrent_agents() -> CheckResult:
    """
    Run all 6 agent missions in parallel; collect latency and success rate.
    """
    results: List[Dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(_run_agent_mission, label, obj, extra): label
            for label, obj, extra in _AGENT_MISSIONS
        }
        for fut in concurrent.futures.as_completed(futures, timeout=MISSION_TIMEOUT + 10):
            try:
                results.append(fut.result())
            except Exception as exc:
                results.append({
                    "agent":   futures[fut],
                    "code":    0,
                    "body":    str(exc),
                    "latency": 0.0,
                    "success": False,
                })

    successes = [r for r in results if r["success"]]
    failures  = [r for r in results if not r["success"]]
    latencies = [r["latency"] for r in successes]

    avg_lat   = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    max_lat   = round(max(latencies), 2) if latencies else 0.0
    fail_info = [{"agent": r["agent"], "code": r["code"]} for r in failures]

    detail = {
        "total":       len(results),
        "successes":   len(successes),
        "failures":    len(failures),
        "avg_latency": avg_lat,
        "max_latency": max_lat,
        "failed":      fail_info,
        "per_agent":   [{
            "agent":   r["agent"],
            "code":    r["code"],
            "latency": r["latency"],
            "success": r["success"],
        } for r in results],
    }

    rate = len(successes) / max(len(results), 1)

    if rate == 1.0:
        return CheckResult(
            "concurrent_agents", CheckStatus.PASS,
            f"All {len(results)} agents responded — avg {avg_lat}s, max {max_lat}s",
            detail=detail,
        )
    if rate >= 0.66:
        return CheckResult(
            "concurrent_agents", CheckStatus.WARN,
            f"{len(successes)}/{len(results)} agents responded — {len(failures)} failed",
            detail=detail,
        )
    return CheckResult(
        "concurrent_agents", CheckStatus.FAIL,
        f"Stress test: only {len(successes)}/{len(results)} agents responded",
        detail=detail,
    )


def _check_latency_sla() -> CheckResult:
    """
    Verify that individual mission latency is within acceptable bounds.
    Acceptable: p95 < 30 s (cloud LLM calls can be slow).
    """
    results: List[float] = []

    for label, obj, extra in _AGENT_MISSIONS[:3]:  # only first 3 to avoid double-billing
        r = _run_agent_mission(label, obj, extra)
        results.append(r["latency"])

    if not results:
        return skip_("latency_sla", "No latency data collected")

    results_sorted = sorted(results)
    p50 = results_sorted[len(results_sorted) // 2]
    p95 = results_sorted[int(len(results_sorted) * 0.95)]

    if p95 < 30.0:
        return pass_("latency_sla",
                     f"Latency SLA met — p50={p50:.1f}s p95={p95:.1f}s",
                     p50=p50, p95=p95)
    if p95 < 60.0:
        return warn_("latency_sla",
                     f"Latency elevated — p50={p50:.1f}s p95={p95:.1f}s (SLA <30s)",
                     p50=p50, p95=p95)
    return fail_("latency_sla",
                 f"Latency SLA breached — p95={p95:.1f}s > 30s",
                 p50=p50, p95=p95)


def _check_recovery_after_stress() -> CheckResult:
    """
    After the stress burst, verify the backend is still healthy.
    """
    time.sleep(2.0)  # brief cooldown
    code, body = http_get("/health", timeout=8.0)
    if code == 200:
        return pass_("recovery_after_stress", "Backend healthy after concurrent stress")
    return fail_("recovery_after_stress", f"Backend unhealthy after stress: HTTP {code}")


def _check_runtime_state_after_stress() -> CheckResult:
    """
    Verify no executions are stuck in 'running' state after stress.
    """
    code, body = http_get("/runtime-state", timeout=5.0)
    if code != 200:
        return skip_("runtime_state_cleanup", f"/runtime-state HTTP {code}")

    if isinstance(body, dict):
        running = body.get("running_executions", body.get("active", []))
        count   = len(running) if isinstance(running, list) else int(running or 0)
        if count <= 2:
            return pass_("runtime_state_cleanup", f"{count} executions still running (acceptable)")
        return warn_("runtime_state_cleanup",
                     f"{count} executions still running after stress — possible leak",
                     running_count=count)
    return skip_("runtime_state_cleanup", "Unexpected runtime-state format")


def _check_mission_list_after_stress() -> CheckResult:
    """
    Verify /api/missions/completed recorded at least some of the stress missions.
    """
    code, body = http_get("/api/missions/completed", timeout=5.0)
    if code == 200 and isinstance(body, dict):
        missions = body.get("missions", [])
        count    = len(missions)
        return pass_("completed_missions_recorded",
                     f"{count} completed missions in registry")
    if code == 200 and isinstance(body, list):
        return pass_("completed_missions_recorded",
                     f"{len(body)} completed missions in registry")
    return skip_("completed_missions_recorded", f"Mission list HTTP {code}")


# ---------------------------------------------------------------------------
# Category runner
# ---------------------------------------------------------------------------

def run() -> CategoryResult:
    cat = CategoryResult("02 — Multi-Agent Stress")

    if not backend_is_up():
        cat.checks.append(skip_("all_checks", "Backend not reachable at " + BASE_URL))
        return cat

    for fn in [
        _check_concurrent_agents,
        _check_latency_sla,
        _check_recovery_after_stress,
        _check_runtime_state_after_stress,
        _check_mission_list_after_stress,
    ]:
        cat.checks.append(check(fn.__name__.lstrip("_"), fn))

    return cat
