"""Architecture report generation.

A pass/fail bit tells a build system what to do. It tells a human nothing. When
a fitness function fails, the person fixing it needs to know which rule, which
module, which line, and what the rule was protecting -- otherwise the fastest
route to green is deleting the rule.

Three formats, three audiences:

``render_text``
    Terminal output for a failing build. Leads with what broke.
``render_markdown``
    A PR comment or a compliance artifact.
``to_dict``
    Machine-readable, for trend tracking.

The dependency graph is included because architectural drift is usually visible
in the shape of dependencies before any single rule fails.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from backend.platform.architecture.fitness_functions import SuiteResult
from backend.platform.architecture.invariant_tests import (
    InvariantCheck,
    InvariantStatus,
)
from backend.platform.architecture.rules import ModuleGraph

__all__ = [
    "render_text",
    "render_markdown",
    "to_dict",
    "dependency_summary",
]


def dependency_summary(graph: ModuleGraph, top: int = 10) -> dict[str, Any]:
    """Summarize the internal dependency graph.

    ``most_depended_upon`` is the interesting number: a module many others
    import is one that cannot be changed cheaply, whether or not that was
    intended.
    """
    edges = graph.internal_edges()
    fan_in: dict[str, int] = {name: 0 for name in edges}
    for targets in edges.values():
        for target in targets:
            if target in fan_in:
                fan_in[target] += 1

    fan_out = {name: len(targets) for name, targets in edges.items()}
    ranked_in = sorted(fan_in.items(), key=lambda item: (-item[1], item[0]))[:top]
    ranked_out = sorted(fan_out.items(), key=lambda item: (-item[1], item[0]))[:top]

    return {
        "module_count": len(edges),
        "edge_count": sum(len(targets) for targets in edges.values()),
        "most_depended_upon": [
            {"module": name, "dependents": count} for name, count in ranked_in if count
        ],
        "most_dependencies": [
            {"module": name, "imports": count} for name, count in ranked_out if count
        ],
    }


def _invariant_rows(
    result: SuiteResult, invariants: tuple[InvariantCheck, ...]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for check in invariants:
        rule_result = result.result_for(check.rule_id)
        if rule_result is None:
            continue
        if check.status is InvariantStatus.NOT_ENFORCED:
            state = "NOT ENFORCED"
        elif rule_result.passed:
            state = "PASS"
        else:
            state = "FAIL"
        rows.append(
            {
                "id": check.invariant_id,
                "statement": check.statement,
                "status": check.status.value,
                "state": state,
                "gated": check.status.is_gated,
                "tracking": check.tracking,
                "detail": (
                    rule_result.violations[0].detail if rule_result.violations else None
                ),
            }
        )
    return rows


def to_dict(
    result: SuiteResult,
    *,
    graph: Optional[ModuleGraph] = None,
    invariants: tuple[InvariantCheck, ...] = (),
) -> dict[str, Any]:
    """Machine-readable report."""
    payload: dict[str, Any] = {
        "gate_passed": result.gate_passed,
        "summary": result.summary(),
        "evaluated_at": result.evaluated_at.isoformat(),
        "modules_analyzed": result.modules_analyzed,
        "counts": {
            "passed": len(result.passed),
            "failed": len(result.failed),
            "skipped": len(result.skipped),
            "warnings": len(result.all_warnings),
        },
        "rules": [rule_result.to_dict() for rule_result in result.results],
    }
    if invariants:
        payload["invariants"] = _invariant_rows(result, invariants)
    if graph is not None:
        payload["dependencies"] = dependency_summary(graph)
    return payload


def render_text(
    result: SuiteResult,
    *,
    graph: Optional[ModuleGraph] = None,
    invariants: tuple[InvariantCheck, ...] = (),
) -> str:
    """Terminal report. Leads with failures -- that is what the reader wants."""
    lines: list[str] = []
    banner = "ARCHITECTURE GATE: PASS" if result.gate_passed else "ARCHITECTURE GATE: FAIL"
    lines.append("=" * 70)
    lines.append(banner)
    lines.append("=" * 70)
    lines.append(result.summary())
    lines.append("")

    if result.blocking_violations:
        lines.append(f"BLOCKING VIOLATIONS ({len(result.blocking_violations)})")
        lines.append("-" * 70)
        for violation in result.blocking_violations:
            lines.append(f"  {violation}")
        lines.append("")

    if result.all_warnings:
        lines.append(f"WARNINGS ({len(result.all_warnings)}) — not blocking")
        lines.append("-" * 70)
        for violation in result.all_warnings[:20]:
            lines.append(f"  {violation}")
        if len(result.all_warnings) > 20:
            lines.append(f"  ... and {len(result.all_warnings) - 20} more")
        lines.append("")

    if invariants:
        lines.append("CONSTITUTIONAL INVARIANTS")
        lines.append("-" * 70)
        for row in _invariant_rows(result, invariants):
            marker = {"PASS": "  OK  ", "FAIL": " FAIL ", "NOT ENFORCED": " ---- "}[
                row["state"]
            ]
            lines.append(f"[{marker}] {row['id']:<10} {row['statement']}")
            if row["state"] == "NOT ENFORCED" and row["tracking"]:
                lines.append(f"           tracked by: {row['tracking']}")
            elif row["state"] == "FAIL" and row["detail"]:
                lines.append(f"           {row['detail']}")
        lines.append("")

    lines.append("RULES")
    lines.append("-" * 70)
    for rule_result in result.results:
        if rule_result.skipped:
            state = " SKIP "
        elif rule_result.passed:
            state = "  OK  "
        else:
            state = " FAIL "
        lines.append(f"[{state}] {rule_result.rule_id:<28} {rule_result.description}")
        if rule_result.skipped and rule_result.skip_reason:
            lines.append(f"           {rule_result.skip_reason}")
    lines.append("")

    if graph is not None:
        summary = dependency_summary(graph)
        lines.append("DEPENDENCY GRAPH")
        lines.append("-" * 70)
        lines.append(
            f"  {summary['module_count']} modules, {summary['edge_count']} internal edges"
        )
        if summary["most_depended_upon"]:
            lines.append("  most depended upon:")
            for entry in summary["most_depended_upon"][:5]:
                lines.append(f"    {entry['dependents']:>4}  {entry['module']}")
        lines.append("")

    return "\n".join(lines)


def render_markdown(
    result: SuiteResult,
    *,
    graph: Optional[ModuleGraph] = None,
    invariants: tuple[InvariantCheck, ...] = (),
) -> str:
    """Markdown report, for a PR comment or a compliance artifact."""
    lines: list[str] = []
    badge = "✅ PASS" if result.gate_passed else "❌ FAIL"
    lines.append(f"# Architecture Report — {badge}")
    lines.append("")
    lines.append(result.summary())
    lines.append("")

    if result.blocking_violations:
        lines.append("## Blocking violations")
        lines.append("")
        lines.append("| Rule | Location | Detail |")
        lines.append("|---|---|---|")
        for violation in result.blocking_violations:
            lines.append(
                f"| `{violation.rule_id}` | `{violation.location()}` | {violation.detail} |"
            )
        lines.append("")

    if invariants:
        lines.append("## Constitutional invariants")
        lines.append("")
        lines.append("| | Invariant | Statement | Status |")
        lines.append("|---|---|---|---|")
        for row in _invariant_rows(result, invariants):
            icon = {"PASS": "✅", "FAIL": "❌", "NOT ENFORCED": "⏳"}[row["state"]]
            note = row["tracking"] if row["state"] == "NOT ENFORCED" else row["state"]
            lines.append(
                f"| {icon} | **{row['id']}** | {row['statement']} | {note or ''} |"
            )
        lines.append("")

    lines.append("## Rules")
    lines.append("")
    lines.append("| | Rule | Description |")
    lines.append("|---|---|---|")
    for rule_result in result.results:
        icon = "⏭️" if rule_result.skipped else ("✅" if rule_result.passed else "❌")
        lines.append(f"| {icon} | `{rule_result.rule_id}` | {rule_result.description} |")
    lines.append("")

    if graph is not None:
        summary = dependency_summary(graph)
        lines.append("## Dependency graph")
        lines.append("")
        lines.append(
            f"{summary['module_count']} modules, {summary['edge_count']} internal edges."
        )
        lines.append("")
        if summary["most_depended_upon"]:
            lines.append("| Module | Dependents |")
            lines.append("|---|---|")
            for entry in summary["most_depended_upon"][:10]:
                lines.append(f"| `{entry['module']}` | {entry['dependents']} |")
            lines.append("")

    return "\n".join(lines)
