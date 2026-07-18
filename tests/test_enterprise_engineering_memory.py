"""
Phase 9 Validation — Enterprise Engineering Memory & Experience Intelligence.

Each scenario validates the experience model, builder, pattern mining,
similarity search, retrieval, and decision integration.
"""
from __future__ import annotations

import pytest

from backend.services.enterprise_engineering_memory import (
    EngineeringExperience,
    EnterpriseEngineeringMemory,
    ExperienceBuilder,
    ExperienceReportGenerator,
    PatternMiner,
    SimilarityEngine,
)
from backend.services.engineering_decision_engine import (
    ChangeCategory,
    EngineeringDecisionEngine,
    RiskLevel,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def memory():
    return EnterpriseEngineeringMemory()


@pytest.fixture
def engine():
    return EngineeringDecisionEngine()


def _make_experience(**overrides) -> EngineeringExperience:
    defaults = {
        "experience_id": "exp-1",
        "execution_id": "exec-1",
        "repository": "org/repo",
        "branch": "main",
        "commit_sha": "abc123",
        "changed_files": ["backend/services/payment/processor.py"],
        "changed_services": ["payment"],
        "change_categories": ["backend"],
        "risk_score": 75.0,
        "risk_level": "high",
        "deployment_strategy": "canary",
        "outcome": "success",
        "duration_seconds": 120.0,
        "completed_at": "2024-01-01T00:00:00Z",
        "created_at": "2024-01-01T00:00:00Z",
        "source": "test",
    }
    defaults.update(overrides)
    return EngineeringExperience(**defaults)


PAYLOAD_CSS = {
    "modified_files": ["frontend/styles/main.css"],
    "head_commit": {"modified": ["frontend/styles/main.css"]},
}


# ── Phase 1: Engineering Experience Model ─────────────────────────────────────


class TestEngineeringExperienceModel:
    def test_experience_immutable(self):
        """EngineeringExperience must be immutable (frozen=True)."""
        exp = _make_experience()
        with pytest.raises(Exception):
            exp.repository = "other/repo"

    def test_experience_to_dict(self):
        """to_dict() returns a serializable dictionary."""
        exp = _make_experience()
        d = exp.to_dict()
        assert d["experience_id"] == "exp-1"
        assert d["execution_id"] == "exec-1"
        assert d["outcome"] == "success"
        assert d["changed_files_count"] == 1
        assert d["source"] == "test"

    def test_experience_signature(self):
        """get_signature() generates a unique pattern signature."""
        exp = _make_experience(
            change_categories=["backend", "payment"],
            changed_services=["payment", "auth"],
        )
        sig = exp.get_signature()
        assert "org/repo" in sig
        assert "main" in sig
        assert "backend" in sig

    def test_experience_defaults(self):
        """All fields have sensible defaults."""
        exp = EngineeringExperience(experience_id="test")
        assert exp.execution_id == ""
        assert exp.repository == ""
        assert exp.outcome == ""
        assert exp.risk_score == 0.0
        assert exp.duration_seconds == 0.0
        assert exp.lessons == []
        assert exp.tags == []


# ── Phase 2: Experience Builder ───────────────────────────────────────────────


class TestExperienceBuilder:
    @pytest.mark.asyncio
    async def test_builder_handles_missing_execution(self):
        """Builder returns None for non-existent execution."""
        builder = ExperienceBuilder()
        exp = await builder.build_from_execution("nonexistent-id")
        assert exp is None

    @pytest.mark.asyncio
    async def test_builder_does_not_crash(self):
        """Builder gracefully handles missing subsystems."""
        builder = ExperienceBuilder()
        exp = await builder.build_from_execution("test-exec-missing")
        # Should not crash — returns None or partial experience
        assert exp is None or isinstance(exp, EngineeringExperience)


# ── Phase 3: Pattern Mining ───────────────────────────────────────────────────


class TestPatternMiner:
    def test_mine_database_migration(self):
        """Database migration changes are identified as pattern."""
        miner = PatternMiner()
        exps = [
            _make_experience(
                experience_id="exp-db-1",
                change_categories=["database", "backend"],
                changed_files=["backend/migrations/001_add_table.py"],
            ),
            _make_experience(
                experience_id="exp-db-2",
                change_categories=["database"],
                changed_files=["db/migrate/002_update.sql"],
            ),
        ]
        patterns = miner.mine(exps)
        assert "database_migration" in patterns
        assert patterns["database_migration"]["count"] >= 1

    def test_mine_payment_deployment(self):
        """Payment service changes are identified."""
        miner = PatternMiner()
        exps = [
            _make_experience(
                experience_id="exp-pay-1",
                changed_services=["payment"],
                change_categories=["backend"],
            ),
        ]
        patterns = miner.mine(exps)
        assert "payment_deployment" in patterns
        assert patterns["payment_deployment"]["count"] == 1

    def test_mine_terraform_failure(self):
        """Terraform infra changes with .tf extension are identified."""
        miner = PatternMiner()
        exps = [
            _make_experience(
                experience_id="exp-tf-1",
                change_categories=["infrastructure"],
                changed_files=["terraform/aws/main.tf"],
            ),
        ]
        patterns = miner.mine(exps)
        assert "terraform_failure" in patterns

    def test_mine_helm_rollout(self):
        """Helm changes are identified."""
        miner = PatternMiner()
        exps = [
            _make_experience(
                experience_id="exp-helm-1",
                change_categories=["infrastructure"],
                changed_files=["helm/chart/templates/deploy.yaml"],
            ),
        ]
        patterns = miner.mine(exps)
        assert "helm_rollout" in patterns

    def test_mine_rollback_scenario(self):
        """Rolled back outcomes are identified."""
        miner = PatternMiner()
        exps = [
            _make_experience(
                experience_id="exp-rb-1",
                outcome="rolled_back",
                changed_files=["backend/api.py"],
            ),
        ]
        patterns = miner.mine(exps)
        assert "rollback_scenario" in patterns
        assert patterns["rollback_scenario"]["count"] == 1

    def test_mine_no_matches(self):
        """No patterns matched for unrelated changes."""
        miner = PatternMiner()
        exps = [
            _make_experience(
                experience_id="exp-other",
                change_categories=["documentation"],
                changed_services=[],
                changed_files=["README.md"],
            ),
        ]
        patterns = miner.mine(exps)
        # Documentation-only changes match no pattern
        all_counts = sum(p["count"] for p in patterns.values())
        assert all_counts == 0


# ── Phase 4: Similarity Engine ────────────────────────────────────────────────


class TestSimilarityEngine:
    def test_similarity_exact_match(self):
        """Exact category and service match gives high score."""
        engine = SimilarityEngine()

        # Direct score test via _score_experience
        exp = _make_experience(
            change_categories=["backend", "payment"],
            changed_services=["payment"],
        )
        score = engine._score_experience(
            exp,
            query_categories=["backend", "payment"],
            query_services=["payment"],
            query_files=["backend/services/payment/processor.py"],
            query_repository="org/repo",
        )
        assert score > 0.5

    def test_similarity_no_match(self):
        """No matching categories gives lower score than matching."""
        engine = SimilarityEngine()
        exp_no_match = _make_experience(
            experience_id="exp-no-match",
            change_categories=["documentation"],
            changed_services=[],
            changed_files=["README.md"],
        )
        exp_match = _make_experience(
            experience_id="exp-match",
            change_categories=["backend"],
            changed_services=["payment"],
            changed_files=["backend/services/payment/processor.py"],
        )
        score_no = engine._score_experience(
            exp_no_match,
            query_categories=["backend", "database"],
            query_services=["payment"],
            query_files=[],
            query_repository="",
        )
        score_yes = engine._score_experience(
            exp_match,
            query_categories=["backend", "database"],
            query_services=["payment"],
            query_files=[],
            query_repository="",
        )
        assert score_yes > score_no

    def test_similarity_partial_match(self):
        """Partial category overlap gives intermediate score."""
        engine = SimilarityEngine()
        exp = _make_experience(
            change_categories=["backend", "api"],
            changed_services=["payment"],
        )
        score = engine._score_experience(
            exp,
            query_categories=["backend", "database"],
            query_services=["payment"],
            query_files=[],
            query_repository="",
        )
        # Should have positive score from backend + payment match
        assert 0 < score < 1.0

    def test_similarity_repository_bonus(self):
        """Same repository gives a bonus."""
        engine = SimilarityEngine()
        exp = _make_experience(
            repository="org/repo",
            change_categories=["frontend"],
        )
        score_same = engine._score_experience(
            exp,
            query_categories=["frontend"],
            query_services=[],
            query_files=[],
            query_repository="org/repo",
        )
        score_diff = engine._score_experience(
            exp,
            query_categories=["frontend"],
            query_services=[],
            query_files=[],
            query_repository="other/repo",
        )
        assert score_same > score_diff

    def test_similarity_empty_query(self):
        """Empty query returns zero score (no dimensions to match)."""
        engine = SimilarityEngine()
        exp = _make_experience(outcome="success")
        score = engine._score_experience(exp, [], [], [], "")
        assert score == 0.0


# ── Phase 5: Experience Retrieval ─────────────────────────────────────────────


class TestExperienceRetrieval:
    @pytest.mark.asyncio
    async def test_retrieval_no_crash(self):
        """Retrieval does not crash with empty data."""
        from backend.services.enterprise_engineering_memory import ExperienceRetrieval
        retrieval = ExperienceRetrieval()
        result = await retrieval.retrieve(
            categories=["frontend"],
            services=[],
            files=[],
        )
        assert "experiences" in result
        assert "total_found" in result
        assert "summary" in result


# ── Phase 6: Decision Integration ─────────────────────────────────────────────


class TestDecisionIntegration:
    @pytest.mark.asyncio
    async def test_decision_engine_retrieves_experiences(self, engine):
        """Decision engine retrieves similar experiences during decision."""
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload=PAYLOAD_CSS,
            repository="org/repo",
            branch="main",
            commit_sha="abc123",
        )
        assert report is not None
        assert report.decision_record is not None
        # Decision record should contain evidence
        assert len(report.decision_record.evidence) > 0

    @pytest.mark.asyncio
    async def test_decision_with_payment_retrieves_experiences(self, engine):
        """Payment change retrieves payment-related experiences."""
        payload = {
            "modified_files": ["backend/services/payment/processor.py"],
            "head_commit": {"modified": ["backend/services/payment/processor.py"]},
        }
        report = await engine.analyze(
            source="github",
            event_type="push",
            payload=payload,
            repository="org/repo",
        )
        assert report is not None
        assert report.risk_assessment.score > 0


