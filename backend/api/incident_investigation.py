"""The CrashLoopBackOff investigation vertical — Phase 9.5 (ADR-085).

Three things live here, all of them *deployment configuration* rather than
mechanism, which is why they are in the composition layer:

1. **The hypothesis vocabulary** — the competing explanations a CrashLoopBackOff
   admits, seeded as OPEN with explicit evidence gaps.
2. **The tool catalog** — which read-only governed capability discriminates which
   hypothesis, and how its declared evidence projects onto a proposition.
3. **The report assembler** — the explainable result, which *computes no verdict*.

Why the hypotheses are seeded, not generated
----------------------------------------------
The five explanations below are the incident class's differential. Seeding them
is deliberate: it means the investigation begins with competitors that must be
eliminated by evidence, rather than with whatever the model happened to think of.
A model that proposes only the right answer is indistinguishable from a model
that guessed, and neither is an investigation.

Each is seeded ``OPEN`` with a stated ``missing_evidence``, so the very first gap
analysis can say *why* each is unresolved. **None of them is a finding.** The
model may add more; the platform never removes one except by observation.

The misleading hypothesis is real
-----------------------------------
H4 (resource exhaustion) is not a straw man. A container crashlooping under a
memory limit is exactly the shape an OOM kill takes, and suspecting it is
correct practice. What eliminates it is evidence and only evidence: an exit code
of 1 with reason ``Error`` is not the 137/``OOMKilled`` a kernel OOM produces,
and working-set memory far below the limit says the same thing from an
instrument that never consulted the API server.

What is deliberately absent
-----------------------------
No numeric confidence, no score, no probability, no ranking by model preference.
A hypothesis is OPEN, SUPPORTED or REFUTED, and the reason is always an
observation reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "H_STARTUP", "H_CONFIG", "H_DEPENDENCY", "H_RESOURCE", "H_REGRESSION",
    "CRASHLOOP_HYPOTHESES",
    "crashloop_hypotheses",
    "crashloop_tools",
    "InvestigationReport",
    "assemble_report",
]

H_STARTUP = "h-startup-failure"
H_CONFIG = "h-configuration"
H_DEPENDENCY = "h-dependency-connectivity"
H_RESOURCE = "h-resource-exhaustion"
H_REGRESSION = "h-deployment-regression"

#: The differential for this incident class. Order is the order they are seeded,
#: which is deliberately NOT an order of likelihood — there is no such ordering
#: here, and inventing one would be a confidence score wearing a list.
CRASHLOOP_HYPOTHESES: tuple = (
    (H_STARTUP, "the application fails during startup and exits non-zero",
     "an observation of how the container last terminated"),
    (H_CONFIG, "required configuration or a secret is missing or invalid",
     "an observation of the container's termination reason and exit code"),
    (H_DEPENDENCY, "a dependency the application needs at startup is unreachable",
     "an observation of dependency reachability"),
    (H_RESOURCE, "the container is being killed for exceeding its resource limits",
     "an observation of the container's memory use against its limit"),
    (H_REGRESSION, "a recent deployment revision introduced the failure",
     "an observation of the deployment's current revision and image"),
)


def crashloop_hypotheses(*, subject_ref: str, created_by: str = "platform:crashloop-differential/1"):
    """Seed the differential. Every hypothesis is OPEN with a stated gap.

    ``temporal_fit`` is UNKNOWN for all of them, and stays UNKNOWN until an
    observation says otherwise: asserting that a hypothesis fits the incident's
    timeline before observing the timeline is the assumption this whole apparatus
    exists to avoid.
    """
    from backend.contracts.intelligence import DifferentialHypothesis, TemporalFit
    from backend.contracts.world import HypothesisStatus

    return tuple(
        DifferentialHypothesis(
            hypothesis_ref=ref, subject_ref=subject_ref, proposition=proposition,
            status=HypothesisStatus.OPEN, temporal_fit=TemporalFit.UNKNOWN,
            missing_evidence=(gap,), created_by=created_by)
        for ref, proposition, gap in CRASHLOOP_HYPOTHESES
    )


# ---------------------------------------------------------------------------
# The read-only tool catalog
# ---------------------------------------------------------------------------

def _pod_payload(subject_ref: str) -> Mapping[str, Any]:
    """``kubernetes:pod:<namespace>/<name>`` → the governed read's parameters."""
    _, _, tail = subject_ref.partition("kubernetes:pod:")
    namespace, _, name = tail.partition("/")
    if not namespace or not name:
        raise ContractViolation(f"{subject_ref!r} is not a pod reference")
    return {"namespace": namespace, "name": name}


