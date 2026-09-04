# ADR-088 — The execution trust model: isolation answers to code trust, not consequence

**Status:** **ACCEPTED — ratified by the owner on 2026-09-04, as written.**
Ratified in full: the two-axis model, the `CodeTrust` axis, the `SANDBOXED` tier,
SEALED retained verbatim, and the one named relaxation
(`FIXED`/`PARAMETERIZED` × `IRREVERSIBLE_WRITE`: SEALED → CONTAINED) under both
preconditions in Decision 4. Implementation is Phase 9.9.
**Date:** 2026-09-04
**Extends:** ADR-059 (in-process worker gap), ADR-086 (Phase 9.6 blocked write),
ADR-087 (Phase 9.7 SEALED unavailable).
**Analysis:** `docs/PHASE_9_8_EXECUTION_TRUST_MODEL.md`

Claims are labelled `[FACT]` (verified from this repository), `[INFERENCE]`,
`[SOURCE]` (established external documentation), `[PROPOSAL]`.

---

## Context

ADR-087 stopped Phase 9.7 because SEALED demands hardware virtualization this
machine cannot provide, and noted a suspected architectural mismatch underneath
that hardware blocker. Phase 9.8 was to determine whether the mismatch is real,
**without letting hardware drive the answer.**

It is real, and the evidence does not involve hardware.

---

## Finding 1 — the taxonomy forbids posting a GitHub comment `[FACT]`

Every non-read operation any real connector declares, constructed at the tier its
connector is actually composed with:

```
REFUSED   github  repository.create_issue          -> tier 'contained' insufficient for 'irreversible_write'
REFUSED   github  repository.create_issue_comment  -> tier 'contained' insufficient for 'irreversible_write'
REFUSED   k8s     workload.rollout_restart         -> tier 'contained' insufficient for 'irreversible_write'
```

`repository.create_issue_comment` is correctly classified `IRREVERSIBLE_WRITE` —
a comment has no inverse. Under the current taxonomy it therefore requires
*"full virtualization, no ambient credentials."*

`[INFERENCE]` **The classification is right; the routing is wrong.** This is not
a Kubernetes problem and was not created by Phase 9.6 — it has been structurally
true since the capability fabric was built, unnoticed only because Phase 5.5
blocked GitHub on credentials before registration was ever attempted.

**This is the hardware-independence test the brief demanded, and it passes:** the
result is equally absurd on a KVM host with a Kata `RuntimeClass`.

## Finding 2 — the coverage is inverted `[FACT]`

`backend/connectors/terraform.py`, `backend/services/enterprise_execution_sandbox.py`
and `backend/computer/computer_task_engine.py` — the three modules that actually
execute arbitrary code — declare **zero** `side_effect_class` and **zero**
`IsolationTier` between them.

`[INFERENCE]` The isolation taxonomy maximally constrains typed two-parameter API
calls and does not reach `terraform apply` or arbitrary shell at all. A control
that is maximal on the safe cases and silent on the dangerous ones is misaimed,
not conservative.

## Finding 3 — SEALED has never been declared, anywhere `[FACT]`

One hit for `IsolationTier.SEALED` in `backend/`, inside a report's string
comparison. No capability, worker or composition root has ever used it.
`_TIER_SUFFICIENCY[SEALED]` has never gated anything; the first honest write to
reach it stopped the platform entirely.

## Finding 4 — the cited authority does not exist `[FACT]`

`IsolationTier` and `CapabilityContract` attribute this rule to *"Constitution
S6"* and *"ADR-005"*. `docs/adr/` holds 76 ADRs beginning at **ADR-010** — there
is no ADR-005 — and no document in `docs/` defines an "S6" or any `S`-clause set.

`[INFERENCE]` There is **no Constitution text to amend.** The rule's entire
authoritative statement is an enum docstring and a five-line dict.

## Finding 5 — the ratified Constitution already separates the axes `[FACT]`

`docs/CORTEXPRIME_INTELLIGENCE_CONSTITUTION.md` §14, verbatim:

> **L10 — Reversibility Is Priced.** Every action declares reversible /
> compensable / irreversible. **Authority, approval depth, and verification
> strength scale with the class.** Irreversible actions always face a fresh human.
> *Mechanism: Reversibility on every capability contract; ladder rules in policy.*

