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
from backend.intelligence.application.differential import (
    analyze_gaps,
    select_test,
    settle,
)
from backend.intelligence.application.investigation_service import InvestigationService
from backend.intelligence.application.proposal import (
    EvidenceResult,
    EvidenceSelectionPolicy,
    ModelProviderUnavailable,
    ModelSchemaRejected,
    ModelTraceUnavailable,
    ProposedTest,
    TestRejected,
    test_identity,
)

__all__ = ["InvestigationBudget", "StepOutcome", "StepResult", "InvestigationEngine"]


@dataclass(frozen=True)
class InvestigationBudget:
    """Explicit deterministic budgets. When exhausted, the loop terminates.

    ``max_steps`` bounds model proposals (one per step) and ``max_reads`` bounds
    governed reads. Phase 11.3 adds the two an unattended runner needs:
    ``max_seconds`` of wall clock (enforced by the runner between steps, since the
    engine itself takes injected instants) and ``max_tokens`` of model usage
    (enforced by the proposal port, which is the only place usage is known).
    Neither is a target; both are ceilings past which the loop settles on the
    evidence it has and says so.
    """

    max_steps: int = 8
    max_reads: int = 12
    context: ContextBudget = ContextBudget()
    max_seconds: Optional[float] = None
    max_tokens: Optional[int] = None


class StepOutcome(str, __import__("enum").Enum):
    ADVANCED = "advanced"          # a test ran, evidence acquired, differential updated
    NO_TEST = "no_test"            # the model proposed no valid test this step
    TEST_REJECTED = "test_rejected"  # the proposed test was refused by policy
    TERMINATED = "terminated"      # a terminal conclusion was reached
    EVIDENCE_ABSENT = "evidence_absent"  # the read succeeded; the instrument reported nothing for the subject


@dataclass(frozen=True)
class StepResult:
    outcome: StepOutcome
    investigation: Investigation
    context_digest: str
    provider: str
    reason: str = ""
    evidence_ref: Optional[str] = None
    gaps: tuple = ()   # deterministic evidence-gap analysis for this step (Part C)


