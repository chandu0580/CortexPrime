# ADR-058 — V1 Execution Strangler and Runtime Boundary

**Status:** Accepted
**Date:** 2026-08-11
**Phase:** 5.15
**Relates to:** ADR-057 (application composition), ADR-056 (production audit authority), ADR-041 (transport fabric), ADR-040 (credential fabric), ADR-038 (the legacy execution flag this extends)
**Does not complete:** Phase 5.5, independently blocked on `credential_unavailable`.

---

## The question

Can the real application stop depending on V1 execution/mission
infrastructure and ambient connector credentials while the governed runtime
remains the sole authoritative execution path? **Yes — by quarantine and by
composition, not yet by migration.** No V1 caller could be *migrated* in this
phase, because migration requires capability declarations that do not exist
(see "the missing contract" below). Every V1 execution surface is now behind
one explicit boundary instead, and no provider credential is ambient.

## V1 execution inventory

The Phase 3.3.x boundary (`backend/api/legacy_execution_boundary.py`,
`CORTEXPRIME_ENABLE_LEGACY_EXECUTION`, default-off, 503) already gated ten
HTTP surfaces. Phase 5.15 traced the mission runtimes and found its "zero
ungated" claim false. There are **three parallel V1 mission runtimes**:

* **A. The mission BC** (`backend/mission/` → `backend/execution/`): four
  hardcoded plan steps dispatched to shell/HTTP sandboxes; step names never
  match the shell allowlist, so it fails closed in practice. Its HTTP
  starter (`POST /api/missions/{id}/execute`) was ungated.
* **B. The enterprise template orchestrator**
  (`enterprise_mission_orchestrator.launch`): resolves a template's connector
  chain and invokes `getattr(connector, operation)(**params)` on the V1
  connector registry — **real writes to GitHub/Jira/ServiceNow** — with no
  tenant anywhere in the call, no capability authorization, no durable audit,
  and recovery/rollback re-invocations by the same mechanism. Reachable from
  the always-on watcher timer (watcher → autonomous mission generator →
  `launch`) and the continuous cognition loop **with no HTTP request in the
  stack** — no existing flag touched it.
* **C. The cognition mission runtime** (`mission_runtime.execute_mission`):
  drives the LLM router and autonomous browser/computer agents. Its HTTP
  starter (`POST /execute` — a router mounted unprefixed) was ungated.

V1 governance on these paths is best-effort by construction: an `Optional`
governance service registered as `None` when unavailable, evaluation
failures swallowed, guardrails disabled by a bare `except ImportError`.

## The strangler decision: quarantine, on the existing boundary

All five newly found surfaces are gated on the **same flag, same refusal**
(no second mechanism): the three HTTP routes via the existing
`guard_legacy_execution` dependency, and — because path B is reached without
HTTP — a new internal twin, `guard_legacy_internal`, raising
`LegacyExecutionRefused` at `enterprise_mission_orchestrator.launch` (the
choke point for watchers, the autonomous generator, the cognition loop, and
the enterprise routes at once) and at `mission_runtime.execute_mission`. The
autonomous mission generator already contains exceptions, so under refusal
the watcher loops degrade to "mission not created", with the reason logged —
verified live. The inventory now carries 14 surfaces, `ungated_surfaces()`
is empty again, and the docstring records that its previous emptiness claim
was falsified and re-established.

**The missing contract, stated for the migration that comes next:** the
orchestrator's templates name connector operations (`github.create_issue`,
`jira.transition`, …) that have no capability declarations, no side-effect
classes, no tenant model, and no approval mapping. Migrating path B onto the
governed gateway means declaring those operations as capabilities and giving
autonomous missions a principal and a tenant — product decisions, not
refactors. Until then the flag is the honest state; setting it restores the
old behaviour deliberately and loudly. This quarantines the auto-remediation
feature by default — a deliberate, reversible product trade recorded here,
with the governed migration as the way to get it back permanently.

## Ambient credential elimination

As found: every V1 connector read its provider credential straight from the
environment inside `initialize()` (`self._token or os.getenv("GITHUB_TOKEN")`),
and `CredentialService.load()` fell back to the environment on its own. That
is why booting the application in 5.14 contacted GitHub.