`[INFERENCE]` L10 assigns consequence to **authority, approval depth and
verification strength** — and names its mechanism as *policy ladder rules*. It
does not name isolation. L4 and the trust boundary independently confine
*untrusted computation*.

**The two-axis model is already latent in the ratified Constitution. What
collapses the axes is `_TIER_SUFFICIENCY`, which no ratified document
authorises.**

---

## Decision 1 — `[PROPOSAL]` Isolation answers to code trust; governance answers to consequence

> **Governance controls what may happen. Isolation controls what the executing
> computation can do. Neither substitutes for the other.**

Two threats, two controls:

- **Threat A — untrusted code.** Unbounded behaviour. Governance cannot enumerate
  it; approval cannot approve "whatever this program decides." **Only isolation
  contains it**, scaling to hardware-enforced isolation for model-generated code.
- **Threat B — trusted declared code, high-consequence action.** One fixed
  implementation, typed validated arguments, one destination. The computation
  cannot do anything unexpected. The risk is that the *declared* action happens
  when it should not: wrong workload, wrong tenant, wrong moment, unapproved, too
  broad, repeated. **Only governance contains that** — and `[FACT]` Phase 9.6
  proved all of it works: ten autonomy gates, five approval-voiding clauses,
  blast radius refused at construction, `provider_writes == 0` on every refusal.

`[INFERENCE]` The current taxonomy applies the Threat-A control to a Threat-B
risk. Wrapping a two-parameter `PATCH` in a microVM protects the host from code
that cannot do anything else anyway; it does not make the restart authorized,
correct, or reversible. That category error is what produces Finding 1.

## Decision 2 — `[PROPOSAL]` Adopt Option B; reject A, C and D

**Option B — split the dimensions. Recommended.** Isolation ← code trust
(`FIXED` / `PARAMETERIZED` / `THIRD_PARTY` / `OPERATOR_SCRIPT` / `ARBITRARY`).
Effect class unchanged. Governance depth ← effect class, per L10.

**Option A — keep the taxonomy. Rejected as incorrect, not merely
over-conservative** (Findings 1–2). Recorded honestly: A is survivable and costs
nothing that has ever worked, because no write has ever executed. Choosing it
means accepting CortexPrime as a permanently read-only diagnostic system. That is
a legitimate product decision and remains the owner's to make.

**Option C — a "trusted fixed action" class inside the current taxonomy.
Rejected.** CONTAINED is already defined as *"reversible writes via known APIs;
separate worker, per-execution credentials."* A class with those requirements
that merely admits more effect classes **is** a widening of CONTAINED under a new
name — the disguised weakening Phase 9.7 refused. Option B expresses C's
salvageable idea as a declared property on its own axis instead.

**Option D — require VM isolation for all irreversible writes. Rejected on
threat-model grounds, not convenience.** `[INFERENCE]` A microVM performs an
unauthorized rollout restart exactly as effectively as a process does: for C0
code the residual risk after D is identical to the residual risk after B. It is
rejected because **it does not reduce the risk it is aimed at.** Where it does —
third-party binaries, operator scripts, model-generated code — Option B already
requires it. (Its practical costs are recorded in the analysis; they are not the
reason.)

## Decision 3 — `[PROPOSAL]` SEALED is retained verbatim and gains occupants

SEALED keeps its definition, including *"explicitly excludes shared-kernel
containers."* It is **not** renamed, widened, or applied to shared-kernel
infrastructure.

The proposed `ARBITRARY` row is SEALED in **every** effect column, including
`READ` — stricter than today, where those paths declare no tier at all. For
arbitrary code the declared effect class is meaningless, because the code is not
bound by it; what bounds it is the credential and the network, and what contains
a kernel escape is virtualization.

`[SOURCE]` The proposed `SANDBOXED` tier corresponds to the hardened-container /
gVisor band (user-space kernel, shared host kernel); `SEALED` to the Kata/microVM
band (own guest kernel, hardware virtualization). Docker containers, Kubernetes
Pods, `RuntimeClass`, gVisor, Kata and VMs are **not** interchangeable boundaries
and are not treated as such here.

