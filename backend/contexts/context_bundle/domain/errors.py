"""Failures raised by the ContextBundle context.

Every one is a refusal. A bundle never quietly widens, never silently includes a
path nobody granted, and never repairs a malformed layer. Engineering
Constitution EP-6: ambiguity resolves to refusal.

The refusals here matter more than most, because a context bundle is what an
agent *sees*. A bundle that widened by accident would give an agent access
nobody approved, and the only trace would be work that turned out better
informed than it should have been.
"""

from __future__ import annotations

from typing import Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "ContextBundleError",
    "InvalidIdentifier",
    "LayerViolation",
    "ImplicitExpansion",
    "ExpansionDenied",
    "ExpansionAlreadyDecided",
    "UnknownExpansion",
    "BundleSuperseded",
    "BundleInvalidated",
    "StaleBaseCommit",
    "ManifestMismatch",
    "IncompleteBundle",
    "BundleNotFound",
    "DuplicateBundle",
]


class ContextBundleError(ContractViolation):
    """Base for every refusal raised by this context."""


class InvalidIdentifier(ContextBundleError):
    def __init__(self, kind: str, value: object, reason: str) -> None:
        super().__init__(f"{kind} cannot be {value!r}: {reason}")
        self.kind = kind
        self.value = value
        self.reason = reason


class LayerViolation(ContextBundleError):
    """A reference was placed in a layer whose access it cannot have.

    Layers are not labels. L2 dependency contracts are read-only because writing
    to another context's interface is how a boundary erodes; L4 is search-only
    because retrieving from it is an expansion, not a search.
    """

    def __init__(self, *, path: str, layer: str, access: str, reason: str) -> None:
        super().__init__(f"{path} in {layer} with {access} access: {reason}")
        self.path = path
        self.layer = layer
        self.access = access
        self.reason = reason


class ImplicitExpansion(ContextBundleError):
    """Something tried to widen a bundle without an expansion request.

    The rule this context exists to enforce. A bundle that can grow without a
    recorded request is a bundle whose contents nobody can account for, and the
    expansion log -- the highest-value signal this context produces -- would be
    silently incomplete.
    """

    def __init__(self, *, bundle_id: str, path: str) -> None:
        super().__init__(
            f"bundle {bundle_id}: {path!r} was added without an expansion request; "
            "all expansion must be explicit and auditable"
        )
        self.bundle_id = bundle_id
        self.path = path


class ExpansionDenied(ContextBundleError):
    """A requested path was refused.

    Raised when a caller acts on a denied request. The denial itself is recorded
    rather than raised -- a denial is information, and discarding it would lose
    the signal that someone keeps asking for the same out-of-scope path.
    """

    def __init__(self, *, request_id: str, path: str, reason: str) -> None:
        super().__init__(f"expansion {request_id} for {path!r} was denied: {reason}")
        self.request_id = request_id
        self.path = path
        self.reason = reason


class ExpansionAlreadyDecided(ContextBundleError):
    def __init__(self, *, request_id: str, disposition: str) -> None:
        super().__init__(
            f"expansion {request_id} is already {disposition}; a second decision would "
            "overwrite the first and lose who decided what"
        )
        self.request_id = request_id
        self.disposition = disposition


class UnknownExpansion(ContextBundleError):
    def __init__(self, *, bundle_id: str, request_id: str) -> None:
        super().__init__(f"bundle {bundle_id} has no expansion request {request_id}")
        self.bundle_id = bundle_id
        self.request_id = request_id


class BundleSuperseded(ContextBundleError):
    def __init__(self, *, bundle_id: str, successor: str) -> None:
        super().__init__(
            f"bundle {bundle_id} is superseded by {successor}; work from the current "
            "version rather than reviving a replaced one"
        )
        self.bundle_id = bundle_id
        self.successor = successor


class BundleInvalidated(ContextBundleError):
    def __init__(self, *, bundle_id: str, reason: str) -> None:
        super().__init__(f"bundle {bundle_id} was invalidated: {reason}")
        self.bundle_id = bundle_id
        self.reason = reason


class StaleBaseCommit(ContextBundleError):
    """The tree moved under the bundle.

    A bundle describes a particular commit. When the base moves, every content
    digest in the manifest describes a tree nobody is working on -- and an agent
    reasoning from it is reasoning about code that no longer exists.
    """

    def __init__(self, *, bundle_id: str, assembled_at: str, current: str) -> None:
        super().__init__(
            f"bundle {bundle_id} was assembled at {assembled_at} but the base is now "
            f"{current}; reassemble rather than reason from a tree nobody is working on"
        )
        self.bundle_id = bundle_id
        self.assembled_at = assembled_at
        self.current = current


class ManifestMismatch(ContextBundleError):
    """The bundle no longer hashes to its recorded manifest digest.

    The check that makes "this is what the agent saw" a verifiable claim rather
    than an assertion about the past.
    """

    def __init__(self, *, bundle_id: str, recorded: str, recomputed: str) -> None:
        super().__init__(
            f"bundle {bundle_id}: manifest recorded {recorded} but content now hashes to "
            f"{recomputed}; the record no longer describes what it claims"
        )
        self.bundle_id = bundle_id
        self.recorded = recorded
        self.recomputed = recomputed


class IncompleteBundle(ContextBundleError):
    """A bundle is missing something every bundle must carry."""

    def __init__(self, *, missing: Sequence[str]) -> None:
        names = ", ".join(sorted(missing))
        super().__init__(
            f"a context bundle must carry repository scope, ADR references, dependency "
            f"contracts and a blast radius; missing: {names}"
        )
        self.missing = tuple(missing)


class BundleNotFound(ContextBundleError):
    def __init__(self, bundle_id: str) -> None:
        super().__init__(f"no context bundle with id {bundle_id}")
        self.bundle_id = bundle_id


class DuplicateBundle(ContextBundleError):
    def __init__(self, *, work_id: str, version: int) -> None:
        super().__init__(
            f"bundle version {version} for WorkOrder {work_id} already exists"
        )
        self.work_id = work_id
        self.version = version
