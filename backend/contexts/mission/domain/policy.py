"""Mission policy: whether a transition should be permitted.

The aggregate enforces what is *legal*. This decides what is *advisable*, which
is a different question -- a transition every invariant allows can still be one
nobody should make.

Kept out of the aggregate so the service can report every failure at once. A
transition refused one reason at a time takes five attempts to land, and the
fifth is made by someone who has stopped reading the refusals.

The rules, and the failure each prevents
-----------------------------------------
**P0 the mission is open.** An archived mission is sealed.

**P1 the transition is legal.** The operational table, re-checked here so the
report can carry it alongside everything else rather than raising first.

**P2 a plan is recorded before planning is claimed.** Mission Runtime does not
plan; "planned" with nothing to point at is an assertion about nothing.

**P3 preconditions are met before readiness.** A precondition discovered at
launch has already cost the delay it was meant to prevent.

**P4 an acting mission is authorised before it runs.** A mission that changes a
live system needs an explicit authorisation precondition. The cost of a wrong
observation is a wrong answer; the cost of a wrong action is an outage.

**P5 completion follows verification.** The gate. Constitution S4 forbids
``EXECUTING -> CONCLUDED`` directly, and this is the operational half of the same
rule.

**P6 a running mission has an open execution.** Otherwise "running" describes
nothing that is happening.

**P7 a paused mission can say where it resumes from.** Advisory: pausing without
a checkpoint is legal and means resuming restarts the run, which the operator
should know before it happens rather than after.

**P8 a long-running non-continuous mission is worth a look.** Advisory, and
suppressed for ``MONITOR`` missions, which are long-running by design.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contexts.mission.domain.metadata import MissionKind
from backend.contexts.mission.domain.status import (
    MissionStatus,
    is_legal_status_transition,
    permitted_from,
    refusal_reason,
)

__all__ = [
    "Severity",
    "PolicyFinding",
    "PolicyReport",
    "MissionPolicy",
    "default_policy",
    "AUTHORISATION_PRECONDITION",
]

#: The precondition key a mission that changes a live system must carry.
#: Named rather than inferred, so an operator can see it in the mission's own
#: record instead of trusting that policy applied it.
AUTHORISATION_PRECONDITION = "authorisation.to-act"


class Severity(str, Enum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"

    @property
    def refuses(self) -> bool:
        return self is Severity.BLOCKING


@dataclass(frozen=True)
class PolicyFinding:
    rule: str
    severity: Severity
    detail: str
    subject: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.rule}: {self.detail}"


@dataclass(frozen=True)
class PolicyReport:
    findings: tuple = ()

    @property
    def blocking(self) -> tuple:
        return tuple(f for f in self.findings if f.severity.refuses)

    @property
    def advisory(self) -> tuple:
        return tuple(f for f in self.findings if not f.severity.refuses)

    @property
    def may_transition(self) -> bool:
        return not self.blocking


class MissionPolicy:
    """Decides whether a mission may make a given move."""

    def __init__(self, *, require_authorisation_to_act: bool = True) -> None:
        self._require_authorisation = require_authorisation_to_act

    @property
    def requires_authorisation_to_act(self) -> bool:
        return self._require_authorisation

    def evaluate(self, mission, to_status: MissionStatus) -> PolicyReport:
        """Every finding, not just the first."""
        findings: list = []

        # P0 -- the mission is open.
        if not mission.status.is_open:
            findings.append(
                PolicyFinding(
                    rule="P0-mission-open",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"the mission is {mission.status.value} and sealed; answer it "
                        "with a new mission that cites this one"
                    ),
                    subject=str(mission.mission_id),
                )
            )
            return PolicyReport(findings=tuple(findings))

        # P1 -- the transition is legal.
        if not is_legal_status_transition(mission.status, to_status):
            findings.append(
                PolicyFinding(
                    rule="P1-legal-transition",
                    severity=Severity.BLOCKING,
                    detail=(
                        refusal_reason(mission.status, to_status)
                        or f"{mission.status.value} may only move to: "
                        f"{', '.join(permitted_from(mission.status))}"
                    ),
                    subject=to_status.value,
                )
            )

        # P2 -- a plan is recorded before planning is claimed.
        if to_status is MissionStatus.PLANNED and mission.plan_ref is None:
            findings.append(
                PolicyFinding(
                    rule="P2-plan-recorded",
                    severity=Severity.BLOCKING,
                    detail=(
                        "no plan reference is recorded; Mission Runtime does not plan, "
                        "so it records where the plan lives"
                    ),
                    subject=str(mission.mission_id),
                )
            )

        # P3 -- preconditions before readiness.
        if to_status is MissionStatus.READY:
            for key in mission.outstanding_preconditions:
                findings.append(
                    PolicyFinding(
                        rule="P3-preconditions-met",
                        severity=Severity.BLOCKING,
                        detail=(
                            f"precondition {key!r} is not satisfied; one discovered at "
                            "launch has already cost the delay it was meant to prevent"
                        ),
                        subject=key,
                    )
                )

            # P4 -- an acting mission is authorised.
            if self._require_authorisation and mission.metadata.kind.changes_the_world:
                declared = {p.key for p in mission.preconditions}
                if AUTHORISATION_PRECONDITION not in declared:
                    findings.append(
                        PolicyFinding(
                            rule="P4-authorised-to-act",
                            severity=Severity.BLOCKING,
                            detail=(
                                f"a {mission.metadata.kind.value} mission changes a live "
                                f"system and declares no {AUTHORISATION_PRECONDITION!r} "
                                "precondition; the cost of a wrong observation is a "
                                "wrong answer, the cost of a wrong action is an outage"
                            ),
                            subject=mission.metadata.kind.value,
                        )
                    )

        # P5 -- completion follows verification.
        if to_status is MissionStatus.COMPLETED and not mission.is_verified:
            findings.append(
                PolicyFinding(
                    rule="P5-verified-before-complete",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"the execution is {mission.execution_state.value!r}, not "
                        "'concluded'; Constitution S4 requires verification before an "
                        "execution concludes, and a mission reported complete over "
                        "unverified work is the failure that rule exists to stop"
                    ),
                    subject=mission.execution_state.value,
                )
            )

        # P6 -- a running mission has something running.
        if to_status is MissionStatus.RUNNING and mission.current_execution is None:
            findings.append(
                PolicyFinding(
                    rule="P6-execution-open",
                    severity=Severity.BLOCKING,
                    detail=(
                        "no execution is open; 'running' with nothing in flight "
                        "describes nothing that is happening"
                    ),
                    subject=str(mission.mission_id),
                )
            )

        # P7 -- pausing without a resumption point.
        if to_status is MissionStatus.PAUSED and mission.latest_checkpoint is None:
            findings.append(
                PolicyFinding(
                    rule="P7-resumable",
                    severity=Severity.ADVISORY,
                    detail=(
                        "no checkpoint has been recorded, so resuming restarts the run "
                        "from the beginning; worth knowing before the pause, not after"
                    ),
                    subject=str(mission.mission_id),
                )
            )

        # P8 -- a mission that has been running a long time without concluding.
        if (
            to_status is MissionStatus.COMPLETED
            and mission.metadata.kind is not MissionKind.MONITOR
            and len(mission.executions) > 3
        ):
            findings.append(
                PolicyFinding(
                    rule="P8-repeated-attempts",
                    severity=Severity.ADVISORY,
                    detail=(
                        f"this objective took {len(mission.executions)} executions; a "
                        "non-continuous mission needing repeated attempts usually means "
                        "the objective was scoped wrong rather than executed wrong"
                    ),
                    subject=str(len(mission.executions)),
                )
            )

        return PolicyReport(findings=tuple(findings))


def default_policy() -> MissionPolicy:
    """The policy the Constitution defines."""
    return MissionPolicy(require_authorisation_to_act=True)
