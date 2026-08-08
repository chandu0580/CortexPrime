"""Test and build outcomes.

Both record what a command *did*, not what someone said it did. That distinction
is the reason these exist as value objects rather than a summary string: a
verifier reproducing a claim needs the command to re-run, and "tests pass" is not
a command.

Counts are recorded and never used as a gate
---------------------------------------------
``passed``/``failed``/``skipped`` size a run for a reader. They do not decide
anything, because a rule keyed on a count optimises for the count -- the first
response to "no failures allowed" is a skip, and the first response to "N tests
required" is N trivial tests. What decides is ``failed == 0``, which is a
different claim and is checked as one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = ["ExecutionStatus", "TestExecution", "BuildResult"]


class ExecutionStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERRORED = "errored"
    NOT_RUN = "not_run"

    @property
    def is_green(self) -> bool:
        return self is ExecutionStatus.PASSED

    @property
    def was_attempted(self) -> bool:
        """``NOT_RUN`` is distinct from ``FAILED``, and the distinction matters.

        A suite that failed tells a reviewer the work is wrong. One that was never
        run tells them nothing about the work and something about the submission.
        Collapsing them into "not green" loses exactly the part they need.
        """
        return self is not ExecutionStatus.NOT_RUN


@dataclass(frozen=True)
class TestExecution(Contract):
    """One test run: the command, the outcome, and the tree it ran against."""

    #: pytest tries to collect any class named ``Test*``, warning on each import.
    #: This is a value object, not a test case.
    __test__ = False

    CONTRACT_NAME = "cortexprime.engineering.test_execution"

    command: str
    status: ExecutionStatus
    revision: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_seconds: Optional[float] = None
    suite: Optional[str] = None
    output_digest: Optional[str] = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.command, str) or not self.command.strip():
            raise ContractViolation(
                "a test execution must record the exact command; 'tests pass' is not a "
                "command a verifier can re-run"
            )
        object.__setattr__(self, "command", self.command.strip())

        if not isinstance(self.status, ExecutionStatus):
            raise ContractViolation("status must be an ExecutionStatus")
        if not isinstance(self.revision, str) or not self.revision.strip():
            raise ContractViolation(
                "a test execution must name the revision it ran against; the same "
                "command against a different tree is a different result"
            )

        for label in ("passed", "failed", "skipped", "errors"):
            value = getattr(self, label)
            if not isinstance(value, int) or value < 0:
                raise ContractViolation(f"{label} must be a non-negative integer")

        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ContractViolation("duration_seconds must not be negative")
        if self.executed_at.tzinfo is None:
            raise ContractViolation("executed_at must be timezone-aware")

        # The status and the counts must tell the same story. A run reported green
        # with failures in it is the single most misleading artifact this context
        # could produce, because a reader who trusts the status stops reading.
        if self.status is ExecutionStatus.PASSED and (self.failed or self.errors):
            raise ContractViolation(
                f"{self.command!r} is reported passed with {self.failed} failed and "
                f"{self.errors} errored; the status contradicts the counts"
            )
        if self.status is ExecutionStatus.NOT_RUN and (
            self.passed or self.failed or self.skipped or self.errors
        ):
            raise ContractViolation(
                f"{self.command!r} is reported not-run but carries counts; a run that "
                "produced numbers was run"
            )

    @property
    def is_green(self) -> bool:
        return self.status.is_green and not self.failed and not self.errors

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped + self.errors

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.status.value}:{self.command[:40]}"


@dataclass(frozen=True)
class BuildResult(Contract):
    """The outcome of building, linting, or gating the change.

    Separate from :class:`TestExecution` because the two fail differently. A
    failing test says a behaviour is wrong; a failing build says the artifact does
    not exist. A reviewer needs to know which, and a single "checks" type would
    make them ask.
    """

    CONTRACT_NAME = "cortexprime.engineering.build_result"

    name: str
    command: str
    status: ExecutionStatus
    revision: str
    output_digest: Optional[str] = None
    detail: Optional[str] = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        for label, value in (
            ("name", self.name),
            ("command", self.command),
            ("revision", self.revision),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "command", self.command.strip())

        if not isinstance(self.status, ExecutionStatus):
            raise ContractViolation("status must be an ExecutionStatus")
        if self.executed_at.tzinfo is None:
            raise ContractViolation("executed_at must be timezone-aware")

        # A failure that does not say what failed is a failure nobody can act on.
        if self.status in (ExecutionStatus.FAILED, ExecutionStatus.ERRORED) and not (
            self.detail and self.detail.strip()
        ):
            raise ContractViolation(
                f"{self.name!r} is reported {self.status.value} with no detail; a "
                "failure nobody can act on is worse than none reported"
            )

    @property
    def is_green(self) -> bool:
        return self.status.is_green

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.name}:{self.status.value}"
