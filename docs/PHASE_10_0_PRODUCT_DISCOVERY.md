# Phase 10.0 — Product Discovery

**Discovery only. No production code, migration, table, connector, execution or
credential change.**

Every statement is labelled `[FACT]` (verified from this repository or a live
probe), `[SOURCE]` (external, web-verified), `[INFERENCE]`, `[PROPOSAL]`.

---

## Part A — Product surface map

### The headline finding

`[FACT]` The repository contains **138 frontend pages** under `frontend/app/`.
**One** of them references any governed concept (capability / governed / world /
assurance / autonomy / investigation).

`[FACT]` The backend contains **96 route modules** and registers **185 routers**
in `backend/api/router_registry.py`. Searching that registry for `world`,
`assurance`, `investigation` or `autonomy` returns **zero** matches.

`[FACT]` HTTP route modules per governed plane:

| Plane | Route modules |
|---|---|
| World | **0** |
| Assurance | **0** |
| Investigation | **0** |
| Autonomy | **0** |
| Calibration | **0** |
| Belief / Observation | **0** |
| Remediation | **0** |

`[FACT]` The two files matching "verification" are
`engineering_verification_routes.py` and `enterprise_verification_routes.py` —
neither touches `WorldVerification`. The one matching "incident" is
`enterprise_incidents_routes.py`, a V1 alert-correlation endpoint whose grep
count for governed concepts is **0**.

`[INFERENCE]` **The entire Phase 7–9 engine is reachable only from harness
scripts.** There is no product surface in front of it, and the 185 registered
routers are a V1 surface built before it existed. This single fact determines the
Phase 10 roadmap more than anything else in this document.

### Classification

| Surface | Status |
|---|---|
| 138 frontend pages | `[FACT]` V1 / disconnected from the governed engine |
| 185 registered routers | `[FACT]` V1; none reach World / Assurance / Investigation / Autonomy |
| `capability_routes`, `capability_authorization_routes`, `capability_discovery_routes`, `capability_resolution_routes`, `audit_routes`, `approval_center_routes` | `[FACT]` Governed-adjacent — these do touch the capability fabric |
| World / Assurance / Investigation / Autonomy | `[FACT]` **No HTTP surface at all** |

---

## Part B — The DevOps user journey, honestly graded

| # | Step | Status | Evidence |
|---|---|---|---|
| 1 | Incident detected | `[FACT]` **V1** | `enterprise_incidents_routes` correlates alerts; no governed link |
| 2 | Engineer opens CortexPrime | `[FACT]` **V1** | 138 pages, none wired to the engine |
| 3 | CortexPrime builds context | `[FACT]` **PARTIALLY VERIFIED** | World evidence + corroboration proven (9.4); no product surface |
| 4 | CortexPrime investigates | `[FACT]` **VERIFIED (engine), MISSING (product)** | 9.5 read-only investigator, harness-only |
| 5 | Engineer sees hypotheses | `[FACT]` **MISSING** | `CRASHLOOP_HYPOTHESES` exists; nothing renders it |
| 6 | Evidence is shown | `[FACT]` **MISSING** | `WorldQuery` returns evidence refs; no UI |
| 7 | CortexPrime explains uncertainty | `[FACT]` **VERIFIED (engine), MISSING (product)** | INSUFFICIENT_EVIDENCE / STALE / CONFLICTED verdicts exist (9.10 Part B) |
| 8 | Engineer approves an action | `[FACT]` **PARTIALLY VERIFIED** | `ApprovalFacts` + action-digest binding (ADR-090) proven; `approval_center_routes` is V1 and not wired to it |
| 9 | Execute through governance | `[FACT]` **VERIFIED** | 9.9C/9.10/9.11, real Kubernetes write |
| 10 | World state independently verified | `[FACT]` **VERIFIED** | 9.10, Assurance SUPPORTED from an independent read |
| 11 | Engineer receives final result | `[FACT]` **MISSING** | No surface |
| 12 | Investigation becomes reusable experience | `[FACT]` **PARTIALLY VERIFIED** | Phase 8 experiential memory exists; not surfaced, not fed back |

