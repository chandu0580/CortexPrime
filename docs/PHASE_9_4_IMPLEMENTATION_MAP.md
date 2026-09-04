# PHASE 9.4 — Implementation Map (DISCOVERY OUTPUT)

**Status: DISCOVERY COMPLETE.** Every statement is cited to source read in this
session; prior phase reports were used only as pointers, never as evidence. No
stop condition fires. Two findings change what this phase is (§6, §7).

Labels: `[FACT]` read in source · `[VERIFIED]` proven by a run · `[NOT VERIFIED]`
· `[DEFERRED]` · `[BLOCKED]` · `[INFERENCE]`.

---

## 1. Observability inventory

### 1.1 Governed (the fabric that counts) `[FACT]`

| Provider | Governed operations | Evidence value |
|---|---|---|
| `kubernetes` | `pods.list`, `pods.watch` real-exposed; 5 more declared | **Real, since 9.2/9.3** |
| `grafana` | `folder.create_folder`, `folder.get_folder` | **None.** Folder CRUD only |
| `github` | 5 ops | credential `[BLOCKED]` (Phase 5.5) |
| controlled/widget | scripted | test fixture |

`[FACT]` `grafana_catalog()`
(`backend/contexts/execution/infrastructure/adapters/connectors/grafana.py`)
declares exactly two operations, both about folders. **There is no governed
metric, query, datasource, alert or dashboard read anywhere in the repository.**
Grafana today is a governed *write* vertical, not an evidence source.

### 1.2 Ungoverned V1 zone (quarantined) `[FACT]`

`backend/connectors/`: `prometheus.py`, `loki.py`, `opentelemetry.py`,
`grafana.py`. The Prometheus one is a complete PromQL client —
`query(self, query: str)` → `GET /api/v1/query?query=<promql>`, plus
`query_range`, `labels`, `series`, `targets`, `rules`, `alerts`.

`[FACT]` **This is the exact anti-pattern `provider_operation.py` exists to
prevent**: a caller-supplied query string is the Prometheus equivalent of
`request(url, method, body)`. Every operation it can perform is "whatever the
caller typed", so a capability authorizing it would describe nothing. It is a
strangler target and must not be reused.

Also present and irrelevant here: `backend/observability/prometheus_metrics.py`
(CortexPrime exporting *its own* metrics), `backend/services/enterprise_*_
intelligence.py` (V1 analytics).

### 1.3 Is Prometheus actually present? `[FACT] — YES`

`docker-compose.yml:351` → `prom/prometheus:v2.52.0`, host port 9090, config at
`infra/prometheus/prometheus.yml` (real scrape config, 15s interval).
`docker-compose.yml:378` → `grafana/grafana:11.1.0`, host port 3001, with
`infra/grafana/provisioning/datasources/prometheus.yml`.

So the topology **Prometheus → Grafana** already exists in this repository's own
deployment, which is precisely the lineage trap the mission names.

---

## 2. Which provider becomes the second evidence source

**Decision: A — Prometheus, directly.** On evidence, not convenience:

1. `[FACT]` Grafana's governed catalog has **no query capability**. Making
   Grafana the evidence source means building a new Grafana datasource-proxy
   capability *and* it would return Prometheus data.
2. `[FACT]` Grafana-proxied Prometheus data is `DERIVED` from Prometheus. The
   mission itself states this must not count as a second independent source —
   so routing through Grafana adds a hop and **subtracts** evidential value.
3. `[FACT]` The Prometheus HTTP API is conventional JSON over HTTP; no SDK is
   needed, so `BND-PROVIDER-SDK` is untouched and the existing
   `ConnectorAdapter` + `ProviderChannel` + `TransportBroker` carry it unchanged.
4. `[FACT]` Prometheus returns a **provider sample timestamp** with every
   series, which is what makes honest `observed_at` possible (§8).

Grafana stays what it is. This phase does not touch its catalog.

---

## 3. The reuse story: almost all of this already exists `[FACT]`

This is the central discovery finding, and it changes what Phase 9.4 *is*.

### 3.1 Lineage-aware corroboration is already built

`backend/world/application/lineage.py` (Phase 7.6) already models exactly the
cases the mission specifies — its own docstring uses the Prometheus example:

> "two providers may both read the same API… Prometheus from kube-state-metrics
> from the K8s API"

