# Phase 9.8 — Execution Trust Model Reassessment

**Architecture only. No code, no migration, no Constitution amendment, no execution.**

Every claim below is labelled `[FACT]` (verified from this repository, by
execution or by reading source), `[SOURCE]` (established external documentation),
`[INFERENCE]` (reasoning from those), or `[PROPOSAL]` (a recommendation requiring
ratification).

---

## 0. The test this phase had to pass first

The brief sets a hard stop: *"STOP if the only justification is 'our current
machine cannot run SEALED.' Hardware limitations must NEVER drive security
architecture."*

Applied honestly, the test is: **would this analysis reach the same conclusion on
a cloud cluster with a gVisor or Kata `RuntimeClass` available?**

**Yes.** The decisive evidence is §2.3 — under the current taxonomy, *posting a
comment on a GitHub issue* requires full virtualization. That is absurd on a KVM
host, on a laptop, and in a datacentre alike. And §2.4 shows the taxonomy does
not reach the actual arbitrary-code paths at all. Neither finding mentions
hardware.

Phase 9.7's hardware blocker is what caused this question to be *asked*. It is
not what answers it, and this document does not rest on it.

---

## 1. Current semantics, verified from source

### 1.1 `IsolationTier` — `backend/contracts/connector.py:53-80` `[FACT]`

```
AMBIENT   = "Read-only calls to declared APIs. Process-level, scoped credentials."
CONTAINED = "Reversible writes via known APIs. Separate worker, per-execution credentials."
SEALED    = "Arbitrary commands or code. Full virtualization, no ambient credentials."
```

Class docstring: *"Assigned by consequence, not convenience. `SEALED` explicitly
excludes shared-kernel containers: where untrusted or model-generated commands
run, hardware-enforced isolation is required."*

`_TIER_SUFFICIENCY`:

| Tier | Sufficient for |
|---|---|
| `AMBIENT` | `READ` |
| `CONTAINED` | `READ`, `REVERSIBLE_WRITE` |
| `SEALED` | everything (`IRREVERSIBLE_WRITE`, `DESTRUCTIVE`) |

**`[FACT]` The three tier definitions are written in three different
vocabularies.** `AMBIENT` and `SEALED` describe *what computation runs*
("read-only calls to declared APIs", "arbitrary commands or code"). The
sufficiency table maps *what effect results*. The class docstring asserts both at
once — "assigned by consequence" in one sentence, "where untrusted or
model-generated commands run" in the next. Two axes, one enum.

### 1.2 Where the tier is enforced `[FACT]`

Two independent gates, both verified by execution in Phase 9.6 and again in 9.7:

1. `CapabilityContract.__post_init__` (`contexts/connectivity/domain/contract.py:206`)
   — refuses **registration**: *"isolation tier 'contained' is insufficient for a
   'irreversible_write' capability."*
2. `worker_selection.py:355` → `WorkerRefusal.ISOLATION_INSUFFICIENT` — refuses
   **worker selection**.

### 1.3 The authority the rule cites does not exist in this repository `[FACT]`

`IsolationTier` and `CapabilityContract` both attribute this rule to
*"Constitution S6"* / *"ADR-005"* / *"BC-8"*. Verified:

- `docs/adr/` contains 76 ADRs; the lowest is **ADR-010**. **There is no ADR-005.**
- No document in `docs/` defines a clause "S6", or any `S`-numbered clause set.
- `docs/CORTEXPRIME_INTELLIGENCE_CONSTITUTION.md` — the Constitution that *does*
  exist — contains **no isolation-tier rule at all**.

`[INFERENCE]` The isolation-sufficiency rule is not currently governed by any
ratified, reviewable document in this repository. Its entire authoritative text
is an enum docstring and a five-line dict. That does not make it wrong, but it
means "amending the Constitution" is the wrong description of changing it —
there is no Constitution text to amend. What exists is code.

### 1.4 What the ratified Constitution *does* say `[FACT]`

`docs/CORTEXPRIME_INTELLIGENCE_CONSTITUTION.md` §14, verbatim:

