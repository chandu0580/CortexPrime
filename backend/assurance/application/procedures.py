"""Verification procedures — typed, deterministic, versioned. Never model code.

A procedure names HOW the Assurance Plane obtains independent evidence and what
it compares. It is a typed descriptor resolved against a frozen registry of
deterministic evaluators — exactly like the harness tool exposure, where a model
may name a key but never supply a Python target, a shell string, a URL, or SQL.

The model cannot invent a procedure: ``VerificationProcedureKind`` is a closed
enum, and the parameters are typed references, not code. A procedure a caller
names that is not in the registry is refused.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

__all__ = [
    "VerificationProcedureKind",
    "VerificationProcedure",
    "PROCEDURE_VERSION",
]

#: Bumped when the procedure semantics change; travels on every verification so a
#: verdict is always attributable to the exact procedure ruleset that produced it.
PROCEDURE_VERSION = 1


class VerificationProcedureKind(str, Enum):
    """The closed set of verification procedures. No dynamic/model-authored
    procedure exists; adding one is a code + ADR change, never a runtime input."""

    COMPARE_WORLD_STATE = "compare_world_state"
    """Independently query the current/as-of world state for (subject, predicate)
    and compare it to the claimed expected value."""

    COMPARE_PREDICTION_OUTCOME = "compare_prediction_outcome"
    """After a prediction's horizon, independently obtain the world state for the
    predicted subject and compare it to the prediction's expected value."""

    INSPECT_EXECUTION_RESULT = "inspect_execution_result"
    """Compare a claimed outcome against the world state observed after a real
    governed execution (identified by execution_ref). The outcome is never
    created here; only compared."""


@dataclass(frozen=True)
class VerificationProcedure:
    """A typed procedure descriptor. ``subject_ref``/``predicate`` name what to
    verify; ``expected`` is the claimed value to compare independent evidence
    against; ``at_valid``/``execution_ref`` scope the evidence. All references,
    no code."""

    kind: VerificationProcedureKind
    subject_ref: str
    predicate: str
    expected: Any
    at_valid: Optional[Any] = None            # datetime; world-time to verify at
    execution_ref: Optional[str] = None
    version: int = PROCEDURE_VERSION

    @property
    def procedure_ref(self) -> str:
        """A stable, inspectable reference for this procedure (goes on the
        WorldVerification's ``procedure_ref``)."""
        return f"procedure:{self.kind.value}/{self.version}"
