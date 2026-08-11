"""What the storage boundary requires of an execution context.

:class:`RepositoryContext` is a structural protocol rather than an import of
:class:`~backend.platform.context.ExecutionContext`. Two reasons, and the second
is the load-bearing one:

1. It keeps ``platform.storage`` from depending on ``platform.context``, so the
   two can be reasoned about and tested apart.

2. It states the *minimum* a context must provide to be trusted at the storage
   boundary. An ``ExecutionContext`` satisfies it, but so does a purpose-built
   test double -- and being able to construct a deliberately malformed one is
   what makes the guard's refusals testable. A guard that can only ever be
   handed valid input has never been shown to reject anything.

``ExecutionContext`` satisfies this protocol structurally; no registration or
inheritance is needed, and :func:`is_repository_context` checks it at runtime.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

__all__ = ["RepositoryContext", "is_repository_context"]


@runtime_checkable
class RepositoryContext(Protocol):
    """The context surface the storage boundary reads.

    Deliberately narrow. The guard needs to know which tenant an operation
    belongs to and whether it claims to have none; it has no business reading
    feature flags, locale, or request headers, and cannot be steered by them if
    it cannot see them.
    """

    @property
    def tenant_id(self) -> str:
        """The tenant this operation belongs to. Never blank, never optional."""
        ...

    @property
    def is_platform_internal(self) -> bool:
        """True when the operation genuinely has no tenant of its own."""
        ...

    def audit_detail(self) -> dict[str, Any]:
        """Context fields worth recording alongside a storage access."""
        ...


def is_repository_context(candidate: Any) -> bool:
    """Whether ``candidate`` can be trusted as a storage-boundary context.

    ``isinstance`` against a ``runtime_checkable`` Protocol only checks that the
    attribute *names* exist -- it does not check types, and it happily accepts a
    ``tenant_id`` that is ``None``. That is not enough at a security boundary, so
    this additionally verifies the values are the right shape.
    """
    if candidate is None:
        return False

    try:
        # The isinstance check is INSIDE the try (Phase 6.2 defect fix): a
        # runtime_checkable Protocol isinstance calls hasattr on each member,
        # and hasattr only suppresses AttributeError — a property raising
        # anything else escaped this function *before* the accessor try below
        # ever ran, surfacing as a query-path fault instead of a refusal.
        if not isinstance(candidate, RepositoryContext):
            return False
        tenant_id = candidate.tenant_id
        platform_internal = candidate.is_platform_internal
    except Exception:
        # A context whose accessors raise is not a context. Better to reject it
        # here than to let the exception surface from inside a query builder,
        # where it reads as a database fault rather than a boundary refusal.
        return False

    if not isinstance(tenant_id, str) or not tenant_id.strip():
        return False
    if not isinstance(platform_internal, bool):
        return False
    return callable(getattr(candidate, "audit_detail", None))
