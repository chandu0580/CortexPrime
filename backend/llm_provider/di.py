from __future__ import annotations

import logging

from backend.core.dependency_container import container

log = logging.getLogger(__name__)


def register_llm_provider_services() -> None:
    service = None
    try:
        from backend.llm_provider.service import LLMService
        service = LLMService()
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(service.initialize())
            else:
                loop.run_until_complete(service.initialize())
        except RuntimeError:
            pass
        container.register("llm_service", service, startup_priority=22)
        log.info("LLM Provider Runtime services registered")
    except Exception as exc:
        log.warning("LLMService creation failed: %s", exc)
        if service is None:
            service = type("Placeholder", (), {
                "initialize": lambda: True,
                "generate": lambda **kw: type("R", (), {"content": "", "error": str(exc)})(),
                "stream": lambda **kw: iter([]),
                "health": lambda: [],
                "list_providers": lambda: [],
                "list_models": lambda: [],
                "cancel_stream": lambda x: False,
                "shutdown": lambda: None,
            })()
        container.register("llm_service", service, startup_priority=22)
