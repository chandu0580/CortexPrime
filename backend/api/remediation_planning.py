"""Remediation planning — Phase 11.4 (ADR-124).

MODEL -> PROPOSAL -> VALIDATION -> PLAN -> POLICY. This module is the
VALIDATION and PLAN steps, and it asks POLICY (the existing autonomy policy,
supplied by composition) for the one decision that is policy's to make.

It turns a schema-validated proposal plus fresh governed evidence into either a
``RemediationPlan`` -- one typed action, exactly bound to one resource, with a
platform-computed risk, a reversibility class, a blast radius, an expected
state, verification criteria, a compensation, an authority and the digest an
approval is bound to -- or a ``ProposalDecision`` saying why not.

What is decided here, and by what
---------------------------------
* whether the requested action is a tool at all: the ACTION REGISTRY (one
  admitted action; a named set of prohibited classes; everything else unknown);
* whether the diagnosis supports it: the assessment's own supported hypotheses,
  never the model's say-so;
* which resource: the incident's own workload in the bound namespace, resolved
  to a UID from a governed read -- a proposal naming anything else is a
  confused deputy and is rejected;
* which revision: one the Deployment itself still owns, whose template differs
  from the running one, and never the running one;
* the risk: ``classify_action_risk`` from declared factors, starting at the
  capability's own implied risk (supplied by composition, so the taxonomy has
  one implementation);
* the authority: the autonomy policy's decision, mapped without interpretation.

This module imports no bounded context (the composition-root rule): the
approval-digest function, the capability's implied risk and the autonomy
evaluator are handed in by ``capability_execution_composition``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping, Optional, Sequence

from backend.contracts.execution import SideEffectClass
from backend.contracts.intelligence.autonomy import Capability
from backend.contracts.intelligence.investigation import AutonomyLevel
from backend.contracts.policy import RiskClassification, RiskFactors, RiskLevel
from backend.contracts.remediation import (
    BlastRadius, PlanAuthority, ProposalDecision, RemediationPlan, RemediationStage,
    ResourceTarget, ReversibilityClass, RollbackStrategy, VerificationCriterion,
)
from backend.platform.hashing import compute_digest

__all__ = [
    "ACTION_ROLLBACK", "ACTION_NONE", "REGRESSION_HYPOTHESIS", "OUTCOME_PREDICATE",
    "classify_action", "classify_action_risk", "workload_of", "CapabilityFacts",
    "PlanningScope", "WorldSnapshot", "DiagnosisFacts", "PlanningResult", "RemediationPlanner",
    "PROHIBITED_ACTIONS",
]

ACTION_ROLLBACK = "deployment.rollback"
ACTION_NONE = "no_action"
REGRESSION_HYPOTHESIS = "h-deployment-regression"
OUTCOME_PREDICATE = "remediation_outcome"
TARGET_PREDICATE = "remediation_target"

#: The ONE admitted action and the capability it maps to.
ACTION_REGISTRY = {
    ACTION_ROLLBACK: {"capability": "platform.kubernetes.deployment.rollback",
                      "operation": "kubernetes.deployment.rollback", "kind": "deployment"},
}

#: Action classes the platform refuses outright, with the reason recorded. A
#: model may recommend any of these in prose; none becomes a plan.
PROHIBITED_ACTIONS = {
    "deployment.delete": "deletes the workload: DESTRUCTIVE (removes state and capacity)",
    "deployment.scale_to_zero": "removes all capacity: DESTRUCTIVE",
    "pod.delete": "deletes pods directly: bypasses the controller, DESTRUCTIVE",
    "namespace.delete": "deletes a namespace: DESTRUCTIVE, unbounded blast radius",
    "pvc.delete": "deletes persistent data: DESTRUCTIVE, irrecoverable",
    "node.drain": "evicts every pod on a node: cluster-scoped blast radius",
    "shell.exec": "arbitrary shell: not a typed capability",
    "kubectl": "arbitrary kubectl: not a typed capability",
    "kubectl.exec": "exec into a container: arbitrary code in a workload",
    "cluster-admin": "cluster-admin authority: an escalation, never an action",
    "rbac.escalate": "privilege escalation: never an action",
    "http.request": "arbitrary HTTP: not a typed capability",
    "credential.read": "credential retrieval: credentials never leave the broker",
    "secret.read": "secret retrieval: credentials never leave the broker",
}
_PROHIBITED_WORDS = ("delete", "destroy", "drop", "exec", "shell", "kubectl", "admin", "escalat",
                     "impersonat", "credential", "secret", "token", "http", "curl", "wget",
                     "scale_to_zero", "drain", "cordon", "bash", "patch", "apply", "yaml")

_SUBJECT = re.compile(
    r"^kubernetes:(?P<kind>pod|deployment):(?P<namespace>[a-z0-9][a-z0-9.-]{0,62})/"
    r"(?P<name>[a-z0-9][a-z0-9.-]{0,62})$")
_POD_SUFFIX = re.compile(r"-[a-z0-9]{6,10}-[a-z0-9]{5}$|-[a-z0-9]{8,10}$")


def workload_of(incident_ref: Optional[str]) -> Optional[tuple[str, str]]:
    """``(namespace, deployment)`` from a platform-written incident reference.

    One implementation, used by the planner and by the product's remediation
    service. Anything it does not understand yields ``None`` -- no guess about
    what an operator probably meant."""
    match = _SUBJECT.match((incident_ref or "").strip())
    if match is None:
        return None
    name = match.group("name")
    if match.group("kind") == "pod":
        name = _POD_SUFFIX.sub("", name) or name
    return match.group("namespace"), name


def classify_action(action: Optional[str]) -> tuple[str, str]:
    """The tool registry. Returns ``(class, reason)``: allowed / no_action /
    prohibited / unknown. Unknown and prohibited are both refusals; the
    difference is recorded because a request for deletion is a different signal
    from a typo."""
    normalized = (action or "").strip().lower()
    if normalized in ACTION_REGISTRY:
        return "allowed", f"{normalized} is the admitted typed action"
    if normalized == ACTION_NONE:
        return "no_action", "the proposer judged that no automated action is appropriate"
    if normalized in PROHIBITED_ACTIONS:
        return "prohibited", f"{normalized}: {PROHIBITED_ACTIONS[normalized]}"
    if any(word in normalized for word in _PROHIBITED_WORDS):
        return "prohibited", f"{normalized!r} names a prohibited action class"
    return "unknown", f"{normalized!r} is not a capability in the remediation registry"


def classify_action_risk(
    *, floor: RiskLevel, side_effect_class: SideEffectClass, environment: str, production: bool,
    resource_count: int, replicas: int, persistent_volumes: bool, compensation_available: bool,
    target_health_known: bool, credential_scope: str = "namespace",
    max_replicas_for_reduction: int = 10,
) -> RiskClassification:
    """The platform's action risk. Deterministic, factor by factor, and never
    lower than the capability's consequence class except by ONE stated rule.

    The floor is the capability's implied risk (``implied_risk_for``, passed in).
    It may be lowered by exactly one level, and only when every one of these
    holds: the compensation was verified available, the environment is not
    production, exactly one resource, no persistent volume in the pod template,
    the target revision was observed healthy by the World Plane, the replica
    count is bounded, and the credential is namespace-scoped. Anything that
    widens the blast radius raises it. DESTRUCTIVE is CRITICAL whatever else holds.
    """
    order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
    level = floor
    notes = [f"capability consequence class: {floor.value} ({side_effect_class.value})"]
    if side_effect_class is SideEffectClass.DESTRUCTIVE:
        level = RiskLevel.CRITICAL
        notes.append("destructive: critical regardless of any other factor")
    reducible = (side_effect_class is not SideEffectClass.DESTRUCTIVE and compensation_available
                 and not production and resource_count == 1 and not persistent_volumes
                 and target_health_known and replicas <= max_replicas_for_reduction
                 and credential_scope == "namespace")
    notes.append(f"resource type deployment, scope {resource_count} resource(s), {replicas} replica(s) replaced")
    notes.append(f"environment {environment} ({'production' if production else 'non-production'})")
    notes.append(f"data mutation: {'persistent volumes in the pod template' if persistent_volumes else 'none (no persistent volume)'}")
    notes.append(f"rollback availability: {'compensation verified available' if compensation_available else 'NO compensation available'}")
    notes.append(f"target revision health: {'observed healthy by the World Plane' if target_health_known else 'never observed healthy (unknown)'}")
    notes.append(f"credential sensitivity: {credential_scope}-scoped service account")
    if reducible and level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
        level = order[order.index(level) - 1]
        notes.append("reduced one level: every reduction condition holds")
    if production:
        level = max(level, RiskLevel.HIGH, key=order.index)
        notes.append("production: at least high")
    if resource_count > 1 or replicas > max_replicas_for_reduction:
        level = max(level, RiskLevel.HIGH, key=order.index)
        notes.append("wide blast radius: at least high")
    factors = RiskFactors(side_effect_class=side_effect_class, environment=environment,
                          resource_count=max(1, resource_count),
                          reversible=False, resource_criticality=None)
    return RiskClassification(level=level, factors=factors, rationale="; ".join(notes))


@dataclass(frozen=True)
class CapabilityFacts:
    capability_ref: str
    capability_digest: str
    operation: str
    risk_floor: RiskLevel
    side_effect_class: SideEffectClass
    compensation_declared: bool


@dataclass(frozen=True)
class PlanningScope:
    tenant_id: str
    cluster_ref: str
    namespace: str
    environment: str
    production: bool
    principal_id: str
    policy_version: str
    timeout_seconds: int = 120
    verification_window_seconds: int = 180
    max_replicas_for_reduction: int = 10


@dataclass(frozen=True)
class WorldSnapshot:
    """What fresh governed reads said at plan time. Values from evidence only."""

    deployment: Mapping[str, Any]
    replicasets: Sequence[Mapping[str, Any]]
    observation_refs: tuple[str, ...]
    healthy_revisions: Mapping[str, tuple] = field(default_factory=dict)
    read_at: Optional[datetime] = None


@dataclass(frozen=True)
class DiagnosisFacts:
    assessment: Mapping[str, Any]
    assessment_ref: str
    diagnosed_template_digest: Optional[str] = None
    rollout_observation_ref: Optional[str] = None


@dataclass(frozen=True)
class PlanningResult:
    plan: Optional[RemediationPlan] = None
    decision: Optional[ProposalDecision] = None
    autonomy: Any = None

    @property
    def planned(self) -> bool:
        return self.plan is not None


def _supports_regression(assessment: Mapping[str, Any]) -> bool:
    if assessment.get("outcome") not in ("ROOT_CAUSE_IDENTIFIED",):
        return False
    if assessment.get("confidence") not in ("high", "medium"):
        return False
    if assessment.get("root_cause_hypothesis") == REGRESSION_HYPOTHESIS:
        return True
    for weight in assessment.get("weights") or ():
        if isinstance(weight, Mapping) and weight.get("role") == "supports" \
                and weight.get("hypothesis_ref") == REGRESSION_HYPOTHESIS:
            return True
    return False


def _int(value: Any) -> Optional[int]:
    try:
        if isinstance(value, bool):
            return None
        return int(str(value))
    except (TypeError, ValueError):
        return None


class RemediationPlanner:
    def __init__(self, *, scope: PlanningScope, capability: CapabilityFacts,
                 approval_digest: Callable[[Mapping[str, Any]], str],
                 autonomy: Callable[..., Any]) -> None:
        self._scope = scope
        self._capability = capability
        self._approval_digest = approval_digest
        self._autonomy = autonomy

    # -- refusals ------------------------------------------------------------

    def _decision(self, *, stage: RemediationStage, proposal: Any, incident_ref: str,
                  investigation_ref: str, reasons: Sequence[str], now: datetime,
                  risk_level: Optional[str] = None, recommendation: Optional[str] = None,
                  autonomy: Any = None) -> PlanningResult:
        return PlanningResult(decision=ProposalDecision(
            proposal_digest=getattr(proposal, "digest", None) or "absent",
            incident_ref=incident_ref, investigation_ref=investigation_ref,
            tenant_id=self._scope.tenant_id, stage=stage,
            requested_action=str(getattr(proposal, "action", "") or "")[:80],
            reasons=tuple(str(r)[:400] for r in reasons), proposal_source=getattr(proposal, "source", "none"),
            decided_at=now, risk_level=risk_level, recommendation=recommendation), autonomy=autonomy)

    # -- the plan ------------------------------------------------------------

    def plan(self, *, incident_ref: str, investigation_ref: str, proposal: Any,
             diagnosis: DiagnosisFacts, world: WorldSnapshot, now: datetime) -> PlanningResult:
        scope = self._scope
        assessment = diagnosis.assessment or {}
        recommendation = assessment.get("recommended_action_candidate") or assessment.get("next_step")
        common = dict(proposal=proposal, incident_ref=incident_ref,
                      investigation_ref=investigation_ref, now=now)

        # 1. the tool registry ------------------------------------------------
        action_class, action_reason = classify_action(proposal.action)
        if action_class == "prohibited":
            return self._decision(stage=RemediationStage.PROHIBITED, reasons=(action_reason,),
                                  risk_level=RiskLevel.CRITICAL.value, recommendation=recommendation, **common)
        if action_class == "unknown":
            return self._decision(stage=RemediationStage.PROPOSAL_REJECTED, reasons=(action_reason,),
                                  recommendation=recommendation, **common)
        if action_class == "no_action":
            return self._decision(stage=RemediationStage.RECOMMENDATION_ONLY,
                                  reasons=(action_reason, str(proposal.rationale or "")[:300] or "no rationale"),
                                  recommendation=recommendation, **common)

        # 2. the diagnosis must support THIS action ----------------------------
        if not _supports_regression(assessment):
            return self._decision(
                stage=RemediationStage.PROPOSAL_REJECTED,
                reasons=(f"the diagnosis does not support a rollback: outcome={assessment.get('outcome')}, "
                         f"confidence={assessment.get('confidence')}, "
                         f"root cause={assessment.get('root_cause_hypothesis')}",),
                recommendation=recommendation, **common)
        if proposal.hypothesis_ref != REGRESSION_HYPOTHESIS:
            return self._decision(
                stage=RemediationStage.PROPOSAL_REJECTED,
                reasons=(f"a rollback rests on {REGRESSION_HYPOTHESIS}; the proposal cites "
                         f"{proposal.hypothesis_ref!r}",), recommendation=recommendation, **common)

        # 3. evidence: only the investigation's own ---------------------------
        known = {str(r) for r in assessment.get("supporting_evidence") or ()}
        known |= {str(w.get("observation_ref")) for w in assessment.get("weights") or ()
                  if isinstance(w, Mapping)}
        cited = tuple(r for r in proposal.evidence_refs if r in known)
        if not cited:
            return self._decision(
                stage=RemediationStage.PROPOSAL_REJECTED,
                reasons=("missing evidence: none of the proposal's evidence references belongs to this "
                         "investigation; authority cannot be established through foreign evidence",),
                recommendation=recommendation, **common)

        # 4. the target: this incident's workload, in the bound namespace -----
        incident_workload = workload_of(incident_ref)
        if incident_workload is None:
            return self._decision(stage=RemediationStage.PROPOSAL_REJECTED,
                                  reasons=(f"the incident subject {incident_ref!r} names no workload",),
                                  recommendation=recommendation, **common)
        wanted_ns, wanted_name = incident_workload
        if proposal.target_kind.strip().lower() != "deployment":
            return self._decision(stage=RemediationStage.PROPOSAL_REJECTED,
                                  reasons=(f"a rollback targets a Deployment, not {proposal.target_kind!r}",),
                                  recommendation=recommendation, **common)
        if (proposal.target_namespace, proposal.target_name) != (wanted_ns, wanted_name) \
                or wanted_ns != scope.namespace:
            return self._decision(
                stage=RemediationStage.PROPOSAL_REJECTED,
                reasons=(f"target outside this incident's authorized scope: proposal names "
                         f"{proposal.target_namespace}/{proposal.target_name}, the incident is "
                         f"{wanted_ns}/{wanted_name} in tenant namespace {scope.namespace}",),
                recommendation=recommendation, **common)

        # 5. the world, now --------------------------------------------------
        dep = world.deployment or {}
        uid = dep.get("uid")
        generation = _int(dep.get("generation"))
        current_revision = _int(dep.get("revision"))
        current_digest = dep.get("templateDigest")
        replicas = _int(dep.get("replicas")) or 0
        if not (isinstance(uid, str) and uid and generation and current_revision and current_digest):
            return self._decision(stage=RemediationStage.PROPOSAL_REJECTED,
                                  reasons=("the target's identity could not be established from a governed read",),
                                  recommendation=recommendation, **common)
        if dep.get("name") != wanted_name or dep.get("namespace") != wanted_ns:
            return self._decision(stage=RemediationStage.PROPOSAL_REJECTED,
                                  reasons=("the governed read answered for a different object",),
                                  recommendation=recommendation, **common)
        if dep.get("paused") is True:
            return self._decision(stage=RemediationStage.PROPOSAL_REJECTED,
                                  reasons=("the Deployment is paused; a paused rollout is not rolled back",),
                                  recommendation=recommendation, **common)
        if diagnosis.diagnosed_template_digest and diagnosis.diagnosed_template_digest != current_digest:
            return self._decision(
                stage=RemediationStage.STALE if False else RemediationStage.PROPOSAL_REJECTED,
                reasons=("the diagnosis is stale: the running pod template is not the one the investigation "
                         "diagnosed; re-investigate before remediating",),
                recommendation=recommendation, **common)
        owned = [r for r in world.replicasets or () if isinstance(r, Mapping) and r.get("ownerUid") == uid]
        by_revision: dict = {}
        for record in owned:
            rev = _int(record.get("revision"))
            if rev is not None and record.get("podTemplateDigest"):
                by_revision.setdefault(rev, []).append(record)
        current = by_revision.get(current_revision) or []
        if len(current) != 1 or current[0].get("podTemplateDigest") != current_digest:
            return self._decision(stage=RemediationStage.PROPOSAL_REJECTED,
                                  reasons=("the ReplicaSet lineage is inconsistent with the Deployment",),
                                  recommendation=recommendation, **common)
        if proposal.target_revision is not None:
            candidates = by_revision.get(proposal.target_revision) or []
            if proposal.target_revision == current_revision or not candidates:
                return self._decision(
                    stage=RemediationStage.PROPOSAL_REJECTED,
                    reasons=(f"target revision {proposal.target_revision} is not an available prior revision of "
                             f"this Deployment (current {current_revision}); no substitute is chosen",),
                    recommendation=recommendation, **common)
            target_rev = proposal.target_revision
        else:
            prior = sorted((rev for rev, recs in by_revision.items()
                            if rev != current_revision and len(recs) == 1
                            and recs[0].get("podTemplateDigest") != current_digest), reverse=True)
            if not prior:
                return self._decision(stage=RemediationStage.PROPOSAL_REJECTED,
                                      reasons=("no prior revision with a different template exists",),
                                      recommendation=recommendation, **common)
            target_rev = prior[0]
        target_records = by_revision.get(target_rev) or []
        if len(target_records) != 1:
            return self._decision(stage=RemediationStage.PROPOSAL_REJECTED,
                                  reasons=(f"revision {target_rev} is ambiguous in the lineage",),
                                  recommendation=recommendation, **common)
        target_digest = target_records[0].get("podTemplateDigest")
        if target_digest == current_digest:
            return self._decision(stage=RemediationStage.PROPOSAL_REJECTED,
                                  reasons=("the target revision runs the same template; a rollback changes nothing",),
                                  recommendation=recommendation, **common)

        # 6. compensation, health, blast radius, risk ---------------------------
        history_limit = _int(dep.get("revisionHistoryLimit"))
        compensation_available = (self._capability.compensation_declared
                                  and (history_limit is None or history_limit >= 1))
        health_refs = tuple(world.healthy_revisions.get(str(target_rev)) or ())
        persistent = bool(_int(dep.get("persistentVolumeClaims")) or 0)
        risk = classify_action_risk(
            floor=self._capability.risk_floor, side_effect_class=self._capability.side_effect_class,
            environment=scope.environment, production=scope.production, resource_count=1,
            replicas=replicas, persistent_volumes=persistent,
            compensation_available=compensation_available, target_health_known=bool(health_refs),
            max_replicas_for_reduction=scope.max_replicas_for_reduction)
        reversibility = (ReversibilityClass.COMPENSABLE if compensation_available
                         else ReversibilityClass.IRREVERSIBLE)
        blast = BlastRadius(
            scope="single-resource", resource_count=1, namespace=wanted_ns, replicas=replicas,
            pods_replaced=replicas, persistent_volumes=persistent, production=scope.production,
            description=(f"one Deployment ({wanted_name}, uid {uid}) in namespace {wanted_ns}: its pod template "
                         f"becomes revision {target_rev}'s and its {replicas} pod(s) are replaced; no other "
                         "resource is written"))
        if risk.level is RiskLevel.CRITICAL:
            return self._decision(stage=RemediationStage.PROHIBITED,
                                  reasons=(f"critical action risk: {risk.rationale}",),
                                  risk_level=risk.level.value, recommendation=recommendation, **common)

        plan_id = "rplan_" + compute_digest({
            "tenant": scope.tenant_id, "incident": incident_ref, "investigation": investigation_ref,
            "uid": uid, "generation": generation, "from": current_digest, "to": target_digest,
            "policy": scope.policy_version, "proposal": proposal.digest}).value[:24]
        parameters = {
            "namespace": wanted_ns, "name": wanted_name, "uid": uid,
            "expected_generation": generation, "expected_revision": current_revision,
            "expected_template_digest": current_digest, "target_revision": target_rev,
            "target_template_digest": target_digest, "plan_id": plan_id,
            "policy_version": scope.policy_version,
        }
        action_digest = self._approval_digest(parameters)
        expected_state = {"templateDigest": target_digest, "rolledOut": True, "available": True,
                          "crashLooping": False}
        criteria = (
            VerificationCriterion(name="running_template", predicate=OUTCOME_PREDICATE,
                                  expected={"templateDigest": target_digest},
                                  observed_by="independent governed read (reader identity)",
                                  window_seconds=scope.verification_window_seconds),
            VerificationCriterion(name="rolled_out", predicate=OUTCOME_PREDICATE,
                                  expected={"rolledOut": True},
                                  observed_by="deployment status: observedGeneration, updated and unavailable replicas",
                                  window_seconds=scope.verification_window_seconds),
            VerificationCriterion(name="available", predicate=OUTCOME_PREDICATE, expected={"available": True},
                                  observed_by="deployment Available condition and available replicas",
                                  window_seconds=scope.verification_window_seconds),
            VerificationCriterion(name="not_crashlooping", predicate=OUTCOME_PREDICATE,
                                  expected={"crashLooping": False},
                                  observed_by="pod list: readiness and waiting reasons of the workload's pods",
                                  window_seconds=scope.verification_window_seconds),
        )
        strategy = RollbackStrategy(
            kind="compensating_rollback" if compensation_available else "none",
            action=ACTION_ROLLBACK if compensation_available else None,
            target_revision=current_revision if compensation_available else None,
            target_template_digest=current_digest if compensation_available else None,
            available=compensation_available,
            verified_by="governed read of the Deployment (revisionHistoryLimit) and its owned ReplicaSets",
            note=("the pre-action revision's ReplicaSet is retained by the controller; rolling back to it "
                  "restores the declared template (history and pods are not restored)"
                  if compensation_available else "no compensation: the pre-action revision would be discarded"))
        target = ResourceTarget(
            tenant_id=scope.tenant_id, cluster_ref=scope.cluster_ref, namespace=wanted_ns,
            kind="Deployment", name=wanted_name, uid=uid, generation=generation,
            current_revision=current_revision, current_template_digest=current_digest)

        # 7. POLICY: the autonomy decision --------------------------------------
        requested = (AutonomyLevel.A4_AUTONOMOUS if proposal.from_model else AutonomyLevel.A2_RECOMMEND)
        capability = Capability(
            capability_ref=self._capability.capability_ref, operation=self._capability.operation,
            resource_class="deployment", side_effect_class=self._capability.side_effect_class,
            reversible=False, compensable=compensation_available)
        decision = self._autonomy(capability=capability, risk=risk, requested=requested, now=now)
        if not proposal.from_model:
            authority = PlanAuthority.RECOMMENDATION_ONLY
            reason = ("the proposal came from the deterministic fallback (the model was unavailable or not "
                      "configured); a recommendation is recorded and nothing is executed")
        elif getattr(decision, "permits_autonomous_action", False) \
                and reversibility is ReversibilityClass.COMPENSABLE:
            authority = PlanAuthority.AUTONOMOUS
            reason = f"delegated autonomy: {decision.reason}"
        else:
            authority = PlanAuthority.HUMAN_APPROVAL
            reason = f"human approval required: {getattr(decision, 'reason', 'no autonomy decision')}"
        evidence = tuple(dict.fromkeys(cited + tuple(world.observation_refs)
                                       + ((diagnosis.rollout_observation_ref,) if diagnosis.rollout_observation_ref else ())))
        plan = RemediationPlan(
            plan_id=plan_id, incident_ref=incident_ref, investigation_ref=investigation_ref,
            tenant_id=scope.tenant_id, target=target, diagnosis_ref=diagnosis.assessment_ref,
            diagnosis=str(assessment.get("root_cause") or REGRESSION_HYPOTHESIS)[:600],
            evidence_refs=evidence, action=ACTION_ROLLBACK, capability_ref=self._capability.capability_ref,
            operation=self._capability.operation, parameters=parameters, risk=risk,
            reversibility=reversibility, blast_radius=blast, expected_state=expected_state,
            verification_criteria=criteria, rollback_strategy=strategy,
            timeout_seconds=scope.timeout_seconds,
            approval_requirement=getattr(getattr(decision, "approval_requirement", None), "value",
                                         "human_approval"),
            authority=authority, authority_reason=reason[:600], action_digest=action_digest,
            policy_version=scope.policy_version, principal_id=scope.principal_id,
            proposal_source=f"{proposal.source}:{proposal.model_identity}", proposal_digest=proposal.digest,
            created_at=now, autonomy_decision_id=getattr(decision, "decision_id", None),
            target_health_evidence=health_refs)
        return PlanningResult(plan=plan, autonomy=decision)