class InvestigationEngine:
    """Runs the investigation loop over the durable state machine, using ports for
    the model, the world read, and governed evidence acquisition."""

    def __init__(
        self, *, service: InvestigationService, assembler: ContextAssembler,
        model_port, evidence_port, world_read_port, policy: EvidenceSelectionPolicy,
        harness_version: str, available_tools: tuple[str, ...],
        produced_by: str = "intelligence:engine/1", experience_port=None,
        compatible: Optional[Callable[[str, str], bool]] = None,
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
        # Phase 11.3: a declared compatibility between hypotheses (composition
        # supplies it; None means every pair competes, the pre-11.3 rule).
        self._compatible = compatible
        # Optional (Phase 8.6): prior-investigation experience, injected into the
        # model's context as clearly-labelled HISTORY — never current world truth.
        self._experience = experience_port

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

        # ORIENT: assemble a deterministic, digest-stamped context, including any
        # relevant HISTORICAL experience (labelled as history, not world truth).
        experience = self._retrieve_experience(investigation, now)
        context = self._assembler.assemble(
            investigation=investigation, world_evidence=world_evidence,
            available_tools=self._tools, harness_version=self._harness_version,
            now=now, budget=budget.context, historical_experience=experience)

        # PROPOSE: the model proposes through the governed boundary. Failures are
        # classified honestly — a model/trace/provider failure never becomes
        # investigation success (Part H/I).
        try:
            proposal = self._model.propose(context=context, investigation=investigation, now=now)
        except (ModelTraceUnavailable, ModelProviderUnavailable) as exc:
            # Pre-action fail-closed (L14): no attribution-grade evidence, or no
            # provider — cannot advance to a governed read. BLOCKED.
            concluded = self._svc.conclude(
                investigation=investigation, conclusion=InvestigationConclusion.BLOCKED,
                cause=f"model boundary: {exc.category}", now=now)
            return StepResult(StepOutcome.TERMINATED, concluded, context.context_digest,
                              "unknown", reason=exc.category)
        except ModelSchemaRejected as exc:
            # Malformed/oversized/smuggled output: the proposal never existed. A
            # step is consumed (budget), no state pretends success.
            inv = self._svc.checkpoint(investigation=investigation, now=now, steps_delta=1)
            return StepResult(StepOutcome.TEST_REJECTED, inv, context.context_digest,
                              "unknown", reason=f"model output rejected: {exc.reason}")

        inv = investigation
        # Record proposed hypotheses (platform records them as reasoning artifacts).
        # A new OPEN hypothesis with no evidence carries an explicit evidence gap so
        # the context and gap analysis can say WHY it is unresolved (Part C).
        for ph in proposal.proposed_hypotheses:
            if ph.hypothesis_ref not in {h.hypothesis_ref for h in inv.differential}:
                inv = self._svc.upsert_hypothesis(
                    investigation=inv, now=now, hypothesis=DifferentialHypothesis(
                        hypothesis_ref=ph.hypothesis_ref, subject_ref=ph.subject_ref,
                        proposition=ph.proposition, status=HypothesisStatus.OPEN,
                        temporal_fit=_temporal(ph.temporal_fit),
                        missing_evidence=(f"observation:{ph.subject_ref}",),
                        created_by=f"{proposal.provider}:model"))

        gaps = tuple(g.to_dict() for g in analyze_gaps(inv))

        # DECIDE: the platform selects the most discriminating admissible test from
        # the model's candidate(s) (Part D/N) — the model never dictates the order.
        selection = select_test(candidates=proposal.candidate_tests(),
                                 investigation=inv, available_tools=self._tools)
        if selection.chosen is None:
            # No admissible discriminating test remains. Settle honestly (Part P):
            # the leading hypothesis (if any) with its residual uncertainty named —
            # never a fabricated resolution, never FALSE for the open alternatives,
            # never a claim of Assurance verification.
            summary = settle(inv, compatible=self._compatible)
            concluded = self._svc.conclude(
                investigation=inv, conclusion=InvestigationConclusion(summary.conclusion),
                cause=summary.residual_uncertainty, now=now)
            return StepResult(StepOutcome.TERMINATED, concluded, context.context_digest,
                              proposal.provider, reason=summary.residual_uncertainty, gaps=gaps)
        chosen = selection.chosen
        try:
            validated = self._policy.validate(
                investigation=inv, proposed=chosen, available_tools=self._tools)
        except TestRejected as exc:
            inv = self._svc.checkpoint(investigation=inv, now=now, steps_delta=1)
            return StepResult(StepOutcome.TEST_REJECTED, inv, context.context_digest,
                              proposal.provider, reason=str(exc), gaps=gaps)

        # EVIDENCE REUSE (Part F): if the World Plane already holds admissible, fresh
        # evidence for this subject/predicate, reuse it — no second governed read.
        # STALE / CONFLICTED / UNKNOWN are never reused (freshness != truth, conflict
        # is preserved, unknown is not evidence); those fall through to a fresh read.
        reused = self._reuse_existing_evidence(inv, validated, now)
        if reused is None and inv.reads_taken >= budget.max_reads:
            concluded = self._svc.conclude(
                investigation=inv, conclusion=InvestigationConclusion.INSUFFICIENT_EVIDENCE,
                cause="read budget exhausted", now=now)
            return StepResult(StepOutcome.TERMINATED, concluded, context.context_digest,
                              proposal.provider, reason="max_reads reached", gaps=gaps)

        # record the test (with a deterministic identity for redundancy detection)
        tid = test_identity(discriminates=validated.discriminates_hypothesis, tool=validated.tool,
                            subject_ref=validated.subject_ref, predicate=validated.predicate)
        test = InvestigationTest(
            test_ref=f"wtest-{tid}", investigation_ref=inv.investigation_ref, tenant=inv.tenant,
            discriminates_hypothesis=validated.discriminates_hypothesis,
            evidence_expected=chosen.evidence_expected, supports_if=chosen.supports_if,
            contradicts_if=chosen.contradicts_if, residual_uncertainty=chosen.residual_uncertainty,
            created_by=f"{proposal.provider}:model",
            provenance=ProvenanceRef(produced_by=self._produced_by,
                                     parent_claim_ref=inv.investigation_ref))
        inv, _ = self._svc.add_test(investigation=inv, test=test, now=now)

        if reused is not None:
            result, did_read = reused, False
        else:
            # GOVERNED READ: acquire evidence (the ONLY new world contact, via port).
            result = self._evidence.acquire(tenant=inv.tenant, request=validated.request, now=now)
            did_read = True
            if not result.ok and getattr(result, "absent", False):
                # Phase 11.3 (ADR-123 D-15): the world was asked and answered
                # "nothing about this subject". No observation exists to link;
                # the hypothesis keeps its status and its stated gap; the test
                # stays recorded so the plan does not ask again; the read is
                # spent. The investigation continues on what else can be read.
                inv = self._svc.checkpoint(investigation=inv, now=now, steps_delta=1, reads_delta=1)
                return StepResult(StepOutcome.EVIDENCE_ABSENT, inv, context.context_digest,
                                  proposal.provider, reason=f"evidence absent: {result.reason}", gaps=gaps)
            if not result.ok:
                concluded = self._svc.conclude(
                    investigation=inv, conclusion=InvestigationConclusion.BLOCKED,
                    cause=f"evidence acquisition failed: {result.reason}", now=now)
                return StepResult(StepOutcome.TERMINATED, concluded, context.context_digest,
                                  proposal.provider, reason="evidence blocked", gaps=gaps)

        # link the observation and update the differential from the OBSERVED value.
        refs = tuple(r for r in (result.observation_ref, result.fact_ref) if r)
        if refs:
            inv = self._svc.link_evidence(investigation=inv, evidence_refs=refs, now=now)
        inv = self._update_differential(inv, validated, result, now)

        # CHECKPOINT: durable, budget-advancing (a reuse does not spend read budget).
        inv = self._svc.checkpoint(investigation=inv, now=now, steps_delta=1,
                                   reads_delta=1 if did_read else 0)

        # TERMINATE?
        terminal = self._maybe_conclude(inv, now)
        reason = "differential updated" if did_read else "differential updated (evidence reused)"
        if terminal is not None:
            return StepResult(StepOutcome.TERMINATED, terminal, context.context_digest,
                              proposal.provider, reason=terminal.conclusion.value,
                              evidence_ref=result.observation_ref, gaps=gaps)
        return StepResult(StepOutcome.ADVANCED, inv, context.context_digest,
                          proposal.provider, reason=reason,
                          evidence_ref=result.observation_ref, gaps=gaps)

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

    def _retrieve_experience(self, investigation: Investigation, now: datetime) -> tuple[dict, ...]:
        """Retrieve relevant prior-investigation experience (Phase 8.6). Returns
        clearly-labelled HISTORICAL context dicts; the current investigation must
        still acquire its own fresh evidence — experience is never current truth."""
        if self._experience is None:
            return ()
        from backend.intelligence.application.episode import derive_facets
        matches = self._experience.find_relevant_episodes(
            tenant=investigation.tenant, facets=derive_facets(investigation), now=now,
            exclude_ref=investigation.investigation_ref)
        return tuple(m.to_context_dict() for m in matches)

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

    def _reuse_existing_evidence(self, inv: Investigation, validated, now: datetime):
        """Part F: reuse existing World evidence instead of a new governed read,
        but ONLY when it is concrete (backed by an observation), AFFIRMED, and FRESH.
        STALE/CONFLICTED/UNKNOWN return None (freshness != truth; a conflict is
        preserved, never overwritten; unknown is not evidence). Consumes WorldQuery's
        verdicts (via the world-read port) — it never reclassifies them itself."""
        ev = self._world.evidence_for(tenant=inv.tenant, subject_ref=validated.subject_ref,
                                      predicate=validated.predicate, now=now)
        if not isinstance(ev, dict):
            return None
        evidence_items = ev.get("evidence") or ()
        if not evidence_items:
            return None
        status = str(ev.get("status", "")).lower()
        freshness = str(ev.get("freshness", "")).lower()
        if status != "affirmed" or freshness != "fresh":
            return None
        first = evidence_items[0]
        obs_ref = first.get("observation_id") if isinstance(first, dict) else None
        return EvidenceResult(
            ok=True, subject_ref=validated.subject_ref, predicate=validated.predicate,
            observation_ref=obs_ref, observed_value=ev.get("value"),
            source_ref=ev.get("source_ref"))

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
        # Phase 11.3: structured expectations ({"$in": ...}, {"$gte": ...}, ...)
        # are evaluated by the platform's deterministic matcher; a plain value
        # still means exact equality. Still never a model verdict.
        if validated.supports_value is not None and matches(validated.supports_value, obs):
            new_status = HypothesisStatus.SUPPORTED
            ev_for = tuple(dict.fromkeys(ev_for + (obs_ref,)))
        elif validated.contradicts_value is not None and matches(validated.contradicts_value, obs):
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
            refs = [h.hypothesis_ref for h in supported]
            if self._compatible is not None and all(
                    self._compatible(a, b) for i, a in enumerate(refs) for b in refs[i + 1:]):
                if open_:
                    return None  # composite so far; alternatives still open -- keep testing
                return self._svc.conclude(investigation=inv, conclusion=InvestigationConclusion.RESOLVED,
                                          cause=f"composite explanation affirmed: {refs}", now=now)
            return self._svc.conclude(investigation=inv, conclusion=InvestigationConclusion.CONFLICTED,
                                      cause="multiple hypotheses supported", now=now)
        return None  # keep investigating

    def _budget_conclusion(self, inv: Investigation) -> InvestigationConclusion:
        # One honest terminal read shared with the no-more-tests path (Part P).
        return InvestigationConclusion(settle(inv, compatible=self._compatible).conclusion)


def _temporal(value: str) -> TemporalFit:
    try:
        return TemporalFit(value)
    except ValueError:
        return TemporalFit.UNKNOWN


def _eq(a: Any, b: Any) -> bool:
    return compute_digest(a).value == compute_digest(b).value


from backend.intelligence.application.matching import matches  # noqa: E402 - after helpers
