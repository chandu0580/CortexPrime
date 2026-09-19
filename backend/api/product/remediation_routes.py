"""Governed remediation reads for the product API — Phase 11.4 (ADR-124).

``GET /api/v1/remediation/plans``                  the tenant's remediation plans, newest first,
                                                   each with its current lifecycle stage
``GET /api/v1/remediation/plans/{plan_id}``        one plan: the approval preview (what, why,
                                                   target, risk, blast radius, evidence, expected
                                                   outcome, rollback, verification, digest), the
                                                   autonomy decision and every lifecycle event
``GET /api/v1/remediation/plans/{plan_id}/replay`` an inert projection of the recorded chain
``GET /api/v1/remediation/plans/{plan_id}/cost``   investigation + planning + execution cost
``GET /api/v1/remediation/decisions``              proposals the platform did not plan, and why
``GET /api/v1/remediation/autonomy``               the autonomy metrics (mandate §60), computed
                                                   from the ledger, never stored

Every route is a GET. Nothing here plans, approves, executes or verifies: the
human decision on a plan is the EXISTING ``POST /api/v1/approvals/{id}/decision``,
and execution belongs to the remediation runtime. Tenant comes from
``product_context`` and nowhere else; another tenant's plan answers 404.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from backend.api.product.context import ProductContext, product_context

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/remediation", tags=["CortexPrime Governed Remediation"])


def _engine():
    from backend.api.product.app import current_engine

    engine = current_engine()
    if engine is None or getattr(engine, "reasoning", None) is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="the governed engine is not composed in this process")
    return engine


def _kind(record: Any) -> str:
    return str(getattr(record.kind, "value", record.kind))


def _events(engine: Any, tenant_id: str, subject: str) -> list:
    rows = [r for r in engine.reasoning.list_for_subject(tenant_id=tenant_id, subject_ref=subject)
            if _kind(r) == "remediation_event"]
    rows.sort(key=lambda r: (r.recorded_at, int((r.record or {}).get("sequence") or 0)))
    return rows


def _event_view(row: Any) -> dict:
    document = dict(row.record or {})
    document["recorded_at"] = row.recorded_at.isoformat()
    return document


def _plan_row(engine: Any, ctx: ProductContext, plan_id: str) -> Any:
    rows = [r for r in engine.reasoning.list_for_subject(tenant_id=ctx.tenant.tenant_id, subject_ref=plan_id)
            if _kind(r) == "remediation_plan"]
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such plan for this tenant")
    return rows[-1]


def _preview(plan: Mapping[str, Any]) -> dict:
    target = plan.get("target") or {}
    risk = plan.get("risk") or {}
    return {
        "what": {"action": plan.get("action"), "operation": plan.get("operation"),
                 "capability_ref": plan.get("capability_ref"), "parameters": plan.get("parameters")},
        "why": {"diagnosis": plan.get("diagnosis"), "diagnosis_ref": plan.get("diagnosis_ref")},
        "target": target,
        "risk": {"level": risk.get("level"), "rationale": risk.get("rationale"),
                 "reversibility": plan.get("reversibility")},
        "blast_radius": plan.get("blast_radius"),
        "evidence": plan.get("evidence_refs"),
        "expected_outcome": plan.get("expected_state"),
        "rollback": plan.get("rollback_strategy"),
        "verification": plan.get("verification_criteria"),
        "action_digest": plan.get("action_digest"),
        "policy_version": plan.get("policy_version"),
        "authority": plan.get("authority"), "authority_reason": plan.get("authority_reason"),
    }


@router.get("/plans")
def list_plans(ctx: ProductContext = Depends(product_context),
               limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    engine = _engine()
    rows = list(engine.reasoning.list_by_kind(tenant_id=ctx.tenant.tenant_id, kind="remediation_plan"))[-limit:]
    items = []
    for row in reversed(rows):
        plan = dict(row.record or {})
        events = _events(engine, ctx.tenant.tenant_id, row.subject_ref)
        stages = [str((e.record or {}).get("stage")) for e in events]
        closed = next((e.record for e in events if (e.record or {}).get("stage") == "closed"), None)
        items.append({"plan_id": plan.get("plan_id"), "investigation_ref": plan.get("investigation_ref"),
                      "incident_ref": plan.get("incident_ref"), "action": plan.get("action"),
                      "target": plan.get("target"), "risk": (plan.get("risk") or {}).get("level"),
                      "reversibility": plan.get("reversibility"), "authority": plan.get("authority"),
                      "stage": stages[-1] if stages else None,
                      "outcome": (closed or {}).get("outcome"), "created_at": plan.get("created_at")})
    return {"tenant_id": ctx.tenant.tenant_id, "count": len(items), "plans": items, "authority": "none"}


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str = Path(min_length=1, max_length=120),
             ctx: ProductContext = Depends(product_context)) -> dict[str, Any]:
    engine = _engine()
    row = _plan_row(engine, ctx, plan_id)
    plan = dict(row.record or {})
    events = [_event_view(e) for e in _events(engine, ctx.tenant.tenant_id, plan_id)]
    approval = None
    approval_id = next((e.get("approval_id") for e in events if e.get("approval_id")), None)
    approvals = getattr(engine, "approvals", None)
    if approval_id and approvals is not None:
        record = approvals.get(tenant_id=ctx.tenant.tenant_id, approval_id=approval_id)
        if record is not None:
            approval = {"approval_id": record.approval_id, "state": record.outcome,
                        "requested_by": record.requested_by, "decided_by": record.decided_by,
                        "approval_digest": record.approval_digest,
                        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
                        "consumed_by_execution": record.consumed_by_execution}
    autonomy = next((e.get("autonomy_decision") for e in events if e.get("stage") == "autonomy_decided"), None)
    return {"plan": plan, "approval_preview": _preview(plan), "approval": approval,
            "autonomy_decision": autonomy, "events": events,
            "stage": events[-1].get("stage") if events else None, "authority": "none"}


@router.get("/plans/{plan_id}/replay")
def replay_plan(plan_id: str = Path(min_length=1, max_length=120),
                ctx: ProductContext = Depends(product_context)) -> dict[str, Any]:
    from backend.api.remediation_replay import replay_remediation

    engine = _engine()
    row = _plan_row(engine, ctx, plan_id)
    events = _events(engine, ctx.tenant.tenant_id, plan_id)
    return replay_remediation(plan=dict(row.record or {}), events=events)


@router.get("/plans/{plan_id}/cost")
def plan_cost(plan_id: str = Path(min_length=1, max_length=120),
              ctx: ProductContext = Depends(product_context)) -> dict[str, Any]:
    engine = _engine()
    row = _plan_row(engine, ctx, plan_id)
    plan = dict(row.record or {})
    investigation_ref = str(plan.get("investigation_ref") or "")
    investigation_cost: Optional[Mapping[str, Any]] = None
    for record in engine.reasoning.list_for_subject(tenant_id=ctx.tenant.tenant_id, subject_ref=investigation_ref):
        if _kind(record) == "assessment":
            investigation_cost = (record.record or {}).get("cost")
    planning = {"model_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "latency_ms": 0.0}
    traces = getattr(engine, "traces", None)
    if traces is not None:
        try:
            for span in traces.spans_for_mission(f"remediation:{investigation_ref}"):
                if not isinstance(span, Mapping):
                    continue
                usage = span.get("token_usage") if isinstance(span.get("token_usage"), Mapping) else {}
                planning["model_calls"] += 1
                planning["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
                planning["completion_tokens"] += int(usage.get("completion_tokens") or 0)
                planning["latency_ms"] += float(span.get("latency_ms") or 0.0)
        except Exception as exc:  # noqa: BLE001
            log.warning("planning spans unreadable for %s: %s", plan_id, exc)
    events = [_event_view(e) for e in _events(engine, ctx.tenant.tenant_id, plan_id)]
    execution_seconds = sum(float(e.get("seconds") or 0.0) for e in events
                            if e.get("stage") in ("executed", "execution_failed", "execution_unknown"))
    verification_seconds = sum(float((e.get("verification") or {}).get("seconds") or 0.0) for e in events
                               if str(e.get("stage", "")).startswith("verif"))
    inv_tokens = int((investigation_cost or {}).get("total_tokens") or 0)
    plan_tokens = planning["prompt_tokens"] + planning["completion_tokens"]
    return {
        "plan_id": plan_id, "incident_ref": plan.get("incident_ref"),
        "investigation": investigation_cost, "planning": planning,
        "execution": {"seconds": round(execution_seconds, 2), "tokens": 0},
        "verification": {"seconds": round(verification_seconds, 2), "tokens": 0},
        "total": {"tokens": inv_tokens + plan_tokens,
                  "wall_seconds": round(float((investigation_cost or {}).get("wall_seconds") or 0.0)
                                        + planning["latency_ms"] / 1000.0 + execution_seconds
                                        + verification_seconds, 2)},
        "monetary_cost": ("none (no tokens spent)" if inv_tokens + plan_tokens == 0
                          else "unknown: no provider pricing is configured"),
        "authority": "none",
    }


@router.get("/decisions")
def list_decisions(ctx: ProductContext = Depends(product_context),
                   limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    engine = _engine()
    rows = [r for r in engine.reasoning.list_by_kind(tenant_id=ctx.tenant.tenant_id, kind="remediation_event")
            if str(r.subject_ref).startswith("rdecision_")][-limit:]
    items = [_event_view(r) for r in reversed(rows)]
    return {"tenant_id": ctx.tenant.tenant_id, "count": len(items), "decisions": items, "authority": "none"}


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator / denominator, 4) if denominator else None


@router.get("/autonomy")
def autonomy_metrics(ctx: ProductContext = Depends(product_context)) -> dict[str, Any]:
    """Mandate §60, from the ledger. A higher automation rate is not reported as
    better; every rate is shown beside the failures that qualify it."""
    engine = _engine()
    tenant = ctx.tenant.tenant_id
    plans = {r.subject_ref: dict(r.record or {})
             for r in engine.reasoning.list_by_kind(tenant_id=tenant, kind="remediation_plan")}
    events = [r for r in engine.reasoning.list_by_kind(tenant_id=tenant, kind="remediation_event")]
    by_stage: dict = {}
    for row in events:
        by_stage.setdefault(str((row.record or {}).get("stage")), []).append(row)
    executing = by_stage.get("executing", [])
    executions = len(executing)
    autonomous = sum(1 for r in executing if (r.record or {}).get("authority") == "autonomous")
    human = sum(1 for r in executing if (r.record or {}).get("authority") == "human_approved")
    human_requests = sum(1 for r in by_stage.get("approval_requested", [])
                         if (r.record or {}).get("authority") == "human_approval")
    human_grants = sum(1 for r in by_stage.get("approval_granted", [])
                       if (r.record or {}).get("decider_kind") == "human")
    denials = len(by_stage.get("approval_denied", []))
    verified = len(by_stage.get("verified", []))
    failed_verification = len(by_stage.get("verification_failed", []))
    recoveries = len(by_stage.get("recovery_decided", []))
    learned = by_stage.get("learned", [])
    false_diagnosis = sum(1 for r in learned if "false_diagnosis" in ((r.record or {}).get("category") or []))
    compensations = sum(1 for r in by_stage.get("recovery_decided", [])
                        if "compensating" in str((r.record or {}).get("reason") or ""))

    def _seconds(stage: str) -> list:
        values = []
        for row in by_stage.get(stage, []):
            plan = plans.get(row.subject_ref) or {}
            try:
                created = datetime.fromisoformat(str(plan.get("created_at")))
                values.append((row.recorded_at - created).total_seconds())
            except (TypeError, ValueError):
                continue
        return values

    remediate = _seconds("closed")
    verify = [float((r.record or {}).get("verification", {}).get("seconds") or 0.0)
              for r in by_stage.get("verified", []) + by_stage.get("verification_failed", [])]
    action_seconds = [float((r.record or {}).get("seconds") or 0.0)
                      for r in by_stage.get("executed", []) + by_stage.get("execution_failed", [])]
    investigation_tokens = 0
    for plan in plans.values():
        for record in engine.reasoning.list_for_subject(tenant_id=tenant,
                                                        subject_ref=str(plan.get("investigation_ref") or "")):
            if _kind(record) == "assessment":
                investigation_tokens += int(((record.record or {}).get("cost") or {}).get("total_tokens") or 0)
    return {
        "tenant_id": tenant, "plans": len(plans), "executions": executions,
        "AUTONOMOUS_ACTION_RATE": _rate(autonomous, executions),
        "VERIFIED_SUCCESS_RATE": _rate(verified, executions),
        "VERIFICATION_FAILURE_RATE": _rate(failed_verification, executions),
        "HUMAN_APPROVAL_RATE": _rate(human_grants, human_requests),
        "HUMAN_REJECTION_RATE": _rate(denials, human_requests),
        "FALSE_REMEDIATION_RATE": _rate(false_diagnosis, executions),
        "ROLLBACK_RATE": _rate(compensations, executions),
        "RECOVERY_RATE": _rate(recoveries, executions),
        "MEAN_TIME_TO_REMEDIATE": round(sum(remediate) / len(remediate), 1) if remediate else None,
        "MEAN_TIME_TO_VERIFY": round(sum(verify) / len(verify), 1) if verify else None,
        "ACTION_COST": {"mean_execution_seconds": round(sum(action_seconds) / len(action_seconds), 2)
                        if action_seconds else None, "monetary": "unknown: no provider pricing is configured"},
        "INVESTIGATION_COST": {"tokens": investigation_tokens,
                               "monetary": "unknown: no provider pricing is configured"},
        "counts": {"autonomous_actions": autonomous, "human_approved_actions": human,
                   "human_approval_requests": human_requests, "human_grants": human_grants,
                   "human_denials": denials, "verified": verified, "verification_failed": failed_verification,
                   "recoveries": recoveries, "false_diagnosis": false_diagnosis},
        "note": "a higher automation rate is not better by itself; read it beside the failure and rejection rates",
        "authority": "none",
    }
