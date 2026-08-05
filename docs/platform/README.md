# CortexPrime Platform

Cross-cutting technical capability with zero domain knowledge.

> **Dependency rule (Constitution S10):** `platform/` may import `contracts/`.
> It may **not** import `contexts/`, `legacy/`, `services/`, or `api/`.
> Enforced in CI, not by convention.

Platform code knows *how* to do something. It never knows *why*. A module here
that can name a detector, a mission type, or a customer has drifted into a
bounded context and belongs elsewhere.

---

## Hashing — `backend.platform.hashing`

The single source of truth for deterministic hashing. Every bounded context uses
these functions; none implements its own.

```python
from backend.platform.hashing import compute_digest, verify_digest

digest = compute_digest(contract.to_dict())        # -> PayloadDigest
ok     = verify_digest(contract.to_dict(), digest) # -> bool
```

### Why one implementation

A survey found **152 files** doing ad-hoc hashing or identifier generation.
Where two call sites hash "the same" structure by different routes, their
digests diverge and any integrity check between them **fails open** — believed,
and wrong. Constitution I2 depends on exactly this not happening.

### The canonical form

| Aspect | Rule |
|---|---|
| Object keys | Sorted by UTF-8 code point; non-string keys rejected |
| Whitespace | None |
| Booleans | Checked **before** int — `isinstance(True, int)` is True in Python |
| Integers | Decimal, no leading zeros |
| Floats | Shortest round-trip repr; `1.0` never collides with `1`; NaN/Inf rejected |
| Sequences | `list` and `tuple` both become arrays; order significant |
| Encoding | UTF-8, no BOM |

**Limitation, stated plainly.** Float formatting is CPython-specific. It is
stable across 3.x but not guaranteed identical in another language's runtime.
CortexPrime is Python-only by decision (ADR-010), so this is fine today. A
non-Python client verifying digests would need fixed decimal encoding and a
`CANONICAL_VERSION` bump.

### Domain separation

Every digest covers `b"cortexprime/digest/v1\0" + canonical_bytes(value)`.

A ruleset change yields different digests for the same value — a detectable
mismatch rather than a silent one. And a CortexPrime digest can never equal a
bare hash of the same bytes computed elsewhere, so foreign digests cannot be
replayed in.

### Versioning

`CANONICAL_VERSION` identifies the ruleset. Changing any rule above invalidates
every stored digest and requires an increment plus an ADR.

Two pinned regression tests fail if output drifts. **Updating those constants is
only correct alongside a version increment — never to make a failing test pass.**

---

## Identity — `backend.platform.identity`

```python
from backend.platform.identity import new_uuid, deterministic_id, prefixed_id

mission_id    = prefixed_id("msn")                                   # msn_01J8XK...
execution_key = deterministic_id("execution", "docker.restart", "web-01")
```

### Choosing a kind

| Function | Use when | Ordering |
|---|---|---|
| `new_uuid()` | Identity is not derivable from content | None |
| `deterministic_id(*parts)` | Two callers must independently agree — execution keys, idempotency | None |
| `prefixed_id(prefix)` | Humans will read it | Non-decreasing by time |
| `new_ulid()` | Time-sortable, no prefix needed | Non-decreasing by time |
| `monotonic_ulid()` | **Ordering is load-bearing** — audit chains | Strictly increasing |

### ULID

48-bit millisecond timestamp + 80 bits randomness, 26 characters of Crockford
Base32 (no I, L, O, U — so nobody misreads one out of a log).

Implemented rather than imported: `python-ulid` isn't installed, the spec is
short, and Constitution S11 requires a stated reason for every dependency.

**Ordering is weaker than it looks for the stateless generators.** Two ULIDs
minted in the same millisecond tie on timestamp and order arbitrarily by their
random component. That is the ULID specification's documented behavior, not a
defect. Where strict ordering matters, use `monotonic_ulid()` or a
`MonotonicUlidFactory`.

The monotonic factory survives a **backwards clock** (NTP correction, container
migration) by pinning to the last observed millisecond and continuing to
increment. Ordering is preserved; the embedded timestamp is at worst slightly
stale. The alternative — emitting a value that sorts before its predecessor —
would read as corruption in an audit chain.

### Deterministic identifiers

UUIDv5 over a fixed namespace, components joined by ASCII Unit Separator
(U+001F) which components may not contain. Without that guard `("a", "bc")` and
`("ab", "c")` would collide.

Stable across processes, machines, and releases — verified by a subprocess test,
since an idempotency key that changes between a producer and a later consumer is
not an idempotency key.

SHA-1 is present only because RFC 4122 specifies it for UUIDv5. It maps names to
identifiers; it is not a security primitive here. Content integrity uses SHA-256
and lives in `hashing`.

---

## Testing

```bash
pytest tests/platform/ --confcutdir=tests/platform     # ~2.5s, 140 tests
```

| File | Validates |
|---|---|
| `test_canonical.py` | Determinism, escaping, type distinctions, rejections |
| `test_digest.py` | Sensitivity to change, cross-process stability, domain separation |
| `test_identity.py` | Uniqueness, ordering, thread safety, clock regression |
| `test_dependency_isolation.py` | The dependency rule, statically and by subprocess |

**On `--confcutdir`.** Without it the root `tests/conftest.py` applies an
autouse fixture to every test, taking these suites from ~3 seconds to well over
ten minutes. Use the flag during development. Fixing the root conftest is
tracked separately — it means modifying a shared file, which is out of scope for
a foundation PR.

---

## Migration status

Platform is currently imported by nothing. It is consumed progressively:

| PR | Consumes |
|---|---|
| **PR-03/04** | `compute_digest`, `verify_digest` — closes the approval-binding gap (I2) |
| PR-06 | `monotonic_ulid` — audit chain sequencing (I3) |
| PR-11+ | `deterministic_id` — execution keys during state migration |

The 152 ad-hoc hashing and identifier sites are unchanged. They migrate as each
is touched. This PR supplies the destination, not the migration.
