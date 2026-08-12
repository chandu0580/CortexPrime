"""The prediction lifecycle — Phase 8.5.

Turns a SUPPORTED diagnostic hypothesis into a governed, observable, verified test:

    HYPOTHESIS -> PREDICTION -> GOVERNED ACTION -> REAL EXECUTION ->
    OBSERVED OUTCOME -> PREDICTION EVALUATION -> INDEPENDENT ASSURANCE ->
    DURABLE CALIBRATION EVIDENCE

The model PROPOSES a falsifiable prediction (through the governed boundary — the
firewall rejects any self-declared outcome/success/confidence). The platform:
  * validates the prediction's structure and ties it to a real hypothesis;
  * constructs the World ``Prediction`` (a forward claim — legitimately model-
    authored) and records it durably (cw_reasoning);
  * requests a GOVERNED action through a port (the ONE Plane of Action);
  * derives the ``Outcome`` OUTSIDE the intelligence plane, from the real
    ``execution_ref`` + independently observed world state — never model text
    (BND-MODEL-CANNOT-CREATE-FACT forbids intelligence constructing an Outcome);
  * evaluates the prediction deterministically (``evaluate_prediction``);
  * asks the INDEPENDENT Assurance Plane to verify the prediction/outcome
    relationship (a self-verification is refused);
  * links prediction/verification onto the investigation and returns a result that
    keeps three things distinct: diagnostic support, prediction support, and
    independent verification.

This module imports contracts, the World *application* layer (``evaluate_prediction``,
``ReasoningLedger`` — pure, injected repository), and the investigation service. It
imports NO connector, provider, gateway, execution plane, ``Outcome``, or
``WorldVerification`` constructor — those are reached only through ports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional, Protocol

from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantRef
from backend.contracts.world import Prediction, ProvenanceRef
from backend.platform.identity.generators import prefixed_id
from backend.world.application import evaluate_prediction
from backend.intelligence.application.proposal import ProposedPrediction

__all__ = [
    "PredictionRejected",
    "ValidatedPrediction",
    "PredictionSupport",
    "OutcomeResolution",
    "VerificationView",
    "PredictionProposalPort",
    "GovernedOutcomePort",
    "AssuranceVerificationPort",
    "PredictionLifecycleResult",
    "PredictionPolicy",
    "PredictionLifecycle",
]

#: URL / shell / injection fragments a reference must never contain.
_FORBIDDEN_FRAGMENTS = ("http://", "https://", "$(", "`", ";", "&&", "|", "../", "\n")


class PredictionRejected(ContractViolation):
    """A proposed prediction was refused (not tied to a known hypothesis, no
    structured expectation, or an unsafe reference)."""


class PredictionSupport(str, __import__("enum").Enum):
    """The platform's deterministic evaluation of a prediction against reality —
    NOT a model claim and NOT a confidence. Mirrors the Assurance Verdict trichotomy
    so 'we don't know' is never collapsed into 'wrong'."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class ValidatedPrediction:
    hypothesis_ref: str
    subject_ref: str
    predicate: str
    expected: Any
    expected_condition: str
    evaluation_window_seconds: int
    provider: str


@dataclass(frozen=True)
class OutcomeResolution:
    """What a governed action returned: the real execution ref, the independently
    observed world value, and the constructed ``Outcome`` (built OUTSIDE the
    intelligence plane). ``outcome`` is opaque here — the orchestrator only hands it
    to ``evaluate_prediction``. ``observed_value`` is None when nothing was observed
    in the window (INSUFFICIENT_EVIDENCE — silence is never a failure)."""

    ok: bool
    execution_ref: Optional[str] = None
    observation_ref: Optional[str] = None
    observed_value: Any = None
    outcome: Any = None
    reason: str = ""


