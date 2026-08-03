"""
Enterprise Engineering Memory & Experience Intelligence.

Transforms CortexPrime into an engineering platform that continuously
accumulates engineering experience and reuses it during future decisions.

Reuses every existing subsystem. Does NOT duplicate Learning Engine,
ReplayStore, RuntimeStore, or Knowledge Graph.
"""
from __future__ import annotations

import logging
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _outcome_from_exec(d: Dict[str, Any]) -> str:
    s = d.get("status", "")
    if s in ("rolled_back", "cancelled"):
        return "rolled_back"
    if s in ("failed", "error"):
        return "failed"
    if s in ("completed", "success"):
        return "success"
    return "unknown"


# =============================================================================
# Phase 1 — Engineering Experience Model
# =============================================================================


@dataclass(frozen=True)
class EngineeringExperience:
    """Canonical engineering experience — aggregates ALL existing data.

    References:
      - Execution (RuntimeStore)
      - Mission/Pipeline
      - Repository/Branch/Commit
      - Files/Services changed
      - Risk + Decision (Decision Engine)
      - Deployment Strategy + Approvals
      - Outcome
      - Runtime Metrics + Infrastructure State
      - Learning Records
      - Recommendations
      - RCA
      - Replay Timeline
      - Knowledge Graph Links
    """
    experience_id: str = ""
    execution_id: str = ""
    mission_id: str = ""
    pipeline_id: str = ""
    delivery_id: str = ""

    # Repository context
    repository: str = ""
    branch: str = ""
    commit_sha: str = ""
    changed_files: List[str] = field(default_factory=list)
    changed_services: List[str] = field(default_factory=list)
    change_categories: List[str] = field(default_factory=list)

    # Decision context
    risk_score: float = 0.0
    risk_level: str = "low"
    decision_type: str = ""
    execution_plan: str = ""
    deployment_strategy: str = "rolling"

    # Approvals
    approvals_required: bool = False
    approval_categories: List[str] = field(default_factory=list)

    # Outcome
    outcome: str = ""  # success, failed, rolled_back
    failure_reason: str = ""
    duration_seconds: float = 0.0
    completed_at: str = ""

    # Runtime & Infrastructure
    runtime_metrics: Dict[str, Any] = field(default_factory=dict)
    infrastructure_state: Dict[str, Any] = field(default_factory=dict)

    # Learning
    lessons: List[Dict[str, Any]] = field(default_factory=list)
    failure_patterns: List[Dict[str, Any]] = field(default_factory=list)
    recovery_patterns: List[Dict[str, Any]] = field(default_factory=list)

    # Recommendations
    recommendations: List[Dict[str, Any]] = field(default_factory=list)

    # RCA
    rca_analysis: Dict[str, Any] = field(default_factory=dict)

    # Replay
    replay_summary: Dict[str, Any] = field(default_factory=dict)
    replay_event_count: int = 0

    # Knowledge Graph
    knowledge_graph_links: List[str] = field(default_factory=list)

    # Metadata
    created_at: str = ""
    tags: List[str] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "execution_id": self.execution_id,
            "mission_id": self.mission_id,
            "pipeline_id": self.pipeline_id,
            "delivery_id": self.delivery_id,
            "repository": self.repository,
            "branch": self.branch,
            "commit_sha": self.commit_sha,
            "changed_files_count": len(self.changed_files),
            "changed_services": self.changed_services,
            "change_categories": self.change_categories,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "decision_type": self.decision_type,
            "execution_plan": self.execution_plan,
            "deployment_strategy": self.deployment_strategy,
            "approvals_required": self.approvals_required,
            "outcome": self.outcome,
            "failure_reason": self.failure_reason,
            "duration_seconds": self.duration_seconds,
            "completed_at": self.completed_at,
            "lessons_count": len(self.lessons),
            "failure_patterns_count": len(self.failure_patterns),
            "recommendations_count": len(self.recommendations),
            "replay_event_count": self.replay_event_count,
            "knowledge_graph_links_count": len(self.knowledge_graph_links),
            "created_at": self.created_at,
            "tags": self.tags,
            "source": self.source,
        }

    def get_signature(self) -> str:
        """Generate a signature for pattern matching."""
        parts = [self.repository or "", self.branch or ""]
        parts.extend(sorted(self.change_categories))
        parts.extend(sorted(self.changed_services))
        return ":".join(parts)