# ── Phase 7: Knowledge Graph Integration ──────────────────────────────────────


class TestKnowledgeGraphIntegration:
    def test_experience_has_graph_links(self):
        """Experience model supports knowledge graph links."""
        exp = _make_experience(
            knowledge_graph_links=["node:exec-1", "node:risk-1", "node:decision-1"],
        )
        assert len(exp.knowledge_graph_links) == 3
        assert "node:exec-1" in exp.knowledge_graph_links
        assert exp.to_dict()["knowledge_graph_links_count"] == 3


# ── Phase 8: Executive Reports ────────────────────────────────────────────────


class TestExecutiveReports:
    def test_pattern_report_empty(self):
        """Empty patterns report returns no_data status."""
        gen = ExperienceReportGenerator()
        report = gen.generate_pattern_report({})
        assert report["status"] == "no_data"

    def test_pattern_report_with_data(self):
        """Pattern report returns correct structure."""
        gen = ExperienceReportGenerator()
        patterns = {
            "database_migration": {"count": 5, "frequency": 25.0, "example_ids": ["e1"]},
            "payment_deployment": {"count": 3, "frequency": 15.0, "example_ids": ["e2"]},
        }
        report = gen.generate_pattern_report(patterns)
        assert report["status"] == "complete"
        assert report["total_patterns_found"] == 2
        assert report["most_common_pattern"] is not None

    def test_success_report(self):
        """Success report shows successful deployment patterns."""
        gen = ExperienceReportGenerator()
        exps = [
            _make_experience(outcome="success", deployment_strategy="rolling", duration_seconds=60),
            _make_experience(outcome="success", deployment_strategy="canary", duration_seconds=120),
            _make_experience(outcome="failed", deployment_strategy="rolling"),
        ]
        report = gen.generate_success_report(exps)
        assert report["status"] == "complete"
        assert report["total_successful"] == 2

    def test_failure_report(self):
        """Failure report shows common failure patterns."""
        gen = ExperienceReportGenerator()
        exps = [
            _make_experience(outcome="failed", failure_reason="Migration timeout",
                             changed_services=["payment"]),
            _make_experience(outcome="failed", failure_reason="Migration timeout",
                             changed_services=["payment"]),
            _make_experience(outcome="rolled_back", failure_reason="Health check failed",
                             changed_services=["auth"]),
            _make_experience(outcome="success"),
        ]
        report = gen.generate_failure_report(exps)
        assert report["status"] == "complete"
        assert report["total_failures"] >= 2
        assert len(report["top_failure_reasons"]) > 0

    def test_full_report(self):
        """Full report generates without errors."""
        gen = ExperienceReportGenerator()
        report = gen.generate_full_report()
        assert "summary" in report
        assert "patterns" in report
        assert "successful_deployments" in report
        assert "failures" in report
        assert "recommendations" in report


