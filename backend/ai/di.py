from __future__ import annotations

import logging

from backend.ai.service import AIService
from backend.core.dependency_container import container

log = logging.getLogger(__name__)


def register_ai_services() -> None:
    propagator = None
    failure_handler = None
    client = None
    orchestrator = None
    try:
        from backend.ai.context import ContextPropagator
        propagator = ContextPropagator()
        container.register("ai_context_propagator", propagator, startup_priority=24)
    except Exception as exc:
        log.warning("ContextPropagator creation failed: %s", exc)

    try:
        from backend.ai.failure import FailureHandler
        failure_handler = FailureHandler()
        container.register("ai_failure_handler", failure_handler, startup_priority=24)
    except Exception as exc:
        log.warning("FailureHandler creation failed: %s", exc)

    try:
        from backend.ai.client import RuntimeInvocationClient
        from backend.ai.correlation import correlation_events
        client = RuntimeInvocationClient(
            failure_handler=failure_handler,
            correlator=correlation_events,
            propagator=propagator,
        )
        container.register("ai_invocation_client", client, startup_priority=24)
    except Exception as exc:
        log.warning("RuntimeInvocationClient creation failed: %s", exc)

    try:
        from backend.ai.events import ai_event_publisher
        from backend.ai.invoker import RuntimeInvoker
        from backend.ai.orchestrator import AIOrchestrator
        invoker = RuntimeInvoker(
            client=client,
            propagator=propagator,
            failure_handler=failure_handler,
        )
        orchestrator = AIOrchestrator(
            events=ai_event_publisher,
            propagator=propagator,
            client=client,
            failure_handler=failure_handler,
            invoker=invoker,
        )
    except Exception as exc:
        log.warning("AIOrchestrator creation failed: %s", exc)

    service = AIService(
        orchestrator=orchestrator,
        propagator=propagator,
        client=client,
        failure_handler=failure_handler,
    )
    container.register("ai_service", service, startup_priority=25)
    log.info("AI Runtime services registered (Phase 9B integration layer active)")
