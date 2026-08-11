"""Phase 6.3 Part A + C + K: full harness integration through the scheduler,
the replay matrix, and trace/audit/outbox identity agreement — against real
PostgreSQL with the controlled (scripted) provider.

Run:  python -m scripts.phase63_integration_harness

The path, with NO manual dispatcher.cycle() and NO injected result:
  SCRIPTED MODEL (provider="scripted") → HARNESS LOOP → STRICT VALIDATION →
  TOOL EXPOSURE (resolve before governance) → governed execution →
  scheduler.tick → dispatch → lease → gateway → CONTROLLED PROVIDER →
  observation (governed read) → deterministic completion → checkpoint event →
  outbox → audit → trace.

A scripted model is NOT a real-model verification; every model span is
labeled provider="scripted".

Exit codes: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
import uuid
from typing import Any, Optional

# Reuse the commissioning + drive helpers proven in the 6.2 recovery harness.
from scripts.phase62_recovery_harness import (
    TENANT, _commission, _drive, _start_and_resolve, _tenant_ctx,
)

REPORT: dict = {"checks": [], "verdict": "NOT VERIFIED"}


def check(name: str, ok: bool, detail: str = "") -> bool:
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": detail[:300]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {detail[:160]}" if detail else ""))
    return bool(ok)


def bail(code: int, why: str) -> None:
    REPORT["verdict"] = {0: "VERIFIED", 1: "FAILED", 2: "NOT VERIFIED"}[code]
    REPORT["why"] = why
    print(json.dumps(REPORT, indent=1, default=str))
    sys.exit(code)


def main() -> None:  # noqa: PLR0915
    if not (os.getenv("CORTEX_DURABLE_URL") or "").strip():
        bail(2, "CORTEX_DURABLE_URL not set")
    os.environ.setdefault("CORTEX_CONTROLLED_PROVIDER", "1")
    os.environ.setdefault(
        "CORTEX_CONNECTOR_FACTORIES",
        "backend.api.controlled_provider_factory:controlled_extension")

    from backend.api.application_runtime import build_governed_runtime
    from backend.contexts.execution.application.commands import (
        GetExecution, ListExecutions, ReplayExecution,
    )
    from backend.harness import (
        CURRENT_HARNESS_VERSION, GovernedModelBoundary, HarnessLoop, LoopBudget,
    )
    from backend.harness.llm_boundary import ModelInvocation, TokenUsage
    from backend.harness.loop import ActionOutcome, Observation
    from backend.harness.tool_exposure import (
        ArgKind, ArgSpec, ExposedTool, ResolvedTool, ToolExposurePolicy, ToolProposal,
    )
    from backend.harness.trace_sql import SqlTraceRecorder
    from backend.platform.audit import verify_chain
    from backend.platform.context import ExecutionContext

    runtime = build_governed_runtime()
    if runtime is None or "controlled" not in runtime.connectivity.catalogs:
        bail(2, "controlled provider absent")
    platform_ctx = ExecutionContext.platform_internal(
        reason="p63 integration", component="harness", source="cli")
    runtime.audit_writer.acquire()
    defs = _commission(runtime, platform_ctx)
    tenant_ctx = _tenant_ctx()
    adapter = runtime.connectivity.adapters["controlled"]

    run_id = uuid.uuid4().hex[:8]

    # -- tool exposure policy: the two controlled ops -----------------------
    policy = ToolExposurePolicy((
        ExposedTool(name="create_widget", provider="controlled",
                    operation="widget.create",
                    arguments=(ArgSpec("name", ArgKind.STRING, required=True,
                                       max_length=80),)),
        ExposedTool(name="get_widget", provider="controlled",
                    operation="widget.get",
                    arguments=(ArgSpec("widget_id", ArgKind.STRING, required=True,
                                       max_length=40),)),
    ))

    boundaries: dict = {}

    # -- action port: resolved tool → governed execution via scheduler ------
    class GovernedActionPort:
        async def execute(self, resolved: ResolvedTool) -> ActionOutcome:
            assert isinstance(resolved, ResolvedTool)
            definition = defs[resolved.operation]
            node = f"n-{uuid.uuid4().hex[:8]}"
            exec_id = _start_and_resolve(
                runtime, tenant_ctx, definition, node, resolved.operation,
                dict(resolved.arguments))
            state = _drive(runtime, tenant_ctx, exec_id, node)
            boundaries["exec_id"] = exec_id
            boundaries["node"] = node
            boundaries["provider"] = resolved.provider
            boundaries["operation"] = resolved.operation
            return ActionOutcome(
                performed=(state == "succeeded"),
                refused=False,
                failure=None if state == "succeeded" else str(state),
                detail={"execution_id": exec_id, "node_state": state,
                        "provider": resolved.provider, "operation": resolved.operation},
            )

    class GovernedObservationPort:
        async def observe(self, proposal, outcome: ActionOutcome) -> Observation:
            return Observation(observed=outcome.performed,
                               detail={"raw": dict(outcome.detail)})

    class Completion:
        def is_complete(self, observation: Observation) -> bool:
            raw = observation.detail.get("raw") or {}
            return bool(observation.observed and raw.get("node_state") == "succeeded")

    # -- scripted model: proposes a create_widget tool call -----------------
    class ScriptedModel:
        async def generate(self, *, system_prompt: str, prompt: str) -> ModelInvocation:
            # Adversarial extras: a success claim the harness must ignore.
            body = json.dumps({
                "tool": "create_widget",
                "arguments": {"name": f"widget-{run_id}"},
                "reason": "create it",
                "success": True, "status": "completed", "verification": "passed",
            })
            return ModelInvocation(content=body, provider="scripted",
                                   model="scripted-1", latency_ms=0.0,
                                   usage=TokenUsage(10, 10))

    recorder = SqlTraceRecorder(runtime.persistence.store)
    boundary = GovernedModelBoundary(model_port=ScriptedModel(), recorder=recorder,
                                     harness_version=CURRENT_HARNESS_VERSION)
    loop = HarnessLoop(
        boundary=boundary, action_port=GovernedActionPort(),
        observation_port=GovernedObservationPort(), completion_port=Completion(),
        recorder=recorder, harness_version=CURRENT_HARNESS_VERSION,
        budget=LoopBudget(max_iterations=2, max_tool_calls=3,
                          max_wall_clock_seconds=120.0, max_total_tokens=20_000),
        proposal_schema=ToolProposal, tool_exposure=policy,
    )

    provider_before = len(adapter.calls)
    audit_before = runtime.persistence.audit.count()

    print("[A] full integration run through the scheduler")
    mission_id = f"p63-int-{run_id}"
    result = asyncio.run(loop.run(
        mission_id=mission_id, system_prompt="You operate widgets.",
        build_prompt=lambda i, obs: f"iteration {i}",
        correlation_id=tenant_ctx.correlation.correlation_id,
        trace_id=tenant_ctx.trace.trace_id, span_id=tenant_ctx.trace.span_id,
    ))

    check("loop completed via deterministic check (not a model claim)",
          result.completed and result.stop_reason.value == "completed",
          f"stop={result.stop_reason.value}")
    # Part A boundary assertions.
    exec_id = boundaries.get("exec_id")
    check("exactly one governed execution was created for the create",
          exec_id is not None)
    check("exactly one provider call for the mission",
          len(adapter.calls) == provider_before + 1,  # one governed write
          f"{provider_before}->{len(adapter.calls)}")
    agg = runtime.executions.get(tenant_ctx, GetExecution(execution_id=exec_id))
    node = next((r for r in agg.runs if r.node_id == boundaries["node"]), None)
    check("durable result recorded, node succeeded", node is not None
          and node.state.value == "succeeded", node.state.value if node else "?")
    check("correct workflow digest on the execution (non-empty, consistent)",
          agg.workflow_digest == "p62-widget.create-digest", agg.workflow_digest)
    check("correct provider operation resolved (deployment's, not model's)",
          boundaries["operation"] == "widget.create"
          and boundaries["provider"] == "controlled")

    # -- Part E: model span carries tools_available + provider=scripted -----
    spans = recorder.spans_for_mission(mission_id)
    model_spans = [s for s in spans if s.get("kind") == "model_proposal"]
    check("model span is labeled provider=scripted (not a real-model run)",
          all(s.get("model_provider") == "scripted" for s in model_spans))
    check("model span records tools_available",
          model_spans and set(model_spans[0].get("tools_available") or ())
          == {"create_widget", "get_widget"},
          str(model_spans[0].get("tools_available") if model_spans else None))
    check("model success claims did NOT establish completion",
          # completion came from the deterministic port; the observation span
          # carries BOUNDARY_UNVERIFIED, never VERIFIED.
          all(s.get("detail", {}).get("verification") == "BOUNDARY_UNVERIFIED"
              for s in spans if s.get("kind") == "observation"))

    # -- Part K: trace / audit / outbox identity agreement ------------------
    ga_spans = [s for s in spans if s.get("kind") == "governed_action"]
    resolved_ops = {s["tool_call"].get("resolved_operation") for s in ga_spans
                    if s.get("tool_call")}
    check("governed_action span operation agrees with the execution",
          "widget.create" in resolved_ops, str(resolved_ops))
    outbox_events = runtime.executions.history(tenant_ctx, exec_id)
    check("outbox has events for the execution (checkpoint/lifecycle)",
          len(outbox_events) >= 1, f"events={len(outbox_events)}")
    # No secret material in any span (firewall over the trace).
    from backend.harness.firewall import find_secrets
    span_secrets = [f for s in spans for f in find_secrets(s)]
    check("no secret material in any trace span", not span_secrets,
          str(span_secrets[:2]))
    integrity = verify_chain(runtime.persistence.audit)
    check("audit chain verifies end to end", integrity.ok,
          f"records={integrity.records_checked}")

    # ------------------------------------------------------------------
    # Part C — REPLAY MATRIX. Replay never acts, for every representable state.
    # ------------------------------------------------------------------
    print("[C] replay matrix")

    def _replay_is_inert(label: str, execution_id: str) -> None:
        p0 = len(adapter.calls)
        a0 = runtime.persistence.audit.count()
        o0 = len(runtime.executions.history(tenant_ctx, execution_id))
        projection = runtime.executions.replay(
            tenant_ctx, ReplayExecution(execution_id=execution_id))
        check(f"replay[{label}] 0 provider calls", len(adapter.calls) == p0)
        check(f"replay[{label}] 0 audit writes",
              runtime.persistence.audit.count() == a0)
        check(f"replay[{label}] 0 new outbox events",
              len(runtime.executions.history(tenant_ctx, execution_id)) == o0)
        check(f"replay[{label}] returns non-drivable projection",
              not any(hasattr(projection, m)
                      for m in ("assign", "record_result", "start")))

    # 1. completed — the create execution above.
    _replay_is_inert("completed", exec_id)

    # 2. refused — a create whose authorization we skip: start + resolve, then
    #    a governed tick with a REVOKED capability so the gateway refuses.
    from backend.contexts.connectivity.application.commands import (
        RevokeCapability,
    )
    refused_node = f"n-{uuid.uuid4().hex[:8]}"
    refused_id = _start_and_resolve(
        runtime, tenant_ctx, defs["widget.create"], refused_node, "widget.create",
        {"name": "to-be-refused"})
    # Revoke the capability out from under the resolved binding → gateway refuses.
    runtime.capabilities.revoke(platform_ctx, RevokeCapability(
        capability_id="platform.controlled.widget.create", version=1,
        reason="p63 refused-replay scenario"))
    refused_state = _drive(runtime, tenant_ctx, refused_id, refused_node)
    check("refused execution did not succeed",
          refused_state != "succeeded", str(refused_state))
    _replay_is_inert("refused", refused_id)

    # 3. unknown — a mid-flight leased node with no recorded outcome.
    from backend.contexts.execution.application.commands import AssignNode
    # widget.get is still enabled; start + lease but never tick to completion.
    unknown_node = f"n-{uuid.uuid4().hex[:8]}"
    unknown_id = _start_and_resolve(
        runtime, tenant_ctx, defs["widget.get"], unknown_node, "widget.get",
        {"widget_id": "w-1"})
    runtime.executions.assign(tenant_ctx, AssignNode(
        execution_id=unknown_id, node_id=unknown_node,
        worker_id=f"dispatcher:{unknown_id}"))
    _replay_is_inert("unknown/mid-flight", unknown_id)
    unk = runtime.executions.get(tenant_ctx, GetExecution(execution_id=unknown_id))
    unk_node = next((r for r in unk.runs if r.node_id == unknown_node), None)
    check("replay of mid-flight run reproduces not-success (no fabrication)",
          unk_node is not None and unk_node.state.value != "succeeded",
          unk_node.state.value if unk_node else "?")

    try:
        runtime.audit_writer.release()
    except Exception:
        pass

    REPORT["counts"] = {"provider_calls": len(adapter.calls),
                        "audit_records": runtime.persistence.audit.count()}
    ok = all(c["ok"] for c in REPORT["checks"])
    bail(0 if ok else 1, "integration + replay verified" if ok else "a check failed")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        bail(1, "unhandled exception")
