"""What running a node does to the outside world, and how often it may happen.

Two different questions, deliberately separated
------------------------------------------------
``SideEffectClass`` (published, ``backend.contracts.execution``) says how
*consequential* an action is: read, reversible, irreversible, destructive. It
encodes Constitution P2 and P9 and it is not forked here.

It does not say whether running the action **twice** is safe. Those are
independent: a reversible write can be violently non-idempotent, and a
destructive delete can be perfectly idempotent if it is keyed.

``EffectSemantics`` answers the second question, and it is the one that decides
whether a retry may run.

Why UNKNOWN exists and why it is not "safe"
---------------------------------------------
When a node mutates but nothing establishes that repeating it is harmless, the
honest answer is that we do not know. The tempting default -- treat unknown as
idempotent so the retry can proceed -- is exactly the assumption that turns one
production change into two.

So ``UNKNOWN`` is treated as ``NON_IDEMPOTENT_WRITE`` everywhere a decision is
made. Unknown fails closed. It is kept as a distinct value rather than collapsed
into non-idempotent because the two call for different *human* responses: one is
a declared risk, the other is a gap in the declaration.

Delivery semantics
--------------------
No part of this codebase claims exactly-once. Nothing that crosses a network can
honestly claim it. What the runtime does claim is which of two failure modes it
prefers when the answer is unknowable:

``AT_LEAST_ONCE`` -- may run again after ambiguity. Requires idempotency.
``AT_MOST_ONCE``  -- will not run again after ambiguity. Surfaces the ambiguity
                     to a human instead, and accepts that the work may never
                     have happened.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics, SideEffectClass

__all__ = [
    # Re-exported from the published contract: shared with BC-8 Connectivity,
    # which declares it at registration and cannot import this context.
    "EffectSemantics",
    "DeliverySemantics",
    "EffectProfile",
    "profile_for",
]


class DeliverySemantics(str, Enum):
    """What the runtime does when it cannot tell whether the work happened."""

    AT_LEAST_ONCE = "at_least_once"
    """Prefer doing the work to knowing it happened once. Legal only when
    repeating is safe."""

    AT_MOST_ONCE = "at_most_once"
    """Prefer knowing it happened at most once to doing it. After ambiguity the
    runtime stops and says so rather than trying again."""

    @property
    def may_repeat_after_ambiguity(self) -> bool:
        return self is DeliverySemantics.AT_LEAST_ONCE


@dataclass(frozen=True)
class EffectProfile:
    """The effect and delivery semantics of one node, derived not asserted."""

    semantics: EffectSemantics
    delivery: DeliverySemantics
    side_effect: SideEffectClass
    idempotency_key: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.semantics, EffectSemantics):
            raise ContractViolation("semantics must be an EffectSemantics")
        if not isinstance(self.delivery, DeliverySemantics):
            raise ContractViolation("delivery must be a DeliverySemantics")
        if (
            self.delivery is DeliverySemantics.AT_LEAST_ONCE
            and not self.semantics.is_repeatable
        ):
            raise ContractViolation(
                f"a {self.semantics.value} operation cannot be delivered "
                "at-least-once; at-least-once means 'may run again after an "
                "ambiguous outcome', and running this one again is the thing we "
                "are trying to avoid"
            )

    @property
    def may_retry_after_ambiguity(self) -> bool:
        """The single question the retry path asks.

        Both halves must agree. A repeatable operation delivered at-most-once
        still does not re-run: the delivery choice is the stricter promise, and
        the stricter promise wins.
        """
        return self.semantics.is_repeatable and self.delivery.may_repeat_after_ambiguity

    def to_dict(self) -> dict:
        return {
            "semantics": self.semantics.value,
            "delivery": self.delivery.value,
            "side_effect": self.side_effect.value,
            "idempotency_key": self.idempotency_key,
        }


def profile_for(spec) -> EffectProfile:
    """Derive the effect profile of a node from what the workflow declared.

    Derived rather than stored so it cannot drift from the spec it describes,
    and so a node whose declaration is silent is *classified* silent rather than
    quietly assumed safe.
    """
    side_effect = spec.side_effect
    key = spec.idempotency_key

    if not side_effect.mutates:
        return EffectProfile(
            semantics=EffectSemantics.READ_ONLY,
            delivery=DeliverySemantics.AT_LEAST_ONCE,
            side_effect=side_effect,
            idempotency_key=key,
        )

    if key:
        # An idempotency key is a claim that the far side will collapse a repeat.
        # It is the only evidence this context accepts for that claim, because
        # it is the only one it can pass to the far side.
        return EffectProfile(
            semantics=EffectSemantics.IDEMPOTENT_WRITE,
            delivery=DeliverySemantics.AT_LEAST_ONCE,
            side_effect=side_effect,
            idempotency_key=key,
        )

    # Mutates, and nothing says a repeat is safe. Whether the workflow author
    # considered it and accepted the risk, or never considered it at all, is
    # not knowable from here -- so it is UNKNOWN, and it fails closed.
    return EffectProfile(
        semantics=EffectSemantics.UNKNOWN,
        delivery=DeliverySemantics.AT_MOST_ONCE,
        side_effect=side_effect,
        idempotency_key=None,
    )
