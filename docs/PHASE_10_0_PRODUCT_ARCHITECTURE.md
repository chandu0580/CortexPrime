# Phase 10.0 — Product Architecture Proposal

**Proposal only. Nothing here is implemented.** Labels: `[FACT]`, `[SOURCE]`,
`[INFERENCE]`, `[PROPOSAL]`.

Companion to `docs/PHASE_10_0_PRODUCT_DISCOVERY.md`.

---

## Part O — Target architecture

`[PROPOSAL]`

```
   PRODUCT / UI                    (new, thin)
        │  authenticated context carries TENANT
        ▼
   PRODUCT API BOUNDARY            (new, thin — the only new authority-free layer)
        │
        ├──────────────► KNOWLEDGE / RAG ──► CONTEXT ENRICHMENT
        │                (proposes; never cited as evidence)
        ▼
   INTELLIGENCE        (existing — proposes, never decides)
        ▼
   WORLD               (existing — append-only, bitemporal, authoritative)
        ▼
   ASSURANCE           (existing — independent verdicts)
        ▼
   GOVERNED EXECUTION  (existing — approval → authorization → autonomy → gateway)
        ▼
   CONTAINED WORKER ──► PROVIDER
```

### The four arrows that must never exist

`[PROPOSAL]` Each is already structurally prevented; Phase 10 must not create a
path around any of them:

| Forbidden | Prevented today by |
|---|---|
| `RAG → TRUTH` | `[FACT]` `BND-INTELLIGENCE-CANNOT-BYPASS-WORLD` |
| `MODEL → EXECUTION` | `[FACT]` `BND-INTELLIGENCE-CANNOT-EXECUTE`; `ProviderAuthority` only obtainable from the gateway |
| `WORLD → EXECUTION` | `[FACT]` `BND-WORLD-CANNOT-EXECUTE` |
| `UI → PROVIDER` | `[FACT]` `BND-DIRECT-HTTP`, `BND-PROVIDER-SDK`, `BND-EFFECT-GATE` |

`[INFERENCE]` The product API boundary is the **only** genuinely new layer. It
holds no authority: it reads projections and submits requests into the existing
chain. If it ever needs to decide something, that is the signal that it is
becoming a second governance authority.

---

## Part P — First product vertical

### Candidates evaluated

| Candidate | User value | Technical readiness | Safety | Differentiation | Cost |
|---|---|---|---|---|---|
| **A. AI Incident Investigator (read-only)** | High — the daily job | `[FACT]` Engine verified 9.1–9.5 | `[FACT]` Highest: zero writes | Medium — market parity on investigation | **Low** — no new governance |
| B. Investigator + governed remediation | High | `[FACT]` Verified 9.6–9.11 | Medium — real writes | High | Medium |
| C. Compliance / audit console | Medium | `[FACT]` Data exists (Part K) | Highest | Low | Low |
| D. Knowledge/RAG copilot | Low–medium | `[FACT]` 213 modules exist, ungoverned | Low — RAG-as-truth risk | Very low | Medium |

### Selection

`[PROPOSAL]` **A, then B — as two phases, not one.**

`[INFERENCE]` The reasoning:

- The engine's *read* half (9.1–9.5) is verified and has **zero** write risk. A
  read-only investigator can be put in front of users without touching a single
  governance invariant.
- The *write* half is verified but has exactly **one** commissioned capability
  (`kubernetes.workload.rollout_restart`). A product that leads with remediation
  would be a product with one button.
- `[SOURCE]` The market's own recommended rollout is "crawl-walk-run: suggest,
  then approve, then auto-remediate". Shipping investigation first is the same
  sequence, and it is the sequence the safety argument supports independently.
- D is rejected outright: it is the one candidate that pushes *toward* the
  RAG-as-truth failure Phase 8 exists to prevent.

`[PROPOSAL]` The vertical: **"Show me why, with evidence I can check."** An
incident workspace that renders hypotheses, the evidence for and against each,
the lineage and freshness of that evidence, and — explicitly — what is not known.
Remediation arrives later, behind the approval UX, with the single capability
that is actually proven.

---

## Part R — Phase 10 roadmap, evidence-ordered

`[PROPOSAL]` Reordered from the brief's suggestion. The driver is Part A: **the
engine has no HTTP surface**, and Part I: **the V1 route surface is
tenant-unaware**. Nothing user-facing can be built until those are addressed, so
the API boundary is first and is not merged with the UI.

### 10.1 — Governed Product API boundary

- **Central question:** can the verified engine be exposed over HTTP without
  creating a second authority or losing tenant context?
- **Scope:** read-only projections — investigation, hypotheses, evidence with
  lineage and freshness, autonomy decision, approval state, audit record.
- **Reuse:** `WorldQuery`, `Investigation`, `AssuranceVerifier`, audit chain,
  existing auth middleware for tenant.
- **New code:** route modules + response projections. **No** new persistence.
- **Security:** every endpoint derives tenant from the authenticated context,
  never from a body or path. `[FACT]` This is the 89/96 problem.
