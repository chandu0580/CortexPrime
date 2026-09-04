# ADR-083 — Phase 9.3: Governed Kubernetes WATCH and continuous world observation

**Status:** Accepted
**Date:** 2026-09-04
**Supersedes nothing. Extends:** ADR-041 (transport), ADR-042 (provider fabric),
ADR-064 (observation ingestion), ADR-065 (bitemporal facts), ADR-081, ADR-082.

## Context

Phase 9.2 proved a real governed Kubernetes READ against a live cluster and
carried a real `resourceVersion` into a durable Observation — deliberately as the
data contract a WATCH would need, with WATCH itself explicitly not implemented.

Phase 9.3's objective is that the World Plane becomes *continuously* informed by
Kubernetes: LIST → durable resourceVersion → governed WATCH → ADDED/MODIFIED/
DELETED → provenanced Observation → the existing bitemporal World Plane.

Discovery (docs/PHASE_9_3_IMPLEMENTATION_MAP.md) found three collisions between
that objective and the existing architecture, and one gap.

## Decision 1 — Bounded watch windows, not a streaming transport

`HttpxTransportAdapter` refuses server-sent events by construction: *"server-sent
events need idle-timeout and per-frame accounting this request/response adapter
does not provide"*. `TransportBroker.dial` returns one complete `TransportOutcome`.
Consuming a watch as a continuous stream therefore requires a **second transport
architecture**, which is a Phase 9.3 stop condition.

We use Kubernetes' own bounded-window semantics instead:
`?watch=true&resourceVersion=RV&timeoutSeconds=W`. The API server closes the
window; the body is that window's events; the next window resumes from the exact
`resourceVersion` the last event carried. Continuity across windows is exact.

`W = 20s`, chosen against `TimeoutPolicy.read_seconds = 30.0`: a quiet cluster
sends no bytes, so a window longer than the read timeout would be killed as an
ambiguous `ReadTimeout` every time nothing happened. `allowWatchBookmarks=true`
lets a quiet stream hold an unexpired position without inventing an event.

**What is therefore not claimed:** this is near-continuous micro-batch
observation, **not streaming**. Per-event visibility latency is bounded by `W`.
Every report says so.

## Decision 2 — Three narrow additions to the generic execution fabric

Each mirrors something that already exists; none is Kubernetes-specific.

1. **`ProviderOperationSpec.static_query`** (mirrors `static_headers`). Query
   values that are part of *what the operation is*, not input to it. `watch=true`
   lives here, so a watch is a different operation from a list — in the digest —
   rather than a list a caller asked to keep open. A spec declaring the same name
   both statically and as a parameter is refused at construction.
2. **`ProviderBodyDecoder`** (the third narrow port, after
   `ProviderResponseTranslator` and `ProviderBodyNormalizer`). A watch window is
   newline-delimited JSON; `ProviderExchange.json()` is right for everything else.
   The decoder dispatches on the operation's own declaration, and hands *failure*
   bodies straight to the JSON path — a refused watch is an ordinary `Status`
   document, and wrapping it in an events envelope would cost the operator the
   cluster's own "too old resource version: 4 (99)".
3. **`RecordEvidenceSpec` / `response_evidence_records`** — see Decision 3.

## Decision 3 — Bounded *structured* evidence, and the invariant it moves

This was the phase's blocking finding.

`ProviderOutcome.output` is *"digested, never carried into the result"*, and
`spec.evidence()` extracts **top-level scalars only**. ADR-042 §56's reasoning:
a raw provider payload is unbounded, can carry the caller's data back, and
*"belongs in an evidence store with its own governance"*. No evidence store
exists. A watch window is N events, each needing type + identity + its own
`resourceVersion` — **not expressible as a flat scalar map**. Without closing
this there is no governed route from a watch event to an Observation at all.

Three options were weighed (implementation map §6.3): window-summary observations
only (fails the objective — no per-resource identity); build the evidence store
(the right long-term answer, a phase of its own, and a real risk of becoming a
second source of truth about what a provider said); or extend the declaration.

**We extend the declaration.** `RecordEvidenceSpec` names ONE list field, a hard
`max_records` cap, and the per-record scalar fields to keep. Every property that
made scalar evidence safe is kept one level down: declared before the invocation
existed, scalars only (a nested object inside a record is dropped, never
flattened), hard-bounded, and **in the spec digest** — so widening it is contract
drift and a running binding refuses rather than accommodates.