# =============================================================================
# Phase 2 — Experience Builder
# =============================================================================


class ExperienceBuilder:
    """Builds EngineeringExperience from existing subsystems."""

    async def build_from_execution(self, execution_id: str) -> Optional[EngineeringExperience]:
        """Build an experience from an execution by aggregating all subsystems."""
        execution = await self._get_execution(execution_id)
        if not execution:
            return None

        experience = EngineeringExperience(
            experience_id=_id(),
            execution_id=execution_id,
            created_at=_now(),
            source="auto",
        )

        experience = await self._collect_execution_context(experience, execution)
        experience = await self._collect_replay_context(experience)
        experience = await self._collect_learning_context(experience)
        experience = await self._collect_recommendation_context(experience)
        experience = await self._collect_rca_context(experience)
        experience = await self._collect_knowledge_graph_context(experience)
        experience = self._build_tags(experience)

        return experience

    async def _get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        try:
            from backend.services.enterprise_runtime_store import runtime_store
            exec_data = runtime_store.get_execution(execution_id)
            if exec_data:
                return exec_data.to_dict() if hasattr(exec_data, "to_dict") else dict(exec_data)
        except Exception:
            pass
        return None

    async def _collect_execution_context(
        self, exp: EngineeringExperience, execution: Dict[str, Any]
    ) -> EngineeringExperience:
        updates = {
            "mission_id": execution.get("mission_id", ""),
            "pipeline_id": execution.get("pipeline_id", ""),
            "delivery_id": execution.get("delivery_id", ""),
            "repository": execution.get("repository", ""),
            "branch": execution.get("branch", ""),
            "commit_sha": execution.get("commit_sha", ""),
            "deployment_strategy": execution.get("deployment_strategy", "rolling"),
            "outcome": self._determine_outcome(execution),
            "failure_reason": execution.get("failure_reason", "") or (
                execution.get("failure", {}).get("reason", "") if isinstance(execution.get("failure"), dict) else ""
            ),
            "duration_seconds": float(execution.get("duration_seconds", 0)),
            "completed_at": execution.get("completed_at", ""),
            "runtime_metrics": execution.get("monitoring_metrics", {}),
        }

        changed_files: List[str] = []
        changed_services: List[str] = []
        for step in execution.get("build_steps", execution.get("stages_completed", [])):
            if isinstance(step, dict):
                files = step.get("changed_files", step.get("files", []))
                if isinstance(files, list):
                    changed_files.extend(files)
                svc = step.get("services", step.get("service", ""))
                if svc:
                    changed_services.append(svc if isinstance(svc, str) else str(svc))

        updates["changed_files"] = changed_files[:50]
        updates["changed_services"] = list(set(changed_services))[:20]

        history = execution.get("approvals", [])
        if isinstance(history, list):
            updates["approvals_required"] = len(history) > 0
            updates["approval_categories"] = list(set(
                a.get("category", a.get("approver", "")) for a in history if isinstance(a, dict)
            ))

        for key, val in updates.items():
            object.__setattr__(exp, key, val)
        return exp

    def _determine_outcome(self, execution: Dict[str, Any]) -> str:
        status = execution.get("status", "")
        conclusion = execution.get("build_conclusion", "")
        deploy_status = execution.get("deployment_status", "")
        if status in ("rolled_back", "cancelled") or deploy_status == "rolled_back":
            return "rolled_back"
        if status in ("failed", "error") or conclusion in ("failure", "cancelled"):
            return "failed"
        if status in ("completed", "success") or conclusion == "success":
            return "success"
        return "unknown"

    async def _collect_replay_context(self, exp: EngineeringExperience) -> EngineeringExperience:
        if not exp.execution_id:
            return exp
        try:
            from backend.services.mission_replay_store import replay_store
            summary = await replay_store.get_summary(exp.execution_id)
            if summary:
                object.__setattr__(exp, "replay_summary", summary)
                object.__setattr__(exp, "replay_event_count", summary.get("event_count", 0))
        except Exception:
            pass
        return exp

    async def _collect_learning_context(self, exp: EngineeringExperience) -> EngineeringExperience:
        try:
            from backend.services.enterprise_learning_service import enterprise_learning

            lessons = await enterprise_learning.get_lessons(limit=5)
            failures = await enterprise_learning.get_failure_patterns(limit=5)
            recoveries = await enterprise_learning.get_recovery_patterns()

            matching_lessons = self._filter_by_repo(lessons, exp.repository)
            matching_failures = self._filter_by_repo(failures, exp.repository)

            object.__setattr__(exp, "lessons", matching_lessons[:5])
            object.__setattr__(exp, "failure_patterns", matching_failures[:5])
            object.__setattr__(exp, "recovery_patterns", recoveries[:5] if isinstance(recoveries, list) else [])
        except Exception:
            pass
        return exp

    async def _collect_recommendation_context(self, exp: EngineeringExperience) -> EngineeringExperience:
        try:
            from backend.services.enterprise_recommendation_engine import enterprise_recommendation_engine
            active = enterprise_recommendation_engine.get_active()
            matching = self._filter_by_repo(active, exp.repository)
            object.__setattr__(exp, "recommendations", matching[:5])
        except Exception:
            pass
        return exp

    async def _collect_rca_context(self, exp: EngineeringExperience) -> EngineeringExperience:
        if not exp.execution_id:
            return exp
        try:
            from backend.services.enterprise_root_cause_analysis import root_cause_analysis
            analysis = root_cause_analysis.get_analysis(exp.execution_id)
            if analysis:
                object.__setattr__(exp, "rca_analysis", analysis)
        except Exception:
            pass
        return exp

    async def _collect_knowledge_graph_context(self, exp: EngineeringExperience) -> EngineeringExperience:
        if not exp.execution_id:
            return exp
        try:
            from backend.services.enterprise_graph_service import enterprise_graph
            graph = await enterprise_graph.get_mission_graph(exp.execution_id)
            if graph:
                links = []
                for rel in graph.get("relationships", []):
                    src = rel.get("source", "")
                    tgt = rel.get("target", "")
                    if src:
                        links.append(src)
                    if tgt:
                        links.append(tgt)
                object.__setattr__(exp, "knowledge_graph_links", list(set(links))[:20])
        except Exception:
            pass
        return exp

    def _filter_by_repo(self, items: List[Dict[str, Any]], repo: str) -> List[Dict[str, Any]]:
        if not repo:
            return items[:3]
        matching = [i for i in items if repo in str(i.get("metadata", {}).get("repository", ""))
                    or repo in str(i.get("repository", ""))
                    or repo in str(i.get("source", ""))]
        return matching[:3] if matching else items[:2]

    def _build_tags(self, exp: EngineeringExperience) -> EngineeringExperience:
        tags: List[str] = []
        tags.extend(exp.change_categories)
        tags.extend(exp.changed_services)
        if exp.outcome:
            tags.append(f"outcome:{exp.outcome}")
        if exp.risk_level:
            tags.append(f"risk:{exp.risk_level}")
        if exp.deployment_strategy:
            tags.append(f"deploy:{exp.deployment_strategy}")
        if exp.failure_reason:
            tags.append("has_failure")
        object.__setattr__(exp, "tags", list(set(tags)))
        return exp


