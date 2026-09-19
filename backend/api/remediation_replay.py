"""Replay of a remediation lifecycle — Phase 11.4 (ADR-124).

A fold over what was recorded, never a re-run. It holds no repository, no
writer, no reader, no approval store and no worker: the caller hands it the
recorded plan and events (and, optionally, the execution's own recorded events,
folded by the existing ``ExecutionReplayer``), and it returns a projection.

It shows the chain the mandate asks a third party to reconstruct -- proposal,
policy, approval, execution, verification, recovery, learning -- in recorded
order, and it NAMES what is missing or out of order (a causal gap) instead of
filling it in. A replay is not authoritative: it cannot approve, execute,
verify or change a stage; the only thing it can do is disagree loudly with a
ledger that is incomplete.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

__all__ = ["replay_remediation", "PHASES", "stage_phase"]

#: Stage -> lifecycle phase, in causal order.
PHASES = ("proposal", "policy", "approval", "execution", "verification", "recovery", "learning")
_PHASE_OF = {
    "planned": "proposal", "proposal_rejected": "proposal", "prohibited": "policy",
    "recommendation_only": "policy", "autonomy_decided": "policy",
    "approval_requested": "approval", "approval_granted": "approval", "approval_denied": "approval",
    "approval_expired": "approval", "stale": "execution", "execution_refused": "execution",
    "executing": "execution", "executed": "execution", "execution_failed": "execution",
    "execution_unknown": "execution", "duplicate_suppressed": "execution",
    "verified": "verification", "verification_failed": "verification", "no_effect_confirmed": "verification",
    "verification_insufficient": "verification", "discrepancy": "verification",
    "recovery_decided": "recovery", "escalated": "recovery", "learned": "learning", "closed": "learning",
}


def stage_phase(stage: str) -> Optional[str]:
    return _PHASE_OF.get(stage)


def _stage(event: Any) -> str:
    record = getattr(event, "record", None) if not isinstance(event, Mapping) else event.get("record", event)
    return str((record or {}).get("stage") or "")


def _recorded_at(event: Any) -> str:
    value = getattr(event, "recorded_at", None) if not isinstance(event, Mapping) else event.get("recorded_at")
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def replay_remediation(*, plan: Optional[Mapping[str, Any]], events: Sequence[Any],
                       execution_replay: Optional[Mapping[str, Any]] = None) -> dict:
    ordered = sorted(events, key=lambda e: (_recorded_at(e), int((_record(e) or {}).get("sequence") or 0)))
    frames = []
    phases_seen: list = []
    gaps: list = []
    last_rank = -1
    for event in ordered:
        record = _record(event) or {}
        stage = str(record.get("stage") or "")
        phase = stage_phase(stage)
        if phase is None:
            gaps.append(f"unknown stage {stage!r}")
            continue
        rank = PHASES.index(phase)
        if rank < last_rank and phase not in ("policy",):
            gaps.append(f"{stage} recorded after a later phase ({PHASES[last_rank]})")
        last_rank = max(last_rank, rank)
        if phase not in phases_seen:
            phases_seen.append(phase)
        frames.append({"stage": stage, "phase": phase, "recorded_at": _recorded_at(event),
                       "summary": {k: v for k, v in record.items()
                                   if k in ("reason", "decider", "approval_id", "execution_ref", "verdict",
                                            "classification", "action", "discrepancy", "outcome",
                                            "authority", "eligibility", "polls", "category")}})
    stages = [f["stage"] for f in frames]
    if plan is not None and "planned" not in stages:
        gaps.append("a plan exists but no 'planned' event was recorded")
    executed = any(s in ("executed", "execution_failed", "execution_unknown") for s in stages)
    if executed and not any(s in ("approval_granted",) for s in stages):
        gaps.append("an execution was recorded with no approval grant before it")
    if executed and not any(s.startswith("verif") for s in stages):
        gaps.append("an execution was recorded with no verification after it")
    terminal = stages[-1] if stages else None
    return {
        "plan_id": (plan or {}).get("plan_id"),
        "frames": frames, "phases": phases_seen, "causal_gaps": gaps,
        "terminal_stage": terminal, "execution_replay": dict(execution_replay) if execution_replay else None,
        "authoritative": False,
        "note": "a projection of the recorded ledger; it performs, approves and verifies nothing",
    }


def _record(event: Any) -> Optional[Mapping[str, Any]]:
    if isinstance(event, Mapping):
        inner = event.get("record")
        return inner if isinstance(inner, Mapping) else event
    return getattr(event, "record", None)
