# ADR-122 — The signal fabric: World observations are the canonical durable event, a supervised read-only worker drives the governed Kubernetes watch, Alertmanager is consumed not rebuilt, and detection receives projected candidates

- **Status:** ACCEPTED
- **Date:** 2026-09-10
- **Phase:** 11.2 — real production signal fabric (GA Prompt 2/5)
- **Parents:** `e662688` — Phase 11.1 (ADR-121, the trust boundary); ADR-083 (governed Kubernetes WATCH, at-least-once, crash-safe); ADR-082 (governed READ, normalizer lifts exactly); ADR-063–070 (World Plane: observation, fact, bitemporal truth, lineage); ADR-092 (fencing with SQL leadership); ADR-094 (product API is a separate process); Phase 11.0 gap register G-02 / G-03 / D3
- **Evidence:** `docs/PHASE_11_2_SIGNAL_IMPLEMENTATION_MAP.md`, `docs/PHASE_11_2_SIGNAL_VERIFICATION_REPORT.md`, `scripts/phase112_signal_fabric_harness.py`, `docs/phase112_signal_report.json`
- **Change:** application layer only. **No migration. No new table. No new dependency. No governed execution-plane module touched.** One additive hook and one additive method on the watch driver; two additive read queries on the observation repository.

> **Numbering.** Highest used is 121; this is 122. Nothing overwritten.

## Context

Phase 11.0 found the governed engine real but idle: nothing in production
observed anything, the watch driver had no runner, and no external signal could
enter the governed plane. Phase 11.1 made the perimeter true. This phase
connects a real signal to it. The repository already held, verified, every part
that matters except the runner: a crash-safe, position-checkpointing,
410-recovering, database-fenced watch driver; an append-only, tenant-scoped,
identity-deduplicated observation ledger with fact derivation; an authenticated
tenant-bound ingestion boundary. The temptation was to build a second event
model beside them. The decision is to build none.

## Decisions

### D-1 Ownership: consume the ecosystem, own the intelligence layer

| Concern | Owner | CortexPrime's part |
|---|---|---|
| Watch semantics, resourceVersion, bookmarks, 410 | **Kubernetes** | the driver copies positions exactly, never computes them (ADR-083) |
| Pod state (phase, restarts, waiting reason, last termination) | **Kubernetes** | read through the existing governed `pod.get`, lifted exactly (ADR-082) |
| Alert evaluation, deduplication of raw alerts, grouping, routing, inhibition, silencing, HA, repeat and retry | **Prometheus / Alertmanager** | consumed as the webhook output; never re-implemented |
| Alert identity | **Alertmanager** (`fingerprint`, `startsAt`, `status`) | carried as the subject and the observed instant |
| Durable truth, identity, dedupe, tenancy | **PostgreSQL** (`cw_observation`, `cw_fact`) | the World Plane, unchanged |
| Single leader, fencing | **PostgreSQL** (`SqlLeadershipStore`, role `WORLD_WATCH`) | the driver's own leadership |
| Rate control, revocation | **Redis** (existing) | not on the signal's durability path |
| Trust, tenant, audit at HTTP ingress | **CortexPrime** (ADR-121) | the only way in over HTTP |
| Canonical event contract, source-native identity, provenance, correlation context, candidate projection, handoff | **CortexPrime** (`backend/signal`) | this phase |
| OpenTelemetry collection | **deferred** (D-8) | the V1 OTLP receiver stays fenced; no governed OTLP path yet |

### D-2 The canonical durable event is a World `Observation`; the boundary receipt is the `IngressEnvelope`; nothing new is stored

`Observation` already carries tenant, instrument (source kind + ref), subject,
predicate, value, observed and retrieved instants, recorded time, provenance
(produced_by, execution_ref, trace_ref) and an identity digest over (tenant,
source, subject, predicate, observed_at, value) enforced by a unique
constraint. `backend/signal/contract.py` names the source-specific shapes and
views an observation as a `CanonicalSignal` — a projection, not a record.
Prompt 1's `IngressEnvelope` remains the audit receipt for HTTP ingress and is
never persisted as world knowledge. Composition, not duplication.