`[INFERENCE]` Steps 9 and 10 — the hardest and most dangerous — are the only ones
that are fully done. Everything a human touches is missing.

---

## Part C — Incident experience: is a first-class Incident aggregate required?

`[FACT]` The existing `Investigation` aggregate (Phase 8, ledger `0019`) already
carries: identity, tenant, status lifecycle (CREATED → INVESTIGATING → …),
hypotheses with status and temporal fit, evidence references, tests, conclusion
and residual uncertainty.

`[FACT]` The World Plane already carries source lineage, freshness horizons,
authority tiers, and CONFLICTED/CORRELATED/INDEPENDENT corroboration (9.4).

`[FACT]` What no existing aggregate represents: **incident identity distinct
from investigation identity**, severity, affected-service registry,
acknowledgement, and multi-investigation-per-incident.

`[INFERENCE]` One incident can require several investigations (a symptom that
turns out to be two causes), and an incident outlives any single investigation.
Modelling them as the same object would force either one investigation per
incident or an investigation that changes its own subject.

`[PROPOSAL]` A **thin** `Incident` aggregate that *references* investigations
rather than absorbing them — identity, tenant, service, environment, severity,
acknowledgement, timeline, and links. **Not** a second truth store: evidence,
hypotheses and verdicts stay in World / Investigation / Assurance. This decision
is deliberately deferred to a later phase with its own discovery.

---

## Part D — Human-in-the-loop intervention points

| Intervention | Backend contract | Product surface |
|---|---|---|
| Approve | `[FACT]` `ApprovalFacts` + `canonical_approval_digest` (ADR-090) | `[FACT]` MISSING |
| Reject / deny | `[FACT]` `ApprovalOutcome.DENIED`, proven refusing | `[FACT]` MISSING |
| Revoke after grant | `[FACT]` re-checked at dispatch (9.10 D1) | `[FACT]` MISSING |
| Emergency stop | `[FACT]` `EmergencyStopState`, gate 1 of 10 | `[FACT]` MISSING |
| Escalate autonomy | `[FACT]` `AutonomyPolicy` — **platform-decided, never human-forced** | n/a by design |
| Request more evidence | `[FACT]` `select_test` is platform-owned (9.5) | `[FACT]` MISSING |
| Inspect audit trail | `[FACT]` hash-chained audit, `audit_routes` exists | `[FACT]` PARTIAL — V1 route, not wired to governed records |
| Acknowledge / cancel / override | `[FACT]` **no contract** | `[FACT]` MISSING |

`[INFERENCE]` Every *governance* intervention already has a backend contract.
What is missing is exclusively presentation. `[PROPOSAL]` "Override" should
**not** be added: there is no contract for it and inventing one is how a
governance bypass gets built for UX convenience.

---

## Part E — Explainability: every question is already answerable

`[FACT]` Each product question maps to an existing artefact. No new truth system
is needed:

| Question | Existing source |
|---|---|
| Why do you think this? | `Investigation` hypotheses + `diagnosis` |
| What supports it? | `WorldQuery` evidence refs (SUPPORTED cites them — 9.10 B2) |
| What contradicts it? | `Verdict.UNSUPPORTED`, ELIMINATED hypotheses |
| How fresh? | freshness horizons; STALE ≠ FALSE |
| Which source is authoritative? | `SourceAuthority` tiers |
| Are sources independent? | `CorroborationLevel` INDEPENDENT vs CORRELATED (9.4) |
| What don't you know? | `INSUFFICIENT_EVIDENCE`, residual uncertainty, UNKNOWN ≠ FALSE |
| Why is this action safe? | `AutonomyDecision` reasons, blast radius, `CodeTrust`×`SideEffectClass` |
| Why was it refused? | refusal reason codes at every gate |
| Who approved it? | `approval_artifact_id`, durably recorded (9.9C H3) |
| What actually happened? | provider evidence + independent governed read |
| How was success verified? | `WorldVerification` verdict |

---

## Part F — RAG reassessment

`[FACT]` Scale of the existing knowledge surface: **213** modules mention RAG,
**56** embeddings, **41** Neo4j, **24** pgvector, **4** Chroma.

