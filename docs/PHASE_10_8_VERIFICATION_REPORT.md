# Phase 10.8 — Governed Grant Issuance
## Verification Report

**Verdict: VERIFIED — 118/118.**

Harness: `scripts/phase108_governed_grant_issuance_harness.py`
Infrastructure: real k3d (`k3d-cortex-p99b-server-0`, v1.35.5+k3s1), real
PostgreSQL (`cortex_p108`), real Redis, real tenant store, real OS process
death. No mocks, no in-memory substitutes, no simulated refusals.

Every claim is labelled. Discovery answers came from **calling** the
administrative APIs, not from reading them — the brief required this, and it
was right to: source inspection would have missed that ten escalating grant
strings are accepted and stored.

---

## 1. Section results

| § | Area | Checks |
|---|---|---|
| A | Composition — one authority model, one new table | 6 [VERIFIED] |
| B | Issuer authority — no existing role assumed sufficient | 6 [VERIFIED] |
| C | Self-grant | 3 [VERIFIED] |
| D | A grant may not exceed the capability | 4 [VERIFIED] |
| E | Non-escalation | 5 [VERIFIED] |
| F | Tenant isolation | 7 [VERIFIED] |
| G | Wildcards — none introduced, none honoured | 7 [VERIFIED] |
| H | Grant identity and tamper detection | 8 [VERIFIED] |
| I | Revocation | 6 [VERIFIED] |
| J | Audit | 6 [VERIFIED] |
| K | Concurrency | 3 [VERIFIED] |
| L | Positive matrix | 6 [VERIFIED] |
| M | Negative matrix | 46 [VERIFIED] |
| N | Crash / restart | 4 [VERIFIED] |
| O | Measured latency | 1 [VERIFIED] |
| | **Total** | **118 / 118** |

Nine personas, each holding a **real** grant — for something that is not this
act: ISSUER · ISSUER_NARROW · ISSUER_WIDE · SUBJECT · SUBJECT_TWO ·
APPROVER_ONLY · EXECUTOR_ONLY · PLAIN · OTHER_ISSUER.

---

## 2. Discovery — the state before this phase [VERIFIED by probe]

| Question | Answer |
|---|---|
| Who can issue | Anyone holding the singleton. **No route, no product surface.** Only harness scripts called it |
| Issuer identity | **No parameter existed** — an absent concept, not a weak check |
| Tenant authoritative | **Yes** — cross-tenant granting already refused |
| Capability authoritative | **No** — never validated or parsed |
| Scope authoritative | **No** — only `":" in permission` |
| Durable | **No** — `data/tenants/tenant_users.json`, and `data/` is gitignored |
| Versioned | **No** |
| Revocable | Yes |
| Audited | **No** |
| Mutable | **Yes** — editing the file silently replaced authority |
| Wildcards | **Stored yes, honoured no** |
| Can exceed capability scope | **Yes at issuance** |
| Can grant autonomy | No — see §7 for the corrected reason |

**The finding in one sentence:** authority enforcement was governed; authority
creation was an unvalidated, unattributed, unaudited write to an untracked
JSON file.

## 3. Issuer authority [VERIFIED]

Part C forbade assuming any existing role suffices, and none does:

| Case | Result |
|---|---|
| B1 plain member | 403 `no_issuer_authority` |
| B2 holder of APPROVE authority | 403 — using a capability is not delegating it |
| B3 holder of EXECUTE authority | 403 |
| B4 **tenant OWNER** | 403 — no role is automatically an issuer |
| B5 correctly scoped issuer | 201 |
| B6 | the issued grant names the issuer's own grant as its warrant |

## 4. Self-grant and separation of duties [VERIFIED]

Approve and execute self-grants both refuse with `self_grant_refused` — named,
not a flat "forbidden". C3 proves the comparison is on the **authoritative
identity**: a different casing of the same address is still the same human.

## 5. Scope, non-escalation and delegation [VERIFIED]

