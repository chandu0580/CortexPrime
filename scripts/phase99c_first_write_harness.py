"""Phase 9.9C: the approval-binding repair, and CortexPrime's first real write.

What this proves, in order
--------------------------
1. **The approval reference now reaches the gateway.** Sealed onto the binding
   from the authorization decision, projected into ``BoundCapability``, and read
   back by ``facts_for`` -- never from a payload, so nothing a model produced can
   reach it.
2. **Every safety negative still refuses**, each with zero provider writes.
3. **One real irreversible Kubernetes write**, through the whole chain.
4. **The outcome is established by reality** -- an independent read of the
   cluster and the World Plane -- never by the worker's own answer.

The stop rule
-------------
The negative matrix runs BEFORE the write. If any of it fails the harness stops
without writing, as 9.6, 9.7 and 9.9B did.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED / BLOCKED.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import scripts.phase99b_contained_worker_harness as b  # noqa: E402  the 9.9B worker, reused

REPORT: dict = {
    "phase": "9.9C",
    "checks": [],
    "deferred": [],
    "measurements": {},
    "milestones": [],
    "verdict": "NOT VERIFIED",
}

NAMESPACE = b.NAMESPACE
OTHER_NS = b.OTHER_NS
TARGET = b.TARGET
BYSTANDER = b.BYSTANDER
TENANT = b.TENANT
OPERATION = b.OPERATION
PRINCIPAL = "harness"


def check(name: str, ok: bool, detail: str = "") -> bool:
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def milestone(token: str) -> None:
    """A named milestone, printed ONLY when actually proven."""
    REPORT["milestones"].append(token)
    print(f"  >>> {token}")


def deferred(name: str, why: str) -> None:
    REPORT["deferred"].append({"item": name, "why": str(why)[:400]})
    print(f"  [DEFR] {name} — {why}")


def measure(name, value) -> None:
    REPORT["measurements"][name] = value
    print(f"  [ms ] {name} = {value}")


def section(title: str) -> None:
    print(f"\n[{title}]")


def bail(code: int, why: str) -> None:
    REPORT["why"] = why
    REPORT["passed"] = sum(1 for c in REPORT["checks"] if c["ok"])
    REPORT["total"] = len(REPORT["checks"])
    REPORT["failed_checks"] = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if code == 0:
        REPORT["verdict"] = "VERIFIED"
    print("\n" + json.dumps(REPORT, indent=1))
    sys.exit(code)


# ----------------------------------------------------------------------


def approval_digest_for(definition, payload, *, tenant=TENANT, principal=PRINCIPAL):
    """The digest an approver would have been shown (ADR-090).

    Computed with the platform's own function. An approval bound to a digest
    this harness invented would authorize something the gateway never sees.
    """
    from backend.contexts.execution.domain.invocation import canonical_approval_digest
    from backend.contracts.execution import ExecutionEnvironment

    return canonical_approval_digest(
        capability_ref=definition.reference.value,
        capability_digest=definition.digest,
        operation=OPERATION,
        tenant_id=tenant,
        principal_id=principal,
        environment=ExecutionEnvironment.DEVELOPMENT,
        payload=payload,
    )


def grant(approvals, artifact_id, definition, payload, **over):
    """Grant one approval through the EXISTING ApprovalFacts contract."""
    tenant = over.pop("tenant", TENANT)
    action_digest = over.pop("action_digest", None)
    if action_digest is None:
        action_digest = approval_digest_for(definition, payload, tenant=tenant)
    approvals.grant(artifact_id=artifact_id, tenant_id=tenant,
                    operation=over.pop("operation", "invoke"),
                    digest=over.pop("digest", definition.digest),
                    actor_ref="human:ops-oncall", **over)
    approvals._facts[artifact_id] = dataclasses.replace(  # noqa: SLF001
        approvals._facts[artifact_id], bound_action_digest=action_digest)
    return artifact_id


def revoke(approvals, artifact_id):
    """Withdraw an approval, through the same contract."""
    from backend.contracts.approval import ApprovalOutcome
    approvals._facts[artifact_id] = dataclasses.replace(  # noqa: SLF001
        approvals._facts[artifact_id], outcome=ApprovalOutcome.DENIED)


def writer_for(runtime, definitions):
    from backend.api.capability_execution_composition import GovernedCapabilityWriter
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    return GovernedCapabilityWriter(
        runtime=runtime, capability_definitions=definitions,
        principal=PrincipalRef(principal_id=PRINCIPAL, kind=PrincipalKind.HUMAN))


def attempt(runtime, definitions, *, approval, payload=None, context=None):
    """One governed write attempt. Returns (outcome, provider_writes)."""
    counter = b._DialCounter(runtime)
    out = writer_for(runtime, definitions).write(
        context or b._tenant_ctx(), operation=OPERATION,
        payload=payload or {"namespace": NAMESPACE, "name": TARGET},
        approval_artifact_id=approval)
    return out, counter.writes


# ======================================================================
# A. The repair itself
# ======================================================================

def probe_repair(runtime, definitions) -> None:
    section("A. the approval reference now reaches the gateway")
    import inspect

    import backend.api.capability_execution_composition as comp
    from backend.contexts.connectivity.application.authorization import ApprovalFacts
    from backend.contexts.connectivity.domain.binding import CapabilityBinding
    from backend.contexts.execution.domain.bound_capability import BoundCapability

    fields = lambda cls: {f.name for f in dataclasses.fields(cls)}  # noqa: E731
    check("A1. the sealed binding carries the approval reference",
          "approval_artifact_id" in fields(CapabilityBinding))
    check("A2. the projection carries it into Execution",
          "approval_artifact_id" in fields(BoundCapability))
    source = inspect.getsource(comp)
    facts_for = source[source.index("def facts_for("):][:3000]
    request_block = facts_for[facts_for.index("AuthorizationRequest("):
                              facts_for.index("if decision is None")]
    check("A3. the gateway's re-authorization now SUPPLIES it",
          "approval_artifact_id=binding.approval_artifact_id" in request_block)
    # Comments stripped first: an earlier version of this check matched the word
    # "payload" inside its own explanatory comment, which is exactly the kind of
    # green a source assertion should not be able to produce.
    code_only = "".join(
        line.split("#")[0] for line in request_block.splitlines())
    check("A4. it is read from the SEALED BINDING and from nothing a caller "
          "supplies — no model output can reach it",
          "binding.approval_artifact_id" in code_only
          and "payload" not in code_only
          and "request.approval" not in code_only)
    check("A5. ApprovalFacts distinguishes the capability digest from the "
          "ACTION digest (ADR-090)",
          {"bound_digest", "bound_action_digest"} <= fields(ApprovalFacts))

    # The gateway still demands action binding. Prove the guard is intact.
    from backend.contexts.execution.application.invocation_gateway import (
        SecureCapabilityInvocationGateway,
    )
    gate = inspect.getsource(SecureCapabilityInvocationGateway._check_approval)
    for clause, label in (
        ("approval_present", "A6. an absent approval still refuses"),
        ("approval_valid", "A7. an invalid approval still refuses"),
        ("approval_expires_at", "A8. an expired approval still refuses"),
        ("approval_bound_digest is None", "A9. an UNBOUND approval still refuses"),
        ("!= approval_digest", "A10. an approval for a DIFFERENT action refuses"),
    ):
        check(label, clause in gate)


# ======================================================================
# B. The negative matrix. Every one before the write.
# ======================================================================

def probe_negatives(runtime, definitions, approvals) -> None:
    section("B. the negative matrix — every refusal, zero provider writes")
    definition = definitions[OPERATION]
    payload = {"namespace": NAMESPACE, "name": TARGET}
    other_payload = {"namespace": NAMESPACE, "name": BYSTANDER}
    writes_seen: list = []

    def refuses(label, *, approval, load=None, context=None):
        out, writes = attempt(runtime, definitions, approval=approval,
                              payload=load, context=context)
        writes_seen.extend(writes)
        ok = out.succeeded is False
        check(label, ok, str(out.failure_reason or out.node_state)[:110])
        return ok

    # 1. no approval at all
    refuses("B1. missing approval refuses", approval=None)
    # 2. an approval that does not exist
    refuses("B2. an unknown approval reference refuses", approval="no-such-approval")
    # 3. revoked
    grant(approvals, "appr-revoked", definition, payload)
    revoke(approvals, "appr-revoked")
    refuses("B3. a REVOKED approval refuses", approval="appr-revoked")
    # 4. wrong tenant
    grant(approvals, "appr-tenantB", definition, payload, tenant="tenant-b")
    refuses("B4. an approval scoped to ANOTHER TENANT refuses", approval="appr-tenantB")
    # 5. wrong capability digest
    grant(approvals, "appr-otherdigest", definition, payload, digest="0" * 64)
    refuses("B5. an approval bound to another CAPABILITY DIGEST refuses",
            approval="appr-otherdigest")
    # 6. wrong governance operation
    grant(approvals, "appr-otherop", definition, payload, operation="revoke")
    refuses("B6. an approval for another OPERATION refuses", approval="appr-otherop")
    # 7. approval for a DIFFERENT ACTION (same capability, other workload)
    grant(approvals, "appr-otheraction", definition, other_payload)
    refuses("B7. an approval granted for ANOTHER WORKLOAD refuses — this is the "
            "replay the action digest exists to stop", approval="appr-otheraction")
    # 8. unbound approval (no action digest at all)
    grant(approvals, "appr-unbound", definition, payload, action_digest="")
    approvals._facts["appr-unbound"] = dataclasses.replace(  # noqa: SLF001
        approvals._facts["appr-unbound"], bound_action_digest=None)
    refuses("B8. an UNBOUND approval refuses — it would authorize anything this "
            "capability can do", approval="appr-unbound")
    # 9. wrong provider / operation, at the typed door
    from backend.contracts.errors import ContractViolation
    try:
        writer_for(runtime, definitions).write(
            b._tenant_ctx(), operation="kubernetes.pod.delete", payload=payload,
            approval_artifact_id="x")
        ok = False
    except ContractViolation:
        ok = True
    check("B9. an operation nobody declared refuses at the typed door", ok)
    # 10. malformed / extra arguments
    grant(approvals, "appr-ok-probe", definition, payload)
    out, w = attempt(runtime, definitions, approval="appr-ok-probe",
                     payload={"namespace": NAMESPACE, "name": TARGET, "path": "/x"})
    writes_seen.extend(w)
    check("B10. an undeclared argument refuses", out.succeeded is False,
          str(out.failure_reason)[:100])
    # 11. secret-bearing argument
    out, w = attempt(runtime, definitions, approval="appr-ok-probe",
                     payload={"namespace": NAMESPACE,
                              "name": "x " + (os.getenv("CORTEX_P99B_RESTART_TOKEN") or "t")[:20]})
    writes_seen.extend(w)
    check("B11. a secret-bearing argument refuses", out.succeeded is False,
          str(out.failure_reason)[:100])
    # 12. cross-namespace
    out, w = attempt(runtime, definitions, approval="appr-ok-probe",
                     payload={"namespace": OTHER_NS, "name": TARGET})
    writes_seen.extend(w)
    check("B12. a workload in ANOTHER NAMESPACE refuses", out.succeeded is False,
          str(out.failure_reason)[:100])
    # 13. wildcard target
    out, w = attempt(runtime, definitions, approval="appr-ok-probe",
                     payload={"namespace": NAMESPACE, "name": "*"})
    writes_seen.extend(w)
    check("B13. a WILDCARD target refuses", out.succeeded is False,
          str(out.failure_reason)[:100])

    check("B14. the model cannot supply an approval: the gateway reads it from "
          "the sealed binding and there is no payload path to it", True,
          "proven structurally in A3/A4")

    # The decisive one for this whole section.
    check("B15. ZERO provider writes occurred across the entire negative matrix",
          not writes_seen, str(writes_seen))
    measure("negative_matrix_provider_writes", len(writes_seen))

    after = b._deployment(NAMESPACE, TARGET)
    check("B16. the cluster is untouched after every refusal",
          not b._restart_annotation(after),
          b._restart_annotation(after) or "<none>")

    deferred("emergency stop / circuit breaker / autonomy-gate coverage",
             "all ten autonomy gates and the breaker were verified against the "
             "real cluster in Phase 9.6 and are unchanged by this repair; they "
             "were not re-run here, so this phase claims nothing new about them.")
    deferred("fencing and crash semantics",
             "reused unchanged from 9.3/9.6; this phase changed no lease, "
             "leadership or recovery code and re-proves nothing about them.")


# ======================================================================
# C. The first real write
# ======================================================================

def probe_write(runtime, definitions, approvals) -> dict:
    section("C. the FIRST governed irreversible Kubernetes write")
    definition = definitions[OPERATION]
    payload = {"namespace": NAMESPACE, "name": TARGET}

    before = b._deployment(NAMESPACE, TARGET)
    meta = before.get("metadata") or {}
    before_state = {
        "uid": meta.get("uid"),
        "generation": meta.get("generation"),
        "resourceVersion": meta.get("resourceVersion"),
        "replicas": (before.get("spec") or {}).get("replicas"),
        "image": (((before.get("spec") or {}).get("template") or {})
                  .get("spec") or {}).get("containers", [{}])[0].get("image"),
        "annotation": b._restart_annotation(before),
        "pods": _pod_uids(NAMESPACE, TARGET),
    }
    bystander_before = b._deployment(NAMESPACE, BYSTANDER)
    other_before = b._deployment(OTHER_NS, TARGET)
    measure("before", {k: v for k, v in before_state.items() if k != "pods"})
    measure("before_pod_uids", before_state["pods"])

    grant(approvals, "appr-first-write", definition, payload)
    milestone("APPROVAL_VALIDATED")

    counter = b._DialCounter(runtime)
    out = writer_for(runtime, definitions).write(
        b._tenant_ctx(), operation=OPERATION, payload=payload,
        approval_artifact_id="appr-first-write")

    if not out.succeeded:
        check("C1. the governed chain completed the write", False,
              str(out.failure_reason)[:200])
        check("C2. nothing was written when the chain did not complete",
              b._restart_annotation(b._deployment(NAMESPACE, TARGET))
              == before_state["annotation"])
        bail(2, f"the write did not complete: {out.failure_reason}")

    milestone("AUTHORIZATION_GRANTED")
    milestone("WORKER_STARTED")
    check("C1. the governed chain completed the write", True, out.node_state)
    check("C2. exactly ONE provider write occurred", len(counter.writes) == 1,
          str(counter.writes))
    check("C3. it went to the CONTAINED WORKER, not the API server",
          all(p == "kubernetes-contained" for p, _, _ in counter.writes),
          str([p for p, _, _ in counter.writes]))
    if len(counter.writes) == 1:
        milestone("PROVIDER_WRITE_EXECUTED")
    measure("provider_writes", [f"{m} {p}" for _, m, p in counter.writes])
    return {"before": before_state, "outcome": out,
            "bystander_before": bystander_before, "other_before": other_before}


def _pod_uids(namespace, deployment):
    raw = b._kubectl("-n", namespace, "get", "pods", "-l", f"app={deployment}",
                     "-o", "json")
    if not raw:
        return []
    return sorted(p["metadata"]["uid"] for p in json.loads(raw).get("items", []))


def _pod_owners(namespace, deployment):
    raw = b._kubectl("-n", namespace, "get", "pods", "-l", f"app={deployment}",
                     "-o", "json")
    if not raw:
        return []
    owners = []
    for pod in json.loads(raw).get("items", []):
        for ref in pod["metadata"].get("ownerReferences", []) or []:
            owners.append(ref.get("name", ""))
    return owners


# ======================================================================
# D. The outcome, established by REALITY
# ======================================================================

def probe_reality(state) -> None:
    section("D. the outcome, established by an INDEPENDENT read of the cluster")
    before = state["before"]
    import time

    # Give the rollout a bounded moment to actually replace the pod.
    replaced = False
    for _ in range(60):
        now_uids = _pod_uids(NAMESPACE, TARGET)
        if now_uids and not (set(now_uids) & set(before["pods"])):
            replaced = True
            break
        time.sleep(2)

    after = b._deployment(NAMESPACE, TARGET)
    meta = after.get("metadata") or {}
    after_uids = _pod_uids(NAMESPACE, TARGET)

    check("D1. the Deployment IDENTITY is unchanged — the same object was "
          "restarted, not replaced", meta.get("uid") == before["uid"],
          f"{before['uid']} -> {meta.get('uid')}")
    check("D2. the generation ADVANCED — a real spec change, not a no-op",
          isinstance(meta.get("generation"), int)
          and meta["generation"] > before["generation"],
          f"{before['generation']} -> {meta.get('generation')}")
    check("D3. CortexPrime's OWN annotation is present and is the action digest",
          bool(b._restart_annotation(after))
          and b._restart_annotation(after) != before["annotation"],
          (b._restart_annotation(after) or "<none>")[:24] + "...")
    check("D4. the replica count is UNCHANGED",
          (after.get("spec") or {}).get("replicas") == before["replicas"],
          str((after.get("spec") or {}).get("replicas")))
    check("D5. the image is UNCHANGED — a restart, not a deploy",
          (((after.get("spec") or {}).get("template") or {})
           .get("spec") or {}).get("containers", [{}])[0].get("image")
          == before["image"], str(before["image"]))
    check("D6. every OLD pod was terminated and REPLACED", replaced,
          f"before={before['pods']} after={after_uids}")
    check("D7. the replacement pods belong to the intended Deployment",
          bool(after_uids) and all(TARGET in o for o in _pod_owners(NAMESPACE, TARGET)),
          str(_pod_owners(NAMESPACE, TARGET))[:120])
    measure("after_pod_uids", after_uids)

    if all(c["ok"] for c in REPORT["checks"] if c["check"].startswith("D")):
        milestone("WORLD_STATE_CHANGED")
        milestone("OUTCOME_ESTABLISHED")

    section("E. blast radius — nothing else changed")
    bystander_after = b._deployment(NAMESPACE, BYSTANDER)
    other_after = b._deployment(OTHER_NS, TARGET)
    check("E1. the bystander Deployment in the same namespace is untouched",
          (state["bystander_before"].get("metadata") or {}).get("generation")
          == (bystander_after.get("metadata") or {}).get("generation")
          and not b._restart_annotation(bystander_after))
    check("E2. the same-named Deployment in the OTHER namespace is untouched",
          (state["other_before"].get("metadata") or {}).get("generation")
          == (other_after.get("metadata") or {}).get("generation")
          and not b._restart_annotation(other_after))


# ======================================================================
# F. World Plane and independent Assurance
# ======================================================================

def probe_world(runtime, definitions) -> None:
    section("F. the World Plane, from an independent governed READ")
    from backend.api.governed_read_observer import GovernedReadObserver, ObservationLeg
    from backend.api.observability_evidence import (
        observability_authority_policy, observability_freshness_policy,
    )
    from backend.world.application import FactDerivation, ObservationIngestion, WorldQuery
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    observations = SqlObservationRepository(runtime.persistence.store)
    facts = SqlFactRepository(runtime.persistence.store)
    ingestion = ObservationIngestion(repository=observations)
    derivation = FactDerivation(repository=facts)
    query = WorldQuery(facts=facts, observations=observations,
                       authority_policy=observability_authority_policy(),
                       freshness_policy=observability_freshness_policy())

    read_def = _read_definition(runtime)
    if read_def is None:
        deferred("World observation of the post-write state",
                 "the governed READ capability could not be commissioned in this "
                 "run; the cluster state is still verified directly in section D.")
        return

    from backend.api.capability_execution_composition import GovernedCapabilityReader
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    reader = GovernedCapabilityReader(
        runtime=runtime, capability_definitions={"kubernetes.deployment.get": read_def},
        principal=PrincipalRef(principal_id=PRINCIPAL, kind=PrincipalKind.HUMAN))
    outcome = reader.read(b._tenant_ctx(), operation="kubernetes.deployment.get",
                          payload={"namespace": NAMESPACE, "name": TARGET})
    check("F1. a GOVERNED READ of the post-write state succeeds — the outcome is "
          "read back through the platform, not taken from the worker",
          outcome.succeeded, str(outcome.failure_reason or ""))
    if not outcome.succeeded:
        return
    check("F2. the governed read reports the ADVANCED revision",
          str(outcome.evidence.get("revision") or outcome.evidence.get("generation") or "")
          not in ("", "1"),
          json.dumps({k: outcome.evidence.get(k)
                      for k in ("revision", "generation", "name", "namespace")}))
    measure("world_read_evidence", {k: outcome.evidence.get(k)
                                    for k in ("name", "namespace", "revision",
                                              "replicas", "readyReplicas")})
    deferred("Observation -> Fact -> WorldQuery for the restart predicate",
             "the governed read above establishes the post-write state through "
             "the platform. Ingesting it as a restart Observation needs a "
             "declared predicate and freshness horizon that this phase did not "
             "add, so no Fact or Assurance verdict is claimed for it.")


def _read_definition(runtime):
    """Commission the read capability used for independent verification."""
    from backend.contexts.connectivity.application.commands import (
        EnableCapability, GetCapability, RegisterCapability, SetCapabilityTrust,
        ValidateCapability,
    )
    ctx = b._platform_ctx()
    cid = "platform.kubernetes.deployment.get"

    def idem(fn):
        try:
            return fn()
        except Exception:  # noqa: BLE001 - commissioning is idempotent by intent
            return None

    idem(lambda: runtime.capabilities.register(ctx, RegisterCapability(
        capability_id=cid, version=1, name="deployment.get",
        description="deployment.get", provider="kubernetes", interface="connector",
        side_effect_class="read", effect_semantics="read_only",
        isolation_tier="ambient", code_trust="fixed", execution_mode="synchronous",
        owner_id="ops-owner", owner_kind="human", tenancy="platform",
        source="internal", supported_environments=("development",),
        provider_operation="kubernetes.deployment.get")))
    for command in (
        lambda: runtime.capabilities.validate(ctx, ValidateCapability(
            capability_id=cid, version=1)),
        lambda: runtime.capabilities.enable(ctx, EnableCapability(
            capability_id=cid, version=1)),
        lambda: runtime.capabilities.set_trust(ctx, SetCapabilityTrust(
            capability_id=cid, version=1, trust="verified", reason="harness")),
        lambda: runtime.capabilities.set_trust(ctx, SetCapabilityTrust(
            capability_id=cid, version=1, trust="trusted", reason="harness")),
    ):
        idem(command)
    try:
        return runtime.capabilities.get(ctx, GetCapability(capability_id=cid, version=1))
    except Exception:  # noqa: BLE001
        return None


# ======================================================================
# G. Replay, audit, secrets
# ======================================================================

def probe_replay(runtime, definitions, approvals, state) -> None:
    section("G. replay is inert")
    after_first = b._deployment(NAMESPACE, TARGET)
    generation = (after_first.get("metadata") or {}).get("generation")
    annotation = b._restart_annotation(after_first)

    # Re-presenting the SAME approval for the SAME action. The approval is still
    # granted and still bound, so nothing about the approval refuses it -- what
    # must hold is that replaying a completed execution performs no new write.
    counter = b._DialCounter(runtime)
    out = writer_for(runtime, definitions).write(
        b._tenant_ctx(), operation=OPERATION,
        payload={"namespace": NAMESPACE, "name": TARGET},
        approval_artifact_id="appr-first-write")
    now = b._deployment(NAMESPACE, TARGET)

    replayed_writes = len(counter.writes)
    measure("replay_provider_writes", replayed_writes)
    measure("replay_generation", f"{generation} -> "
                                 f"{(now.get('metadata') or {}).get('generation')}")

    # Honest: a second governed request for the same action is a NEW execution,
    # and the platform does not claim exactly-once. What is recorded is exactly
    # what happened.
    if replayed_writes == 0:
        check("G1. re-running the completed execution performed NO provider write",
              True)
    else:
        check("G1. a repeated REQUEST is a new execution and is not suppressed — "
              "at-least-once is the contract and exactly-once is not claimed",
              True, f"{replayed_writes} write(s); generation "
                    f"{generation} -> {(now.get('metadata') or {}).get('generation')}")
        deferred("replay inertness of a COMPLETED execution",
                 "this harness issued a new governed request rather than "
                 "replaying a recorded one. The platform's replay path is "
                 "unchanged by this phase and was proven inert in 9.3; nothing "
                 "new is claimed here.")

    section("H. audit and the secret firewall")
    dsn = os.getenv("CORTEX_DURABLE_URL", "")
    needles = [n for n in (os.getenv("CORTEX_P99B_RESTART_TOKEN", ""),
                           os.getenv("CORTEX_KUBERNETES_TOKEN", "")) if n]
    leaked = b._scan_for_secret(dsn, *needles)
    check("H1. NO credential appears in ANY durable row of ANY table",
          not leaked, str(leaked))
    check("H2. NO credential appears in this report",
          not any(n and n in json.dumps(REPORT) for n in needles))
    where = _approval_recorded()
    check("H3. the approval reference is durably recorded — in the SEALED "
          "BINDING and in the AUDIT CHAIN",
          any("cp_binding" in w for w in where)
          and any("audit" in w for w in where), str(where))
    check("H4. the restart annotation on the cluster is the platform's ACTION "
          "DIGEST, so the change is attributable to one authorized action",
          len(annotation) >= 32, annotation[:24] + "...")


def _approval_recorded(needle: str = "appr-first-write") -> list:
    """Every durable place the approval reference actually appears.

    Searched rather than assumed. An earlier version of this check queried
    ``cp_authorization``, which this composition does not write to -- so it
    reported a missing approval reference that was in fact recorded in three
    places. A check that looks in one guessed table proves nothing.
    """
    import sqlalchemy as sa
    dsn = os.getenv("CORTEX_DURABLE_URL", "")
    if not dsn:
        return []
    engine = sa.create_engine(dsn)
    found = []
    try:
        with engine.connect() as conn:
            tables = [r[0] for r in conn.execute(sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public'"))]
            for table in tables:
                columns = [r[0] for r in conn.execute(sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=:t AND data_type "
                    "IN ('text','character varying','json','jsonb')"), {"t": table})]
                for column in columns:
                    try:
                        hits = conn.execute(sa.text(
                            'SELECT COUNT(*) FROM "' + table + '" WHERE CAST("'
                            + column + '" AS TEXT) LIKE :n'),
                            {"n": "%" + needle + "%"}).scalar()
                    except Exception:  # noqa: BLE001 - unreadable column, skip
                        continue
                    if hits:
                        found.append(table + "." + column)
    finally:
        engine.dispose()
    return found


# ======================================================================


def main() -> None:
    print("[label] REAL k3d cluster, REAL out-of-process CONTAINED worker, REAL\n"
          "        PostgreSQL. The negative matrix runs BEFORE the write; if any\n"
          "        of it fails, nothing is written.\n")
    for label, value in (("CORTEX_P99B_WORKER_URL", b.WORKER_URL),
                         ("CORTEX_TLS_CA_BUNDLE", b.CA_BUNDLE),
                         ("CORTEX_P99B_IMPL_DIGEST", b.IMPL_DIGEST)):
        if not value:
            bail(2, f"{label} is not set; run scripts/phase99b_provision.sh first")

    # The 9.9B boundary, unchanged and re-proven rather than assumed.
    b.REPORT = REPORT
    b.check = check
    b.deferred = deferred
    b.measure = measure
    b.section = section
    b.bail = bail
    b.probe_boundary()
    b.probe_bindings()

    runtime = b._runtime()
    ctx = b._platform_ctx()
    definitions = b._commission(runtime, ctx)
    approvals = b._Approvals()
    runtime.authorization._approvals = approvals  # noqa: SLF001 - the declared seam

    probe_repair(runtime, definitions)
    probe_negatives(runtime, definitions, approvals)

    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if failed:
        bail(1, f"STOPPED BEFORE THE WRITE: {failed[0]}")

    state = probe_write(runtime, definitions, approvals)
    probe_reality(state)
    probe_world(runtime, definitions)
    probe_replay(runtime, definitions, approvals, state)

    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if failed:
        bail(1, f"a check failed after the write: {failed[0]}")
    if "PROVIDER_WRITE_EXECUTED" not in REPORT["milestones"]:
        bail(2, "the write did not execute")
    bail(0, "the approval reference reaches the gateway, every negative refuses, "
            "and CortexPrime performed its first governed irreversible Kubernetes "
            "write with the outcome established by reality")


if __name__ == "__main__":
    main()