`[FACT]` Phase 8 (ADR-071) fenced RAG out of the truth path, and
`BND-INTELLIGENCE-CANNOT-BYPASS-WORLD` enforces it in the architecture gate.

`[PROPOSAL]` RAG's legitimate domain — **none of it authoritative about current
state**:

| RAG may answer | RAG must never answer |
|---|---|
| Runbooks, procedures | Current infrastructure state |
| Architecture and design docs | Current deployment state |
| Service ownership, on-call | Whether an action succeeded |
| Historical incident narratives | Current incident outcome |
| Configuration conventions | Any verification verdict |

`[PROPOSAL]` The rule to carry: **RAG proposes context; World establishes fact;
Assurance establishes outcome.** A retrieved document may suggest a hypothesis
and may never be cited as evidence for a verdict.

---

## Part G — Four categories that must not collapse

`[PROPOSAL]`

| Category | Store | Authority |
|---|---|---|
| **Truth** — what is the case now | World Plane (append-only, bitemporal) | Authoritative, with freshness and lineage |
| **Experience** — what happened before | Phase 8 experiential memory, calibration | Informative; never evidence for a current claim |
| **Documentation** — what people wrote | RAG / knowledge | Context only; never evidence |
| **Model reasoning** — what a model inferred | Reasoning trail (`cw_reasoning`) | Proposal only; never truth, outcome, verification or autonomy |
| **Verified outcome** — what Assurance concluded | `WorldVerification` | The only thing that may be called an outcome |

---

## Part H — Communication surfaces

`[FACT]` Present: Slack (1 module), Teams (1 module). Absent: email, PagerDuty,
webhooks, Opsgenie (0 each).

`[FACT]` Neither Slack nor Teams appears in any governed catalog — they are V1
and ungoverned.

`[INFERENCE]` The safest first communication surface is **outbound,
read-only notification** — no inbound command path. An inbound "approve from
Slack" button would create an approval path outside the action-digest binding
that ADR-090 exists to enforce.

---

## Part I — Multi-tenancy audit

`[FACT]` **89 of 96 route modules contain no reference to `tenant` at all.**
Only 7 do. Three take a tenant from a request body or query parameter.

`[FACT]` By contrast the governed engine enforces tenant everywhere and it is
proven: cross-tenant approvals refuse (9.9C, 9.10, 9.11), World queries are
tenant-scoped, and the credential broker checks tenancy against the
*authenticated context* rather than the request.

`[INFERENCE]` **This is the single largest product risk in Phase 10.** The V1
route surface is tenant-unaware. Building an incident workspace on top of it
would bypass tenant context — a stop condition.

`[PROPOSAL]` Phase 10.1 must introduce a **new** governed product API that
carries tenant from an authenticated context, and must not extend the V1 routes.

---

## Part J — Identity and RBAC

`[FACT]` `PrincipalKind` = `human`, `platform`, `external_system`.
`IdentityContext` = principal, capabilities, on_behalf_of, authenticated_at.

`[FACT]` V1 RBAC (`backend/auth/rbac.py`) is three roles — `owner`, `admin`,
`member` — over resource:action pairs (`missions`, `executions`, `connectors`,
`analytics`, `settings`, `users`, `projects` × `read`/`write`).

`[INFERENCE]` The V1 model expresses **permission** only. It cannot express
approval authority (which is digest-bound, per action) or autonomy authority
(which is platform-derived from calibration and never granted to a person). The
separation `capability ≠ permission ≠ autonomy` is therefore already structurally
true — not because RBAC enforces it, but because RBAC does not reach the other
two.

`[PROPOSAL]` Product roles (SRE, Incident Commander, Auditor…) map onto
**permission + approval authority**. They must not map onto autonomy: no role may
raise an autonomy ceiling, because that is derived from measured calibration.
Whether the existing RBAC can carry approval authority safely needs its own
discovery — it currently has no digest binding.

---

## Part K — Audit and compliance experience

`[FACT]` The audit chain is hash-chained and independently verifiable, and a full
durable-store scan finds **no credential in any column of any table** (9.10, 9.11).

