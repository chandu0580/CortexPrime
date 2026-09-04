# PHASE 9.3 — Implementation Map

**Status: IMPLEMENTED AND VERIFIED (84/84 real-cluster harness).** §§1–4 are the
pre-implementation discovery, kept verbatim because they are the source-cited map
the design was argued from. §5 is what was built. §6 records the three findings
that required a decision, and §9 records what the build changed about them.

Prior phase reports were used only as pointers, never as evidence: every
statement in §§1–4 was read from source in this session.

Labels: `[FACT]` read in source · `[VERIFIED]` proven by a run · `[NOT VERIFIED]` ·
`[BLOCKED]` · `[DEFERRED]` · `[INFERENCE]`.

---

## 1. The existing governed Kubernetes path (11 discovery questions)

### 1.1 Where the LIST/GET capability enters the system  `[FACT]`

```
capability (platform.kubernetes.pods.list)
  -> authorization        contexts/connectivity
  -> resolution + binding contexts/connectivity
  -> StartExecution       contexts/execution/application/service.py
  -> scheduler tick       contexts/execution/application/scheduler.py:356
  -> dispatcher -> worker_runtime
  -> ConnectorAdapter._perform
       backend/contexts/execution/infrastructure/adapters/connector.py:264
  -> OperationCatalog.require(operation)      (catalog, not caller input)
  -> spec.plan(payload)                       provider_operation.py:511
  -> ProviderChannel.send                     adapters/channel.py:274
  -> TransportBroker.dial                     platform/transport/broker.py
  -> HttpxTransportAdapter._send              platform/transport/httpx_adapter.py:287
  -> Kubernetes API server (real HTTPS)
```

The declared catalog is `kubernetes_read_catalog()` / `kubernetes_real_read_catalog()`
(`backend/contexts/execution/infrastructure/adapters/connectors/kubernetes.py`).
Real exposure today is exactly one operation, `kubernetes.pods.list`
(`KUBERNETES_REAL_READ_OPERATIONS`).

`[FACT]` The connector module declares a **contract only**. It imports no
`kubernetes` SDK, no `httpx`, no `os`, no credential carrier. Provider I/O
happens only when the governed transport invokes the composed adapter.

### 1.2 Where resourceVersion is preserved  `[FACT]`

`KubernetesReadNormalizer.normalize` (kubernetes.py) lifts
`metadata.resourceVersion` to a top-level `resourceVersion` **exactly as
returned** — opaque string, never coerced, never fabricated; absent stays absent
and the operation's `response_required_fields` check then refuses the answer as
`MALFORMED_RESPONSE`. The normalizer is attached through the narrow
`ProviderBodyNormalizer` port (connector.py:139) and runs **only on a successful
classification** (connector.py:399).

### 1.3 Where provider evidence reaches the execution aggregate  `[FACT]`

```
ProviderOutcome.evidence = spec.evidence(body)      provider_operation.py:588
  -> AdapterSeam detail["provider_evidence"]        adapters/base.py:842
  -> worker_runtime.to_execution_result             worker_runtime.py:689-719
  -> ExecutionAttempt.result.detail["provider_evidence"]   domain/lease.py:217
```

`[FACT]` **`spec.evidence()` keeps top-level scalars only** — `int`/`float`/`bool`
kept as-is, `str` truncated to 256 chars, everything else dropped
(provider_operation.py:588-609).

`[FACT]` **`ProviderOutcome.output` is "digested, never carried into the result"**
(adapters/base.py:217-219). It never reaches the aggregate.

`[FACT]` `to_execution_result` lifts exactly one key, `provider_evidence`
(worker_runtime.py:713-721). `provider_status`, `provider_failure` and the rest of
the adapter detail stay on the attempt's worker record and do **not** reach
`ExecutionAttempt.result.detail`.

### 1.4 Where observations are created  `[FACT]` — AND THE GAP

`ObservationIngestion.ingest` (`backend/world/application/ingestion.py:144`) is the
only path. It takes a `ReadObservation` value object plus an explicit `TenantRef`
**from the governed context, never from the payload** (ingestion.py:16-19, 161-164),
runs the field-aware secret firewall (`find_secrets`, ingestion.py:169), builds the
immutable `Observation`, and records it under a deterministic `observation_identity`
digest.

