# ADR-068 — Source Lineage, Governed Belief Policies & Hypothesis/Prediction Contracts

Status: Accepted · Date: 2026-08-12 · Phase 7.6 · Follows ADR-062 through ADR-067

## Context

Phase 7.5 formed beliefs but flagged one limitation: it treated a distinct `source_ref` as independent evidence, when two providers may read the same API, cache, or upstream event. Phase 7.6 fixes that (source lineage), adds a governed "when is a belief sufficiently supported?" policy, and lays the contract boundary for the next Intelligence capabilities (Hypothesis → Prediction → Outcome → Verification) — all without letting a model manufacture epistemic truth. It is a **reasoning-contract phase**: no execution, no new tables.

## Decisions

**1. Source lineage as deterministic config (Part B).** `backend/world/application/lineage.py` — a `LineagePolicy` maps a source to a `SourceLineage(origin_id, relation)` where relation ∈ {DIRECT, DERIVED, MIRRORED, UNKNOWN}. It is the strongest model verifiable from metadata, not perfect causal provenance and **not a numeric trust score**. A source matched by no rule has UNKNOWN lineage. A model does not define lineage.

**2. Lineage-aware corroboration (Part C).** `CorroborationLevel` gains CORRELATED and INDETERMINATE. Independence is proven by **distinct known lineage origins**, not distinct `source_ref`s:
- ≥2 distinct **known** origins agree → INDEPENDENT;
- ≥2 sources agree but share one known origin → CORRELATED (e.g. Prometheus derived from the K8s API — one independent unit);
- ≥2 sources agree but any has UNKNOWN lineage → INDETERMINATE — independence is *not claimed*, because **false certainty is worse than admitting the evidence is insufficient**;
- one source → SINGLE; disagreement → CONTRADICTED; none → INSUFFICIENT.
This supersedes the 7.5 behavior (two distinct `source_ref`s → INDEPENDENT), which was optimistic; the two 7.5 tests encoding it were updated with documented supersession (they now assert INDETERMINATE without lineage, INDEPENDENT with distinct known origins).

**3. Three separate concepts, never collapsed (Part D).** Authority (who has standing), lineage (where evidence originated), corroboration (is there independent support) are distinct. A derived secondary (Prometheus) is retained as an alternative, never counted as independent confirmation, and never overrides the authoritative source — proven: K8s AUTHORITATIVE @10:00 beats a newer Prometheus (derived) @10:05, with Prometheus preserved as contradicting evidence.

**4. Governed belief support policy (Part E).** `belief_policy.py` — a `BeliefSupportPolicy` states an explicit `SupportRequirement` (AUTHORITATIVE / AUTHORITATIVE_OR_INDEPENDENT / INDEPENDENT_REQUIRED) and yields a `BeliefAcceptance` (ACCEPTED / PROVISIONAL / UNMET / NOT_APPLICABLE) — a separate axis from `EpistemicStatus`. **No numeric thresholds, no source weights.** A single authoritative source under INDEPENDENT_REQUIRED is PROVISIONAL, not accepted; two distinct-origin sources are ACCEPTED. The model does not choose the policy; it is versioned, inspectable config.

**5. Belief statuses unchanged (Part F).** UNKNOWN / CONFLICTED / STALE / AFFIRMED are preserved; absence never becomes FALSE; newest-source-wins, majority-vote, and LLM-confidence-as-truth remain forbidden. Acceptance is the new axis, not a new epistemic status.

**6. Hypothesis contract, extended additively (Part G).** `Hypothesis` gains optional `contradiction_refs`, `falsifier`, `investigation_ref` — the structure a testable candidate explanation needs. `HypothesisStatus` still has **no VERIFIED**. Additive fields round-trip through `from_dict`.

**7. Model proposes, platform grounds (Part H).** New `ModelHypothesisProposal` contract (claim + proposed_by + optional subject/suggested_investigation) with **no** `to_hypothesis`/`to_fact`/`to_belief`/`to_verification`. `HypothesisFormation.ground` consumes a proposal **plus real evidence refs** to construct an OPEN `Hypothesis`; a proposal with no subject or no evidence is refused. The model suggests; the platform decides validity.

**8. Prediction / Outcome / Verification distinctions (Part I/J).** `Prediction` gains optional `predicate`/`basis`/`hypothesis_ref`; its `deadline` is the enforced horizon (validated after `predicted_at`). `Outcome` gains optional `prediction_ref` but still **requires a real `execution_ref`** — a model cannot self-author an outcome. `WorldVerification` still requires a procedure and an independent verifier. A prediction is never evidence it came true.

**9. Prediction error, comparison-only (Part K).** `evaluate_prediction(prediction, outcome)` deterministically compares expected vs observed (canonical-digest equality) and checks the horizon, tying the result to the outcome's real `execution_ref`. It is the input a *future* calibration phase will consume — **not a learning engine**: no retraining, reward, self-evolution, policy mutation, or invented numbers.

**10. Firewall extended (Part V).** `BND-MODEL-CANNOT-CREATE-FACT` now also forbids the model planes importing `WorldVerification` and `Outcome` (a genuine new invariant — nothing imported them; CURRENT PASS, synthetic imports FAIL). A model plane may still import the proposal types (`ModelProposal`, `ModelHypothesisProposal`), `Hypothesis`, and `Prediction`. The lineage "no false independence" and "outcome requires execution" invariants are enforced by the corroboration *logic* and the *contract* respectively (proven by tests), not by cosmetic import rules.

**11. Storage — contract-only + derived projections, no table (Part Q).** Lineage and belief policies are deterministic config. Hypothesis/Prediction/Outcome/PredictionEvaluation are reasoning contracts the future Intelligence loop produces. Corroboration and belief remain derived projections that reconstruct from the durable ledgers (proven by deterministic reconstruction after a crash). **No new migration.** Persisting the reasoning trail is deferred to when the Intelligence loop exists and needs to remember its hypotheses across restarts — that is the harness/Intelligence plane's concern, not the World Plane's.

## Explicit non-goals

No numeric trust/confidence/reliability scores, no source counting as authority, no majority-vote truth, no model-created belief/verification/outcome, no prediction-as-evidence, no learning/calibration engine, no execution, no embeddings/vector DB/RAG, no second coordination system, no new table. Exactly-once not claimed.

## Kubernetes decision (Part U)

Phase 7.6 completes without the Kubernetes watch stream and it stays DEFERRED for the 7.4/7.5 reasons — the connector strips `resourceVersion`, has no `.watch()`, and there is no governed K8s read capability; a stream would require fabricated continuity or a second connector (stop conditions). Not implemented, not faked.

## Phase 7.7 boundary

Phase 7.7 may build: the durable reasoning trail (persisting hypotheses/predictions when the Intelligence loop runs), the Assurance Plane's independent verification (turning a hypothesis's investigation into a governed check and minting a `WorldVerification`), numerical calibration (once prediction-vs-outcome history exists), or finer lineage (detecting shared backends between distinct DIRECT sources). The governed Kubernetes watch stream remains the concrete deferred item. The model still cannot manufacture epistemic state; belief/hypothesis/prediction still never execute; exactly-once is still not claimed.
