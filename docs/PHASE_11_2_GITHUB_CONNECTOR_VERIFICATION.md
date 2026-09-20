# Phase 11.2 — GitHub connector: verification report

Decision record: `docs/adr/ADR-126-phase-11-2-github-connector.md`. Architecture:
`docs/CONNECTOR_ARCHITECTURE.md`. Operator guide:
`docs/GITHUB_CONNECTOR_RUNBOOK.md`. Machine-readable evidence:
`docs/phase112_github_connector_report.json`.

> **On the number.** This is 11.2 of the *connector* program (11.1 was the
> Kubernetes reference connector, ADR-125). An earlier 11.2 — the signal fabric,
> ADR-122, `docs/phase112_signal_report.json` — is a different phase under the
> earlier roadmap numbering. Neither file nor ADR collides; the number does.

Every claim is marked **FACT** (observed in this phase, evidence named),
**INFERENCE** (reasoned from facts) or **UNKNOWN** (not established here). This
is one connector proven against one real GitHub account, once per scenario.

**At a glance.** Record run **81/81 VERIFIED** against `chandu0580/CortexPrime`
(2026-09-20, 1442 s, ten stages). Deterministic suites **778 passed, 0 failed**.
One real governed write (issue comment 5749368868), independently verified
byte-for-byte. Sixteen negative cases, **0 GitHub writes**. Verdict:
**GITHUB: NOT LOCKED** — one blocker, the GitHub App credential is implemented
and deterministically tested but never authenticated against api.github.com
(section 25).

---

## 1. Research

**FACT.** Against GitHub's official documentation (not blog posts):

| Question | What the documentation says | Where it shows up here |
|---|---|---|
| App installation auth | JWT signed **RS256**, `iss` = App id, `exp` ≤ 10 minutes, `iat` backdated 60 s for clock drift; `POST /app/installations/{id}/access_tokens` returns a token that **expires in 1 hour** and may be restricted with `repositories` and `permissions` | `backend/api/github_credentials.py` |
| Primary rate limits | 5,000 req/hour for a user token and for an App installation (more on Enterprise); headers `x-ratelimit-limit/remaining/used/reset/resource`; exceeding returns **403 or 429** | error classification + worker rate facts |
| Secondary limits | separate from the hourly budget (concurrency, points/minute, content creation); honour `retry-after`, else `x-ratelimit-reset`, else wait ≥ 1 minute, then exponential backoff | `SECONDARY_RATE_LIMITED` error class |
| Pagination | `per_page` ≤ 100; `link` header with `rel="next"/"prev"/"first"/"last"`; some endpoints answer with an object instead of an array | bounded `per_page` parameter; the normalizer handles both shapes |
| Webhooks | `X-Hub-Signature-256`, HMAC-SHA256 over the raw body, compared in constant time | **deferred** (section 24) |
| Issue comments | `POST /repos/{owner}/{repo}/issues/{issue_number}/comments`, body `body`, **201**, fine-grained permission `issues:write`, works for pull requests; 403 / 404 / 410 / 422 documented | the one write capability |
| 404 semantics | GitHub answers 404 for a private resource a credential may not see, deliberately | health reports it as MISCONFIGURED naming the repository, and does not guess |

**FACT.** Repository reality check (mandate §3), before any implementation:
`/api/git/*` (S-1) remains gated; V1 GitHub writes (`create_issue`,
`update_issue`, `dispatch_workflow`, `cancel_workflow_run`, `rerun_workflow`,
`create_branch`, `create_pull_request`, `merge_pull_request`) are refused by
`assert_effect_permitted` without the legacy flag, and raw non-GET requests by
`guard_raw_request`; `POST /api/github/sync` is a **read** behind
`require_user`; and the deployed governed image does not mount the V1 router at
all. Proven by `tests/connector_fabric/test_github_credentials.py` and by the
record run.

---

## 2. GitHub architecture

**FACT.** The Kubernetes architecture, unchanged:

```
GitHub  ←  github (in-process reads)      ─┐
        ←  github-contained (write worker) ─┤
                                            ├─ connection scope (tenant ↔ owner/repo)
                                            ├─ capability fabric (one gateway)
                                            ├─ governance (authorization, approval)
                                            ├─ execution (contained worker)
                                            └─ independent verification
```

One `CORTEX_CONNECTOR_FACTORIES` entry
(`backend.api.github_connector:github_connector_extension`) produces adapters,
one manifest, one connection scope, credential builders and a health probe. No
new connector model, governance path, execution path or verification path.

---

## 3. Authentication

**FACT.** Production is a **GitHub App installation token**: a JWT (RS256, 540-second
window, `iat` backdated 60 s, `iss` = App id) signed with a private key held in
Vault KV, exchanged for an installation token scoped at mint time to the
connected repositories and to exactly the permissions the shipped capabilities
declare, cached until 80 % of its hour, and dropped immediately when GitHub
refuses it. **UNKNOWN (live):** this account has no GitHub App, so the App path
is proven deterministically (`tests/connector_fabric/test_github_credentials.py`,
including a real RSA key and a scripted GitHub) and **not** against
api.github.com.

**FACT.** The live path is the development one: a token in **Vault KV** under
`cortexprime/providers/<tenant>/<environment>/<provider>`, read through the same
broker, never in an environment variable. Production **refuses** it
(`ContractViolation`, tested), which is why the live deployment runs in
`staging`.

---

## 4. Connection scope

**FACT.** `ConnectionScope(tenant, providers, repositories, target_parameters=("owner","repo"))`.
A GitHub organization is not a tenant. Enforced three times independently: the
gateway input stage, the credential (minted for named repositories), and the
worker's compiled binding. Case-insensitive, because GitHub's own resolution is.
A half-named target (`repo` without `owner`) is refused, not ignored.

---

## 5. Capabilities

**FACT.** Ten, and no others:

| Capability | Effect | Risk | Retry | Verification | Provider | GitHub permission |
|---|---|---|---|---|---|---|
| `repository.get_repository` | read | low | safe | none | github | `metadata:read` |
| `repository.list_commits` | read | low | safe | none | github | `contents:read` |
| `repository.get_commit` | read | low | safe | none | github | `contents:read` |
| `repository.list_pull_requests` | read | low | safe | none | github | `pull_requests:read` |
| `repository.get_pull_request` | read | low | safe | none | github | `pull_requests:read` |
| `repository.list_workflow_runs` | read | low | safe | none | github | `actions:read` |
| `repository.get_workflow_run` | read | low | safe | none | github | `actions:read` |
| `repository.list_deployments` | read | low | safe | none | github | `deployments:read` |
| `repository.get_issue` | read | low | safe | none | github | `issues:read` |
| `repository.create_issue_comment` | **irreversible write** | medium | **never** | independent readback | github-contained | `issues:write` |

**FACT.** `create_issue` exists in the catalog and is **not shipped**. There is
no file read, code search, workflow dispatch, merge, push or arbitrary request.

**FACT.** Responses are normalized to bounded, high-signal facts (sha, author
login, authored time, first line of the message, files changed, additions,
deletions, base/head branch, head sha, status, conclusion, environment), never a
raw GitHub payload. A field GitHub did not send stays missing.

---

## 6. Capability Fabric integration

**FACT.** Commissioned at boot by the generic registrar: register → validate →
enable → trust, idempotently, refusing contract drift. The product API publishes
each capability's contract (description, input schema, permissions, risk, retry
class, timeout, verification requirement) at `GET /api/v1/connectors/github`.

---

## 7. Governance

**FACT.** Every invocation passes the one gateway. The write requires a human
approval bound to the action digest; the model (or any caller) can only name a
registered capability with validated arguments.

---

## 8. Execution