`[FACT]` **GAP: no component in `backend/` maps a governed execution result to a
`ReadObservation`.** A repo-wide grep for `ReadObservation(` finds hits only in
`scripts/phase7*`, `scripts/phase8*`, `scripts/phase92_*` — **every phase to date did
that mapping inside its harness.** Phase 9.3 needs the first production one, because
a watch driver cannot live in a harness script.

### 1.5 Where observations are persisted  `[FACT]`

`SqlObservationRepository.record` → `cw_observation`
(`backend/world/infrastructure/sql_observation.py:46`; migration
`0015_world_observation.py`). Append-only by construction: no `update`, no `delete`;
unique constraint `uq_cw_observation_identity` makes a duplicate delivery collide
rather than duplicate world state. The migration states it explicitly: **"This is
NOT exactly-once."**

Indexes present: `(tenant_id, subject_ref)`, `(observed_at)`, `(source_kind, source_ref)`.

### 1.6 How provider credentials enter the composition root  `[FACT]`

`backend/api/kubernetes_provider_factory.py:kubernetes_real_extension` reads
`CORTEX_KUBERNETES_URL` / `_TOKEN` / `_TENANT` **only here**, hands the token to a
`DevelopmentCredentialProvider` (refuses PRODUCTION), and refuses to coexist with
the scripted extension (one provider id, one path, no fallback). The connector never
reads the environment. Phase 5.5 (production credentials) remains `[BLOCKED]` and
untouched.

`[FACT]` The credential becomes a header in exactly one place — `_CREDENTIAL_HEADER`
in `httpx_adapter.py:117` — which is what makes `grep -rn "\.reveal("` a complete
audit of secret handling.

### 1.7 How the existing transport is used  `[FACT]` — LOAD-BEARING CONSTRAINT

`ProviderChannel` holds a `TransportBroker` and **no HTTP client, no socket, no TLS
context** (channel.py:22-35). It cannot dial, cannot set `Authorization`, cannot
retry, cannot pick a destination.

`[FACT]` `HttpxTransportAdapter` **explicitly refuses server-sent events**:

> "server-sent events need idle-timeout and per-frame accounting this
> request/response adapter does not provide; carrying it here would bound a stream
> by its total timeout and by nothing else" — httpx_adapter.py:151-156

`PRODUCTION_TRANSPORT_KINDS = {HTTPS, MCP_STREAMABLE_HTTP}` (httpx_adapter.py:107).
`broker.dial()` returns **one complete `TransportOutcome`**; the body is read bounded
and returned whole (httpx_adapter.py:315-334). There is no incremental frame delivery
anywhere in the governed plane.

`[FACT]` `ProviderExchange.json()` (channel.py:190) decodes the body as **JSON** and
refuses a truncated body before parsing. A non-JSON body is `MALFORMED_RESPONSE`.
(Side finding: the declared `kubernetes.pod.logs` operation returns a text body and
would therefore be refused today. It has never been real-exposed, so no run has
caught it. `[NOT VERIFIED]`, out of 9.3 scope.)

Budgets: `ResourceBudget.max_response_bytes = 10 MiB`, `max_stream_seconds = 300.0`
(`platform/transport/policy.py:326,336`); an operation may narrow, never widen
(channel.py:329-341).

### 1.8 How scheduler lifecycle works  `[FACT]`

`ExecutionScheduler` (`contexts/execution/application/scheduler.py`) is an explicitly
controlled `start`/`stop`/`tick`/`recover` loop — "not a daemon that starts itself on
import". It holds two optional, fail-closed ports: `LeadershipPort` (durable fenced
role) and `ReadinessPort`. It coordinates; it does not execute. `tick(context)` is
callable directly, which is exactly how every harness drives an execution to
completion (`scripts/phase92_kubernetes_real_harness.py:41-62`).

### 1.9 Does a watch loop already exist anywhere?  `[FACT]` — NO

`grep -rn "watch=true|stream_watch|Watch("` over `backend/` returns **nothing**.

### 1.10 Does any V1 Kubernetes watch implementation exist?  `[FACT]` — NO

`backend/connectors/kubernetes.py` (660 lines, the quarantined V1 zone) contains no
occurrence of `watch`. There is nothing here to be tempted by. Stop condition 10 does
not fire.

### 1.11 Would any V1 path bypass governance?  `[FACT]` — STRUCTURALLY FENCED

- `BND-DIRECT-HTTP` (boundary_rules.py:430): `backend.contexts` and
  `backend.platform.credentials` may not import `httpx`/`requests`/`aiohttp`/`urllib3`.
