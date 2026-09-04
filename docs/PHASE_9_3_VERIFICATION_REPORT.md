# PHASE 9.3 — Verification Report

**Governed Kubernetes WATCH & continuous world observation.** Every claim is
labelled `[VERIFIED]` (a run proved it), `[FACT]` (declared in code, cited),
`[NOT VERIFIED]`, `[DEFERRED]` or `[BLOCKED]`. Code existing is never a reason to
write `[VERIFIED]`.

## Honesty header — read this before the table

- `[VERIFIED]` **A real Kubernetes API server was watched.** A disposable local
  k3d cluster (k3s **v1.35.5**), real HTTPS, real ServiceAccount token, real
  RBAC, real pod mutations driven out of band by `kubectl`. Not a mock, not a
  script, not a production cluster.
- `[FACT]` **This is NOT streaming, and the phase never claims it is.** The
  governed transport refuses server-sent events by construction
  (`httpx_adapter.py:151-156`), so the watch is consumed as **bounded windows**
  (`?watch=true&timeoutSeconds=W`). resourceVersion continuity across windows is
  exact; per-event visibility latency is bounded by `W`, not by network arrival.
  Measured below. Calling this "real-time" would be false.
- `[FACT]` **At-least-once, not exactly-once.** Events are recorded, then the
  position advances. A crash between them re-delivers. Exactly-once is neither
  claimed nor implemented.
- `[FACT]` **One invariant was deliberately widened** (bounded structured
  evidence, ADR-083 Decision 3). Stated in full in §7 rather than buried.
- `[FACT]` **Phase 5.5 remains `[BLOCKED]` and untouched.** No production
  credential was inspected, created or modified. The Kubernetes credential is a
  2-hour, namespace-scoped ServiceAccount token for a disposable cluster,
  entering once at the composition root.

## Evidence environment

| Item | Value |
|---|---|
| Cluster | k3d `cortex-p93`, k3s **v1.35.5+k3s1**, single server, disposable |
| API endpoint | `https://127.0.0.1:62562` (literal loopback, in the cert SANs) |
| TLS | verified against the cluster CA (`CORTEX_TLS_CA_BUNDLE`); the transport has no `verify=False` |
| Credential | `kubectl create token cortex-watcher --duration=2h` |
| RBAC | Role `pod-watcher`: **get/list/watch on pods, namespace `cortex-p93` only** |
| RBAC negative proof | `can-i delete pods` → **no**; `can-i watch pods -n default` → **no** |
| Database | Postgres 16 (pgvector), database `cortex_p93`, **dropped and recreated per run**, migrated to head |
| Capabilities | `platform.kubernetes.pods.list`, `platform.kubernetes.pods.watch` (the only real exposure) |
| Harness window / lease | 5s / 12s (production default window is 20s; same code path, both recorded) |
| Provisioning | `scripts/phase93_provision.sh` (also tears down) |
| Harness | `scripts/phase93_kubernetes_watch_harness.py` |

## Verdict

| Gate | Result |
|---|---|
| Phase 9.3 real harness | **VERIFIED — 84/84**, exit 0 |
| Phase 9.3 unit tests | **48/48 passed** (`tests/intelligence/test_kubernetes_watch.py`) |
| Architecture fitness gate | **PASS — 35 passed, 0 failed**, 6 skipped, 1175 modules |
| Regression (affected areas) | see §9 |
| New fitness rule added | **none** — deliberately (§8) |

---

## 1. Requirements A–Y

Every row below is a harness check that ran against the live cluster.

