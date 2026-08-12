"""World Plane epistemic types — Phase 7.1 (Parts B–J, N, P, Q, R).

Seven record types over one immutable spine, plus the model-output firewall.
Contracts only — no persistence, no execution, no I/O.

The spine (:class:`EpistemicRecord`) carries the truly universal fields:
identity, tenant, recording time, provenance. Each type adds only what it
needs, and the type barriers make the five non-collapses structural:

    Observation  →  (ingestion, later)  →  Fact          # not the same type
    Fact         ≠  Belief                                # different types
    Hypothesis   ≠  Belief / Fact                         # different types
    Prediction   ≠  Outcome                               # different types
    ModelProposal / model verdict  ≠  Fact / Verification # different types

There is no method anywhere that turns a ``ModelProposal`` or a ``Hypothesis``
into a ``Fact``, and an ``Observation`` cannot be attributed to a model (its
source kind has no MODEL member). That is the ingestion boundary at the type
level (Part Q): model output becomes a proposal or a hypothesis, and only an
instrument observation can ground a fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.evidence import SourceStatus  # salvaged (7.0 verdict: KEEP)
from backend.contracts.knowledge import KnowledgeAuthority  # salvaged (EXTEND)
from backend.contracts.tenant import TenantRef
from backend.contracts.verification import Verdict, VerifierIdentity
from backend.contracts.world.confidence import ClaimConfidence
from backend.contracts.world.provenance import ProvenanceRef
from backend.contracts.world.temporal import ObservationInstant, ValidityInterval

__all__ = [
    "EpistemicRecord",
    "EpistemicStatus",
    "ObservationSourceKind",
    "ObservationSource",
    "Observation",
    "Fact",
    "Belief",
    "HypothesisStatus",
    "Hypothesis",
    "Prediction",
    "Outcome",
    "WorldVerification",
    "ModelProposal",
]


def _require_aware(value: datetime, label: str) -> None:
    if not isinstance(value, datetime):
        raise ContractViolation(f"{label} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ContractViolation(f"{label} must be timezone-aware")


# ----------------------------------------------------------------------
# The immutable spine (Part J)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class EpistemicRecord(Contract):
    """The universal fields every World Plane record carries. Intermediate base
    (no ``CONTRACT_NAME`` — not registered, not decodable on its own).

    Only truly universal fields live here: a record identity, an explicit
    tenant (Part M — scope is visible on the contract, never inferred from
    request context), the recording/transaction time, and a provenance
    reference (Part L). Everything else is the concern of the specific type.
    """

    record_id: str
    tenant: TenantRef
    recorded_at: datetime
    provenance: ProvenanceRef

    def __post_init__(self) -> None:
        if not isinstance(self.record_id, str) or not self.record_id.strip():
            raise ContractViolation("record_id is required")
        if not isinstance(self.tenant, TenantRef):
            raise ContractViolation(
                "tenant must be an explicit TenantRef; World Plane scope is "
                "never inferred from ambient context (Part M, fail closed)"
            )
        _require_aware(self.recorded_at, "recorded_at")
        if not isinstance(self.provenance, ProvenanceRef):
            raise ContractViolation("provenance must be a ProvenanceRef")


class EpistemicStatus(str, Enum):
    """The epistemic state of a claim (Part P) — never collapsed into FALSE.

    These are first-class, valuable answers. ``CONFLICTED`` and ``UNKNOWN`` are
    not failures of the system; representing them honestly is the system
    working. Contradiction/freshness *engines* are later phases; the states are
    the vocabulary they will set.
    """

    AFFIRMED = "affirmed"
    """Currently held as true, on admissible grounding."""

    STALE = "stale"
    """Was true; its freshness window has lapsed and it needs re-observation.
    STALE ≠ FALSE — a stale claim is not automatically wrong, it is
    inadmissible for a consequential action until refreshed."""

    CONFLICTED = "conflicted"
    """Competing claims exist and have not been resolved. Not a coin flip — the
    conflict is represented, not silently decided."""

    UNKNOWN = "unknown"
    """No admissible grounding exists. 'I don't know', stated plainly."""

    RETRACTED = "retracted"
    """Superseded by a later claim version. Retained for history, never served
    as current (revision storage is a later phase; this is the marker)."""


