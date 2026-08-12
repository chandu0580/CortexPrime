"""Investigation contracts & the state machine — Phase 8.1.

An investigation is a stateful workflow over the World Plane's evidence: it holds
a differential (a set of hypotheses), open questions, referenced evidence, tests,
predictions, and verifications, and it moves through an explicit status machine.
None of it is world truth; all of it is a reasoning/workflow artifact the platform
owns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantRef
from backend.contracts.world import EpistemicStatus, HypothesisStatus, ProvenanceRef

__all__ = [
    "AutonomyLevel",
    "InvestigationStatus",
    "InvestigationConclusion",
    "InvestigationEventKind",
    "TemporalFit",
    "HumanEventKind",
    "DifferentialHypothesis",
    "InvestigationQuestion",
    "InvestigationTest",
    "HumanEvent",
    "Investigation",
    "LEGAL_TRANSITIONS",
    "is_legal_transition",
    "is_terminal_status",
    "legal_transitions_from",
]


def _req_str(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} is required")


def _req_ref_tuple(value: Any, label: str) -> None:
    if not isinstance(value, tuple) or not all(
        isinstance(r, str) and r.strip() for r in value
    ):
        raise ContractViolation(f"{label} must be a tuple of reference strings")


def _req_aware(value: datetime, label: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ContractViolation(f"{label} must be a timezone-aware datetime")


class AutonomyLevel(str, Enum):
    """The autonomy ladder (ADR-071). Set by platform policy, NEVER by the model.

    A model that outputs "I am authorized for A4" has zero authority — autonomy
    is a construction/policy value, and nothing a model produces changes it."""

    A0_OBSERVE = "a0_observe"
    """Ingest signals; take no investigative action."""
    A1_INVESTIGATE = "a1_investigate"
    """Read-only evidence acquisition — the default."""
    A2_RECOMMEND = "a2_recommend"
    """Produce a differential and a proposed action; do not execute."""
    A3_APPROVED_ACTION = "a3_approved_action"
    """Execute a specific action, each human-approved through governance."""
    A4_AUTONOMOUS = "a4_autonomous"
    """Policy-authorized autonomous remediation. Disabled by default."""

    @property
    def rank(self) -> int:
        return {
            AutonomyLevel.A0_OBSERVE: 0, AutonomyLevel.A1_INVESTIGATE: 1,
            AutonomyLevel.A2_RECOMMEND: 2, AutonomyLevel.A3_APPROVED_ACTION: 3,
            AutonomyLevel.A4_AUTONOMOUS: 4,
        }[self]

    def permits_action(self) -> bool:
        """Only A3+ may drive a governed action; A0–A2 are observe/recommend."""
        return self.rank >= AutonomyLevel.A3_APPROVED_ACTION.rank


class InvestigationStatus(str, Enum):
    CREATED = "created"
    INVESTIGATING = "investigating"
    WAITING_FOR_EVIDENCE = "waiting_for_evidence"
    WAITING_FOR_HUMAN = "waiting_for_human"
    READY_FOR_ACTION = "ready_for_action"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


#: The legal transition table. Anything not listed is refused. Terminal states
#: have no outgoing transitions. A crash never fabricates a forward transition —
#: recovery restores the last committed status and only legal moves proceed.
LEGAL_TRANSITIONS: dict[InvestigationStatus, frozenset[InvestigationStatus]] = {
    InvestigationStatus.CREATED: frozenset({
        InvestigationStatus.INVESTIGATING, InvestigationStatus.ABANDONED}),
    InvestigationStatus.INVESTIGATING: frozenset({
        InvestigationStatus.WAITING_FOR_EVIDENCE, InvestigationStatus.WAITING_FOR_HUMAN,
        InvestigationStatus.READY_FOR_ACTION, InvestigationStatus.COMPLETED,
        InvestigationStatus.FAILED, InvestigationStatus.ABANDONED}),
    InvestigationStatus.WAITING_FOR_EVIDENCE: frozenset({
        InvestigationStatus.INVESTIGATING, InvestigationStatus.FAILED,
        InvestigationStatus.ABANDONED}),
    InvestigationStatus.WAITING_FOR_HUMAN: frozenset({
        InvestigationStatus.INVESTIGATING, InvestigationStatus.READY_FOR_ACTION,
        InvestigationStatus.ABANDONED, InvestigationStatus.FAILED}),
    InvestigationStatus.READY_FOR_ACTION: frozenset({
        InvestigationStatus.EXECUTING, InvestigationStatus.WAITING_FOR_HUMAN,
        InvestigationStatus.ABANDONED}),
    InvestigationStatus.EXECUTING: frozenset({
        InvestigationStatus.VERIFYING, InvestigationStatus.FAILED}),
    InvestigationStatus.VERIFYING: frozenset({
        InvestigationStatus.COMPLETED, InvestigationStatus.INVESTIGATING,
        InvestigationStatus.FAILED}),
    InvestigationStatus.COMPLETED: frozenset(),
    InvestigationStatus.FAILED: frozenset(),
    InvestigationStatus.ABANDONED: frozenset(),
}


def is_terminal_status(status: InvestigationStatus) -> bool:
    return not LEGAL_TRANSITIONS[status]


def legal_transitions_from(status: InvestigationStatus) -> frozenset[InvestigationStatus]:
    return LEGAL_TRANSITIONS[status]


def is_legal_transition(src: InvestigationStatus, dst: InvestigationStatus) -> bool:
    return dst in LEGAL_TRANSITIONS[src]


class InvestigationConclusion(str, Enum):
    """The epistemic outcome an investigation reaches when it terminates — a
    separate axis from the workflow ``InvestigationStatus``. Completion requires
    platform evidence; a model can never declare one. UNKNOWN-shaped outcomes
    (INSUFFICIENT_EVIDENCE / CONFLICTED) are never RESOLVED and never FALSE."""

    RESOLVED = "resolved"
    """A hypothesis is affirmed on admissible, verified evidence."""
    UNRESOLVED = "unresolved"
    """Investigated, no hypothesis affirmed; not a failure of the system."""
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    """Not enough admissible evidence to adjudicate — 'we don't know'."""
    CONFLICTED = "conflicted"
    """Competing evidence, unresolved by authority — both paths preserved."""
    ESCALATED = "escalated"
    """Handed to a human for adjudication."""
    BLOCKED = "blocked"
    """A required governed read/action was refused or unavailable."""
    FAILED = "failed"
    """A structural failure (e.g. evidence retrieval failed)."""


