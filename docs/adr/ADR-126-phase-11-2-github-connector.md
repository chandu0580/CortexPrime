# ADR-126 — The GitHub connector: the Kubernetes connector architecture, unchanged, carried to a software-development provider — repository-scoped connections, GitHub App installation credentials, normalized high-signal reads, and one governed comment in a contained worker

- **Status:** ACCEPTED
- **Date:** 2026-09-20
- **Phase:** 11.2 — GitHub, Connector #2
- **Parents:** `5ae80fa` — Phase 11.1-K (ADR-125, the connector architecture and its LOCK); ADR-042 (the original GitHub adapter and catalog); ADR-089/090 (contained workers, canonical approval digest); ADR-121/122/124 (trust boundary, signal fabric, governed autonomous operations)
- **Evidence:** `docs/PHASE_11_2_GITHUB_CONNECTOR_VERIFICATION.md`, `scripts/phase112_github_connector_harness.py`, `docs/phase112_github_connector_report.json`, `tests/connector_fabric/test_github_*.py`
- **Change:** no migration, no new table, no new third-party dependency, no cluster-wide RBAC, no new connector architecture. Six new capabilities in an existing catalog, one manifest, one credential adapter, one contained worker, and four small generic extensions the architecture needed to hold a second provider.

> **Numbering.** Highest used is 125; this is 126.

## Context

ADR-125 established the connector architecture and proved it on Kubernetes:
manifest → boot-time commissioning → one governed execution path → connection
scope → Vault-issued per-action credentials → health through the governed path
→ contained workers for writes → independent verification. The open question was
whether that architecture was *general* or merely fitted to infrastructure
operations. GitHub is the test: a different domain (software development), a
different credential model (App installations rather than ServiceAccount
tokens), a different resource identity (two names, not one), different error
semantics (403 for a rate limit, 404 for "you may not see this"), and content
that is written by people who are not the operator.

## Decisions

### D-1 The architecture is reused, not redesigned

The GitHub connector is the same five parts as Kubernetes
(`docs/CONNECTOR_ARCHITECTURE.md`): adapters, one `ConnectorManifest`,
connection scopes, credential-provider builders, a health probe. No new
abstraction was introduced for it, and the four generic changes it did need
(D-6) are small, provider-neutral and used by both connectors.

### D-2 Ten capabilities: nine reads that answer "what changed", one write

The reads are the ones an incident investigation discriminates on:
`list_commits`, `get_commit`, `list_pull_requests`, `get_pull_request`,
`list_workflow_runs`, `get_workflow_run`, `list_deployments`,
`get_repository`, `get_issue`. The one write is `create_issue_comment`: it adds
a message to a thread somebody already opened, it is visible, attributable and
readable back exactly. `create_issue` exists in the catalog and is deliberately
**not shipped** — opening issues is a second blast radius (new records, new
notifications, no delete) that nothing in the current use case needs. There is
no `search_code`, no `get_file`, no workflow dispatch and no arbitrary request.

### D-3 Responses are normalized to bounded, high-signal facts

GitHub nests the facts an investigation needs and answers some reads with a bare
array. A `ProviderBodyNormalizer` (the port Kubernetes already used) lifts the
declared fields — author login, authored time, first line of the message, files
changed, additions, deletions, branch, head sha, conclusion — into the flat
evidence the operation declares, and nothing else. A commit message is truncated
to its first line and bounded; a field GitHub did not send stays missing rather
than being invented.

### D-4 Production authentication is a GitHub App installation token

