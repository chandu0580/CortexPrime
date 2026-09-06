# Phase 10.8 — Governed Grant Issuance
## Implementation Map (written BEFORE any code)

Every answer below was obtained by **calling the real administrative APIs** in
a probe, not by reading source. Where a claim rests on source alone it says so.

---

## 1. Discovery — `grant_permission` / `revoke_permission`

```
grant_permission (tenant_id: str, user_id: str, permission: str) -> bool
revoke_permission(tenant_id: str, user_id: str, permission: str) -> bool
```

| Question | Answer | Basis |
|---|---|---|
| Who can call them | Any code holding the singleton. **No route, no product surface, no CLI.** Only harness scripts call them | [VERIFIED] grep: only `scripts/phase10{5,6,7}_*.py` |
| How issuer identity is resolved | **It is not. There is no issuer parameter.** An issuer is unrepresentable | [VERIFIED] signature probe |
| How tenant is resolved | Caller-supplied `tenant_id`, used to scope the membership lookup | [VERIFIED] |
| Is tenant authoritative | **Yes for lookup** — a user in tenant B cannot be granted via tenant A (returns `False`) | [VERIFIED] probe step 4 |
| Is capability authoritative | **No.** The capability is never validated, or even parsed | [VERIFIED] |
| Is scope authoritative | **No.** Only validation is `":" in permission` | [VERIFIED] |
| Are grants durable | **No.** `data/tenants/tenant_users.json`, and `data/` is **gitignored** | [VERIFIED] `git check-ignore` |
| Are grants versioned | **No** | [VERIFIED] `TenantUser` has 7 fields, none of them a version |
| Are grants revocable | **Yes**, immediately, written through | [VERIFIED] |
| Are grants audited | **No.** Granting writes two JSON files and emits nothing | [VERIFIED] probe step 7 |
| Are grants mutable | **Yes.** Editing the JSON silently replaces authority | [VERIFIED] probe step 8 |
| Can grants be self-issued | The question does not typecheck — there is no issuer | [VERIFIED] |
| Can grants cross tenants | **No** | [VERIFIED] |
| Can grants be wildcarded | **Stored yes, honoured no** — see §2 | [VERIFIED] |
| Can grants exceed capability scope | **Yes at issuance** — `environment=production` is accepted for a capability that supports only `development` | [VERIFIED] probe 2 + `supported_environments=frozenset({environment})` |
| Can grants exceed risk | **Yes at issuance** — `max_risk=critical` is accepted unconditionally | [VERIFIED] |
| Can grants confer approval authority | Yes | [VERIFIED] |
| Can grants confer execution authority | Yes | [VERIFIED] |
| Can grants confer autonomy | **No** — but see the correction below | [CORRECTED — the original probe passed for the wrong reason] |
| Can grants confer role permissions | No — `role` is a separate field these functions never touch | [VERIFIED] |
| Can a grant grant itself | No issuer concept, so no | [VERIFIED] |
| Can a grant modify another grant | Only by direct file edit | [VERIFIED] |

### The finding in one sentence

**Authority enforcement is governed; authority creation is an unvalidated,
unattributed, unaudited write to an untracked JSON file.**

## 2. Wildcards are already inert — at enforcement only [VERIFIED]

The grammar is `action:resource:capability=<ref>,environment=<env>[,max_risk=<l>]`
— **key=value**, not positional. Matching is strict equality.

| Stored grant | Stored? | Honoured? | Why |
|---|---|---|---|
| `approve:remediation:capability=*,environment=*` | yes | **no** | `"*" != "platform...rollout_restart@1"` |
| `approve:remediation:capability=all,environment=all` | yes | **no** | same |
| `godmode:everything` | yes | **no** | action is not `approve`/`execute` |
| `autonomy:A4` | yes | **no** | no `remediation` segment — see the correction below |
| `approve:remediation` (10.5 bare form) | yes | **no** | `grant_is_not_scoped` |
| `approve:...,environment=production,max_risk=critical` | yes | **YES** | nothing bounds a grant to the capability |

### Correction to the autonomy row (made during implementation)

The probe above concluded that `parse_grants` has no autonomy action. That
was **wrong, and it passed anyway**: `parse_grants` is generic over the
action, and `autonomy:remediation:capability=x,environment=y` parses
perfectly well. The probe used `autonomy:A4`, which fails only because it has
no `remediation` resource segment.

Autonomy is genuinely not conferrable, but not for the reason recorded here.
The real protection was **added** in response: an allow-list in
`durable_grants` means only `approve`, `execute` and `issue` are authorities
the platform will resolve at all, so a row naming anything else authorizes
nothing however it was written. See verification report §7.

Part F is therefore already satisfied **at enforcement** and violated **at
issuance**. No wildcard support will be introduced.

## 3. STOP — a new table is genuinely necessary (Part AB / Part B)

Per Part AB I stopped and am explaining before implementing.

**Reuse was evaluated and refused for each existing candidate:**

1. **`TenantUser.permissions`** — a `List[str]` in a gitignored JSON file. It
   cannot carry issuer, issued_at, revoked_at, digest or an approval reference.
   Encoding those into the grant string would leave the record equally editable
   and equally undetectable. **Insufficient.**

2. **`cp_delegation`** — structurally almost perfect (tenant, subject, scope,
   issuer, issued_at, expires_at, revoked_at, digest, approval evidence). It is
   refused **on security grounds, not aesthetics**: `DurableDelegationAuthority.
   delegation_for()` reads this table to permit **on-behalf-of invocation** at
   the execution gateway ([VERIFIED] `delegation_composition.py:211`). Writing
   authority grants into it would silently convert every grant into an
   identity-borrowing permission. Its workflow also refuses
   `actor == delegated` as `self_delegation`, which is precisely the shape an
   authority grant has. **Reuse would be a privilege escalation.**