**FACT.** Reads run in-process (AMBIENT, read-only). The write runs in a
**contained worker**: its own container, non-root, read-only root filesystem, no
Kubernetes permission at all, no automounted token, no standing credential
(the platform presents the GitHub token per action as the request's
authorization header), egress restricted to HTTPS on the public internet and
DNS — never into the cluster.

---

## 9. Verification

**FACT.** The comment is verified three ways, none of them the worker's word:
the harness reads GitHub directly and finds the comment id the worker reported;
the body GitHub holds is **byte-for-byte** the body the worker composed
(sha-256 comparison); and the platform re-reads the thread through its own
governed `get_issue`. The comment also carries the action digest that produced
it, so a human reading the thread can attribute it.

---

## 10. Tenant isolation

**FACT.** Tenant B sees the connector as DISABLED with no detail about A's
repository, owner or tenant id; a B member presenting A's tenant claim is
refused (403); tenant A is refused for a repository **the same credential can
read** (proven by reading it directly), so the refusal is the platform's, not
GitHub's.

---

## 11. Security

**FACT (record run, SECURITY stage, 12/12).**

- **Repository content is data.** An issue comment carrying an instruction is
  returned as bounded evidence — `author_login`, `state`, `title`, `comments`,
  timestamps — and its text is not carried into any field a capability reads.
  Nothing a repository contains can name a capability, supply an argument, or
  grant an authority.
- **Argument injection** (4 cases): `../` traversal in `repo`, a full URL in
  `owner`, query smuggling, and a second target appended — each refused at input
  validation / connection scope, and the transport node **recorded no attempt**:
  no GitHub request left the process.
- **Alternate routes** (6 cases): V1 `create_issue`, `create_issue_comment`,
  `dispatch_workflow`, `merge_pull_request` and a raw non-GET are each refused
  by the legacy execution boundary; and the deployed governed image answers
  `POST /api/github/sync` with **404** — it does not mount the V1 router at all.
