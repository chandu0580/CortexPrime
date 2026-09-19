"""Independent verification of a remediation — Phase 11.4 (ADR-124).

"The executor saying 'rollback succeeded' means nothing by itself."

This module never reads the executor's answer. It observes the world through
the platform's governed READ path -- a different ServiceAccount, a different
process from the worker, a different code path -- computes one declared
proposition from what the cluster says, records it as a World observation, and
asks the existing Assurance verifier to adjudicate the plan's expected state
against it. The verdict is Assurance's; the classification below maps it
without interpretation and names any discrepancy with what the executor said.

The proposition (predicate ``remediation_outcome``)::

    {"templateDigest": <digest of the running pod template>,
     "rolledOut": observedGeneration >= generation and updated == replicas and nothing unavailable,
     "available": Available=True and availableReplicas == replicas,
     "crashLooping": any of the workload's pods waiting in a back-off}

Every field is computed from declared evidence scalars. A field whose evidence
is absent makes the proposition incomplete, and an incomplete proposition is
never recorded as the expected one -- UNKNOWN is not SUCCESS.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Sequence

from backend.api.remediation_planning import OUTCOME_PREDICATE

log = logging.getLogger("cortexprime.remediation.verification")

__all__ = ["outcome_proposition", "VerificationReport", "RemediationVerifier", "BACKOFF_REASONS"]

BACKOFF_REASONS = frozenset({"CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull",
                             "CreateContainerConfigError", "RunContainerError"})

#: The reasoning path the planner's claims are produced under. The verifier's
#: own path differs, and Assurance refuses to verify a claim under its producer's
#: path (self-verification).
PRODUCER_REASONING_PATH = "platform:remediation-planner/1"


def outcome_proposition(*, deployment: Mapping[str, Any], pods: Sequence[Mapping[str, Any]],
                        workload: str) -> Optional[dict]:
    """The declared proposition, or None when the evidence cannot establish it."""
    digest = deployment.get("templateDigest")
    generation = deployment.get("generation")
    observed = deployment.get("observedGeneration")
    replicas = deployment.get("replicas")
    if not isinstance(digest, str) or not all(isinstance(v, int) for v in (generation, observed, replicas)):
        return None
    updated = deployment.get("updatedReplicas", 0)
    unavailable = deployment.get("unavailableReplicas", 0)
    available_replicas = deployment.get("availableReplicas", 0)
    rolled_out = bool(observed >= generation and updated == replicas and not unavailable)
    available = bool(deployment.get("availableCondition") == "True" and available_replicas == replicas)
    mine = [p for p in pods if isinstance(p, Mapping) and str(p.get("name", "")).startswith(f"{workload}-")]
    crash_looping = any(p.get("waitingReason") in BACKOFF_REASONS for p in mine)
    return {"templateDigest": digest, "rolledOut": rolled_out, "available": available,
            "crashLooping": crash_looping}


@dataclass
class VerificationReport:
    verdict: str                      # supported | unsupported | insufficient_evidence
    classification: str              # VERIFIED | VERIFICATION_FAILED | VERIFICATION_INSUFFICIENT
    proposition: Optional[dict]
    expected: dict
    observation_ref: Optional[str] = None
    verification_ref: Optional[str] = None
    evidence_refs: tuple = ()
    rationale: str = ""
    polls: int = 0
    seconds: float = 0.0
    metric: Optional[dict] = None
    discrepancy: Optional[str] = None
    at_target_template: bool = False
    at_pre_action_template: bool = False
    read_failures: tuple = ()
    reads: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.__dict__.items()}


class RemediationVerifier:
    """Reads, records and asks Assurance. Holds no writer, no worker, no approval."""

    def __init__(self, *, reader: Any, context_factory: Callable[[], Any], observer: Any,
                 derivation: Any, assurance: Any, tenant: Any,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self._reader = reader
        self._context = context_factory
        self._observer = observer
        self._derivation = derivation
        self._assurance = assurance
        self._tenant = tenant
        self._clock = clock
        self._sleep = sleep

    def _read(self, operation: str, payload: Mapping[str, Any]):
        try:
            return self._reader.read(self._context(), operation=operation, payload=dict(payload))
        except Exception as exc:  # noqa: BLE001 - a failed read establishes nothing
            log.warning("verification read %s failed: %s", operation, exc)
            return None

    def observe_once(self, *, namespace: str, name: str) -> tuple:
        failures = []
        dep = self._read("kubernetes.deployment.get", {"namespace": namespace, "name": name})
        pods = self._read("kubernetes.pods.list", {"namespace": namespace})
        if dep is None or not getattr(dep, "succeeded", False):
            failures.append(f"deployment.get: {getattr(dep, 'failure_reason', 'no answer')}")
        if pods is None or not getattr(pods, "succeeded", False):
            failures.append(f"pods.list: {getattr(pods, 'failure_reason', 'no answer')}")
        if failures:
            return None, dep, failures
        proposition = outcome_proposition(deployment=dep.evidence, pods=pods.evidence.get("pods") or (),
                                          workload=name)
        return proposition, dep, failures

    def verify(self, *, plan: Any, execution_ref: str, executor_said: str,
               window_seconds: Optional[int] = None, poll_seconds: float = 5.0,
               metric_operation: Optional[str] = None) -> VerificationReport:
        """Poll a bounded window for the world to reach the plan's expected state,
        then record what the world says and adjudicate it. Never retries past the
        window; never reports anything the evidence does not establish."""
        from backend.api.governed_read_observer import ObservationLeg
        from backend.assurance.application.procedures import VerificationProcedure, VerificationProcedureKind

        expected = dict(plan.expected_state)
        namespace, name = plan.target.namespace, plan.target.name
        window = window_seconds or max(c.window_seconds for c in plan.verification_criteria)
        started = time.monotonic()
        deadline = started + window
        polls = 0
        proposition, dep, failures = None, None, []
        while True:
            polls += 1
            proposition, dep, failures = self.observe_once(namespace=namespace, name=name)
            if proposition == expected or time.monotonic() >= deadline:
                break
            self._sleep(poll_seconds)
        seconds = round(time.monotonic() - started, 2)
        report = VerificationReport(verdict="insufficient_evidence", classification="VERIFICATION_INSUFFICIENT",
                                    proposition=proposition, expected=expected, polls=polls, seconds=seconds,
                                    read_failures=tuple(failures))
        if proposition is None or dep is None:
            report.rationale = "the world could not be observed: " + "; ".join(failures or ["incomplete evidence"])
            return report
        report.at_target_template = proposition["templateDigest"] == expected["templateDigest"]
        report.at_pre_action_template = proposition["templateDigest"] == plan.target.current_template_digest

        now = self._clock()
        try:
            recorded = self._observer.observe(
                tenant=self._tenant, outcome=dep, now=now,
                legs=(ObservationLeg(subject_ref=plan.subject_ref, predicate=OUTCOME_PREDICATE,
                                     value=proposition, observed_at=now),))
            observation = recorded[0][0] if recorded else None
            if observation is not None:
                report.observation_ref = observation.record_id
                self._derivation.derive(tenant=self._tenant, observation=observation, recorded_at=now)
        except Exception as exc:  # noqa: BLE001 - an unrecorded observation cannot be verified against
            report.rationale = f"the verification observation could not be recorded: {type(exc).__name__}"
            return report

        if metric_operation:
            metric = self._read(metric_operation, {})
            if metric is not None and getattr(metric, "succeeded", False):
                report.metric = {k: v for k, v in dict(metric.evidence).items()
                                 if isinstance(v, (int, float, str, bool))}

        result = self._assurance.verify(
            tenant=self._tenant,
            procedure=VerificationProcedure(kind=VerificationProcedureKind.COMPARE_WORLD_STATE,
                                            subject_ref=plan.subject_ref, predicate=OUTCOME_PREDICATE,
                                            expected=expected, execution_ref=execution_ref or None),
            producer_reasoning_path=PRODUCER_REASONING_PATH, verified_at=self._clock())
        verdict = getattr(result.verdict, "value", str(result.verdict))
        report.verdict = verdict
        report.verification_ref = getattr(getattr(result, "verification", None), "record_id", None)
        report.evidence_refs = tuple(getattr(getattr(result, "verification", None), "evidence_refs", ()) or ())
        report.rationale = str(getattr(result, "rationale", ""))[:400]
        if verdict == "supported":
            report.classification = "VERIFIED"
        elif verdict == "unsupported":
            report.classification = "VERIFICATION_FAILED"
        else:
            report.classification = "VERIFICATION_INSUFFICIENT"

        # The discrepancy with the executor, named -- never resolved in the
        # executor's favour.
        if report.classification == "VERIFIED" and executor_said in ("failed", "unknown"):
            report.discrepancy = (f"false failure: the executor reported {executor_said}, and the world "
                                  "independently reached the approved state")
        elif report.classification == "VERIFICATION_FAILED" and executor_said == "succeeded":
            report.discrepancy = ("false success: the executor reported success, and the world did not reach "
                                  "the approved state" + (" (the running template never changed)"
                                                          if report.at_pre_action_template else ""))
        return report
