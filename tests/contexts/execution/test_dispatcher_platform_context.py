"""Phase 11.3 (ADR-123 F-9): a platform-internal context leases nothing.

The gateway's tenancy stage refuses every invocation a platform-internal
context makes. The dispatcher used to take the node's lease first and ask the
gateway second, and a refused-before-run node cannot be reclaimed while its
lease is live -- so the runtime's own scheduler loop, ticking with the platform
context, leased tenant reads out from under the tenant's reader and left them
LEASED for the whole lease term. Measured on the live cluster (eight of one
hundred and twenty-six governed reads in one run). The dispatcher now refuses
such a context before the lease, and the node stays free for the context that
can invoke it."""
from __future__ import annotations

from backend.contexts.execution import (
    ExecutionService, GetExecution, InMemoryExecutionRepository, RegisterWorker, StartExecution,
)
from backend.contexts.execution.application.dispatcher import ExecutionDispatcher
from backend.platform.context import ExecutionContext
from tests.contexts.execution.test_invocation_gateway_matrix import Fixture


class Bindings:
    def __init__(self, binding):
        self.binding = binding

    def binding_for(self, context, execution_id, node_id):
        return self.binding


class Requests:
    """Builds nothing: the platform path must never reach it; the tenant path
    reaches it and gets ``None`` (request unavailable), which proves the lease
    was taken on that path and released again."""

    def __init__(self):
        self.built = 0

    def build(self, *args, **kwargs):
        self.built += 1
        return None


def _stack():
    fx = Fixture()
    service = ExecutionService(repository=InMemoryExecutionRepository())
    started = service.start(fx.context, StartExecution(
        workflow_id="observe-read", workflow_digest="observe-read-digest", mission_id="world-observation",
        nodes=({"node_id": "node-1", "worker_kind": "connector", "side_effect": "read",
                "max_attempts": 1, "input": {}},)))
    execution_id = str(started.execution.execution_id)
    # the dispatcher leases as ``dispatcher:<execution id>`` (one definition, two readers)
    service.register_worker(RegisterWorker(worker_id=f"dispatcher:{execution_id}", kinds=("connector",),
                                           lease_seconds=300))
    requests = Requests()
    dispatcher = ExecutionDispatcher(executions=service, gateway=fx.gateway,
                                     bindings=Bindings(fx.binding), requests=requests)
    return fx, service, execution_id, requests, dispatcher


def test_a_platform_internal_context_is_refused_before_any_lease_is_taken():
    fx, service, execution_id, requests, dispatcher = _stack()
    platform = ExecutionContext.platform_internal(reason="scheduler loop", component="tests", source="pytest")
    report = dispatcher.cycle(platform, execution_id)
    assert report.dispatched == 0
    assert [r.invocation_refusal for r in report.results] == ["tenant_unknown"]
    assert requests.built == 0, "no request was built, so no gateway call and no lease"
    run = service.get(fx.context, GetExecution(execution_id=execution_id)).run_for("node-1")
    assert run.lease is None and run.state.value != "leased"
    assert run.attempt_count == 0


def test_the_tenant_context_still_reaches_the_lease():
    fx, service, execution_id, requests, dispatcher = _stack()
    report = dispatcher.cycle(fx.context, execution_id)
    assert report.dispatched == 0
    assert [r.invocation_refusal for r in report.results] == ["invocation_request_unavailable"]
    assert requests.built == 1, "the tenant path went past the tenancy check to the request factory"