> **L10 — Reversibility Is Priced.** Every action declares reversible /
> compensable / irreversible. **Authority, approval depth, and verification
> strength scale with the class.** Irreversible actions always face a fresh human.
> *Mechanism: Reversibility on every capability contract; ladder rules in policy.*

> **L4 — Cognition Cannot Grant Authority.** No LLM output creates, widens, or
> transfers authority — including its own.

> **Trust boundary:** everything cognition emits is untrusted input,
> schema-validated and typed at the boundary.

`[INFERENCE]` **The ratified Constitution already places effect consequence on
the governance axis, and explicitly names the three controls it scales:
authority, approval depth, verification strength. It does not name isolation.**
Its stated mechanism is "ladder rules in policy," not an isolation tier.

Separately, L4 and the trust boundary place *untrusted computation* on its own
axis, confined to the cognition plane.

**The two-dimensional model this phase is asked to evaluate is therefore already
latent in the ratified Constitution.** What collapses the axes is
`_TIER_SUFFICIENCY`, which no ratified document authorises.

---

## 2. What the collapse actually causes, measured

### 2.1 Every declared write in the repository `[FACT]`

Enumerated by importing the real catalogs:

| Provider | Operation | Effect class | Composed tier |
|---|---|---|---|
| GitHub | `repository.create_issue` | `IRREVERSIBLE_WRITE` | `CONTAINED` |
| GitHub | `repository.create_issue_comment` | `IRREVERSIBLE_WRITE` | `CONTAINED` |
| Grafana | `folder.create_folder` | `REVERSIBLE_WRITE` | `CONTAINED` |
| Kubernetes | `workload.rollout_restart` | `IRREVERSIBLE_WRITE` | `CONTAINED` |

Everything else across GitHub, Grafana, Prometheus and Kubernetes is `READ`.

### 2.2 Nothing has ever declared SEALED `[FACT]`

A search of `backend/` for `IsolationTier.SEALED` finds exactly one hit, and it
is a string comparison inside a *deferred-capability inventory* report. **No
capability, no worker, and no composition root has ever declared SEALED.** The
tier has existed unused since the contract was written.

`[INFERENCE]` `_TIER_SUFFICIENCY[SEALED]` has never gated anything. The first
time an honest classification reached it (Phase 9.6), it blocked the platform
entirely. An unexercised rule that fires once and stops everything is exactly the
shape of a rule nobody has ever had to defend.

### 2.3 The reductio, executed `[FACT]`

Constructing each real declaration at the tier its connector is actually composed
with:

```
REFUSED    github  repository.create_issue          -> tier 'contained' insufficient for 'irreversible_write'
REFUSED    github  repository.create_issue_comment  -> tier 'contained' insufficient for 'irreversible_write'
REFUSED    k8s     workload.rollout_restart         -> tier 'contained' insufficient for 'irreversible_write'
grafana    folder.create_folder                     -> passes the isolation check (refused only for an unrelated missing field)
```

**`[FACT]` CortexPrime cannot post a comment on a GitHub issue.** Not for want of
a credential — Phase 5.5 blocks that separately — but because the isolation
taxonomy demands full virtualization for it. The rule as written says: *to leave
a comment on an issue, run inside a hardware-virtualized sandbox with no ambient
credentials.*

`[INFERENCE]` This has been structurally true since the capability fabric was
built. Nobody noticed because Phase 5.5's credential blocker stopped GitHub
before registration was ever attempted, and every phase since has been read-only.
Phase 9.6 did not create this; it was the first honest write to reach the gate.

`[INFERENCE]` The classification is *correct* — creating an issue genuinely has
no inverse; closing an issue is a different forward action. The **classification
is right and the routing is wrong.**

### 2.4 The coverage is inverted `[FACT]`

The three modules that actually execute arbitrary code —
`backend/connectors/terraform.py`, `backend/services/enterprise_execution_sandbox.py`,
`backend/computer/computer_task_engine.py` — declare **zero** `side_effect_class`
and **zero** `IsolationTier` between them. They are governed by a legacy
quarantine flag and `BND-PROCESS-SPAWN`, not by the tier system.