| # | Requirement | Result | Evidence |
|---|---|---|---|
| A | governed LIST obtains real RV | `[VERIFIED]` | `established`, RV **2833**, exactly 1 provider dial |
| B | WATCH starts from exact real RV | `[VERIFIED]` | request query `resourceVersion=2833`, LIST returned `2833` — byte-identical |
| C | ADDED becomes an Observation | `[VERIFIED]` | real `kubectl scale`; `ADDED` in the ledger |
| D | MODIFIED becomes an Observation | `[VERIFIED]` | `MODIFIED` in the ledger |
| E | DELETED becomes an Observation | `[VERIFIED]` | `DELETED` in the ledger |
| F | resourceVersion preserved exactly | `[VERIFIED]` | every observation carries an opaque non-empty string; none coerced to a number; position `2833 → 2891`, origin `watch` |
| G | tenant scope preserved | `[VERIFIED]` | cross-tenant position read → `None`; cross-tenant subject count → 0 |
| H | provider failure produces no Observation | `[VERIFIED]` | unreachable endpoint + TLS refusal legs: `observations_delta == 0`, position unmoved |
| I | unauthorized produces no Observation | `[VERIFIED]` | bad token → `Unauthorized`; forbidden namespace → the cluster's own *"pods is forbidden: User system:serviceaccount:cortex-p9…"*; both `delta == 0` |
| J | malformed event fails closed | `[VERIFIED]` (unit) | truncated window, unparseable line, non-object line, missing `resourceVersion`, unidentifiable mutation — each `MALFORMED_RESPONSE`, no evidence |
| K | unknown event type fails closed | `[VERIFIED]` (unit) | `{"type":"SYNTHESIZED"}` → refused through the real adapter, `evidence == {}` |
| L | 410 recovery performs a fresh governed LIST | `[VERIFIED]` | **the real cluster refused a real expired position**; `recovered_from_expiry` |
| M | old RV never reused after 410 | `[VERIFIED]` | expired `1` never appears again; the fresh LIST carries **no** `resourceVersion` |
| N | new RV persisted | `[VERIFIED]` | **2892**, checkpoint `origin=list_after_expiry` |
| O | WATCH resumes from the new RV | `[VERIFIED]` | next request `resourceVersion=2892` |
| P | duplicate event is idempotent | `[VERIFIED]` | same delivered observation ingested twice → recorded once (deterministic identity). **Scope stated in §5.** |
| Q | replay is inert | `[VERIFIED]` | zero provider calls, zero observations, zero audit records, watch not restarted |
| R | crash recovery preserves observations | `[VERIFIED]` | 5 real `os._exit(9)` points, all exit 9; no observation lost at any point |
| S | concurrent watcher leadership is single-holder | `[VERIFIED]` | two real OS processes (pid 25136 / 20868): first acquired token 16, second **refused** |
| T | stale watcher is fenced | `[VERIFIED]` | token advanced 17 → 18; stale handle refused; stale handle **cannot even renew** |
| U | secret scan is clean | `[VERIFIED]` | full scan of every text-castable column of every table: token absent |
| V | audit chain valid | `[VERIFIED]` | 16 records, **0 defects** |
| W | WorldQuery sees accepted observations | `[VERIFIED]` | answers the stream position |
| X | Fact reconstruction is deterministic | `[VERIFIED]` | re-deriving every observation → **entirely `DEDUPED`**. Caveat in §6. |
| Y | no World/Intelligence direct provider access | `[VERIFIED]` | `BND-WORLD-CANNOT-EXECUTE` + `BND-DIRECT-HTTP` pass; V1 connector library never imported |

## 2. Crash matrix — real process death

Five points, real `os._exit(9)`, all confirmed by exit code 9.

| Point | Result | Evidence |
|---|---|---|
| before WATCH starts | `[VERIFIED]` | position survived (**2892**), 23 → 23 observations |
| after LIST, before WATCH | `[VERIFIED]` | position **2940**, no loss |
| **after events, before checkpoint** | `[VERIFIED]` | **26 → 31 observations recorded BEFORE the position moved** — the ordering that makes at-least-once safe, proven by killing the process in exactly that gap |
| after the position advanced | `[VERIFIED]` | position **3017**, no loss |
| during 410 recovery | `[VERIFIED]` | position **3035**, no loss |

In every case a successor resumed the stream after the dead process's lease
lapsed. `[FACT]` A successor cannot take over instantly — the dead holder's lease
must expire first — which is the leadership model working, not a defect.

## 3. Performance — measured, not speculated

