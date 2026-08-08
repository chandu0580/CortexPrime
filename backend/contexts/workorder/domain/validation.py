"""Validation rules V1-V10 from Artifact Specification §2.5.

Every rule is implemented. They are not all mechanically decidable, and
pretending otherwise would be worse than saying so -- a validator that claims to
check "criteria are decidable without the implementation" and actually checks
nothing gives false assurance, which is more dangerous than no assurance.

So each rule declares its own **decidability**:

``STRUCTURAL``
    Fully decidable from the WorkOrder alone. Produces ``BLOCKING`` findings.

``RESOLVED``
    Decidable given an injected resolver. Produces ``BLOCKING`` findings.
    Unresolvable references fail closed (EP-6) rather than passing.

``HEURISTIC``
    Detects the mechanical signatures of a violation but cannot decide the
    semantic question. Produces ``ADVISORY`` findings that a human weighs.

Resolvers are injected rather than imported. This context may not import the
Evidence or Governance contexts that own the artifacts being referenced (S2),
and a resolver that silently returned "yes" would turn every reference check
into a formality.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Protocol, runtime_checkable

from backend.contexts.workorder.domain.assumption import AssumptionResolution
from backend.contexts.workorder.domain.work_order import WorkOrder

__all__ = [
    "Decidability",
    "Severity",
    "Finding",
    "ValidationReport",
    "ReferenceResolver",
    "StaticReferenceResolver",
    "validate",
    "UNIVERSAL_CONDITION_MARKERS",
]


class Decidability(str, Enum):
    STRUCTURAL = "structural"
    RESOLVED = "resolved"
    HEURISTIC = "heuristic"


class Severity(str, Enum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"

    @property
    def blocks_approval(self) -> bool:
        return self is Severity.BLOCKING


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: Severity
    decidability: Decidability
    detail: str
    subject: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        where = f" [{self.subject}]" if self.subject else ""
        return f"{self.rule}{where}: {self.detail}"


@dataclass(frozen=True)
class ValidationReport:
    findings: tuple

    @property
    def blocking(self) -> tuple:
        return tuple(f for f in self.findings if f.severity.blocks_approval)

    @property
    def advisory(self) -> tuple:
        return tuple(f for f in self.findings if not f.severity.blocks_approval)

    @property
    def approvable(self) -> bool:
        return not self.blocking

    def rules_fired(self) -> frozenset:
        return frozenset(f.rule for f in self.findings)


# ----------------------------------------------------------------------
# Resolver
# ----------------------------------------------------------------------


@runtime_checkable
class ReferenceResolver(Protocol):
    """Resolves references to artifacts this context does not own.

    Every method answers a yes/no question about an identifier. None of them may
    return "unknown" -- an unresolvable reference is a *no*, and the caller
    reports it as blocking. Allowing a third answer would let a missing resolver
    quietly become a passing check.
    """

    def adr_exists(self, reference: str) -> bool: ...
    def adr_is_superseded(self, reference: str) -> bool: ...
    def evidence_exists(self, reference: str) -> bool: ...
    def evidence_is_stale(self, reference: str) -> bool: ...
    def constraint_is_enforceable(self, reference: str) -> bool: ...


@dataclass(frozen=True)
class StaticReferenceResolver:
    """A resolver over explicitly supplied sets.

    Everything not named is unknown, and unknown resolves to *not present*. There
    is deliberately no permissive mode: a resolver that answered "yes" by default
    would make V4, V5, and V9 unfalsifiable, and an unfalsifiable check is
    indistinguishable from no check.
    """

    known_adrs: frozenset = frozenset()
    superseded_adrs: frozenset = frozenset()
    known_evidence: frozenset = frozenset()
    stale_evidence: frozenset = frozenset()
    enforceable_constraints: frozenset = frozenset()

    def adr_exists(self, reference: str) -> bool:
        return reference in self.known_adrs

    def adr_is_superseded(self, reference: str) -> bool:
        return reference in self.superseded_adrs

    def evidence_exists(self, reference: str) -> bool:
        return reference in self.known_evidence

    def evidence_is_stale(self, reference: str) -> bool:
        return reference in self.stale_evidence

    def constraint_is_enforceable(self, reference: str) -> bool:
        return reference in self.enforceable_constraints


# ----------------------------------------------------------------------
# Heuristic signatures
# ----------------------------------------------------------------------

#: Markers that an "intent" states two outcomes rather than one (V1).
_MULTI_INTENT = (
    re.compile(r";"),
    re.compile(r"\band then\b", re.IGNORECASE),
    re.compile(r"[.!?]\s+\S"),  # a second sentence
)

#: Markers that an acceptance criterion has leaked implementation detail (V2).
_IMPLEMENTATION_LEAK = (
    (re.compile(r"\w+\("), "names a function call"),
    (re.compile(r"\b\w+\.py\b"), "names a source file"),
    (re.compile(r"\bclass\s+[A-Z]\w+"), "names a class"),
    (re.compile(r"\breturns?\s+an?\s+[A-Z]\w+"), "names a return type"),
)

#: Phrases from the universal merge conditions (V10). A definition_of_done that
#: restates one is either redundant or -- worse -- a weakened restatement that
#: reads as authoritative.
UNIVERSAL_CONDITION_MARKERS = (
    "architecture gate",
    "gate is green",
    "tests pass",
    "review",
    "verification record",
    "founder",
    "merge",
    "blast radius",
    "codeowners",
)


# ----------------------------------------------------------------------
# Rules
# ----------------------------------------------------------------------


def _v1_single_intent(work_order: WorkOrder) -> list:
    findings = []
    for pattern in _MULTI_INTENT:
        if pattern.search(work_order.intent):
            findings.append(
                Finding(
                    rule="V1",
                    severity=Severity.ADVISORY,
                    decidability=Decidability.HEURISTIC,
                    detail=(
                        "intent appears to state more than one outcome; if it needs two "
                        "sentences it is two WorkOrders"
                    ),
                    subject=work_order.intent[:60],
                )
            )
            break
    return findings


def _v2_criteria_are_implementation_independent(work_order: WorkOrder) -> list:
    findings = []
    for criterion in sorted(work_order.acceptance_criteria):
        for pattern, reason in _IMPLEMENTATION_LEAK:
            if pattern.search(criterion):
                findings.append(
                    Finding(
                        rule="V2",
                        severity=Severity.ADVISORY,
                        decidability=Decidability.HEURISTIC,
                        detail=(
                            f"acceptance criterion {reason}, so it cannot be tested "
                            "without reading the implementation it describes"
                        ),
                        subject=criterion[:60],
                    )
                )
                break
    return findings


def _v3_assumptions_have_rejection_grounds(work_order: WorkOrder) -> list:
    findings = []
    for assumption in work_order.assumptions:
        if not work_order.grounds_for(assumption.assumption_id):
            findings.append(
                Finding(
                    rule="V3",
                    severity=Severity.BLOCKING,
                    decidability=Decidability.STRUCTURAL,
                    detail=(
                        "assumption has no rejection ground; an unverified belief with "
                        "no refusal path is how a false premise reaches production"
                    ),
                    subject=str(assumption.assumption_id),
                )
            )
    return findings


def _v4_evidence_resolves(work_order: WorkOrder, resolver: ReferenceResolver) -> list:
    findings = []
    for reference in sorted(str(e) for e in work_order.evidence):
        if not resolver.evidence_exists(reference):
            findings.append(
                Finding(
                    rule="V4",
                    severity=Severity.BLOCKING,
                    decidability=Decidability.RESOLVED,
                    detail="evidence reference does not resolve",
                    subject=reference,
                )
            )
        elif resolver.evidence_is_stale(reference):
            findings.append(
                Finding(
                    rule="V4",
                    severity=Severity.BLOCKING,
                    decidability=Decidability.RESOLVED,
                    detail=(
                        "evidence is stale: it was true at a commit no longer in the "
                        "base, so it cannot support a current decision"
                    ),
                    subject=reference,
                )
            )
    return findings


def _v5_adrs_resolve(work_order: WorkOrder, resolver: ReferenceResolver) -> list:
    findings = []
    for reference in sorted(str(a) for a in work_order.adr_references):
        if not resolver.adr_exists(reference):
            findings.append(
                Finding(
                    rule="V5",
                    severity=Severity.BLOCKING,
                    decidability=Decidability.RESOLVED,
                    detail="ADR reference does not resolve",
                    subject=reference,
                )
            )
        elif resolver.adr_is_superseded(reference):
            findings.append(
                Finding(
                    rule="V5",
                    severity=Severity.BLOCKING,
                    decidability=Decidability.RESOLVED,
                    detail=(
                        "ADR is superseded; a WorkOrder governed by a dead decision is "
                        "ungoverned"
                    ),
                    subject=reference,
                )
            )
    return findings


def _v6_blast_radius(work_order: WorkOrder, repository_paths: Optional[Iterable[str]]) -> list:
    # Structural validity is enforced by BlastRadius.__post_init__ -- an invalid
    # radius cannot be constructed, so there is nothing to report here. What
    # remains needs the repository.
    if repository_paths is None:
        return []
    return [
        Finding(
            rule="V6",
            severity=Severity.BLOCKING,
            decidability=Decidability.RESOLVED,
            detail=detail,
        )
        for detail in work_order.blast_radius.validate_against_paths(repository_paths)
    ]


def _v7_no_dependency_cycle(
    work_order: WorkOrder, dependency_graph: Optional[dict]
) -> list:
    """Cycle detection needs every other WorkOrder, so the graph is injected.

    Self-dependency (V8) is caught in the aggregate; this covers cycles of
    length two and above.
    """
    if dependency_graph is None:
        return []

    start = str(work_order.work_id)
    graph = dict(dependency_graph)
    graph[start] = {str(d) for d in work_order.dependencies}

    seen: set = set()
    stack: list = [(start, (start,))]
    while stack:
        node, path = stack.pop()
        for nxt in sorted(graph.get(node, ())):
            if nxt == start:
                return [
                    Finding(
                        rule="V7",
                        severity=Severity.BLOCKING,
                        decidability=Decidability.RESOLVED,
                        detail=(
                            "dependency cycle: "
                            + " -> ".join(path + (nxt,))
                            + "; neither WorkOrder can ever leave Approved"
                        ),
                        subject=start,
                    )
                ]
            if nxt not in seen:
                seen.add(nxt)
                stack.append((nxt, path + (nxt,)))
    return []


def _v8_no_self_dependency(work_order: WorkOrder) -> list:
    # Structurally impossible -- the aggregate refuses construction. Present so
    # the rule is visibly implemented rather than silently absent.
    return []


def _v9_constraints_enforceable(work_order: WorkOrder, resolver: ReferenceResolver) -> list:
    return [
        Finding(
            rule="V9",
            severity=Severity.BLOCKING,
            decidability=Decidability.RESOLVED,
            detail=(
                "constraint does not resolve to an enforceable rule; an unenforceable "
                "constraint is prose, and prose does not block a merge"
            ),
            subject=reference,
        )
        for reference in sorted(str(c) for c in work_order.constraints)
        if not resolver.constraint_is_enforceable(reference)
    ]


def _v10_done_does_not_restate_universal(work_order: WorkOrder) -> list:
    findings = []
    for condition in sorted(work_order.definition_of_done):
        lowered = condition.lower()
        for marker in UNIVERSAL_CONDITION_MARKERS:
            if marker in lowered:
                findings.append(
                    Finding(
                        rule="V10",
                        severity=Severity.ADVISORY,
                        decidability=Decidability.HEURISTIC,
                        detail=(
                            f"definition_of_done appears to restate the universal merge "
                            f"condition about {marker!r}; universal conditions cannot be "
                            "waived or weakened here, and a restatement that drifts from "
                            "them reads as authoritative"
                        ),
                        subject=condition[:60],
                    )
                )
                break
    return findings


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------


def validate(
    work_order: WorkOrder,
    *,
    resolver: ReferenceResolver,
    repository_paths: Optional[Iterable[str]] = None,
    dependency_graph: Optional[dict] = None,
) -> ValidationReport:
    """Run every rule and return the full report.

    Returns all findings rather than raising on the first. Fixing them one
    round-trip at a time is how a Draft takes six approvals to land.

    ``repository_paths`` and ``dependency_graph`` are optional because they need
    a repository and a working tree, which the domain does not have. Omitting
    them **skips** V6's path checks and V7 -- and a caller approving a WorkOrder
    must supply both. The application service does; see
    ``WorkOrderService.approve``.
    """
    if not isinstance(resolver, ReferenceResolver):
        raise TypeError(
            "resolver must satisfy ReferenceResolver; validation cannot fall back to "
            "assuming references resolve"
        )

    findings: list = []
    findings += _v1_single_intent(work_order)
    findings += _v2_criteria_are_implementation_independent(work_order)
    findings += _v3_assumptions_have_rejection_grounds(work_order)
    findings += _v4_evidence_resolves(work_order, resolver)
    findings += _v5_adrs_resolve(work_order, resolver)
    findings += _v6_blast_radius(work_order, repository_paths)
    findings += _v7_no_dependency_cycle(work_order, dependency_graph)
    findings += _v8_no_self_dependency(work_order)
    findings += _v9_constraints_enforceable(work_order, resolver)
    findings += _v10_done_does_not_restate_universal(work_order)

    # An assumption already resolved to something other than CONFIRMED must not
    # pass approval. This is not one of V1-V10; it is the consequence of the
    # assumption machinery existing at all.
    for assumption in work_order.blocking_assumptions:
        findings.append(
            Finding(
                rule="ASSUMPTION",
                severity=Severity.BLOCKING,
                decidability=Decidability.STRUCTURAL,
                detail=(
                    f"assumption resolved {assumption.resolution.value!r}; work may not "
                    "proceed on a belief that was checked and did not hold"
                ),
                subject=str(assumption.assumption_id),
            )
        )

    return ValidationReport(findings=tuple(findings))
