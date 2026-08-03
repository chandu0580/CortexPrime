"""
Enterprise Engineering Executive Runtime — supervises the complete engineering
lifecycle from GitHub event to verified completion.

This is a SUPERVISOR, not an orchestrator.
It delegates all work to existing subsystems.

Reuses (never duplicates):
  - EngineeringDecisionEngine   - EnterpriseContextIntelligence
  - EnterprisePredictiveSimulation - EnterpriseVerificationIntelligence
  - EnterpriseEngineeringMemory - RuntimeStore / ReplayStore
  - KnowledgeGraph              - EventHub
  - EnterpriseDeliveryOrchestrator - EnterpriseEngineeringExecutive

Phases:
  1. Mission Lifecycle (12 states)
  2. Executive State Machine
  3. Executive Supervision
  4. Autonomy Control
  5. Executive Policies
  6. Mission Intervention
  7. Mission Timeline
  8. Executive Dashboard
  9. Validation
"""
from __future__ import annotations

import logging
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(val: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, val))


# =============================================================================
# Phase 1 — Mission Lifecycle States
# =============================================================================


class MissionState(Enum):
    CREATED = "created"
    PLANNED = "planned"
    RUNNING = "running"
    WAITING = "waiting"
    APPROVAL = "approval"
    DEPLOYING = "deploying"
    MONITORING = "monitoring"
    VERIFYING = "verifying"
    LEARNING = "learning"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# =============================================================================
# Phase 4 — Autonomy Levels
# =============================================================================


class AutonomyLevel(Enum):
    AUTOMATIC = "automatic"
    APPROVAL_REQUIRED = "approval_required"
    HUMAN_INTERVENTION = "human_intervention"
    EMERGENCY_STOP = "emergency_stop"
    ROLLBACK = "rollback"


# =============================================================================
# Phase 1 — Mission Record (canonical runtime state)
# =============================================================================


@dataclass(frozen=True)
class MissionRecord:
    mission_id: str = ""
    execution_id: str = ""
    source: str = ""
    source_event: str = ""

    # Phase 2 — State
    current_phase: str = MissionState.CREATED.value
    previous_phase: str = ""
    current_owner: str = "executive_runtime"
    phase_changed_at: str = ""

    # Core context
    repository: str = ""
    branch: str = ""
    commit_sha: str = ""
    service: str = ""
    environment: str = ""

    # Decision
    decision_id: str = ""
    risk_score: float = 0.0
    risk_level: str = "low"
    deployment_strategy: str = "rolling"

    # Prediction
    prediction_id: str = ""
    predicted_success_probability: float = 0.5
    predicted_rollback_probability: float = 0.1

    # Verification
    verification_id: str = ""
    verification_accuracy: float = 0.0

    # Autonomy
    autonomy_level: str = AutonomyLevel.AUTOMATIC.value
    requires_human_approval: bool = False
    human_approval_status: str = ""
    intervention_count: int = 0
    last_intervention: str = ""

    # Runtime health
    runtime_health: str = "healthy"
    error_message: str = ""

    # Timing
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0

    # Scorecards
    change_categories: List[str] = field(default_factory=list)
    changed_services: List[str] = field(default_factory=list)
    has_db_migrations: bool = False
    has_infrastructure_changes: bool = False

    # Debug
    delivery_id: str = ""
    timeline_event_count: int = 0

    # Supervision (Phase 3 — GitOps / Infrastructure / Observability)
    gitops_sync_status: str = ""
    infra_health: str = ""
    observability_status: str = ""
    supervision_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Phase 2 — Executive State Machine
# =============================================================================


class ExecutiveStateMachine:
    """Maintain canonical runtime state and enforce valid transitions."""

    VALID_TRANSITIONS: Dict[str, List[str]] = {
        MissionState.CREATED.value: [MissionState.PLANNED.value, MissionState.FAILED.value, MissionState.CANCELLED.value],
        MissionState.PLANNED.value: [MissionState.RUNNING.value, MissionState.WAITING.value, MissionState.FAILED.value, MissionState.CANCELLED.value],
        MissionState.RUNNING.value: [MissionState.APPROVAL.value, MissionState.DEPLOYING.value, MissionState.WAITING.value, MissionState.FAILED.value, MissionState.CANCELLED.value],
        MissionState.WAITING.value: [MissionState.RUNNING.value, MissionState.CANCELLED.value, MissionState.FAILED.value],
        MissionState.APPROVAL.value: [MissionState.DEPLOYING.value, MissionState.RUNNING.value, MissionState.FAILED.value, MissionState.CANCELLED.value],
        MissionState.DEPLOYING.value: [MissionState.MONITORING.value, MissionState.WAITING.value, MissionState.FAILED.value, MissionState.CANCELLED.value],
        MissionState.MONITORING.value: [MissionState.VERIFYING.value, MissionState.DEPLOYING.value, MissionState.FAILED.value, MissionState.CANCELLED.value],
        MissionState.VERIFYING.value: [MissionState.LEARNING.value, MissionState.FAILED.value, MissionState.CANCELLED.value],
        MissionState.LEARNING.value: [MissionState.COMPLETED.value, MissionState.FAILED.value],
        MissionState.COMPLETED.value: [],
        MissionState.FAILED.value: [MissionState.PLANNED.value, MissionState.CANCELLED.value],
        MissionState.CANCELLED.value: [MissionState.PLANNED.value],
    }

    @classmethod
    def can_transition(cls, current: str, target: str) -> bool:
        return target in cls.VALID_TRANSITIONS.get(current, [])

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        return state in (MissionState.COMPLETED.value, MissionState.FAILED.value, MissionState.CANCELLED.value)


# =============================================================================
# Phase 5 — Executive Policies
# =============================================================================


