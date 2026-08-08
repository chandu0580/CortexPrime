"""Canonical digest over a WorkOrder's governed fields.

Approval binds to this value. Every later transition re-checks it, so a change
to a governed field after approval means the WorkOrder no longer hashes to what
was approved and the transition halts. That is the process analogue of the
product's approved-payload-equals-executed-payload invariant, and it is here for
the same reason: without it, "approved" describes a document that may since have
become a different document.

Governed fields (Artifact Specification §2.7)::

    work_id, version, intent, acceptance_criteria, adr_references, evidence,
    constraints, blast_radius, assumptions, rejection_grounds, dependencies,
    definition_of_done

Excluded, each for a stated reason:

``priority``
    Re-orderable without re-approval. Scheduling is not scope.

``state``
    Changes by design; including it would invalidate the digest on the first
    legitimate transition.

assumption ``resolution`` / ``resolution_evidence``
    Written *after* approval, by the receiver. Including them would mean the act
    of checking an assumption broke the approval that required it.

envelope fields other than ``work_id`` and ``version``
    Timestamps and actors describe the record, not the work.

Two properties this file exists to guarantee
--------------------------------------------
**Versioned canonicalisation.** ``CANONICAL_FORM_VERSION`` is an input to the
digest. The day the serialisation rules change silently is the day every stored
approval becomes unverifiable, with no error to announce it.

**Domain separation.** The payload carries an artifact-kind marker, so a digest
over a WorkOrder can never be replayed as a digest over some other artifact that
happened to canonicalise identically. The platform's hashing layer applies its
own separation tag on top of this one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from backend.contracts.approval import HashAlgorithm, PayloadDigest
from backend.platform.hashing import compute_digest, digests_match

if TYPE_CHECKING:  # pragma: no cover - typing only
    from backend.contexts.workorder.domain.work_order import WorkOrder

__all__ = [
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
    "digest_payload",
    "compute_work_order_digest",
    "digest_matches",
]

#: Domain-separation marker. Distinct from every other artifact kind.
ARTIFACT_KIND: Final[str] = "cortexprime.engineering.workorder"

#: Version of the rules below. Changing what is included, excluded, or how it is
#: ordered is a breaking change and must increment this.
CANONICAL_FORM_VERSION: Final[int] = 1

#: The fields the digest covers, in the order they are written.
GOVERNED_FIELDS: Final[tuple] = (
    "work_id",
    "version",
    "intent",
    "acceptance_criteria",
    "adr_references",
    "evidence",
    "constraints",
    "blast_radius",
    "assumptions",
    "rejection_grounds",
    "dependencies",
    "definition_of_done",
)


def _sorted_strings(values) -> list:
    """Sets are unordered; a digest is not.

    Sorting is what makes two WorkOrders with the same content hash the same
    regardless of the order a caller happened to build their sets in.
    """
    return sorted(str(v) for v in values)


def _assumption_payload(assumption) -> dict:
    """Only the parts of an assumption that were approved.

    ``resolution`` and ``resolution_evidence`` are deliberately absent: they are
    written after approval, and including them would mean checking an assumption
    invalidated the approval that demanded the check.
    """
    return {
        "assumption_id": str(assumption.assumption_id),
        "statement": assumption.statement,
        "verification_method": assumption.verification_method,
    }


def _rejection_ground_payload(ground) -> dict:
    return {
        "ground_id": str(ground.ground_id),
        "condition": ground.condition,
        "rejection_type": ground.rejection_type.value,
        "triggering_assumption": (
            str(ground.triggering_assumption) if ground.triggering_assumption else None
        ),
    }


def _blast_radius_payload(radius) -> dict:
    return {
        "allowed": _sorted_strings(radius.allowed),
        "forbidden": _sorted_strings(radius.forbidden),
        "read_only": _sorted_strings(radius.read_only),
        "justification": radius.justification,
    }


def digest_payload(work_order: "WorkOrder") -> dict[str, Any]:
    """The exact structure the digest is computed over.

    Exposed rather than kept private so a verifier can recompute it, inspect it,
    and say precisely which field diverged -- rather than reporting only that two
    hex strings differ, which tells an investigator nothing.
    """
    return {
        "__artifact__": ARTIFACT_KIND,
        "__canonical_form__": CANONICAL_FORM_VERSION,
        "work_id": str(work_order.work_id),
        "version": work_order.version,
        "intent": work_order.intent,
        "acceptance_criteria": sorted(work_order.acceptance_criteria),
        "adr_references": _sorted_strings(work_order.adr_references),
        "evidence": _sorted_strings(work_order.evidence),
        "constraints": _sorted_strings(work_order.constraints),
        "blast_radius": _blast_radius_payload(work_order.blast_radius),
        "assumptions": sorted(
            (_assumption_payload(a) for a in work_order.assumptions),
            key=lambda item: item["assumption_id"],
        ),
        "rejection_grounds": sorted(
            (_rejection_ground_payload(g) for g in work_order.rejection_grounds),
            key=lambda item: item["ground_id"],
        ),
        "dependencies": _sorted_strings(work_order.dependencies),
        "definition_of_done": sorted(work_order.definition_of_done),
    }


def compute_work_order_digest(
    work_order: "WorkOrder", algorithm: HashAlgorithm = HashAlgorithm.SHA256
) -> PayloadDigest:
    """Hash the governed fields."""
    return compute_digest(digest_payload(work_order), algorithm)


def digest_matches(work_order: "WorkOrder", expected: PayloadDigest) -> bool:
    """Whether the WorkOrder still hashes to ``expected``.

    Recomputes with the *expected* digest's algorithm rather than the current
    default, so an algorithm upgrade does not retroactively invalidate every
    approval already on record.
    """
    return digests_match(compute_work_order_digest(work_order, expected.algorithm), expected)
