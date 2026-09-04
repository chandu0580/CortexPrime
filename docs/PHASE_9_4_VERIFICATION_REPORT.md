# PHASE 9.4 — Verification Report

**Observability corroboration and multi-source world evidence.** Every claim is
labelled `[VERIFIED]` (a run proved it), `[FACT]` (declared in code, cited),
`[NOT VERIFIED]`, `[DEFERRED]` or `[BLOCKED]`. Code existing is never a reason to
write `[VERIFIED]`.

## Honesty header — read this before the table

- `[VERIFIED]` **Two real providers, one real cluster, real numbers.** A real k3d
  cluster (k3s v1.35.5) running a real deliberately-crashlooping workload, a real
  kube-state-metrics scraping that cluster's API server, a real Prometheus v2.52.0
  scraping kube-state-metrics, behind a real bearer-token proxy. Nothing in the
  decisive path is scripted.
- `[VERIFIED]` **The decisive result is a refusal.** Both providers reported
  `restartCount: 7` for the same pod, and the platform answered **CORRELATED —
  not independent**, naming `kubernetes-cluster` as the shared origin. That is
  the phase: refusing to manufacture confidence out of one fact counted twice.
- `[FACT]` **No arbitrary PromQL exists.** The governed Prometheus operations
  declare **zero parameters**. There is no field a model could compose a query
  with; the query is a constant of the operation and is in its digest.
- `[FACT]` **No numeric confidence anywhere.** Corroboration is categorical with
  a stated reason. This was asserted, not assumed (`no numeric confidence score
  appears anywhere in the assessment`).
- `[FACT]` **Phase 5.5 remains `[BLOCKED]` and untouched.** Both credentials are
  disposable, local, 2-hour or fixed dev tokens entering once at the composition
  root.
- `[FACT]` **Nothing was interpreted.** The shared proposition is a restart
  count, which both instruments literally report. "This pod is unhealthy" is not
  derived anywhere.

## Evidence environment

| Item | Value |
|---|---|
| Cluster | k3d `cortex-p94`, k3s **v1.35.5+k3s1**, disposable |
| Workload | `flapper` — a container that exits 1 every 12s, so restart counts are real and moving |
| Derived instrument | **kube-state-metrics v2.13.0**, in-cluster, scraping the API server |
| Metrics store | **Prometheus v2.52.0**, host container, 5s scrape of kube-state-metrics |
| Prometheus auth | **nginx bearer proxy** — verified `no token → 401`, `token → 200` |
| Kubernetes auth | ServiceAccount token, `get/list/watch pods` in one namespace; `delete pods → no` |
| TLS | Kubernetes verified against the cluster CA; Prometheus plaintext loopback behind the proxy, under the stated Grafana-precedent policy exception |
| Database | Postgres 16 (pgvector), `cortex_p94`, **dropped and recreated per run**, migrated to head |
| Capabilities | `kubernetes.pods.list`, `prometheus.pod_restarts`, `prometheus.self_build_info` |
| Provisioning | `scripts/phase94_provision.sh` (also tears down) |
| Harness | `scripts/phase94_observability_harness.py` |

## Verdict

| Gate | Result |
|---|---|
| Phase 9.4 real harness | **VERIFIED — 92/92**, exit 0 |
| Phase 9.4 unit tests | **43/43 passed** |
| Architecture fitness gate | **PASS — 35 passed, 0 failed**, 1178 modules |
| Regression (affected areas) | §9 |
| New fitness rule | **none** — deliberately (§7) |
| New table / migration | **none** |

---

## 1. Requirements A–W

