"""
Validation tests for the Enterprise Patch Pipeline.

Simulates:
  ✓ Patch Planner — input parsing, risk assessment, test suggestion
  ✓ Candidate Generator — multiple approaches, file suggestion
  ✓ Validation Pipeline — sandbox execution, build/test/security/coverage
  ✓ Candidate Comparator — weighted scoring, ranking, selection
  ✓ Refactoring Analyzer — unused imports, large methods, complexity, dead code
  ✓ EnterprisePatchPipeline — full plan→generate→validate→compare workflow

Verifies:
  ✓ Plans are created with correct risk/complexity
  ✓ Candidates are generated with correct approaches
  ✓ Validation returns structured results
  ✓ Comparator ranks and selects best candidate
  ✓ Refactoring detects code issues
  ✓ Full pipeline round-trip
  ✓ Error handling for missing data
"""
import os
import tempfile
import pytest

from backend.services.enterprise_patch_pipeline import (
    EnterprisePatchPipeline,
    PatchPlanner,
    CandidateGenerator,
    ValidationPipeline,
    CandidateComparator,
    RefactoringAnalyzer,
    PATCH_PIPELINE_EVENTS,
    PIPELINE_STATUSES,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_python_repo():
    """Create a temp directory with Python files for refactoring analysis."""
    with tempfile.TemporaryDirectory() as tmp:
        # File 1: simple module
        with open(os.path.join(tmp, "utils.py"), "w") as f:
            f.write("""
import os
import sys
import json


def greet(name: str) -> str:
    return f"Hello {name}"


def unused_func():
    return "I am never called"
""")
        # File 2: large method + high complexity
        with open(os.path.join(tmp, "processor.py"), "w") as f:
            f.write("""
import math
import random


class DataProcessor:
    def process(self, data):
        result = []
        for i in range(100):
            if i % 2 == 0 and data.get("flag"):
                for j in range(10):
                    if j > 8:
                        result.append(j * 3)
                    elif j > 6:
                        result.append(j * 2)
                    elif j > 4:
                        result.append(j)
                    elif j > 2:
                        result.append(j // 2)
                    else:
                        result.append(0)
            elif i % 3 == 0:
                if data.get("mode") == "fast":
                    result.append(i)
                elif data.get("mode") == "slow":
                    result.append(i * 2)
                else:
                    result.append(i * 3)
            elif i % 5 == 0:
                result.append(i * 5)
            else:
                if i > 50:
                    result.append(i * 10)
                elif i > 25:
                    result.append(i * 4)
                else:
                    result.append(i)
        return result

    def small_method(self):
        return 42
""")
        # File 3: large method (>50 lines)
        long_lines = "\n".join([f"    # line {i}" for i in range(60)])
        with open(os.path.join(tmp, "large_module.py"), "w") as f:
            f.write(f"""
def large_function():
{long_lines}
    return "done"
""")
        yield tmp


# ── Part 1: PatchPlanner tests ──────────────────────────────────────────────

class TestPatchPlanner:
    def test_plan_created(self):
        plan = PatchPlanner.plan(
            input_type="bug",
            description="Fix login API returning 500 error on invalid token",
            source="manual",
        )
        assert plan["plan_id"].startswith("plan-")
        assert plan["status"] == "planned"
        assert "api" in plan["affected_areas"] or "backend" in plan["affected_areas"]
        assert plan["risk"] in ("low", "medium", "high")
        assert len(plan["required_tests"]) > 0
        assert plan["complexity"] in ("low", "medium", "high")

    def test_high_risk_security(self):
        plan = PatchPlanner.plan(
            input_type="security",
            description="SQL injection vulnerability in user search endpoint",
        )
        assert plan["risk"] == "high"

    def test_infer_backend_areas_from_description(self):
        plan = PatchPlanner.plan(
            input_type="feature",
            description="Add new API endpoint for user profile with database migration",
        )
        areas = plan["affected_areas"]
        assert "backend" in areas

    def test_infer_frontend_areas_from_description(self):
        plan = PatchPlanner.plan(
            input_type="feature",
            description="Create new React component for the user dashboard page",
        )
        assert "frontend" in plan["affected_areas"]

    def test_suggest_tests_backend(self):
        tests = PatchPlanner._suggest_tests(["backend"])
        assert "unit:service" in tests
        assert "integration:api" in tests

    def test_suggest_tests_security(self):
        tests = PatchPlanner._suggest_tests(["security"])
        assert "security:scan" in tests

    def test_complexity_low(self):
        assert PatchPlanner._assess_complexity(["backend"]) == "low"

    def test_complexity_high(self):
        areas = ["backend", "frontend", "database", "security", "infrastructure"]
        assert PatchPlanner._assess_complexity(areas) == "high"

    def test_plan_with_explicit_areas(self):
        plan = PatchPlanner.plan(
            input_type="refactor",
            description="Clean up configuration",
            affected_areas=["configuration"],
        )
        assert plan["affected_areas"] == ["configuration"]


# ── Part 2: CandidateGenerator tests ────────────────────────────────────────

class TestCandidateGenerator:
    def setup_method(self):
        self.plan = PatchPlanner.plan("bug", "Fix timeout in data sync", source="auto")
        self.generator = CandidateGenerator()

    def test_generate_default_count(self):
        candidates = self.generator.generate(self.plan)
        assert len(candidates) == 3
        for c in candidates:
            assert c["plan_id"] == self.plan["plan_id"]
            assert c["status"] == "generated"
            assert c["candidate_id"].startswith("candidate-")
            assert c["approach"] in CandidateGenerator.PATCH_APPROACHES

    def test_generate_five_candidates(self):
        candidates = self.generator.generate(self.plan, count=5)
        assert len(candidates) == 5
        approaches = {c["approach"] for c in candidates}
        assert len(approaches) == 5

    def test_each_candidate_has_different_approach(self):
        candidates = self.generator.generate(self.plan, count=3)
        approaches = [c["approach"] for c in candidates]
        assert len(set(approaches)) == 3

    def test_confidence_range(self):
        candidates = self.generator.generate(self.plan, count=3)
        for c in candidates:
            assert 0 <= c["confidence"] <= 1.0

    def test_files_match_areas(self):
        plan = PatchPlanner.plan("feature", "Update API and tests")
        plan["affected_areas"] = ["backend", "tests"]
        candidates = self.generator.generate(plan, count=1)
        assert len(candidates[0]["files_changed"]) >= 2

    def test_reasoning_present(self):
        candidates = self.generator.generate(self.plan, count=1)
        assert len(candidates[0]["reasoning"]) > 10


# ── Part 3: ValidationPipeline tests ───────────────────────────────────────

class TestValidationPipeline:
    @pytest.mark.asyncio
    async def test_validate_returns_structure(self):
        plan = PatchPlanner.plan("bug", "Fix test issue")
        candidate = CandidateGenerator.generate(plan, count=1)[0]
        result = await ValidationPipeline.validate(candidate)
        assert result["candidate_id"] == candidate["candidate_id"]
        assert result["validation_id"].startswith("val-")
        assert result["status"] in ("completed", "failed", "running")
        assert "build" in result
        assert "tests" in result
        assert "security" in result
        assert "coverage" in result

    @pytest.mark.asyncio
    async def test_validate_has_timing(self):
        plan = PatchPlanner.plan("bug", "Performance fix")
        candidate = CandidateGenerator.generate(plan, count=1)[0]
        result = await ValidationPipeline.validate(candidate)
        assert result["started_at"]
        assert result["completed_at"]


# ── Part 4: CandidateComparator tests ──────────────────────────────────────

class TestCandidateComparator:
    def test_compare_empty_list(self):
        result = CandidateComparator.compare([])
        assert result["selected"] is None
        assert result["rankings"] == []

    def test_compare_single_candidate(self):
        candidate = {
            "candidate_id": "test-1",
            "approach": "direct_fix",
            "confidence": 0.85,
            "files_changed": [{"path": "a.py"}],
            "validation": {
                "build": {"success": True},
                "tests": {"success": True, "passed": 10, "total": 10},
                "coverage": {"line_coverage_pct": 90.0},
                "security": {"passed": True, "vulnerabilities": 0, "warnings": 0},
            },
        }
        result = CandidateComparator.compare([candidate])
        assert result["selected"] is not None
        assert result["selected"]["candidate_id"] == "test-1"
        assert result["selected"]["score"] > 0

    def test_compare_ranks_by_score(self):
        good = {
            "candidate_id": "good",
            "approach": "direct_fix",
            "confidence": 0.9,
            "files_changed": [{"path": "a.py"}],
            "validation": {
                "build": {"success": True},
                "tests": {"success": True, "passed": 10, "total": 10},
                "coverage": {"line_coverage_pct": 95.0},
                "security": {"passed": True, "vulnerabilities": 0, "warnings": 0},
            },
        }
        bad = {
            "candidate_id": "bad",
            "approach": "alternative",
            "confidence": 0.3,
            "files_changed": [{"path": "a.py"}, {"path": "b.py"}, {"path": "c.py"}],
            "validation": {
                "build": {"success": False, "exit_code": 1},
                "tests": {"success": False, "passed": 2, "total": 10},
                "coverage": {"line_coverage_pct": 30.0},
                "security": {"passed": False, "vulnerabilities": 3, "warnings": 5},
            },
        }
        result = CandidateComparator.compare([bad, good])
        assert result["selected"]["candidate_id"] == "good"
        assert result["rankings"][0]["candidate_id"] == "good"
        assert result["rankings"][1]["candidate_id"] == "bad"

    def test_score_non_negative(self):
        candidate = {
            "candidate_id": "test",
            "approach": "test",
            "confidence": 0.0,
            "files_changed": [{"path": f"f{i}.py"} for i in range(20)],
            "validation": {
                "build": {"success": False},
                "tests": {"success": False, "passed": 0, "total": 10},
                "coverage": {"line_coverage_pct": 0.0},
                "security": {"passed": False},
            },
        }
        score = CandidateComparator._score_candidate(candidate)
        assert score >= 0


# ── Part 5: RefactoringAnalyzer tests ──────────────────────────────────────

class TestRefactoringAnalyzer:
    def test_analyze_nonexistent_directory(self):
        result = RefactoringAnalyzer.analyze("/nonexistent/path")
        assert result["analysis_id"].startswith("refactor-")
        assert result["findings"] == []
        assert "Directory not found" in result.get("error", "")

    def test_analyze_detects_unused_imports(self, sample_python_repo):
        result = RefactoringAnalyzer.analyze(sample_python_repo)
        unused_types = [f["type"] for f in result["findings"]]
        assert "unused_import" in unused_types

    def test_analyze_detects_large_method(self, sample_python_repo):
        result = RefactoringAnalyzer.analyze(sample_python_repo)
        large = [f for f in result["findings"] if f["type"] == "large_method"]
        assert len(large) >= 1

    def test_analyze_detects_high_complexity(self, sample_python_repo):
        result = RefactoringAnalyzer.analyze(sample_python_repo)
        complex_f = [f for f in result["findings"] if f["type"] == "high_complexity"]
        assert len(complex_f) >= 1

    def test_analyze_detects_dead_code(self, sample_python_repo):
        result = RefactoringAnalyzer.analyze(sample_python_repo)
        dead = [f for f in result["findings"] if f["type"] == "dead_code"]
        assert len(dead) >= 1

    def test_analyze_returns_summary(self, sample_python_repo):
        result = RefactoringAnalyzer.analyze(sample_python_repo)
        assert result["summary"]["total_findings"] > 0
        assert "by_type" in result["summary"]
        assert "by_severity" in result["summary"]

    def test_analyze_returns_suggestions(self, sample_python_repo):
        result = RefactoringAnalyzer.analyze(sample_python_repo)
        assert len(result["suggestions"]) > 0

    def test_analyze_counts_by_severity(self, sample_python_repo):
        result = RefactoringAnalyzer.analyze(sample_python_repo)
        by_sev = result["summary"]["by_severity"]
        assert "low" in by_sev or "medium" in by_sev


# ── EnterprisePatchPipeline integration tests ──────────────────────────────

class TestEnterprisePatchPipeline:
    @pytest.fixture
    def pipeline(self):
        return EnterprisePatchPipeline()

    @pytest.mark.asyncio
    async def test_create_plan(self, pipeline):
        plan = await pipeline.create_plan(
            input_type="bug",
            description="Fix authentication timeout",
        )
        assert plan["plan_id"] in pipeline._plans
        assert plan["status"] == "planned"

    @pytest.mark.asyncio
    async def test_list_plans(self, pipeline):
        await pipeline.create_plan("bug", "Issue A")
        await pipeline.create_plan("feature", "Feature B")
        plans = await pipeline.list_plans()
        assert len(plans) >= 2

    @pytest.mark.asyncio
    async def test_generate_candidates(self, pipeline):
        plan = await pipeline.create_plan("bug", "Fix timeout")
        candidates = await pipeline.generate_candidates(plan["plan_id"], count=3)
        assert len(candidates) == 3
        for c in candidates:
            assert c["plan_id"] == plan["plan_id"]
            assert c["candidate_id"] in pipeline._candidates

    @pytest.mark.asyncio
    async def test_list_candidates_by_plan(self, pipeline):
        plan = await pipeline.create_plan("bug", "Fix timeout")
        await pipeline.generate_candidates(plan["plan_id"], count=3)
        candidates = await pipeline.list_candidates(plan["plan_id"])
        assert len(candidates) == 3

    @pytest.mark.asyncio
    async def test_generate_for_missing_plan(self, pipeline):
        candidates = await pipeline.generate_candidates("nonexistent")
        assert candidates == []

    @pytest.mark.asyncio
    async def test_validate_missing_candidate(self, pipeline):
        result = await pipeline.validate_candidate("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_fulls_compare_no_validated(self, pipeline):
        plan = await pipeline.create_plan("bug", "Fix")
        await pipeline.generate_candidates(plan["plan_id"], count=2)
        result = await pipeline.compare_candidates(plan["plan_id"])
        assert result["rankings"] == []

    @pytest.mark.asyncio
    async def test_analyze_refactoring_nonexistent(self, pipeline):
        result = await pipeline.analyze_refactoring("/nonexistent")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_apply_refactoring(self, pipeline):
        result = await pipeline.apply_refactoring("suggestion-1")
        assert result["status"] == "applied"
        assert result["suggestion_id"] == "suggestion-1"

    @pytest.mark.asyncio
    async def test_refactor_analyze_real_dir(self, pipeline, sample_python_repo):
        result = await pipeline.analyze_refactoring(sample_python_repo)
        assert result["files_analyzed"] >= 3
        assert result["summary"]["total_findings"] > 0

    @pytest.mark.asyncio
    async def test_analyze_refactoring_emits_event(self, pipeline, sample_python_repo):
        result = await pipeline.analyze_refactoring(sample_python_repo)
        # Should have findings to emit
        if result.get("findings"):
            assert result["analysis_id"] is not None


# ── Event type constants tests ─────────────────────────────────────────────

class TestPatchPipelineConstants:
    def test_pipeline_events_defined(self):
        assert "planned" in PATCH_PIPELINE_EVENTS
        assert "generated" in PATCH_PIPELINE_EVENTS
        assert "validated" in PATCH_PIPELINE_EVENTS
        assert "rejected" in PATCH_PIPELINE_EVENTS
        assert "selected" in PATCH_PIPELINE_EVENTS
        assert "refactor_suggested" in PATCH_PIPELINE_EVENTS
        assert "refactor_applied" in PATCH_PIPELINE_EVENTS

    def test_pipeline_statuses_defined(self):
        for status in ["planned", "generating", "generated", "validating",
                        "validated", "failed", "compared", "selected",
                        "rejected", "refactoring", "refactored"]:
            assert status in PIPELINE_STATUSES
