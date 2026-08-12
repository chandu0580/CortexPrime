"""The investigation service — the durable, crash-safe state machine.

Every mutation is an immutable event appended to the investigation ledger,
carrying the full new aggregate snapshot; the latest committed snapshot is the
authoritative current state. The service enforces, structurally:

  * tenant scope from the governed context (never a payload/model/prompt) —
    fail closed;
  * legal state transitions only (an invalid transition refuses);
  * autonomy is platform-set and never promotable by a model; a real action
    (transition to EXECUTING) requires A3+ AND an explicit authorization (a human
    APPROVED event for A3, a policy authorization ref for A4);
  * a model PROPOSES (a question/hypothesis/test carries a producer label) —
    it never sets status, autonomy, or truth;
  * the field-aware secret firewall runs over every event before it is written.

No model call, no execution, no provider, no database here (the repository is a
port; the model boundary and world-read are ports supplied by composition).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any, Optional, Protocol

from backend.contracts.errors import ContractViolation
from backend.contracts.intelligence import (
    AutonomyLevel,
    DifferentialHypothesis,
    HumanEvent,
    HumanEventKind,
    Investigation,
    InvestigationEventKind,
    InvestigationQuestion,
    InvestigationStatus,
    InvestigationTest,
    is_legal_transition,
    is_terminal_status,
)
from backend.contracts.tenant import TenantRef
from backend.contracts.world import ProvenanceRef
from backend.platform.credentials.inspection import find_secrets
from backend.platform.hashing import compute_digest
from backend.platform.identity.generators import prefixed_id

__all__ = [
    "InvestigationRepository",
    "InvestigationService",
    "InvestigationRejected",
    "InvestigationTransitionRefused",
    "AutonomyRefused",
    "InvestigationNotFound",
    "InvestigationConcurrencyError",
]


class InvestigationRejected(ContractViolation):
    """An investigation operation was refused (bad tenant, secret-bearing content,
    cross-tenant, malformed proposal)."""


class InvestigationTransitionRefused(InvestigationRejected):
    """An illegal state transition was refused."""


class AutonomyRefused(InvestigationRejected):
    """An action was refused because autonomy policy did not permit it — a model
    can never promote autonomy."""


class InvestigationNotFound(InvestigationRejected):
    """No investigation with that ref for this tenant (fail closed)."""


class InvestigationConcurrencyError(InvestigationRejected):
    """A concurrent writer already committed this sequence; reload and retry."""


class InvestigationRepository(Protocol):
    """The durable, append-only event ledger. No update, no delete — each event is
    immutable; the latest committed snapshot is the current state."""

    def append(
        self, *, event_id: str, identity_digest: str, investigation_id: str,
        tenant_id: str, incident_ref: str, seq: int, event_kind: str,
        from_status: Optional[str], to_status: str, autonomy_level: str,
        state: dict, payload: dict, recorded_at: datetime,
    ) -> bool:
        """Append one event; return True if newly recorded, False if a writer
        already committed this (investigation, seq) — optimistic concurrency."""
        ...

    def latest_state(
        self, *, tenant_id: str, investigation_id: str
    ) -> Optional[dict]:
        """The latest committed aggregate snapshot for this investigation, only if
        it belongs to ``tenant_id`` (fail closed). None if unknown."""
        ...


def _event_identity(tenant_id: str, investigation_id: str, seq: int) -> str:
    # One event per (investigation, seq): the unique constraint gives optimistic
    # concurrency and idempotency.
    return compute_digest(
        {"tenant": tenant_id, "investigation": investigation_id, "seq": seq}).value


class InvestigationService:
    """Owns the investigation state machine over the durable ledger."""

    def __init__(
        self, *, repository: InvestigationRepository,
        produced_by: str = "intelligence:investigator/1",
    ) -> None:
        self._repository = repository
        self._produced_by = produced_by

    # -- construction -------------------------------------------------------

    def create(
        self, *, tenant: TenantRef, incident_ref: str, policy_ref: str,
        harness_version: str, now: datetime,
        autonomy_level: AutonomyLevel = AutonomyLevel.A1_INVESTIGATE,
        investigation_ref: Optional[str] = None,
    ) -> Investigation:
        """Open an investigation at status CREATED. ``autonomy_level`` is a
        PLATFORM value (default A1); nothing a model produces sets it."""
        if not isinstance(tenant, TenantRef):
            raise InvestigationRejected("tenant must be an explicit TenantRef")
        if not isinstance(autonomy_level, AutonomyLevel):
            raise InvestigationRejected("autonomy_level must be an AutonomyLevel (platform-set)")
        inv = Investigation(
            investigation_ref=investigation_ref or prefixed_id("winv"),
            tenant=tenant, incident_ref=incident_ref, status=InvestigationStatus.CREATED,
            autonomy_level=autonomy_level, seq=0, created_at=now, updated_at=now,
            provenance=ProvenanceRef(produced_by=self._produced_by,
                                     parent_claim_ref=incident_ref),
            policy_ref=policy_ref, harness_version=harness_version)
        return self._commit(inv, InvestigationEventKind.CREATED, from_status=None,
                            payload={"incident_ref": incident_ref}, now=now)

    def reconstruct(
        self, *, tenant: TenantRef, investigation_ref: str
    ) -> Investigation:
        """The current state, reconstructed from the latest committed snapshot."""
        if not isinstance(tenant, TenantRef):
            raise InvestigationRejected("tenant must be an explicit TenantRef")
        state = self._repository.latest_state(
            tenant_id=tenant.tenant_id, investigation_id=investigation_ref)
        if state is None:
            raise InvestigationNotFound(
                f"no investigation {investigation_ref!r} for this tenant")
        return Investigation.from_dict(state)

    # -- reasoning artifacts (the model proposes; the platform records) -----

    def add_question(
        self, *, investigation: Investigation, purpose: str, created_by: str,
        now: datetime, evidence_required: tuple[str, ...] = (),
        hypothesis_refs: tuple[str, ...] = (),
    ) -> tuple[Investigation, InvestigationQuestion]:
        self._guard_open(investigation)
        question = InvestigationQuestion(
            question_ref=prefixed_id("wq"), investigation_ref=investigation.investigation_ref,
            tenant=investigation.tenant, purpose=purpose, created_by=created_by,
            provenance=ProvenanceRef(produced_by=created_by,
                                     parent_claim_ref=investigation.investigation_ref),
            evidence_required=evidence_required, hypothesis_refs=hypothesis_refs)
        status = (InvestigationStatus.INVESTIGATING
                  if investigation.status is InvestigationStatus.CREATED
                  else investigation.status)
        updated = self._advance(
            investigation, now, status=status,
            current_question_ref=question.question_ref,
            question_refs=investigation.question_refs + (question.question_ref,))
        updated = self._commit(updated, InvestigationEventKind.QUESTION_ADDED,
                               from_status=investigation.status,
                               payload=question.to_dict(), now=now)
        return updated, question

    def upsert_hypothesis(
        self, *, investigation: Investigation, hypothesis: DifferentialHypothesis,
        now: datetime,
    ) -> Investigation:
        """Add or replace a differential candidate. The hypothesis is a
        model/platform reasoning artifact — never a fact."""
        self._guard_open(investigation)
        if not isinstance(hypothesis, DifferentialHypothesis):
            raise InvestigationRejected("upsert_hypothesis requires a DifferentialHypothesis")
        others = tuple(h for h in investigation.differential
                       if h.hypothesis_ref != hypothesis.hypothesis_ref)
        updated = self._advance(investigation, now, differential=others + (hypothesis,))
        return self._commit(updated, InvestigationEventKind.HYPOTHESIS_UPSERTED,
                            from_status=investigation.status,
                            payload=hypothesis.to_dict(), now=now)

    def link_evidence(
        self, *, investigation: Investigation, evidence_refs: tuple[str, ...], now: datetime
    ) -> Investigation:
        self._guard_open(investigation)
        merged = tuple(dict.fromkeys(investigation.evidence_refs + evidence_refs))
        updated = self._advance(investigation, now, evidence_refs=merged)
        return self._commit(updated, InvestigationEventKind.EVIDENCE_LINKED,
                            from_status=investigation.status,
                            payload={"evidence_refs": list(evidence_refs)}, now=now)

    def add_test(
        self, *, investigation: Investigation, test: InvestigationTest, now: datetime
    ) -> tuple[Investigation, InvestigationTest]:
        self._guard_open(investigation)
        if not isinstance(test, InvestigationTest):
            raise InvestigationRejected("add_test requires an InvestigationTest")
        updated = self._advance(investigation, now, test_refs=investigation.test_refs + (test.test_ref,))
        updated = self._commit(updated, InvestigationEventKind.TEST_ADDED,
                               from_status=investigation.status,
                               payload=test.to_dict(), now=now)
        return updated, test

    def link_prediction(
        self, *, investigation: Investigation, prediction_ref: str, now: datetime
    ) -> Investigation:
        self._guard_open(investigation)
        updated = self._advance(
            investigation, now,
            prediction_refs=tuple(dict.fromkeys(
                investigation.prediction_refs + (prediction_ref,))))
        return self._commit(updated, InvestigationEventKind.PREDICTION_LINKED,
                            from_status=investigation.status,
                            payload={"prediction_ref": prediction_ref}, now=now)

    def link_verification(
        self, *, investigation: Investigation, verification_ref: str, now: datetime
    ) -> Investigation:
        updated = self._advance(
            investigation, now,
            verification_refs=tuple(dict.fromkeys(
                investigation.verification_refs + (verification_ref,))))
        return self._commit(updated, InvestigationEventKind.VERIFICATION_LINKED,
                            from_status=investigation.status,
                            payload={"verification_ref": verification_ref}, now=now)

    def record_human_event(
        self, *, investigation: Investigation, human_event: HumanEvent, now: datetime
    ) -> Investigation:
        if not isinstance(human_event, HumanEvent):
            raise InvestigationRejected("record_human_event requires a HumanEvent")
        return self._commit(self._advance(investigation, now),
                            InvestigationEventKind.HUMAN_EVENT,
                            from_status=investigation.status,
                            payload=human_event.to_dict(), now=now)

    def checkpoint(self, *, investigation: Investigation, now: datetime) -> Investigation:
        """An explicit durable checkpoint (the current snapshot). Resumption
        restores this exactly; it never advances the workflow."""
        return self._commit(self._advance(investigation, now),
                            InvestigationEventKind.CHECKPOINT,
                            from_status=investigation.status,
                            payload={"checkpoint_seq": investigation.seq}, now=now)

    # -- transitions --------------------------------------------------------

    def transition(
        self, *, investigation: Investigation, to_status: InvestigationStatus,
        cause: str, now: datetime, human_event: Optional[HumanEvent] = None,
        policy_authorization_ref: Optional[str] = None,
    ) -> Investigation:
        """Move to ``to_status`` if the transition is legal and (for a real
        action) authorized. Never fabricates progress; UNKNOWN never becomes
        success — the caller must transition through VERIFYING to COMPLETED."""
        if not isinstance(to_status, InvestigationStatus):
            raise InvestigationRejected("to_status must be an InvestigationStatus")
        if is_terminal_status(investigation.status):
            raise InvestigationTransitionRefused(
                f"{investigation.status.value} is terminal; no transition allowed")
        if not is_legal_transition(investigation.status, to_status):
            raise InvestigationTransitionRefused(
                f"illegal transition {investigation.status.value} -> {to_status.value}")

        # Autonomy gate: a real action requires A3+ AND explicit authorization —
        # a model can neither promote autonomy nor authorize itself.
        if to_status is InvestigationStatus.EXECUTING:
            if not investigation.autonomy_level.permits_action():
                raise AutonomyRefused(
                    f"autonomy {investigation.autonomy_level.value} does not permit "
                    "action; a model cannot promote autonomy")
            approved_by_human = (
                human_event is not None
                and human_event.kind is HumanEventKind.APPROVED)
            if investigation.autonomy_level is AutonomyLevel.A3_APPROVED_ACTION and not approved_by_human:
                raise AutonomyRefused(
                    "A3 requires an explicit human APPROVED event before EXECUTING")
            if investigation.autonomy_level is AutonomyLevel.A4_AUTONOMOUS \
                    and not (policy_authorization_ref or approved_by_human):
                raise AutonomyRefused(
                    "A4 requires an explicit policy authorization reference")

        updated = self._advance(investigation, now, status=to_status)
        payload: dict = {"cause": cause, "from": investigation.status.value,
                         "to": to_status.value}
        if human_event is not None:
            payload["human_event"] = human_event.to_dict()
        if policy_authorization_ref is not None:
            payload["policy_authorization_ref"] = policy_authorization_ref
        return self._commit(updated, InvestigationEventKind.TRANSITIONED,
                            from_status=investigation.status, payload=payload, now=now)

    # -- internals ----------------------------------------------------------

    def _guard_open(self, investigation: Investigation) -> None:
        if is_terminal_status(investigation.status):
            raise InvestigationTransitionRefused(
                f"investigation is {investigation.status.value} (terminal); no further "
                "reasoning artifacts may be added")

    def _advance(self, base: Investigation, now: datetime, **changes: Any) -> Investigation:
        """The next snapshot: seq incremented, update time stamped, changes applied.
        Model output never reaches here as a seq/autonomy/status change — those come
        only from the service's own validated operations."""
        return replace(base, seq=base.seq + 1, updated_at=now, **changes)

    def _commit(
        self, investigation: Investigation, kind: InvestigationEventKind, *,
        from_status: Optional[InvestigationStatus], payload: dict, now: datetime,
    ) -> Investigation:
        # ``investigation`` already carries its final seq (0 for CREATED, advanced
        # for every other op). The event is appended AT that seq.
        state = investigation.to_dict()
        # Secret firewall over BOTH the event payload and the full snapshot: no
        # credential material ever enters the reasoning/investigation ledger.
        findings = find_secrets(payload) + find_secrets(state)
        if findings:
            where = ", ".join(f"{f.path} ({f.why})" for f in findings[:6])
            raise InvestigationRejected(
                f"investigation artifact carries secret-shaped material ({where}); "
                "the ledger stores references and digests, never credentials")
        identity = _event_identity(
            investigation.tenant.tenant_id, investigation.investigation_ref, investigation.seq)
        newly = self._repository.append(
            event_id=prefixed_id("winvev"), identity_digest=identity,
            investigation_id=investigation.investigation_ref,
            tenant_id=investigation.tenant.tenant_id,
            incident_ref=investigation.incident_ref, seq=investigation.seq,
            event_kind=kind.value,
            from_status=from_status.value if from_status else None,
            to_status=investigation.status.value,
            autonomy_level=investigation.autonomy_level.value,
            state=state, payload=payload, recorded_at=now)
        if not newly:
            raise InvestigationConcurrencyError(
                f"sequence {investigation.seq} for {investigation.investigation_ref} "
                "already committed by another writer; reload and retry")
        return investigation