class InvestigationEventKind(str, Enum):
    CREATED = "created"
    TRANSITIONED = "transitioned"
    QUESTION_ADDED = "question_added"
    HYPOTHESIS_UPSERTED = "hypothesis_upserted"
    EVIDENCE_LINKED = "evidence_linked"
    TEST_ADDED = "test_added"
    PREDICTION_LINKED = "prediction_linked"
    VERIFICATION_LINKED = "verification_linked"
    HUMAN_EVENT = "human_event"
    CHECKPOINT = "checkpoint"


class TemporalFit(str, Enum):
    """Whether a hypothesis is temporally consistent with the incident — an
    honest three-state, never a probability."""

    CONSISTENT = "consistent"
    INCONSISTENT = "inconsistent"
    UNKNOWN = "unknown"


class HumanEventKind(str, Enum):
    APPROVAL_REQUESTED = "approval_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLARIFICATION_REQUESTED = "clarification_requested"
    EVIDENCE_ADJUDICATED = "evidence_adjudicated"
    HYPOTHESIS_CONFIRMED = "hypothesis_confirmed"
    INVESTIGATION_STOPPED = "investigation_stopped"


@dataclass(frozen=True)
class DifferentialHypothesis(Contract):
    """One candidate in the differential. Evidence is referenced; the status is
    an epistemic state; there is NO numeric confidence."""

    CONTRACT_NAME = "cortexprime.intelligence.differential_hypothesis"

    hypothesis_ref: str
    subject_ref: str
    proposition: str
    status: HypothesisStatus
    temporal_fit: TemporalFit
    created_by: str                       # producer label, not authority
    evidence_for: tuple[str, ...] = ()
    evidence_against: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    contradiction_refs: tuple[str, ...] = ()
    lineage_origins: tuple[str, ...] = ()   # known lineage origins of its evidence
    authority: Optional[str] = None         # KnowledgeAuthority tier value, if known

    def __post_init__(self) -> None:
        for name in ("hypothesis_ref", "subject_ref", "proposition", "created_by"):
            _req_str(getattr(self, name), name)
        if not isinstance(self.status, HypothesisStatus):
            raise ContractViolation("status must be a HypothesisStatus (no numeric confidence)")
        if not isinstance(self.temporal_fit, TemporalFit):
            raise ContractViolation("temporal_fit must be a TemporalFit")
        for name in ("evidence_for", "evidence_against", "missing_evidence",
                     "contradiction_refs", "lineage_origins"):
            _req_ref_tuple(getattr(self, name), name)


@dataclass(frozen=True)
class InvestigationQuestion(Contract):
    """A unit of uncertainty the investigation is trying to reduce. A model may
    propose it; the platform validates and records it. Not world truth."""

    CONTRACT_NAME = "cortexprime.intelligence.investigation_question"

    question_ref: str
    investigation_ref: str
    tenant: TenantRef
    purpose: str
    created_by: str
    provenance: ProvenanceRef
    evidence_required: tuple[str, ...] = ()
    hypothesis_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("question_ref", "investigation_ref", "purpose", "created_by"):
            _req_str(getattr(self, name), name)
        if not isinstance(self.tenant, TenantRef):
            raise ContractViolation("tenant must be a TenantRef")
        if not isinstance(self.provenance, ProvenanceRef):
            raise ContractViolation("provenance must be a ProvenanceRef")
        for name in ("evidence_required", "hypothesis_refs"):
            _req_ref_tuple(getattr(self, name), name)