The runtime signs a short JWT (RS256, ≤10 minutes, `iss` = App id, `iat`
backdated 60 s per GitHub's guidance) with a private key held **in Vault**, and
exchanges it for an installation access token scoped at mint time to the
connected repositories and to exactly the permissions the shipped capabilities
declare. The token expires in an hour and is replaced at 80 % of its life. A
stored personal access token (`CORTEX_GITHUB_CREDENTIALS=vault-token`) is a
development path and is **refused in production**, because a classic PAT is
long-lived and account-wide, which is the opposite of a production connection.

### D-5 A connection binds a tenant to named repositories, enforced three times

A GitHub organization is not a tenant and an installation is not one either.
`ConnectionScope(tenant, providers, repositories)` with a **composite** target
(`owner` + `repo`) is enforced at the gateway's input stage; the credential is
minted for those repositories only; and the contained worker holds its own
compiled repository binding. Any one of the three refuses a cross-repository
call, and the comparison is case-insensitive because GitHub's is.

### D-6 The smallest generic extensions, shared by both connectors

1. **Composite connection targets** (`target_parameters`): a provider whose
   resource needs two names cannot be scoped by one. A partially named target
   is refused rather than ignored.
2. **`PERMISSION_DENIED` health state**: a credential that authenticates and
   lacks a scope is a different operator action from one that expired.
3. **`SECONDARY_RATE_LIMITED` and `VALIDATION_FAILED` error classes**: GitHub
   throttles bursts separately from its hourly budget, and refuses content
   (422) distinctly from refusing a malformed request.
4. **`platform.credentials.http_json`**: the one JSON-over-broker call the
   Vault adapter already made, with the provider's name and headers as
   parameters, now shared with the GitHub App adapter.

### D-7 Repository content is evidence, never instruction

Every string this connector returns was written by somebody else, and some of it
is written by an attacker. It is bounded and truncated by the operation's
declared evidence, it never becomes a capability argument, and no capability can
be reached by anything a repository contains. The write worker refuses a
repository outside its binding regardless of what any text asked for.

## Findings

| # | Finding | Severity | Status |
|---|---|---|---|
| F-1 | A cached Vault login is not invalidated when Vault refuses it, so adding a policy to a running deployment (or restarting Vault) locked the GitHub credential out until the login expired — the 11.1-K F-9 lesson, on the generic KV path this time. Found live, by granting the GitHub policy to a running runtime. | High | **Fixed**: a `PROVIDER_REFUSED` read invalidates the login and retries once; regression tests. |
| F-2 | The chart issued no TLS certificate for a newly added worker, and regenerating the CA would have invalidated the certificates the running workers serve. | Medium | **Fixed**: the GitHub worker is signed by the same CA, and an upgrade keeps it. |
| F-3 | **A governed execution started by any process that is not the scheduler leader is never dispatched by anybody.** `ExecutionScheduler.tick` answers `not_leader`, and the leader only drives executions it tracked itself (tracking is process-local). Everything governed works today only because every caller lives inside the leader process. | High (platform, pre-existing) | **Open — documented, not fixed.** See *Consequences*. |
| F-4 | A dispatch refusal reached the caller as a bare code (`input_invalid`) without the gateway's own sentence, so "which stage refused and why" was lost. | Medium | **Fixed**: the refusal's message is carried in the dispatch detail and surfaced to the caller. |
| F-5 | A contained worker's bytes are its identity, but a CRLF checkout rewrites them and every governed write would be refused on a digest mismatch. | Medium | **Fixed**: `workers/**/worker.py text eol=lf`. |
| F-6 | An approval is marked consumed by **the caller that spends it** (as the product approval route does), not by the writer path itself, so a caller that forgets would leave a spent approval marked open. Replay is still refused — authorization re-checks the approval's state — so this is a bookkeeping gap, not an authorization hole. | Low | **Open — documented.** The live run consumes it exactly as the product route does, and proves replay refused. |

## Consequences

- GitHub is installable through the same chart and the same one-time Vault
  step, reports its own health, and performs one governed, independently
  verified write. The architecture generalized without being redesigned.
- **F-3 bounds what can be claimed.** The connector is fully usable by the
  platform's own loops (the investigator, the remediation runtime, connector
  health) because they run in the leader process. It is **not** usable from a
  second replica, from a product API route, or from an MCP server without
  either running in that process or fixing the dispatch path — and "agents
  request typed capabilities" eventually means exactly that. The live proof in
  this phase therefore runs each dispatching call as a one-shot instance of the
  same image and configuration, holding the scheduler role, rather than
  pretending a follower can execute.
- Stated limits: one GitHub connection per deployment; no webhooks (deferred
  deliberately, §15 of the mandate — unsigned ingestion is worse than none);
  no GitHub App live proof in this phase (the available credential is a classic
  PAT, so the App path is deterministic-only); the rate limiter is per process.