@dataclass(frozen=True)
class VerificationView:
    """The independent Assurance decision, as the intelligence plane consumes it —
    a small view over the minted ``WorldVerification`` (which the orchestrator never
    constructs). ``refused`` is set when Assurance refused to even adjudicate (e.g.
    self-verification)."""

    verdict: str                       # Verdict value: supported/unsupported/insufficient_evidence
    verification_ref: Optional[str] = None
    evidence_refs: tuple[str, ...] = ()
    rationale: str = ""
    refused: bool = False

    @property
    def is_supported(self) -> bool:
        return self.verdict == "supported"


# -- ports (composition supplies the implementations) ----------------------

class PredictionProposalPort(Protocol):
    """The governed model boundary seam for a prediction proposal."""

    def propose_prediction(self, *, context, investigation, hypothesis_ref: str,
                           now: datetime) -> ProposedPrediction:
        ...


class GovernedOutcomePort(Protocol):
    """Runs ONE governed action (the existing One Plane of Action) for the predicted
    subject/predicate and returns the real execution ref, the independently observed
    world value, and the ``Outcome`` (constructed OUTSIDE intelligence, grounded in
    the execution + world observation). The intelligence plane requests it; it never
    executes, and it never mints the Outcome itself."""

    def resolve(self, *, tenant: TenantRef, prediction_ref: str, subject_ref: str,
                predicate: str, expected: Any, now: datetime) -> OutcomeResolution:
        ...


class AssuranceVerificationPort(Protocol):
    """Requests INDEPENDENT verification of the prediction/outcome relationship from
    the Assurance Plane (which re-queries the World itself). ``producer_reasoning_path``
    is the model's path; a verifier sharing it is refused (self-verification)."""

    def verify_prediction(self, *, tenant: TenantRef, subject_ref: str, predicate: str,
                          expected: Any, execution_ref: Optional[str],
                          producer_reasoning_path: str, verified_at: datetime) -> VerificationView:
        ...


@dataclass(frozen=True)
class PredictionLifecycleResult:
    """The end state, keeping THREE distinct judgements separate (Part L):
    diagnostic support (the differential's hypothesis status), prediction support
    (the platform's deterministic evaluation), and independent verification (the
    Assurance verdict). ``calibration`` is the durable, reconstructable evidence
    bundle Phase 8.7 will consume — no calibration score is produced here."""

    investigation: Any
    prediction_ref: str
    hypothesis_ref: str
    execution_ref: Optional[str]
    diagnostic_support: str
    prediction_support: str
    independent_verification: str
    verification_ref: Optional[str]
    evidence_refs: tuple[str, ...]
    calibration: dict
    reason: str = ""


class PredictionPolicy:
    """Validates a proposed prediction deterministically before anything is
    persisted or executed (Part B/D)."""

    def validate(self, *, proposed: ProposedPrediction, investigation) -> ValidatedPrediction:
        if not isinstance(proposed, ProposedPrediction):
            raise PredictionRejected("a ProposedPrediction is required")
        # 1. Tied to a KNOWN hypothesis in the differential.
        known = {h.hypothesis_ref for h in investigation.differential}
        if proposed.hypothesis_ref not in known:
            raise PredictionRejected(
                f"prediction references unknown hypothesis {proposed.hypothesis_ref!r}")
        # 2. Falsifiable: a structured expected observation must exist.
        if proposed.expected is None:
            raise PredictionRejected(
                "a prediction must carry a structured expected observation the "
                "platform can compare against reality; a bare claim is not falsifiable")
        # 3. Safe references — subject/predicate are references, not URLs/shell.
        for name in ("subject_ref", "predicate"):
            v = getattr(proposed, name)
            if not isinstance(v, str) or not v.strip():
                raise PredictionRejected(f"{name} must be a reference string")
            if any(bad in v.lower() for bad in _FORBIDDEN_FRAGMENTS):
                raise PredictionRejected(f"{name} looks like a URL/shell fragment, not a reference")
        # 4. A sane, bounded evaluation window.
        if not isinstance(proposed.evaluation_window_seconds, int) or proposed.evaluation_window_seconds <= 0:
            raise PredictionRejected("evaluation_window_seconds must be a positive integer")
        return ValidatedPrediction(
            hypothesis_ref=proposed.hypothesis_ref, subject_ref=proposed.subject_ref,
            predicate=proposed.predicate, expected=proposed.expected,
            expected_condition=proposed.expected_condition,
            evaluation_window_seconds=proposed.evaluation_window_seconds,
            provider=proposed.provider)


