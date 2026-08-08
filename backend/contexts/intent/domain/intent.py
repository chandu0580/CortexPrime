"""The Intent aggregate.

An intent is a mandate under construction: what somebody asked for, turned into
something an automated system can act on without guessing. It is the canonical
input to planning, and this context produces nothing else.

What this aggregate refuses to be
----------------------------------
It holds no tasks, no steps, no ordering, no dependencies, no tool selection.
Those are a *plan*, and the moment an intent could express one, the boundary
between wanting something and deciding how to get it would be gone -- which is
the boundary that lets a human approve the first without implicitly approving
the second.

Intent never executes either. Every field here is a statement about what should
become true; none is a record of anything happening.

The six things an intent must contain
--------------------------------------
Objective, constraints, scope, priority, risk, success criteria. Validation
refuses without all six, and each has its own rule about what makes it real:
a criterion nobody can check is a wish, a quantitative constraint with no limit
constrains nothing, a scope that includes nothing authorises nothing.

Approval seals the mandate
---------------------------
An approved intent binds a digest. Planning acts on it, so an intent that
changed afterwards would mean the plan was built from something nobody approved.
Expansion before approval is normal and returns a validated intent to draft --
because the thing that was validated is no longer the thing on record.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Final, Optional

from backend.contracts._contract import Contract
from backend.contracts.approval import HashAlgorithm, PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contracts.mission import MissionIntent
from backend.contexts.intent.domain.constraints import IntentConstraint
from backend.contexts.intent.domain.errors import (
    DigestMismatch,
    DigestNotComputed,
    DuplicateConstraint,
    IllegalIntentTransition,
    IncompleteIntent,
    IntentApproved,
    IntentIsSuperseded,
    UnknownConstraint,
    UnknownCriterion,
)
from backend.contexts.intent.domain.identifiers import (
    ConstraintId,
    CriterionId,
    IntentId,
)
from backend.contexts.intent.domain.metadata import IntentMetadata
from backend.contexts.intent.domain.objective import IntentObjective, SuccessCriterion
from backend.contexts.intent.domain.priority import (
    AcknowledgedRisk,
    IntentPriority,
    RiskAppetite,
)
from backend.contexts.intent.domain.scope import IntentScope
from backend.contexts.intent.domain.status import (
    IntentStatus,
    is_legal_transition,
    permitted_from,
)
from backend.platform.hashing import compute_digest, digests_match

__all__ = [
    "Intent",
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
    "REQUIRED_ELEMENTS",
]

ARTIFACT_KIND: Final[str] = "cortexprime.intent.intent"
CANONICAL_FORM_VERSION: Final[int] = 1

#: What the approval digest covers. Excludes status, timestamps, and the digest
#: itself -- superseding an approved intent is legal and must not invalidate it.
GOVERNED_FIELDS: Final[tuple] = (
    "intent_id",
    "stated_goal",
    "metadata",
    "objective",
    "constraints",
    "scope",
    "priority",
    "risk_appetite",
    "acknowledged_risks",
    "success_criteria",
    "rejection_reason",
)

#: The six the rules name. Validation refuses without all of them, and the names
#: are the ones a refusal reports.
REQUIRED_ELEMENTS: Final[tuple] = (
    "objective",
    "constraints",
    "scope",
    "priority",
    "risk",
    "success criteria",
)


@dataclass(frozen=True)
class Intent(Contract):
    """One enterprise goal, structured enough to act on without guessing."""

    CONTRACT_NAME = "cortexprime.intent.intent_aggregate"

    intent_id: IntentId
    raw: MissionIntent
    metadata: IntentMetadata

    objective: Optional[IntentObjective] = None
    constraints: tuple = ()
    scope: Optional[IntentScope] = None
    priority: IntentPriority = IntentPriority.ROUTINE
    risk_appetite: RiskAppetite = RiskAppetite.MEASURED
    acknowledged_risks: tuple = ()
    success_criteria: tuple = ()

    status: IntentStatus = IntentStatus.DRAFT
    validated_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    digest: Optional[str] = None
    expansion_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    superseded_by: Optional[IntentId] = None

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, IntentId):
            raise ContractViolation("intent_id must be an IntentId")
        if not isinstance(self.raw, MissionIntent):
            raise ContractViolation(
                "raw must be a MissionIntent; the requester's own words are what "
                "makes it auditable whether the mandate matches what was asked for"
            )
        if not isinstance(self.metadata, IntentMetadata):
            raise ContractViolation("metadata must be an IntentMetadata")
        if not isinstance(self.priority, IntentPriority):
            raise ContractViolation("priority must be an IntentPriority")
        if not isinstance(self.risk_appetite, RiskAppetite):
            raise ContractViolation("risk_appetite must be a RiskAppetite")
        if not isinstance(self.status, IntentStatus):
            raise ContractViolation("status must be an IntentStatus")

        if self.objective is not None and not isinstance(self.objective, IntentObjective):
            raise ContractViolation("objective must be an IntentObjective")
        if self.scope is not None and not isinstance(self.scope, IntentScope):
            raise ContractViolation("scope must be an IntentScope")

        for label, items, expected in (
            ("constraints", self.constraints, IntentConstraint),
            ("acknowledged_risks", self.acknowledged_risks, AcknowledgedRisk),
            ("success_criteria", self.success_criteria, SuccessCriterion),
        ):
            if not isinstance(items, tuple):
                raise ContractViolation(f"{label} must be a tuple")
            for item in items:
                if not isinstance(item, expected):
                    raise ContractViolation(
                        f"{label} contains {item!r}, which is not a {expected.__name__}"
                    )

        for label, ids in (
            ("constraints", [str(c.constraint_id) for c in self.constraints]),
            ("success_criteria", [str(c.criterion_id) for c in self.success_criteria]),
            ("acknowledged_risks", [str(r.risk_id) for r in self.acknowledged_risks]),
        ):
            if len(set(ids)) != len(ids):
                raise ContractViolation(f"{label} contains duplicate ids")

        if not isinstance(self.expansion_count, int) or self.expansion_count < 0:
            raise ContractViolation("expansion_count must be a non-negative integer")

        # Validation and approval are statements about a complete intent.
        if self.status in (IntentStatus.VALIDATED, IntentStatus.APPROVED):
            missing = self._missing_elements()
            if missing:
                raise IncompleteIntent(intent_id=str(self.intent_id), missing=missing)

        if self.status is IntentStatus.VALIDATED and self.validated_at is None:
            raise ContractViolation("a validated intent must record when")

        if self.status is IntentStatus.APPROVED:
            if not self.digest:
                raise ContractViolation(
                    "an approved intent must carry the digest computed at approval; "
                    "without it the mandate planning acts on cannot be shown to be "
                    "the one that was approved"
                )
            if self.approved_at is None:
                raise ContractViolation("an approved intent must record when")
            if not (self.approved_by and self.approved_by.strip()):
                raise ContractViolation(
                    "an approved intent must name who approved it; an unattributed "
                    "mandate has nobody accountable for it"
                )

        if self.status is IntentStatus.REJECTED and not (
            self.rejection_reason and self.rejection_reason.strip()
        ):
            raise ContractViolation(
                "a rejected intent must say why; the next attempt is built from the "
                "reason, and an unexplained refusal produces the same intent again"
            )

        if self.status is IntentStatus.SUPERSEDED and self.superseded_by is None:
            raise ContractViolation("a superseded intent must name its successor")

        if self.superseded_by is not None and not isinstance(self.superseded_by, IntentId):
            raise ContractViolation("superseded_by must be an IntentId")

        for label in ("created_at", "validated_at", "approved_at"):
            value = getattr(self, label)
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def _missing_elements(self) -> tuple:
        """Which of the six required elements are absent."""
        missing: list = []
        if self.objective is None:
            missing.append("objective")
        if not self.constraints:
            missing.append("constraints")
        if self.scope is None:
            missing.append("scope")
        if not self.success_criteria:
            missing.append("success criteria")
        # Priority and risk appetite always have a value, so they cannot be
        # missing -- but a defaulted risk appetite on an acting objective is a
        # decision nobody made, which policy reports rather than the aggregate.
        return tuple(missing)

    @property
    def missing_elements(self) -> tuple:
        return self._missing_elements()

    @property
    def is_complete(self) -> bool:
        return not self._missing_elements()

    @property
    def stated_goal(self) -> str:
        """The requester's own words, verbatim."""
        return self.raw.stated_goal

    @property
    def is_open(self) -> bool:
        return self.status.is_open

    @property
    def is_planable(self) -> bool:
        return self.status.is_planable

    @property
    def hard_constraints(self) -> tuple:
        return tuple(c for c in self.constraints if c.is_hard)

    @property
    def inviolable_constraints(self) -> tuple:
        return tuple(c for c in self.constraints if c.kind.is_inviolable)

    @property
    def unaccepted_high_risks(self) -> tuple:
        return tuple(
            r for r in self.acknowledged_risks if r.impact.requires_acceptance and not r.accepted_by
        )

    @property
    def comparative_criteria_without_baseline(self) -> tuple:
        return tuple(c for c in self.success_criteria if c.is_comparative)

    @property
    def changes_the_world(self) -> bool:
        return self.objective is not None and self.objective.changes_the_world

    @property
    def touches_production(self) -> bool:
        return self.scope is not None and self.scope.touches_production

    def constraint(self, constraint_id: ConstraintId) -> Optional[IntentConstraint]:
        for candidate in self.constraints:
            if candidate.constraint_id == constraint_id:
                return candidate
        return None

    def criterion(self, criterion_id: CriterionId) -> Optional[SuccessCriterion]:
        for candidate in self.success_criteria:
            if candidate.criterion_id == criterion_id:
                return candidate
        return None

    def permitted_transitions(self) -> tuple:
        return permitted_from(self.status)

    # ------------------------------------------------------------------
    # Digest
    # ------------------------------------------------------------------

    def digest_payload(self) -> dict[str, Any]:
        """Exactly what the approval digest covers."""
        return {
            "__artifact__": ARTIFACT_KIND,
            "__canonical_form__": CANONICAL_FORM_VERSION,
            "intent_id": str(self.intent_id),
            "stated_goal": self.raw.stated_goal,
            "metadata": {
                "title": self.metadata.title,
                "origin": self.metadata.origin.value,
                "tags": sorted(self.metadata.tags),
                "derived_from": self.metadata.derived_from,
            },
            "objective": (
                {
                    "outcome": self.objective.outcome,
                    "kind": self.objective.kind.value,
                    "rationale": self.objective.rationale,
                    "subject": self.objective.subject,
                }
                if self.objective
                else None
            ),
            "constraints": sorted(
                (
                    {
                        "constraint_id": str(c.constraint_id),
                        "kind": c.kind.value,
                        "statement": c.statement,
                        "limit": c.limit,
                        "enforcement": c.enforcement.value,
                    }
                    for c in self.constraints
                ),
                key=lambda item: item["constraint_id"],
            ),
            "scope": (
                {
                    "included": list(self.scope.included_identifiers),
                    "excluded": list(self.scope.excluded_identifiers),
                    "environments": sorted(e.value for e in self.scope.environments),
                    "note": self.scope.note,
                }
                if self.scope
                else None
            ),
            "priority": self.priority.value,
            "risk_appetite": self.risk_appetite.value,
            "acknowledged_risks": sorted(
                (
                    {
                        "risk_id": str(r.risk_id),
                        "statement": r.statement,
                        "impact": r.impact.value,
                        "accepted_by": r.accepted_by,
                    }
                    for r in self.acknowledged_risks
                ),
                key=lambda item: item["risk_id"],
            ),
            "success_criteria": sorted(
                (
                    {
                        "criterion_id": str(c.criterion_id),
                        "statement": c.statement,
                        "measure": c.measure,
                        "threshold": c.threshold,
                        "baseline": c.baseline,
                    }
                    for c in self.success_criteria
                ),
                key=lambda item: item["criterion_id"],
            ),
            "rejection_reason": self.rejection_reason,
        }

    def compute_digest(self, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> PayloadDigest:
        return compute_digest(self.digest_payload(), algorithm)

    def verify_digest(self) -> None:
        """Raise unless the intent still hashes to the digest bound at approval."""
        if not self.digest:
            raise DigestNotComputed(str(self.intent_id))
        recomputed = self.compute_digest()
        if not digests_match(
            recomputed, PayloadDigest(algorithm=recomputed.algorithm, value=self.digest)
        ):
            raise DigestMismatch(
                intent_id=str(self.intent_id),
                recorded=self.digest,
                recomputed=recomputed.value,
            )

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _require_open(self, operation: str) -> None:
        if self.status is IntentStatus.SUPERSEDED:
            raise IntentIsSuperseded(
                intent_id=str(self.intent_id), successor=str(self.superseded_by)
            )
        if self.status is IntentStatus.APPROVED:
            raise IntentApproved(intent_id=str(self.intent_id), operation=operation)
        if not self.status.is_open:
            raise IntentApproved(intent_id=str(self.intent_id), operation=operation)

    def _expanded(self, **changes: Any) -> "Intent":
        """Apply a change, returning a validated intent to draft.

        Expansion invalidates validation. ``VALIDATED`` is a statement about a
        particular set of constraints, scope and criteria; changing any of them
        makes it a statement about a document that no longer exists.
        """
        # The demotion is applied in the *same* construction as the change, not a
        # second one. Removing a constraint from a validated intent would
        # otherwise build an intermediate that is validated and incomplete --
        # which its own invariant refuses, correctly.
        if self.status is IntentStatus.VALIDATED:
            return replace(
                self,
                expansion_count=self.expansion_count + 1,
                status=IntentStatus.DRAFT,
                validated_at=None,
                **changes,
            )
        return replace(self, expansion_count=self.expansion_count + 1, **changes)

    # ------------------------------------------------------------------
    # Expansion -- filling in the mandate
    # ------------------------------------------------------------------

    def set_objective(self, objective: IntentObjective) -> "Intent":
        self._require_open("setting the objective")
        if not isinstance(objective, IntentObjective):
            raise ContractViolation("objective must be an IntentObjective")
        return self._expanded(objective=objective)

    def set_scope(self, scope: IntentScope) -> "Intent":
        self._require_open("setting the scope")
        if not isinstance(scope, IntentScope):
            raise ContractViolation("scope must be an IntentScope")
        return self._expanded(scope=scope)

    def set_priority(self, priority: IntentPriority) -> "Intent":
        self._require_open("setting the priority")
        if not isinstance(priority, IntentPriority):
            raise ContractViolation("priority must be an IntentPriority")
        return self._expanded(priority=priority)

    def set_risk_appetite(self, appetite: RiskAppetite) -> "Intent":
        self._require_open("setting the risk appetite")
        if not isinstance(appetite, RiskAppetite):
            raise ContractViolation("appetite must be a RiskAppetite")
        return self._expanded(risk_appetite=appetite)

    def add_constraint(self, constraint: IntentConstraint) -> "Intent":
        self._require_open("adding a constraint")
        if not isinstance(constraint, IntentConstraint):
            raise ContractViolation("constraint must be an IntentConstraint")
        if any(
            c.kind is constraint.kind and c.statement == constraint.statement
            for c in self.constraints
        ):
            raise DuplicateConstraint(constraint.statement)
        return self._expanded(constraints=self.constraints + (constraint,))

    def remove_constraint(self, constraint_id: ConstraintId) -> "Intent":
        """Drop a constraint. Counts as an expansion, because it widens the mandate."""
        self._require_open("removing a constraint")
        if self.constraint(constraint_id) is None:
            raise UnknownConstraint(
                intent_id=str(self.intent_id), constraint_id=str(constraint_id)
            )
        return self._expanded(
            constraints=tuple(
                c for c in self.constraints if c.constraint_id != constraint_id
            )
        )

    def add_success_criterion(self, criterion: SuccessCriterion) -> "Intent":
        self._require_open("adding a success criterion")
        if not isinstance(criterion, SuccessCriterion):
            raise ContractViolation("criterion must be a SuccessCriterion")
        if any(c.statement == criterion.statement for c in self.success_criteria):
            raise ContractViolation(
                f"success criterion {criterion.statement[:60]!r} is already declared"
            )
        return self._expanded(success_criteria=self.success_criteria + (criterion,))

    def remove_success_criterion(self, criterion_id: CriterionId) -> "Intent":
        self._require_open("removing a success criterion")
        if self.criterion(criterion_id) is None:
            raise UnknownCriterion(
                intent_id=str(self.intent_id), criterion_id=str(criterion_id)
            )
        return self._expanded(
            success_criteria=tuple(
                c for c in self.success_criteria if c.criterion_id != criterion_id
            )
        )

    def acknowledge_risk(self, risk: AcknowledgedRisk) -> "Intent":
        self._require_open("acknowledging a risk")
        if not isinstance(risk, AcknowledgedRisk):
            raise ContractViolation("risk must be an AcknowledgedRisk")
        return self._expanded(acknowledged_risks=self.acknowledged_risks + (risk,))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _transition(self, to_status: IntentStatus, **changes: Any) -> "Intent":
        if not is_legal_transition(self.status, to_status):
            raise IllegalIntentTransition(
                intent_id=str(self.intent_id),
                source=self.status.value,
                target=to_status.value,
                permitted=permitted_from(self.status),
            )
        return replace(self, status=to_status, **changes)

    def validate(self) -> "Intent":
        """Mark the intent coherent and complete.

        The aggregate checks *completeness*; policy checks coherence and reports
        every reason at once. Both run -- an intent missing an element cannot be
        constructed as validated at all, so this refusal fires before storage
        could ever hold one.
        """
        self._require_open("validating")
        missing = self._missing_elements()
        if missing:
            raise IncompleteIntent(intent_id=str(self.intent_id), missing=missing)
        return self._transition(
            IntentStatus.VALIDATED, validated_at=datetime.now(timezone.utc)
        )

    def approve(self, approved_by: str) -> "Intent":
        """Seal the mandate and bind its digest."""
        self._require_open("approving")
        if not approved_by or not approved_by.strip():
            raise ContractViolation(
                "an approval must name who gave it; an unattributed mandate has "
                "nobody accountable for it"
            )
        if not is_legal_transition(self.status, IntentStatus.APPROVED):
            raise IllegalIntentTransition(
                intent_id=str(self.intent_id),
                source=self.status.value,
                target=IntentStatus.APPROVED.value,
                permitted=permitted_from(self.status),
            )

        # The digest covers the approved content, but an approved intent cannot
        # be constructed without one. So the payload is assembled directly rather
        # than by building an intermediate that would violate one invariant to
        # satisfy the other. It is byte-identical to what the sealed intent
        # reports -- no governed field changes at approval -- which is what makes
        # ``verify_digest`` on the result pass. A test asserts exactly that.
        digest = compute_digest(self.digest_payload()).value

        return self._transition(
            IntentStatus.APPROVED,
            approved_at=datetime.now(timezone.utc),
            approved_by=approved_by.strip(),
            digest=digest,
        )

    def reject(self, reason: str) -> "Intent":
        self._require_open("rejecting")
        if not reason or not reason.strip():
            raise ContractViolation("rejecting an intent must say why")
        return self._transition(IntentStatus.REJECTED, rejection_reason=reason.strip())

    def supersede(self, successor: IntentId) -> "Intent":
        """Record that a later intent replaces this one.

        Permitted on an approved intent, unlike every other change: superseding
        does not alter what the intent *said*, only whether it is current. The
        digest still verifies afterwards, and a test asserts that.
        """
        if not isinstance(successor, IntentId):
            raise ContractViolation("successor must be an IntentId")
        if successor == self.intent_id:
            raise ContractViolation("an intent cannot supersede itself")
        if self.superseded_by is not None:
            raise ContractViolation(
                f"intent {self.intent_id} is already superseded by {self.superseded_by}"
            )
        return self._transition(IntentStatus.SUPERSEDED, superseded_by=successor)
