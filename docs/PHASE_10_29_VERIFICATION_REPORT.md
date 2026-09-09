# Phase 10.29 — Verification Report: retirement of the organizational directory and the enterprise-operations surface

- **Parent:** `34b1892` — Phase 10.28 · **ADR:** ADR-119 · **Map:** `docs/PHASE_10_29_IMPLEMENTATION_MAP.md`
- **Date:** 2026-09-09

Labels: `[VERIFIED]` executed and observed · `[NOT VERIFIED]` inferred · `[DEFERRED]` · `[STOP]`.

## 1. Summary

| Claim | Result |
|---|---|
| Preflight matched the brief | `[VERIFIED]` HEAD `34b1892` ← `e464c22`, branch `phase-1-foundation`, tree clean, next ADR 119 |
| Final inventory found no consumer beyond 10.27/10.28 | `[VERIFIED]` whole-repository grep; three prose mentions only (map §"Final implementation inventory") |
| Database gate: no table, no data, no FK, no migration | `[VERIFIED]` 18 databases inspected by SQL; 0 tables, 0 FK references, 0 migrations creating them → **no migration required** |
| No production import of retired modules remains | `[VERIFIED]` post-change grep over `backend`, `frontend`, `tests`, `scripts`, `helm`, `infra`, `.github`: none (only the retirement notes in the inventory/registry comments) |
| Retired routes unmounted; retained routes intact | `[VERIFIED]` real `register_all_routers` on a bare app: 1,030 routes; retired paths **absent**; `/api/api/operations/diagnostics`, `/api/mission-replay/{execution_id}`, `/api/enterprise-replay/events/{execution_id}`, `/api/security/organizations` present; retired `availability` keys gone, `diagnostics: True` |
| Every remaining `*_routes` module imports | `[VERIFIED]` all |
| `create_all` census | `[VERIFIED]` metadata 31 tables, head DB 57, **in-metadata-not-migrated: `[]`** (was the seven) |
| Fresh DB | `[VERIFIED]` 25 migrations, 57 tables, head `0025_mission_replay_events`, retired tables 0, `mission_replay_events` present |
| Existing head DB | `[VERIFIED]` `cortex_p1014_legacy`: 0 migrations ran; full schema fingerprint `5b62dfb5…` and row-count fingerprint identical before/after; identical to the fresh DB's schema fingerprint |
| Alembic | `[VERIFIED]` autogenerate on fresh head: **86 operations, byte-identical to the 10.22 inventory**, 0 retired-table mentions; `alembic check` still red on exactly those — **not claimed clean**; 0 temp revisions left |
| Targeted tests | `[VERIFIED]` `test_api_endpoints.py` + `test_enterprise_operations.py` + `test_tenancy_guard.py`: 52 passed, 3 failed — all three are in the 10.22 baseline failure list (`test_response_model_or_dict_return`, `test_list_endpoint_has_pagination[mission_library_routes.py]`, `[approval_center_routes.py]`), unrelated to this phase; the ratchet's stale-entry test passes on this tree |
| Frontend | `[VERIFIED]` vitest `enterprise-platform.test.tsx` 14/14 (renders the Operations Center landing page); no tracked file links to the retired pages; `tsc --noEmit` excluding `.next`: 11 errors, all in four files this phase did not touch (`dashboard-panel.tsx`, `RuntimeHealth.tsx`, `e2e/health.spec.ts`, `playwright.config.ts`; `git diff HEAD` on them empty) — pre-existing; the only errors naming the removed pages were in Next's gitignored `.next/**/validator.ts` route-type cache, which regenerates on the next build |
| GA backup/DR untouched | `[VERIFIED]` `git diff HEAD` on `scripts/backup-database.sh`, `helm/cortexprime/templates/backup-cronjob.yaml`, `helm/cortexprime/values.yaml`: empty; script `bash -n` ok; `values.yaml:245 backup:` block present |
| Architecture / regression / harnesses | `[VERIFIED]` architecture **155 passed** (unchanged); regression **75 failed / 6744 passed / 36 skipped / 58 xfailed / 24 errors** — the `FAILED` set is identical to the 10.26 re-run (0 new, 0 gone) and contains 0 new entries vs the 10.22 baseline; the passed count fell by exactly 38 = the tests removed with the retired surface (collect-only: the two edited modules went 74 → 36); harnesses 10.7 **155/155** · 10.8 **118/118** · 10.9 **107/107** · 10.10 **107/107** (solo) · 10.11 **68/68** (solo) · 10.13 **60/60** · 10.14 **53/53** — all VERIFIED; 10.19 readiness `ready: true`; 10.20 write-path + 10.26 replay tests 7 passed (§3) |
| Mission runtime | `[VERIFIED]` mission admission/execution unchanged: the 10.28 census found no caller of `should_block_new_mission()` in any commit; the architecture gate (155) and the governed execution harnesses (10.7 scoped execution authority, 10.11 retirement regression incl. mission-runtime paths) pass at full counts after removal; no mission-runtime file changed (`git diff` on `backend/mission`, `backend/execution`, `backend/services/mission_runtime.py`: empty) |
| Governance | `[VERIFIED]` by re-executing the governed harnesses: 10.7 scoped authority/execution (155), 10.8 grant issuance (118), 10.9 membership (107), 10.10 tenant records (107), 10.11 TenantManager retirement (68), 10.13 V1 reads retirement (60), 10.14 IAM retirement (53) — tenant, membership, authority, approval, execution, assurance, worker, connector, credential and audit paths at full counts; no file under `backend/auth`, `contexts`, `platform` (other than the ratchet list), `contracts`, `assurance`, `world` changed; governed table fingerprints identical |
| Provider writes | **0** from this phase; harness-reported writes `[0,1]` on 10.7 only (its one standing rollout restart, as in every prior run), 0 on every other harness and every negative-matrix case |

