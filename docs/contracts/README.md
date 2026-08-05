# CortexPrime Contracts

The shared language of the platform. Every bounded context speaks to every other
bounded context in these terms.

> **The one rule:** contracts depend on nothing. Every other package may import
> `backend.contracts`; `backend.contracts` imports only the standard library.
> This is enforced in CI, not by convention.

---

## Why this package exists

The Constitution defines nine bounded contexts that communicate by published
contract only. Before this package there was nowhere for those contracts to
live, so vocabulary was redefined wherever it was needed — twelve modules
independently defined a "Mission."

A shared vocabulary is only safe if it is a *leaf* dependency. If contracts
could import a database module, then every context importing contracts would
transitively depend on the database, and the boundary would be decorative.

## What contracts may do

- Define immutable, typed value objects
- Validate their own invariants at construction
- Expose derived properties over their own fields (`is_terminal`, `can_approve`)
- Serialize to and from transport-neutral dictionaries

## What contracts may never do

- Business logic, orchestration, or decisions
- Persistence, I/O, or network access
- Import a framework, an ORM, or any third-party library
- Import any `backend` module other than `backend.contracts.*`
- Compute hashes, generate identifiers, or read the clock

The last one is worth stating plainly: a contract carries a digest, it does not
compute one. Hashing is platform infrastructure (PR-02). A contract that
computed its own digest would be doing work, and "contracts do no work" is what
makes the dependency rule hold.

---

## Contract catalogue

| Module | Owner | Defines |
|---|---|---|
| `tenant` | BC-9 | `TenantRef`, `OrganizationRef`, `ProjectRef`, `TenantScope` |
| `identity` | BC-9 | `PrincipalRef`, `PrincipalKind`, `SecurityContext` |
| `mission` | BC-1 | `MissionState`, `MissionIntent`, `MissionTransition`, `TaskRef`, `LEGAL_TRANSITIONS` |
| `evidence` | BC-2 | `Citation`, `EvidenceItem`, `EvidenceSet`, `SourceOutcome`, `SourceStatus` |
| `knowledge` | BC-7 | `KnowledgeItem`, `KnowledgeKind`, `KnowledgeAuthority`, `AssembledContext` |
| `verification` | BC-4 | `Verdict`, `VerifierIdentity`, `VerificationResult` |
| `execution` | BC-5 | `SideEffectClass`, `ExecutionScope`, `ExecutionContract`, `ExecutionResult` |
| `approval` | BC-6 | `PayloadDigest`, `ApprovalArtifact`, `ApprovalRequest`, `ApprovalDecision` |
| `policy` | BC-6 | `RiskLevel`, `PolicyEffect`, `RiskFactors`, `RiskClassification`, `PolicyDecision` |
| `audit` | BC-6 | `AuditEventKind`, `AuditEvent` |
| `connector` | BC-8 | `ConnectorRef`, `ToolDescriptor`, `IsolationTier`, `ConnectorCapabilities` |
| `configuration` | Administration | `ResourceDeclaration`, `EnvironmentDeclaration`, `DeclarationSet` |

---

## Using contracts

```python
from backend.contracts import (
    ActionRef, ExecutionContract, ExecutionScope, SideEffectClass,
)

restart = ActionRef("docker.restart", {"container": "web-01"})

contract = ExecutionContract(
    execution_key="restart-web-01",
    action=restart,
    scope=ExecutionScope("docker", ("web-01",), "production"),
    side_effect_class=SideEffectClass.REVERSIBLE_WRITE,
    inverse=restart,                       # required — see below
    verification_criteria=("container reports running",),
)

wire = contract.to_dict()                  # transport-neutral, JSON-safe
restored = ExecutionContract.from_dict(wire)
assert restored == contract
```

Omitting `inverse` on a `REVERSIBLE_WRITE` raises `ContractViolation`. That is
Constitution P2 made structural: you cannot forget to think about rollback,
because the value will not construct without an answer. If there genuinely is no
inverse, classify the action `IRREVERSIBLE_WRITE` and let policy escalate it.

### Decoding an unknown message

```python
from backend.contracts import decode_envelope

contract = decode_envelope(payload)   # resolves type from the envelope
```

---

## Versioning

Each contract carries `CONTRACT_VERSION`. The package carries
`CONTRACTS_PACKAGE_VERSION`.

**Evolution is additive-only.**

| Change | Breaking? | Action |
|---|---|---|
| Add an optional field with a default | No | Ship it |
| Add an enum member | No | Ship it |
| Add a derived property | No | Ship it |
| Remove or rename a field | **Yes** | New version, both supported in parallel |
| Make an optional field required | **Yes** | New version |
| Remove an enum member | **Yes** | New version |
| Narrow a field's type | **Yes** | New version |

**Decoding rules**

- Older payload → accepted. Additive evolution makes it a valid subset.
- Newer payload → `ContractVersionError`. Better to refuse than to silently
  drop fields you do not understand.
- Unknown field in a payload → ignored, enabling forward compatibility for
  additive changes.

Breaking changes run both versions in parallel and retire the old one on a
schedule, never on hope.

---

## Adding a contract

1. Put it in the module owned by the responsible bounded context.
2. Declare `@dataclass(frozen=True)`, subclass `Contract`, set `CONTRACT_NAME`
   as `cortexprime.<area>.<name>`.
3. Use `tuple` for sequences. Use `freeze_mapping` for opaque bags.
4. Validate invariants in `__post_init__`, raising `ContractViolation`.
5. Justify every `Optional` in the docstring. The default is required.
6. Export from `__init__.py`.
7. Add the fixture to `tests/contracts/conftest.py` and the round-trip
   parametrization in `test_serialization.py`.

Optional fields deserve particular scrutiny. Every `Optional` in this package
has a stated reason — machine principals have no display name; deterministic
verifiers use no model; criticality must distinguish "declared low" from "not
declared." An `Optional` without a reason is usually a missing decision.

---

## Testing

```bash
# fast, isolated — no database, no app bootstrap, ~3 seconds
pytest tests/contracts/ --confcutdir=tests/contracts
```

| File | Validates |
|---|---|
| `test_dependency_isolation.py` | The dependency rule, by static analysis and subprocess import |
| `test_serialization.py` | Round-trip, envelope, version compatibility, determinism |
| `test_immutability.py` | Frozen instances, immutable collections, defensive copying |
| `test_validation.py` | Every constitutional rule enforced at construction |

`test_validation.py` is organized by constitutional rule rather than by module,
so a reviewer can check coverage against the Constitution directly.

---

## Migration status (Phase 1)

Contracts are currently imported by nothing. They are consumed progressively:

| PR | Consumes |
|---|---|
| PR-02 | `PayloadDigest` — canonical hashing |
| PR-03/04 | `ApprovalArtifact` — closes the approval-binding gap (I2) |
| PR-06/07 | `AuditEvent` — hash-chained audit (I3) |
| PR-23 | `ExecutionContract` — declared inverses (P2) |
| PR-29 | `RiskFactors`, `DeclarationSet` — declared criticality, replacing name matching |

Until migration completes, `backend.contracts.RiskLevel` and
`backend.approval_center.models.RiskLevel` both exist. The contracts one is
canonical; the other is retired as its consumers migrate. Do not import both
into the same module.