## Decision 4 — `[PROPOSAL]` Name the one real relaxation, and its preconditions

The proposal is not risk-neutral, and pretending otherwise is how a weakening
gets ratified by accident.

**`FIXED` / `PARAMETERIZED` × `IRREVERSIBLE_WRITE` moves from SEALED to
CONTAINED.** That is a genuine relaxation. It must be ratified as one, and it is
sound only under two preconditions:

1. **Code integrity is enforced.** "This worker runs only fixed declared code" is
   true only while the code is what it was declared to be; compromised fixed code
   is arbitrary code. `[FACT]` The mechanisms exist and are already strict:
   `implementation_version` refuses `latest`, `pinned_capability_digests` binds an
   adapter to exact contract shapes, and the capability digest is checked at
   authorization and re-checked at credential mint.
2. **The credential is no broader than the declared effect.** `[FACT]` The broker
   already refuses a credential broader than the authority that requested it.

`[PROPOSAL]` Additionally, `FIXED × DESTRUCTIVE` should require a **second
independent human authority**. The model returns CONTAINED for it — stated
plainly because it is where the model will be attacked — and the defence is that
isolation was never the control that stops a wrong deletion. Blast radius in the
type, least-privilege credentials, and a fresh human are.

## Decision 5 — `[PROPOSAL]` Write the isolation rule down

Independently of the outcome: a load-bearing security invariant whose only
statement is a docstring citing a document that does not exist is a governance
gap. If the current model is retained, that too should be recorded as a
deliberate, reviewable decision rather than left in a dict.

---

## Phase 9.6 reassessment — no execution, no reclassification

`[FACT]` `kubernetes.workload.rollout_restart` is unchanged: `IRREVERSIBLE_WRITE`,
`NON_IDEMPOTENT_WRITE`, `reversible=False`, `INDEPENDENT_READBACK`, ceiling A3,
`RiskLevel.HIGH`, two parameters, one fixed document. The worker-selection gate is
not bypassed. It was not executed.

Under the proposed model it is `FIXED × IRREVERSIBLE_WRITE` → **CONTAINED**.

`[INFERENCE]` **It still does not execute.** CONTAINED means *"separate worker,
per-execution credentials,"* and the Kubernetes connector is declared CONTAINED
while running in-process — ADR-059's stated gap. The tier is declared, not
provided.

What changes is the obstacle:

| | Requirement | Buildable here? |
|---|---|---|
| Today | SEALED — hardware virtualization | **No** (ADR-087) |
| Proposed | CONTAINED — genuinely separate worker, brokered per-execution credentials, no ambient secrets | **Yes** |

`[INFERENCE]` The proposal converts an impossible requirement into a buildable
one and makes ADR-059's in-process gap load-bearing for **every** write to every
provider, GitHub's issue comment included. If ratified, Phase 9.9 is *"make
CONTAINED real"* — not *"build a sealed worker."*

---

## Stop conditions

None triggered. Unchanged by the proposal: authorization, capability binding,
tenant binding, approval and its five voiding clauses, all ten autonomy gates,
emergency stop, circuit breaker, fencing, replay inertness, audit chain,
independent assurance, `SideEffectClass` and every existing reversibility
classification, L1–L16, and the Phase 5.5 credential blocker. No second execution
authority, gateway, scheduler or credential authority is proposed. Arbitrary
model execution becomes *more* constrained, not less.

The hardware test is answered in Finding 1: the justification is a GitHub comment,
not a missing `/dev/kvm`.

---

## Consequences

**If ratified:** every capability declares a code-trust class (`[FACT]` 20
governed operations across four connectors, all `FIXED`); three V1 modules become
*more* constrained than today; Phase 9.9 becomes "make CONTAINED real" — an
out-of-process worker with credentials from the existing broker, buildable on
available hardware; the isolation rule gets written down.

**If rejected:** CortexPrime remains read-only against every provider,
permanently and by decision rather than by accident. Findings 2–4 still stand and
still deserve fixing: the arbitrary-code paths still declare no tier, SEALED is
still unoccupied, and the rule still cites a document that does not exist.

**Either way:** nothing in this ADR has been applied. No code, no migration, no
new table, no connector, no worker, no execution, no Constitution modification.
The phase ends at the decision.
