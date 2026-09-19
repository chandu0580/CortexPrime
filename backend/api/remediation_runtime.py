"""The governed remediation runtime — Phase 11.4 (ADR-124).

REAL INCIDENT -> INVESTIGATION -> REMEDIATION PLAN -> GOVERNANCE -> APPROVAL
WHEN REQUIRED -> CONTROLLED EXECUTION -> INDEPENDENT WORLD-STATE VERIFICATION ->
RECOVERY -> HONEST OUTCOME -> LEARNING.

This module is the loop, and it holds no authority of its own. Every decision
that matters is made by something that already existed:

    proposal ........ the model, through GovernedModelBoundary (schema-validated)
    validation/plan . RemediationPlanner (registry, diagnosis, target, risk)
    policy .......... AutonomyPolicy (Phase 8.8) over calibration from real outcomes
    approval ........ cp_approval -- a human with scoped authority, or a policy
                      decision recorded in the same authority for a compensable class
    action digest ... canonical_approval_digest (ADR-090), then the gateway's own
    execution ....... GovernedCapabilityWriter -> gateway -> CONTAINED rollback worker
    world ........... GovernedCapabilityReader (a different ServiceAccount)
    verification .... AssuranceVerifier (Phase 7.7)
    recovery ........ the execution plane's RecoveryAction vocabulary, bounded
    learning ........ Prediction / PredictionEvaluation / WorldVerification --
                      the calibration substrate (Phase 8.7); advisory only

What it adds is ORDER and HONESTY: nothing executes before its approval is
granted and re-checked against a fresh read of the world; nothing is reported
as a success that independent verification did not establish; nothing retries
a mutation; and every stage is appended to the reasoning ledger before the next
one begins, so a crash leaves a legible trail rather than a guess.

Composition-root rule: this module imports ONE bounded context (execution, for
the recovery vocabulary). The approval store, the digest function, the
capability's implied risk and the governed doors are handed in.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Optional

from backend.api.remediation_planning import (
    ACTION_ROLLBACK, OUTCOME_PREDICATE, REGRESSION_HYPOTHESIS, TARGET_PREDICATE, CapabilityFacts,
    DiagnosisFacts, PlanningScope, RemediationPlanner, WorldSnapshot, workload_of,
)
from backend.api.remediation_verification import BACKOFF_REASONS, RemediationVerifier
from backend.contracts.remediation import PlanAuthority, RemediationPlan, RemediationStage
from backend.platform.hashing import compute_digest

log = logging.getLogger("cortexprime.remediation.runtime")

__all__ = [
    "RemediationRuntimeConfig", "RemediationPorts", "RemediationRuntime", "start_embedded_remediator",
    "EmbeddedRemediator", "POLICY_LABEL", "HARNESS_VERSION_LABEL", "RUNTIME_PRINCIPAL",
]

POLICY_LABEL = "phase114-remediation/1"
HARNESS_VERSION_LABEL = "phase114-remediation"
RUNTIME_PRINCIPAL = "remediation-runtime"
RUNTIME_REQUESTER = f"platform:{RUNTIME_PRINCIPAL}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RemediationRuntimeConfig:
    tenant_id: str
    namespace: str
    cluster_ref: str = "kubernetes"
    environment: str = "development"
    production: bool = False
    principal_id: str = RUNTIME_PRINCIPAL
    autonomy_policy_version: str = "phase114-autonomy/1"
    #: The explicit, versioned choice ADR-124 asks the owner to ratify: whether a
    #: COMPENSABLE action may earn delegated autonomy. False keeps every plan on
    #: the human-approval path.
    compensable_autonomy: bool = False
    min_decided_outcomes: int = 8
    min_support_rate: float = 0.8
    min_assurance_coverage: float = 0.75
    approval_ttl_seconds: int = 1800
    approval_poll_seconds: float = 2.0
    verification_window_seconds: int = 180
    verification_poll_seconds: float = 5.0
    #: Explicit bounds (mandate §31). Mutations are never retried; an UNKNOWN
    #: outcome is reconciled by independent verification, never by re-running.
    max_executions_per_incident: int = 2
    max_recovery_attempts: int = 1
    mutation_retries: int = 0
    breaker_lookback_seconds: int = 86400
    model_provider: str = ""
    model_name: str = ""
    model_timeout_seconds: float = 120.0
    #: A reasoning model spends part of its output budget before the answer;
    #: 4096 was measured exhausted with an empty answer (record run 1, F-1).
    model_max_output_tokens: int = 16384
    emergency_stop: bool = False
    harness_version: str = HARNESS_VERSION_LABEL
    metric_operation: Optional[str] = "prometheus.deployment_unavailable"
    health_lookback_seconds: int = 7200
    max_queue: int = 64

    @classmethod
    def from_env(cls, *, tenant_id: str, namespace: str) -> "RemediationRuntimeConfig":
        def _f(name: str, default: float) -> float:
            raw = (os.getenv(name) or "").strip()
            return float(raw) if raw else default

        def _i(name: str, default: int) -> int:
            raw = (os.getenv(name) or "").strip()
            return int(raw) if raw else default

        def _b(name: str, default: bool) -> bool:
            raw = (os.getenv(name) or "").strip().lower()
            return default if not raw else raw in ("1", "true", "yes")

        return cls(
            tenant_id=tenant_id, namespace=namespace,
            cluster_ref=(os.getenv("CORTEX_SIGNAL_CLUSTER_REF") or "kubernetes").strip(),
            environment=(os.getenv("CORTEX_REMEDIATION_ENVIRONMENT") or "development").strip(),
            production=_b("CORTEX_REMEDIATION_PRODUCTION", False),
            autonomy_policy_version=(os.getenv("CORTEX_REMEDIATION_AUTONOMY_POLICY") or "phase114-autonomy/1").strip(),
            compensable_autonomy=_b("CORTEX_REMEDIATION_COMPENSABLE_AUTONOMY", False),
            min_decided_outcomes=_i("CORTEX_REMEDIATION_MIN_DECIDED_OUTCOMES", 8),
            approval_ttl_seconds=_i("CORTEX_REMEDIATION_APPROVAL_TTL_SECONDS", 1800),
            verification_window_seconds=_i("CORTEX_REMEDIATION_VERIFICATION_WINDOW_SECONDS", 180),
            verification_poll_seconds=_f("CORTEX_REMEDIATION_VERIFICATION_POLL_SECONDS", 5.0),
            max_executions_per_incident=_i("CORTEX_REMEDIATION_MAX_EXECUTIONS_PER_INCIDENT", 2),
            model_provider=(os.getenv("CORTEX_REMEDIATION_MODEL_PROVIDER") or "").strip(),
            model_name=(os.getenv("CORTEX_REMEDIATION_MODEL") or "").strip(),
            model_timeout_seconds=_f("CORTEX_REMEDIATION_MODEL_TIMEOUT_SECONDS", 120.0),
            model_max_output_tokens=_i("CORTEX_REMEDIATION_MODEL_MAX_OUTPUT_TOKENS", 16384),
            emergency_stop=_b("CORTEX_REMEDIATION_EMERGENCY_STOP", False),
        )

    @property
    def policy_version(self) -> str:
        """Bound into every plan's parameters, so into its approval digest. A
        policy change makes every earlier approval a different action."""
        return f"{self.autonomy_policy_version}+{POLICY_LABEL}+compensable={int(self.compensable_autonomy)}"

    @property
    def model_identity(self) -> str:
        return f"{self.model_provider}:{self.model_name}" if self.model_provider else "deterministic"

    def autonomy_config(self) -> Any:
        from backend.contracts.intelligence import AutonomyLevel
        from backend.contracts.intelligence.autonomy import AutonomyPolicyConfig

        return AutonomyPolicyConfig(
            policy_version=self.autonomy_policy_version, min_decided_outcomes=self.min_decided_outcomes,
            min_support_rate=self.min_support_rate, min_assurance_coverage=self.min_assurance_coverage,
            compensable_autonomy=self.compensable_autonomy,
            max_level_low=AutonomyLevel.A4_AUTONOMOUS,
            # Bounded actions under policy (mandate A3) may be delegated; high-impact
            # actions (mandate A4) need a human; critical ones are prohibited (A5).
            max_level_medium=AutonomyLevel.A4_AUTONOMOUS if self.compensable_autonomy
            else AutonomyLevel.A3_APPROVED_ACTION,
            max_level_high=AutonomyLevel.A3_APPROVED_ACTION,
            max_level_critical=AutonomyLevel.A1_INVESTIGATE,
        )


@dataclass
class RemediationPorts:
    """Everything the loop may touch, handed in by composition. Nothing else."""

    tenant: Any
    reader: Any
    writer: Any
    approvals: Any
    reasoning: Any
    observations: Any
    observer: Any
    derivation: Any
    assurance: Any
    verifications: Any
    idempotency: Any
    investigations: Any
    context_factory: Callable[[], Any]
    approval_digest: Callable[[Mapping[str, Any]], str]
    capability: CapabilityFacts
    authorization_operation: str
    proposal_port: Any = None
    fallback_proposer: Any = None
    audit: Any = None
    traces: Any = None
    metrics: Any = None


class RemediationRuntime:
    def __init__(self, *, config: RemediationRuntimeConfig, ports: RemediationPorts,
                 clock: Callable[[], datetime] = _utcnow, sleep: Callable[[float], None] = time.sleep) -> None:
        self._config = config
        self._ports = ports
        self._clock = clock
        self._sleep = sleep
        self._planner = RemediationPlanner(
            scope=PlanningScope(tenant_id=config.tenant_id, cluster_ref=config.cluster_ref,
                                namespace=config.namespace, environment=config.environment,
                                production=config.production, principal_id=config.principal_id,
                                policy_version=config.policy_version,
                                verification_window_seconds=config.verification_window_seconds),
            capability=ports.capability, approval_digest=ports.approval_digest,
            autonomy=self._decide_autonomy)
        self._verifier = RemediationVerifier(
            reader=ports.reader, context_factory=ports.context_factory, observer=ports.observer,
            derivation=ports.derivation, assurance=ports.assurance, tenant=ports.tenant,
            clock=clock, sleep=sleep)
        self._queue: "queue.Queue" = queue.Queue(maxsize=config.max_queue)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="cortexprime-remediator", daemon=True)
        self._lock = threading.RLock()
        self._seen: set = set()
        self._pending: dict = {}
        self._sequence: dict = {}
        self.results: list = []

    # -- lifecycle ------------------------------------------------------------

    def start(self) -> "RemediationRuntime":
        self.resume()
        self._thread.start()
        return self

    def stop(self, timeout: float = 30.0) -> None:
        self._stop.set()
        self._thread.join(timeout=timeout)

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def offer(self, outcome: Any) -> bool:
        """The investigator's outcome hook. Non-blocking; one entry per investigation."""
        ref = getattr(outcome, "investigation_ref", None) or (outcome or {}).get("investigation_ref")
        if not ref:
            return False
        with self._lock:
            if ref in self._seen:
                return False
            self._seen.add(ref)
        try:
            self._queue.put_nowait(ref)
            return True
        except queue.Full:
            with self._lock:
                self._seen.discard(ref)
            log.warning("remediation queue full; %s deferred", ref)
            return False

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                ref = self._queue.get(timeout=max(0.2, self._config.approval_poll_seconds))
            except queue.Empty:
                ref = None
            if ref is not None:
                try:
                    self.results.append(self.handle_investigation(ref))
                except Exception:  # noqa: BLE001 - never silent
                    log.exception("remediation of %s crashed", ref)
            try:
                self.process_pending()
            except Exception:  # noqa: BLE001
                log.exception("pending approvals could not be processed")

    # -- the ledger -----------------------------------------------------------

    def _firewall(self, document: Mapping[str, Any]) -> None:
        from backend.platform.credentials.inspection import find_secrets

        found = find_secrets(dict(document))
        if found:
            raise ValueError(f"a remediation record carried secret-shaped content ({len(found)} finding(s)); refused")

    def _record(self, *, kind: str, subject_ref: str, predicate: str, record: Mapping[str, Any],
                refs: Mapping[str, Any]) -> Optional[str]:
        from backend.platform.identity.generators import prefixed_id

        document = dict(record)
        self._firewall(document)
        identity = compute_digest({"kind": kind, "subject": subject_ref, "predicate": predicate,
                                   "record": document}).value
        reasoning_id = prefixed_id("wreason")
        newly = self._ports.reasoning.record(
            reasoning_id=reasoning_id, identity_digest=identity, tenant_id=self._config.tenant_id,
            kind=kind, subject_ref=subject_ref, predicate=predicate, record=document, refs=dict(refs),
            recorded_at=self._clock())
        return reasoning_id if newly else None

    def _event(self, plan_id: str, stage: RemediationStage, *, investigation_ref: str = "",
               incident_ref: str = "", **detail: Any) -> None:
        with self._lock:
            sequence = self._sequence.get(plan_id)
            if sequence is None:
                sequence = len(self.events_for(plan_id))
            sequence += 1
            self._sequence[plan_id] = sequence
        record = {"stage": stage.value, "plan_id": plan_id, "sequence": sequence,
                  "investigation_ref": investigation_ref, "incident_ref": incident_ref,
                  "authority": detail.pop("authority", None), **detail}
        try:
            self._record(kind="remediation_event", subject_ref=plan_id, predicate=stage.value,
                         record=record, refs={"plan_id": plan_id, "investigation_ref": investigation_ref})
        except Exception:  # noqa: BLE001 - a lost stage is logged loudly, never hidden
            log.exception("remediation event %s/%s was not recorded", plan_id, stage.value)
        log.info("remediation %s: %s %s", plan_id, stage.value,
                 {k: v for k, v in detail.items() if k in ("reason", "classification", "decider", "execution_ref")})

    def events_for(self, plan_id: str) -> list:
        try:
            rows = self._ports.reasoning.list_for_subject(tenant_id=self._config.tenant_id, subject_ref=plan_id)
        except Exception:  # noqa: BLE001
            return []
        return [r for r in rows if getattr(r.kind, "value", r.kind) == "remediation_event"]

    def _stages(self, plan_id: str) -> list:
        return [str((r.record or {}).get("stage")) for r in self.events_for(plan_id)]

    def _audit(self, kind: str, plan_id: str, detail: Mapping[str, Any]) -> bool:
        if self._ports.audit is None:
            return False
        try:
            from backend.contracts.audit import AuditEventKind

            self._ports.audit.record_in_context(AuditEventKind[kind], self._ports.context_factory(),
                                                subject_reference=plan_id, detail=dict(detail))
            return True
        except Exception as exc:  # noqa: BLE001 - reported, and recorded on the event
            log.error("audit %s for %s was not recorded: %s", kind, plan_id, exc)
            return False

    def _count(self, name: str, *labels: str) -> None:
        metrics = self._ports.metrics
        if metrics is None:
            return
        try:
            getattr(metrics, name).labels(*labels).inc()
        except Exception:  # noqa: BLE001
            pass

    def _observe(self, name: str, value: float, *labels: str) -> None:
        metrics = self._ports.metrics
        if metrics is None:
            return
        try:
            getattr(metrics, name).labels(*labels).observe(value)
        except Exception:  # noqa: BLE001
            pass

    # -- POLICY: autonomy ------------------------------------------------------

    def _reliability(self, now: datetime) -> Any:
        from backend.contracts.intelligence.calibration import CalibrationPolicy, PredictionClass
        from backend.contracts.tenant import TenantRef
        from backend.intelligence.application import VerdictView
        from backend.intelligence.application.calibration import (
            CalibrationDatasetBuilder, ReliabilityEstimator,
        )

        verifications = self._ports.verifications

        class _Verdicts:
            def list_for_subject(self, *, tenant_id, subject_ref, predicate, known_at=None):
                rows = verifications.list_for_subject(tenant_id=tenant_id, subject_ref=subject_ref,
                                                      predicate=predicate, known_at=known_at)
                return tuple(VerdictView(verdict=v.verdict.value, verified_at=v.recorded_at,
                                         verification_ref=v.record_id) for v in rows)

        policy = CalibrationPolicy(min_decided_samples=self._config.min_decided_outcomes)
        builder = CalibrationDatasetBuilder(prediction_port=self._ports.reasoning, verification_port=_Verdicts(),
                                            environment=self._config.environment)
        dataset = builder.build(tenant=TenantRef(tenant_id=self._config.tenant_id), policy=policy, now=now,
                                provider_label=self._config.model_identity)
        pclass = PredictionClass(subject_type=f"kubernetes:deployment:{self._config.namespace}",
                                 predicate=OUTCOME_PREDICATE, environment=self._config.environment,
                                 model_identity=self._config.model_identity,
                                 harness_version=self._config.harness_version)
        return ReliabilityEstimator().estimate(dataset=dataset, prediction_class=pclass, policy=policy, now=now,
                                               allow_fallback=False)

    def _breaker(self, now: datetime) -> Any:
        from backend.contracts.intelligence.autonomy import CircuitBreakerConfig

        since = now - timedelta(seconds=self._config.breaker_lookback_seconds)
        failures = verification_failures = 0
        try:
            rows = self._ports.reasoning.list_by_kind(tenant_id=self._config.tenant_id, kind="remediation_event")
        except Exception:  # noqa: BLE001
            rows = ()
        for row in rows:
            if row.recorded_at < since:
                continue
            stage = (row.record or {}).get("stage")
            if stage == RemediationStage.EXECUTION_FAILED.value:
                failures += 1
            if stage == RemediationStage.VERIFICATION_FAILED.value:
                verification_failures += 1
        return CircuitBreakerConfig().evaluate(action_failures=failures,
                                               verification_failures=verification_failures)

    def _decide_autonomy(self, *, capability: Any, risk: Any, requested: Any, now: datetime) -> Any:
        from backend.contracts.intelligence.autonomy import AutonomyScope, EmergencyStopState
        from backend.contracts.intelligence.calibration import DriftStatus
        from backend.contracts.tenant import TenantRef
        from backend.intelligence.application.autonomy import AutonomyPolicy

        reliability = None
        try:
            reliability = self._reliability(now)
        except Exception:  # noqa: BLE001 - no calibration is INSUFFICIENT_EVIDENCE, never a pass
            log.exception("calibration could not be computed; autonomy is not eligible")
        drift = getattr(DriftStatus, "UNKNOWN_DRIFT_STATUS", DriftStatus.NO_DRIFT)
        return AutonomyPolicy().evaluate(
            requested_level=requested,
            scope=AutonomyScope(tenant=TenantRef(tenant_id=self._config.tenant_id),
                                environment=self._config.environment, service=self._config.namespace,
                                capability_ref=capability.capability_ref, operation=capability.operation,
                                resource_class="deployment"),
            capability=capability, risk=risk, reliability=reliability, drift=drift, world_fresh=True,
            world_conflicted=False,
            versions={"model_identity": self._config.model_identity,
                      "harness_version": self._config.harness_version},
            stop_state=EmergencyStopState.STOP_ACTIVE if self._config.emergency_stop else EmergencyStopState.RUNNING,
            breaker=self._breaker(now), config=self._config.autonomy_config(), now=now)

    # -- 1. investigation -> plan -----------------------------------------------

    def _assessment(self, investigation_ref: str) -> tuple:
        rows = [r for r in self._ports.reasoning.list_for_subject(tenant_id=self._config.tenant_id,
                                                                  subject_ref=investigation_ref)
                if getattr(r.kind, "value", r.kind) == "assessment"]
        if not rows:
            return None, None
        return dict(rows[-1].record or {}), rows[-1].reasoning_id

    def _read(self, operation: str, payload: Mapping[str, Any]) -> Any:
        try:
            return self._ports.reader.read(self._ports.context_factory(), operation=operation, payload=dict(payload))
        except Exception as exc:  # noqa: BLE001 - a failed read is an absent answer
            log.warning("remediation read %s failed: %s", operation, exc)
            return None

    def _world(self, namespace: str, name: str, now: datetime) -> tuple:
        from backend.api.governed_read_observer import ObservationLeg

        dep = self._read("kubernetes.deployment.get", {"namespace": namespace, "name": name})
        rs = self._read("kubernetes.replicasets.list", {"namespace": namespace})
        if dep is None or not dep.succeeded or rs is None or not rs.succeeded:
            reason = (getattr(dep, "failure_reason", None) or getattr(rs, "failure_reason", None)
                      or "no answer")
            return None, f"the target could not be read through the governed path: {reason}"
        evidence = dict(dep.evidence)
        refs: tuple = ()
        try:
            value = {k: evidence.get(k) for k in ("uid", "generation", "revision", "templateDigest", "replicas",
                                                  "availableReplicas", "revisionHistoryLimit",
                                                  "persistentVolumeClaims", "paused")
                     if evidence.get(k) is not None}
            recorded = self._ports.observer.observe(
                tenant=self._ports.tenant, outcome=dep, now=now,
                legs=(ObservationLeg(subject_ref=f"kubernetes:deployment:{namespace}/{name}",
                                     predicate=TARGET_PREDICATE, value=value, observed_at=now),))
            refs = tuple(obs.record_id for obs, _ in recorded)
        except Exception:  # noqa: BLE001
            log.exception("the plan-time target observation was not recorded")
        records = [r for r in rs.evidence.get("replicaSets") or () if isinstance(r, Mapping)]
        healthy = self._healthy_revisions(namespace, name, records, now)
        return WorldSnapshot(deployment=evidence, replicasets=records, observation_refs=refs,
                             healthy_revisions=healthy, read_at=now), None

    def _healthy_revisions(self, namespace: str, name: str, records: list, now: datetime) -> dict:
        """Revisions whose pods the signal fabric OBSERVED running without a
        back-off. Evidence, not assumption: a revision nobody saw healthy is a
        revision of unknown health, and the risk model says so."""
        out: dict = {}
        try:
            observations = self._ports.observations.list_recent(
                tenant_id=self._config.tenant_id,
                since=now - timedelta(seconds=self._config.health_lookback_seconds),
                subject_prefix=f"kubernetes:pod:{namespace}/{name}-", limit=2000)
        except Exception:  # noqa: BLE001
            return out
        for record in records:
            rs_name, revision = record.get("name"), record.get("revision")
            if not rs_name or not revision:
                continue
            refs = []
            for obs in observations:
                pod = str(getattr(obs, "subject_ref", "")).rsplit("/", 1)[-1]
                value = getattr(obs, "value", None) or {}
                if not pod.startswith(f"{rs_name}-") or not isinstance(value, Mapping):
                    continue
                if value.get("phase") == "Running" and value.get("waitingReason") in (None, "") \
                        and value.get("eventType") != "DELETED":
                    refs.append(obs.record_id)
            if refs:
                out[str(revision)] = tuple(refs[:5])
        return out

    def _diagnosis(self, investigation_ref: str, assessment: Mapping[str, Any], assessment_ref: str) -> DiagnosisFacts:
        digest = rollout_ref = None
        try:
            investigation = self._ports.investigations.reconstruct(tenant=self._ports.tenant,
                                                                   investigation_ref=investigation_ref)
            for ref in investigation.evidence_refs:
                if not str(ref).startswith("wobs"):
                    continue
                obs = self._ports.observations.get_observation(tenant_id=self._config.tenant_id,
                                                               observation_id=ref)
                if obs is not None and obs.predicate == "rollout_history" and isinstance(obs.value, Mapping):
                    digest = obs.value.get("currentPodTemplateDigest") or digest
                    rollout_ref = ref
        except Exception:  # noqa: BLE001
            log.exception("the diagnosed rollout history of %s could not be read", investigation_ref)
        return DiagnosisFacts(assessment=assessment, assessment_ref=assessment_ref,
                              diagnosed_template_digest=digest, rollout_observation_ref=rollout_ref)

    def _proposal_document(self, *, incident_ref: str, workload: tuple, assessment: Mapping[str, Any],
                           world: Optional[WorldSnapshot]) -> dict:
        keep = ("outcome", "confidence", "root_cause", "root_cause_hypothesis", "basis", "supporting_evidence",
                "contradicting_evidence", "eliminated", "alternatives_open", "unknowns", "next_step",
                "recommended_action_candidate")
        document = {
            "incident_ref": incident_ref,
            "incident_workload": {"kind": "Deployment", "namespace": workload[0], "name": workload[1]},
            "assessment": {k: assessment.get(k) for k in keep},
            "allowed_actions": ["deployment.rollback", "no_action"],
            "note": "you propose; the platform validates the target, computes the risk and decides authority",
        }
        document["assessment"]["weights"] = [
            {k: w.get(k) for k in ("observation_ref", "hypothesis_ref", "role", "source_ref", "predicate")}
            for w in assessment.get("weights") or () if isinstance(w, Mapping)][:40]
        if world is not None:
            dep = world.deployment
            current_digest = dep.get("templateDigest")
            document["current"] = {k: dep.get(k) for k in ("revision", "image", "replicas", "availableReplicas",
                                                           "generation")}
            document["current"]["templateDigest"] = str(current_digest or "")[:16]
            # Phase 11.4 record run 1 (F-2): the history used to carry each old
            # ReplicaSet's replica counts, which the controller sets to 0 after
            # every rollout, and only the image tag. A real model read "revision
            # 1 had 0 replicas" as "a rollback scales to zero" and "same image"
            # as "same behaviour". Both were artefacts of the document, not
            # facts about the revisions; the document now states what a
            # revision IS (its pod template) and what a rollback DOES.
            document["rollout_history"] = sorted(
                ({"revision": r.get("revision"), "image": r.get("image"), "createdAt": r.get("creationTimestamp"),
                  "templateDigest": str(r.get("podTemplateDigest") or "")[:16],
                  "isCurrent": bool(current_digest) and r.get("podTemplateDigest") == current_digest,
                  "differsFromCurrentTemplate": bool(current_digest) and r.get("podTemplateDigest") != current_digest,
                  "observedHealthy": str(r.get("revision")) in world.healthy_revisions}
                 for r in world.replicasets if r.get("ownerUid") == dep.get("uid")),
                key=lambda r: int(str(r.get("revision") or 0)), reverse=True)[:10]
            document["rollback_semantics"] = (
                "A rollback copies the chosen revision's pod template into the Deployment. The Deployment keeps "
                f"its own replica count ({dep.get('replicas')}). The controller scales every superseded "
                "ReplicaSet to 0 after each rollout, so an old revision's replica count says nothing about it. "
                "Two revisions with the same image tag can run different container configuration (command, "
                "arguments, environment, resources): compare templateDigest. observedHealthy means the platform "
                "observed that revision's pods running without a back-off.")
        return document

    def _propose(self, *, investigation_ref: str, document: Mapping[str, Any], now: datetime) -> Any:
        from backend.intelligence.application.proposal import ModelProposalFailed
        from backend.intelligence.application.remediation_proposal import DeterministicRemediationProposer

        mission = f"remediation:{investigation_ref}"
        fallback = self._ports.fallback_proposer or DeterministicRemediationProposer()
        if self._ports.proposal_port is None:
            self._count("remediation_model_calls", "deterministic", "not_configured")
            return fallback.propose(document=document, mission_id=mission, now=now, failure="no model configured")
        provider = self._config.model_provider or "model"
        try:
            proposal = self._ports.proposal_port.propose(document=document, mission_id=mission, now=now)
            self._count("remediation_model_calls", provider, "ok")
            metrics = self._ports.metrics
            if metrics is not None:
                try:
                    metrics.remediation_model_tokens.labels(provider, "prompt").inc(proposal.prompt_tokens)
                    metrics.remediation_model_tokens.labels(provider, "completion").inc(proposal.completion_tokens)
                except Exception:  # noqa: BLE001
                    pass
            return proposal
        except ModelProposalFailed as exc:
            self._count("remediation_model_calls", provider, exc.category)
            if exc.category == "schema_violation":
                # Malformed output is a REJECTED proposal, not a fallback trigger:
                # the model spoke, and what it said was not admissible.
                return exc
            return fallback.propose(document=document, mission_id=mission, now=now,
                                    failure=f"{exc.category}: {exc.reason}"[:200])

    def handle_investigation(self, investigation_ref: str) -> dict:
        """Plan ONE concluded investigation, then govern the plan."""
        from backend.contracts.remediation import ProposalDecision
        from backend.intelligence.application.proposal import ModelProposalFailed

        now = self._clock()
        assessment, assessment_ref = self._assessment(investigation_ref)
        if assessment is None:
            return {"investigation_ref": investigation_ref, "result": "no_assessment"}
        incident_ref = str(assessment.get("incident_ref") or "")
        workload = workload_of(incident_ref)
        decision_subject = "rdecision_" + compute_digest({"investigation": investigation_ref}).value[:24]
        if workload is None or workload[0] != self._config.namespace:
            return self._record_decision(ProposalDecision(
                proposal_digest="absent", incident_ref=incident_ref or "unknown", investigation_ref=investigation_ref,
                tenant_id=self._config.tenant_id, stage=RemediationStage.PROPOSAL_REJECTED, requested_action="",
                reasons=("the incident is not a workload in this tenant's namespace",), proposal_source="none",
                decided_at=now), decision_subject)
        if assessment.get("outcome") not in ("ROOT_CAUSE_IDENTIFIED", "LIKELY_CAUSE"):
            return self._record_decision(ProposalDecision(
                proposal_digest="absent", incident_ref=incident_ref, investigation_ref=investigation_ref,
                tenant_id=self._config.tenant_id, stage=RemediationStage.RECOMMENDATION_ONLY, requested_action="",
                reasons=(f"no remediation is planned on an {assessment.get('outcome')} conclusion; "
                         "the investigation's next step is the recommendation",), proposal_source="none",
                decided_at=now, recommendation=assessment.get("next_step")), decision_subject)

        world, unreadable = self._world(workload[0], workload[1], now)
        document = self._proposal_document(incident_ref=incident_ref, workload=workload, assessment=assessment,
                                           world=world)
        proposal = self._propose(investigation_ref=investigation_ref, document=document, now=now)
        if isinstance(proposal, ModelProposalFailed):
            return self._record_decision(ProposalDecision(
                proposal_digest="schema-rejected", incident_ref=incident_ref, investigation_ref=investigation_ref,
                tenant_id=self._config.tenant_id, stage=RemediationStage.PROPOSAL_REJECTED, requested_action="",
                reasons=(f"the model's proposal failed the schema: {proposal.reason}"[:400],),
                proposal_source=f"model:{self._config.model_identity}", decided_at=now), decision_subject)
        if world is None:
            return self._record_decision(ProposalDecision(
                proposal_digest=proposal.digest, incident_ref=incident_ref, investigation_ref=investigation_ref,
                tenant_id=self._config.tenant_id, stage=RemediationStage.PROPOSAL_REJECTED,
                requested_action=proposal.action, reasons=(unreadable or "the world could not be read",),
                proposal_source=f"{proposal.source}:{proposal.model_identity}", decided_at=now), decision_subject,
                proposal=proposal)

        diagnosis = self._diagnosis(investigation_ref, assessment, assessment_ref)
        result = self._planner.plan(incident_ref=incident_ref, investigation_ref=investigation_ref,
                                    proposal=proposal, diagnosis=diagnosis, world=world, now=now)
        if not result.planned:
            return self._record_decision(result.decision, decision_subject, proposal=proposal,
                                         autonomy=result.autonomy)
        return self._govern(result.plan, proposal=proposal, autonomy=result.autonomy)

    def _record_decision(self, decision: Any, subject: str, *, proposal: Any = None, autonomy: Any = None) -> dict:
        document = decision.to_dict()
        if proposal is not None and hasattr(proposal, "to_dict"):
            document["proposal"] = proposal.to_dict()
        if autonomy is not None and hasattr(autonomy, "to_dict"):
            document["autonomy_decision"] = autonomy.to_dict()
        try:
            self._record(kind="remediation_event", subject_ref=subject, predicate=decision.stage.value,
                         record={"stage": decision.stage.value, "plan_id": subject, "sequence": 1,
                                 "investigation_ref": decision.investigation_ref,
                                 "incident_ref": decision.incident_ref, "decision": document},
                         refs={"investigation_ref": decision.investigation_ref})
        except Exception:  # noqa: BLE001
            log.exception("the proposal decision for %s was not recorded", decision.investigation_ref)
        self._count("remediation_proposals_rejected", decision.stage.value)
        self._audit("POLICY_EVALUATED", subject, {"stage": decision.stage.value,
                                                  "reasons": list(decision.reasons)[:3],
                                                  "requested_action": decision.requested_action})
        return {"investigation_ref": decision.investigation_ref, "result": decision.stage.value,
                "subject": subject, "reasons": list(decision.reasons)}

    # -- 2. GOVERNANCE: record, decide, approve --------------------------------

    def _govern(self, plan: RemediationPlan, *, proposal: Any, autonomy: Any) -> dict:
        document = plan.to_dict()
        document["proposal"] = proposal.to_dict()
        self._record(kind="remediation_plan", subject_ref=plan.plan_id, predicate="plan", record=document,
                     refs={"investigation_ref": plan.investigation_ref, "incident_ref": plan.incident_ref,
                           "evidence": list(plan.evidence_refs)})
        common = dict(investigation_ref=plan.investigation_ref, incident_ref=plan.incident_ref)
        self._event(plan.plan_id, RemediationStage.PLANNED, authority=plan.authority.value,
                    risk=plan.risk.level.value, reversibility=plan.reversibility.value,
                    action_digest=plan.action_digest, **common)
        self._count("remediation_plans", plan.authority.value)
        if autonomy is not None:
            self._event(plan.plan_id, RemediationStage.AUTONOMY_DECIDED, authority=plan.authority.value,
                        eligibility=getattr(autonomy.eligibility, "value", None),
                        effective_level=getattr(autonomy.effective_level, "value", None),
                        approval_requirement=getattr(autonomy.approval_requirement, "value", None),
                        reason=autonomy.reason, autonomy_decision=autonomy.to_dict(), **common)
        audited = self._audit("POLICY_EVALUATED", plan.plan_id, {
            "stage": "planned", "authority": plan.authority.value, "risk": plan.risk.level.value,
            "reversibility": plan.reversibility.value, "action_digest": plan.action_digest,
            "policy_version": plan.policy_version})
        if plan.authority is PlanAuthority.RECOMMENDATION_ONLY:
            self._event(plan.plan_id, RemediationStage.RECOMMENDATION_ONLY, reason=plan.authority_reason, **common)
            self._close(plan, outcome="not_executed", reason="recommendation only", categories=("recommendation",))
            return {"plan_id": plan.plan_id, "result": "recommendation_only", "audited": audited}

        approval_id = self._request_approval(plan)
        if approval_id is None:
            self._close(plan, outcome="not_executed", reason="the approval request could not be recorded",
                        categories=())
            return {"plan_id": plan.plan_id, "result": "approval_request_failed"}
        if plan.authority is PlanAuthority.AUTONOMOUS:
            decided = self._ports.approvals.decide(
                approval_id=approval_id, tenant_id=self._config.tenant_id,
                outcome=_approval_outcome("granted"),
                decided_by=f"policy:autonomy/{self._config.autonomy_policy_version}",
                decided_at=self._clock(),
                justification=(f"delegated autonomy decision {plan.autonomy_decision_id}: "
                               f"{plan.authority_reason}")[:2000])
            if not decided:
                self._event(plan.plan_id, RemediationStage.EXECUTION_REFUSED,
                            reason="the delegated approval could not be recorded", **common)
                self._close(plan, outcome="not_executed", reason="no approval", categories=())
                return {"plan_id": plan.plan_id, "result": "delegated_approval_failed"}
            self._event(plan.plan_id, RemediationStage.APPROVAL_GRANTED, approval_id=approval_id,
                        decider=f"policy:autonomy/{self._config.autonomy_policy_version}", decider_kind="policy",
                        authority=plan.authority.value, **common)
            self._count("remediation_approvals", "granted", "policy")
            self._audit("APPROVAL_GRANTED", plan.plan_id, {"approval_id": approval_id, "decider_kind": "policy",
                                                           "autonomy_decision": plan.autonomy_decision_id})
            return self.execute_plan(plan, approval_id=approval_id, authority_kind="autonomous")
        with self._lock:
            self._pending[plan.plan_id] = (plan, approval_id)
        return {"plan_id": plan.plan_id, "result": "awaiting_approval", "approval_id": approval_id}

    def _request_approval(self, plan: RemediationPlan) -> Optional[str]:
        from backend.platform.identity.generators import prefixed_id

        now = self._clock()
        approval_id = prefixed_id("appr")
        identity = f"{plan.action_digest}:{RUNTIME_REQUESTER}:{plan.plan_id}"[:128]
        preview = _approval_preview(plan)
        try:
            created = self._ports.approvals.request(
                approval_id=approval_id, identity_digest=identity, tenant_id=self._config.tenant_id,
                capability_ref=plan.capability_ref, capability_digest=self._ports.capability.capability_digest,
                operation=plan.operation, authorization_operation=self._ports.authorization_operation,
                environment=self._config.environment, principal_id=plan.principal_id,
                payload=dict(plan.parameters), approval_digest=plan.action_digest,
                requested_by=RUNTIME_REQUESTER, expires_at=now + timedelta(seconds=self._config.approval_ttl_seconds),
                requested_at=now, investigation_ref=plan.investigation_ref, justification=preview[:2000])
            if not created:
                existing = self._ports.approvals.get_by_identity(tenant_id=self._config.tenant_id,
                                                                 identity_digest=identity)
                approval_id = existing.approval_id if existing is not None else None
        except Exception:  # noqa: BLE001
            log.exception("approval request for %s failed", plan.plan_id)
            return None
        if approval_id is not None:
            self._event(plan.plan_id, RemediationStage.APPROVAL_REQUESTED, approval_id=approval_id,
                        authority=plan.authority.value, expires_in_seconds=self._config.approval_ttl_seconds,
                        investigation_ref=plan.investigation_ref, incident_ref=plan.incident_ref)
            self._count("remediation_approvals", "requested",
                        "policy" if plan.authority is PlanAuthority.AUTONOMOUS else "human")
            self._audit("APPROVAL_REQUESTED", plan.plan_id, {"approval_id": approval_id,
                                                             "authority": plan.authority.value,
                                                             "action_digest": plan.action_digest})
        return approval_id

    def process_pending(self) -> list:
        """Advance plans waiting for a human. Granted -> execute; denied ->
        closed, not executed; expired -> closed, not executed."""
        now = self._clock()
        handled = []
        with self._lock:
            pending = list(self._pending.items())
        for plan_id, (plan, approval_id) in pending:
            record = self._ports.approvals.get(tenant_id=self._config.tenant_id, approval_id=approval_id)
            common = dict(investigation_ref=plan.investigation_ref, incident_ref=plan.incident_ref)
            if record is None:
                continue
            if record.outcome == "granted":
                with self._lock:
                    self._pending.pop(plan_id, None)
                decider = str(record.decided_by or "")
                kind = "human" if decider.startswith("human:") else "policy"
                self._event(plan_id, RemediationStage.APPROVAL_GRANTED, approval_id=approval_id, decider=decider,
                            decider_kind=kind, authority=plan.authority.value, **common)
                self._count("remediation_approvals", "granted", kind)
                self._audit("APPROVAL_GRANTED", plan_id, {"approval_id": approval_id, "decider": decider})
                handled.append(self.execute_plan(plan, approval_id=approval_id,
                                                 authority_kind="human_approved" if kind == "human" else "autonomous"))
            elif record.outcome in ("denied", "withdrawn"):
                with self._lock:
                    self._pending.pop(plan_id, None)
                self._event(plan_id, RemediationStage.APPROVAL_DENIED, approval_id=approval_id,
                            decider=record.decided_by, reason=(record.justification or "")[:500],
                            outcome=record.outcome, **common)
                self._count("remediation_approvals", "denied", "human")
                self._audit("APPROVAL_DENIED", plan_id, {"approval_id": approval_id, "decider": record.decided_by})
                self._close(plan, outcome="not_executed", reason=f"approval {record.outcome} by a human",
                            categories=("human_rejection",))
                handled.append({"plan_id": plan_id, "result": "denied"})
            elif record.outcome == "pending" and record.is_expired_at(now):
                with self._lock:
                    self._pending.pop(plan_id, None)
                self._event(plan_id, RemediationStage.APPROVAL_EXPIRED, approval_id=approval_id, **common)
                self._count("remediation_approvals", "expired", "human")
                self._audit("APPROVAL_EXPIRED", plan_id, {"approval_id": approval_id})
                self._close(plan, outcome="not_executed", reason="the approval expired unanswered",
                            categories=("approval_expired",))
                handled.append({"plan_id": plan_id, "result": "expired"})
        return handled

    # -- 3. EXECUTION (fenced, idempotent, never retried) ----------------------

    def _stale_reasons(self, plan: RemediationPlan, approval_id: str, now: datetime) -> list:
        reasons = []
        if plan.policy_version != self._config.policy_version:
            reasons.append(f"policy changed: approved under {plan.policy_version}, current "
                           f"{self._config.policy_version}; re-plan and re-approve")
        target = plan.target
        dep = self._read("kubernetes.deployment.get", {"namespace": target.namespace, "name": target.name})
        if dep is None or not dep.succeeded:
            reasons.append(f"the target is not readable now ({getattr(dep, 'failure_reason', 'no answer')})")
        else:
            ev = dep.evidence
            if ev.get("uid") != target.uid:
                reasons.append("the Deployment was replaced (uid changed)")
            if ev.get("generation") != target.generation:
                reasons.append(f"target drift: generation {ev.get('generation')} != planned {target.generation}")
            if str(ev.get("revision")) != str(target.current_revision):
                reasons.append(f"target drift: revision {ev.get('revision')} != planned {target.current_revision}")
            if ev.get("templateDigest") != target.current_template_digest:
                reasons.append("target drift: the running pod template changed")
        rs = self._read("kubernetes.replicasets.list", {"namespace": target.namespace})
        if rs is not None and rs.succeeded:
            wanted_rev = str(plan.parameters.get("target_revision"))
            if not any(r.get("ownerUid") == target.uid and str(r.get("revision")) == wanted_rev
                       and r.get("podTemplateDigest") == plan.parameters.get("target_template_digest")
                       for r in rs.evidence.get("replicaSets") or () if isinstance(r, Mapping)):
                reasons.append(f"the target revision {wanted_rev} is no longer available with the approved template")
        facts = None
        try:
            facts = self._ports.approvals.find(self._ports.context_factory(), approval_id)
        except Exception:  # noqa: BLE001
            facts = None
        if facts is None or not facts.is_valid_for(tenant_id=self._config.tenant_id,
                                                   capability_digest=self._ports.capability.capability_digest,
                                                   operation=self._ports.authorization_operation, moment=now):
            reasons.append("the approval is no longer valid (expired, withdrawn, other tenant or other capability)")
        return reasons

    def _claim(self, key: str, plan: RemediationPlan) -> str:
        try:
            first = self._ports.idempotency.claim(self._ports.context_factory(), key=key,
                                                  execution_id=plan.plan_id, action_digest=plan.action_digest)
            return "claimed" if first else "duplicate"
        except Exception as exc:  # noqa: BLE001
            if type(exc).__name__ == "IdempotencyConflict":
                return "conflict"
            raise

    def execute_plan(self, plan: RemediationPlan, *, approval_id: str, authority_kind: str) -> dict:
        now = self._clock()
        common = dict(investigation_ref=plan.investigation_ref, incident_ref=plan.incident_ref)
        executions = sum(1 for p in self._plans_for_incident(plan.incident_ref)
                         for s in self._stages(p) if s == RemediationStage.EXECUTING.value)
        if executions >= self._config.max_executions_per_incident:
            self._event(plan.plan_id, RemediationStage.ESCALATED,
                        reason=(f"incident action budget exhausted: {executions} execution(s) of "
                                f"{self._config.max_executions_per_incident} permitted"), **common)
            self._close(plan, outcome="escalated", reason="action budget exhausted", categories=("escalation",))
            return {"plan_id": plan.plan_id, "result": "escalated_budget"}

        action_key = compute_digest({"tenant": self._config.tenant_id, "approval_digest": plan.action_digest,
                                     "plan": plan.plan_id, "uid": plan.target.uid}).value
        claimed = self._claim(action_key, plan)
        if claimed != "claimed":
            self._event(plan.plan_id, RemediationStage.DUPLICATE_SUPPRESSED, approval_id=approval_id,
                        reason=f"this action was already started ({claimed}); no second mutation", **common)
            self._count("remediation_executions", "duplicate")
            return {"plan_id": plan.plan_id, "result": "duplicate_suppressed"}

        stale = self._stale_reasons(plan, approval_id, now)
        if stale:
            self._event(plan.plan_id, RemediationStage.STALE, approval_id=approval_id, reasons=stale, **common)
            self._count("remediation_executions", "stale")
            self._audit("EXECUTION_REFUSED", plan.plan_id, {"reason": "stale plan", "reasons": stale[:4]})
            self._close(plan, outcome="not_executed", reason="stale plan refused before execution",
                        categories=("stale_plan",))
            return {"plan_id": plan.plan_id, "result": "stale", "reasons": stale}

        target_key = compute_digest({"tenant": self._config.tenant_id, "target": plan.target.uid,
                                     "generation": plan.target.generation}).value
        fence = self._claim(target_key, plan)
        if fence != "claimed":
            self._event(plan.plan_id, RemediationStage.EXECUTION_REFUSED, approval_id=approval_id,
                        reason=("another remediation already holds this target at this generation; "
                                "concurrent execution against one target is fenced"), **common)
            self._count("remediation_executions", "fenced")
            self._close(plan, outcome="not_executed", reason="fenced", categories=("concurrency_fenced",))
            return {"plan_id": plan.plan_id, "result": "fenced"}

        prediction = self._record_prediction(plan, now)
        self._event(plan.plan_id, RemediationStage.EXECUTING, approval_id=approval_id, authority=authority_kind,
                    prediction_ref=prediction.record_id if prediction else None, **common)
        self._count("remediation_actions", authority_kind)
        started = time.monotonic()
        try:
            outcome = self._ports.writer.write(self._ports.context_factory(), operation=plan.operation,
                                               payload=dict(plan.parameters), approval_artifact_id=approval_id)
        except Exception as exc:  # noqa: BLE001 - an exception is a refusal, never a success
            outcome = None
            failure = f"{type(exc).__name__}: {exc}"[:300]
        seconds = round(time.monotonic() - started, 2)
        execution_ref = str(getattr(outcome, "execution_id", "") or "")
        if outcome is None:
            said, reason = "refused", failure
        elif outcome.succeeded:
            said, reason = "succeeded", None
        elif not execution_ref:
            said, reason = "refused", str(outcome.failure_reason or "refused")[:300]
        elif outcome.node_state in (None, "unknown"):
            said, reason = "unknown", str(outcome.failure_reason or "the outcome is unknown")[:300]
        else:
            said, reason = "failed", str(outcome.failure_reason or "failed")[:300]
        if execution_ref:
            self._ports.approvals.mark_consumed(approval_id=approval_id, tenant_id=self._config.tenant_id,
                                                execution_ref=execution_ref)
        evidence = {k: v for k, v in dict(getattr(outcome, "evidence", {}) or {}).items()
                    if isinstance(v, (str, int, float, bool))}
        stage = {"succeeded": RemediationStage.EXECUTED, "failed": RemediationStage.EXECUTION_FAILED,
                 "unknown": RemediationStage.EXECUTION_UNKNOWN, "refused": RemediationStage.EXECUTION_REFUSED}[said]
        self._event(plan.plan_id, stage, approval_id=approval_id, execution_ref=execution_ref or None,
                    executor_said=said, reason=reason, seconds=seconds, provider_evidence=evidence,
                    authority=authority_kind, **common)
        self._count("remediation_executions", said)
        self._observe("remediation_action_seconds", seconds, said)
        try:
            self._ports.idempotency.record_outcome(self._ports.context_factory(), key=action_key, outcome=said)
        except Exception:  # noqa: BLE001
            pass
        if said == "refused":
            self._close(plan, outcome="not_executed", reason=f"the governed chain refused: {reason}",
                        categories=("execution_refused",))
            return {"plan_id": plan.plan_id, "result": "refused", "reason": reason}

        precondition = said == "failed" and any(code in (reason or "") for code in _PRECONDITION_CODES)
        report = self._verifier.verify(
            plan=plan, execution_ref=execution_ref, executor_said=said,
            window_seconds=1 if precondition else self._config.verification_window_seconds,
            poll_seconds=self._config.verification_poll_seconds, metric_operation=self._metric_operation())
        verdict_stage = {"VERIFIED": RemediationStage.VERIFIED,
                         "VERIFICATION_FAILED": RemediationStage.VERIFICATION_FAILED}.get(
            report.classification, RemediationStage.VERIFICATION_INSUFFICIENT)
        if said in ("failed", "unknown") and report.classification == "VERIFICATION_FAILED" \
                and not report.at_target_template:
            # The executor said it failed and the world confirms nothing changed:
            # an honest failure, independently confirmed. Recording it as a
            # verification failure would misdescribe it and trip the breaker that
            # exists for remediations that RAN and did not hold.
            verdict_stage = RemediationStage.NO_EFFECT_CONFIRMED
        self._event(plan.plan_id, verdict_stage, execution_ref=execution_ref, verdict=report.verdict,
                    classification=report.classification, verification=report.to_dict(), **common)
        self._count("remediation_verifications", report.verdict)
        self._observe("remediation_verification_seconds", report.seconds, report.verdict)
        self._audit("VERIFICATION_RECORDED", plan.plan_id, {"execution_ref": execution_ref,
                                                            "verdict": report.verdict,
                                                            "verification_ref": report.verification_ref})
        if report.discrepancy:
            self._event(plan.plan_id, RemediationStage.DISCREPANCY, execution_ref=execution_ref,
                        discrepancy=report.discrepancy, **common)
        evaluation = self._record_evaluation(plan, prediction, execution_ref, report)
        return self._recover(plan, said=said, report=report, execution_ref=execution_ref,
                             prediction=prediction, evaluation=evaluation, authority_kind=authority_kind)

    def _metric_operation(self) -> Optional[str]:
        op = self._config.metric_operation
        definitions = getattr(self._ports.reader, "_definitions", {}) or {}
        return op if op and op in definitions else None

    def _plans_for_incident(self, incident_ref: str) -> list:
        try:
            rows = self._ports.reasoning.list_by_kind(tenant_id=self._config.tenant_id, kind="remediation_plan")
        except Exception:  # noqa: BLE001
            return []
        return [r.subject_ref for r in rows if (r.refs or {}).get("incident_ref") == incident_ref]

    # -- 4. LEARNING substrate ---------------------------------------------------

    def _record_prediction(self, plan: RemediationPlan, now: datetime) -> Any:
        from backend.contracts.tenant import TenantRef
        from backend.contracts.world import Prediction
        from backend.contracts.world.epistemic import ProvenanceRef
        from backend.platform.identity.generators import prefixed_id
        from backend.world.application.reasoning import ReasoningLedger

        try:
            tenant = TenantRef(tenant_id=self._config.tenant_id)
            prediction = Prediction(
                record_id=prefixed_id("wpred"), tenant=tenant, recorded_at=now,
                provenance=ProvenanceRef(produced_by="platform:remediation-planner/1",
                                         parent_claim_ref=REGRESSION_HYPOTHESIS),
                subject_ref=plan.subject_ref, expected=dict(plan.expected_state), predicted_at=now,
                deadline=now + timedelta(seconds=self._config.verification_window_seconds + 300),
                model_ref=self._config.model_identity, predicate=OUTCOME_PREDICATE,
                basis=tuple(plan.evidence_refs[:10]), hypothesis_ref=REGRESSION_HYPOTHESIS)
            ReasoningLedger(repository=self._ports.reasoning).record_prediction(
                tenant=tenant, prediction=prediction, recorded_at=now,
                harness_version=self._config.harness_version)
            return prediction
        except Exception:  # noqa: BLE001 - calibration substrate lost is logged, never faked
            log.exception("the prediction for %s was not recorded", plan.plan_id)
            return None

    def _record_evaluation(self, plan: RemediationPlan, prediction: Any, execution_ref: str, report: Any) -> Any:
        if prediction is None or not execution_ref or report.proposition is None:
            return None
        from backend.contracts.tenant import TenantRef
        from backend.contracts.world import Outcome
        from backend.contracts.world.epistemic import ProvenanceRef
        from backend.platform.identity.generators import prefixed_id
        from backend.world.application.hypothesis import evaluate_prediction
        from backend.world.application.reasoning import ReasoningLedger

        try:
            now = self._clock()
            tenant = TenantRef(tenant_id=self._config.tenant_id)
            outcome = Outcome(record_id=prefixed_id("oc"), tenant=tenant, recorded_at=now,
                              provenance=ProvenanceRef(produced_by="platform:remediation-verifier/1",
                                                       execution_ref=execution_ref),
                              execution_ref=execution_ref, observed=dict(report.proposition),
                              observation_ref=report.observation_ref, prediction_ref=prediction.record_id)
            evaluation = evaluate_prediction(prediction=prediction, outcome=outcome, observed_at=now)
            ReasoningLedger(repository=self._ports.reasoning).record_evaluation(
                tenant=tenant, subject_ref=plan.subject_ref, evaluation=evaluation, recorded_at=now,
                predicate=OUTCOME_PREDICATE)
            return evaluation
        except Exception:  # noqa: BLE001
            log.exception("the prediction evaluation for %s was not recorded", plan.plan_id)
            return None

    # -- 5. RECOVERY (bounded) -> outcome -> learning ----------------------------

    def _recover(self, plan: RemediationPlan, *, said: str, report: Any, execution_ref: str, prediction: Any,
                 evaluation: Any, authority_kind: str) -> dict:
        from backend.contexts.execution.domain.recovery import RecoveryAction

        common = dict(investigation_ref=plan.investigation_ref, incident_ref=plan.incident_ref)
        budgets = {"mutation_retries": self._config.mutation_retries,
                   "recovery_attempts_permitted": self._config.max_recovery_attempts,
                   "recovery_attempts_used": 0, "executions_per_incident": self._config.max_executions_per_incident}
        categories: list = [authority_kind]
        if report.classification == "VERIFIED":
            categories.append("successful_remediation")
            if report.discrepancy:
                categories.append("false_failure_detected")
            self._close(plan, outcome="resolved", reason="independent verification: the approved state was reached "
                        "and the workload is available and not crash-looping", categories=categories,
                        execution_ref=execution_ref, report=report, prediction=prediction, evaluation=evaluation)
            return {"plan_id": plan.plan_id, "result": "resolved", "execution_ref": execution_ref,
                    "verification": report.to_dict()}

        if said in ("failed", "unknown") and report.classification == "VERIFICATION_FAILED" \
                and not report.at_target_template:
            # Observed, not assumed: the independent read established that the
            # approved state was not reached and the pre-action template is (or a
            # different one is) still running. An UNKNOWN delivery that changed
            # nothing is the same finding.
            action = RecoveryAction.WAIT_FOR_HUMAN
            reason = (f"the execution {'failed' if said == 'failed' else 'outcome was unknown'} and the world was "
                      f"independently observed not to have reached the approved state ({report.rationale or 'no change'}); "
                      "a mutation is never retried automatically, and no destructive fallback is attempted")
            categories += ["failed_remediation", "no_effect_confirmed"]
            outcome = "execution_failed"
        elif report.classification == "VERIFICATION_FAILED" and report.at_target_template:
            action = RecoveryAction.WAIT_FOR_HUMAN
            reason = ("the rollback took effect (the running template is the approved one) but the incident "
                      "persists: the diagnosis did not hold. No further automatic action: mutations are never "
                      "retried, and the one permitted recovery attempt -- compensating back to revision "
                      f"{plan.target.current_revision} -- needs a new plan and a human")
            categories += ["failed_remediation", "false_diagnosis", "verification_failure"]
            outcome = "verification_failed"
        elif report.classification == "VERIFICATION_FAILED":
            action = RecoveryAction.RECONCILE_EXTERNAL_STATE
            reason = ((report.discrepancy or "the world did not reach the approved state")
                      + "; the independent reading stands, the executor's claim does not, and a human decides next")
            categories += ["verification_failure"] + (["false_success_detected"] if said == "succeeded" else [])
            outcome = "verification_failed"
        elif said == "failed":
            action = RecoveryAction.WAIT_FOR_HUMAN
            reason = ("the execution failed and the world was independently observed not to have reached the "
                      "approved state; a mutation is never retried automatically")
            categories += ["failed_remediation"]
            outcome = "execution_failed"
        else:
            action = RecoveryAction.RECONCILE_EXTERNAL_STATE
            reason = ("the outcome could not be established by independent verification "
                      f"({report.rationale or report.classification}); nothing is assumed either way")
            categories += ["verification_insufficient"]
            outcome = "insufficient_evidence"
        self._event(plan.plan_id, RemediationStage.RECOVERY_DECIDED, action=action.value, reason=reason,
                    budgets=budgets, execution_ref=execution_ref, **common)
        self._count("remediation_recoveries", action.value)
        self._event(plan.plan_id, RemediationStage.ESCALATED, reason="escalated to a human: " + reason[:300],
                    **common)
        self._close(plan, outcome=outcome, reason=reason, categories=categories, execution_ref=execution_ref,
                    report=report, prediction=prediction, evaluation=evaluation)
        return {"plan_id": plan.plan_id, "result": outcome, "execution_ref": execution_ref,
                "recovery": action.value, "verification": report.to_dict()}

    def _close(self, plan: RemediationPlan, *, outcome: str, reason: str, categories: Any,
               execution_ref: str = "", report: Any = None, prediction: Any = None, evaluation: Any = None) -> None:
        common = dict(investigation_ref=plan.investigation_ref, incident_ref=plan.incident_ref)
        self._event(plan.plan_id, RemediationStage.LEARNED, category=list(categories), outcome=outcome,
                    prediction_ref=getattr(prediction, "record_id", None),
                    evaluation_matched=getattr(evaluation, "matched", None),
                    verification_ref=getattr(report, "verification_ref", None), advisory=True,
                    note=("advisory: calibration reads the prediction, its evaluation and the independent "
                          "verification; nothing here changes policy or autonomy directly"), **common)
        self._event(plan.plan_id, RemediationStage.CLOSED, outcome=outcome, reason=reason[:600],
                    execution_ref=execution_ref or None, **common)

    # -- resume -------------------------------------------------------------------

    def resume(self) -> None:
        """Re-attach plans waiting on a human; reconcile plans a crash left mid-execution.

        A plan whose last stage is ``executing`` may or may not have written:
        it is never re-executed. It is reconciled by independent verification,
        which is the only thing that can say what the world now is."""
        try:
            plans = self._ports.reasoning.list_by_kind(tenant_id=self._config.tenant_id, kind="remediation_plan")
        except Exception:  # noqa: BLE001
            return
        for row in plans:
            stages = self._stages(row.subject_ref)
            if not stages or any(s in (RemediationStage.CLOSED.value,) for s in stages):
                continue
            try:
                plan = RemediationPlan.from_dict({k: v for k, v in (row.record or {}).items() if k != "proposal"})
            except Exception:  # noqa: BLE001
                log.exception("plan %s could not be reconstructed", row.subject_ref)
                continue
            last = stages[-1]
            if last == RemediationStage.APPROVAL_REQUESTED.value:
                approval_id = next((str((e.record or {}).get("approval_id")) for e in self.events_for(plan.plan_id)
                                    if (e.record or {}).get("stage") == last), None)
                if approval_id:
                    with self._lock:
                        self._pending[plan.plan_id] = (plan, approval_id)
            elif last == RemediationStage.EXECUTING.value:
                report = self._verifier.verify(plan=plan, execution_ref="", executor_said="unknown",
                                               window_seconds=self._config.verification_window_seconds,
                                               poll_seconds=self._config.verification_poll_seconds)
                self._event(plan.plan_id, RemediationStage.EXECUTION_UNKNOWN,
                            reason="the process stopped between dispatch and a recorded result; reconciled by "
                                   "independent verification, never re-executed",
                            investigation_ref=plan.investigation_ref, incident_ref=plan.incident_ref)
                stage = {"VERIFIED": RemediationStage.VERIFIED,
                         "VERIFICATION_FAILED": RemediationStage.VERIFICATION_FAILED}.get(
                    report.classification, RemediationStage.VERIFICATION_INSUFFICIENT)
                self._event(plan.plan_id, stage, verdict=report.verdict, classification=report.classification,
                            verification=report.to_dict(), investigation_ref=plan.investigation_ref,
                            incident_ref=plan.incident_ref)
                self._recover(plan, said="unknown", report=report, execution_ref="", prediction=None,
                              evaluation=None, authority_kind="reconciled_after_crash")