# =============================================================================
# Phase 3 — Pattern Mining
# =============================================================================


PATTERN_SIGNATURES = {
    "database_migration": {"categories": {"database"}, "services": set()},
    "payment_deployment": {"categories": set(), "services": {"payment"}},
    "terraform_failure": {"categories": {"infrastructure"}, "files": {".tf"}},
    "helm_rollout": {"categories": {"infrastructure"}, "files": {"helm"}},
    "auth_change": {"categories": {"authentication", "rbac"}},
    "secret_change": {"categories": {"secrets"}},
    "infrastructure_change": {"categories": {"infrastructure"}},
    "rollback_scenario": {"outcome": "rolled_back"},
    "high_latency": {"tags": {"latency"}},
    "dependency_failure": {"categories": {"dependency"}},
    "crashloop": {"files": {"crash", "crashloop"}},
}


class PatternMiner:
    """Identifies recurring patterns from accumulated experiences."""

    def __init__(self) -> None:
        self._pattern_counts: Dict[str, int] = defaultdict(int)
        self._pattern_examples: Dict[str, List[str]] = defaultdict(list)

    def mine(self, experiences: List[EngineeringExperience]) -> Dict[str, Any]:
        """Mine patterns from a list of experiences."""
        self._pattern_counts.clear()
        self._pattern_examples.clear()

        for exp in experiences:
            for pattern_name, signature in PATTERN_SIGNATURES.items():
                if self._matches_pattern(exp, signature):
                    self._pattern_counts[pattern_name] += 1
                    if len(self._pattern_examples[pattern_name]) < 5:
                        self._pattern_examples[pattern_name].append(exp.experience_id)

        results = {}
        for pattern_name in sorted(PATTERN_SIGNATURES.keys()):
            count = self._pattern_counts.get(pattern_name, 0)
            if count > 0:
                results[pattern_name] = {
                    "count": count,
                    "frequency": round(count / max(len(experiences), 1) * 100, 1),
                    "example_ids": self._pattern_examples.get(pattern_name, []),
                }
        return results

    def _matches_pattern(self, exp: EngineeringExperience, signature: Dict[str, Any]) -> bool:
        cats = signature.get("categories", set())
        svcs = signature.get("services", set())
        files = signature.get("files", set())
        outcome = signature.get("outcome", "")
        tags = signature.get("tags", set())

        if cats and not cats.intersection(set(exp.change_categories)):
            return False
        if svcs and not svcs.intersection(set(exp.changed_services)):
            return False
        if files and not any(any(fpat in f for fpat in files) for f in exp.changed_files):
            return False
        if outcome and exp.outcome != outcome:
            return False
        if tags and not tags.intersection(set(exp.tags)):
            return False
        return True

    def mine_from_store(self, limit: int = 100) -> Dict[str, Any]:
        """Mine patterns from stored experiences."""
        try:
            experiences = self._load_experiences()
            return self.mine(experiences[-limit:])
        except Exception:
            return {}

    def _load_experiences(self) -> List[EngineeringExperience]:
        try:
            from backend.services.enterprise_runtime_store import runtime_store
            executions = runtime_store.list_executions(limit=100)
            experiences_list: List[EngineeringExperience] = []
            for exec_data in executions:
                d = exec_data.to_dict() if hasattr(exec_data, "to_dict") else dict(exec_data)
                exp = EngineeringExperience(
                    experience_id=d.get("execution_id", _id()),
                    execution_id=d.get("execution_id", ""),
                    repository=d.get("repository", ""),
                    branch=d.get("branch", ""),
                    commit_sha=d.get("commit_sha", ""),
                    outcome=self._outcome_from_exec(d),
                    risk_level=d.get("risk_level", "unknown"),
                    deployment_strategy=d.get("deployment_strategy", "rolling"),
                    duration_seconds=float(d.get("duration_seconds", 0)),
                    completed_at=d.get("completed_at", ""),
                    failure_reason=d.get("failure_reason", ""),
                    created_at=d.get("created_at", _now()),
                    source="runtime_store",
                )
                experiences_list.append(exp)
            return experiences_list
        except Exception:
            return []

    def _outcome_from_exec(self, d: Dict[str, Any]) -> str:
        return _outcome_from_exec(d)


