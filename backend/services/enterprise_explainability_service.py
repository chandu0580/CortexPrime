"""
Enterprise Explainability Service — reconstructs complete decision intelligence
for every enterprise mission using existing runtime data.

This is a READ-ONLY aggregation layer: it gathers data from all existing services
and composes it into comprehensive explanations. No new data is written.

Data sources:
  - Replay Store    → full event sequence
  - Knowledge Graph → entities, relationships, lineage
  - Audit Logger    → governance decisions, policy evaluations
  - Learning Engine → lessons, patterns, recommendations used
  - Memory Store    → episodic/semantic/reflection entries
  - Connector Registry → operation metadata
  - Reflection Store   → self-reflection entries
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from backend.safety.audit_logger import audit_logger
from backend.services.enterprise_graph_service import enterprise_graph
from backend.services.mission_replay_store import replay_store

log = logging.getLogger(__name__)


class EnterpriseExplainabilityService:
    """
    Reconstructs full decision explanations for enterprise missions.

    Every public method reads from existing services and returns structured
    explanation data — no side effects, no writes.
    """

    # ------------------------------------------------------------------
    # Public: list recent missions with explainability metadata
    # ------------------------------------------------------------------

    async def list_missions(
        self, limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List recent missions with summary explainability metadata."""
        missions_raw = await enterprise_graph.list_recent_missions(limit=limit)
        missions = missions_raw if isinstance(missions_raw, list) else missions_raw.get("missions", [])

        result: List[Dict[str, Any]] = []
        for m in missions:
            execution_id = m.get("execution_id", "")
            result.append({
                "execution_id": execution_id,
                "template_name": m.get("template_name", ""),
                "objective": m.get("objective", ""),
                "status": m.get("status", "unknown"),
                "started_at": m.get("started_at", ""),
                "completed_at": m.get("completed_at", ""),
                "has_explainability": bool(execution_id),
            })
        return result

    # ------------------------------------------------------------------
    # Public: full mission explanation
    # ------------------------------------------------------------------

    async def get_mission_explanation(
        self, execution_id: str,
    ) -> Dict[str, Any]:
        """Full decision explanation for a mission."""
        replay_events = await self._get_replay_events(execution_id)
        graph = await self._get_mission_graph(execution_id)
        audit = await self._get_audit_records(execution_id)
        learning = await self._get_learning_context(execution_id)
        timeline = self._build_timeline(replay_events, audit)
        reasoning = self._build_reasoning_chain(replay_events, graph, audit)
        evidence = self._build_evidence(replay_events, graph)
        alternatives = self._build_alternatives(replay_events)
        policies = self._build_policies(audit)
        verification = self._build_verification(replay_events, graph)
        confidence = self._compute_confidence(replay_events, audit, verification)
        connector_calls = self._build_connector_calls(replay_events)

        return {
            "execution_id": execution_id,
            "summary": self._build_summary(graph, replay_events, confidence),
            "timeline": timeline,
            "reasoning": reasoning,
            "evidence": evidence,
            "alternatives": alternatives,
            "policies": policies,
            "verification": verification,
            "confidence": confidence,
            "connector_calls": connector_calls,
            "learning_context": learning,
            "sources": {
                "replay_events": len(replay_events),
                "graph_entities": len(graph.get("actions", [])) if graph else 0,
                "audit_records": len(audit),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Individual section endpoints
    # ------------------------------------------------------------------

    async def get_timeline(self, execution_id: str) -> Dict[str, Any]:
        replay_events = await self._get_replay_events(execution_id)
        audit = await self._get_audit_records(execution_id)
        return {
            "execution_id": execution_id,
            "timeline": self._build_timeline(replay_events, audit),
            "total_entries": len(replay_events) + len(audit),
        }

    async def get_reasoning(self, execution_id: str) -> Dict[str, Any]:
        replay_events = await self._get_replay_events(execution_id)
        graph = await self._get_mission_graph(execution_id)
        audit = await self._get_audit_records(execution_id)
        return {
            "execution_id": execution_id,
            "reasoning": self._build_reasoning_chain(replay_events, graph, audit),
        }

    async def get_evidence(self, execution_id: str) -> Dict[str, Any]:
        replay_events = await self._get_replay_events(execution_id)
        graph = await self._get_mission_graph(execution_id)
        return {
            "execution_id": execution_id,
            "evidence": self._build_evidence(replay_events, graph),
        }

    async def get_alternatives(self, execution_id: str) -> Dict[str, Any]:
        replay_events = await self._get_replay_events(execution_id)
        return {
            "execution_id": execution_id,
            "alternatives": self._build_alternatives(replay_events),
        }

    async def get_policies(self, execution_id: str) -> Dict[str, Any]:
        audit = await self._get_audit_records(execution_id)
        return {
            "execution_id": execution_id,
            "policies": self._build_policies(audit),
        }

    async def get_verification(self, execution_id: str) -> Dict[str, Any]:
        replay_events = await self._get_replay_events(execution_id)
        graph = await self._get_mission_graph(execution_id)
        return {
            "execution_id": execution_id,
            "verification": self._build_verification(replay_events, graph),
        }

    async def get_confidence(self, execution_id: str) -> Dict[str, Any]:
        replay_events = await self._get_replay_events(execution_id)
        audit = await self._get_audit_records(execution_id)
        graph = await self._get_mission_graph(execution_id)
        verification = self._build_verification(replay_events, graph)
        return {
            "execution_id": execution_id,
            "confidence": self._compute_confidence(replay_events, audit, verification),
        }

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    async def get_dashboard(self) -> Dict[str, Any]:
        """Aggregated explainability dashboard."""
        missions = await self.list_missions(limit=100)
        total = len(missions)
        completed = sum(1 for m in missions if m.get("status") == "completed")
        failed = sum(1 for m in missions if m.get("status") == "failed")
        running = sum(1 for m in missions if m.get("status") == "running")

        avg_events = 0
        if missions:
            for m in missions[:10]:
                eid = m.get("execution_id", "")
                if eid:
                    events = await self._get_replay_events(eid)
                    avg_events += len(events)
            avg_events = avg_events // min(len(missions), 10)

        return {
            "total_missions": total,
            "completed_missions": completed,
            "failed_missions": failed,
            "running_missions": running,
            "avg_events_per_mission": avg_events,
            "explainable_missions": sum(1 for m in missions if m.get("has_explainability")),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal data retrieval
    # ------------------------------------------------------------------

    async def _get_replay_events(self, execution_id: str) -> List[Dict[str, Any]]:
        try:
            return await replay_store.get_events(execution_id)
        except Exception as exc:
            log.debug("Replay fetch failed for %s: %s", execution_id, exc)
            return []

    async def _get_mission_graph(self, execution_id: str) -> Dict[str, Any]:
        try:
            return await enterprise_graph.get_mission_graph(execution_id)
        except Exception as exc:
            log.debug("Graph fetch failed for %s: %s", execution_id, exc)
            return {}

    async def _get_audit_records(self, execution_id: str) -> List[Dict[str, Any]]:
        try:
            entries = await audit_logger.get_by_execution_async(execution_id)
            return [e.as_dict() if hasattr(e, "as_dict") else (e if isinstance(e, dict) else {"raw": str(e)}) for e in entries]
        except Exception as exc:
            log.debug("Audit fetch failed for %s: %s", execution_id, exc)
            return []

    async def _get_learning_context(self, execution_id: str) -> Dict[str, Any]:
        try:
            from backend.services.enterprise_learning_service import enterprise_learning

            lessons = await enterprise_learning.get_lessons(limit=10)
            relevant = [
                lesson for lesson in lessons
                if lesson.get("metadata", {}).get("execution_id") == execution_id
            ]
            patterns = await enterprise_learning.get_failure_patterns(limit=5)
            recovery = await enterprise_learning.get_recovery_patterns()
            return {
                "lessons_applied": [
                    {"content": lesson.get("content", "")[:200], "confidence": lesson.get("confidence", 0)}
                    for lesson in relevant[:5]
                ],
                "patterns_available": [
                    {"signature": p.get("signature", ""), "count": p.get("metadata", {}).get("count", 0)}
                    for p in patterns[:5]
                ],
                "recovery_strategies": [
                    {"type": r.get("recovery_type", ""), "count": r.get("metadata", {}).get("count", 0)}
                    for r in recovery
                ],
            }
        except ImportError:
            return {}
        except Exception as exc:
            log.debug("Learning context unavailable: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Explanation builders
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        graph: Dict[str, Any],
        events: List[Dict[str, Any]],
        confidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        mission = graph.get("mission", {})
        status = mission.get("status", "unknown")
        steps = graph.get("actions", [])
        decisions = graph.get("decisions", [])
        recoveries = graph.get("recoveries", [])
        approvals = graph.get("approvals", [])
        artifacts = graph.get("artifacts", [])
        outcomes = graph.get("outcomes", [])

        return {
            "mission_objective": mission.get("objective", ""),
            "template_name": mission.get("template_name", ""),
            "status": status,
            "started_at": mission.get("started_at", ""),
            "completed_at": mission.get("completed_at", ""),
            "total_steps": len(steps),
            "total_decisions": len(decisions),
            "total_recoveries": len(recoveries),
            "total_approvals": len(approvals),
            "total_artifacts": len(artifacts),
            "total_outcomes": len(outcomes),
            "overall_confidence": confidence.get("overall", 0.0),
            "risk_level": self._assess_risk_level(recoveries, status),
        }

    def _build_timeline(
        self,
        events: List[Dict[str, Any]],
        audit: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        timeline: List[Dict[str, Any]] = []
        for ev in events:
            timeline.append({
                "type": "event",
                "source": "replay",
                "timestamp": ev.get("timestamp", ev.get("recorded_at", "")),
                "event_type": ev.get("event_type", ev.get("type", "unknown")),
                "agent": ev.get("agent", ""),
                "status": ev.get("status", ""),
                "message": (ev.get("message", "") or "")[:300],
                "phase": self._classify_phase(ev),
            })
        for entry in audit:
            timeline.append({
                "type": "audit",
                "source": "audit_log",
                "timestamp": entry.get("timestamp", ""),
                "event_type": entry.get("action", "audit_entry"),
                "agent": entry.get("agent", ""),
                "status": entry.get("outcome", ""),
                "message": entry.get("reason", "")[:300],
                "phase": "governance",
            })
        timeline.sort(key=lambda x: x.get("timestamp", ""))
        return timeline

    def _build_reasoning_chain(
        self,
        events: List[Dict[str, Any]],
        graph: Dict[str, Any],
        audit: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        chain: List[Dict[str, Any]] = []
        for ev in events:
            et = ev.get("event_type", ev.get("type", ""))
            if any(kw in et.lower() for kw in ["decision", "reasoning", "plan", "select", "choose", "evaluate"]):
                chain.append({
                    "step": len(chain) + 1,
                    "event_type": et,
                    "decision": ev.get("message", ""),
                    "agent": ev.get("agent", ""),
                    "timestamp": ev.get("timestamp", ev.get("recorded_at", "")),
                    "rationale": self._extract_rationale(ev),
                })
        for d in graph.get("decisions", []):
            chain.append({
                "step": len(chain) + 1,
                "event_type": "decision",
                "decision": f"{d.get('decision_type', 'decision')}: {d.get('outcome', '')}",
                "agent": "system",
                "timestamp": d.get("created_at", d.get("started_at", "")),
                "rationale": d.get("reason", ""),
            })
        for a_entry in audit:
            if a_entry.get("action") in ("approve", "reject", "block", "escalate"):
                chain.append({
                    "step": len(chain) + 1,
                    "event_type": "governance_decision",
                    "decision": f"{a_entry.get('action')}: {a_entry.get('target', '')}",
                    "agent": a_entry.get("agent", "governance"),
                    "timestamp": a_entry.get("timestamp", ""),
                    "rationale": a_entry.get("reason", ""),
                })
        chain.sort(key=lambda x: x.get("timestamp", ""))
        for i, item in enumerate(chain):
            item["step"] = i + 1
        return chain

    def _build_evidence(
        self,
        events: List[Dict[str, Any]],
        graph: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        evidence_list: List[Dict[str, Any]] = []

        for ev in events:
            payload = ev.get("payload") or ev.get("metadata") or {}
            if payload:
                evidence_list.append({
                    "source": "replay_event",
                    "event_type": ev.get("event_type", ev.get("type", "unknown")),
                    "content": str(payload)[:500],
                    "timestamp": ev.get("timestamp", ev.get("recorded_at", "")),
                })

        for art in graph.get("artifacts", []):
            evidence_list.append({
                "source": "knowledge_graph",
                "event_type": "artifact",
                "content": f"{art.get('name', 'artifact')}: {art.get('description', '')}",
                "url": art.get("url", ""),
                "timestamp": art.get("created_at", art.get("started_at", "")),
            })

        for ev_item in graph.get("evidence", []):
            evidence_list.append({
                "source": "verification",
                "event_type": "evidence",
                "content": f"Verified: {ev_item.get('verified', False)} — method: {ev_item.get('method_used', 'unknown')}",
                "timestamp": ev_item.get("created_at", ev_item.get("started_at", "")),
            })

        return evidence_list

    def _build_alternatives(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        recoveries = [ev for ev in events if "recover" in (ev.get("event_type", ev.get("type", ""))).lower()]
        retries = 0
        fallbacks = 0
        rollbacks = 0
        escalations = 0

        for r in recoveries:
            rt = (r.get("payload") or r.get("metadata") or {}).get("recovery_type", "")
            msg = (r.get("message", "") or "").lower()
            if "retry" in rt or "retry" in msg:
                retries += 1
            elif "fallback" in rt or "fallback" in msg or "alternative" in rt:
                fallbacks += 1
            elif "rollback" in rt or "rollback" in msg:
                rollbacks += 1
            elif "escalation" in rt or "escalation" in msg:
                escalations += 1

        alternatives_considered = []
        if retries > 0:
            alternatives_considered.append({
                "type": "retry",
                "count": retries,
                "description": "Re-attempted the failed operation",
                "status": "executed",
            })
        if fallbacks > 0:
            alternatives_considered.append({
                "type": "fallback",
                "count": fallbacks,
                "description": "Used alternative connector or operation",
                "status": "executed",
            })
        if rollbacks > 0:
            alternatives_considered.append({
                "type": "rollback",
                "count": rollbacks,
                "description": "Rolled back previous steps",
                "status": "executed",
            })
        if escalations > 0:
            alternatives_considered.append({
                "type": "escalation",
                "count": escalations,
                "description": "Escalated to human operator",
                "status": "executed",
            })

        return {
            "total_alternatives": len(alternatives_considered),
            "alternatives": alternatives_considered,
            "note": "Alternatives are selected automatically by the recovery pipeline based on failure context.",
        }

    def _build_policies(self, audit: List[Dict[str, Any]]) -> Dict[str, Any]:
        policy_evals = []
        for entry in audit:
            action = entry.get("action", "")
            risk = entry.get("risk_level", "low")
            outcome = entry.get("outcome", "")
            reason = entry.get("reason", "")
            target = entry.get("target", "")

            if action in ("check_tool", "validate", "guardrails", "approve", "reject", "block", "escalate"):
                policy_name = f"{action}:{target}" if target else action
                policy_evals.append({
                    "policy": policy_name,
                    "risk_level": risk,
                    "outcome": outcome,
                    "reason": reason,
                    "timestamp": entry.get("timestamp", ""),
                })

        return {
            "total_evaluated": len(policy_evals),
            "policies": policy_evals,
        }

    def _build_verification(
        self,
        events: List[Dict[str, Any]],
        graph: Dict[str, Any],
    ) -> Dict[str, Any]:
        verification_results = []
        for ev_item in graph.get("evidence", []):
            verified = ev_item.get("verified", False)
            verification_results.append({
                "verified": verified,
                "method": ev_item.get("method_used", "unknown"),
                "evidence_data": str(ev_item.get("evidence_data", ""))[:300],
                "timestamp": ev_item.get("created_at", ev_item.get("started_at", "")),
            })
        for ev in events:
            et = ev.get("event_type", ev.get("type", ""))
            if "verif" in et.lower():
                payload = ev.get("payload") or ev.get("metadata") or {}
                verification_results.append({
                    "verified": payload.get("verified", False),
                    "method": payload.get("method_used", "event"),
                    "evidence_data": ev.get("message", "")[:300],
                    "timestamp": ev.get("timestamp", ev.get("recorded_at", "")),
                })

        return {
            "total_checks": len(verification_results),
            "passed": sum(1 for v in verification_results if v.get("verified")),
            "failed": sum(1 for v in verification_results if not v.get("verified")),
            "results": verification_results,
        }

    def _build_connector_calls(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        calls = []
        for ev in events:
            et = ev.get("event_type", ev.get("type", ""))
            if "connector" in et.lower() or "step" in et.lower():
                payload = ev.get("payload") or ev.get("metadata") or {}
                calls.append({
                    "connector": payload.get("connector", ev.get("agent", "unknown")),
                    "operation": payload.get("operation", et),
                    "status": ev.get("status", ""),
                    "description": (ev.get("message", "") or "")[:200],
                    "timestamp": ev.get("timestamp", ev.get("recorded_at", "")),
                })
        return calls

    # ------------------------------------------------------------------
    # Confidence computation
    # ------------------------------------------------------------------

    def _compute_confidence(
        self,
        events: List[Dict[str, Any]],
        audit: List[Dict[str, Any]],
        verification: Dict[str, Any],
    ) -> Dict[str, Any]:
        base_score = 0.7
        weights = {
            "completion": 0.2,
            "verification": 0.2,
            "recovery": 0.15,
            "approval": 0.15,
            "audit": 0.15,
            "consistency": 0.15,
        }

        completion_score = self._score_completion(events)
        verification_score = self._score_verification(verification)
        recovery_score = self._score_recovery(events)
        approval_score = self._score_approval(audit)
        audit_score = self._score_audit(audit)
        consistency_score = self._score_consistency(events)

        component_scores = {
            "completion": completion_score,
            "verification": verification_score,
            "recovery": recovery_score,
            "approval": approval_score,
            "audit": audit_score,
            "consistency": consistency_score,
        }

        overall = base_score + sum(
            component_scores[k] * weights[k] for k in weights
        )
        overall = max(0.0, min(1.0, overall))

        return {
            "overall": round(overall, 3),
            "components": {k: round(v, 3) for k, v in component_scores.items()},
            "weights": weights,
            "base_score": base_score,
        }

    @staticmethod
    def _score_completion(events: List[Dict[str, Any]]) -> float:
        has_completion = any(
            "completed" in (ev.get("status", "") or "").lower()
            or "completed" in (ev.get("event_type", ev.get("type", "") or ""))
            for ev in events
        )
        return 0.15 if has_completion else -0.15

    @staticmethod
    def _score_verification(verification: Dict[str, Any]) -> float:
        total = verification.get("total_checks", 0)
        if total == 0:
            return -0.05
        passed = verification.get("passed", 0)
        ratio = passed / total
        return 0.15 * ratio - 0.05 * (1 - ratio)

    @staticmethod
    def _score_recovery(events: List[Dict[str, Any]]) -> float:
        recovery_count = sum(
            1 for ev in events
            if "recover" in (ev.get("event_type", ev.get("type", "") or "")).lower()
        )
        if recovery_count == 0:
            return 0.05
        return -0.05 * min(recovery_count, 5)

    @staticmethod
    def _score_approval(audit: List[Dict[str, Any]]) -> float:
        approvals = sum(1 for e in audit if e.get("outcome") == "approved")
        rejections = sum(1 for e in audit if e.get("outcome") == "rejected")
        total = approvals + rejections
        if total == 0:
            return 0.0
        return 0.1 * (approvals / total) - 0.05 * (rejections / total)

    @staticmethod
    def _score_audit(audit: List[Dict[str, Any]]) -> float:
        if not audit:
            return -0.05
        high_risk = sum(1 for e in audit if e.get("risk_level") == "high")
        if high_risk > 2:
            return -0.05
        return 0.05

    @staticmethod
    def _score_consistency(events: List[Dict[str, Any]]) -> float:
        statuses = [ev.get("status", "") for ev in events if ev.get("status")]
        if not statuses:
            return 0.0
        failure_count = sum(1 for s in statuses if "fail" in s.lower() or "error" in s.lower())
        ratio = failure_count / len(statuses)
        if ratio > 0.5:
            return -0.1
        return 0.05 * (1 - ratio)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_phase(ev: Dict[str, Any]) -> str:
        et = (ev.get("event_type", ev.get("type", "") or "")).lower()
        if "launch" in et or "start" in et:
            return "planning"
        if "reason" in et or "think" in et or "plan" in et:
            return "reasoning"
        if "simulat" in et:
            return "simulation"
        if "decid" in et or "select" in et or "choose" in et:
            return "decision"
        if "step" in et or "connector" in et or "action" in et:
            return "workflow"
        if "verif" in et:
            return "verification"
        if "recover" in et or "retry" in et or "fallback" in et or "rollback" in et or "escalat" in et:
            return "recovery"
        if "approv" in et:
            return "approval"
        if "complet" in et:
            return "completion"
        if "fail" in et or "error" in et:
            return "failure"
        return "unknown"

    @staticmethod
    def _extract_rationale(ev: Dict[str, Any]) -> str:
        payload = ev.get("payload") or ev.get("metadata") or {}
        for key in ("reason", "rationale", "explanation", "evidence", "justification"):
            val = payload.get(key)
            if val:
                return str(val)[:300]
        return ""

    @staticmethod
    def _assess_risk_level(recoveries: List[Any], status: str) -> str:
        if status == "failed":
            return "high"
        if len(recoveries) >= 3:
            return "high"
        if len(recoveries) >= 1:
            return "medium"
        if status == "completed":
            return "low"
        return "unknown"


enterprise_explainability = EnterpriseExplainabilityService()