def _deployment_payload(subject_ref: str) -> Mapping[str, Any]:
    _, _, tail = subject_ref.partition("kubernetes:deployment:")
    namespace, _, name = tail.partition("/")
    if not namespace or not name:
        raise ContractViolation(f"{subject_ref!r} is not a deployment reference")
    return {"namespace": namespace, "name": name}


def _termination(evidence: Mapping[str, Any]) -> Optional[dict]:
    """How the container last died, as the declared proposition.

    Both fields or neither. A termination reason without its exit code (or the
    reverse) is half an answer, and half an answer about *why a process died* is
    exactly the kind of thing that gets read as the whole one.
    """
    code = evidence.get("lastExitCode")
    reason = evidence.get("lastTerminationReason")
    if not isinstance(code, int) or isinstance(code, bool) or not isinstance(reason, str):
        return None
    return {"exitCode": code, "reason": reason}


def _pod_state(evidence: Mapping[str, Any]) -> Optional[dict]:
    phase = evidence.get("phase")
    waiting = evidence.get("waitingReason")
    if not isinstance(phase, str):
        return None
    return {"phase": phase, "waitingReason": waiting if isinstance(waiting, str) else None}


def _deployment_revision(evidence: Mapping[str, Any]) -> Optional[dict]:
    revision = evidence.get("revision")
    image = evidence.get("image")
    if not isinstance(revision, str) or not isinstance(image, str):
        return None
    return {"revision": revision, "image": image}


def _memory_headroom(limit_bytes: int):
    """Working-set bytes against the configured limit — H4's falsifier.

    The proposition is a *categorical* statement, not a percentage: at or above
    the limit, or below it. A number here would be a confidence score in
    disguise, and the question a resource hypothesis asks is categorical anyway —
    was this container killed for exceeding its limit, or was it not.
    """
    def _project(evidence: Mapping[str, Any]) -> Optional[dict]:
        series = evidence.get("series")
        if not isinstance(series, list) or not series:
            return None
        peak: Optional[float] = None
        for record in series:
            if not isinstance(record, Mapping):
                continue
            raw = record.get("value")
            if not isinstance(raw, str):
                continue
            try:
                value = float(raw)
            except ValueError:
                continue
            peak = value if peak is None else max(peak, value)
        if peak is None:
            return None
        return {"atOrAboveLimit": peak >= limit_bytes}
    return _project