| Measurement | Value |
|---|---|
| LIST latency | **985 ms** |
| WATCH establishment + one 5s window | **5 642 ms** |
| event → observation (real scale-up) | **6 076 ms** (one window + persistence) |
| 410 expiry recovery (refused watch + fresh LIST) | **1 661 ms** |
| observation persistence p50 / p95 | **11.3 ms / 13.0 ms** |
| total provider dials, whole run | 12 |
| declared window (production / harness) | 20 s / 5 s |
| max events per window | 64 |

`[FACT]` Event-to-observation latency is dominated by the window length, exactly
as the bounded-window design implies. No index and no infrastructure was added:
nothing in these numbers asked for one.

## 4. Failure boundaries — every negative proves absence of effect

`[VERIFIED]` Four real failure legs, each in its own OS process with its own
composition-time configuration, so the failure is genuine rather than injected.
Every one recorded **zero observations** and **left the stream position
unmoved**:

| Leg | The cluster's / transport's own answer |
|---|---|
| bad token | `Unauthorized` |
| forbidden namespace | `pods is forbidden: User "system:serviceaccount:cortex-p9…"` |
| unreachable API server | `the destination refused the connection (ConnectError)` |
| wrong CA | `the transport could not be configured (SSLError)` |

`[FACT]` The forbidden-namespace message is the cluster's own sentence, which
only survives because the NDJSON decoder hands **failure** bodies to the JSON
path. A bug found by a test during this phase: decoding a refused watch as a
stream wrapped Kubernetes' `Status` document in an events envelope and the
operator got "status 410" instead of "too old resource version: 4 (99)".

## 5. What "idempotent" does and does not mean here `[FACT]`

`[VERIFIED]` The same delivered observation ingested twice is recorded **once** —
deterministic identity over (tenant, source, subject, predicate, `observed_at`,
value) collides on the unique constraint.

`[NOT VERIFIED — and not claimed]` Exactly-once across a crash. A re-delivered
event after a crash has a later `observed_at` (Kubernetes watch events carry no
event timestamp, and CortexPrime will not fabricate one), so it becomes a second
Observation row: an honest record of a second delivery, never a lost one. Fact
derivation then resolves it to `DEDUPED`, so world **belief** does not move.
Duplicate delivery is visible in the ledger and inert in the conclusions.

## 6. An honest finding: CONFLICTED facts within a window `[FACT]`

Fact derivation over the watch observations produced both `asserted` **and
`conflicted`** outcomes. This is correct behaviour and worth stating plainly:
every event in one window shares an `observed_at` (the window's retrieval
moment), so two events about the same pod in the same window are two different
values at the same valid instant — and the World Plane records `CONFLICTED`
rather than choosing without authority.

That is the bitemporal model doing its job, not a defect. It is also a real
limitation of window-granularity valid time. Giving each event its own valid time
would need an event timestamp Kubernetes does not provide; deriving one from
`resourceVersion` would be exactly the "treat resourceVersion as a timestamp"
error this phase forbids. `[DEFERRED]` to a phase that can source a real per-event
time (e.g. correlating `Event` objects, which do carry timestamps).

## 7. The invariant that moved, stated plainly `[FACT]`

`ProviderOutcome.output` is *"digested, never carried into the result"*, and
`spec.evidence()` extracted **top-level scalars only**, because ADR-042 §56 says
a raw provider payload *"belongs in an evidence store with its own governance"*.
**No evidence store exists.** A watch window is N events, each needing type +
identity + its own `resourceVersion` — not expressible as a flat scalar map.

Phase 9.3 extends the declaration rather than abandoning it
(`RecordEvidenceSpec`): ONE declared list field, a hard `max_records` cap (64),
declared per-record scalar fields, nested structures dropped, and the whole spec
**in the operation digest** so widening it is contract drift.

**The cost, not hidden:** an execution attempt's detail can now grow from ~6
scalars to up to 64 × 6. The bound is bigger and it is still a bound. Building
the governed evidence store ADR-042 §56 names remains the correct successor and
is now an explicit, named debt. `[DEFERRED]`

Related: `to_execution_result` now lifts `provider_status` as well as
`provider_evidence` — one bounded scalar, without which 410 (expired, re-LIST)
could not be told from 403 (refused, fail closed) except by substring-matching a
message.

## 8. Architecture fitness `[VERIFIED]`

