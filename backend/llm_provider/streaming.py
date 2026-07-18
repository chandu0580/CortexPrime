from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Callable, Optional

from backend.llm_provider.models import FinishReason, LLMResponse, StreamChunk

log = logging.getLogger(__name__)


class StreamManager:
    def __init__(self, timeout_seconds: float = 60.0) -> None:
        self._timeout = timeout_seconds
        self._active_streams: dict[str, asyncio.Event] = {}

    async def handle_stream(
        self,
        stream_generator: AsyncGenerator[StreamChunk, None],
        request_id: str,
        cancel_event: Optional[asyncio.Event] = None,
        on_chunk: Optional[Callable[[StreamChunk], Any]] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        cancel = cancel_event or asyncio.Event()
        self._active_streams[request_id] = cancel
        start = time.monotonic()

        try:
            async for chunk in stream_generator:
                if cancel.is_set():
                    yield StreamChunk(
                        finish_reason=FinishReason.CANCELLED,
                        done=True, request_id=request_id,
                        provider=chunk.provider, model=chunk.model,
                    )
                    return

                if time.monotonic() - start > self._timeout:
                    yield StreamChunk(
                        finish_reason=FinishReason.TIMEOUT,
                        done=True, request_id=request_id,
                        provider=chunk.provider, model=chunk.model,
                    )
                    return

                if on_chunk:
                    try:
                        await on_chunk(chunk) if asyncio.iscoroutinefunction(on_chunk) else on_chunk(chunk)
                    except Exception as exc:
                        log.warning("Stream on_chunk callback error: %s", exc)

                yield chunk

                if chunk.done:
                    return

        except asyncio.CancelledError:
            yield StreamChunk(
                finish_reason=FinishReason.CANCELLED,
                done=True, request_id=request_id,
            )
        except Exception as exc:
            log.warning("Stream error: %s", exc)
            yield StreamChunk(
                finish_reason=FinishReason.ERROR,
                done=True, request_id=request_id,
                error=str(exc),
            )
        finally:
            self._active_streams.pop(request_id, None)

    def cancel_stream(self, request_id: str) -> bool:
        cancel = self._active_streams.get(request_id)
        if cancel:
            cancel.set()
            return True
        return False

    def cancel_all(self) -> int:
        count = 0
        for request_id, cancel in list(self._active_streams.items()):
            cancel.set()
            count += 1
        self._active_streams.clear()
        return count

    def collect_stream(self, generator: AsyncGenerator[StreamChunk, None]) -> AsyncGenerator[StreamChunk, None]:
        return generator

    def has_active_streams(self) -> bool:
        return len(self._active_streams) > 0

    @property
    def active_count(self) -> int:
        return len(self._active_streams)

    async def stream_to_text(self, generator: AsyncGenerator[StreamChunk, None]) -> str:
        parts: list[str] = []
        async for chunk in generator:
            parts.append(chunk.content)
            if chunk.done:
                break
        return "".join(parts)


stream_manager = StreamManager()
