"""Harness version identity — L15's precondition.

A harness change that cannot be named cannot be evaluated, promoted, or rolled
back, and a failure that cannot be joined to the harness version that produced
it cannot be attributed (L14). So the version is a frozen value object whose
identity is a digest over its policy components: change any policy — loop,
schema, context, tool exposure, budget — and the identity changes with it.

There is deliberately no setter, no registry, no reload hook. The running
process carries exactly the version it was started with; changing the harness
is a code change, reviewed and deployed like one. Self-modification is not a
missing feature here — its absence is the feature (Phase 6.0 §19).
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.platform.hashing import compute_digest

__all__ = ["HarnessVersion", "CURRENT_HARNESS_VERSION"]


@dataclass(frozen=True)
class HarnessVersion:
    """The immutable identity of one harness configuration."""

    release: str
    loop_policy: str
    schema_policy: str
    context_policy: str
    tool_exposure_policy: str
    budget_policy: str

    @property
    def identity(self) -> str:
        """``release+digest12`` — stable for identical policies, different for
        any policy change. This string goes on every trace span."""
        digest = compute_digest(
            {
                "release": self.release,
                "loop_policy": self.loop_policy,
                "schema_policy": self.schema_policy,
                "context_policy": self.context_policy,
                "tool_exposure_policy": self.tool_exposure_policy,
                "budget_policy": self.budget_policy,
            }
        )
        return f"{self.release}+{digest.value[:12]}"


#: The harness this build ships. Policy strings are versioned names, not prose:
#: bump the suffix when the behaviour changes, and the identity moves with it.
CURRENT_HARNESS_VERSION = HarnessVersion(
    release="6.1.0",
    loop_policy="loop/budgeted-stop-reasons/1",
    schema_policy="schema/strict-json-pydantic/1",
    context_policy="context/scrub-before-send/1",
    tool_exposure_policy="tools/governed-gateway-only/1",
    budget_policy="budget/iter-tool-clock-token/1",
)