## 2. Method notes

- Route mounting was verified by calling the real `register_all_routers`
  against a bare `FastAPI()` and inspecting `app.routes`, not by reading the
  registry.
- The existing-DB check computes one md5 over every column, index definition
  and constraint in `public` plus one over every table's row count, before and
  after `alembic upgrade head`.
- The autogenerate comparison uses the same extraction as Phases 10.22–10.26
  (upgrade `op.` lines of a temporary revision, moved out of `versions/`).
- Regression uses the 10.22 collection scope (`python -m pytest tests/ -q
  --tb=no -rf -p no:cacheprovider`); counts are compared list-to-list against
  the 10.22 baseline failure set.

## 3. Gates

| Gate | Result |
|---|---|
| Architecture (`tests/architecture`) | **155 passed** (203 s) — the ratchet test passes with the three deleted repository names removed; no assertion weakened |
| Regression (10.22 scope: `pytest tests/ -q --tb=no -rf -p no:cacheprovider`) | **75 failed / 6744 passed / 36 skipped / 58 xfailed / 24 errors** (1143 s). `FAILED` list: identical to the 10.26 re-run (0 new / 0 gone); vs the 10.22 baseline 0 new, 1 gone (the known non-reproducible `test_invoke_reaches_the_provider_exactly_once…`). Passed 6782 → 6744 = −38, exactly the tests removed: collect-only on `test_enterprise_operations.py` + `test_api_endpoints.py` at HEAD vs now = 74 → 36 (32 retired-service tests, 3 `test_route_file_uses_auth` and 3 `test_list_endpoint_has_pagination` parametrizations for the deleted route files). The three targeted failures seen during development (`test_response_model_or_dict_return`, pagination for `mission_library_routes.py` / `approval_center_routes.py`) are baseline failures |
| Harness chain (serial) | 10.7 155/155 (rc 0) · 10.8 118/118 (rc 0) · 10.9 107/107 VERIFIED but rc 124 · 10.10 crashed · 10.11 timed out · 10.13 60/60 VERIFIED, hung · 10.14 53/53 VERIFIED, hung |
| What happened in the chain | Another Claude Code session on this machine ran a full `pytest tests` (pid 14180, parent bash marker `claude-13e6-cwd`, 16:51 to about 19:20) concurrently — not this session's process and not touched. Under that contention 10.9, 10.13 and 10.14 each printed their complete report and JSON verdict and then hung on shutdown (the recurring TestClient post-report hang); Git's `timeout.exe` cannot kill a Windows child, so the chain wedged on 10.13 until I killed my own hung processes. Their verdicts were flushed before the hang and are taken as evidence; each hung process was killed only after that |
| 10.10 crash — a real finding of this phase | `scripts/phase1010_tenant_record_harness.py:312` read `backend/database/models/organization.py` by path string to prove ADR-103's "organizations is a different concept" (A5); the inventory grep matched names, not paths, so it was missed. The check was adapted, not removed: when the model file is absent it now proves the stronger property by execution — `importlib.util.find_spec("backend.database.models.organization") is None` and no tracked backend file declares `__tablename__ = "organizations"`; a missing file alone is not accepted. The original AST branch stays for trees that still carry the model. A path-string grep over `backend`, `scripts`, `tests`, `frontend`, `helm`, `infra`, `.github` for every retired basename found no other path reference |
| 10.10 / 10.11 solo | A first solo attempt through a Python runner crashed both in the negative matrix (`load_verify_locations` `FileNotFoundError`): the runner's parsing of `.phase99b.env` differed from the chain's shell sourcing — my defect, not the harnesses'. Re-run through the same shell sourcing every prior chain used, serially, contention gone: 10.10 **107/107 VERIFIED** (A5 `[OK]` via the retired-model branch, writes 0), 10.11 **68/68 VERIFIED** (writes 0). 10.10 hung post-report and was killed after its verdict flushed |
| 10.19 readiness | `cortex_p1014_legacy` → `ready: true`, `missing_tables: []` |
| 10.20 write-path + 10.26 replay | 7 passed |
| Frontend | vitest `enterprise-platform.test.tsx` 14/14; tsc: see §1 |

## 4. Data integrity

No table dropped (none existed). No row written or deleted on any database
except the disposable `cortex_p1029_fresh` (created, migrated, inspected,
dropped). `cortex_p1014_legacy` unchanged (fingerprints). No Redis key
written. No provider call.

## 5. Known limitations

- `tsc` on the frontend is not clean at HEAD either (11 pre-existing errors
  in four untouched files); this phase neither fixed nor worsened it.
- `.next/` route-type cache in the developer's checkout still lists the two
  removed pages until the next `next build`/`dev` regenerates it; it is
  gitignored build output.
- `docs/RELEASE_READINESS.md:59`, `backend/database/durable/tables.py:1086`
  and `versions/0022_tenant_record.py:16` still mention `organization_routes`
  / `OrganizationModel` in prose; historical, deliberately untouched.