`LineageRelation` = `DIRECT` / `DERIVED` / `MIRRORED` / `UNKNOWN`.
`LineageRule` matches on `(source_kind, source_ref)`; unmatched ⇒ `UNKNOWN`.

`backend/world/application/belief.py:368-425` `_corroborate` already decides:

| Situation | Level | Already implemented |
|---|---|---|
| ≥2 distinct **known** origins agree | `INDEPENDENT` | ✅ |
| 1 known origin, no unknowns | `CORRELATED` | ✅ |
| ≥2 sources agree, lineage unknown | `INDETERMINATE` | ✅ |
| sources disagree | `CONTRADICTED` | ✅ |
| one supporting source | `SINGLE` | ✅ |
| nothing covers the instant | `INSUFFICIENT` | ✅ |

Every branch carries a `reason` string. **No numeric weights anywhere.**

### 3.2 Freshness and authority are already policy-driven

`FreshnessPolicy` — ordered `FreshnessRule`s on `(source_kind, predicate)`, first
match wins, **no default horizon**, unmatched ⇒ `UNKNOWN`. Docstring: *"STALE is
NOT FALSE… UNKNOWN is NOT FALSE either."*

`AuthorityPolicy` — ordered `AuthorityRule`s on `(source_kind, source_ref)` to a
`SourceAuthority` tier; unmatched ⇒ `UNVERIFIED`. `AuthorityStatus.CONFLICTED`
preserves both paths.

### 3.3 The Investigation evidence path is already correct

`backend/intelligence/application/proposal.py:271-287` declares two ports:

- `WorldReadPort.evidence_for(...)` — *"Read-only World Plane evidence… backed by
  WorldQuery. Tenant-scoped, no side effects."*
- `EvidenceAcquisitionPort.acquire(...)` — *"the governed READ path… **This is
  the ONLY way the Intelligence Plane obtains new world evidence; it never
  touches a connector itself.**"*

`engine.py:290-312` `_reuse_existing_evidence` consumes `WorldQuery`'s verdicts
and refuses to reclassify them (`STALE`/`CONFLICTED`/`UNKNOWN` ⇒ no reuse).

**So requirements Q and R are about *proving* this against a real second source,
not building it.**

### 3.4 Therefore Phase 9.4 is not "add Prometheus"

It is: **produce a real second observation source whose lineage is honestly
declared, and prove the existing engine against real multi-source evidence.**
The build is small; the evidence is the deliverable.

---

## 4. What must NOT be built `[FACT]`

| Feared addition | Verdict |
|---|---|
| New World store / RAG / vector DB / graph DB | **Not needed.** `cw_observation` + `cw_fact` already carry everything; §5 shows the contract fits |
| New corroboration engine | **Already exists** (§3.1) |
| New freshness/authority model | **Already exists** (§3.2) |
| New execution/governance/credential/audit authority | Reused verbatim |
| New observation type | **Not needed** — `ObservationSourceKind.CONNECTOR` + `source_ref` covers a metric instrument |
| New fitness rule | **Not needed** — see §9 |
| New transport | Not needed — Prometheus is conventional HTTP |

---

## 5. The observation contract fits, unchanged `[FACT]`

`ObservationSourceKind.CONNECTOR` is documented as *"A governed connector read
(e.g. Grafana query, kubectl get)"* — a metric read is exactly that.
`ObservationSource.source_ref` is *"an instrument id"*.

**That last point is load-bearing** (§7): every policy in the World Plane —
lineage, authority, freshness — matches on `(source_kind, source_ref)`. So the
mechanism for distinguishing "this Prometheus series came from kube-state-metrics"
from "this one came from the node exporter" is **a distinct `source_ref` per
instrument**, which requires no new machinery at all.

---

## 6. FINDING 1 — arbitrary PromQL must not exist, and need not `[FACT]`

A governed Prometheus read cannot take a caller-supplied query. Discovery found
the resolution already shipped in Phase 9.3: **`ProviderOperationSpec.static_query`**.

The PromQL lives in the operation's declaration, in its digest:

```python
ProviderOperationSpec(
    operation="prometheus.pod_restarts",
    method="GET", path_template="/api/v1/query",
    static_query={"query": 'kube_pod_container_status_restarts_total{namespace="cortex-p94"}'},
    side_effect_class=SideEffectClass.READ,
    response_evidence_records=RecordEvidenceSpec(
        field_name="series", fields=("pod", "container", "value", "timestamp"), max_records=64),
)
```

