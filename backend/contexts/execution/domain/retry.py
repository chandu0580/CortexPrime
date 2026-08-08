"""Retry as an explicit, recorded decision.

Retry is not ``state = FAILED; state = READY``. That form of retry has no
reason, no policy, no delay, and no record that it happened, which means an
incident review cannot tell a deliberate second attempt from a runtime that lost
track of itself.

Who owns what
---------------
**Workflow** owns retry *legality*: how many attempts a node may have, what
backoff, whether an idempotency key was supplied. That is part of the approved
graph and this context does not get to change it.

**Execution** owns retry *execution*: given a failure that actually happened,
may this node run again right now, and if so when. That decision needs facts
Workflow cannot have -- what went wrong, whether the outcome is known, how many
attempts are already spent.

So the policy here reads the spec's limits and never rewrites them.

Determinism
-------------
The delay is a pure function of (attempt number, policy). Jitter is derived from
a caller-supplied seed rather than a random source, so replaying a history
produces the same schedule it originally produced. A runtime whose recovery plan
changes every time you ask it is not one you can reason about during an
incident.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contracts.errors import ContractViolation
from backend.contexts.execution.domain.effects import EffectProfile
from backend.contexts.execution.domain.failure import FailureClass, FailureRecord

__all__ = [
    "RetryVerdict",
    "BackoffKind",
    "RetryPolicy",
    "RetryDecision",
    "decide_retry",
    "DEFAULT_RETRY_POLICY",
]

_MAX_DELAY_SECONDS = 3600


class RetryVerdict(str, Enum):
    """What the runtime concluded about running this node again."""

    RETRY = "retry"
    """Run it again, after the stated delay."""

    EXHAUSTED = "exhausted"
    """It could be retried, but the attempts the workflow allowed are spent."""

    NOT_RETRYABLE = "not_retryable"
    """A further attempt fails the same way. Retrying is only a slower report."""

    UNSAFE_TO_RETRY = "unsafe_to_retry"
    """It might succeed, but nobody can say whether the last attempt already
    changed something, and repeating it is not safe. The most important verdict
    in this module: it is the one that stops a delete happening twice."""

    REFUSED_BY_DELIVERY = "refused_by_delivery"
    """At-most-once delivery. The runtime committed to not repeating this after
    ambiguity, and it is keeping that promise."""

    @property
    def may_run_again(self) -> bool:
        return self is RetryVerdict.RETRY

    @property
    def needs_a_human(self) -> bool:
        return self in {
            RetryVerdict.UNSAFE_TO_RETRY,
            RetryVerdict.REFUSED_BY_DELIVERY,
        }


class BackoffKind(str, Enum):
    IMMEDIATE = "immediate"
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


@dataclass(frozen=True)
class RetryPolicy:
    """How long to wait. Bounded, because unbounded backoff is a stall."""

    kind: BackoffKind = BackoffKind.EXPONENTIAL
    initial_delay_seconds: int = 1
    max_delay_seconds: int = 300
    jitter_seconds: int = 0

    def __post_init__(self) -> None:
        if self.initial_delay_seconds < 0:
            raise ContractViolation("initial_delay_seconds cannot be negative")
        if self.max_delay_seconds < self.initial_delay_seconds:
            raise ContractViolation(
                "max_delay_seconds cannot be below initial_delay_seconds; a "
                "ceiling under the floor silently makes every delay the ceiling"
            )
        if self.max_delay_seconds > _MAX_DELAY_SECONDS:
            raise ContractViolation(
                f"max_delay_seconds above {_MAX_DELAY_SECONDS} is a stall wearing "
                "a retry's clothes; a run that waits an hour between attempts "
                "should be paused so somebody is told"
            )
        if self.jitter_seconds < 0:
            raise ContractViolation("jitter_seconds cannot be negative")

    def delay_for(self, attempt_number: int, *, seed: int = 0) -> int:
        """Seconds to wait before ``attempt_number``. Deterministic.

        ``seed`` spreads a thundering herd without a random source: same seed,
        same schedule, so a replay reproduces the original timing exactly.
        """
        if attempt_number < 2:
            return 0
        step = attempt_number - 2
        if self.kind is BackoffKind.IMMEDIATE:
            base = 0
        elif self.kind is BackoffKind.FIXED:
            base = self.initial_delay_seconds
        elif self.kind is BackoffKind.LINEAR:
            base = self.initial_delay_seconds * (step + 1)
        else:
            base = self.initial_delay_seconds * (2**step)
        if self.jitter_seconds:
            base += (seed + attempt_number) % (self.jitter_seconds + 1)
        return max(0, min(base, self.max_delay_seconds))


DEFAULT_RETRY_POLICY = RetryPolicy()


@dataclass(frozen=True)
class RetryDecision:
    """The recorded answer to 'may this run again, and when'."""

    verdict: RetryVerdict
    node_id: str
    previous_attempt: int
    next_attempt: Optional[int]
    delay_seconds: int
    reason: str
    failure_class: Optional[FailureClass] = None
    attempts_allowed: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.verdict, RetryVerdict):
            raise ContractViolation("verdict must be a RetryVerdict")
        if not self.reason.strip():
            raise ContractViolation(
                "a retry decision must say why; a retry nobody can explain is "
                "indistinguishable from a loop"
            )
        if self.verdict.may_run_again and self.next_attempt is None:
            raise ContractViolation(
                "a decision to retry must name the attempt it authorises"
            )
        if not self.verdict.may_run_again and self.next_attempt is not None:
            raise ContractViolation(
                "only a decision to retry may name a next attempt; naming one "
                "otherwise invites a caller to run it"
            )

    @property
    def may_run_again(self) -> bool:
        return self.verdict.may_run_again

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "node_id": self.node_id,
            "previous_attempt": self.previous_attempt,
            "next_attempt": self.next_attempt,
            "delay_seconds": self.delay_seconds,
            "reason": self.reason,
            "failure_class": self.failure_class.value if self.failure_class else None,
            "attempts_allowed": self.attempts_allowed,
        }


def decide_retry(
    *,
    node_id: str,
    attempts_spent: int,
    attempts_allowed: int,
    effect: EffectProfile,
    failure: Optional[FailureRecord] = None,
    policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    seed: int = 0,
) -> RetryDecision:
    """Decide whether a node may run again. Pure, and therefore replayable.

    The order of the checks is the design. Safety is evaluated before
    worthwhileness, so an operation that must not repeat is refused even when
    the failure looks eminently retryable -- which is precisely the case where a
    naive runtime does the damage.
    """
    failure_class = failure.failure_class if failure else None
    ambiguous = failure.failure_class.is_ambiguous if failure else False

    # 1. Ambiguity first. If we cannot say whether the last attempt changed
    #    anything, the effect decides -- not how retryable the error looked.
    if ambiguous and not effect.may_retry_after_ambiguity:
        if not effect.semantics.is_repeatable:
            return RetryDecision(
                verdict=RetryVerdict.UNSAFE_TO_RETRY,
                node_id=node_id,
                previous_attempt=attempts_spent,
                next_attempt=None,
                delay_seconds=0,
                reason=(
                    f"the outcome is unknown ({failure_class.value}) and this node "
                    f"is {effect.semantics.value}; running it again could apply the "
                    "change a second time. Reconcile the external state, compensate, "
                    "or skip it deliberately"
                ),
                failure_class=failure_class,
                attempts_allowed=attempts_allowed,
            )
        return RetryDecision(
            verdict=RetryVerdict.REFUSED_BY_DELIVERY,
            node_id=node_id,
            previous_attempt=attempts_spent,
            next_attempt=None,
            delay_seconds=0,
            reason=(
                "delivery is at-most-once and the outcome is unknown; the runtime "
                "undertook not to repeat this after ambiguity and is not going to"
            ),
            failure_class=failure_class,
            attempts_allowed=attempts_allowed,
        )

    # 2. Failures that a further attempt cannot fix.
    if failure_class is not None and failure_class.is_terminal_for_the_node:
        return RetryDecision(
            verdict=RetryVerdict.NOT_RETRYABLE,
            node_id=node_id,
            previous_attempt=attempts_spent,
            next_attempt=None,
            delay_seconds=0,
            reason=(
                f"{failure_class.value} does not clear by trying again; a retry "
                "would fail identically and delay the report"
            ),
            failure_class=failure_class,
            attempts_allowed=attempts_allowed,
        )

    # 3. The budget the workflow approved. Execution does not extend it.
    if attempts_spent >= attempts_allowed:
        return RetryDecision(
            verdict=RetryVerdict.EXHAUSTED,
            node_id=node_id,
            previous_attempt=attempts_spent,
            next_attempt=None,
            delay_seconds=0,
            reason=(
                f"{attempts_spent} of {attempts_allowed} attempts are spent; the "
                "limit belongs to the approved workflow and execution does not "
                "raise it"
            ),
            failure_class=failure_class,
            attempts_allowed=attempts_allowed,
        )

    next_attempt = attempts_spent + 1
    return RetryDecision(
        verdict=RetryVerdict.RETRY,
        node_id=node_id,
        previous_attempt=attempts_spent,
        next_attempt=next_attempt,
        delay_seconds=policy.delay_for(next_attempt, seed=seed),
        reason=(
            f"attempt {attempts_spent} ended "
            + (f"in {failure_class.value}" if failure_class else "without success")
            + f"; {effect.semantics.value} work may be attempted again within the "
            f"{attempts_allowed} the workflow allowed"
        ),
        failure_class=failure_class,
        attempts_allowed=attempts_allowed,
    )
