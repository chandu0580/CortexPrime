# Phase 10.22 — GA Integrity + ORM/Alembic Drift Reconciliation
## Implementation Map

**Written before code, as this phase family requires.**

- **Parents:** `4db52fb` (10.21 discovery, ADR-115) ← `978a32c` (10.20) ← `3069a60` (10.19)
- **ADR for this phase:** ADR-116 (highest used: 115)
- **Baseline** — the code tree is unchanged since Phase 10.20's gate run
  (10.21 was documentation-only), so that run is the pre-modification baseline:
  architecture **155 passed**; regression **75 failed / 6779 passed / 36 skipped
  / 58 xfailed / 24 errors**; autogenerate **129** operations; historical
  harnesses at full counts.

---

## Workstream A — remove the accidental v2.0 coupling

### A.1 What is coupled, proven before any edit

On a clean git worktree of `HEAD` (ignored files absent), executed:

```
backend.database.models   -> ModuleNotFoundError: backend.database.models.cost_intelligence
backend.governance.service -> ModuleNotFoundError: backend.governance.policy_engine
backend.governance.models  -> ModuleNotFoundError: backend.governance.policy_engine
backend.execution.service  -> ModuleNotFoundError: backend.governance.policy_engine
backend.mission.service    -> ModuleNotFoundError: backend.governance.policy_engine
```

Two tracked package `__init__` files re-export gitignored v2.0 files:

| Tracked file | Ignored import | Reach on a clean clone |
|---|---|---|
| `backend/database/models/__init__.py:3-16` | `models.cost_intelligence`, `models.fleet`, `models.workflow` | `alembic env.py:32`, `init_db()`, every `backend.database.models` importer, 20 tracked tests, 3 architecture tests |
| `backend/governance/__init__.py:1` | `governance.policy_engine` | `main.py:140` (guarded), `router_registry.py:99` (guarded), **`execution/service.py:26` and `mission/service.py:14` — unguarded module-level imports of `governance.models`**, which execute the package `__init__` first |

### A.2 `governance/__init__.py` — proven accidental, by the brief's four tests

| Test | Evidence |
|---|---|
| Does production require `PolicyEngine`? | **No.** A tracked-file search finds `PolicyEngine` only in `governance/__init__.py` and the ignored file itself. The tracked `governance/service.py` imports `events`, `models`, `pipeline` — not `policy_engine` |
| Part of the GA architecture? | **No.** `.gitignore:114` excludes it under *"v2.0 Phase 1 components — not part of v1.0.0 GA"* |
| Does clean checkout fail because of it? | **Yes** — four modules above, including the mission and execution services |
| Does removing the import change governed runtime behaviour? | **No.** Nothing tracked references the name; `GovernanceService`, `DecisionRequest`, `DecisionPipeline` and the routes are untouched. `backend/governance` is the V1 decision pipeline, not the Phase 10.5–10.8 authority path (`backend/auth`, `contexts/connectivity`), which does not import it |

**Decision:** remove the one import line and the one `__all__` entry. The ignored
`policy_engine.py` is not touched.

### A.3 Changes

| File | Change |
|---|---|
| `backend/database/models/__init__.py` | delete the three imports (lines 3-7, 11, 16) and the ten `__all__` entries |
| `backend/governance/__init__.py` | delete `from backend.governance.policy_engine import PolicyEngine` and `"PolicyEngine"` from `__all__` |
| `backend/platform/architecture/tenancy_rules.py` | **only if** the ratchet, run from a clean checkout, fails **solely** on `CostRepository` / `FleetRepository` / `WorkflowRepository` — names of gitignored files that are not repository content. Any other failure: STOP |

**Not changed:** any gitignored file; any migration; any table; tenant,
membership, authority, approval, execution, worker, connector, credential or
assurance code; the frontend; `env.py`.

### A.4 Verification — from a clean filesystem state

A worktree of `HEAD` with **only the edited tracked files copied in** is an
exact stand-in for the eventual commit (a worktree can only check out a commit,
and the brief requires one commit after Workstream B's discovery). After the
commit, the same probes are re-run on a worktree of the commit itself.

| # | Check |
|---|---|
| 1 | `import backend.database.models`, `backend.governance.service`, `backend.execution.service`, `backend.mission.service` — from the clean worktree |
| 2 | `alembic upgrade head` on a fresh database — from the clean worktree |
| 3 | fresh database: 56 tables, none of the ten candidates |
| 4 | existing head database (`cortex_p1014_legacy` @ `0024`): schema fingerprint identical, rows preserved |
| 5 | application boot: `import backend.main` and the ASGI app's lifespan against the fresh database, with the real Redis and a bounded timeout — from the clean worktree |
| 6 | architecture gate — from this tree **and** from the clean worktree (the ratchet scans the filesystem) |
| 7 | regression suite — from this tree, against the baseline |
| 8 | harnesses 10.7, 10.8, 10.9, 10.10, 10.11, 10.13, 10.14; 10.16 metadata probe; 10.19 readiness; 10.20 write-path test; 10.21 repository probe |
| 9 | autogenerate from the clean worktree: exact operation inventory persisted; expected 129 → 86 with the 86 byte-identical to the baseline's non-candidate set |

---

## STOP POINT

After A.4 item 9, no migration is generated. The 86 remaining operations are
classified first (Workstream B).

## Workstream B — discover and classify the remaining drift

For each of the remaining discrepancies: table, ORM definition, migration
definition, reflected schema, consumers, writers, readers, tests, public API,
governance impact, durable data, FKs, indexes, constraints, which side is
canonical, whether the difference is intentional, whether the table should
exist, whether a migration is required — and exactly one of `KEEP_MODEL`,
`KEEP_MIGRATION`, `RECONCILE`, `ADD_MIGRATION`, `RETIRE_MODEL`, `RETIRE_TABLE`,
`STOP_ARCHITECTURAL_DECISION`.

Index-only drift: per the special rule, establish whether the repository has a
single index convention. If it does not, **STOP** and document the decision —
no index migration is generated. Expression indexes the ORM cannot declare are
classified on their own evidence.

One implementation commit after A and B's discovery, unless B stops on an
architectural decision — then the commit records the discovery and stops.