class PredictionLifecycle:
    """Orchestrates the prediction lifecycle over ports. The model proposes; the
    platform governs; execution acts (via a port); the World observes; Assurance
    verifies. The orchestrator never executes, never constructs an Outcome or a
    WorldVerification, and never lets model text become a result."""

    def __init__(
        self, *, service, assembler, proposal_port: PredictionProposalPort,
        outcome_port: GovernedOutcomePort, verifier_port: AssuranceVerificationPort,
        reasoning_ledger, harness_version: str, available_tools: tuple[str, ...] = (),
        producer_reasoning_path: str = "intelligence:investigator/1",
        produced_by: str = "intelligence:prediction/1",
    ) -> None:
        self._svc = service
        self._assembler = assembler
        self._proposal = proposal_port
        self._outcome = outcome_port
        self._verifier = verifier_port
        self._ledger = reasoning_ledger
        self._harness_version = harness_version
        self._tools = tuple(available_tools)
        self._producer_path = producer_reasoning_path
        self._produced_by = produced_by

    def resolve(self, *, investigation, hypothesis_ref: str, now: datetime) -> PredictionLifecycleResult:
        inv = investigation
        hyp = next((h for h in inv.differential if h.hypothesis_ref == hypothesis_ref), None)
        if hyp is None:
            raise PredictionRejected(f"hypothesis {hypothesis_ref!r} is not in the differential")

        # PROPOSE (governed boundary) + VALIDATE (platform).
        context = self._assembler.assemble(
            investigation=inv, world_evidence=(), available_tools=self._tools,
            harness_version=self._harness_version, now=now)
        proposed = self._proposal.propose_prediction(
            context=context, investigation=inv, hypothesis_ref=hypothesis_ref, now=now)
        validated = self._policy.validate(proposed=proposed, investigation=inv)

        # CONSTRUCT the World Prediction (a forward claim — legitimately authored
        # here) and record it durably (cw_reasoning) + link onto the investigation.
        deadline = now + timedelta(seconds=validated.evaluation_window_seconds)
        prediction = Prediction(
            record_id=prefixed_id("wpred"), tenant=inv.tenant, recorded_at=now,
            provenance=ProvenanceRef(produced_by=f"{validated.provider}:model",
                                     parent_claim_ref=hypothesis_ref),
            subject_ref=validated.subject_ref, expected=validated.expected,
            predicted_at=now, deadline=deadline, model_ref=validated.provider,
            predicate=validated.predicate, hypothesis_ref=hypothesis_ref,
            basis=tuple(inv.evidence_refs))
        self._ledger.record_prediction(tenant=inv.tenant, prediction=prediction, recorded_at=now,
                                       harness_version=self._harness_version)
        inv = self._svc.link_prediction(investigation=inv, prediction_ref=prediction.record_id, now=now)

        # GOVERNED ACTION -> OUTCOME (built OUTSIDE intelligence, from execution +
        # independently observed world state; never model text).
        resolution = self._outcome.resolve(
            tenant=inv.tenant, prediction_ref=prediction.record_id, subject_ref=validated.subject_ref,
            predicate=validated.predicate, expected=validated.expected, now=now)
        if not resolution.ok or resolution.outcome is None:
            return self._result(inv, prediction, hyp, execution_ref=resolution.execution_ref,
                                 support=PredictionSupport.INSUFFICIENT_EVIDENCE,
                                 verification=VerificationView(verdict="insufficient_evidence",
                                                               rationale="no governed outcome"),
                                 observed=None, matched=None, within=None, now=now,
                                 reason=resolution.reason or "governed action produced no outcome")
        if resolution.observed_value is None:
            # Silence in the window is INSUFFICIENT_EVIDENCE, never a failure (Part J/K).
            return self._result(inv, prediction, hyp, execution_ref=resolution.execution_ref,
                                 support=PredictionSupport.INSUFFICIENT_EVIDENCE,
                                 verification=VerificationView(verdict="insufficient_evidence",
                                                               rationale="no observation in window"),
                                 observed=None, matched=None, within=None, now=now,
                                 reason="no observation in the evaluation window")

        # EVALUATE deterministically (platform, never the model). The Outcome carries
        # a real execution_ref, so this compares reality, not a claim.
        ev = evaluate_prediction(prediction=prediction, outcome=resolution.outcome, observed_at=now)
        self._ledger.record_evaluation(
            tenant=inv.tenant, subject_ref=validated.subject_ref, evaluation=ev,
            recorded_at=now, predicate=validated.predicate)
        support = self._classify(ev)

        # INDEPENDENT ASSURANCE — the verifier re-queries the World itself and cannot
        # share the model's reasoning path (self-verification is refused).
        verification = self._verifier.verify_prediction(
            tenant=inv.tenant, subject_ref=validated.subject_ref, predicate=validated.predicate,
            expected=validated.expected, execution_ref=resolution.execution_ref,
            producer_reasoning_path=self._producer_path, verified_at=now)
        if verification.verification_ref:
            inv = self._svc.link_verification(
                investigation=inv, verification_ref=verification.verification_ref, now=now)

        return self._result(inv, prediction, hyp, execution_ref=resolution.execution_ref,
                            support=support, verification=verification,
                            observed=resolution.observed_value, matched=ev.matched,
                            within=ev.within_horizon, now=now, reason=ev.reason,
                            evidence_refs=verification.evidence_refs)

    # -- internals ----------------------------------------------------------

    _policy = PredictionPolicy()

    def _classify(self, ev) -> PredictionSupport:
        """Deterministic prediction support from the real outcome. A match within
        the horizon is SUPPORTED; a mismatch is UNSUPPORTED; a late (out-of-horizon)
        outcome is INSUFFICIENT_EVIDENCE — never silently accepted, never FALSE."""
        if not ev.within_horizon:
            return PredictionSupport.INSUFFICIENT_EVIDENCE
        return PredictionSupport.SUPPORTED if ev.matched else PredictionSupport.UNSUPPORTED

    def _result(self, inv, prediction, hyp, *, execution_ref, support, verification,
                observed, matched, within, now, reason="", evidence_refs=()) -> PredictionLifecycleResult:
        calibration = {
            "prediction_ref": prediction.record_id, "predicted_at": prediction.predicted_at.isoformat(),
            "deadline": prediction.deadline.isoformat() if prediction.deadline else None,
            "observed_at": now.isoformat(), "hypothesis_ref": hyp.hypothesis_ref,
            "subject_ref": prediction.subject_ref, "predicate": prediction.predicate,
            "expected": prediction.expected, "observed": observed,
            "matched": matched, "within_horizon": within,
            "diagnostic_support": hyp.status.value, "prediction_support": support.value,
            "independent_verification": verification.verdict, "verification_ref": verification.verification_ref,
            "execution_ref": execution_ref, "evidence_refs": list(evidence_refs),
            "model_ref": prediction.model_ref, "harness_version": self._harness_version,
            "investigation_ref": inv.investigation_ref,
        }
        return PredictionLifecycleResult(
            investigation=inv, prediction_ref=prediction.record_id, hypothesis_ref=hyp.hypothesis_ref,
            execution_ref=execution_ref, diagnostic_support=hyp.status.value,
            prediction_support=support.value, independent_verification=verification.verdict,
            verification_ref=verification.verification_ref, evidence_refs=tuple(evidence_refs),
            calibration=calibration, reason=reason)