# ----------------------------------------------------------------------
# Observation (Part C) — raw evidence, never a fact, never from a model
# ----------------------------------------------------------------------


class ObservationSourceKind(str, Enum):
    """What kind of instrument produced an observation.

    There is deliberately **no MODEL member.** An observation can be attributed
    only to an instrument that read the world — a connector, a probe, an
    execution outcome, a human report. Model output cannot be an observation,
    which is the first half of 'model output cannot become a fact' (Part Q).
    """

    CONNECTOR = "connector"
    """A governed connector read (e.g. Grafana query, kubectl get)."""

    PROBE = "probe"
    """An active probe/measurement (e.g. a health check, a canary)."""

    EXECUTION = "execution"
    """An execution outcome observed by the platform's own machinery."""

    HUMAN = "human"
    """A human operator's direct report."""


@dataclass(frozen=True)
class ObservationSource(Contract):
    """Who observed, and how. Names an instrument, never a model (Part C, Q)."""

    CONTRACT_NAME = "cortexprime.world.observation_source"

    kind: ObservationSourceKind
    source_ref: str  # e.g. "connector:grafana", "probe:http-health/1"

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ObservationSourceKind):
            raise ContractViolation(
                "kind must be an ObservationSourceKind; there is no MODEL kind — "
                "model output cannot be an observation"
            )
        if not isinstance(self.source_ref, str) or not self.source_ref.strip():
            raise ContractViolation("source_ref must name the instrument")


@dataclass(frozen=True)
class Observation(EpistemicRecord):
    """Raw evidence of something observed (Part C). Immutable.

    An observation is a subject–predicate–value triple as an instrument
    reported it, with its two times kept distinct (``instant``) and its source
    status honest (``status``: RETURNED_DATA / RETURNED_EMPTY / UNAVAILABLE /
    NOT_CONFIGURED — salvaged from ``contracts.evidence``, so empty ≠
    unavailable ≠ not-configured). An observation is NOT a fact: it has no
    valid-time interval and no authority. Only the (future) deterministic
    ingestion boundary derives facts from observations.
    """

    CONTRACT_NAME = "cortexprime.world.observation"

    source: ObservationSource
    subject_ref: str
    predicate: str
    value: Optional[Any]
    status: SourceStatus
    instant: ObservationInstant

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.source, ObservationSource):
            raise ContractViolation("source must be an ObservationSource")
        for name in ("subject_ref", "predicate"):
            v = getattr(self, name)
            if not isinstance(v, str) or not v.strip():
                raise ContractViolation(f"{name} is required on an observation")
        if not isinstance(self.status, SourceStatus):
            raise ContractViolation("status must be a SourceStatus")
        if not isinstance(self.instant, ObservationInstant):
            raise ContractViolation("instant must be an ObservationInstant")
        # An informative status must carry a value; a non-informative one must
        # not pretend to (empty/unavailable/not-configured describe absence).
        if self.status.is_informative and self.status is SourceStatus.RETURNED_DATA:
            if self.value is None:
                raise ContractViolation(
                    "RETURNED_DATA must carry a value; use RETURNED_EMPTY for a "
                    "successful query that genuinely found nothing"
                )
        if not self.status.is_informative and self.value is not None:
            raise ContractViolation(
                f"{self.status.value} is an absence and must carry no value; "
                "recording a value under it is how absence becomes a false claim"
            )


