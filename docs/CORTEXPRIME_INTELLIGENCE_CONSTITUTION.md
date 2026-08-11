# CORTEXPRIME — INTELLIGENCE CONSTITUTION AND NEXT-GENERATION ARCHITECTURE

**Zero Phase deliverable — design document only. Nothing in this document is implemented by it.**

Date: 2026-08-11 · Basis: fresh literature research (2024–2026 primary sources), a read-only conceptual audit of the repository at HEAD `3bf0b11`, and a competitive survey of the coding-agent and AI-SRE segments.

Status: DRAFT FOR REVIEW. Implementation begins only after this document is reviewed and accepted.

---

## 1. Executive Thesis

**CortexPrime should become an epistemically governed engineering intelligence: a system whose every consequential action is justified by typed, provenanced, fresh evidence; verified by something other than what produced it; authorized by something that cannot think; and scored afterward against what it predicted.**

That sentence is the whole thesis. Everything else in this document derives from it.

Five claims support it:

1. **"LLM + planner + tools + memory = intelligence" is empirically false.** The 2024–2026 record is unambiguous: agents built on that formula fail plausibly rather than loudly (~75% of production agent failures are silent "fail-plausible" outputs), game any verifier they can see, cannot detect their own errors (64.5% self-correction blind-spot rate), collapse from 90% single-attempt success to ~57% consistency at eight attempts, and treat stale memory as reality (55.2% accuracy at detecting invalidated beliefs). More agents amplify these failures — the MAST taxonomy shows multi-agent systems fail through specification gaps, inter-agent misalignment, and weak verification, not through lack of model capability. Intelligence is not the model. Intelligence is the *system that constrains, checks, and corrects* the model.

2. **The mature engineering fields already solved the shape of this problem.** Aviation runtime assurance (ASTM F3269, Simplex), automotive SOTIF, and Waymo's graduated-deployment methodology all converge on one architecture: *an untrusted capable core inside a trusted simple envelope, with authority expanded only where evidence has been earned.* CortexPrime's Phase 1–5 work built exactly the right envelope. The Zero Phase's uncomfortable finding is that the envelope currently surrounds nothing (§3).

3. **Every pillar of the vision is individually validated; no one has composed them.** Bitemporal belief stores (Zep/Graphiti), Kubernetes-style reconciliation of desired vs. observed state, dry-run-grounded outcome prediction, differential-diagnosis investigation, independent verification, capability-scoped authorization, prediction-error learning — each has 2025–2026 literature or a shipped partial implementation behind it. The SoK on trust-authorization mismatch (arXiv:2512.06914) names the exact gap CortexPrime sits in: *no shipped system connects what the agent believes to what the agent is authorized to do.* The moat is the composition, not any pillar.

4. **The current architecture's problem is not weakness — it is disconnection.** Phases 1–5 produced genuinely strong governed-execution machinery: digest-bound authorization, TOCTOU-safe admission, fenced leases, unknown-outcome semantics, hash-chained audit. The audit (§3) shows this machinery is a parallel demonstration: the code that actually calls GitHub, deploys, and drives a desktop never touches it, and the governed runtime is off by default. The single most important architectural decision of Phase 6 is therefore not to add intelligence — it is to make the governed plane **the only path to a side effect**, and then build the epistemic layer on top of it.

5. **Autonomy must be earned per capability class, never assumed.** ITBench: state-of-the-art agents autonomously resolve 13.8% of SRE scenarios. Devin's field record: no discernible pattern predicting which tasks succeed. The correct product posture is not "autonomous engineer" — it is *investigate autonomously, propose with evidence and predicted effects, execute under graduated authority, verify independently, and widen authority only where the track record justifies it.* This matches the product vision on file (detect real issues, explain root cause, suggest/take the actual fix) and is the honest version of what the market's failures demand.