# ── Scenario 1: Repeated Deployment ───────────────────────────────────────────


class TestScenario1RepeatedDeployment:
    def test_pattern_detects_repeated_deployments(self):
        """Multiple similar deployments create a pattern."""
        miner = PatternMiner()
        exps = [
            _make_experience(experience_id=f"exp-d-{i}",
                             changed_services=["payment"],
                             change_categories=["backend"])
            for i in range(5)
        ]
        patterns = miner.mine(exps)
        assert patterns.get("payment_deployment", {}).get("count", 0) >= 3


# ── Scenario 2: Repeated Infrastructure Issue ─────────────────────────────────


class TestScenario2RepeatedInfraIssue:
    def test_pattern_detects_repeated_infra(self):
        """Multiple Terraform changes create a pattern."""
        miner = PatternMiner()
        exps = [
            _make_experience(experience_id=f"exp-tf-{i}",
                             change_categories=["infrastructure"],
                             changed_files=["terraform/aws/main.tf"])
            for i in range(3)
        ]
        patterns = miner.mine(exps)
        assert patterns.get("terraform_failure", {}).get("count", 0) >= 3


# ── Scenario 3: Repeated Rollback ─────────────────────────────────────────────


class TestScenario3RepeatedRollback:
    def test_pattern_detects_repeated_rollbacks(self):
        """Multiple rollbacks create a pattern."""
        miner = PatternMiner()
        exps = [
            _make_experience(experience_id=f"exp-rb-{i}",
                             outcome="rolled_back",
                             failure_reason="Health check failed")
            for i in range(4)
        ]
        patterns = miner.mine(exps)
        assert patterns.get("rollback_scenario", {}).get("count", 0) >= 3