# ----------------------------------------------------------------------
# Fact (Part D) — normalized world claim grounded in observations
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Fact(EpistemicRecord):
    """A normalized world claim whose provenance points back to observation(s)
    (Part D). Immutable claim version.

    A Fact can be constructed only with observation grounding: its provenance
    must name an observation anchor. There is no constructor from arbitrary
    text, and the model's types (``ModelProposal``, ``Hypothesis``) do not
    convert to ``Fact`` — so 'model output cannot become a fact' holds both by
    the missing conversion and by this grounding requirement. Use
    :meth:`from_observations` to derive one from real ``Observation`` objects.

    A Fact carries valid-time (``validity``), an authority axis (salvaged
    ``KnowledgeAuthority``), and an ``EpistemicStatus`` — so a fact may be
    AFFIRMED, STALE, CONFLICTED or RETRACTED without becoming FALSE.
    """

    CONTRACT_NAME = "cortexprime.world.fact"

    subject_ref: str
    predicate: str
    value: Any
    validity: ValidityInterval
    authority: KnowledgeAuthority
    status: EpistemicStatus

    def __post_init__(self) -> None:
        super().__post_init__()
        for name in ("subject_ref", "predicate"):
            v = getattr(self, name)
            if not isinstance(v, str) or not v.strip():
                raise ContractViolation(f"{name} is required on a fact")
        if not isinstance(self.validity, ValidityInterval):
            raise ContractViolation("validity must be a ValidityInterval")
        if not isinstance(self.authority, KnowledgeAuthority):
            raise ContractViolation("authority must be a KnowledgeAuthority")
        if not isinstance(self.status, EpistemicStatus):
            raise ContractViolation("status must be an EpistemicStatus")
        # The grounding rule: a fact must be grounded in an observation. Model
        # text has no observation anchor, so this refuses a fabricated fact.
        if self.provenance.observation_ref is None and not self.provenance.grounds_a_claim:
            raise ContractViolation(
                "a fact must be grounded: its provenance must name an "
                "observation (or another anchor). A claim with no observational "
                "grounding is not a fact — it is a belief or a hypothesis"
            )

    @classmethod
    def from_observations(
        cls,
        *,
        record_id: str,
        tenant: TenantRef,
        recorded_at: datetime,
        observations: tuple[Observation, ...],
        subject_ref: str,
        predicate: str,
        value: Any,
        validity: ValidityInterval,
        authority: KnowledgeAuthority = KnowledgeAuthority.ADVISORY,
        status: EpistemicStatus = EpistemicStatus.AFFIRMED,
        produced_by: str,
    ) -> "Fact":
        """Derive a fact from real observations (the sanctioned constructor).

        Requires a non-empty tuple of ``Observation`` objects — not strings,
        not model output. The provenance is built to name the first
        observation, so the grounding invariant is satisfied by construction.
        """
        if not observations or not all(isinstance(o, Observation) for o in observations):
            raise ContractViolation(
                "a fact must be derived from at least one Observation object; "
                "arbitrary text cannot ground a fact (Part D, Part Q)"
            )
        provenance = ProvenanceRef(
            produced_by=produced_by,
            observation_ref=observations[0].record_id,
        )
        return cls(
            record_id=record_id,
            tenant=tenant,
            recorded_at=recorded_at,
            provenance=provenance,
            subject_ref=subject_ref,
            predicate=predicate,
            value=value,
            validity=validity,
            authority=authority,
            status=status,
        )


# ----------------------------------------------------------------------
# Belief (Part E) — CortexPrime's current position, distinct from Fact
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Belief(EpistemicRecord):
    """CortexPrime's current epistemic position about a claim (Part E).
    Append-only revision (semantics only; storage is a later phase).

    A Belief is a different type from a Fact and never converts to one. Where a
    Fact says "the instrument reported X", a Belief says "CortexPrime currently
    holds X", carrying a ``ClaimConfidence`` (UNCALIBRATED by default) and a
    ``basis`` of the references it rests on. A Fact does not auto-become a
    Belief: you construct a Belief explicitly, citing its basis — so
    'Fact → Belief' never becomes implicit truth.
    """

    CONTRACT_NAME = "cortexprime.world.belief"

    subject_ref: str
    predicate: str
    value: Any
    confidence: ClaimConfidence
    status: EpistemicStatus
    basis: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        for name in ("subject_ref", "predicate"):
            v = getattr(self, name)
            if not isinstance(v, str) or not v.strip():
                raise ContractViolation(f"{name} is required on a belief")
        if not isinstance(self.confidence, ClaimConfidence):
            raise ContractViolation("confidence must be a ClaimConfidence")
        if not isinstance(self.status, EpistemicStatus):
            raise ContractViolation("status must be an EpistemicStatus")
        if not isinstance(self.basis, tuple) or not all(
            isinstance(b, str) and b.strip() for b in self.basis
        ):
            raise ContractViolation("basis must be a tuple of reference strings")
        # A belief must rest on *something* — an observation, a fact, or a
        # hypothesis — named in provenance or basis. A belief from nowhere is a
        # guess wearing a belief's clothes.
        if not self.provenance.grounds_a_claim and not self.basis:
            raise ContractViolation(
                "a belief must cite a basis (observation/fact/hypothesis refs) "
                "or carry grounding provenance"
            )


