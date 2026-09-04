# ADR-084 — Phase 9.4: Observability corroboration and multi-source world evidence

**Status:** Accepted
**Date:** 2026-09-04
**Extends:** ADR-041 (transport), ADR-042 (provider fabric), ADR-064 (observation
ingestion), ADR-067 (corroboration), ADR-068 (lineage/authority), ADR-081/082/083.

## Context

Phase 9.3 gave the World Plane one continuous view of reality. One view cannot be
corroborated: a single instrument reporting a fact is a fact with one witness,
and a platform that treats that as confirmed is manufacturing certainty.

Phase 9.4's objective is a *second* view, and — the harder half — an honest
answer to whether the two views are actually independent.

## Decision 1 — Prometheus directly, not Grafana

Discovery (docs/PHASE_9_4_IMPLEMENTATION_MAP.md §2) settled this on evidence:

- Grafana's governed catalog declares two **folder** operations and no query
  capability. It is a governed *write* vertical, not an evidence source.
- Data read *through* Grafana is `DERIVED` from Prometheus, so routing through it
  adds a hop and **subtracts** evidential value — it cannot be a second
  independent source of what Prometheus already says.
- The Prometheus HTTP API is conventional JSON, so `BND-PROVIDER-SDK` is
  untouched and the existing adapter/channel/broker carry it unchanged.
- Prometheus returns a **provider sample timestamp**, which is what makes honest
  `observed_at` possible at all.

Grafana's catalog is not touched by this phase.

## Decision 2 — The PromQL is declared, never composed

The quarantined V1 connector has `query(self, query: str)` — a caller-supplied
PromQL string, which is the Prometheus form of `request(url, method, body)`. A
capability authorizing it would describe nothing.

So the query lives in `static_query` (the mechanism Phase 9.3 added) and is in
the operation's digest. The governed Prometheus operations declare **zero
parameters**: there is no field through which a caller or a model could compose,
extend or influence a query, and `plan()` refuses an undeclared input outright.

The observed namespace is compiled into the declared selector at catalog
construction from deployment configuration — the same rule as `base_url` — and a
namespace containing characters that could close the label matcher is refused at
construction rather than trusted for being configuration.

**Stated cost:** one declared operation per (metric, scope) pair. A declared,
validated selector-template mechanism is the successor. `[DEFERRED]`, named.

## Decision 3 — Lineage keys on the *instrument*, not the provider

Every World Plane policy — lineage, authority, freshness — matches on
`(source_kind, source_ref)`, and `source_ref` is documented as an instrument id.
That is the whole mechanism, and it needed no new machinery:

| `source_ref` | origin | relation |
|---|---|---|
| `connector:kubernetes` | `kubernetes-cluster` | `DIRECT` |
| `prometheus:kube-state-metrics` | `kubernetes-cluster` | **`DERIVED`** |
| `prometheus:self` | `prometheus-server` | `DIRECT` |
| anything unmapped | — | `UNKNOWN` |

The second row is the point of the phase. `kube_pod_container_status_restarts_total`
arrives through a different provider, over a different connection, with a
different credential — and it is **the Kubernetes API's own number**, because
kube-state-metrics does nothing but scrape the API server and re-export it. A
platform that could not tell would count one fact twice and call it corroboration.

Lineage is an operator's statement about their own topology; nothing in the data
declares it. The honest default for an unstated instrument is `UNKNOWN`, and the
corroboration engine already refuses to claim independence for it.

## Decision 4 — Corroboration needs a declared shared proposition

This was the discovery finding that most shaped the design.

`belief.py` decides support by comparing **value digests** for the same
`(subject_ref, predicate)`. Raw provider shapes never match: Kubernetes says
`restartCount: 7`, Prometheus says `value: "7"`, and those are two digests —
which reads as CONTRADICTED when the sources actually agree.

**So what proposition an operation observes, and in what shape, is declared per
operation and shared across providers.** It is in the catalog and in the digest,
never inferred.