def crashloop_tools(*, memory_limit_bytes: int):
    """The frozen read-only allowlist for this incident class.

    Five keys, each binding one governed READ capability to one proposition. The
    model may name a key and nothing else — not a path, not a query, not a
    provider, not a URL. It does not know those exist.
    """
    from backend.api.governed_evidence_acquisition import InvestigationTool
    from backend.contexts.execution.infrastructure.adapters.connectors.prometheus import (
        INSTRUMENT_KUBELET, INSTRUMENT_KUBE_STATE_METRICS, POD_MEMORY_OPERATION,
        POD_RESTARTS_OPERATION,
    )

    kubernetes_api = "connector:kubernetes"
    return (
        InvestigationTool(
            key="k8s.pod_state", operation="kubernetes.pod.get",
            subject_kind="kubernetes:pod:", predicate="pod_state",
            describes="the pod's phase and why its container is waiting",
            project=_pod_state, source_ref=kubernetes_api,
            payload_from_subject=_pod_payload),
        InvestigationTool(
            key="k8s.pod_termination", operation="kubernetes.pod.get",
            subject_kind="kubernetes:pod:", predicate="last_termination",
            describes="the container's last exit code and termination reason",
            project=_termination, source_ref=kubernetes_api,
            payload_from_subject=_pod_payload),
        InvestigationTool(
            key="k8s.deployment_revision", operation="kubernetes.deployment.get",
            subject_kind="kubernetes:deployment:", predicate="deployed_revision",
            describes="the deployment's current revision and container image",
            project=_deployment_revision, source_ref=kubernetes_api,
            payload_from_subject=_deployment_payload),
        InvestigationTool(
            key="metrics.pod_memory", operation=POD_MEMORY_OPERATION,
            subject_kind="kubernetes:pod:", predicate="memory_pressure",
            describes="whether container memory reached its configured limit",
            project=_memory_headroom(memory_limit_bytes),
            source_ref=INSTRUMENT_KUBELET,
            payload_from_subject=lambda _s: {}),
        InvestigationTool(
            key="metrics.pod_restarts", operation=POD_RESTARTS_OPERATION,
            subject_kind="kubernetes:pod:", predicate="restart_count",
            describes="the restart count as the metrics pipeline reports it",
            project=lambda e: _restart_count(e), source_ref=INSTRUMENT_KUBE_STATE_METRICS,
            payload_from_subject=lambda _s: {}),
    )


def _restart_count(evidence: Mapping[str, Any]) -> Optional[dict]:
    """The 9.4 proposition, unchanged — so a metric restart count and a
    Kubernetes restart count remain comparable and the corroboration engine can
    still see that they share an origin."""
    series = evidence.get("series")
    if not isinstance(series, list) or not series:
        return None
    for record in series:
        if not isinstance(record, Mapping):
            continue
        raw = record.get("value")
        if not isinstance(raw, str):
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if value == int(value):
            return {"restartCount": int(value)}
    return None


# ---------------------------------------------------------------------------
# The explainable result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InvestigationReport:
    """The answer to the questions an operator actually asks.

    Assembled entirely from what the platform already decided — the differential,
    the World Plane's evidence with its lineage, the corroboration assessment and
    the Assurance verdict. **Nothing here computes a verdict.** A report that
    could reach its own conclusion would be a second opinion competing with the
    engine's, and the whole point is that there is one.
    """

    incident_ref: str
    investigation_ref: str
    conclusion: str
    diagnosis: Optional[str]
    supported: tuple
    eliminated: tuple
    still_open: tuple
    eliminated_by: Mapping[str, tuple]
    supported_by: Mapping[str, tuple]
    evidence: tuple
    corroboration: Optional[Mapping[str, Any]]
    assurance: Optional[Mapping[str, Any]]
    residual_uncertainty: str
    read_only: bool = True

    def to_dict(self) -> dict:
        return {
            "incident_ref": self.incident_ref,
            "investigation_ref": self.investigation_ref,
            "conclusion": self.conclusion,
            "diagnosis": self.diagnosis,
            "hypotheses": {
                "supported": list(self.supported),
                "eliminated": list(self.eliminated),
                "still_open": list(self.still_open),
            },
            "why_eliminated": {k: list(v) for k, v in self.eliminated_by.items()},
            "why_supported": {k: list(v) for k, v in self.supported_by.items()},
            "evidence": list(self.evidence),
            "corroboration": dict(self.corroboration) if self.corroboration else None,
            "assurance": dict(self.assurance) if self.assurance else None,
            "residual_uncertainty": self.residual_uncertainty,
            "read_only": self.read_only,
        }

    def render(self) -> str:
        """The operator-facing narration. Every line is traceable to a field."""
        lines = [
            f"INCIDENT      {self.incident_ref}",
            f"CONCLUSION    {self.conclusion}",
            f"DIAGNOSIS     {self.diagnosis or 'none — no hypothesis was affirmed'}",
            "",
            "SUPPORTED     " + (", ".join(self.supported) or "none"),
        ]
        for ref in self.supported:
            lines.append(f"                by {list(self.supported_by.get(ref, ()))}")
        lines.append("ELIMINATED    " + (", ".join(self.eliminated) or "none"))
        for ref in self.eliminated:
            lines.append(f"                by {list(self.eliminated_by.get(ref, ()))}")
        lines.append("STILL OPEN    " + (", ".join(self.still_open) or "none"))
        if self.corroboration:
            lines += ["",
                      f"CORROBORATION {self.corroboration.get('level')}",
                      f"              {self.corroboration.get('reason')}"]
        if self.assurance:
            lines += ["",
                      f"ASSURANCE     {self.assurance.get('verdict')}",
                      f"              {self.assurance.get('rationale')}"]
        lines += ["", f"RESIDUAL      {self.residual_uncertainty}"]
        return "\n".join(lines)


