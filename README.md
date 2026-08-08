# CortexPrime

**An autonomous DevOps operating platform — built so that an AI can be trusted with production access.**

CortexPrime detects real infrastructure problems, explains the root cause, and proposes or performs the fix. The hard part is not making an AI act. It is making an AI act on production systems in a way an enterprise can actually authorise, audit, and stop.

That constraint shapes every line of this codebase.

---

## The problem

Every "AI agent that runs commands" demo works until it meets a real estate. Then the questions start:

- Who approved this action, and against exactly which version of it?
- The API call timed out — did the deletion happen or not?
- The tool description says it reads data. What if it doesn't?
- A tenant's private capability just appeared in another tenant's list. How?
- The agent retried a failed payment. Was that safe?
- Something changed at 3am. What ran, under whose authority, and can we prove it?

Most agent frameworks cannot answer these. They treat safety as a prompt or a wrapper. CortexPrime treats it as **architecture**: the unsafe operation is not blocked at runtime, it is *unrepresentable* in the type system and the control flow.

---

## The thesis

Six separations, each enforced in code rather than convention:

```
existence  ≠  trust  ≠  permission  ≠  selection  ≠  binding  ≠  execution
```

A capability existing in the registry does not mean it is trusted. Trusted does not mean a given user may use it. Permission does not decide *which* implementation runs. Selection does not grant standing authority. And a binding made 30 seconds ago is re-verified before anything touches a real system.

Some concrete consequences, all implemented and tested:

| Invariant | Why it exists |
|---|---|
| **"Unknown" is a first-class outcome** | A lapsed lease or lost response means *nobody knows* whether the change landed. Calling that "failed" and retrying is how a delete runs twice. |
| **Undeclared effects never default to safe** | A tool that doesn't say whether it mutates is treated as the most dangerous case, not the most convenient one. |
| **No silent retry** | Every retry is a recorded decision with a reason. Ambiguity is checked *before* worthwhileness, so an operation that must not repeat is refused even when the error looks retryable. |
| **Revocation is terminal** | A revoked capability has no transition back. Restoring it means a new version and a new decision — not flipping a boolean. |
| **Separation of duties** | Whoever registers a capability cannot be the one who enables or trusts it. |
| **Replay cannot execute** | The replay engine holds no repository, no worker pool, no queue. Re-running history is structurally impossible, not merely discouraged. |
| **Fails closed everywhere** | Policy engine unreachable → deny. Worker unresolvable → refuse. No default worker, no default tenant, no fallback provider. |
| **No LLM in the security path** | Authorization and provider selection are deterministic and inspectable. A model may later *suggest*; it never decides. |

**Exactly-once is never claimed.** Nothing that crosses a network can honestly promise it. The system models the choice — at-least-once with idempotency, or at-most-once with surfaced ambiguity — and says which one it is making.

---

## Architecture

```
  USER INTENT
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│  MISSION CONTROL PLANE          what should happen           │
│                                                              │
│  Mission → Intent → Planner → Workflow → approved graph      │
└──────────────────────────────┬──────────────────────────────┘
                               │  digest-verified handoff
┌──────────────────────────────▼──────────────────────────────┐
│  CAPABILITY FABRIC              what may happen               │
│                                                              │
│  Identity → Discovery → Authorization → Resolution → Binding │
└──────────────────────────────┬──────────────────────────────┘
                               │  immutable, expiring binding
┌──────────────────────────────▼──────────────────────────────┐
│  EXECUTION RUNTIME             what did happen                │
│                                                              │
│  Leases · Attempts · Checkpoints · Recovery · Replay · Audit │
└──────────────────────────────┬──────────────────────────────┘
                               │  worker contract  (Phase 3.3)
                               ▼
                    Workers / Connectors / MCP
```

**12 bounded contexts**, each owning one responsibility and forbidden from importing another. Cross-context wiring happens only in named composition roots, so "what talks to what" is one greppable file rather than an archaeology project.

---

## Current status

Honest, because anyone technical will check.

