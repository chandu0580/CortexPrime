"""Shared doubles for the storage boundary tests.

The contexts here are hand-built rather than real ``ExecutionContext`` instances.
That is deliberate: the guard accepts anything structurally satisfying
:class:`~backend.platform.storage.context.RepositoryContext`, and the only way to
prove it *rejects* a malformed one is to be able to construct a malformed one.
A real ``ExecutionContext`` refuses to be built wrong, which makes it useless for
testing refusals.

``test_context.py`` separately asserts that a real ``ExecutionContext`` satisfies
the protocol, so the doubles cannot drift into testing a shape nothing uses.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest

from backend.contracts.storage import StorageBinding
from backend.platform.storage import RepositoryGuard


class FakeContext:
    """A minimal, well-formed repository context."""

    def __init__(
        self,
        tenant_id: str = "tenant-a",
        *,
        platform_internal: bool = False,
        reason: Optional[str] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.is_platform_internal = platform_internal
        self.platform_internal_reason = reason

    def audit_detail(self) -> dict[str, Any]:
        return {"tenant_id": self.tenant_id}


class FakeRow:
    """A record carrying a tenant in the conventional column."""

    def __init__(self, tenant_id: Optional[str] = None) -> None:
        self.tenant_id = tenant_id


@pytest.fixture
def binding() -> StorageBinding:
    return StorageBinding(record_type="ProbeModel", scope_column="tenant_id")


@pytest.fixture
def guard(binding: StorageBinding) -> RepositoryGuard:
    return RepositoryGuard(binding)


@pytest.fixture
def open_guard() -> RepositoryGuard:
    """A guard over a record type that permits platform-internal access."""
    return RepositoryGuard(
        StorageBinding(
            record_type="ProbeModel",
            scope_column="tenant_id",
            platform_internal_allowed=True,
        )
    )


@pytest.fixture
def context() -> FakeContext:
    return FakeContext("tenant-a")
