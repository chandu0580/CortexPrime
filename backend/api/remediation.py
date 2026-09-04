"""The governed remediation lifecycle — Phase 9.6 (ADR-086).

What this is, and what it is emphatically not
-----------------------------------------------
It is **not** a remediation engine. It holds no executor, no gateway, no
scheduler, no approval store and no autonomy model; every one of those already
exists and this module calls them in order. What it adds is the *order* — the
sequence in which a platform must earn the right to change something:

    diagnosis (9.5)
        -> PRE-ACTION ASSURANCE      is the incident still there, still ours,
        |                            still fresh, still unconflicted?
        -> AUTONOMY DECISION         emergency stop, breaker, blast radius,
        |                            calibration, drift, reversibility
        -> HUMAN APPROVAL            digest-bound, tenant-scoped, expiring
        -> GOVERNED WRITE            the existing capability chain, ONE action
        -> POST-ACTION OBSERVATION   a governed READ; the write proves nothing
        -> PREDICTION EVALUATION     against what reality did
        -> POST-ACTION ASSURANCE     independent, re-queried
        -> EXPLAINABLE RESULT

Four axes, deliberately never collapsed
-----------------------------------------
``diagnosis support``, ``prediction support``, ``execution result`` and
``assurance verdict`` are separate fields and stay separate. A restart that
succeeds does not prove the diagnosis; a prediction that holds does not prove
causation; an execution that returned 200 does not mean the world recovered. Each
of those is a different question with a different answer, and a system that
merges them is a system that will eventually report the one it likes best.

The order is the safety property
----------------------------------
Assurance runs BEFORE the write, not only after. An investigation is a snapshot
of a world that keeps moving, and acting on a stale snapshot is how automation
does damage while following every rule it was given. If the incident is gone, or
the target changed, or the evidence went stale or conflicted, this refuses — and
the provider is never contacted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "RemediationRefused",
    "RemediationTarget",
    "PreActionGate",
    "RemediationOutcome",
    "RemediationResult",
    "GovernedRemediation",
]


class RemediationRefused(ContractViolation):
    """The platform declined to act. Carries WHY, and guarantees the provider was
    not contacted — every raise site in this module is before the write."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(f"{stage}: {reason}")
        self.stage = stage
        self.reason = reason


@dataclass(frozen=True)
class RemediationTarget:
    """One workload. The blast radius, as a value.

    There is no ``selector``, no ``names``, no ``all`` and no ``namespaces``.
    A remediation targets one workload in one namespace because this type cannot
    express anything else, which is a stronger guarantee than a check that a list
    has length one.
    """

    namespace: str
    workload: str
    kind: str = "deployment"

    def __post_init__(self) -> None:
        for name in ("namespace", "workload", "kind"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"a remediation target needs a {name}")
            if any(bad in value for bad in ("*", ",", " ", "/", "=", "\n")):
                raise ContractViolation(
                    f"{name}={value!r} looks like a selector or a list; a "
                    "remediation names exactly one workload")
        if self.kind != "deployment":
            raise ContractViolation(
                "only deployments can be restarted by this capability; anything "
                "else would be a different operation with a different risk")

    @property
    def subject_ref(self) -> str:
        return f"kubernetes:{self.kind}:{self.namespace}/{self.workload}"


@dataclass(frozen=True)
class PreActionGate:
    """What the platform checked before it was willing to act, and what it found."""

    incident_still_present: bool
    target_matches_investigation: bool
    evidence_fresh: bool
    evidence_conflicted: bool
    tenant_matches: bool
    assurance_verdict: Optional[str]
    reason: str

    @property
    def permits_action(self) -> bool:
        return (self.incident_still_present and self.target_matches_investigation
                and self.evidence_fresh and not self.evidence_conflicted
                and self.tenant_matches)

    def to_dict(self) -> dict:
        return {
            "incident_still_present": self.incident_still_present,
            "target_matches_investigation": self.target_matches_investigation,
            "evidence_fresh": self.evidence_fresh,
            "evidence_conflicted": self.evidence_conflicted,
            "tenant_matches": self.tenant_matches,
            "assurance_verdict": self.assurance_verdict,
            "permits_action": self.permits_action,
            "reason": self.reason,
        }