**Stated honestly:** this widens a deliberately narrow invariant. An execution
attempt's detail can now grow from ~6 scalars to up to `max_records × k`
(64 × 6 for the watch). The bound is bigger and it is still a bound. Building the
governed evidence store ADR-042 §56 names remains the correct successor, and is
deferred to its own phase rather than smuggled into this one.

Related: `worker_runtime.to_execution_result` now lifts `provider_status`
alongside `provider_evidence`. A *failed* provider answer carries no evidence, so
without it the only thing separating an expired watch position (410) from a
refused one (403) would be substring-matching a failure message.

## Decision 4 — Stream state is reconstructed, not stored

No new table. The position is written as an ordinary append-only Observation
(`subject_ref = kubernetes:podstream:<ns>`, `predicate = watch_position`), and
recovered with one new **read** on the existing repository
(`latest_for_subject`, ordered by `recorded_at` — never by the value, because a
`resourceVersion` is opaque text with no order). One ledger, one answer to "where
are we", and crash recovery is the same read as the ordinary one.

## Decision 5 — Leadership reuses the existing fenced role

One new member on the closed `LeadershipRole` enum: `WORLD_WATCH`, `scope =
tenant`. No Kubernetes-specific election. A stream position is a *single* place in
a provider's history; two processes advancing it independently both read from the
same point and both move forward, producing a position that skips whatever the
other consumed. There is no per-item claim to express that as, because the item
does not exist until the position is used to fetch it.

`assert_current` before a durable advance is **advisory**, and labelled so — the
same limitation ADR-054 states for the audit writer: real fencing composes the
token into the write's `WHERE`, and an `INSERT` into the observation ledger has no
such predicate to join. The residual window's worst outcome is a late checkpoint
moving the position backwards, which causes re-delivery — at-least-once, which is
what is claimed. It cannot corrupt, delete or overwrite anything.

## Decision 6 — Ordering, and at-least-once

**Events are recorded, then the position advances. Always.** A crash between them
re-delivers; the other order would silently lose. A re-delivered event produces a
second Observation row — an honest record of a second delivery — and Fact
derivation resolves it to `DEDUPED`, so world *belief* does not move. Duplicate
delivery is visible in the ledger and inert in the conclusions.

**Exactly-once is not claimed and is not implemented.**

## Decision 7 — 410 Gone is load-bearing and never silently succeeds

Handled on both routes Kubernetes uses: HTTP `410` on the request, and — the
common modern path — HTTP 200 whose stream carries
`{"type":"ERROR","object":{"kind":"Status","code":410,"reason":"Expired"}}`.

Either way the expired position is **discarded and never presented again**; a
fresh governed LIST produces a new real `resourceVersion`; the checkpoint records
`origin = list_after_expiry`, so the discontinuity is legible in provenance
rather than smoothed into a line that implies continuity. Recovery is bounded
(3 consecutive) — a cluster expiring every position is a condition to surface.

## Decision 8 — The driver lives in the composition layer

`BND-WORLD-CANNOT-EXECUTE` makes `backend.world` importing
`backend.contexts.execution` an architecture ERROR. That rule *is* the
enforcement of "the World Plane never opens the Kubernetes connection itself", so
the driver lives in `backend/api/` — the layer permitted to see both planes.

`backend/api/governed_read_observer.py` also closes a long-standing gap: until
now, *nothing in `backend/`* mapped a governed execution result to a
`ReadObservation`. Every phase from 7.2 to 9.2 did it inside its harness script.
A continuous observer cannot live in `scripts/`.

## Decision 9 — No new architecture fitness rule

`BND-WATCH-CANNOT-BYPASS-GOVERNANCE` was considered and **rejected as cosmetic**.
`BND-WORLD-CANNOT-EXECUTE` already forbids the World Plane importing connectors,
execution or transport; `BND-DIRECT-HTTP` already forbids a second HTTP client in
`backend.contexts`; `BND-PROVIDER-SDK` already bans provider SDKs. A watch that
bypassed governance would have to violate one of these first.

## Consequences

- Kubernetes changes reach the World Plane continuously, through one governed
  path, with exact resourceVersion continuity and honest 410 recovery.
- The generic execution fabric gained three narrow, provider-neutral extensions;
  one of them (Decision 3) widens a stated invariant, disclosed above.
- No second gateway, executor, scheduler, transport, credential path, audit
  chain, observation store, election, or persistence authority was created.
- The governed evidence store of ADR-042 §56 is now an explicit, named debt.
- Per-event latency is bounded by the watch window, and "streaming" is not
  claimed anywhere.
