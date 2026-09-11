# ADR-123 — Detection and investigation are platform-owned: deterministic detection over the signal fabric, one supervised investigator that composes the existing engine, a deterministic test plan offered through the same governed model boundary a real model uses, structured evidence matching, categorical confidence, and a real local model that may propose but never decide

- **Status:** ACCEPTED
- **Date:** 2026-09-10
- **Phase:** 11.3 — real detection + investigation (GA Prompt 3/5)
- **Parents:** `e4913b3` — Phase 11.2 (ADR-122, the signal fabric); ADR-121 (trust boundary); ADR-085 (read-only incident investigator, Phase 9.5); ADR-073/074/075 (investigation engine, governed model boundary, differential diagnosis); ADR-084 (observability corroboration and lineage); ADR-063–070 (World Plane); ADR-071 (intelligence boundary)
- **Evidence:** `docs/PHASE_11_3_DETECTION_INVESTIGATION_IMPLEMENTATION_MAP.md`, `docs/PHASE_11_3_DETECTION_INVESTIGATION_VERIFICATION_REPORT.md`, `scripts/phase113_detection_investigation_harness.py`, `docs/phase113_detection_investigation_report.json`
- **Change:** application and composition layers, two connector contract extensions, one additive evaluator in the engine, two reasoning kinds. **No migration. No new table. No new dependency. No write capability.**

> **Numbering.** Highest used is 122; this is 123. Nothing overwritten.

## Context

Phase 11.2 left a real signal fabric ending at a candidate projection and a
`DetectionHandoff` seam whose default opened nothing. The repository already
held — verified in Phases 8 and 9.5 — a platform-owned investigation loop: a
durable state machine (`cw_investigation`), a differential with categorical
statuses set only from observed values, a governed model boundary with a
schema firewall and a durable trace, a read-only tool registry that refuses a
write operation at construction, and an evidence port over the governed read
path. Nothing in `backend/` opened or advanced an investigation; every
composition used a scripted model; the only evidence tools were pod state,
termination, deployment revision and two metrics; no provider could
authenticate on this machine. This phase connects detection to that loop,
gives it the evidence an investigation actually needs, makes it run unattended
with budgets, and puts a real (local) model behind the boundary — without
letting anything the model says become truth, authority or action.

## Decisions

### D-1 Detection is deterministic, sustained, and recorded — and is not an incident

`backend/signal/detection.py` turns Phase 11.2 candidates into
`DetectionEvent`s from the observation history behind each subject: a
CrashLoopBackOff must be seen across `crashloop_min_observations` or for
`crashloop_min_duration_seconds`; a restart-count condition needs
`restart_threshold`; an alert must have been firing for
`alert_min_firing_seconds`. The thresholds are a stated `DetectionPolicy`
carried on every event, not a learned model. A detection has a deterministic
identity (tenant, condition, subject, incident-start instant) and is persisted
as a `cw_reasoning` row of kind `detection` with the observation ids that made
it — the platform's judgement about the world, kept apart from world truth. One
sustained condition opens at most ONE investigation per incident reference.
Statistical detection was evaluated and not built: the repository carries no
baseline data that would justify it, and an unexplainable detector would be a
second model the platform cannot audit.

### D-2 One investigator, embedded, composed from what exists

`backend/api/investigation_runtime.py` implements the `DetectionHandoff` and a
single supervised runner thread that runs each investigation to a conclusion
within explicit budgets (steps, governed reads, wall-clock seconds, model
tokens). It composes the existing `InvestigationService`, `InvestigationEngine`,
`ContextAssembler`, `EvidenceSelectionPolicy`, `GovernedCapabilityReader`,
`GovernedEvidenceAcquisition`, `ToolRegistry`, `GovernedModelBoundary`,
`WorldQuery` and `BeliefFormation`. It composes no dispatcher, no write
capability and no credential of its own, and runs in the process that holds the
runtime's roles (ADR-122 F-1) beside the signal worker. On start it resumes the
tenant's active investigations from the durable ledger. A second engine, queue
or worker framework was not built.

