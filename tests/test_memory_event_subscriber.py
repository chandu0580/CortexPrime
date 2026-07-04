from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_start_and_stop_manage_subscription_and_channel(monkeypatch):
    from backend.memory.event_subscriber import MemoryEventSubscriber
    from backend.events.event_bus import event_bus

    subscriber = MemoryEventSubscriber()
    subscribed: list = []

    monkeypatch.setattr(event_bus, "subscribe", lambda callback: subscribed.append(callback))

    class FakeChannel:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    channel = FakeChannel()
    subscriber._mq_channel = channel

    await subscriber.start()
    assert subscriber._running is True
    assert subscribed == [subscriber._on_event]

    await subscriber.stop()
    assert subscriber._running is False
    assert channel.closed is True
    assert subscriber._mq_channel is None


def test_on_event_only_dispatches_when_running(monkeypatch):
    from backend.memory.event_subscriber import MemoryEventSubscriber

    subscriber = MemoryEventSubscriber()
    scheduled: list = []

    async def _fake_process(event):
        return None

    monkeypatch.setattr(subscriber, "_process", _fake_process)

    monkeypatch.setattr(
        "backend.memory.event_subscriber.asyncio.ensure_future",
        lambda task: scheduled.append(task) or task.close(),
    )

    subscriber._on_event(SimpleNamespace())
    assert scheduled == []

    subscriber._running = True
    subscriber._on_event(SimpleNamespace())
    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_process_routes_persist_event(monkeypatch):
    from backend.memory.event_subscriber import MemoryEventSubscriber
    from backend.memory.memory_orchestrator import memory_orchestrator

    subscriber = MemoryEventSubscriber()
    captured = {}

    async def _store_cognition_event(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(memory_orchestrator, "store_cognition_event", _store_cognition_event)

    event = SimpleNamespace(
        event_type="AGENT_COMPLETED",
        message="planner finished",
        agent="planner",
        execution_id="exec-1",
        status="completed",
        latency_ms=12,
        phase="planning",
    )

    await subscriber._process(event)

    assert captured["agent"] == "planner"
    assert captured["event_type"] == "AGENT_COMPLETED"
    assert captured["content"] == "planner finished"
    assert captured["session_id"] == "exec-1"
    assert captured["metadata"]["phase"] == "planning"


@pytest.mark.asyncio
async def test_process_routes_reflection_event(monkeypatch):
    from backend.memory.event_subscriber import MemoryEventSubscriber
    from backend.memory.memory_orchestrator import memory_orchestrator

    subscriber = MemoryEventSubscriber()
    captured = {}

    async def _store_reflection(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(memory_orchestrator, "store_reflection", _store_reflection)

    event = SimpleNamespace(
        event_type="SELF_CRITIQUE",
        message="needs better evidence",
        agent="critic",
        execution_id="exec-2",
        confidence_score=0.42,
    )

    await subscriber._process(event)

    assert captured == {
        "agent": "critic",
        "reflection": "needs better evidence",
        "mission_id": "exec-2",
        "score": 0.42,
    }


@pytest.mark.asyncio
async def test_process_ignores_empty_message(monkeypatch):
    from backend.memory.event_subscriber import MemoryEventSubscriber
    from backend.memory.memory_orchestrator import memory_orchestrator

    subscriber = MemoryEventSubscriber()

    async def _unexpected(**kwargs):
        raise AssertionError("should not be called")

    monkeypatch.setattr(memory_orchestrator, "store_cognition_event", _unexpected)
    monkeypatch.setattr(memory_orchestrator, "store_reflection", _unexpected)

    await subscriber._process(SimpleNamespace(event_type="AGENT_COMPLETED", message="", agent="planner"))


@pytest.mark.asyncio
async def test_process_swallows_storage_error(monkeypatch):
    from backend.memory.event_subscriber import MemoryEventSubscriber
    from backend.memory.memory_orchestrator import memory_orchestrator

    subscriber = MemoryEventSubscriber()

    async def _boom(**kwargs):
        raise RuntimeError("storage offline")

    monkeypatch.setattr(memory_orchestrator, "store_cognition_event", _boom)

    await subscriber._process(
        SimpleNamespace(event_type="AGENT_COMPLETED", message="done", agent="planner", execution_id="exec-1")
    )


@pytest.mark.asyncio
async def test_connect_rabbitmq_import_error_is_ignored(monkeypatch):
    from backend.memory.event_subscriber import MemoryEventSubscriber

    subscriber = MemoryEventSubscriber()

    original_import = __import__

    def _fake_import(name, *args, **kwargs):
        if name == "aio_pika":
            raise ImportError("missing aio_pika")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _fake_import)

    await subscriber._connect_rabbitmq()
    assert subscriber._mq_channel is None


@pytest.mark.asyncio
async def test_connect_rabbitmq_success(monkeypatch):
    from backend.memory.event_subscriber import MemoryEventSubscriber

    subscriber = MemoryEventSubscriber()
    bindings: list[tuple[str, str]] = []

    class FakeQueue:
        def __init__(self, name: str) -> None:
            self.name = name

        async def bind(self, exchange, routing_key: str) -> None:
            bindings.append((self.name, routing_key))

    class FakeChannel:
        async def declare_exchange(self, name, exchange_type, durable=True):
            return SimpleNamespace(name=name, exchange_type=exchange_type, durable=durable)

        async def declare_queue(self, queue_name, durable=True):
            return FakeQueue(queue_name)

    class FakeConnection:
        async def channel(self):
            return FakeChannel()

    class FakeAioPika:
        class ExchangeType:
            TOPIC = "topic"

        @staticmethod
        async def connect_robust(url, timeout=5):
            return FakeConnection()

    monkeypatch.setitem(__import__("sys").modules, "aio_pika", FakeAioPika)

    await subscriber._connect_rabbitmq()

    assert subscriber._mq_channel is not None
    assert bindings == [
        ("memory.episodic", "memory.episodic"),
        ("memory.semantic", "memory.semantic"),
        ("memory.reflection", "memory.reflection"),
    ]


@pytest.mark.asyncio
async def test_publish_memory_event_no_channel_is_noop():
    from backend.memory.event_subscriber import MemoryEventSubscriber

    subscriber = MemoryEventSubscriber()
    await subscriber.publish_memory_event("memory.episodic", {"ok": True})


@pytest.mark.asyncio
async def test_publish_memory_event_sends_message(monkeypatch):
    from backend.memory.event_subscriber import MemoryEventSubscriber

    published = {}

    class FakeExchange:
        async def publish(self, message, routing_key: str) -> None:
            published["routing_key"] = routing_key
            published["body"] = message.body
            published["content_type"] = message.content_type

    class FakeChannel:
        async def get_exchange(self, name: str):
            published["exchange"] = name
            return FakeExchange()

    class FakeMessage:
        def __init__(self, body, content_type, delivery_mode):
            self.body = body
            self.content_type = content_type
            self.delivery_mode = delivery_mode

    class FakeAioPika:
        Message = FakeMessage

        class DeliveryMode:
            PERSISTENT = "persistent"

    monkeypatch.setitem(__import__("sys").modules, "aio_pika", FakeAioPika)

    subscriber = MemoryEventSubscriber()
    subscriber._mq_channel = FakeChannel()

    await subscriber.publish_memory_event("memory.semantic", {"value": 1})

    assert published["exchange"] == "cortex.memory"
    assert published["routing_key"] == "memory.semantic"
    assert published["content_type"] == "application/json"
    assert b'"value": 1' in published["body"]


@pytest.mark.asyncio
async def test_publish_memory_event_swallows_publish_error(monkeypatch):
    from backend.memory.event_subscriber import MemoryEventSubscriber

    class FakeChannel:
        async def get_exchange(self, name: str):
            raise RuntimeError("exchange missing")

    class FakeAioPika:
        class DeliveryMode:
            PERSISTENT = "persistent"

        class Message:
            def __init__(self, body, content_type, delivery_mode):
                self.body = body
                self.content_type = content_type
                self.delivery_mode = delivery_mode

    monkeypatch.setitem(__import__("sys").modules, "aio_pika", FakeAioPika)

    subscriber = MemoryEventSubscriber()
    subscriber._mq_channel = FakeChannel()

    await subscriber.publish_memory_event("memory.reflection", {"value": 2})