**PASS — 35 passed, 0 failed, 6 skipped, across 1175 modules.**

`BND-WATCH-CANNOT-BYPASS-GOVERNANCE` was considered and **not added**, because it
would be cosmetic. The relevant rules already pass and already cover it:

- `BND-WORLD-CANNOT-EXECUTE` — the World Plane imports no connector, transport or
  execution plane. This is what makes "World never opens the Kubernetes
  connection" structural rather than a convention.
- `BND-DIRECT-HTTP` — no second HTTP client inside the governed path.
- `BND-PROVIDER-SDK` — no Kubernetes SDK.
- `BND-OBSERVATION-APPEND-ONLY` — no UPDATE/DELETE on observations.

`[FACT]` One existing rule **caught a real violation during this phase**:
`GovernedCapabilityReader` was written into `governed_read_observer.py`, which
made that module import two bounded contexts. The composition-root test failed,
and the class was moved into `capability_execution_composition.py` — a named,
ADR-recorded composition root — where importing two contexts is sanctioned.

## 9. Regression `[VERIFIED]` / `[FACT]`

- `[VERIFIED]` Phase 9.3 unit tests: **48/48**.
- `[VERIFIED]` The affected areas — `tests/intelligence`, `tests/contexts/execution`,
  `tests/world`, `tests/platform`, `tests/assurance` — **1203 passed, 1 failed**.
  The single failure is `test_dependency_isolation[credentials\inspection.py]`
  (*"imports disallowed root(s): ['base64']"*), which reproduces identically on
  clean `HEAD` with every Phase 9.3 change stashed. That file is untouched here
  (`git diff HEAD` on it is empty; last changed in `ee43f3a`).
- `[VERIFIED]` Composition-root boundary tests pass.
- `[FACT]` Four Phase 9.1/9.2 assertions were updated because 9.3 legitimately
  supersedes them (a seventh declared operation; list **+ watch** as the real
  exposure; the watch's position living in `lastResourceVersion`; and
  `provider_status` now being lifted). Each was rewritten to assert the new
  intent, not deleted.
- `[FACT]` The whole-repo suite has **pre-existing failures unrelated to this
  phase** — confirmed by stashing every Phase 9.3 change and re-running the
  suspect files on clean `HEAD`, which reproduced them (24 failures in that
  subset, including `credentials\inspection.py imports base64` and the
  `test_auth_enforcement` cases; the file is untouched by this phase). They are
  **not** claimed as green and are **not** introduced here.
- `[NOT VERIFIED]` `tests/benchmarks/test_infrastructure_performance.py` needs a
  Neo4j instance and does not run in this environment. Pre-existing.

## 10. Stop conditions

| # | Condition | Status |
|---|---|---|
| 1 | second transport architecture | **Avoided** — bounded windows, one dial each |
| 2 | World opens a provider connection | Never — structurally impossible, gate-enforced |
| 3 | resourceVersion continuity unprovable | Disproved — exact continuity verified |
| 4 | 410 recovery needs fabricated history | No — fresh LIST, discontinuity recorded in provenance |
| 5 | tenant identity untrustworthy | No — tenant from governed context only |
| 6 | credentials not composable through the root | No — composition root only |
| 7 | weakening an existing invariant | **Triggered, surfaced, decided by the user, disclosed in §7** |
| 8 | second execution/governance/coordination authority | None created |
| 9 | exactly-once claimed without proof | Not claimed anywhere |
| 10 | tempting V1 implementation | None exists — no V1 Kubernetes watch in the repo |

## 11. Explicitly NOT in this phase `[FACT]`

No RCA, hypothesis generation, prediction, embeddings, vector search, semantic
RAG, LLM reasoning, incident diagnosis or autonomous remediation. The watch makes
the World Plane observe reality continuously; it draws no conclusions.

## 12. Reproducing

```bash
bash scripts/phase93_provision.sh          # k3d cluster + RBAC + fresh Postgres
set -a; . ./.phase93.env; set +a
python -m scripts.phase93_kubernetes_watch_harness   # exit 0 = VERIFIED
bash scripts/phase93_provision.sh teardown # removes cluster, container, certs
```
