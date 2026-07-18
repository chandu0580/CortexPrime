"""
Autonomous Trigger Runtime — continuously observes enterprise events, matches them
against configurable trigger policies, and auto-generates engineering missions.

Trigger Sources:
  GitHub, Azure DevOps, Jira, Slack, Teams, ServiceNow,
  Monitoring, Recommendations, Learning, Scheduler

Every generated mission executes through existing Mission Runtime and Delivery Orchestrator.
No duplicate orchestration, monitoring, or engineering logic.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.events.event_bus import event_bus
from backend.events.event_models import CognitionEvent

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_POLICIES_FILE = _DATA_DIR / "trigger_policies.json"
_HISTORY_FILE = _DATA_DIR / "trigger_history.json"

# ── Trigger event types ─────────────────────────────────────────────────────
TRIGGER_EVENT_DETECTED        = "trigger.detected"
TRIGGER_EVENT_POLICY_MATCHED  = "trigger.policy_matched"
TRIGGER_EVENT_MISSION_GENERATED = "trigger.mission_generated"
TRIGGER_EVENT_MISSION_STARTED = "trigger.mission_started"
TRIGGER_EVENT_MISSION_SUPPRESSED = "trigger.mission_suppressed"

# ── Trigger sources ─────────────────────────────────────────────────────────
TRIGGER_SOURCES = [
    "github", "azure_devops", "jira", "slack", "teams",
    "servicenow", "monitoring", "recommendations", "learning", "scheduler",
]

# ── Policy event type patterns ──────────────────────────────────────────────
SOURCE_EVENT_PATTERNS: Dict[str, List[str]] = {
    "github":          ["push", "pull_request", "issue", "workflow", "check_run", "commit_comment"],
    "azure_devops":    ["build.completed", "release.created", "workitem.updated", "git.push"],
    "jira":            ["issue_created", "issue_updated", "issue_deleted", "issue_resolved"],
    "slack":           ["message", "channel_created", "file_shared", "reaction_added"],
    "teams":           ["message", "channel_created", "meeting_started", "meeting_ended"],
    "servicenow":      ["incident", "change_request", "problem", "alert"],
    "monitoring":      ["monitoring.event_detected", "monitoring.rule_triggered", "watcher.alert"],
    "recommendations": ["recommendation.generated", "recommendation.executed"],
    "learning":        ["learning.lesson_discovered", "learning.pattern_updated"],
    "scheduler":       ["cron", "interval", "time_of_day", "day_of_week"],
}


def _load_json(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.error("Failed to load %s: %s", path.name, exc)
    return []


def _save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# =============================================================================
# Trigger Policy
# =============================================================================

class TriggerPolicy:
    """A configurable policy that defines when to auto-generate engineering missions."""

    def __init__(
        self,
        name: str,
        description: str = "",
        source: str = "",
        event_pattern: str = "",
        conditions: Optional[Dict[str, Any]] = None,
        mission_template: str = "software_release",
        requires_approval: bool = False,
        cooldown_seconds: int = 300,
        priority: str = "medium",
        enabled: bool = True,
        tags: Optional[List[str]] = None,
        policy_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.policy_id = policy_id or f"tp-{uuid.uuid4().hex[:12]}"
        self.name = name
        self.description = description
        self.source = source
        self.event_pattern = event_pattern
        self.conditions = conditions or {}
        self.mission_template = mission_template
        self.requires_approval = requires_approval
        self.cooldown_seconds = cooldown_seconds
        self.priority = priority
        self.enabled = enabled
        self.tags = tags or []
        self.created_at = created_at or now
        self.updated_at = now

    def matches(self, source: str, event_type: str, payload: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        if self.source and self.source != source:
            return False
        if self.event_pattern and self.event_pattern != event_type:
            if self.event_pattern in event_type:
                pass  # partial match allowed
            else:
                return False
        if self.conditions:
            for key, expected in self.conditions.items():
                actual = payload.get(key)
                if isinstance(expected, list):
                    if actual not in expected:
                        return False
                elif callable(expected):
                    if not expected(actual):
                        return False
                elif actual != expected:
                    return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "event_pattern": self.event_pattern,
            "conditions": self.conditions,
            "mission_template": self.mission_template,
            "requires_approval": self.requires_approval,
            "cooldown_seconds": self.cooldown_seconds,
            "priority": self.priority,
            "enabled": self.enabled,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> TriggerPolicy:
        return TriggerPolicy(
            name=data.get("name", ""),
            description=data.get("description", ""),
            source=data.get("source", ""),
            event_pattern=data.get("event_pattern", ""),
            conditions=data.get("conditions", {}),
            mission_template=data.get("mission_template", "software_release"),
            requires_approval=data.get("requires_approval", False),
            cooldown_seconds=data.get("cooldown_seconds", 300),
            priority=data.get("priority", "medium"),
            enabled=data.get("enabled", True),
            tags=data.get("tags", []),
            policy_id=data.get("policy_id"),
            created_at=data.get("created_at"),
        )


# =============================================================================
# Trigger History Entry
# =============================================================================

class TriggerHistoryEntry:
    """A record of a trigger event and its outcome."""

    def __init__(
        self,
        source: str,
        event_type: str,
        policy_id: str,
        policy_name: str,
        matched: bool,
        mission_id: str = "",
        status: str = "detected",
        payload: Optional[Dict[str, Any]] = None,
        error: str = "",
    ) -> None:
        self.entry_id = f"th-{uuid.uuid4().hex[:12]}"
        self.source = source
        self.event_type = event_type
        self.policy_id = policy_id
        self.policy_name = policy_name
        self.matched = matched
        self.mission_id = mission_id
        self.status = status
        self.payload = payload or {}
        self.error = error
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "source": self.source,
            "event_type": self.event_type,
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "matched": self.matched,
            "mission_id": self.mission_id,
            "status": self.status,
            "payload": self.payload,
            "error": self.error,
            "timestamp": self.timestamp,
        }


# =============================================================================
# Autonomous Trigger Runtime
# =============================================================================

class AutonomousTriggerRuntime:
    """
    Continuously observes enterprise events, matches against trigger policies,
    and auto-generates engineering missions through the existing Mission Runtime
    and Delivery Orchestrator.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._policies: Dict[str, TriggerPolicy] = {}
        self._history: List[TriggerHistoryEntry] = []
        self._cooldowns: Dict[str, float] = {}
        self._load_persisted()

    # ── Lifecycle ───────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        if self._initialized:
            return
        event_bus.subscribe(self._on_event)
        self._initialized = True
        log.info("AutonomousTriggerRuntime initialized — subscribed to EventBus")

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        log.info("AutonomousTriggerRuntime started — scheduler loop active")

    async def shutdown(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._persist_history()
        self._persist_policies()
        log.info("AutonomousTriggerRuntime shutdown")

    # ── Event Handler ───────────────────────────────────────────────────────

    async def _on_event(self, event: CognitionEvent) -> None:
        if not self._running:
            return
        event_type = event.event_type or ""
        payload = event.payload or {}

        source = self._classify_source(event_type, payload)
        if not source:
            return

        await self._process_event(source, event_type, payload | {"agent": event.agent, "message": event.message})

    def _classify_source(self, event_type: str, payload: Dict[str, Any]) -> Optional[str]:
        if event_type.startswith("monitoring.") or payload.get("source") == "monitoring":
            return "monitoring"
        if event_type.startswith("recommendation."):
            return "recommendations"
        if event_type.startswith("learning."):
            return "learning"
        if event_type.startswith("engineering.") or event_type.startswith("build."):
            return "github"
        if event_type.startswith("deploy."):
            return "azure_devops"
        if event_type.startswith("workspace.") or event_type.startswith("patch."):
            return "github"
        connector = payload.get("connector_type", payload.get("connector", "")).lower()
        source_map: Dict[str, str] = {
            "github": "github", "azure_devops": "azure_devops", "jira": "jira",
            "slack": "slack", "teams": "teams", "servicenow": "servicenow",
        }
        for key, val in source_map.items():
            if key in connector:
                return val
        return None

    async def _process_event(self, source: str, event_type: str, payload: Dict[str, Any]) -> None:
        matched_any = False
        for policy in self._policies.values():
            if not policy.matches(source, event_type, payload):
                continue

            matched_any = True
            cooldown_key = f"{policy.policy_id}:{payload.get('id', payload.get('execution_id', 'global'))}"
            now = datetime.now(timezone.utc).timestamp()
            last = self._cooldowns.get(cooldown_key, 0)
            if now - last < policy.cooldown_seconds:
                continue
            self._cooldowns[cooldown_key] = now

            await self._emit(TRIGGER_EVENT_POLICY_MATCHED, source, event_type, policy.to_dict(), payload)

            try:
                await self._generate_mission(source, event_type, policy, payload)
            except Exception as exc:
                log.error("Mission generation failed for policy '%s': %s", policy.name, exc)
                entry = TriggerHistoryEntry(
                    source=source, event_type=event_type,
                    policy_id=policy.policy_id, policy_name=policy.name,
                    matched=True, status="failed", payload=payload, error=str(exc),
                )
                self._history.append(entry)
                self._persist_history()

        if not matched_any:
            entry = TriggerHistoryEntry(
                source=source, event_type=event_type,
                policy_id="", policy_name="",
                matched=False, status="discarded", payload=payload,
            )
            self._history.append(entry)
            if len(self._history) > 1000:
                self._history = self._history[-1000:]

    # ── Mission Generator ───────────────────────────────────────────────────

    async def _generate_mission(
        self,
        source: str,
        event_type: str,
        policy: TriggerPolicy,
        payload: Dict[str, Any],
    ) -> None:
        await self._emit(TRIGGER_EVENT_MISSION_GENERATED, source, event_type, policy.to_dict(), payload)

        # 0. Run Engineering Decision Engine — THINK before ACT
        decision_report = None
        try:
            from backend.services.engineering_decision_engine import engineering_decision_engine
            repo_url = payload.get("repository", payload.get("repo_url", ""))
            branch = payload.get("branch", payload.get("ref", "main"))
            if branch.startswith("refs/heads/"):
                branch = branch[len("refs/heads/"):]
            commit_sha = payload.get("after", payload.get("commit_sha", ""))
            decision_report = await engineering_decision_engine.analyze(
                source=source,
                event_type=event_type,
                payload=payload,
                repository=repo_url,
                branch=branch,
                commit_sha=commit_sha,
            )
            log.info(
                "Decision: risk=%s score=%.0f plan=%s deploy=%s",
                decision_report.risk_assessment.level.value,
                decision_report.risk_assessment.score,
                decision_report.execution_plan.reasoning,
                decision_report.deployment_strategy.strategy.value,
            )
        except Exception as exc:
            log.warning("Engineering decision engine failed (non-fatal): %s", exc)

        # 1. Create workspace
        repo_url = payload.get("repository", payload.get("repo_url", ""))
        workspace_id = ""
        try:
            from backend.services.enterprise_workspace_engine import workspace_manager
            ws = await workspace_manager.create(
                name=f"auto-{policy.name}-{uuid.uuid4().hex[:8]}",
                repo_url=repo_url,
            )
            workspace_id = ws.id
        except Exception as exc:
            log.warning("Workspace creation failed (non-fatal): %s", exc)

        # 2. Extract branch from payload
        branch = payload.get("branch", payload.get("ref", "main"))
        if branch.startswith("refs/heads/"):
            branch = branch[len("refs/heads/"):]

        # 3. Start full delivery pipeline via Delivery Orchestrator
        delivery_id = ""
        try:
            from backend.services.enterprise_delivery_orchestrator import delivery_orchestrator

            delivery = await delivery_orchestrator.create_delivery(
                mission=f"[Auto] {policy.name}: {payload.get('title', payload.get('message', event_type))}",
                repository=repo_url,
                workspace=workspace_id,
            )
            # Attach decision report to blueprint
            bp_updates = {
                "branch": branch,
                "artifacts": [{
                    "stage": "trigger_pipeline",
                    "type": "github_push",
                    "source": source,
                    "event_type": event_type,
                    "payload_keys": list(payload.keys()),
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                }],
            }
            if decision_report:
                bp_updates["decision_report"] = decision_report.to_dict()
                bp_updates["risk_assessment"] = {
                    "score": decision_report.risk_assessment.score,
                    "level": decision_report.risk_assessment.level.value,
                    "reasoning": decision_report.risk_assessment.reasoning,
                    "factors": decision_report.risk_assessment.factors,
                }
                bp_updates["execution_plan"] = {
                    "reasoning": decision_report.execution_plan.reasoning,
                    "required_stages": decision_report.execution_plan.required_stages,
                    "skipped_stages": decision_report.execution_plan.skipped_stages,
                }
                bp_updates["deployment_strategy"] = decision_report.deployment_strategy.strategy.value
                bp_updates["approval_required"] = decision_report.approval_requirements.approval_required
                bp_updates["required_approvers"] = [a.value for a in decision_report.approval_requirements.required_approvers]

            await delivery_orchestrator.update_blueprint(delivery["delivery_id"], bp_updates)
            delivery_id = delivery["delivery_id"]

            # Attach learning context
            try:
                from backend.services.enterprise_learning_service import enterprise_learning
                lessons = await enterprise_learning.get_lessons(limit=5)
                learning_ctx = [{"lesson_id": lesson.get("id", ""), "content": lesson.get("content", "")[:200]} for lesson in lessons[:3]]
                await delivery_orchestrator.update_blueprint(delivery_id, {
                    "learning_references": learning_ctx,
                })
            except Exception as exc:
                log.debug("Learning context attach failed: %s", exc)

            # Attach recommendation references
            try:
                from backend.services.enterprise_recommendation_engine import enterprise_recommendation_engine
                recs = enterprise_recommendation_engine.get_active(limit=3)
                rec_refs = [{"rec_id": r.get("id", ""), "title": r.get("title", "")[:200]} for r in recs[:3]]
                await delivery_orchestrator.update_blueprint(delivery_id, {
                    "recommendation_references": rec_refs,
                })
            except Exception as exc:
                log.debug("Recommendation attach failed: %s", exc)

            # Start delivery
            await delivery_orchestrator.start_delivery(delivery_id)

        except Exception as exc:
            log.error("Delivery creation failed for triggered mission: %s", exc)
            await self._emit(TRIGGER_EVENT_MISSION_SUPPRESSED, source, event_type, policy.to_dict(),
                             payload | {"error": str(exc)})
            entry = TriggerHistoryEntry(
                source=source, event_type=event_type,
                policy_id=policy.policy_id, policy_name=policy.name,
                matched=True, status="suppressed", payload=payload, error=str(exc),
            )
            self._history.append(entry)
            self._persist_history()
            return

        # 3. Record history
        entry = TriggerHistoryEntry(
            source=source, event_type=event_type,
            policy_id=policy.policy_id, policy_name=policy.name,
            matched=True, status="mission_created",
            mission_id=delivery_id, payload=payload,
        )
        self._history.append(entry)
        if len(self._history) > 1000:
            self._history = self._history[-1000:]
        self._persist_history()

        await self._emit(TRIGGER_EVENT_MISSION_STARTED, source, event_type, policy.to_dict(),
                         payload | {"delivery_id": delivery_id})
        log.info("Auto mission created: policy=%s delivery=%s", policy.name, delivery_id)

    # ── Scheduler Loop ──────────────────────────────────────────────────────

    async def _scheduler_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(60)
                # Emit scheduler heartbeat for time-based policies
                now = datetime.now(timezone.utc)
                for policy in self._policies.values():
                    if policy.source == "scheduler" and policy.enabled:
                        if policy.event_pattern in ("cron", "interval"):
                            await self._process_event(
                                "scheduler", policy.event_pattern,
                                {"timestamp": now.isoformat(), "source": "scheduler"},
                            )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.warning("Scheduler loop error: %s", exc)

    # ── Policy CRUD ─────────────────────────────────────────────────────────

    async def create_policy(self, policy: TriggerPolicy) -> TriggerPolicy:
        if policy.policy_id in self._policies:
            raise ValueError(f"Policy already exists: {policy.policy_id}")
        self._policies[policy.policy_id] = policy
        self._persist_policies()
        log.info("Trigger policy created: %s (%s)", policy.name, policy.policy_id)
        return policy

    async def get_policy(self, policy_id: str) -> Optional[TriggerPolicy]:
        return self._policies.get(policy_id)

    async def list_policies(self, source: str = "", enabled: Optional[bool] = None) -> List[Dict[str, Any]]:
        policies = list(self._policies.values())
        if source:
            policies = [p for p in policies if p.source == source]
        if enabled is not None:
            policies = [p for p in policies if p.enabled == enabled]
        return [p.to_dict() for p in sorted(policies, key=lambda p: p.created_at, reverse=True)]

    async def update_policy(self, policy_id: str, updates: Dict[str, Any]) -> Optional[TriggerPolicy]:
        policy = self._policies.get(policy_id)
        if not policy:
            return None
        for key, val in updates.items():
            if hasattr(policy, key) and key not in ("policy_id", "created_at"):
                setattr(policy, key, val)
        policy.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist_policies()
        return policy

    async def delete_policy(self, policy_id: str) -> bool:
        policy = self._policies.pop(policy_id, None)
        if not policy:
            return False
        self._persist_policies()
        return True

    # ── History ─────────────────────────────────────────────────────────────

    async def get_history(
        self,
        source: str = "",
        status: str = "",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        entries = list(self._history)
        if source:
            entries = [e for e in entries if e.source == source]
        if status:
            entries = [e for e in entries if e.status == status]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return [e.to_dict() for e in entries[:limit]]

    # ── Simulate ────────────────────────────────────────────────────────────

    async def simulate(self, source: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        matched_policies = []
        for policy in self._policies.values():
            if policy.matches(source, event_type, payload):
                matched_policies.append(policy.to_dict())
        return {
            "source": source,
            "event_type": event_type,
            "matched_policies": len(matched_policies),
            "policies": matched_policies,
            "simulated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Dashboard ───────────────────────────────────────────────────────────

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        total_policies = len(self._policies)
        enabled_policies = sum(1 for p in self._policies.values() if p.enabled)
        total_entries = len(self._history)
        missions_created = sum(1 for e in self._history if e.status == "mission_created")
        suppressed = sum(1 for e in self._history if e.status == "suppressed")
        failed = sum(1 for e in self._history if e.status == "failed")
        discarded = sum(1 for e in self._history if e.status == "discarded")

        by_source: Dict[str, int] = {}
        for e in self._history:
            by_source[e.source] = by_source.get(e.source, 0) + 1

        return {
            "total_policies": total_policies,
            "enabled_policies": enabled_policies,
            "total_trigger_events": total_entries,
            "missions_created": missions_created,
            "missions_suppressed": suppressed,
            "mission_failures": failed,
            "events_discarded": discarded,
            "by_source": by_source,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Events ──────────────────────────────────────────────────────────────

    async def _emit(self, event_type: str, source: str, event_type_detail: str,
                     policy: Dict[str, Any], payload: Dict[str, Any]) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=event_type,
                agent="autonomous_trigger_runtime",
                status="info",
                message=f"Trigger: {source}/{event_type_detail}",
                execution_id=policy.get("policy_id", ""),
                metadata={
                    "source": source,
                    "event_type_detail": event_type_detail,
                    "policy": policy,
                    "payload": payload,
                },
            )
        except Exception as exc:
            log.debug("Trigger event emit failed: %s", exc)

    # ── Persistence ─────────────────────────────────────────────────────────

    def _persist_policies(self) -> None:
        try:
            _save_json(_POLICIES_FILE, [p.to_dict() for p in self._policies.values()])
        except Exception as exc:
            log.warning("Policy persistence failed: %s", exc)

    def _persist_history(self) -> None:
        try:
            _save_json(_HISTORY_FILE, [e.to_dict() for e in self._history[-500:]])
        except Exception as exc:
            log.warning("History persistence failed: %s", exc)

    def _load_persisted(self) -> None:
        try:
            for item in _load_json(_POLICIES_FILE):
                policy = TriggerPolicy.from_dict(item)
                self._policies[policy.policy_id] = policy

            for item in _load_json(_HISTORY_FILE):
                entry = TriggerHistoryEntry(
                    source=item.get("source", ""),
                    event_type=item.get("event_type", ""),
                    policy_id=item.get("policy_id", ""),
                    policy_name=item.get("policy_name", ""),
                    matched=item.get("matched", False),
                    mission_id=item.get("mission_id", ""),
                    status=item.get("status", "detected"),
                    payload=item.get("payload", {}),
                    error=item.get("error", ""),
                )
                entry.entry_id = item.get("entry_id", entry.entry_id)
                entry.timestamp = item.get("timestamp", entry.timestamp)
                self._history.append(entry)

            log.info("Loaded %d policies, %d history entries", len(self._policies), len(self._history))
        except Exception as exc:
            log.warning("Trigger load failed: %s", exc)

    # ── Default seed policies ───────────────────────────────────────────────

    async def seed_default_policies(self) -> int:
        defaults = [
            TriggerPolicy(
                name="GitHub Push to Main",
                description="Auto-build on push to main branch",
                source="github",
                event_pattern="push",
                conditions={"ref": "refs/heads/main"},
                mission_template="software_release",
                priority="high",
            ),
            TriggerPolicy(
                name="Jira P1 Issue Created",
                description="Auto-create incident response for P1 issues",
                source="jira",
                event_pattern="issue_created",
                conditions={"priority": "P1"},
                mission_template="incident_response",
                requires_approval=True,
                priority="critical",
            ),
            TriggerPolicy(
                name="Slack #incidents Alert",
                description="Respond to messages in #incidents channel",
                source="slack",
                event_pattern="message",
                conditions={"channel": "#incidents"},
                mission_template="incident_response",
                priority="high",
            ),
            TriggerPolicy(
                name="Monitoring CPU Alert",
                description="Create mission when CPU exceeds 90%",
                source="monitoring",
                event_pattern="monitoring.event_detected",
                conditions={"metric": "cpu_usage", "severity": "high"},
                mission_template="incident_response",
                priority="high",
            ),
            TriggerPolicy(
                name="Recommendation Generated",
                description="Auto-create engineering task from recommendations",
                source="recommendations",
                event_pattern="recommendation.generated",
                conditions={"priority": "critical"},
                mission_template="incident_response",
                priority="medium",
            ),
            TriggerPolicy(
                name="Learning Pattern Detected",
                description="Create learning mission from new failure patterns",
                source="learning",
                event_pattern="learning.pattern_updated",
                mission_template="incident_response",
                priority="low",
            ),
            TriggerPolicy(
                name="Hourly Health Check",
                description="Scheduled health check every hour",
                source="scheduler",
                event_pattern="interval",
                mission_template="incident_response",
                priority="low",
            ),
            TriggerPolicy(
                name="ServiceNow P1 Incident",
                description="Auto-create mission for P1 ServiceNow incidents",
                source="servicenow",
                event_pattern="incident",
                conditions={"priority": "1"},
                mission_template="incident_response",
                requires_approval=True,
                priority="critical",
            ),
            TriggerPolicy(
                name="Azure DevOps Build Failure",
                description="Auto-create bug fix mission on build failure",
                source="azure_devops",
                event_pattern="build.completed",
                conditions={"result": "failed"},
                mission_template="bug_triage",
                priority="high",
            ),
            TriggerPolicy(
                name="Teams Alert Channel",
                description="Respond to critical messages in Teams alert channel",
                source="teams",
                event_pattern="message",
                conditions={"channel": "alerts"},
                mission_template="incident_response",
                priority="high",
            ),
        ]
        count = 0
        for policy in defaults:
            if policy.policy_id not in self._policies:
                self._policies[policy.policy_id] = policy
                count += 1
        if count > 0:
            self._persist_policies()
            log.info("Seeded %d default trigger policies", count)
        return count


# =============================================================================
# Singleton
# =============================================================================

autonomous_trigger_runtime = AutonomousTriggerRuntime()