@dataclass(frozen=True)
class PolicyConfig:
    max_risk_score: float = 0.7
    max_rollback_probability: float = 0.5
    require_approval_risk_threshold: float = 0.5
    require_approval_rollback_threshold: float = 0.3
    deployment_freeze_check: bool = True
    maintenance_window_check: bool = True
    max_concurrent_deployments: int = 3
    auto_rollback_risk_threshold: float = 0.75
    auto_abort_risk_threshold: float = 0.9


class PolicyEnforcer:
    """Enforce executive policies — risk thresholds, approvals, windows."""

    def __init__(self, config: Optional[PolicyConfig] = None) -> None:
        self.config = config or PolicyConfig()

    def check_risk_threshold(self, mission: MissionRecord) -> Tuple[bool, str]:
        if mission.risk_score >= self.config.auto_abort_risk_threshold:
            return False, f"Risk score {mission.risk_score:.2f} exceeds auto-abort threshold {self.config.auto_abort_risk_threshold}"
        if mission.risk_score >= self.config.auto_rollback_risk_threshold:
            return False, f"Risk score {mission.risk_score:.2f} exceeds auto-rollback threshold {self.config.auto_rollback_risk_threshold}"
        if mission.risk_score > self.config.max_risk_score:
            return False, f"Risk score {mission.risk_score:.2f} exceeds max {self.config.max_risk_score}"
        if mission.predicted_rollback_probability > self.config.max_rollback_probability:
            return False, f"Rollback probability {mission.predicted_rollback_probability:.2f} exceeds max {self.config.max_rollback_probability}"
        return True, ""

    def check_approval_required(self, mission: MissionRecord) -> Tuple[bool, str]:
        reasons: List[str] = []
        if mission.risk_score >= self.config.require_approval_risk_threshold:
            reasons.append(f"Risk score {mission.risk_score:.2f} >= threshold {self.config.require_approval_risk_threshold}")
        if mission.predicted_rollback_probability >= self.config.require_approval_rollback_threshold:
            reasons.append(f"Rollback probability {mission.predicted_rollback_probability:.2f} >= threshold {self.config.require_approval_rollback_threshold}")
        if mission.has_db_migrations:
            reasons.append("Database migration requires approval")
        if mission.has_infrastructure_changes:
            reasons.append("Infrastructure change requires approval")
        if not reasons:
            return False, ""
        return True, "; ".join(reasons)

    def set_autonomy_level(self, mission: MissionRecord) -> AutonomyLevel:
        if mission.risk_score >= self.config.auto_abort_risk_threshold:
            return AutonomyLevel.EMERGENCY_STOP
        if mission.risk_score >= self.config.auto_rollback_risk_threshold:
            return AutonomyLevel.ROLLBACK
        approval_needed, _ = self.check_approval_required(mission)
        if approval_needed:
            return AutonomyLevel.APPROVAL_REQUIRED
        return AutonomyLevel.AUTOMATIC

    def check_deployment_window(self, mission: MissionRecord) -> Tuple[bool, str]:
        try:
            from backend.services.enterprise_context_intelligence import enterprise_context_intelligence
            snap = enterprise_context_intelligence.build_snapshot(
                repository=mission.repository, branch=mission.branch,
                execution_id=mission.execution_id, environment=mission.environment,
            )
            if hasattr(snap, "business") and snap.business.deployment_freeze:
                return False, "Deployment freeze active"
            if hasattr(snap, "business") and not snap.business.maintenance_window:
                return True, "Outside maintenance window but no freeze"
        except Exception:
            pass
        return True, ""


# =============================================================================
# Phase 7 — Timeline
# =============================================================================


@dataclass(frozen=True)
class TimelineEntry:
    mission_id: str = ""
    phase: str = ""
    event_type: str = ""
    agent: str = ""
    message: str = ""
    timestamp: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Enterprise Engineering Executive Runtime
# =============================================================================