class RemediationOutcome:
    """What the WORLD did — never what the action returned."""

    RECOVERED = "recovered"
    NOT_RECOVERED = "not_recovered"
    PARTIALLY_RECOVERED = "partially_recovered"
    UNKNOWN = "unknown"
    CONFLICTED = "conflicted"


@dataclass(frozen=True)
class RemediationResult:
    """The explainable record of one remediation attempt.

    Every field is something a different part of the platform decided. This type
    holds them together; it computes none of them.
    """

    remediation_ref: str
    investigation_ref: str
    tenant_id: str
    target: RemediationTarget
    capability_ref: str
    capability_version: int
    input_digest: str
    action_ref: Optional[str]

    diagnosis: Optional[str]
    diagnosis_supported_by: tuple

    pre_action_gate: Optional[Mapping[str, Any]]
    autonomy_decision: Optional[Mapping[str, Any]]
    approval_ref: Optional[str]

    executed: bool
    execution_state: Optional[str]
    provider_evidence: Mapping[str, Any] = field(default_factory=dict)

    world_outcome: str = RemediationOutcome.UNKNOWN
    post_action_observation_ref: Optional[str] = None

    prediction_ref: Optional[str] = None
    prediction_evaluation: Optional[str] = None

    post_assurance_verdict: Optional[str] = None
    rollback_available: bool = False
    rollback_reason: str = ""
    residual_uncertainty: str = ""
    refused_at: Optional[str] = None
    refusal_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "remediation_ref": self.remediation_ref,
            "investigation_ref": self.investigation_ref,
            "tenant": self.tenant_id,
            "target": {"namespace": self.target.namespace,
                       "workload": self.target.workload, "kind": self.target.kind},
            "capability": {"ref": self.capability_ref,
                           "version": self.capability_version,
                           "input_digest": self.input_digest},
            "action_ref": self.action_ref,
            "diagnosis": self.diagnosis,
            "diagnosis_supported_by": list(self.diagnosis_supported_by),
            "pre_action_gate": dict(self.pre_action_gate) if self.pre_action_gate else None,
            "autonomy_decision": dict(self.autonomy_decision) if self.autonomy_decision else None,
            "approval_ref": self.approval_ref,
            "executed": self.executed,
            "execution_state": self.execution_state,
            "provider_evidence": dict(self.provider_evidence),
            "world_outcome": self.world_outcome,
            "post_action_observation_ref": self.post_action_observation_ref,
            "prediction": {"ref": self.prediction_ref,
                           "evaluation": self.prediction_evaluation},
            "post_assurance_verdict": self.post_assurance_verdict,
            "rollback": {"available": self.rollback_available,
                         "reason": self.rollback_reason},
            "residual_uncertainty": self.residual_uncertainty,
            "refused_at": self.refused_at,
            "refusal_reason": self.refusal_reason,
        }

    def render(self) -> str:
        lines = [
            f"REMEDIATION   {self.remediation_ref}",
            f"TARGET        {self.target.kind}/{self.target.workload} "
            f"in {self.target.namespace} (tenant {self.tenant_id})",
            f"DIAGNOSIS     {self.diagnosis or 'none'}",
        ]
        if self.refused_at:
            lines += [f"REFUSED AT    {self.refused_at}",
                      f"              {self.refusal_reason}",
                      "EXECUTED      no — the provider was not contacted"]
            return "\n".join(lines)
        gate = self.pre_action_gate or {}
        decision = self.autonomy_decision or {}
        lines += [
            "",
            f"PRE-ASSURANCE {gate.get('assurance_verdict')} "
            f"(permits action: {gate.get('permits_action')})",
            f"AUTONOMY      requested={decision.get('requested_level')} "
            f"allowed={decision.get('allowed_level')} "
            f"effective={decision.get('effective_level')}",
            f"              {decision.get('reason')}",
            f"APPROVAL      {self.approval_ref or 'none'}",
            "",
            f"EXECUTED      {self.executed} ({self.execution_state})",
            f"WORLD OUTCOME {self.world_outcome}",
            f"PREDICTION    {self.prediction_evaluation or 'not evaluated'}",
            f"ASSURANCE     {self.post_assurance_verdict or 'not adjudicated'}",
            f"ROLLBACK      {'available' if self.rollback_available else 'UNAVAILABLE'}"
            f" — {self.rollback_reason}",
            "",
            f"RESIDUAL      {self.residual_uncertainty}",
        ]
        return "\n".join(lines)


