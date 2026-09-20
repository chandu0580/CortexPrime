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
| **Separation of duties** | Whoever registers a capability cannot be the one who enables or trusts it. The requester of an action cannot approve it. |
| **Replay cannot execute** | The replay engine holds no repository, no worker pool, no queue. Re-running history is structurally impossible, not merely discouraged. |
| **Outcomes are established independently** | A worker reporting success is not success. The world is re-read through a separate path before anything is called done. |
| **Fails closed everywhere** | Policy engine unreachable → deny. Worker unresolvable → refuse. No default worker, no default tenant, no fallback provider. |
| **No LLM in the security path** | Authorization and provider selection are deterministic and inspectable. A model may *propose*; it never decides. |

**Exactly-once is never claimed.** Nothing that crosses a network can honestly promise it. The system provides durable at-least-once dispatch with a revision-checked claim, idempotency where the provider supports it, and independent verification — and says so.

---

## Architecture

```
  API   ·   Agent   ·   Scheduler   ·   ChatOps
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  CAPABILITY FABRIC              what may happen              │
│                                                              │
│  Identity → Tenant → Authorization → Policy/Risk →           │
│  Approval/Autonomy → Action digest → Binding                 │
└──────────────────────────────┬──────────────────────────────┘
                               │  immutable, expiring binding
┌──────────────────────────────▼──────────────────────────────┐
│  DURABLE EXECUTION             what did happen               │
│                                                              │
│  Revision-checked claim · Leases · Attempts · Recovery ·     │
│  Replay · Hash-chained audit                                 │
└──────────────────────────────┬──────────────────────────────┘
                               │  one governed path, no bypass
┌──────────────────────────────▼──────────────────────────────┐
│  CONTAINED WORKERS             who may touch the world       │
│                                                              │
│  Own container · non-root · read-only rootfs · no standing   │
│  credential · compiled bindings · egress allow-list          │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
              Kubernetes   ·   GitHub   ·   (next connector)
                               │
                               ▼
                    INDEPENDENT VERIFICATION
```

**13 bounded contexts**, each owning one responsibility and forbidden from importing another. Cross-context wiring happens only in named composition roots, so "what talks to what" is one greppable file rather than an archaeology project.

---

## Current status

Honest, because anyone technical will check. Claims below are marked **proven** only where a real external system was changed and the change was verified independently.

| Layer | State |
|---|---|
| Capability Fabric (identity → tenant → authorization → approval → digest → binding) | **Proven** |
| Durable execution core (claim, leases, attempts, recovery, replay) | **Proven** |
| Durable persistence (PostgreSQL, bitemporal world/fact/verification ledgers) | **Proven** |
| Credential management (Vault, per-action, never in env/logs/records) | **Proven** |
| Contained workers (own container, no standing credential, egress-fenced) | **Proven** |
| Hash-chained audit, fenced single writer | **Proven** |
| **Kubernetes connector** — 8 reads + governed restart + governed rollback | **LOCKED** — real cluster, real rollback, independently verified |
| **GitHub connector** — 9 reads + one governed issue comment | **NOT LOCKED** — see blockers |
| Multi-replica operation (leader-elected singletons, idempotency-fenced) | **Proven** — 2 replicas, one holder per role |
| Asynchronous execution API (submit, leave, come back) | **Partial** — the receipt and status path works; the async *write* does not yet land |
| Governed execution reachable from the product API | **Partial** — one route, Kubernetes remediation capabilities only |
| MCP surface | **Legacy/gated** — the V1 MCP path is disabled and does not reach the governed plane |
| V1 agent runtime (agents, memory, voice, browser, ~50 UI screens) | **Working** — the product this architecture is being built beneath |

### Known blockers, stated plainly

- **GitHub is not locked.** The production credential — a GitHub App installation token — is implemented and covered by deterministic tests including a real RSA signature, but has never authenticated against `api.github.com`. Locking on the development token path would claim a production auth path that was never exercised.
- **An asynchronous write does not complete.** It is refused after the node is leased, and the refusal's reason is not persisted (the gateway sets it; it does not survive into the durable record). That missing reason is the next thing to fix, because without it the refusal cannot be diagnosed from the record at all.
- **The V1 plane is legacy.** Its writes are gated off, its MCP execution path is disabled, and none of the governed capabilities above appear in its UI.

---

## Why the engineering is the moat

Ambitious AI products are easy to demo and hard to trust. What is unusual here is not the feature list — it is that the safety properties are **mechanically enforced**, and that the failures are written down.

- **118 Architecture Decision Records.** Every non-obvious choice is recorded with its reasoning, its cost, and what it deliberately does *not* claim.
- **A written Constitution, executed as CI.** 43 architectural rules run as fitness functions on every pull request. A blocking violation fails the build — bounded-context isolation, tenancy on every repository method, no ungated execution site, dependency direction.
- **Findings are published, including the ones that were refuted.** Each phase report lists what broke, what it cost, and what was *hypothesised and then disproved by its own test*. A finding nobody can reproduce is not a finding.
- **Failures are first-class.** Denials, refusals, ambiguity and unknown outcomes are modelled, recorded and auditable. A security system that only logs successes cannot explain why an attack was stopped.

A representative lesson, from the phase that made execution durable:

> Three defects were found on the dispatch path, two of them introduced by that phase's own fixes. None was reachable by deterministic testing — one needed four real processes racing, another needed a real cluster with real accumulated data. A change to a concurrency path is unproven until real concurrency *and* real data volume have run against it.

```
.github/workflows/architecture.yml   →  Constitution fitness functions
docs/adr/                            →  118 decision records
backend/platform/architecture/       →  the rules themselves
```

---

## Tech stack

**Backend** — Python 3.11, FastAPI, domain-driven design with strict bounded contexts
**Frontend** — Next.js, TypeScript, Zustand, live WebSocket event streaming (~50 screens)
**AI** — OpenAI-compatible, Anthropic, Google Gemini, Ollama (provider-routed; GLM-5.2 in the governed investigator)
**Data** — PostgreSQL (durable governed plane), Redis, ChromaDB, Neo4j
**Infra** — Docker, Kubernetes (Helm chart), HashiCorp Vault, GitHub Actions CI

Scale: ~1,200 backend modules · ~1,800 frontend modules · 311 test files · 118 ADRs

---

## Repository map

```
backend/
  contexts/          13 bounded contexts (the governed architecture)
  contracts/         published vocabulary shared across contexts
  platform/          hashing, identity, events, audit, storage, architecture rules
  api/               REST surface + composition roots
docs/adr/            118 architecture decision records
docs/PHASE_*.md      verification reports (FACT / INFERENCE / UNKNOWN)
tests/               unit, architecture, integration, connector fabric
scripts/             phase harnesses and demonstrations
frontend/            Next.js application
helm/ · infra/       deployment
workers/             contained worker implementations (digest-pinned)
```

---

## Getting started

### The governed plane (what the architecture above describes)

Needs a Kubernetes cluster (k3d is fine), PostgreSQL and Vault.

```bash
helm upgrade --install cortexprime ./helm/cortexprime-governed -n cortexprime \
  --set connection.tenant=<tenant> \
  --set connection.namespace=<namespace> \
  --set database.existingSecret=<secret> \
  --wait
```

Then, as a member of the connected tenant:

```
GET  /api/v1/connectors            # health, per connector, through the governed path
GET  /api/v1/approvals             # the human approval queue
POST /api/v1/approvals/{id}/decision
POST /api/v1/approvals/{id}/execute
GET  /api/v1/executions/{id}       # durable status; the caller need not wait
```

See `docs/KUBERNETES_CONNECTOR_RUNBOOK.md` and `docs/GITHUB_CONNECTOR_RUNBOOK.md`.

### See one governed change, end to end

```bash
python scripts/demo_governed_write.py --slow
```

Seven steps: an anonymous caller refused; connector health read as the tenant; a change requiring a human approval; a member *without* approve authority refused; the scoped approver granting it; the action running through a contained worker; and finally Kubernetes itself — not CortexPrime's own reply — confirming the workload restarted.

### The V1 application

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example backend/.env                      # add your API keys
uvicorn backend.main:app --reload --port 8000

cd frontend && npm install && npm run dev         # http://localhost:3000
```

On a host already running many containers, set `CORTEX_DISABLE_DOCKER_EVENTS=1`: the V1 Docker event listener writes through to a JSON store on every event and can prevent startup from completing.

Verify the architecture gate locally:

```bash
python -c "from backend.platform.architecture import analyze; r=analyze(); print('gate passed:', r.gate_passed)"
```

---

## Roadmap

| Phase | Scope | State |
|---|---|---|
| 1–3 | Platform foundations, Mission Control, durable execution, Capability Fabric | Complete |
| 7 | World / Intelligence / Assurance planes, bitemporal truth | Complete |
| 8 | Governed intelligence: investigation, prediction, calibration, autonomy tiers | Complete |
| 9 | First real governed write, contained workers, isolation taxonomy | Complete |
| 10 | Productization, tenancy, trust boundary | Complete |
| 11.1 | Kubernetes reference connector | **Locked** |
| 11.2 | GitHub connector — the architecture carried to a second provider | Not locked (App auth) |
| 11.3 | Governed execution fabric — dispatch survives the process that created it | Complete |
| 11.4 | Async API, multi-replica, final gate | Partial |
| Next | Close the async write, lock GitHub, then Connector #3 | Planned |

---

## For reviewers

The fastest way to judge this codebase is not the feature list — it is `docs/adr/` and the phase verification reports. Each states a decision, the failure mode it prevents, what it costs, and what it explicitly does not claim.

Worth reading first:

- **[ADR-031 — Durable Execution Core](docs/adr/ADR-031-durable-execution-core.md)** — why "unknown" is a first-class outcome and why exactly-once is never claimed
- **[ADR-125 — The Kubernetes Reference Connector](docs/adr/ADR-125-phase-11-1-kubernetes-reference-connector.md)** — what a production connector actually requires
- **[ADR-127 — The Governed Execution Fabric](docs/adr/ADR-127-phase-11-3-governed-execution-fabric.md)** — how a limitation turned out to be the only thing preventing duplicate execution
- **[ADR-128 — Final Execution Gate](docs/adr/ADR-128-phase-11-4-final-execution-gate.md)** — six findings from running two replicas, three of them self-inflicted

---

<sub>© CortexPrime. Private and proprietary. All rights reserved. This repository and its contents are confidential and may not be copied, distributed, or disclosed without written permission.</sub>
