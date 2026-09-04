# Phase 9.7 — Implementation Map (discovery output)

**Written before any implementation. No production code was changed in this phase.**

Phase 9.7 was to build the SEALED execution tier that Phase 9.6 discovered it
needed. Discovery found that it cannot be built on this machine, so this document
is the map plus the contradiction, and there is no implementation section to
follow it.

---

## 1. What already exists (reuse, never rebuild)

The brief's forbidden list is almost entirely already present and already
correct. Nothing below needed to be created.

| Concern | Where it already lives | State |
|---|---|---|
| Credential authority | `backend/platform/credentials/broker.py` | Complete. Fail-closed. Verifies **after** the provider answers, and refuses a credential *broader* than the authority that requested it — "a credential stronger than the authority that asked for it is a privilege escalation delivered by the component meant to prevent one." No default provider, no system credential, no environment fallback. |
| Credential authority re-check | `GatewayAuthorityRevalidator` (`backend/api/credential_composition.py`) | Complete. Re-reads the binding through the same Connectivity service the gateway consults, at mint time. Fails closed in every direction. |
| Credential delivery | `ScopedCredentialProvider.scoped_credential` → broker | Complete. Tenancy checked against the *authenticated context*, not just the request. |
| Credential adapters | `DevelopmentCredentialProvider`, `VaultCredentialAdapter` | Present. Broker ships with **zero** adapters registered — "a platform with no credential source should refuse rather than find one." |
| Execution authority | `InvocationGateway.invoke` → `WorkerRuntime.invoke` | Complete. "Admit, invoke exactly once, check the result, record it. No loop, no retry, no fallback." |
| Worker plug point | `WorkerRuntime.invoke(context, worker_request, selection=, authority=)` | **This is where a sealed worker would attach** — as a new worker entry + adapter, not a new executor. |
| Isolation enforcement | `worker_selection.py:355` → `WorkerRefusal.ISOLATION_INSUFFICIENT` | Complete, in the domain. |
| Contract-time isolation gate | `CapabilityContract.__post_init__` (`contract.py:206`) | Complete. Refuses registration. |
| Leases / fencing | `ExecutionLease`, `SqlLeadershipStore.heartbeat` (fenced conditional UPDATE) | Complete; reused in 9.3's watch driver. |
| Emergency stop, breaker, autonomy | `AutonomyPolicy.evaluate` — ten gates | Complete; all ten exercised in 9.6. |
| Audit | Hash-chained, independently verifiable (`BND-LEGACY-AUDIT`, invariant I3) | Complete. |
| Transport | `TransportBroker` + `HttpxTransportAdapter`, fenced by `BND-DIRECT-HTTP` | Complete. |
| World store | `cw_observation` / `cw_fact` / `cw_verification` / `cw_reasoning`, append-only | Complete (Phase 7). |

### What does *not* exist

- **No out-of-process worker of any kind.** Every worker is an in-process
  adapter. `IsolationTier.CONTAINED` is declared for GitHub, Grafana, Prometheus
  and Kubernetes alike, with the in-process gap stated openly in ADR-059.
- **No sealed anything.** No irreversible-write capability has ever been
  registered (ADR-086).
- **No Kubernetes credential adapter.** The real K8s token today is a long-lived
  ServiceAccount token read from `CORTEX_KUBERNETES_TOKEN` in exactly one
  composition module and handed to a `DevelopmentCredentialProvider` that
  refuses PRODUCTION four ways over. There is no TokenRequest adapter.

### The one thing that looks relevant and is not

`backend/execution/sandbox/interfaces.py` — a V1 `ShellSandbox` whose allowlist
includes `python3`, `git` and `env` (22 commands), plus `ScriptSandbox` and
`HTTPSandbox`. This is quarantined legacy and is the **exact opposite** of this
phase: arbitrary shell with an allowlist is the thing SEALED exists to contain,
not a foundation to build it on. Verified executed: check C5.

---

## 2. The three contradictions

### Contradiction 1 — the environment cannot provide SEALED. No escape.

`IsolationTier.SEALED` (`backend/contracts/connector.py:56-68`) is defined as:

> *"Arbitrary commands or code. **Full virtualization**, no ambient credentials."*

and the enum docstring states, with emphasis in the original:

> *"`SEALED` **explicitly excludes shared-kernel containers**: where untrusted or
> model-generated commands run, hardware-enforced isolation is required."*

Executed probes (harness section A — real `docker`, real containers):

| Probe | Result |
|---|---|
| Available runtimes | `io.containerd.runc.v2`, `nvidia`, `runc` — **no `runsc`, no `kata`** |
| Host kernel | `6.6.87.2-microsoft-standard-WSL2` |
| Kernel seen *inside* a container | `6.6.87.2-microsoft-standard-WSL2` — **identical** |
| `/dev/kvm` inside a container | **ABSENT** |
| `vmx` flags in `/proc/cpuinfo` | **0** |

