"""
Phase 12 Validation — Engineering Decision Engine end-to-end tests.

Each scenario exercises the full decision pipeline (Phases 1–11) via
EngineeringDecisionEngine.analyze() with a distinct payload and validates
every phase output.
"""

import pytest

from backend.services.engineering_decision_engine import (
    ApprovalCategory,
    DeploymentStrategy,
    EngineeringDecisionEngine,
    RiskLevel,
)

# ── Fixture ───────────────────────────────────────────────────────────────────


@pytest.fixture
def engine():
    inst = EngineeringDecisionEngine()
    return inst


# ── Helpers ───────────────────────────────────────────────────────────────────


def _assert_all_phases_produced(report):
    """Verify every phase produced a non-default output."""
    assert report.change_report is not None
    assert report.impact_graph is not None
    assert report.risk_assessment is not None
    assert report.execution_plan is not None
    assert report.approval_requirements is not None
    assert report.deployment_strategy is not None
    assert report.decision_record is not None
    assert report.explanation is not None
    assert report.executive_summary is not None

    # Phase 1 — change_report should have detected files
    assert len(report.change_report.changed_files) > 0
    assert report.change_report.summary != ""

    # Phase 2 — impact_graph should have modules
    assert len(report.impact_graph.affected_modules) > 0

    # Phase 3 — risk assessment should have factors
    assert report.risk_assessment.score >= 0
    assert len(report.risk_assessment.factors) > 0
    assert report.risk_assessment.reasoning != ""

    # Phase 4 — execution plan should have stages
    assert len(report.execution_plan.required_stages) > 0
    assert report.execution_plan.reasoning != ""

    # Phase 5 — approval requirements
    assert report.approval_requirements.risk_justification != ""
    assert report.approval_requirements.expected_impact != ""

    # Phase 6 — deployment strategy
    assert report.deployment_strategy.strategy is not None
    assert report.deployment_strategy.confidence > 0
    assert report.deployment_strategy.reasoning != ""

    # Phase 7-8 — decision record
    assert report.decision_record.decision_id != ""
    assert report.decision_record.reason != ""

    # Phase 10 — explanation
    assert report.explanation.why != ""
    assert len(report.explanation.factors) > 0
    assert len(report.explanation.evidence_chain) > 0

    # Phase 11 — executive summary
    assert report.executive_summary.change_summary != ""
    assert report.executive_summary.key_decision != ""
    assert report.executive_summary.deployment_strategy != ""
    assert report.executive_summary.risk_level != ""


# ── Scenario 1: CSS frontend-only change ──────────────────────────────────────


@pytest.mark.asyncio
async def test_css_frontend_change(engine):
    """CSS-only change → LOW risk, no approval, no_deployment."""
    payload = {
        "modified_files": ["frontend/styles/main.css"],
        "head_commit": {"modified": ["frontend/styles/main.css"]},
    }
    report = await engine.analyze(
        source="github",
        event_type="push",
        payload=payload,
        repository="org/repo",
        branch="main",
        commit_sha="abc123",
    )

    _assert_all_phases_produced(report)

    # Phase 1
    assert report.change_report.has_frontend_changes is True
    assert "frontend" in [c.value for c in report.change_report.categories]

    # Phase 3
    assert report.risk_assessment.level == RiskLevel.LOW
    assert 0 <= report.risk_assessment.score < 25

    # Phase 4
    assert report.execution_plan.reasoning != ""

    # Phase 5
    assert report.approval_requirements.approval_required is False
    assert report.approval_requirements.required_approvers == []

    # Phase 6
    assert report.deployment_strategy.strategy == DeploymentStrategy.NO_DEPLOYMENT

    # Phase 8
    assert report.decision_record.decision_id != ""


# ── Scenario 2: Payment service change ────────────────────────────────────────