- **Stop conditions:** any endpoint that decides, authorizes, writes, or accepts
  a tenant from the request.
- **DoD:** every projection tenant-scoped and proven cross-tenant-refusing; zero
  new authority; architecture gate green.

### 10.2 — Incident workspace (read-only)

- **Central question:** can an engineer reach a supported conclusion from the UI
  alone, including when the answer is "not enough evidence"?
- **Reuse:** 10.1 only. **New:** frontend. **No** backend authority.
- **Stop conditions:** UI computing a verdict, inventing a confidence number, or
  rendering STALE/CONFLICTED/UNKNOWN as false or as absent.
- **DoD:** a real k3d CrashLoopBackOff investigated end to end through the UI,
  with residual uncertainty visible.

### 10.3 — Human approval UX

- **Central question:** can a human approve *this exact action* from a UI without
  weakening the action-digest binding?
- **Reuse:** `ApprovalFacts`, `canonical_approval_digest` (ADR-090).
- **Security:** the UI shows the action and its digest; approval binds to that
  digest. `[FACT]` An approval for workload A must still refuse workload B.
- **Stop conditions:** approval by reference-only, inbound approval from a chat
  surface, or any path where the digest is supplied by the client.
- **DoD:** the 9.9C negative matrix re-run *through the product path*, at zero
  Kubernetes mutations.

### 10.4 — Governed remediation in the product

- Only after 10.3. One capability. `[PROPOSAL]` Repeat 9.9B–9.10 for any second
  capability before commissioning it.

### 10.5 — Context enrichment (RAG, subordinate)

- **Central question:** can retrieved documents inform a hypothesis without ever
  becoming evidence?
- **Stop conditions:** a retrieved document appearing in an evidence list, an
  Assurance citation, or any verdict.

### 10.6 — Notifications (outbound only)

- `[INFERENCE]` Outbound Slack first. No inbound command path (Part H).

### 10.7 — Audit / compliance projection
### 10.8 — Product observability
### 10.9 — Enterprise RBAC (approval authority; never autonomy)
### 10.10 — Production-readiness gate

`[INFERENCE]` RBAC moved late deliberately: `[FACT]` the governed engine already
enforces tenant and approval binding, so product roles are a convenience layer.
Building them early would invite expressing approval authority in the V1 RBAC
model, which has no digest binding.

---

## Part S — Invariants carried forward

`[PROPOSAL]` All of the following remain in force and **none may be weakened for
UX convenience**:

model output ≠ truth · ≠ outcome · ≠ verification · ≠ autonomy · World cannot
execute · Intelligence cannot execute · Assurance cannot execute · one execution
authority · one governance path · tenant isolation · append-only ledgers ·
bitemporal semantics · lineage honesty · UNKNOWN ≠ FALSE · STALE ≠ FALSE ·
CONFLICTED ≠ FALSE · no invented confidence · no self-verification · no
self-authorization · no autonomy self-promotion · no direct provider access · no
secret persistence · at-least-once · **never claim exactly-once** · L1–L16.

`[INFERENCE]` Three are most at risk from product pressure specifically:

1. **No invented confidence.** A UI wants a percentage. There isn't one.
2. **UNKNOWN ≠ FALSE.** A UI wants a green tick. INSUFFICIENT_EVIDENCE is not a
   failure and must not render as one.
3. **No autonomy self-promotion.** A customer will ask for a toggle to raise the
   autonomy level. It is derived from measured calibration and there is no toggle.

---

## Part T — Stop-condition audit

`[PROPOSAL]` Tested against the proposed architecture:

| Stop condition | Does 10.0's proposal introduce it? |
|---|---|
| Second execution authority | **No** — product API submits into the existing chain |
| Second governance authority | **No** — the boundary decides nothing |
| Second approval authority | **No** — reuses `ApprovalFacts` + action digest |
| Second credential broker | **No** — product layer never touches credentials |
| Second truth store | **No** — a thin `Incident` would reference, not absorb |
| Model-driven authorization | **No** |
| Tenant bypass | **Risk identified, mitigated by design** — `[FACT]` 89/96 V1 routes are tenant-unaware, so 10.1 builds new endpoints rather than extending them |
| RAG-as-truth | **No** — 10.5 gated, and fenced by an existing rule |
| UI bypassing backend governance | **No** — UI holds no capability |
| Direct provider access | **No** |
| Secret persistence | **No** |
| Unsafe caching | **Risk noted** — any product cache of World state must carry `observed_at`/`retrieved_at` or it presents stale evidence as current |
| Cross-tenant context | **Risk noted** — RAG retrieval must be tenant-scoped before 10.5 |
| Stale evidence as current truth | **Risk noted** — freshness must be rendered, not stripped |

**Result: PASS.** `[INFERENCE]` No stop condition is introduced. Four risks are
identified and each is assigned to the phase that must address it. The tenant risk
is the load-bearing one and is why 10.1 is first.