# =============================================================================
# Phase 4 — Similarity Engine
# =============================================================================


class SimilarityEngine:
    """Finds similar historical experiences for a given change context."""

    async def compute_similarity(
        self,
        query_categories: List[str],
        query_services: List[str],
        query_files: List[str],
        query_repository: str = "",
    ) -> Dict[str, Any]:
        """Compute similarity against all stored experiences."""
        experiences = await self._get_all_experiences()
        scored: List[tuple[float, EngineeringExperience]] = []

        for exp in experiences:
            score = self._score_experience(exp, query_categories, query_services, query_files, query_repository)
            if score > 0:
                scored.append((score, exp))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:10]

        return {
            "total_experiences_scored": len(scored),
            "total_experiences_available": len(experiences),
            "results": [
                {
                    "experience_id": exp.experience_id,
                    "execution_id": exp.execution_id,
                    "repository": exp.repository,
                    "outcome": exp.outcome,
                    "risk_level": exp.risk_level,
                    "deployment_strategy": exp.deployment_strategy,
                    "similarity_score": round(score, 3),
                    "change_categories": exp.change_categories,
                    "changed_services": exp.changed_services,
                    "failure_reason": exp.failure_reason,
                    "duration_seconds": exp.duration_seconds,
                }
                for score, exp in top
            ],
            "query": {
                "categories": query_categories,
                "services": query_services,
                "files_count": len(query_files),
                "repository": query_repository,
            },
        }

    def _score_experience(
        self,
        exp: EngineeringExperience,
        query_categories: List[str],
        query_services: List[str],
        query_files: List[str],
        query_repository: str = "",
    ) -> float:
        """Score 0.0-1.0 how similar an experience is to a query."""
        score = 0.0
        weight_total = 0

        # Category similarity (weight: 0.35)
        if query_categories and exp.change_categories:
            q_set = set(query_categories)
            e_set = set(exp.change_categories)
            intersection = q_set & e_set
            union = q_set | e_set
            if union:
                score += 0.35 * (len(intersection) / len(union))
                weight_total += 0.35

        # Service similarity (weight: 0.30)
        if query_services and exp.changed_services:
            q_set = set(query_services)
            e_set = set(exp.changed_services)
            intersection = q_set & e_set
            union = q_set | e_set
            if union:
                score += 0.30 * (len(intersection) / len(union))
                weight_total += 0.30

        # File similarity (weight: 0.15)
        if query_files and exp.changed_files:
            q_exts = set(f.split(".")[-1] if "." in f else f for f in query_files)
            e_exts = set(f.split(".")[-1] if "." in f else f for f in exp.changed_files)
            ext_match = len(q_exts & e_exts) / max(len(q_exts | e_exts), 1)
            score += 0.15 * ext_match
            weight_total += 0.15

        # Repository similarity (weight: 0.10)
        if query_repository and exp.repository:
            if query_repository == exp.repository:
                score += 0.10
            elif query_repository.split("/")[-1:] == exp.repository.split("/")[-1:]:
                score += 0.05
            weight_total += 0.10

        # Outcome weighting (weight: 0.05) — prefer experiences with outcomes
        if exp.outcome and (query_categories or query_services or query_files or query_repository):
            score += 0.05
            weight_total += 0.05

        if weight_total > 0:
            return score / weight_total
        return 0.0

    async def _get_all_experiences(self) -> List[EngineeringExperience]:
        experiences: List[EngineeringExperience] = []
        try:
            from backend.services.enterprise_runtime_store import runtime_store
            executions = runtime_store.list_executions(limit=200)
            for exec_data in executions:
                d = exec_data.to_dict() if hasattr(exec_data, "to_dict") else dict(exec_data)
                exp = EngineeringExperience(
                    experience_id=d.get("execution_id", _id()),
                    execution_id=d.get("execution_id", ""),
                    repository=d.get("repository", ""),
                    branch=d.get("branch", ""),
                    commit_sha=d.get("commit_sha", ""),
                    changed_services=[],
                    change_categories=[],
                    outcome=_outcome_from_exec(d),
                    risk_level=d.get("risk_level", "unknown"),
                    deployment_strategy=d.get("deployment_strategy", "rolling"),
                    duration_seconds=float(d.get("duration_seconds", 0)),
                    completed_at=d.get("completed_at", ""),
                    failure_reason=d.get("failure_reason", ""),
                    created_at=d.get("created_at", _now()),
                    source="runtime_store",
                )
                experiences.append(exp)
        except Exception:
            pass

        try:
            from backend.services.enterprise_learning_service import enterprise_learning
            failures = await enterprise_learning.get_failure_patterns(limit=50)
            for f in failures:
                if isinstance(f, dict):
                    exp = EngineeringExperience(
                        experience_id=_id(),
                        repository=f.get("source", ""),
                        change_categories=[f.get("pattern_type", "failure")],
                        outcome="failed",
                        failure_reason=f.get("signature", f.get("error", "")),
                        created_at=_now(),
                        source="learning",
                    )
                    experiences.append(exp)
        except Exception:
            pass

        return experiences