- `BND-PROVIDER-SDK` (boundary_rules.py:632): no provider SDK in the governed path.
- `BND-WORLD-CANNOT-EXECUTE` (boundary_rules.py:1049): `backend.contracts.world` and
  `backend.world` may import **none** of `backend.connectors`,
  `backend.contexts.execution`, `backend.platform.transport`, the credential carriers,
  or `backend.harness`.
- `BND-INTELLIGENCE-CANNOT-EXECUTE` / `BND-INTELLIGENCE-CANNOT-BYPASS-WORLD`
  (boundary_rules.py:1409, 1535).
- `BND-OBSERVATION-APPEND-ONLY` (boundary_rules.py:1262).

### 1.12 Reusable crash/recovery mechanisms  `[FACT]`

- **Leadership + fencing:** `SqlLeadershipStore`
  (`backend/database/durable/leadership.py`) — conditional-`UPDATE` election,
  monotonic `fencing_token` carried into the durable mutation so **the database**
  rejects a stale writer (`fenced_where`, leadership.py:437). Table `cp_leadership`,
  PK `(scope, role)`, where `scope` is the tenant for a tenant-scoped role
  (`database/durable/tables.py:450-467`). `LeadershipRole` is a **deliberately closed
  list**: `RECOVERY_SWEEP`, `OUTBOX_PUBLISHER`, `AUDIT_WRITER`, `SCHEDULER`
  (leadership.py:94-127).
- **Replay:** `ExecutionReplayer` (`contexts/execution/application/replay.py`) is
  **structurally inert** — "holds no repository, no worker pool, and no queue, so
  there is nothing here for it to call even if the code wanted to." Reusable as-is;
  requirement Q needs no new mechanism.
- **Crash methodology:** real `os._exit(9)` child processes at named points, JSON
  markers, parent re-asserts durable state
  (`scripts/phase92_kubernetes_real_harness.py:190-247, 312-328`).
- **Audit chain:** single-writer `AUDIT_WRITER` role + chain verification.

---

## 2. Kubernetes WATCH semantics this phase must honour  `[FACT]`

```
GET /api/v1/namespaces/{ns}/pods
    ?watch=true&resourceVersion=<RV>&timeoutSeconds=<W>&allowWatchBookmarks=true
```

- Response is **HTTP 200 + newline-delimited JSON**, one object per line:
  `{"type": "ADDED"|"MODIFIED"|"DELETED"|"BOOKMARK"|"ERROR", "object": {...}}`.
- The RV to resume from is `object.metadata.resourceVersion` of the **last event
  consumed** — opaque, never numeric, never a timestamp.
- `BOOKMARK` carries only `metadata.resourceVersion`. It advances stream position and
  **is not a resource mutation**.
- The API server closes the connection when `timeoutSeconds` elapses. Every real
  Kubernetes client re-establishes. A bounded window is normal watch operation, not a
  degraded mode.
- **410 Gone arrives two ways** and both must be handled:
  1. HTTP `410 Gone` on the watch request itself; and
  2. **HTTP 200 followed by an in-stream
     `{"type":"ERROR","object":{"kind":"Status","code":410,"reason":"Expired"}}`** —
     the common modern path.

  Route (2) is a *successful* HTTP exchange whose body says continuity is lost.

---

## 3. What Phase 9.3 does NOT need  `[FACT]`

| Feared addition | Verdict | Why |
|---|---|---|
| New table for stream state | **NOT NEEDED** | The last committed position is reconstructable from `cw_observation` — a checkpoint observation carries the RV. Needs one new **read** method on the existing repo (tenant+subject+predicate scoped, ordered by `recorded_at`), not a new store. |
| New election system | **NOT NEEDED** | `SqlLeadershipStore` + fencing token, `scope = tenant`. Requires **one** new member on the closed `LeadershipRole` enum. |
| New replay path | **NOT NEEDED** | `ExecutionReplayer` is already structurally inert. |
| New fitness rule (`BND-WATCH-CANNOT-BYPASS-GOVERNANCE`) | **NOT NEEDED — would be cosmetic** | `BND-WORLD-CANNOT-EXECUTE` already forbids `backend.world` importing `contexts.execution` / `platform.transport` / `connectors`; `BND-DIRECT-HTTP` already forbids a second HTTP client in `backend.contexts`. A watch that bypassed governance would have to violate one of these first. Per the mission's own instruction, no rule is added. |
| New gateway / executor / scheduler / audit chain / credential system | **NOT NEEDED** | Every one is reused verbatim. |

---