| # | Requirement | Result | Evidence |
|---|---|---|---|
| A | governed observability READ | `[VERIFIED]` | real Prometheus read SUCCEEDED through the governed path |
| B | exactly one provider call | `[VERIFIED]` | `dials_by_provider = {kubernetes: 1, prometheus: 1}` |
| C | Observation persisted | `[VERIFIED]` | metric observations durable, each naming its instrument |
| D | provider timestamps preserved | `[VERIFIED]` | `observed_at` **is** Prometheus's sample timestamp (drift < 1s), distinct from `recorded_at`, never in the future |
| E | tenant isolation | `[VERIFIED]` | cross-tenant subject count 0; cross-tenant list empty; no tenant taken from a label or namespace |
| F | secret firewall | `[VERIFIED]` | a **nested** credential-shaped metric label refused at ingestion; neither provider token in any durable row of any table; no token in the World evidence view |
| G | WorldQuery retrieves observability evidence | `[VERIFIED]` | value returned with authority and freshness overlays |
| H | freshness policy | `[VERIFIED]` | FRESH by stated horizon; STALE after 6h **with the value still present**; UNKNOWN where no rule governs |
| I | authority policy | `[VERIFIED]` | K8s API AUTHORITATIVE, its re-export SINGLE_SOURCE, unmapped UNVERIFIED, and the API outranks its own re-export |
| J | lineage classification | `[VERIFIED]` | all four instruments classified (§2) |
| K | same lineage → CORRELATED | `[VERIFIED]` | **the decisive claim** (§3) |
| L | unknown lineage → INDETERMINATE | `[VERIFIED]` | reason says independence is *unproven*, not disproven |
| M | distinct known origins → INDEPENDENT | `[VERIFIED]` | both origins named |
| N | disagreement → CONFLICTED | `[VERIFIED]` | CONTRADICTED, evidence preserved, not AFFIRMED |
| O | corroborated proposition | `[VERIFIED]` | §3 |
| P | contradictory proposition | `[VERIFIED]` | §3 |
| Q | Investigation consumes via WorldQuery | `[VERIFIED]` | the **production** `WorldQueryEvidencePort` returned the evidence with **zero provider calls** |
| R | Investigation never contacts a provider | `[VERIFIED]` | no Intelligence module imports a connector, provider adapter or HTTP client; gate-enforced |
| S | replay inert | `[VERIFIED]` | zero provider reads, zero observations, zero facts, zero audit records |
| T | crash recovery | `[VERIFIED]` | 5 real `os._exit(9)` points; no observation lost; every surviving value still attributed to a real source |
| U | multi-process | `[VERIFIED]` | two real OS processes; first acquired, second **refused**; no observability-specific election |
| V | audit chain valid | `[VERIFIED]` | 0 defects |
| W | deterministic reconstruction | `[VERIFIED]` | re-deriving every observation is entirely `DEDUPED`; re-forming the belief yields the same verdict |

## 2. Lineage — all six cases, against real instruments `[VERIFIED]`

| Case | Instrument | Origin | Relation |
|---|---|---|---|
| **A** | `connector:kubernetes` | `kubernetes-cluster` | `DIRECT` |
| **C** | `prometheus:kube-state-metrics` | `kubernetes-cluster` | **`DERIVED`** |
| **B** | `prometheus:self` | `prometheus-server` | `DIRECT` |
| **D** | `connector:unheard-of` | `None` | `UNKNOWN` |

## 3. The decisive demonstration `[VERIFIED]`

**Both providers reported the same real number:**

```
k8s = {'restartCount': 7}    prometheus = {'restartCount': 7}
```

**And the platform refused to call that independent corroboration:**

```
level               = correlated
independent_sources = ['connector:kubernetes', 'prometheus:kube-state-metrics']
independent_origins = ['kubernetes-cluster']          # ONE, not two
reason              = "2 sources agree but share lineage origin
                       'kubernetes-cluster' — correlated, not independent"
supporting          = both, preserved
```

The other three verdicts, over the same declared policy:

| Scenario | Verdict |
|---|---|
| `connector:kubernetes` + `prometheus:self` agreeing | **`independent`**, origins `['kubernetes-cluster', 'prometheus-server']` |
| two unmapped instruments agreeing | **`indeterminate`** — "independence is unproven… false certainty is worse than insufficient evidence" |
| equal-authority distinct origins disagreeing | **`contradicted`** — evidence preserved, status not AFFIRMED |

