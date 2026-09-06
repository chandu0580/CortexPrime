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

Two clocks, never one (Phase 10.2)
----------------------------------
Every timestamp is named for what it means:

* ``observed_at`` -- when the WORLD was in this state, according to the instrument.
* ``retrieved_at`` -- when CORTEXPRIME learned it.
* ``recorded_at`` -- when CortexPrime committed a ledger event.
* ``read_at`` -- when this response was computed.

They are separate fields with separate names because a UI that shows one of them
labelled "time" is asserting an event time nobody measured.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

__all__ = [
    "ApprovalList",
    "ApprovalView",
    "AssuranceList",
    "AuthorityAlternativeView",
    "AuthorityView",
    "CorroborationView",
    "ErrorResponse",
    "EvidenceRef",
    "FreshnessView",
    "HypothesisView",
    "InvestigationDetail",
    "InvestigationSummary",
    "InvestigationList",
    "RemediationOutcomeView",
    "RemediationProposalView",
    "SourceLineageView",
    "TimelineEvent",
    "TimelineView",
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


# ----------------------------------------------------------------------
# Evidence, and the standing of the source that produced it
# ----------------------------------------------------------------------

class SourceLineageView(BaseModel):
    """Where a source's data ultimately comes from.

    ``origin_id`` is the shared root two sources are compared on. When it is
    null, or ``relation`` is unknown, independence **cannot be proven** -- and
    the corroboration level says so rather than assuming the best case.
    """

    source_kind: str = ""
    source_ref: str = ""
    origin_id: Optional[str] = Field(
        default=None,
        description="The lineage root. Null means UNKNOWN origin, which is not "
                    "the same as a distinct origin.")
    relation: Optional[str] = None
    origin_known: bool = Field(
        default=False,
        description="False when lineage is not established well enough to "
                    "reason about independence.")


class EvidenceRef(BaseModel):
    """One World observation, projected.

    Carries the observation's own standing and both of its clocks, because an
    evidence list that shows only ids cannot be audited by the person reading
    it -- which was the honest limitation recorded at the end of Phase 10.1.
    """

    observation_id: str
    subject_ref: str
    predicate: str
    value: Optional[str] = None
    status: Optional[str] = Field(
        default=None,
        description="The observation's own epistemic status, unmapped.")
    source_ref: Optional[str] = Field(
        default=None, description="Which instrument observed it")
    source_kind: Optional[str] = None
    authority_tier: Optional[str] = Field(
        default=None,
        description="The source's authority tier, when a policy governs it.")
    lineage: Optional[SourceLineageView] = None
    observed_at: Optional[str] = Field(
        default=None,
        description="WHEN THE WORLD WAS OBSERVED. Not when CortexPrime learned it.")
    retrieved_at: Optional[str] = Field(
        default=None,
        description="WHEN CORTEXPRIME LEARNED IT. Never presented as the event time.")
    execution_ref: Optional[str] = Field(
        default=None,
        description="The governed execution that acquired it, for audit.")
    trace_ref: Optional[str] = None
    resolved: bool = Field(
        default=True,
        description="False when only a reference is known and the observation "
                    "itself could not be read. An unresolved reference is "
                    "reported as unresolved, never silently dropped.")


class FreshnessView(BaseModel):
    """How old the evidence is, and against which horizon.

    ``STALE`` is a first-class state here. It is not an error, and a stale
    observation is not a false one -- it is a true observation of an earlier
    moment.
    """

    state: str = "unknown"
    age_seconds: Optional[float] = None
    horizon_seconds: Optional[float] = None
    reason: str = ""


class AuthorityAlternativeView(BaseModel):
    """A value a non-authoritative source reported. Preserved, not discarded."""

    value: Optional[str] = None
    source_ref: Optional[str] = None
    tier: Optional[str] = None
    observation_ref: Optional[str] = None


class AuthorityView(BaseModel):
    """Which source settled the value, and what the others said.

    ``CONFLICTED`` keeps every competing value visible. Hiding the losing
    alternatives would turn a conflict into a clean answer, which is the
    specific dishonesty the authority layer exists to prevent.
    """

    status: str = "ungoverned"
    reason: str = ""
    source_ref: Optional[str] = None
    source_kind: Optional[str] = None
    tier: Optional[str] = None
    alternatives: tuple[AuthorityAlternativeView, ...] = ()


class CorroborationView(BaseModel):
    """How the agreeing sources relate to each other (Phase 7.6 / 9.4).

    ``CORRELATED`` is the level that matters most here: two sources agreeing
    while sharing one lineage origin are **one** independent unit, not two, and
    presenting that as independent verification is the exact error this level
    was introduced to make visible.
    """

    level: str = Field(
        description="independent / correlated / indeterminate / single / "
                    "contradicted. Never a count and never a probability.")
    independent_sources: tuple[str, ...] = ()
    independent_origins: tuple[str, ...] = ()
    lineage: tuple[SourceLineageView, ...] = ()
    correlated_count: int = 0
    supporting_count: int = 0
    contradicting_count: int = 0
    reason: str = ""


# ----------------------------------------------------------------------
# Investigation
# ----------------------------------------------------------------------

class HypothesisView(BaseModel):
    """One candidate explanation, with its standing left intact."""

    hypothesis_id: str
    statement: str
    subject_ref: Optional[str] = None
    status: str = Field(
        description="OPEN / SUPPORTED / REFUTED / UNRESOLVED as the engine "
                    "recorded it. REFUTED is not 'false' about the world; it is "
                    "'ruled out by this investigation's evidence'.")
    temporal_fit: Optional[str] = Field(
        default=None,
        description="Whether the hypothesis fits the incident's timing. UNKNOWN "
                    "is a real value and is not absence.")
    evidence_for: tuple[str, ...] = ()
    evidence_against: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = Field(
        default=(),
        description="What has not been observed. An explicit gap, not an "
                    "implied absence.")
    contradiction_refs: tuple[str, ...] = ()
    lineage_origins: tuple[str, ...] = ()
    authority: Optional[str] = None
    created_by: Optional[str] = Field(
        default=None,
        description="The producer label. A producer is not an authority: a "
                    "model may propose a hypothesis and never settle one.")
    unresolved_reason: Optional[str] = Field(
        default=None,
        description="Why this hypothesis is still open, from the platform's own "
                    "deterministic gap analysis. Absent for settled hypotheses.")
    would_support: Optional[str] = None
    would_contradict: Optional[str] = None
    discriminates_from: tuple[str, ...] = ()


class InvestigationSummary(BaseModel):
    investigation_ref: str
    status: str
    incident_ref: Optional[str] = None
    subject_ref: Optional[str] = None
    autonomy_level: Optional[str] = Field(
        default=None,
        description="Platform-set (A0-A4). Never settable by a model, and never "
                    "settable by a client -- this is a fact about the "
                    "investigation, not a control.")
    conclusion_kind: Optional[str] = Field(
        default=None,
        description="resolved / unresolved / insufficient_evidence / conflicted "
                    "/ escalated / blocked / failed. Carried unmapped.")
    opened_at: Optional[str] = None
    last_event_at: Optional[str] = Field(
        default=None,
        description="When CortexPrime last recorded an event for this "
                    "investigation. Not a world-event time.")
    is_terminal: bool = False


class InvestigationList(BaseModel):
    """A bounded page. ``limit`` is echoed so a client can see what was applied
    rather than assume its request was honoured."""

    items: tuple[InvestigationSummary, ...]
    count: int
    limit: int
    state: str = Field(
        default="all",
        description="Which lifecycle states were listed: active / completed / all.")
    note: str = ""


class TimelineEvent(BaseModel):
    """One recorded event. What happened, not what probably happened."""

    seq: int
    event_kind: str
    from_status: Optional[str] = None
    to_status: str
    autonomy_level: Optional[str] = None
    recorded_at: Optional[str] = Field(
        default=None,
        description="WHEN CORTEXPRIME COMMITTED THIS EVENT. This is a ledger "
                    "time, not the time the world changed.")
    detail: Optional[str] = Field(
        default=None,
        description="A short, safe description drawn from named payload "
                    "reference fields only. The raw payload is never returned.")


class TimelineView(BaseModel):
    investigation_ref: str
    events: tuple[TimelineEvent, ...] = ()
    count: int = 0
    note: str = Field(
        default="Recorded events only. Gaps between events are not filled in, "
                "and no event is inferred.")


class InvestigationDetail(BaseModel):
    investigation_ref: str
    status: str
    incident_ref: Optional[str] = None
    subject_ref: Optional[str] = None
    autonomy_level: Optional[str] = None
    opened_at: Optional[str] = None
    last_event_at: Optional[str] = None
    conclusion_kind: Optional[str] = None
    hypotheses: tuple[HypothesisView, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    residual_uncertainty: tuple[str, ...] = Field(
        default=(),
        description="What remains unexplained, from the platform's own terminal "
                    "read. Present even on a concluded investigation, because "
                    "concluding is not knowing everything.")
    supported: tuple[str, ...] = ()
    eliminated: tuple[str, ...] = ()
    still_open: tuple[str, ...] = ()
    assurance_verified: bool = Field(
        default=False,
        description="Whether Assurance independently verified the conclusion. "
                    "A supported hypothesis is not a verified one.")
    verification_refs: tuple[str, ...] = ()
    steps_taken: int = 0
    reads_taken: int = 0
    read_at: Optional[str] = None


# ----------------------------------------------------------------------
# World
# ----------------------------------------------------------------------

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
    queried_valid_at: Optional[str] = Field(
        default=None,
        description="The instant the world was asked about.")
    as_known_at: Optional[str] = Field(
        default=None,
        description="The knowledge cut-off the answer was computed against. "
                    "Null means 'as known now'.")
    observed_at: Optional[str] = Field(
        default=None,
        description="WHEN THE WORLD WAS OBSERVED, from the evidence that "
                    "grounds the effective value.")
    read_at: Optional[str] = Field(
        default=None,
        description="When this response was computed. A client that caches this "
                    "response must show this, not the time it rendered it.")
    freshness: FreshnessView = FreshnessView()
    authority: AuthorityView = AuthorityView()
    corroboration: Optional[CorroborationView] = None
    evidence: tuple[EvidenceRef, ...] = ()
    evidence_count: int = 0


# ----------------------------------------------------------------------
# Assurance
# ----------------------------------------------------------------------

class VerificationView(BaseModel):
    """An Assurance verdict, as Assurance recorded it."""

    verification_id: str
    verdict: str = Field(
        description="SUPPORTED / UNSUPPORTED / INSUFFICIENT_EVIDENCE. The third "
                    "is not a failure: it means the evidence did not settle the "
                    "question, which is a different thing from settling it "
                    "negatively.")
    subject_ref: str
    procedure_ref: Optional[str] = Field(
        default=None,
        description="The check that ran. A verification with no procedure would "
                    "be a self-report, which the contract forbids -- so this is "
                    "shown rather than assumed.")
    verifier_ref: Optional[str] = Field(
        default=None,
        description="Who verified. Assurance is independent of the actor that "
                    "produced the outcome, and the identity is shown so that "
                    "independence can be checked rather than assumed.")
    verifier_reasoning_path: Optional[str] = Field(
        default=None,
        description="The verifier's reasoning lineage. Independence is proven by "
                    "this differing from the producer's, not asserted.")
    rationale: Optional[str] = None
    verified_at: Optional[str] = None
    evidence_refs: tuple[str, ...] = Field(
        default=(),
        description="A SUPPORTED verdict must cite evidence; the verifier "
                    "downgrades to INSUFFICIENT_EVIDENCE when it cannot.")


class AssuranceList(BaseModel):
    investigation_ref: str
    items: tuple[VerificationView, ...] = ()
    count: int = 0
    note: str = Field(
        default="Verifications this investigation references. An empty list "
                "means nothing has been verified yet -- it does not mean the "
                "investigation was refuted.")

# ----------------------------------------------------------------------
# Remediation and approval (Phase 10.3)
# ----------------------------------------------------------------------

class RemediationProposalView(BaseModel):
    """What the platform would do, shown before anyone is asked to allow it.

    Every field is read from a capability contract, a policy or a platform digest
    function. **The client computes none of them**, which is the property that
    makes this a preview of a governed action rather than a description a
    frontend assembled and hoped the backend agreed with.
    """

    investigation_ref: str
    capability_ref: str
    capability_version: int
    capability_digest: str
    operation: str
    provider: str
    tenant_id: str = Field(
        description="Resolved from the verified session. Shown so an approver "
                    "can see whose systems this touches -- never accepted from "
                    "a request.")
    principal_id: str
    environment: str
    namespace: str
    workload: str
    parameters: dict = Field(
        description="The validated input. This exact mapping is inside the "
                    "approval digest and is what executes.")
    side_effect_class: str
    effect_semantics: Optional[str] = None
    code_trust: str
    isolation_tier: str
    reversible: bool = Field(
        description="From the capability contract. An irreversible action says "
                    "so; nothing here infers it from the operation's name.")
    blast_radius: str
    approval_required: bool
    autonomy_ceiling: str = Field(
        description="Platform-set. Displayed as a fact; there is no route that "
                    "could change it.")
    approval_digest: str = Field(
        description="ADR-090. The digest a human approves, and the one the "
                    "gateway compares against. An approval for one workload "
                    "cannot authorize another because the payload is inside it.")
    evidence_refs: tuple[str, ...] = ()
    diagnosis: Optional[str] = None


class ApprovalView(BaseModel):
    """One approval, with the exact action it is bound to."""

    approval_id: str
    investigation_ref: Optional[str] = None
    capability_ref: str
    capability_digest: str
    operation: str
    environment: str
    namespace: str
    workload: str
    parameters: dict
    approval_digest: str
    state: str = Field(
        description="pending / granted / denied / withdrawn / expired, as the "
                    "approval contract names them. Not success or failure.")
    requested_by: str = Field(
        description="A namespaced identity reference for the authenticated "
                    "human. Never a name supplied by a browser.")
    decided_by: Optional[str] = None
    justification: Optional[str] = None
    requested_at: Optional[str] = None
    decided_at: Optional[str] = None
    expires_at: Optional[str] = Field(
        default=None,
        description="Every approval expires. A standing authorization nobody "
                    "consciously granted is not something this system issues.")
    expired: bool = False
    consumed_by_execution: Optional[str] = Field(
        default=None,
        description="Which execution used it. Recorded so a second use is "
                    "visible -- at-least-once remains the platform contract and "
                    "this field does not change it.")


class ApprovalList(BaseModel):
    items: tuple[ApprovalView, ...] = ()
    count: int = 0
    limit: int = 25


class RemediationOutcomeView(BaseModel):
    """What is ESTABLISHED about a remediation, stage by stage.

    ``world_status`` comes from an independent World read and
    ``assurance_verdicts`` from Assurance. Neither is derived from the
    execution's own reply: Phase 9.10's finding was that a POST to a worker is
    not a mutation of Kubernetes, and a product outcome screen is the easiest
    place in the system to forget that.
    """

    execution_ref: str
    approval_id: str
    subject_ref: str
    action_requested: bool = False
    action_approved: bool = False
    execution_started: bool = False
    world_status: Optional[str] = Field(
        default=None,
        description="The epistemic status of the world afterwards. Null means "
                    "not yet observed -- which is not the same as unchanged.")
    world_value: Optional[str] = None
    world_observed_at: Optional[str] = None
    assurance_verdicts: tuple[str, ...] = Field(
        default=(),
        description="SUPPORTED / UNSUPPORTED / INSUFFICIENT_EVIDENCE, unmapped. "
                    "An empty tuple means Assurance has not ruled.")
    read_at: Optional[str] = None
    note: Optional[str] = None