Meanwhile `ShellSandbox` (`backend/execution/sandbox/interfaces.py`) permits 22
commands including `python3`, `git` and `env` `[FACT]`.

`[INFERENCE]` **The isolation taxonomy maximally constrains the capabilities that
need it least (typed, fixed, two-parameter API calls) and does not reach the
capabilities it was written for (arbitrary shell, Terraform apply, computer
control).** That inversion is the strongest evidence that the axes are wrong, and
it is entirely independent of what hardware is available.

---

## 3. The threat model, stated separately

### 3.1 Threat A — untrusted code execution

The worker can be made to run computation nobody declared: model-generated shell
or Python, arbitrary imports, arbitrary filesystem reads, arbitrary outbound
sockets, syscall-level attacks on the host kernel.

**What contains it:** isolation. Nothing else can. Governance cannot enumerate
what arbitrary code will do, because the space is unbounded. Approval cannot
approve "whatever this program decides to do."

`[INFERENCE]` **Isolation is the only control for Threat A, and its strength must
scale with how untrusted the code is — up to and including hardware-enforced
isolation for model-generated code.** The current SEALED definition is *correct*
for this threat and must not be weakened.

### 3.2 Threat B — trusted, declared code performing a high-consequence action

One fixed implementation, one declared provider operation, validated typed
arguments, one destination, no branching on untrusted input, no shell, no dynamic
dispatch. The Phase 9.6 rollout restart: `PATCH` to one path, two parameters, one
fixed JSON document `[FACT]`.

The danger is **not** that the computation does something unexpected — it cannot.
The danger is that the *declared* action is performed when it should not have
been: wrong workload, wrong tenant, wrong moment, without approval, too broadly,
or repeated.

**What contains it:** authorization, capability binding, tenant binding, approval
binding, autonomy policy, blast-radius typing, emergency stop, circuit breaker,
fencing, replay inertness, independent assurance, post-action observation, audit.

`[FACT]` Every one of those was exercised and passed in Phase 9.6: 53/53 harness
checks including all ten autonomy gates, five independent approval-voiding
clauses, blast-radius refusals at construction, and `provider_writes == 0` for
every refusal.

### 3.3 The rule that follows

> **Governance controls *what may happen*. Isolation controls *what the executing
> computation can do*. Neither substitutes for the other.**

`[INFERENCE]` Applying this rule to §3.1 and §3.2:

- For Threat A, governance is nearly useless and isolation is everything.
- For Threat B, isolation is nearly useless and governance is everything —
  because there is no computation to contain. Wrapping a fixed two-parameter
  `PATCH` in a microVM protects the host from code that cannot do anything else
  anyway. It does not make the restart more correct, more authorized, or more
  reversible.

**`[INFERENCE]` The current taxonomy applies the Threat-A control to a Threat-B
risk.** That is not conservatism; it is a category error, and it is why it
produces the GitHub-comment result in §2.3.

### 3.4 The load-bearing caveat: code trust is a claim about integrity

`[INFERENCE]` "This worker runs only fixed declared code" is a claim that is only
true while the code is what it was declared to be. A compromised adapter is not
trusted-fixed code; it is arbitrary code, and its real classification is
Threat A.

**Any two-axis model is therefore sound only if code integrity is enforced.**
`[FACT]` The mechanisms already exist and are already strict:
`WorkerImplementation.implementation_version` refuses `latest` — *"an
authoritative execution decision that resolves at invocation time is a decision
nobody made"*; `pinned_capability_digests` binds an adapter to the exact contract
shapes it was built against; the capability digest is checked at authorization
and re-checked at credential mint.

This caveat is not a footnote. It is the condition under which the proposal in §6
is safe at all, and it must be stated in any amendment.

---

## 4. The capability matrix

### 4.1 Axis 1 — code trust `[PROPOSAL]`

How much computation the worker can perform that nobody declared:

| | Class | Meaning | Real examples in this repo |
|---|---|---|---|
| **C0** | **FIXED** | One declared operation. Typed validated arguments. Fixed destination. No shell, no dynamic dispatch, no branching on untrusted input. | `kubernetes.workload.rollout_restart`, `repository.create_issue`, every governed read |
| **C1** | **PARAMETERIZED** | A declared program whose caller-supplied data selects among declared behaviours. Still no new code. | A templated PromQL query; a declared patch shape with an operator-chosen field |
| **C2** | **THIRD-PARTY BINARY** | A vendor binary with declared arguments. Arbitrary behaviour *inside* the binary: its own syscalls, its own filesystem access, its own network. | `terraform apply`, `kubectl` |
| **C3** | **OPERATOR SCRIPT** | Human-authored code of trusted origin. Arbitrary, but attributable and reviewable. | remediation runbooks (none built) |
| **C4** | **ARBITRARY / MODEL-GENERATED** | Untrusted origin, unbounded behaviour. | `ShellSandbox`, `ScriptSandbox`, `computer_task_engine` |

### 4.2 Axis 2 — effect consequence `[FACT]`

Unchanged. `SideEffectClass` as it exists today: `READ`, `REVERSIBLE_WRITE`,
`IRREVERSIBLE_WRITE`, `DESTRUCTIVE`. **This phase proposes no change to it.**

### 4.3 The matrix `[PROPOSAL]`

Cell value = **minimum execution isolation**. `SANDBOXED` denotes a
kernel-hardened shared-kernel boundary (separate process/container, non-root,
read-only rootfs, dropped capabilities, seccomp, restricted egress, resource
limits, no ambient credentials). `SEALED` retains its current meaning: hardware
virtualization, and it still *"explicitly excludes shared-kernel containers."*

| | READ | REVERSIBLE_WRITE | IRREVERSIBLE_WRITE | DESTRUCTIVE |
|---|---|---|---|---|
| **C0 fixed** | AMBIENT | CONTAINED | **CONTAINED** | **CONTAINED** |
| **C1 parameterized** | AMBIENT | CONTAINED | CONTAINED | SANDBOXED |
| **C2 third-party binary** | CONTAINED | SANDBOXED | SANDBOXED | SEALED |
| **C3 operator script** | CONTAINED | SANDBOXED | SEALED | SEALED |
| **C4 arbitrary / model-generated** | SEALED | SEALED | SEALED | SEALED |

**Governance depth is a separate function of the column alone**, per L10 — and it
is already implemented:

| Effect | Approval | Autonomy ceiling | Verification |
|---|---|---|---|
| `READ` | none | A4 permitted | none required |
| `REVERSIBLE_WRITE` | required above A2 | A3 | readback |
| `IRREVERSIBLE_WRITE` | **always, fresh human** | **A3 — never delegated** | **independent readback** |
| `DESTRUCTIVE` | fresh human + second authority | A3 | independent readback + blast-radius sweep |

`[FACT]` The `IRREVERSIBLE_WRITE` row is already exactly what Phase 9.6 built and
proved. The proposal changes **only which column of the isolation matrix that
row is read from** — it changes nothing in the governance table.

### 4.4 Reading the matrix honestly — the uncomfortable cell

**C0 × DESTRUCTIVE = CONTAINED.** The model says a fixed, typed
`delete-namespace` operation needs only a separate worker with per-execution
credentials — not a VM.

`[INFERENCE]` This is the correct answer and it should be stated plainly rather
than hidden, because it is where the model will be attacked. The defence:

- Isolation was never the control that stops a wrong deletion. A microVM performs
  the deletion just as thoroughly.
- The controls that stop it are the ones L10 already names, plus two more the
  repo already has: blast radius expressed in the type (Phase 9.6's
  `RemediationTarget` refuses `*`, `,`, `/`, `=` at construction `[FACT]`), and a
  credential scoped no wider than the declared effect.
- If the fixed code could be subverted into deleting something else, it was never
  C0 — see §3.4. Integrity is the precondition, not an afterthought.

