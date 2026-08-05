"""Invariant probes whose enforcement lives outside ``platform/``.

Constitution S10 forbids ``platform/`` from importing a bounded context or a
service. Invariant **I2**'s enforcement lives in ``backend.services``, so its
probe cannot live in ``backend.platform.architecture`` -- the architecture suite
would violate the very rule it enforces.

It lives here instead and is injected via
``constitutional_invariants(probes=...)``. That is the difference between an
architecture suite that holds itself to its own rules and one with an exemption
list.

The alternative -- exempting ``invariant_tests.py`` from the platform rule --
was rejected: an exemption granted once to the module that enforces the rules is
the first step in the erosion this suite exists to prevent.
"""

from __future__ import annotations

import copy
import tempfile
from pathlib import Path
from typing import Optional


def probe_i2_approval_binding(_graph) -> Optional[str]:
    """I2 -- no approved action executes with a payload that differs.

    Probes both enforcement layers, so removing either is caught:

    * PR-04 self-consistency -- the payload matches the digest beside it.
    * PR-05 decision binding  -- the artifact matches the digest recorded
      independently at approval time.

    Returns ``None`` when the invariant holds, or a description of the breach.
    """
    from backend.services.enterprise_approval_decision import (
        ApprovalDecisionStore,
        ApprovalFailure,
        HmacApprovalSigner,
    )
    from backend.services.enterprise_approval_integrity import (
        IntegrityFailure,
        build_record,
        record_digest,
        verify_record,
    )

    # -- layer 1: record self-consistency ---------------------------------
    record = build_record("inv-wf", "docker_health_fix", {"container": "web-01"})
    if not verify_record("inv-wf", record).ok:
        return "an untampered record failed verification (false positive)"

    tampered = copy.deepcopy(record)
    tampered["payload"]["container"] = "prod-payments-db"
    verdict = verify_record("inv-wf", tampered)
    if verdict.ok:
        return "a tampered payload passed integrity verification"
    if verdict.failure is not IntegrityFailure.DIGEST_MISMATCH:
        return f"tampering reported as {verdict.failure}, expected DIGEST_MISMATCH"

    stripped = copy.deepcopy(record)
    del stripped["digest"]
    if verify_record("inv-wf", stripped).ok:
        return "a record with no digest passed verification (fail-open)"

    legacy = {"action_type": "docker_health_fix", "payload": {"container": "web-01"}}
    if verify_record("inv-wf", legacy).ok:
        return "a pre-integrity legacy record passed verification (fail-open)"

    # -- layer 2: authoritative decision binding ---------------------------
    with tempfile.TemporaryDirectory() as tmp:
        store = ApprovalDecisionStore(
            Path(tmp) / "decisions.json", signer=HmacApprovalSigner("i" * 32)
        )
        approved = record_digest("inv-wf", "docker_health_fix", {"container": "web-01"})
        store.record_request("inv-wf", "docker_health_fix", approved)
        store.record_grant("inv-wf", "inv-approver", "human")

        if not store.verify_for_execution("inv-wf", approved, "docker_health_fix").ok:
            return "a matching artifact failed decision binding (false positive)"

        forged = record_digest("inv-wf", "docker_health_fix", {"container": "prod-db"})
        forged_verdict = store.verify_for_execution("inv-wf", forged, "docker_health_fix")
        if forged_verdict.ok:
            return "a self-consistent forgery passed decision binding"
        if forged_verdict.failure is not ApprovalFailure.ARTIFACT_MODIFIED:
            return (
                f"forgery reported as {forged_verdict.failure}, expected ARTIFACT_MODIFIED"
            )

        # The platform must never authorize itself.
        store.record_request("inv-self", "docker_health_fix", approved)
        store.record_grant("inv-self", "cortexprime", "platform")
        self_auth = store.verify_for_execution("inv-self", approved, "docker_health_fix")
        if self_auth.ok:
            return "a platform principal authorized an execution"

    return None


#: Probes registered by the test layer, keyed by invariant id.
SERVICE_LEVEL_PROBES = {"I2": probe_i2_approval_binding}