_PRECONDITION_CODES = (
    "target_absent", "uid_changed", "generation_changed", "revision_changed", "template_changed",
    "deployment_paused", "target_revision_unavailable", "target_revision_ambiguous", "target_revision_drifted",
    "compensation_unavailable", "compensation_would_be_discarded", "dry_run_conflict", "dry_run_refused",
    "dry_run_unexpected_result", "precondition_changed_during_write", "authority_expired",
)


def _approval_outcome(value: str) -> Any:
    from backend.contracts.approval import ApprovalOutcome

    return ApprovalOutcome(value)


def _approval_preview(plan: RemediationPlan) -> str:
    """What a human sees when asked to approve (mandate §16): WHAT, WHY, TARGET,
    RISK, BLAST RADIUS, EVIDENCE, EXPECTED OUTCOME, ROLLBACK, VERIFICATION and
    ACTION DIGEST -- of the concrete action, not an intention."""
    p = plan.parameters
    return (
        f"WHAT: {plan.action} ({plan.operation}) to revision {p.get('target_revision')} from "
        f"{p.get('expected_revision')}. "
        f"WHY: {plan.diagnosis[:240]}. "
        f"TARGET: Deployment {plan.target.namespace}/{plan.target.name} uid {plan.target.uid} generation "
        f"{plan.target.generation}. "
        f"RISK: {plan.risk.level.value} ({plan.reversibility.value}). "
        f"BLAST RADIUS: {plan.blast_radius.description[:200]}. "
        f"EVIDENCE: {', '.join(plan.evidence_refs[:6])}. "
        f"EXPECTED: {dict(plan.expected_state)}. "
        f"ROLLBACK: {plan.rollback_strategy.note[:160]}. "
        f"VERIFICATION: {', '.join(c.name for c in plan.verification_criteria)} by an independent read. "
        f"ACTION DIGEST: {plan.action_digest}. PLAN: {plan.plan_id}. POLICY: {plan.policy_version}."
    )