class GovernedRemediation:
    """Runs the lifecycle. Owns no authority; calls the components that do."""

    def __init__(
        self, *, reader: Any, writer: Any, observer: Any, derivation: Any,
        query: Any, verifier: Any, autonomy_policy: Any, capability_profile: Any,
        approvals: Any, context: Any, tenant: Any,
        produced_by: str = "platform:governed-remediation/1",
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._observer = observer
        self._derivation = derivation
        self._query = query
        self._verifier = verifier
        self._policy = autonomy_policy
        self._profile = capability_profile
        self._approvals = approvals
        self._context = context
        self._tenant = tenant
        self._produced_by = produced_by

    # -- pre-action ---------------------------------------------------------

    def pre_action_gate(
        self, *, investigation: Any, target: RemediationTarget, now: datetime,
        expected_symptom: Mapping[str, Any],
    ) -> PreActionGate:
        """Is the world the investigation described still the world in front of us?

        This is a **governed read**, not a memory lookup. An investigation is a
        snapshot; the whole reason to re-check is that the snapshot may have
        stopped being true — the incident may have resolved itself, somebody may
        have already fixed it, or the workload may have been replaced by
        something else with the same name.
        """
        if investigation.tenant.tenant_id != self._tenant.tenant_id:
            return PreActionGate(False, False, False, False, False, None,
                                 "the investigation belongs to a different tenant")

        outcome = self._reader.read(
            self._context, operation="kubernetes.pod.get",
            payload={"namespace": target.namespace,
                     "name": expected_symptom.get("pod", "")})
        if not outcome.succeeded:
            return PreActionGate(
                False, True, False, False, True, None,
                f"the target could not be re-read before acting: "
                f"{outcome.failure_reason}")

        waiting = outcome.evidence.get("waitingReason")
        restarts = outcome.evidence.get("restartCount")
        still_broken = (waiting == "CrashLoopBackOff"
                        or (isinstance(restarts, int) and restarts >= 1))

        # Freshness and conflict come from the World Plane's own verdicts, not
        # from a second opinion computed here.
        world = self._query.current(
            tenant=self._tenant, subject_ref=target.subject_ref,
            predicate="deployed_revision", now=now)
        fresh = world.freshness.state.value != "stale"
        conflicted = bool(world.to_dict().get("conflicted"))

        matches = str(outcome.evidence.get("namespace") or target.namespace) == target.namespace

        verdict = None
        if self._verifier is not None and still_broken:
            verdict = self._independent_check(target, expected_symptom, now)

        reason = (
            "the incident is still present and the target still matches"
            if still_broken and matches and fresh and not conflicted
            else "the world moved since the investigation; acting on it would be "
                 "acting on a snapshot that has stopped being true")
        return PreActionGate(
            incident_still_present=still_broken,
            target_matches_investigation=matches,
            evidence_fresh=fresh, evidence_conflicted=conflicted,
            tenant_matches=True, assurance_verdict=verdict, reason=reason)

    def _independent_check(self, target, expected_symptom, now) -> Optional[str]:
        from backend.assurance.application.procedures import (
            VerificationProcedure, VerificationProcedureKind,
        )
        try:
            result = self._verifier.verify(
                tenant=self._tenant,
                procedure=VerificationProcedure(
                    kind=VerificationProcedureKind.COMPARE_WORLD_STATE,
                    subject_ref=target.subject_ref, predicate="deployed_revision",
                    expected=expected_symptom.get("deployed_revision")),
                producer_reasoning_path="intelligence:engine/1",
                verified_at=now)
            return result.verification.verdict.value
        except Exception:  # noqa: BLE001 — an unavailable verifier is not a pass
            return None

    # -- the action ---------------------------------------------------------

    def remediate(
        self, *, investigation: Any, target: RemediationTarget,
        expected_symptom: Mapping[str, Any], autonomy_inputs: Mapping[str, Any],
        approval_artifact_id: Optional[str], requested_level: Any,
        prediction: Optional[Mapping[str, Any]], now: datetime,
        diagnosis: Optional[str] = None, diagnosis_supported_by: Sequence[str] = (),
    ) -> RemediationResult:
        """The whole lifecycle. Every refusal returns before the provider is called."""
        from backend.platform.hashing import compute_digest
        from backend.platform.identity.generators import prefixed_id

        payload = {"namespace": target.namespace, "name": target.workload}
        digest = compute_digest(payload).value
        base = dict(
            remediation_ref=prefixed_id("wrem"),
            investigation_ref=investigation.investigation_ref,
            tenant_id=self._tenant.tenant_id, target=target,
            capability_ref=self._profile.capability_ref, capability_version=1,
            input_digest=digest, action_ref=None,
            diagnosis=diagnosis, diagnosis_supported_by=tuple(diagnosis_supported_by),
            pre_action_gate=None, autonomy_decision=None, approval_ref=None,
            executed=False, execution_state=None,
            rollback_available=False,
            rollback_reason=(
                "a rollout restart has no inverse: it stamps the pod template and "
                "creates a revision that nothing removes. Rolling back would be a "
                "separate governed capability, separately approved — it does not "
                "exist and is not implied by this one."),
        )

        def refused(stage: str, reason: str, **extra) -> RemediationResult:
            return RemediationResult(
                **{**base, **extra}, refused_at=stage, refusal_reason=reason,
                world_outcome=RemediationOutcome.UNKNOWN,
                residual_uncertainty=(
                    "no action was taken; the world is as it was and the incident "
                    "is unchanged"))

        # 1. PRE-ACTION ASSURANCE — before anything else costs anything.
        gate = self.pre_action_gate(investigation=investigation, target=target,
                                     now=now, expected_symptom=expected_symptom)
        base["pre_action_gate"] = gate.to_dict()
        if not gate.permits_action:
            return refused("pre_action_assurance", gate.reason)

        # 2. AUTONOMY — the platform's own gates, in their own order.
        decision = self._policy.evaluate(
            requested_level=requested_level, capability=self._profile.to_capability(),
            risk=self._profile.risk, **autonomy_inputs)
        base["autonomy_decision"] = decision.to_dict()
        if not decision.effective_level.permits_action():
            return refused("autonomy",
                           f"{decision.eligibility.value}: {decision.reason}")

        # 3. APPROVAL — required, digest-bound, and checked by the existing
        #    approval facts rather than by anything invented here.
        from backend.contracts.intelligence.autonomy import ApprovalRequirement

        if decision.approval_requirement is ApprovalRequirement.HUMAN_APPROVAL:
            if not approval_artifact_id:
                return refused("approval",
                               "human approval is required for this action and "
                               "none was presented")
            facts = self._approvals.find(self._context, approval_artifact_id)
            if facts is None:
                return refused("approval",
                               f"approval {approval_artifact_id!r} was not found; "
                               "an approval that cannot be produced is not one")
            if not facts.is_valid_for(
                tenant_id=self._tenant.tenant_id, capability_digest=digest,
                operation=self._profile.operation, moment=now,
            ):
                return refused(
                    "approval",
                    f"the approval does not cover this action "
                    f"(outcome={facts.outcome.value}, bound_digest="
                    f"{(facts.bound_digest or '')[:16]}…, expected={digest[:16]}…)")
            base["approval_ref"] = approval_artifact_id
        elif decision.approval_requirement is ApprovalRequirement.NOT_PERMITTED:
            return refused("approval", "no autonomous action is permitted at this level")

        # 4. THE GOVERNED WRITE — one action, through the existing chain.
        write = self._writer.write(
            self._context, operation=self._profile.operation, payload=payload)
        base["action_ref"] = write.execution_id
        base["executed"] = write.succeeded
        base["execution_state"] = write.node_state
        base["provider_evidence"] = dict(write.evidence)
        if not write.succeeded:
            # An ambiguous provider outcome stays ambiguous. A write that may have
            # landed must never be recorded as one that did not.
            return RemediationResult(
                **base, refused_at=None,
                refusal_reason=f"the governed write did not succeed: "
                               f"{write.failure_reason}",
                world_outcome=RemediationOutcome.UNKNOWN,
                residual_uncertainty=(
                    "the provider outcome is not a success; whether the cluster "
                    "applied anything is not established by this result and must "
                    "be determined by observation"))

        return RemediationResult(**base, world_outcome=RemediationOutcome.UNKNOWN,
                                 residual_uncertainty="the action ran; the world has "
                                                      "not yet been observed")

    # -- after the action ---------------------------------------------------

    def observe_outcome(
        self, *, result: RemediationResult, target: RemediationTarget,
        pod_hint: str, now: datetime,
    ) -> tuple:
        """Read the world back. The action established nothing on its own.

        Returns ``(outcome, observation_ref, evidence)``. ``UNKNOWN`` is a real
        answer here and is used: a read that fails after a write leaves the world
        genuinely undetermined, and saying so is better than assuming either way.
        """
        from backend.api.governed_read_observer import ObservationLeg

        outcome = self._reader.read(
            self._context, operation="kubernetes.pods.list",
            payload={"namespace": target.namespace})
        if not outcome.succeeded:
            return RemediationOutcome.UNKNOWN, None, {}

        pods = [p for p in (outcome.evidence.get("pods") or ())
                if isinstance(p, Mapping)]
        owned = [p for p in pods
                 if isinstance(p.get("name"), str)
                 and p["name"].startswith(target.workload + "-")]
        if not owned:
            return RemediationOutcome.UNKNOWN, None, {"pods": pods}

        crashing = [p for p in owned if p.get("waitingReason") == "CrashLoopBackOff"]
        running = [p for p in owned if p.get("phase") == "Running" and not p.get("waitingReason")]
        if crashing and running:
            world = RemediationOutcome.PARTIALLY_RECOVERED
        elif crashing:
            world = RemediationOutcome.NOT_RECOVERED
        elif running:
            world = RemediationOutcome.RECOVERED
        else:
            world = RemediationOutcome.UNKNOWN

        recorded = self._observer.observe(
            tenant=self._tenant, outcome=outcome, now=now,
            legs=(ObservationLeg(
                subject_ref=target.subject_ref, predicate="workload_health",
                value={"outcome": world, "crashing": len(crashing),
                       "running": len(running)},
                observed_at=now),))
        observation_ref = recorded[0][0].record_id if recorded else None
        if recorded and self._derivation is not None:
            self._derivation.derive(tenant=self._tenant,
                                    observation=recorded[0][0], recorded_at=now)
        return world, observation_ref, {"crashing": len(crashing),
                                        "running": len(running),
                                        "pods": [p.get("name") for p in owned]}