# ----------------------------------------------------------------------
# Hypothesis (Part F) — unresolved explanatory claim (may be model-proposed)
# ----------------------------------------------------------------------


class HypothesisStatus(str, Enum):
    """A hypothesis lifecycle status. VERIFIED is deliberately absent —
    verification belongs to the Assurance Plane, not here (Part F)."""

    OPEN = "open"
    SUPPORTED = "supported"
    """Discriminating evidence supports it — but 'supported' is NOT 'verified'
    and NOT a fact."""
    REFUTED = "refuted"
    UNRESOLVED = "unresolved"
    """Investigated, could not be settled either way (distinct from OPEN, which
    has not been investigated)."""


@dataclass(frozen=True)
class Hypothesis(EpistemicRecord):
    """An unresolved explanatory claim (Part F). Append-only state transitions.

    This is where a model's explanatory text legitimately lives — clearly typed
    as a hypothesis, never a fact. ``origin`` names who proposed it (which may
    be a model). A hypothesis is not a Fact, not a Belief, not a Verification,
    and none of its statuses is VERIFIED. Promotion to belief/fact is a later
    phase and requires the named discriminating evidence to resolve — it never
    happens on the strength of the hypothesis's own supporting refs.
    """

    CONTRACT_NAME = "cortexprime.world.hypothesis"

    claim: str
    origin: str
    status: HypothesisStatus
    support_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.claim, str) or not self.claim.strip():
            raise ContractViolation("claim is required on a hypothesis")
        if not isinstance(self.origin, str) or not self.origin.strip():
            raise ContractViolation("origin must name who proposed the hypothesis")
        if not isinstance(self.status, HypothesisStatus):
            raise ContractViolation("status must be a HypothesisStatus")
        if not isinstance(self.support_refs, tuple) or not all(
            isinstance(r, str) and r.strip() for r in self.support_refs
        ):
            raise ContractViolation("support_refs must be a tuple of reference strings")


# ----------------------------------------------------------------------
# Prediction (Part G) and Outcome (Part H) — never collapsed
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Prediction(EpistemicRecord):
    """A falsifiable statement about a future observation (Part G). Immutable.

    Carries what is expected and when the prediction was made; a model/harness
    reference when it was model-produced. A Prediction is NOT evidence the
    outcome occurred — it is a separate type from ``Outcome`` and never becomes
    one. It is resolved by comparing against a later ``Outcome``, and the diff
    is the prediction error (a later phase; the separation is what 7.1 fixes).
    """

    CONTRACT_NAME = "cortexprime.world.prediction"

    subject_ref: str
    expected: Any
    predicted_at: datetime
    deadline: Optional[datetime] = None
    model_ref: Optional[str] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.subject_ref, str) or not self.subject_ref.strip():
            raise ContractViolation("subject_ref is required on a prediction")
        _require_aware(self.predicted_at, "predicted_at")
        if self.deadline is not None:
            _require_aware(self.deadline, "deadline")
            if self.deadline <= self.predicted_at:
                raise ContractViolation("deadline must be after predicted_at")


@dataclass(frozen=True)
class Outcome(EpistemicRecord):
    """The observed result of an action/execution (Part H). Immutable.

    An Outcome must reference the actual execution (``execution_ref``) — the
    deterministic execution/completion machinery is the authority for execution
    state, and a model cannot declare its own outcome. It optionally names the
    observation that evidences the observed result. An Outcome is not a
    Prediction and does not fulfil one merely by existing; comparison is
    explicit and later.
    """

    CONTRACT_NAME = "cortexprime.world.outcome"

    execution_ref: str
    observed: Any
    observation_ref: Optional[str] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.execution_ref, str) or not self.execution_ref.strip():
            raise ContractViolation(
                "an outcome must reference the actual execution; a model cannot "
                "declare its own outcome (Part H)"
            )
        # Provenance must also point at that execution — the outcome is grounded
        # in the platform's own execution record, not asserted.
        if self.provenance.execution_ref is None and not self.provenance.grounds_a_claim:
            raise ContractViolation(
                "an outcome's provenance must name the execution it observed")


