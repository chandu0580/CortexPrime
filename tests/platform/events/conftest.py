"""Fixtures for event foundation tests.

Test event types are declared once at module scope rather than per-test.
``DomainEvent`` subclasses self-register in the contract registry at class
creation, and redeclaring a type inside a test function would either collide or
silently shadow depending on execution order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pytest

from backend.contracts import PrincipalKind, PrincipalRef, TenantRef, TenantScope
from backend.platform.events import DomainEvent, EventMetadata

NOW = datetime(2030, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class SampleOccurred(DomainEvent):
    """A minimal event with a single payload field."""

    EVENT_TYPE = "cortexprime.test.sample_occurred"

    detail: str


@dataclass(frozen=True)
class SampleFollowed(DomainEvent):
    """A second type, for causal-chain tests."""

    EVENT_TYPE = "cortexprime.test.sample_followed"

    reference: str


@dataclass(frozen=True)
class VersionedEvent(DomainEvent):
    """Declares version 2, for upcasting tests."""

    EVENT_TYPE = "cortexprime.test.versioned"
    EVENT_VERSION = 2

    name: str
    added_in_v2: Optional[str] = None


@dataclass(frozen=True)
class EmptyPayloadEvent(DomainEvent):
    """An event whose entire content is the fact that it happened."""

    EVENT_TYPE = "cortexprime.test.empty_payload"


@pytest.fixture
def scope() -> TenantScope:
    return TenantScope(tenant=TenantRef(tenant_id="tenant-alpha"))


@pytest.fixture
def actor() -> PrincipalRef:
    return PrincipalRef(principal_id="user-1", kind=PrincipalKind.HUMAN)


@pytest.fixture
def metadata(scope: TenantScope) -> EventMetadata:
    return EventMetadata.create(
        aggregate_id="agg-1", aggregate_type="mission", scope=scope
    )


@pytest.fixture
def event(metadata: EventMetadata) -> SampleOccurred:
    return SampleOccurred(metadata=metadata, detail="something happened")


@pytest.fixture
def make_event(scope: TenantScope):
    """Factory for events with independent metadata."""

    def _make(detail: str = "detail", **kwargs) -> SampleOccurred:
        return SampleOccurred(
            metadata=EventMetadata.create(
                aggregate_id=kwargs.pop("aggregate_id", "agg-1"),
                aggregate_type=kwargs.pop("aggregate_type", "mission"),
                scope=kwargs.pop("scope", scope),
                **kwargs,
            ),
            detail=detail,
        )

    return _make
