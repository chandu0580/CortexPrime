"""The outbox publisher: hand recorded events over, at least once.

What Phase 5.1 left, and what this adds
-----------------------------------------
5.1 made the outbox durable: an event is recorded in the same transaction as the
state change that produced it, so publication may fail, retry or duplicate
without ever losing the fact. What it did not have was anything that publishes.

This is that. It claims, hands over, acknowledges — and every one of those is a
durable step, so a publisher that dies mid-batch loses nothing.

The guarantee, stated once and not upgraded
---------------------------------------------
**At-least-once.** An entry can be published, the acknowledgement lost, and the
entry published again after its claim lapses. There is no distributed transaction
across the sink, so there is no honest way to make it exactly-once, and nothing
here pretends otherwise.

``event_id`` is stable across the initial publish, every retry, every reclaim and
every restart — it is a column, written once, never regenerated. A consumer that
deduplicates on it is correct. A consumer that assumes single delivery is not,
and no amount of care here makes it so.

Ordering, and its actual scope
--------------------------------
Entries are claimed in ``sequence`` order, which is database-assigned and
monotonic. That gives **per-claim ordering**, not global processing order: two
publishers claiming concurrently each take the head of what they can see, so
entry 7 can be handed over before entry 5. Ordering within one publisher's batch
is guaranteed; ordering across publishers is not.

A deployment that needs total ordering runs one publisher, which is what the
``OUTBOX_PUBLISHER`` leadership role is for — and even then the guarantee is
"one publisher at a time", not "one publisher ever", because a leader can lapse.
That is the honest scope and it is recorded rather than implied.

Unknown delivery is not failure
---------------------------------
A sink that raised after the message may have left is ``UNKNOWN`` — the entry
stays pending, its claim lapses, and it is published again with the same
``event_id``. That is the correct behaviour for at-least-once and the reason
``event_id`` must never be regenerated: the duplicate is the recovery, and a new
id would make it a second event instead.

No retry loop, no sleeping
----------------------------
``publish_batch`` does one pass and returns. Repeating is the caller's business —
a scheduler tick, a cron, a test calling it twice. A loop in here would be a
second scheduler, and a sleep in here would hold a database connection while
doing nothing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

from backend.contracts.errors import ContractViolation
from backend.contexts.execution.application.metrics import NullMetrics, SafeMetrics
from backend.contexts.execution.domain.invocation import Clock, SystemClock

__all__ = [
    "EventSink",
    "DeliveryOutcome",
    "PublishReport",
    "OutboxPublisher",
    "OUTBOX_PUBLISHER_METRICS",
]

log = logging.getLogger(__name__)

OUTBOX_PUBLISHER_METRICS = (
    "outbox.claim",
    "outbox.publish",
    "outbox.publish_failure",
    "outbox.publish_unknown",
    "outbox.reclaim",
    "outbox.dead_letter",
)


class DeliveryOutcome(str, Enum):
    """What the sink did with an event. Three answers, and the third is real.

    Collapsing ``UNKNOWN`` into either neighbour is the failure mode this
    vocabulary exists to prevent: treated as delivered, the event is lost;
    treated as failed, it is counted towards dead-lettering for something that
    may well have worked.
    """

    DELIVERED = "delivered"
    REJECTED = "rejected"
    """The sink received it and refused it — a malformed payload, an unknown
    type. Repeating will not help, and it counts towards dead-lettering."""

    UNKNOWN = "unknown"
    """The sink may or may not have received it. The claim lapses and the entry
    is published again, with the **same** event id, which is what makes the
    duplicate a recovery rather than a second event."""


@runtime_checkable
class EventSink(Protocol):
    """Where published events go. Implemented at the composition root.

    Deliberately not an event bus and deliberately not this module's problem:
    RabbitMQ, an HTTP webhook, an in-process bus and a test recorder are all
    equivalent here. What the sink owes back is which of the three outcomes
    happened, and an implementation that cannot tell says ``UNKNOWN`` rather
    than guessing.
    """

    def deliver(self, context: Any, entry: Any) -> DeliveryOutcome: ...


@dataclass(frozen=True)
class PublishReport:
    """One publication pass. Facts, not a decision."""

    at: datetime
    claimed: int = 0
    delivered: int = 0
    rejected: int = 0
    unknown: int = 0
    dead_lettered: int = 0
    skipped: bool = False
    reason: str = ""

    @property
    def handled(self) -> int:
        return self.delivered + self.rejected + self.unknown

    def to_dict(self) -> dict:
        return {
            "at": self.at.isoformat(),
            "claimed": self.claimed,
            "delivered": self.delivered,
            "rejected": self.rejected,
            "unknown": self.unknown,
            "dead_lettered": self.dead_lettered,
            "skipped": self.skipped,
            "reason": self.reason,
        }


class OutboxPublisher:
    """Claims recorded events and hands them over. Owns no loop and no policy."""

    def __init__(
        self,
        *,
        outbox: Any,
        sink: EventSink,
        publisher_id: str,
        claim_seconds: int = 60,
        batch_size: int = 50,
        readiness: Optional[Any] = None,
        metrics: Optional[Any] = None,
        clock: Optional[Clock] = None,
    ) -> None:
        if not isinstance(publisher_id, str) or not publisher_id.strip():
            raise ContractViolation(
                "a publisher must identify itself; an anonymous claim cannot be "
                "released by whoever made it and cannot be told from a rival's"
            )
        if claim_seconds < 1:
            raise ContractViolation(
                "a claim must last at least a second; one that expires instantly "
                "would be reclaimed by a rival before this publisher finished"
            )
        if batch_size < 1:
            raise ContractViolation("a batch must contain at least one entry")
        self._outbox = outbox
        self._sink = sink
        self._publisher_id = publisher_id.strip()
        self._claim_seconds = claim_seconds
        self._batch_size = batch_size
        self._readiness = readiness
        self._metrics = SafeMetrics(metrics or NullMetrics())
        self._clock = clock or SystemClock()

    @property
    def publisher_id(self) -> str:
        return self._publisher_id

    # ------------------------------------------------------------------

    def publish_batch(self, context: Any) -> PublishReport:
        """Claim, deliver, acknowledge. One pass, no loop, no sleep.

        The order is the whole design: **claim before delivering**, so two
        publishers cannot hand over the same entry; **acknowledge after
        delivering**, so a crash between the two leaves the entry pending rather
        than marked published. Both failure modes are survivable and only one
        direction loses an event, which is why the risk is taken on the side of
        duplication.
        """
        now = self._clock.now()

        if not self._ready():
            return PublishReport(at=now, skipped=True, reason="durability_unavailable")

        try:
            claimed = self._outbox.claim(
                context,
                publisher_id=self._publisher_id,
                limit=self._batch_size,
                seconds=self._claim_seconds,
            )
        except Exception:  # noqa: BLE001 - a failed claim is not a failed publish
            log.warning("outbox claim failed", exc_info=False)
            return PublishReport(at=now, skipped=True, reason="claim_failed")

        if not claimed:
            return PublishReport(at=now)

        self._metrics.increment(
            "outbox.claim", value=len(claimed), labels={"publisher": self._publisher_id}
        )

        delivered = rejected = unknown = dead = 0
        for entry in claimed:
            outcome = self._deliver(context, entry)
            if outcome is DeliveryOutcome.DELIVERED:
                delivered += 1
                self._acknowledge(context, entry)
            elif outcome is DeliveryOutcome.REJECTED:
                rejected += 1
                if self._record_failure(context, entry, "sink rejected the event"):
                    dead += 1
            else:
                unknown += 1
                # Deliberately **not** marked failed. A failure counts towards
                # dead-lettering, and an event that may well have been delivered
                # must not be dead-lettered for it. The claim lapses and it is
                # published again with the same event id.
                self._metrics.increment(
                    "outbox.publish_unknown", labels={"publisher": self._publisher_id}
                )
                log.warning(
                    "delivery outcome unknown for outbox entry %s; it stays "
                    "pending and will be republished with the same event id",
                    entry.entry_id,
                )

        return PublishReport(
            at=now,
            claimed=len(claimed),
            delivered=delivered,
            rejected=rejected,
            unknown=unknown,
            dead_lettered=dead,
        )

    # ------------------------------------------------------------------

    def _deliver(self, context: Any, entry: Any) -> DeliveryOutcome:
        """Hand one entry over. Anything unclassifiable is ``UNKNOWN``.

        A sink that raised mid-send cannot say whether the message left. Reading
        that as a failure would dead-letter an event that may have been
        delivered; reading it as success would lose one. Unknown is the only
        answer that is true.
        """
        try:
            outcome = self._sink.deliver(context, entry)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "outbox delivery raised for %s (%s); treating as unknown",
                entry.entry_id,
                type(exc).__name__,
            )
            return DeliveryOutcome.UNKNOWN
        if not isinstance(outcome, DeliveryOutcome):
            log.warning(
                "sink returned %s rather than a DeliveryOutcome; treating as unknown",
                type(outcome).__name__,
            )
            return DeliveryOutcome.UNKNOWN
        return outcome

    def _acknowledge(self, context: Any, entry: Any) -> None:
        try:
            self._outbox.mark_published(context, entry.entry_id)
            self._metrics.increment(
                "outbox.publish",
                labels={"publisher": self._publisher_id, "event": entry.event_type},
            )
        except Exception:  # noqa: BLE001
            # Delivered, and the acknowledgement did not land. The entry stays
            # pending and will be delivered again -- which is exactly what
            # at-least-once means, and why the consumer deduplicates.
            log.warning(
                "acknowledging outbox entry %s failed; it will be republished "
                "with the same event id",
                entry.entry_id,
            )

    def _record_failure(self, context: Any, entry: Any, reason: str) -> bool:
        """Count a rejection. Returns whether it dead-lettered this entry."""
        try:
            self._outbox.mark_failed(context, entry.entry_id, reason)
            self._metrics.increment(
                "outbox.publish_failure", labels={"publisher": self._publisher_id}
            )
        except Exception:  # noqa: BLE001
            log.warning("recording an outbox failure failed", exc_info=False)
            return False
        try:
            dead = {e.entry_id for e in self._outbox.dead_lettered(context)}
        except Exception:  # noqa: BLE001
            return False
        if entry.entry_id in dead:
            self._metrics.increment(
                "outbox.dead_letter", labels={"publisher": self._publisher_id}
            )
            log.error(
                "outbox entry %s (event %s) was dead-lettered after repeated "
                "rejection; it is kept, never deleted",
                entry.entry_id,
                entry.event_id or "<none>",
            )
            return True
        return False

    def _ready(self) -> bool:
        if self._readiness is None:
            return True
        try:
            return bool(self._readiness.is_ready())
        except Exception:  # noqa: BLE001 - unverifiable durability is unusable
            return False