`[PROPOSAL]` C0 × DESTRUCTIVE should additionally require a **second independent
human authority** and a credential proven least-privilege for that exact resource.
Those are governance and credential controls, which is where the risk actually is.

### 4.5 Row C4 is deliberately flat

`[INFERENCE]` For arbitrary or model-generated code, the declared effect class is
**meaningless** — the code is not bound by it. What bounds it is the credential
and the network, and what contains a kernel escape is virtualization. So C4 is
SEALED in every column, including READ. This is stricter than today for
`C4 × READ`, and it is the row where the current SEALED definition is exactly
right.

---

## 5. Options A–D

### Option A — keep the current taxonomy

`IRREVERSIBLE_WRITE → SEALED`, SEALED = full virtualization.

**Verdict: architecturally incorrect, not merely over-conservative.** `[INFERENCE]`

Over-conservative would mean "right principle, dial set too high." This is a
different failure: §2.4 shows the rule is simultaneously **too strict where it
applies** (a GitHub comment needs a microVM) and **absent where it matters**
(Terraform and shell declare no tier at all). A control that is maximal on the
safe cases and silent on the dangerous ones is misaimed, not cautious.

`[FACT]` Its practical consequence is total: **no write to any provider, ever.**

Honest counter-argument, recorded: keeping A costs nothing that has ever worked,
since no write has ever executed. Option A is survivable — it means accepting
CortexPrime as a read-only diagnostic system permanently. That is a legitimate
product choice (§7), and it is not this document's place to overrule it.

### Option B — two independent dimensions

Isolation ← code trust. Effect class ← consequence. Governance depth ← effect
class (already L10).

**Verdict: correct. Recommended for ratification.** `[PROPOSAL]`

- It matches the ratified Constitution: L10 already scales *authority, approval
  depth, verification strength* — not isolation — with reversibility `[FACT]`.
- It matches the trust boundary: cognition is untrusted, execution of declared
  capabilities is not `[FACT]`.
- It preserves SEALED's definition **unchanged** and, via row C4, extends SEALED
  to a case that is under-covered today.
- It fixes the inversion in §2.4 by giving Terraform and shell a tier they
  currently lack.
- It requires code-integrity enforcement (§3.4), which already exists.

It is not free: it introduces a fourth tier, needs every existing capability
classified on the new axis, and its correctness depends on classifications being
made honestly — the same dependency `SideEffectClass` already has.

### Option C — a narrow "trusted fixed action" class inside the current taxonomy

**Verdict: reject as specified.** `[INFERENCE]`

The brief's own test decides it: *"Reject it if it merely renames CONTAINED."*
A class defined as "trusted, fixed, capability-bound" that maps to CONTAINED's
requirements **is** CONTAINED — the definition of CONTAINED is already "reversible
writes via known APIs, separate worker, per-execution credentials." Adding a
class that changes only which effect classes it admits is a disguised widening of
CONTAINED wearing a new name, which is precisely the move Phase 9.7 refused.

The salvageable part of C — that a *narrow, typed, fixed* action is a distinct
thing deserving distinct treatment — is exactly what Option B's C0 row expresses,
but as a declared property on its own axis rather than a special case bolted to
a tier.

### Option D — require real VM/sandbox isolation for all irreversible writes

**Verdict: reject — on threat-model grounds, not convenience.** `[INFERENCE]`

Assessed as the brief requires:

| Dimension | Assessment |
|---|---|
| **Security** | Excellent against Threat A. **Adds nothing against Threat B** — a microVM performs an unauthorized rollout restart exactly as effectively as a process does. The residual risk after Option D is identical to the residual risk after Option B for C0 code. |
| **Practicality** | Every GitHub issue comment pays VM startup. |
| **Operational complexity** | A `RuntimeClass`, a sandboxed node pool, and image/kernel management for every write path. |
| **Developer environment** | Impossible on any machine without nested virtualization — which pushes writes onto an ungoverned path locally, and an ungoverned path is L1's stated end of every other guarantee `[FACT]`. |
| **Cloud deployment** | Feasible `[SOURCE]`. |
| **Future scalability** | Poor for high-frequency, low-consequence writes. |