`[FACT]` Present in durable state today: tenant, execution id, capability +
version + digest, `approval_artifact_id` (in the sealed binding and the audit
chain), authorization decision, worker identity, provider operation, provider
evidence, observation, outcome, `WorldVerification`.

`[INFERENCE]` The data for a complete human-readable execution record **already
exists**. What is missing is a reader that joins it. `[PROPOSAL]` A compliance
view is a *projection*, not a new store — duplicating the audit system is
explicitly out of scope.

---

## Part L — Observability

`[FACT]` Already instrumented and measured by harnesses: provider dials, provider
writes, refusals by gate, worker boundary facts, replay writes, fencing tokens,
crash markers, architecture violations.

`[PROPOSAL]` Product metrics worth surfacing, all derived from existing counters —
**no second telemetry authority**: governed read latency, write latency, refusals
by reason code, Assurance verdict distribution (SUPPORTED / UNSUPPORTED /
INSUFFICIENT_EVIDENCE), autonomy downgrades by gate, evidence staleness at
decision time.

`[INFERENCE]` The Assurance verdict distribution is the most product-meaningful
metric CortexPrime has, because INSUFFICIENT_EVIDENCE is a first-class outcome
rather than a failure.

---

## Part M — Measured performance baselines

`[FACT]` **Measured** on 2026-09-05, disposable k3d + local PostgreSQL, n=5 reads
and 1 write, on the hardened worker:

| Step | Measured |
|---|---|
| Runtime boot + composition | **3.56 s** |
| Governed read (median) | **0.52 s** (min 0.47, max 1.22) |
| Governed write, end to end | **1.19 s** |
| Post-write observe + derive | **0.97 s** |
| Assurance verdict | **0.13 s** |

`[FACT]` Also measured across 9.9C–9.11: negative-matrix Kubernetes mutations
**0**, replay provider writes **0**, fencing stale-holder rows **0** / live **1**,
pod `pids.max` **128** on 9/9 pods.

**Estimated:** none. **Target:** none. `[INFERENCE]` No SLA is proposed; these are
single-host development numbers and would not survive contact with a real cluster
under load.

---

## Part N — V1 strangler status

| Surface | Status | Evidence |
|---|---|---|
| V1 execution paths | `[FACT]` **QUARANTINE — holding** | legacy execution disabled, 0 ungated surfaces, guard/sandbox/credential-store all refuse when called (9.11 Part I) |
| V1 credential store | `[FACT]` **QUARANTINE** | refuses to construct |
| V1 route surface (185 routers) | `[PROPOSAL]` **DEPRECATE** — do not extend | tenant-unaware (Part I) |
| 138 frontend pages | `[PROPOSAL]` **REPLACE** for the incident vertical; leave the rest untouched | none reach the engine |
| RAG / knowledge / embeddings | `[PROPOSAL]` **MIGRATE** to context-only, subordinate to World | Part F |
| LLM gateway | `[FACT]` **BLOCKED** — Phase 5.5 credentials; proposer remains scripted | unchanged |
| MCP, agents, research, RCA | `[PROPOSAL]` **DEPRECATE / assess later** | out of scope for the first vertical |

`[FACT]` No V1 direct execution path exists. The prohibition holds.

---

## Part Q — 2026 competitive scan

### Web-verified facts

`[SOURCE]` The market has converged on **human-in-the-loop with tiered
autonomy**: "the realistic deployment pattern through 2026 is human-in-the-loop
for execution, with the agent doing investigation, generating a recommended fix,
and waiting for approval before touching production," rolled out "crawl-walk-run:
suggest, then approve, then auto-remediate only the failure classes the agent has
proven safe on."

`[SOURCE]` Policy-scoped action lists are standard practice — "writing the
policies that say which actions an agent can execute without approval (restart a
pod, yes; drain a node, no…)".

`[SOURCE]` **Komodor** — Kubernetes troubleshooting with the Klaudia AI agent,
claiming "97%+ accuracy across real-world incident resolution" and "up to 80%
MTTR reduction". `[INFERENCE]` These are vendor-claimed figures; the search
surfaced no independent verification methodology.

