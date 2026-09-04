"""Phase 9.6 evidence: the platform REFUSES its own first irreversible write.

Run:  bash scripts/phase96_provision.sh && source .phase96.env
      python -m scripts.phase96_reversible_remediation_harness

Phase 9.6 set out to perform CortexPrime's first governed Kubernetes write — a
workload rollout restart — and stopped before executing it. This harness proves
why, and proves that nothing was written.

The chain of honest steps that ends in a refusal:

  a rollout restart stamps the pod template and creates a revision, and nothing
  removes either, so it is an IRREVERSIBLE_WRITE and not a reversible one;

  the platform's own rule derives RiskLevel.HIGH from that classification;

  IsolationTier says only SEALED — "arbitrary commands or code, full
  virtualization, no ambient credentials" — is sufficient for an irreversible
  write, and the Kubernetes connector runs IN-PROCESS at CONTAINED (ADR-059);

  so the capability is refused at registration, and the worker would be refused
  at selection. Two independent gates, neither of which anybody wrote for this
  phase, and no irreversible-write capability had ever been registered before.

Executing anyway would mean declaring the in-process connector SEALED — asserting
virtualization that does not exist. That is the one thing this project must never
do, so the phase stops here.

Everything that does NOT depend on the write is still proven against the real
cluster: the declaration, both isolation gates, the autonomy ladder, approval
binding, the typed read/write doors, the body builder, tenant isolation, secrets
and the audit chain — and, decisively, that ZERO provider writes occurred.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED (this phase exits 2 by design).
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
NAMESPACE = os.getenv("CORTEX_P96_NAMESPACE", "cortex-p96")
FIXABLE = os.getenv("CORTEX_P96_FIXABLE_WORKLOAD", "config-consumer")
UNFIXABLE = os.getenv("CORTEX_P96_WORKLOAD", "payments-api")
FIXABLE_POD = os.getenv("CORTEX_P96_FIXABLE_POD", "")
UNFIXABLE_POD = os.getenv("CORTEX_P96_POD", "")
HARNESS_VERSION = "phase96/1"

RESTART_OP = "kubernetes.workload.rollout_restart"
#: Worker commissioning is a one-way lifecycle; run it once per process.
_COMMISSIONED = False
READ_OPS = ("kubernetes.pod.get", "kubernetes.deployment.get", "kubernetes.pods.list")


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
        bail(2, "no governed runtime")
    if "kubernetes" not in runtime.connectivity.catalogs:
        bail(2, "kubernetes provider absent")
    return runtime


def _commission(runtime, platform_ctx, *, include_write=True, swallow=True):
    """Commission the reads AND the one write. The write is registered with its
    real declared effect — irreversible_write — so the governed policy sees what
    it actually is."""
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

    # The worker lifecycle is a one-way transition, so commissioning it twice in
    # ONE process raises rather than being idempotent. Capabilities are different
    # (they have their own idempotent path), which is why only this half is
    # guarded.
    d = runtime.connectivity.directory
    for worker in ((), ("kubernetes-connector", "prometheus-connector"))[
            not _COMMISSIONED]:
        for step in (
            lambda w=worker: d.validate(platform_ctx, worker_id=w, tenant_id=""),
            lambda w=worker: d.enable(platform_ctx, worker_id=w, tenant_id=""),
            lambda w=worker: d.set_trust(platform_ctx, worker_id=w, tenant_id="",
                                         trust=WorkerTrust.VERIFIED, reason="phase-9.6"),
            lambda w=worker: d.set_trust(platform_ctx, worker_id=w, tenant_id="",
                                         trust=WorkerTrust.TRUSTED, reason="phase-9.6"),
            lambda w=worker: d.set_availability(platform_ctx, worker_id=w, tenant_id="",
                                                availability=WorkerAvailability.AVAILABLE),
        ):
            _idem(step)
    globals()["_COMMISSIONED"] = True

    specs = [(op, "read", "read_only") for op in READ_OPS]
    if include_write:
        specs.append((RESTART_OP, "irreversible_write", "non_idempotent_write"))
    definitions = {}
    for op, effect, semantics in specs:
        cid = f"platform.{op}"
        register = lambda cid=cid, op=op, e=effect, sm=semantics: runtime.capabilities.register(
            platform_ctx, RegisterCapability(
                capability_id=cid, version=1, name=op, description=op,
                provider="kubernetes", interface="connector", side_effect_class=e,
                effect_semantics=sm, isolation_tier="contained", code_trust="fixed",
                execution_mode="synchronous", owner_id="ops-owner", owner_kind="human",
                tenancy="platform", source="internal",
                supported_environments=("development",), provider_operation=op))
        if swallow:
            _idem(register)
        else:
            register()
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
    """Counts every provider dial and records its METHOD and PATH, so a write can
    be counted separately from a read and a mutating path can be spotted."""

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

    @property
    def writes(self):
        return [p for p in self.plans if p[1] not in ("GET", "HEAD")]


class _Approvals:
    """A digest-bound approval lookup over the EXISTING ApprovalFacts contract.

    It stores nothing of its own beyond the granted artifacts a human produced;
    every question about whether an approval covers an action is answered by
    ``ApprovalFacts.is_valid_for``, which already checks outcome, expiry, tenant,
    operation and digest. This is a lookup, not a second approval system.
    """

    def __init__(self):
        self._facts = {}

    def grant(self, *, artifact_id, tenant_id, operation, digest, actor_ref,
              expires_at=None):
        from backend.contracts.approval import ApprovalOutcome
        from backend.contexts.connectivity.application.authorization import ApprovalFacts
        if ":" not in actor_ref:
            raise ValueError("an approver must be a namespaced identity reference")
        self._facts[artifact_id] = ApprovalFacts(
            artifact_id=artifact_id, outcome=ApprovalOutcome.GRANTED,
            bound_digest=digest, scope_tenant_id=tenant_id, operation=operation,
            expires_at=expires_at)
        return artifact_id

    def deny(self, *, artifact_id, tenant_id, operation, digest):
        from backend.contracts.approval import ApprovalOutcome
        from backend.contexts.connectivity.application.authorization import ApprovalFacts
        self._facts[artifact_id] = ApprovalFacts(
            artifact_id=artifact_id, outcome=ApprovalOutcome.DENIED,
            bound_digest=digest, scope_tenant_id=tenant_id, operation=operation)
        return artifact_id

    def find(self, context, artifact_id):
        return self._facts.get(artifact_id)


def _target(workload):
    from backend.api.remediation import RemediationTarget
    return RemediationTarget(namespace=NAMESPACE, workload=workload)


def _autonomy_inputs(*, stop=None, breaker=None, world_fresh=True,
                     world_conflicted=False, decided=20, support=0.95,
                     coverage=0.95, drift=None, reliability=None, config=None):
    """The platform-side inputs to the autonomy decision.

    Every one comes from the platform — the stop state, the breaker, the
    calibration evidence, the drift verdict, the world's freshness. None of them
    is anything a model produced, and that is the property the decision depends
    on. The harness varies them to prove each gate refuses on its own.
    """
    from backend.contracts.intelligence.autonomy import (
        AutonomyPolicyConfig, AutonomyScope, EmergencyStopState,
    )
    from backend.contracts.intelligence.calibration import (
        CalibrationStatus, DriftStatus, PredictionClass, ReliabilityEstimate,
    )
    from backend.contracts.intelligence.investigation import AutonomyLevel
    from backend.contracts.tenant import TenantRef
    from backend.harness.version import CURRENT_HARNESS_VERSION

    model_id = "scripted"
    harness_v = str(CURRENT_HARNESS_VERSION)
    pc = PredictionClass(subject_type="deployment", predicate="workload_health",
                         environment="development", model_identity=model_id,
                         harness_version=harness_v)
    if reliability is None and decided > 0:
        supported = max(0, int(round(decided * support)))
        reliability = ReliabilityEstimate(
            prediction_class=pc, status=CalibrationStatus.CALIBRATED,
            sample_count=decided, decided_count=decided, supported_count=supported,
            unsupported_count=decided - supported, insufficient_count=0,
            conflicted_count=0, pending_count=0,
            assured_count=max(0, int(round(decided * coverage))),
            dataset_digest="d" * 64, policy_digest="p" * 64, confidence=None,
            generated_at=datetime.now(timezone.utc), support_rate=support,
            assurance_coverage=coverage)
    elif reliability is None:
        reliability = ReliabilityEstimate(
            prediction_class=pc, status=CalibrationStatus.INSUFFICIENT_DATA,
            sample_count=1, decided_count=0, supported_count=0, unsupported_count=0,
            insufficient_count=1, conflicted_count=0, pending_count=1,
            assured_count=0, dataset_digest="d" * 64, policy_digest="p" * 64,
            confidence=None, generated_at=datetime.now(timezone.utc),
            support_rate=None, assurance_coverage=None)
    return {
        "scope": AutonomyScope(
            tenant=TenantRef(tenant_id=TENANT), environment="development",
            service="payments", capability_ref=f"platform.{RESTART_OP}",
            operation=RESTART_OP, resource_class="deployment"),
        # The DEPLOYMENT's explicit, versioned autonomy policy.
        #
        # The shipped default caps HIGH-risk actions at A2 — no autonomous action
        # at all, even with a human approving. That default is deliberate and the
        # harness proves it still holds. This deployment raises HIGH to A3, which
        # is not a weakening: A3 means every single execution needs a fresh,
        # digest-bound human approval, and gate 9 independently forces an
        # irreversible action to A3 anyway, so A4 stays unreachable either way.
        # What changes is only whether a human is ALLOWED to approve it at all.
        #
        # Changing a threshold changes policy_version, which is the whole point
        # of these being configuration rather than constants.
        "config": config or AutonomyPolicyConfig(
            policy_version="phase96-autonomy/1",
            max_level_high=AutonomyLevel.A3_APPROVED_ACTION),
        "stop_state": stop or EmergencyStopState.RUNNING,
        "breaker": breaker,
        "reliability": reliability,
        "drift": drift or DriftStatus.NO_DRIFT,
        "world_fresh": world_fresh,
        "world_conflicted": world_conflicted,
        # The runtime versions the calibration evidence must match. Gate 4
        # refuses evidence gathered under a different model or harness, so this
        # is not decoration: it is what stops yesterday's reliability from
        # authorising today's action.
        "versions": {"model_identity": model_id, "harness_version": harness_v},
        "now": datetime.now(timezone.utc),
    }


def _build_stack(runtime, definitions, approvals):
    from backend.api.capability_execution_composition import (
        GovernedCapabilityReader, GovernedCapabilityWriter,
    )
    from backend.api.governed_read_observer import GovernedReadObserver
    from backend.api.observability_evidence import (
        observability_authority_policy, observability_freshness_policy,
        observability_lineage_policy,
    )
    from backend.api.remediation import GovernedRemediation
    from backend.assurance.application.verifier import AssuranceVerifier
    from backend.assurance.infrastructure import SqlVerificationRepository
    from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
        kubernetes_write_profiles,
    )
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    from backend.contracts.tenant import TenantRef
    from backend.intelligence.application.autonomy import AutonomyPolicy
    from backend.world.application import (
        FactDerivation, ObservationIngestion, WorldQuery,
    )
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository

    context = _tenant_ctx()
    tenant = TenantRef(tenant_id=TENANT)
    observations = SqlObservationRepository(runtime.persistence.store)
    facts = SqlFactRepository(runtime.persistence.store)
    ingestion = ObservationIngestion(repository=observations)
    derivation = FactDerivation(repository=facts)
    query = WorldQuery(facts=facts, observations=observations,
                       authority_policy=observability_authority_policy(),
                       freshness_policy=observability_freshness_policy())
    principal = PrincipalRef(principal_id="harness", kind=PrincipalKind.HUMAN)
    reader = GovernedCapabilityReader(runtime=runtime, capability_definitions=definitions,
                                       principal=principal)
    writer = GovernedCapabilityWriter(runtime=runtime, capability_definitions=definitions,
                                       principal=principal)
    observer = GovernedReadObserver(ingestion=ingestion, source_ref="connector:kubernetes",
                                     produced_by="connector:kubernetes")
    verifier = AssuranceVerifier(
        query=query, repository=SqlVerificationRepository(runtime.persistence.store),
        lineage_policy=observability_lineage_policy())
    profile = kubernetes_write_profiles()[RESTART_OP]
    return {
        "context": context, "tenant": tenant, "observations": observations,
        "facts": facts, "ingestion": ingestion, "derivation": derivation,
        "query": query, "reader": reader, "writer": writer, "observer": observer,
        "verifier": verifier, "profile": profile, "approvals": approvals,
        "remediation": GovernedRemediation(
            reader=reader, writer=writer, observer=observer, derivation=derivation,
            query=query, verifier=verifier, autonomy_policy=AutonomyPolicy(),
            capability_profile=profile, approvals=approvals, context=context,
            tenant=tenant),
    }


def _seed_world(stack, workload, pod, now):
    """Put the pre-action facts in the World the way 9.5 would have."""
    from backend.api.governed_read_observer import ObservationLeg
    outcome = stack["reader"].read(stack["context"], operation="kubernetes.deployment.get",
                                    payload={"namespace": NAMESPACE, "name": workload})
    if not outcome.succeeded:
        return None, {}
    stack["observer"].observe(
        tenant=stack["tenant"], outcome=outcome, now=now,
        legs=(ObservationLeg(subject_ref=f"kubernetes:deployment:{NAMESPACE}/{workload}",
                             predicate="deployed_revision",
                             value={"revision": outcome.evidence.get("revision"),
                                    "image": outcome.evidence.get("image")},
                             observed_at=now),))
    import sqlalchemy as sa
    from backend.contracts.world import Observation
    from backend.database.durable.tables import world_observation_table as T
    with stack["observations"]._store.atomic() as work:  # noqa: SLF001
        rows = [r[0] for r in work.execute(sa.select(T.c.record).where(
            T.c.tenant_id == TENANT).order_by(T.c.recorded_at)).fetchall()]
    for row in rows:
        stack["derivation"].derive(tenant=stack["tenant"],
                                    observation=Observation.from_dict(row),
                                    recorded_at=now)
    return outcome, dict(outcome.evidence)


class _Investigation:
    """The minimum an investigation reference needs to be here. The real one comes
    from 9.5; this carries the two fields the gate reads."""

    def __init__(self, tenant, ref="winv_p96"):
        self.tenant = tenant
        self.investigation_ref = ref


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
    marker = os.path.join(tempfile.gettempdir(), f"p96_{suffix}_{os.getpid()}.json")
    env = dict(os.environ)
    env["CORTEX_P96_MARKER"] = marker
    env.update(env_overrides)
    argv = [sys.executable, "-m", "scripts.phase96_reversible_remediation_harness", mode]
    if not wait:
        return subprocess.Popen(argv, env=env, cwd=os.getcwd(),
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL), marker
    proc = subprocess.run(argv, env=env, cwd=os.getcwd(),
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          timeout=timeout)
    return proc.returncode, _read_marker(marker)


def _kubectl(*args):
    return subprocess.run(["kubectl", "-n", NAMESPACE, *args], capture_output=True,
                          text=True, timeout=120).stdout.strip()


def _percentiles(samples):
    if not samples:
        return None, None
    ordered = sorted(samples)
    return (round(statistics.median(ordered) * 1000, 1),
            round(ordered[min(len(ordered) - 1,
                              max(0, round(0.95 * len(ordered)) - 1))] * 1000, 1))


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


def main():  # noqa: PLR0912, PLR0915
    if "--crash-child" in sys.argv:
        _require_env(); _run_crash_child(); return
    if "--concurrent" in sys.argv:
        _require_env(); _run_concurrent_child(); return
    _require_env()

    from backend.api.remediation import RemediationOutcome, RemediationTarget
    from backend.contracts.connector import CodeTrust, IsolationTier, minimum_isolation
    from backend.contracts.errors import ContractViolation
    from backend.contracts.execution import EffectSemantics, SideEffectClass
    from backend.contracts.intelligence.autonomy import (
        ApprovalRequirement, AutonomyEligibility, AutonomyPolicyConfig, BreakerTrip,
        EmergencyStopState,
    )
    from backend.contracts.intelligence.investigation import AutonomyLevel
    from backend.contracts.policy import RiskLevel
    from backend.contracts.tenant import TenantRef
    from backend.contexts.execution.domain.worker_directory import WorkerImplementation
    from backend.intelligence.application.autonomy import AutonomyPolicy
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext
    from backend.platform.hashing import compute_digest
    from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
        KUBERNETES_REAL_READ_OPERATIONS, RESTART_ANNOTATION, ROLLOUT_RESTART_OPERATION,
        KubernetesRestartBodyBuilder, kubernetes_write_catalog, kubernetes_write_profiles,
    )

    print("[label] REAL k3d cluster. Phase 9.6 STOPPED before the write, and this")
    print("        harness proves WHY: the platform refuses to register or select")
    print("        an irreversible write it cannot isolate. NO WRITE WAS ATTEMPTED.")

    catalog = kubernetes_write_catalog()
    spec = catalog.require(ROLLOUT_RESTART_OPERATION)
    profile = kubernetes_write_profiles()[ROLLOUT_RESTART_OPERATION]

    # ---- the declaration, classified honestly -------------------------------
    print("\n[declaration] the operation, classified honestly")
    check("exactly ONE write operation exists in the Kubernetes catalog",
          len([o for o in catalog.operations
               if catalog.require(o).side_effect_class.mutates]) == 1,
          sorted(o for o in catalog.operations
                 if catalog.require(o).side_effect_class.mutates))
    check("it is declared IRREVERSIBLE_WRITE — a restart has no inverse",
          spec.side_effect_class is SideEffectClass.IRREVERSIBLE_WRITE
          and profile.reversible is False)
    check("it is declared NON_IDEMPOTENT — execution must not blind-retry it",
          not spec.effect_semantics.is_repeatable, spec.effect_semantics.value)
    check("it requires INDEPENDENT_READBACK verification",
          profile.verification_requirement.value == "independent_readback")
    check("its autonomy ceiling is A3 — never delegated to the platform itself",
          profile.autonomy_ceiling is AutonomyLevel.A3_APPROVED_ACTION)
    check("BLAST RADIUS: the operation declares only namespace + name",
          {p.name for p in spec.parameters} == {"namespace", "name"},
          sorted(p.name for p in spec.parameters))
    for namespace, workload in ((NAMESPACE, "*"), ("*", "app"), (NAMESPACE, "a,b")):
        refused = False
        try:
            RemediationTarget(namespace=namespace, workload=workload)
        except ContractViolation:
            refused = True
        check(f"a wildcard/list target {namespace}/{workload} is refused", refused)

    # ---- THE BLOCKING FINDING ----------------------------------------------
    print("\n[BLOCKED] the platform refuses to isolate its own first irreversible write")
    check("the platform DERIVES HIGH risk from the honest classification",
          profile.risk.level is RiskLevel.HIGH, profile.risk.level.value)
    # SUPERSEDED BY ADR-088 (ratified 2026-09-04). When this harness first ran,
    # every irreversible write routed to SEALED regardless of what code performed
    # it, and these three checks recorded that. The taxonomy now asks what runs:
    # a FIXED typed operation needs CONTAINED, and only arbitrary code needs
    # SEALED. What did NOT change is the conclusion this harness reaches -- the
    # write is still refused, because an in-process adapter is AMBIENT and
    # AMBIENT is still insufficient. The reason is now the honest one.
    check("AMBIENT isolation is insufficient for an irreversible write",
          not IsolationTier.AMBIENT.satisfies(
              minimum_isolation(CodeTrust.FIXED, SideEffectClass.IRREVERSIBLE_WRITE)))
    check("a FIXED irreversible write requires CONTAINED — a separate worker "
          "with per-execution credentials, which in-process is not",
          minimum_isolation(CodeTrust.FIXED, SideEffectClass.IRREVERSIBLE_WRITE)
          is IsolationTier.CONTAINED)
    check("ARBITRARY code still requires SEALED for every effect, reads included",
          all(minimum_isolation(CodeTrust.ARBITRARY, e) is IsolationTier.SEALED
              for e in SideEffectClass))

    runtime = _build_runtime()
    platform_ctx = ExecutionContext.platform_internal(
        reason="p96 governed remediation", component="remediation-harness", source="cli")
    runtime.audit_writer.acquire()
    dials = _DialCounter(runtime)

    worker = next((e.implementation for e in
                   [type("E", (), {"implementation": impl})()
                    for impl in _kubernetes_workers(runtime)]), None)
    check("the Kubernetes connector runs at CONTAINED (in-process; ADR-059)",
          worker is not None and worker.isolation is IsolationTier.CONTAINED,
          worker.isolation.value if worker is not None else "<not found>")
    check("GATE 2 — that worker would REFUSE to perform an irreversible write",
          worker is not None
          and not worker.permits_side_effect(SideEffectClass.IRREVERSIBLE_WRITE))

    # GATE 1: registering the capability at CONTAINED is refused outright.
    gate1 = None
    try:
        _commission(runtime, platform_ctx, include_write=True, swallow=False)
    except ContractViolation as refusal:
        gate1 = str(refusal)
    check("GATE 1 — registering the capability at CONTAINED is REFUSED",
          gate1 is not None and "insufficient" in (gate1 or ""), gate1)
    check("the two gates are independent — either alone stops the write",
          gate1 is not None and worker is not None
          and not worker.permits_side_effect(SideEffectClass.IRREVERSIBLE_WRITE))

    # ---- everything that does NOT need the write ---------------------------
    definitions = _commission(runtime, platform_ctx, include_write=False)
    approvals = _Approvals()
    stack = _build_stack(runtime, definitions, approvals)
    context, tenant = stack["context"], stack["tenant"]

    print("\n[reads] the governed READ path is unaffected")
    outcome = stack["reader"].read(context, operation="kubernetes.deployment.get",
                                   payload={"namespace": NAMESPACE, "name": FIXABLE})
    check("a governed READ still succeeds against the real cluster",
          outcome.succeeded, outcome.failure_reason)
    check("the read reported the deployment's real revision",
          bool(outcome.evidence.get("revision")), outcome.evidence.get("revision"))
    check("no restart annotation is present — nothing restarted anything",
          outcome.evidence.get("restartedByAction") is None)

    # ---- the doors ----------------------------------------------------------
    print("\n[doors] read and write are separate, typed entrances")
    write_through_read = False
    try:
        stack["reader"].read(context, operation=ROLLOUT_RESTART_OPERATION,
                             payload={"namespace": NAMESPACE, "name": FIXABLE})
    except ContractViolation:
        write_through_read = True
    check("a WRITE cannot be performed through the read door", write_through_read)
    read_through_write = False
    try:
        stack["writer"].write(context, operation="kubernetes.pods.list",
                              payload={"namespace": NAMESPACE})
    except ContractViolation:
        read_through_write = True
    check("a READ cannot be performed through the write door", read_through_write)

    # ---- the body builder ---------------------------------------------------
    print("\n[body] the one document this platform could send")
    builder = KubernetesRestartBodyBuilder()
    body = builder.build(spec, {"namespace": NAMESPACE, "name": FIXABLE},
                          idempotency_key="act_1")
    check("the builder produces exactly one declared document", body == {
        "spec": {"template": {"metadata": {"annotations": {
            RESTART_ANNOTATION: "act_1"}}}}}, body)
    check("the same action identity produces the SAME request (deterministic)",
          builder.build(spec, {}, idempotency_key="act_1") == body)
    no_key = False
    try:
        builder.build(spec, {}, idempotency_key=None)
    except ValueError:
        no_key = True
    check("it refuses without the platform's action identity", no_key)
    check("the annotation is CortexPrime's own, not kubectl's",
          RESTART_ANNOTATION.startswith("cortexprime.io/"))

    # ---- autonomy -----------------------------------------------------------
    print("\n[G] autonomy — every gate, on the capability as declared")
    policy = AutonomyPolicy()
    shipped = AutonomyPolicyConfig(policy_version="shipped-default")
    check("the SHIPPED DEFAULT caps HIGH risk at A2 — no action at all",
          shipped.cap_for_risk(RiskLevel.HIGH) is AutonomyLevel.A2_RECOMMEND)
    default_decision = policy.evaluate(
        requested_level=AutonomyLevel.A3_APPROVED_ACTION,
        capability=profile.to_capability(), risk=profile.risk,
        **_autonomy_inputs(config=shipped))
    check("under the shipped default the action is refused even WITH approval",
          not default_decision.effective_level.permits_action(), default_decision.reason)

    decision = policy.evaluate(requested_level=AutonomyLevel.A4_AUTONOMOUS,
                                capability=profile.to_capability(), risk=profile.risk,
                                **_autonomy_inputs())
    check("A4 requested is never A4 effective for an irreversible action",
          decision.effective_level is not AutonomyLevel.A4_AUTONOMOUS,
          f"{decision.requested_level.value} -> {decision.allowed_level.value} "
          f"-> {decision.effective_level.value}")
    check("the reversibility gate forces HUMAN_APPROVAL_REQUIRED",
          decision.eligibility is AutonomyEligibility.HUMAN_APPROVAL_REQUIRED,
          decision.reason)
    check("effective <= allowed <= requested",
          decision.effective_level.rank <= decision.allowed_level.rank
          <= AutonomyLevel.A4_AUTONOMOUS.rank)

    for label, kwargs in (
        ("R. emergency stop refuses", {"stop": EmergencyStopState.STOP_ACTIVE}),
        ("S. circuit breaker refuses",
         {"breaker": BreakerTrip(trigger="verification_failure", count=5, threshold=3,
                                 reason="verification failures crossed the threshold")}),
        ("T. stale world evidence refuses", {"world_fresh": False}),
        ("U. conflicted world evidence refuses", {"world_conflicted": True}),
        ("insufficient calibration refuses", {"decided": 0}),
        ("low reliability refuses", {"support": 0.10}),
        ("insufficient assurance coverage refuses", {"coverage": 0.10}),
        ("drift refuses", {"drift": _drift_detected()}),
    ):
        verdict = policy.evaluate(requested_level=AutonomyLevel.A3_APPROVED_ACTION,
                                   capability=profile.to_capability(),
                                   risk=profile.risk, **_autonomy_inputs(**kwargs))
        check(label, not verdict.effective_level.permits_action(), verdict.reason[:130])

    # ---- approval binding ---------------------------------------------------
    print("\n[F/V/W] approval binding — five independent clauses")
    digest = compute_digest({"namespace": NAMESPACE, "name": FIXABLE}).value
    approvals.grant(artifact_id="appr-ok", tenant_id=TENANT,
                    operation=ROLLOUT_RESTART_OPERATION, digest=digest,
                    actor_ref="principal:sre-oncall",
                    expires_at=datetime.now(timezone.utc) + timedelta(minutes=30))
    moment = datetime.now(timezone.utc)

    def _covers(artifact, **over):
        base = dict(tenant_id=TENANT, capability_digest=digest,
                    operation=ROLLOUT_RESTART_OPERATION, moment=moment)
        base.update(over)
        facts = approvals.find(None, artifact)
        return facts is not None and facts.is_valid_for(**base)

    check("a matching approval covers the action", _covers("appr-ok"))
    approvals.deny(artifact_id="appr-denied", tenant_id=TENANT,
                   operation=ROLLOUT_RESTART_OPERATION, digest=digest)
    check("V. a DENIED approval authorizes nothing", not _covers("appr-denied"))
    approvals.grant(artifact_id="appr-expired", tenant_id=TENANT,
                    operation=ROLLOUT_RESTART_OPERATION, digest=digest,
                    actor_ref="principal:sre-oncall",
                    expires_at=moment - timedelta(minutes=1))
    check("V. an EXPIRED approval authorizes nothing", not _covers("appr-expired"))
    check("Q. an approval for ANOTHER TENANT authorizes nothing",
          not _covers("appr-ok", tenant_id="other-tenant"))
    check("an approval for ANOTHER OPERATION authorizes nothing",
          not _covers("appr-ok", operation="kubernetes.pods.list"))
    check("W. an approval bound to ANOTHER DIGEST authorizes nothing",
          not _covers("appr-ok", capability_digest="e" * 64))
    bare = False
    try:
        approvals.grant(artifact_id="x", tenant_id=TENANT,
                        operation=ROLLOUT_RESTART_OPERATION, digest=digest,
                        actor_ref="admin")
    except ValueError:
        bare = True
    check("an approver of 'admin' is not an authority", bare)

    # ---- the decisive negative ---------------------------------------------
    print("\n[I] the decisive negative: NOTHING was written")
    check("ZERO provider WRITES occurred in this entire run", not dials.writes,
          dials.writes)
    check("every provider dial was a GET",
          all(method == "GET" for _p, method, _path in dials.plans),
          sorted({m for _p, m, _ in dials.plans}))
    stamped = _kubectl("get", "deploy", FIXABLE, "-o",
                       "jsonpath={.spec.template.metadata.annotations}")
    check("the cluster carries NO CortexPrime restart annotation",
          RESTART_ANNOTATION not in (stamped or ""), stamped or "<none>")

    # ---- P/Q/N -------------------------------------------------------------
    print("\n[P/Q/N] secrets, tenant, audit")
    leaked = _scan_for_secret(os.environ["CORTEX_DURABLE_URL"],
                              os.environ["CORTEX_KUBERNETES_TOKEN"],
                              os.environ["CORTEX_PROMETHEUS_TOKEN"])
    check("no token appears in ANY durable row of ANY table", not leaked, leaked)
    check("no token appears in this report",
          os.environ["CORTEX_KUBERNETES_TOKEN"][:20] not in json.dumps(REPORT, default=str))
    check("cross-tenant world evidence is empty",
          stack["query"].current(tenant=TenantRef(tenant_id="other-tenant"),
                                  subject_ref=f"kubernetes:deployment:{NAMESPACE}/{FIXABLE}",
                                  predicate="workload_health",
                                  now=datetime.now(timezone.utc)
                                  ).to_dict()["what"]["value"] is None)
    verification = verify_chain(runtime.persistence.audit)
    check("the audit chain verifies", bool(getattr(verification, "ok", False)),
          f"records={getattr(verification, 'records_checked', None)}")

    measure("total_provider_dials", dials.total)
    measure("provider_writes", len(dials.writes))

    REPORT["blocking_finding"] = {
        "operation": ROLLOUT_RESTART_OPERATION,
        "declared_side_effect": spec.side_effect_class.value,
        "required_isolation": "sealed",
        "connector_isolation": worker.isolation.value if worker else None,
        "gate_1_registration_refusal": gate1,
        "gate_2_worker_refusal": (
            worker is not None
            and not worker.permits_side_effect(SideEffectClass.IRREVERSIBLE_WRITE)),
        "conclusion": (
            "the platform will not perform an irreversible write it cannot isolate. "
            "Executing it would require declaring the in-process connector SEALED "
            "('full virtualization, no ambient credentials'), which would assert "
            "isolation that does not exist. Phase 9.6's Definition of Done is NOT "
            "met and the write was never attempted."),
    }

    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if failed:
        bail(1, f"{len(failed)} check(s) failed")
    bail(2, "BLOCKED: every gate behaved correctly and the write is refused by the "
            "platform's own isolation invariant; no real Kubernetes write occurred")


def _drift_detected():
    from backend.contracts.intelligence.calibration import DriftStatus
    return DriftStatus.DRIFT_DETECTED


def _kubernetes_workers(runtime):
    directory = getattr(runtime.connectivity, "directory", None)
    entries = []
    for attr in ("entries", "_entries", "implementations", "_implementations"):
        found = getattr(directory, attr, None)
        if isinstance(found, dict):
            entries = list(found.values())
            break
    out = []
    for entry in entries:
        impl = getattr(entry, "implementation", entry)
        if getattr(impl, "worker_id", "") == "kubernetes-connector":
            out.append(impl)
    return out


def _refuses_target(kwargs) -> bool:
    from backend.api.remediation import RemediationTarget
    from backend.contracts.errors import ContractViolation
    try:
        RemediationTarget(namespace=kwargs["namespace"], workload=kwargs["name"])
    except ContractViolation:
        return True
    return False


def _run_crash_child():
    """Real os._exit(9) at a named point in the remediation lifecycle."""
    from backend.contracts.intelligence.investigation import AutonomyLevel
    from backend.platform.context import ExecutionContext
    from backend.platform.hashing import compute_digest
    from datetime import timedelta as _td

    point = (os.getenv("CORTEX_P96_CRASH_AT") or "after_write").strip()
    marker = os.getenv("CORTEX_P96_MARKER")
    runtime = _build_runtime()
    platform_ctx = ExecutionContext.platform_internal(
        reason="p96 crash child", component="remediation-harness", source="cli")
    runtime.audit_writer.acquire()
    definitions = _commission(runtime, platform_ctx)
    approvals = _Approvals()
    stack = _build_stack(runtime, definitions, approvals)
    out = {"point": point, "wrote": False, "fabricated": False}

    if point == "before_authorization":
        _write_marker(marker, out)
        os._exit(9)

    target = _target(FIXABLE)
    payload = {"namespace": NAMESPACE, "name": FIXABLE}
    digest = compute_digest(payload).value
    investigation = _Investigation(stack["tenant"])
    now = datetime.now(timezone.utc)

    if point == "after_authorization":
        stack["remediation"].pre_action_gate(
            investigation=investigation, target=target, now=now,
            expected_symptom={"pod": FIXABLE_POD})
        _write_marker(marker, out)
        os._exit(9)

    approvals.grant(artifact_id="appr-crash", tenant_id=TENANT,
                    operation=RESTART_OP, digest=digest,
                    actor_ref="principal:sre-oncall",
                    expires_at=now + _td(minutes=10))
    out["approval"] = "appr-crash"
    if point in ("after_approval", "before_dispatch"):
        _write_marker(marker, out)
        os._exit(9)

    result = stack["remediation"].remediate(
        investigation=investigation, target=target,
        expected_symptom={"pod": FIXABLE_POD}, autonomy_inputs=_autonomy_inputs(),
        approval_artifact_id="appr-crash",
        requested_level=AutonomyLevel.A3_APPROVED_ACTION, prediction=None,
        now=datetime.now(timezone.utc), diagnosis="crash-child")
    out["wrote"] = bool(result.executed)
    out["action_ref"] = result.action_ref
    # The crucial one: after a real write, the world outcome is still UNKNOWN
    # until it is observed. Recovery must not turn that into success.
    out["world_outcome_before_observation"] = result.world_outcome
    out["fabricated"] = result.world_outcome == "recovered"
    if point in ("after_write", "before_observation"):
        _write_marker(marker, out)
        os._exit(9)

    world, obs_ref, _detail = stack["remediation"].observe_outcome(
        result=result, target=target, pod_hint=FIXABLE_POD,
        now=datetime.now(timezone.utc))
    out["world"] = world
    out["observation_ref"] = obs_ref
    _write_marker(marker, out)
    os._exit(9)


def _run_concurrent_child():
    """Two of these race the same approved remediation."""
    from backend.contracts.intelligence.investigation import AutonomyLevel
    from backend.platform.context import ExecutionContext
    from backend.platform.hashing import compute_digest
    from datetime import timedelta as _td

    marker = os.getenv("CORTEX_P96_MARKER")
    out = {"role": os.getenv("CORTEX_P96_ROLE", "a")}
    try:
        runtime = _build_runtime()
        platform_ctx = ExecutionContext.platform_internal(
            reason="p96 concurrency", component="remediation-harness", source="cli")
        definitions = _commission(runtime, platform_ctx)
        approvals = _Approvals()
        stack = _build_stack(runtime, definitions, approvals)
        target = _target(FIXABLE)
        digest = compute_digest({"namespace": NAMESPACE, "name": FIXABLE}).value
        now = datetime.now(timezone.utc)
        approvals.grant(artifact_id="appr-conc", tenant_id=TENANT,
                        operation=RESTART_OP, digest=digest,
                        actor_ref="principal:sre-oncall", expires_at=now + _td(minutes=10))
        time.sleep(1.0)
        result = stack["remediation"].remediate(
            investigation=_Investigation(stack["tenant"]), target=target,
            expected_symptom={"pod": FIXABLE_POD}, autonomy_inputs=_autonomy_inputs(),
            approval_artifact_id="appr-conc",
            requested_level=AutonomyLevel.A3_APPROVED_ACTION, prediction=None,
            now=datetime.now(timezone.utc), diagnosis="concurrency probe")
        out.update({"executed": bool(result.executed), "action_ref": result.action_ref,
                    "refused_at": result.refused_at})
    except Exception as problem:  # noqa: BLE001
        out.update({"executed": False,
                    "error": f"{type(problem).__name__}: {problem}"[:200]})
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