@pytest.mark.asyncio
async def test_payment_service_change(engine):
    """Payment processor change → HIGH keyword match, critical risk, multi-approval."""
    payload = {
        "modified_files": [
            "backend/services/payment/processor.py",
            "backend/services/payment/models.py",
        ],
        "head_commit": {
            "modified": [
                "backend/services/payment/processor.py",
                "backend/services/payment/models.py",
            ]
        },
    }
    report = await engine.analyze(
        source="github",
        event_type="push",
        payload=payload,
        repository="org/repo",
        branch="main",
        commit_sha="abc123",
    )

    _assert_all_phases_produced(report)

    # Phase 1
    assert len(report.change_report.changed_files) == 2
    assert report.change_report.has_backend_changes is True
    assert "payment" in report.change_report.changed_services

    # Phase 3 — "payment" keyword contributes weight 90
    assert any("payment" in f.get("factor", "") for f in report.risk_assessment.factors)
    assert report.risk_assessment.score >= 50
    assert report.risk_assessment.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    # Phase 4
    assert "full pipeline" in report.execution_plan.reasoning.lower()

    # Phase 5
    assert report.approval_requirements.approval_required is True
    assert ApprovalCategory.ENGINEERING in report.approval_requirements.required_approvers
    assert ApprovalCategory.SECURITY in report.approval_requirements.required_approvers

    # Phase 6
    assert report.deployment_strategy.strategy is not None

    # Phase 11
    assert report.executive_summary.risk_score >= 50


# ── Scenario 3: Terraform infrastructure change ───────────────────────────────


@pytest.mark.asyncio
async def test_terraform_infra_change(engine):
    """Terraform IaC change → infrastructure flag, keyword match, multi-approval."""
    payload = {
        "modified_files": [
            "terraform/aws/main.tf",
            "terraform/aws/variables.tf",
        ],
        "head_commit": {
            "modified": [
                "terraform/aws/main.tf",
                "terraform/aws/variables.tf",
            ]
        },
    }
    report = await engine.analyze(
        source="github",
        event_type="push",
        payload=payload,
        repository="org/repo",
        branch="main",
        commit_sha="abc123",
    )

    _assert_all_phases_produced(report)

    # Phase 1
    assert report.change_report.has_infrastructure_changes is True
    assert any(
        c.value == "infrastructure" for c in report.change_report.categories
    )

    # Phase 2
    assert len(report.impact_graph.affected_terraform_modules) > 0

    # Phase 3 — "terraform" keyword
    assert any("terraform" in f.get("factor", "") for f in report.risk_assessment.factors)
    assert report.risk_assessment.score >= 50
    assert report.risk_assessment.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    # Phase 4
    assert report.execution_plan.reasoning != ""

    # Phase 5
    assert report.approval_requirements.approval_required is True
    assert ApprovalCategory.ENGINEERING in report.approval_requirements.required_approvers

    # Phase 6
    assert report.deployment_strategy.strategy is not None
    assert report.deployment_strategy.confidence > 0


# ── Scenario 4: Helm chart change ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_helm_chart_change(engine):
    """Helm chart change → infrastructure flag, medium-high risk, engineering+security."""
    payload = {
        "modified_files": [
            "helm/cortexprime/templates/deployment.yaml",
            "helm/cortexprime/values.yaml",
        ],
        "head_commit": {
            "modified": [
                "helm/cortexprime/templates/deployment.yaml",
                "helm/cortexprime/values.yaml",
            ]
        },
    }
    report = await engine.analyze(
        source="github",
        event_type="push",
        payload=payload,
        repository="org/repo",
        branch="main",
        commit_sha="abc123",
    )

    _assert_all_phases_produced(report)

    # Phase 1
    assert report.change_report.has_infrastructure_changes is True
    assert report.change_report.has_config_changes is True

    # Phase 2
    assert len(report.impact_graph.affected_helm_releases) > 0

    # Phase 3 — "helm" keyword contributes weight 60
    assert any("helm" in f.get("factor", "") for f in report.risk_assessment.factors)
    assert report.risk_assessment.score >= 25
    assert report.risk_assessment.level in (RiskLevel.MEDIUM, RiskLevel.HIGH)

    # Phase 5
    assert report.approval_requirements.approval_required is True
    assert ApprovalCategory.ENGINEERING in report.approval_requirements.required_approvers

    # Phase 6
    assert report.deployment_strategy.strategy is not None
    assert report.deployment_strategy.confidence > 0


# ── Scenario 5: Database migration change ─────────────────────────────────────


