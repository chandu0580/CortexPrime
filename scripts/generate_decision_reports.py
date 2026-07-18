"""
Generate decision report markdown files from EngineeringDecisionEngine analysis.

Runs all 7 scenarios through the engine and writes phase-specific reports to docs/reports/.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path so that 'backend' is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.engineering_decision_engine import EngineeringDecisionEngine

REPORTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "reports"

SCENARIOS = [
    ("CSS Frontend Change", {"head_commit": {"modified": ["frontend/styles/main.css"]}}),
    ("Payment Service Change", {"head_commit": {"modified": ["backend/services/payment/processor.py", "backend/services/payment/models.py"]}}),
    ("Terraform Infrastructure Change", {"head_commit": {"modified": ["terraform/aws/main.tf", "terraform/aws/variables.tf"]}}),
    ("Helm Chart Change", {"head_commit": {"modified": ["helm/cortexprime/templates/deployment.yaml", "helm/cortexprime/values.yaml"]}}),
    ("Database Migration Change", {"head_commit": {"modified": ["backend/migrations/2024_01_add_users_table.py", "backend/models/user.py"]}}),
    ("RBAC Change", {"head_commit": {"modified": ["backend/auth/rbac.py", "backend/auth/permissions.py"]}}),
    ("Critical Hotfix (Payment + Secrets)", {"head_commit": {"modified": ["backend/services/payment/processor.py", "backend/auth/secrets.py"]}}),
]


def _phase_data(report, phases):
    """Extract specific phases from a report to_dict."""
    d = report.to_dict()
    return {p: d[p] for p in phases}


def write_report(filepath, title, phase_keys, reports):
    """Write a markdown report file containing phase data for each scenario."""
    lines = [f"# {title}", ""]
    for idx, (scenario_name, report) in enumerate(zip([s[0] for s in SCENARIOS], reports), 1):
        data = _phase_data(report, phase_keys)
        lines.append(f"## Scenario {idx}: {scenario_name}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(data, indent=2, default=str))
        lines.append("```")
        lines.append("")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text("\n".join(lines), encoding="utf-8")


async def main():
    engine = EngineeringDecisionEngine()

    reports = []
    for scenario_name, payload in SCENARIOS:
        print("  Analyzing: " + scenario_name + "...")
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload=payload,
            repository="org/repo",
            branch="main",
            commit_sha="abc123",
        )
        reports.append(report)

    print("\nWriting report files...\n")

    # 1. ENGINEERING_DECISION_ENGINE.md — full decision report for each scenario
    lines = ["# Engineering Decision Engine — Full Decision Reports", ""]
    for idx, (scenario_name, _), report in zip(range(1, len(SCENARIOS) + 1), SCENARIOS, reports):
        lines.append(f"## Scenario {idx}: {scenario_name}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(report.to_dict(), indent=2, default=str))
        lines.append("```")
        lines.append("")
    (REPORTS_DIR / "ENGINEERING_DECISION_ENGINE.md").write_text("\n".join(lines), encoding="utf-8")
    print("[OK] ENGINEERING_DECISION_ENGINE.md")

    # 2. CHANGE_INTELLIGENCE.md — Phase 1
    write_report(REPORTS_DIR / "CHANGE_INTELLIGENCE.md", "Change Intelligence - Phase 1", ["change_report"], reports)
    print("[OK] CHANGE_INTELLIGENCE.md")

    # 3. IMPACT_ANALYSIS.md — Phase 2
    write_report(REPORTS_DIR / "IMPACT_ANALYSIS.md", "Impact Analysis - Phase 2", ["impact_graph"], reports)
    print("[OK] IMPACT_ANALYSIS.md")

    # 4. RISK_ENGINE.md — Phase 3
    write_report(REPORTS_DIR / "RISK_ENGINE.md", "Risk Engine - Phase 3", ["risk_assessment"], reports)
    print("[OK] RISK_ENGINE.md")

    # 5. DEPLOYMENT_STRATEGY.md — Phase 6 + Phase 5
    write_report(REPORTS_DIR / "DEPLOYMENT_STRATEGY.md", "Deployment Strategy - Phase 6 & Approval Requirements - Phase 5", ["deployment_strategy", "approval_requirements"], reports)
    print("[OK] DEPLOYMENT_STRATEGY.md")

    # 6. DECISION_EXPLAINABILITY.md — Phase 10
    write_report(REPORTS_DIR / "DECISION_EXPLAINABILITY.md", "Decision Explainability - Phase 10", ["explanation"], reports)
    print("[OK] DECISION_EXPLAINABILITY.md")

    # 7. EXECUTIVE_DECISION_REPORT.md — Phase 11
    write_report(REPORTS_DIR / "EXECUTIVE_DECISION_REPORT.md", "Executive Decision Report - Phase 11", ["executive_summary"], reports)
    print("[OK] EXECUTIVE_DECISION_REPORT.md")

    print("All 7 report files written to: " + str(REPORTS_DIR))


if __name__ == "__main__":
    asyncio.run(main())
