# ADR-011 — Canonical Identity and Hashing Foundation

- **Status:** Accepted
- **Date:** 2026-08-04
- **Phase:** 1 (PR-02)
- **Related:** ADR-007 (Approval Binding), ADR-010 (Contract Vocabulary)

## Context

Constitution I2 requires that the payload a human approved and the payload the
system executes are provably the same, bound by content digest. That guarantee
is only as strong as the determinism of the hashing beneath it.

A repository survey found **152 files** performing ad-hoc hashing or identifier
generation. Where two call sites hash "the same" structure by different routes —
one via `json.dumps` with default key ordering, another via `str()` — their
digests diverge and any integrity check between them silently fails open. A
security control that fails open is worse than no control, because it is
believed.

PR-02 establishes one implementation that every bounded context uses.

## Decision

Create `backend/platform/hashing` and `backend/platform/identity`.

### Location

The request specified `core/shared/{identity,hashing}/`. Two facts made that
unworkable:

1. `backend/core/shared.py` already exists with two importers. Python cannot
   resolve both `core/shared.py` and `core/shared/` — the package would shadow
   the module and break those imports.
2. Constitution S10 already designates `platform/` for exactly this content:
   "Infrastructure with zero domain knowledge: hashing, persistence, messaging,
   config, telemetry."

Same module structure, at the location the frozen architecture designates.

### Canonical form

A restricted JSON dialect, fully specified in `canonical.py`: keys sorted by
UTF-8 code point, no insignificant whitespace, `bool` checked before `int`
(because `isinstance(True, int)` is True in Python), floats emitted with a
decimal point so `1` and `1.0` cannot collide, NaN and Infinity rejected.

**Known limitation, stated rather than hidden.** Float formatting uses Python's
shortest-round-trip `repr`. That is stable across CPython 3.x but is not
guaranteed byte-identical in another language's runtime. CortexPrime is
Python-only by decision (ADR-010 rejected Protocol Buffers on those grounds), so
this is acceptable today. A non-Python client verifying digests would require a
fixed decimal encoding and a `CANONICAL_VERSION` increment.

### Domain separation

Every digest is computed over `b"cortexprime/digest/v1\0" + canonical_bytes`.

This buys two things. A ruleset change produces different digests for the same
value, making the change a detectable mismatch rather than a silent
unverifiable difference. And a CortexPrime digest can never equal a bare hash of
the same bytes computed elsewhere, so a digest from another system cannot be
replayed into ours.

### Versioning

`CANONICAL_VERSION` identifies the ruleset. Changing any canonicalization rule
invalidates every previously computed digest and requires an increment plus an
ADR. Two pinned regression tests fail loudly if the output ever drifts —
updating those constants is only correct alongside a version increment, never to
make a failing test pass.

### ULID implemented, not imported

`python-ulid` is not installed. The specification is small and fully described
in the module docstring: 48-bit millisecond timestamp, 80 bits of randomness,
26 characters of Crockford Base32. Constitution S11 requires a stated reason for
every dependency; sixty lines of tested code is the cheaper side of that trade.

Two generators, because they answer different questions:

- `new_ulid()` — stateless, independent randomness, safe from any thread.
  Ordering between two values in the same millisecond is unspecified.
- `MonotonicUlidFactory` — strictly increasing, lock-protected. Within a
  millisecond it increments the random component rather than redrawing.

A backwards clock (NTP correction, container migration) would otherwise produce
a value sorting before its predecessor — detectable corruption in an audit
chain. The factory pins to the last observed millisecond and keeps incrementing:
ordering is preserved, the embedded timestamp is at worst slightly stale.

### Three kinds of identifier

| Function | Use when |
|---|---|
| `new_uuid()` | Identity is not derivable from content |
| `deterministic_id(*parts)` | Two callers must independently agree — execution keys, idempotency |
| `prefixed_id(prefix)` | Humans will read it: time-sortable, type-tagged |
| `monotonic_ulid()` | Ordering is load-bearing — audit chains |

`deterministic_id` is UUIDv5 over a fixed namespace with components joined by
ASCII Unit Separator (U+001F), which components may not contain. Without that
guard `("a", "bc")` and `("ab", "c")` would collide.

SHA-1 appears here because RFC 4122 specifies it for UUIDv5. It is a
name-to-identifier mapping, never a security primitive — collision resistance is
not a property we depend on. Content integrity uses SHA-256 and is separate.

## Alternatives Considered

**`json.dumps(sort_keys=True)` as the canonical form.** Available immediately,
no code. Rejected: it does not reject NaN or Infinity (it emits `NaN`, which is
invalid JSON), serializes `True` and `1` distinguishably only by luck of
implementation, and its float formatting and separator defaults are not
contractually stable across releases. Determinism here must be specified, not
inherited.

**Depend on `python-ulid`.** Rejected per Constitution S11 — a dependency needs a
stated reason, and the specification is short enough that implementing it costs
less than carrying it.

**UUIDv7 instead of ULID.** Also time-sortable and now standardized. Genuinely
close. ULID chosen for its 26-character Crockford encoding, which is shorter,
case-insensitive, and excludes I/L/O/U — materially better when a human reads an
identifier out of a log or pastes it into a ticket. Worth revisiting if a
database gains native UUIDv7 support we want.

**Store digests as bare hex strings.** Rejected: the algorithm must travel with
the value, or verification has to guess and an algorithm migration becomes
silent. `PayloadDigest` already carries both.

## Consequences

**Positive**

- One implementation. The 152 ad-hoc sites now have a single destination.
- PR-04 (the critical approval-binding fix) is unblocked.
- Digests are stable across processes and `PYTHONHASHSEED` values — verified by
  a subprocess test, because a stored digest that cannot be reproduced after a
  restart is worthless.
- Zero third-party dependencies; a test asserts `APPROVED_THIRD_PARTY` stays
  empty.
- Both suites run in ~3 seconds without a database or app bootstrap.

**Negative**

- Float canonicalization is Python-specific (documented above).
- ULID is our code to maintain, including its edge cases. Mitigated by 140 tests
  covering ordering, concurrency, clock regression, and boundary values.
- Two pinned digest constants must be updated deliberately if the ruleset ever
  changes — a feature, but one that will surprise someone eventually.

**Neutral**

- The 152 existing sites are unchanged. Migration happens as each is touched;
  this PR adds the destination, not the migration.

## Compliance

Enforced by `tests/platform/test_dependency_isolation.py`:

- No platform module imports outside an explicit stdlib allowlist.
- No platform module imports `contexts/`, `legacy/`, `services/`, or `api/`.
- Importing platform in a clean interpreter loads no framework.
- Every module imports standalone in a fresh interpreter, proving no cycles.
- `APPROVED_THIRD_PARTY` is empty and asserted so.
