"""
Engineering Decision Engine — the intelligence layer that makes CortexPrime
THINK before it ACTS.

Reuses every existing subsystem. Does NOT create new orchestrators, workflow
engines, or duplicate intelligence services.

Every engineering workflow begins with reasoning:
  1. What changed?           (Repository Change Intelligence)
  2. What is affected?       (Dependency Impact Analysis)
  3. What is the risk?       (Engineering Risk Engine)
  4. What should run?        (Execution Planner)
  5. Who must approve?       (Approval Intelligence)
  6. How to deploy?          (Deployment Strategy Intelligence)
  7. Learn from decisions.   (Learning Integration)
  8. Recommend improvements. (Recommendation Integration)
  9. Trace everything.       (Knowledge Graph)
 10. Explain why.            (Decision Explainability)
 11. Summarize.              (Executive Summary)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)


# =============================================================================
# Data Models — all plain dict-compatible dataclasses
# =============================================================================


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeCategory(str, Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    API = "api"
    DATABASE = "database"
    INFRASTRUCTURE = "infrastructure"
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    RBAC = "rbac"
    SECRETS = "secrets"
    TEST = "test"
    DOCUMENTATION = "documentation"
    CI_CD = "cicd"
    DEPENDENCY = "dependency"
    UNKNOWN = "unknown"


class DeploymentStrategy(str, Enum):
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    SHADOW = "shadow"
    HOTFIX = "hotfix"
    ROLLBACK = "rollback"
    NO_DEPLOYMENT = "no_deployment"


class ApprovalCategory(str, Enum):
    ENGINEERING = "engineering"
    SECURITY = "security"
    DEVOPS = "devops"
    PLATFORM = "platform"
    ARCHITECTURE = "architecture"


# ---------------------------------------------------------------------------
# Phase 1 — Repository Change Intelligence
# ---------------------------------------------------------------------------


@dataclass
class ChangeReport:
    changed_files: List[str] = field(default_factory=list)
    changed_folders: List[str] = field(default_factory=list)
    changed_services: List[str] = field(default_factory=list)
    changed_apis: List[str] = field(default_factory=list)
    has_db_migrations: bool = False
    has_infrastructure_changes: bool = False
    has_frontend_changes: bool = False
    has_backend_changes: bool = False
    has_test_changes: bool = False
    has_documentation_changes: bool = False
    has_config_changes: bool = False
    has_auth_changes: bool = False
    has_rbac_changes: bool = False
    has_secret_changes: bool = False
    has_dependency_changes: bool = False
    categories: List[ChangeCategory] = field(default_factory=list)
    summary: str = ""
    raw_payload: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Phase 2 — Dependency Impact Analysis
# ---------------------------------------------------------------------------


@dataclass
class ImpactGraph:
    affected_modules: List[str] = field(default_factory=list)
    affected_services: List[str] = field(default_factory=list)
    affected_apis: List[str] = field(default_factory=list)
    affected_packages: List[str] = field(default_factory=list)
    affected_deployments: List[str] = field(default_factory=list)
    affected_k8s_resources: List[str] = field(default_factory=list)
    affected_pipelines: List[str] = field(default_factory=list)
    affected_terraform_modules: List[str] = field(default_factory=list)
    affected_helm_releases: List[str] = field(default_factory=list)
    affected_dashboards: List[str] = field(default_factory=list)
    affected_monitoring_rules: List[str] = field(default_factory=list)
    affected_alert_rules: List[str] = field(default_factory=list)
    affected_documentation: List[str] = field(default_factory=list)
    total_affected_entities: int = 0


# ---------------------------------------------------------------------------
# Phase 3 — Engineering Risk Engine
# ---------------------------------------------------------------------------


@dataclass
class RiskAssessment:
    score: float = 0.0  # 0-100
    level: RiskLevel = RiskLevel.LOW
    factors: List[Dict[str, Any]] = field(default_factory=list)
    past_failure_count: int = 0
    past_failure_patterns: List[str] = field(default_factory=list)
    reasoning: str = ""


RISK_WEIGHTS = {
    ChangeCategory.DATABASE: 90,
    ChangeCategory.SECRETS: 85,
    ChangeCategory.AUTHENTICATION: 80,
    ChangeCategory.RBAC: 75,
    ChangeCategory.INFRASTRUCTURE: 70,
    ChangeCategory.API: 55,
    ChangeCategory.CONFIGURATION: 45,
    ChangeCategory.BACKEND: 35,
    ChangeCategory.DEPENDENCY: 30,
    ChangeCategory.FRONTEND: 10,
    ChangeCategory.TEST: 5,
    ChangeCategory.DOCUMENTATION: 2,
    ChangeCategory.CI_CD: 40,
    ChangeCategory.UNKNOWN: 25,
}

RISK_KEYWORDS: Dict[str, Tuple[float, str]] = {
    "password": (90, "Password or credential detected"),
    "secret": (85, "Secret or sensitive value"),
    "token": (85, "Authentication token"),
    "key": (70, "Cryptographic or API key"),
    "certificate": (75, "Certificate change"),
    "auth": (80, "Authentication logic"),
    "oauth": (85, "OAuth flow"),
    "rbac": (75, "Role-based access control"),
    "permission": (70, "Permission change"),
    "migration": (85, "Database migration"),
    "schema": (80, "Database schema change"),
    "terraform": (70, "Infrastructure as Code"),
    "helm": (60, "Helm chart change"),
    "docker": (50, "Dockerfile change"),
    "kubernetes": (65, "Kubernetes manifest"),
    "deployment": (45, "Deployment configuration"),
    "payment": (90, "Payment processing"),
    "billing": (85, "Billing system"),
    "pii": (90, "Personal identifiable information"),
    "gdpr": (85, "GDPR compliance"),
    "encrypt": (80, "Encryption logic"),
    "firewall": (75, "Firewall rule"),
    "network": (65, "Network change"),
    "config": (45, "Configuration change"),
    "hotfix": (60, "Hotfix change"),
    "rollback": (50, "Rollback change"),
}


# ---------------------------------------------------------------------------
# Phase 4 — Execution Planner
# ---------------------------------------------------------------------------


@dataclass
class ExecutionPlan:
    required_stages: List[str] = field(default_factory=list)
    skipped_stages: List[str] = field(default_factory=list)
    requires_full_pipeline: bool = True
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Phase 5 — Approval Intelligence
# ---------------------------------------------------------------------------


@dataclass
class ApprovalRequirements:
    approval_required: bool = False
    required_approvers: List[ApprovalCategory] = field(default_factory=list)
    risk_justification: str = ""
    expected_impact: str = ""


# ---------------------------------------------------------------------------
# Phase 6 — Deployment Strategy Intelligence
# ---------------------------------------------------------------------------


@dataclass
class DeploymentStrategyDecision:
    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    reasoning: str = ""
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 7+8 — Learning & Recommendation
# ---------------------------------------------------------------------------


@dataclass
class DecisionRecord:
    decision_id: str = ""
    decision_type: str = ""
    reason: str = ""
    evidence: List[str] = field(default_factory=list)
    outcome: str = ""
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Phase 10 — Decision Explainability
# ---------------------------------------------------------------------------


@dataclass
class DecisionExplanation:
    why: str = ""
    factors: List[Dict[str, Any]] = field(default_factory=list)
    evidence_chain: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    alternatives: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 11 — Executive Summary
# ---------------------------------------------------------------------------


@dataclass
class ExecutiveSummary:
    repository: str = ""
    change_summary: str = ""
    impact: str = ""
    risk_level: str = "low"
    risk_score: float = 0.0
    affected_services: List[str] = field(default_factory=list)
    required_tests: List[str] = field(default_factory=list)
    required_approvals: List[str] = field(default_factory=list)
    deployment_strategy: str = "rolling"
    rollback_strategy: str = ""
    estimated_duration: str = ""
    confidence: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    key_decision: str = ""


# ---------------------------------------------------------------------------
# Top-level Decision Report
# ---------------------------------------------------------------------------


@dataclass
class DecisionReport:
    report_id: str = ""
    trigger_source: str = ""
    trigger_event: str = ""
    timestamp: str = ""
    repository: str = ""
    branch: str = ""
    commit_sha: str = ""

    # Phase outputs
    change_report: ChangeReport = field(default_factory=ChangeReport)
    impact_graph: ImpactGraph = field(default_factory=ImpactGraph)
    risk_assessment: RiskAssessment = field(default_factory=RiskAssessment)
    execution_plan: ExecutionPlan = field(default_factory=ExecutionPlan)
    approval_requirements: ApprovalRequirements = field(default_factory=ApprovalRequirements)
    deployment_strategy: DeploymentStrategyDecision = field(default_factory=DeploymentStrategyDecision)
    decision_record: DecisionRecord = field(default_factory=DecisionRecord)
    explanation: DecisionExplanation = field(default_factory=DecisionExplanation)
    executive_summary: ExecutiveSummary = field(default_factory=ExecutiveSummary)
    predictions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "trigger_source": self.trigger_source,
            "trigger_event": self.trigger_event,
            "timestamp": self.timestamp,
            "repository": self.repository,
            "branch": self.branch,
            "commit_sha": self.commit_sha,
            "change_report": asdict(self.change_report),
            "impact_graph": asdict(self.impact_graph),
            "risk_assessment": asdict(self.risk_assessment),
            "execution_plan": asdict(self.execution_plan),
            "approval_requirements": asdict(self.approval_requirements),
            "deployment_strategy": asdict(self.deployment_strategy),
            "decision_record": asdict(self.decision_record),
            "explanation": asdict(self.explanation),
            "executive_summary": asdict(self.executive_summary),
            "predictions": self.predictions,
        }


# =============================================================================
# Engineering Decision Engine
# =============================================================================


class EngineeringDecisionEngine:
    """
    Central decision intelligence — reuses every existing subsystem.

    This is NOT an orchestrator or workflow engine. It is a reasoning layer
    that analyzes changes, assesses risk, plans execution, determines
    approvals and deployment strategy, then records decisions for learning.
    """

    def __init__(self) -> None:
        self._report_id_counter = 0

    # ── Main Entry Point ──────────────────────────────────────────────────

    async def analyze(
        self,
        source: str,
        event_type: str,
        payload: Dict[str, Any],
        repository: str = "",
        branch: str = "",
        commit_sha: str = "",
        context_snapshot: Any = None,
        repository_brain: Any = None,
    ) -> DecisionReport:
        """Analyze a trigger event and produce a full DecisionReport.

        Optionally accepts a ContextSnapshot from EnterpriseContextIntelligence
        for enriched operational, historical, and dependency awareness.

        Optionally accepts a RepositoryBrain summary from EnterpriseRepositoryBrain
        for enriched architecture, dependency, ownership, and drift awareness.

        This is the single entry point for the entire decision layer.
        It runs all phases in order and returns a comprehensive report.
        """
        self._report_id_counter += 1
        report = DecisionReport(
            report_id=f"dr-{uuid.uuid4().hex[:12]}",
            trigger_source=source,
            trigger_event=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            repository=repository,
            branch=branch,
            commit_sha=commit_sha,
        )

        # Phase 9 — Load Repository Brain (provides architecture + dependency + drift awareness)
        if repository_brain is None and repository:
            try:
                from backend.services.enterprise_repository_brain import repository_brain as rb
                brain_data = await rb.get_brain_summary(repository)
                if brain_data:
                    repository_brain = brain_data
            except Exception:
                pass

        # Build context if not provided
        if context_snapshot is None:
            try:
                from backend.services.enterprise_context_intelligence import enterprise_context_intelligence
                context_snapshot = await enterprise_context_intelligence.build_snapshot(
                    repository=repository,
                    branch=branch,
                    commit=commit_sha,
                    execution_id=report.report_id,
                )
            except Exception:
                pass

        # Phase 1 — What changed? (leveraging brain architecture awareness)
        report.change_report = self._analyze_change(payload, context_snapshot, repository_brain)
        report.change_report.raw_payload = payload

        # Phase 2 — What is affected? (leveraging brain dependency + ownership)
        report.impact_graph = await self._analyze_impact(report.change_report, context_snapshot, repository_brain)

        # Phase 3 — What is the risk? (leveraging brain drift + history)
        report.risk_assessment = await self._calculate_risk(report.change_report, report.impact_graph, context_snapshot, repository_brain)

        # Phase 4 — What should run?
        report.execution_plan = self._plan_execution(report.change_report, report.risk_assessment, context_snapshot)

        # Phase 5 — Who must approve?
        report.approval_requirements = self._determine_approvals(report.risk_assessment, report.change_report, context_snapshot)

        # Phase 6 — How to deploy?
        report.deployment_strategy = await self._choose_deployment_strategy(
            report.risk_assessment, report.impact_graph, context_snapshot,
        )

        # Phase 6b — Retrieve similar engineering experiences
        similar_experiences = {}
        try:
            from backend.services.enterprise_engineering_memory import enterprise_engineering_memory
            similar_experiences = await enterprise_engineering_memory.retrieve_for_decision(
                categories=[c.value for c in report.change_report.categories],
                services=report.change_report.changed_services,
                files=report.change_report.changed_files[:20],
                repository=report.repository,
            )
        except Exception:
            pass

        # Phase 6c — Predictive Simulation (predict outcomes BEFORE learning)
        try:
            from backend.services.enterprise_predictive_simulation import enterprise_predictive_simulation
            predictions = await enterprise_predictive_simulation.consume_predictions(
                repository=report.repository,
                branch=report.branch,
                commit_sha=report.commit_sha,
                execution_id=report.report_id,
                changed_files=report.change_report.changed_files,
                changed_services=report.change_report.changed_services,
                change_categories=[c.value for c in report.change_report.categories],
            )
            report.predictions = predictions
        except Exception:
            pass

        # Phase 7 — Learn from decisions
        await self._record_decision(report)

        # Phase 8 — Generate recommendations
        report.decision_record = self._build_decision_record(report, similar_experiences)

        # Phase 9 — Knowledge Graph (relationships returned in report)
        await self._update_knowledge_graph(report)

        # Phase 10 — Explain why
        report.explanation = self._explain_decision(report, context_snapshot)

        # Phase 11 — Executive summary
        report.executive_summary = self._generate_executive_summary(report, context_snapshot)

        # Persist to RuntimeStore
        await self._persist_report(report)

        return report

    # ── Phase 1: Repository Change Intelligence ───────────────────────────

    def _analyze_change(self, payload: Dict[str, Any], context_snapshot: Any = None,
                        repository_brain: Any = None) -> ChangeReport:
        """Determine what changed from the webhook payload.

        When repository_brain is provided, enriches change detection with
        known services, APIs, and architecture from the brain.
        """
        changed_files: List[str] = []
        if "commits" in payload:
            for commit in payload.get("commits", []):
                changed_files.extend(commit.get("added", []))
                changed_files.extend(commit.get("modified", []))
                changed_files.extend(commit.get("removed", []))
        if "head_commit" in payload:
            hc = payload["head_commit"]
            changed_files.extend(hc.get("added", []))
            changed_files.extend(hc.get("modified", []))
            changed_files.extend(hc.get("removed", []))

        changed_files = list(set(changed_files))
        changed_folders = list(set(
            f.rsplit("/", 1)[0] if "/" in f else "." for f in changed_files
        ))

        report = ChangeReport(
            changed_files=changed_files,
            changed_folders=changed_folders,
            summary=f"{len(changed_files)} file(s) changed across {len(changed_folders)} folder(s)",
        )

        for f in changed_files:
            fp = f.lower()
            if any(p in fp for p in ("/migrations/", "/migrate/", "migration")):
                report.has_db_migrations = True
                report.categories.append(ChangeCategory.DATABASE)
            if any(p in fp for p in ("terraform", ".tf", "helm", "dockerfile", "docker-compose", "kubernetes", "k8s")):
                report.has_infrastructure_changes = True
                report.categories.append(ChangeCategory.INFRASTRUCTURE)
            if any(p in fp for p in ("/frontend/", "/ui/", "/web/", ".tsx", ".jsx", ".vue", ".css", ".scss")):
                report.has_frontend_changes = True
                if ChangeCategory.FRONTEND not in report.categories:
                    report.categories.append(ChangeCategory.FRONTEND)
            if any(p in fp for p in ("/backend/", "/api/", "/server/", ".py", ".go", ".rs", ".java", ".cs")):
                report.has_backend_changes = True
                if ChangeCategory.BACKEND not in report.categories:
                    report.categories.append(ChangeCategory.BACKEND)
            if any(p in fp for p in ("/test", "/spec", "_test.", "_spec.", ".test.", ".spec.")):
                report.has_test_changes = True
                if ChangeCategory.TEST not in report.categories:
                    report.categories.append(ChangeCategory.TEST)
            if any(p in fp for p in ("/docs/", ".md", ".rst", "/wiki/")):
                report.has_documentation_changes = True
                if ChangeCategory.DOCUMENTATION not in report.categories:
                    report.categories.append(ChangeCategory.DOCUMENTATION)
            if any(p in fp for p in (".env", ".config", "config.", "settings", ".yaml", ".yml", ".toml", ".ini")):
                report.has_config_changes = True
                if ChangeCategory.CONFIGURATION not in report.categories:
                    report.categories.append(ChangeCategory.CONFIGURATION)
            if any(p in fp for p in ("auth", "oauth", "login", "password", "token")):
                report.has_auth_changes = True
                if ChangeCategory.AUTHENTICATION not in report.categories:
                    report.categories.append(ChangeCategory.AUTHENTICATION)
            if any(p in fp for p in ("rbac", "permission", "role", "policy")):
                report.has_rbac_changes = True
                if ChangeCategory.RBAC not in report.categories:
                    report.categories.append(ChangeCategory.RBAC)
            if any(p in fp for p in ("secret", "vault", "credential")):
                report.has_secret_changes = True
                if ChangeCategory.SECRETS not in report.categories:
                    report.categories.append(ChangeCategory.SECRETS)
            if any(p in fp for p in ("requirements", "package", "yarn.lock", "package-lock", "go.mod", "cargo")):
                report.has_dependency_changes = True
                if ChangeCategory.DEPENDENCY not in report.categories:
                    report.categories.append(ChangeCategory.DEPENDENCY)

        # Identify changed services — enriched by brain architecture
        services: Set[str] = set()
        for f in changed_files:
            parts = f.split("/")
            for i, p in enumerate(parts):
                if p in ("services", "service", "apps", "app"):
                    if i + 1 < len(parts):
                        services.add(parts[i + 1])

        # Brain-aware enrichment: match changed files against known services
        if repository_brain and isinstance(repository_brain, dict):
            arch = repository_brain.get("architecture", {})
            brain_services = [s.get("name", "") for s in (
                repository_brain.get("identity", {}).get("services", [])
            )] if isinstance(repository_brain.get("identity"), dict) else []
            # Also match against known service names from brain summary
            for f in changed_files:
                f_lower = f.lower()
                for bs in brain_services:
                    if bs.lower() in f_lower:
                        services.add(bs)

        report.changed_services = sorted(services)

        return report

    # ── Phase 2: Dependency Impact Analysis ───────────────────────────────

    async def _analyze_impact(self, change: ChangeReport, context_snapshot: Any = None,
                               repository_brain: Any = None) -> ImpactGraph:
        """Determine affected systems using code intelligence."""
        graph = ImpactGraph()
        all_affected: Set[str] = set()

        try:
            from backend.services.enterprise_code_intelligence import code_intelligence

            for changed_file in change.changed_files[:20]:  # limit for performance
                result = await code_intelligence.analyze_impact(changed_file)
                if result:
                    graph.affected_services.extend(result.get("affected_services", []))
                    graph.affected_apis.extend(result.get("affected_apis", []))
                    all_affected.update(result.get("all_affected_files", []))
        except Exception as exc:
            log.debug("Code intelligence impact analysis failed: %s", exc)
            self._classify_impact_basic(change, graph)

        graph.affected_services = list(set(graph.affected_services))
        graph.affected_apis = list(set(graph.affected_apis))
        graph.affected_modules = [f.split("/")[0] for f in change.changed_files if "/" in f]

        # Categorize impacted infrastructure
        if change.has_infrastructure_changes:
            for f in change.changed_files:
                fp = f.lower()
                if fp.endswith(".tf"):
                    graph.affected_terraform_modules.append(f)
                if "helm" in fp:
                    graph.affected_helm_releases.append(f)
                if "k8s" in fp or "kubernetes" in fp:
                    graph.affected_k8s_resources.append(f)

        graph.total_affected_entities = len(all_affected) + len(graph.affected_services) + len(graph.affected_apis)

        # Infer from folder structure
        if change.has_db_migrations:
            graph.affected_deployments.append("database-migration")
        if change.has_auth_changes or change.has_rbac_changes:
            graph.affected_deployments.append("security-layer")

        return graph

    def _classify_impact_basic(self, change: ChangeReport, graph: ImpactGraph) -> None:
        """Fallback impact classification when code intelligence is unavailable."""
        for f in change.changed_files:
            fp = f.lower()
            if "api" in fp or "/routes/" in fp:
                graph.affected_apis.append(f)
            if "/services/" in fp or "/controllers/" in fp:
                parts = fp.split("/")
                for i, p in enumerate(parts):
                    if p in ("services", "controllers") and i + 1 < len(parts):
                        graph.affected_services.append(parts[i + 1])
            if "test" in fp or "spec" in fp:
                graph.affected_deployments.append("none")

    # ── Phase 3: Engineering Risk Engine ──────────────────────────────────

    async def _calculate_risk(self, change: ChangeReport, impact: ImpactGraph, context_snapshot: Any = None,
                               repository_brain: Any = None) -> RiskAssessment:
        """Calculate risk score 0-100 with level and reasoning."""
        factors: List[Dict[str, Any]] = []
        score = 0.0

        # Category-based risk
        for cat in change.categories:
            weight = RISK_WEIGHTS.get(cat, 25)
            if cat == ChangeCategory.DATABASE:
                factors.append({"factor": "database_migration", "weight": weight, "reason": "Database migration changes"})
            elif cat == ChangeCategory.SECRETS:
                factors.append({"factor": "secrets", "weight": weight, "reason": "Secret/credential changes"})
            elif cat == ChangeCategory.AUTHENTICATION:
                factors.append({"factor": "authentication", "weight": weight, "reason": "Authentication logic changes"})
            elif cat == ChangeCategory.RBAC:
                factors.append({"factor": "rbac", "weight": weight, "reason": "RBAC/authorization changes"})
            elif cat == ChangeCategory.INFRASTRUCTURE:
                factors.append({"factor": "infrastructure", "weight": weight, "reason": "Infrastructure as Code changes"})
            elif cat == ChangeCategory.CONFIGURATION:
                factors.append({"factor": "configuration", "weight": weight, "reason": "Configuration changes"})
            elif cat == ChangeCategory.DEPENDENCY:
                factors.append({"factor": "dependency", "weight": weight, "reason": "Dependency changes"})
            elif cat == ChangeCategory.API:
                factors.append({"factor": "api", "weight": weight, "reason": "API changes"})
            elif cat == ChangeCategory.BACKEND:
                if not any(f.get("factor") in ("api", "database", "auth") for f in factors):
                    factors.append({"factor": "backend", "weight": weight, "reason": "Backend code changes"})
            elif cat == ChangeCategory.FRONTEND:
                factors.append({"factor": "frontend", "weight": weight, "reason": "Frontend changes"})

        # File keyword-based risk
        for f in change.changed_files:
            fp = f.lower()
            for keyword, (kw_score, reason) in RISK_KEYWORDS.items():
                if keyword in fp:
                    factors.append({"factor": f"keyword:{keyword}", "weight": kw_score, "reason": reason})
                    break

        if factors:
            score = sum(f["weight"] for f in factors) / len(factors)
        score = min(score, 100.0)

        # Past failures (from learning engine)
        past_failure_count = 0
        past_failure_patterns: List[str] = []
        try:
            from backend.services.enterprise_learning_service import enterprise_learning
            patterns = await enterprise_learning.get_failure_patterns(limit=10)
            for p in patterns:
                sig = p.get("signature", "").lower()
                for f in change.changed_files:
                    if f.lower() in sig:
                        past_failure_count += 1
                        past_failure_patterns.append(p.get("signature", ""))
                        score = min(score + 10, 100)
                        break
        except Exception:
            pass

        # Operational context risk adjustments
        if context_snapshot:
            op = context_snapshot.operational
            biz = context_snapshot.business

            # Active alerts increase risk
            active_alert_count = len(op.active_alerts)
            if active_alert_count > 0:
                alert_boost = min(active_alert_count * 5, 25)
                score = min(score + alert_boost, 100)
                factors.append({"factor": f"active_alerts:{active_alert_count}", "weight": alert_boost,
                                "reason": f"{active_alert_count} active alert(s) in cluster"})

            # Ongoing rollbacks increase risk
            rollback_count = len(op.rollbacks)
            if rollback_count > 0:
                score = min(score + 15, 100)
                factors.append({"factor": f"rollbacks:{rollback_count}", "weight": 15,
                                "reason": f"{rollback_count} rollback(s) in progress"})

            # Deployment freeze blocks deployments
            if biz.deployment_freeze:
                score = min(score + 20, 100)
                factors.append({"factor": "deployment_freeze", "weight": 20,
                                "reason": "Deployment freeze is active"})

            # Maintenance window reduces risk for infra changes
            if biz.maintenance_window and change.has_infrastructure_changes:
                score = max(score - 10, 0)
                factors.append({"factor": "maintenance_window", "weight": -10,
                                "reason": "Change during maintenance window"})

        # Brain drift awareness — unresolved drift increases risk
        if repository_brain and isinstance(repository_brain, dict):
            drift_count = repository_brain.get("drift_count", 0)
            drift_list = repository_brain.get("drift", [])
            if drift_count > 0:
                drift_boost = min(drift_count * 8, 30)
                score = min(score + drift_boost, 100)
                factors.append({"factor": f"brain_drift:{drift_count}", "weight": drift_boost,
                                "reason": f"{drift_count} unresolved architecture drift(s)"})
            for d in drift_list:
                if isinstance(d, dict) and d.get("severity") == "critical":
                    score = min(score + 15, 100)
                    factors.append({"factor": f"critical_drift:{d.get('drift_type', 'unknown')}",
                                    "weight": 15, "reason": d.get("description", "Critical drift")})
            # Recent failures in brain history increase risk
            brain_history = repository_brain.get("history", {})
            recent_failures = brain_history.get("recent_failures", [])
            if len(recent_failures) > 0:
                score = min(score + min(len(recent_failures) * 5, 20), 100)
                factors.append({"factor": f"brain_recent_failures:{len(recent_failures)}", "weight": 15,
                                "reason": f"{len(recent_failures)} recent failure(s) in brain history"})

        if score >= 70:
            level = RiskLevel.CRITICAL
            reasoning = "Critical risk — requires mandatory approvals and enhanced validation"
        elif score >= 50:
            level = RiskLevel.HIGH
            reasoning = "High risk — requires security and architecture review"
        elif score >= 25:
            level = RiskLevel.MEDIUM
            reasoning = "Medium risk — standard validation with targeted reviews"
        else:
            level = RiskLevel.LOW
            reasoning = "Low risk — standard automated pipeline"

        return RiskAssessment(
            score=round(score, 1),
            level=level,
            factors=factors,
            past_failure_count=past_failure_count,
            past_failure_patterns=past_failure_patterns,
            reasoning=reasoning,
        )

    # ── Phase 4: Execution Planner ────────────────────────────────────────

    def _plan_execution(self, change: ChangeReport, risk: RiskAssessment, context_snapshot: Any = None) -> ExecutionPlan:
        """Determine which stages must run and which can be skipped."""
        all_stages = [
            "trigger_pipeline", "repository", "workspace", "sandbox_execution",
            "code_intel_scan", "build", "qa", "security", "patch_generation",
            "engineering_review", "approval", "pr", "deployment", "gitops_sync",
            "k8s_verification", "observability", "root_cause_analysis",
            "learning", "recommendation", "replay_capture", "knowledge_graph",
            "complete",
        ]

        required = list(all_stages)
        skipped: List[str] = []

        # Documentation-only changes
        if change.categories == [ChangeCategory.DOCUMENTATION]:
            skipped = [s for s in required if s not in (
                "trigger_pipeline", "repository", "learning", "knowledge_graph", "complete", "replay_capture",
            )]
            required = [s for s in required if s not in skipped]
            full_reason = "Documentation only — skip build, test, deploy"

        # Frontend-only changes
        elif change.categories == [ChangeCategory.FRONTEND]:
            skipped = ["patch_generation", "engineering_review", "approval", "deployment",
                       "gitops_sync", "k8s_verification", "root_cause_analysis"]
            required = [s for s in required if s not in skipped]
            full_reason = "Frontend only — skip backend build, deploy"

        # Configuration changes
        elif change.categories in ([ChangeCategory.CONFIGURATION], [ChangeCategory.CONFIGURATION, ChangeCategory.TEST]):
            skipped = ["workspace", "sandbox_execution", "code_intel_scan",
                       "engineering_review", "root_cause_analysis"]
            required = [s for s in required if s not in skipped]
            full_reason = "Configuration change — skip sandbox and engineering review"

        # Infrastructure-only
        elif change.categories == [ChangeCategory.INFRASTRUCTURE]:
            skipped = ["sandbox_execution", "code_intel_scan", "build", "qa",
                       "security", "patch_generation", "engineering_review",
                       "observability", "root_cause_analysis"]
            required = [s for s in required if s not in skipped]
            full_reason = "Infrastructure only — skip code build, QA, security scan"

        # Database migration
        elif change.has_db_migrations:
            full_reason = "Database migration — add backup validation"

        # High/Critical risk — full pipeline
        elif risk.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            full_reason = f"{risk.level.value.title()} risk — full pipeline with all safeguards"

        else:
            full_reason = "Standard pipeline"

        return ExecutionPlan(
            required_stages=required,
            skipped_stages=skipped,
            requires_full_pipeline=len(skipped) == 0,
            reasoning=full_reason,
        )

    # ── Phase 5: Approval Intelligence ────────────────────────────────────

    def _determine_approvals(self, risk: RiskAssessment, change: ChangeReport, context_snapshot: Any = None) -> ApprovalRequirements:
        """Determine if approval is required and who must approve."""
        required: List[ApprovalCategory] = []

        if risk.level == RiskLevel.CRITICAL:
            required = [
                ApprovalCategory.ENGINEERING,
                ApprovalCategory.SECURITY,
                ApprovalCategory.ARCHITECTURE,
            ]
            justification = "Critical risk — requires engineering, security, and architecture sign-off"
            impact = "Changes may affect system stability, security, or data integrity"
        elif risk.level == RiskLevel.HIGH:
            required = [
                ApprovalCategory.ENGINEERING,
                ApprovalCategory.SECURITY,
            ]
            justification = "High risk — requires engineering and security review"
            impact = "Changes may affect security posture or service reliability"
        elif risk.level == RiskLevel.MEDIUM:
            if change.has_db_migrations:
                required.append(ApprovalCategory.ENGINEERING)
                justification = "Database migration requires engineering approval"
                impact = "Schema changes may affect data integrity"
            elif change.has_infrastructure_changes:
                required.append(ApprovalCategory.DEVOPS)
                justification = "Infrastructure changes require DevOps review"
                impact = "Infrastructure changes may affect deployment pipelines"
            else:
                justification = "Medium risk — standard review"
                impact = "Limited impact expected"
        else:
            justification = "Low risk — no approval required"
            impact = "Minimal impact expected"

        # Context-aware approval escalation
        if context_snapshot:
            biz = context_snapshot.business
            if biz.deployment_freeze and risk.level not in (RiskLevel.LOW,):
                if ApprovalCategory.PLATFORM not in required:
                    required.append(ApprovalCategory.PLATFORM)
                justification += " (deployment freeze active — requires platform approval)"
            if biz.hotfix_mode:
                if ApprovalCategory.ENGINEERING not in required:
                    required.append(ApprovalCategory.ENGINEERING)
                justification += " (hotfix mode — engineering override)"

        return ApprovalRequirements(
            approval_required=len(required) > 0,
            required_approvers=required,
            risk_justification=justification,
            expected_impact=impact,
        )

    # ── Phase 6: Deployment Strategy Intelligence ─────────────────────────

    async def _choose_deployment_strategy(
        self,
        risk: RiskAssessment,
        impact: ImpactGraph,
        context_snapshot: Any = None,
    ) -> DeploymentStrategyDecision:
        """Choose the optimal deployment strategy based on risk and impact."""
        strategies: List[Tuple[DeploymentStrategy, float, List[str]]] = []

        if risk.level == RiskLevel.CRITICAL:
            strategies.append((DeploymentStrategy.BLUE_GREEN, 50, ["Critical risk — full isolation required"]))
            strategies.append((DeploymentStrategy.CANARY, 30, ["Progressive exposure with monitoring"]))
        elif risk.level == RiskLevel.HIGH:
            strategies.append((DeploymentStrategy.CANARY, 60, ["High risk — canary deployment with monitoring"]))
            strategies.append((DeploymentStrategy.BLUE_GREEN, 20, ["Full isolation available"]))
        elif risk.level == RiskLevel.MEDIUM:
            strategies.append((DeploymentStrategy.ROLLING, 70, ["Medium risk — rolling update is adequate"]))
            strategies.append((DeploymentStrategy.CANARY, 20, ["Optional canary for additional safety"]))
        else:
            strategies.append((DeploymentStrategy.ROLLING, 90, ["Low risk — standard rolling update"]))
            strategies.append((DeploymentStrategy.NO_DEPLOYMENT, 5, ["No deployment needed"]))

        # Override for documentation
        if not impact.affected_services and not impact.affected_apis:
            strategies.append((DeploymentStrategy.NO_DEPLOYMENT, 95, ["No services affected — skip deployment"]))
            strategies = [strategies[-1]]

        # Override for hotfix urgency
        if risk.level == RiskLevel.CRITICAL:
            strategies.append((DeploymentStrategy.HOTFIX, 10, ["Emergency hotfix bypass"]))
            strategies.sort(key=lambda x: x[1], reverse=True)

        # Context-aware strategy adjustments
        if context_snapshot:
            biz = context_snapshot.business
            op = context_snapshot.operational

            # Hotfix mode — push hotfix to top
            if biz.hotfix_mode:
                strategies.insert(0, (DeploymentStrategy.HOTFIX, 95, ["Hotfix mode active — fast deployment"]))
                strategies = [strategies[0]]

            # Deployment freeze — no deployment
            if biz.deployment_freeze:
                strategies.insert(0, (DeploymentStrategy.NO_DEPLOYMENT, 98, ["Deployment freeze active — skip deployment"]))
                strategies = [strategies[0]]

            # Active cluster degradation — prefer blue/green for safety
            if op.runtime_health == "degraded":
                strategies.insert(0, (DeploymentStrategy.BLUE_GREEN, 80, ["Cluster degraded — full isolation required"]))
                strategies = strategies[:2]

            # Ongoing rollbacks — avoid deployment
            if len(op.rollbacks) > 0:
                strategies.insert(0, (DeploymentStrategy.NO_DEPLOYMENT, 90, ["Ongoing rollback — skip deployment"]))
                strategies = [strategies[0]]

        best = strategies[0]
        return DeploymentStrategyDecision(
            strategy=best[0],
            reasoning=best[2][0] if best[2] else "Standard strategy",
            confidence=best[1],
            evidence=[f"{s.value} ({c}% confidence)" for s, c, _ in strategies],
        )

    # ── Phase 7: Learning Integration ─────────────────────────────────────

    async def _record_decision(self, report: DecisionReport) -> None:
        """Record decision to Learning Engine for future improvement."""
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit_decision_made(
                report_id=report.report_id,
                risk_score=report.risk_assessment.score,
                risk_level=report.risk_assessment.level.value,
                execution_plan=report.execution_plan.reasoning,
                deployment_strategy=report.deployment_strategy.strategy.value,
                approval_required=report.approval_requirements.approval_required,
                categories=[c.value for c in report.change_report.categories],
                repository=report.repository,
                branch=report.branch,
            )
        except Exception as exc:
            log.debug("Failed to record decision to learning: %s", exc)

        try:
            from backend.events.event_models import CognitionEvent
            from backend.services.mission_replay_store import replay_store
            await replay_store.record(CognitionEvent(
                agent="engineering_decision_engine",
                event_type="decision.recorded",
                status="completed",
                message=f"Decision report {report.report_id} recorded",
                execution_id=report.report_id,
                payload=report.to_dict(),
            ))
        except Exception as exc:
            log.debug("Failed to record decision to replay store: %s", exc)

    # ── Phase 8: Recommendation Integration ───────────────────────────────

    def _build_decision_record(self, report: DecisionReport, similar_experiences: Optional[Dict[str, Any]] = None) -> DecisionRecord:
        """Build a structured decision record with optional experience evidence."""
        evidence = [
            f"Risk score: {report.risk_assessment.score}",
            f"Risk level: {report.risk_assessment.level.value}",
            f"Changed files: {len(report.change_report.changed_files)}",
            f"Affected services: {len(report.impact_graph.affected_services)}",
            f"Execution plan: {report.execution_plan.reasoning}",
            f"Deployment strategy: {report.deployment_strategy.strategy.value}",
        ]

        if similar_experiences:
            exps = similar_experiences.get("experiences", [])
            summary = similar_experiences.get("summary", {})
            if exps:
                evidence.append(f"Similar past experiences: {len(exps)} found")
                if summary.get("success_rate") is not None:
                    evidence.append(f"Historical success rate: {summary['success_rate']}%")
                if summary.get("top_failure_reasons"):
                    evidence.append(f"Common failure reasons: {'; '.join(summary['top_failure_reasons'][:2])}")

        return DecisionRecord(
            decision_id=report.report_id,
            decision_type="engineering_decision",
            reason=report.risk_assessment.reasoning,
            evidence=evidence,
            outcome=report.execution_plan.reasoning,
            confidence=report.deployment_strategy.confidence,
        )

    # ── Phase 9: Knowledge Graph Integration ──────────────────────────────

    async def _update_knowledge_graph(self, report: DecisionReport) -> None:
        """Record decision relationships in the knowledge graph."""
        try:
            from backend.services.enterprise_graph_service import enterprise_graph

            # Record the decision
            await enterprise_graph.record_decision(
                decision_id=report.report_id,
                execution_id=report.report_id,
                decision_type="engineering_decision",
                outcome=report.execution_plan.reasoning,
                reason=report.risk_assessment.reasoning,
            )

            # Record the risk
            await enterprise_graph.record_risk(
                execution_id=report.report_id,
                risk_id=f"{report.report_id}-risk",
                level=report.risk_assessment.level.value,
                description=report.risk_assessment.reasoning,
            )

        except Exception as exc:
            log.debug("Failed to update knowledge graph: %s", exc)

    # ── Phase 10: Decision Explainability ─────────────────────────────────

    def _explain_decision(self, report: DecisionReport, context_snapshot: Any = None) -> DecisionExplanation:
        """Explain WHY every decision was made."""
        factors: List[Dict[str, Any]] = []
        for f in report.risk_assessment.factors:
            factors.append({
                "factor": f.get("factor", "unknown"),
                "contribution": f"{f.get('weight', 0)}/100",
                "reason": f.get("reason", ""),
            })

        evidence_chain = [
            {"step": "change_detection", "what": f"{len(report.change_report.changed_files)} files changed",
             "categories": [c.value for c in report.change_report.categories]},
            {"step": "impact_analysis", "what": f"{report.impact_graph.total_affected_entities} entities affected",
             "services": report.impact_graph.affected_services},
            {"step": "risk_assessment", "what": f"Risk score {report.risk_assessment.score}/100",
             "level": report.risk_assessment.level.value},
            {"step": "execution_planning", "what": report.execution_plan.reasoning,
             "skipped_stages": report.execution_plan.skipped_stages},
            {"step": "approval_determination", "what": "Approval required" if report.approval_requirements.approval_required else "No approval needed",
             "approvers": [a.value for a in report.approval_requirements.required_approvers]},
            {"step": "deployment_strategy", "what": report.deployment_strategy.strategy.value,
             "confidence": report.deployment_strategy.confidence},
        ]

        # Add context evidence
        if context_snapshot:
            ctx_evidence = {"step": "enterprise_context", "what": "Full context snapshot collected"}
            ctx_sources = []
            biz = context_snapshot.business
            op = context_snapshot.operational

            # Operational evidence
            if op.active_alerts:
                ctx_sources.append(f"{len(op.active_alerts)} active alert(s)")
                ctx_evidence["active_alerts"] = len(op.active_alerts)
            if op.ongoing_deployments:
                ctx_sources.append(f"{len(op.ongoing_deployments)} ongoing deployment(s)")
            if op.rollbacks:
                ctx_sources.append(f"{len(op.rollbacks)} rollback(s) in progress")
            if op.runtime_health:
                ctx_evidence["runtime_health"] = op.runtime_health

            # Business evidence
            ctx_evidence["environment"] = biz.environment
            ctx_evidence["deployment_freeze"] = biz.deployment_freeze
            ctx_evidence["business_hours"] = biz.business_hours
            ctx_evidence["maintenance_window"] = biz.maintenance_window

            if ctx_sources:
                ctx_evidence["sources"] = "; ".join(ctx_sources)
            evidence_chain.append(ctx_evidence)

        # Build the main "why" statement
        why_parts = [
            f"Change involves {len(report.change_report.categories)} category(ies): {', '.join(c.value for c in report.change_report.categories)}.",
            f"Risk assessed at {report.risk_assessment.score:.0f}/100 ({report.risk_assessment.level.value}).",
        ]
        if report.approval_requirements.approval_required:
            why_parts.append(f"Approval required from: {', '.join(a.value for a in report.approval_requirements.required_approvers)}.")
        why_parts.append(f"Deploying via {report.deployment_strategy.strategy.value} ({report.deployment_strategy.confidence:.0f}% confidence).")
        why_parts.append(f"Pipeline: {report.execution_plan.reasoning}.")

        return DecisionExplanation(
            why=" ".join(why_parts),
            factors=factors,
            evidence_chain=evidence_chain,
            confidence=report.deployment_strategy.confidence,
            alternatives=[
                f"Full pipeline ({DeploymentStrategy.ROLLING.value})" if report.execution_plan.skipped_stages else "Reduced pipeline",
                f"{DeploymentStrategy.BLUE_GREEN.value} deployment" if report.deployment_strategy.strategy != DeploymentStrategy.BLUE_GREEN else f"{DeploymentStrategy.ROLLING.value} deployment",
            ],
        )

    # ── Phase 11: Executive Summary ───────────────────────────────────────

    def _generate_executive_summary(self, report: DecisionReport, context_snapshot: Any = None) -> ExecutiveSummary:
        """Generate an executive-facing summary of the decision."""
        change_count = len(report.change_report.changed_files)
        category_labels = ", ".join(c.value.replace("_", " ").title() for c in report.change_report.categories)

        # Add context-aware impact description
        impact_text = (
            f"{report.impact_graph.total_affected_entities} entities affected across "
            f"{len(report.impact_graph.affected_services)} service(s), "
            f"{len(report.impact_graph.affected_apis)} API(s)"
        )
        if context_snapshot:
            ctx_info = []
            biz = context_snapshot.business
            op = context_snapshot.operational
            if op.active_alerts:
                ctx_info.append(f"{len(op.active_alerts)} active alert(s)")
            if biz.deployment_freeze:
                ctx_info.append("deployment freeze active")
            if biz.hotfix_mode:
                ctx_info.append("hotfix mode")
            if op.runtime_health:
                ctx_info.append(f"cluster: {op.runtime_health}")
            if ctx_info:
                impact_text += f" | Context: {', '.join(ctx_info)}"

        predictions = report.predictions
        if predictions:
            pred_success = predictions.get("deployment_success_probability", 0)
            pred_rollback = predictions.get("rollback_probability", 0)
            pred_confidence = predictions.get("confidence", 0)
            impact_text += (
                f" | Prediction: {pred_success:.0%} success, "
                f"{pred_rollback:.0%} rollback risk "
                f"(confidence: {pred_confidence:.0%})"
            )
            if predictions.get("recommended_strategy"):
                impact_text += f" | Recommended: {predictions['recommended_strategy']}"

        confidence = report.deployment_strategy.confidence
        recommendations = self._generate_recommendations(report)
        estimated_dur = self._estimate_duration(report)

        if predictions:
            pred_success = predictions.get("deployment_success_probability", 0)
            pred_recovery = predictions.get("recovery_probability", 0)
            combined = 0.6 * confidence + 0.4 * (0.5 + pred_success * 0.3 + pred_recovery * 0.2)
            if combined > confidence:
                recommendations.append(f"Predictive simulation suggests {pred_success:.0%} deployment success probability — proceeding is recommended")
            else:
                recommendations.append(f"Predictive simulation shows {pred_success:.0%} success probability — consider {predictions.get('recommended_strategy', 'blue_green')} strategy for higher confidence")
            confidence = round(combined, 2)

        return ExecutiveSummary(
            repository=report.repository,
            change_summary=f"{change_count} file(s) changed — {category_labels}",
            impact=impact_text,
            risk_level=report.risk_assessment.level.value,
            risk_score=report.risk_assessment.score,
            affected_services=report.impact_graph.affected_services,
            required_tests=["unit", "integration"] if report.change_report.has_backend_changes else [],
            required_approvals=[a.value for a in report.approval_requirements.required_approvers],
            deployment_strategy=report.deployment_strategy.strategy.value,
            rollback_strategy=f"Automatic rollback via {report.deployment_strategy.strategy.value} rollback",
            estimated_duration=estimated_dur,
            confidence=confidence,
            recommendations=recommendations,
            key_decision=report.execution_plan.reasoning,
        )

    def _estimate_duration(self, report: DecisionReport) -> str:
        """Estimate pipeline duration based on change scope."""
        skipped = len(report.execution_plan.skipped_stages)
        total = len(report.execution_plan.required_stages)
        base = 5  # minutes
        if report.change_report.has_db_migrations:
            base += 10
        if report.change_report.has_infrastructure_changes:
            base += 15
        if report.risk_assessment.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            base += 10
        if report.approval_requirements.approval_required:
            base += 30  # buffer for human approval
        return f"~{base} min ({total} stages, {skipped} skipped)"

    def _generate_recommendations(self, report: DecisionReport) -> List[str]:
        """Generate actionable recommendations."""
        recs: List[str] = []
        if report.change_report.has_db_migrations:
            recs.append("Ensure database backup before migration")
            recs.append("Run migration in a transaction with rollback capability")
        if report.risk_assessment.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            recs.append("Enable enhanced monitoring and alerting for this deployment")
            recs.append("Prepare rollback plan before starting deployment")
        if report.change_report.has_dependency_changes:
            recs.append("Run dependency vulnerability scan")
            recs.append("Verify dependency licenses for compliance")
        if report.change_report.has_secret_changes:
            recs.append("Audit secret rotation — ensure no hardcoded credentials")
        if report.change_report.has_infrastructure_changes:
            recs.append("Run Terraform plan review before apply")
            recs.append("Validate infrastructure changes in a sandbox environment first")
        if not recs:
            recs.append("Standard deployment — no additional recommendations")
        return recs


    # ── Phase 12: Persistence ──────────────────────────────────────────────

    async def _persist_report(self, report: DecisionReport) -> None:
        """Persist the decision report to RuntimeStore."""
        try:
            from backend.services.enterprise_runtime_store import runtime_store
            await runtime_store.create_execution({
                "execution_id": report.report_id,
                "mission_id": report.report_id,
                "objective": f"Decision: {report.executive_summary.key_decision}",
                "repository": report.repository,
                "branch": report.branch,
                "commit_sha": report.commit_sha,
                "current_stage": "complete",
                "stages_completed": report.execution_plan.required_stages,
                "stages_failed": [],
                "deployment_strategy": report.deployment_strategy.strategy.value,
                "metadata": report.to_dict(),
            })
        except Exception as exc:
            log.debug("Failed to persist decision report: %s", exc)


# =============================================================================
# Singleton
# =============================================================================

engineering_decision_engine = EngineeringDecisionEngine()