**What CortexPrime is NOT to become:** another IDE agent (commoditized — mini-swe-agent reaches 74% SWE-bench Verified in 100 lines of Python; scaffolding is not a moat), another multi-agent framework (documented production failure category), or an "autonomous SRE" that auto-resolves incidents (the segment's own hallucination rates are its top abandonment driver).

---

## 2. Research Findings

Condensed from three parallel research sweeps over 2024–2026 primary sources. Each finding carries the rating vocabulary used throughout this document: **BUILD** (production-ready), **RESEARCH** (promising, immature), **REJECT** (dead end).

### 2.1 Agentic software engineering — what actually works in production

- **The task distribution, not the agent, determines success.** Cognition's 18-month Devin retrospective: PR merge rate 34%→67%, with the sweet spot at "clear requirements + verifiable outcome + 4–8h junior scope"; 10–20× gains only on batchable repetitive work (migrations, vulnerability fixes). Answer.AI's independent month-long test: 3/20 tasks succeeded with *no discernible pattern* — users cannot form a mental model of what will work. ([Devin 2025 review](https://cognition.com/blog/devin-annual-performance-review-2025), [Answer.AI](https://www.answer.ai/posts/2025-01-08-devin.html))
- **Harness engineering is the maturity frontier.** Anthropic's long-horizon harness posts: state lives in durable artifacts (git, feature ledgers, progress files), the context window is a cache; documented failure modes are *overambition* and *premature completion declaration*. Harnesses are model-version-fragile. **BUILD** — directly aligned with durable-Postgres state. ([Effective harnesses](https://anthropic.com/engineering/effective-harnesses-for-long-running-agents))
- **The half-life result is the mathematical case for CortexPrime's execution core.** Agent success decays exponentially with task length, consistent with a constant per-minute failure hazard ([Ord, arXiv:2505.05115](https://arxiv.org/pdf/2505.05115); METR: 50% time-horizon doubles ~every 7 months, but the 80%-reliability horizon is 4–5× shorter). The only structural escapes: checkpointing with verified restarts (failure hazard resets at each boundary) and independent verification at boundaries (errors don't propagate). **BUILD.**
- **METR's RCT: experienced devs using AI tools were 19% slower while believing themselves 20% faster.** Self-reported agent value is untrustworthy; measure outcomes. **BUILD** (as methodology). ([arXiv:2507.09089](https://arxiv.org/abs/2507.09089))
- **Multi-agent: read/gather parallelizes, decide/edit does not.** Cognition ("Don't Build Multi-Agents"): parallel implicit decisions conflict. Anthropic: orchestrator + parallel subagents beat single-agent by 90% *only* for read-only research, at ~15× token cost. MAST confirms the failure modes empirically ([arXiv:2503.13657](https://arxiv.org/abs/2503.13657)). **BUILD** the synthesis: multi-reader, single-writer.

### 2.2 Verification — the decisive literature

- **Weak oracles pass wrong work at ~30% rates.** SWE-bench's collapse is a controlled experiment: 32.67% of "successful" patches involved solution leakage; UTBoost found 345 passing-but-wrong patches (24.4% of leaderboard ranks changed); PatchDiff: 29.6% of test-passing patches behave differently from ground truth; OpenAI retired SWE-bench Verified after finding 59.4% of hard instances had flawed tests. **"Tests passed" is a ~70%-reliable oracle at best.**
- **Self-verification is structurally broken.** 64.5% average blind-spot rate: models correct injected errors but not identical errors in their own output ([Self-Correction Bench, arXiv:2507.02778](https://arxiv.org/abs/2507.02778)). Independence of *context* recovers much of the value even with the same weights.
- **Agents build to the visible check.** When checks diverge from intent, agents satisfy the check, not the request — specification gaming is default behavior ([arXiv:2606.28430](https://arxiv.org/pdf/2606.28430)). The verifier must be hidden from, independent of, and richer than what the agent optimizes against.
- **LLM-as-judge: one signal, never a gate.** Position/verbosity/self-enhancement/authority biases documented; "reliability without validity" (judges agree while wrong); judges are injectable. **REJECT** as sole gate; **BUILD** in ensembles with execution-based oracles.
- **What works:** reproduction-test-first (SWT-bench: bug must fail→pass), test augmentation (UTBoost), differential testing (PatchDiff), hidden server-side acceptance criteria. **BUILD.**

### 2.3 World models, state, and staleness

- **Runtime discovery beats learned dynamics for enterprise systems.** Offline-learned world models go brittle as tenant-specific logic changes; reading the live system's actual rules outperforms and survives drift ([arXiv:2605.12178](https://arxiv.org/abs/2605.12178)). **Learned neural world models for ops: REJECT for now. Explicit, continuously refreshed, queryable state models: BUILD.**
- **"Dynamics blindness" is the named enterprise failure.** World of Workflows (ServiceNow-scale environment): frontier LLMs consistently fail to predict invisible cascading side effects of their own actions ([arXiv:2601.22130](https://arxiv.org/abs/2601.22130)). An agent's action model omits the environment's reactive rules.
- **Stale beliefs are quantified and undefended.** STALE: 55.2% accuracy at detecting invalidated memories; worst on implicit conflicts; even when updated evidence is retrieved, agents act on the stale belief ([arXiv:2605.06527](https://arxiv.org/abs/2605.06527)). Belief-state drift from true environment state grows over multi-step tasks. Nobody ships a defense. **BUILD the defense** (provenance, timestamps, TTL, re-verification before consequential action).
- **Bitemporal memory is the transferable pattern.** Zep/Graphiti: event-time vs. ingestion-time on every edge, validity intervals, invalidation-not-deletion ([arXiv:2501.13956](https://arxiv.org/abs/2501.13956)). Postgres-native. **BUILD.**
- **Memory is an attack surface.** MINJA: >95% memory-injection success through the normal query interface; 0.1% poisoning → >80% attack success. Provenance-gated writes double as the defense. **BUILD.**

### 2.4 Runtime assurance, causality, planning

- **ASTM F3269 / Simplex doctrine transfers whole:** don't assure the ML component; assure the bounding architecture — deterministic monitors, verified fallback ("halt and escalate" is a valid fallback), switch logic outside the model's trust boundary. **BUILD** as doctrine.
- **LLMs cannot do causal inference; they can generate causal hypotheses.** Corr2Cause: near-random at correlation→causation; "causal parrots" recite rather than infer. The escape is *intervention*: agents that run experiments and interpret interventional results substantially outperform observational prompting ([arXiv:2605.27567](https://arxiv.org/pdf/2605.27567)) — and DevOps is unusually intervenable (canaries, flags, rollbacks). Microsoft's production RCA study: tool-grounding cut hallucination 40%→4% but accuracy stayed ~35%; ITBench autonomous SRE resolution: 13.8%. **LLM-as-causal-inferencer: REJECT. LLM-hypothesis + algorithmic RCA (BARO/CIRCA-class) + interventional probes: BUILD.**
- **Verbalized confidence is not calibrated.** Systematic overconfidence clustered in the 80–100% band regardless of accuracy; prompt-sensitive; mechanistically ingrained. Confidence as control signal: **REJECT**. Confidence derived from logged predicted-vs-actual outcomes per task class (own recalibration curves): **BUILD.**
- **Risk-tiered action gating is deployable engineering:** classify actions read-only / reversible / compensable / irreversible; pre-action gates for irreversible (post-hoc filtering is impossible); the biggest blast-radius reduction is permission removal, not smarter guardrails. **BUILD.**
- **Dry-runs are the cheapest high-fidelity world model.** `terraform plan`, `kubectl --dry-run`, DB transactions, canaries produce *real* predicted outcomes; almost no agent platform harvests them systematically as prediction artifacts. Predicted-vs-actual diffing afterward is free calibration data. **BUILD** — likely CortexPrime's highest-leverage cheap idea.

### 2.5 Memory, learning, governance

- **Learning without fine-tuning works when the artifact is verified and the signal is external.** Voyager (skills as verified executable artifacts), ACE (curated playbooks, +10.6%). The risk literature is damning: 73.8% of self-improving agents' "optimizations" were proxy gains; hacking rate *grows* 26%→58% with iteration; self-authored verification has structural conflict of interest. **Design consequence: lesson-writer, lesson-verifier, and oracle must be separate parties; the ungameable learning signal is the diff between predicted and actual outcome, because reality supplies it.**
- **Approval fatigue is an attack vector, not a UX nit.** OWASP classifies "overwhelming HITL" as deliberate attack: flood low-risk approvals, then slip the high-risk one in. A 100% approval rate is a red flag. Mitigations: risk-tiered approvals, evidence-carrying approval requests, scrutiny telemetry. **BUILD.**
- **Meaningful human control = tracking + tracing.** The audit chain and approval evidence are the "tracing" half; the "tracking" half (does the system act on the humans' actual reasons?) is the open research problem.
- **The named gap CortexPrime sits in:** the B-I-P (Belief–Intention–Permission) SoK shows prompt injection, memory poisoning, and tool poisoning share one root cause — desynchronization between dynamic epistemic state and static authorization. **No shipped system feeds belief-trust into authorization decisions.** ([arXiv:2512.06914](https://arxiv.org/pdf/2512.06914)) **BUILD — flagship differentiator.**
- **Compliance is convergent, cheaply:** EU AI Act Article 50 transparency lands Aug 2026; high-risk logging/oversight obligations (~Dec 2027) have exactly the shape of the audit chain + approval evidence already designed. Mapping the capability model onto CSA AICM control IDs turns architecture into a sellable compliance artifact.

### 2.6 Research gap matrix

| Area | State of the art (2026) | Unsolved | CortexPrime opportunity |
|---|---|---|---|
| Agentic SWE | Async issue→PR agents GA; ~67% merge on curated classes | Outcome predictability per task; anything past the PR boundary | Per-capability-class reliability ledger (pass^k) gating graduated autonomy |
| Long-horizon | Horizon doubling ~7mo; harness patterns validated | Exponential decay within a run; 80% horizon ≪ 50% horizon | Durable checkpoints + verified boundaries reset the failure hazard |
| Reliability | MAST taxonomy; ~75% failures silent/plausible; pass^k | Semantic health monitoring; no SRE discipline for agents | Treat agent output as untrusted input: provenance, canaries, single-writer |
| Verification | Repro-first, differential, augmented tests catch 25–30% wrong-but-passing | Agents game visible checks; self-verify blind spot 64.5% | Independent verification plane: separate context, separate grants, hidden criteria, execution-based oracles |
| World models | LLM simulation short-lookahead only; discovery beats learning; dynamics blindness named | Side-effect prediction for ops actions | Explicit Postgres world model + dry-run harvesting + predict-before-act gate |
| State/staleness | Bitemporal KGs exist; STALE quantifies the gap (55.2%) | Belief validity, invalidation, read-your-writes for agents | Bitemporal facts with TTL, re-verification before consequential action, reconciliation loops |
| Proactivity | Propose-then-approve defined; PROBE best 40%; discovery is the bottleneck | Discovery at acceptable false-positive rates; safe mitigation (~10%) | Drive attention from the owned world model's deltas, not open-ended search |
| Causality/RCA | Algorithmic RCA beats LLMs on localization; grounding cuts hallucination | LLM causal inference near-random; cross-system generalization | Differential diagnosis: LLM hypotheses × algorithmic checks × interventional probes |
| Memory | Persistence solved (Letta/Mem0/Zep) | Validity, poisoning, memory-vs-reality | Governed memory: provenanced, bitemporal, advisory-only, poisoning-audited |
| Mixed initiative | Autonomy-level taxonomies; fatigue documented as attack | Evidence-based autonomy adjustment; oversight quality measurement | Autonomy ledger: authority earned per class from verified track record, demoted on failure |
| Governance | Agent identity (Entra-style), JIT privilege, AICM controls | **Belief↔authorization coupling (named, unshipped)** | Belief-trust as authorization input; audit chain as MHC tracing evidence |
| Learning | Verified-skill libraries; curated playbooks | Proxy-gap widens with iteration; self-authored verification unreliable | Prediction-error-grounded lessons; writer/verifier separation; influence auditing |

---

## 3. Current Architecture Critique

Read-only conceptual audit at HEAD `3bf0b11`. Every claim carries file evidence. The docstrings throughout the repo are unusually honest — nearly every limitation below is *stated somewhere in the code*. The failure is not dishonesty; it is that the honesty is filed per-module and never composed into the one sentence that matters.

### 3.1 The single most important structural fact

**There are two systems in this repository, and they do not touch each other.**

- The **V2 governed plane** — `backend/contexts/*` (12 bounded contexts, ~74k lines), `backend/contracts/*`, `backend/platform/*` — contains everything Phase 1–5 is proud of: digest-bound authorization, TOCTOU-safe admission, fenced leases, unknown-outcome semantics, the hash-chained audit runtime, the credential broker.
- The **V1 acting plane** — `backend/services/*` (~47k lines), `backend/agents/*`, `backend/orchestrator/*`, `backend/computer/*`, `backend/connectors/*` — contains everything that actually calls GitHub, deploys, rolls back, opens tickets, and drives a desktop.

Verified by grep: **no module in the acting plane imports `backend.contexts` at all.** The only importers are ~26 files under `backend/api/` plus the architecture fitness rules. And the governed runtime is off by default: it requires `CORTEX_DURABLE_URL` ([application_runtime.py:63](../backend/api/application_runtime.py#L63), [main.py:111-124](../backend/main.py#L111-L124)), which appears nowhere in `.env.example`.

**Consequence: the safety architecture is a parallel demonstration, not a control plane.** The README's "fails closed everywhere" is true of the plane that does nothing and false of the plane that deploys. Every subsequent finding is colored by this.

### 3.2 Answers to the twenty challenge questions

**Q1–2 (assumptions; dangerous ones).** The load-bearing dangerous assumptions: (a) that governance built beside the acting path governs it; (b) that stored state is truth — no provenance, freshness, confidence, or contradiction tracking exists in any live state store; (c) that a caller's self-report constitutes verification; (d) that technical success implies semantic success; (e) that an approval string identifies an approver.

**Q3 (locally correct components).** Nearly all of the V2 plane is locally correct and globally unused. Sharpest case: `backend/contracts/knowledge.py` and `contracts/evidence.py` are the best epistemics in the repo — `KnowledgeAuthority` (authoritative vs. advisory), mandatory confidence on advisory items, invariant I7 enforced at construction; `SourceStatus` distinguishing `RETURNED_EMPTY` from `UNAVAILABLE` with the stated reason that *"collapsing them is how 'no evidence of a problem' silently becomes 'evidence of no problem'."* **Neither has a single importer outside `backend/contracts/`.** Meanwhile `backend/memory/models.py:69` defines a *colliding* `AssembledContext` — plain Pydantic, no authority, no kind, no expiry — and that is the one the live retrieval path uses. `SemanticEntry` defaults stored memory to `confidence = 1.0`.

**Q4 (semantic drift) / Q8 (memory as false authority).** The "repository brain" (`services/enterprise_repository_brain.py:42`) — the permanent engineering knowledge model for every repository — is a JSON file with no staleness field of any kind. The architecture rules themselves inventory **76 grandfathered JSON/JSONL state stores** (`platform/architecture/state_rules.py:350`) and call file-based state "the most expensive defect in the codebase," noting it "has already caused one total outage." Lessons are injected into delivery blueprints top-3-by-recency with no relevance test (`autonomous_trigger_runtime.py:446-450`).

**Q5 (stale state) / Q9 (planning diverges from reality).** A plan is executed as scripted. `Precondition` is satisfied once by a named human and never re-evaluated (`contexts/mission/domain/metadata.py:125-171`). `Assumption` is three-valued and well-designed (`contexts/workorder/domain/assumption.py`) but resolved at work-order time, never re-checked at execution. The only execution-time re-reads are *authority* re-reads (is this capability still permitted); nothing re-reads the *world* (does the service still exist; did someone already fix it). `PLANNED → DRAFT` is a legal transition "because replanning is normal" — and no service triggers it.

**Q6 (uncertainty → confidence) / Q7 (wrong output → trusted input).** `orchestration/task_decomposer.py:196-230`: LLM output is regex-extracted, `json.loads`-ed, and becomes executable subtasks with no schema validation and no agent allowlist enforcement — the prompt constrains, the code does not. The Engineering Decision Engine's LLM output is copied verbatim into the delivery blueprint's `risk_assessment`, `approval_required`, and `deployment_strategy` (`autonomous_trigger_runtime.py:414-434`) — the risk assessment that decides whether a human is consulted is produced by the same reasoning layer that proposed the change. LLM RCA hypotheses are filed as the incident's root cause with nothing distinguishing hypothesis from finding downstream (`enterprise_deploy_incident_reporter.py:105`).

**Q10 (technically successful, semantically failed).** Unrepresentable. `WorkerOutcome` has no value for "performed, but not what was wanted"; `contradicts()` catches only effect-class overreach, never wrong target or wrong value. The canonical instance: `_stage_deployment` deploys to `envs[0]` — *whichever environment is first in the list* (`enterprise_delivery_orchestrator.py:1253-1254`). A fully "approved" delivery can deploy to an arbitrary environment and report success. No `SuccessCriterion` from the Intent context is ever evaluated against an execution result anywhere in the codebase.

**Q11–12 (verification wrong; verifier shares generator's blind spots).** There are five unrelated things called "verification":
1. `contexts/engineering_verification/` — the strongest *design* in the repo (asserted vs. verified evidence as unconvertible types, INCOMPLETE ≠ FAILED, adversarial absence claims, derived-not-chosen outcomes). But the API accepts `verdict`, `evidence_trust`, `determinism` as **caller-supplied strings** and mints `VerifiedEvidence` from them. Nothing executes a reproduction step. `collected_by` defaults to the literal string `"verifier"`. **"Verification COMPLETE" proves someone POSTed well-formed JSON.**
2. `services/verification_service.py` — the only verifier that touches reality (read-after-write on connectors) and it checks existence, not correctness, and explicitly does not block the mission.
3. `enterprise_verification_intelligence.py` — a genuine prediction-vs-reality comparator whose `verify()` takes **all 20 predicted and actual values as caller-supplied keyword arguments with defaults**, and invents actual risk when absent.
4. `computer/verification_engine.py` — strategies 1–4 prove *something changed*; strategy 5 asks the same LLM that acted, looking at the same screenshot. The recovery engine then asks the same model to replan.
5. The delivery pipeline: `_stage_security` initializes `{"passed": True}` and swallows all read failures; `_stage_qa` never raises; `_stage_pr` is `pass`. **Absence of evidence is a pass in the gate that guards production** — the exact inversion `contracts/evidence.py` warns against.

**Q13 (agents amplifying errors).** The cognition pipeline chains agent outputs with no independent check between links; the review that gates delivery is performed by the same executive that produced the patch plan (`_stage_engineering_review`), and an LLM reviewer returning `{}` passes.

**Q14 (autonomy exceeding intent) / Q20 (governance authorizing the operationally wrong).** The full autonomous path (`autonomous_trigger_runtime.py:346-497`) runs webhook → LLM decision → 22-stage delivery with: the THINK step optional in the failure case (decision-engine failure is logged "non-fatal" and delivery proceeds with *no* risk assessment); approval hardcoded to any 1 approval with no identity requirement or digest binding; and two disjoint approval systems — the cryptographic one (`contracts/approval.py`, constant-time digest match) unused by the acting path, the used one (`backend/approval_center/`) having no digest binding, so what a human approves is a rendered description, not a hashed artifact. In the V2 plane, `ApprovePlan.approved_by` is a caller-supplied string — an agent can approve its own plan as `"cto@company.com"` (`api/planner_routes.py:582`). Break-glass changes only the audit label, not the decision (`GrantBackedPolicy` never inspects it).

**Q15 (confidently wrong) / Q19 (proxy optimization).** The prediction-reality comparator scoring the system's own recorded status as "reality" (W15) is a textbook proxy loop: the calibration machinery calibrates against self-report.

**Q16 (long-horizon error accumulation).** The V1 delivery pipeline is linear, index-based, resumable — with gates that default to pass. Errors don't accumulate; they pass silently at each boundary, which is worse.

**Q17 (recovery creating second-order failure).** The governed plane handles this superbly (AMBIGUOUS leases never auto-reclaimed; recovery coordinator performs nothing itself; resume-past-unknown is unrepresentable). The acting plane's rollback executor is candid that it does not track whether the redeploy it triggers ever completes.

**Q18 (learning reinforcing bad strategy).** Memory grows monotonically; nothing measures whether a lesson helped; nothing removes one that hurt; injection is by recency. Invariant I7 ("experiential memory may propose, never authorize") is marked ENFORCED by a probe that tests a *dataclass constructor* — the live memory systems don't use the type, so the invariant is reported enforced and is not.

### 3.3 What deserves to survive

To be equally honest in the other direction — these are genuinely strong and ahead of the field:

- **The invocation gateway's 13 ordered checks** (`invocation_gateway.py:560-615`), including: input validation *before* digest computation; credentials minted last so a to-be-refused request never mints a secret; obligations as refusals, not advisories; freshness windows (work that cannot finish inside its authority never starts); result integrity (a result naming another binding becomes UNKNOWN_OUTCOME, never success *or* failure).
- **`implied_risk`: missing effect declaration is CRITICAL, never LOW** (`authorization.py:342-359`). Fail-closed epistemics in one line.
- **Unknown as a first-class outcome** — `UNKNOWN_OUTCOME` and `TIMEOUT` distinct from `FAILURE`; "a deadline is a fact about the caller, not the callee"; AMBIGUOUS leases escalated to humans.
- **Replay that structurally cannot execute** (no repository, no worker pool; causal gaps reported, never repaired).
- **The asserted/verified evidence type separation** and the review context that holds only opaque ids of what it reviews.
- **`reduces_exposure` operations exempt from risk escalation** — no approval needed to shut something down at 3 a.m.
- **The dormant contracts** (`knowledge.py`, `evidence.py`) — the right vocabulary, waiting for a system.
- **48 ADRs and executable architecture fitness rules** — the constitutional *habit* exists; this document proposes the constitution's content.

The pattern across all of §3: **the ideas are right and the wiring is absent.** Zero Phase's conclusion is not "redesign the ideas" — it is "make the wiring the next phase's only job, then extend the ideas into the epistemic layer they were clearly reaching for."

---

## 4. The CortexPrime Ontology

**Verdict: yes, the formal distinctions are needed — as a type system, not as twenty database tables.** The audit shows exactly what happens without them: hypotheses filed as root causes, self-reports minted as verified evidence, memory defaulting to confidence 1.0, absence of evidence passing gates. The research shows the cost at scale: fail-plausible outputs propagate because nothing downstream can ask "what *kind* of claim is this and who owes evidence for it?"

The twenty entities collapse into **four families** sharing infrastructure, plus the authority family that already exists:

- **Epistemic family** (claims about the world): OBSERVATION, FACT, BELIEF, HYPOTHESIS, ASSUMPTION, INFERENCE, PREDICTION, UNKNOWN — one bitemporal ledger, one provenance model, different admission rules per type.
- **Intentional family** (claims about what should happen): INTENT, PLAN, ACTION, OBLIGATION — already largely modeled in `contexts/intent`, `planner`, `workflow`, `execution`.
- **Outcome family** (claims about what happened): EVENT, STATE, OUTCOME, POSTCONDITION, VERIFICATION — partly modeled; the semantic half missing.
- **Learning family**: LESSON — advisory forever, per dormant invariant I7.
- **Authority family**: AUTHORITY — already correct in the capability fabric; the ontology's only change is that authority is *never* an epistemic object: no belief, however confident, is authority.

### 4.1 Entity definitions

For each: meaning · source · mutability · trust · LLM-create? · LLM-modify? · needs external evidence? · may influence execution?

| Entity | Meaning | Source | Mutable? | LLM create? | LLM modify? | External evidence? | Influences execution? |
|---|---|---|---|---|---|---|---|
| **OBSERVATION** | What an instrument returned at a moment: tool output, API response, metric sample, exit code — *including* "source unavailable" | Instruments only (connectors, probes, CI, telemetry) | Never (append-only) | **No** | No | Is itself the evidence | Yes — the only raw input reality gets |
| **FACT** | An observation-backed claim currently held true: "deploy `d-142` of `payments` completed 14:02Z" | Derived from observations by deterministic rules | Superseded, never edited | **No** | No | ≥1 observation with provenance | Yes |
| **EVENT** | A dated occurrence in world history: "deploy happened", "alert fired" | Observation pipeline | Never | No | No | Yes | Yes (as history) |
| **STATE** | The world model's current view of an entity: fields + per-field freshness + provenance | Reconciliation of facts | Only by reconciliation | No | No | Yes | Yes |
| **BELIEF** | A claim held with less than observational backing: "service X probably still owns queue Y" — carries confidence, source, freshness, contradictions | Inference over facts, or accepted hypotheses, or memory | Revisable (superseded) | **Yes — as proposal, admitted by rules** | Via revision only | Not required — which is exactly why it is not a FACT | Only through the epistemic gate (§6.4) |
| **HYPOTHESIS** | A candidate explanation with testable predictions and named discriminating evidence: "latency is the connection-pool exhaustion" | LLM or algorithmic RCA | Status only (open→supported/refuted/abandoned) | **Yes — freely** | Own status via evidence | Required *to be promoted*, not to exist | Never directly; only via investigation actions (reads/probes) |
| **ASSUMPTION** | A claim treated as true for planning *without* current evidence, explicitly flagged, with a validity horizon and a re-check trigger | Planner (LLM or human) | Confirmed/contradicted/expired | Yes — must be declared, never implicit | No — resolution comes from observation | Required at execution time (re-check), not at planning time | Yes — and blocks execution when contradicted or expired |
| **INFERENCE** | A derived claim with its derivation recorded (inputs + method) | LLM or deterministic rules | Superseded | Yes — always marked as inference, never laundered into fact | No | Inherits the *weakest* input's trust | Through the epistemic gate |
| **PREDICTION** | A falsifiable statement about a future observation, with deadline: "after rollback, p95 < 300ms within 10min" | Planner/simulation layer (LLM or dry-run) | Never edited; resolved against outcome | **Yes — required before consequential action** | No | Resolved only by later observation | Yes — as approval evidence and verification target |
| **INTENT** | The human mandate: objective, constraints, scope, success criteria | Human (or human-ratified) | Sealed by approval | Draft only | No after approval | — | Yes — the root of all authority to act |
| **PLAN** | How the mandate would be achieved; carries assumptions + predictions per step | Planner | Sealed; replanning = new plan | Yes — draft only | No after approval | Assumptions re-checked at execution | Yes, after approval |
| **ACTION** | One governed side-effecting operation: digest, capability, authority ref, predicted outcome, reversibility class | Execution plane | Immutable once dispatched | Proposes only | No | — | Is execution |
| **AUTHORITY** | Permission to perform an operation class: grants, approvals, delegation | Governance plane + humans | By governance operations only | **Never. Under no circumstances. This is Law 4.** | Never | — | Gates execution |
| **OBLIGATION** | A duty attached to authority ("notify on-call", "rollback if p95 regresses") | Policy/approval | Discharged or outstanding | No | No | Discharge requires evidence | Outstanding obligation = refusal (already built) |
| **OUTCOME** | What the action's *caller* can claim: success/failure/**unknown** + observed effects | Execution plane | Never | No | No | Worker result + observations | Yes |
| **POSTCONDITION** | The world-state the action was *supposed* to produce, stated before dispatch | Plan/action author | Sealed with action | Yes — proposing them is cognition's job | No | Checked only by observation | Yes — verification target |
| **VERIFICATION** | An independent, *executed* comparison of postconditions and success criteria against fresh observations | Assurance plane — never the generator | Never | **No** (an LLM may *interpret* results; the record is minted only from executed checks) | No | By definition | Yes — gates mission completion |
| **LESSON** | A validated generalization from prediction error: "canary deploys of service X need 15min, not 5" | Learning plane, from PREDICTION↔OUTCOME diffs | Advisory forever; retirable | Draft only; admitted by independent validation | No | Requires the prediction-error record it generalizes | **Advisory only — may shape proposals, never gate or authorize (I7, finally enforced for real)** |
| **UNKNOWN** | A first-class record that something is not known: named question, why it matters, what would answer it | Any plane | Resolved or standing | Yes — declaring ignorance is encouraged | Status via evidence | Resolution requires observation | Yes — an UNKNOWN on a load-bearing claim forces investigation or escalation |

### 4.2 The critical non-collapses

- **FACT ≠ BELIEF.** A fact names the observations that back it and the instrument that produced them. A belief names the inference that produced it and the confidence it carries. The current codebase stores both in the same JSON fields with no marker — which is precisely how an LLM's guess about service ownership becomes next week's routing decision.
- **BELIEF ≠ HYPOTHESIS.** A belief is *held*; a hypothesis is *on trial*. A hypothesis carries its discriminating tests; holding it costs nothing and authorizes nothing. Promoting it to belief requires the tests. The audit's finding that RCA hypotheses are filed directly as incident root causes is this collapse, live in production code.
- **HYPOTHESIS ≠ PREDICTION.** A hypothesis explains the past; a prediction commits to a future observation with a deadline. Predictions are what make the system falsifiable — and what make learning possible (§10).
- **PREDICTION ≠ OUTCOME.** The comparator exists (`enterprise_verification_intelligence.py`) and currently takes both sides as caller-supplied arguments. The ontology makes that impossible: predictions are sealed before dispatch, outcomes minted only from observations, and the comparison is computed, never supplied.
- **OUTCOME ≠ VERIFICATION.** The outcome says the call completed. Verification says the *world* changed the way the intent required, checked by a party that did not produce the change. `WorkerOutcome.SUCCESS` and mission success are different claims — today they are the same claim (W17).

### 4.3 Timestamp semantics (uniform across the epistemic family)

Every epistemic record is **bitemporal** (per Zep/Graphiti and the bitemporal-facts literature): `occurred_at` (when true in the world), `recorded_at` (when the system learned it), `valid_until` (TTL/staleness horizon; NULL = must-re-verify-before-use), `superseded_by` (revision chain, never in-place edit). This is plain Postgres engineering with outsized payoff, and it is what makes "how fresh is this?" and "what did we believe on Tuesday?" answerable queries rather than vibes.

---

## 5. The World Model

**Verdict: yes — but a world model is a discipline, not a database.** Another knowledge graph would reproduce the repository brain with more edges. What makes a world model *fundamentally* different from memory, RAG, a knowledge graph, a vector store, or an event store is four properties, all absent from those technologies and all absent from the current codebase:

1. **Epistemic typing.** Every entry is an OBSERVATION, FACT, BELIEF, or UNKNOWN — never an untyped blob. A knowledge graph stores edges; a world model knows *which edges are load-bearing observations and which are last month's inference*.
2. **Reconciliation.** The model is continuously diffed against reality, Kubernetes-controller style: observed state vs. recorded state, drift surfaced as first-class deltas. Memory is written once and trusted; a world model is *level-triggered* — it assumes it is wrong and keeps checking. This converts "agent failure" from an incident into a retry, and makes drift detection continuous rather than event-driven. (The research is blunt here: runtime discovery beats learned models under enterprise drift, and no mainstream agent framework reconciles.)
3. **Prediction support.** The model can hold *expected* future state (from plans, dry-runs, deploy intents) alongside current state, so predicted-vs-actual is a standing query, not a special report.
4. **Known unknowns.** The model records what it does not know (`SourceStatus.UNAVAILABLE ≠ RETURNED_EMPTY` — the dormant contract, finally live). An empty answer and a failed probe are different world states.

### 5.1 The four layers

- **WORLD HISTORY** — append-only observations and events. The ground truth ledger; nothing here is ever wrong, only incomplete ("instrument X returned Y at T" stays true forever). Sources: connectors, watchers, CI results, telemetry probes, execution outcomes.
- **WORLD STATE** — the current reconciled view per entity (repository, service, deployment, environment, database, queue, dependency edge, incident, team, ownership, policy, credential *reference* — never material). Every field carries provenance (which observations), freshness (when last confirmed), and mode (observed / inferred / declared-by-human / stale). Answering a query with stale fields *says so*.
- **WORLD BELIEF** — inferences layered on state: probable ownership, suspected coupling, causal hypotheses, capacity estimates. Confidence-carrying, supersedable, advisory. This is where LLM output lives — visibly, quarantined by type, never laundered into WORLD STATE.
- **WORLD PREDICTION** — expected states with deadlines, from approved plans, harvested dry-runs (`terraform plan` diffs, `--dry-run` results, canary baselines), and declared postconditions. Resolved against WORLD HISTORY as observations arrive; unresolved-past-deadline predictions become prediction-error records feeding §10.

Interaction: **HISTORY feeds STATE by reconciliation; STATE grounds BELIEF; BELIEF and STATE generate PREDICTION; HISTORY resolves PREDICTION; resolution errors update BELIEF confidence and mint LESSONS.** One loop, four layers.

### 5.2 What it is not

- Not a learned/neural simulator (**REJECT** for now — brittleness under tenant drift is documented; the environment's own dry-runs are higher-fidelity and free).
- Not a vector store (embeddings may *index* the model for retrieval; they are never the model — similarity is not truth).
- Not global. Coverage is explicitly partial and *known to be partial*: the model tracks which entities are instrumented and which are dark, because "we don't observe that cluster" is itself world knowledge.
- Not new storage technology. It is Postgres tables under Alembic, replacing the 76 JSON stores — which the codebase's own state rules already name as the most expensive defect.

---

## 6. Epistemic Architecture

The system must know **what it knows, why, since when, from where, how fresh, how trustworthy, what contradicts it, and what it does not know.** Concretely:

### 6.1 Provenance

Every epistemic record links to its sources: observations cite instrument + query (re-executable, per the dormant `Citation` contract); facts cite observations; inferences cite inputs + method; lessons cite prediction-error records. W3C-PROV-shaped, exportable. Provenance is also the memory-poisoning defense (MINJA-class attacks arrive as unprovenanced writes) and the forensic substrate the audit chain already almost is.

### 6.2 What confidence actually means

**Confidence is a calibration statement, not a feeling.** The research verdict is final: verbalized LLM confidence is systematically overconfident, prompt-sensitive, and mechanistically ingrained — as a control signal it is **rejected**. In CortexPrime, the confidence on a belief means exactly one thing:

> *"Of claims of this class, produced by this source, via this method, over the trailing window, this fraction were later confirmed by observation."*

That number exists only because predictions get resolved (§5.1) and outcomes get recorded. Before enough history exists, a belief's confidence is **UNCALIBRATED** — a named epistemic state, displayed as such, never a default 0.5 and never the memory system's current default of 1.0. LLM-stated confidence may be *stored* as metadata ("the model said 90%"); it never gates anything. Fake numerical decoration is the failure mode; earned frequencies are the design.

### 6.3 Contradiction and revision

- New observations that conflict with held facts/beliefs create a **CONTRADICTION record** — never a silent overwrite, never ignored. Resolution: supersede the older claim (normal), flag the instrument (both claims observational), or escalate (both load-bearing and irreconcilable).
- Supersession chains preserve history: the system can answer "what did we believe when we approved this plan?" — which is what makes post-incident review of *the system's own reasoning* possible.
- **Freshness is enforced at use, not at write.** Every consumer of world state declares a staleness tolerance; the epistemic layer refuses to serve staler data to a consequential action without re-observation. This is the STALE-benchmark defense (agents act on stale beliefs even after retrieving fresh evidence) done structurally: the stale belief is not *available* to the action path.

### 6.4 The epistemic gate

The one new hard boundary this architecture adds: **consequential actions may only be justified by claims that pass the gate** — typed FACT or confirmed ASSUMPTION, fresh within tolerance, uncontradicted, provenance-complete. Beliefs and hypotheses may shape *proposals*; they may not, alone, justify an *irreversible action*. If a plan's justification rests on a belief, the gate's answer is not "deny" — it is "**observe first**": the plan grows an investigation step that converts the belief to a fact or kills the plan. This single rule operationalizes Evidence Before Belief (§14, Law 2) and directly implements the B-I-P coupling the security literature identifies as the unfilled gap: belief-trust becomes an input the authorization engine reads.

---

## 7. The Investigation Engine

**Verdict: yes — OBSERVE → HYPOTHESIZE → PREDICT → INVESTIGATE → OBSERVE → UPDATE BELIEF replaces PROMPT → PLAN → TOOL → ANSWER for every diagnostic task.** The evidence: differential-diagnosis structure measurably reduces diagnostic error independent of the diagnostician (proven in medicine, echoed in AIOps scaffolds); tool-grounded RCA cut hallucination 40%→4% in Microsoft's production study; and the single biggest documented failure of the current codebase's RCA path is committing to one explanation and filing it as truth.

### 7.1 The loop

1. **OBSERVE.** Assemble the evidence set from the world model + targeted fresh reads. Absences are typed (`RETURNED_EMPTY` vs `UNAVAILABLE`) — a dark telemetry source is recorded as an UNKNOWN, not skipped.
2. **HYPOTHESIZE — plural, mandatory.** The LLM's actual comparative advantage is generating *diverse candidate explanations*, not choosing among them. Minimum two live hypotheses (or an explicit record of why only one is tenable); each states its **discriminating evidence**: what observation would support it, what would refute it, and — critically — what distinguishes it *from the others*. Algorithmic RCA (BARO/CIRCA-class over telemetry) runs beside the LLM as an independent hypothesis source; where both are available, agreement is signal and disagreement is an UNKNOWN worth chasing.
3. **PREDICT.** Each hypothesis commits to falsifiable predictions ("if pool exhaustion: connection wait-time histogram is saturated; rolling one pod restarts the symptom within 5 min").
4. **INVESTIGATE.** Choose the *cheapest discriminating* probe, not the most confirming one. Probes are ranked read-first: logs/metrics/config reads → replicas/shadow traffic → **interventional probes** (canary restart, flag flip, traffic shift) which are governed actions requiring authority like any other. Intervention is the causal disambiguator LLMs cannot be (Corr2Cause: near-random) — DevOps environments are unusually intervenable, and that, not model reasoning, is where causal power comes from.
5. **OBSERVE + UPDATE.** Resolve predictions against fresh observations; update hypothesis status (supported/refuted/still-open). Refuted hypotheses are *kept* — "we ruled out X because Y" is the most valuable artifact an incident review inherits.
6. **Terminate honestly.** Exit states: one hypothesis supported at calibrated confidence → promote to belief/fact and hand to planning; budget exhausted with plural survivors → escalate to a human *with the differential*, ranked, with evidence for and against each — which is a materially better handoff than any current tool's single confident guess; all refuted → widen hypothesis generation and say so.

### 7.2 Engineering coverage

The same loop instantiates across the required examples with domain probe libraries: production incident (topology-aware differential across deploy/dependency/capacity/data), failing deployment (diff-scoped hypotheses: code, config, environment, infra), latency spike (upstream/downstream/self, saturation vs. contention vs. external), database saturation (workload change vs. plan regression vs. capacity vs. lock contention), security anomaly (true positive vs. misconfiguration vs. benign change — with the investigation itself read-only until authority says otherwise), broken CI (test vs. code vs. infra vs. flake — the flaky-test detector already on file becomes one hypothesis source), dependency failure (upstream outage vs. contract change vs. auth expiry).

What today's agents do at each of these: retrieve, pattern-match to the most familiar explanation, and present it fluently. The loop's whole purpose is to make that fluent first guess *one candidate among several, with a price on its head*.

---

## 8. The Future / Simulation Model

**Verdict: a prediction layer, yes; a simulator, no.**

Every candidate consequential action is annotated before execution with a **PREDICTED OUTCOME RECORD**: expected effects (as WORLD PREDICTIONs with deadlines), uncertainty (calibrated where history exists, UNCALIBRATED where not), blast radius (what could this touch — from the world model's dependency edges, not from the LLM's imagination), reversibility class (reversible / compensable / irreversible), cost, policy impact, dependencies, and known failure modes with tripwires ("abort if error rate exceeds X during rollout").

Three sources, in strict preference order:

1. **The environment's own dry-runs** — `terraform plan`, `kubectl --dry-run`, `helm --dry-run`, DB transactions, canary baselines. These are *real* predicted outcomes at near-zero cost, and harvesting them systematically as first-class prediction artifacts is CortexPrime's cheapest differentiator; almost no platform does it. **BUILD.**
2. **Historical outcomes of the same action class** — "the last 14 deploys of this service took 6–9 min; two rolled back." Pure database queries over the outcome ledger. **BUILD.**
3. **LLM-imagined simulation** — usable only as a *ranking prior* among candidate actions, never as a gate, never as evidence. The research is consistent: one-step imagination works, multi-step rollouts compound hallucinated dynamics, and enterprise "dynamics blindness" (invisible cascading side effects) is precisely where imagination fails. **RESEARCH — admit later, quarantined by type.**

A **counterfactual layer** ("what would have happened had we not acted?") is **DEFERred**: genuinely useful for learning attribution, genuinely a research problem, not load-bearing for Phases 6–10. The predicted-outcome record, by contrast, is load-bearing three times over: it is what the approver approves (mixed initiative, §12), what verification checks (§9), and what learning scores (§10). One artifact, three consumers — that is the design's keystone.

---

## 9. Verification Architecture

The critical section, because the current system's verification is self-report with a type system in front of it (W2), and the literature says weak verification is the common root of benchmark inflation, production fail-plausible incidents, and multi-agent failure.

### 9.1 The four verifications, kept separate

- **PROCESS verification** — did execution follow the governed path? Authority present, digests matched, obligations discharged, audit chain intact. *Already built and genuinely strong.* Proves the system did what it was told, deterministically checkable.
- **OUTCOME verification** — did the action's declared effect occur? Read-after-write against the actual provider, checking *content*, not existence (upgrading the one honest verifier, `services/verification_service.py`, from "the PR exists" to "the PR contains the intended diff against the intended base").
- **WORLD-STATE verification** — did the world reach the predicted state, and *only* the predicted state? Postconditions checked against fresh observations at their deadlines; side-effect sweep over the blast radius for effects that were *not* predicted (the dynamics-blindness defense: unpredicted deltas inside the blast radius are findings, not noise).
- **INTENT verification** — were the mission's success criteria met? Each `SuccessCriterion` (already modeled, never evaluated — W17) must be *operationalized at intent time*: a criterion that names no observable check is rejected at the gate as unverifiable, forcing the conversation about what "done" means before work starts rather than after. Criteria are evaluated against the world model, not against the executor's account of itself.

### 9.2 The independence rule

**The component that generated a solution is never its sole verifier. No exception.** Grounds: the 64.5% self-correction blind spot; verifier gaming of visible checks; the audit's W16 (the computer agent's verifier is the same model reading the same screenshot; the delivery reviewer is the executive that produced the patch plan). Independence requirements, in increasing strength: separate *context* (fresh session, no access to the generator's reasoning — recovers most of the value even with the same weights), separate *criteria* (the verifier holds acceptance criteria the generator never saw — the anti-gaming move; criteria live server-side with the intent), separate *authority* (the verifier runs under its own capability grants — read-heavy, distinct credentials — which the capability fabric already supports), and for high-stakes gates, separate *oracle* (execution-based checks — reproduction tests, differential behavior, postcondition probes — that no LLM can flatter).

### 9.3 Verification executes; it never transcribes

The verification record is minted **only** from checks the assurance plane *ran*: commands executed, observations collected, comparisons computed. The API shape that accepts `verdict` and `evidence_trust` as caller-supplied strings is abolished. An LLM may participate in *interpreting* results (does this log line indicate the migration applied?) — flagged as interpretation, over evidence the plane collected itself. The existing engineering-verification design (asserted vs. verified evidence as unconvertible types, INCOMPLETE ≠ FAILED, adversarial absence claims, P1–P7 policies, derived-not-chosen outcomes) is *kept as the vocabulary* and finally given the executor it was designed for. Verification of chained work verifies each boundary — per the half-life math, a verified boundary is what stops error propagation from compounding hazard.

### 9.4 What verification cannot promise

Honesty clause, per Part 17 discipline: verification is itself fallible (wrong postconditions verify the wrong thing perfectly; probes can lie; the sweep sees only the instrumented blast radius). The mitigations are structural, not aspirational: postconditions are reviewed *as part of plan approval* (humans approve what "success" will be checked as); verification instruments are ordinary capabilities whose reliability is itself tracked (a probe that later proves wrong demotes the verifications it supported — supersession chains make that traceable); and residual doubt is stated on the record (`VERIFIED` vs `VERIFIED_PARTIAL: 2 of 5 postconditions unobservable`), never rounded up. No silent degradation applies to the verifier first.

---

## 10. Learning Architecture

**Verdict: PREDICTION → ACTUAL → ERROR → LESSON replaces conversation-memory accumulation entirely.**

Definitions: a **prediction** is the sealed pre-action record (§8); the **expected outcome** its content; the **actual outcome** the observation-derived resolution; the **prediction error** the computed diff — computed by the platform from two records it owns, *never supplied by a caller* (abolishing W15, where both sides of the comparison are keyword arguments); a **lesson** an independently validated generalization over recurring errors; a **strategy update** a change to how proposals are generated (prompt context, probe rankings, plan templates, cost estimates) — and never anything else.

Why this signal: it is the only learning signal the agent cannot game, because reality supplies half of it. The self-improvement literature's core numbers — 73.8% of self-assessed "optimizations" were proxy-only; hacking rates *grow* with iteration; self-authored verification is structurally conflicted — all describe systems where the same party writes the work, the test, and the grade. Prediction error breaks the loop at the grade.

**The learning firewall — how learning cannot corrupt governance:**
1. **Learning never touches the authority family.** No lesson modifies a grant, policy, approval requirement, or autonomy tier. Learning may generate a *petition* ("this action class has 40 consecutive verified successes; consider promotion") that enters the same human-decided governance process as any other change. Cognition proposes; governance disposes — even about itself.
2. **Lessons are advisory forever** (I7, now enforced by the write path, not by a dataclass test). They shape proposals; they never gate, authorize, or veto.
3. **Writer/validator separation.** The lesson-drafter (LLM over error clusters) and the lesson-validator (independent check: is the generalization supported by the error records it cites? does it contradict fresher evidence?) are separate parties; unvalidated drafts influence nothing.
4. **Lesson influence is audited.** Every proposal records which lessons shaped it (replacing today's top-3-by-recency blind injection). A lesson whose influenced proposals *underperform* is demoted automatically — the lesson ledger is itself subject to prediction-error scoring. Poisoned or merely wrong lessons die of measured irrelevance instead of compounding.
5. **Memory hygiene:** every lesson carries provenance and a validity horizon; lessons about a changed world expire; supersession, never deletion.

What this yields that conversation memory cannot: calibration curves per action class (the substance behind §6.2's confidence), honest duration/cost priors, per-capability-class reliability records (the input to graduated autonomy, §12) — and a system whose knowledge visibly *improves* because its errors are measured, not because its self-assessments are stored.

---

## 11. Attention / Proactivity Architecture

**Verdict: situation-aware and proactive — with attention driven by the world model, not by polling everything and firing every rule.**

The research frames the design cleanly: proactive capability decomposes into *discover → identify → execute*, and discovery is the weak stage (best end-to-end: 40%) — **for agents that must search**. A platform that owns the world model doesn't search; reconciliation *produces* the deltas. CortexPrime's proactivity is therefore structurally advantaged exactly where the field is weakest — but only if attention is disciplined. The current system is the cautionary tale: ten watchers polling on intervals, every matching policy firing, cooldowns as the only brake, no salience model anywhere (§3, audit §8).

**The attention engine** consumes one stream — world-model deltas (new facts, contradictions, expired assumptions, unresolved predictions, drift findings, new UNKNOWNs) — and answers the required questions as a pipeline:

- *What changed?* — the delta itself (reconciliation already computed it).
- *What matters?* — *salience scoring against standing concerns*: intent-linked entities (things active missions depend on), SLO/error-budget positions, blast-radius adjacency to recent actions, policy-flagged assets, calibrated base rates ("this queue's depth varies wildly; a spike is not news; *this* queue's never does").
- *What is anomalous / becoming risky?* — trends against history: prediction misses clustering on one service, freshness decaying on load-bearing facts, error budgets burning ahead of schedule.
- *What requires investigation?* — salient anomalies spawn *investigation missions* (§7) — **read-only until authority says otherwise**. Investigating silently is cheap and safe; acting is neither.
- *What should be surfaced vs. remain background?* — the **attention policy**, which is governance-owned configuration, not model judgment.

**The attention policy (the anti-spam contract):** severity tiers with explicit budgets (page-worthy / propose-worthy / digest-worthy / log-only); deduplication by *cause hypothesis*, not by event (one investigation per suspected cause, not one alert per symptom — the alert-correlation detector already on file becomes an input); every surfaced item carries evidence and, when possible, a proposed next step with predicted effects — surfacing work, not noise; and a feedback loop — dismissed surfacings are prediction errors of the attention engine itself, scored like any other prediction, so attention *calibrates*. A fixed proposal budget per period forces ranking rather than flooding — which is also the defense against the "overwhelm the approver" attack (§12).

Scheduled behavior (freshness sweeps, reconciliation cadences, report generation) remains — as the world model's metabolism, not as the intelligence.

---

## 12. Mixed Initiative

**Verdict: a dynamic authority relationship, priced in evidence — not a click-approve checkbox.**

### 12.1 Division of responsibility

| Party | Owns | Never owns |
|---|---|---|
| **Human** | Intent, success criteria, risk appetite, authority grants, promotion/demotion of autonomy, irreversible-action approval, final merge | Being a rubber stamp |
| **LLM (cognition)** | Hypotheses, plans, interpretations, drafts, lessons-drafts | Facts, authority, verification verdicts, its own grading |
| **Planner** | Turning intent + world state into candidate plans with predictions and declared assumptions | Executing anything |
| **Verifier (assurance plane)** | Executed checks, postcondition/intent verification | Generating what it checks |
| **Governance** | Authorization, admission, approval evidence, audit — deterministic | Reasoning |
| **Execution system** | Leases, attempts, outcomes, recovery — durable | Deciding what to do |
| **CortexPrime (the composition)** | Routing between all of the above; knowing which mode it is in | Pretending a mode it hasn't earned |

### 12.2 The autonomy ladder

Autonomy is a property of an **(action class × context) pair, earned from the verified track record** — never a global mode, never a vibe. Rungs:

- **A0 — Observe & report:** read-only investigation, surfaced findings. Default for everything new.
- **A1 — Propose:** plans with predicted-outcome records, awaiting approval.
- **A2 — Execute reversible, notify:** pre-declared reversible action classes within tripwires; human informed, not asked.
- **A3 — Execute compensable, approval on exception:** proceeds unless tripwires fire or the epistemic gate objects.
- **A4 — Execute irreversible:** *always* requires fresh human approval bound to the action digest and its predicted-outcome record. A4 is a rung, not a destination; some classes never leave A1 by policy.

Promotion requires: pass^k-style repeated verified success for the class (pass@1 is a demo metric; pass^k is a delegation metric), no open contradictions in the supporting world state, and a human governance decision recorded like any approval. **Demotion is automatic on failed verification, missed prediction beyond tolerance, or tripwire breach** — asymmetry is deliberate: authority is slow to earn, fast to lose. This is the agent version of graduated operational domains (Waymo's methodology) and the honest answer to "when should the system act vs. ask": *when its measured record for exactly this kind of action says it may, and a human has ratified that record.*

### 12.3 When the system stops, asks, escalates, rolls back

- **Act autonomously:** rung ≥ A2 for the class, epistemic gate green, tripwires armed.
- **Ask:** irreversible action; epistemic gate yellow (justification rests on belief — the request to the human *is* the evidence gap, stated as such); success criteria ambiguous.
- **Recommend:** confident diagnosis, action class at A1.
- **Investigate silently:** anything read-only. No permission needed to look.
- **Stop:** verification failure, contradiction on load-bearing state, tripwire breach → halt is the verified fallback (Simplex doctrine: the safe state is always available and always allowed).
- **Escalate:** plural surviving hypotheses at budget exhaustion; AMBIGUOUS execution states (already built — the lease model's honest UNKNOWN handling extends upward).
- **Rollback:** a *governed action like any other* — predicted, authorized, verified. Rollbacks are not exempt from the machinery; recovery-creating-second-order-failure is the audit's W17-adjacent lesson and the failure model's RECOVERY class (§13).
- **Continue monitoring:** every executed action leaves standing predictions; monitoring them is not optional post-work, it is the tail of the action itself.

### 12.4 The approval interface

An approval request is an **evidence package**: the action digest (already built), the predicted-outcome record, the epistemic status of the justification (which claims are facts vs. beliefs, and how fresh), blast radius and reversibility class, and the tripwires + rollback plan. The human approves *a specific action with specific predicted effects on specific evidence* — the digest binding extended from "what will run" to "what we claim it will do."

Oversight quality is itself instrumented: approval latency, modification rate, and post-approval verification failures are health metrics. **A 100% approval rate triggers review of the approval tier, because it means the tier is either too strict (everything routine is being asked) or the human has stopped reading (rubber stamp).** Flooding the approver is treated as an attack pattern (OWASP), and the attention budget (§11) is its structural defense.

---

## 13. Failure Model

Formal taxonomy. For every class: **Detection / Containment / Recovery / Reconciliation / Escalation / Learning.** Cross-cutting rules first, because they matter more than the rows: (1) *silent is worse than wrong* — every gate that cannot obtain evidence refuses loudly; defaulting to pass (W10) is abolished as a category; (2) *unknown is not failure* — the execution core's UNKNOWN discipline extends to every plane; (3) *recovery actions are governed actions* — predicted, authorized, verified, so recovery cannot create ungoverned second-order damage.

| Failure class | Detection | Containment | Recovery | Reconciliation | Escalation | Learning |
|---|---|---|---|---|---|---|
| **Model failure** (wrong/hallucinated output) | Schema validation at every LLM boundary; epistemic typing (output enters as hypothesis/draft, never fact) | Typed quarantine — untrusted by construction | Regenerate with fresh context; alternate hypothesis source | — | Repeated failures on a task class → class demoted to A0/A1 | Error rates per prompt/task class feed calibration |
| **Reasoning failure** (invalid inference chain) | Independent verification at boundaries; discriminating-evidence requirement in investigations | Inference records name inputs — poisoned conclusions are traceable | Re-derive; supersede | Supersession chain | Plural-hypothesis deadlock → human with the differential | Prediction-error clusters on inference-heavy classes |
| **Evidence failure** (instrument lied / probe wrong) | Contradiction records; cross-instrument disagreement | Mark instrument suspect; widen UNKNOWN | Re-observe via independent instrument | Supersede derived facts; demote dependent verifications | Two instruments irreconcilable → human | Instrument reliability ledger |
| **Stale-state failure** | Freshness enforcement at use (§6.3); reconciliation sweeps | Epistemic gate blocks consequential use | Re-observe before action | Continuous by design | Load-bearing fact unrefreshable → block + surface | Staleness-caused misses tighten TTLs per entity class |
| **Planning failure** (plan wrong for the world) | Assumption re-check at execution; predicted-vs-actual divergence early in run | Halt at first contradicted assumption — remaining steps do not run | Replan against current world state (a *real* trigger at last: contradicted assumption → PLANNED→DRAFT) | Plan's world-snapshot vs. current state diff | Replan exceeds budget/authority → human | Which assumption classes rot fastest |
| **Tool failure** (call errored) | Worker result; timeout | Retry policy (built); idempotency keys (built) | Retry / alternate binding | Outcome recorded | Exhausted retries → mission blocked, not silently degraded | Tool reliability feeds binding preferences |
| **Execution failure** (crash, lease loss) | Lease expiry; heartbeat silence (built) | Fencing (built) | Recovery coordinator (built) | Durable record replay (built) | AMBIGUOUS → human (built) | — (already strong) |
| **Semantic failure** (succeeded technically, wrong in the world) | **World-state + intent verification (§9) — the new detector for the currently undetectable** | Tripwires abort mid-rollout | Compensate/rollback as governed action | Side-effect sweep updates world model with what *actually* happened | Verification failure at A2+ → automatic demotion + human | The highest-value prediction errors in the system |
| **Verification failure** (verifier wrong) | Instrument tracking; sampled re-verification; postcondition review at approval | Verification records carry method + instrument provenance | Re-verify independently | Demote dependent verifications via supersession | Disputed verification → human | Verifier calibration curves |
| **Governance failure** (authorized the operationally wrong thing) | Predicted-outcome record makes "what was approved" explicit; post-hoc audit diffs approval vs. actual | Blast-radius bounds on every grant | Revoke (reduces_exposure — never needs approval, already built) | Audit chain + world model reconstruct what happened | Pattern of approved-but-wrong → policy review | Approval-quality metrics (§12.4) |
| **Recovery failure** (rollback made it worse) | Rollback is predicted + verified like any action | Rollback tripwires; halt as always-available fallback | Escalate to human with full state — no automatic third-order attempts | World model reflects post-rollback reality, not assumed restoration | Immediately — two failed layers is a human's problem, definitionally | Compensation reliability per action class |
| **Learning failure** (bad lesson reinforced) | Lesson-influence audit; influenced-proposal underperformance | Lessons advisory-only (firewall, §10) | Demote/retire lesson | Supersession | Lesson implicated in an incident → freeze + review | The learning loop learns about itself |
| **Environmental change mid-mission** | Reconciliation deltas during execution; standing predictions violated | Pause-and-recheck on load-bearing delta | Replan | Continuous | Change invalidates approval's basis → re-approval required | Which environments move fastest |
| **Contradictory observations** | Contradiction records (§6.3) | Both claims held, neither trusted; UNKNOWN opened | Independent third observation | Resolution recorded with grounds | Irreconcilable + load-bearing → human | Instrument disagreement patterns |
| **Unknown commit outcome** (did the write land?) | UNKNOWN_OUTCOME (built); read-your-writes probes | No retry without idempotency key (built) | Reconcile by observation: *look at the world* rather than trust the error | The definitive answer comes from WORLD STATE, not the client library | Unresolvable → human, with both possibilities priced | Which providers produce ambiguity |
| **Partial completion with side effects** | Per-step outcomes + world sweep | Compensation graph (designed; must actually dispatch — the audit notes it never fires) | Compensate completed steps as governed actions | World model records the partial reality, not the intended whole | Irreversible steps in partial state → human | Which plan shapes strand partial state |
| **Irreversible side effect (unintended)** | Reversibility classing at planning; side-effect sweep after | Pre-action gates (post-hoc filtering of the irreversible is impossible — the literature's bluntest finding) | None — that is what irreversible means. Mitigation and honest disclosure | World model records the new permanent reality | Always, immediately | Feeds the strongest lessons and tightest future gates |

---

## 14. The CortexPrime Intelligence Constitution

The fifteen candidate laws, challenged. Verdicts: kept, rewritten, merged, or rejected — then the additions the research demanded. Final count: **twelve laws**, each with a stated enforcement mechanism, because a law without a mechanism is the current codebase's I1: aspiration marked ENFORCED.

**Challenged candidates:**

1. *World Before Task* — **KEPT, sharpened.** No consequential action without a world-model read fresh within tolerance. (Mechanism: epistemic gate.)
2. *Evidence Before Belief* — **REWRITTEN** as **Evidence Before Action**. Beliefs are legitimate and useful — the system runs on them; they just cannot *alone* justify irreversible action. The original phrasing wrongly implies beliefs are bad rather than cheap.
3. *Unknown Is First-Class* — **KEPT.** Already half-built in the execution core; extended to the epistemic family. (Mechanism: UNKNOWN records; `RETURNED_EMPTY ≠ UNAVAILABLE`.)
4. *Cognition Cannot Grant Authority* — **KEPT VERBATIM.** The single most important law. (Mechanism: authority family writable only by governance operations; no cognition-plane code path reaches it.)
5. *Every Action Has Provenance* — **MERGED into Law 7** (actions already have provenance via the audit chain; the gap is claims).
6. *Every Important Action Has a Postcondition* — **KEPT, strengthened**: every consequential action has a *predicted outcome record*, of which postconditions are part. (Mechanism: admission refuses consequential actions without one.)
7. *Reality Beats Memory* — **KEPT, renamed** **Reconcile Continuously**: memory loses to observation *by construction* (freshness enforcement), not by exhortation.
8. *Predictions Must Be Testable* — **KEPT.** A prediction no observation could resolve is rejected at write time. Same rule applied to success criteria (§9.1).
9. *Failure Must Be Recoverable* — **REWRITTEN**: irreversible actions exist; pretending otherwise is fantasy. The honest law is **Reversibility Is Priced**: every action declares its class, and authority scales with irreversibility.
10. *Learning Cannot Rewrite Authority* — **KEPT** (mechanism: the learning firewall, §10).
11. *Independent Verification* — **KEPT** (mechanism: §9.2; the generator never sole-verifies).
12. *No Silent Degradation* — **KEPT, generalized**: absence of evidence is never evidence of absence; a gate that cannot check refuses loudly. (The current codebase violates this in its most guarded path.)
13. *Every Autonomous Action Has a Known Blast Radius* — **KEPT** (mechanism: blast radius from world-model edges, required on the predicted-outcome record).
14. *Prefer Reversible Actions* — **MERGED into 9's rewrite.**
15. *Continuous Reality Reconciliation* — **MERGED into 7's rewrite.**

**Additions the evidence forced:** *One Plane of Action* (the audit's central finding made law); *Claims Are Typed* (the ontology made law); *Confidence Is Earned* (the calibration literature made law); *Authority Is Earned Per Class* (the autonomy ladder made law).

### The Constitution (draft for ratification)

| # | Law | Meaning | Enforcement |
|---|---|---|---|
| **L1** | **One Plane of Action** | Every side effect flows through the governed execution path. A second path is not a convenience; it is the end of every other guarantee. | Architecture fitness rule: no connector/provider write reachable except through the invocation gateway. CI-blocking, no grandfathering. |
| **L2** | **Claims Are Typed** | Every stored claim is an observation, fact, belief, hypothesis, assumption, prediction, or unknown — with provenance, bitemporal stamps, and freshness. Untyped claims cannot exist. | Epistemic ledger schema; no free-form knowledge writes. |
| **L3** | **Evidence Before Action** | Consequential actions are justified by facts and confirmed assumptions, fresh within tolerance. A belief-justified plan grows an observation step or dies. | The epistemic gate, evaluated at admission. |
| **L4** | **Cognition Cannot Grant Authority** | No LLM output creates, widens, or transfers authority — including its own. Risk assessments produced by cognition are advisory input to governance, never governance. | Authority family has no cognition-plane writer; approval identity is authenticated, not asserted. |
| **L5** | **The Generator Never Grades Itself** | Independent verification for every gate: separate context minimum, separate criteria and authority for consequential work, execution-based oracles for the irreversible. | Assurance plane; verification mintable only from executed checks. |
| **L6** | **Predictions Precede Consequences** | Every consequential action carries a predicted outcome record — effects, blast radius, reversibility, tripwires — sealed before dispatch, resolved after. | Admission refuses consequential actions without one; the resolver runs unconditionally. |
| **L7** | **Reconcile Continuously** | The world model is presumed stale and is perpetually diffed against observation. Memory loses to reality by construction. | Reconciliation loops; freshness enforcement at use. |
| **L8** | **Unknown Is First-Class** | "We don't know" is a recorded, queryable, escalatable state — never rounded to success, failure, or silence. | UNKNOWN types across all planes (execution core's discipline, universalized). |
| **L9** | **No Silent Degradation** | A check that cannot obtain evidence refuses loudly. Absence of evidence is never evidence of absence. Subsystem death is a stated fact, not a warning log. | Fail-closed gates; startup honesty; degraded-mode surfaced in every report touched by it. |
| **L10** | **Reversibility Is Priced** | Every action declares reversible / compensable / irreversible. Authority, approval depth, and verification strength scale with the class. Irreversible actions always face a fresh human. | Reversibility on every capability contract; ladder rules in policy. |
| **L11** | **Authority Is Earned Per Class** | Autonomy is granted per action class from verified track record (pass^k), ratified by humans, and lost automatically on failure. Slow up, fast down. | The autonomy ledger; demotion triggers wired to verification. |
| **L12** | **Learning Cannot Rewrite Authority** | Lessons are advisory forever. Learning improves proposals; it petitions for authority changes through governance like everyone else. | The learning firewall; lesson-influence audit. |

---

## 15. Reconstructed Architecture

From first principles — and it turns out first principles *keep* most of what Phases 1–5 built, because the envelope was right; it rearranges everything around one rule: **cognition is untrusted, evidence is typed, and there is exactly one way to touch the world.**

### 15.1 The planes

```
                          ┌─────────────────────────────────────────┐
                          │                HUMANS                   │
                          │   intent · approval · autonomy grants   │
                          └───────▲─────────────────────▲───────────┘
                        evidence  │                     │ escalation,
                        packages  │                     │ differentials
┌───────────────┐       ┌────────┴────────┐   ┌────────┴────────┐
│ ATTENTION      │──────▶│ COGNITION PLANE │   │ ASSURANCE PLANE │
│ salience over  │spawns │ (untrusted)     │   │ (independent)   │
│ world deltas   │invest.│ hypotheses      │   │ executes checks │
└──────▲────────┘       │ plans, drafts   │   │ mints           │
       │ deltas         │ interpretations │   │ VERIFICATION    │
       │                └───────┬─────────┘   └────────▲────────┘
┌──────┴──────────┐   proposals │ + predicted          │ fresh
│ WORLD PLANE     │             ▼   outcomes           │ observations
│ history · state │      ┌─────────────────┐           │
│ belief · pred.  │      │ AUTHORITY PLANE │───────────┤
│ reconciliation  │      │ (deterministic) │           │
│ epistemic ledger│      │ capability      │           │
└──────▲──────────┘      │ fabric · gate · │           │
       │ observations    │ approvals·audit │           │
       │                 └───────┬─────────┘           │
┌──────┴──────────────────────── ▼ ────────────────────┴──┐
│ EXECUTION PLANE (durable) — leases · attempts · outcomes │
│ recovery · outbox · THE ONLY PATH TO SIDE EFFECTS        │
└───────────────────────────┬──────────────────────────────┘
                            ▼
                    the actual world
                            │ observations (connectors, watchers, probes)
                            └──────────▶ back to WORLD PLANE
        LEARNING PLANE (background): prediction↔outcome diffs → lessons
        → advisory context to COGNITION · petitions to HUMANS. Never to AUTHORITY.
```

- **World Plane** *(new — built from the dormant contracts + the 76 JSON stores' funerals)*: observation ingestion, the epistemic ledger, world state/history/belief/prediction, reconciliation loops, freshness enforcement, contradiction tracking.
- **Cognition Plane** *(exists as V1 agents/services — to be re-homed and defanged)*: every LLM call in the system. Emits only typed, quarantined artifacts: hypotheses, plan drafts, interpretations, lesson drafts. Structurally cannot mint facts, verifications, or authority.
- **Authority Plane** *(exists — the Phase 5 capability fabric, kept nearly verbatim)*: authorization, admission, digests, approvals (authenticated), obligations, credential broker, audit chain — now also consuming epistemic status (the gate) and the autonomy ledger.
- **Execution Plane** *(exists — the Phase 4 durable core, kept verbatim)*: the only path to side effects. The V1 connectors become workers behind the worker contract.
- **Assurance Plane** *(new — the engineering-verification vocabulary given an executor)*: runs outcome/world-state/intent verification with its own grants and hidden criteria.
- **Attention Engine** *(replaces the watcher/trigger sprawl)*: salience over world deltas; spawns investigations; owns the surfacing budget.
- **Learning Plane** *(new, background)*: prediction-error ledger, lesson lifecycle, calibration curves, autonomy petitions.

### 15.2 Boundaries

- **Trust boundary:** everything cognition emits is untrusted input, schema-validated and typed at the boundary — the same posture the gateway already takes toward tool descriptions (`normalization.py`: "text is data"), extended to the system's own reasoning.
- **Authority boundary:** unchanged from Phase 5 — and finally exclusive (L1).
- **Intelligence boundary:** the LLM is confined to the cognition plane and to *interpretation* roles elsewhere, always marked as such. Resolution stays deterministic ("no LLM anywhere" — kept). Policy stays deterministic. The gateway stays LLM-free.
- **Verification boundary:** assurance shares no context, criteria, or credentials with cognition.
- **Learning boundary:** the firewall (§10). One-directional: learning reads everything, writes only advisory artifacts and petitions.

### 15.3 Control flow for one governed action

Intent (human) → investigation if needed (§7) → plan draft + predicted outcomes (cognition) → epistemic gate (evidence fresh? assumptions confirmed?) → authorization + approval with evidence package (authority) → admission (TOCTOU re-check, built) → dispatch (execution) → outcome (execution) → verification (assurance, independent) → world reconciliation (world plane) → prediction resolution → error → lesson (learning) → monitoring tail (attention). Every arrow audited; every claim typed; one plane touching the world.

---

## 16. The DevOps Proof Case

**Scenario:** production service `payments` shows latency increase + error-rate increase; there was a deployment 40 minutes ago; the database shows saturation; a queue is backing up; telemetry conflicts (one dashboard says CPU is fine, another says throttling).

**1. Observe.** The attention engine already has most of this: the deploy is a world-model EVENT; the SLO burn is a delta; the alert storm dedupes into one situation (by suspected cause, not per symptom). Fresh targeted reads fill gaps. The conflicting telemetry becomes a **CONTRADICTION record** — not silently resolved by picking the dashboard the prompt saw first.

**2. Establish facts.** Typed: deploy `d-891` completed 13:22Z (fact, CI observation); p95 rose 240ms→890ms from ~13:30Z (fact, metrics); DB active connections at pool max (fact); queue depth growing 400/min (fact); CPU-throttling status **UNKNOWN** (contradiction open).

**3. Identify uncertainty.** Standing UNKNOWNs: throttling contradiction; whether the deploy changed connection handling (diff not yet read); whether queue growth is cause or symptom.

**4. Generate hypotheses — plural, with discriminators.** H1: deploy introduced connection leak (predicts: pool exhaustion trends from 13:22Z, diff touches DB code; discriminator: rollback fixes). H2: organic traffic surge saturating DB (predicts: request-rate step-change; discriminator: traffic metrics; rollback does nothing). H3: downstream dependency slow → workers hold connections longer (predicts: dependency latency up *before* 13:30Z; rollback does nothing). H4: queue consumer failure → retry amplification (predicts: consumer error logs precede latency). The algorithmic RCA layer independently ranks suspects from telemetry topology; agreement with H1 is noted as converging evidence, not proof.

**5. Gather evidence — cheapest discriminating first.** Traffic metrics: flat (H2 refuted, *kept on record*). Dependency latency: normal until 13:31Z (H3 weakened — the timing follows, doesn't precede). Deploy diff: touches connection-pool configuration (H1 supported). Consumer logs: errors present but starting 13:34Z (H4 demoted to symptom). The contradiction resolves: one dashboard was averaging across pods, the other per-pod — per-pod throttling real on 2 of 12 pods; instrument quirk recorded.

**6. Predict outcomes for candidate actions.** Rollback of `d-891`: predicted p95 < 300ms within 10 min of completion, queue drains in ~20 min; reversibility: compensable (re-deploy exists); blast radius: `payments` + its callers (world-model edges, not imagination); historical prior: last 6 rollbacks of this service took 4–7 min, all verified. Alternative — pool-size bump: reversible, but treats symptom; predicted to defer, not fix. Alternative — wait: predicted SLO breach in ~25 min at current burn.

**7. Compare.** Rollback dominates on expected value: strongest supported hypothesis, best predicted outcome, compensable class, tight tripwires.

**8. Check authority.** Rollback for `payments` sits at A3 (compensable, earned: 11 verified rollbacks, zero failures). The epistemic gate: H1 is a *supported hypothesis* — for an A3 action with tripwires this suffices under policy; had the action been irreversible, the differential itself would have gone to a human as the evidence package. On-call is notified with the evidence package either way (A3 = act, notify, abort window).

**9. Execute.** Through the gateway: digest-bound, leased, fenced, audited — the Phase 4/5 machinery, now actually in the path. Tripwires armed: abort if error rate rises during rollback.

**10. Verify — independently.** The assurance plane (own credentials, criteria sealed at approval) resolves the predictions: p95 at 265ms after 8 min ✓; queue draining ✓; connection pool at 40% ✓. Side-effect sweep over the blast radius: one caller (`billing`) shows a brief error spike during rollback — *unpredicted*, recorded as a finding, not discarded.

**11. Reconcile.** World state updated from observations: `payments` now runs `d-890`; incident record carries the full differential — including refuted H2/H3/H4 and their evidence; the `billing` coupling edge is strengthened in world belief.

**12. Record prediction error.** Latency recovered in 8 min vs. predicted 10 (small, within tolerance); the `billing` spike was a genuine miss — dynamics blindness caught and priced.

**13. Learn.** Lesson drafts: "rollbacks of `payments` transiently spike `billing` errors — add to future rollback blast radius and tripwires"; connection-pool config-change class gets a canary-first recommendation. Both validated against the records they cite; both advisory.

**14. Continue monitoring.** Standing predictions with deadlines: p95 stays < 300ms for 24h; queue depth normal by 14:30Z. The action is not "done" until its tail resolves.

**Where today's agents fail on this exact scenario:** commit to H1-shaped explanations *without* the differential (or to whatever the retrieval surfaced first) and present them confidently — the segment's documented top abandonment driver is hallucinated root cause; act on the stale pre-deploy picture of the topology; treat the conflicting dashboards by silently trusting one; verify by asking themselves whether it looks fixed; report success with no standing predictions, so the 24-hour regression goes unowned; and learn nothing structured — the next identical incident starts from zero. Each failure maps to a plane today's products don't have; that is the proof the composition matters.

---

## 17. Competitive Differentiation

Honest assessment against the field (full survey in the research record).

**What they optimize for.** Cursor: IDE flow and parallel task throughput. Claude Code / Agent SDK: general agentic capability as a substrate — mechanisms (hooks, permissions, subagents), not an opinionated epistemic product. Codex: PR throughput in sandboxed cloud tasks. Google (Jules/Antigravity): async coding + "Artifacts" as reviewable proof — notable, but self-produced proof for human review, not independent verification. Devin: end-to-end completion volume on well-scoped work; its documented failure mode ("confidently completely off-track") is precisely epistemic. OpenHands: open substrate; Enterprise adds RBAC + event triggers. SWE-agent/mini-swe-agent: proof that scaffolding is commoditized (100 lines → 74% SWE-bench Verified) — *scaffolding is not a moat for anyone, including CortexPrime*. LangGraph: checkpointing and HITL off the shelf — durable execution alone is not differentiation either.

**The segment that matters — AI SRE — is crowded, and honesty requires naming it:** Datadog Bits AI SRE (hypothesis generation + self-validation inside Datadog's silo), PagerDuty SRE Agent, Resolve.ai (~80% auto-resolution ambition, coarse trust model), Cleric (evidence chains + confidence from verified outcomes, deliberately read-only), and **Traversal — the closest conceptual competitor**, $48M funded, selling a trademarked "Production World Model™" and "Causal Search Engine™" for evidence-backed RCA. World-model-based investigation is **not whitespace**.

**Mere parity (do not claim as novel):** sandboxed execution + PR review; checkpointed state; permission hooks; RBAC/SSO/audit *logging*; evidence artifacts for humans; knowledge graphs with confidence scores; hypothesis-driven RCA per se; event-triggered automation.

**Genuinely underserved — the four-way composition:**
1. **Verification independent of generation.** Every product in both segments verifies with the agent that produced the work. Nobody ships a separate assurance plane with its own credentials and hidden criteria.
2. **Epistemic typing as the product surface.** Cleric and Traversal hold confidence internally; nobody exposes fact-vs-belief-vs-hypothesis with calibrated (not verbalized) confidence as the interface. The segment's defining failure — confident wrongness — is the demand signal.
3. **The governed middle of execution.** The market splits into read-only (Cleric) and aggressive auto-resolution (Resolve). Graduated, evidence-earned, per-class autonomy with digest-bound approval — the A0–A4 ladder — is an unoccupied position. Traversal diagnoses; it does not govern execution of fixes.
4. **Belief-coupled authorization + attested trajectories.** Named as unshipped by the security literature itself; the audit chain + capability fabric are 70% of the substrate.

**What would be hard for incumbents to reproduce:** not any feature — the *posture*. Datadog and PagerDuty monetize their silos (cross-vendor world models cut against their gravity); throughput-oriented products cannot bolt on independent verification without slowing the metric they sell; and the epistemic ledger only pays off through accumulated calibration history, which cannot be shipped in a release — it must be *earned per customer*, which is also what makes it a moat.

**What could kill the differentiation:** Traversal adding governed execution (they have the funding and the world model); or Anthropic/OpenAI shipping opinionated verification planes in their SDKs. The window is the composition's integration cost — high for everyone, including CortexPrime.

---

## 18. Reality Check

Mandatory honesty, using the document's own vocabulary. The vision's biggest risk is not any single component — it is that *the last five phases produced 200k lines containing two disjoint systems, and this document proposes concepts that could become a third*. Every verdict below is calibrated against a solo student developer with no budget building a real product.

**REJECT:**
- LLM causal inference as a decision input (near-random on formal tasks; hypothesis generation only).
- Verbalized confidence as a control signal (systematically miscalibrated; UI metadata at most).
- Learned/neural world models for ops (brittle under drift; the environment's own dry-runs are better and free).
- Full autonomous incident *resolution* as a near-term product claim (ITBench: 13.8%; the segment's honest ceiling today is governed proposal + graduated execution).
- The 20-entity ontology as 20 database tables (it is a type discipline over ~4 ledger families; reifying every concept separately is how this becomes unbuildable).
- Multi-agent deciding/editing swarms (MAST; Cognition's conflict result; multi-reader/single-writer only).
- A separate "attention ML system" (salience starts as scored rules over world deltas; anything fancier is premature).

**RESEARCH (promising, do not bet the roadmap):**
- LLM-imagined outcome simulation as ranking prior.
- Automated belief-drift-triggered replanning thresholds (the trigger discipline is buildable; the *thresholds* are open research).
- Counterfactual/attribution analysis for learning.
- Formal POMDP/AGM machinery (adopt the *shapes* — belief states, supersession — not the formalisms).
- Fully automatic hypothesis generation quality at investigation start (the loop is buildable; discovery-quality is the field's open weakness).

**BUILD (production-ready patterns, evidence-backed):**
- One plane of action (strangler over V1 connectors; the single highest-value change available).
- Bitemporal, provenanced epistemic ledger in Postgres (plain database engineering).
- Reconciliation loops over world state (Kubernetes-proven pattern).
- Dry-run harvesting + predicted-outcome records + prediction resolution (cheap, ungameable, nobody does it).
- Independent executing verification (the design exists in-repo; it needs an executor and separated credentials).
- Reversibility classing + risk-tiered gates + the autonomy ladder (deployable engineering per the RTA literature).
- Differential-diagnosis investigation scaffold (structure carries the value; medicine proved it before AI did).
- Prediction-error learning with the firewall.

**DEFER:**
- Cross-vendor world-model breadth (start with the connectors that exist; coverage honesty makes partial coverage acceptable).
- Compliance artifact mapping (AICM/RMF) — cheap later, once the machinery exists.
- Counterfactual layer; attested/signed trajectory export; multi-tenant productization of the epistemic ledger.

**Where LLMs stay weak and the design must not lean on them:** causal inference, self-verification, calibration, multi-step outcome simulation, memory-validity detection. The architecture's stance — LLM proposes, deterministic systems dispose — is not conservatism; it is the literature's consensus reading.

**Where humans remain mandatory:** intent and success criteria; irreversible approvals; autonomy promotion; irreconcilable contradictions; plural-hypothesis deadlocks; second-order recovery failures.

**Where this document itself risks overengineering:** if Phase 6 starts with the ontology instead of the wiring, the project fails. The ordering in §20 is therefore not a suggestion — consolidation *is* the next phase. A simpler architecture genuinely is better for: the attention engine (scored rules first), confidence (raw frequencies before curves), and the world model's scope (instrumented entities only, dark honestly declared).

---

## 19. KEEP / REFACTOR / EXTEND / REPLACE / DEFER / DELETE

| Disposition | Items (evidence in §3) |
|---|---|
| **KEEP** | `contexts/execution` (durable core, leases, UNKNOWN discipline, recovery, replay-that-cannot-execute); `contexts/connectivity` (capability fabric, authorization, admission, bindings); `backend/contracts/*`; `backend/platform/*` (audit chain, credential broker, hashing, storage guard, fitness-rule habit); the Mission→Intent→Plan→Workflow separation and its whole-graph rules; ADR discipline |
| **REFACTOR** | All V1 connectors → workers behind the worker contract (the strangler that makes L1 true); V2 API routes off `platform_internal` + in-memory repositories onto real tenancy and Postgres (W7); approval identity from asserted string to authenticated principal (W6); the two approval systems into the one cryptographic one (W12); startup from silent-degradation warnings to declared degraded modes (W22, L9); `engineering_verification` from transcription to execution (W2) |
| **EXTEND** | `contracts/knowledge.py` + `contracts/evidence.py` from dormant vocabulary into the live epistemic ledger (§4–6); `enterprise_verification_intelligence`'s comparator into the platform-computed prediction-error loop (W15 fixed); the watcher fleet into observation ingestion for the world plane; compensation from designed-but-never-dispatched into governed recovery actions; `Assumption`'s three-valued design into execution-time re-checking (L3) |
| **REPLACE** | The 76 JSON/JSONL state stores → Postgres under Alembic (the codebase's own named "most expensive defect"); repository brain → world model (typed, fresh, reconciled); top-3-by-recency lesson injection → audited lesson influence; `_stage_qa`/`_stage_security` default-pass gates → fail-closed verification; per-event cooldowns → the attention policy |
| **DEFER** | Counterfactual layer; learned simulation; signed/attested trajectory export; compliance control-mapping; multi-tenant epistemic ledger; anything ML-shaped in attention |
| **DELETE** | Dead code: zero-byte modules (`mission_agent_runtime.py`, `memory/episodic_memory.py`, `memory/memory_store.py`, et al.); `orchestrator/mission_planner.py` (keyword-matching impostor); the colliding `memory/models.py` `AssembledContext`; duplicate Mission definitions (I8's "12 modules define Mission"); the quarantined `auth/credential_store.py` once nothing references it |

---

## 20. Proposed Phase 6–10 Roadmap

Each phase has one sentence of essence, its laws, and its honest exit criterion. Ordering is load-bearing: **wiring before epistemics, epistemics before intelligence, intelligence before autonomy.**

- **Phase 6 — One Plane of Action (consolidation).** Make L1 true: every side effect through the governed gateway (connector-by-connector strangler, starting with the highest-blast-radius: deploy/rollback, git write, K8s); real persistence and tenancy for the V2 routes; authenticated approvals; one approval system; loud degradation; delete the dead code. *No new intelligence in this phase — deliberately.* Exit: the architecture fitness rule "no ungoverned side-effect path" passes CI un-grandfathered, and one real end-to-end action (a governed rollback) runs through gateway → outcome → audit against a real provider. (Laws: L1, L4, L9.)
- **Phase 7 — The World Plane.** Epistemic ledger (bitemporal, provenanced, typed); observation ingestion from the existing watchers; world state for the entities the connectors already see; reconciliation loops; freshness enforcement; contradiction records; JSON-store funerals begin. Exit: a consequential action is refused because its justifying fact is stale, and the refusal explains itself. (Laws: L2, L7, L8.)
- **Phase 8 — Assurance and Prediction.** Predicted-outcome records at admission; dry-run harvesting; the assurance plane executing outcome/world-state/intent verification with separated credentials; prediction resolution; the platform-computed error ledger. Exit: a technically-successful-but-semantically-wrong action (the `envs[0]` class of bug) is *caught by verification* in a test scenario — the currently-undetectable, detected. (Laws: L3, L5, L6.)
- **Phase 9 — Investigation and Attention.** The differential-diagnosis loop over real detector streams; hypothesis ledger; discriminating-evidence discipline; interventional probes as governed actions; the attention engine + policy replacing raw trigger policies. Exit: a seeded incident produces a ranked differential with refuted-hypothesis records, and the attention engine surfaces it within budget — zero spam. (Law: L8 in anger.)
- **Phase 10 — Learning and Earned Autonomy.** Lesson lifecycle with the firewall; calibration curves; the autonomy ledger with pass^k promotion and automatic demotion; approval evidence packages; oversight-quality telemetry. Exit: one action class is promoted A1→A2 on measured record, ratified by a human, and demoted automatically on an injected failure. (Laws: L10, L11, L12.)

Phase 5.5 (real-provider GitHub validation) stays blocked on the invalid credential, exactly as intended; nothing here weakens the credential boundary, and Phase 6's exit criterion will *require* that boundary intact.

---

## 21. Risks

1. **Complexity collapse (highest).** Solo developer, 200k lines, five planes. Mitigations are structural: Phase 6 removes code before any phase adds it; the ontology is a type discipline, not a schema zoo; every phase has one falsifiable exit criterion.
2. **The third-system risk.** This document could spawn a new plane beside the existing two. Countermeasure: L1 is Phase 6's *only* job, and the fitness rule is un-grandfathered — the constitution's first law is enforced before its most interesting ones exist.
3. **Verification cost.** Independent verification doubles some work. Mitigation: verification depth scales with reversibility class (L10); reads verify cheaply.
4. **Epistemic theater.** Typed claims could become decoration if consumers ignore types. Countermeasure: the gate refuses, it does not warn — the types have teeth or they are the old repository brain with extra columns.
5. **Calibration cold start.** Confidence needs history. Countermeasure: UNCALIBRATED is a displayed state; the ladder starts everything at A0/A1, which requires no calibration to be safe.
6. **Competitive timing.** Traversal or an SDK vendor occupies the governed middle first. Mitigation: the wedge (per the validation memory: prove against real external systems, report degraded results honestly) is demonstrable at Phase 8 — governed rollback with independent verification is a demo no one else can currently give.
7. **Attention noise → trust death.** One spammy month kills proactivity credibility permanently. Countermeasure: budgets from day one; surfacing quality is itself prediction-error-scored.
8. **Research-grade pieces leaking into load-bearing positions.** The RESEARCH list (§18) must stay quarantined; the fitness-rule habit should encode it ("no gate consumes an LLM-verbalized confidence" is a grep-able rule).

## 22. Open Research Questions

1. Belief-drift thresholds: *when* has the world moved enough to force replanning? (Heuristics buildable; principled triggers open.)
2. Hypothesis-generation coverage: how does the system know its differential spans the true cause? (The field's discovery bottleneck.)
3. Attention salience learning: can dismissal-feedback train ranking without creating blind spots for rare-but-critical events?
4. Verification of verification: sampling strategies for re-verifying the assurance plane without infinite regress.
5. Calibration transfer: does a calibration curve for "rollback predictions on service X" inform service Y? (Cold-start economics depend on it.)
6. Lesson generalization boundaries: when does a valid lesson over-generalize, and can influence-auditing catch it before an incident does?
7. The tracking half of meaningful human control: does the system act on the human's *reasons*, not just their approvals? (Philosophy meets product; unsolved everywhere.)
8. Cross-tenant epistemic isolation with shared calibration: learnable without leakage?

## 23. Architecture Invariants

The twelve laws (§14) are the constitution; these are their permanently machine-checkable shadows, intended for `platform/architecture/` as un-grandfathered fitness rules once their phases land:

1. No module outside the execution plane imports a connector's write path. (L1)
2. No epistemic record exists without type, provenance, and bitemporal stamps. (L2)
3. No consequential admission without a fresh-within-tolerance factual justification. (L3)
4. No code path from cognition-plane output to the authority family. (L4)
5. No verification record minted from caller-supplied verdicts; the minting path requires an executed check. (L5)
6. No consequential admission without a sealed predicted-outcome record; no prediction without a resolver. (L6)
7. Every world-state field carries freshness; every consumer declares tolerance. (L7)
8. UNKNOWN is representable and non-collapsible in every plane's outcome type. (L8)
9. No gate defaults to pass; no subsystem death is a `log.warning`. (L9)
10. Every capability contract declares a reversibility class; admission reads it. (L10)
11. Autonomy tier changes exist only as governance decisions with human principals. (L11)
12. Lessons carry `advisory` in the type system; no gate, policy, or authorization reads the lesson ledger. (L12)

## 24. Definition of Done for the Zero Phase

The Zero Phase is complete when — and only when — all of the following are true:

1. This document has been **read in full** by its owner, not skimmed.
2. Each of the twelve laws is explicitly **ratified, amended, or rejected** — silence is not acceptance.
3. The §19 dispositions (especially REPLACE and DELETE) are **ratified** — deleting the impostor planner and the JSON stores is a decision, not a default.
4. The Phase 6 exit criterion is **agreed verbatim**, because it constrains everything after it.
5. The REJECT list (§18) is accepted as *binding* on Phases 6–10 — anything on it re-enters only through a new written case.
6. The open questions (§22) are acknowledged as open — no phase plan silently assumes one is solved.
7. A decision is recorded on the competitive posture (§17): the governed-middle wedge, named, with the demo that proves it.
8. **No implementation has occurred.** The Zero Phase's output is this document and the decisions it forces — nothing else.

*Then* Phase 6 begins.

---

*Compiled from: three parallel research sweeps over 2024–2026 primary sources (citations inline in §2); a read-only conceptual audit of the repository at `3bf0b11` with file:line evidence (§3); and a competitive survey of the coding-agent and AI-SRE segments (§17). No source code, migrations, or configuration were modified in producing this document.*