# ── Scenario 4: Repeated Payment Deployment ───────────────────────────────────


class TestScenario4RepeatedPaymentDeployment:
    def test_similarity_finds_payment_deployments(self):
        """Similarity engine finds similar payment deployments."""
        engine = SimilarityEngine()
        exp = _make_experience(
            change_categories=["backend", "payment"],
            changed_services=["payment"],
            changed_files=["backend/services/payment/processor.py"],
        )
        score = engine._score_experience(
            exp,
            query_categories=["backend", "payment"],
            query_services=["payment"],
            query_files=["backend/services/payment/processor.py"],
            query_repository="org/repo",
        )
        assert score > 0.5


# ── Scenario 5: Repeated Terraform Change ─────────────────────────────────────


class TestScenario5RepeatedTerraformChange:
    def test_similarity_finds_terraform_changes(self):
        """Similarity engine finds Terraform changes."""
        engine = SimilarityEngine()
        exp = _make_experience(
            change_categories=["infrastructure"],
            changed_files=["terraform/aws/main.tf"],
        )
        score = engine._score_experience(
            exp,
            query_categories=["infrastructure"],
            query_services=[],
            query_files=["terraform/aws/main.tf"],
            query_repository="",
        )
        assert score > 0


# ── Scenario 6: Repeated Helm Rollout ─────────────────────────────────────────