## 4. Where the watch driver may live  `[FACT]`

It **cannot** live in `backend/world/` — driving a governed execution means importing
`backend.contexts.execution`, which `BND-WORLD-CANNOT-EXECUTE` makes an ERROR. That
is the enforcement of "the World Plane never opens the Kubernetes connection itself",
and it is already in place.

It therefore lives in the composition layer (`backend/api/`), the same place the
providers are composed — the only layer permitted to see both planes. Direction stays:

```
governed execution/capability -> Kubernetes -> Observation -> World Plane
```

---

## 5. Proposed minimal implementation (pending §6 decisions)

1. **`kubernetes.pods.watch`** — one new READ operation in the declared catalog: same
   path template as `pods.list`; `watch` / `timeoutSeconds` / `allowWatchBookmarks` /
   `resourceVersion` declared; `success_statuses=(200,)`; `provider_timeout_seconds`
   greater than `timeoutSeconds`; narrowed `max_response_bytes`. A `CapabilityProfile`
   with `SideEffectClass.READ`, ceiling `A1_INVESTIGATE`, `VerificationRequirement.NONE`
   — identical treatment to every other read.
2. **`KubernetesWatchNormalizer`** — parses the NDJSON window into declared, bounded,
   per-event records; surfaces the in-stream `ERROR`/410 as a declared scalar; refuses
   unknown event types and events missing `object.metadata.resourceVersion` (fail
   closed, never synthesize).
3. **`KubernetesWatchDriver`** (composition layer) — leadership-gated, crash-safe
   loop: read last position → governed LIST if none / after 410 → governed WATCH
   window → per-event `ObservationIngestion.ingest` → checkpoint observation → repeat.
   Bounded 410-recovery counter.
4. **`GovernedReadObserver`** — the missing production mapping from an execution
   attempt's provider evidence to a `ReadObservation` (§1.4 gap), tenant taken from the
   governed context.
5. **`LeadershipRole.WORLD_WATCH`** — one enum member, `scope = tenant`.
6. **`SqlObservationRepository.latest_for_subject(...)`** — one read method.
7. **Phase 9.3 harness** — fresh Postgres + real k3d cluster + real OS processes,
   proving A–Y.

---

## 6. THREE FINDINGS REQUIRING A DECISION BEFORE CODE

### 6.1 The transport cannot stream — resolved WITHOUT a second transport  `[FACT]`

Stop condition 1 ("WATCH requires a second transport architecture") **was reached and
is avoidable**. A true continuous stream would need incremental frame delivery, idle
timeouts and per-frame accounting that `HttpxTransportAdapter` explicitly refuses
(§1.7) — building it is a second transport architecture.

**Resolution:** bounded watch windows. `?watch=true&timeoutSeconds=W` makes each
window an ordinary one-shot governed dial whose body is the NDJSON of that window's
events. RV continuity across windows is exact (the last event's RV starts the next
window). This is honest Kubernetes semantics, not a workaround.

**Honest cost, to be stated in every claim:** this is **near-continuous micro-batch
observation, not streaming**. Per-event visibility latency is bounded by the window
length `W`, not by network arrival. Phase 9.3 must never claim "streaming" or
"real-time".

### 6.2 NDJSON cannot be decoded today  `[DECISION]`

`ProviderExchange.json()` (channel.py:190) refuses a non-JSON body. A watch window is
NDJSON. Resolving this needs one small, generic, provider-neutral addition to the
adapter — a `ProviderBodyDecoder` port mirroring the two ports that already exist
(`ProviderResponseTranslator`, `ProviderBodyNormalizer`), defaulting to
`exchange.json()`. The generic adapter stays generic; Kubernetes supplies its decoder
from its own module.

Also needed: **`static_query` on `ProviderOperationSpec`** (mirroring `static_headers`,
provider_operation.py:318) so `watch=true` is part of the operation's declaration and
its digest — **not** something a caller can set. Without it, `watch` would have to be a
caller-supplied parameter, which is precisely the model-controlled watch URL the
mission forbids.

Both are strengthenings. Judged in scope. **Flagging, not blocking.**

### 6.3 WATCH EVENTS CANNOT CROSS THE EXECUTION BOUNDARY — **BLOCKING**  `[FACT]`

This is the real one, and it is a genuine architectural collision.

- `ProviderOutcome.output` is **"digested, never carried into the result"**
  (adapters/base.py:217-219).