| Case | Result |
|---|---|
| D1 environment the capability does not support | 403 `environment_not_supported_by_capability` |
| D2 ceiling above the capability's declared risk | 403 `risk_ceiling_exceeds_capability` |
| D3 uncommissioned capability | 403 |
| D4 subject not a member of this tenant | 403 `subject_not_a_member` |
| E1 issuer whose own ceiling is lower | 403 `risk_exceeds_grant_ceiling` |
| E2 issuing an `issue` grant | 422 — unrepresentable in the request model |
| E3 issuing `autonomy` | 422 |
| E4 **the same, called below the route** | refused `authority_type_not_issuable` |

E4 matters: the control is **not** in the HTTP model alone. Calling
`issue_grant()` directly with `authority_type="issue"` is still refused, so
transitive delegation cannot be reached by bypassing the route.

**D1 and D2 required a dedicated persona.** With only the normally-scoped
issuer, the issuer's own scope refuses first and the capability bound is never
reached — the checks would have passed while proving nothing. `ISSUER_WIDE`
holds issue-authority *wider* than the capability, which is what makes Part E's
control reachable and therefore real.

## 6. Tenant isolation [VERIFIED]

Cross-tenant issuance refuses; tenant B's listing contains only tenant B's
grants; cross-tenant revocation returns **404, not 403** — a tenant may not
learn that another tenant's grant exists. Both tenants hold real grants, so
this is isolation rather than emptiness.

Client-supplied authority fields: `tenant_id`, `issuer`, `actor`, `role`,
`issued_by`, `digest`, `capability_version` in the **body** are **422 —
rejected, not ignored**. In query parameters and headers they are inert: the
grant still lands in the session's tenant.

## 7. Wildcards, and a corrected claim [VERIFIED]

Wildcard capability (`*`, `all`, `any`), wildcard environment, and
comma-separated capability injection are all refused **at issuance**. A
wildcard row planted directly in the store still authorizes nothing, because
the matcher compares by strict equality.

**A correction that matters.** An earlier version of check A6 asserted that
`parse_grants(action="autonomy")` returns nothing. It passed — and it was
wrong. The parser is *generic over the action*, and
`autonomy:remediation:capability=x,environment=y` parses perfectly well; the
original probe merely used a malformed string (`autonomy:A4`). The Phase 10.8
discovery document initially recorded this accidental pass as a verified
property.

The real protection was added in response: an **allow-list in
`durable_grants`** — only `approve`, `execute` and `issue` are authorities the
platform will resolve at all. A6 now asserts that allow-list *and* the parser's
genuine behaviour, rather than a comfortable misreading of it. [VERIFIED]

## 8. Grant identity and tamper detection [VERIFIED]

`digest` covers tenant, subject, authority type, capability, capability
version, environment and risk ceiling — and excludes issuer, timestamps and
revocation, because those describe the *provenance* of authority, not the
authority itself. No token, secret, credential or DSN can appear: there is no
such field on a grant.

Direct **PostgreSQL** edits of the environment, risk ceiling, authority type,
subject and capability each stop the grant authorizing. Detection is reported,
not merely effected: the row is logged as an integrity finding, recorded in
`tampered_grants`, and the product projects `intact: false`.

Honest boundary: this is **detection, not prevention**. A database
administrator can also recompute a digest. The claim is that *silent* mutation
becomes impossible. [VERIFIED as stated]

## 9. Revocation [VERIFIED]

| Case | Result |
|---|---|
| I2 caller with no issue-authority | 403 |
| I3 the issuer revokes what they issued | 200 |
| I4 authority gone on the **next** check, same token | `no_approver_authority` |
| I5 revoking twice | 409, not a silent overwrite of who revoked first |
| I6 revoked grants still **listed**, with `revoked_by` | present |

**A defect found and fixed here.** Revocation initially resolved the revoker's
authority at ceiling `critical`, so an issuer with a `high` ceiling could
create a grant and then be unable to revoke it — stranding authority nobody
could retract. Revocation is now bounded by capability and environment but
**not** by risk: revoking only removes authority, so the ceiling comparison
bought no safety and cost a one-way door.

