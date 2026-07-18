from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

_log = logging.getLogger(__name__)


class DependencyContainer:
    _instance: Optional[DependencyContainer] = None

    def __new__(cls) -> DependencyContainer:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._registry: Dict[str, Any] = {}
        self._lifecycle: Dict[str, Dict[str, Any]] = {}
        self._order: List[str] = []
        self._running: bool = False

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        instance: Any,
        *,
        startup: Optional[Callable] = None,
        shutdown: Optional[Callable] = None,
        depends_on: Optional[List[str]] = None,
        startup_priority: int = 100,
    ) -> None:
        if name in self._registry:
            _log.warning("DependencyContainer: %s already registered — skipping", name)
            return
        self._registry[name] = instance
        self._lifecycle[name] = {
            "instance": instance,
            "startup": startup,
            "shutdown": shutdown,
            "depends_on": depends_on or [],
            "startup_priority": startup_priority,
            "started": False,
        }
        self._order.append(name)
        _log.debug("DependencyContainer registered: %s", name)

    def resolve(self, name: str) -> Any:
        if name not in self._registry:
            raise KeyError(f"DependencyContainer: {name} not registered")
        return self._registry[name]

    def registered(self) -> List[str]:
        return list(self._order)

    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Startup (ordered by startup_priority ascending then registration order)
    # ------------------------------------------------------------------

    async def startup_all(self) -> None:
        sorted_services = sorted(
            self._order,
            key=lambda n: (self._lifecycle[n]["startup_priority"], self._order.index(n)),
        )

        for name in sorted_services:
            entry = self._lifecycle[name]
            try:
                deps = entry["depends_on"]
                for dep in deps:
                    if dep in self._lifecycle and not self._lifecycle[dep]["started"]:
                        _log.warning(
                            "DependencyContainer: %s depends on %s which hasn't started yet",
                            name, dep,
                        )

                fn = entry["startup"]
                if fn:
                    result = fn()
                    if asyncio.iscoroutine(result):
                        await result
                entry["started"] = True
                _log.debug("DependencyContainer started: %s", name)
            except Exception as exc:
                _log.warning("DependencyContainer startup failed for %s: %s", name, exc)

        self._running = True
        _log.info("DependencyContainer: all %d services started", len(sorted_services))

    # ------------------------------------------------------------------
    # Shutdown (reverse startup order)
    # ------------------------------------------------------------------

    async def shutdown_all(self) -> None:
        self._running = False

        sorted_services = sorted(
            self._order,
            key=lambda n: (self._lifecycle[n]["startup_priority"], self._order.index(n)),
            reverse=True,
        )

        for name in sorted_services:
            entry = self._lifecycle[name]
            if not entry["started"]:
                continue
            try:
                fn = entry["shutdown"]
                if fn:
                    result = fn()
                    if asyncio.iscoroutine(result):
                        await result
                entry["started"] = False
                _log.debug("DependencyContainer shutdown: %s", name)
            except Exception as exc:
                _log.warning("DependencyContainer shutdown error for %s: %s", name, exc)

        _log.info("DependencyContainer: all services shut down")

    # ------------------------------------------------------------------
    # Context manager for FastAPI lifespan
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def lifespan(self) -> AsyncGenerator[None, None]:
        await self.startup_all()
        try:
            yield
        finally:
            await self.shutdown_all()


container = DependencyContainer()