@pytest.mark.asyncio
async def test_db_migration_change(engine):
    """DB migration change → critical risk, db flag, three-pillar approval."""
    payload = {
        "modified_files": [
            "backend/migrations/2024_01_add_users_table.py",
            "backend/models/user.py",
        ],
        "head_commit": {
            "modified": [
                "backend/migrations/2024_01_add_users_table.py",
                "backend/models/user.py",
            ]
        },
    }
    report = await engine.analyze(
        source="github",
        event_type="push",
        payload=payload,
        repository="org/repo",
        branch="main",
        commit_sha="abc123",
    )

    _assert_all_phases_produced(report)

    # Phase 1
    assert report.change_report.has_db_migrations is True
    assert report.change_report.has_backend_changes is True
    assert any(
        c.value == "database" for c in report.change_report.categories
    )

    # Phase 3 — database_migration factor weight 90
    assert any(
        f.get("factor") == "database_migration" for f in report.risk_assessment.factors
    )
    assert any("migration" in f.get("factor", "") for f in report.risk_assessment.factors)
    assert report.risk_assessment.score >= 50
    assert report.risk_assessment.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    # Phase 4 — database migration reasoning
    assert "database" in report.execution_plan.reasoning.lower()
    assert report.execution_plan.requires_full_pipeline is True

    # Phase 5 — critical → engineering + security + architecture
    assert report.approval_requirements.approval_required is True
    assert ApprovalCategory.ENGINEERING in report.approval_requirements.required_approvers
    assert ApprovalCategory.SECURITY in report.approval_requirements.required_approvers
    assert ApprovalCategory.ARCHITECTURE in report.approval_requirements.required_approvers

    # Phase 6
    assert report.deployment_strategy.strategy is not None


# ── Scenario 6: RBAC change ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rbac_change(engine):
    """RBAC/permission change → auth+rbac flags, critical risk, engineering+security."""
    payload = {
        "modified_files": [
            "backend/auth/rbac.py",
            "backend/auth/permissions.py",
        ],
        "head_commit": {
            "modified": [
                "backend/auth/rbac.py",
                "backend/auth/permissions.py",
            ]
        },
    }
    report = await engine.analyze(
        source="github",
        event_type="push",
        payload=payload,
        repository="org/repo",
        branch="main",
        commit_sha="abc123",
    )

    _assert_all_phases_produced(report)

    # Phase 1
    assert report.change_report.has_auth_changes is True
    assert report.change_report.has_rbac_changes is True
    assert report.change_report.has_backend_changes is True
    assert any(
        c.value == "rbac" for c in report.change_report.categories
    )
    assert any(
        c.value == "authentication" for c in report.change_report.categories
    )

    # Phase 3 — rbac and auth factors
    factor_names = [f.get("factor") for f in report.risk_assessment.factors]
    assert "rbac" in factor_names or any("rbac" in fn for fn in factor_names)
    assert "authentication" in factor_names or any("auth" in fn for fn in factor_names)
    assert report.risk_assessment.score >= 50
    assert report.risk_assessment.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    # Phase 5 — high/critical → engineering + security (and architecture if critical)
    assert report.approval_requirements.approval_required is True
    assert ApprovalCategory.ENGINEERING in report.approval_requirements.required_approvers
    assert ApprovalCategory.SECURITY in report.approval_requirements.required_approvers

    # Phase 6
    assert report.deployment_strategy.strategy is not None


# ── Scenario 7: Critical hotfix (payment + secrets) ───────────────────────────


@pytest.mark.asyncio
async def test_critical_hotfix(engine):
    """Payment + secrets change → critical risk, security flag, three-pillar approval."""
    payload = {
        "modified_files": [
            "backend/services/payment/processor.py",
            "backend/auth/secrets.py",
        ],
        "head_commit": {
            "modified": [
                "backend/services/payment/processor.py",
                "backend/auth/secrets.py",
            ]
        },
    }
    report = await engine.analyze(
        source="github",
        event_type="push",
        payload=payload,
        repository="org/repo",
        branch="main",
        commit_sha="abc123",
    )

    _assert_all_phases_produced(report)

    # Phase 1
    assert report.change_report.has_backend_changes is True
    assert report.change_report.has_auth_changes is True
    assert report.change_report.has_secret_changes is True
    assert any(
        c.value == "secrets" for c in report.change_report.categories
    )
    assert "payment" in report.change_report.changed_services

    # Phase 3 — highest weights: secrets (85) + payment keyword (90)
    assert any("secrets" in f.get("factor", "") for f in report.risk_assessment.factors)
    assert any("payment" in f.get("factor", "") for f in report.risk_assessment.factors)
    assert report.risk_assessment.score >= 50
    assert report.risk_assessment.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    # Phase 5 — critical → engineering + security + architecture
    assert report.approval_requirements.approval_required is True
    assert ApprovalCategory.ENGINEERING in report.approval_requirements.required_approvers
    assert ApprovalCategory.SECURITY in report.approval_requirements.required_approvers
    assert ApprovalCategory.ARCHITECTURE in report.approval_requirements.required_approvers

    # Phase 6
    assert report.deployment_strategy.strategy is not None
    assert report.deployment_strategy.confidence > 0
