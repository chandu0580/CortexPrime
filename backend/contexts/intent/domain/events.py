"""Intent lifecycle events.

Namespaced ``intent.runtime.*``. ``CONTRACT_NAME`` is globally unique and a clash
raises at import time.

These describe a *mandate taking shape*, never work. There is no
``IntentPlanned``, no ``IntentExecuted``: this context produces the input to
planning and has nothing to say about what planning did with it.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "AGGREGATE_TYPE",
    "IntentCreated",
    "IntentValidated",
    "IntentExpanded",
    "IntentApproved",
    "IntentRejected",
    "IntentSuperseded",
    "INTENT_EVENT_TYPES",
]

AGGREGATE_TYPE = "intent"


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class IntentCreated(DomainEvent):
    """An intent was opened, carrying the requester's own words."""

    EVENT_TYPE = "intent.runtime.created"

    intent_id: str = ""
    title: str = ""
    stated_goal: str = ""
    origin: str = ""
    requested_by: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("intent_id", self.intent_id)
        _require_text("title", self.title)
        _require_text(
            "stated_goal",
            self.stated_goal,
        )
        _require_text("origin", self.origin)


@dataclass(frozen=True)
class IntentExpanded(DomainEvent):
    """The mandate gained or lost detail.

    ``returned_to_draft`` is the field worth reading. Expanding a validated
    intent invalidates the validation, and a consumer that missed that would act
    on a "validated" mandate whose current content nobody checked.
    """

    EVENT_TYPE = "intent.runtime.expanded"

    intent_id: str = ""
    element: str = ""
    detail: str = ""
    expansion_count: int = 1
    returned_to_draft: bool = False

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("intent_id", self.intent_id)
        _require_text("element", self.element)
        if not isinstance(self.returned_to_draft, bool):
            raise ContractViolation("returned_to_draft must be a bool")
        if self.expansion_count < 1:
            raise ContractViolation("an expansion is at least the first one")


@dataclass(frozen=True)
class IntentValidated(DomainEvent):
    """The mandate is complete and coherent.

    Refuses construction with missing elements. An event that could describe a
    validated-but-incomplete intent would make the log a worse record than the
    aggregate.
    """

    EVENT_TYPE = "intent.runtime.validated"

    intent_id: str = ""
    constraints: int = 0
    success_criteria: int = 0
    scope_breadth: int = 0
    missing_elements: int = 0
    advisories: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("intent_id", self.intent_id)
        if self.missing_elements:
            raise ContractViolation(
                f"an intent cannot be validated with {self.missing_elements} required "
                "element(s) missing"
            )
        if self.constraints < 1:
            raise ContractViolation(
                "a validated intent carries at least one constraint; an objective "
                "with no stated limit hands a planner an unbounded mandate"
            )
        if self.success_criteria < 1:
            raise ContractViolation(
                "a validated intent carries at least one success criterion; without "
                "one nothing can be shown to have achieved it"
            )


@dataclass(frozen=True)
class IntentApproved(DomainEvent):
    """The mandate was accepted. Planning may act on it."""

    EVENT_TYPE = "intent.runtime.approved"

    intent_id: str = ""
    approved_by: str = ""
    digest: str = ""
    priority: str = ""
    touches_production: bool = False
    hard_constraints: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("intent_id", self.intent_id)
        _require_text("digest", self.digest)
        _require_text(
            "approved_by",
            self.approved_by,
        )
        if not isinstance(self.touches_production, bool):
            raise ContractViolation("touches_production must be a bool")


@dataclass(frozen=True)
class IntentRejected(DomainEvent):
    """The mandate was refused, with the reason the next attempt is built from."""

    EVENT_TYPE = "intent.runtime.rejected"

    intent_id: str = ""
    reason: str = ""
    rejected_by: str = ""
    rejected_from: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("intent_id", self.intent_id)
        _require_text(
            "reason",
            self.reason,
        )


@dataclass(frozen=True)
class IntentSuperseded(DomainEvent):
    EVENT_TYPE = "intent.runtime.superseded"

    intent_id: str = ""
    superseded_by: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("intent_id", self.intent_id)
        _require_text("superseded_by", self.superseded_by)
        if self.intent_id == self.superseded_by:
            raise ContractViolation("an intent cannot supersede itself")


INTENT_EVENT_TYPES = (
    IntentCreated,
    IntentValidated,
    IntentExpanded,
    IntentApproved,
    IntentRejected,
    IntentSuperseded,
)