- The only thing that survives to the aggregate is `evidence`, and `spec.evidence()`
  extracts **top-level scalars only** — `int`/`float`/`bool`, `str` truncated to 256
  (provider_operation.py:588-609).
- The stated reason is ADR-042 §56: *"a raw provider payload is unbounded, can contain
  the caller's own data coming back, and belongs in an evidence store with its own
  governance rather than in an execution event."*
- `grep -rn "evidence.store"` → **no evidence store exists.**

A watch window yields N events, each needing type + resource identity + its own
`resourceVersion`. **N events cannot be expressed as a flat scalar map.** So today
there is no governed route by which a watch event can reach `ObservationIngestion`.
Requirements C, D, E, F, P and W all depend on closing this.

Three ways to close it, with honest trade-offs:

**Option A — bounded structured evidence (extend the declaration).**
Add `response_evidence_records` to `ProviderOperationSpec`: ONE named list field, a
hard `max_records` cap, and a declared tuple of per-record scalar field names.
`evidence()` applies the same scalar/truncation discipline one level down. It enters
`identity_payload` → the spec digest → contract-drift refusal.
*Pro:* no new store, no new authority, everything else reused; all 25 harness claims
become reachable.
*Con:* widens a deliberately narrow invariant. The attempt record and
`ExecutionResult.detail` grow from ~6 scalars to up to `max_records × k` scalars. This
is the honest weakening to weigh against stop condition 7 — the bound stays *declared,
digested and enforced*, but it is a bigger bound than ADR-042 §56 had in mind.

**Option B — window-summary observations only.**
One observation per window carrying `eventCount` / `addedCount` / `modifiedCount` /
`deletedCount` / `lastResourceVersion` as scalars.
*Pro:* zero change to the execution fabric.
*Con:* **fails the mission's Definition of Done** — no per-resource identity, so C/D/E
cannot be proven. Recorded for completeness; not recommended.

**Option C — build the governed evidence store ADR-042 §56 names.**
The adapter writes bounded, secret-scanned payloads to a governed store; the execution
result carries a reference; the World driver resolves it.
*Pro:* the architecturally "correct" long-term answer; keeps execution events small.
*Con:* a genuinely new persistence structure with its own ownership, retention, tenant
scoping, crash semantics and audit story — a phase of its own, and a serious risk of
becoming a second source of truth about what a provider said. The mission requires an
explicit STOP before adding new persistence; this is that stop.

**Recommendation: Option A**, with `max_records` set low (64) and every field declared.
It adds no store and no authority, and keeps the discipline that makes evidence safe
(declared before invocation, scalar, bounded, digested) while extending its shape.
Option C is right eventually and should become its own phase.

### 6.4 Secondary decision inside Option A  `[FACT]`

HTTP-410 (route 1 of §2) produces a *failure* outcome, and failures carry no evidence.
`to_execution_result` lifts only `provider_evidence` (worker_runtime.py:713-721), so
`provider_status` never reaches the aggregate and the driver cannot distinguish
"expired RV, re-LIST" from "403, fail closed". Fix: lift `provider_status` alongside
`provider_evidence` — one bounded scalar, already recorded on the worker result,
exactly the 9.2 precedent. Without it, 410 recovery would have to string-match a
failure message, which is not evidence-grade.

---

## 7. Environment gaps for the harness  `[FACT]`

- `k3d` is **not installed** on this machine (`command -v k3d` → missing). Phase 9.2's
  cluster was disposable and deleted. The 9.3 runner must re-provision.
- `kubectl` and `docker` are present; Docker is running.
- `psql` is **not on PATH**; something is listening on 5432. The fresh-Postgres
  requirement (`cortex_p93`) needs confirmation of a usable server before the decisive
  claims can be run. `[NOT VERIFIED]`

---

## 8. Stop-condition status at end of discovery

| # | Condition | Status |
|---|---|---|
| 1 | second transport architecture | **Avoided** via bounded windows (§6.1) |
| 2 | World opens a provider connection | Not triggered — structurally impossible (§4) |
| 3 | resourceVersion continuity unprovable | Not triggered — exact continuity available (§2) |
| 4 | 410 recovery needs fabricated history | Not triggered — fresh governed LIST, explicit in provenance |
| 5 | tenant identity untrustworthy | Not triggered — tenant from governed context (§1.4) |
| 6 | credentials not composable through the root | Not triggered (§1.6) |
| 7 | weakening an existing invariant | **TRIGGERED — §6.3, awaiting decision** |
| 8 | second execution/governance/coordination authority | Not triggered under Option A; **would be** under Option C |
| 9 | exact-once claimed without proof | Not triggered — at-least-once, stated everywhere |
| 10 | tempting V1 implementation | Not triggered — no V1 watch exists (§1.10) |