# ----------------------------------------------------------------------
# Verification (Part I) — an assurance result, never a model self-report
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class WorldVerification(EpistemicRecord):
    """An assurance result about a subject (Part I). Immutable.

    Reuses the established ``Verdict`` (SUPPORTED / UNSUPPORTED /
    INSUFFICIENT_EVIDENCE — the honest three answers, where 'we don't know' ≠
    'it's wrong') and ``VerifierIdentity``, which already forbids a verifier
    that shares the producer's reasoning path. A Verification requires a
    ``procedure_ref`` (the check that ran) and a ``VerifierIdentity`` — it
    cannot be constructed from a model self-report alone, because a bare model
    verdict has no procedure and no independent verifier. Minting VERIFIED
    truth is the Assurance Plane's job (Phase 8); this is only the contract
    boundary.
    """

    CONTRACT_NAME = "cortexprime.world.verification"

    subject_ref: str
    procedure_ref: str
    verifier: VerifierIdentity
    verdict: Verdict
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.subject_ref, str) or not self.subject_ref.strip():
            raise ContractViolation("subject_ref is required on a verification")
        if not isinstance(self.procedure_ref, str) or not self.procedure_ref.strip():
            raise ContractViolation(
                "a verification must name the procedure/check that produced it; "
                "a verification with no procedure is a model self-report (Part I)"
            )
        if not isinstance(self.verifier, VerifierIdentity):
            raise ContractViolation("verifier must be a VerifierIdentity")
        if not isinstance(self.verdict, Verdict):
            raise ContractViolation("verdict must be a Verdict")
        if not isinstance(self.evidence_refs, tuple) or not all(
            isinstance(r, str) and r.strip() for r in self.evidence_refs
        ):
            raise ContractViolation("evidence_refs must be a tuple of reference strings")
        # A SUPPORTED verdict must cite evidence — an unevidenced 'it worked' is
        # exactly the model self-report this type exists to exclude.
        if self.verdict is Verdict.SUPPORTED and not self.evidence_refs:
            raise ContractViolation(
                "a SUPPORTED verification must cite evidence_refs; an unevidenced "
                "support verdict is a self-report, not a verification"
            )


# ----------------------------------------------------------------------
# The model-output firewall (Part Q) — the ONLY home for raw model text
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ModelProposal(EpistemicRecord):
    """Raw model output as a *proposal* about the world (Part Q).

    This is the type a model's world-claim becomes: a proposal, explicitly not
    a fact and not a belief. It exists so model output has a typed home that
    cannot be mistaken for grounded knowledge. There is no method converting a
    ``ModelProposal`` into a ``Fact``, a ``Belief``, an ``Outcome``, or a
    ``WorldVerification`` — the ingestion/assurance boundary (a later phase)
    consumes proposals and produces hypotheses or, only via observations,
    facts. The barrier is the missing conversion, enforced here by the type
    system and, at the import level, by ``BND-MODEL-CANNOT-CREATE-FACT``.

    ``model_stated_confidence`` may record what the model said about its own
    certainty, as attribution — it is a ``ModelStatedConfidence``, which also
    cannot become a ``ClaimConfidence``.
    """

    CONTRACT_NAME = "cortexprime.world.model_proposal"

    content: str
    proposed_by: str
    model_stated_confidence: Optional[Any] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.content, str) or not self.content.strip():
            raise ContractViolation("content is required on a model proposal")
        if not isinstance(self.proposed_by, str) or not self.proposed_by.strip():
            raise ContractViolation("proposed_by must name the model")
        # Note, loudly, the absence of any to_fact()/to_belief() method. That
        # absence is the firewall; adding one would breach ADR-062.
