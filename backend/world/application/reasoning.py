"""The durable reasoning trail — the smallest append-only record of the
model-authored reasoning that cannot be reconstructed from the World ledgers.

Only three kinds are persisted (Phase 7.8, Part J/K):
  * a grounded ``Hypothesis`` (model-proposed, evidence-grounded),
  * a ``Prediction`` (forward claim with a horizon), and
  * a ``PredictionEvaluation`` (the calibration payload: expected vs the actual
    outcome of a real execution, with the evidence references).

Beliefs remain derived projections; observations/facts/verifications live in
their own ledgers. Every record is immutable, tenant-scoped, provenance-bearing,
idempotent, and secret-free — the field-aware firewall runs before any row is
written, so no credential material enters the reasoning ledger.

This module imports the epistemic contracts, the platform hashing and secret
detector, and stdlib. It touches no database (composition supplies the
repository), no connector, gateway, credential carrier, or execution plane —
reasoning records never execute.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Protocol

from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantRef
from backend.contracts.world import Hypothesis, Prediction
from backend.platform.credentials.inspection import find_secrets
from backend.platform.hashing import compute_digest
from backend.world.application.hypothesis import PredictionEvaluation

__all__ = [
    "ReasoningKind",
    "ReasoningRejected",
    "ReasoningRecord",
    "ReasoningRepository",
    "ReasoningLedger",
]


class ReasoningKind(str, Enum):
    HYPOTHESIS = "hypothesis"
    PREDICTION = "prediction"
    PREDICTION_EVALUATION = "prediction_evaluation"
    EXPERIENCE_USE = "experience_use"
    DETECTION = "detection"
    """Phase 11.3 (ADR-123): a sustained condition the detector decided is worth
    an investigation -- the platform's judgement about the world, with the
    observations that made it. Not world truth; a reasoning artefact."""
    ASSESSMENT = "assessment"
    """Phase 11.3 (ADR-123): the categorical confidence assessment of a concluded
    investigation -- outcome, confidence, basis, contradictions, unknowns, next
    step, recommendation candidate (authority none). Computed from the
    differential and evidence lineage by stated rules; never a model verdict."""
    """Phase 8.6: a record that a prior investigation EPISODE was retrieved and
    injected into a current investigation's context — the calibration substrate for
    "did historical experience help or mislead?" (Part T). References only; whether
    it helped is computed later (Phase 8.7), never asserted here."""
    REMEDIATION_PLAN = "remediation_plan"
    """Phase 11.4 (ADR-124): one governed remediation plan -- the platform's
    typed, digest-bound action for an incident (target, parameters, risk,
    reversibility class, blast radius, expected state, verification criteria,
    compensation, authority). Built by the platform from a validated proposal
    and fresh evidence; never model text. Immutable: a later stage is a new
    event, never an edit."""
    REMEDIATION_EVENT = "remediation_event"
    """Phase 11.4 (ADR-124): one stage of a remediation's lifecycle (proposal
    decision, autonomy decision, approval, execution, verification, outcome,
    recovery), appended in order. The lifecycle is the fold of these events;
    replay reads them and can change nothing."""


class ReasoningRejected(ContractViolation):
    """A reasoning record was refused (bad tenant, or secret-bearing content)."""


@dataclass(frozen=True)
class ReasoningRecord:
    """A stored reasoning row, as reads return it."""

    reasoning_id: str
    tenant_id: str
    kind: ReasoningKind
    subject_ref: str
    predicate: Optional[str]
    record: dict
    refs: dict
    recorded_at: datetime


class ReasoningRepository(Protocol):
    """The durable, append-only sink. No update, no delete — a reasoning record
    is immutable. Reads are tenant-scoped, fail closed."""

    def record(
        self,
        *,
        reasoning_id: str,
        identity_digest: str,
        tenant_id: str,
        kind: str,
        subject_ref: str,
        predicate: Optional[str],
        record: dict,
        refs: dict,
        recorded_at: datetime,
    ) -> bool:
        """Insert; return True if newly recorded, False if an identical record
        already existed (idempotent dedupe)."""
        ...


def _identity(kind: str, tenant_id: str, subject_ref: str,
              predicate: Optional[str], record: dict) -> str:
    return compute_digest({
        "kind": kind, "tenant": tenant_id, "subject_ref": subject_ref,
        "predicate": predicate or "", "record": record,
    }).value


class ReasoningLedger:
    """Records model-authored reasoning artifacts durably, or refuses.

    Constructed with a repository. Each ``record_*`` firewalls the content for
    secrets, computes a deterministic identity, and appends. The caller supplies
    the knowledge time (``recorded_at``); there is no clock of its own."""

    def __init__(self, *, repository: ReasoningRepository,
                 id_factory=None) -> None:
        self._repository = repository
        # id_factory injected so the harness/tests can make ids deterministic;
        # defaults to the platform generator.
        if id_factory is None:
            from backend.platform.identity.generators import prefixed_id
            id_factory = lambda: prefixed_id("wreason")  # noqa: E731
        self._new_id = id_factory

    def _record(self, *, tenant: TenantRef, kind: ReasoningKind, subject_ref: str,
                predicate: Optional[str], document: dict, refs: dict,
                recorded_at: datetime) -> tuple[str, bool]:
        if not isinstance(tenant, TenantRef):
            raise ReasoningRejected("tenant must be an explicit TenantRef (fail closed)")
        findings = find_secrets(document)
        if findings:
            where = ", ".join(f"{f.path} ({f.why})" for f in findings[:6])
            raise ReasoningRejected(
                f"reasoning record carries secret-shaped material ({where}); the "
                "reasoning ledger stores references and digests, never credentials")
        identity = _identity(kind.value, tenant.tenant_id, subject_ref, predicate, document)
        reasoning_id = self._new_id()
        newly = self._repository.record(
            reasoning_id=reasoning_id, identity_digest=identity,
            tenant_id=tenant.tenant_id, kind=kind.value, subject_ref=subject_ref,
            predicate=predicate, record=document, refs=refs, recorded_at=recorded_at)
        return reasoning_id, newly

    def record_hypothesis(
        self, *, tenant: TenantRef, subject_ref: str, hypothesis: Hypothesis,
        recorded_at: datetime
    ) -> tuple[str, bool]:
        """Record a grounded hypothesis under its *domain* subject (the thing it
        is about). The Hypothesis contract carries no subject_ref, so the caller —
        which knows what the hypothesis explains — supplies it, keeping the
        reasoning trail queryable by the same subject as the observations/facts."""
        if not isinstance(hypothesis, Hypothesis):
            raise ReasoningRejected("record_hypothesis requires a Hypothesis")
        if not isinstance(subject_ref, str) or not subject_ref.strip():
            raise ReasoningRejected("subject_ref is required to record a hypothesis")
        refs = {"support_refs": list(hypothesis.support_refs),
                "contradiction_refs": list(hypothesis.contradiction_refs),
                "investigation_ref": hypothesis.investigation_ref,
                "parent_claim_ref": hypothesis.provenance.parent_claim_ref}
        return self._record(
            tenant=tenant, kind=ReasoningKind.HYPOTHESIS, subject_ref=subject_ref,
            predicate=None, document=hypothesis.to_dict(), refs=refs,
            recorded_at=recorded_at)

    def record_prediction(
        self, *, tenant: TenantRef, prediction: Prediction, recorded_at: datetime,
        harness_version: Optional[str] = None,
    ) -> tuple[str, bool]:
        if not isinstance(prediction, Prediction):
            raise ReasoningRejected("record_prediction requires a Prediction")
        # ``harness_version`` is stamped into the refs (not the record) so calibration
        # (Phase 8.7) can stratify by runtime version without silently merging
        # incompatible versions — the record document and identity are unchanged.
        refs = {"hypothesis_ref": prediction.hypothesis_ref,
                "basis": list(prediction.basis),
                "deadline": prediction.deadline.isoformat() if prediction.deadline else None,
                "harness_version": harness_version}
        return self._record(
            tenant=tenant, kind=ReasoningKind.PREDICTION,
            subject_ref=prediction.subject_ref, predicate=prediction.predicate,
            document=prediction.to_dict(), refs=refs, recorded_at=recorded_at)

    def record_evaluation(
        self, *, tenant: TenantRef, subject_ref: str,
        evaluation: PredictionEvaluation, recorded_at: datetime,
        predicate: Optional[str] = None,
    ) -> tuple[str, bool]:
        if not isinstance(evaluation, PredictionEvaluation):
            raise ReasoningRejected("record_evaluation requires a PredictionEvaluation")
        refs = {"prediction_ref": evaluation.prediction_ref,
                "outcome_ref": evaluation.outcome_ref,
                "execution_ref": evaluation.execution_ref}
        return self._record(
            tenant=tenant, kind=ReasoningKind.PREDICTION_EVALUATION,
            subject_ref=subject_ref, predicate=predicate,
            document=evaluation.to_dict(), refs=refs, recorded_at=recorded_at)

    def record_experience_use(
        self, *, tenant: TenantRef, subject_ref: str, investigation_ref: str,
        episode_ref: str, document: dict, recorded_at: datetime,
        predicate: Optional[str] = None,
    ) -> tuple[str, bool]:
        """Record that historical episode ``episode_ref`` was retrieved into the
        current ``investigation_ref`` (Phase 8.6, Part T). ``document`` is a
        references-only summary (episode ref, match reasons, categorical assurance/
        quality) — the field-aware firewall runs before it is written. This captures
        the calibration substrate; it never asserts the experience was correct."""
        if not isinstance(document, dict):
            raise ReasoningRejected("record_experience_use requires a document dict")
        refs = {"investigation_ref": investigation_ref, "episode_ref": episode_ref}
        return self._record(
            tenant=tenant, kind=ReasoningKind.EXPERIENCE_USE, subject_ref=subject_ref,
            predicate=predicate, document=document, refs=refs, recorded_at=recorded_at)
