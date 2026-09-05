"""Explicit response schemas for the product API.

Every field here is named. Nothing passes through as ``dict[str, Any]``, because
a pass-through of internal domain state is how a secret, a raw database row or an
internal identifier reaches a client without anybody deciding that it should.

The rule these schemas exist to protect
---------------------------------------
The engine distinguishes ``SUPPORTED`` / ``UNSUPPORTED`` /
``INSUFFICIENT_EVIDENCE``, and ``UNKNOWN`` / ``STALE`` / ``CONFLICTED``. Those are
not shades of failure -- they are different answers, and Phase 7-9 spent
considerable effort making sure they never collapse into each other.

So they are carried as **their own string values**. They are never mapped onto
``success``/``failure``, never coerced to a boolean, and **no confidence number is
synthesised**: there is no confidence value in the domain to carry, and inventing
one here would put a number in front of a user that nothing computed.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

__all__ = [
    "ErrorResponse",
    "EvidenceRef",
    "HypothesisView",
    "InvestigationDetail",
    "InvestigationSummary",
    "InvestigationList",
    "VerificationView",
    "WorldStateView",
]


class ErrorResponse(BaseModel):
    """A deterministic error. Carries a stable code and a safe message.

    No internal exception text, no stack trace, no query. The ``code`` is what a
    client branches on; ``message`` is for a human and is written here rather
    than taken from an exception.
    """

    code: str = Field(description="Stable machine-readable refusal code")
    message: str = Field(description="Safe human-readable explanation")


class HypothesisView(BaseModel):
    """One candidate explanation, with its standing left intact."""

    hypothesis_id: str
    statement: str
    status: str = Field(
        description="OPEN / SUPPORTED / ELIMINATED as the engine recorded it. "
                    "ELIMINATED is not 'false' about the world; it is 'ruled out "
                    "by this investigation's evidence'.")
    temporal_fit: Optional[str] = Field(
        default=None,
        description="Whether the hypothesis fits the incident's timing. UNKNOWN "
                    "is a real value and is not absence.")
    evidence_refs: tuple[str, ...] = ()


class EvidenceRef(BaseModel):
    """A pointer to World evidence, never the evidence's raw record."""

    observation_id: str
    subject_ref: str
    predicate: str
    source_ref: Optional[str] = Field(
        default=None, description="Which instrument observed it, for lineage")
    observed_at: Optional[str] = None
    retrieved_at: Optional[str] = None


class InvestigationSummary(BaseModel):
    investigation_ref: str
    status: str
    subject_ref: Optional[str] = None
    opened_at: Optional[str] = None
    concluded_at: Optional[str] = None
    diagnosis: Optional[str] = None


class InvestigationList(BaseModel):
    """A bounded page. ``limit`` is echoed so a client can see what was applied
    rather than assume its request was honoured."""

    items: tuple[InvestigationSummary, ...]
    count: int
    limit: int
    note: str = Field(
        default="Completed investigations only. The engine exposes no "
                "tenant-scoped listing of in-progress investigations, and this "
                "API does not invent one.")


class InvestigationDetail(BaseModel):
    investigation_ref: str
    status: str
    subject_ref: Optional[str] = None
    opened_at: Optional[str] = None
    concluded_at: Optional[str] = None
    diagnosis: Optional[str] = None
    hypotheses: tuple[HypothesisView, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    residual_uncertainty: tuple[str, ...] = Field(
        default=(),
        description="What remains unexplained. Present even on a concluded "
                    "investigation, because concluding is not knowing "
                    "everything.")
    conclusion_kind: Optional[str] = None


class WorldStateView(BaseModel):
    """What the World Plane represents, with its epistemic standing intact."""

    subject_ref: str
    predicate: str
    epistemic_status: str = Field(
        description="KNOWN / UNKNOWN / STALE / CONFLICTED. UNKNOWN is not false, "
                    "STALE is not false, and CONFLICTED is not false -- each is a "
                    "distinct answer and none may be rendered as absence.")
    value: Optional[str] = Field(
        default=None,
        description="The effective value, rendered as text. Null when the status "
                    "is one where no single value is established.")
    observed_at: Optional[str] = None
    evidence: tuple[EvidenceRef, ...] = ()
    evidence_count: int = 0


class VerificationView(BaseModel):
    """An Assurance verdict, as Assurance recorded it."""

    verification_id: str
    verdict: str = Field(
        description="SUPPORTED / UNSUPPORTED / INSUFFICIENT_EVIDENCE. The third "
                    "is not a failure: it means the evidence did not settle the "
                    "question, which is a different thing from settling it "
                    "negatively.")
    subject_ref: str
    predicate: str
    rationale: Optional[str] = None
    verified_at: Optional[str] = None
    evidence_refs: tuple[str, ...] = Field(
        default=(),
        description="A SUPPORTED verdict must cite evidence; the verifier "
                    "downgrades to INSUFFICIENT_EVIDENCE when it cannot.")