- **0 GitHub writes** across all 16 negative cases (machine-readable in the
  report's `negative_matrix`).

**FACT.** A credential appears nowhere a human or a model can read it: not in
the runtime's environment or ConfigMap, not in the worker's environment (which
holds only its bindings), not in either log, not in a metric label, not in the
durable store, and not in the evidence this report links.

**INFERENCE.** The prompt-injection defence rests on structure — a model can
only name a registered capability with schema-validated arguments — not on
detecting malicious text. That is the stronger property, but it was tested with
one crafted comment, not a corpus.

---

## 12. Rate limiting

**FACT.** The gateway's token-bucket limiter (11.1-K) applies to GitHub
unchanged. GitHub's own semantics are translated in its module: a 403 carrying
`x-ratelimit-remaining: 0` or an "abuse detection" message is classified
RATE_LIMITED rather than a permissions problem; a secondary limit has its own
class; the worker returns the rate-limit headers as facts with every write.
Retry honours a provider `Retry-After` as a floor, and writes are never retried.

**UNKNOWN.** A real GitHub 429/secondary limit was **not** provoked (it would
need thousands of requests against the operator's own account); rate-limit
behaviour is proven deterministically and by header capture, not by exhaustion.

---

## 13. Error handling

**FACT.** Fourteen classes, including the two this phase added
(`SECONDARY_RATE_LIMITED`, `VALIDATION_FAILED`). GitHub's dialect is translated
where it departs from convention (403-as-rate-limit, 404-as-hidden). Provider
messages are bounded and sanitized; no response body reaches a log unbounded.

---

## 14. Observability

**FACT.** `cortex_connector_health{connector,state}` is exported for both
connectors (8 series), beside the gateway and transport metrics on
`CORTEX_METRICS_PORT`. No metric carries a credential-like label or value
(checked against the live scrape).

**FACT.** Health is produced **through the governed path**: `CONNECTED` means
every connected repository was read, just now, with this connection's own
credential. A failure names the check — `chandu0580/CortexPrime ->
authentication_failed: Bad credentials` — rather than a state alone.

**UNKNOWN.** There is no per-capability latency or error-rate dashboard for
GitHub specifically; what exists is the shared gateway instrumentation.

---

## 15. Audit

**FACT.** Governed GitHub work lands in the durable, hash-chained audit store
(`cp_audit_record`, one chain), not in the V1 `audit_logs` table (0 rows). The
kinds recorded in this run: `connector_operation` 1453, `identity_event` 662,
`execution_succeeded` 602, `execution_failed` 42, `execution_refused` 15,
`policy_evaluated` 3.

**FACT.** A refusal is audited as deliberately as a success: each of the 16
negative cases is recorded with what refused it. The write carries its approval
digest, its approver, the worker identity and the independent verification
result, so "who approved this comment, and did it actually appear" is answerable
from the record alone.

---

## 16. Deployment

**FACT.** The same chart, one flag: `github.enabled=true` plus the repositories,
the installation id (App mode) and the worker digest. The chart creates the
worker, its service, its TLS certificate (signed by the **same** worker CA, kept
across upgrades) and its egress policy, and refuses to render without a pinned
worker digest or without repositories. One operator script
(`scripts/connector/configure_vault_github.sh`) grants the runtime read access
to exactly this tenant's GitHub credential paths.

---

## 17. Deterministic tests

**FACT.** `tests/connector_fabric tests/connectors tests/contexts/execution
tests/architecture` — **778 passed, 0 failed** (331 s), of which **88** are the
two new GitHub files:

| File | Tests | What it pins |
|---|---|---|
| `tests/connector_fabric/test_github_connector.py` | 52 | catalog and manifest shape, the ten shipped capabilities and the unshipped one, permissions per capability, normalizer (both response shapes, missing fields, bounded evidence), connection scope (composite, case, partial), health states, error translation, the worker's bindings and attribution |
| `tests/connector_fabric/test_github_credentials.py` | 36 | App JWT (RS256, `iat`/`exp`/`iss`) against a real RSA key, installation-token exchange with `repositories` + `permissions`, caching to 80 %, invalidation on refusal, Vault KV read, stale-login retry, production's refusal of a stored token, and that the V1 GitHub plane cannot write |

**FACT.** The architecture guard derives the gated sites from
`ConnectorEffectGateRule.gate_sites` rather than a hand-written list, so a new
ungated execution site fails the suite instead of passing unnoticed.

**FACT (wider regression).** `tests/connector_fabric tests/connectors
tests/contexts tests/architecture tests/platform tests/contracts
tests/deployment tests/signal` — **3351 passed, 1 failed** (412 s). The single
failure is **pre-existing and unrelated**:
`test_dependency_isolation.py::test_imports_only_approved_roots[credentials\inspection.py]`
— `backend/platform/credentials/inspection.py` imports `base64` (legitimately,
to decode a base64 payload while looking for secret-shaped material) and the
guard's `APPROVED_STDLIB` does not list it. Both files are byte-identical to
`HEAD` and were last touched in Phase 7.2 / 6.2; nothing in this phase imports
or edits them. It is reported rather than fixed, because the fix is to widen a
security guard's allow-list, which is not this phase's to change.

---

## 18. Real GitHub tests

**FACT.** One record run, `scripts/phase112_github_connector_harness.py`, ten
stages, **81/81 checks passed, verdict VERIFIED**, 1442 s wall clock, against
**chandu0580/CortexPrime** on a real k3d cluster with a real Vault, through the
Helm-installed product.

| Stage | Checks | What it established |
|---|---|---|
| INSTALL | 5 | Vault holds the credential for both providers under the tenant's path; one operator script; `helm upgrade --install --wait` brings up runtime + worker + service + egress policy in 12.9 s |
| CONNECT | 6 | health `CONNECTED` (10 capabilities available) read through the product API as the connection's tenant; all 10 commissioned at boot with zero conflicts; every capability publishes its full contract; no arbitrary-request capability exists; GitHub sits beside Kubernetes, each with its own state |
| CREDS | 6 | no GitHub token in the runtime environment, ConfigMap or log; the worker holds only bindings, mounts no service-account token, has no Kubernetes permission |
| TENANCY | 7 | tenant B reads DISABLED and learns nothing; B's member with A's claim gets 403; a repository outside the connection is refused **although the same token can read it** (proven by a direct 200) |
| READS | 12 | every shipped read against the real repository through the governed path, with normalized evidence |
| WRITE | 16 | one real governed comment, end to end (section 9) |
| SECURITY | 12 | section 11 |
| FAILURES | 7 | section 20 |
| OBSERVE | 10 | sections 14 and 15 |
| EVALUATE | 2 | section 21 |

**FACT (reads).** Real facts, not shapes: repository `1304831979`
`chandu0580/CortexPrime`, public, default branch `main`; 5 commits with sha,
author and subject; commit `cea4345` with its files and per-file
additions/deletions; 5 pull requests (e.g. #15 "Bump js-yaml from 4.1.1 to
4.3.2 in /frontend", base `main`); workflow runs out of a real
`total_count: 141` (run `34856215965`, "Security Scan", schedule, completed);
3 deployments. `get_issue` is exercised in the WRITE stage's platform-side
verification. The whole read evidence set is **2,076 bytes** — bounded, not raw
payloads.

**FACT (write).** Issue #21 in the real repository; approval
`appr-p112-1789901943` bound to digest `7efbeaa6d205407c...`; approved through
`POST /api/v1/approvals/{id}/decision` by the scoped approver; executed by the
contained worker; GitHub returned **201**; comment id **5749368868** at
`https://github.com/chandu0580/CortexPrime/issues/21#issuecomment-5749368868`;
the comment count on that issue went **0 to 1**; the body GitHub holds hashes to
`465cdc7f47395ee6...`, the body the worker composed; the comment carries action
marker `a5dfab95ee12d2cf`. 53.1 s from approval to executed. The harness closed
issue #21 afterwards.

---

## 19. Security tests

See section 11. Sixteen negative cases, **0 GitHub writes**, each recorded with
the layer that refused it.

**FACT, stated precisely.** Two entries in the matrix are refused *earlier* than
their name suggests: the write aimed at an out-of-scope repository, and the
injected-argument writes, are stopped by **authorization (approval required)**
before the connection-scope check is reached. They are genuinely stopped and no
request is attempted — but the evidence for those entries proves the approval
gate, not the scope gate. The scope gate is proven independently, three times:
on the read path against a repository the same credential can read (TENANCY),
in the worker's compiled binding, and deterministically
(`test_github_connector.py`).

---

## 20. Failure tests

**FACT.** Two injections, each named by health and each recovered, with no
restart:

| Injection | Health became | Detail it gave | Recovered |
|---|---|---|---|
| GitHub credential replaced with an invalid one | `AUTHENTICATION_REQUIRED` | `chandu0580/CortexPrime -> authentication_failed: Bad credentials` (commissioning still ok) | yes — `CONNECTED` again, and the connection read its repository |
| contained GitHub worker scaled to zero | `DEGRADED` | `create_issue_comment: worker unreachable: not delivered`; reads stayed available | yes |

**FACT.** Two deployment failures are refused at render time, each naming the
value: a worker with no pinned digest, and a connection with no repositories
("a connection to 'whatever the token can see' is not a connection").

---

## 21. Evaluation

**FACT.** The reusable suite (`backend/api/connector_evaluation.py`), run
against GitHub from this run's own evidence:

- **Contract evaluation:** 10 capabilities, **passed, zero findings**.
- **Behavioural evaluation:** all seven questions **PASS** with no missing
  evidence — select, arguments, governance, authorized execution, verification,
  recovery, explain.

**FACT.** The suite is provider-neutral: it is the same code that evaluated
Kubernetes in 11.1-K. One rule was corrected this phase (`FORBIDDEN_VERBS` now
matches verbs rather than substrings, so `pull_request` is no longer read as a
forbidden `pull`).

**INFERENCE.** A PASS here means the evidence for that question exists in a real
run, not that the behaviour is optimal.

---

## 22. UX and complexity

**FACT.** What an operator does: store a credential in Vault, run one script,
set `github.enabled=true` with the repositories. What they read: one line per
connector with a state, and — when it is not CONNECTED — the exact permission,
credential or endpoint to fix. What they never see: GitHub API URLs, pagination,
token exchange, JWT lifetimes, catalogs or digests.

**FACT.** What an agent sees: ten typed capabilities with names that say what
they do (`github.list_commits`, not `github_api`), explicit parameters (`owner`,
`repo`, `commit_sha`, `workflow_run_id`), and responses that are already the
facts an investigation needs. **INFERENCE:** this is better tool ergonomics than
a raw API surface; it was not measured against alternative phrasings.

---

## 23. Reusable improvements

**FACT.** Four provider-neutral extensions, all used by Kubernetes too:
composite connection targets; the `PERMISSION_DENIED` health state; two error
classes; and `platform.credentials.http_json` (one JSON-over-broker call shared
by the Vault and GitHub App adapters). Plus `REQUIRED_ARGUMENTS` on the
contained-worker adapter, so the argument check belongs to the operation rather
than to Kubernetes.

---

## 24. Known limitations

Stated, not implied.

1. **The GitHub App path is not live-proven.** It is implemented and covered by
   36 deterministic tests including a real RSA signature, but this account has
   no GitHub App, so the live run used the Vault-stored token in `staging` —
   which production refuses. **This is the blocker in section 25.**
2. **No webhooks.** Deliberately deferred (the mandate permits an explicit
   deferral): an ingestion path that cannot verify `X-Hub-Signature-256` is
   worse than none, and that verification belongs with the App credential in 1.
3. **A governed execution is dispatched only by the process holding the
   scheduler role**, and that process drives only executions it started itself
   (ADR-126 F-3). Every governed caller today lives in that process, so nothing
   is broken; but a product API route, an MCP server or a second replica cannot
   invoke a capability until this is addressed. The harness works around it by
   executing beside the runtime, which is why this is reported as a platform
   limitation rather than a harness detail.
4. **Rate limiting is not proven by exhaustion** (section 12).
5. **One connection per deployment**, and the rate limiter is per process.
6. **`create_issue` is written but not shipped**, so the "GitHub write" claim
   covers exactly one operation: a comment on an existing thread.
7. **Scale**: one repository, one account, one run per scenario. Nothing here
   establishes behaviour at organization scale, across many repositories, or
   under concurrency.
8. **The approval-consumption step is performed by the caller**, as the product
   route does; the writer path does not consume it itself (ADR-126 F-6). Replay
   is nonetheless refused, which the run proves.

---

## 25. LOCK decision

### GITHUB: NOT LOCKED

Every item in the mandate's completion gate is proven **except one**, and that
item is production authentication — which is not a detail.

**What is proven (real, this run):** real GitHub authentication through Vault;
every shipped read against a real repository with normalized evidence; one real
governed write with a human approval bound to its digest, executed by a
contained worker holding no standing credential, verified independently and
byte-for-byte; tenant isolation proven against a repository the same credential
can read; 16 negative cases at 0 GitHub writes; failures named and recovered;
audit, metrics and secret hygiene; the same chart, the same governance, the same
verification as Kubernetes. 81/81 live, 778/778 deterministic.

**The blocker:** the production credential — a GitHub App installation token —
has never authenticated against api.github.com. The operator chose to verify
with the existing classic PAT, which the code itself refuses in `production`.
Locking on that basis would mean claiming a production auth path this phase did
not exercise, so it is not claimed.

**To lock:** create a GitHub App, install it on the target repositories, store
its id and private key in Vault, and re-run the harness with
`github.credentials=app` in `production`. No code change is expected — that path
is implemented and tested; what is missing is evidence that it works against the
real provider.