class EnterpriseEngineeringExecutiveRuntime:
    """Highest-level engineering coordinator — supervises full mission lifecycle."""

    def __init__(self) -> None:
        self._missions: Dict[str, MissionRecord] = {}
        self._timelines: Dict[str, List[TimelineEntry]] = defaultdict(list)
        self._policy = PolicyEnforcer()
        self._mission_counter: int = 0

    # ── Phase 1: Mission Lifecycle ─────────────────────────────────────────

    async def create_mission(
        self,
        source: str,
        source_event: str = "push",
        repository: str = "",
        branch: str = "main",
        commit_sha: str = "",
        service: str = "",
        environment: str = "production",
        execution_id: str = "",
        change_categories: Optional[List[str]] = None,
        changed_services: Optional[List[str]] = None,
        has_db_migrations: bool = False,
        has_infrastructure_changes: bool = False,
    ) -> Dict[str, Any]:
        """Create a new engineering mission."""
        self._mission_counter += 1
        mid = f"msn-{_id()}"
        eid = execution_id or f"exec-{_id()}"

        mission = MissionRecord(
            mission_id=mid,
            execution_id=eid,
            source=source,
            source_event=source_event,
            current_phase=MissionState.CREATED.value,
            current_owner="executive_runtime",
            phase_changed_at=_now(),
            repository=repository,
            branch=branch,
            commit_sha=commit_sha,
            service=service,
            environment=environment,
            autonomy_level=AutonomyLevel.AUTOMATIC.value,
            runtime_health="healthy",
            created_at=_now(),
            change_categories=change_categories or [],
            changed_services=changed_services or [],
            has_db_migrations=has_db_migrations,
            has_infrastructure_changes=has_infrastructure_changes,
        )
        self._missions[mid] = mission
        self._add_timeline(mid, MissionState.CREATED.value, "mission.created",
                           "executive_runtime", f"Mission {mid} created from {source}/{source_event}")
        return mission.to_dict()

    async def plan_mission(self, mission_id: str) -> Dict[str, Any]:
        """Plan mission — gather context, make decision, run prediction."""
        mission = self._get_mission(mission_id)
        if mission.current_phase != MissionState.PLANNED.value:
            self._transition(mission_id, MissionState.PLANNED.value)

        # Phase 8 — Repository Brain auto-load (feeds context + decision)
        brain_summary = {}
        try:
            from backend.services.enterprise_repository_brain import repository_brain
            brain_summary = await repository_brain.get_brain_summary(mission.repository)
            self._add_timeline(mission_id, MissionState.PLANNED.value, "brain.loaded",
                               "enterprise_repository_brain",
                               f"Brain summary loaded: {brain_summary.get('architecture', {}).get('services', 0)} services, "
                               f"{brain_summary.get('drift_count', 0)} drifts")
        except Exception as exc:
            log.debug("Repository Brain load failed: %s", exc)

        # Phase 3 — Gather context
        ctx = {}
        if brain_summary:
            ctx["brain"] = brain_summary
        try:
            from backend.services.enterprise_context_intelligence import enterprise_context_intelligence
            snap = await enterprise_context_intelligence.build_snapshot(
                repository=mission.repository, branch=mission.branch,
                commit=mission.commit_sha, execution_id=mission.execution_id,
                service=mission.service, environment=mission.environment,
            )
            ctx = snap.to_dict()
            self._add_timeline(mission_id, MissionState.PLANNED.value, "context.collected",
                               "enterprise_context_intelligence",
                               f"Context snapshot built ({len(ctx.get('sources_used', []))} sources)")
        except Exception as exc:
            log.debug("Context collection failed: %s", exc)

        # Phase 3 — Make decision (with Repository Brain awareness)
        decision = {}
        try:
            from backend.services.engineering_decision_engine import engineering_decision_engine
            report = await engineering_decision_engine.analyze(
                source=mission.source, event_type=mission.source_event,
                payload={"repository": mission.repository, "ref": f"refs/heads/{mission.branch}",
                         "commits": [{"modified": mission.change_categories, "added": [], "removed": []}]},
                repository=mission.repository, branch=mission.branch,
                commit_sha=mission.commit_sha, context_snapshot=snap if ctx else None,
                repository_brain=brain_summary,
            )
            decision = report.to_dict()
            risk = decision.get("risk_assessment", {})
            strat = decision.get("deployment_strategy", {})
            self._update_mission(mission_id,
                                 decision_id=report.report_id,
                                 # engineering_decision_engine's RiskAssessment.score is 0-100;
                                 # every consumer of mission.risk_score elsewhere in this file
                                 # (PolicyConfig thresholds, confidence=1.0-risk_score, etc.)
                                 # treats it as 0-1 — normalize at the boundary.
                                 risk_score=risk.get("score", 0) / 100.0,
                                 risk_level=risk.get("level", "low"),
                                 deployment_strategy=strat.get("strategy", "rolling"),
                                 )
            self._add_timeline(mission_id, MissionState.PLANNED.value, "decision.made",
                               "engineering_decision_engine",
                               f"Decision {report.report_id}: risk={risk.get('score', 0)}, strategy={strat.get('strategy', '')}")
        except Exception as exc:
            log.debug("Decision engine failed: %s", exc)

        # Phase 3 — Run prediction
        prediction = {}
        try:
            from backend.services.enterprise_predictive_simulation import enterprise_predictive_simulation
            pred_result = await enterprise_predictive_simulation.consume_predictions(
                repository=mission.repository, branch=mission.branch,
                commit_sha=mission.commit_sha, execution_id=mission.execution_id,
                service=mission.service, environment=mission.environment,
                change_categories=mission.change_categories,
                changed_services=mission.changed_services,
            )
            prediction = pred_result
            self._update_mission(mission_id,
                                 prediction_id=pred_result.get("prediction_id", ""),
                                 predicted_success_probability=pred_result.get("deployment_success_probability", 0.5),
                                 predicted_rollback_probability=pred_result.get("rollback_probability", 0.1),
                                 )
            self._add_timeline(mission_id, MissionState.PLANNED.value, "prediction.completed",
                               "enterprise_predictive_simulation",
                               f"Prediction: success={pred_result.get('deployment_success_probability', 0):.1%}")
        except Exception as exc:
            log.debug("Prediction failed: %s", exc)

        # Phase 5 — Enforce policies
        mission = self._get_mission(mission_id)
        policy_ok, policy_msg = self._policy.check_risk_threshold(mission)
        if not policy_ok:
            self._update_mission(mission_id, error_message=policy_msg)
            self._add_timeline(mission_id, MissionState.PLANNED.value, "policy.violation",
                               "executive_runtime", policy_msg)
            self._transition(mission_id, MissionState.FAILED.value)
            return {"status": "failed", "reason": policy_msg, "mission_id": mission_id,
                    "decision": decision, "prediction": prediction}

        approval_needed, approval_reason = self._policy.check_approval_required(mission)
        self._update_mission(mission_id, requires_human_approval=approval_needed)
        if approval_needed:
            self._add_timeline(mission_id, MissionState.PLANNED.value, "approval.required",
                               "executive_runtime", approval_reason)

        return {
            "status": "planned",
            "mission_id": mission_id,
            "decision": decision,
            "prediction": prediction,
            "context": ctx,
            "approval_required": approval_needed,
            "approval_reason": approval_reason if approval_needed else "",
        }

    async def run_mission(
        self,
        mission_id: str,
        approval_granted: bool = False,
        delivery_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run mission — proceed through approval, deployment, monitoring, verification, learning."""
        mission = self._get_mission(mission_id)

        self._transition(mission_id, MissionState.RUNNING.value)
        if mission.requires_human_approval and not approval_granted:
            self._transition(mission_id, MissionState.APPROVAL.value)
            autonomy = self._policy.set_autonomy_level(mission)
            self._update_mission(mission_id, autonomy_level=autonomy.value,
                                 human_approval_status="pending")
            self._add_timeline(mission_id, MissionState.APPROVAL.value, "approval.pending",
                               "executive_runtime", "Awaiting human approval before deployment")
            return {"status": "awaiting_approval", "mission_id": mission_id,
                    "risk_score": mission.risk_score,
                    "requires_human_approval": True}
        self._update_mission(mission_id, started_at=_now(),
                             autonomy_level=AutonomyLevel.AUTOMATIC.value,
                             human_approval_status="approved" if approval_granted else "not_required")

        # Phase 4 — Determine autonomy
        autonomy = self._policy.set_autonomy_level(mission)
        self._update_mission(mission_id, autonomy_level=autonomy.value)
        if autonomy == AutonomyLevel.EMERGENCY_STOP:
            self._transition(mission_id, MissionState.CANCELLED.value)
            self._add_timeline(mission_id, MissionState.CANCELLED.value, "emergency.stop",
                               "executive_runtime", "Emergency stop triggered by risk threshold")
            return {"status": "emergency_stopped", "mission_id": mission_id}

        if autonomy == AutonomyLevel.ROLLBACK:
            return await self._execute_rollback(mission_id, "Risk threshold triggered auto-rollback")

        # Phase 3 — Deploy
        deploy_result = {}
        try:
            from backend.services.enterprise_delivery_orchestrator import delivery_orchestrator
            self._transition(mission_id, MissionState.DEPLOYING.value)
            d_result = await delivery_orchestrator.create_delivery(
                mission={"execution_id": mission.execution_id, "objective": f"Deploy {mission.repository}"},
                repository=mission.repository,
            )
            if isinstance(d_result, dict):
                did = d_result.get("delivery_id", d_result.get("id", ""))
                self._update_mission(mission_id, delivery_id=did)
                try:
                    d_start = await delivery_orchestrator.start_delivery(did)
                    deploy_result = d_start if isinstance(d_start, dict) else {"status": "started"}
                except Exception:
                    deploy_result = {"status": "delivery_started"}
                self._add_timeline(mission_id, MissionState.DEPLOYING.value, "deployment.started",
                                   "enterprise_delivery_orchestrator",
                                   f"Delivery {did} started for {mission.repository}")
        except Exception as exc:
            log.debug("Deployment failed: %s", exc)
            deploy_result = {"status": "failed", "error": str(exc)[:200]}

        # Phase 3 — Monitor
        self._transition(mission_id, MissionState.MONITORING.value)
        monitor = self._monitor_health(mission_id)
        self._add_timeline(mission_id, MissionState.MONITORING.value, "monitoring.started",
                           "executive_runtime", "Post-deployment monitoring initiated")

        # Phase 3 — Verify
        self._transition(mission_id, MissionState.VERIFYING.value)
        verification = {}
        try:
            from backend.services.enterprise_verification_intelligence import enterprise_verification_intelligence
            v_result = await enterprise_verification_intelligence.verify(
                execution_id=mission.execution_id,
                prediction_id=mission.prediction_id,
                repository=mission.repository,
                environment=mission.environment,
                predicted_success=mission.predicted_success_probability,
                actual_success=deploy_result.get("status") in ("completed", "started", "delivery_started"),
                predicted_rollback_probability=mission.predicted_rollback_probability,
                actual_rolled_back=deploy_result.get("status") == "rolled_back",
                actual_outcome=deploy_result.get("status", "unknown"),
                change_categories=mission.change_categories,
                changed_services=mission.changed_services,
                has_db_migrations=mission.has_db_migrations,
                has_infrastructure_changes=mission.has_infrastructure_changes,
            )
            verification = v_result
            report = v_result.get("report", {})
            self._update_mission(mission_id,
                                 verification_id=v_result.get("verification_id", ""),
                                 verification_accuracy=report.get("prediction_accuracy", 0),
                                 )
            self._add_timeline(mission_id, MissionState.VERIFYING.value, "verification.completed",
                               "enterprise_verification_intelligence",
                               f"Verification accuracy: {report.get('prediction_accuracy', 0):.1%}")
        except Exception as exc:
            log.debug("Verification failed: %s", exc)

        # Phase 3 — Learn
        self._transition(mission_id, MissionState.LEARNING.value)
        try:
            from backend.services.enterprise_engineering_memory import enterprise_engineering_memory
            await enterprise_engineering_memory.build_experience(
                execution_id=mission.execution_id,
                repository=mission.repository,
                outcome=deploy_result.get("status", "unknown"),
                duration_seconds=0,
                changed_services=mission.changed_services,
                change_categories=mission.change_categories,
            )
            self._add_timeline(mission_id, MissionState.LEARNING.value, "learning.completed",
                               "enterprise_engineering_memory", "Experience stored")
        except Exception as exc:
            log.debug("Learning failed: %s", exc)

        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type="engineering.mission_completed",
                agent="enterprise_executive_runtime",
                status="completed",
                message=f"Mission {mission_id} completed for {mission.repository}",
                execution_id=mission.execution_id,
                metadata={
                    "mission_id": mission_id,
                    "repository": mission.repository,
                    "risk_score": mission.risk_score,
                    "verification_accuracy": mission.verification_accuracy,
                    "deployment_status": deploy_result.get("status", ""),
                },
            )
        except Exception:
            pass

        self._transition(mission_id, MissionState.COMPLETED.value)
        completed = _now()
        dur = 0.0
        if mission.created_at:
            try:
                dur = (datetime.fromisoformat(completed) - datetime.fromisoformat(mission.created_at)).total_seconds()
            except Exception:
                pass
        self._update_mission(mission_id, completed_at=completed, duration_seconds=round(dur, 1))

        return {
            "status": "completed",
            "mission_id": mission_id,
            "deployment": deploy_result,
            "monitoring": monitor,
            "verification": verification,
            "duration_seconds": round(dur, 1),
            "timeline": self._get_timeline(mission_id),
        }

    # ── Phase 6: Mission Intervention ──────────────────────────────────────

    async def pause_mission(self, mission_id: str) -> Dict[str, Any]:
        """Pause a running mission."""
        mission = self._get_mission(mission_id)
        if mission.current_phase not in (MissionState.RUNNING.value, MissionState.DEPLOYING.value,
                                         MissionState.MONITORING.value, MissionState.VERIFYING.value):
            return {"status": "invalid", "message": f"Cannot pause in phase {mission.current_phase}"}
        self._transition(mission_id, MissionState.WAITING.value)
        self._record_intervention(mission_id, "pause")
        return {"status": "paused", "mission_id": mission_id}

    async def resume_mission(self, mission_id: str) -> Dict[str, Any]:
        """Resume a paused mission."""
        mission = self._get_mission(mission_id)
        if mission.current_phase != MissionState.WAITING.value:
            return {"status": "invalid", "message": f"Cannot resume from phase {mission.current_phase}"}
        self._transition(mission_id, mission.previous_phase or MissionState.RUNNING.value)
        self._record_intervention(mission_id, "resume")
        return {"status": "resumed", "mission_id": mission_id, "phase": mission.current_phase}

    async def escalate_mission(self, mission_id: str, reason: str = "") -> Dict[str, Any]:
        """Escalate mission — require human intervention."""
        mission = self._get_mission(mission_id)
        self._update_mission(mission_id, autonomy_level=AutonomyLevel.HUMAN_INTERVENTION.value,
                             error_message=reason or "Escalated by executive")
        self._record_intervention(mission_id, "escalate")
        self._add_timeline(mission_id, mission.current_phase, "mission.escalated",
                           "executive_runtime", reason or "Mission escalated")
        return {"status": "escalated", "mission_id": mission_id}

    async def rollback_mission(self, mission_id: str, reason: str = "") -> Dict[str, Any]:
        """Rollback a mission."""
        return await self._execute_rollback(mission_id, reason or "Manual rollback requested")

    async def retry_mission(self, mission_id: str) -> Dict[str, Any]:
        """Retry from current phase."""
        mission = self._get_mission(mission_id)
        if ExecutiveStateMachine.is_terminal(mission.current_phase):
            return {"status": "invalid", "message": f"Cannot retry terminal phase {mission.current_phase}"}
        self._record_intervention(mission_id, "retry")
        self._add_timeline(mission_id, mission.current_phase, "mission.retry",
                           "executive_runtime", "Retrying from current phase")
        return {"status": "retrying", "mission_id": mission_id, "phase": mission.current_phase}

    async def abort_mission(self, mission_id: str, reason: str = "") -> Dict[str, Any]:
        """Abort and cancel a mission."""
        mission = self._get_mission(mission_id)
        if ExecutiveStateMachine.is_terminal(mission.current_phase):
            return {"status": "invalid", "message": "Mission already in terminal state"}
        self._transition(mission_id, MissionState.CANCELLED.value)
        self._update_mission(mission_id, error_message=reason or "Aborted by executive")
        self._record_intervention(mission_id, "abort")
        self._add_timeline(mission_id, MissionState.CANCELLED.value, "mission.aborted",
                           "executive_runtime", reason or "Mission aborted")
        return {"status": "cancelled", "mission_id": mission_id, "reason": reason}

    async def replan_mission(self, mission_id: str) -> Dict[str, Any]:
        """Re-plan mission from PLANNED state."""
        mission = self._get_mission(mission_id)
        if mission.current_phase not in (MissionState.FAILED.value, MissionState.CANCELLED.value, MissionState.PLANNED.value):
            return {"status": "invalid", "message": "Can only re-plan failed/cancelled/planned missions"}
        self._transition(mission_id, MissionState.PLANNED.value)
        self._record_intervention(mission_id, "replan")
        return await self.plan_mission(mission_id)

    # ── Phases 7+8: Timeline & Dashboard ───────────────────────────────────

    async def get_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        mission = self._missions.get(mission_id)
        if not mission:
            return None
        result = mission.to_dict()
        result["timeline"] = self._get_timeline(mission_id)
        return result

    async def list_missions(self, status: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        results = []
        for mid, m in sorted(self._missions.items(), key=lambda x: x[1].created_at, reverse=True):
            if status and m.current_phase != status:
                continue
            results.append(m.to_dict())
            if len(results) >= limit:
                break
        return results

    async def list_active_missions(self) -> List[Dict[str, Any]]:
        active_states = {MissionState.CREATED.value, MissionState.PLANNED.value,
                         MissionState.RUNNING.value, MissionState.WAITING.value,
                         MissionState.APPROVAL.value, MissionState.DEPLOYING.value,
                         MissionState.MONITORING.value, MissionState.VERIFYING.value,
                         MissionState.LEARNING.value}
        return [m.to_dict() for m in self._missions.values()
                if m.current_phase in active_states]

    async def get_dashboard(self) -> Dict[str, Any]:
        total = len(self._missions)
        if total == 0:
            return {
                "active_missions": 0,
                "total_missions": 0,
                "mission_health": "no_data",
                "executive_decisions": 0,
                "autonomy_level": "automatic",
                "human_approvals": 0,
                "interventions": 0,
                "mission_success_rate": 0.0,
                "mission_reliability": 0.0,
            }

        active = sum(1 for m in self._missions.values()
                     if m.current_phase not in (MissionState.COMPLETED.value,
                                                MissionState.FAILED.value,
                                                MissionState.CANCELLED.value))
        completed = sum(1 for m in self._missions.values()
                        if m.current_phase == MissionState.COMPLETED.value)
        failed = sum(1 for m in self._missions.values()
                     if m.current_phase == MissionState.FAILED.value)
        cancelled = sum(1 for m in self._missions.values()
                        if m.current_phase == MissionState.CANCELLED.value)

        success_rate = completed / max(total, 1)
        reliability = completed / max(completed + failed, 1) if completed + failed > 0 else 0

        autonomy_counts = Counter(m.autonomy_level for m in self._missions.values())
        total_interventions = sum(m.intervention_count for m in self._missions.values())
        approvals_granted = sum(1 for m in self._missions.values()
                                if m.human_approval_status == "approved")

        health = "healthy"
        if failed > completed * 0.5 and total > 5:
            health = "degraded"
        if failed > completed and total > 3:
            health = "critical"

        return {
            "active_missions": active,
            "total_missions": total,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "mission_health": health,
            "executive_decisions": total,
            "autonomy_level": autonomy_counts.most_common(1)[0][0] if autonomy_counts else "automatic",
            "human_approvals": approvals_granted,
            "interventions": total_interventions,
            "mission_success_rate": round(success_rate, 3),
            "mission_reliability": round(reliability, 3),
            "by_phase": dict(Counter(m.current_phase for m in self._missions.values())),
        }

    # ── Internal ───────────────────────────────────────────────────────────

    def _get_mission(self, mission_id: str) -> MissionRecord:
        mission = self._missions.get(mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")
        return mission

    def _get_timeline(self, mission_id: str) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._timelines.get(mission_id, [])]

    def _monitor_health(self, mission_id: str) -> Dict[str, Any]:
        health = "healthy"
        details: List[str] = []
        mission = self._get_mission(mission_id)
        if mission.risk_score > 0.7:
            health = "degraded"
            details.append("High risk score")
        if mission.verification_accuracy > 0 and mission.verification_accuracy < 0.3:
            health = "degraded"
            details.append("Low verification accuracy")
        self._update_mission(mission_id, runtime_health=health)
        return {"health": health, "details": details}

    async def _execute_rollback(self, mission_id: str, reason: str) -> Dict[str, Any]:
        self._update_mission(mission_id, autonomy_level=AutonomyLevel.ROLLBACK.value,
                             error_message=reason)
        self._add_timeline(mission_id, MissionState.DEPLOYING.value, "rollback.started",
                           "executive_runtime", reason)
        rollback_result = {}
        try:
            from backend.services.enterprise_delivery_orchestrator import delivery_orchestrator
            mission = self._get_mission(mission_id)
            if mission.delivery_id:
                rb = await delivery_orchestrator.rollback_delivery(mission.delivery_id)
                rollback_result = rb if isinstance(rb, dict) else {"status": "rolled_back"}
        except Exception as exc:
            log.debug("Rollback failed: %s", exc)
            rollback_result = {"status": "rollback_failed"}
        self._add_timeline(mission_id, MissionState.DEPLOYING.value, "rollback.completed",
                           "executive_runtime", "Rollback executed")
        self._transition(mission_id, MissionState.FAILED.value)
        completed = _now()
        dur = 0.0
        mission = self._get_mission(mission_id)
        if mission.created_at:
            try:
                dur = (datetime.fromisoformat(completed) - datetime.fromisoformat(mission.created_at)).total_seconds()
            except Exception:
                pass
        self._update_mission(mission_id, completed_at=completed, duration_seconds=round(dur, 1))
        return {"status": "rolled_back", "mission_id": mission_id, "reason": reason,
                "rollback": rollback_result}


    # ── Persistence ─────────────────────────────────────────────────────────

    def _persist_to_runtime_store(self, mission: MissionRecord) -> None:
        """Persist mission to RuntimeStore."""
        try:
            from backend.services.enterprise_runtime_store import EngineeringExecution, runtime_store
            execution = EngineeringExecution(
                execution_id=mission.execution_id,
                mission_id=mission.mission_id,
                repository=mission.repository,
                branch=mission.branch,
                commit_sha=mission.commit_sha,
                status=mission.current_phase,
                owner=mission.current_owner,
                started_at=mission.started_at or mission.created_at,
                completed_at=mission.completed_at,
                duration_seconds=mission.duration_seconds,
                deployment_environment=mission.environment,
                deployment_strategy=mission.deployment_strategy,
                approval_status=mission.human_approval_status,
                approval_required=mission.requires_human_approval,
                verification=(
                    {"accuracy": mission.verification_accuracy, "verification_id": mission.verification_id}
                    if mission.verification_id else {}
                ),
                event_type=mission.source_event,
                failure_reason=mission.error_message,
                created_at=mission.created_at,
                updated_at=_now(),
            )
            existing = runtime_store.get_execution(mission.execution_id)
            if existing:
                runtime_store.update_execution(mission.execution_id,
                    status=mission.current_phase, updated_at=_now(),
                    deployment_environment=mission.environment,
                    failure_reason=mission.error_message,
                )
            else:
                runtime_store.create_execution(execution)
        except Exception as exc:
            log.debug("RuntimeStore persistence failed: %s", exc)

    async def _record_to_replay_store(self, timeline_entry: TimelineEntry) -> None:
        """Record timeline event to ReplayStore."""
        try:
            from backend.events.event_models import CognitionEvent
            from backend.services.mission_replay_store import replay_store
            event = CognitionEvent(
                event_type=timeline_entry.event_type,
                agent=timeline_entry.agent,
                status=timeline_entry.phase,
                message=timeline_entry.message,
                execution_id=timeline_entry.mission_id,
                metadata={"phase": timeline_entry.phase, **timeline_entry.metadata},
            )
            await replay_store.record(event)
        except Exception as exc:
            log.debug("ReplayStore recording failed: %s", exc)

    async def _record_to_knowledge_graph(self, mission: MissionRecord, record_type: str = "state_change") -> None:
        """Record mission lifecycle event to KnowledgeGraph."""
        try:
            from backend.services.enterprise_graph_service import enterprise_graph
            props = {
                "mission_id": mission.mission_id,
                "execution_id": mission.execution_id,
                "phase": mission.current_phase,
                "repository": mission.repository,
                "branch": mission.branch,
                "risk_score": mission.risk_score,
                "environment": mission.environment,
                "autonomy_level": mission.autonomy_level,
                "timestamp": _now(),
            }
            if record_type == "mission_created":
                await enterprise_graph.record_mission_launch(
                    execution_id=mission.execution_id,
                    template_name=mission.source,
                    objective=f"Deploy {mission.repository}/{mission.branch}",
                    repository=mission.repository,
                    environment=mission.environment,
                )
            elif record_type == "decision":
                await enterprise_graph.record_decision(
                    execution_id=mission.execution_id,
                    decision_id=mission.decision_id,
                    decision=f"Mission {mission.mission_id}: risk={mission.risk_score}",
                    rationale=f"Risk level {mission.risk_level}, strategy {mission.deployment_strategy}",
                    outcome="approved",
                    confidence=1.0 - mission.risk_score,
                )
            elif record_type == "risk":
                await enterprise_graph.record_risk(
                    execution_id=mission.execution_id,
                    risk_id=f"risk-{mission.mission_id}",
                    risk_type="engineering",
                    severity=mission.risk_level,
                    description=mission.error_message or f"Risk score: {mission.risk_score}",
                    mitigated=mission.current_phase not in (MissionState.FAILED.value, MissionState.CANCELLED.value),
                )
            elif record_type == "approval":
                await enterprise_graph.record_approval(
                    execution_id=mission.execution_id,
                    approval_id=f"aprv-{_id()}",
                    approver=mission.current_owner,
                    decision=mission.human_approval_status,
                    justification=mission.error_message or "Executive approval",
                )
            elif record_type == "outcome":
                await enterprise_graph.record_outcome(
                    execution_id=mission.execution_id,
                    outcome_id=f"out-{_id()}",
                    result=mission.current_phase,
                    summary=f"Mission completed with {mission.verification_accuracy:.1%} accuracy",
                    success=mission.current_phase == MissionState.COMPLETED.value,
                    duration_seconds=mission.duration_seconds,
                )
            else:
                await enterprise_graph.upsert_entity(
                    entity_type="executive_mission_state",
                    entity_id=f"{mission.mission_id}-{mission.current_phase}",
                    properties=props,
                )
        except Exception as exc:
            log.debug("KnowledgeGraph recording failed: %s", exc)

    # ── Phase 3: Supervision (GitOps / Infrastructure / Observability) ────

    async def _supervise_gitops(self, mission: MissionRecord) -> Dict[str, Any]:
        """Supervise GitOps — check ArgoCD sync status."""
        result: Dict[str, Any] = {"status": "unknown", "details": []}
        try:
            from backend.services.enterprise_argocd_intelligence import argocd_intelligence
            if hasattr(argocd_intelligence, "get_sync_status"):
                sync = await argocd_intelligence.get_sync_status(
                    app_name=mission.service or mission.repository.split("/")[-1],
                    environment=mission.environment,
                )
                if isinstance(sync, dict):
                    result["status"] = sync.get("status", "unknown")
                    result["details"] = [f"ArgoCD sync: {sync.get('status', 'unknown')}"]
            self._update_mission(mission.mission_id, gitops_sync_status=result["status"])
        except Exception as exc:
            log.debug("GitOps supervision failed: %s", exc)
            result["status"] = "unavailable"
        return result

    async def _supervise_infrastructure(self, mission: MissionRecord) -> Dict[str, Any]:
        """Supervise Infrastructure — check cluster/pod health."""
        result: Dict[str, Any] = {"status": "healthy", "details": []}
        try:
            from backend.services.enterprise_infrastructure_intelligence import infrastructure_intelligence
            if hasattr(infrastructure_intelligence, "get_cluster_health"):
                health = await infrastructure_intelligence.get_cluster_health()
                if isinstance(health, dict):
                    overall = health.get("overall", health.get("status", "healthy"))
                    result["status"] = overall
                    if overall != "healthy":
                        result["details"].append(f"Cluster health: {overall}")
            if hasattr(infrastructure_intelligence, "check_deployment_health"):
                dep_health = await infrastructure_intelligence.check_deployment_health(
                    namespace=mission.environment,
                    deployment=mission.service or "unknown",
                )
                if isinstance(dep_health, dict):
                    dep_status = dep_health.get("status", dep_health.get("health", "healthy"))
                    if dep_status != "healthy":
                        result["details"].append(f"Deployment health: {dep_status}")
            self._update_mission(mission.mission_id, infra_health=result["status"])
        except Exception as exc:
            log.debug("Infrastructure supervision failed: %s", exc)
        return result

    async def _supervise_observability(self, mission: MissionRecord) -> Dict[str, Any]:
        """Supervise Observability — check metrics, alerts, logs."""
        result: Dict[str, Any] = {"status": "nominal", "details": [], "alerts": []}
        try:
            from backend.services.enterprise_prometheus_intelligence import prometheus_intelligence
            if hasattr(prometheus_intelligence, "get_alert_status"):
                alerts = await prometheus_intelligence.get_alert_status()
                if isinstance(alerts, list):
                    active_alerts = [a for a in alerts if isinstance(a, dict) and a.get("status") == "firing"]
                    result["alerts"] = active_alerts[:5]
                    if active_alerts:
                        result["details"].append(f"{len(active_alerts)} active alerts")
                        result["status"] = "degraded"
            if hasattr(prometheus_intelligence, "get_metrics_summary"):
                metrics = await prometheus_intelligence.get_metrics_summary()
                if isinstance(metrics, dict):
                    error_rate = metrics.get("error_rate", 0)
                    latency = metrics.get("p99_latency_ms", 0)
                    if error_rate > 5:
                        result["details"].append(f"Error rate: {error_rate}%")
                        result["status"] = "degraded"
                    if latency > 2000:
                        result["details"].append(f"P99 latency: {latency}ms")
                        result["status"] = "degraded"
            try:
                from backend.services.enterprise_loki_intelligence import loki_intelligence
                if hasattr(loki_intelligence, "check_recent_errors"):
                    errors = await loki_intelligence.check_recent_errors()
                    if isinstance(errors, list) and errors:
                        result["details"].append(f"{len(errors)} recent log errors")
                        if result["status"] == "nominal":
                            result["status"] = "degraded"
            except Exception:
                pass
            self._update_mission(mission.mission_id, observability_status=result["status"])
        except Exception as exc:
            log.debug("Observability supervision failed: %s", exc)
        return result

    async def _collect_supervision_context(self, mission_id: str) -> Dict[str, Any]:
        """Collect supervision context from all supervision domains."""
        mission = self._get_mission(mission_id)
        supervision: Dict[str, Any] = {}
        supervision["gitops"] = await self._supervise_gitops(mission)
        supervision["infrastructure"] = await self._supervise_infrastructure(mission)
        supervision["observability"] = await self._supervise_observability(mission)
        self._update_mission(mission_id, supervision_details=supervision)
        return supervision

    # ── GitHub event handler — auto-create missions from webhooks ─────────

    async def handle_github_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle a GitHub webhook event and auto-create a mission.

        Delegates to AutonomousTriggerRuntime for policy matching, or
        creates a mission directly for simple push/pull_request events.
        """
        gh_event = payload.get("event_type", event_type)
        repo_full = ""
        branch = "main"
        commit_sha = ""
        change_categories: List[str] = []
        changed_services: List[str] = []

        if "repository" in payload:
            repo_data = payload["repository"]
            repo_full = repo_data.get("full_name", repo_data.get("name", ""))
            if not repo_full and "clone_url" in repo_data:
                repo_full = repo_data["clone_url"]

        if "ref" in payload:
            ref = payload["ref"]
            if ref.startswith("refs/heads/"):
                branch = ref[11:]

        if "commits" in payload and isinstance(payload["commits"], list):
            for c in payload["commits"]:
                if isinstance(c, dict):
                    for ftype in ("modified", "added", "removed"):
                        for f in c.get(ftype, []):
                            change_categories.append(ftype)
                            if "/" in f:
                                svc = f.split("/")[0]
                                if svc not in changed_services:
                                    changed_services.append(svc)
                            if f.endswith((".py", ".js", ".ts", ".java", ".go", ".rs")):
                                if "backend" not in changed_services:
                                    changed_services.append("backend")

        if "head_commit" in payload and isinstance(payload["head_commit"], dict):
            commit_sha = payload["head_commit"].get("id", payload["head_commit"].get("sha", ""))

        try:
            from backend.services.autonomous_trigger_runtime import trigger_runtime
            if hasattr(trigger_runtime, "process_event"):
                result = await trigger_runtime.process_event(
                    source="github",
                    event_type=gh_event,
                    payload=payload,
                )
                return result
        except Exception:
            pass

        if gh_event in ("push", "pull_request", "workflow_run"):
            has_db = any("migration" in c or "database" in c for c in change_categories)
            has_infra = any(c in ("infrastructure", "terraform", "k8s", "helm", "docker") for c in change_categories)
            return await self.create_mission(
                source="github",
                source_event=gh_event,
                repository=repo_full,
                branch=branch,
                commit_sha=commit_sha,
                change_categories=list(set(change_categories)),
                changed_services=list(set(changed_services)),
                has_db_migrations=has_db,
                has_infrastructure_changes=has_infra,
            )

        return None

    # ── Override internal methods for persistence ──────────────────────────

    def _update_mission(self, mission_id: str, **kwargs: Any) -> None:
        mission = self._get_mission(mission_id)
        current = mission.to_dict()
        for k, v in kwargs.items():
            current[k] = v
        new_mission = MissionRecord(**current)
        self._missions[mission_id] = new_mission
        self._persist_to_runtime_store(new_mission)

    def _add_timeline(self, mission_id: str, phase: str, event_type: str,
                      agent: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        entry = TimelineEntry(
            mission_id=mission_id, phase=phase, event_type=event_type,
            agent=agent, message=message, timestamp=_now(),
            metadata=metadata or {},
        )
        self._timelines[mission_id].append(entry)
        self._update_mission(mission_id, timeline_event_count=len(self._timelines[mission_id]))

    def _transition(self, mission_id: str, target: str) -> None:
        mission = self._get_mission(mission_id)
        if not ExecutiveStateMachine.can_transition(mission.current_phase, target):
            raise ValueError(f"Invalid transition: {mission.current_phase} -> {target}")
        prev = mission.current_phase
        self._update_mission(mission_id, previous_phase=prev, current_phase=target,
                             phase_changed_at=_now())

    def _record_intervention(self, mission_id: str, intervention_type: str) -> None:
        mission = self._get_mission(mission_id)
        self._update_mission(mission_id,
                             intervention_count=mission.intervention_count + 1,
                             last_intervention=f"{intervention_type} at {_now()}")


# =============================================================================
# Singleton
# =============================================================================

enterprise_executive_runtime = EnterpriseEngineeringExecutiveRuntime()
