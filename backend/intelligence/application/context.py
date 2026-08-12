"""Deterministic Context Assembly — the model never chooses its own context.

The harness assembles the model's context from typed sections, in a fixed order,
each with provenance, source, freshness, an inclusion reason, a token budget, and
a content digest. The whole assembly has a ``context_digest`` that is a pure
function of its inputs: the same investigation + the same world evidence + the
same tools + the same policy + the same harness version produce the same digest —
no arbitrary prompt concatenation, no hidden memory injection, no best-effort
selection. The digest is what the trace records so every model proposal is
reproducible from its context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from backend.contracts.intelligence import Investigation
from backend.platform.hashing import compute_digest

__all__ = [
    "ContextSection",
    "AssembledContext",
    "ContextBudget",
    "ContextAssembler",
    "SECTION_ORDER",
]

#: The fixed, deterministic section order. Lower index = higher priority (kept
#: first, dropped last under budget pressure).
SECTION_ORDER: tuple[str, ...] = (
    "incident",
    "investigation_state",
    "autonomy",
    "policy_constraints",
    "hypotheses",
    "contradicting_evidence",
    "missing_evidence",
    "world_evidence",
    "prior_tests",
    "historical_investigation_experience",
    "available_tools",
    "harness_metadata",
)


def _estimate_tokens(content: Any) -> int:
    """A deterministic, cheap token estimate (chars/4 over the canonical form).
    Not a tokenizer — a stable size budget that never depends on a model."""
    from backend.platform.hashing.canonical import canonical_text
    return (len(canonical_text(content)) + 3) // 4


@dataclass(frozen=True)
class ContextBudget:
    """Explicit, deterministic budgets for one assembly."""

    max_context_tokens: int = 4000
    max_world_evidence_items: int = 20


@dataclass(frozen=True)
class ContextSection:
    section_type: str
    order: int
    content: Any
    provenance: str
    inclusion_reason: str
    token_estimate: int
    digest: str
    source_ref: Optional[str] = None
    freshness: Optional[str] = None
    included: bool = True
    exclusion_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "section_type": self.section_type, "order": self.order,
            "content": self.content, "provenance": self.provenance,
            "inclusion_reason": self.inclusion_reason,
            "token_estimate": self.token_estimate, "digest": self.digest,
            "source_ref": self.source_ref, "freshness": self.freshness,
            "included": self.included, "exclusion_reason": self.exclusion_reason,
        }


@dataclass(frozen=True)
class AssembledContext:
    """The exact context handed to one model proposal, and its digest."""

    investigation_ref: str
    tenant_id: str
    assembled_at: datetime
    harness_version: str
    policy_ref: str
    sections: tuple[ContextSection, ...]
    context_digest: str
    total_tokens: int
    budget: ContextBudget

    @property
    def included_sections(self) -> tuple[ContextSection, ...]:
        return tuple(s for s in self.sections if s.included)

    def to_dict(self) -> dict:
        return {
            "investigation_ref": self.investigation_ref, "tenant_id": self.tenant_id,
            "assembled_at": self.assembled_at.isoformat(),
            "harness_version": self.harness_version, "policy_ref": self.policy_ref,
            "context_digest": self.context_digest, "total_tokens": self.total_tokens,
            "budget": {"max_context_tokens": self.budget.max_context_tokens,
                       "max_world_evidence_items": self.budget.max_world_evidence_items},
            "sections": [s.to_dict() for s in self.sections],
        }


class ContextAssembler:
    """Assembles a deterministic, versioned, digest-stamped context. Pure: no
    model, no I/O, no clock of its own (the caller supplies ``now``)."""

    def _section(self, section_type: str, content: Any, *, provenance: str,
                 inclusion_reason: str, source_ref: Optional[str] = None,
                 freshness: Optional[str] = None) -> ContextSection:
        return ContextSection(
            section_type=section_type, order=SECTION_ORDER.index(section_type),
            content=content, provenance=provenance, inclusion_reason=inclusion_reason,
            token_estimate=_estimate_tokens(content),
            digest=compute_digest(content).value[:16], source_ref=source_ref,
            freshness=freshness)

    def assemble(
        self, *, investigation: Investigation, world_evidence: tuple[dict, ...],
        available_tools: tuple[str, ...], harness_version: str, now: datetime,
        budget: Optional[ContextBudget] = None,
        historical_experience: tuple[dict, ...] = (),
    ) -> AssembledContext:
        """``world_evidence`` is already-fetched structured evidence (from
        WorldQuery/governed reads) — the assembler never fetches; it only orders,
        bounds, and digests. ``historical_experience`` is prior-investigation
        experience (from the experience-retrieval layer), placed in its OWN clearly
        labelled section — never mixed with world facts. Section order and content
        are fully determined by the inputs, so the ``context_digest`` is
        reproducible."""
        budget = budget or ContextBudget()
        # World evidence is bounded deterministically (oldest-first stable slice).
        bounded_evidence = tuple(world_evidence[: budget.max_world_evidence_items])
        dropped = len(world_evidence) - len(bounded_evidence)

        sections: list[ContextSection] = [
            self._section("incident", {"incident_ref": investigation.incident_ref},
                          provenance="platform", inclusion_reason="the incident under investigation"),
            self._section("investigation_state",
                          {"status": investigation.status.value, "seq": investigation.seq,
                           "steps_taken": investigation.steps_taken,
                           "reads_taken": investigation.reads_taken},
                          provenance="investigation-ledger", inclusion_reason="current workflow state",
                          source_ref=investigation.investigation_ref),
            self._section("autonomy", {"autonomy_level": investigation.autonomy_level.value},
                          provenance="platform-policy",
                          inclusion_reason="autonomy is platform-set; the model may not change it"),
            self._section("policy_constraints",
                          {"policy_ref": investigation.policy_ref,
                           "model_may": ["propose hypotheses", "propose a discriminating test",
                                         "propose an evidence request", "interpret evidence"],
                           "model_may_not": ["create fact/belief/outcome/verification",
                                             "change status/autonomy", "execute", "select a URL/shell/provider"]},
                          provenance="platform-policy", inclusion_reason="the model proposal boundary"),
            self._section("hypotheses",
                          [{"hypothesis_ref": h.hypothesis_ref, "proposition": h.proposition,
                            "status": h.status.value, "temporal_fit": h.temporal_fit.value,
                            "evidence_for": list(h.evidence_for),
                            "evidence_against": list(h.evidence_against),
                            "missing_evidence": list(h.missing_evidence),
                            "contradiction_refs": list(h.contradiction_refs)}
                           for h in investigation.differential],
                          provenance="investigation-ledger",
                          inclusion_reason="the competing hypotheses to discriminate"),
            self._section("contradicting_evidence",
                          sorted({r for h in investigation.differential for r in h.contradiction_refs}),
                          provenance="investigation-ledger",
                          inclusion_reason="evidence that contradicts a hypothesis (never hidden)"),
            self._section("missing_evidence",
                          sorted({r for h in investigation.differential for r in h.missing_evidence}),
                          provenance="investigation-ledger",
                          inclusion_reason="evidence gaps the next test should close"),
            self._section("world_evidence", list(bounded_evidence),
                          provenance="world-plane",
                          inclusion_reason=(f"world facts/beliefs backing the differential"
                                            + (f" ({dropped} dropped by budget)" if dropped else "")),
                          freshness="see per-item freshness"),
            self._section("prior_tests", list(investigation.test_refs),
                          provenance="investigation-ledger",
                          inclusion_reason="tests already run (avoid redundant tests)"),
            self._section("historical_investigation_experience", list(historical_experience),
                          provenance="experience-memory",
                          inclusion_reason=("prior investigations of similar situations — "
                                            "HISTORICAL EXPERIENCE, never current world truth; "
                                            "acquire fresh evidence before relying on it"),
                          freshness="historical (see per-episode episode_time)"),
            self._section("available_tools", sorted(available_tools),
                          provenance="tool-exposure",
                          inclusion_reason="the frozen read-only tool allowlist the model may name"),
            self._section("harness_metadata",
                          {"harness_version": harness_version, "assembled_at": now.isoformat()},
                          provenance="harness", inclusion_reason="reproducibility metadata"),
        ]
        sections.sort(key=lambda s: s.order)

        # Deterministic budget enforcement: keep sections in priority order until
        # the token budget is reached; drop the rest with an explicit reason.
        total = 0
        enforced: list[ContextSection] = []
        over = False
        for s in sections:
            if over or total + s.token_estimate > budget.max_context_tokens:
                over = True
                enforced.append(dataclasses_replace(
                    s, included=False, exclusion_reason="context token budget exceeded"))
            else:
                total += s.token_estimate
                enforced.append(s)

        digest = compute_digest(
            [s.to_dict() for s in enforced] + [investigation.tenant.tenant_id, harness_version]
        ).value
        return AssembledContext(
            investigation_ref=investigation.investigation_ref,
            tenant_id=investigation.tenant.tenant_id, assembled_at=now,
            harness_version=harness_version, policy_ref=investigation.policy_ref,
            sections=tuple(enforced), context_digest=digest, total_tokens=total, budget=budget)


def dataclasses_replace(obj, **changes):
    from dataclasses import replace
    return replace(obj, **changes)