def assemble_report(
    *, investigation: Any, evidence_view: Sequence[Mapping[str, Any]] = (),
    corroboration: Any = None, assurance: Any = None,
) -> InvestigationReport:
    """Assemble the explainable result. Reads state; decides nothing.

    ``residual_uncertainty`` comes from ``settle()`` — the same honest terminal
    read the engine itself uses — so the report cannot be more confident than the
    investigation was. Where Assurance did not verify the conclusion, the report
    says so rather than omitting the question.
    """
    from backend.contracts.world import HypothesisStatus
    from backend.intelligence.application.differential import settle

    summary = settle(investigation)
    supported, eliminated, still_open = [], [], []
    supported_by: dict = {}
    eliminated_by: dict = {}
    for hypothesis in investigation.differential:
        if hypothesis.status is HypothesisStatus.SUPPORTED:
            supported.append(hypothesis.hypothesis_ref)
            supported_by[hypothesis.hypothesis_ref] = tuple(hypothesis.evidence_for)
        elif hypothesis.status is HypothesisStatus.REFUTED:
            eliminated.append(hypothesis.hypothesis_ref)
            eliminated_by[hypothesis.hypothesis_ref] = tuple(hypothesis.evidence_against)
        else:
            still_open.append(hypothesis.hypothesis_ref)

    diagnosis = None
    if len(supported) == 1:
        diagnosis = next(h.proposition for h in investigation.differential
                         if h.hypothesis_ref == supported[0])

    # ``settle`` always says "not Assurance-verified", because at Phase 8.4 that
    # was always true: settling and verifying are different gates and settle does
    # not know about the second one. Once Assurance HAS run, leaving that phrase
    # standing would understate what the platform knows — and replacing it with
    # nothing would overstate it. So the verdict is named either way.
    residual = summary.residual_uncertainty
    if assurance is None:
        residual = (residual + " The conclusion has not been independently "
                    "verified by the Assurance Plane.").strip()
    else:
        verdict = assurance.verification.verdict.value
        residual = residual.replace(
            "not Assurance-verified",
            f"independently adjudicated by Assurance as {verdict.upper()}")
        if verdict != "supported":
            residual += (f" Assurance did not support the conclusion "
                         f"({verdict}); the diagnosis stands on the "
                         "investigation's evidence alone.")

    return InvestigationReport(
        incident_ref=investigation.incident_ref,
        investigation_ref=investigation.investigation_ref,
        conclusion=(investigation.conclusion.value if investigation.conclusion
                    else summary.conclusion),
        diagnosis=diagnosis,
        supported=tuple(supported), eliminated=tuple(eliminated),
        still_open=tuple(still_open),
        eliminated_by=eliminated_by, supported_by=supported_by,
        evidence=tuple(evidence_view),
        corroboration=(corroboration.to_dict() if hasattr(corroboration, "to_dict")
                       else corroboration),
        assurance=(
            {"verdict": assurance.verification.verdict.value,
             "rationale": getattr(assurance, "rationale", ""),
             "verifier": assurance.verification.verifier.identity_ref
             if hasattr(assurance.verification.verifier, "identity_ref") else None}
            if assurance is not None else None),
        residual_uncertainty=residual,
    )