### D-3 Identity is global + source-native; delivery is at-least-once, never exactly-once

- Global: `Observation.record_id` (ULID) and the identity digest (deterministic,
  tenant-scoped by construction; a redelivery collides and is DEDUPED).
- Kubernetes-native: cluster, namespace, kind, name, uid as the subject;
  `resourceVersion` + `eventType` distinguish deliveries.
- Alertmanager-native: `fingerprint` as the subject; `startsAt` as the observed
  instant; `status`/`endsAt` distinguish lifecycle states. A repeated
  notification of the same firing alert is the same identity (effectively-once
  per lifecycle state); a resolution is a new observation of the same subject.
- Loss is only possible across a `410 Gone` or a deliberate stall-relist, and
  both are recorded as checkpoint provenance (`origin=list_after_expiry` /
  `list_after_stall`, with the reason) and counted
  (`cortex_signal_events_dropped_total`). Never silent.
- Ordering is per source: `resourceVersion` for a stream, `startsAt`/`endsAt`
  for an alert, `recorded_at` + ULID for what CortexPrime learned when. No
  global order is claimed.

### D-4 The supervised worker is read-only, composes what exists, and runs where the runtime's roles are

Two deployment shapes of ONE loop (`SignalWorker`):

* **Embedded** (`start_embedded`, opt-in through `CORTEX_SIGNAL_TENANT_ID` +
  `CORTEX_SIGNAL_NAMESPACE`): a supervised thread of `backend.main`'s own
  governed runtime. This is the production shape beside the API, for a
  reason measured in this phase: the runtime's `SCHEDULER` and `AUDIT_WRITER`
  roles are per-store singletons and a runtime dispatches only the
  executions its own process started, so a governed read issued from a
  second process waits out its budget (`the node recorded no attempt`) while
  the API holds the roles. The loop still takes the `WORLD_WATCH` stream role
  through the leadership store, so two API replicas elect one observer.
* **Standalone** (`python -m backend.signal.worker`): its own process, for a
  store no API runtime is dispatching against. It takes the audit-writer role
  lazily and admits the connector worker only once it holds it; while another
  process holds the role it reports `follower` and waits — an honest hot
  standby that takes over when the leader's leases lapse.


`python -m backend.signal.worker` composes the governed runtime the API
composes (without starting its scheduler or outbox pump), holds the
`WORLD_WATCH` role through the existing SQL leadership store, and drives
`KubernetesWatchDriver.cycle` under supervision: follower sleep, exponential
backoff on failure, an explicit relist after `max_stall_failures` at one
position, relist on expiry exhaustion, graceful release on SIGTERM. It holds
the `cortex-reader` ServiceAccount token only (list/watch/get pods), never a
restart credential, composes no dispatcher and cannot execute anything. It
does not register capabilities: commissioning is an operator act and a worker
that finds the read capabilities missing refuses to start.

### D-5 Watch events are enriched through the existing governed `pod.get`, not by widening a contract

