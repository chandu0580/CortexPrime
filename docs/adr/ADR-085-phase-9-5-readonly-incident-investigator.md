# ADR-085 — Phase 9.5: The read-only Kubernetes incident investigator

**Status:** Accepted
**Date:** 2026-09-04
**Extends:** ADR-071 (intelligence boundary), ADR-072–079 (Phase 8), ADR-081–084.

## Context

Phase 8 built an investigation engine: a deterministic OODA loop with a governed
model boundary, differential diagnosis, prediction, independent assurance and
controlled autonomy. Phases 9.2–9.4 built the evidence: governed Kubernetes reads,
a continuous watch, and a second observability source with honest lineage.

Nothing had ever connected them against a real incident.

## Decision 1 — Build the missing port, not a new investigator

Discovery (docs/PHASE_9_5_IMPLEMENTATION_MAP.md §1) found the loop already
implements this phase's lifecycle line for line, including the parts most easily
got wrong: `_reuse_existing_evidence` already refuses STALE/CONFLICTED/UNKNOWN
evidence, `select_test` is already platform-owned, `settle` already produces an
honest terminal read with residual uncertainty, and the proposal schema already
rejects every authority field.

What was missing was one thing: **`EvidenceAcquisitionPort` had no production
implementation.** Its docstring has carried the strongest claim in the codebase
since Phase 8 — *"This is the ONLY way the Intelligence Plane obtains new world
evidence; it never touches a connector itself"* — and every phase from 8.2 to 8.8
satisfied it with a stub inside its own harness. The claim was true of the design
and untested in production code.

This is the **third and last** instance of that pattern:

| Port | Production adapter added in |
|---|---|
| observation mapping | 9.3 — `GovernedReadObserver` |
| `WorldReadPort` | 9.4 — `WorldQueryEvidencePort` |
| **`EvidenceAcquisitionPort`** | **9.5 — `GovernedEvidenceAcquisition`** |

With it closed, the investigation loop composes from production code end to end
for the first time.

## Decision 2 — Read-only is a property of assembly, not a runtime check

`ToolRegistry` looks every tool's operation up in the composed catalogs **at
construction** and refuses to assemble if any is not `SideEffectClass.READ`. A
deployment holding a tool that could write cannot start; therefore no
investigation can select one. There is no branch to forget and no flag to set
wrongly.

`EvidenceRequest` reinforces it from the other side: `tool`, `subject_ref`,
`predicate`, `read_only` — and no field through which a write could be described.

The harness verifies the stronger fact directly: **no catalog composed in the
investigator's process declares a single write operation.**

## Decision 3 — The model names a tool key and nothing else

The model's entire vocabulary is five keys. It does not name a capability, a
provider, an endpoint, a query, a path or a URL, because it does not know they
exist. `GovernedEvidenceAcquisition` holds the only mapping from key to
capability, and that mapping is data supplied at composition.

`EvidenceSelectionPolicy` then refuses, before any provider is contacted: an
unknown hypothesis, a non-falsifiable test, a test with no structured
expectation, a tool outside the allowlist, a subject or predicate containing a
URL/shell fragment, and a redundant repeat.

A subject of the wrong *kind* is refused too — a deployment tool handed a pod
reference would answer about the wrong object, which is worse than refusing.

## Decision 4 — Seed the differential; do not let the model choose the competitors

The five CrashLoopBackOff hypotheses are seeded OPEN with stated evidence gaps.
This is deliberate. A model that proposes only the right answer is
indistinguishable from a model that guessed, and neither is an investigation. The
platform starts with competitors that must be *eliminated by evidence*.

`temporal_fit` starts UNKNOWN for all of them and stays there until an
observation says otherwise: asserting that a hypothesis fits the incident's
timeline before observing the timeline is the assumption this apparatus exists to
avoid.

## Decision 5 — The misleading hypothesis is real, and eliminated by two origins

H4 (resource exhaustion) is not a straw man. The staged workload has a real 64Mi
memory limit and really crashloops; suspecting an OOM kill is correct practice.

It is eliminated by evidence from **two different origins**:

- the Kubernetes API: `lastExitCode: 1`, `lastTerminationReason: "Error"` — not
  the 137/`OOMKilled` a kernel OOM produces;
- the kubelet's cAdvisor, scraped through Prometheus: working-set memory of
  ~2.7 MB against a 64 MB limit. cAdvisor measures the container runtime
  directly, so this is not the API server agreeing with itself.

Two new normalizer lifts made this possible, both declared and bounded:
`lastState.terminated.exitCode`/`.reason` on `pod.get`, and the revision
annotation plus container image on `deployment.get`. `kubernetes.pod.get` and
`kubernetes.deployment.get` were declared in 9.1 and are only now real-exposed —
which is the point of declaring a contract ahead of exposing it.

## Decision 6 — The report computes no verdict

`assemble_report` reads state: the differential, the evidence with its lineage,
the corroboration assessment, the Assurance verdict, and `settle()`'s residual
uncertainty. A report that could reach its own conclusion would be a second
opinion competing with the engine's, and the whole point is that there is one.

One correction was needed: `settle()` always says *"not Assurance-verified"*,
because at Phase 8.4 that was always true. Once Assurance has run, leaving the
phrase would understate what the platform knows and deleting it would overstate
it — so the report names the verdict either way, and says explicitly when
Assurance did **not** support the conclusion.

## Decision 7 — Freshness horizons stated for the investigator's predicates

An investigator that cannot tell fresh evidence from old cannot refuse to reuse
the old, and refusing is the behaviour that matters. The deployment's freshness
policy now states horizons for `pod_state`, `last_termination`, `memory_pressure`
and `deployed_revision` — with a longer horizon for a deployment's revision, which
changes only when somebody deploys, than for a pod's phase, which changes second
to second while it crashloops.

## Decision 8 — No new fitness rule

`BND-INTELLIGENCE-CANNOT-EXECUTE`, `BND-INTELLIGENCE-CANNOT-BYPASS-WORLD`,
`BND-WORLD-CANNOT-EXECUTE`, `BND-DIRECT-HTTP` and `BND-PROVIDER-SDK` already make
Intelligence→provider impossible. "Investigation cannot perform writes" is
stronger than a fitness rule here: it is a construction-time refusal plus a
contract with no write field. A rule would restate what assembly already prevents.

## Decision 9 — The model provider is scripted, and labelled

`[BLOCKED]` The real provider remains unavailable while Phase 5.5 holds. The
proposer is scripted and labelled `provider="scripted"` everywhere.

That boundary is where it should be for what this phase claims. A scripted
proposer weakens *"an LLM generates good hypotheses"* — a claim this phase does
not make — and weakens nothing about *"the platform never lets a model's claim
become truth"*, which is the claim it does make and which is verified
independently at every step. The **evidence** path is entirely real.

## Consequences

- CortexPrime can investigate a real CrashLoopBackOff, hold five competing
  explanations, eliminate the plausible wrong one on evidence from an independent
  instrument, support another, and state plainly what it still does not know.
- The last of the three harness-only ports is closed; the loop is composable from
  production code.
- Two more governed Kubernetes reads are real-exposed, with the termination and
  revision facts a differential actually turns on.
- No remediation, no writes, no second authority, no new rule, no migration.
- Autonomy stays A1: `permits_action()` is False, and nothing in this phase can
  raise it.