| Layer | State |
|---|---|
| Mission → Intent → Planner → Workflow control plane | **Implemented** — full lifecycle, policy gates, digest binding |
| Durable execution core (leases, attempts, checkpoints, recovery, replay) | **Implemented** |
| Capability Fabric (identity, discovery, authorization, resolution, binding) | **Implemented** |
| Worker execution contract | **Implemented** — the contract and the pre-execution gate |
| Workers & connectors (shell, Docker, K8s, MCP, GitHub, AWS…) | **Not built** — next phase |
| Durable persistence | **Not built** — repositories are in-memory behind Protocols |
| Credential management | **Not built** — Protocol seam only |
| Authorization policy engine | **Placeholder** — coarse grant checks, designed for replacement |
| V1 agent runtime (agents, memory, voice, browser, ~50 UI screens) | **Working** — the product this architecture is being built beneath |

The V2 architecture is being introduced under the working V1 system via a strangler migration. V1 proved the product; V2 is making it safe enough to sell to an enterprise.

---

## Why the engineering is the moat

Ambitious AI products are easy to demo and hard to trust. What is unusual here is not the feature list — it is that the safety properties are **mechanically enforced**:

- **27 Architecture Decision Records.** Every non-obvious choice is written down with its reasoning, its cost, and what it deliberately does *not* claim.
- **A written Constitution, executed as CI.** 22 architectural rules run as fitness functions on every pull request. A blocking violation fails the build — bounded-context isolation, tenancy on every repository method, no new authoritative file stores, dependency direction. Architecture that drifts is architecture that was never enforced.
- **Documentation that refuses to oversell.** The ADRs contain explicit "what this does not claim" sections. Where persistence is in-memory, it says so. Where a code branch is currently unreachable, it says so.
- **Failures are first-class.** Denials, refusals, ambiguity and unknown outcomes are modelled, recorded and auditable. A security system that only logs successes cannot explain why an attack was stopped.

```
.github/workflows/architecture.yml   →  Constitution fitness functions
docs/adr/                            →  27 decision records
backend/platform/architecture/       →  the rules themselves
```

---

## Tech stack

**Backend** — Python 3.13, FastAPI, domain-driven design with strict bounded contexts
**Frontend** — Next.js, TypeScript, Zustand, live WebSocket event streaming (~50 screens)
**AI** — OpenAI, Anthropic, Google Gemini, Ollama (provider-routed)
**Data** — PostgreSQL, Redis, ChromaDB, Neo4j
**Infra** — Docker, Kubernetes (Helm charts), GitHub Actions CI

Scale: ~1,000 backend modules · ~1,800 frontend modules · 231 test files

---

## Repository map

```
backend/
  contexts/          12 bounded contexts (the V2 architecture)
  contracts/         published vocabulary shared across contexts
  platform/          hashing, identity, events, audit, storage, architecture rules
  api/               REST surface + composition roots
docs/adr/            27 architecture decision records
tests/               unit, architecture, integration
frontend/            Next.js application
helm/ · infra/       deployment
```

---

## Getting started

```bash
# Backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example backend/.env                      # add your API keys
uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev         # http://localhost:3000
```

Verify the architecture gate locally:

```bash
python -c "from backend.platform.architecture import analyze; r=analyze(); print('gate passed:', r.gate_passed)"
```

---

## Roadmap

| Phase | Scope | State |
|---|---|---|
| 1 | Platform foundations, audit, tenancy, Constitution-as-CI | Complete |
| 2 | Mission Control Plane + authoritative workflow handoff | Complete |
| 3.1 | Durable execution core | Complete |
| 3.2 | Capability Fabric — identity → binding | Complete |
| 3.3.1 | Worker execution contract | Complete |
| 3.3.2 | Worker & connector implementations | Next |
| 3.4 | Evidence plane, telemetry, root-cause analysis | Planned |
| 4 | Durable persistence, production hardening | Planned |

---

## For reviewers and investors

The fastest way to judge this codebase is not the feature list — it is `docs/adr/`. Each record states a decision, the failure mode it prevents, what it costs, and what it explicitly does not claim.

Three worth reading first:

- **[ADR-031 — Durable Execution Core](docs/adr/ADR-031-durable-execution-core.md)** — why "unknown" is a first-class outcome and why exactly-once is never claimed
- **[ADR-034 — Capability Authorization](docs/adr/ADR-034-capability-authorization-and-admission.md)** — default deny, separation of duties, and closing the time-of-check/time-of-use gap
- **[ADR-036 — Execution Worker Contract](docs/adr/ADR-036-execution-worker-contract.md)** — the seven refusals that gate anything touching a real system

---

<sub>© CortexPrime. Private and proprietary. All rights reserved. This repository and its contents are confidential and may not be copied, distributed, or disclosed without written permission.</sub>
