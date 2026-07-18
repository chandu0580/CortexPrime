"""
Enterprise Continuous Cognition Runtime — CortexPrime's always-on engineering
reasoning loop.

This is NOT an AI engine.
This is NOT a Decision Engine.
This is NOT a Context Intelligence.
This is NOT a Repository Brain.

This is a cognition runtime that continuously observes, reasons, updates, and
maintains the engineering state even when no user is interacting.

Reuses (never duplicates):
  - Repository Brain           - Executive Runtime
  - Context Intelligence       - Engineering Decision Engine
  - Predictive Simulation      - Verification Intelligence
  - Engineering Memory         - RuntimeStore
  - ReplayStore                - Knowledge Graph
  - EventHub                   - Infrastructure Intelligence
  - GitHub Integration         - ArgoCD Intelligence
  - Prometheus Intelligence    - Loki Intelligence
  - OpenTelemetry Intelligence - Learning Engine
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_COGNITION_FILE = _DATA_DIR / "cognition_timeline.json"
_COGNITION_STATE_FILE = _DATA_DIR / "cognition_runtime_state.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str = "cog") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.debug("Failed to load %s: %s", path.name, exc)
    return {}


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# =============================================================================
# Phase 1 — Cognition Loop State
# =============================================================================


class CognitionLoopState(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class CognitionPhase(Enum):
    IDLE = "idle"
    REPOSITORY_MONITORING = "repository_monitoring"
    CONTEXT_REFRESH = "context_refresh"
    RISK_RE_EVALUATION = "risk_re_evaluation"
    PREDICTION_REFRESH = "prediction_refresh"
    INFRASTRUCTURE_AWARENESS = "infrastructure_awareness"
    KNOWLEDGE_EVOLUTION = "knowledge_evolution"
    EXECUTIVE_NOTIFICATION = "executive_notification"


# =============================================================================
# Phase 9 — Cognition Timeline Entry
# =============================================================================


@dataclass(frozen=True)
class CognitionTimelineEntry:
    entry_id: str = ""
    timestamp: str = ""
    phase: str = ""
    change_type: str = ""
    reason: str = ""
    affected_repositories: List[str] = field(default_factory=list)
    affected_services: List[str] = field(default_factory=list)
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    triggered_actions: List[str] = field(default_factory=list)
    risk_before: Optional[float] = None
    risk_after: Optional[float] = None
    prediction_id: Optional[str] = None
    mission_id: Optional[str] = None


# =============================================================================
# Continuous Engineering Cognition Runtime
# =============================================================================


class EnterpriseContinuousCognitionRuntime:
    """
    Always-on engineering reasoning loop.

    Phases:
      1. Cognition Scheduler — periodic evaluation
      2. Repository Monitoring — detect changes via Repository Brain
      3. Context Refresh — refresh Context Intelligence on meaningful changes
      4. Risk Re-evaluation — rerun Decision Engine for affected items
      5. Prediction Refresh — refresh predictions via Predictive Simulation
      6. Infrastructure Awareness — monitor K8s, ArgoCD, Prometheus, Loki, OTel
      7. Knowledge Evolution — update KG, Memory, Learning Engine, Stores
      8. Executive Awareness — notify Executive Runtime on risk/health changes
      9. Cognition Timeline — persist history of all observations
    """

    def __init__(
        self,
        loop_interval_seconds: int = 60,
        repo_check_interval_seconds: int = 300,
        infra_check_interval_seconds: int = 120,
    ):
        self._loop_interval = max(10, loop_interval_seconds)
        self._repo_interval = max(30, repo_check_interval_seconds)
        self._infra_interval = max(30, infra_check_interval_seconds)

        self._state: CognitionLoopState = CognitionLoopState.STOPPED
        self._current_phase: CognitionPhase = CognitionPhase.IDLE
        self._task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        self._known_repositories: Set[str] = set()
        self._known_services: Set[str] = set()
        self._previous_risk_scores: Dict[str, float] = {}
        self._previous_architectures: Dict[str, Dict[str, Any]] = {}
        self._infra_health_baseline: Dict[str, str] = {}

        self._timeline: List[CognitionTimelineEntry] = []
        self._loop_count: int = 0
        self._started_at: str = ""
        self._last_repo_check: str = ""
        self._last_infra_check: str = ""

        self._load_state()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        data = _load_json(_COGNITION_STATE_FILE)
        self._known_repositories = set(data.get("known_repositories", []))
        self._known_services = set(data.get("known_services", []))
        self._previous_risk_scores = data.get("previous_risk_scores", {})
        self._previous_architectures = data.get("previous_architectures", {})
        self._infra_health_baseline = data.get("infra_health_baseline", {})
        self._timeline = [
            CognitionTimelineEntry(**e)
            for e in data.get("timeline", [])
        ]
        log.info("Loaded cognition state: %d repos, %d timeline entries",
                 len(self._known_repositories), len(self._timeline))

    def _save_state(self) -> None:
        _save_json(_COGNITION_STATE_FILE, {
            "known_repositories": list(self._known_repositories),
            "known_services": list(self._known_services),
            "previous_risk_scores": self._previous_risk_scores,
            "previous_architectures": self._previous_architectures,
            "infra_health_baseline": self._infra_health_baseline,
            "timeline": [asdict(e) for e in self._timeline[-200:]],  # keep last 200
            "loop_count": self._loop_count,
            "started_at": self._started_at,
            "state": self._state.value,
            "last_repo_check": self._last_repo_check,
            "last_infra_check": self._last_infra_check,
        })

    async def start(self) -> None:
        if self._state == CognitionLoopState.RUNNING:
            log.warning("Cognition runtime already running")
            return
        self._state = CognitionLoopState.RUNNING
        self._started_at = _now()
        self._shutdown_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        log.info("Enterprise Continuous Cognition Runtime started (interval=%ds, repo=%ds, infra=%ds)",
                 self._loop_interval, self._repo_interval, self._infra_interval)

    async def stop(self) -> None:
        if self._state != CognitionLoopState.RUNNING:
            return
        self._state = CognitionLoopState.STOPPED
        self._shutdown_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._save_state()
        log.info("Enterprise Continuous Cognition Runtime stopped")

    async def pause(self) -> None:
        if self._state == CognitionLoopState.RUNNING:
            self._state = CognitionLoopState.PAUSED
            log.info("Cognition runtime paused")

    async def resume(self) -> None:
        if self._state == CognitionLoopState.PAUSED:
            self._state = CognitionLoopState.RUNNING
            log.info("Cognition runtime resumed")

    @property
    def is_running(self) -> bool:
        return self._state == CognitionLoopState.RUNNING

    # ------------------------------------------------------------------
    # Phase 1 — Main Cognition Loop
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        loop_cycles = 0
        while not self._shutdown_event.is_set():
            try:
                self._loop_count += 1
                loop_cycles += 1
                await self._cognition_cycle()

                # Wait for next interval or shutdown
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self._loop_interval,
                    )
                    break  # shutdown requested
                except asyncio.TimeoutError:
                    pass  # normal cycle wait

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._state = CognitionLoopState.ERROR
                log.error("Cognition cycle failed: %s", exc, exc_info=True)
                # Brief backoff before retry
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=min(self._loop_interval * 2, 300),
                    )
                    break
                except asyncio.TimeoutError:
                    self._state = CognitionLoopState.RUNNING
                    continue

    async def _cognition_cycle(self) -> None:
        """Execute one full cognition cycle (Phases 2-8)."""

        # Phase 2 — Repository Monitoring (periodic)
        now = _now()
        if self._last_repo_check:
            elapsed = (
                datetime.fromisoformat(now) -
                datetime.fromisoformat(self._last_repo_check)
            ).total_seconds()
        else:
            elapsed = self._repo_interval + 1

        if elapsed >= self._repo_interval:
            self._current_phase = CognitionPhase.REPOSITORY_MONITORING
            await self._monitor_repositories()
            self._last_repo_check = now

        # Phase 5 — Infrastructure Awareness (periodic)
        if self._last_infra_check:
            elapsed = (
                datetime.fromisoformat(now) -
                datetime.fromisoformat(self._last_infra_check)
            ).total_seconds()
        else:
            elapsed = self._infra_interval + 1

        if elapsed >= self._infra_interval:
            self._current_phase = CognitionPhase.INFRASTRUCTURE_AWARENESS
            await self._check_infrastructure()
            self._last_infra_check = now

        # Phase 4 — Risk Re-evaluation (always runs if repos changed)
        if self._repos_changed_since_last_cycle():
            self._current_phase = CognitionPhase.RISK_RE_EVALUATION
            await self._reevaluate_risk()

        self._current_phase = CognitionPhase.IDLE
        self._save_state()

    def _repos_changed_since_last_cycle(self) -> bool:
        """Check if any tracked repository had changes detected."""
        from backend.services.enterprise_repository_brain import repository_brain
        try:
            dashboard = repository_brain.get_dashboard()
            current_repos = set()
            for repo_data in dashboard.get("repositories", []):
                repo_name = repo_data.get("repository", "")
                if repo_name:
                    current_repos.add(repo_name)
            if not current_repos:
                return False
            if current_repos != self._known_repositories:
                return True
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Phase 2 — Repository Monitoring
    # ------------------------------------------------------------------

    async def _monitor_repositories(self) -> None:
        """Detect changes in tracked repositories via Repository Brain."""
        from backend.services.enterprise_repository_brain import repository_brain

        try:
            dashboard = repository_brain.get_dashboard()
            repositories = dashboard.get("repositories", [])
            current_repos = set()

            for repo_data in repositories:
                repo_name = repo_data.get("repository", "")
                if not repo_name:
                    continue
                current_repos.add(repo_name)

                is_new = repo_name not in self._known_repositories
                self._known_repositories.add(repo_name)

                # Check for architecture drift
                drift = repository_brain.detect_drift(repo_name)
                if drift:
                    await self._on_drift_detected(repo_name, drift)

                # Check for ownership changes
                ownership = repository_brain.refresh_ownership(repo_name)
                if ownership and is_new:
                    await self._on_ownership_changed(repo_name, ownership)

                # Check for dependency changes via architecture
                arch = repository_brain.refresh_architecture(repo_name)
                if arch:
                    prev_arch = self._previous_architectures.get(repo_name, {})
                    if prev_arch and self._architecture_changed(prev_arch, arch):
                        await self._on_architecture_changed(repo_name, prev_arch, arch)
                    self._previous_architectures[repo_name] = arch

                if is_new:
                    await self._on_new_repository(repo_name, repo_data)

            # Detect deleted repositories
            deleted = self._known_repositories - current_repos
            for repo_name in deleted:
                await self._on_repository_deleted(repo_name)
                self._known_repositories.discard(repo_name)

        except Exception as exc:
            log.warning("Repository monitoring failed: %s", exc)

    def _architecture_changed(
        self,
        prev: Dict[str, Any],
        curr: Dict[str, Any],
    ) -> bool:
        """Compare two architecture snapshots for meaningful changes."""
        prev_services = set(prev.get("services", []))
        curr_services = set(curr.get("services", []))
        if prev_services != curr_services:
            return True
        prev_libs = set(prev.get("libraries", []))
        curr_libs = set(curr.get("libraries", []))
        if prev_libs != curr_libs:
            return True
        return False

    async def _on_new_repository(
        self, repo_name: str, repo_data: Dict[str, Any]
    ) -> None:
        """Handle new repository discovery."""
        log.info("Cognition: new repository detected: %s", repo_name)
        self._append_timeline(
            change_type="repository_added",
            reason="New repository discovered during monitoring cycle",
            affected_repositories=[repo_name],
            new_state={"repository": repo_name, **repo_data},
            confidence=0.9,
            triggered_actions=["context_refresh", "risk_assessment"],
        )
        await self._refresh_context_for_repository(repo_name)
        await self._reevaluate_risk_for_repository(repo_name)

    async def _on_repository_deleted(self, repo_name: str) -> None:
        """Handle repository removal."""
        log.info("Cognition: repository removed: %s", repo_name)
        self._append_timeline(
            change_type="repository_removed",
            reason="Repository no longer tracked in Repository Brain",
            affected_repositories=[repo_name],
            previous_state={"repository": repo_name},
            confidence=0.95,
        )

    async def _on_drift_detected(
        self, repo_name: str, drift: Dict[str, Any]
    ) -> None:
        """Handle architecture drift detection."""
        log.info("Cognition: architecture drift in %s: %s", repo_name, drift)
        self._append_timeline(
            change_type="architecture_drift",
            reason=f"Architecture drift detected: {drift.get('description', 'unknown')}",
            affected_repositories=[repo_name],
            previous_state={"drift": drift.get("previous", {})},
            new_state={"drift": drift.get("current", {})},
            confidence=drift.get("confidence", 0.7),
            triggered_actions=["context_refresh", "risk_re_evaluation"],
        )
        await self._refresh_context_for_repository(repo_name)

    async def _on_ownership_changed(
        self, repo_name: str, ownership: Dict[str, Any]
    ) -> None:
        """Handle ownership changes."""
        log.info("Cognition: ownership changed in %s", repo_name)
        self._append_timeline(
            change_type="ownership_changed",
            reason="Repository ownership updated",
            affected_repositories=[repo_name],
            new_state={"ownership": ownership},
            confidence=0.9,
        )

    async def _on_architecture_changed(
        self,
        repo_name: str,
        prev_arch: Dict[str, Any],
        new_arch: Dict[str, Any],
    ) -> None:
        """Handle architecture changes."""
        log.info("Cognition: architecture changed in %s", repo_name)
        self._append_timeline(
            change_type="architecture_changed",
            reason="Repository architecture model updated",
            affected_repositories=[repo_name],
            previous_state={"architecture": prev_arch},
            new_state={"architecture": new_arch},
            confidence=0.85,
            triggered_actions=["context_refresh", "risk_re_evaluation", "prediction_refresh"],
        )
        await self._refresh_context_for_repository(repo_name)
        await self._reevaluate_risk_for_repository(repo_name)
        await self._refresh_predictions_for_repository(repo_name)

    # ------------------------------------------------------------------
    # Phase 3 — Context Refresh
    # ------------------------------------------------------------------

    async def _refresh_context_for_repository(self, repo_name: str) -> None:
        """Refresh Context Intelligence for a repository."""
        from backend.services.enterprise_context_intelligence import (
            enterprise_context_intelligence,
        )

        self._current_phase = CognitionPhase.CONTEXT_REFRESH
        try:
            snapshot = await enterprise_context_intelligence.build_snapshot(
                repository=repo_name,
            )
            log.debug("Context refreshed for %s", repo_name)
            self._append_timeline(
                change_type="context_refreshed",
                reason=f"Context snapshot refreshed for {repo_name}",
                affected_repositories=[repo_name],
                new_state={"context_execution_id": getattr(snapshot, 'execution_id', '')},
                confidence=0.8,
            )
        except Exception as exc:
            log.warning("Context refresh failed for %s: %s", repo_name, exc)

    # ------------------------------------------------------------------
    # Phase 4 — Risk Re-evaluation
    # ------------------------------------------------------------------

    async def _reevaluate_risk(self) -> None:
        """Re-evaluate risk for all tracked repositories."""
        for repo_name in list(self._known_repositories):
            await self._reevaluate_risk_for_repository(repo_name)

    async def _reevaluate_risk_for_repository(self, repo_name: str) -> None:
        """Run decision engine risk analysis for a single repository."""
        from backend.services.engineering_decision_engine import (
            EngineeringDecisionEngine,
        )

        self._current_phase = CognitionPhase.RISK_RE_EVALUATION
        try:
            engine = EngineeringDecisionEngine()
            report = await engine.analyze(
                source="cognition_runtime",
                event_type="continuous_monitoring",
                payload={},
                repository=repo_name,
            )

            if report and hasattr(report, 'risk_assessment'):
                risk = report.risk_assessment
                current_score = getattr(risk, 'score', 0) or 0
                prev_score = self._previous_risk_scores.get(repo_name, 0)

                if abs(current_score - prev_score) > 5:
                    log.info("Risk changed for %s: %.1f -> %.1f",
                             repo_name, prev_score, current_score)
                    self._append_timeline(
                        change_type="risk_changed",
                        reason=f"Risk score changed: {prev_score:.1f} -> {current_score:.1f}",
                        affected_repositories=[repo_name],
                        previous_state={"risk_score": prev_score},
                        new_state={"risk_score": current_score, "risk_level": getattr(risk, 'level', 'unknown')},
                        confidence=getattr(risk, 'confidence', 0.7),
                        triggered_actions=(
                            ["executive_notification"]
                            if current_score > 60 or current_score - prev_score > 20
                            else []
                        ),
                        risk_before=prev_score,
                        risk_after=current_score,
                    )

                    self._previous_risk_scores[repo_name] = current_score

                    # Phase 8 — Executive notification for high risk
                    if current_score > 60 or current_score - prev_score > 20:
                        await self._notify_executive(
                            reason=f"Risk {'increased' if current_score > prev_score else 'decreased'} "
                                   f"for {repo_name}: {prev_score:.1f} -> {current_score:.1f}",
                            affected_repositories=[repo_name],
                            risk_level=getattr(risk, 'level', 'unknown'),
                            risk_score=current_score,
                        )

        except Exception as exc:
            log.warning("Risk re-evaluation failed for %s: %s", repo_name, exc)

    # ------------------------------------------------------------------
    # Phase 5 — Prediction Refresh
    # ------------------------------------------------------------------

    async def _refresh_predictions_for_repository(self, repo_name: str) -> None:
        """Refresh predictions for a repository via Predictive Simulation."""
        from backend.services.enterprise_predictive_simulation import (
            enterprise_predictive_simulation,
        )

        self._current_phase = CognitionPhase.PREDICTION_REFRESH
        try:
            from backend.services.enterprise_context_intelligence import (
                enterprise_context_intelligence,
            )

            context = await enterprise_context_intelligence.build_snapshot(
                repository=repo_name,
            )
            prediction = await enterprise_predictive_simulation.simulate(
                context=context,
            )

            if prediction:
                pred_id = getattr(prediction, 'report_id', '') or _id("pred")
                log.debug("Prediction refreshed for %s: %s", repo_name, pred_id)
                self._append_timeline(
                    change_type="prediction_refreshed",
                    reason=f"Prediction updated for {repo_name}",
                    affected_repositories=[repo_name],
                    new_state={"prediction_id": pred_id},
                    confidence=getattr(prediction, 'confidence', 0.6),
                    prediction_id=pred_id,
                )
        except Exception as exc:
            log.warning("Prediction refresh failed for %s: %s", repo_name, exc)

    # ------------------------------------------------------------------
    # Phase 6 — Infrastructure Awareness
    # ------------------------------------------------------------------

    async def _check_infrastructure(self) -> None:
        """Monitor infrastructure health from all sources."""
        await self._check_kubernetes_health()
        await self._check_argocd_sync()
        await self._check_prometheus_alerts()
        await self._check_loki_errors()
        await self._check_opentelemetry_degradation()

    async def _check_kubernetes_health(self) -> None:
        """Check Kubernetes cluster health."""
        try:
            from backend.services.enterprise_infrastructure_intelligence import (
                infrastructure_intelligence,
            )

            health = await infrastructure_intelligence.get_cluster_health()
            if health:
                current_status = health.get("status", "unknown")
                prev_status = self._infra_health_baseline.get("kubernetes", "unknown")
                if current_status != prev_status and prev_status != "unknown":
                    log.info("Kubernetes health changed: %s -> %s", prev_status, current_status)
                    self._append_timeline(
                        change_type="kubernetes_health_changed",
                        reason=f"Kubernetes cluster health: {prev_status} -> {current_status}",
                        affected_services=["kubernetes"],
                        previous_state={"health": prev_status},
                        new_state={"health": current_status, **health},
                        confidence=0.9,
                        triggered_actions=(
                            ["executive_notification"]
                            if current_status in ("degraded", "unhealthy")
                            else []
                        ),
                    )
                    await self._notify_executive_if_degraded(
                        "kubernetes", current_status,
                        f"Kubernetes health degraded: {current_status}",
                    )
                self._infra_health_baseline["kubernetes"] = current_status
        except Exception as exc:
            log.debug("Kubernetes health check unavailable: %s", exc)

    async def _check_argocd_sync(self) -> None:
        """Check ArgoCD application sync status."""
        try:
            from backend.services.enterprise_argocd_intelligence import (
                argocd_intelligence,
            )
            apps = await argocd_intelligence.discover_all()
            if apps and "applications" in apps:
                unsynced = [
                    a for a in apps["applications"]
                    if a.get("sync_status") != "Synced"
                ]
                if unsynced:
                    app_names = [a.get("name", "unknown") for a in unsynced[:5]]
                    log.info("ArgoCD: %d unsynced applications", len(unsynced))
                    self._append_timeline(
                        change_type="argocd_sync_drift",
                        reason=f"{len(unsynced)} ArgoCD applications out of sync",
                        affected_services=app_names,
                        new_state={"unsynced_count": len(unsynced), "applications": unsynced[:10]},
                        confidence=0.85,
                        triggered_actions=["executive_notification"],
                    )
        except Exception as exc:
            log.debug("ArgoCD check unavailable: %s", exc)

    async def _check_prometheus_alerts(self) -> None:
        """Check Prometheus firing alerts."""
        try:
            from backend.services.enterprise_prometheus_intelligence import (
                alert_intelligence,
            )
            alerts = await alert_intelligence.get_alerts()
            firing = [
                a for a in (alerts or [])
                if a.get("state") == "firing" or a.get("status") == "firing"
            ]
            if firing:
                log.info("Prometheus: %d firing alerts", len(firing))
                self._append_timeline(
                    change_type="prometheus_alerts_firing",
                    reason=f"{len(firing)} Prometheus alerts firing",
                    affected_services=list(set(
                        a.get("labels", {}).get("service", "unknown")
                        for a in firing[:10]
                    )),
                    new_state={"firing_count": len(firing), "alerts": firing[:10]},
                    confidence=0.9,
                    triggered_actions=["executive_notification"],
                )
        except Exception as exc:
            log.debug("Prometheus check unavailable: %s", exc)

    async def _check_loki_errors(self) -> None:
        """Check Loki for error spikes."""
        try:
            from backend.services.enterprise_loki_intelligence import loki_intelligence
            errors = await loki_intelligence.check_recent_errors()
            if errors and len(errors) > 10:
                log.info("Loki: %d recent errors detected", len(errors))
                self._append_timeline(
                    change_type="loki_error_spike",
                    reason=f"{len(errors)} errors detected in recent logs",
                    new_state={"error_count": len(errors), "sample": errors[:5]},
                    confidence=0.8,
                    triggered_actions=["executive_notification"],
                )
        except Exception as exc:
            log.debug("Loki check unavailable: %s", exc)

    async def _check_opentelemetry_degradation(self) -> None:
        """Check OpenTelemetry for service degradation."""
        try:
            from backend.services.enterprise_trace_intelligence import (
                trace_intelligence,
            )
            graph = await trace_intelligence.get_service_graph()
            if graph and "services" in graph:
                degraded = [
                    s for s in graph["services"]
                    if s.get("health") in ("degraded", "unhealthy")
                ]
                if degraded:
                    svc_names = [s.get("name", "unknown") for s in degraded]
                    log.info("OpenTelemetry: %d degraded services", len(degraded))
                    self._append_timeline(
                        change_type="otel_service_degradation",
                        reason=f"{len(degraded)} services degraded",
                        affected_services=svc_names,
                        new_state={"degraded_count": len(degraded), "services": degraded[:10]},
                        confidence=0.85,
                        triggered_actions=["executive_notification"],
                    )
        except Exception as exc:
            log.debug("OpenTelemetry check unavailable: %s", exc)

    async def _notify_executive_if_degraded(
        self, component: str, status: str, reason: str
    ) -> None:
        """Notify executive runtime if infrastructure degrades."""
        if status in ("degraded", "unhealthy"):
            await self._notify_executive(
                reason=reason,
                affected_services=[component],
                risk_level="high",
                risk_score=70.0,
            )

    # ------------------------------------------------------------------
    # Phase 7 — Knowledge Evolution
    # ------------------------------------------------------------------

    async def _evolve_knowledge(self, entry: CognitionTimelineEntry) -> None:
        """Update knowledge stores when significant state changes occur."""
        self._current_phase = CognitionPhase.KNOWLEDGE_EVOLUTION

        try:
            # Update Knowledge Graph
            await self._update_knowledge_graph(entry)
        except Exception as exc:
            log.debug("Knowledge graph update skipped: %s", exc)

        try:
            # Update Engineering Memory
            await self._update_engineering_memory(entry)
        except Exception as exc:
            log.debug("Engineering memory update skipped: %s", exc)

        try:
            # Update Learning Engine
            await self._update_learning_engine(entry)
        except Exception as exc:
            log.debug("Learning engine update skipped: %s", exc)

        # Phase 8 — Executive Notification (for risky changes)
        if entry.risk_after and (entry.risk_after > 60 or
                                 (entry.risk_before and entry.risk_after - entry.risk_before > 20)):
            try:
                await self._notify_executive(
                    reason=entry.reason,
                    affected_repositories=entry.affected_repositories,
                    affected_services=entry.affected_services,
                    risk_level="high" if entry.risk_after > 70 else "medium",
                    risk_score=entry.risk_after,
                )
            except Exception as exc:
                log.debug("Executive notification skipped: %s", exc)

    async def _update_knowledge_graph(self, entry: CognitionTimelineEntry) -> None:
        """Record cognition event in Knowledge Graph."""
        from backend.services.enterprise_graph_service import enterprise_graph

        await enterprise_graph.record_decision(
            decision_id=entry.entry_id,
            execution_id=entry.entry_id,
            decision_type=f"cognition_{entry.change_type}",
            reasoning=entry.reason,
            confidence=entry.confidence,
            metadata={
                "phase": entry.phase,
                "change_type": entry.change_type,
                "affected_repositories": entry.affected_repositories,
                "affected_services": entry.affected_services,
                "risk_before": entry.risk_before,
                "risk_after": entry.risk_after,
                "timestamp": entry.timestamp,
            },
        )

    async def _update_engineering_memory(self, entry: CognitionTimelineEntry) -> None:
        """Record cognition observation in Engineering Memory."""
        from backend.services.enterprise_engineering_memory import (
            enterprise_engineering_memory,
        )

        await enterprise_engineering_memory.build_experience(
            execution_id=entry.entry_id,
        )

    async def _update_learning_engine(self, entry: CognitionTimelineEntry) -> None:
        """Feed cognition observations to Learning Engine."""
        from backend.events.event_bus import event_bus
        from backend.events.event_models import CognitionEvent

        await event_bus.publish(
            CognitionEvent(
                agent="cognition_runtime",
                event_type=f"cognition.{entry.change_type}",
                status="completed",
                phase="continuous_cognition",
                execution_id=entry.entry_id,
                message=entry.reason,
                payload={
                    "change_type": entry.change_type,
                    "affected_repositories": entry.affected_repositories,
                    "affected_services": entry.affected_services,
                    "risk_before": entry.risk_before,
                    "risk_after": entry.risk_after,
                    "confidence": entry.confidence,
                    "timestamp": entry.timestamp,
                },
            )
        )

    # ------------------------------------------------------------------
    # Phase 8 — Executive Awareness
    # ------------------------------------------------------------------

    async def _notify_executive(
        self,
        reason: str,
        affected_repositories: Optional[List[str]] = None,
        affected_services: Optional[List[str]] = None,
        risk_level: str = "medium",
        risk_score: float = 50.0,
    ) -> None:
        """Notify Enterprise Executive Runtime of significant changes."""
        from backend.services.enterprise_executive_runtime import (
            EnterpriseEngineeringExecutiveRuntime,
        )

        self._current_phase = CognitionPhase.EXECUTIVE_NOTIFICATION
        try:
            executive = EnterpriseEngineeringExecutiveRuntime()
            mission = await executive.create_mission(
                source="cognition_runtime",
                source_event=f"cognition.{risk_level}_risk",
                payload={
                    "reason": reason,
                    "affected_repositories": affected_repositories or [],
                    "affected_services": affected_services or [],
                    "risk_level": risk_level,
                    "risk_score": risk_score,
                    "auto_created": True,
                },
            )
            if mission:
                mission_id = getattr(mission, 'mission_id', '') or _id("mission")
                log.info("Executive mission created: %s — %s", mission_id, reason)
                self._append_timeline(
                    change_type="executive_mission_created",
                    reason=f"Executive mission created: {reason}",
                    affected_repositories=affected_repositories or [],
                    affected_services=affected_services or [],
                    new_state={"mission_id": mission_id, "risk_level": risk_level},
                    confidence=0.9,
                    mission_id=mission_id,
                )
        except Exception as exc:
            log.warning("Executive notification failed: %s", exc)

    # ------------------------------------------------------------------
    # Phase 9 — Cognition Timeline
    # ------------------------------------------------------------------

    def _append_timeline(
        self,
        change_type: str,
        reason: str,
        affected_repositories: Optional[List[str]] = None,
        affected_services: Optional[List[str]] = None,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        confidence: float = 0.5,
        triggered_actions: Optional[List[str]] = None,
        risk_before: Optional[float] = None,
        risk_after: Optional[float] = None,
        prediction_id: Optional[str] = None,
        mission_id: Optional[str] = None,
    ) -> CognitionTimelineEntry:
        """Append an entry to the cognition timeline."""
        entry = CognitionTimelineEntry(
            entry_id=_id(),
            timestamp=_now(),
            phase=self._current_phase.value,
            change_type=change_type,
            reason=reason,
            affected_repositories=affected_repositories or [],
            affected_services=affected_services or [],
            previous_state=previous_state,
            new_state=new_state,
            confidence=confidence,
            triggered_actions=triggered_actions or [],
            risk_before=risk_before,
            risk_after=risk_after,
            prediction_id=prediction_id,
            mission_id=mission_id,
        )
        self._timeline.append(entry)
        if len(self._timeline) > 1000:
            self._timeline = self._timeline[-500:]

        # Trigger knowledge evolution for significant entries
        if triggered_actions or (risk_after and risk_after > 50):
            asyncio.ensure_future(self._evolve_knowledge(entry))

        return entry

    # ------------------------------------------------------------------
    # Dashboard / Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Get cognition runtime status."""
        return {
            "state": self._state.value,
            "current_phase": self._current_phase.value,
            "loop_count": self._loop_count,
            "started_at": self._started_at,
            "last_repo_check": self._last_repo_check,
            "last_infra_check": self._last_infra_check,
            "known_repositories_count": len(self._known_repositories),
            "known_services_count": len(self._known_services),
            "timeline_entries_count": len(self._timeline),
            "loop_interval_seconds": self._loop_interval,
            "repo_interval_seconds": self._repo_interval,
            "infra_interval_seconds": self._infra_interval,
        }

    def get_dashboard(self) -> Dict[str, Any]:
        """Get complete cognition dashboard data."""
        from backend.services.enterprise_repository_brain import repository_brain

        timeline = [asdict(e) for e in self._timeline[-100:]]

        # Latest observations
        latest_observations = []
        for entry in reversed(self._timeline[-20:]):
            latest_observations.append({
                "type": entry.change_type,
                "reason": entry.reason,
                "timestamp": entry.timestamp,
                "confidence": entry.confidence,
                "repositories": entry.affected_repositories,
                "services": entry.affected_services,
                "risk_before": entry.risk_before,
                "risk_after": entry.risk_after,
            })

        # Risk evolution
        risk_evolution = [
            {"repository": repo, "score": score}
            for repo, score in self._previous_risk_scores.items()
        ]

        # Architecture changes
        arch_changes = []
        for entry in self._timeline:
            if entry.change_type in ("architecture_changed", "architecture_drift"):
                arch_changes.append({
                    "type": entry.change_type,
                    "repository": entry.affected_repositories[0] if entry.affected_repositories else "",
                    "timestamp": entry.timestamp,
                    "reason": entry.reason,
                })

        # Repository brain summary
        brain_summary = {}
        try:
            brain_summary = repository_brain.get_dashboard()
        except Exception:
            pass

        return {
            "status": self.get_status(),
            "latest_observations": latest_observations,
            "risk_evolution": risk_evolution,
            "architecture_changes": arch_changes[-20:],
            "timeline": timeline,
            "repository_brain": brain_summary,
            "infra_health_baseline": self._infra_health_baseline,
        }

    def get_timeline(
        self,
        limit: int = 50,
        offset: int = 0,
        change_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get cognition timeline entries with optional filtering."""
        entries = list(reversed(self._timeline))
        if change_type:
            entries = [e for e in entries if e.change_type == change_type]
        return [asdict(e) for e in entries[offset:offset + limit]]


# =============================================================================
# Module-level singleton
# =============================================================================

enterprise_continuous_cognition_runtime = EnterpriseContinuousCognitionRuntime()