## 4. Time semantics `[VERIFIED]` / `[FACT]`

- `[VERIFIED]` `observed_at` is Prometheus's own sample timestamp (drift from the
  provider value < 1s), distinct from `recorded_at`, and never in the future.
- `[FACT]` **Stated limitation:** for `/api/v1/query` that timestamp is the
  *evaluation* instant, not the scrape instant. Prometheus resolves each series
  to the most recent sample within its lookback delta (5m default), so the
  underlying sample may be older than the timestamp returned. The metric
  freshness horizon (120s) is set with this in mind. This is real Prometheus
  semantics, classified rather than claimed away.
- `[VERIFIED]` **Two clocks, reconciled explicitly.** A provider container whose
  clock runs ahead produced `observed_at > retrieved_at`, which the temporal
  contract refuses — correctly. The resolution keeps `observed_at` exactly as the
  provider stated and advances `retrieved_at` to meet it; skew beyond a declared
  bound is refused outright. The skew is **not** written into the value, because
  the value is the proposition and must be byte-identical across instruments or
  corroboration reads agreement as contradiction.

## 5. Governance and the absent attack surface `[VERIFIED]`

- `[VERIFIED]` Both governed providers compose in one process through the
  existing comma-separated factory seam; no second gateway, executor, scheduler,
  credential system or audit chain.
- `[VERIFIED]` **Every Prometheus operation declares zero parameters.** There is
  no PromQL-injection surface to close because there is no input field at all.
  A caller supplying `query` is refused before a request is built.
- `[VERIFIED]` The declared query is in the digest: changing it changes the
  operation's identity.
- `[VERIFIED]` The catalog is scoped to one namespace at construction, and a
  namespace containing characters that could close the label matcher is refused.
- `[VERIFIED]` The V1 observability connectors were never imported.
- `[VERIFIED]` Negative legs — bad token, unreachable server — each **failed**
  and recorded **zero observations**.

## 6. What was reused rather than rebuilt `[FACT]`

The corroboration engine, lineage model, freshness policy, authority policy,
observation ledger, fact derivation, `WorldQuery`, the whole
execution/governance/credential/audit fabric, and the leadership role were
**already built and already correct**. Discovery's central finding was that Phase
9.4 is not "add Prometheus" but "produce a real second source with honest lineage
and prove the existing engine against it".

Genuinely new: the governed Prometheus catalog, the deployment's declared policy
set, the proposition mapper, per-pod record evidence on `pods.list`, and
`WorldQueryEvidencePort` — a production adapter for a port that had been declared
with no implementation behind it since Phase 8 (every phase satisfied it inside
its own harness).

**No new table, no migration, no World store, no RAG, no vector or graph
database, no second authority.** Lineage, authority and freshness are computed
from policy at query time, so there is nothing new to persist.

## 7. Architecture fitness `[VERIFIED]`

**PASS — 35 passed, 0 failed, 6 skipped, across 1178 modules.**

`BND-INTELLIGENCE-CANNOT-DIRECT-OBSERVABILITY` was considered and **not added**,
because it would be cosmetic. Four existing ERROR rules already make it
impossible, and all four passed:

- `BND-INTELLIGENCE-CANNOT-EXECUTE` — the Intelligence Plane imports no
  connector, execution, transport or credential carrier.
- `BND-INTELLIGENCE-CANNOT-BYPASS-WORLD` — it consumes evidence only through the
  World application layer / read ports.
- `BND-WORLD-CANNOT-EXECUTE` — the World Plane cannot reach a provider at all.
- `BND-DIRECT-HTTP` / `BND-PROVIDER-SDK` — no second HTTP client, no provider SDK.

## 8. Performance — measured, not speculated `[VERIFIED]`

| Measurement | Value |
|---|---|
| Prometheus read latency (governed, end to end) | **488 ms** |
| Kubernetes read latency (governed, end to end) | **520 ms** |
| WorldQuery latency | **33 ms** |
| Corroboration latency | **53 ms** |
| Observation ingest p50 / p95 | **13.7 ms / 30.0 ms** |
| Total provider dials, whole run | **2** (one per provider) |