The decisive line is the first one. **Option D is rejected because it does not
reduce the risk it is aimed at**, not because it is expensive. Where it *does*
reduce risk — C2/C3/C4 code — Option B already requires it.

---

## 6. Constitution review

### 6.1 Finding

`[FACT]` **Clause "S6" does not exist in this repository.** It is cited by
`backend/contracts/connector.py` and `contexts/connectivity/domain/contract.py`,
attributed to a non-existent ADR-005, and defined nowhere.

`[FACT]` The Constitution that does exist contains no isolation rule, and its
L10 assigns effect consequence to *authority, approval depth and verification
strength*.

`[INFERENCE]` There is therefore **no Constitution text to amend**. The two-axis
collapse lives entirely in code. What §6.2 proposes is a code amendment requiring
ratification because of what it governs — not a constitutional amendment.

`[PROPOSAL]` Independently of the outcome here: the isolation rule should be
written down as a reviewable clause. A load-bearing security invariant whose only
statement is a docstring citing a document that does not exist is a governance
gap in its own right.

### 6.2 Proposed wording — NOT APPLIED

**CURRENT** — `backend/contracts/connector.py:53-80`:

```python
class IsolationTier(str, Enum):
    """The isolation a tool's invocation requires (Constitution S6).

    Assigned by consequence, not convenience. ``SEALED`` explicitly excludes
    shared-kernel containers: where untrusted or model-generated commands run,
    hardware-enforced isolation is required.
    """
    AMBIENT = "ambient"
    CONTAINED = "contained"
    SEALED = "sealed"

_TIER_SUFFICIENCY = {
    IsolationTier.AMBIENT: frozenset({SideEffectClass.READ}),
    IsolationTier.CONTAINED: frozenset({SideEffectClass.READ, SideEffectClass.REVERSIBLE_WRITE}),
    IsolationTier.SEALED: frozenset(SideEffectClass),
}
```

**PROPOSED** — for ratification only:

```python
class CodeTrust(str, Enum):
    """How much computation a worker can perform that nobody declared.

    This is the axis isolation answers to. It is NOT how consequential the
    action is -- that is ``SideEffectClass``, and it is priced by governance
    (L10: authority, approval depth and verification strength), not by a
    sandbox. A microVM does not make a wrong action right; it stops unknown
    code from doing unknown things.

    A declaration here is a claim about the code as shipped, and is only true
    while integrity is enforced. Compromised fixed code is ARBITRARY code.
    """
    FIXED = "fixed"                  # one declared op, typed args, fixed destination
    PARAMETERIZED = "parameterized"  # declared program, caller data selects declared behaviour
    THIRD_PARTY = "third_party"      # vendor binary, arbitrary behaviour inside it
    OPERATOR_SCRIPT = "operator_script"  # human-authored, trusted origin, arbitrary
    ARBITRARY = "arbitrary"          # model-generated or untrusted origin


class IsolationTier(str, Enum):
    """The execution boundary a worker runs behind.

    Assigned by CODE TRUST, not by consequence. Consequence is priced by
    governance under L10.
    """
    AMBIENT = "ambient"      # in-process, declared API calls, scoped credentials
    CONTAINED = "contained"  # separate worker, per-execution credentials, no ambient secrets
    SANDBOXED = "sandboxed"  # kernel-hardened shared-kernel boundary: non-root,
                             # read-only rootfs, dropped capabilities, seccomp,
                             # restricted egress, resource limits
    SEALED = "sealed"        # hardware virtualization. Explicitly excludes
                             # shared-kernel containers. UNCHANGED.

#: Minimum isolation per (code trust, effect). Isolation answers to the row;
#: governance answers to the column.
_MINIMUM_ISOLATION = {...}  # the matrix in section 4.3
```