@dataclass(frozen=True)
class InvestigationTest(Contract):
    """A test with a falsifiable purpose: it discriminates a hypothesis and names
    what would support vs contradict it, and the residual uncertainty if it
    fails. The model may propose it; the platform maps it to a governed READ
    capability — the model supplies no URL/shell/provider/connector/credential."""

    CONTRACT_NAME = "cortexprime.intelligence.investigation_test"

    test_ref: str
    investigation_ref: str
    tenant: TenantRef
    discriminates_hypothesis: str
    evidence_expected: str
    supports_if: str
    contradicts_if: str
    residual_uncertainty: str
    created_by: str
    provenance: ProvenanceRef
    prediction_ref: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("test_ref", "investigation_ref", "discriminates_hypothesis",
                     "evidence_expected", "supports_if", "contradicts_if",
                     "residual_uncertainty", "created_by"):
            _req_str(getattr(self, name), name)
        if not isinstance(self.tenant, TenantRef):
            raise ContractViolation("tenant must be a TenantRef")
        if not isinstance(self.provenance, ProvenanceRef):
            raise ContractViolation("provenance must be a ProvenanceRef")
        if self.prediction_ref is not None:
            _req_str(self.prediction_ref, "prediction_ref")


@dataclass(frozen=True)
class HumanEvent(Contract):
    """An explicit human intervention. The actor is a governance/approval identity
    reference (never a free-text name), so authority is auditable, not asserted."""

    CONTRACT_NAME = "cortexprime.intelligence.human_event"

    kind: HumanEventKind
    actor_ref: str          # a governance principal / approval identity reference
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, HumanEventKind):
            raise ContractViolation("kind must be a HumanEventKind")
        _req_str(self.actor_ref, "actor_ref")
        _req_str(self.reason, "reason")
        # A free-text personal name is not an authority. Require a namespaced ref.
        if ":" not in self.actor_ref:
            raise ContractViolation(
                "actor_ref must be a namespaced identity reference (e.g. "
                "'approval:<id>' or 'principal:<id>'), never a bare name")


@dataclass(frozen=True)
class Investigation(Contract):
    """The folded investigation aggregate — a snapshot of the workflow state.

    It references World evidence (never duplicates it), owns the differential, and
    carries the autonomy level (platform-set) and the seq (monotonic version). The
    durable ledger stores one immutable snapshot per event; the latest committed
    snapshot is the authoritative current state (crash recovery restores it, never
    fabricates progress)."""

    CONTRACT_NAME = "cortexprime.intelligence.investigation"

    investigation_ref: str
    tenant: TenantRef
    incident_ref: str
    status: InvestigationStatus
    autonomy_level: AutonomyLevel
    seq: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceRef
    policy_ref: str
    harness_version: str
    current_question_ref: Optional[str] = None
    differential: tuple[DifferentialHypothesis, ...] = ()
    question_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    test_refs: tuple[str, ...] = ()
    prediction_refs: tuple[str, ...] = ()
    verification_refs: tuple[str, ...] = ()
    # Phase 8.2 (additive): the epistemic conclusion (set only at terminal
    # COMPLETED/FAILED via the platform), and durable budget counters so budgets
    # survive resume (a model can neither set the conclusion nor reset counters).
    conclusion: Optional[InvestigationConclusion] = None
    steps_taken: int = 0
    reads_taken: int = 0

    def __post_init__(self) -> None:
        for name in ("investigation_ref", "incident_ref", "policy_ref", "harness_version"):
            _req_str(getattr(self, name), name)
        if self.conclusion is not None and not isinstance(self.conclusion, InvestigationConclusion):
            raise ContractViolation("conclusion must be an InvestigationConclusion")
        for name in ("steps_taken", "reads_taken"):
            v = getattr(self, name)
            if not isinstance(v, int) or v < 0:
                raise ContractViolation(f"{name} must be a non-negative integer")
        if not isinstance(self.tenant, TenantRef):
            raise ContractViolation("tenant must be a TenantRef; scope is never inferred")
        if not isinstance(self.status, InvestigationStatus):
            raise ContractViolation("status must be an InvestigationStatus")
        if not isinstance(self.autonomy_level, AutonomyLevel):
            raise ContractViolation("autonomy_level must be an AutonomyLevel")
        if not isinstance(self.seq, int) or self.seq < 0:
            raise ContractViolation("seq must be a non-negative integer")
        _req_aware(self.created_at, "created_at")
        _req_aware(self.updated_at, "updated_at")
        if not isinstance(self.provenance, ProvenanceRef):
            raise ContractViolation("provenance must be a ProvenanceRef")
        if not isinstance(self.differential, tuple) or not all(
            isinstance(h, DifferentialHypothesis) for h in self.differential
        ):
            raise ContractViolation("differential must be a tuple of DifferentialHypothesis")
        for name in ("question_refs", "evidence_refs", "test_refs",
                     "prediction_refs", "verification_refs"):
            _req_ref_tuple(getattr(self, name), name)

    @property
    def is_terminal(self) -> bool:
        return is_terminal_status(self.status)