3. **`cp_approval`** — binds a capability invocation via
   `canonical_approval_digest`. A grant is not an invocation; fitting one in
   would produce a digest covering a fiction. This is the codebase's own
   established reasoning — `delegation.py` refuses to reuse `ApprovalArtifact`
   for exactly this reason. **Semantically wrong.**

4. **The audit ledger (`cp_audit_record`)** — append-only evidence of what
   happened, not a store of what is currently true. Making it authoritative
   would turn revocation into an event replay and would overload its meaning
   the same way (2) overloads delegation. **Rejected**; it will carry the
   issuance *events*, which is what it is for.

**Decision:** one new table, `cp_authority_grant`, migration `0020`. It is the
durable home the authority of Phases 10.5–10.7 has never had.

## 4. Issuer authority (Part C) — there is no existing one [VERIFIED]

The existing model offers `role` (member/admin/owner) and `permissions`.
Neither means "may issue grants", and Part C forbids assuming owner suffices.
Phase 10.5 already established that **a tenant owner is not an approver**; by
the same reasoning an owner is not an issuer.

**Decision:** a third action in the *same* grammar and the *same* parser —
`issue`, beside `approve` and `execute`. This is exactly how 10.7 added
`execute` beside `approve`. **No new authority model, no second engine, one
`resolve_scoped_authority`.**

**Bootstrap is a real limitation, stated plainly:** the first `issue:` grant
must be provisioned out-of-band. No system can issue its own root of trust.
This will be documented, not hidden.

## 5. Does issuance require human approval? (Part I) — explicit decision

**No, and here is the rationale rather than an inherited "admin can do
anything".**

Grant issuance *is* an administrative authority change, so Part I's first test
is met. But the smallest existing approval mechanism (`cp_approval`) binds an
approval to a capability invocation through `canonical_approval_digest`. A
grant is not an invocation. Manufacturing one would produce an approval whose
digest covers a fiction — the precise failure mode `delegation.py` already
refuses.

Issuance is therefore governed by **issuer authority + separation of duties +
scope bounding + durable audit**, not by a second approval workflow. Building
one would be the "second approval engine" the stop conditions forbid.

## 6. Design — what will be built

**One new table** (`cp_authority_grant`, migration 0020):

| Column | Why |
|---|---|
| `grant_id` PK | identity |
| `tenant_id` | isolation, tenant-first index |
| `subject_principal_id` | who holds it |
| `authority_type` | `approve` / `execute` — **never merged** (Part D) |
| `capability_ref`, `capability_version` | version-pinned, as 10.7 established |
| `environment`, `max_risk` | scope |
| `issued_by`, `issued_at` | attribution — the thing that does not exist today |
| `revoked_at`, `revoked_by`, `revocation_reason` | governed revocation |
| `digest` | stable identity over every authority-bearing field |

**`backend/auth/grants.py`** — issuance and revocation, in the module already
fenced by `BND-AUTH-CANNOT-EXECUTE`. Validation order:

```
authenticated issuer → issuer authority (issue: scope) → subject is a real
member of THIS tenant → separation of duties (issuer != subject) →
authority_type is approve|execute (never issue, never autonomy) →
capability exists in the catalog → environment ∈ supported_environments →
risk ceiling ≤ capability's implied risk → non-escalation (issued scope ⊆
issuer scope) → durable write → IDENTITY_EVENT audit
```

**No new audit kind.** `AuditEventKind.IDENTITY_EVENT` already means
"authentication, authorization, or credential lifecycle" and is
`is_security_relevant`, so it can never be sampled away. [VERIFIED]

**Non-escalation rules (Parts O, P):**
- an issuer may issue only `approve` or `execute` — **never `issue`**, so
  delegation of delegation is structurally impossible and transitive
  escalation cannot arise;
- holding `approve` does not permit issuing `execute`, and vice versa —
  issuance authority comes only from an `issue:` grant;
- `autonomy` is not an issuable authority type and the parser has no such
  action.

**Enforcement change:** `resolve_scoped_authority` reads durable grants first.
A grant present only in the JSON file, with no durable row, no longer confers
authority — which is how direct tampering is **detected** rather than merely
deplored (Part M). This is a deliberate, fail-closed breaking change of the
same kind 10.7 made to bare grants.

**Frontend (Part AC):** only if discovery of the product surface proves one is
needed. Grant issuance today has no UI and none is required by the DoD;
expected outcome is **DEFERRED**, stated rather than half-built.

**Expiration (Part L):** `cp_authority_grant` will carry no `expires_at`.
Grants today have no expiry and Part L forbids inventing one for this phase.
**DEFERRED**, documented.

## 7. What will NOT be built

No `GrantPolicyEngine2`, no second approval engine, no second gateway, no
wildcard support, no numeric trust score, no autonomy grant path, no new
capability, no change to `rollout_restart`, no expiry invention, and no claim
of exactly-once.

## 8. Risks accepted

1. Moving the authority substrate under 10.5–10.7 is the highest-risk change in
   Phase 10. The full 10.5/10.6/10.7 harnesses will be re-run, not just 10.8's.
2. Bootstrap grants must be provisioned out-of-band (§4).
3. The JSON membership store remains the source of *membership*; only
   *authority* moves. Membership durability is a separate, larger problem and
   will be named as a limitation, not silently absorbed.