**RATIONALE.** `[PROPOSAL]` The current enum answers two questions with one
value. Splitting them makes each rule state the threat it addresses, brings the
code into agreement with ratified L10, and closes the §2.4 inversion by giving
the arbitrary-code paths a tier they currently do not have.

**SECURITY IMPACT.**

*Strengthened:* `C4 × READ` rises from unregulated to SEALED; Terraform and shell
acquire a declared tier for the first time; SEALED's own definition is unchanged
and gains real occupants.

*Unchanged:* authorization, capability binding, tenant binding, approval binding
and its five voiding clauses, all ten autonomy gates, emergency stop, circuit
breaker, fencing, replay inertness, audit chain, independent assurance,
`SideEffectClass`, the reversibility classification of every existing capability,
L1–L16, and the Phase 5.5 credential blocker.

*Relaxed, and exactly here:* `C0/C1 × IRREVERSIBLE_WRITE` moves from SEALED to
CONTAINED. **This is a real relaxation and must be ratified as one.** Its
justification is §3.3 — for fixed code there is no computation to contain — and
its preconditions are §3.4 (integrity enforcement) plus a credential no broader
than the declared effect.

*Newly required:* code-integrity enforcement becomes load-bearing rather than
merely good practice.

**MIGRATION IMPACT.** Every existing capability needs a `CodeTrust`
declaration — 20 governed operations across four connectors, all C0 `[FACT]`.
Three V1 modules would be classified C2/C4 and would then be *more* constrained
than today. No data migration; no table; `SideEffectClass` values are untouched,
so no capability digest changes for that field. New fitness rules would be
justified only where an invariant is otherwise unenforced.

### 6.3 Verdict

`[PROPOSAL]` **S6 as intended is RETAINED** — semantic allowlisting, and
hardware-enforced isolation where untrusted or model-generated code runs. Both
survive intact; row C4 strengthens the second.

**Its current encoding is PROPOSED FOR AMENDMENT.** Not applied.

---

## 7. Phase 9.6 reassessment — no execution

`[FACT]` `kubernetes.workload.rollout_restart` today: `IRREVERSIBLE_WRITE`,
`NON_IDEMPOTENT_WRITE`, `reversible=False`, `INDEPENDENT_READBACK`, autonomy
ceiling A3, derived `RiskLevel.HIGH`, two parameters, one fixed document.

**None of that changes.** Not the risk, not the reversibility, not the effect
class, and the worker-selection gate is not bypassed.

Under the proposed model it classifies as **C0 FIXED × IRREVERSIBLE_WRITE**, and
the matrix returns **CONTAINED**.

`[INFERENCE]` **CONTAINED is not what it runs on today, and this is the finding
that matters most in this section.** CONTAINED means *"separate worker,
per-execution credentials."* The Kubernetes connector is declared CONTAINED but
runs **in-process**, which ADR-059 states openly as a gap. Today the tier is
declared, not provided.

So under the proposed model the rollout restart is still **not executable**. What
changes is the nature of the obstacle:

| | Requirement | Buildable on available hardware? |
|---|---|---|
| Today | SEALED — hardware virtualization | **No.** Proven in Phase 9.7. |
| Proposed | CONTAINED — genuinely: separate worker, per-execution brokered credentials, no ambient secrets | **Yes.** |

`[INFERENCE]` The proposal does not hand CortexPrime the write. It converts an
impossible requirement into a buildable one, and it makes ADR-059's in-process
gap load-bearing for every write to every provider — including GitHub's issue
comment. Phase 9.9, if ratified, is *"make CONTAINED real"*: an out-of-process
worker with credentials from the existing broker. Not a sealed worker.

The Phase 9.7 map already located everything that work would reuse: the credential
broker, `GatewayAuthorityRevalidator`, the `WorkerRuntime.invoke` plug point,
leases and fencing `[FACT]`.

---

## 8. Stop conditions

Each condition from the brief, against the §6.2 proposal:

| Condition | Status |
|---|---|
| Weaken existing authorization | **No.** Untouched. |
| Weaken approval | **No.** `IRREVERSIBLE_WRITE` still always faces a fresh human; all five voiding clauses stand. |
| Weaken autonomy controls | **No.** All ten gates, ceiling A3, `HUMAN_APPROVAL_REQUIRED` on irreversible actions, unchanged. |
| Allow arbitrary model execution | **No.** Row C4 is SEALED in every column — stricter than today. |
| Permit ambient credentials | **No.** CONTAINED requires per-execution credentials; SANDBOXED and SEALED forbid ambient secrets explicitly. |
| Permit arbitrary network access | **No.** Restricted egress is a stated requirement of SANDBOXED, and CONTAINED still dials through the existing transport under `BND-DIRECT-HTTP`. |
| Bypass governance | **No.** One gateway, one chain. The proposal changes a lookup table, not a path. |
| Create another execution authority | **No.** No executor, no scheduler, no gateway proposed. |
| Weaken audit | **No.** Untouched. |
| Weaken assurance | **No.** `INDEPENDENT_READBACK` still required. |
| Make irreversible writes automatically trusted | **No.** They remain HIGH risk, A3-capped, approval-bound, assurance-verified. Only the *isolation* requirement moves, and only for fixed code. |
| **Justified only by "our machine cannot run SEALED"** | **No** — §0. The GitHub-comment reductio and the coverage inversion are hardware-independent. |

**No stop condition is triggered.**

---

## 9. Isolation boundaries are not interchangeable `[SOURCE]`

Stated from established documentation. No sources were fetched in this session;
these are stable, well-documented distinctions, and they are recorded here
because the brief requires that the boundaries not be conflated.

| Boundary | What it is | Kernel |
|---|---|---|
| **Docker container / ordinary Kubernetes Pod** | Namespaces, cgroups, capabilities, seccomp, optional MAC. Process isolation on a shared kernel. | **Shared with host** |
| **`RuntimeClass`** | A Kubernetes mechanism for selecting which container runtime configuration a Pod's containers use — the supported way to schedule a Pod onto a stronger-isolation runtime. Not itself a boundary. | n/a |
| **gVisor (`runsc`)** | A user-space kernel intercepting syscalls, reducing host-kernel attack surface. Stronger than ordinary containers; **not hardware virtualization.** | Shared, but indirectly reached |
| **Kata Containers** | Each pod in a lightweight VM with its own guest kernel, using hardware virtualization. | **Own guest kernel** |
| **VM / microVM (e.g. Firecracker)** | Full hardware-virtualized isolation. | **Own guest kernel** |
| **Pod Security Standards** | Privileged / Baseline / Restricted policy levels. A *policy* control, not an isolation boundary. | n/a |

`[FACT]` This machine offers `runc` only, on one shared WSL2 kernel, with no
`/dev/kvm` and no `vmx` — verified by execution in Phase 9.7.

`[INFERENCE]` The proposed `SANDBOXED` tier corresponds to the hardened-container
/ gVisor band; `SEALED` corresponds to the Kata/microVM band and **retains its
current definition, including the exclusion of shared-kernel containers.** The
proposal does not reclassify any boundary as stronger than it is.

---

## 10. Summary

`[FACT]` The taxonomy collapses two independent dimensions, and the collapse is
measurable: it forbids posting a GitHub comment while leaving `terraform apply`
and arbitrary shell entirely outside the tier system.

`[FACT]` The ratified Constitution already separates them — L10 prices
consequence in authority, approval depth and verification strength; L4 and the
trust boundary confine untrusted computation.

`[INFERENCE]` The collapse is in `_TIER_SUFFICIENCY`, which no ratified document
authorises and whose cited authority does not exist in this repository.

`[PROPOSAL]` Split the axes (Option B). Keep SEALED exactly as defined and give
it real occupants. Keep every governance control. Accept, explicitly and on the
record, one real relaxation — `C0/C1 × IRREVERSIBLE_WRITE` from SEALED to
CONTAINED — conditional on code integrity and least-privilege credentials.

**Nothing has been changed. This phase ends at the decision.**