class EmbeddedRemediator:
    def __init__(self, runtime: RemediationRuntime) -> None:
        self.runtime = runtime

    def offer(self, outcome: Any) -> bool:
        return self.runtime.offer(outcome)

    def stop(self, timeout: float = 30.0) -> None:
        self.runtime.stop(timeout=timeout)


def start_embedded_remediator(runtime: Any, *, metrics: Any = None) -> Optional[EmbeddedRemediator]:
    """Compose and start the remediator beside the investigator when enabled.

    Off unless ``CORTEX_REMEDIATION_ENABLED=1`` AND the signal loop is configured
    AND the rollback capability is commissioned: a deployment that did not ask
    for remediation gets none, and one that asked but cannot perform it says so
    at boot rather than planning actions it could never take."""
    tenant_id = (os.getenv("CORTEX_SIGNAL_TENANT_ID") or "").strip()
    namespace = (os.getenv("CORTEX_SIGNAL_NAMESPACE") or "").strip()
    if not (tenant_id and namespace) or (os.getenv("CORTEX_REMEDIATION_ENABLED") or "").strip() != "1":
        return None
    try:
        from backend.api.capability_execution_composition import build_remediation_runtime

        if metrics is None:
            try:
                from backend.observability.prometheus_metrics import metrics as _metrics
                metrics = _metrics
            except Exception:  # noqa: BLE001
                metrics = None
        config = RemediationRuntimeConfig.from_env(tenant_id=tenant_id, namespace=namespace)
        remediation = build_remediation_runtime(runtime, config=config, metrics=metrics)
    except Exception as exc:  # noqa: BLE001 - the API keeps booting; remediation does not run half-composed
        log.error("embedded remediator refused to start: %s", exc)
        return None
    remediation.start()
    log.info("embedded remediator started: tenant=%s namespace=%s model=%s compensable_autonomy=%s",
             tenant_id, namespace, config.model_identity, config.compensable_autonomy)
    return EmbeddedRemediator(remediation)