## 10. Audit [VERIFIED]

Issuing and revoking each append to the existing hash-chained ledger
(`11 → 13` in the recorded run). Both use `IDENTITY_EVENT` — the existing kind
meaning "authentication, authorization, or credential lifecycle", which is
`is_security_relevant` and therefore never sampled or truncated. **No new audit
kind was invented.**

Each record names issuer, subject, tenant, authority type, capability,
capability version, environment, risk ceiling and digest. No token, credential
or DSN appears. **A read writes no event** — looking is not an action.

**A defect found here.** The first run recorded zero audit events: `_audit`
imported `TenantScope` from the wrong module and the failure was swallowed. It
was found because the swallow **logs loudly** rather than passing silently —
the log was the reason the bug was visible at all. Fixed; the write is now
proven, not assumed.

## 11. Concurrency and replay [VERIFIED — with an explicit non-claim]

```
concurrent_issue_codes  = [201, 201]
concurrent_issue_rows   = 2   (sharing ONE digest)
concurrent_revoke_codes = [200, 409]
```

Reported verbatim. Two concurrent issuances of the same authority produced two
rows — **two legitimate attributed acts conferring identical power**, which is
why the digest is the same and why no uniqueness was invented.
**Exactly-once is NOT claimed.** Two concurrent revocations: one wins on the
conditional `UPDATE`, the other is told it already happened. No lock.

Replay of an issuance produces a second attributed act, not a resurrection of
the first.

## 12. Negative matrix — 43 cases, 0 provider writes [VERIFIED]

| Stopping layer | Cases |
|---|---|
| governance | 21 |
| grant_scope | 11 |
| issuer_authority | 6 |
| authentication | 3 |
| grant_state | 2 |

Covers anonymous and forged issuers; body/query/header/path tenant and identity;
cross-tenant issuance and revocation; self-grant of both authorities; approve↔
execute escalation; autonomy and transitive-delegation escalation; wildcards
and comma injection; altered capability version; unknown capability; direct DB
mutation; replay; unauthorized revocation; and absent worker, provider,
autonomy, grant-mutation and grant-deletion routes.

`N35b` proves the grant every revocation negative targeted is **still live** —
the matrix did not pass by destroying its own fixture.

## 13. Crash / restart [VERIFIED]

A **real separate OS process** reads the same grants, the same issuer
attribution and the same 64-character digest. Authority survives restart
because it lives in PostgreSQL. No partial grant was created: every live row
still matches its own digest.

## 14. Performance [VERIFIED — measured, not estimated]

| Path | p50 | p95 |
|---|---|---|
| Grant validation (authorization after grant) | 18.1 ms | 35.8 ms |
| Grant issuance | 119.1 ms | 170.2 ms |
| Unauthorized issuance (refusal) | 16.4 ms | 21.4 ms |
| Grant list | 19.2 ms | 21.2 ms |

Refusal is again the fastest write path. No index was added beyond the
tenant-first index the table ships with; none was justified by measurement.

## 15. Architecture, regression and frontend [VERIFIED]

- `tests/architecture` — **155 passed**. **No new fitness rule was added.**
  Per Part Z, none is warranted: the grant subsystem executes no provider,
  invokes no worker, reveals no credential, creates no World/Observation/
  Outcome/Verification state, and cannot grant or modify autonomy. All
  authority logic lives in `backend/auth/`, already fenced by
  `BND-AUTH-CANNOT-EXECUTE` from Phase 10.5.
- Backend regression — **2819 passed**. Combined **2974**, the pre-phase
  baseline exactly.
- **Phase 10.7's harness re-run on the new substrate — 155/155, unchanged.**
  This is the load-bearing regression: moving authority from a JSON file to
  PostgreSQL altered nothing about what 10.7 proves.
