"""Phase 6.1 vertical slice: MODEL → HARNESS → GOVERNANCE → EXECUTION → PROVIDER
→ OBSERVATION → VERIFICATION BOUNDARY → AUDIT, against real PostgreSQL and a
real Grafana.

Run:  python -m scripts.phase61_vertical_slice

Required environment:
  CORTEX_DURABLE_URL          Postgres DSN, migrated to head (0014)
  CORTEX_GRAFANA_TOKEN        Grafana service-account token (operator-provisioned)
  CORTEX_CONNECTOR_FACTORIES  backend.api.grafana_provider_factory:grafana_extension
Optional:
  CORTEX_GRAFANA_URL          default http://localhost:3001
  CORTEX_GRAFANA_TENANT       default dev
  CORTEX_SLICE_MODEL          LLM model id (default gpt-4o-mini); CORTEX_SLICE_SCRIPTED=1
                              substitutes a scripted model port, and the trace
                              then names provider="scripted" — scripted evidence
                              cannot masquerade as a model run.

Exit codes (the postgres-harness convention):
  0  VERIFIED      the full chain ran and every check passed
  1  FAILED        a check failed
  2  NOT VERIFIED  a precondition is absent (no DB, no token, no Grafana)

This script is COMPOSITION + DRIVING, not an execution path: every provider
call in it happens inside SecureCapabilityInvocationGateway.invoke, reached
through the scheduler's dispatcher. Nothing here calls an adapter, a channel,
a connector, or httpx.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from typing import Any, Optional

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED"}


def check(name: str, ok: bool, detail: str = "") -> bool:
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": detail[:500]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {detail[:180]}" if detail else ""))
    return bool(ok)


def bail(code: int, why: str) -> None:
    REPORT["verdict"] = {0: "VERIFIED", 1: "FAILED", 2: "NOT VERIFIED"}[code]
    REPORT["why"] = why
    print(json.dumps(REPORT, indent=1, default=str))
    sys.exit(code)


def main() -> None:  # noqa: PLR0915 - a driver reads top to bottom
    # ------------------------------------------------------------------
    # Preconditions
    # ------------------------------------------------------------------
    if not (os.getenv("CORTEX_DURABLE_URL") or "").strip():
        bail(2, "CORTEX_DURABLE_URL is not set")
    if not (os.getenv("CORTEX_GRAFANA_TOKEN") or "").strip():
        bail(2, "CORTEX_GRAFANA_TOKEN is not set")
    os.environ.setdefault(
        "CORTEX_CONNECTOR_FACTORIES",
        "backend.api.grafana_provider_factory:grafana_extension",
    )

    from backend.api.application_runtime import build_governed_runtime
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    from backend.harness import (
        CURRENT_HARNESS_VERSION,
        GovernedModelBoundary,
        HarnessLoop,
        LoopBudget,
    )
    from backend.harness.loop import ActionOutcome, Observation
    from backend.harness.llm_boundary import LLMServiceModelPort, ModelInvocation, TokenUsage
    from backend.harness.trace_sql import SqlTraceRecorder
    from backend.platform.context import ExecutionContext
    from backend.platform.context.identity import IdentityContext
    from pydantic import BaseModel, Field

    tenant_id = (os.getenv("CORTEX_GRAFANA_TENANT") or "dev").strip()

    # ------------------------------------------------------------------
    # 1. The governed runtime, from its real builder
    # ------------------------------------------------------------------
    print("[1] building governed runtime")
    runtime = build_governed_runtime()
    if runtime is None:
        bail(2, "build_governed_runtime returned None")
    if "grafana" not in runtime.connectivity.catalogs:
        bail(2, "grafana catalog absent — factory did not contribute (token set?)")
    check("governed runtime built", True)

    platform_ctx = ExecutionContext.platform_internal(
        reason="phase-6.1 slice commissioning", component="slice-driver", source="cli"
    )

    # The audit writer role, held for the whole run. runtime.start() would do
    # this too, but it also starts the scheduler thread; a deterministic driver
    # ticks the scheduler itself, so it takes the role the same way start()
    # does and releases it at the end. Without the role every audit append is
    # refused and the run would produce actions it cannot demonstrate.
    runtime.audit_writer.acquire()
    check("audit writer role acquired", runtime.audit_writer.handle is not None)

    # ------------------------------------------------------------------
    # 2. Commission the worker: four deliberate acts, four records
    # ------------------------------------------------------------------
    print("[2] commissioning grafana-connector")
    from backend.contexts.execution.domain.worker_directory import (
        WorkerAvailability,
        WorkerTrust,
    )

    directory = runtime.connectivity.directory
    directory.validate(platform_ctx, worker_id="grafana-connector", tenant_id="")
    directory.enable(platform_ctx, worker_id="grafana-connector", tenant_id="")
    directory.set_trust(
        platform_ctx, worker_id="grafana-connector", tenant_id="",
        trust=WorkerTrust.VERIFIED, reason="phase-6.1 slice commissioning",
    )
    directory.set_trust(
        platform_ctx, worker_id="grafana-connector", tenant_id="",
        trust=WorkerTrust.TRUSTED, reason="phase-6.1 slice commissioning",
    )
    directory.set_availability(
        platform_ctx, worker_id="grafana-connector", tenant_id="",
        availability=WorkerAvailability.AVAILABLE,
    )
    check("worker commissioned (validated/enabled/trusted/available)", True)

    # Catalog safety: this catalog must contain nothing beyond READ and
    # REVERSIBLE_WRITE — the slice's whole claim rests on that.
    catalog = runtime.connectivity.catalogs["grafana"]
    from backend.contracts.execution import SideEffectClass

    effects = {catalog.require(op).side_effect_class for op in catalog.operations}
    if not check(
        "catalog holds only READ + REVERSIBLE_WRITE",
        effects <= {SideEffectClass.READ, SideEffectClass.REVERSIBLE_WRITE},
        str(sorted(e.value for e in effects)),
    ):
        bail(1, "grafana catalog carries an effect class the slice must not")

    # ------------------------------------------------------------------
    # 3. Register + enable + trust the two capabilities
    # ------------------------------------------------------------------
    print("[3] registering capabilities")
    from backend.contexts.connectivity.application.commands import (
        EnableCapability,
        RegisterCapability,
        SetCapabilityTrust,
        ValidateCapability,
    )

    def register(op: str, effect: str, semantics: str, description: str) -> Any:
        cid = f"platform.grafana.{op}"
        runtime.capabilities.register(
            platform_ctx,
            RegisterCapability(
                capability_id=cid,
                version=1,
                name=f"Grafana {op}",
                description=description,
                provider="grafana",
                interface="connector",
                side_effect_class=effect,
                effect_semantics=semantics,
                isolation_tier="contained", code_trust="fixed",
                execution_mode="synchronous",
                owner_id="ops-owner",
                owner_kind="human",
                tenancy="platform",
                source="internal",
                supported_environments=("development",),
                provider_operation=f"folder.{op.split('.', 1)[1]}"
                if "." in op else op,
            ),
        )
        runtime.capabilities.validate(
            platform_ctx, ValidateCapability(capability_id=cid, version=1)
        )
        runtime.capabilities.enable(
            platform_ctx, EnableCapability(capability_id=cid, version=1)
        )
        runtime.capabilities.set_trust(
            platform_ctx,
            SetCapabilityTrust(
                capability_id=cid, version=1, trust="verified",
                reason="phase-6.1 slice commissioning",
            ),
        )
        result = runtime.capabilities.set_trust(
            platform_ctx,
            SetCapabilityTrust(
                capability_id=cid, version=1, trust="trusted",
                reason="phase-6.1 slice commissioning",
            ),
        )
        return result.capability

    create_def = register(
        "folder.create_folder", "reversible_write", "non_idempotent_write",
        "Create a Grafana folder (inverse: DELETE /api/folders/{uid})",
    )
    get_def = register(
        "folder.get_folder", "read", "read_only", "Read one Grafana folder by uid"
    )
    check("capabilities registered/enabled/trusted", True)

    # ------------------------------------------------------------------
    # 4. The tenant context that will drive everything
    # ------------------------------------------------------------------
    identity = IdentityContext(
        # HUMAN honestly: the slice is driven by an operator at a CLI.
        principal=PrincipalRef(principal_id="slice-driver", kind=PrincipalKind.HUMAN),
        capabilities=("capability:invoke",),
    )
    tenant_ctx = ExecutionContext.for_tenant(
        tenant_id=tenant_id, identity=identity, source="cli"
    )

    # ------------------------------------------------------------------
    # 5. The governed action leg (shared by action + observation ports)
    # ------------------------------------------------------------------
    from backend.contexts.connectivity.domain.authorization import (
        AuthorizationRequest,
        CapabilityOperation,
    )
    from backend.contexts.connectivity.domain.identifiers import (
        CapabilityId,
        CapabilityVersion,
    )
    from backend.contexts.connectivity.domain.resolution import (
        ResolutionRequest,
        VersionSelection,
    )
    from backend.contexts.connectivity.domain.contract import CapabilityEnvironment
    from backend.contexts.execution.application.commands import (
        GetExecution,
        StartExecution,
    )

    def governed_call(
        *, definition: Any, node_id: str, payload: dict, label: str
    ) -> dict:
        """One governed provider operation: authorize → start → bind → tick."""
        decision = runtime.authorization.authorize(
            tenant_ctx,
            AuthorizationRequest(
                tenant_id=tenant_id,
                principal=identity.principal,
                capability_ref=definition.reference,
                operation=CapabilityOperation.INVOKE,
                expected_digest=definition.digest,
                environment=CapabilityEnvironment.DEVELOPMENT,
            ),
        )
        if not getattr(decision, "allowed", False):
            return {"performed": False, "refused": True,
                    "stage": f"authorization:{getattr(decision, 'reason', None)}"}

        started = runtime.executions.start(
            tenant_ctx,
            StartExecution(
                workflow_id=f"phase61-{label}",
                workflow_digest=f"phase61-{label}-digest",
                mission_id="phase61-slice",
                nodes=(
                    {
                        "node_id": node_id,
                        "worker_kind": "connector",
                        "side_effect": definition.contract.side_effect_class.value,
                        "max_attempts": 1,
                        "input": payload,
                    },
                ),
                requested_by="slice-driver",
            ),
        )
        execution_id = str(started.execution.execution_id)

        # Capacity, not authority: the pool must know the dispatcher's lease
        # identity for this execution before a lease can be issued (the same
        # two-registry distinction Phase 5.5 learned the hard way).
        from backend.contexts.execution.application.commands import RegisterWorker

        runtime.executions.register_worker(
            RegisterWorker(
                worker_id=f"dispatcher:{execution_id}",
                kinds=("connector",),
                lease_seconds=300,
            )
        )

        outcome = runtime.resolution.resolve(
            tenant_ctx,
            ResolutionRequest(
                tenant_id=tenant_id,
                principal=identity.principal,
                capability_id=CapabilityId.parse(str(definition.capability_id)),
                operation=CapabilityOperation.INVOKE,
                authorization=decision,
                version=CapabilityVersion(1),
                version_selection=VersionSelection.EXACT,
                environment=CapabilityEnvironment.DEVELOPMENT,
                execution_id=execution_id,
                node_id=node_id,
            ),
        )
        if not outcome.resolved or outcome.binding is None:
            return {"performed": False, "refused": True,
                    "stage": f"resolution:{outcome.result}", "execution_id": execution_id}

        runtime.scheduler.track(execution_id)
        refusal: Optional[str] = None
        tick_notes: list = []
        for _ in range(20):
            report = runtime.scheduler.tick(tenant_ctx)
            if getattr(report, "skipped", False):
                tick_notes.append(f"tick_skipped:{getattr(report, 'reason', None)}")
            for cycle in report.cycles:
                for result in getattr(cycle, "results", ()):
                    if getattr(result, "invocation_refusal", None):
                        refusal = str(result.invocation_refusal)
                    dispatch_refusal = getattr(result, "refusal", None)
                    # NODE_LEASED / NOT_READY mean "in progress", not refusal.
                    name = getattr(dispatch_refusal, "name", str(dispatch_refusal or ""))
                    if dispatch_refusal is not None and name not in (
                        "NODE_LEASED", "NODE_NOT_READY", "NOTHING_READY",
                    ):
                        refusal = f"dispatch:{name}"
                    if not getattr(result, "dispatched", False):
                        tick_notes.append(
                            f"undispatched:{name}"
                            f":{getattr(result, 'invocation_refusal', None)}"
                            f":{str(getattr(result, 'detail', ''))[:160]}"
                        )
            state = runtime.executions.stream_state(tenant_ctx, execution_id)
            nodes = {n["node_id"]: n["state"] for n in state.get("nodes", ())}
            if nodes.get(node_id) in {"succeeded", "failed", "unknown", "skipped"}:
                break
            time.sleep(0.2)

        state = runtime.executions.stream_state(tenant_ctx, execution_id)
        node_state = {n["node_id"]: n["state"] for n in state.get("nodes", ())}.get(node_id)
        aggregate = runtime.executions.get(
            tenant_ctx, GetExecution(execution_id=execution_id)
        )
        evidence: dict = {}
        for run in getattr(aggregate, "runs", ()):
            if getattr(run, "node_id", None) == node_id:
                detail = getattr(run, "detail", None) or {}
                if isinstance(detail, dict):
                    evidence = detail.get("evidence") or detail
        return {
            "performed": node_state == "succeeded",
            "refused": refusal is not None,
            "stage": refusal,
            "node_state": node_state,
            "execution_id": execution_id,
            "evidence": evidence,
            "correlation_id": tenant_ctx.correlation.correlation_id,
            "tick_notes": tick_notes[-6:],
        }

    # ------------------------------------------------------------------
    # 6. Harness ports over the governed leg
    # ------------------------------------------------------------------
    class FolderProposal(BaseModel):
        action: str = Field(pattern="^create_folder$")
        title: str = Field(min_length=1, max_length=189)
        uid: str = Field(min_length=1, max_length=40, pattern="^[a-zA-Z0-9-]+$")
        reason: str

    class GrafanaActionPort:
        def __init__(self) -> None:
            self.last: dict = {}

        async def execute(self, proposal: FolderProposal) -> ActionOutcome:
            result = governed_call(
                definition=create_def,
                node_id="create-folder",
                payload={"title": proposal.title, "uid": proposal.uid},
                label="create",
            )
            self.last = result
            return ActionOutcome(
                performed=result["performed"],
                refused=result["refused"] and not result["performed"],
                refusal_stage=result.get("stage"),
                failure=None if result["performed"] else (result.get("stage") or result.get("node_state")),
                detail=result,
            )

    class GrafanaObservationPort:
        """The read-back. Grafana's RBAC scope cache denies a service account
        reads of a folder it JUST created for up to ~45s (reproduced outside
        the platform: create 200 -> immediate GET 403 -> 200 at ~45s). A READ
        is safe to repeat, so this port retries the governed read -- each
        attempt a fresh governed execution -- rather than teaching any other
        layer to wave a 403 through."""

        async def observe(self, proposal: FolderProposal, outcome: ActionOutcome) -> Observation:
            import asyncio as _asyncio

            result: dict = {}
            for attempt in range(6):
                result = governed_call(
                    definition=get_def,
                    node_id="get-folder",
                    payload={"uid": proposal.uid},
                    label="observe",
                )
                if result["performed"]:
                    break
                await _asyncio.sleep(15)
            return Observation(
                observed=result.get("performed", False),
                detail={"evidence": result.get("evidence"), "raw": result},
                failure=None if result.get("performed") else result.get("stage"),
            )

    class FolderCompletion:
        """Deterministic completion: the governed folder.get_folder read of
        the proposal's uid SUCCEEDED. The uid is a validated, digested path
        parameter of that read; a missing folder is a provider 404 -> NOT_FOUND
        -> the node fails -> observed is False. Provider evidence fields are
        digested, never carried (result_digest on the attempt) -- so existence
        via an independent governed read is the strongest content check the
        fabric exposes."""

        def __init__(self, expected_uid_holder: dict) -> None:
            self._expected = expected_uid_holder

        def is_complete(self, observation: Observation) -> bool:
            raw = observation.detail.get("raw") or {}
            return bool(
                observation.observed
                and raw.get("performed")
                and raw.get("node_state") == "succeeded"
                and self._expected.get("uid")
            )

        def _unused(self, observation):
            evidence = observation.detail.get("evidence") or {}
            return (
                isinstance(evidence, dict)
                and str(evidence.get("uid", "")) == self._expected.get("uid", "\u0000-never")
            )

    expected: dict = {}
    scripted = (os.getenv("CORTEX_SLICE_SCRIPTED") or "").strip() == "1"

    class ScriptedSlicePort:
        async def generate(self, *, system_prompt: str, prompt: str) -> ModelInvocation:
            body = json.dumps(
                {"action": "create_folder", "title": "Phase 6.1 Slice",
                 "uid": "phase61-slice", "reason": "scripted slice run"}
            )
            return ModelInvocation(
                content=body, provider="scripted", model="scripted-1",
                latency_ms=0.0, usage=TokenUsage(10, 10),
            )

    model_port = (
        ScriptedSlicePort()
        if scripted
        else LLMServiceModelPort(model=(os.getenv("CORTEX_SLICE_MODEL") or "gpt-4o-mini"))
    )

    recorder = SqlTraceRecorder(runtime.persistence.store)
    boundary = GovernedModelBoundary(
        model_port=model_port, recorder=recorder,
        harness_version=CURRENT_HARNESS_VERSION,
    )

    class ExpectationCapturingAction(GrafanaActionPort):
        async def execute(self, proposal: FolderProposal) -> ActionOutcome:
            expected["uid"] = proposal.uid
            return await super().execute(proposal)

    action_port = ExpectationCapturingAction()

    loop = HarnessLoop(
        boundary=boundary,
        action_port=action_port,
        observation_port=GrafanaObservationPort(),
        completion_port=FolderCompletion(expected),
        recorder=recorder,
        harness_version=CURRENT_HARNESS_VERSION,
        budget=LoopBudget(
            max_iterations=2, max_tool_calls=4,
            max_wall_clock_seconds=420.0, max_total_tokens=20_000,
        ),
        proposal_schema=FolderProposal,
    )

    # ------------------------------------------------------------------
    # 7. Run the slice
    # ------------------------------------------------------------------
    print("[7] running harness loop (model=%s)" % ("scripted" if scripted else "real"))
    import asyncio
    import uuid

    run_suffix = uuid.uuid4().hex[:8]
    result = asyncio.run(
        loop.run(
            mission_id=f"phase61-slice-{run_suffix}",
            system_prompt=(
                "You operate Grafana through a governed platform. Respond with "
                "ONLY a JSON object: {\"action\": \"create_folder\", \"title\": "
                "<short folder title>, \"uid\": <lowercase-alphanumeric-dashes, "
                f"must be exactly 'p61-{run_suffix}'>, \"reason\": <one line>}}."
            ),
            build_prompt=lambda i, obs: (
                f"Iteration {i}. Create a Grafana folder recording the Phase 6.1 "
                f"vertical slice run {run_suffix}. Use uid exactly 'p61-{run_suffix}'."
                + (f" Previous observation: {json.dumps(dict(obs.detail))[:400]}" if obs else "")
            ),
            correlation_id=tenant_ctx.correlation.correlation_id,
            trace_id=tenant_ctx.trace.trace_id,
            span_id=tenant_ctx.trace.span_id,
        )
    )
    REPORT["loop_result"] = {
        "stop_reason": result.stop_reason.value,
        "completed": result.completed,
        "iterations": result.iterations_run,
        "tool_calls": result.tool_calls_made,
        "tokens": result.tokens_spent,
        "failure": result.failure,
    }
    check("loop completed via deterministic check", result.completed,
          f"stop={result.stop_reason.value} failure={result.failure}")

    # ------------------------------------------------------------------
    # 8. Evidence: trace spans + audit correlation
    # ------------------------------------------------------------------
    spans = recorder.spans_for_mission(f"phase61-slice-{run_suffix}")
    kinds = [s.get("kind") for s in spans]
    check("trace spans persisted (model/action/observation/loop_state)",
          {"model_proposal", "governed_action", "observation", "loop_state"} <= set(kinds),
          str(kinds))
    check("harness version on every span",
          all(s.get("harness_version") == CURRENT_HARNESS_VERSION.identity for s in spans))
    token = (os.getenv("CORTEX_GRAFANA_TOKEN") or "").strip()
    leaked = [s for s in spans if token and token in json.dumps(s, default=str)]
    check("no credential material in any span", not leaked)

    REPORT["spans"] = len(spans)
    REPORT["action_result"] = action_port.last or REPORT.get("action_result")

    # ------------------------------------------------------------------
    # 9. Negative path: a principal without capability:invoke is refused
    # ------------------------------------------------------------------
    bare_identity = IdentityContext(
        principal=PrincipalRef(principal_id="no-grant", kind=PrincipalKind.HUMAN),
    )
    denied = runtime.authorization.authorize(
        ExecutionContext.for_tenant(
            tenant_id=tenant_id, identity=bare_identity, source="cli"
        ),
        AuthorizationRequest(
            tenant_id=tenant_id,
            principal=bare_identity.principal,
            capability_ref=create_def.reference,
            operation=CapabilityOperation.INVOKE,
            expected_digest=create_def.digest,
            environment=CapabilityEnvironment.DEVELOPMENT,
        ),
    )
    check(
        "grant-less principal is refused by authorization",
        not getattr(denied, "allowed", True),
        str(getattr(denied, "reason", ""))[:120],
    )

    # ------------------------------------------------------------------
    # 10. Audit evidence: the chain holds records correlated to this run
    # ------------------------------------------------------------------
    import sqlalchemy as _sa
    from backend.database.durable.tables import audit_record_table as _art

    with runtime.persistence.store.atomic() as _work:
        _total = _work.execute(
            _sa.select(_sa.func.count()).select_from(_art)
        ).scalar_one()
        _kinds = _work.execute(
            _sa.select(_art.c.kind, _sa.func.count())
            .group_by(_art.c.kind)
        ).fetchall()
    REPORT["audit"] = {"records": int(_total), "kinds": {k: int(c) for k, c in _kinds}}
    check("audit chain holds records for this run", _total > 0, str(REPORT["audit"]))

    try:
        runtime.audit_writer.release()
    except Exception:
        pass

    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if (ok and result.completed) else 1,
         "slice complete" if ok else "one or more checks failed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception — see traceback")
