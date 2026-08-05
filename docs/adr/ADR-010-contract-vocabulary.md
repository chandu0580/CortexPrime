# ADR-010 — Contract Vocabulary and Event Contracts

- **Status:** Accepted
- **Date:** 2026-08-04
- **Phase:** 1 (PR-01)
- **Supersedes:** none
- **Related:** ADR-002 (Mission Model), ADR-003 (System Boundaries), ADR-005 (Execution Contract), ADR-007 (Approval Binding)

## Context

The Architecture Constitution defines nine bounded contexts that communicate by
published contract only — no shared tables, no reaching through. That rule is
unenforceable without a place for the contracts to live.

The repository currently has 698 Python files across 40+ backend packages, with
twelve modules independently defining something called a "Mission." Vocabulary
has been duplicated because there has never been a single place for it to exist.

We need a package that every context may depend on, which is only safe if that
package depends on nothing itself.

## Decision

Create `backend/contracts` as a dependency-free vocabulary package.

**1. Contracts are frozen stdlib dataclasses, not pydantic models.**

The Constitution states contracts depend on "nothing except the Python standard
library." `dataclasses` is stdlib; pydantic is not. Beyond the letter of the
rule, the reason is durability: the pydantic v1→v2 migration was a multi-quarter
cost across the ecosystem, and a vocabulary layer intended to outlive frameworks
should not inherit framework upgrade risk. The existing house style in
`backend/approval_center/models.py` already uses stdlib dataclasses with `str`
enums, so this is continuity rather than novelty.

**2. Serialization uses an explicit envelope.**

```json
{"_contract": "cortexprime.approval.artifact", "_version": 1, "...": "fields"}
```

A receiver can inspect the contract name and version before interpreting any
field. Bare field dictionaries make cross-version decoding guesswork.

**3. Contract evolution is additive-only.**

- Adding an optional field with a default: **not** a version bump.
- Removing a field, renaming a field, narrowing a type, or removing an enum
  member: **breaking**, requires `CONTRACT_VERSION + 1`.
- Decoding a payload from an *older* version succeeds — additive evolution makes
  older payloads a strict subset.
- Decoding a payload from a *newer* version raises `ContractVersionError` rather
  than silently dropping fields it does not understand.
- Unknown fields in a received payload are ignored, so a newer peer can talk to
  an older one for additive changes.

**4. Validation lives in `__post_init__`; nothing else does.**

The single permitted exception to "no logic in contracts" is validation of the
value's own invariants, plus small derived properties over the value's own
fields (`is_terminal`, `can_approve`, `links_to`). Everything else — hashing,
persistence, policy evaluation, execution — belongs to a context or to platform.

This is deliberate and load-bearing. Constitutional rules enforced at
construction cannot be forgotten by a caller, because the value will not
construct without satisfying them. Specifically:

| Rule | Enforced by |
|---|---|
| P2 — reversibility precedes action | `ExecutionContract` refuses `reversible_write` without an inverse |
| P5 — verification is independent | `VerificationResult` refuses a verifier sharing the producer's reasoning path |
| P9 — blast radius is declared | `ExecutionScope` refuses an empty resource set |
| I2 — approval binding is cryptographic | `ApprovalArtifact` carries a digest and has no caller-supplied summary field |
| I7 — experience may not authorize | `KnowledgeItem` refuses authoritative experiential knowledge |
| S4 — no state exited without a reason | `MissionTransition` requires a reason and checks legality |
| S8 — risk is declared, not inferred | `RiskFactors` has no field that accepts a resource name |
| Platform may not authorize itself | `ApprovalDecision` refuses a non-human grantor |

**5. Immutability is total.**

All contracts are `frozen=True`. Sequence fields are `tuple`, never `list`.
Opaque mappings (execution parameters, audit detail) are wrapped in
`MappingProxyType` at construction and copied from the caller's dict, so a
caller retaining a reference cannot reach in afterward.

## Alternatives Considered

**Pydantic models.** Better ergonomics, automatic validation, direct FastAPI
integration. Rejected: introduces a third-party dependency into the one package
that must have none, couples vocabulary to a framework's release cycle, and
makes the "contracts depend on nothing" rule unenforceable by static check.
The interface layer may still use pydantic for request/response translation —
that is its job.

**Protocol Buffers / Avro.** Strong schema evolution, cross-language support,
generated code. Rejected as premature: CortexPrime is Python-only, and a codegen
step adds build complexity for a benefit (polyglot clients) nobody currently
needs. Worth revisiting if a non-Python client ever appears.

**Plain dictionaries with JSON Schema.** Minimal machinery. Rejected: no type
checking at development time, no immutability, and validation that only runs
where somebody remembers to call it — which is precisely how the current
duplication arose.

**TypedDict.** Stdlib, typed, zero runtime cost. Rejected: no runtime
validation and no immutability, both of which are load-bearing here. A
`TypedDict` cannot refuse to construct.

## Consequences

**Positive**

- One place where domain vocabulary is defined, ending the twelve-Mission problem.
- Constitutional rules become unforgettable rather than documented.
- The dependency rule is statically enforceable, and is enforced in
  `tests/contracts/test_dependency_isolation.py`.
- Contract tests run in ~3 seconds with no database, no app bootstrap, no network.
- Deterministic `to_dict` output gives PR-02's canonical hashing a stable input.

**Negative**

- More boilerplate than pydantic. Each contract writes its own validation.
- Two vocabularies coexist during migration: `backend.contracts.RiskLevel` and
  the pre-existing `backend.approval_center.models.RiskLevel`. This is accepted
  for Phase 1 and resolved as contexts migrate.
- Manual `from_dict` decoding means unsupported field types fail at first
  serialization rather than at definition. Mitigated by round-trip tests over
  every registered contract.

**Neutral**

- Contracts are additive and currently imported by nothing. This PR carries no
  runtime risk.

## Compliance

Enforced automatically by `tests/contracts/test_dependency_isolation.py`:

- No contract module imports anything outside an explicit stdlib allowlist.
- Where a contract imports `backend`, it must be `backend.contracts.*`.
- Importing `backend.contracts` in a clean interpreter loads no framework
  (checked for fastapi, sqlalchemy, pydantic, starlette, redis, httpx, openai).
- Every module imports standalone in a fresh interpreter, proving no cycles.

`APPROVED_THIRD_PARTY` in that test file is deliberately empty. Adding an entry
is an architectural change and requires superseding this ADR.
