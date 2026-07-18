"""
Enterprise Graph Service — Neo4j persistence for enterprise domain entities.

Records missions, connector actions, decisions, approvals, risks, artifacts,
recovery events, verification evidence, and outcomes to the Neo4j knowledge
graph with typed relationships for end-to-end lineage traversal.

Node Labels
-----------
  EnterpriseMission  — a launched enterprise mission (from templates)
  ConnectorAction    — a single step executed against a connector
  Decision           — an approval/rejection decision (human or auto)
  Risk               — a risk event or guardrails block
  Approval           — an approval gate record
  Evidence           — verification result / evidence snippet
  Artifact           — a produced artifact (issue, PR, page, etc.)
  Outcome            — final outcome of a mission
  Recovery           — a recovery action (retry, fallback, rollback)

Relationships
-------------
  (EnterpriseMission)-[:HAS_STEP]->(ConnectorAction)
  (ConnectorAction)-[:PRODUCED]->(Artifact)
  (ConnectorAction)->[:VERIFIED_BY]->(Evidence)
  (EnterpriseMission)-[:HAS_DECISION]->(Decision)
  (EnterpriseMission)-[:HAS_APPROVAL]->(Approval)
  (EnterpriseMission)-[:HAS_RISK]->(Risk)
  (EnterpriseMission)-[:HAS_OUTCOME]->(Outcome)
  (EnterpriseMission)-[:HAS_RECOVERY]->(Recovery)
  (Decision)-[:APPLIES_TO]->(ConnectorAction)
  (Approval)-[:GATED]->(ConnectorAction)
  (Recovery)-[:RECOVERED]->(ConnectorAction)
  (Evidence)-[:SUPPORTS]->(Artifact)
  (ConnectorAction)-[:NEXT]->(ConnectorAction)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.infrastructure.neo4j.connection import neo4j_connection

log = logging.getLogger(__name__)


# ======================================================================
# CONSTANTS
# ======================================================================

ENTERPRISE_SCHEMA_STATEMENTS: List[str] = [
    "CREATE CONSTRAINT enterprise_mission_id IF NOT EXISTS "
    "FOR (m:EnterpriseMission) REQUIRE m.execution_id IS UNIQUE",
    "CREATE CONSTRAINT connector_action_id IF NOT EXISTS "
    "FOR (a:ConnectorAction) REQUIRE a.action_id IS UNIQUE",
    "CREATE CONSTRAINT decision_id IF NOT EXISTS "
    "FOR (d:Decision) REQUIRE d.decision_id IS UNIQUE",
    "CREATE CONSTRAINT approval_request_id IF NOT EXISTS "
    "FOR (a:Approval) REQUIRE a.request_id IS UNIQUE",
    "CREATE CONSTRAINT evidence_id IF NOT EXISTS "
    "FOR (e:Evidence) REQUIRE e.evidence_id IS UNIQUE",
    "CREATE CONSTRAINT artifact_key IF NOT EXISTS "
    "FOR (a:Artifact) REQUIRE a.artifact_key IS UNIQUE",
    "CREATE INDEX enterprise_mission_status IF NOT EXISTS "
    "FOR (m:EnterpriseMission) ON (m.status)",
    "CREATE INDEX connector_action_type IF NOT EXISTS "
    "FOR (a:ConnectorAction) ON (a.connector_type)",
    "CREATE INDEX enterprise_mission_template IF NOT EXISTS "
    "FOR (m:EnterpriseMission) ON (m.template_id)",
    "CREATE FULLTEXT INDEX enterprise_mission_obj_fts IF NOT EXISTS "
    "FOR (m:EnterpriseMission) ON EACH [m.objective, m.template_name]",
    "CREATE FULLTEXT INDEX connector_action_desc_fts IF NOT EXISTS "
    "FOR (a:ConnectorAction) ON EACH [a.description, a.operation]",
    "CREATE FULLTEXT INDEX artifact_content_fts IF NOT EXISTS "
    "FOR (a:Artifact) ON EACH [a.name, a.description]",
]


class EnterpriseGraphService:
    """Records enterprise domain entities into Neo4j for lineage & search."""

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def ensure_schema(self) -> None:
        if not await neo4j_connection.ensure_connected():
            return
        async with neo4j_connection.driver.session() as session:
            for stmt in ENTERPRISE_SCHEMA_STATEMENTS:
                try:
                    await session.run(stmt)
                except Exception:
                    pass
        log.info("Enterprise graph schema ready")

    # ------------------------------------------------------------------
    # Record mission lifecycle
    # ------------------------------------------------------------------

    async def record_mission_launch(
        self,
        execution_id: str,
        template_id: str,
        template_name: str,
        objective: str,
        params: Dict[str, Any],
        launched_by: str = "system",
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return
        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MERGE (m:EnterpriseMission {execution_id: $execution_id})
                    SET m.template_id   = $template_id,
                        m.template_name = $template_name,
                        m.objective     = $objective,
                        m.params        = $params,
                        m.launched_by   = $launched_by,
                        m.status        = 'running',
                        m.started_at    = $now
                    """,
                    execution_id=execution_id,
                    template_id=template_id,
                    template_name=template_name,
                    objective=objective,
                    params=params,
                    launched_by=launched_by,
                    now=datetime.utcnow().isoformat(),
                )
            self._emit_graph_event("EnterpriseMission", execution_id, "created", execution_id)
        except Exception as exc:
            log.warning("record_mission_launch failed: %s", exc)

    async def record_mission_completion(
        self,
        execution_id: str,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return
        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MATCH (m:EnterpriseMission {execution_id: $execution_id})
                    SET m.status       = $status,
                        m.error        = $error,
                        m.completed_at = $now
                    """,
                    execution_id=execution_id,
                    status=status,
                    error=error,
                    now=datetime.utcnow().isoformat(),
                )
        except Exception as exc:
            log.warning("record_mission_completion failed: %s", exc)

    # ------------------------------------------------------------------
    # Connector actions
    # ------------------------------------------------------------------

    async def record_connector_action(
        self,
        execution_id: str,
        step_idx: int,
        action_id: str,
        connector_type: str,
        operation: str,
        description: str,
        status: str = "completed",
        params: Optional[Dict[str, Any]] = None,
        output: Optional[Any] = None,
        previous_action_id: Optional[str] = None,
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return
        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MERGE (a:ConnectorAction {action_id: $action_id})
                    SET a.connector_type = $connector_type,
                        a.operation      = $operation,
                        a.description    = $description,
                        a.step_idx       = $step_idx,
                        a.status         = $status,
                        a.params         = $params,
                        a.executed_at    = $now
                    """,
                    action_id=action_id,
                    connector_type=connector_type,
                    operation=operation,
                    description=description,
                    step_idx=step_idx,
                    status=status,
                    params=params or {},
                    now=datetime.utcnow().isoformat(),
                )

                # Link to mission
                await session.run(
                    """
                    MATCH (m:EnterpriseMission {execution_id: $execution_id})
                    MATCH (a:ConnectorAction {action_id: $action_id})
                    MERGE (m)-[:HAS_STEP]->(a)
                    """,
                    execution_id=execution_id,
                    action_id=action_id,
                )

                # Chain to previous step
                if previous_action_id:
                    await session.run(
                        """
                        MATCH (prev:ConnectorAction {action_id: $prev_id})
                        MATCH (curr:ConnectorAction {action_id: $curr_id})
                        MERGE (prev)-[:NEXT]->(curr)
                        """,
                        prev_id=previous_action_id,
                        curr_id=action_id,
                    )
            self._emit_graph_event("ConnectorAction", action_id, "created", execution_id)
        except Exception as exc:
            log.warning("record_connector_action failed: %s", exc)

    # ------------------------------------------------------------------
    # Artifacts produced by connector actions
    # ------------------------------------------------------------------

    async def record_artifact(
        self,
        action_id: str,
        artifact_key: str,
        artifact_type: str,
        name: str,
        description: Optional[str] = None,
        url: Optional[str] = None,
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return
        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MERGE (art:Artifact {artifact_key: $artifact_key})
                    SET art.type        = $artifact_type,
                        art.name        = $name,
                        art.description = $description,
                        art.url         = $url,
                        art.created_at  = $now
                    """,
                    artifact_key=artifact_key,
                    artifact_type=artifact_type,
                    name=name,
                    description=description,
                    url=url,
                    now=datetime.utcnow().isoformat(),
                )

                # Link from action
                await session.run(
                    """
                    MATCH (a:ConnectorAction {action_id: $action_id})
                    MATCH (art:Artifact {artifact_key: $artifact_key})
                    MERGE (a)-[:PRODUCED]->(art)
                    """,
                    action_id=action_id,
                    artifact_key=artifact_key,
                )
        except Exception as exc:
            log.warning("record_artifact failed: %s", exc)

    # ------------------------------------------------------------------
    # Verification evidence
    # ------------------------------------------------------------------

    async def record_evidence(
        self,
        evidence_id: str,
        action_id: str,
        verified: bool,
        method_used: str,
        evidence_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return
        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MERGE (e:Evidence {evidence_id: $evidence_id})
                    SET e.verified     = $verified,
                        e.method_used  = $method_used,
                        e.data         = $evidence_data,
                        e.created_at   = $now
                    """,
                    evidence_id=evidence_id,
                    verified=verified,
                    method_used=method_used,
                    evidence_data=evidence_data or {},
                    now=datetime.utcnow().isoformat(),
                )

                # Link from action
                await session.run(
                    """
                    MATCH (a:ConnectorAction {action_id: $action_id})
                    MATCH (e:Evidence {evidence_id: $evidence_id})
                    MERGE (a)-[:VERIFIED_BY]->(e)
                    """,
                    action_id=action_id,
                    evidence_id=evidence_id,
                )
        except Exception as exc:
            log.warning("record_evidence failed: %s", exc)

    # ------------------------------------------------------------------
    # Approval gate records
    # ------------------------------------------------------------------

    async def record_approval(
        self,
        request_id: str,
        execution_id: str,
        action_id: Optional[str],
        step_idx: int,
        status: str,
        reason: str,
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return
        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MERGE (a:Approval {request_id: $request_id})
                    SET a.status      = $status,
                        a.reason      = $reason,
                        a.step_idx    = $step_idx,
                        a.created_at  = $now
                    """,
                    request_id=request_id,
                    status=status,
                    reason=reason,
                    step_idx=step_idx,
                    now=datetime.utcnow().isoformat(),
                )

                # Link to mission
                await session.run(
                    """
                    MATCH (m:EnterpriseMission {execution_id: $execution_id})
                    MATCH (a:Approval {request_id: $request_id})
                    MERGE (m)-[:HAS_APPROVAL]->(a)
                    """,
                    execution_id=execution_id,
                    request_id=request_id,
                )

                # Link to action if applicable
                if action_id:
                    await session.run(
                        """
                        MATCH (a:Approval {request_id: $request_id})
                        MATCH (ca:ConnectorAction {action_id: $action_id})
                        MERGE (a)-[:GATED]->(ca)
                        """,
                        request_id=request_id,
                        action_id=action_id,
                    )
        except Exception as exc:
            log.warning("record_approval failed: %s", exc)

    # ------------------------------------------------------------------
    # Decisions (approval/rejection outcomes)
    # ------------------------------------------------------------------

    async def record_decision(
        self,
        decision_id: str,
        execution_id: str,
        decision_type: str,
        outcome: str,
        reason: str,
        action_id: Optional[str] = None,
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return
        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MERGE (d:Decision {decision_id: $decision_id})
                    SET d.type        = $decision_type,
                        d.outcome     = $outcome,
                        d.reason      = $reason,
                        d.created_at  = $now
                    """,
                    decision_id=decision_id,
                    decision_type=decision_type,
                    outcome=outcome,
                    reason=reason,
                    now=datetime.utcnow().isoformat(),
                )

                await session.run(
                    """
                    MATCH (m:EnterpriseMission {execution_id: $execution_id})
                    MATCH (d:Decision {decision_id: $decision_id})
                    MERGE (m)-[:HAS_DECISION]->(d)
                    """,
                    execution_id=execution_id,
                    decision_id=decision_id,
                )

                if action_id:
                    await session.run(
                        """
                        MATCH (d:Decision {decision_id: $decision_id})
                        MATCH (ca:ConnectorAction {action_id: $action_id})
                        MERGE (d)-[:APPLIES_TO]->(ca)
                        """,
                        decision_id=decision_id,
                        action_id=action_id,
                    )
        except Exception as exc:
            log.warning("record_decision failed: %s", exc)

    # ------------------------------------------------------------------
    # Risk events
    # ------------------------------------------------------------------

    async def record_risk(
        self,
        execution_id: str,
        risk_id: str,
        level: str,
        description: str,
        action_id: Optional[str] = None,
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return
        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MERGE (r:Risk {risk_id: $risk_id})
                    SET r.level       = $level,
                        r.description = $description,
                        r.created_at  = $now
                    """,
                    risk_id=risk_id,
                    level=level,
                    description=description,
                    now=datetime.utcnow().isoformat(),
                )

                await session.run(
                    """
                    MATCH (m:EnterpriseMission {execution_id: $execution_id})
                    MATCH (r:Risk {risk_id: $risk_id})
                    MERGE (m)-[:HAS_RISK]->(r)
                    """,
                    execution_id=execution_id,
                    risk_id=risk_id,
                )

                if action_id:
                    await session.run(
                        """
                        MATCH (r:Risk {risk_id: $risk_id})
                        MATCH (ca:ConnectorAction {action_id: $action_id})
                        MERGE (r)-[:AFFECTS]->(ca)
                        """,
                        risk_id=risk_id,
                        action_id=action_id,
                    )
        except Exception as exc:
            log.warning("record_risk failed: %s", exc)

    # ------------------------------------------------------------------
    # Recovery events
    # ------------------------------------------------------------------

    async def record_recovery(
        self,
        execution_id: str,
        recovery_id: str,
        recovery_type: str,
        description: str,
        action_id: Optional[str] = None,
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return
        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MERGE (r:Recovery {recovery_id: $recovery_id})
                    SET r.type        = $recovery_type,
                        r.description = $description,
                        r.created_at  = $now
                    """,
                    recovery_id=recovery_id,
                    recovery_type=recovery_type,
                    description=description,
                    now=datetime.utcnow().isoformat(),
                )

                await session.run(
                    """
                    MATCH (m:EnterpriseMission {execution_id: $execution_id})
                    MATCH (r:Recovery {recovery_id: $recovery_id})
                    MERGE (m)-[:HAS_RECOVERY]->(r)
                    """,
                    execution_id=execution_id,
                    recovery_id=recovery_id,
                )

                if action_id:
                    await session.run(
                        """
                        MATCH (r:Recovery {recovery_id: $recovery_id})
                        MATCH (ca:ConnectorAction {action_id: $action_id})
                        MERGE (r)-[:RECOVERED]->(ca)
                        """,
                        recovery_id=recovery_id,
                        action_id=action_id,
                    )
        except Exception as exc:
            log.warning("record_recovery failed: %s", exc)

    # ------------------------------------------------------------------
    # Outcome
    # ------------------------------------------------------------------

    async def record_outcome(
        self,
        execution_id: str,
        outcome_id: str,
        outcome_type: str,
        summary: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not await neo4j_connection.ensure_connected():
            return
        try:
            async with neo4j_connection.driver.session() as session:
                await session.run(
                    """
                    MERGE (o:Outcome {outcome_id: $outcome_id})
                    SET o.type        = $outcome_type,
                        o.summary     = $summary,
                        o.details     = $details,
                        o.created_at  = $now
                    """,
                    outcome_id=outcome_id,
                    outcome_type=outcome_type,
                    summary=summary,
                    details=details or {},
                    now=datetime.utcnow().isoformat(),
                )

                await session.run(
                    """
                    MATCH (m:EnterpriseMission {execution_id: $execution_id})
                    MATCH (o:Outcome {outcome_id: $outcome_id})
                    MERGE (m)-[:HAS_OUTCOME]->(o)
                    """,
                    execution_id=execution_id,
                    outcome_id=outcome_id,
                )
        except Exception as exc:
            log.warning("record_outcome failed: %s", exc)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    async def get_mission_graph(
        self,
        execution_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Return the full enterprise subgraph for a mission."""
        if not await neo4j_connection.ensure_connected():
            return None
        try:
            async with neo4j_connection.driver.session() as session:
                result = await session.run(
                    """
                    MATCH (m:EnterpriseMission {execution_id: $execution_id})
                    OPTIONAL MATCH (m)-[:HAS_STEP]->(ca:ConnectorAction)
                    OPTIONAL MATCH (ca)-[:PRODUCED]->(art:Artifact)
                    OPTIONAL MATCH (ca)-[:VERIFIED_BY]->(ev:Evidence)
                    OPTIONAL MATCH (ca)-[:NEXT]->(next_ca:ConnectorAction)
                    OPTIONAL MATCH (m)-[:HAS_DECISION]->(d:Decision)
                    OPTIONAL MATCH (m)-[:HAS_APPROVAL]->(ap:Approval)
                    OPTIONAL MATCH (m)-[:HAS_RISK]->(r:Risk)
                    OPTIONAL MATCH (m)-[:HAS_RECOVERY]->(rec:Recovery)
                    OPTIONAL MATCH (m)-[:HAS_OUTCOME]->(o:Outcome)
                    RETURN m,
                           collect(DISTINCT ca) AS actions,
                           collect(DISTINCT art) AS artifacts,
                           collect(DISTINCT ev) AS evidence,
                           collect(DISTINCT d) AS decisions,
                           collect(DISTINCT ap) AS approvals,
                           collect(DISTINCT r) AS risks,
                           collect(DISTINCT rec) AS recoveries,
                           collect(DISTINCT o) AS outcomes
                    """,
                    execution_id=execution_id,
                )
                record = await result.single()
                if not record:
                    return None

                def node_to_dict(n):
                    return dict(n) if n else {}

                return {
                    "mission": node_to_dict(record.get("m")),
                    "actions": [node_to_dict(a) for a in (record.get("actions") or []) if a],
                    "artifacts": [node_to_dict(a) for a in (record.get("artifacts") or []) if a],
                    "evidence": [node_to_dict(e) for e in (record.get("evidence") or []) if e],
                    "decisions": [node_to_dict(d) for d in (record.get("decisions") or []) if d],
                    "approvals": [node_to_dict(a) for a in (record.get("approvals") or []) if a],
                    "risks": [node_to_dict(r) for r in (record.get("risks") or []) if r],
                    "recoveries": [node_to_dict(r) for r in (record.get("recoveries") or []) if r],
                    "outcomes": [node_to_dict(o) for o in (record.get("outcomes") or []) if o],
                }
        except Exception as exc:
            log.warning("get_mission_graph failed: %s", exc)
            return None

    async def search_entities(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Full-text search across enterprise entities."""
        if not await neo4j_connection.ensure_connected():
            return []
        try:
            async with neo4j_connection.driver.session() as session:
                results = await session.run(
                    """
                    CALL {
                        CALL db.index.fulltext.queryNodes(
                            'enterprise_mission_obj_fts', $query
                        ) YIELD node AS n, score
                        RETURN n, score, 'EnterpriseMission' AS label
                        UNION
                        CALL db.index.fulltext.queryNodes(
                            'connector_action_desc_fts', $query
                        ) YIELD node AS n, score
                        RETURN n, score, 'ConnectorAction' AS label
                        UNION
                        CALL db.index.fulltext.queryNodes(
                            'artifact_content_fts', $query
                        ) YIELD node AS n, score
                        RETURN n, score, 'Artifact' AS label
                    }
                    RETURN n, score, label
                    ORDER BY score DESC
                    LIMIT $limit
                    """,
                    query=query,
                    limit=limit,
                )
                rows = await results.data()
                return [
                    {
                        "label": row["label"],
                        "score": row["score"],
                        "node": dict(row["n"]),
                    }
                    for row in rows
                ]
        except Exception as exc:
            log.warning("search_entities failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Event emission helper
    # ------------------------------------------------------------------

    def _emit_graph_event(
        self,
        entity_type: str,
        entity_id: str,
        action: str = "created",
        execution_id: Optional[str] = None,
    ) -> None:
        """Emit a graph update event via the EnterpriseEventHub."""
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            asyncio.ensure_future(enterprise_hub.emit_graph_update(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                execution_id=execution_id,
            ))
        except Exception:
            pass

    async def list_recent_missions(self, limit: int = 20) -> List[Dict[str, Any]]:
        if not await neo4j_connection.ensure_connected():
            return []
        try:
            async with neo4j_connection.driver.session() as session:
                results = await session.run(
                    """
                    MATCH (m:EnterpriseMission)
                    RETURN m ORDER BY m.started_at DESC LIMIT $limit
                    """,
                    limit=limit,
                )
                rows = await results.data()
                return [dict(row["m"]) for row in rows]
        except Exception as exc:
            log.warning("list_recent_missions failed: %s", exc)
            return []

    async def list_entities_by_type(self, label: str, limit: int = 50) -> List[Dict[str, Any]]:
        if not await neo4j_connection.ensure_connected():
            return []
        valid = {"EnterpriseMission", "ConnectorAction", "Decision", "Approval",
                 "Risk", "Recovery", "Evidence", "Artifact", "Outcome"}
        if label not in valid:
            return []
        try:
            async with neo4j_connection.driver.session() as session:
                results = await session.run(
                    f"MATCH (n:{label}) RETURN n ORDER BY n.created_at DESC LIMIT $limit",
                    limit=limit,
                )
                rows = await results.data()
                return [dict(row["n"]) for row in rows]
        except Exception as exc:
            log.warning("list_entities_by_type failed: %s", exc)
            return []

    async def get_connected_nodes(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Return a node and its immediate neighbors regardless of label."""
        if not await neo4j_connection.ensure_connected():
            return None
        try:
            async with neo4j_connection.driver.session() as session:
                result = await session.run(
                    """
                    MATCH (n)
                    WHERE n.execution_id = $node_id
                       OR n.action_id    = $node_id
                       OR n.evidence_id  = $node_id
                       OR n.decision_id  = $node_id
                       OR n.request_id   = $node_id
                       OR n.artifact_key = $node_id
                       OR n.outcome_id   = $node_id
                       OR n.risk_id      = $node_id
                       OR n.recovery_id  = $node_id
                    OPTIONAL MATCH (n)-[r]-(neighbor)
                    RETURN n,
                           collect(DISTINCT {rel: type(r), node: neighbor}) AS relationships
                    """,
                    node_id=node_id,
                )
                record = await result.single()
                if not record:
                    return None

                return {
                    "node": dict(record["n"]),
                    "relationships": [
                        {
                            "type": rel["rel"],
                            "node": dict(rel["node"]),
                        }
                        for rel in (record.get("relationships") or [])
                        if rel["node"] is not None
                    ],
                }
        except Exception as exc:
            log.warning("get_connected_nodes failed: %s", exc)
            return None


enterprise_graph = EnterpriseGraphService()
