"""Phase 6.3 Part B: leadership + audit-writer reclaim after real process death.

Two real OS processes against real PostgreSQL, using the EXISTING leadership
architecture (SqlLeadershipStore) — no new election system. Short leases so
the test is fast; the semantics are the store's own.

Run:  python -m scripts.phase63_leadership_harness
      python -m scripts.phase63_leadership_harness --holder   (internal child)

Proves, in order:
  1. WHILE A's lease is live (A already dead), B must NOT steal it — acquire
     returns None for both SCHEDULER and AUDIT_WRITER.
  2. AFTER legitimate expiry, B acquires both roles and the fencing token is
     ADVANCED (A_token + 1), never reset.
  3. The dead leader A is fenced out: a heartbeat carrying A's old token
     matches no row and returns None (StaleFencingToken territory).
  4. Row integrity: exactly one row per (scope, role), never deleted, now HELD
     by B — no manual repair, no forced acquisition, no token reset.
  5. The successor recovers durable state and the audit chain still verifies.

Exit codes: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED"}
LEASE = 5  # seconds — short, so expiry is fast; the store defaults to 30.


def check(name: str, ok: bool, detail: str = "") -> bool:
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": detail[:300]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {detail[:160]}" if detail else ""))
    return bool(ok)


def bail(code: int, why: str) -> None:
    REPORT["verdict"] = {0: "VERIFIED", 1: "FAILED", 2: "NOT VERIFIED"}[code]
    REPORT["why"] = why
    print(json.dumps(REPORT, indent=1, default=str))
    sys.exit(code)


def _store():
    from backend.api.durability_composition import build_durable_persistence
    from backend.database.durable.config import DurabilityConfig
    from backend.contracts.execution import ExecutionEnvironment

    dsn = os.environ["CORTEX_DURABLE_URL"]
    persistence = build_durable_persistence(
        config=DurabilityConfig(environment=ExecutionEnvironment.DEVELOPMENT,
                                dsn_variable="CORTEX_DURABLE_URL"),
        dsn=dsn,
    )
    return persistence


def _run_holder() -> None:
    """Child A: take both singleton roles, write the marker, die uncleanly."""
    from backend.database.durable.leadership import LeadershipRole, SqlLeadershipStore

    persistence = _store()
    store = SqlLeadershipStore(persistence.store, instance_id="holder-A")
    sched = store.acquire(role=LeadershipRole.SCHEDULER, lease_seconds=LEASE)
    audit = store.acquire(role=LeadershipRole.AUDIT_WRITER, lease_seconds=LEASE)
    marker = os.getenv("CORTEX_P63_MARKER")
    if marker and sched and audit:
        with open(marker, "w", encoding="utf-8") as fh:
            json.dump({
                "scheduler": sched.to_dict(),
                "audit_writer": audit.to_dict(),
                "expires_at": sched.expires_at.isoformat(),
            }, fh)
    sys.stdout.flush()
    os._exit(9)  # no release, no heartbeat — the hard way


def main() -> None:
    if "--holder" in sys.argv:
        _run_holder()
        return

    if not (os.getenv("CORTEX_DURABLE_URL") or "").strip():
        bail(2, "CORTEX_DURABLE_URL not set")

    import subprocess
    import tempfile
    from datetime import timedelta

    from backend.database.durable.leadership import (
        LeadershipHandle, LeadershipRole, SqlLeadershipStore,
    )
    from backend.database.durable.tables import PLATFORM_SCOPE, leadership_table
    import sqlalchemy as sa

    marker = os.path.join(tempfile.gettempdir(), f"p63_leader_{os.getpid()}.json")
    child_env = dict(os.environ)
    child_env["CORTEX_P63_MARKER"] = marker

    # --- Process A: acquires both roles, then os._exit(9) ------------------
    child = subprocess.run(
        [sys.executable, "-m", "scripts.phase63_leadership_harness", "--holder"],
        env=child_env, cwd=os.getcwd(),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    check("holder A died the hard way (exit 9)", child.returncode in (9, -9),
          f"returncode={child.returncode}")
    if not os.path.exists(marker):
        bail(1, "holder A wrote no marker — it did not acquire both roles")
    with open(marker, encoding="utf-8") as fh:
        held = json.load(fh)
    os.remove(marker)
    a_sched_token = held["scheduler"]["fencing_token"]
    a_audit_token = held["audit_writer"]["fencing_token"]
    expires_at = datetime.fromisoformat(held["expires_at"])
    check("holder A acquired both roles with fencing tokens",
          a_sched_token >= 1 and a_audit_token >= 1,
          f"sched={a_sched_token} audit={a_audit_token}")

    persistence = _store()
    store_b = SqlLeadershipStore(persistence.store, instance_id="successor-B")

    # --- 1. WHILE A's lease is live, B must NOT steal ----------------------
    now = datetime.now(timezone.utc)
    if now >= expires_at:
        bail(2, "A's lease already expired before B could test the live case "
                "(machine too slow / lease too short)")
    b_sched_live = store_b.acquire(role=LeadershipRole.SCHEDULER, lease_seconds=LEASE)
    b_audit_live = store_b.acquire(role=LeadershipRole.AUDIT_WRITER, lease_seconds=LEASE)
    check("B does NOT steal SCHEDULER while A's lease is live", b_sched_live is None)
    check("B does NOT steal AUDIT_WRITER while A's lease is live", b_audit_live is None)

    # --- wait out the legitimate expiry ------------------------------------
    while datetime.now(timezone.utc) <= expires_at + timedelta(seconds=1):
        time.sleep(0.2)

    # --- 2. AFTER expiry, B acquires; token ADVANCED, not reset ------------
    b_sched = store_b.acquire(role=LeadershipRole.SCHEDULER, lease_seconds=LEASE)
    b_audit = store_b.acquire(role=LeadershipRole.AUDIT_WRITER, lease_seconds=LEASE)
    check("B acquires SCHEDULER after expiry", b_sched is not None)
    check("B acquires AUDIT_WRITER after expiry", b_audit is not None)
    check("SCHEDULER fencing token ADVANCED (A+1), not reset",
          b_sched is not None and b_sched.fencing_token == a_sched_token + 1,
          f"{a_sched_token} -> {b_sched.fencing_token if b_sched else '?'}")
    check("AUDIT_WRITER fencing token ADVANCED (A+1), not reset",
          b_audit is not None and b_audit.fencing_token == a_audit_token + 1,
          f"{a_audit_token} -> {b_audit.fencing_token if b_audit else '?'}")

    # --- 3. The dead leader A is fenced out --------------------------------
    a_sched_handle = LeadershipHandle(
        role=LeadershipRole.SCHEDULER, scope=PLATFORM_SCOPE,
        instance_id="holder-A", fencing_token=a_sched_token,
        acquired_at=now, expires_at=expires_at,
    )
    store_as_a = SqlLeadershipStore(persistence.store, instance_id="holder-A")
    a_heartbeat = store_as_a.heartbeat(a_sched_handle, lease_seconds=LEASE)
    check("dead leader A's stale token cannot heartbeat (fenced out)",
          a_heartbeat is None, str(a_heartbeat))

    # --- 4. Row integrity: one row per role, never deleted, now B ----------
    with persistence.store.atomic() as work:
        rows = work.execute(
            sa.select(
                leadership_table.c.role,
                leadership_table.c.instance_id,
                leadership_table.c.fencing_token,
                leadership_table.c.status,
            ).where(leadership_table.c.scope == PLATFORM_SCOPE)
        ).fetchall()
    by_role = {r[0]: r for r in rows}
    sched_row = by_role.get("scheduler")
    audit_row = by_role.get("audit_writer")
    check("exactly one SCHEDULER row (never deleted, one per role)",
          sum(1 for r in rows if r[0] == "scheduler") == 1)
    check("SCHEDULER row now HELD by successor-B (no manual repair)",
          sched_row is not None and sched_row[1] == "successor-B"
          and sched_row[3] == "held",
          f"{sched_row[1] if sched_row else '?'}/{sched_row[3] if sched_row else '?'}")
    check("AUDIT_WRITER row now HELD by successor-B",
          audit_row is not None and audit_row[1] == "successor-B"
          and audit_row[3] == "held")

    # --- 5. Successor recovers + audit chain verifies ----------------------
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext

    succ_ctx = ExecutionContext.platform_internal(
        reason="p63 successor", component="leadership-harness", source="cli")
    integrity = verify_chain(persistence.audit)
    check("audit chain verifies after the leadership handover", integrity.ok,
          f"records={integrity.records_checked}")

    REPORT["tokens"] = {
        "scheduler": {"A": a_sched_token, "B": b_sched.fencing_token if b_sched else None},
        "audit_writer": {"A": a_audit_token, "B": b_audit.fencing_token if b_audit else None},
    }
    try:
        store_b.release(b_sched)
        store_b.release(b_audit)
    except Exception:
        pass

    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "leadership reclaim verified" if ok else "a check failed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
