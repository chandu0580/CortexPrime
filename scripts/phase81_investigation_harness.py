"""Phase 8.1 real-Postgres evidence: durable investigation state machine.

Run:  python -m scripts.phase81_investigation_harness
      python -m scripts.phase81_investigation_harness --crash-child   (internal)

Proves against a fresh cortex_p81: an investigation is a durable, append-only,
tenant-scoped state machine that survives a real os._exit(9) crash and
reconstructs from the latest committed snapshot — never fabricating progress. No
provider, no execution, no world-write. The event ledger is inspected directly to
confirm append-only + idempotency.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED"}
TENANT = "acme-corp"


def check(name, ok, detail=""):
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {str(detail)[:160]}" if detail else ""))
    return bool(ok)


def bail(code, why):
    REPORT["verdict"] = {0: "VERIFIED", 1: "FAILED", 2: "NOT VERIFIED"}[code]
    REPORT["why"] = why
    print(json.dumps(REPORT, indent=1, default=str))
    sys.exit(code)


def _utc(m):
    return datetime(2026, 8, 12, 10, m, tzinfo=timezone.utc)


def _store():
    from backend.api.durability_composition import build_durable_persistence
    from backend.database.durable.config import DurabilityConfig
    from backend.contracts.execution import ExecutionEnvironment
    return build_durable_persistence(
        config=DurabilityConfig(environment=ExecutionEnvironment.DEVELOPMENT,
                                dsn_variable="CORTEX_DURABLE_URL"),
        dsn=os.environ["CORTEX_DURABLE_URL"])


def _svc(persistence):
    from backend.intelligence.application import InvestigationService
    from backend.intelligence.infrastructure import SqlInvestigationRepository
    return SqlInvestigationRepository(persistence.store), \
        InvestigationService(repository=SqlInvestigationRepository(persistence.store))


def _run_crash_child():
    """Open an investigation, advance a few steps, checkpoint, then die BEFORE
    completion — the durable state must survive and reconstruct."""
    from backend.contracts.tenant import TenantRef
    from backend.contracts.world import HypothesisStatus
    from backend.contracts.intelligence import (
        DifferentialHypothesis, InvestigationStatus, TemporalFit,
    )
    repo, svc = _svc(_store())
    tenant = TenantRef(tenant_id=TENANT)
    inv = svc.create(tenant=tenant, incident_ref="incident:crash", policy_ref="pol/1",
                     harness_version="h/1", now=_utc(0), investigation_ref="winv-crash")
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                         cause="triage", now=_utc(1))
    inv, _ = svc.add_question(investigation=inv, purpose="did the rollout cause 5xx?",
                              created_by="model:gpt", now=_utc(2))
    inv = svc.upsert_hypothesis(investigation=inv, hypothesis=DifferentialHypothesis(
        hypothesis_ref="h1", subject_ref="deployment/payments", proposition="rollout",
        status=HypothesisStatus.OPEN, temporal_fit=TemporalFit.CONSISTENT,
        created_by="model:gpt", evidence_for=("wfact-1",)), now=_utc(3))
    inv = svc.checkpoint(investigation=inv, now=_utc(4))
    sys.stdout.flush()
    os._exit(9)  # die BEFORE READY_FOR_ACTION/COMPLETED


def main():  # noqa: PLR0915
    if "--crash-child" in sys.argv:
        _run_crash_child()
        return
    if not (os.getenv("CORTEX_DURABLE_URL") or "").strip():
        bail(2, "CORTEX_DURABLE_URL not set")

    import sqlalchemy as sa
    from backend.contracts.tenant import TenantRef
    from backend.contracts.world import HypothesisStatus
    from backend.contracts.intelligence import (
        AutonomyLevel, DifferentialHypothesis, HumanEvent, HumanEventKind,
        InvestigationStatus, TemporalFit,
    )
    from backend.database.durable.tables import world_investigation_table as T
    from backend.intelligence.application import (
        AutonomyRefused, InvestigationNotFound, InvestigationTransitionRefused,
    )

    persistence = _store()
    repo, svc = _svc(persistence)
    tenant = TenantRef(tenant_id=TENANT)
    other = TenantRef(tenant_id="other")

    # ---- happy path: create -> investigate -> hypotheses -> ready ----
    print("[A] durable state machine")
    inv = svc.create(tenant=tenant, incident_ref="incident:pay-5xx", policy_ref="pol/1",
                     harness_version="h/1", now=_utc(0), investigation_ref="winv-a")
    check("created at seq 0", inv.status is InvestigationStatus.CREATED and inv.seq == 0)
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                         cause="triage", now=_utc(1))
    inv, q = svc.add_question(investigation=inv, purpose="rollout?", created_by="model:gpt", now=_utc(2))
    for ref, prop in (("h1", "rollout"), ("h2", "db-saturation"), ("h3", "dependency")):
        inv = svc.upsert_hypothesis(investigation=inv, hypothesis=DifferentialHypothesis(
            hypothesis_ref=ref, subject_ref="deployment/payments", proposition=prop,
            status=HypothesisStatus.OPEN, temporal_fit=TemporalFit.UNKNOWN,
            created_by="model:gpt", evidence_for=("wfact-1",)), now=_utc(3))
    check("differential holds 3 candidates", len(inv.differential) == 3)
    inv = svc.link_evidence(investigation=inv, evidence_refs=("wobs-1", "wfact-1"), now=_utc(4))
    inv = svc.transition(investigation=inv, to_status=InvestigationStatus.READY_FOR_ACTION,
                         cause="diagnosed", now=_utc(5))
    check("reached READY_FOR_ACTION", inv.status is InvestigationStatus.READY_FOR_ACTION)

    # reconstruct from Postgres
    rebuilt = svc.reconstruct(tenant=tenant, investigation_ref="winv-a")
    check("reconstructed from durable ledger", rebuilt == inv)
    check("cross-tenant reconstruct fails closed",
          _fails(lambda: svc.reconstruct(tenant=other, investigation_ref="winv-a"),
                 InvestigationNotFound))

    # ---- illegal transition refused ----
    print("[B] illegal transition + autonomy refusal")
    check("illegal transition refused (READY->COMPLETED)",
          _fails(lambda: svc.transition(investigation=inv, to_status=InvestigationStatus.COMPLETED,
                                        cause="skip", now=_utc(6)), InvestigationTransitionRefused))
    check("A1 cannot execute (autonomy refused)",
          _fails(lambda: svc.transition(investigation=inv, to_status=InvestigationStatus.EXECUTING,
                                        cause="act", now=_utc(6)), AutonomyRefused))

    # ---- A3 requires human approval to execute ----
    inv3 = svc.create(tenant=tenant, incident_ref="incident:b", policy_ref="pol/1",
                      harness_version="h/1", now=_utc(0), investigation_ref="winv-b",
                      autonomy_level=AutonomyLevel.A3_APPROVED_ACTION)
    inv3 = svc.transition(investigation=inv3, to_status=InvestigationStatus.INVESTIGATING, cause="t", now=_utc(1))
    inv3 = svc.transition(investigation=inv3, to_status=InvestigationStatus.READY_FOR_ACTION, cause="d", now=_utc(2))
    check("A3 without approval cannot execute",
          _fails(lambda: svc.transition(investigation=inv3, to_status=InvestigationStatus.EXECUTING,
                                        cause="act", now=_utc(3)), AutonomyRefused))
    approval = HumanEvent(kind=HumanEventKind.APPROVED, actor_ref="approval:req-1", reason="ok")
    inv3 = svc.transition(investigation=inv3, to_status=InvestigationStatus.EXECUTING,
                          cause="act", now=_utc(4), human_event=approval)
    check("A3 with human approval executes", inv3.status is InvestigationStatus.EXECUTING)

    # ---- append-only + idempotency (inspect the ledger directly) ----
    print("[C] append-only + idempotency")
    before = repo.event_count(tenant_id=TENANT, investigation_id="winv-a")
    # a stale snapshot at an already-committed seq collides (optimistic concurrency)
    dup = repo.append(event_id="dup", identity_digest=__import__(
        "backend.platform.hashing", fromlist=["compute_digest"]).compute_digest(
        {"tenant": TENANT, "investigation": "winv-a", "seq": inv.seq}).value,
        investigation_id="winv-a", tenant_id=TENANT, incident_ref="x", seq=inv.seq,
        event_kind="transitioned", from_status="ready_for_action", to_status="executing",
        autonomy_level="a1_investigate", state={}, payload={}, recorded_at=_utc(9))
    check("duplicate seq collides (append-only, idempotent)", dup is False)
    check("event count unchanged after duplicate",
          repo.event_count(tenant_id=TENANT, investigation_id="winv-a") == before)

    # ---- crash / recovery ----
    print("[D] crash before completion -> reconstruct, no fabricated progress")
    import subprocess
    child = subprocess.run(
        [sys.executable, "-m", "scripts.phase81_investigation_harness", "--crash-child"],
        env=dict(os.environ), cwd=os.getcwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    check("child died the hard way (exit 9)", child.returncode in (9, -9), f"rc={child.returncode}")
    _, succ = _svc(_store())
    crashed = succ.reconstruct(tenant=tenant, investigation_ref="winv-crash")
    check("crashed investigation reconstructs", crashed is not None)
    check("reconstructed status is INVESTIGATING (not fabricated COMPLETED)",
          crashed.status is InvestigationStatus.INVESTIGATING)
    check("pre-crash hypothesis survived", any(h.hypothesis_ref == "h1" for h in crashed.differential))
    check("crashed investigation cross-tenant fail-closed",
          _fails(lambda: succ.reconstruct(tenant=other, investigation_ref="winv-crash"),
                 InvestigationNotFound))

    # ---- replay inertness: reconstruction is a pure read (no new events) ----
    print("[E] reconstruction is read-only")
    n1 = repo.event_count(tenant_id=TENANT, investigation_id="winv-crash")
    for _ in range(5):
        succ.reconstruct(tenant=tenant, investigation_ref="winv-crash")
    n2 = repo.event_count(tenant_id=TENANT, investigation_id="winv-crash")
    check("reconstruction created zero new events", n1 == n2)

    REPORT["counts"] = {"investigation_events": repo.count_all()}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "durable investigation state verified" if ok else "a check failed")


def _fails(fn, exc):
    try:
        fn()
        return False
    except exc:
        return True


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
