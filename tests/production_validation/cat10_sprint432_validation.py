"""
Category 10 — Sprint 43.2 Fixes Validation
===========================================
Validates 5 specific fixes applied in Sprint 43.2:

  1. Neo4j Execution completion — status, duration, summary persisted
  2. Mission node creation with HAS_EXECUTION → Execution relationship
  3. Replay integrity — unique event_id and timestamp per CognitionEvent
  4. Redis execution state persistence on every stage transition
  5. Active execution cleanup — removed from cx:rt:active ZSET on completion

Tests use import verification and AST analysis; no live backend needed.
"""
from __future__ import annotations

import ast
import inspect
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

from tests.production_validation import (
    CategoryResult, CheckResult, CheckStatus,
    pass_, fail_, skip_, warn_, check,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"

# ── Helpers ─────────────────────────────────────────────────────────────────

def _read_source(rel_path: str) -> str:
    full = BACKEND_DIR / rel_path
    return full.read_text(encoding="utf-8")


def _has_ast_import(tree: ast.AST, module: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module or alias.name.startswith(module + "."):
                    return True
    return False


def _has_ast_call(tree: ast.AST, func_name: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr == func_name:
                return True
            if isinstance(fn, ast.Name) and fn.id == func_name:
                return True
    return False


# =============================================================================
# CATEGORY RUNNER
# =============================================================================

def run_category() -> CategoryResult:
    cat = CategoryResult("Sprint 43.2 Fixes")

    # ── Fix 1: Neo4j Execution completion ─────────────────────────────────
    cat.checks.append(check("F1.1 complete_execution accepts duration_ms", _check_f1_duration))
    cat.checks.append(check("F1.2 complete_execution accepts summary",     _check_f1_summary))
    cat.checks.append(check("F1.3 complete_execution sets duration_ms",    _check_f1_cypher))
    cat.checks.append(check("F1.4 Neo4j Execution node created in pipeline",_check_f1_create_exec))

    # ── Fix 2: Mission node ────────────────────────────────────────────────
    cat.checks.append(check("F2.1 create_mission method exists",           _check_f2_create_mission))
    cat.checks.append(check("F2.2 link_mission_to_execution exists",       _check_f2_link))
    cat.checks.append(check("F2.3 HAS_EXECUTION relationship in schema",   _check_f2_has_execution))
    cat.checks.append(check("F2.4 Mission node created in pipeline",       _check_f2_mission_called))
    cat.checks.append(check("F2.5 Mission node completed on finish",       _check_f2_mission_complete))

    # ── Fix 3: Replay integrity ───────────────────────────────────────────
    cat.checks.append(check("F3.1 event_id uses default_factory",          _check_f3_event_id))
    cat.checks.append(check("F3.2 timestamp uses default_factory",         _check_f3_timestamp))
    cat.checks.append(check("F3.3 Field imported in event_models",         _check_f3_field_import))

    # ── Fix 4: Redis state persistence ────────────────────────────────────
    cat.checks.append(check("F4.1 runtime_state_store imported",           _check_f4_import))
    cat.checks.append(check("F4.2 runtime_state_store.start called",       _check_f4_start))
    cat.checks.append(check("F4.3 runtime_state_store.update called",      _check_f4_update))
    cat.checks.append(check("F4.4 runtime_state_store.complete called",    _check_f4_complete))

    # ── Fix 5: Active execution cleanup ───────────────────────────────────
    cat.checks.append(check("F5 complete removes from cx:rt:active",       _check_f5_active_cleanup))

    return cat


# =============================================================================
# FIX 1 — Neo4j Execution completion
# =============================================================================

def _check_f1_duration() -> CheckResult:
    src = _read_source("infrastructure/neo4j/graph_manager.py")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "complete_execution":
            params = {a.arg for a in node.args.args}
            if "duration_ms" in params:
                return pass_("F1.1", "duration_ms parameter present")
            return fail_("F1.1", "duration_ms parameter missing")
    return fail_("F1.1", "complete_execution method not found")


def _check_f1_summary() -> CheckResult:
    src = _read_source("infrastructure/neo4j/graph_manager.py")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "complete_execution":
            params = {a.arg for a in node.args.args}
            if "summary" in params:
                return pass_("F1.2", "summary parameter present")
            return fail_("F1.2", "summary parameter missing")
    return fail_("F1.2", "complete_execution method not found")


def _check_f1_cypher() -> CheckResult:
    src = _read_source("infrastructure/neo4j/graph_manager.py")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "complete_execution":
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    if "duration_ms" in child.value and "summary" in child.value:
                        return pass_("F1.3", "duration_ms and summary in Cypher SET clause")
            return fail_("F1.3", "duration_ms or summary not in Cypher SET clause")
    return fail_("F1.3", "complete_execution method not found")


def _check_f1_create_exec() -> CheckResult:
    src = _read_source("services/mission_runtime.py")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_run_pipeline":
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    fn = child.func
                    if isinstance(fn, ast.Attribute) and fn.attr == "create_execution":
                        return pass_("F1.4", "create_execution called in _run_pipeline")
            return fail_("F1.4", "create_execution not called in _run_pipeline")
    return fail_("F1.4", "_run_pipeline not found")


# =============================================================================
# FIX 2 — Mission node
# =============================================================================

def _check_f2_create_mission() -> CheckResult:
    src = _read_source("infrastructure/neo4j/graph_manager.py")
    if "async def create_mission" in src:
        return pass_("F2.1", "create_mission method found")
    return fail_("F2.1", "create_mission method missing")


def _check_f2_link() -> CheckResult:
    src = _read_source("infrastructure/neo4j/graph_manager.py")
    if "async def link_mission_to_execution" in src:
        return pass_("F2.2", "link_mission_to_execution method found")
    return fail_("F2.2", "link_mission_to_execution method missing")


def _check_f2_has_execution() -> CheckResult:
    src = _read_source("infrastructure/neo4j/schema.py")
    if "HAS_EXECUTION" in src:
        return pass_("F2.3", "HAS_EXECUTION relationship type defined")
    return fail_("F2.3", "HAS_EXECUTION relationship type missing")


def _check_f2_mission_called() -> CheckResult:
    src = _read_source("services/mission_runtime.py")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_run_pipeline":
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    fn = child.func
                    if isinstance(fn, ast.Attribute) and fn.attr == "create_mission":
                        return pass_("F2.4", "create_mission called in _run_pipeline")
            return fail_("F2.4", "create_mission not called in _run_pipeline")
    return fail_("F2.4", "_run_pipeline not found")


def _check_f2_mission_complete() -> CheckResult:
    src = _read_source("services/mission_runtime.py")
    if "m:Mission {mission_id:" in src:
        return pass_("F2.5", "Mission node status updated on completion")
    return fail_("F2.5", "Mission node completion update missing")


# =============================================================================
# FIX 3 — Replay integrity
# =============================================================================

def _check_f3_event_id() -> CheckResult:
    src = _read_source("events/event_models.py")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "CognitionEvent":
            for item in node.body:
                if isinstance(item, ast.AnnAssign):
                    target = item.target
                    if isinstance(target, ast.Name) and target.id == "event_id":
                        if item.value and "default_factory" in ast.dump(item.value):
                            return pass_("F3.1", "event_id uses default_factory")
                        return fail_("F3.1", "event_id does not use default_factory")
    return fail_("F3.1", "event_id not found in CognitionEvent")


def _check_f3_timestamp() -> CheckResult:
    src = _read_source("events/event_models.py")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "CognitionEvent":
            for item in node.body:
                if isinstance(item, ast.AnnAssign):
                    target = item.target
                    if isinstance(target, ast.Name) and target.id == "timestamp":
                        if item.value and "default_factory" in ast.dump(item.value):
                            return pass_("F3.2", "timestamp uses default_factory")
                        return fail_("F3.2", "timestamp does not use default_factory")
    return fail_("F3.2", "timestamp not found in CognitionEvent")


def _check_f3_field_import() -> CheckResult:
    src = _read_source("events/event_models.py")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "pydantic":
            names = {alias.name for alias in node.names}
            if "Field" in names:
                return pass_("F3.3", "Field imported from pydantic")
    return fail_("F3.3", "Field not imported from pydantic")


# =============================================================================
# FIX 4 — Redis state persistence
# =============================================================================

def _check_f4_import() -> CheckResult:
    src = _read_source("services/mission_runtime.py")
    if "from backend.runtime.runtime_state_store import runtime_state_store" in src:
        return pass_("F4.1", "runtime_state_store imported")
    return fail_("F4.1", "runtime_state_store not imported")


def _check_f4_start() -> CheckResult:
    src = _read_source("services/mission_runtime.py")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_run_pipeline":
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    fn = child.func
                    if isinstance(fn, ast.Attribute) and fn.attr == "runtime_state_store":
                        for inner in ast.walk(child):
                            if isinstance(inner, ast.Attribute) and inner.attr == "start":
                                return pass_("F4.2", "runtime_state_store.start called")
            return fail_("F4.2", "runtime_state_store.start not called in _run_pipeline")
    return fail_("F4.2", "_run_pipeline not found")


def _check_f4_update() -> CheckResult:
    src = _read_source("services/mission_runtime.py")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_run_pipeline":
            update_count = 0
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    fn = child.func
                    if isinstance(fn, ast.Attribute) and getattr(fn, "attr", None) == "update":
                        if any(
                            isinstance(arg, ast.Constant) and "completed" in str(arg.value)
                            for arg in child.args
                        ):
                            update_count += 1
            if update_count >= 2:
                return pass_("F4.3", f"runtime_state_store.update called {update_count}x")
            return fail_("F4.3", f"runtime_state_store.update called only {update_count}x (need >=2)")
    return fail_("F4.3", "_run_pipeline not found")


def _check_f4_complete() -> CheckResult:
    src = _read_source("services/mission_runtime.py")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_run_pipeline":
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    fn = child.func
                    if isinstance(fn, ast.Attribute) and getattr(fn, "attr", None) == "complete":
                        return pass_("F4.4", "runtime_state_store.complete called")
            return fail_("F4.4", "runtime_state_store.complete not called in _run_pipeline")
    return fail_("F4.4", "_run_pipeline not found")


# =============================================================================
# FIX 5 — Active execution cleanup
# =============================================================================

def _check_f5_active_cleanup() -> CheckResult:
    """
    Verify that runtime_state_store.complete() removes from cx:rt:active ZSET.
    Check the runtime_state_store.py source for zrem call on _KEY_ACTIVE.
    """
    src = _read_source("../runtime/runtime_state_store.py")
    if "zrem(_KEY_ACTIVE" in src:
        return pass_("F5", "runtime_state_store.complete calls zrem on cx:rt:active ZSET")
    return fail_("F5", "runtime_state_store.complete does not remove from active ZSET")


# =============================================================================
# MAIN — run directly
# =============================================================================

if __name__ == "__main__":
    result = run_category()
    print(f"\n{'='*60}")
    print(f"Category: {result.name}")
    print(f"{'='*60}")
    for c in result.checks:
        icon = {"pass": "✓", "fail": "✗", "warn": "△", "skip": "⊘"}.get(c.status.value, "?")
        print(f"  {icon} {c.name:45s} {c.message}")
    print(f"{'='*60}")
    print(f"Score: {result.score}%  |  {result.passed} passed  {result.failed} failed  {result.warned} warned  {result.skipped} skipped")
