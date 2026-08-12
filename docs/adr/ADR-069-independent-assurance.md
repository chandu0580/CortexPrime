# ADR-069 — Independent Assurance & the Verification Ledger

Status: Accepted · Date: 2026-08-12 · Phase 7.7 · Follows ADR-062 through ADR-068

## Context

Phases 7.1–7.6 built the World Plane (observations → facts → beliefs → hypotheses/predictions) and kept the model unable to mint grounded state. ADR-069 answers the central question: **can CortexPrime independently verify reasoning claims without letting the intelligence plane verify itself?** It introduces the Assurance Plane — a deterministic evaluator that adjudicates claims against evidence it obtains itself from the World Plane and mints a durable `WorldVerification`. The model may propose; it may never certify its own success.

Architecture: `WORLD → INTELLIGENCE → ASSURANCE → HARNESS → GOVERNANCE → EXECUTION`.

## Decisions

**1. A new Assurance Plane, fenced from execution (Part B/S).** `backend/assurance/` is an application-only evaluator. It imports the World read layer (`WorldQuery`) and the epistemic/verification contracts, and — in its infrastructure layer only — the durable store. It imports **no** connector, gateway, transport, credential carrier, scheduler, dispatcher, harness, or computer-use. Enforced by the new `BND-ASSURANCE-CANNOT-EXECUTE` fitness rule (CURRENT PASS; synthetic connector/gateway/harness imports FAIL). Assurance evaluates; it never acts.

**2. Reuse the existing verification vocabulary — no parallel concepts (Part A/F/N).** `Verdict` (SUPPORTED / UNSUPPORTED / INSUFFICIENT_EVIDENCE — the honest three; `permits_autonomous_action` only for SUPPORTED), `VerifierIdentity` (with `reasoning_path_id`, `is_independent_of`, `model_identifier=None` for deterministic verifiers), and `WorldVerification` (requires a procedure + verifier + evidence-for-SUPPORTED) all already exist and are reused verbatim. **No new status was introduced** — INSUFFICIENT_EVIDENCE already carries "we don't know ≠ it's wrong", and there is no FALSE.

**3. Model self-verification is structurally impossible (Part C/G).** Two independent barriers: (a) the import firewall `BND-MODEL-CANNOT-CREATE-FACT` already forbids model planes minting `WorldVerification` (Phase 7.6); (b) the verifier **refuses to adjudicate if its reasoning path equals the claim's producer** (`verifier.is_independent_of(producer)` → `AssuranceRefused`). The platform verifier is deterministic (`model_identifier=None`) with a fixed reasoning path distinct from any model. Crucially, the verifier **never accepts the model's assertion as evidence** — it obtains its own evidence from the World ledgers via `WorldQuery`.

**4. Typed procedures, never model code (Part D).** `VerificationProcedureKind` is a closed enum (COMPARE_WORLD_STATE, COMPARE_PREDICTION_OUTCOME, INSPECT_EXECUTION_RESULT); a `VerificationProcedure` is a typed descriptor of references, not code. The model may name a procedure (a key), never supply Python, shell, SQL, URLs, or imports — the same discipline as harness tool exposure. Adding a procedure is a code + ADR change, never a runtime input.

**5. Failure semantics: verifier failure is never success (Part O).** UNKNOWN world state → INSUFFICIENT_EVIDENCE; CONFLICTED evidence → INSUFFICIENT_EVIDENCE; STALE evidence (under policy) → INSUFFICIENT_EVIDENCE; missing/citation-less evidence → cannot be SUPPORTED. A SUPPORTED verdict requires the independently-obtained evidence to match the claimed value *and* be citable. Timeout/absence/model-confidence never become success.

**6. Independence via lineage, honestly (Part G).** The primary independence is structural (deterministic verifier, evidence from the World not the model). The `AssurancePolicy` may additionally require `require_known_lineage`: if the evidence source's lineage is UNKNOWN, independence cannot be *proven*, so the verdict is INSUFFICIENT_EVIDENCE — no false independence, reusing the Phase 7.6 `LineagePolicy`.

**7. Deterministic, versioned assurance policy — no numbers (Part M).** `AssurancePolicy` is explicit config (require_fresh, require_known_lineage, min_authority tier). No numeric trust scores. The model cannot modify policy; it is versioned and inspectable (`policy_ref`).

**8. Durable verification ledger — the one thing that must persist (Part J/R).** `cw_verification` (migration 0017), append-only, is the first new table since 7.3. **Justification:** corroboration and beliefs are derived projections that reconstruct from the observation/fact ledgers; a *verification* cannot — it adjudicates an ephemeral model claim against the world at a knowledge time, and that decision is an externally-meaningful historical record governance and humans rely on. Nothing in the World ledgers records "the platform verified claim X at time T". It is immutable (a re-check is a new row), tenant-scoped, provenanced, idempotent (unique `identity_digest`, at-least-once, **not exactly-once**), and reconstructable (`WorldVerification.from_dict`). Hypothesis/Prediction/Outcome remain contract-only (reasoning artifacts, not decisions).

**9. Bitemporal correctness & no future leakage (Part K).** The verifier obtains evidence via `WorldQuery.as_of_valid`, honoring valid time and knowledge time. A verification as-known at T does not see observations recorded after T — proven: a value observed at 10:00 but recorded at 10:10 is invisible to a verification known-at 10:05 (→ INSUFFICIENT). `verified_at` (knowledge time of the decision) and `recorded_at` (row write) are stored distinctly.

**10. Tenant isolation, fail closed (Part L).** Every read is tenant-predicated; a cross-tenant verification finds no evidence → INSUFFICIENT; a cross-tenant `get` returns None. No fetch-then-filter.

**11. Outcome/prediction boundary preserved (Part H/I).** An `Outcome` still requires a real `execution_ref` (Phase 7.6, unchanged). A prediction is verified by independently obtaining the world state at/after its horizon and comparing — the verifier never creates the outcome, and a prediction is never evidence it came true. The comparison provides the raw basis a future calibration phase will consume; **no ML, no calibration numbers** here.

## Explicit non-goals

No model-created/model-owned verification, no verifier consuming its own claim as evidence, no numeric confidence/trust, no timeout-as-success, no dynamic/model-authored verifier code, no execution, no embeddings/vector DB/RAG, no second coordination system, no Kubernetes watch. Exactly-once not claimed.

## Kubernetes decision (Part V)

Not implemented; DEFERRED for the 7.4–7.6 reasons (connector strips `resourceVersion`, no `.watch()`, no governed K8s read capability). A future stream must implement LIST→WATCH continuity and 410 recovery, never fake continuity.

## Phase 7.8 boundary

Phase 7.8 may build: outcome/prediction verification wired end to end (independently obtaining the post-execution metric window), the durable reasoning trail (persisting hypotheses/predictions when the Intelligence loop runs), numerical calibration (once verification+outcome history accumulates), or human-verifier identity (a distinct `VerifierIdentity` with a real person, never fabricated). The governed Kubernetes watch stream remains the concrete deferred item. The model still cannot manufacture epistemic state or verification; assurance still never executes; exactly-once is still not claimed.