### D-3 Evidence tools over three new real reads, bounded by declaration

Kubernetes `pod.logs`, `events.list` and a new `replicasets.list` are now
real-exposed. A log is never evidence as text: the connector reduces it to
declared, bounded, secret-scrubbed **message patterns** (identifiers, numbers
and timestamps replaced by placeholders) with counts and levels — ten copies of
one error are one pattern that happened ten times. Events carry reason, type,
bounded message, count and timestamps. ReplicaSets carry revision, image,
creation time, owner and a **template digest** of what the containers run, so a
rollout that changed only metadata is distinguishable from one that changed the
process. Prometheus gains a memory-to-limit ratio, replicas-unavailable, and a
bounded **range query** whose only parameters are two platform-computed
integer instants. No parameter anywhere can reach a query string. The tools
(`backend/api/investigation_catalog.py`) bind each read to one proposition; the
kubelet is a declared lineage origin distinct from the API server.

### D-4 The platform matches structured expectations; the model never judges evidence

`backend/intelligence/application/matching.py` evaluates a test's
`supports_value` / `contradicts_value` against the observed value with a small,
total, deterministic condition language (`$in`, `$not_in`, `$gt/$gte/$lt/$lte`,
`$contains`, `$exists`, `$any_of`); a plain value still means equality. The
engine's differential update uses it. Whether a hypothesis is SUPPORTED or
REFUTED is therefore still decided from the observation by the platform —
now for expectations a real investigation needs ("exit code is one of these",
"memory at or above its limit", "a rollout inside the window that changed the
container spec").

### D-5 A deterministic test plan, offered through the same governed boundary a model uses

For each hypothesis the catalog declares the ordered tests that would support
or contradict it, with structured expectations. `PlanModelPort` emits that plan
as a schema-shaped proposal through `GovernedModelBoundary`, traced with
`provider="deterministic"`. With no model configured the investigation runs
entirely on the plan and every trace says so. With a model configured,
`PlanAugmentedModelPort` asks the model (with a timeout and a token budget) and
unions its proposal with the plan: the model may add hypotheses and tests; it
cannot remove a planned test, cannot name a tool outside the allowlist (the
selection policy refuses it), and cannot carry an authoritative field (the
schema refuses it). A provider failure, timeout, budget exhaustion or
unparseable answer falls back to the plan and is recorded in the span's config.
The investigation continues deterministically without the model, and the trace
never pretends a model ran.

### D-6 A change and the mechanism it introduced are one composite explanation, not a conflict

The engine and `settle()` accept a declared `compatible(a, b)` relation. The
catalog declares the change-attribution hypothesis (`h-deployment-regression`)
compatible with every mechanism hypothesis. Two supported hypotheses that are
compatible resolve as a composite ("revision N introduced it — specifically:
the configuration is invalid"); two supported mechanism hypotheses still
conflict. The relation comes from the incident class's vocabulary, never from
the model. Correlation alone is not attribution: the regression test supports
only when the rollout is inside the change window AND changed what the
containers run; a metadata-only rollout leaves the hypothesis OPEN and is named
as residual uncertainty.

### D-7 Confidence is categorical, computed by stated rules, de-duplicated by origin

`backend/intelligence/application/confidence.py` produces
`ROOT_CAUSE_IDENTIFIED` / `LIKELY_CAUSE` / `INSUFFICIENT_EVIDENCE` /
`CONFLICTED` / `BLOCKED` with confidence `high` / `medium` / `low` / `none` from
the differential statuses, the lineage origins of the supporting and eliminating
observations, their freshness and any contradiction. Correlated evidence
(same origin) counts once. HIGH needs either two independent supporting origins
or one supporting origin with every alternative eliminated by evidence from a
different origin, all fresh, nothing contradicting, nothing open. The
assessment carries the basis, the eliminated alternatives with their evidence,
the open alternatives, the unknowns, the next investigation step, a
recommendation CANDIDATE and `authority: none`. It is persisted as a
`cw_reasoning` row of kind `assessment`. No probability is produced; empirical
reliability of the categories is the Calibration Plane's business (Phase 8.7).

### D-8 A real local model, activated through the existing stack, labelled honestly

*Superseded for the record run by D-18 (the operator's hosted `glm-5.2`); the local provider remains supported, and D-17 applies to it.*

The existing `backend.llm_provider` Ollama adapter was made usable for the
governed boundary (JSON mode, token usage, honoured timeout, stated context
window) and `LLMServiceModelPort` gained provider/timeout/token parameters. A
local Ollama container serving `llama3.2:3b` is a REAL provider: real HTTP, real
tokens, real latency, no key, no data leaving the machine. Configured by
`CORTEX_INVESTIGATION_MODEL_PROVIDER` / `CORTEX_INVESTIGATION_MODEL`; unset
means the deterministic plan. External hosted providers stay unconfigured on
this machine (placeholder keys) and were not activated.

### D-9 Cost is measured from the durable trace, not accounted in a new table

Model calls, tokens and latency come from `cp_harness_trace` spans keyed by the
investigation reference; governed reads and steps from the investigation
aggregate; USD from the existing static cost table (a local provider prices at
zero). Exposed as `GET /api/v1/investigations/{ref}/cost` and inside the
assessment; mirrored into the existing Prometheus registry. No billing system
was created.

## Consequences

- A real CrashLoopBackOff on the cluster becomes, unattended: a durable
  detection, an investigation, governed reads of pod state, events, logs,
  termination, ReplicaSet lineage and cAdvisor memory, a differential updated
  from observed values, and an assessment with evidence ids — or an honest
  INSUFFICIENT_EVIDENCE.
- The evidence path costs one governed read per test (≤ `max_reads`) plus two
  baseline reads; a model step costs one bounded model call.
- The engine gained one optional parameter and one evaluator; `settle()` one
  optional parameter. Pre-11.3 behaviour is unchanged when they are absent.
- Two connector contracts widened for declared-only operations (`pod.logs`,
  `events.list`); `replicasets.list` and two Prometheus operations were added.
  Deployments that commissioned the earlier contracts re-commission the widened
  ones (an operator act, as before).

### D-10 A finished governed read leaves the dispatch set; one read in flight per process, served fairly

`GovernedCapabilityReader._drive` tracked every execution it started in the
shared scheduler and never untracked it. Because a read execution never
finalises at the aggregate level (the node succeeds; the run stays "running"),
every tick thereafter re-loaded every execution ever read in the process — a
cost that grew with every watch window and every enrichment read until the
loop crawled to a stop. That is the stall Phase 11.2 recorded as F-6, now
reproduced deterministically (41 tracked executions and a loop that no longer
advanced) and fixed: a read untracks itself when it is done, budget exhausted
or not.

Two threads that each drive the shared scheduler with a tenant context (the
signal watch loop and the investigator) performed each other's executions and
blocked on each other's rows — the stall Phase 11.2 recorded as F-6, now
reproduced deterministically. The runtime's own scheduler loop cannot take the
work over: it ticks with a platform context and refuses tenant nodes. So
`GovernedCapabilityReader.read` serialises through a process-wide, FAIR,
re-entrant ticket lock. Fair, because `threading.RLock` let the watch loop
(which reads back-to-back) starve the investigator indefinitely on this
platform. Cost: an investigation read waits at most one watch window.

### D-11 The transport enforces its total budget on a streaming body

Measured: of 23 back-to-back governed watch windows declared with
`timeoutSeconds=5`, 22 closed at 5.5 s and one never closed — the API server
kept the stream open and the client read it indefinitely, because the transport
applied connect/read/write timeouts per socket operation and never the
`total_seconds` the policy already declares. A body that keeps trickling bytes
never trips a per-read timeout. `_read_bounded` now raises `httpx.ReadTimeout`
once the total budget has elapsed; the watch driver sees an ordinary failed
window and re-watches from its position. The other half of F-6.

### D-12 A context the gateway will refuse leases nothing

Measured on the live cluster in the first full run: 8 of 126 governed reads
stayed `leased` for their whole lease term and the investigations that needed
them concluded BLOCKED. Every one of the eight carried
`tenant_id: __platform_internal__` in its persisted record. The runtime's own
scheduler loop ticks with a platform-internal context over the same dispatch
set the tenant readers use; the dispatcher took the node's lease first and
asked the gateway second; the gateway's tenancy stage refuses every invocation
a platform-internal context makes; and the "quiet reclaim" that should return a
refused-before-run node rightly declines to take back a lease that has not
lapsed. The tenant's own reader then waited its whole tick budget on a node it
could not lease. The dispatcher now refuses a platform-internal context before
the lease (`invocation_refusal=tenant_unknown`, nothing leased, the same
refusal the gateway would have recorded), so the node stays free for the
context that can invoke it. The gateway's rule is unchanged; the dispatcher
merely stops taking a lease it knows will be refused.

### D-13 A concluded incident is not reopened inside the detection lookback

A CrashLoop keeps being a CrashLoop until somebody changes something. Each
detection window it sustains is the same incident, so the handoff consults the
durable ledger (`list_terminal`) and does not open a second investigation for
an incident reference that concluded inside the detection lookback (1800 s).
Measured: without this rule the S1 pod, still crash-looping, received a second
investigation the moment its next window fired — queued ahead of the S2
incident that needed one — and the second one told nothing the first had not.
After the lookback a fresh detection opens a fresh investigation: the world may
have changed. The rule reads the ledger, so a restarted process applies it too.

### D-14 A metric projection answers for the subject, and a sample below the limit refutes nothing

Two things the first full runs measured. First, every Prometheus operation is
declared namespace-wide — a caller supplies no selector, which is what keeps a
model from composing a query — and the projections read that answer as if it
were about the subject: the peak memory ratio S1 recorded (0.1752) belonged to
`contained-worker`, and the restart projections took the first or the summed
series. The platform now narrows every metric answer to the subject's series,
bound at composition from the subject reference; a subject with no series
decides nothing. Second, the memory ratio itself: cAdvisor keeps a series per
container instance, so a restarted pod's raw series cannot be divided
("many-to-one matching"), and the container-level limit series is absent while
the pod waits in back-off. Each side is aggregated per pod, the limit comes
from the pod cgroup, and the numerator is the scraped thirty-minute peak. Even
so, a burst shorter than cAdvisor's housekeeping interval is invisible: in S4
the kernel killed the container within a second and the scraped peak stayed
under a tenth of the limit. So the memory test supports and never refutes; a
kernel kill (exit 137 / OOMKilled), already read from the kubelet's termination,
refutes the application-exit hypotheses; an ordinary non-zero exit supports
none of them (the silent scenario stays open). With the metadata-only rollout
open, S4's honest outcome is LIKELY_CAUSE with low confidence from one origin.

### D-15 "Not observed" is neither a value nor a block

The acquisition port already refused to record a read that succeeded but
reported nothing for the subject ("not observed is not a value"). The engine,
however, read every `ok=False` as a platform failure and concluded BLOCKED.
Measured: a container that panics within a second of starting has no
cAdvisor series at all, so the memory read ended the S2 and S3 investigations
before the kubelet's termination and log were read. The result now says
`absent=True`; the engine spends the read, keeps the test recorded (so the plan
does not ask again), leaves the hypothesis at its stated gap, labels the step
`evidence_absent`, and continues. A refused or failed read still ends in
BLOCKED. The ratio query reads the pod cgroup on both sides for the same reason:
the pod cgroup outlives the containers whose memory it sums.

### D-16 The plan is offered in stages, decisive reads first

The engine chooses among admissible tests by deterministic identity — never by
anything a model could steer — so the order a plan lists its tests in carries
no weight. With the kernel-kill contradictions and the previous-instance logs
added, the CrashLoop plan grew to twelve tests, and the silent scenario spent
its whole ten-step budget without reaching the termination read that
eliminates resource exhaustion. The plan port now offers only the earliest
stage that still has an unrun test: every hypothesis's primary discriminator
(stage 0), then the previous-instance logs and the memory ratio (stage 1), then
the kernel-kill contradictions (stage 2). The default step budget is sized to
the staged plan (sixteen); reads stay at twelve because most later steps reuse
World evidence the first stage already read. The port learns what has run from
the investigation's own ledger, handed to it by the runner before each step:
the assembled context drops its `prior_tests` section under token-budget
pressure on real evidence (measured on the OOM scenario), and a port that
relied on the prompt alone offered stage 0 forever and settled early.

### D-17 The model sees the budgeted context; a local provider refuses what it would truncate

Measured in record runs 9 and 10. The investigation prompt was
`json.dumps(context.to_dict())`, and `to_dict` carries every section — the ones
the budget excluded included, with all of their content. The context budget
therefore recorded exclusions that never happened: in the stored prompts the
excluded world-evidence section was 17,500–19,700 of 25,000–27,000 characters,
and lowering the budget from 4,000 to 1,500 changed the prompt by 2,000
characters. Ollama then truncated those prompts (8,948 and 18,914 tokens, both
cut to 4,098, keeping 4 tokens of the front) and said so only in its own server
log. The front of the prompt is the system instruction. Every local-model
answer before this decision was produced from such a truncated prompt; none is
counted as verification.

The model is now shown `AssembledContext.prompt_view()`: the included
sections' content in priority order, the excluded sections named with their
reason and no content, and the context digest. `to_dict` and the digest are
unchanged — the recorded context still carries everything, for audit. The
Ollama adapter refuses, before any call, a prompt whose conservative estimate
(three characters per token, plus the answer's token budget) exceeds its window;
the plan answers and the span's fallback reason says why, scrubbed. Hosted
providers are shown fewer tokens for the same decision. Unchanged and stated:
when a section exceeds the budget the assembler excludes the whole section, so
a model may reason without world evidence the platform holds.

### D-18 The hosted model provider is an OpenAI-compatible endpoint named by configuration

The operator's model provider for the investigator is an OpenAI-compatible
endpoint (a proxy serving `glm-5.2`). The provider layer had no adapter for an
arbitrary OpenAI-compatible URL — the OpenAI adapter speaks only to OpenAI or
Azure, the OpenRouter adapter only to OpenRouter — so one was added:
`OpenAICompatibleAdapter`, configured by `LLM_API_KEY`, `LLM_BASE_URL` and
`LLM_MODEL`, registered beside the existing adapters. Three rules come with it.
It declares only `LLM_MODEL`, because the router matches declared model names,
so a caller that names the model reaches it. It sorts last by priority (1000;
a lower number wins), so an unnamed request elsewhere in the application does
not start sending data to it while any other provider is available. And a
plain-`http://` URL to a non-loopback host is refused unless
`LLM_ALLOW_PLAINTEXT_HTTP=1` accepts it in the operator's own configuration,
because the key and every prompt would cross the network unencrypted; when it
is accepted the adapter says so at initialisation. The operator's endpoint is
plain HTTP and the opt-in is set in the git-ignored `backend/.env`; that choice
and its consequence are recorded here, not hidden. The keys live only in that
git-ignored file; nothing in the repository carries a value.

The harness's model pass takes its provider from `CORTEX_P113_MODEL_PROVIDER`
(`ollama` by default, `openai-compatible` for the hosted endpoint). The
deterministic pass blanks every hosted key so no hosted provider registers
there. With a hosted provider the outage scenario restarts the API with the
endpoint pointed at a loopback port nothing serves, since a remote service
cannot be paused.

### D-19 A provider's "that log does not exist" is absence, whether it arrives as 200 or as an error

The kubelet has answered a request for a container's previous log in two ways
on this cluster: HTTP 200 with its own error text in the body (F-5, already
declared `logUnavailable`), and — in record run 12 — an API error carrying
`previous terminated container "app" in pod … not found`. The second failed the
governed read, and the evidence port turned the failed read into BLOCKED, so
the OOM scenario concluded with no cause. Both answers mean the same thing: the
log of that instance does not exist. A tool may now declare `absent_when`, a
compiled pattern over a failed read's reason; when it matches, the port answers
`absent` (D-15) and the investigation continues on what else can be read. The
two log tools declare the connector's own log-unavailable pattern. Every other
read failure still blocks.

### D-20 Model content that breaks a platform contract is a rejected proposal; a crash is recorded

The strict schema bounds the shape of model output, and the platform contracts
bound its meaning. In record run 13 glm-5.2 restated the seeded hypotheses with
empty references and subjects: valid JSON, valid shape, meaningless to the
differential. The engine tried to record them, the `DifferentialHypothesis`
contract refused them, and the raw
`ContractViolation` escaped the engine, crashed the investigation, and — because
the runner recorded the crash only in memory — left it `investigating` in the
ledger for good. Now the proposal port checks the fields that contract requires (reference,
subject, proposition) and rejects an incomplete model hypothesis as
`ModelSchemaRejected`, which the engine already treats as a rejected step; the
plan-augmented merge drops model hypotheses missing any of those fields, keeps the model's
valid tests and says what it dropped; and the runner records a crashed
investigation in the durable ledger with the cause: FAILED when it was
investigating, ABANDONED when it crashed before investigation began (the only
legal exit from CREATED). A model cannot crash
an investigation, and an investigation cannot silently stay open.

## Findings surfaced (recorded, not changed)

- **A platform-internal replace rewrites the record's tenant.** The execution
  repository writes `to_record(execution, tenant_id=access.tenant_id)` on every
  replace, so a lease taken under the platform-internal context stamped
  `tenant_id: __platform_internal__` into the record of a tenant's execution
  while the row's own `tenant_id` column kept the tenant. D-12 stops the
  platform loop from writing such records; the repository behaviour itself is
  the runtime owner's to decide.

- The 9.9b reader ClusterRole never granted the `pods/log` subresource;
  `kubectl auth can-i get pods/log` answers `yes` misleadingly (the resource
  form), while `--subresource=log` answers `no`. The harness grants a
  namespace-scoped Role for it; a deployment must do the same.

- Log classification is keyword-based and the words overlap: a Go nil-pointer
  panic says "invalid memory address", which is the runtime describing a
  fault, not an operator describing a setting. Runtime-fault phrases are
  removed before the configuration words are matched (S2 named the wrong
  mechanism until they were). The classifier remains a bounded heuristic over
  bounded, scrubbed patterns; it decides which structured test matched, never
  the conclusion.
- The World Plane's secret firewall refuses any value key containing
  `signature`; a projection field had to be renamed. Correct behaviour, worth
  knowing.
- `InMemoryTraceRecorder.spans_for_mission` returns span objects while
  `SqlTraceRecorder` returns records; consumers must normalise (the runner does).
- The `llm_provider` router matches a model name against each adapter's
  declared model list; a local model must be registered under a declared name
  (the harness aliases `llama3.2:3b` as `llama3.2`).

## Limitations (stated)

- Incident classes: CrashLoopBackOff, workload unavailable, alert-with-workload.
  An alert naming nothing observable concludes INSUFFICIENT_EVIDENCE by design.
- Workload identity is inferred from the pod name (as in 11.2).
- Loki logs, traces and Git/CI change metadata are not governed sources; change
  correlation rests on the ReplicaSet lineage.
- The record's real-model evidence comes from the operator's hosted `glm-5.2` over a
  plain-HTTP proxy (D-18): unencrypted in transit, acceptable only for the
  synthetic data of the test cluster. The local 3B model is CPU-bound here and
  was not used for the record.
- One investigation at a time per process; the queue is bounded.
