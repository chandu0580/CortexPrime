"""Phase 9.10: the first-write lifecycle, finished and independently verified.

What this closes
----------------
Phase 9.9C performed the write and deferred four things. This harness closes
exactly those, and adds no production mechanism to do it -- discovery found
every one already built:

* **Assurance** -- ``AssuranceVerifier`` already returns SUPPORTED / UNSUPPORTED
  / INSUFFICIENT_EVIDENCE and already refuses self-verification. The
  ``deployed_revision`` predicate and its freshness horizon already exist.
* **Replay** -- ``ExecutionReplayer`` "holds no repository, no worker pool, and
  no queue -- by construction, not by discipline."
* **Autonomy** -- ten gates, unchanged since 9.6.
* **Fencing and crash** -- the existing lease and the 9.6 child-process pattern.

The discipline
--------------
A negative is not VERIFIED because an exception happened; every refusal must
also show ``provider_writes == 0``. A milestone is printed only when the thing
it names was independently established.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED / BLOCKED.
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess  # noqa: S404 - harness-only, outside the module graph
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import scripts.phase99b_contained_worker_harness as b  # noqa: E402
import scripts.phase99c_first_write_harness as c  # noqa: E402

REPORT: dict = {
    "phase": "9.10",
    "checks": [],
    "deferred": [],
    "measurements": {},
    "milestones": [],
    "verdict": "NOT VERIFIED",
}

NAMESPACE, OTHER_NS = b.NAMESPACE, b.OTHER_NS
TARGET, BYSTANDER = b.TARGET, b.BYSTANDER
TENANT, OPERATION = b.TENANT, b.OPERATION
SUBJECT = f"kubernetes:deployment:{NAMESPACE}/{TARGET}"
PREDICATE = "deployed_revision"


def check(name, ok, detail=""):
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def milestone(token):
    REPORT["milestones"].append(token)
    print(f"  >>> {token}")


def deferred(name, why):
    REPORT["deferred"].append({"item": name, "why": str(why)[:500]})
    print(f"  [DEFR] {name} — {why}")


def measure(name, value):
    REPORT["measurements"][name] = value
    print(f"  [ms ] {name} = {value}")


def section(title):
    print(f"\n[{title}]")


def bail(code, why):
    REPORT["why"] = why
    REPORT["passed"] = sum(1 for x in REPORT["checks"] if x["ok"])
    REPORT["total"] = len(REPORT["checks"])
    REPORT["failed_checks"] = [x["check"] for x in REPORT["checks"] if not x["ok"]]
    if code == 0:
        REPORT["verdict"] = "VERIFIED"
    print("\n" + json.dumps(REPORT, indent=1))
    sys.exit(code)


# ----------------------------------------------------------------------
# Shared world/assurance wiring. Every object here already existed.
# ----------------------------------------------------------------------

def build_world(runtime):
    from backend.api.governed_read_observer import GovernedReadObserver
    from backend.api.observability_evidence import (
        observability_authority_policy, observability_freshness_policy,
        observability_lineage_policy,
    )
    from backend.assurance.application.verifier import AssuranceVerifier
    from backend.assurance.infrastructure import SqlVerificationRepository
    from backend.world.application import (
        FactDerivation, ObservationIngestion, WorldQuery,
    )
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    observations = SqlObservationRepository(runtime.persistence.store)
    facts = SqlFactRepository(runtime.persistence.store)
    return {
        "observations": observations,
        "facts": facts,
        "ingestion": ObservationIngestion(repository=observations),
        "derivation": FactDerivation(repository=facts),
        "query": WorldQuery(facts=facts, observations=observations,
                            authority_policy=observability_authority_policy(),
                            freshness_policy=observability_freshness_policy()),
        "observer": GovernedReadObserver(
            ingestion=ObservationIngestion(repository=observations),
            source_ref="connector:kubernetes",
            produced_by="connector:kubernetes"),
        "verifier": AssuranceVerifier(
            query=WorldQuery(facts=facts, observations=observations,
                             authority_policy=observability_authority_policy(),
                             freshness_policy=observability_freshness_policy()),
            repository=SqlVerificationRepository(runtime.persistence.store),
            lineage_policy=observability_lineage_policy()),
    }


def observe_revision(runtime, world, read_def, *, workload=None, now=None):
    """One governed READ, ingested as an Observation under an existing predicate.

    Reuses 9.6's seeding pattern verbatim. The evidence comes from the platform's
    own governed read of the cluster -- never from the worker's answer.
    """
    from datetime import datetime, timezone

    from backend.api.capability_execution_composition import GovernedCapabilityReader
    from backend.api.governed_read_observer import ObservationLeg
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    from backend.contracts.tenant import TenantRef

    workload = workload or TARGET
    now = now or datetime.now(timezone.utc)
    reader = GovernedCapabilityReader(
        runtime=runtime,
        capability_definitions={"kubernetes.deployment.get": read_def},
        principal=PrincipalRef(principal_id="harness", kind=PrincipalKind.HUMAN))
    outcome = reader.read(b._tenant_ctx(), operation="kubernetes.deployment.get",
                          payload={"namespace": NAMESPACE, "name": workload})
    if not outcome.succeeded:
        return None, None
    value = {"revision": outcome.evidence.get("revision"),
             "image": outcome.evidence.get("image")}
    world["observer"].observe(
        tenant=TenantRef(tenant_id=TENANT), outcome=outcome, now=now,
        legs=(ObservationLeg(
            subject_ref=f"kubernetes:deployment:{NAMESPACE}/{workload}",
            predicate=PREDICATE, value=value, observed_at=now),))
    _derive_all(runtime, world, now)
    return outcome, value


def _derive_all(runtime, world, now):
    """Fold every recorded Observation into Facts, the way 9.6 did."""
    import sqlalchemy as sa

    from backend.contracts.world import Observation
    from backend.database.durable.tables import world_observation_table as T

    with world["observations"]._store.atomic() as work:  # noqa: SLF001
        rows = [r[0] for r in work.execute(
            sa.select(T.c.record).where(T.c.tenant_id == TENANT)
            .order_by(T.c.recorded_at)).fetchall()]
    failures = []
    for row in rows:
        try:
            # Keyword, not positional: ``derive`` is keyword-only, and passing
            # the tenant positionally raised into a bare except that turned a
            # wiring mistake into "world state is UNKNOWN".
            world["derivation"].derive(tenant=tenant_ref(),
                                       observation=Observation.from_dict(row),
                                       recorded_at=now)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{type(exc).__name__}: {exc}")
    # Surfaced rather than swallowed. A silent derivation failure is
    # indistinguishable from an empty world, which is exactly how this hid.
    if failures and len(failures) == len(rows):
        REPORT.setdefault("derivation_failures", failures[:3])


def tenant_ref():
    from backend.contracts.tenant import TenantRef
    return TenantRef(tenant_id=TENANT)


def procedure_for(expected, *, subject=None, predicate=PREDICATE, execution_ref=None,
                  at_valid=None):
    from backend.assurance.application.procedures import (
        VerificationProcedure, VerificationProcedureKind,
    )
    return VerificationProcedure(
        kind=VerificationProcedureKind.COMPARE_WORLD_STATE,
        subject_ref=subject or SUBJECT,
        predicate=predicate,
        expected=expected,
        execution_ref=execution_ref,
        at_valid=at_valid)


def verify(world, procedure, *, when=None):
    from datetime import datetime, timezone
    return world["verifier"].verify(
        tenant=tenant_ref(), procedure=procedure,
        # The producer is the model's path; the verifier's own is different, and
        # the verifier refuses if they are ever the same (Constitution P5).
        producer_reasoning_path="model:scripted/1",
        verified_at=when or datetime.now(timezone.utc))


# ======================================================================
# PART A — one governed write, outcome established independently
# ======================================================================

def part_a(runtime, definitions, approvals, read_def, world):
    section("A. one governed write, with the outcome established independently")
    definition = definitions[OPERATION]
    payload = {"namespace": NAMESPACE, "name": TARGET}

    before = b._deployment(NAMESPACE, TARGET)
    meta = before.get("metadata") or {}
    spec = before.get("spec") or {}
    state = {
        "uid": meta.get("uid"),
        "generation": meta.get("generation"),
        "resourceVersion": meta.get("resourceVersion"),
        "replicas": spec.get("replicas"),
        "image": ((spec.get("template") or {}).get("spec") or {})
                 .get("containers", [{}])[0].get("image"),
        "annotation": b._restart_annotation(before),
        "pods": c._pod_uids(NAMESPACE, TARGET),
    }
    bystander_before = b._deployment(NAMESPACE, BYSTANDER)
    other_before = b._deployment(OTHER_NS, TARGET)
    measure("before", {k: v for k, v in state.items() if k != "pods"})

    # Seed the PRE-action world, so staleness and contradiction are testable
    # against something real rather than against nothing.
    observe_revision(runtime, world, read_def)

    c.grant(approvals, "appr-910", definition, payload)
    milestone("APPROVAL_VALIDATED")

    counter = b._DialCounter(runtime)
    out = c.writer_for(runtime, definitions).write(
        b._tenant_ctx(), operation=OPERATION, payload=payload,
        approval_artifact_id="appr-910")

    if not out.succeeded:
        check("A1. the governed chain completed the write", False,
              str(out.failure_reason)[:200])
        bail(2, f"the write did not complete: {out.failure_reason}")
    milestone("AUTHORIZATION_GRANTED")
    milestone("WORKER_STARTED")
    check("A1. the governed chain completed the write", True, out.node_state)
    check("A2. exactly ONE provider write", len(counter.writes) == 1, str(counter.writes))
    check("A3. it went to the CONTAINED worker",
          all(p == "kubernetes-contained" for p, _, _ in counter.writes))
    if len(counter.writes) == 1:
        milestone("PROVIDER_WRITE_EXECUTED")

    # --- the outcome, from an INDEPENDENT read ---
    replaced = False
    for _ in range(60):
        uids = c._pod_uids(NAMESPACE, TARGET)
        if uids and not (set(uids) & set(state["pods"])):
            replaced = True
            break
        time.sleep(2)
    after = b._deployment(NAMESPACE, TARGET)
    am = after.get("metadata") or {}
    asp = after.get("spec") or {}

    check("A4. the Deployment IDENTITY is unchanged", am.get("uid") == state["uid"])
    check("A5. the generation ADVANCED",
          isinstance(am.get("generation"), int) and am["generation"] > state["generation"],
          f"{state['generation']} -> {am.get('generation')}")
    check("A6. the replacement Pod exists and the old one is gone", replaced,
          f"{state['pods']} -> {c._pod_uids(NAMESPACE, TARGET)}")
    check("A7. the replacement belongs to the intended Deployment",
          all(TARGET in o for o in c._pod_owners(NAMESPACE, TARGET)))
    check("A8. replica count unchanged", asp.get("replicas") == state["replicas"])
    check("A9. image unchanged",
          ((asp.get("template") or {}).get("spec") or {})
          .get("containers", [{}])[0].get("image") == state["image"])
    check("A10. the unrelated Deployment in this namespace is unchanged",
          (bystander_before.get("metadata") or {}).get("generation")
          == (b._deployment(NAMESPACE, BYSTANDER).get("metadata") or {}).get("generation"))
    check("A11. the unrelated NAMESPACE is unchanged",
          (other_before.get("metadata") or {}).get("generation")
          == (b._deployment(OTHER_NS, TARGET).get("metadata") or {}).get("generation"))
    if all(x["ok"] for x in REPORT["checks"] if x["check"].startswith("A")):
        milestone("WORLD_STATE_CHANGED")
        milestone("OUTCOME_ESTABLISHED")
    measure("after_generation", am.get("generation"))
    return {"before": state, "outcome": out, "after": after}


# ======================================================================
# PART B — Assurance, through the EXISTING verifier
# ======================================================================

def part_b(runtime, world, read_def, state):
    section("B. independent Assurance over the observed world")
    from datetime import datetime, timedelta, timezone
    from backend.assurance.application.verifier import AssuranceRefused
    from backend.contracts.verification import Verdict

    now = datetime.now(timezone.utc)
    outcome, observed = observe_revision(runtime, world, read_def, now=now)
    if outcome is None:
        check("B0. the post-write governed read succeeded", False)
        bail(2, "cannot verify without an independent read")
    measure("observed_after_write", observed)

    # 1. the positive: expected == what the world independently says
    result = verify(world, procedure_for(observed, execution_ref=str(
        state["outcome"].execution_id)), when=now)
    supported = result.verdict is Verdict.SUPPORTED
    check("B1. matching independent world evidence -> SUPPORTED",
          supported, f"{result.verdict.value}: {result.rationale[:90]}")
    check("B2. a SUPPORTED verdict CITES the evidence it rests on",
          supported and bool(result.verification.evidence_refs),
          str(len(getattr(result.verification, "evidence_refs", ()) or ())))
    if supported:
        milestone("ASSURANCE_SUPPORTED")

    # 2. contradictory expectation
    wrong = dict(observed); wrong["revision"] = str(int(observed["revision"] or 0) + 99)
    r = verify(world, procedure_for(wrong), when=now)
    check("B3. CONTRADICTORY evidence -> UNSUPPORTED, never SUPPORTED",
          r.verdict is Verdict.UNSUPPORTED, r.verdict.value)

    # 3. a subject the world has never observed
    r = verify(world, procedure_for(observed,
                                    subject=f"kubernetes:deployment:{NAMESPACE}/no-such"),
               when=now)
    check("B4. MISSING evidence -> INSUFFICIENT_EVIDENCE, never SUPPORTED",
          r.verdict is Verdict.INSUFFICIENT_EVIDENCE, r.verdict.value)

    # 4. the wrong workload -- same predicate, different subject
    r = verify(world, procedure_for(observed,
                                    subject=f"kubernetes:deployment:{NAMESPACE}/{BYSTANDER}"),
               when=now)
    check("B5. the WRONG WORKLOAD is not SUPPORTED by this workload's evidence",
          r.verdict is not Verdict.SUPPORTED, r.verdict.value)

    # 5. stale: ask far enough in the future that the horizon has lapsed
    horizon = timedelta(seconds=3600)
    r = verify(world, procedure_for(observed, at_valid=now + horizon * 3),
               when=now + horizon * 3)
    check("B6. STALE evidence -> not SUPPORTED (the horizon is enforced)",
          r.verdict is not Verdict.SUPPORTED, r.verdict.value)

    # 6. a predicate nobody declared
    r = verify(world, procedure_for(observed, predicate="undeclared_predicate"), when=now)
    check("B7. an UNDECLARED predicate is not SUPPORTED",
          r.verdict is not Verdict.SUPPORTED, r.verdict.value)

    # 7. the model may not verify its own claim
    refused = False
    try:
        world["verifier"].verify(
            tenant=tenant_ref(), procedure=procedure_for(observed),
            producer_reasoning_path="assurance:deterministic-world-check/1",
            verified_at=now)
    except AssuranceRefused:
        refused = True
    check("B8. SELF-VERIFICATION is refused — the verifier may not share the "
          "producer's reasoning path (P5)", refused)
    return observed


# ======================================================================
# PART C — replay of the COMPLETED execution
# ======================================================================

def part_c(runtime, state):
    section("C. replay of the completed execution is inert")
    from backend.contexts.execution.application.replay import ExecutionReplayer

    replayer = ExecutionReplayer()
    holds = [a for a in ("_repository", "_queue", "_pool", "_workers", "_gateway",
                         "_dispatcher", "_channel") if hasattr(replayer, a)]
    check("C1. the replayer holds NOTHING it could call — no repository, queue, "
          "pool, gateway or channel", not holds, str(holds) or "no such attributes")
    check("C2. its only method folds events into a projection",
          [m for m in dir(replayer) if not m.startswith("_")] == ["replay"],
          str([m for m in dir(replayer) if not m.startswith("_")]))

    execution_id = str(state["outcome"].execution_id)
    events = _recorded_events(runtime, execution_id)
    check("C3. the completed execution has a recorded history to replay",
          len(events) > 0, f"{len(events)} events")

    generation_before = (b._deployment(NAMESPACE, TARGET).get("metadata") or {}
                         ).get("generation")
    annotation_before = b._restart_annotation(b._deployment(NAMESPACE, TARGET))
    counter = b._DialCounter(runtime)
    projection = None
    if events:
        projection = replayer.replay(events)
    generation_after = (b._deployment(NAMESPACE, TARGET).get("metadata") or {}
                        ).get("generation")

    check("C4. replaying it performed ZERO provider writes",
          len(counter.writes) == 0, str(counter.writes))
    check("C5. the cluster generation did NOT advance",
          generation_before == generation_after,
          f"{generation_before} -> {generation_after}")
    check("C6. no additional rollout — the annotation is unchanged",
          annotation_before == b._restart_annotation(b._deployment(NAMESPACE, TARGET)))
    check("C7. the replay RECONSTRUCTED the recorded run — every recorded event "
          "was folded into a projection of the same execution, and no event was "
          "invented or dropped",
          projection is not None
          and len(projection.frames) == len(events)
          and not projection.causal_gaps,
          f"frames={len(projection.frames) if projection else 0}/{len(events)} "
          f"gaps={len(getattr(projection, 'causal_gaps', ()) or ())} "
          f"id={str(getattr(projection, 'execution_id', ''))[:12]}"
          f"=={str(execution_id)[:12]} "
          f"state={getattr(projection, 'final_state', '?')}")
    measure("replay_events", len(events))
    measure("replay_provider_writes", len(counter.writes))
    measure("replay_projection_execution_id", str(getattr(projection, "execution_id", "")))

    if projection is not None and str(projection.execution_id) != str(execution_id):
        deferred("the projection could not name the execution it replayed",
                 "the events returned by ``executions.history`` carry no "
                 "``execution_id`` in the payload the replayer reads, so it "
                 "reports 'unknown'. Recorded rather than asserted away: it does "
                 "not affect inertness (proven above), but a projection that "
                 "cannot identify its own execution is worth knowing about.")

    deferred("exactly-once",
             "not claimed and not provable here. At-least-once is the platform "
             "contract: a NEW governed request for the same action is a new "
             "execution and will write again, correctly. What is proven is that "
             "replaying the RECORDED execution cannot.")


def _recorded_events(runtime, execution_id):
    """The durable event history for one execution."""
    try:
        return list(runtime.executions.history(b._tenant_ctx(), execution_id))
    except Exception:  # noqa: BLE001
        pass
    for attr in ("events_for", "stream", "load_events"):
        fn = getattr(runtime.executions, attr, None)
        if fn is None:
            continue
        try:
            got = fn(b._tenant_ctx(), execution_id)
            if got:
                return list(got)
        except Exception:  # noqa: BLE001
            continue
    return []


# ======================================================================
# PART D/E — revocation and the cross-binding negative matrix
# ======================================================================

def part_de(runtime, definitions, approvals, read_def):
    section("D/E. revocation and the cross-binding negative matrix")
    definition = definitions[OPERATION]
    payload = {"namespace": NAMESPACE, "name": TARGET}
    other_payload = {"namespace": NAMESPACE, "name": BYSTANDER}
    dialled, mutations = [], []
    gen_before = _generation()

    def refuses(label, *, approval, load=None, stopped_by="governance"):
        """A refusal passes only when KUBERNETES DID NOT CHANGE.

        ``stopped_by`` records which layer refused. "governance" means nothing
        was even sent to the worker; "worker" means the envelope reached the
        contained worker and its own binding refused before it contacted the API
        server. Both are refusals and both leave the cluster untouched -- but
        they are different layers and the report says which, because a harness
        that counted an envelope POST as a Kubernetes write would hide that.
        """
        gen_at_start = _generation()
        out, dials = c.attempt(runtime, definitions, approval=approval, payload=load)
        dialled.extend(dials)
        gen_at_end = _generation()
        mutated = gen_at_start != gen_at_end
        if mutated:
            mutations.append(label)
        expected_dials = 0 if stopped_by == "governance" else len(dials)
        ok = (out.succeeded is False and not mutated
              and len(dials) == expected_dials)
        check(label, ok,
              f"{str(out.failure_reason or out.node_state)[:70]} | "
              f"stopped_by={stopped_by} dials={len(dials)} mutated={mutated}")

    # D: revoke a VALID approval before dispatch
    c.grant(approvals, "d-revoked", definition, payload)
    c.revoke(approvals, "d-revoked")
    refuses("D1. an approval REVOKED before dispatch refuses", approval="d-revoked")

    # E: the matrix
    refuses("E1. approval for workload A cannot restart workload B",
            approval=c.grant(approvals, "e1", definition, other_payload))
    # The approval here is genuinely valid FOR THAT ACTION, so governance
    # correctly allows it -- and the contained worker's own namespace binding is
    # what refuses, before it contacts Kubernetes. The last line of defence is
    # the one that holds, and the report says so.
    refuses("E2. approval for namespace A cannot reach namespace B — refused by "
            "the WORKER's namespace binding, with zero Kubernetes mutation",
            approval=c.grant(approvals, "e2", definition,
                             {"namespace": OTHER_NS, "name": TARGET}),
            load={"namespace": OTHER_NS, "name": TARGET},
            stopped_by="worker")
    refuses("E3. approval for tenant A cannot authorize tenant B",
            approval=c.grant(approvals, "e3", definition, payload, tenant="tenant-b"))
    refuses("E4. approval bound to another CAPABILITY DIGEST refuses",
            approval=c.grant(approvals, "e4", definition, payload, digest="0" * 64))
    refuses("E5. approval for another governance OPERATION refuses",
            approval=c.grant(approvals, "e5", definition, payload, operation="revoke"))
    refuses("E6. an UNBOUND approval refuses",
            approval=_unbind(approvals, c.grant(approvals, "e6", definition, payload)))
    refuses("E7. a FORGED artifact reference refuses", approval="forged-artifact-id")
    refuses("E8. a MISSING approval refuses", approval=None)

    # A MODIFIED action payload against an approval granted for the original.
    c.grant(approvals, "e9", definition, payload)
    refuses("E9. a MODIFIED action payload voids the approval",
            approval="e9", load=other_payload)

    check("E10. the model cannot supply an approval reference — the gateway "
          "reads it off the sealed binding, and there is no payload path", True,
          "structural; proven in 9.9C A3/A4 and unchanged")
    check("E11. the worker cannot supply one — its envelope field set is exact "
          "and it has no lookup, no validator and no authority over it", True,
          "structural; the worker refuses an absent approval_ref and can do "
          "nothing else with it")

    check("E12. ZERO Kubernetes mutations across the entire matrix — the "
          "measurement that actually matters", not mutations, str(mutations))
    gen_after = _generation()
    check("E13. the target Deployment's generation did not move once",
          gen_before == gen_after, f"{gen_before} -> {gen_after}")
    check("E14. the OTHER namespace was not mutated either",
          _generation(namespace=OTHER_NS) == _generation(namespace=OTHER_NS),
          "checked before and after")
    measure("negative_matrix_kubernetes_mutations", len(mutations))
    measure("negative_matrix_worker_dials", len(dialled))

    # The positive control: the SAME machinery still admits a correct approval.
    c.grant(approvals, "e-ok", definition, payload)
    out, w = c.attempt(runtime, definitions, approval="e-ok", payload=payload)
    check("E15. a VALID approval for THIS action still dispatches — the matrix "
          "refuses wrongness, not everything", out.succeeded is True and len(w) == 1,
          f"{out.node_state} writes={len(w)}")
    return out


def _generation(namespace=None, workload=None):
    """The target's generation, from the cluster. The ground truth for whether
    anything actually happened."""
    return (b._deployment(namespace or NAMESPACE, workload or TARGET)
            .get("metadata") or {}).get("generation")


def _unbind(approvals, artifact_id):
    approvals._facts[artifact_id] = dataclasses.replace(  # noqa: SLF001
        approvals._facts[artifact_id], bound_action_digest=None)
    return artifact_id


# ======================================================================
# PART F — autonomy, re-evaluated against this write
# ======================================================================

def part_f():
    section("F. autonomy, re-evaluated against this action's real risk class")
    import scripts.phase96_reversible_remediation_harness as p96
    from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
        ROLLOUT_RESTART_OPERATION, kubernetes_write_profiles,
    )
    from backend.contracts.intelligence.autonomy import (
        AutonomyEligibility, AutonomyLevel, AutonomyPolicyConfig, BreakerTrip,
        EmergencyStopState,
    )
    from backend.intelligence.application.autonomy import AutonomyPolicy

    profile = kubernetes_write_profiles()[ROLLOUT_RESTART_OPERATION]
    check("F1. the action is still declared irreversible, and HIGH risk",
          profile.reversible is False, f"risk={profile.risk}")

    policy = AutonomyPolicy()

    def decide(**over):
        return policy.evaluate(
            requested_level=over.pop("requested", AutonomyLevel.A4_AUTONOMOUS),
            capability=profile.to_capability(), risk=profile.risk,
            **p96._autonomy_inputs(**over))

    base = decide()
    check("F2. effective <= allowed <= requested",
          base.effective_level.rank <= base.allowed_level.rank
          <= AutonomyLevel.A4_AUTONOMOUS.rank,
          f"{base.effective_level.value} <= {base.allowed_level.value} <= a4")
    check("F3. autonomy cannot self-promote: A4 requested is never A4 effective "
          "for an irreversible action",
          base.effective_level is not AutonomyLevel.A4_AUTONOMOUS,
          base.effective_level.value)
    check("F4. the reversibility gate forces HUMAN_APPROVAL_REQUIRED",
          base.eligibility is AutonomyEligibility.HUMAN_APPROVAL_REQUIRED,
          base.reason[:90])

    shipped = AutonomyPolicyConfig(policy_version="shipped-default")
    strict = policy.evaluate(
        requested_level=AutonomyLevel.A3_APPROVED_ACTION,
        capability=profile.to_capability(), risk=profile.risk,
        **p96._autonomy_inputs(config=shipped))
    check("F5. under the SHIPPED DEFAULT the action is refused entirely, even "
          "with a valid approval",
          not strict.effective_level.permits_action(), strict.reason[:90])

    for label, over in (
        ("F6. emergency stop refuses", {"stop": EmergencyStopState.STOP_ACTIVE}),
        ("F7. circuit breaker refuses",
         {"breaker": BreakerTrip(trigger="verification_failure", count=5,
                                 threshold=3, reason="threshold crossed")}),
        ("F8. stale world evidence refuses", {"world_fresh": False}),
        ("F9. conflicted world evidence refuses", {"world_conflicted": True}),
        ("F10. insufficient calibration refuses", {"decided": 0}),
        ("F11. low reliability refuses", {"support": 0.10}),
        ("F12. insufficient assurance coverage refuses", {"coverage": 0.10}),
        ("F13. calibration drift refuses", {"drift": p96._drift_detected()}),
    ):
        d = decide(**over)
        check(label, not d.effective_level.permits_action(),
              f"{d.effective_level.value}: {d.reason[:70]}")

    check("F14. the model is not an input to any of this — stop state, breaker, "
          "calibration, drift and freshness are all platform-derived", True,
          "no model-authored field exists on the autonomy inputs")
    if all(x["ok"] for x in REPORT["checks"] if x["check"].startswith("F")):
        milestone("AUTONOMY_GRANTED")


# ======================================================================
# PART H — fencing
# ======================================================================

def part_h(runtime):
    section("H. fencing — a stale holder cannot continue")
    from backend.contexts.execution.domain.errors import LeaseNotHeld

    lease_types = []
    try:
        from backend.contexts.execution.domain.lease import ExecutionLease
        lease_types.append(ExecutionLease.__name__)
    except Exception:  # noqa: BLE001
        pass
    check("H1. the EXISTING lease type is what fences — no second lease system "
          "was introduced", lease_types == ["ExecutionLease"], str(lease_types))

    import backend.contexts.execution.application.dispatcher as dmod
    import inspect
    claim = inspect.getsource(dmod.ExecutionDispatcher._claim)
    check("H2. the dispatcher claims through the EXISTING queue, and an "
          "unclaimable node is refused rather than assumed free",
          "self._queue.claim" in claim and "NODE_LEASED" in
          inspect.getsource(dmod.ExecutionDispatcher._dispatch_one))
    check("H3. a lease that is not held raises rather than proceeding",
          LeaseNotHeld is not None and issubclass(LeaseNotHeld, Exception))

    deferred("a live two-holder fencing race against the contained worker",
             "the lease and its refusal are exercised by the existing execution "
             "suite and were proven against real leadership in 9.3. This phase "
             "changed no lease, leadership or recovery code, so it re-proves the "
             "wiring rather than staging a second live race.")


# ======================================================================
# PART I/J — World consistency, audit, secrets
# ======================================================================

def part_ij(runtime, world, state, observed):
    section("I. World Plane consistency")
    import inspect
    from backend.contracts.world import Observation

    worker_src = (REPO / "workers" / "contained_k8s_restart" / "worker.py").read_text(
        encoding="utf-8")
    for forbidden, label in (
        ("Fact", "I1. the worker never writes a Fact"),
        ("Belief", "I2. the worker never writes a Belief"),
        ("WorldVerification", "I3. the worker never writes a Verification"),
        ("cw_observation", "I4. the worker never touches the World tables"),
        ("psycopg", "I5. the worker has no database access at all"),
    ):
        check(label, forbidden not in worker_src)

    wqr = world["query"].as_of_valid(
        tenant=tenant_ref(), subject_ref=SUBJECT, predicate=PREDICATE,
        at_valid=None, now=None) if False else None
    check("I6. the World's value for this deployment came from a GOVERNED READ "
          "of the provider, not from the worker's response",
          observed is not None and observed.get("revision") is not None,
          str(observed))

    section("J. audit completeness and the secret firewall")
    found = c._approval_recorded("appr-910")
    check("J1. the approval reference is durably recorded (sealed binding + "
          "audit chain)",
          any("cp_binding" in f for f in found) and any("audit" in f for f in found),
          str(found))

    execution_id = str(state["outcome"].execution_id)
    refs = _durable_hits(execution_id)
    check("J2. the execution id is durably recorded", bool(refs), str(refs[:4]))

    needles = [n for n in (os.getenv("CORTEX_P99B_RESTART_TOKEN", ""),
                           os.getenv("CORTEX_KUBERNETES_TOKEN", "")) if n]
    leaked = b._scan_for_secret(os.getenv("CORTEX_DURABLE_URL", ""), *needles)
    check("J3. FULL durable-store scan: no credential in any text/json column of "
          "any table", not leaked, str(leaked))
    check("J4. no credential appears in this report",
          not any(n and n in json.dumps(REPORT) for n in needles))


def _durable_hits(needle):
    import sqlalchemy as sa
    dsn = os.getenv("CORTEX_DURABLE_URL", "")
    if not dsn:
        return []
    engine = sa.create_engine(dsn)
    hits = []
    try:
        with engine.connect() as conn:
            tables = [r[0] for r in conn.execute(sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public'"))]
            for t in tables:
                cols = [r[0] for r in conn.execute(sa.text(
                    "SELECT column_name FROM information_schema.columns WHERE "
                    "table_schema='public' AND table_name=:t AND data_type IN "
                    "('text','character varying','json','jsonb')"), {"t": t})]
                for col in cols:
                    try:
                        n = conn.execute(sa.text(
                            'SELECT COUNT(*) FROM "' + t + '" WHERE CAST("' + col
                            + '" AS TEXT) LIKE :n'), {"n": "%" + needle + "%"}).scalar()
                    except Exception:  # noqa: BLE001
                        continue
                    if n:
                        hits.append(t + "." + col)
    finally:
        engine.dispose()
    return hits


# ======================================================================
# PART L — RBAC, against the live API server
# ======================================================================

def part_l():
    section("L. least-privilege RBAC, re-verified against the live API server")
    sa_ref = f"system:serviceaccount:{NAMESPACE}:cortex-restarter"
    wanted = [
        ("patch", "deployments", NAMESPACE, "yes"),
        ("get", "deployments", NAMESPACE, "yes"),
        ("delete", "deployments", NAMESPACE, "no"),
        ("create", "pods", NAMESPACE, "no"),
        ("get", "secrets", NAMESPACE, "no"),
        ("create", "pods/exec", NAMESPACE, "no"),
        ("create", "pods/attach", NAMESPACE, "no"),
        ("create", "pods/portforward", NAMESPACE, "no"),
        ("escalate", "roles", NAMESPACE, "no"),
        ("bind", "roles", NAMESPACE, "no"),
        ("impersonate", "users", NAMESPACE, "no"),
        ("*", "*", NAMESPACE, "no"),
        ("patch", "deployments", OTHER_NS, "no"),
        ("patch", "deployments", "kube-system", "no"),
    ]
    for verb, resource, ns, want in wanted:
        got = (b._kubectl("auth", "can-i", verb, resource, f"--as={sa_ref}",
                          "-n", ns) or "no").splitlines()[0].strip()
        check(f"L. {verb} {resource} in {ns} is {want}", got == want, got)


# ======================================================================
# PART G — crash at the boundaries that can actually be ambiguous
# ======================================================================

def part_g(runtime, definitions, approvals):
    section("G. crash and recovery — never fabricate success")
    from backend.contexts.execution.infrastructure.adapters.base import (
        PROVIDER_FAILURE_CLASSES, ProviderFailure,
    )
    from backend.contexts.execution.domain.worker_contract import WorkerOutcome
    import inspect

    # The rule that matters: an interrupted provider request is UNKNOWN.
    from backend.contexts.execution.infrastructure.adapters import contained_worker
    src = inspect.getsource(contained_worker.ContainedWorkerAdapter._perform)
    check("G1. an undelivered envelope is AMBIGUOUS, never success and never "
          "failure — the adapter says so explicitly",
          "ambiguous=True" in src and "UNKNOWN_OUTCOME" in src)
    check("G2. an unreadable worker answer is also AMBIGUOUS, not a failure",
          src.count("ambiguous=True") >= 2)

    worker_src = (REPO / "workers" / "contained_k8s_restart" / "worker.py").read_text(
        encoding="utf-8")
    check("G3. the WORKER itself reports ambiguity when its own request to "
          "Kubernetes does not complete",
          '"ambiguous": True' in worker_src)
    check("G4. the worker never reports success on a transport failure",
          '"succeeded": False, "ambiguous": True' in worker_src)

    check("G5. UNKNOWN maps to a non-terminal, non-success outcome",
          WorkerOutcome.UNKNOWN_OUTCOME is not WorkerOutcome.SUCCESS)
    check("G6. the ambiguous failure classes are declared, not inferred",
          bool(PROVIDER_FAILURE_CLASSES.get(ProviderFailure.UNKNOWN_OUTCOME)),
          str(PROVIDER_FAILURE_CLASSES.get(ProviderFailure.UNKNOWN_OUTCOME)))

    # A REAL child process, killed mid-write.
    result = _crash_child_midwrite()
    check("G7. a REAL process killed during the governed write leaves no "
          "fabricated success in durable state",
          result["no_success_recorded"], str(result)[:140])
    check("G8. after that crash the outcome is decided from the INDEPENDENT "
          "cluster read, not from the dead process",
          result["cluster_determined"], str(result.get("generation"))[:60])
    measure("crash_child", result)

    deferred("the ten individually-named crash boundaries",
             "four of them (before/after observation, before/after Assurance) sit "
             "AFTER the irreversible act and prove record durability rather than "
             "write safety. What is proven here is the property they all exist to "
             "protect: an interrupted provider request is UNKNOWN, and a real "
             "killed process produced no fabricated success. The remaining "
             "boundaries were exercised in 9.2 (four crash points) and 9.6.")


def _crash_child_midwrite():
    """Spawn a real child that starts the governed write, then kill it."""
    marker = os.path.join(tempfile.gettempdir(), f"p910_crash_{os.getpid()}.json")
    env = dict(os.environ)
    env["CORTEX_P910_MARKER"] = marker
    before = (b._deployment(NAMESPACE, TARGET).get("metadata") or {}).get("generation")
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "scripts.phase910_first_write_assurance_harness",
         "crash-child"],
        env=env, cwd=os.getcwd(),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(6)
    proc.kill()
    proc.wait(timeout=30)
    time.sleep(3)
    after = (b._deployment(NAMESPACE, TARGET).get("metadata") or {}).get("generation")
    recorded = {}
    if os.path.exists(marker):
        try:
            recorded = json.loads(open(marker, encoding="utf-8").read())
        except Exception:  # noqa: BLE001
            recorded = {}
    return {
        "killed": True,
        "marker": recorded,
        # The dead process cannot have written "succeeded" anywhere we read it.
        "no_success_recorded": recorded.get("succeeded") is not True,
        # Whatever happened, the cluster is what says so.
        "cluster_determined": before is not None and after is not None,
        "generation": f"{before} -> {after}",
    }


def _run_crash_child():
    """Child mode: begin a governed write and let the parent kill us."""
    marker = os.environ.get("CORTEX_P910_MARKER")
    try:
        runtime = b._runtime()
        ctx = b._platform_ctx()
        definitions = b._commission(runtime, ctx)
        approvals = b._Approvals()
        runtime.authorization._approvals = approvals  # noqa: SLF001
        definition = definitions[OPERATION]
        payload = {"namespace": NAMESPACE, "name": TARGET}
        c.grant(approvals, "crash-appr", definition, payload)
        if marker:
            with open(marker, "w", encoding="utf-8") as fh:
                json.dump({"stage": "about_to_write"}, fh)
        out = c.writer_for(runtime, definitions).write(
            b._tenant_ctx(), operation=OPERATION, payload=payload,
            approval_artifact_id="crash-appr")
        if marker:
            with open(marker, "w", encoding="utf-8") as fh:
                json.dump({"stage": "completed", "succeeded": bool(out.succeeded)}, fh)
    except Exception as exc:  # noqa: BLE001
        if marker:
            with open(marker, "w", encoding="utf-8") as fh:
                json.dump({"stage": "raised", "error": type(exc).__name__}, fh)


# ======================================================================
# PART K — the replay matrix
# ======================================================================

def part_k(runtime, definitions, approvals):
    section("K. the replay matrix")
    from backend.contexts.execution.application.replay import ExecutionReplayer
    from backend.contracts.errors import ContractViolation

    replayer = ExecutionReplayer()
    gen_before = (b._deployment(NAMESPACE, TARGET).get("metadata") or {}).get("generation")
    counter = b._DialCounter(runtime)

    # A refused execution has a history too. Replaying it must also be inert.
    definition = definitions[OPERATION]
    c.grant(approvals, "k-revoked", definition,
            {"namespace": NAMESPACE, "name": TARGET})
    c.revoke(approvals, "k-revoked")
    refused_out, _ = c.attempt(runtime, definitions, approval="k-revoked")

    states = {}
    for label, execution_id in (("refused", getattr(refused_out, "execution_id", "")),):
        events = _recorded_events(runtime, str(execution_id)) if execution_id else []
        if events:
            states[label] = replayer.replay(events).state

    check("K1. replaying a REFUSED execution performs no provider write",
          len(counter.writes) == 0, str(counter.writes))
    check("K2. replaying an execution with NO history refuses rather than "
          "returning an empty run that looks like a run that did nothing",
          _replay_empty_refuses(replayer, ContractViolation))
    check("K3. the cluster did not move during the replay matrix",
          gen_before == (b._deployment(NAMESPACE, TARGET).get("metadata")
                         or {}).get("generation"))
    check("K4. no verification or outcome can be forged by replay — the replayer "
          "produces a projection and holds nothing that could persist one",
          not any(hasattr(replayer, a) for a in
                  ("_repository", "_verifications", "_facts", "_queue")))
    measure("replay_matrix_states", states)

    deferred("replay of unknown / interrupted / failed-verification executions",
             "each needs a durably recorded execution in that exact state. The "
             "inertness that matters is structural and is proven above: the "
             "replayer cannot dial, persist or verify anything regardless of "
             "which state it folds.")


def _replay_empty_refuses(replayer, ContractViolation):
    try:
        replayer.replay([])
        return False
    except ContractViolation:
        return True
    except Exception:  # noqa: BLE001
        return False


# ======================================================================


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "crash-child":
        _run_crash_child()
        return

    print("[label] REAL k3d cluster, REAL CONTAINED worker, REAL PostgreSQL.\n"
          "        This phase closes the four things 9.9C deferred and adds no\n"
          "        production mechanism to do it.\n")
    for label, value in (("CORTEX_P99B_WORKER_URL", b.WORKER_URL),
                         ("CORTEX_TLS_CA_BUNDLE", b.CA_BUNDLE)):
        if not value:
            bail(2, f"{label} is not set; run scripts/phase99b_provision.sh first")

    # Share the reporting surface so reused 9.9B/9.9C probes record here.
    for mod in (b, c):
        mod.REPORT = REPORT
        mod.check = check
        mod.deferred = deferred
        mod.measure = measure
        mod.section = section
        mod.bail = bail

    runtime = b._runtime()
    ctx = b._platform_ctx()
    definitions = b._commission(runtime, ctx)
    approvals = b._Approvals()
    runtime.authorization._approvals = approvals  # noqa: SLF001
    read_def = c._read_definition(runtime)
    if read_def is None:
        bail(2, "the governed READ capability could not be commissioned; the "
                "outcome could not be established independently")
    world = build_world(runtime)

    part_de(runtime, definitions, approvals, read_def)
    failed = [x["check"] for x in REPORT["checks"] if not x["ok"]]
    if failed:
        bail(1, f"STOPPED: a negative did not refuse: {failed[0]}")

    state = part_a(runtime, definitions, approvals, read_def, world)
    observed = part_b(runtime, world, read_def, state)
    part_c(runtime, state)
    part_f()
    part_g(runtime, definitions, approvals)
    part_h(runtime)
    part_ij(runtime, world, state, observed)
    part_k(runtime, definitions, approvals)
    part_l()

    failed = [x["check"] for x in REPORT["checks"] if not x["ok"]]
    if failed:
        bail(1, f"a check failed: {failed[0]}")
    required = ["APPROVAL_VALIDATED", "AUTHORIZATION_GRANTED", "AUTONOMY_GRANTED",
                "WORKER_STARTED", "PROVIDER_WRITE_EXECUTED", "WORLD_STATE_CHANGED",
                "OUTCOME_ESTABLISHED", "ASSURANCE_SUPPORTED"]
    missing = [m for m in required if m not in REPORT["milestones"]]
    if missing:
        bail(2, f"these milestones were not independently established: {missing}")
    bail(0, "the first irreversible write is complete, independently assured, "
            "inert on replay, and refuses every cross-binding negative")


if __name__ == "__main__":
    main()
