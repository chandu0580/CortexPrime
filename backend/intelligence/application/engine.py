"""The Investigation Engine — the platform-controlled OODA loop.

One deterministic step: assemble context -> get a model PROPOSAL through the
governed boundary -> validate it -> record proposed hypotheses -> validate and
run a discriminating governed READ -> update the differential from the OBSERVED
world value (never the model's claim) -> checkpoint -> decide continue/terminate.

The platform controls every transition. The model never changes status/autonomy,
never creates truth, never concludes, and never executes. Budgets bound the loop
so it cannot run forever; termination is deterministic and evidence-based.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Callable, Optional

from backend.contracts.intelligence import (
    DifferentialHypothesis,
    Investigation,
    InvestigationConclusion,
    InvestigationStatus,
    InvestigationTest,
    TemporalFit,
    is_terminal_status,
)
from backend.contracts.world import HypothesisStatus, ProvenanceRef
from backend.platform.hashing import compute_digest
from backend.platform.identity.generators import prefixed_id
from backend.intelligence.application.context import ContextAssembler, ContextBudget
from backend.intelligence.application.investigation_service import InvestigationService
from backend.intelligence.application.proposal import (
    EvidenceSelectionPolicy,
    ProposedTest,
    TestRejected,
    test_identity,
)

__all__ = ["InvestigationBudget", "StepOutcome", "StepResult", "InvestigationEngine"]


@dataclass(frozen=True)
class InvestigationBudget:
    """Explicit deterministic budgets. When exhausted, the loop terminates."""

    max_steps: int = 8
    max_reads: int = 12
    context: ContextBudget = ContextBudget()


class StepOutcome(str, __import__("enum").Enum):
    ADVANCED = "advanced"          # a test ran, evidence acquired, differential updated
    NO_TEST = "no_test"            # the model proposed no valid test this step
    TEST_REJECTED = "test_rejected"  # the proposed test was refused by policy
    TERMINATED = "terminated"      # a terminal conclusion was reached


@dataclass(frozen=True)
class StepResult:
    outcome: StepOutcome
    investigation: Investigation
    context_digest: str
    provider: str
    reason: str = ""
    evidence_ref: Optional[str] = None


class InvestigationEngine:
    """Runs the investigation loop over the durable state machine, using ports for
    the model, the world read, and governed evidence acquisition."""

    def __init__(
        self, *, service: InvestigationService, assembler: ContextAssembler,
        model_port, evidence_port, world_read_port, policy: EvidenceSelectionPolicy,
        harness_version: str, available_tools: tuple[str, ...],
        produced_by: str = "intelligence:engine/1",
    ) -> None:
        self._svc = service
        self._assembler = assembler
        self._model = model_port
        self._evidence = evidence_port
        self._world = world_read_port
        self._policy = policy
        self._harness_version = harness_version
        self._tools = tuple(available_tools)
        self._produced_by = produced_by

    # -- one step -----------------------------------------------------------

    def step(self, *, investigation: Investigation, budget: InvestigationBudget,
             now: datetime) -> StepResult:
        if is_terminal_status(investigation.status):
            return StepResult(StepOutcome.TERMINATED, investigation, "", "n/a",
                              reason=f"already {investigation.status.value}")

        # Budget: stop before over-spending. INSUFFICIENT is honest, not FALSE.
        if investigation.steps_taken >= budget.max_steps:
            concluded = self._svc.conclude(
                investigation=investigation, conclusion=self._budget_conclusion(investigation),
                cause="step budget exhausted", now=now)
            return StepResult(StepOutcome.TERMINATED, concluded, "", "n/a",
                              reason="max_steps reached")

        # OBSERVE: gather current world evidence for the differential's subjects.
        world_evidence = self._gather_world_evidence(investigation, now)

        # ORIENT: assemble a deterministic, digest-stamped context.
        context = self._assembler.assemble(
            investigation=investigation, world_evidence=world_evidence,
            available_tools=self._tools, harness_version=self._harness_version,
            now=now, budget=budget.context)

        # PROPOSE: the model proposes through the governed boundary.
        proposal = self._model.propose(context=context, investigation=investigation, now=now)

        inv = investigation
        # Record proposed hypotheses (platform records them as reasoning artifacts).
        for ph in proposal.proposed_hypotheses:
            if ph.hypothesis_ref not in {h.hypothesis_ref for h in inv.differential}:
                inv = self._svc.upsert_hypothesis(
                    investigation=inv, now=now, hypothesis=DifferentialHypothesis(
                        hypothesis_ref=ph.hypothesis_ref, subject_ref=ph.subject_ref,
                        proposition=ph.proposition, status=HypothesisStatus.OPEN,
                        temporal_fit=_temporal(ph.temporal_fit),
                        created_by=f"{proposal.provider}:model"))

        # DECIDE: validate a discriminating test; refuse a bad one.
        if proposal.proposed_test is None:
            inv = self._svc.checkpoint(investigation=inv, now=now, steps_delta=1)
            return StepResult(StepOutcome.NO_TEST, inv, context.context_digest,
                              proposal.provider, reason="no test proposed",)
        try:
            validated = self._policy.validate(
                investigation=inv, proposed=proposal.proposed_test, available_tools=self._tools)
        except TestRejected as exc:
            inv = self._svc.checkpoint(investigation=inv, now=now, steps_delta=1)
            return StepResult(StepOutcome.TEST_REJECTED, inv, context.context_digest,
                              proposal.provider, reason=str(exc))

        # read budget guard
        if inv.reads_taken >= budget.max_reads:
            concluded = self._svc.conclude(
                investigation=inv, conclusion=InvestigationConclusion.INSUFFICIENT_EVIDENCE,
                cause="read budget exhausted", now=now)
            return StepResult(StepOutcome.TERMINATED, concluded, context.context_digest,
                              proposal.provider, reason="max_reads reached")

        # record the test (with a deterministic identity for redundancy detection)
        tid = test_identity(discriminates=validated.discriminates_hypothesis, tool=validated.tool,
                            subject_ref=validated.subject_ref, predicate=validated.predicate)
        test = InvestigationTest(
            test_ref=f"wtest-{tid}", investigation_ref=inv.investigation_ref, tenant=inv.tenant,
            discriminates_hypothesis=validated.discriminates_hypothesis,
            evidence_expected=proposal.proposed_test.evidence_expected,
            supports_if=proposal.proposed_test.supports_if,
            contradicts_if=proposal.proposed_test.contradicts_if,
            residual_uncertainty=proposal.proposed_test.residual_uncertainty,
            created_by=f"{proposal.provider}:model",
            provenance=ProvenanceRef(produced_by=self._produced_by,
                                     parent_claim_ref=inv.investigation_ref))
        inv, _ = self._svc.add_test(investigation=inv, test=test, now=now)

        # GOVERNED READ: acquire evidence (the ONLY new world contact, via the port).
        result = self._evidence.acquire(tenant=inv.tenant, request=validated.request, now=now)
        if not result.ok:
            concluded = self._svc.conclude(
                investigation=inv, conclusion=InvestigationConclusion.BLOCKED,
                cause=f"evidence acquisition failed: {result.reason}", now=now)
            return StepResult(StepOutcome.TERMINATED, concluded, context.context_digest,
                              proposal.provider, reason="evidence blocked")

        # link the observation and update the differential from the OBSERVED value.
        refs = tuple(r for r in (result.observation_ref, result.fact_ref) if r)
        if refs:
            inv = self._svc.link_evidence(investigation=inv, evidence_refs=refs, now=now)
        inv = self._update_differential(inv, validated, result, now)

        # CHECKPOINT: durable, budget-advancing.
        inv = self._svc.checkpoint(investigation=inv, now=now, steps_delta=1, reads_delta=1)

        # TERMINATE?
        terminal = self._maybe_conclude(inv, now)
        if terminal is not None:
            return StepResult(StepOutcome.TERMINATED, terminal, context.context_digest,
                              proposal.provider, reason=terminal.conclusion.value,
                              evidence_ref=result.observation_ref)
        return StepResult(StepOutcome.ADVANCED, inv, context.context_digest,
                          proposal.provider, reason="differential updated",
                          evidence_ref=result.observation_ref)

    def run(self, *, investigation: Investigation, budget: InvestigationBudget,
            clock: Callable[[int], datetime]) -> Investigation:
        """Run steps until a terminal conclusion or budget exhaustion. ``clock``
        maps a step index to an injected timestamp (deterministic, no wall clock)."""
        inv = investigation
        i = 0
        while not is_terminal_status(inv.status):
            res = self.step(investigation=inv, budget=budget, now=clock(i))
            inv = res.investigation
            i += 1
            if i > budget.max_steps + 2:  # hard backstop
                break
        return inv

    # -- internals ----------------------------------------------------------

    def _gather_world_evidence(self, investigation: Investigation, now: datetime) -> tuple[dict, ...]:
        seen = set()
        out = []
        for h in investigation.differential:
            key = (h.subject_ref,)
            if key in seen:
                continue
            seen.add(key)
            ev = self._world.evidence_for(tenant=investigation.tenant,
                                          subject_ref=h.subject_ref, predicate="state", now=now)
            if ev:
                out.append(ev)
        return tuple(out)

    def _update_differential(self, inv: Investigation, validated, result, now: datetime) -> Investigation:
        """Deterministic: compare the OBSERVED value to the test's structured
        expectation. Support -> the discriminated hypothesis SUPPORTED; contradict
        -> REFUTED. Never a model verdict."""
        target = next((h for h in inv.differential
                       if h.hypothesis_ref == validated.discriminates_hypothesis), None)
        if target is None:
            return inv
        obs = result.observed_value
        new_status = target.status
        ev_for = target.evidence_for
        ev_against = target.evidence_against
        obs_ref = result.observation_ref or "obs"
        if validated.supports_value is not None and _eq(obs, validated.supports_value):
            new_status = HypothesisStatus.SUPPORTED
            ev_for = tuple(dict.fromkeys(ev_for + (obs_ref,)))
        elif validated.contradicts_value is not None and _eq(obs, validated.contradicts_value):
            new_status = HypothesisStatus.REFUTED
            ev_against = tuple(dict.fromkeys(ev_against + (obs_ref,)))
        updated = replace(target, status=new_status, evidence_for=ev_for, evidence_against=ev_against)
        return self._svc.upsert_hypothesis(investigation=inv, hypothesis=updated, now=now)

    def _maybe_conclude(self, inv: Investigation, now: datetime) -> Optional[Investigation]:
        supported = [h for h in inv.differential if h.status is HypothesisStatus.SUPPORTED]
        open_ = [h for h in inv.differential if h.status is HypothesisStatus.OPEN]
        if len(supported) == 1 and not open_:
            return self._svc.conclude(investigation=inv, conclusion=InvestigationConclusion.RESOLVED,
                                      cause=f"single hypothesis affirmed: {supported[0].hypothesis_ref}",
                                      now=now)
        if len(supported) >= 2:
            return self._svc.conclude(investigation=inv, conclusion=InvestigationConclusion.CONFLICTED,
                                      cause="multiple hypotheses supported", now=now)
        return None  # keep investigating

    def _budget_conclusion(self, inv: Investigation) -> InvestigationConclusion:
        supported = [h for h in inv.differential if h.status is HypothesisStatus.SUPPORTED]
        if len(supported) == 1:
            return InvestigationConclusion.RESOLVED
        if not inv.differential:
            return InvestigationConclusion.INSUFFICIENT_EVIDENCE
        return InvestigationConclusion.UNRESOLVED


def _temporal(value: str) -> TemporalFit:
    try:
        return TemporalFit(value)
    except ValueError:
        return TemporalFit.UNKNOWN


def _eq(a: Any, b: Any) -> bool:
    return compute_digest(a).value == compute_digest(b).value