The first vertical deliberately uses a quantity both instruments *literally
report* — a container's restart count — so nothing is interpreted. Deriving "this
pod is unhealthy" from a restart count would be the inference this phase forbids
and is not performed.

## Decision 5 — Provider event time, and two clocks

`observed_at` is Prometheus's own sample timestamp, not this process's clock.

Two consequences are stated rather than hidden:

1. **The instant-query timestamp is the evaluation instant, not the scrape
   instant.** Prometheus resolves each series to the most recent sample within
   its lookback delta (5m default), so the underlying sample may be older than
   the timestamp returned. The freshness horizon is set with that in mind, and
   the report classifies it rather than claiming sample-exact time.
2. **Two clocks disagree.** A provider container running a second ahead produces
   `observed_at > retrieved_at`, which the temporal contract refuses — correctly,
   because a fetch cannot precede the moment it observed. The resolution keeps
   `observed_at` exactly as the provider stated it and advances `retrieved_at` to
   meet it; skew beyond a declared bound is **refused**, because a provider whose
   clock is minutes ahead is a condition to surface, not to absorb.

The skew is deliberately **not** written into the observation value: the value is
the proposition, and it must be byte-identical to what the other instrument
reports or corroboration compares two digests and calls agreement a
contradiction. Retrieval metadata does not belong in a claim about the world; the
skew stays reconstructable from the execution the observation names.

## Decision 6 — Everything else is reused

The corroboration engine, the lineage model, the freshness and authority
policies, the observation ledger, the fact derivation, `WorldQuery`, the
execution/governance/credential/audit fabric and the leadership role were all
**already built and already correct**. Phase 9.4 adds no World store, no RAG, no
vector database, no graph database, no second authority, and no migration —
lineage, authority and freshness are computed from policy at query time, so there
is nothing new to persist.

What was genuinely missing and is added:

- `backend/api/observability_evidence.py` — the deployment's **declared policy
  set** (which instrument came from which origin, what standing each has, how
  long its evidence stays fresh) and the proposition mapper.
- `WorldQueryEvidencePort` — a production adapter for the `WorldReadPort` the
  investigation engine consumes. The protocol was declared with no production
  implementation behind it; every phase satisfied it inside its own harness. It
  holds a `WorldQuery` and nothing else, so there is no path through which an
  investigation could reach a provider.
- Per-pod record evidence on `kubernetes.pods.list`. A list previously kept only
  counts, which is enough to notice something is wrong and not enough to say
  anything about a *particular* pod — so it could not corroborate a metric that
  names one.

## Decision 7 — No new fitness rule

`BND-INTELLIGENCE-CANNOT-DIRECT-OBSERVABILITY` was considered and **rejected as
cosmetic**. `BND-INTELLIGENCE-CANNOT-EXECUTE` already makes an Intelligence
module importing a connector or transport an ERROR;
`BND-INTELLIGENCE-CANNOT-BYPASS-WORLD` already forbids it importing World
storage; `BND-WORLD-CANNOT-EXECUTE` already forbids the World Plane reaching a
provider at all; `BND-DIRECT-HTTP` already forbids a second HTTP client. A
Prometheus read that bypassed governance would have to violate one of these
first.

## Decision 8 — Prometheus sits behind a bearer proxy in the evidence topology

The credential broker refuses **per provider** ("no credential adapter is
registered for this provider; there is no default credential and no fallback"),
and Prometheus has no native bearer auth. A reverse proxy that enforces one is
how Prometheus is actually protected in real deployments; it makes the governed
credential do real work and makes a 401 a real refusal rather than a decorative
one. This is evidence-environment topology, not product code.

## Consequences

- CortexPrime can state, with reasons, whether two views of reality are
  independent, correlated, contradictory, indeterminate or insufficient — over
  real evidence from two real providers.
- The most valuable answer it can now give is a **refusal**: two sources
  reporting the same number are CORRELATED, not corroborating, when one derives
  from the other.
- No numeric source weights, no confidence scores, no model in the evidence path.
- Cost: the proposition vocabulary must be declared per operation, and the
  declared-query approach does not yet scale across namespaces. Both are named
  debts, not hidden ones.
