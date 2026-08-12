"""Model proposals, ports, and the deterministic evidence-selection policy.

The model PROPOSES (hypotheses, a discriminating test, an interpretation); the
platform DECIDES. A proposal is a typed value with a producer label and a digest;
it carries no authority. The evidence-selection policy validates a proposed test
deterministically — it must discriminate a known hypothesis, have falsifiable
outcomes, name a tool from the frozen read-only allowlist, be non-redundant, and
carry no URL/shell/provider/credential. The governed read and the model call are
reached only through ports supplied by composition (never imported here).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Protocol

from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantRef
from backend.platform.hashing import compute_digest

__all__ = [
    "ProposedHypothesis",
    "ProposedTest",
    "ProposedPrediction",
    "InvestigationProposal",
    "EvidenceRequest",
    "EvidenceResult",
    "ValidatedTest",
    "TestRejected",
    "ModelProposalFailed",
    "ModelSchemaRejected",
    "ModelTraceUnavailable",
    "ModelProviderUnavailable",
    "EvidenceSelectionPolicy",
    "ModelProposalPort",
    "WorldReadPort",
    "EvidenceAcquisitionPort",
    "test_identity",
]


class TestRejected(ContractViolation):
    """A proposed investigation test was refused (purposeless, non-falsifiable,
    redundant, undeclared tool, or attempting more than a governed read)."""


class ModelProposalFailed(RuntimeError):
    """The governed model boundary could not produce an admissible proposal.
    Carries a category so the engine classifies the step honestly (never turns a
    model/trace/provider failure into investigation success)."""

    def __init__(self, category: str, reason: str) -> None:
        super().__init__(f"{category}: {reason}")
        self.category = category
        self.reason = reason


class ModelSchemaRejected(ModelProposalFailed):
    """Model output failed strict schema validation — malformed/oversized/extra
    fields. The proposal never existed; no state pretends success."""

    def __init__(self, reason: str) -> None:
        super().__init__("schema_violation", reason)


class ModelTraceUnavailable(ModelProposalFailed):
    """The pre-action model-proposal trace could not be committed (L14).
    Fail closed: without attribution-grade evidence the proposal may not advance
    to a governed read."""

    def __init__(self, reason: str) -> None:
        super().__init__("trace_unavailable", reason)


class ModelProviderUnavailable(ModelProposalFailed):
    """The model provider was unavailable / timed out / authentication failed.
    Investigation state does not change; the step is classified BLOCKED."""

    def __init__(self, reason: str) -> None:
        super().__init__("provider_unavailable", reason)


@dataclass(frozen=True)
class ProposedHypothesis:
    hypothesis_ref: str
    proposition: str
    subject_ref: str
    temporal_fit: str = "unknown"


@dataclass(frozen=True)
class ProposedTest:
    """What the model proposes to test. It names a TOOL (a key) and subject/
    predicate references — never a URL, shell, provider, or connector. The
    supports/contradicts expectations make the test falsifiable."""

    discriminates_hypothesis: str
    tool: str
    subject_ref: str
    predicate: str
    evidence_expected: str
    supports_if: str
    contradicts_if: str
    residual_uncertainty: str
    # Structured expectation the platform compares the observed value against —
    # deterministic, never a model verdict.
    supports_value: Any = None
    contradicts_value: Any = None


@dataclass(frozen=True)
class InvestigationProposal:
    """One validated model proposal. A model may suggest a conclusion, but it has
    NO authority — the platform decides from evidence.

    ``proposed_tests`` (Phase 8.4) lets the model offer several candidate tests; the
    platform selects the most discriminating admissible one (``differential.select_test``).
    ``proposed_test`` is the legacy single-test field — the engine considers both,
    so the platform always owns the choice, never the model's ordering."""

    provider: str
    proposal_digest: str
    interpretation: str = ""
    proposed_hypotheses: tuple[ProposedHypothesis, ...] = ()
    proposed_test: Optional[ProposedTest] = None
    proposed_tests: tuple[ProposedTest, ...] = ()
    suggested_conclusion: Optional[str] = None   # advisory only; never authoritative

    def candidate_tests(self) -> tuple[ProposedTest, ...]:
        """All proposed tests, de-duplicated by identity — the candidate pool the
        platform selects from. The model proposes; the platform decides."""
        seen: set = set()
        out: list[ProposedTest] = []
        for t in tuple(self.proposed_tests) + (
            (self.proposed_test,) if self.proposed_test is not None else ()
        ):
            key = test_identity(discriminates=t.discriminates_hypothesis, tool=t.tool,
                                subject_ref=t.subject_ref, predicate=t.predicate)
            if key in seen:
                continue
            seen.add(key)
            out.append(t)
        return tuple(out)


@dataclass(frozen=True)
class EvidenceRequest:
    """A governed READ request the platform maps to a capability. Read-only by
    construction — there is no write field."""

    tool: str
    subject_ref: str
    predicate: str
    read_only: bool = True