- Frontend — **121/121**, unchanged. No frontend work was done (§17).

## 16. Stop conditions — none triggered [VERIFIED]

| Stop condition | Result |
|---|---|
| Self-grant possible | No — refused, on authoritative identity |
| Cross-tenant grant possible | No |
| Transitive delegation possible | No — `issue` is not issuable, at route *and* service |
| Grant can widen capability scope | No — environment and risk both bounded |
| Grant can grant autonomy | No — allow-list at issuance *and* at resolution |
| Revoked authority remains usable | No — next check, nothing cached |
| Client controls authority / tenant / scope | No — 422 in body, inert elsewhere |
| Grant mutation silently changes authority | No — digest recomputed on every read |
| Second authority / approval engine / gateway | None — one resolver, asserted by AST scan |
| Model influences grant authorization | No model is reachable from this path |
| New capability commissioned | No — still exactly one |
| Exactly-once claimed | **Not claimed** |

The one stop condition that *did* fire is Part AB's: a new table was necessary.
It was stopped on and documented with its rationale in the implementation map
**before** any code was written.

## 17. Known limitations [NOT VERIFIED / DEFERRED]

1. **Bootstrap is out-of-band.** No system issues its own root of trust.
   `bootstrap_grant` is unreachable from any route and attributes itself to
   `bootstrap`, but anything that can call it can already write to the
   database. [Stated, not solved]
2. **Grant expiration does not exist.** [DEFERRED] Grants carry no
   `expires_at`. Part L forbids inventing one for this phase and forbids
   hidden timeouts; a standing grant is revoked, never aged out.
3. **Tamper detection is detection, not prevention.** A database administrator
   can recompute a digest. Silent mutation is what becomes impossible.
4. **Revocation is authoritative-on-next-check, not instantaneous.**
5. **Revoking one grant is not revoking an authority.** If two grants confer
   the same power, revoking one leaves the other. The harness found this the
   hard way. There is no "revoke all authority for this subject" operation.
   [NOT VERIFIED as safe operationally — named as a trap]
6. **No frontend.** [DEFERRED] Part AC applies only if discovery proves a
   surface is necessary; the DoD does not require one and half-building a
   grant-management UI would be worse than none. Grants are issued through the
   API by an authenticated human.
7. **Membership still lives in the JSON file.** Only *authority* moved. Who is
   a member of a tenant remains file-backed and gitignored — a separate,
   larger problem, named rather than silently absorbed.
8. **Version pinning has no re-issue tooling.** A capability version bump
   invalidates grants fail-closed but with no migration path (inherited from
   10.7).
9. **One commissioned capability.** All of this is proven against
   `rollout_restart@1`.

---

## 18. Defects found and fixed during this phase

1. **The audit write was silently failing.** `_audit` imported `TenantScope`
   from `backend.contracts.identity`, which does not define it. Zero events
   were written. Found because the exception handler **logs loudly** instead of
   passing — the deliberate noise was the only reason the bug was visible.
2. **Revocation was harder than issuance.** It resolved the revoker at ceiling
   `critical`, so an issuer with a `high` ceiling could create a grant and
   never take it back. Fixed by bounding revocation on capability and
   environment only, with the reasoning recorded in the code.
3. **My own A6 assertion passed for the wrong reason** (§7). The parser is
   action-generic; the probe string was malformed. Corrected, and the missing
   protection — an authority allow-list at resolution — was *added*, not
   assumed.
4. **Two checks were unreachable and would have proven nothing.** D1 and D2
   were refused by the issuer's own scope before the capability bound was ever
   evaluated. A wider-scoped persona was added so Part E's control actually
   executes.
5. **Two probes passed by masking.** The tamper and revocation checks ran
   against subjects holding several grants, so a second grant conferring the
   same authority hid the effect. Both now start from a known-clean subject —
   which is also how limitation 5 above was discovered.

As in every prior phase, the verification checks were wrong more often than the
production code was, and each was fixed to be stronger rather than removed.