There is **no parameter a model could compose a query with**, and `plan()`
refuses an undeclared input outright (proven in Phase 9.3's tests). The namespace
is deployment configuration baked in at catalog construction — the same rule as
`base_url`: *"the destination is deployment configuration, not request input."*

`[FACT]` **Stated cost:** one declared operation per (metric, scope) pair. This
does not scale to many namespaces, and a declared, validated selector-template
mechanism is the successor. `[DEFERRED]`, named, not smuggled in here.

`[FACT]` The vector response shape maps onto Phase 9.3's `RecordEvidenceSpec`
with **zero new generic machinery**: one record per series, declared scalar
fields only, hard-capped.

---

## 7. FINDING 2 — corroboration needs a shared proposition vocabulary `[FACT]`

This is the finding that most shapes the design, and it is not obvious.

`belief.py:386` decides support by comparing **value digests**:

```python
if eff_digest is not None and compute_digest(obs.value).value == eff_digest:
    supporting.append(ev)
```

So two sources corroborate only if they produce the **same `(subject_ref,
predicate)` and the same value**. Raw provider shapes never do: Kubernetes says
`{"restartCount": 7}` and Prometheus says `{"value": "7"}`, and those are two
digests — which would read as `CONTRADICTED` when the sources actually agree.

**Therefore: what proposition an operation observes, and in what shape, must be
declared per operation and shared across providers.** The vocabulary is part of
the catalog, in the digest, and never inferred.

Chosen for the first vertical — deliberately a quantity **both instruments
literally report**, so nothing is interpreted:

| Proposition | Kubernetes | Prometheus |
|---|---|---|
| subject `kubernetes:pod:{ns}/{pod}`, predicate `restart_count` | pod status `restartCount` | `kube_pod_container_status_restarts_total` |

`[FACT]` These are **the same number** — kube-state-metrics scrapes it from the
Kubernetes API. That makes it the perfect Case C: two sources, identical value,
and the platform must still refuse to call it independent corroboration.

**No interpretation is performed.** Deriving "the pod is unhealthy" from a
restart count would be exactly the inference the mission forbids, and is not done.

---

## 8. Time semantics, honestly `[FACT]`

A Prometheus instant query returns, per series, `[<unix_ts>, "<value>"]`.
`<unix_ts>` is a genuine provider timestamp and becomes `observed_at`.

`[FACT] **Stated limitation, not glossed:** for `/api/v1/query` that timestamp is
the **evaluation instant**, not the scrape instant. Prometheus resolves each
series to the most recent sample within its lookback delta (default 5m), so the
underlying sample may be older than the timestamp returned.` This is real
Prometheus semantics. The freshness horizon for metric evidence must be set with
it in mind, and the report will classify it rather than claim sample-exact time.

`recorded_at` remains CortexPrime's own write time. No future knowledge; the
bitemporal model is untouched.

---

## 9. Fitness rules — no new rule `[FACT]`

`BND-INTELLIGENCE-CANNOT-DIRECT-OBSERVABILITY` was considered and is **cosmetic**.
Two existing ERROR rules already make it impossible, and both passed the Phase 9.3
gate:

- `BND-INTELLIGENCE-CANNOT-EXECUTE` (boundary_rules.py:1409) — the Intelligence
  Plane imports no connector, gateway, adapter, transport or credential carrier.
  A `backend/intelligence/**` module importing the Prometheus connector is an
  ERROR today, before this phase adds anything.
- `BND-INTELLIGENCE-CANNOT-BYPASS-WORLD` (boundary_rules.py:1535) — it imports no
  World storage; evidence comes through the World application layer only.

Plus `BND-DIRECT-HTTP` (no second HTTP client in `backend.contexts`) and
`BND-WORLD-CANNOT-EXECUTE` (the World Plane cannot reach a provider at all).

A Prometheus read that bypassed governance would have to violate one of these
first. Per the mission's own instruction, no rule is added.

---

## 10. Tenant and credential implications `[FACT]`

**Tenant.** Comes from the governed `ExecutionContext`, exactly as in 9.3.
`ObservationIngestion.ingest` re-checks it and refuses a non-`TenantRef`. Nothing
reads a tenant from a Prometheus label, a Kubernetes namespace, or a metric name —
and `find_secrets` runs over every value before it is recorded.

**Credential — a real constraint discovered here.** `CredentialBroker`
(`broker.py:297-305`) refuses `NO_PROVIDER` **per provider**: *"no credential
adapter is registered for this provider; there is no default credential and no
fallback."* The broker is deployment-wide, so once Kubernetes registers one, a
Prometheus read with no registered adapter is refused before it is attempted.

`[FACT]` Prometheus has no native bearer auth (`--web.config.file` supports basic
auth only), and `_present()` (`httpx_adapter.py:455-475`) renders every supported
credential type as `Bearer`. So the evidence topology puts Prometheus behind a
**bearer-token reverse proxy** — which is how Prometheus is actually protected in
real deployments, makes the credential do real work, and makes the 401 negative
test a genuine refusal rather than a decorative one.

---

## 11. Is a new persistence structure necessary? `[FACT] — NO`

`cw_observation` already stores tenant, source kind, source ref, subject,
predicate, value, status, `observed_at`, `retrieved_at`, `recorded_at`,
provenance and a deterministic identity — every field §5 of the mission requires.
Lineage, authority and freshness are **computed from policy at query time**, not
stored, so there is nothing new to persist. `cw_fact` handles derivation.

No migration. No new table. No new column.

---

## 12. Minimal implementation plan

1. **`.../adapters/connectors/prometheus.py`** — the governed catalog: fixed
   PromQL in `static_query`, `PrometheusResponseTranslator` (Prometheus reports
   errors as `{"status":"error","errorType":...,"error":...}` **with HTTP 200 in
   some versions** — that must classify as a failure, not a success),
   `PrometheusVectorNormalizer` (vector → declared bounded records + the
   proposition projection of §7), `build_prometheus_channel`, `CapabilityProfile`s.
   Imports no SDK, no httpx, no `os`, no `backend.connectors`.
2. **`backend/api/prometheus_provider_factory.py`** — composition-root factory on
   the `CORTEX_CONNECTOR_FACTORIES` seam (comma-separated, so Kubernetes and
   Prometheus compose together — verified at `application_runtime.py:303-318`),
   env-gated, `DevelopmentCredentialProvider`.
3. **`backend/api/observability_evidence.py`** — the deployment's declared
   **policy set** for this vertical (lineage, authority, freshness rules mapping
   `source_ref` → origin/tier/horizon) plus the metric-record → `ObservationLeg`
   mapper. Policies are configuration and belong in the composition layer.
4. **`scripts/phase94_provision.sh`** — k3d + kube-state-metrics + a real
   Prometheus scraping it + the bearer proxy + fresh Postgres.
5. **`scripts/phase94_observability_harness.py`** — requirements A–W.
6. **`tests/intelligence/test_observability_corroboration.py`** — unit evidence.
7. Docs: ADR-084, verification report, this map, memory addendum.

---

## 13. Stop-condition review

| # | Condition | Status |
|---|---|---|
| 1 | second transport architecture | **No** — Prometheus is conventional request/response HTTP |
| 2 | Intelligence must access a provider directly | **No** — `EvidenceAcquisitionPort` already exists and is gate-enforced |
| 3 | World must access a provider directly | **No** — `BND-WORLD-CANNOT-EXECUTE` |
| 4 | lineage cannot be represented honestly | **No** — `source_ref` per instrument + `LineagePolicy`; the Prometheus/K8s correlation is representable and *is* the demonstration |
| 5 | timestamps cannot be preserved without fabrication | **No** — real provider timestamps; the instant-query limitation is classified (§8), not hidden |
| 6 | tenant isolation cannot be guaranteed | **No** — governed context only |
| 7 | evidence requires model-generated facts | **No** — no model anywhere in this path |
| 8 | corroboration requires numeric weights | **No** — the existing engine is categorical |
| 9 | new authority system needed | **No** — `AuthorityPolicy` reused |
| 10 | second RAG/world store needed | **No** — §11 |
| 11 | existing invariants must be weakened | **No** — nothing widens; §6 uses a mechanism Phase 9.3 already added |
| 12 | success only demonstrable via a disguised scripted provider | **No** — real Prometheus, real kube-state-metrics, real samples |

**No stop condition fires. Proceeding to implementation.**
