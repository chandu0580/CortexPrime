<div align="center">

<img src="docs/assets/banner.svg" alt="CortexPrime — an autonomous DevOps operating platform" width="100%">

<br>

[![Architecture Gate](https://github.com/chandu0580/CortexPrime/actions/workflows/architecture.yml/badge.svg)](https://github.com/chandu0580/CortexPrime/actions/workflows/architecture.yml)
[![CI](https://github.com/chandu0580/CortexPrime/actions/workflows/ci.yml/badge.svg)](https://github.com/chandu0580/CortexPrime/actions/workflows/ci.yml)
[![Security Scan](https://github.com/chandu0580/CortexPrime/actions/workflows/security.yml/badge.svg)](https://github.com/chandu0580/CortexPrime/actions/workflows/security.yml)

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-Helm-326CE5?logo=kubernetes&logoColor=white)
![Vault](https://img.shields.io/badge/HashiCorp-Vault-FFEC6E?logo=vault&logoColor=black)
![ADRs](https://img.shields.io/badge/ADRs-118-38B88A)
![Fitness functions](https://img.shields.io/badge/architecture%20rules-43-38B88A)

**[Architecture](#architecture) · [Status](#status) · [Quickstart](#quickstart) · [Security model](#security-model) · [Decision records](#decision-records)**

</div>

---

## Why this exists

Every "AI agent that runs commands" demo works until it meets a real estate. Then the questions start.

> *Who approved this action, and against exactly which version of it?*
> *The API call timed out — did the deletion happen, or not?*
> *The tool description says it only reads. What if it doesn't?*
> *Something changed at 3am. What ran, under whose authority, and can we prove it?*

Most agent frameworks cannot answer these. They treat safety as a prompt, or a wrapper around a shell. CortexPrime treats it as **architecture**: the unsafe operation is not blocked at runtime — it is *unrepresentable* in the type system and the control flow.

CortexPrime detects real infrastructure problems, explains the root cause, and proposes or performs the fix. The hard part is not making an AI act. It is making an AI act on production systems in a way an enterprise can authorise, audit, and stop.

---

## The thesis

Six separations, each enforced in code rather than convention:

```
existence  ≠  trust  ≠  permission  ≠  selection  ≠  binding  ≠  execution
```

A capability existing in the registry does not mean it is trusted. Trusted does not mean a given user may use it. Permission does not decide *which* implementation runs. Selection does not grant standing authority. And a binding made 30 seconds ago is re-verified before anything touches a real system.

<table>
<tr><th align="left">Invariant</th><th align="left">The failure it prevents</th></tr>
<tr><td><b>“Unknown” is a first-class outcome</b></td><td>A lapsed lease or lost response means <i>nobody knows</i> whether the change landed. Calling that “failed” and retrying is how a delete runs twice.</td></tr>
<tr><td><b>Undeclared effects never default to safe</b></td><td>A tool that doesn’t say whether it mutates is treated as the most dangerous case, not the most convenient one.</td></tr>
<tr><td><b>No silent retry</b></td><td>Every retry is a recorded decision with a reason. Ambiguity is checked <i>before</i> worthwhileness, so an operation that must not repeat is refused even when the error looks retryable.</td></tr>
<tr><td><b>Revocation is terminal</b></td><td>A revoked capability has no transition back. Restoring it means a new version and a new decision — not flipping a boolean.</td></tr>
<tr><td><b>Separation of duties</b></td><td>Whoever registers a capability cannot enable or trust it. Whoever requests an action cannot approve it.</td></tr>
<tr><td><b>Replay cannot execute</b></td><td>The replay engine holds no repository, no worker pool, no queue. Re-running history is structurally impossible, not merely discouraged.</td></tr>
<tr><td><b>Outcomes are established independently</b></td><td>A worker reporting success is not success. The world is re-read through a separate path before anything is called done.</td></tr>
<tr><td><b>Fails closed everywhere</b></td><td>Policy engine unreachable → deny. Worker unresolvable → refuse. No default worker, no default tenant, no fallback provider.</td></tr>
<tr><td><b>No LLM in the security path</b></td><td>Authorization and provider selection are deterministic and inspectable. A model may <i>propose</i>; it never decides.</td></tr>
</table>

> **Exactly-once is never claimed.** Nothing that crosses a network can honestly promise it. CortexPrime provides durable at-least-once dispatch with a revision-checked claim, idempotency where the provider supports it, and independent verification — and says so.

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

**13 bounded contexts**, each owning one responsibility and forbidden from importing another. Cross-context wiring happens only in named composition roots, so *what talks to what* is one greppable file rather than an archaeology project.

---

## Status

Marked **Proven** only where a real external system was changed and the change was verified through an independent path.

| Capability | State |
|---|:--|
| Capability Fabric — identity → tenant → authorization → approval → digest → binding | ✅ **Proven** |
| Durable execution — claim, leases, attempts, recovery, replay | ✅ **Proven** |
| Durable persistence — PostgreSQL, bitemporal world/fact/verification ledgers | ✅ **Proven** |
| Credential management — Vault, per-action, never in env, logs or records | ✅ **Proven** |
| Contained workers — own container, no standing credential, egress-fenced | ✅ **Proven** |
| Hash-chained audit with a fenced single writer | ✅ **Proven** |
| Multi-replica operation — leader-elected singletons, idempotency-fenced | ✅ **Proven** |
| **Kubernetes connector** — 8 reads · governed restart · governed rollback | 🔒 **Locked** |
| **GitHub connector** — 9 reads · one governed issue comment | 🟡 Not locked — *see limitations* |
| Asynchronous execution API — submit, leave, come back | 🟡 Partial |
| Governed execution from the product API | 🟡 Partial — one route, Kubernetes capabilities |
| MCP surface | ⛔ Legacy, gated off |
| V1 agent runtime — agents, memory, voice, browser, ~50 screens | ✅ Working |

<details>
<summary><b>Known limitations, stated plainly</b> — click to expand</summary>

<br>

**GitHub is not locked.** The production credential — a GitHub App installation token — is implemented and covered by deterministic tests including a real RSA signature, but has never authenticated against `api.github.com`. Locking on the development token path would claim a production auth path that was never exercised.

**An asynchronous write does not complete.** It is refused after the node is leased, and the refusal's reason is not persisted — the gateway sets it, but it does not survive into the durable record. That missing reason is the next thing to fix, because without it the refusal cannot be diagnosed from the record at all.

**The V1 plane is legacy.** Its writes are gated off, its MCP execution path is disabled, and none of the governed capabilities above appear in its UI.

*This section exists on purpose. A status table with no limitations section is a marketing document.*

</details>

---

## Quickstart

### See one governed change, end to end

```bash
python scripts/demo_governed_write.py --slow
```

Seven steps, against a real cluster:

1. an anonymous caller is refused
2. connector health is read as a member of the tenant
3. a change requiring human approval is requested
4. a member **without** approve authority is refused
5. the scoped approver grants it
6. the action runs through a contained worker holding no standing credential
7. **Kubernetes itself** — not CortexPrime's own reply — confirms the workload restarted

### Deploy the governed plane

Requires a Kubernetes cluster (k3d is fine), PostgreSQL and Vault.

```bash
helm upgrade --install cortexprime ./helm/cortexprime-governed -n cortexprime \
  --set connection.tenant=<tenant> \
  --set connection.namespace=<namespace> \
  --set database.existingSecret=<secret> \
  --wait
```

Then, as a member of the connected tenant:

```http
GET  /api/v1/connectors             # per-connector health, through the governed path
GET  /api/v1/approvals              # the human approval queue
POST /api/v1/approvals/{id}/decision
POST /api/v1/approvals/{id}/execute
GET  /api/v1/executions/{id}        # durable status; the caller need not wait
```

See [`docs/KUBERNETES_CONNECTOR_RUNBOOK.md`](docs/KUBERNETES_CONNECTOR_RUNBOOK.md) and [`docs/GITHUB_CONNECTOR_RUNBOOK.md`](docs/GITHUB_CONNECTOR_RUNBOOK.md).

### Run the V1 application

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example backend/.env                      # add your API keys
uvicorn backend.main:app --reload --port 8000

cd frontend && npm install && npm run dev         # http://localhost:3000
```

Verify the architecture gate locally:

```bash
python -c "from backend.platform.architecture import analyze; r=analyze(); print('gate passed:', r.gate_passed)"
```

---

## Security model

| Control | Implementation |
|---|---|
| **Authentication** | JWT, verified before any tenant resolution |
| **Tenant isolation** | Enforced in SQL by a storage guard — another tenant's row cannot be returned even when its id is known exactly |
| **Authorization** | Deterministic policy; default deny; no model in the path |
| **Approval** | Bound to an action digest; consumed once; replay refused |
| **Credentials** | Vault-issued per action; revealed at exactly one site; never in environment, logs, metrics, queue payloads or execution records |
| **Execution isolation** | Contained workers: own container, non-root, read-only rootfs, no automounted token, compiled bindings, digest-pinned, egress allow-list |
| **Audit** | Hash-chained, fenced single writer; refusals recorded as deliberately as successes |
| **Untrusted content** | Repository and provider content is evidence, never instruction — it cannot name a capability or supply an argument |

---

## Engineering practice

What is unusual here is not the feature list — it is that the safety properties are **mechanically enforced**, and the failures are written down.

- **118 Architecture Decision Records.** Every non-obvious choice, with its reasoning, its cost, and what it deliberately does *not* claim.
- **A written Constitution, executed as CI.** 43 fitness functions run on every pull request — bounded-context isolation, tenancy on every repository method, no ungated execution site, dependency direction. A blocking violation fails the build.
- **Findings are published, including refuted ones.** Each phase report lists what broke and what was hypothesised then *disproved by its own test*. A finding nobody can reproduce is not a finding.
- **Failures are first-class.** Denials, refusals, ambiguity and unknown outcomes are modelled, recorded and auditable. A security system that only logs successes cannot explain why an attack was stopped.

> A representative lesson, from the phase that made execution durable:
>
> Three defects were found on the dispatch path, **two introduced by that phase's own fixes.** None was reachable by deterministic testing — one needed four real processes racing, another needed a real cluster with real accumulated data. A change to a concurrency path is unproven until real concurrency *and* real data volume have run against it.

---

## Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11 · FastAPI · domain-driven design with strict bounded contexts |
| **Frontend** | Next.js 16 · TypeScript · Zustand · live WebSocket event streaming |
| **AI** | OpenAI-compatible · Anthropic · Gemini · Ollama — provider-routed |
| **Data** | PostgreSQL (governed plane) · Redis · ChromaDB · Neo4j |
| **Infrastructure** | Docker · Kubernetes (Helm) · HashiCorp Vault · GitHub Actions |

<sub>~1,200 backend modules · ~1,800 frontend modules · 311 test files · 118 ADRs · 43 fitness functions</sub>

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
workers/             contained worker implementations (digest-pinned)
frontend/            Next.js application
helm/ · infra/       deployment
```

---

## Roadmap

| Phase | Scope | State |
|---|---|:--|
| 1–3 | Platform foundations, Mission Control, durable execution, Capability Fabric | ✅ Complete |
| 7 | World / Intelligence / Assurance planes, bitemporal truth | ✅ Complete |
| 8 | Governed intelligence — investigation, prediction, calibration, autonomy | ✅ Complete |
| 9 | First real governed write, contained workers, isolation taxonomy | ✅ Complete |
| 10 | Productization, tenancy, trust boundary | ✅ Complete |
| 11.1 | Kubernetes reference connector | 🔒 Locked |
| 11.2 | GitHub connector — the architecture carried to a second provider | 🟡 App auth pending |
| 11.3 | Governed execution fabric — dispatch survives the process that created it | ✅ Complete |
| 11.4 | Async API, multi-replica, final gate | 🟡 Partial |
| Next | Close the async write · lock GitHub · Connector #3 | ⏳ Planned |

---

## Decision records

The fastest way to judge this codebase is not the feature list — it is [`docs/adr/`](docs/adr/) and the phase verification reports. Each states a decision, the failure mode it prevents, what it costs, and what it explicitly does not claim.

| Record | Why it's worth reading |
|---|---|
| [ADR-031 — Durable Execution Core](docs/adr/ADR-031-durable-execution-core.md) | Why "unknown" is a first-class outcome, and why exactly-once is never claimed |
| [ADR-125 — Kubernetes Reference Connector](docs/adr/ADR-125-phase-11-1-kubernetes-reference-connector.md) | What a production connector actually requires |
| [ADR-127 — Governed Execution Fabric](docs/adr/ADR-127-phase-11-3-governed-execution-fabric.md) | How a documented limitation turned out to be the only thing preventing duplicate execution |
| [ADR-128 — Final Execution Gate](docs/adr/ADR-128-phase-11-4-final-execution-gate.md) | Six findings from running two replicas, three of them self-inflicted |

---

<div align="center">
<sub>© CortexPrime. Private and proprietary. All rights reserved.<br>
This repository and its contents are confidential and may not be copied, distributed, or disclosed without written permission.</sub>
</div>