Now: **eleven connectors** (github, jira, slack, teams, circleci, notion,
confluence, azure_devops, gitlab_ci, jenkins, servicenow) read only the
injected store; `CredentialService` answers only with what was explicitly
stored; and the single road in is
`backend/api/connector_credential_composition.bootstrap_connector_credentials`
— one logged composition act in the lifespan, using the same env var names
deployments already set, so behaviour under `main.py` is unchanged while
every other context (harnesses, tests, the governed runtime, bare imports)
consumes nothing. Classification of what stayed: `VAULT_TOKEN` (bootstrap
trust model, ADR-040), `DOCKER_HOST`/`KUBECONFIG`-family (local
infrastructure endpoints the SDKs define, in docker/kubernetes/terraform
connectors — documented exceptions), LLM provider keys (out of scope: they
are the LLM fabric's composition, not provider-connector credentials).

Negative evidence: with `GITHUB_TOKEN=sentinel` in the environment,
importing, constructing, and initializing the GitHub connector consumes
nothing — degraded, token untouched, store empty, no request; the bootstrap
carries the sentinel in explicitly and is the only thing that does.

## Import-time side effects

Full audit (module-level constructions across `backend/`): two import-crash
cases, both fixed by deferring construction to first use with the original
precise error preserved at the call site —

* `DeepResearchEngine` (raised without `TAVILY_API_KEY`; through the
  orchestrator import chain this made a Tavily credential a precondition for
  booting the entire application). Now a lazy proxy; research is optional
  and its absence fails the research call, not the boot. No dummy
  credentials anywhere in production.
* `OpenAIProvider` (module-level `AsyncAzureOpenAI` raising without three
  Azure variables; previously masked by a `try/except` in the agent
  registry). Now a lazy client property.
* `tavily_search_tool` (version-fragile module-level `TavilyClient`;
  dead module) — lazy for hygiene.

Everything else surveyed was verified lazy-safe (infrastructure singletons
connect in `connect()`, LLM adapters build clients in accessors) or low
severity (local-disk JSON reads), and is recorded in the phase evidence.

## Machine-checkable rules (now 19 in the gate)

* **BND-AMBIENT-CREDENTIALS** (ERROR): AST-level — an `os.getenv`/
  `os.environ` access naming a provider credential variable outside the
  allowlisted composition module is a violation. Comments and docstrings
  cannot trip it; a synthetic violation is detected (sensitivity-tested).
* **BND-DIRECT-HTTP** (ERROR): the bounded contexts and the credential
  fabric import no HTTP client library; transport lives in
  `backend.platform.transport` (ADR-041). Also sensitivity-tested.
* The legacy execution boundary itself remains the machine-checkable
  execution quarantine (`ungated_surfaces()` empty, asserted in phase
  evidence), alongside BND-LEGACY-AUDIT from ADR-057.

## Evidence from the real application (cortex_p515, blank → Alembic 0013)

Booted with **zero provider credentials and no Tavily key**: the 5.14
import-crash is gone; the governed runtime is ONLINE; the V1 GitHub
connector is registered but visibly degraded with an empty store. Governed
execution through the application's own scheduler: exactly one provider
call, audited, outbox delivered, chain verifies. Five refusal classes
correctly classified and audited. Legacy negatives inside the running app:
the mcp/mission routes refuse 503; the internal orchestrator launch refuses
`LegacyExecutionRefused` with no provider contact, no credential, no audit
write; the autonomous generator degrades to "mission not created". Replay
inert (provider/credential/audit/outbox/leadership all zero-delta).
Multi-process: one live holder per role, one dispatch per queue item.
Crash: leader dies holding scheduler + audit writer; successor takes the
lapsed roles and completes a governed execution; the chain verifies across
the crash. Secret safety: no material and no sentinel anywhere in rows or
exports. Retention remains plan-only. Developer DB at 0009 with zero cp_*
tables throughout.

Contract tests updated explicitly for the intentional change (the two
`CredentialService` env-fallback tests now assert the no-fallback contract
and the bootstrap road; documented in the tests themselves).

## Guarantees

One authoritative execution path (the governed gateway); every known V1
execution surface refuses by default behind one flag, including the
non-HTTP autonomous chain; no provider credential is consumed ambiently by
any connector module; importing any audited module requires no credential
and no connectivity; the boundary and the credential rule are enforced by
the architecture gate on every run.

**Not guaranteed.** Migration of V1 mission semantics onto governed
capabilities (deliberately deferred until the capability declarations
exist); the conduct of V1 surfaces when an operator sets the legacy flag
(deliberate, logged bypass); LLM-fabric key hygiene (out of scope here);
V1 read-only routes (unchanged, by the boundary's documented scope).

## Phase 5.16 boundary

Candidates: declaring the mission templates' connector operations as
governed capabilities (the migration this phase prepared, and the road to
re-enabling autonomous remediation on governed rails); tenancy and
principals for autonomous missions; LLM provider key composition; retiring
path A's dead sandbox pipeline. Phase 5.5 remains **BLOCKED —
`credential_unavailable`**, untouched.