The watch operation's declared record fields are `type, kind, namespace, name,
uid, resourceVersion` — a watch event says *what* changed, not the pod's
state. Widening that declaration changes a governed contract digest. Instead
the driver gained an optional `enricher` hook; the worker supplies one that
reads the state through the commissioned `pod.get` capability and merges its
declared scalars (phase, restartCount, waitingReason, lastExitCode,
lastTerminationReason) into the same observation. One event, one complete,
identity-deduplicated observation; a failed enrichment records
`enrichment: unavailable:…` rather than inventing a state; a `DELETED` event
is not enriched. Cost: one governed read per mutation (bounded by the window
cap of 64), stated in the report.

### D-6 Alertmanager enters only through Prompt 1's boundary

`POST /api/signals/alertmanager` on `backend.main`: the perimeter authenticates
the token Alertmanager sends in `http_config.authorization`; the governed
ingest principal establishes tenant from that token and refuses a token
without one; the body is bounded; the Alertmanager v4 schema is validated
(bounded labels/annotations, ≤200 alerts); each alert becomes a World
observation through the World Plane's own ingestion; every decision is
audited without the payload; persistence failure answers 503 so Alertmanager
retries and nothing is acknowledged that was not durable. The surface is
exempt from the V1 single-tenant fence because the ledger it writes is
tenant-scoped by row. A clock-skewed `startsAt` in the future is clamped to
receipt and the skew recorded.

### D-7 Candidates are a deterministic projection, not incidents

`backend/signal/correlation.py` projects `IncidentCandidate`s from the latest
observation of every subject: pods in a backoff waiting reason or above a
restart threshold (folded per inferred workload), alerts that are firing.
Each carries correlation context (tenant, cluster, namespace, workload, pod,
alert name, severity, timestamps, resource version, evidence observation
ids), a deterministic id, `authority: none`, and a handoff record with an
`incident_ref` that `InvestigationService.create` can take. Nothing opens an
investigation; the default `DetectionHandoff` records the projection. The
product API exposes `/api/v1/signals/recent` and `/api/v1/signals/candidates`
read-only so an operator sees what detection will see. Workload is inferred
from the pod name (ownerReferences are not a declared watch field) and
labelled as inferred.

### D-8 OpenTelemetry: present, not adopted for the governed plane in this phase

The SDK and exporters are installed and the V1 OTLP receiver exists behind
the 11.1 boundary. A governed OTLP path would be a third source with its own
identity (trace/span) and a collector to own; adopting it now would add a
component before a consumer exists. Deferred with the contract stated
(`backend/signal/contract.py`) so Prompt 3 or later can add it as another
observation shape.

### D-9 Redis is not on the signal path

Positions, observations, facts and leadership are PostgreSQL. The API's
Alertmanager path was run with no Redis at all and lost nothing. Redis keeps
its existing roles (rate-limit windows, revocation list); it is neither a
buffer nor a source of truth for signals.

## Consequences

- One worker per (tenant, namespace) stream. A second instance is a follower
  and takes over within the lease after a hard kill.
- Every mutation costs a governed read for enrichment (≤64 per window).
- Two new read queries on `cw_observation` use existing indexes
  (`tenant_id, subject_ref`) plus a sort on `recorded_at`; no index was added.
- A CrashLoopBackOff on the cluster is now, within about one window plus one
  read, a durable observation, a fact, and a candidate.

## Findings surfaced in the governed runtime (recorded, not changed)

- **One dispatching process per durable store.** The scheduler and
  audit-writer roles are singletons and foreign executions are not picked up
  by the leader's scheduler; a second process's governed reads stall. The
  embedded shape is the answer for this phase; multi-process dispatch is a
  decision for the runtime's owner.
- **A refused worker selection leaves the node `leased`.** When the process's
  worker directory holds no admitted connector, the dispatcher answers
  `invocation_request_unavailable` and releases, but the run stays `leased`
  and the reader waits its whole budget with no reason string. Found by the
  harness; the worker now admits the connector before it reads.
- **The worker directory is process-local** (`InMemoryWorkerDirectory`), so
  connector admission is per process; the capability registry is durable.

## Limitations (stated)

- Kubernetes source is pods only; Kubernetes `Event` objects and Deployment
  objects are not watched (would need further read capabilities, 11.6).
- Workload identity is inferred from pod names.
- A window over the event cap (64) is refused by the normalizer; the worker's
  answer is an explicit relist, which loses the events between the abandoned
  and the fresh position and says so.
- Candidate projection thresholds (`BACKOFF_REASONS`, restart ≥ 3) are
  projection defaults, not detection policy; Prompt 3 owns policy.
- Ingestion audit persistence is best-effort by the existing audit logger's
  design (the World row itself is the durable proof).
- One API-only iteration saw the embedded loop stop cycling with no
  exception; a dedicated reproduction and every later run cycled throughout.
  Open observation (verification report F-6): the harness runs the API under
  a periodic thread dump and asserts liveness by cycle count; production
  should alert on `cortex_signal_cycles_total` stalling while
  `cortex_signal_worker_leader` is 1.
- Transport and credential audit facts are not recorded by the governed
  brokers (pre-existing `TypeError`, verification report F-3) — the World row
  and the execution record are the evidence this phase relies on.