---

## 9. What was actually built (post-implementation)

Discovery held up. The one thing it did not predict is recorded honestly below.

### 9.1 Files

| File | What |
|---|---|
| `backend/contexts/execution/domain/provider_operation.py` | `RecordEvidenceSpec`; `static_query`; `response_evidence_records`; both in `identity_payload` |
| `backend/contexts/execution/infrastructure/adapters/connector.py` | `ProviderBodyDecoder` — the third narrow port |
| `.../adapters/connectors/kubernetes.py` | `kubernetes.pods.watch`; `KubernetesWatchDecoder`; the normalizer's watch branch |
| `backend/contexts/execution/application/worker_runtime.py` | lifts `provider_status` alongside `provider_evidence` |
| `backend/database/durable/leadership.py` | `LeadershipRole.WORLD_WATCH` |
| `backend/world/infrastructure/sql_observation.py` | `latest_for_subject` — a read, no new table |
| `backend/api/governed_read_observer.py` | `GovernedReadOutcome`, `ObservationLeg`, `GovernedReadObserver` |
| `backend/api/capability_execution_composition.py` | `GovernedCapabilityReader` (see §9.3) + the decoder wiring |
| `backend/api/kubernetes_watch_driver.py` | `KubernetesWatchDriver` |
| `scripts/phase93_provision.sh` | disposable k3d + RBAC + fresh migrated Postgres |
| `scripts/phase93_kubernetes_watch_harness.py` | the 84-check real harness |
| `tests/intelligence/test_kubernetes_watch.py` | 48 unit tests |

### 9.2 Discovery predictions that held

- No new table. The position is an append-only Observation; `latest_for_subject`
  is the only addition, and it is a read.
- No new election. `LeadershipRole.WORLD_WATCH`, scope = tenant, one enum member.
- No new fitness rule. The existing rules cover it — and one of them **caught a
  real violation** (§9.3).
- Bounded windows avoided the second-transport stop condition entirely.
- `ProviderOutcome.output` really is unreachable from the aggregate; the evidence
  extension in §6.3 was genuinely required.

### 9.3 What discovery got wrong, and what the build found

1. **The reader belongs in the composition root, not beside the observer.**
   Discovery said "the driver lives in `backend/api/`", which was right but not
   precise enough. `GovernedCapabilityReader` touches BOTH bounded contexts
   (Connectivity authorizes/resolves, Execution starts/dispatches), and exactly
   five named modules may do that. The composition-root test failed and the class
   moved to `capability_execution_composition.py`. An existing rule found this,
   which is the rule working.

2. **A lease shorter than a window fences every advance.** Not predicted. A
   stream lease that expires while a watch window is open means the advance at
   the end of every window is refused and the position never moves — it looks
   like a fencing bug and is a configuration one. The driver now refuses the
   incoherent combination at construction.

3. **`_still_leader` should heartbeat, not assert.** Discovery planned
   `assert_current`, which the leadership module itself labels advisory.
   `heartbeat` is a conditional UPDATE matching on the fencing token, so the
   *database* refuses a superseded writer — strictly stronger — and it renews,
   which a leader that is alive and doing one unit of work legitimately needs.

4. **A failure body must not be decoded as a stream.** Found by a unit test:
   decoding a refused watch as NDJSON wrapped Kubernetes' `Status` document in an
   events envelope, and the operator lost the cluster's own sentence
   ("too old resource version: 4 (99)") in favour of "status 410". The decoder
   now hands non-success statuses to the JSON path, matching the rule the
   normalizer already followed.

5. **Environment.** `k3d` had to be installed; `psql` is absent (the provisioning
   script uses `docker exec`); the migration path reads `POSTGRES_URL`, not
   `CORTEX_DURABLE_URL`; migrations need `pgvector`; and k3d writes
   `host.docker.internal` as the server address, which is unreachable from this
   host and had to be rewritten to the published loopback (still TLS-verified —
   the transport has no way to disable verification).

### 9.4 The one architectural debt this phase names

The governed evidence store of ADR-042 §56. Phase 9.3 extended bounded evidence
one level down rather than building it; that is the right scope for this phase
and the wrong long-term answer. See ADR-083 Decision 3 and the verification
report §7.