`[SOURCE]` **Shoreline** converts runbooks into fleet-wide automated remediation.
**Rootly** does AI incident management, timelines and postmortems, Slack-native.
**incident.io** ships a multi-agent AI SRE investigation with code-fix
suggestions. Azure SRE Agent and Resolve AI ship governance controls as standard.

`[SOURCE]` **Post-remediation verification is already a claimed market
capability**: the strongest platforms "explain why, propose a fix, and in the most
advanced cases carry out the remediation and confirm it worked." Blast-radius
statements before execution and full audit trails afterwards are also named as
expected features.

`[SOURCE]` The 2026 research frontier is precisely grounding: GSAR partitions
agent claims into "grounded, ungrounded, contradicted, complementary" because
trustworthiness "hinges on whether each claim is grounded in observed evidence
rather than model-internal inference." Hallucination rate is being treated as a
first-class operational metric. A 2026 survey reported **88% of organizations
experienced a confirmed or suspected AI agent security incident** in the prior
year.

### What this means for CortexPrime

`[INFERENCE]` **CortexPrime is not differentiated by having approval gates,
tiered autonomy, blast-radius statements, audit trails or post-action
verification.** All are claimed by shipping products. Any positioning that rests
on those is positioning on parity.

`[PRODUCT BET]` The defensible differences, stated as bets rather than verified
uniqueness — I have no evidence competitors *lack* these, only that the search
did not surface them:

1. **Uncertainty is a first-class verdict.** `INSUFFICIENT_EVIDENCE` is a real
   outcome; STALE ≠ FALSE, CONFLICTED ≠ FALSE, UNKNOWN ≠ FALSE. `[SOURCE]` The
   grounding literature treats this as the open problem; `[FACT]` CortexPrime
   ships it as a verdict the verifier can return.
2. **Lineage-aware corroboration.** Two sources that share an origin are
   CORRELATED, not INDEPENDENT `[FACT]` (9.4, keyed on the instrument).
3. **No invented confidence.** `[FACT]` No numeric confidence anywhere;
   reliability is empirical calibration over decided outcomes.
4. **Structural rather than configured refusal.** `[FACT]` The platform refused
   its own first write for three consecutive phases on its own invariants
   (ADR-086, 087, 089) — a property of the architecture, not of a policy file.

`[INFERENCE]` **CortexPrime's weakness against this market is stark and should be
stated plainly**: competitors have products; CortexPrime has an engine with no UI,
one commissioned write capability, and a scripted model proposer. On breadth of
integration, time-to-value and proven scale, it is far behind.

---

## Sources

- [Top 5 Use Cases for Autonomous Operations in SRE (2026)](https://stackgen.com/blog/top-5-use-cases-for-autonomous-operations-in-sre-2026)
- [How The SRE Role Is Changing In The Age Of Agentic AI — Komodor](https://komodor.com/learn/how-the-sre-role-is-changing-in-the-age-of-agentic-ai/)
- [AI SRE Agents: Autonomous Kubernetes Operations — Edixos](https://edixos.com/en/blog/ai-sre-agents-autonomous-operations/)
- [Komodor Expands AI SRE Platform with Klaudia Memory](https://finance.yahoo.com/technology/ai/articles/komodor-expands-ai-sre-platform-130400602.html)
- [Top 11 AI SRE Tools in 2026](https://www.sherlocks.ai/blog/top-ai-sre-tools-in-2026)
- [AI SRE explained — incident.io](https://incident.io/blog/what-is-ai-sre-complete-guide-2026)
- [GSAR: Typed Grounding for Hallucination Detection and Recovery in Multi-Agent LLMs](https://arxiv.org/abs/2604.23366)
- [Cascading Hallucination in Agentic RAG: The CHARM Framework](https://arxiv.org/pdf/2606.04435)
- [Building Production-Ready AI Agents in 2026 — MLflow](https://mlflow.org/articles/building-production-ready-ai-agents-in-2026/)
- [The Best AIOps Platforms in 2026 — Ops Singularity](https://www.opssingularity.com/blog/blog-top-aiops-platforms.html)
- [AIOps Platforms: The Complete 2026 Buyer's Guide](https://novaaiops.com/blog/aiops-platforms-buyers-guide-2026)
