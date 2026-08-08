"""Bounds on what one discovery run may take in.

Why a budget object rather than constants scattered about
-----------------------------------------------------------
Discovery reads data that something else controls. Every one of these limits is
the answer to "what happens if the far side is hostile, broken, or just much
larger than expected" -- and the answer must not be "the process grows until it
dies", because a discovery source that can exhaust the platform is a denial of
service with an inventory API in front of it.

Keeping them in one frozen object means the limits are reviewable in one place,
overridable per deployment, and impossible to drift apart from each other. A
magic number buried in a loop is a limit nobody can find when it needs raising.

Exceeding a budget is a *finding*, not a crash
------------------------------------------------
When a source offers more than the budget allows, discovery records what it took
and reports what it dropped. Silently truncating would be worse than failing:
the caller would see a short inventory and have no way to tell it apart from a
source that genuinely has few tools.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation

__all__ = ["DiscoveryBudget", "DEFAULT_BUDGET", "BudgetExceeded"]


class BudgetExceeded(ContractViolation):
    """A source offered more than a discovery run is allowed to take."""

    def __init__(self, *, limit_name: str, limit: int, observed: int) -> None:
        super().__init__(
            f"discovery budget {limit_name!r} is {limit} and the source offered "
            f"{observed}; taking it all would let a source decide how much of this "
            "platform it uses"
        )
        self.limit_name = limit_name
        self.limit = limit
        self.observed = observed


@dataclass(frozen=True)
class DiscoveryBudget:
    """What one discovery run may consume."""

    max_sources: int = 50
    max_capabilities_per_source: int = 500
    max_response_bytes: int = 1_048_576
    max_schema_depth: int = 12
    max_schema_properties: int = 256
    max_pages: int = 20
    timeout_seconds: int = 30
    max_description_chars: int = 4096
    max_identifier_chars: int = 128

    def __post_init__(self) -> None:
        for label in (
            "max_sources",
            "max_capabilities_per_source",
            "max_response_bytes",
            "max_schema_depth",
            "max_schema_properties",
            "max_pages",
            "timeout_seconds",
            "max_description_chars",
            "max_identifier_chars",
        ):
            value = getattr(self, label)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ContractViolation(f"{label} must be a positive integer")

        if self.max_schema_depth > 64:
            raise ContractViolation(
                "max_schema_depth above 64 defeats the purpose; a schema that deep "
                "is either generated or hostile, and walking it is what the limit "
                "is protecting against"
            )

    def assert_within(self, limit_name: str, observed: int) -> None:
        limit = getattr(self, limit_name, None)
        if limit is None:
            raise ContractViolation(f"{limit_name!r} is not a discovery budget")
        if observed > limit:
            raise BudgetExceeded(
                limit_name=limit_name, limit=limit, observed=observed
            )

    def truncated(self, limit_name: str, items: tuple) -> tuple:
        """Take what fits. The caller reports what was dropped."""
        limit = getattr(self, limit_name)
        return tuple(items[:limit])

    def to_dict(self) -> dict:
        return {
            "max_sources": self.max_sources,
            "max_capabilities_per_source": self.max_capabilities_per_source,
            "max_response_bytes": self.max_response_bytes,
            "max_schema_depth": self.max_schema_depth,
            "max_schema_properties": self.max_schema_properties,
            "max_pages": self.max_pages,
            "timeout_seconds": self.timeout_seconds,
            "max_description_chars": self.max_description_chars,
            "max_identifier_chars": self.max_identifier_chars,
        }


DEFAULT_BUDGET = DiscoveryBudget()