A container here reports the host's own kernel because it *is* the host's kernel.
And without `/dev/kvm`, Kata Containers and Firecracker are not merely
uninstalled — they cannot run at all. gVisor is absent, and gVisor is a
user-space kernel rather than hardware-enforced isolation in any case.

**Every container obtainable on this host is precisely the shared-kernel
container that SEALED excludes.** There is no configuration, installation or
workaround that changes this; it is a property of the hardware exposure.

### Contradiction 2 — an out-of-process worker breaks `BND-PROCESS-SPAWN`

`ProcessSpawnQuarantineRule` (`boundary_rules.py:530`) confines process creation
to exactly four named legacy modules and states that a fifth call site "is an
ERROR, not a review comment." Executed: the allowlist has exactly 4 entries, its
severity is `ERROR`, all four are legacy, and the rule passes today across 1181
modules with **0** violations.

A CortexPrime-spawned worker needs a fifth entry. Widening that allowlist is
weakening an existing invariant, which this phase was told not to do.

**Escapable.** An *operator-provisioned* worker — deployment infrastructure, like
PostgreSQL — requires no spawn from the platform at all, and the platform reaches
it through the existing transport. This contradiction alone would not stop the
phase.

### Contradiction 3 — bootstrap regress and privilege inversion

If CortexPrime creates the sealed worker itself as a Kubernetes Pod or Job, that
creation runs code that terminates and has no inverse — an `IRREVERSIBLE_WRITE`
at minimum. So **creating a SEALED worker would require a SEALED worker.**
Executed: D1–D3.

Separately, and not executed here (recorded as `[REASONED]`, not as a pass):
`create pods` is a strictly larger grant than `patch deployments` — a principal
that may create Pods may mount any Secret in the namespace and assume any
ServiceAccount in it. Bootstrapping the worker would hand CortexPrime **more**
authority than the single action the worker exists to contain. Proving this
empirically would mean granting that permission on a live cluster, which is the
thing being argued against.

**Escapable**, by the same operator-provisioning route as contradiction 2.

---

## 3. The deeper architectural finding

`_TIER_SUFFICIENCY` routes `IRREVERSIBLE_WRITE` to SEALED. But SEALED's
*definition* is written about **arbitrary or model-generated code**. The taxonomy
carries one axis where the architecture has two independent ones:

| Axis | Question | Our rollout restart |
|---|---|---|
| Code trust | Can the worker be made to run something nobody declared? | **No.** One typed operation, two validated parameters, one fixed JSON document, one HTTPS destination. |
| Consequence | What does it cost if it happens? | **High.** Irreversible; pods terminate. |

The tier system answers only the second question, using vocabulary drawn from the
first. So the platform currently requires the isolation appropriate to *running
attacker-supplied code* in order to perform a two-parameter typed `PATCH` — while
the actual risk of that PATCH is consequence, which governance already contained
in 9.6 (approval, autonomy ceiling, blast radius, authorization, assurance).

**This is not recorded as a defect to fix here.** Separating the axes changes a
Constitution-level contract (S6), and that is a ratification decision, not an
engineering one. It is recorded because it is the honest reason the phase is
stuck: the block is a *taxonomy* limit as much as a hardware one.

---

## 4. What was NOT done, deliberately

- No SEALED worker was built.
- No tier was renamed, and **no intermediate tier was invented** — an
  `ISOLATED`-between-`CONTAINED`-and-`SEALED` tier permitting irreversible writes
  without virtualization is the invariant-weakening this phase forbids, wearing a
  new name.
- `IRREVERSIBLE_WRITE` on the rollout restart is unchanged.
- The autonomy policy, gateway, authorization, approval, audit and tenant
  isolation are untouched.
- No second executor, gateway, credential authority or approval authority was
  created — none was created because none was needed and nothing was built.
- **Zero production modules changed.**

---

## 5. What would unblock this

In rough order of how much they change:

1. **Different infrastructure.** A host or cloud cluster exposing KVM, or a
   managed cluster with a gVisor/Kata `RuntimeClass`. This satisfies the contract
   as written, changes no contract, and is the only path that needs no
   ratification. It needs hardware this project does not have.
2. **Ratify a split of the two axes** (§3), so a typed non-arbitrary irreversible
   capability has a tier whose requirements the environment can actually meet,
   while arbitrary/model-generated code still requires full virtualization. This
   ends with a real write. It is a Constitution-level amendment and needs
   explicit sign-off.
3. **Accept that CortexPrime remains read-only.** Defensible: every read phase
   (9.1–9.5) is verified and useful, and an investigator that diagnoses correctly
   and refuses to act is worth more than one that acts unsafely.

Option 1 is the honest default. Option 2 is the one worth deliberating.