No index and no infrastructure was added: nothing in these numbers asked for one.

## 9. Regression `[VERIFIED]` / `[FACT]`

- `[VERIFIED]` Phase 9.4 unit tests: **43/43**.
- `[VERIFIED]` Affected areas (`tests/intelligence`, `tests/contexts/execution`,
  `tests/world`, `tests/platform`, `tests/assurance`): **1246 passed, 1 failed**.
  The single failure is the pre-existing
  `test_dependency_isolation[credentials\inspection.py]` (*"imports disallowed
  root(s): ['base64']"*) — reproduced on clean `HEAD` with every change stashed
  during Phase 9.3, and that file is untouched by this phase.
- `[FACT]` Two Phase 9.2/9.3 assertions were updated because 9.4 legitimately
  supersedes them: `pods.list` now carries per-pod record evidence alongside its
  counts. Both were rewritten to assert the new intent — and the second was
  strengthened into a pin that record evidence stays the exception (exactly the
  watch window and the pod list), so it does not spread by habit.
- `[FACT]` `tests/benchmarks` needs a Neo4j instance and does not run in this
  environment. Pre-existing.

## 10. Honest findings

1. `[FACT]` **A moving counter legitimately produces CONTRADICTED.** The flapper
   really is restarting, so two observations taken seconds apart disagree, and
   the World Plane says so rather than picking one. The crash checks were
   rewritten to assert what actually matters — nothing fabricated, every value
   still attributed to a real source — instead of asserting a verdict that has no
   right to be stable.
2. `[FACT]` **Corroboration requires a declared shared vocabulary.** Two
   providers can only corroborate if they report the same proposition in the same
   shape, because support is decided by comparing value digests. This is stated
   in the catalog rather than inferred, and it is the single most important
   design constraint the phase discovered.
3. `[FACT]` **The declared-query approach does not scale across namespaces.** One
   operation per (metric, scope) pair. A declared, validated selector-template
   mechanism is the successor. `[DEFERRED]`, named.
4. `[FACT]` **A real bug found by a unit test:** `int(NaN)` raises, so the
   finiteness guard had to precede the whole-number guard in the metric mapper. A
   `NaN` sample would have crashed the observation leg rather than being skipped.

## 11. Explicitly NOT in this phase `[FACT]`

No embeddings, no vector database, no semantic similarity, no chunking, no Neo4j,
no "RAG confidence", no LLM-generated facts. Structured World evidence was
sufficient, and RAG remains subordinate to the World Plane until evidence shows
otherwise.

## 12. Stop conditions

| # | Condition | Status |
|---|---|---|
| 1 | second transport architecture | Not triggered — conventional HTTP |
| 2 | Intelligence must access a provider | Not triggered — gate-enforced |
| 3 | World must access a provider | Not triggered — gate-enforced |
| 4 | lineage cannot be represented honestly | Not triggered — it *is* the demonstration |
| 5 | timestamps cannot be preserved without fabrication | Not triggered — provider time preserved, limitations classified (§4) |
| 6 | tenant isolation cannot be guaranteed | Not triggered |
| 7 | evidence requires model-generated facts | Not triggered — no model in this path |
| 8 | corroboration requires numeric weights | Not triggered — categorical, asserted |
| 9 | new authority system needed | Not triggered |
| 10 | second RAG/world store needed | Not triggered |
| 11 | existing invariants must be weakened | Not triggered — nothing widened |
| 12 | success only demonstrable via a disguised scripted provider | Not triggered — everything decisive is real |

## 13. Reproducing

```bash
bash scripts/phase94_provision.sh          # k3d + kube-state-metrics + Prometheus + proxy + fresh Postgres
set -a; . ./.phase94.env; set +a
python -m scripts.phase94_observability_harness   # exit 0 = VERIFIED
bash scripts/phase94_provision.sh teardown
```