@dataclass(frozen=True)
class EvidenceResult:
    """The outcome of a governed read: an observation reference and the observed
    world value (or an explicit failure). Never a model self-report.

    ``execution_ref`` (Phase 8.5) is the real governed-execution id that produced
    the observation — it anchors any Outcome the World Plane derives, so an outcome
    is grounded in a real execution, never in model text."""

    ok: bool
    subject_ref: str
    predicate: str
    observation_ref: Optional[str] = None
    fact_ref: Optional[str] = None
    observed_value: Any = None
    source_ref: Optional[str] = None
    execution_ref: Optional[str] = None
    reason: str = ""


@dataclass(frozen=True)
class ProposedPrediction:
    """A model-proposed falsifiable prediction (Phase 8.5). A forward claim about
    an observable future world value tied to a hypothesis — never a confidence
    number, never an outcome, never a self-declared success. The platform validates
    the structure and the platform (not the model) later compares it to reality."""

    hypothesis_ref: str
    subject_ref: str
    predicate: str
    expected: Any                 # the structured observation expected (not a number-as-confidence)
    expected_condition: str       # human-readable falsifiable condition
    evaluation_window_seconds: int = 300
    provider: str = "scripted"    # platform-stamped identity, never model-supplied


@dataclass(frozen=True)
class ValidatedTest:
    discriminates_hypothesis: str
    tool: str
    subject_ref: str
    predicate: str
    supports_value: Any
    contradicts_value: Any
    request: EvidenceRequest


def test_identity(*, discriminates: str, tool: str, subject_ref: str, predicate: str) -> str:
    """Deterministic identity for redundancy detection."""
    return compute_digest(
        {"discriminates": discriminates, "tool": tool,
         "subject_ref": subject_ref, "predicate": predicate}).value[:16]


class EvidenceSelectionPolicy:
    """Deterministically validates a proposed test before any governed read."""

    def validate(
        self, *, investigation, proposed: ProposedTest,
        available_tools: tuple[str, ...],
    ) -> ValidatedTest:
        if not isinstance(proposed, ProposedTest):
            raise TestRejected("a ProposedTest is required")
        # 1. Discriminates a KNOWN hypothesis in the differential.
        known = {h.hypothesis_ref for h in investigation.differential}
        if proposed.discriminates_hypothesis not in known:
            raise TestRejected(
                f"test discriminates unknown hypothesis "
                f"{proposed.discriminates_hypothesis!r}; not in the differential")
        # 2. Falsifiable: both a support and a contradict outcome must be stated.
        if not (proposed.supports_if.strip() and proposed.contradicts_if.strip()):
            raise TestRejected("a test must have both a support and a contradict outcome")
        if proposed.supports_value is None and proposed.contradicts_value is None:
            raise TestRejected(
                "a test must carry a structured expectation the platform can "
                "compare (supports_value / contradicts_value); a model verdict is "
                "not evidence")
        # 3. Tool is in the frozen read-only allowlist (the model names a key).
        if proposed.tool not in available_tools:
            raise TestRejected(
                f"tool {proposed.tool!r} is not in the exposed read-only allowlist")
        # 4. No smuggled targets: subject/predicate are references, not URLs/shell.
        for name in ("subject_ref", "predicate"):
            v = getattr(proposed, name)
            if not isinstance(v, str) or not v.strip():
                raise TestRejected(f"{name} must be a reference string")
            if any(bad in v.lower() for bad in ("http://", "https://", "$(", "`", ";",
                                                "&&", "|", "../", "\n")):
                raise TestRejected(f"{name} looks like a URL/shell fragment, not a reference")
        # 5. Non-redundant: not already run.
        tid = test_identity(discriminates=proposed.discriminates_hypothesis, tool=proposed.tool,
                            subject_ref=proposed.subject_ref, predicate=proposed.predicate)
        if any(tid in ref for ref in investigation.test_refs):
            raise TestRejected("this exact test was already run (redundant)")
        return ValidatedTest(
            discriminates_hypothesis=proposed.discriminates_hypothesis, tool=proposed.tool,
            subject_ref=proposed.subject_ref, predicate=proposed.predicate,
            supports_value=proposed.supports_value, contradicts_value=proposed.contradicts_value,
            request=EvidenceRequest(tool=proposed.tool, subject_ref=proposed.subject_ref,
                                    predicate=proposed.predicate, read_only=True))


# -- ports (composition supplies the implementations) ----------------------

class ModelProposalPort(Protocol):
    """The governed model boundary seam. The implementation runs the harness
    GovernedModelBoundary against a real or scripted provider and returns a typed
    proposal. ``provider`` on the result is honest ('scripted' when scripted)."""

    def propose(self, *, context, investigation, now: datetime) -> InvestigationProposal:
        ...


class WorldReadPort(Protocol):
    """Read-only World Plane evidence for context assembly (backed by WorldQuery).
    Tenant-scoped, no side effects."""

    def evidence_for(self, *, tenant: TenantRef, subject_ref: str, predicate: str,
                     now: datetime) -> dict:
        ...


class EvidenceAcquisitionPort(Protocol):
    """The governed READ path (backed by composition): governed read -> Observation
    -> Fact -> Belief, returning references. This is the ONLY way the Intelligence
    Plane obtains new world evidence; it never touches a connector itself."""

    def acquire(self, *, tenant: TenantRef, request: EvidenceRequest,
                now: datetime) -> EvidenceResult:
        ...
