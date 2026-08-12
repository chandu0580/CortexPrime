"""Hypothesis formation & prediction evaluation — the reasoning-contract boundary.

Phase 7.6 is a contract phase (no execution). This module owns two deterministic
boundaries the Intelligence Plane will build on:

  * ``HypothesisFormation`` — a model *proposes* a hypothesis
    (``ModelHypothesisProposal``); the platform grounds it in REAL evidence
    (beliefs/facts/observations for and against) to construct a ``Hypothesis``
    (status OPEN, never VERIFIED). A proposal with no real subject/evidence is
    refused. The model suggests; the platform decides validity.

  * ``evaluate_prediction`` — a deterministic comparison of a ``Prediction``
    against a real ``Outcome`` (whose ``execution_ref`` ties it to a governed
    execution). It computes match/mismatch as the input a *future* calibration
    phase will consume. It is NOT a learning engine: no retraining, no reward,
    no policy mutation, no invented numbers.

No connector, gateway, transport, credential, scheduler, or execution is
imported. A hypothesis never executes; a prediction never counts as evidence it
came true; an outcome is never self-authored by a model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantRef
from backend.contracts.world import (
    Hypothesis,
    HypothesisStatus,
    ModelHypothesisProposal,
    Outcome,
    Prediction,
    ProvenanceRef,
)
from backend.platform.hashing import compute_digest
from backend.platform.identity.generators import prefixed_id

__all__ = [
    "HypothesisRejected",
    "HypothesisEvidence",
    "HypothesisFormation",
    "PredictionEvaluation",
    "evaluate_prediction",
]


class HypothesisRejected(ContractViolation):
    """A model hypothesis proposal could not be grounded into a hypothesis."""


@dataclass(frozen=True)
class HypothesisEvidence:
    """The structured evidence a hypothesis is grounded in — references only,
    split into support and contradiction, plus an optional falsifier and
    investigation step."""

    support_refs: tuple[str, ...] = ()
    contradiction_refs: tuple[str, ...] = ()
    falsifier: Optional[str] = None
    investigation_ref: Optional[str] = None


class HypothesisFormation:
    """Grounds a model's hypothesis proposal in real evidence (Part G/H).

    Deterministic and evidence-gated: the proposal supplies the claim; the caller
    supplies structured evidence references gathered from the World Plane. The
    result is a ``Hypothesis`` with status OPEN — a candidate explanation that can
    be tested, never a verified one. There is no path from a bare proposal (no
    evidence) to a hypothesis."""

    def __init__(self, *, produced_by: str = "hypothesis:world/1") -> None:
        self._produced_by = produced_by

    def ground(
        self,
        *,
        tenant: TenantRef,
        proposal: ModelHypothesisProposal,
        recorded_at: datetime,
        evidence: HypothesisEvidence,
    ) -> Hypothesis:
        """Construct a grounded OPEN hypothesis from a proposal + real evidence.

        Refuses a proposal with no subject or no supporting evidence — a model
        cannot conjure a hypothesis about nothing, and an ungrounded claim is a
        ``ModelProposal``, not a testable hypothesis."""
        if not isinstance(tenant, TenantRef):
            raise HypothesisRejected("tenant must be an explicit TenantRef")
        if not isinstance(proposal, ModelHypothesisProposal):
            raise HypothesisRejected(
                "a hypothesis is grounded only from a ModelHypothesisProposal")
        if not proposal.subject_ref:
            raise HypothesisRejected(
                "the proposal names no subject; a hypothesis must be about "
                "something the platform can find evidence for")
        if not evidence.support_refs and not evidence.contradiction_refs:
            raise HypothesisRejected(
                "no real evidence references were supplied; a bare model claim is "
                "a ModelProposal, not a grounded hypothesis")

        provenance = ProvenanceRef(
            produced_by=self._produced_by,
            parent_claim_ref=proposal.record_id,
            observation_ref=evidence.support_refs[0] if evidence.support_refs else None,
        )
        return Hypothesis(
            record_id=prefixed_id("whyp"), tenant=tenant, recorded_at=recorded_at,
            provenance=provenance,
            claim=proposal.claim, origin=proposal.proposed_by,
            status=HypothesisStatus.OPEN,   # never VERIFIED (that is the Assurance Plane)
            support_refs=evidence.support_refs,
            contradiction_refs=evidence.contradiction_refs,
            falsifier=evidence.falsifier,
            investigation_ref=evidence.investigation_ref or proposal.suggested_investigation)


@dataclass(frozen=True)
class PredictionEvaluation:
    """The deterministic comparison of a prediction against a real outcome — the
    input a future calibration phase consumes. No numbers are invented here."""

    prediction_ref: str
    outcome_ref: str
    execution_ref: str
    expected: Any
    observed: Any
    matched: bool
    within_horizon: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "prediction_ref": self.prediction_ref, "outcome_ref": self.outcome_ref,
            "execution_ref": self.execution_ref, "expected": self.expected,
            "observed": self.observed, "matched": self.matched,
            "within_horizon": self.within_horizon, "reason": self.reason,
        }


def evaluate_prediction(
    *, prediction: Prediction, outcome: Outcome, observed_at: datetime,
) -> PredictionEvaluation:
    """Compare a prediction against a real outcome, deterministically.

    ``outcome`` carries a real ``execution_ref`` (the contract enforces it), so a
    model cannot self-author the result being compared. Matching is exact value
    equality by canonical digest — no invented probability, no learning. The
    horizon check uses the prediction's ``deadline`` and the outcome's observed
    time; a late outcome is reported, never silently accepted."""
    if not isinstance(prediction, Prediction) or not isinstance(outcome, Outcome):
        raise ContractViolation("evaluate_prediction needs a Prediction and an Outcome")
    if outcome.tenant.tenant_id != prediction.tenant.tenant_id:
        raise ContractViolation("prediction and outcome belong to different tenants")

    matched = compute_digest(prediction.expected).value == compute_digest(outcome.observed).value
    within_horizon = prediction.deadline is None or observed_at <= prediction.deadline
    reason = (f"expected {'==' if matched else '!='} observed; "
              f"outcome {'within' if within_horizon else 'AFTER'} the prediction horizon")
    return PredictionEvaluation(
        prediction_ref=prediction.record_id, outcome_ref=outcome.record_id,
        execution_ref=outcome.execution_ref, expected=prediction.expected,
        observed=outcome.observed, matched=matched, within_horizon=within_horizon,
        reason=reason)
