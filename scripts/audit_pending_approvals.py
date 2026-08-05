"""Report the integrity status of every stashed approval action.

Run this **before** deploying PR-04. Records written by an earlier build carry
no digest, so after the change they will refuse to dispatch. This script names
them so an operator can act deliberately rather than discovering it when an
approval silently does nothing.

    python scripts/audit_pending_approvals.py            # report only
    python scripts/audit_pending_approvals.py --purge    # report, then delete legacy records

Exit codes
----------
0   every pending record verifies
1   one or more records will refuse to dispatch
2   the store could not be read

Purging is opt-in and only ever removes records that *cannot* dispatch anyway.
A legacy record left in place is harmless but permanently stuck; purging clears
it so the operator can re-request approval and get a bound record.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.services.enterprise_approval_integrity import (  # noqa: E402
    IntegrityFailure,
    verify_record,
)

DEFAULT_STORE = REPO_ROOT / "backend" / "data" / "pending_approval_actions.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument(
        "--purge",
        action="store_true",
        help="delete records that cannot dispatch (legacy or unsupported version)",
    )
    args = parser.parse_args()

    if not args.store.exists():
        print(f"No pending-action store at {args.store} — nothing to audit.")
        return 0

    try:
        pending = json.loads(args.store.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - any read failure is fatal here
        print(f"ERROR: could not read {args.store}: {exc}", file=sys.stderr)
        return 2

    if not isinstance(pending, dict) or not pending:
        print("Pending-action store is empty — nothing to audit.")
        return 0

    verified: list[str] = []
    legacy: list[str] = []
    tampered: list[tuple[str, str]] = []

    for workflow_id, record in pending.items():
        verdict = verify_record(workflow_id, record)
        if verdict.ok:
            verified.append(workflow_id)
        elif verdict.failure in {
            IntegrityFailure.LEGACY_UNVERSIONED,
            IntegrityFailure.UNSUPPORTED_VERSION,
        }:
            legacy.append(workflow_id)
        else:
            tampered.append((workflow_id, verdict.reason()))

    print(f"Pending approval records in {args.store}: {len(pending)}\n")
    print(f"  verified, will dispatch : {len(verified)}")
    print(f"  legacy, will refuse     : {len(legacy)}")
    print(f"  integrity failure       : {len(tampered)}")

    if legacy:
        print("\nLegacy records (no digest — re-request approval for these):")
        for workflow_id in legacy:
            print(f"  - {workflow_id}")

    if tampered:
        print("\n*** INTEGRITY FAILURES — investigate before purging anything ***")
        for workflow_id, reason in tampered:
            print(f"  - {workflow_id}: {reason}")

    if args.purge and legacy:
        for workflow_id in legacy:
            pending.pop(workflow_id, None)
        args.store.write_text(json.dumps(pending, indent=2), encoding="utf-8")
        print(f"\nPurged {len(legacy)} legacy record(s).")
        print("Integrity failures were NOT purged — they are evidence.")

    return 1 if (legacy or tampered) else 0


if __name__ == "__main__":
    raise SystemExit(main())