class TestScenario6RepeatedHelmRollout:
    def test_pattern_detects_helm_rollouts(self):
        """Helm rollout changes create a pattern."""
        miner = PatternMiner()
        exps = [
            _make_experience(experience_id=f"exp-helm-{i}",
                             change_categories=["infrastructure"],
                             changed_files=["helm/chart/templates/deploy.yaml"])
            for i in range(3)
        ]
        patterns = miner.mine(exps)
        assert patterns.get("helm_rollout", {}).get("count", 0) >= 3


# ── Scenario 7: Repeated Kubernetes Incident ──────────────────────────────────


class TestScenario7RepeatedK8sIncident:
    def test_similarity_handles_k8s_context(self):
        """Similarity engine handles K8s-related changes."""
        engine = SimilarityEngine()
        exp = _make_experience(
            changed_files=["k8s/deployment.yaml"],
            change_categories=["infrastructure"],
        )
        score = engine._score_experience(
            exp,
            query_categories=["infrastructure"],
            query_services=[],
            query_files=["k8s/deployment-patch.yaml"],
            query_repository="",
        )
        # Should match on infrastructure category
        assert score > 0


# ── Scenario 8: Repeated Authentication Issue ─────────────────────────────────


class TestScenario8RepeatedAuthIssue:
    def test_pattern_detects_auth_changes(self):
        """Authentication changes create a pattern."""
        miner = PatternMiner()
        exps = [
            _make_experience(experience_id=f"exp-auth-{i}",
                             change_categories=["authentication", "rbac"])
            for i in range(3)
        ]
        patterns = miner.mine(exps)
        assert patterns.get("auth_change", {}).get("count", 0) >= 3


# ── Main Memory Service ───────────────────────────────────────────────────────


class TestEnterpriseEngineeringMemory:
    @pytest.mark.asyncio
    async def test_build_experience_nonexistent(self, memory):
        """Building experience for nonexistent execution returns None."""
        exp = await memory.build_experience("nonexistent")
        assert exp is None

    def test_list_experiences_empty(self, memory):
        """Listing experiences from empty store returns empty list."""
        exps = memory.list_experiences()
        assert exps == []

    def test_get_experience_not_found(self, memory):
        """Getting nonexistent experience returns None."""
        exp = memory.get_experience("nonexistent")
        assert exp is None

    def test_mine_patterns_no_crash(self, memory):
        """Mining patterns doesn't crash on empty data."""
        patterns = memory.mine_patterns()
        assert patterns is not None

    @pytest.mark.asyncio
    async def test_find_similar_no_crash(self, memory):
        """Finding similar doesn't crash on empty data."""
        result = await memory.find_similar(categories=["frontend"])
        assert "results" in result

    @pytest.mark.asyncio
    async def test_retrieve_for_decision_no_crash(self, memory):
        """Retrieving for decision doesn't crash."""
        result = await memory.retrieve_for_decision(categories=["frontend"])
        assert "experiences" in result

    def test_generate_report_no_crash(self, memory):
        """Generating report doesn't crash."""
        report = memory.generate_report()
        assert "summary" in report
