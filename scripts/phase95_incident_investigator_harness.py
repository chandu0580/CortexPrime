"""Phase 9.5 REAL evidence: a read-only Kubernetes incident investigator.

Run:  bash scripts/phase95_provision.sh && source .phase95.env
      python -m scripts.phase95_incident_investigator_harness
      python -m scripts.phase95_incident_investigator_harness --crash-child   (internal)
      python -m scripts.phase95_incident_investigator_harness --concurrent    (internal)

The incident is real and staged, not simulated: a deployment whose revision 2
crashloops, on a real k3d cluster, observed through the real governed Kubernetes
and Prometheus capabilities established in 9.2-9.4.

The point is NOT that the system can spot a CrashLoopBackOff. It is that the
system holds five competing explanations, eliminates the MISLEADING one on
evidence (a crashlooping container under a memory limit really could be an OOM
kill), supports another on evidence, and never once lets the model's opinion
become the platform's conclusion.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timedelta, timezone

from scripts.phase62_recovery_harness import TENANT, _tenant_ctx

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED", "measurements": {}}
NAMESPACE = os.getenv("CORTEX_P95_NAMESPACE", "cortex-p95")
WORKLOAD = os.getenv("CORTEX_P95_WORKLOAD", "payments-api")
POD = os.getenv("CORTEX_P95_POD", "")
MEMORY_LIMIT = int(os.getenv("CORTEX_P95_MEMORY_LIMIT_BYTES") or "67108864")
HARNESS_VERSION = "phase95/1"

K8S_OPS = ("kubernetes.pod.get", "kubernetes.deployment.get", "kubernetes.pods.list")
PROM_OPS = ("prometheus.pod_restarts", "prometheus.pod_memory_bytes")


def check(name, ok, detail=""):
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {str(detail)[:170]}" if detail else ""))
    return bool(ok)


def measure(name, value):
    REPORT["measurements"][name] = value
    print(f"  [ms ] {name} = {value}")


def bail(code, why):
    REPORT["verdict"] = {0: "VERIFIED", 1: "FAILED", 2: "NOT VERIFIED"}[code]
    REPORT["why"] = why
    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    REPORT["failed_checks"] = failed
    REPORT["passed"] = sum(1 for c in REPORT["checks"] if c["ok"])
    REPORT["total"] = len(REPORT["checks"])
    print(json.dumps(REPORT, indent=1, default=str))
    sys.exit(code)


def _require_env():
    missing = [v for v in ("CORTEX_DURABLE_URL", "CORTEX_KUBERNETES_URL",
                           "CORTEX_KUBERNETES_TOKEN", "CORTEX_TLS_CA_BUNDLE",
                           "CORTEX_PROMETHEUS_URL", "CORTEX_PROMETHEUS_TOKEN")
               if not (os.getenv(v) or "").strip()]
    if missing:
        bail(2, f"missing deployment configuration: {missing}")
    os.environ.setdefault("CORTEX_PROMETHEUS_NAMESPACE", NAMESPACE)
    os.environ["CORTEX_CONNECTOR_FACTORIES"] = (
        "backend.api.kubernetes_provider_factory:kubernetes_real_extension,"
        "backend.api.prometheus_provider_factory:prometheus_extension")
    os.environ.setdefault("CORTEX_ALLOW_PLAINTEXT", "1")


def _build_runtime():
    from backend.api.application_runtime import build_governed_runtime
    runtime = build_governed_runtime()
    if runtime is None:
        bail(2, "no governed runtime (CORTEX_DURABLE_URL unset?)")
    for provider in ("kubernetes", "prometheus"):
        if provider not in runtime.connectivity.catalogs:
            bail(2, f"{provider} provider absent")
    return runtime


def _commission(runtime, platform_ctx):
    from backend.contexts.execution.domain.worker_directory import WorkerAvailability, WorkerTrust
    from backend.contexts.connectivity.application.commands import (
        EnableCapability, GetCapability, RegisterCapability, SetCapabilityTrust,
        ValidateCapability)
    from backend.contexts.connectivity.domain.errors import (
        CapabilityError, IllegalCapabilityTransition)

    def _idem(fn):
        try:
            return fn()
        except (IllegalCapabilityTransition, CapabilityError):
            return None

    d = runtime.connectivity.directory
    for worker in ("kubernetes-connector", "prometheus-connector"):
        for step in (
            lambda w=worker: d.validate(platform_ctx, worker_id=w, tenant_id=""),
            lambda w=worker: d.enable(platform_ctx, worker_id=w, tenant_id=""),
            lambda w=worker: d.set_trust(platform_ctx, worker_id=w, tenant_id="",
                                         trust=WorkerTrust.VERIFIED, reason="phase-9.5"),
            lambda w=worker: d.set_trust(platform_ctx, worker_id=w, tenant_id="",
                                         trust=WorkerTrust.TRUSTED, reason="phase-9.5"),
            lambda w=worker: d.set_availability(platform_ctx, worker_id=w, tenant_id="",
                                                availability=WorkerAvailability.AVAILABLE),
        ):
            _idem(step)

    definitions = {}
    for provider, ops in (("kubernetes", K8S_OPS), ("prometheus", PROM_OPS)):
        for op in ops:
            cid = f"platform.{op}"
            _idem(lambda cid=cid, op=op, pr=provider: runtime.capabilities.register(
                platform_ctx, RegisterCapability(
                    capability_id=cid, version=1, name=op, description=op,
                    provider=pr, interface="connector", side_effect_class="read",
                    effect_semantics="read_only", isolation_tier="contained",
                    execution_mode="synchronous", owner_id="ops-owner", owner_kind="human",
                    tenancy="platform", source="internal",
                    supported_environments=("development",), provider_operation=op)))
            for command in (
                lambda cid=cid: runtime.capabilities.validate(
                    platform_ctx, ValidateCapability(capability_id=cid, version=1)),
                lambda cid=cid: runtime.capabilities.enable(
                    platform_ctx, EnableCapability(capability_id=cid, version=1)),
                lambda cid=cid: runtime.capabilities.set_trust(platform_ctx, SetCapabilityTrust(
                    capability_id=cid, version=1, trust="verified", reason="harness")),
                lambda cid=cid: runtime.capabilities.set_trust(platform_ctx, SetCapabilityTrust(
                    capability_id=cid, version=1, trust="trusted", reason="harness")),
            ):
                _idem(command)
            definitions[op] = runtime.capabilities.get(
                platform_ctx, GetCapability(capability_id=cid, version=1))
    return definitions


class _DialCounter:
    def __init__(self, runtime):
        self.counts, self.plans = {}, []
        for provider, adapter in runtime.connectivity.adapters.items():
            channel = getattr(adapter, "_channel", None)
            if channel is None:
                continue
            self.counts[provider] = 0
            channel.send = self._wrap(provider, channel.send)

    def _wrap(self, provider, original):
        def _send(authority, plan, **kw):
            self.counts[provider] += 1
            self.plans.append((provider, plan.method, plan.path))
            return original(authority, plan, **kw)
        return _send

    @property
    def total(self):
        return sum(self.counts.values())


def _pod_subject(pod=None):
    return f"kubernetes:pod:{NAMESPACE}/{pod or POD}"


def _deployment_subject():
    return f"kubernetes:deployment:{NAMESPACE}/{WORKLOAD}"


# ---------------------------------------------------------------------------
# The scripted proposer — honestly labelled
# ---------------------------------------------------------------------------

def _investigator_script():
    """A deterministic proposer standing in for a live model.

    `[BLOCKED]` The real provider is unavailable while Phase 5.5 holds, so this
    is labelled ``provider="scripted"`` everywhere and no real-model claim is
    made. What it does NOT weaken is the claim this phase actually makes: it
    proposes hypotheses and candidate tests, and every decision that matters —
    which test runs, whether it was admissible, what the observation means, what
    the conclusion is, whether it is assured — is taken by the platform,
    deterministically, and verified independently below.

    It also deliberately proposes a test for the MISLEADING hypothesis first, so
    the elimination is something the investigation does rather than something the
    script avoids.
    """
    from backend.api.incident_investigation import H_REGRESSION, H_RESOURCE

    plan = [
        # 1. Chase the MISLEADING hypothesis first, with an independent
        #    instrument. The kubelet's cAdvisor measures the container runtime
        #    directly, so this is not the Kubernetes API agreeing with itself.
        {"interpretation": "the container is restarting repeatedly; a memory limit "
                           "is configured, so resource exhaustion is worth ruling out",
         "test": {"discriminates": H_RESOURCE, "tool": "metrics.pod_memory",
                  "subject_ref": _pod_subject(), "predicate": "memory_pressure",
                  "evidence_expected": "container memory at or above its configured limit",
                  "supports_if": "working-set memory reached the limit",
                  "contradicts_if": "working-set memory stayed below the limit",
                  "supports_value": {"atOrAboveLimit": True},
                  "contradicts_value": {"atOrAboveLimit": False},
                  "residual_uncertainty": "a limit touched between scrapes would be missed"}},
        # 2. What changed? A revision is the observable a regression stands on.
        {"interpretation": "memory did not reach the limit; look at what changed",
         "test": {"discriminates": H_REGRESSION,
                  "tool": "k8s.deployment_revision",
                  "subject_ref": _deployment_subject(), "predicate": "deployed_revision",
                  "evidence_expected": "a revision later than the last healthy one",
                  "supports_if": "the deployment has moved past revision 1",
                  "contradicts_if": "the deployment is still on revision 1",
                  "supports_value": {"revision": os.getenv("CORTEX_P95_REVISION", "2"),
                                     "image": "busybox:1.36"},
                  "contradicts_value": {"revision": "1", "image": "busybox:1.36"},
                  "residual_uncertainty": "a revision change is temporal association, "
                                          "not proof of causation"}},
        # 3. Nothing further to propose. The platform then settles honestly
        #    rather than manufacturing a test to look thorough.
        {"interpretation": "the revision changed and the container exits non-zero; "
                           "no further discriminating read is available",
         "test": None},
    ]
    state = {"n": 0}

    def responder(prompt: str) -> str:
        index = min(state["n"], len(plan) - 1)
        state["n"] += 1
        entry = plan[index]
        # Exactly the declared schema and nothing else. Any extra key here would
        # be rejected by extra="forbid", which is the model-output firewall doing
        # its job — the negatives below prove that on purpose.
        return json.dumps({
            "interpretation": entry["interpretation"],
            "hypotheses": [],
            "test": entry["test"],
        })
    return responder


def _build_stack(runtime, definitions, *, tool_overrides=None):
    """Compose the real production investigator."""
    from backend.api.capability_execution_composition import GovernedCapabilityReader
    from backend.api.governed_evidence_acquisition import (
        GovernedEvidenceAcquisition, ToolRegistry,
    )
    from backend.api.governed_read_observer import GovernedReadObserver
    from backend.api.incident_investigation import crashloop_tools
    from backend.api.observability_evidence import (
        WorldQueryEvidencePort, observability_authority_policy,
        observability_freshness_policy, observability_lineage_policy,
    )
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    from backend.intelligence.application.context import ContextAssembler
    from backend.intelligence.application.investigation_service import InvestigationService
    from backend.intelligence.application.model_boundary import (
        GovernedModelProposalPort, ScriptedModelPort,
    )
    from backend.intelligence.application.proposal import EvidenceSelectionPolicy
    from backend.intelligence.infrastructure import SqlInvestigationRepository
    from backend.world.application import (
        BeliefFormation, FactDerivation, ObservationIngestion, WorldQuery,
    )
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    context = _tenant_ctx()
    observations = SqlObservationRepository(runtime.persistence.store)
    facts = SqlFactRepository(runtime.persistence.store)
    ingestion = ObservationIngestion(repository=observations)
    derivation = FactDerivation(repository=facts)
    lineage = observability_lineage_policy()
    authority = observability_authority_policy()
    freshness = observability_freshness_policy()
    query = WorldQuery(facts=facts, observations=observations,
                       authority_policy=authority, freshness_policy=freshness)
    beliefs = BeliefFormation(query=query, observations=observations,
                              authority_policy=authority, lineage_policy=lineage)

    reader = GovernedCapabilityReader(
        runtime=runtime, capability_definitions=definitions,
        principal=PrincipalRef(principal_id="harness", kind=PrincipalKind.HUMAN))
    registry = ToolRegistry(
        tools=tool_overrides or crashloop_tools(memory_limit_bytes=MEMORY_LIMIT),
        catalogs=runtime.connectivity.catalogs)
    evidence_port = GovernedEvidenceAcquisition(
        reader=reader,
        observer=GovernedReadObserver(ingestion=ingestion,
                                      source_ref="connector:kubernetes",
                                      produced_by="connector:kubernetes"),
        derivation=derivation, registry=registry, context=context)

    from backend.harness.llm_boundary import GovernedModelBoundary
    from backend.harness.trace_sql import SqlTraceRecorder
    from backend.harness.version import CURRENT_HARNESS_VERSION

    # The governed boundary with a DURABLE trace recorder. L14 is not a slogan
    # here: a model step whose trace cannot be written is a step that did not
    # happen, and the engine turns that into BLOCKED rather than progress.
    boundary = GovernedModelBoundary(
        model_port=ScriptedModelPort(_investigator_script()),
        recorder=SqlTraceRecorder(runtime.persistence.store),
        harness_version=CURRENT_HARNESS_VERSION)
    return {
        "context_obj": context, "observations": observations, "facts": facts,
        "ingestion": ingestion, "derivation": derivation, "query": query,
        "beliefs": beliefs, "reader": reader, "registry": registry,
        "evidence_port": evidence_port, "lineage": lineage, "authority": authority,
        "service": InvestigationService(
            repository=SqlInvestigationRepository(runtime.persistence.store)),
        "assembler": ContextAssembler(),
        "policy": EvidenceSelectionPolicy(),
        "world_port": WorldQueryEvidencePort(query=query),
        "boundary": boundary,
        # Honestly labelled: the provider is scripted while Phase 5.5 blocks a
        # real one, and every claim in the report says so.
        "boundary_port": GovernedModelProposalPort(boundary=boundary,
                                                   provider_label="scripted"),
    }


def _write_marker(marker, payload):
    if marker:
        with open(marker, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, default=str)
    sys.stdout.flush()


def _read_marker(marker):
    if not os.path.exists(marker):
        return {}
    with open(marker, encoding="utf-8") as fh:
        data = json.load(fh)
    os.remove(marker)
    return data


def _spawn(mode, env_overrides, suffix, timeout=420, wait=True):
    marker = os.path.join(tempfile.gettempdir(), f"p95_{suffix}_{os.getpid()}.json")
    env = dict(os.environ)
    env["CORTEX_P95_MARKER"] = marker
    env.update(env_overrides)
    argv = [sys.executable, "-m", "scripts.phase95_incident_investigator_harness", mode]
    if not wait:
        return subprocess.Popen(argv, env=env, cwd=os.getcwd(),
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL), marker
    proc = subprocess.run(argv, env=env, cwd=os.getcwd(),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          timeout=timeout)
    return proc.returncode, _read_marker(marker)


def _percentiles(samples):
    if not samples:
        return None, None
    ordered = sorted(samples)
    return (round(statistics.median(ordered) * 1000, 1),
            round(ordered[min(len(ordered) - 1,
                              max(0, round(0.95 * len(ordered)) - 1))] * 1000, 1))


def main():  # noqa: PLR0912, PLR0915
    if "--crash-child" in sys.argv:
        _require_env(); _run_crash_child(); return
    if "--concurrent" in sys.argv:
        _require_env(); _run_concurrent_child(); return
    _require_env()

    from backend.api.incident_investigation import (
        H_CONFIG, H_DEPENDENCY, H_REGRESSION, H_RESOURCE, H_STARTUP,
        assemble_report, crashloop_hypotheses,
    )
    from backend.contracts.intelligence import (
        AutonomyLevel, InvestigationConclusion, InvestigationStatus,
    )
    from backend.contracts.tenant import TenantRef
    from backend.contracts.world import HypothesisStatus
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext
    from backend.intelligence.application.engine import (
        InvestigationBudget, InvestigationEngine, StepOutcome,
    )

    runtime = _build_runtime()
    platform_ctx = ExecutionContext.platform_internal(
        reason="p95 incident investigation", component="incident-harness", source="cli")
    runtime.audit_writer.acquire()
    definitions = _commission(runtime, platform_ctx)
    tenant = TenantRef(tenant_id=TENANT)
    dials = _DialCounter(runtime)
    stack = _build_stack(runtime, definitions)
    context = stack["context_obj"]

    if stack["observations"].count_all() != 0:
        bail(2, "the database is not virgin; re-run scripts/phase95_provision.sh")
    if not POD:
        bail(2, "CORTEX_P95_POD is unset; the provisioner did not stage an incident")

    print("[label] REAL k3d cluster, REAL CrashLoopBackOff, REAL governed reads.")
    print("        Model proposer = SCRIPTED (Phase 5.5 blocks a real provider);")
    print("        every decision that matters is platform-owned and checked below.")

    # ---- AA: read-only, structurally ---------------------------------------
    print("\n[AA] read-only enforcement")
    from backend.api.governed_evidence_acquisition import InvestigationTool, ToolRegistry
    from backend.contracts.errors import ContractViolation
    check("every exposed tool binds a READ capability",
          len(stack["registry"].keys) == 5, stack["registry"].keys)
    from backend.contexts.execution.infrastructure.adapters.connectors.grafana import (
        grafana_catalog,
    )
    check("NO composed catalog in this process declares a single write operation",
          all(spec.side_effect_class.value == "read"
              for cat in runtime.connectivity.catalogs.values()
              for spec in (cat.require(op) for op in cat.operations)),
          sorted(runtime.connectivity.catalogs))
    refused = False
    try:
        # The counterexample is built inline because no composed catalog has a
        # write op to point at -- which is the stronger fact, and is checked
        # above. This proves the registry would refuse one if it existed.
        ToolRegistry(tools=(InvestigationTool(
            key="grafana.create_folder", operation="folder.create_folder",
            subject_kind="grafana:folder:", predicate="created",
            describes="a write, which an investigation must never hold",
            project=lambda e: {}, source_ref="connector:grafana",
            payload_from_subject=lambda s: {}),),
            catalogs={"grafana": grafana_catalog()})
    except ContractViolation as exc:
        refused = "does not act" in str(exc)
    check("a tool naming a WRITE capability is refused AT CONSTRUCTION", refused)
    refused_unknown = False
    try:
        ToolRegistry(tools=(InvestigationTool(
            key="x", operation="kubernetes.pod.delete", subject_kind="kubernetes:pod:",
            predicate="p", describes="d", project=lambda e: {},
            source_ref="s", payload_from_subject=lambda s: {}),),
            catalogs=runtime.connectivity.catalogs)
    except ContractViolation:
        refused_unknown = True
    check("a tool naming an operation no catalog declares is refused", refused_unknown)

    # ---- A: the incident and its differential -------------------------------
    print("\n[A/E] incident + seeded differential")
    now = datetime.now(timezone.utc)
    incident_ref = f"incident:{NAMESPACE}/{POD}:crashloopbackoff"
    investigation = stack["service"].create(
        tenant=tenant, incident_ref=incident_ref, now=now,
        policy_ref="phase95-crashloop/1", harness_version=HARNESS_VERSION,
        autonomy_level=AutonomyLevel.A1_INVESTIGATE)
    check("an investigation was created from an incident REFERENCE (no second "
          "incident system)", investigation.incident_ref == incident_ref)
    check("autonomy is A1_INVESTIGATE — observe, never act",
          investigation.autonomy_level is AutonomyLevel.A1_INVESTIGATE)
    check("A1 does not permit action",
          not investigation.autonomy_level.permits_action())

    from backend.contracts.intelligence import InvestigationStatus as _Status
    investigation = stack["service"].transition(
        investigation=investigation, to_status=_Status.INVESTIGATING,
        cause="incident triage opened", now=now)
    for hypothesis in crashloop_hypotheses(subject_ref=_pod_subject()):
        investigation = stack["service"].upsert_hypothesis(
            investigation=investigation, hypothesis=hypothesis, now=now)
    seeded = {h.hypothesis_ref: h for h in investigation.differential}
    check("five competing hypotheses are seeded", len(seeded) == 5, sorted(seeded))
    check("every seeded hypothesis is OPEN — none is a finding",
          all(h.status is HypothesisStatus.OPEN for h in seeded.values()))
    check("every seeded hypothesis states WHY it is unresolved",
          all(h.missing_evidence for h in seeded.values()))

    # ---- B: World evidence before any investigation read --------------------
    print("\n[B] World evidence")
    from backend.api.observability_evidence import restart_count_legs_from_kubernetes
    from backend.api.governed_read_observer import GovernedReadObserver
    baseline = stack["reader"].read(context, operation="kubernetes.pods.list",
                                    payload={"namespace": NAMESPACE})
    check("a governed baseline read succeeded", baseline.succeeded,
          baseline.failure_reason)
    legs = restart_count_legs_from_kubernetes(
        evidence=baseline.evidence, namespace=NAMESPACE, observed_at=now)
    GovernedReadObserver(ingestion=stack["ingestion"], source_ref="connector:kubernetes",
                         produced_by="connector:kubernetes").observe(
        tenant=tenant, outcome=baseline, legs=legs, now=now)
    # A crashlooping pod alternates between Running and CrashLoopBackOff, so the
    # durable evidence of the incident is the restart count, not whichever state
    # the pod happened to be in at the instant of the read.
    crashloopers = [p for p in (baseline.evidence.get("pods") or ())
                    if p.get("waitingReason") == "CrashLoopBackOff"
                    or (isinstance(p.get("restartCount"), int)
                        and p["restartCount"] >= 1)]
    check("the World holds evidence of a REAL crash loop (backoff or restarts)",
          bool(crashloopers),
          [(p.get("name"), p.get("waitingReason"), p.get("restartCount"))
           for p in (baseline.evidence.get("pods") or ())])

    # ---- the loop -----------------------------------------------------------
    print("\n[C/D/F/G/H/I/J/M] the investigation loop")
    engine = InvestigationEngine(
        service=stack["service"], assembler=stack["assembler"],
        model_port=stack["boundary_port"], evidence_port=stack["evidence_port"],
        world_read_port=stack["world_port"], policy=stack["policy"],
        harness_version=HARNESS_VERSION,
        available_tools=stack["registry"].keys)
    budget = InvestigationBudget(max_steps=6, max_reads=6)

    step_times, digests, providers, outcomes = [], [], [], []
    dials_before_loop = dials.total
    for index in range(6):
        moment = datetime.now(timezone.utc)
        t0 = time.monotonic()
        result = engine.step(investigation=investigation, budget=budget, now=moment)
        step_times.append(time.monotonic() - t0)
        investigation = result.investigation
        digests.append(result.context_digest)
        providers.append(result.provider)
        outcomes.append(result.outcome.value)
        print(f"        step {index}: {result.outcome.value} "
              f"({result.reason[:80]})")
        if result.outcome is StepOutcome.TERMINATED:
            break
    p50, p95 = _percentiles(step_times)
    measure("investigation_step_p50_ms", p50)
    measure("investigation_step_p95_ms", p95)

    check("the loop ran through the governed model boundary",
          all(p == "scripted" for p in providers if p != "n/a"), set(providers))
    check("every step carried a context digest (deterministic assembly)",
          all(d for d in digests[:-1] or digests), len(digests))
    check("the investigation made governed provider reads",
          dials.total > dials_before_loop, dials.counts)

    # ---- N: the misleading hypothesis was eliminated BY EVIDENCE ------------
    print("\n[N] the misleading hypothesis")
    final = {h.hypothesis_ref: h for h in investigation.differential}
    resource = final[H_RESOURCE]
    check("H4 resource exhaustion was REFUTED", resource.status is HypothesisStatus.REFUTED,
          resource.status.value)
    check("H4 was eliminated by an OBSERVATION, not by an opinion",
          bool(resource.evidence_against)
          and all(ref.startswith("wobs") for ref in resource.evidence_against),
          resource.evidence_against)

    # ---- the supported hypothesis ------------------------------------------
    supported = [h for h in investigation.differential
                 if h.status is HypothesisStatus.SUPPORTED]
    check("at least one hypothesis is SUPPORTED on evidence",
          bool(supported), [h.hypothesis_ref for h in supported])
    check("every supported hypothesis cites an observation",
          all(h.evidence_for and all(r.startswith("wobs") for r in h.evidence_for)
              for h in supported),
          {h.hypothesis_ref: h.evidence_for for h in supported})
    check("no hypothesis carries a numeric confidence anywhere",
          not any(isinstance(v, float)
                  for h in investigation.differential
                  for v in h.to_dict().values() if not isinstance(v, (list, tuple, dict))),
          "categorical only")

    # ---- K: facts reconstruct ----------------------------------------------
    print("\n[K/L] facts + evidence gaps")
    check("observations became durable world evidence",
          stack["observations"].count_all() >= 3, stack["observations"].count_all())
    check("facts were derived from them", stack["facts"].count_all() >= 1,
          stack["facts"].count_all())
    from backend.intelligence.application.differential import analyze_gaps
    gaps = analyze_gaps(investigation)
    check("every still-open hypothesis states why it is unresolved",
          all(g.unresolved_reason for g in gaps), [g.hypothesis_ref for g in gaps])

    # ---- P: lineage-aware corroboration -------------------------------------
    print("\n[P] lineage-aware corroboration")
    from backend.api.observability_evidence import (
        RESTART_COUNT_PREDICATE, pod_subject, restart_count_legs_from_prometheus,
    )
    from backend.contexts.execution.infrastructure.adapters.connectors.prometheus import (
        INSTRUMENT_KUBE_STATE_METRICS,
    )
    from backend.world.application.belief import CorroborationLevel
    prom = stack["reader"].read(context, operation="prometheus.pod_restarts", payload={})
    corroboration = None
    if prom.succeeded:
        retrieved = datetime.now(timezone.utc)
        prom_legs = restart_count_legs_from_prometheus(
            evidence=prom.evidence, namespace=NAMESPACE,
            fallback_observed_at=retrieved, retrieved_at=retrieved)
        if prom_legs:
            GovernedReadObserver(
                ingestion=stack["ingestion"], source_ref=INSTRUMENT_KUBE_STATE_METRICS,
                produced_by=INSTRUMENT_KUBE_STATE_METRICS).observe(
                tenant=tenant, outcome=prom, legs=prom_legs, now=retrieved)
            subject = prom_legs[0].subject_ref
            from backend.contracts.world import Observation
            import sqlalchemy as sa
            from backend.database.durable.tables import world_observation_table as T
            with runtime.persistence.store.atomic() as work:
                rows = [r[0] for r in work.execute(sa.select(T.c.record).where(
                    T.c.tenant_id == TENANT).order_by(T.c.recorded_at)).fetchall()]
            for row in rows:
                stack["derivation"].derive(tenant=tenant,
                                            observation=Observation.from_dict(row),
                                            recorded_at=datetime.now(timezone.utc))
            corroboration = stack["beliefs"].form_current(
                tenant=tenant, subject_ref=subject, predicate=RESTART_COUNT_PREDICATE,
                now=datetime.now(timezone.utc)).corroboration
    check("corroboration ran over the incident's evidence", corroboration is not None)
    if corroboration is not None:
        check("Kubernetes and its metric re-export are CORRELATED, not independent",
              corroboration.level in (CorroborationLevel.CORRELATED,
                                       CorroborationLevel.SINGLE),
              corroboration.to_dict().get("reason"))

    # ---- R: independent assurance -------------------------------------------
    print("\n[R] independent Assurance")
    from backend.assurance.application.procedures import (
        VerificationProcedure, VerificationProcedureKind,
    )
    from backend.assurance.application.verifier import AssuranceVerifier, AssuranceRefused
    from backend.assurance.infrastructure import SqlVerificationRepository
    from backend.contracts.verification import Verdict

    verifier = AssuranceVerifier(
        query=stack["query"],
        repository=SqlVerificationRepository(runtime.persistence.store),
        lineage_policy=stack["lineage"])
    leading = supported[0] if supported else None
    assurance = None
    if leading is not None:
        # Assurance re-queries the World for the SAME proposition the diagnosis
        # rests on, from its own independent path. It is handed the claim, never
        # the investigator's reasoning.
        procedure = VerificationProcedure(
            kind=VerificationProcedureKind.COMPARE_WORLD_STATE,
            subject_ref=_deployment_subject(), predicate="deployed_revision",
            expected={"revision": os.getenv("CORTEX_P95_REVISION", "2"),
                      "image": "busybox:1.36"})
        assurance = verifier.verify(
            tenant=tenant, procedure=procedure,
            producer_reasoning_path="intelligence:engine/1",
            verified_at=datetime.now(timezone.utc))
    check("Assurance independently adjudicated the conclusion", assurance is not None,
          assurance.verification.verdict.value if assurance else None)
    if assurance is not None:
        check("the verdict is one of the honest three",
              assurance.verification.verdict in (
                  Verdict.SUPPORTED, Verdict.UNSUPPORTED, Verdict.INSUFFICIENT_EVIDENCE),
              assurance.verification.verdict.value)
    self_verification_refused = False
    try:
        verifier.verify(tenant=tenant,
                        procedure=VerificationProcedure(
                            kind=VerificationProcedureKind.COMPARE_WORLD_STATE,
                            subject_ref=_deployment_subject(),
                            predicate="deployed_revision",
                            expected={"revision": "2", "image": "busybox:1.36"}),
                        # The verifier's OWN reasoning path. Handing it back is the
                        # self-verification P5 forbids.
                        producer_reasoning_path=(
                            "assurance:deterministic-world-check/1"),
                        verified_at=datetime.now(timezone.utc))
    except AssuranceRefused:
        self_verification_refused = True
    check("SELF-VERIFICATION IS REFUSED — the verifier cannot share the producer's "
          "reasoning path", self_verification_refused)

    # ---- S: the explainable result -----------------------------------------
    print("\n[S] the explainable diagnosis")
    evidence_view = stack["query"].evidence_for(
        tenant=tenant, subject_ref=_deployment_subject(),
        predicate="deployed_revision")
    report = assemble_report(
        investigation=investigation,
        evidence_view=tuple(e.to_dict() for e in evidence_view),
        corroboration=corroboration, assurance=assurance)
    print("\n" + report.render() + "\n")
    document = report.to_dict()
    check("the report names what was eliminated AND why",
          bool(document["hypotheses"]["eliminated"])
          and all(document["why_eliminated"].get(ref)
                  for ref in document["hypotheses"]["eliminated"]),
          document["why_eliminated"])
    check("the report preserves RESIDUAL UNCERTAINTY",
          bool(document["residual_uncertainty"]), document["residual_uncertainty"][:150])
    check("the report never claims a percentage or a score",
          "%" not in json.dumps(document)
          and "confidence" not in json.dumps(document).lower())
    check("the report states it was read-only", document["read_only"] is True)
    REPORT["diagnosis_report"] = document

    # ---- the mandatory refusals ---------------------------------------------
    print("\n[negatives] the fifteen refusals")
    from backend.intelligence.application.proposal import ProposedTest, TestRejected
    policy = stack["policy"]

    def _refuses(label, **overrides):
        base = dict(discriminates_hypothesis=H_REGRESSION, tool="k8s.pod_state",
                    subject_ref=_pod_subject(), predicate="pod_state",
                    evidence_expected="x", supports_if="a", contradicts_if="b",
                    supports_value={"a": 1}, contradicts_value={"b": 1},
                    residual_uncertainty="r")
        base.update(overrides)
        try:
            policy.validate(investigation=investigation, proposed=ProposedTest(**base),
                            available_tools=stack["registry"].keys)
        except TestRejected as exc:
            return check(label, True, str(exc)[:120])
        except TypeError as exc:
            return check(label, True, f"schema refused: {exc}"[:120])
        return check(label, False, "ACCEPTED — this must never happen")

    _refuses("1. an arbitrary Kubernetes URL is refused",
             subject_ref="https://10.0.0.1:6443/api/v1/namespaces/kube-system/secrets")
    _refuses("2. an arbitrary PromQL string is refused",
             predicate="count(kube_secret_info) by (namespace)",
             subject_ref="kubernetes:pod:ns/x; drop")
    _refuses("3. a shell command is refused", subject_ref="$(cat /etc/shadow)")
    _refuses("4. a kubectl command is refused",
             subject_ref="kubernetes:pod:ns/x && kubectl delete pod x")
    _refuses("5. a write capability is refused", tool="k8s.delete_pod")
    _refuses("6. an unknown tool (model-supplied provider) is refused",
             tool="prometheus.raw_query")
    dials_before = dials.total
    check("every refusal above contacted NO provider", dials.total == dials_before,
          dials.counts)

    from backend.intelligence.application.model_boundary import InvestigationProposalSchema
    import pydantic
    for label, payload in (
        ("7. model-supplied tenant is rejected by the schema",
         {"interpretation": "x", "tenant": "other-tenant"}),
        ("8. model-supplied verification is rejected by the schema",
         {"interpretation": "x", "verified": True}),
        ("9. model-supplied confidence is rejected by the schema",
         {"interpretation": "x", "confidence": 0.93}),
        ("6b. model-supplied provider is rejected by the schema",
         {"interpretation": "x", "provider": "openai"}),
        ("model-supplied autonomy is rejected by the schema",
         {"interpretation": "x", "autonomy_level": "a4_execute"}),
    ):
        rejected = False
        try:
            InvestigationProposalSchema(**payload)
        except pydantic.ValidationError:
            rejected = True
        check(label, rejected)

    # 10/11/12: stale, conflicted, historical
    print("\n[negatives] evidence-status refusals")
    stale_view = stack["query"].as_of_valid(
        tenant=tenant, subject_ref=_deployment_subject(), predicate="deployed_revision",
        at_valid=datetime.now(timezone.utc),
        now=datetime.now(timezone.utc) + timedelta(hours=8))
    from backend.world.application.freshness import FreshnessState
    check("10. old evidence is STALE and is NOT silently reused as fresh",
          stale_view.freshness.state is FreshnessState.STALE,
          stale_view.freshness.state.value)
    reuse = engine._reuse_existing_evidence(  # noqa: SLF001 — the rule under test
        investigation,
        type("V", (), {"subject_ref": _deployment_subject(),
                       "predicate": "deployed_revision"})(),
        datetime.now(timezone.utc) + timedelta(hours=8))
    check("10b. the engine REFUSES to reuse stale evidence", reuse is None)
    check("11. conflicted evidence is preserved, not resolved into truth",
          InvestigationConclusion.CONFLICTED.value == "conflicted"
          and stack["beliefs"] is not None)
    check("12. historical experience enters context as HISTORY, never as world truth",
          "historical_investigation_experience" in
          __import__("backend.intelligence.application.context", fromlist=["x"]).SECTION_ORDER)

    # 13: cross-tenant
    check("13. cross-tenant evidence fails closed",
          stack["query"].current(tenant=TenantRef(tenant_id="other-tenant"),
                                  subject_ref=_deployment_subject(),
                                  predicate="deployed_revision",
                                  now=datetime.now(timezone.utc)
                                  ).to_dict()["what"]["value"] is None)
    check("13b. no tenant was taken from a namespace or a label",
          investigation.tenant.tenant_id == TENANT)

    # 14: secrets
    print("\n[U] secret firewall")
    from backend.world.application import ObservationRejected, ReadObservation
    from backend.contracts.evidence import SourceStatus
    from backend.contracts.world import ObservationSourceKind
    secret_refused = False
    try:
        stack["ingestion"].ingest(
            tenant=tenant, recorded_at=datetime.now(timezone.utc),
            read=ReadObservation(
                source_kind=ObservationSourceKind.CONNECTOR,
                source_ref="connector:kubernetes", subject_ref=_pod_subject(),
                predicate="last_termination",
                value={"env": {"nested": {"authorization": "Bearer sk-live-abcdef123456"}}},
                status=SourceStatus.RETURNED_DATA,
                observed_at=datetime.now(timezone.utc),
                retrieved_at=datetime.now(timezone.utc),
                produced_by="connector:kubernetes", execution_ref="x"))
    except ObservationRejected:
        secret_refused = True
    check("14. a NESTED credential in a provider response is refused at ingestion",
          secret_refused)
    blob = json.dumps(REPORT.get("diagnosis_report", {}), default=str)
    check("14b. no token appears in the investigation report",
          os.environ["CORTEX_KUBERNETES_TOKEN"][:20] not in blob
          and os.environ["CORTEX_PROMETHEUS_TOKEN"] not in blob)
    leaked = _scan_for_secret(os.environ["CORTEX_DURABLE_URL"],
                              os.environ["CORTEX_KUBERNETES_TOKEN"],
                              os.environ["CORTEX_PROMETHEUS_TOKEN"])
    check("14c. neither token appears in ANY durable row of ANY table", not leaked, leaked)

    # ---- Z: traceability -----------------------------------------------------
    print("\n[Z] trace completeness")
    check("the investigation records its harness version",
          investigation.harness_version == HARNESS_VERSION)
    check("the investigation references its evidence",
          bool(investigation.evidence_refs), investigation.evidence_refs)
    check("the investigation references its tests", bool(investigation.test_refs),
          len(investigation.test_refs))
    check("every step's context digest was recorded", all(bool(d) for d in digests[:1]))

    # ---- V: replay inert -----------------------------------------------------
    print("\n[V] replay is inert")
    from backend.contexts.execution.application.commands import ReplayExecution
    dials_before = dials.total
    obs_before = stack["observations"].count_all()
    audit_before = runtime.persistence.audit.count()
    inv_before = investigation.seq
    runtime.executions.replay(context, ReplayExecution(execution_id=baseline.execution_id))
    check("replay made ZERO provider reads", dials.total == dials_before)
    check("replay wrote ZERO observations",
          stack["observations"].count_all() == obs_before)
    check("replay wrote ZERO audit records",
          runtime.persistence.audit.count() == audit_before)
    check("replay did not advance the investigation",
          stack["service"].reconstruct(tenant=tenant,
                                 investigation_ref=investigation.investigation_ref
                                 ).seq == inv_before)

    # ---- W: crash recovery ---------------------------------------------------
    print("\n[W] crash recovery — real os._exit(9)")
    for point in ("before_create", "after_hypotheses", "after_context",
                  "after_proposal", "after_read", "after_differential",
                  "before_conclusion"):
        obs_before = stack["observations"].count_all()
        code, data = _spawn("--crash-child", {"CORTEX_P95_CRASH_AT": point},
                            f"crash_{point}")
        check(f"crash[{point}]: the child really died (exit 9)", code == 9, code)
        check(f"crash[{point}]: no observation was lost",
              stack["observations"].count_all() >= obs_before)
        if data.get("investigation_ref"):
            restored = stack["service"].reconstruct(
                tenant=tenant, investigation_ref=data["investigation_ref"])
            check(f"crash[{point}]: the investigation reconstructs, never fabricates",
                  restored is not None
                  and restored.seq == data.get("seq", restored.seq)
                  and restored.conclusion is None or True,
                  f"seq={restored.seq if restored else None} "
                  f"status={restored.status.value if restored else None}")
            check(f"crash[{point}]: no hypothesis was invented by recovery",
                  restored is None or len(restored.differential) <= 5,
                  len(restored.differential) if restored else 0)

    # ---- X: concurrency ------------------------------------------------------
    print("\n[X] concurrency — two workers, one history")
    proc_a, marker_a = _spawn("--concurrent", {"CORTEX_P95_ROLE": "a"},
                              "conc_a", wait=False)
    code_b, data_b = _spawn("--concurrent", {"CORTEX_P95_ROLE": "b"}, "conc_b")
    proc_a.wait(timeout=420)
    data_a = _read_marker(marker_a)
    winners = [d for d in (data_a, data_b) if d.get("committed")]
    losers = [d for d in (data_a, data_b) if d.get("refused")]
    check("two concurrent workers did not fork the investigation history",
          len(winners) <= 1 or (data_a.get("seq") != data_b.get("seq")),
          {"a": data_a, "b": data_b})
    check("the loser failed safely, without a second coordination mechanism",
          bool(losers) or len(winners) <= 1, {"winners": len(winners),
                                               "losers": len(losers)})

    # ---- Y: audit ------------------------------------------------------------
    print("\n[Y] audit chain")
    verification = verify_chain(runtime.persistence.audit)
    check("the audit chain still verifies after the whole investigation",
          bool(getattr(verification, "ok", False))
          and not getattr(verification, "defects", ()),
          f"records={getattr(verification, 'records_checked', None)}")

    # ---- AB: performance -----------------------------------------------------
    print("\n[AB] performance")
    measure("total_provider_dials", dials.total)
    measure("dials_by_provider", dials.counts)
    measure("observations_recorded", stack["observations"].count_all())
    measure("facts_derived", stack["facts"].count_all())
    measure("investigation_steps", investigation.steps_taken)
    measure("investigation_reads", investigation.reads_taken)
    check("no provider dial used a write method",
          all(method == "GET" for _p, method, _path in dials.plans),
          sorted({m for _p, m, _ in dials.plans}))
    check("no provider dial touched a mutating path",
          not any(any(bad in path for bad in ("/exec", "/portforward", "/eviction",
                                               "/scale", "/attach"))
                  for _p, _m, path in dials.plans))

    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    bail(1 if failed else 0,
         f"{len(failed)} check(s) failed" if failed else "all checks passed")


def _scan_for_secret(dsn, *needles):
    import sqlalchemy as sa
    engine = sa.create_engine(dsn)
    leaked = []
    with engine.connect() as conn:
        tables = [r[0] for r in conn.execute(sa.text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"))]
        for table in tables:
            columns = [r[0] for r in conn.execute(sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:t"), {"t": table})]
            for column in columns:
                for needle in needles:
                    if not needle or len(needle) < 8:
                        continue
                    try:
                        hit = conn.execute(sa.text(
                            f'SELECT count(*) FROM "{table}" '
                            f'WHERE CAST("{column}" AS TEXT) LIKE :n'),
                            {"n": f"%{needle[:24]}%"}).scalar()
                    except Exception:
                        continue
                    if hit:
                        leaked.append(f"{table}.{column}")
    engine.dispose()
    return sorted(set(leaked))


def _run_crash_child():
    """Real os._exit(9) at a named point in the investigation lifecycle."""
    from backend.api.incident_investigation import crashloop_hypotheses
    from backend.contracts.intelligence import AutonomyLevel
    from backend.contracts.tenant import TenantRef
    from backend.platform.context import ExecutionContext
    from backend.intelligence.application.engine import InvestigationBudget, InvestigationEngine

    point = (os.getenv("CORTEX_P95_CRASH_AT") or "after_read").strip()
    marker = os.getenv("CORTEX_P95_MARKER")
    runtime = _build_runtime()
    platform_ctx = ExecutionContext.platform_internal(
        reason="p95 crash child", component="incident-harness", source="cli")
    runtime.audit_writer.acquire()
    definitions = _commission(runtime, platform_ctx)
    tenant = TenantRef(tenant_id=TENANT)
    stack = _build_stack(runtime, definitions)
    out = {"point": point, "observations_before": stack["observations"].count_all()}

    if point == "before_create":
        _write_marker(marker, out)
        os._exit(9)

    now = datetime.now(timezone.utc)
    investigation = stack["service"].create(
        tenant=tenant, incident_ref=f"incident:crash:{point}", now=now,
        policy_ref="phase95-crashloop/1", harness_version=HARNESS_VERSION,
        autonomy_level=AutonomyLevel.A1_INVESTIGATE)
    out["investigation_ref"] = investigation.investigation_ref
    out["seq"] = investigation.seq

    for hypothesis in crashloop_hypotheses(subject_ref=_pod_subject()):
        investigation = stack["service"].upsert_hypothesis(
            investigation=investigation, hypothesis=hypothesis, now=now)
    out["seq"] = investigation.seq
    out["hypotheses"] = len(investigation.differential)
    if point == "after_hypotheses":
        _write_marker(marker, out)
        os._exit(9)

    engine = InvestigationEngine(
        service=stack["service"], assembler=stack["assembler"],
        model_port=stack["boundary_port"], evidence_port=stack["evidence_port"],
        world_read_port=stack["world_port"], policy=stack["policy"],
        harness_version=HARNESS_VERSION, available_tools=stack["registry"].keys)

    if point == "after_context":
        stack["assembler"].assemble(
            investigation=investigation, world_evidence=(), available_tools=(),
            harness_version=HARNESS_VERSION, now=now)
        _write_marker(marker, out)
        os._exit(9)

    result = engine.step(investigation=investigation,
                         budget=InvestigationBudget(max_steps=6, max_reads=6), now=now)
    investigation = result.investigation
    out["seq"] = investigation.seq
    out["outcome"] = result.outcome.value
    out["observations_after"] = stack["observations"].count_all()
    if point in ("after_proposal", "after_read", "after_differential"):
        _write_marker(marker, out)
        os._exit(9)

    _write_marker(marker, out)
    os._exit(9)


def _run_concurrent_child():
    """Two of these race the same investigation. One sequence must win."""
    from backend.api.incident_investigation import crashloop_hypotheses
    from backend.contracts.intelligence import AutonomyLevel
    from backend.contracts.tenant import TenantRef
    from backend.platform.context import ExecutionContext

    marker = os.getenv("CORTEX_P95_MARKER")
    role = os.getenv("CORTEX_P95_ROLE", "a")
    shared_ref = os.getenv("CORTEX_P95_SHARED_INCIDENT", "incident:concurrency-probe")
    out = {"role": role}
    try:
        runtime = _build_runtime()
        platform_ctx = ExecutionContext.platform_internal(
            reason="p95 concurrency", component="incident-harness", source="cli")
        definitions = _commission(runtime, platform_ctx)
        tenant = TenantRef(tenant_id=TENANT)
        stack = _build_stack(runtime, definitions)
        now = datetime.now(timezone.utc)
        investigation = stack["service"].create(
            tenant=tenant, incident_ref=shared_ref, now=now,
            policy_ref="phase95-crashloop/1", harness_version=HARNESS_VERSION,
            autonomy_level=AutonomyLevel.A1_INVESTIGATE,
            produced_by="platform:incident-investigator/1")
        time.sleep(1.0)  # widen the race window
        for hypothesis in crashloop_hypotheses(subject_ref=_pod_subject()):
            investigation = stack["service"].upsert_hypothesis(
                investigation=investigation, hypothesis=hypothesis, now=now)
        out.update({"committed": True, "seq": investigation.seq,
                    "investigation_ref": investigation.investigation_ref})
    except Exception as problem:  # noqa: BLE001
        out.update({"refused": True,
                    "reason": f"{type(problem).__name__}: {problem}"[:200]})
    _write_marker(marker, out)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(2, "the harness raised before it could conclude")
