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


def test_a_platform_context_becomes_the_binding_s_own_tenant_context():
    """Phase 11.3 (ADR-127 D-2, ratified 2026-09-20) refines F-9's rule.

    F-9's rule was never "platform contexts are refused"; it was **never lease
    under a context the gateway will certainly refuse**. Refusing was simply the
    only move available when the loop had no tenant context to offer.

    It has one now: the node's sealed binding names the tenant and principal the
    work was authorized for. Rebuilt from it, the context is the one the gateway
    will *not* refuse on tenancy -- so the run goes past the tenancy check to the
    request factory, exactly as a tenant caller does. F-9's guarantee is kept by
    the test below, which is the case where no such context can be built.
    """
    fx, service, execution_id, requests, dispatcher = _stack()
    platform = ExecutionContext.platform_internal(reason="scheduler loop", component="tests", source="pytest")
    report = dispatcher.cycle(platform, execution_id)
    assert [r.invocation_refusal for r in report.results] == ["invocation_request_unavailable"]
    assert requests.built == 1, "the rebuilt context went past tenancy, as a tenant's does"


def test_a_binding_that_names_no_tenant_is_still_refused_before_any_lease():
    """F-9's guarantee, unchanged: a context that cannot invoke leases nothing.

    A binding missing its tenant or principal cannot produce a dispatchable
    context, and a half-identified dispatch is not dispatched. Nothing is built,
    nothing is leased, and the node stays free for a caller that can run it --
    which is the property whose absence left eight live reads LEASED for a full
    lease term on the cluster.
    """
    # A real ``BoundCapability`` cannot be built without both -- the contract
    # refuses it ("an uncheckable binding is not authority"), which is a
    # stronger guarantee than this check. The stand-in is what the binding seam
    # could hand back from somewhere other than that type.
    class Unidentified:
        tenant_id = ""
        principal_id = ""
        execution_id = "e"
        node_id = "node-1"

    fx, service, execution_id, requests, dispatcher = _stack()
    dispatcher._bindings = Bindings(Unidentified())
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