# =============================================================================
# Phase 5 — Experience Retrieval
# =============================================================================


class ExperienceRetrieval:
    """Retrieves relevant historical experiences before decisions."""

    def __init__(self) -> None:
        self._similarity = SimilarityEngine()

    async def retrieve(
        self,
        categories: Optional[List[str]] = None,
        services: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        repository: str = "",
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Retrieve top historical experiences for a given change context."""
        result = await self._similarity.compute_similarity(
            query_categories=categories or [],
            query_services=services or [],
            query_files=files or [],
            query_repository=repository,
        )

        top_experiences = result.get("results", [])[:limit]
        if not top_experiences:
            return {"experiences": [], "total_found": 0, "summary": "No similar experiences found"}

        outcomes = Counter(e["outcome"] for e in top_experiences)
        success_count = outcomes.get("success", 0)
        failed_count = outcomes.get("failed", 0) + outcomes.get("rolled_back", 0)
        total = len(top_experiences)

        return {
            "experiences": top_experiences,
            "total_found": result["total_experiences_scored"],
            "summary": {
                "success_rate": round(success_count / total * 100, 1) if total > 0 else 0,
                "failure_rate": round(failed_count / total * 100, 1) if total > 0 else 0,
                "top_failure_reasons": list(set(
                    e.get("failure_reason", "") for e in top_experiences if e.get("failure_reason")
                ))[:3],
                "common_strategies": [e["deployment_strategy"] for e in top_experiences[:3]],
                "average_duration_seconds": round(
                    sum(e.get("duration_seconds", 0) for e in top_experiences) / max(total, 1), 1
                ),
            },
        }


# =============================================================================
# Phase 8 — Executive Report Generator
# =============================================================================


class ExperienceReportGenerator:
    """Generates executive reports from accumulated engineering experiences."""

    def generate_pattern_report(self, patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a report from mined patterns."""
        if not patterns:
            return {"status": "no_data", "patterns": {}}

        sorted_patterns = sorted(patterns.items(), key=lambda x: x[1]["count"], reverse=True)
        most_common = sorted_patterns[:5] if sorted_patterns else []

        return {
            "status": "complete",
            "total_patterns_found": len(patterns),
            "most_common_pattern": most_common[0] if most_common else None,
            "patterns": patterns,
            "generated_at": _now(),
        }

    def generate_success_report(self, experiences: List[EngineeringExperience]) -> Dict[str, Any]:
        """Report on most successful deployment patterns."""
        by_strategy: Dict[str, List[EngineeringExperience]] = defaultdict(list)
        for exp in experiences:
            if exp.outcome == "success":
                by_strategy[exp.deployment_strategy].append(exp)

        strategy_stats = {}
        for strategy, exps in by_strategy.items():
            durations = [e.duration_seconds for e in exps if e.duration_seconds > 0]
            strategy_stats[strategy] = {
                "count": len(exps),
                "avg_duration": round(sum(durations) / max(len(durations), 1), 1) if durations else 0,
            }

        return {
            "status": "complete",
            "total_successful": sum(v["count"] for v in strategy_stats.values()),
            "by_strategy": strategy_stats,
            "generated_at": _now(),
        }

    def generate_failure_report(self, experiences: List[EngineeringExperience]) -> Dict[str, Any]:
        """Report on most common failures."""
        failures = [e for e in experiences if e.outcome in ("failed", "rolled_back")]
        reason_counts: Dict[str, int] = defaultdict(int)
        service_counts: Dict[str, int] = defaultdict(int)

        for exp in failures:
            if exp.failure_reason:
                reason_counts[exp.failure_reason[:80]] += 1
            for svc in exp.changed_services:
                service_counts[svc] += 1

        top_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_services = sorted(service_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "status": "complete",
            "total_failures": len(failures),
            "failure_rate": round(len(failures) / max(len(experiences), 1) * 100, 1),
            "top_failure_reasons": [
                {"reason": r, "count": c} for r, c in top_reasons
            ],
            "highest_risk_services": [
                {"service": s, "failures": c} for s, c in top_services
            ],
            "generated_at": _now(),
        }

    def generate_full_report(self) -> Dict[str, Any]:
        """Generate full executive report from all available data."""
        pattern_miner = PatternMiner()
        patterns = pattern_miner.mine_from_store(limit=100)

        experiences = pattern_miner._load_experiences()

        return {
            "summary": {
                "total_experiences": len(experiences),
                "patterns_detected": len(patterns),
                "generated_at": _now(),
            },
            "patterns": self.generate_pattern_report(patterns),
            "successful_deployments": self.generate_success_report(experiences),
            "failures": self.generate_failure_report(experiences),
            "recommendations": self._generate_insights(patterns, experiences),
        }

    def _generate_insights(
        self, patterns: Dict[str, Any], experiences: List[EngineeringExperience]
    ) -> List[Dict[str, Any]]:
        insights = []
        for pattern_name, data in patterns.items():
            if data["count"] >= 3:
                insights.append({
                    "pattern": pattern_name,
                    "occurrences": data["count"],
                    "frequency": data["frequency"],
                    "suggestion": self._suggestion_for_pattern(pattern_name),
                })

        failed_count = sum(1 for e in experiences if e.outcome in ("failed", "rolled_back"))
        total = len(experiences)
        if total > 0 and failed_count / total > 0.3:
            insights.append({
                "pattern": "high_failure_rate",
                "occurrences": failed_count,
                "frequency": round(failed_count / total * 100, 1),
                "suggestion": "High overall failure rate detected — consider reviewing deployment processes",
            })

        return insights

    def _suggestion_for_pattern(self, pattern: str) -> str:
        suggestions = {
            "database_migration": "Consider automated backup validation before migrations",
            "payment_deployment": "Add payment-specific integration tests and canary deployment",
            "terraform_failure": "Run terraform plan review and policy checks before apply",
            "helm_rollout": "Add Kubernetes manifest validation to CI pipeline",
            "auth_change": "Include security review for all authentication changes",
            "secret_change": "Implement automated secret scanning and rotation audit",
            "rollback_scenario": "Review rollback procedures and add automated rollback testing",
            "dependency_failure": "Add dependency vulnerability scanning to build pipeline",
        }
        return suggestions.get(pattern, "Review pattern and implement preventive measures")


# =============================================================================
# Enterprise Engineering Memory — Main Service
# =============================================================================


class EnterpriseEngineeringMemory:
    """Central engineering memory service.

    Aggregates engineering experiences from every completed workflow,
    mines patterns, provides similarity search, and integrates with
    the Engineering Decision Engine.

    Reuses: RuntimeStore, ReplayStore, Learning, Recommendation,
    Knowledge Graph, Decision Engine, RCA.
    """

    def __init__(self) -> None:
        self._experiences: Dict[str, EngineeringExperience] = {}
        self.builder = ExperienceBuilder()
        self.pattern_miner = PatternMiner()
        self.similarity = SimilarityEngine()
        self.retrieval = ExperienceRetrieval()
        self.reports = ExperienceReportGenerator()

    async def build_experience(self, execution_id: str) -> Optional[EngineeringExperience]:
        """Build and store an experience from an execution."""
        exp = await self.builder.build_from_execution(execution_id)
        if exp:
            self._experiences[exp.experience_id] = exp
            await self._persist_experience(exp)
            await self._emit_experience_event(exp)
        return exp

    async def build_experiences_batch(self, execution_ids: List[str]) -> List[EngineeringExperience]:
        """Build experiences for multiple executions."""
        results = []
        for eid in execution_ids:
            exp = await self.build_experience(eid)
            if exp:
                results.append(exp)
        return results

    def get_experience(self, experience_id: str) -> Optional[EngineeringExperience]:
        return self._experiences.get(experience_id)

    def list_experiences(self, limit: int = 50) -> List[EngineeringExperience]:
        all_exps = sorted(
            self._experiences.values(),
            key=lambda e: e.created_at,
            reverse=True,
        )
        return all_exps[:limit]

    def mine_patterns(self, limit: int = 100) -> Dict[str, Any]:
        return self.pattern_miner.mine_from_store(limit=limit)

    async def find_similar(
        self,
        categories: Optional[List[str]] = None,
        services: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        repository: str = "",
    ) -> Dict[str, Any]:
        return await self.similarity.compute_similarity(
            query_categories=categories or [],
            query_services=services or [],
            query_files=files or [],
            query_repository=repository,
        )

    async def retrieve_for_decision(
        self,
        categories: Optional[List[str]] = None,
        services: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        repository: str = "",
    ) -> Dict[str, Any]:
        return await self.retrieval.retrieve(
            categories=categories,
            services=services,
            files=files,
            repository=repository,
        )

    def generate_report(self) -> Dict[str, Any]:
        return self.reports.generate_full_report()

    async def _persist_experience(self, exp: EngineeringExperience) -> None:
        try:
            from backend.services.enterprise_runtime_store import runtime_store
            await runtime_store.create_execution({
                "execution_id": exp.experience_id,
                "mission_id": exp.mission_id,
                "objective": f"Experience: {exp.repository} {exp.outcome}",
                "repository": exp.repository,
                "branch": exp.branch,
                "commit_sha": exp.commit_sha,
                "status": "completed",
                "current_stage": "complete",
                "stages_completed": ["experience_built"],
                "deployment_strategy": exp.deployment_strategy,
                "failure_reason": exp.failure_reason,
                "duration_seconds": exp.duration_seconds,
                "completed_at": exp.completed_at,
            })
        except Exception as exc:
            log.debug("Failed to persist experience: %s", exc)

    async def _emit_experience_event(self, exp: EngineeringExperience) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="engineering.experience_built",
                agent="enterprise_engineering_memory",
                status="completed",
                message=f"Experience built: {exp.repository} {exp.outcome}",
                metadata={
                    "domain": "engineering",
                    "experience_id": exp.experience_id,
                    "execution_id": exp.execution_id,
                    "repository": exp.repository,
                    "outcome": exp.outcome,
                    "risk_level": exp.risk_level,
                    "deployment_strategy": exp.deployment_strategy,
                    "change_categories": exp.change_categories,
                    "changed_services": exp.changed_services,
                },
            )
        except Exception as exc:
            log.debug("Failed to emit experience event: %s", exc)


# =============================================================================
# Singleton
# =============================================================================

enterprise_engineering_memory = EnterpriseEngineeringMemory()
