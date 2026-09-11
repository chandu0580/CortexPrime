"""The Phase 11.3 investigation catalog — incident classes, their differentials,
the read-only evidence tools, and the deterministic test plan (ADR-123).

This module is *deployment configuration* for the investigator, in the same
sense ``incident_investigation.py`` (Phase 9.5) is: it names what an incident
class's competing explanations are, which governed READ discriminates which
explanation, and what an observation must look like to support or contradict
each. It decides nothing at runtime. The engine
(``backend/intelligence/application/engine.py``) owns the loop; the World Plane
owns the evidence; this module owns the vocabulary.

Three things are new here relative to 9.5:

1. **Tools over the reads 11.3 exposed** — what the container SAID (its logs,
   from the kubelet, reduced to bounded message patterns), what the control
   plane RECORDED (events), what CHANGED (the ReplicaSet lineage carrying every
   revision's image and creation time), and two metrics views (memory against
   its limit as a ratio; replicas a deployment is short of).
2. **A deterministic test plan.** For each hypothesis, the ordered tests that
   would support or contradict it, each with a *structured* expectation the
   platform evaluates (``matching.matches``). The plan is offered to the engine
   through the SAME governed model boundary a real model uses
   (``PlanModelPort``), traced with ``provider="deterministic"``, so an
   investigation continues — and says how it continued — when no model is
   configured or the model is unavailable. When a model IS configured, its
   proposals are augmented with the plan (``PlanAugmentedModelPort``): the model
   may add hypotheses and tests; the platform still selects, validates and
   evaluates every one.
3. **Incident classes beyond CrashLoopBackOff** — a workload that is
   unavailable (readiness / image / config), and an alert whose labels name a
   workload. An alert that names nothing observable seeds a differential with
   no admissible tool, and the engine concludes INSUFFICIENT_EVIDENCE — which
   is the correct answer, not a failure.

What is deliberately absent: numeric confidence on any hypothesis, a model
verdict anywhere, a write tool, a URL, a query string a caller composes.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any, Callable, Mapping, Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "IncidentClass", "classify_incident", "seed_hypotheses", "hypotheses_compatible",
    "InvestigationWindow", "window_for",
    "PlannedTest", "planned_tests", "PlanModelPort", "PlanAugmentedModelPort",
    "investigation_tools", "ToolComposition",
    "H_STARTUP", "H_CONFIG", "H_DEPENDENCY", "H_RESOURCE", "H_REGRESSION",
    "H_PROBE", "H_IMAGE", "H_UNMAPPED",
    "INSTRUMENT_KUBELET_LOGS", "DEFAULT_LOG_TAIL", "LOG_PATTERN_LIMIT",
    "workload_of_subject", "deployment_subject",
]

# Re-use the 9.5 vocabulary for the CrashLoopBackOff class, verbatim.
from backend.api.incident_investigation import (  # noqa: E402
    H_CONFIG, H_DEPENDENCY, H_REGRESSION, H_RESOURCE, H_STARTUP,
    _deployment_payload, _deployment_revision, _pod_payload, _pod_state,
    _restart_count, _termination,
)

H_PROBE = "h-probe-failure"
H_IMAGE = "h-image-pull-failure"
H_UNMAPPED = "h-unobservable-subject"

#: The kubelet reads container logs from the container runtime's log files —
#: a different measurement path from the API server's status, and the source
#: reference says so, so the lineage policy can place it.
INSTRUMENT_KUBELET_LOGS = "kubelet:container-logs"
DEFAULT_LOG_TAIL = 200
LOG_PATTERN_LIMIT = 8


# ---------------------------------------------------------------------------
# Incident classes and their differentials
# ---------------------------------------------------------------------------

class IncidentClass:
    CRASHLOOP = "kubernetes.pod.crashloop"
    WORKLOAD_UNAVAILABLE = "kubernetes.workload.unavailable"
    ALERT = "alertmanager.alert"
    UNMAPPED = "unobservable"


_POD_REF = re.compile(r"^kubernetes:pod:(?P<ns>[a-z0-9][a-z0-9.-]{0,62})/(?P<name>[a-z0-9][a-z0-9.-]{0,62})$")
_DEPLOY_REF = re.compile(r"^kubernetes:deployment:(?P<ns>[a-z0-9][a-z0-9.-]{0,62})/(?P<name>[a-z0-9][a-z0-9.-]{0,62})$")
_POD_SUFFIX = re.compile(r"-[a-z0-9]{6,10}-[a-z0-9]{5}$|-[a-z0-9]{8,10}$")


def workload_of_subject(subject_ref: str) -> Optional[str]:
    """``kubernetes:pod:ns/app-7d9f8b6c5-abcde`` → ``app`` (inferred from the
    pod name; ownerReferences are not a declared watch field). A deployment
    reference answers its own name."""
    m = _POD_REF.match(subject_ref)
    if m:
        return _POD_SUFFIX.sub("", m.group("name"))
    m = _DEPLOY_REF.match(subject_ref)
    if m:
        return m.group("name")
    return None


def namespace_of_subject(subject_ref: str) -> Optional[str]:
    m = _POD_REF.match(subject_ref) or _DEPLOY_REF.match(subject_ref)
    return m.group("ns") if m else None


def deployment_subject(subject_ref: str) -> Optional[str]:
    ns = namespace_of_subject(subject_ref)
    workload = workload_of_subject(subject_ref)
    if ns and workload:
        return f"kubernetes:deployment:{ns}/{workload}"
    return None


def classify_incident(*, detection_kind: str, subject_ref: str) -> str:
    """Which differential an incident admits. Deterministic, from the
    detection kind and whether the subject is something this investigator can
    observe through a governed read."""
    if not (_POD_REF.match(subject_ref) or _DEPLOY_REF.match(subject_ref)):
        return IncidentClass.UNMAPPED
    if detection_kind in ("kubernetes.pod.crashloop", "kubernetes.pod.backoff",
                          "kubernetes.pod.restarting"):
        return IncidentClass.CRASHLOOP
    if detection_kind in ("kubernetes.workload.unavailable", "kubernetes.pod.unavailable"):
        return IncidentClass.WORKLOAD_UNAVAILABLE
    if detection_kind.startswith("alertmanager."):
        return IncidentClass.ALERT
    return IncidentClass.CRASHLOOP if _POD_REF.match(subject_ref) else IncidentClass.WORKLOAD_UNAVAILABLE


#: (ref, proposition, missing evidence, subject: "pod" | "deployment")
_DIFFERENTIALS: dict = {
    IncidentClass.CRASHLOOP: (
        (H_STARTUP, "the application fails at startup for an application-internal reason "
                    "(an unhandled error, not configuration, not a dependency, not resources)",
         "the container's own log patterns from the run that died", "pod"),
        (H_CONFIG, "required configuration or a secret is missing or invalid",
         "the container's own log patterns from the run that died", "pod"),
        (H_DEPENDENCY, "a dependency the application needs at startup is unreachable",
         "the container's own log patterns from the run that died", "pod"),
        (H_RESOURCE, "the container is being killed for exceeding its resource limits",
         "the container's last termination and its memory against its limit", "pod"),
        (H_REGRESSION, "a recent deployment revision introduced the failure",
         "the ReplicaSet lineage: whether a rollout happened in the window and what it changed",
         "deployment"),
    ),
    IncidentClass.WORKLOAD_UNAVAILABLE: (
        (H_REGRESSION, "a recent deployment revision introduced the failure",
         "the ReplicaSet lineage: whether a rollout happened in the window and what it changed",
         "deployment"),
        (H_PROBE, "the readiness or liveness probe fails, so pods never become ready",
         "the control plane's events for the pod", "pod"),
        (H_IMAGE, "the container image cannot be pulled",
         "the pod's waiting reason and the control plane's events", "pod"),
        (H_CONFIG, "required configuration or a secret is missing or invalid",
         "the container's own log patterns", "pod"),
        (H_RESOURCE, "the container is being killed for exceeding its resource limits",
         "the container's last termination and its memory against its limit", "pod"),
    ),
}
_DIFFERENTIALS[IncidentClass.ALERT] = _DIFFERENTIALS[IncidentClass.WORKLOAD_UNAVAILABLE]
_DIFFERENTIALS[IncidentClass.UNMAPPED] = (
    (H_UNMAPPED, "the signal names no Kubernetes subject this investigator can observe "
                 "through a governed read; nothing can be tested",
     "a subject reference the platform can read", "none"),
)


#: The change-attribution hypothesis is COMPATIBLE with every mechanism
#: hypothesis: "revision N introduced it" and "the configuration is invalid" are
#: one composite explanation when both are supported by evidence, not a
#: conflict. Two mechanism hypotheses still compete.
_CHANGE_HYPOTHESES = frozenset({H_REGRESSION})


def hypotheses_compatible(a: str, b: str) -> bool:
    return a != b and (a in _CHANGE_HYPOTHESES or b in _CHANGE_HYPOTHESES)


def seed_hypotheses(*, incident_class: str, subject_ref: str,
                    created_by: str = "platform:investigation-catalog/1") -> tuple:
    """Seed the differential OPEN with stated gaps (never a finding)."""
    from backend.contracts.intelligence import DifferentialHypothesis, TemporalFit
    from backend.contracts.world import HypothesisStatus

    entries = _DIFFERENTIALS.get(incident_class)
    if entries is None:
        raise ContractViolation(f"unknown incident class {incident_class!r}")
    out = []
    for ref, proposition, gap, kind in entries:
        subject = subject_ref
        if kind == "deployment":
            subject = deployment_subject(subject_ref) or subject_ref
        out.append(DifferentialHypothesis(
            hypothesis_ref=ref, subject_ref=subject, proposition=proposition,
            status=HypothesisStatus.OPEN, temporal_fit=TemporalFit.UNKNOWN,
            missing_evidence=(gap,), created_by=created_by))
    return tuple(out)


# ---------------------------------------------------------------------------
# Investigation windows (section 10 of the phase brief)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InvestigationWindow:
    """Explicit windows an investigation reasons within. Stated assumptions:

    * ``incident_start`` is the earliest instant the signal fabric recorded the
      failing condition (first observation in the candidate's evidence), not
      the instant the investigation opened.
    * ``baseline`` precedes the incident by ``baseline_seconds``; ``active`` runs
      from the incident start to now; the ``change`` window is the span in which
      a rollout counts as "recent" — it starts ``change_lookback_seconds`` before
      the incident start (a rollout AFTER the first failure cannot have caused
      it, but the lookback is generous because source clocks disagree).
    * ``clock_skew_seconds`` is the tolerance applied when comparing instants
      from different sources.
    """

    incident_start: datetime
    now: datetime
    baseline_seconds: int = 900
    change_lookback_seconds: int = 1800
    clock_skew_seconds: int = 30

    @property
    def baseline_start(self) -> datetime:
        return self.incident_start - timedelta(seconds=self.baseline_seconds)

    @property
    def change_start(self) -> datetime:
        return self.incident_start - timedelta(seconds=self.change_lookback_seconds)

    @property
    def change_end(self) -> datetime:
        return self.incident_start + timedelta(seconds=self.clock_skew_seconds)

    def to_dict(self) -> dict:
        return {
            "incident_start": self.incident_start.isoformat(),
            "baseline_start": self.baseline_start.isoformat(),
            "change_window": [self.change_start.isoformat(), self.change_end.isoformat()],
            "active_window": [self.incident_start.isoformat(), self.now.isoformat()],
            "clock_skew_seconds": self.clock_skew_seconds,
            "assumptions": [
                "incident_start is the first recorded observation of the failing condition",
                "a change counts as recent only inside the change window",
                "instants from different sources are compared with the stated skew tolerance",
            ],
        }


def window_for(*, first_observed_at: datetime, now: datetime) -> InvestigationWindow:
    start = first_observed_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if start > now:
        start = now
    return InvestigationWindow(incident_start=start, now=now)


# ---------------------------------------------------------------------------
# Projections: declared evidence → the proposition each tool observes
# ---------------------------------------------------------------------------

_CONFIG_WORDS = ("missing", "not set", "is required", "required env", "no such file",
                 "permission denied", "invalid", "unknown flag", "parse", "config",
                 "environment variable", "secret", "malformed", "unset")
_DEPENDENCY_WORDS = ("connection refused", "timed out", "timeout", "unreachable", "dns",
                     "no route to host", "could not connect", "econnrefused",
                     "name resolution", "dial tcp", "connection reset", "no such host")
_CRASH_WORDS = ("traceback", "panic", "exception", "segfault", "segmentation fault",
                "nullpointer", "stack trace", "fatal")
# Runtime-fault vocabulary that happens to contain a configuration word. A Go
# nil-pointer panic says "invalid memory address"; that "invalid" is the
# runtime describing a fault, not an operator describing a setting. Measured
# on the live cluster (S2): the bad revision's panic was classified as a
# configuration error. These phrases are removed before the configuration
# words are looked for; they still count as a crash signature.
_RUNTIME_FAULT_PHRASES = ("invalid memory address", "nil pointer", "null pointer",
                          "index out of range", "invalid opcode", "invalid pointer",
                          "invalid instruction")


def _classify_patterns(patterns: Sequence[Mapping[str, Any]]) -> dict:
    config = dependency = crash = False
    for record in patterns:
        text = str(record.get("pattern", "")).lower()
        if not text:
            continue
        if any(word in text for word in _DEPENDENCY_WORDS):
            dependency = True
        if any(phrase in text for phrase in _RUNTIME_FAULT_PHRASES):
            crash = True
        stripped = text
        for phrase in _RUNTIME_FAULT_PHRASES:
            stripped = stripped.replace(phrase, " ")
        if any(word in stripped for word in _CONFIG_WORDS):
            config = True
        if any(word in text for word in _CRASH_WORDS):
            crash = True
    return {"configError": config, "dependencyError": dependency, "crashTrace": crash}


def _log_patterns(evidence: Mapping[str, Any]) -> Optional[dict]:
    """The bounded shape of what the container said. The top patterns are
    carried as evidence text (already secret-scrubbed by the normalizer) so a
    human can read WHY a classification was made; they are DATA, and an
    instruction inside them is a message the container logged, not an
    instruction to anyone."""
    line_count = evidence.get("lineCount")
    if not isinstance(line_count, int) or isinstance(line_count, bool):
        return None
    patterns = evidence.get("patterns")
    records = [p for p in patterns if isinstance(p, Mapping)] if isinstance(patterns, list) else []
    classified = _classify_patterns(records)
    top = [{"pattern": str(p.get("pattern", ""))[:200], "count": p.get("count"),
            "level": p.get("level")} for p in records[:LOG_PATTERN_LIMIT]]
    return {
        "available": not bool(evidence.get("logUnavailable", False)),
        "lineCount": line_count,
        "errorLineCount": evidence.get("errorLineCount", 0),
        "truncated": bool(evidence.get("truncated", False)),
        **classified,
        "topPatterns": top,
    }


_PROBE_REASONS = ("Unhealthy",)
_IMAGE_REASONS = ("ErrImagePull", "ImagePullBackOff", "Failed")
_BACKOFF_REASONS = ("BackOff",)


def _events(evidence: Mapping[str, Any]) -> Optional[dict]:
    events = evidence.get("events")
    if not isinstance(events, list):
        return None
    reasons: dict = {}
    probe = image = backoff = False
    warnings = []
    for record in events:
        if not isinstance(record, Mapping):
            continue
        reason = record.get("reason")
        message = str(record.get("message", "")).lower()
        if isinstance(reason, str):
            reasons[reason] = reasons.get(reason, 0) + (record.get("count") if isinstance(record.get("count"), int) else 1)
            if reason in _PROBE_REASONS or "probe failed" in message:
                probe = True
            if reason in _IMAGE_REASONS and ("pull" in message or reason != "Failed"):
                image = True
            if reason in _BACKOFF_REASONS:
                backoff = True
        if record.get("type") == "Warning":
            first = record.get("firstTimestamp") or record.get("lastTimestamp")
            if isinstance(first, str):
                warnings.append(first)
    return {
        "eventCount": evidence.get("eventCount", len(events)),
        "reasons": dict(sorted(reasons.items())),
        "probeFailure": probe,
        "imagePullFailure": image,
        "backoff": backoff,
        "firstWarningAt": min(warnings) if warnings else None,
        "lastWarningAt": max(warnings) if warnings else None,
        "truncated": bool(evidence.get("eventsTruncated", False)),
    }


def _parse_instant(text: Any) -> Optional[datetime]:
    if not isinstance(text, str) or not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _rollout_history(workload: str, window: InvestigationWindow):
    def _project(evidence: Mapping[str, Any]) -> Optional[dict]:
        sets = evidence.get("replicaSets")
        if not isinstance(sets, list):
            return None
        mine = [r for r in sets if isinstance(r, Mapping) and r.get("ownerName") == workload]
        if not mine:
            return None

        def _rev(record: Mapping[str, Any]) -> int:
            try:
                return int(str(record.get("revision", "0")))
            except ValueError:
                return 0

        ordered = sorted(mine, key=lambda r: (_rev(r), str(r.get("creationTimestamp", ""))))
        current = ordered[-1]
        previous = ordered[-2] if len(ordered) >= 2 else None
        rolled_at = _parse_instant(current.get("creationTimestamp"))
        recent = bool(rolled_at and window.change_start <= rolled_at <= window.change_end)
        after = bool(rolled_at and rolled_at > window.change_end)
        return {
            "revisionCount": len(ordered),
            "currentRevision": str(current.get("revision", "")),
            "currentImage": current.get("image"),
            "previousImage": previous.get("image") if previous else None,
            "imageChanged": bool(previous and previous.get("image") != current.get("image")),
            # What the containers RUN changed (image/command/args/env/resources),
            # as opposed to a rollout that touched only template metadata.
            "containerSpecChanged": bool(previous and previous.get("templateDigest") is not None
                                         and previous.get("templateDigest") != current.get("templateDigest")),
            "latestRolloutAt": current.get("creationTimestamp"),
            "recentChange": recent,
            "changeAfterIncident": after,
            "changeWindow": [window.change_start.isoformat(), window.change_end.isoformat()],
        }
    return _project


def _deployment_state(evidence: Mapping[str, Any]) -> Optional[dict]:
    replicas = evidence.get("replicas")
    if not isinstance(replicas, int) or isinstance(replicas, bool):
        return None
    ready = evidence.get("readyReplicas", 0)
    available = evidence.get("availableReplicas", 0)
    ready = ready if isinstance(ready, int) else 0
    available = available if isinstance(available, int) else 0
    return {"replicas": replicas, "readyReplicas": ready, "availableReplicas": available,
            "unavailable": max(0, replicas - available), "short": replicas > available,
            "revision": evidence.get("revision"), "image": evidence.get("image")}


def _subject_series(evidence: Mapping[str, Any], label: str, name: Optional[str]) -> Optional[list]:
    """The series that belong to THIS subject. Every Prometheus operation is
    declared namespace-wide (a caller supplies no selector, so a model cannot
    compose one); the platform narrows the answer to the subject here, by the
    label the operation records. Without this, the first full run took the
    namespace's peak memory ratio and its summed restart counts as evidence
    about one pod. ``None`` when the subject is unknown selects nothing rather
    than everything."""
    series = evidence.get("series")
    if not isinstance(series, list):
        return None
    if name is None:
        return [r for r in series if isinstance(r, Mapping)]
    return [r for r in series if isinstance(r, Mapping) and r.get(label) == name]


def _memory_ratio(evidence: Mapping[str, Any], *, pod: Optional[str] = None) -> Optional[dict]:
    series = _subject_series(evidence, "pod", pod)
    if not series:
        return None
    peak: Optional[float] = None
    limited = True
    for record in series:
        if not isinstance(record, Mapping):
            continue
        raw = record.get("value")
        if not isinstance(raw, str):
            continue
        if raw in ("+Inf", "NaN", "-Inf"):
            limited = False
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        peak = value if peak is None else max(peak, value)
    if peak is None and limited:
        return None
    return {"limited": limited, "peakRatio": round(peak, 4) if peak is not None else None,
            "atOrAboveLimit": bool(limited and peak is not None and peak >= 0.95)}


def _replicas_unavailable(evidence: Mapping[str, Any], *, deployment: Optional[str] = None) -> Optional[dict]:
    series = _subject_series(evidence, "deployment", deployment)
    if series is None:
        return None
    worst = 0
    for record in series:
        if not isinstance(record, Mapping):
            continue
        try:
            worst = max(worst, int(float(record.get("value", "0"))))
        except (TypeError, ValueError):
            continue
    return {"unavailable": worst, "short": worst > 0}


def _restart_count_for(evidence: Mapping[str, Any], *, pod: Optional[str] = None) -> Optional[dict]:
    """The 9.5 restart-count projection, applied to the subject's series only.
    Unchanged in what it reads (so the corroboration engine still sees one
    origin); changed in WHICH series it reads -- the 9.5 one took the first
    series the namespace-wide query returned."""
    series = _subject_series(evidence, "pod", pod)
    if not series:
        return None
    return _restart_count({**evidence, "series": series})


def _restart_onset(evidence: Mapping[str, Any], *, pod: Optional[str] = None) -> Optional[dict]:
    series = _subject_series(evidence, "pod", pod)
    if not series:
        return None
    first_total = last_total = 0
    earliest = None
    for record in series:
        if not isinstance(record, Mapping):
            continue
        try:
            first_total += int(float(record.get("first", "0")))
            last_total += int(float(record.get("last", "0")))
        except (TypeError, ValueError):
            continue
        ts = record.get("firstTimestamp")
        if isinstance(ts, (int, float)):
            earliest = ts if earliest is None else min(earliest, ts)
    return {"restartsIncreased": last_total > first_total, "firstCount": first_total,
            "lastCount": last_total, "windowStartedAt": earliest}


# ---------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ToolComposition:
    """What the runner knows when it composes tools for ONE investigation."""

    subject_ref: str
    window: InvestigationWindow
    restart_count: int = 0
    prometheus: bool = False

    @property
    def workload(self) -> Optional[str]:
        return workload_of_subject(self.subject_ref)

    @property
    def namespace(self) -> Optional[str]:
        return namespace_of_subject(self.subject_ref)


def investigation_tools(composition: ToolComposition) -> tuple:
    """The frozen read-only allowlist for one investigation.

    Every entry binds ONE governed READ to ONE proposition. The model may name a
    key and nothing else. Time bounds and selectors are computed here, by the
    platform, from the composition — never supplied by a model.
    """
    from backend.api.governed_evidence_acquisition import InvestigationTool
    from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
        _LOG_UNAVAILABLE, KUBERNETES_REPLICASETS_OPERATION,
    )
    from backend.contexts.execution.infrastructure.adapters.connectors.prometheus import (
        DEPLOYMENT_UNAVAILABLE_OPERATION, INSTRUMENT_KUBE_STATE_METRICS, INSTRUMENT_KUBELET,
        POD_RESTARTS_OPERATION, POD_RESTARTS_RANGE_OPERATION, RANGE_MAX_SPAN_SECONDS,
    )

    kubernetes_api = "connector:kubernetes"
    window = composition.window
    pod_match = _POD_REF.match(composition.subject_ref)
    pod_name = pod_match.group("name") if pod_match else None
    workload = composition.workload

    def _log_payload(subject: str) -> Mapping[str, Any]:
        payload = dict(_pod_payload(subject))
        payload.update({"tailLines": DEFAULT_LOG_TAIL, "previous": False})
        return payload

    def _previous_log_payload(subject: str) -> Mapping[str, Any]:
        payload = dict(_pod_payload(subject))
        payload.update({"tailLines": DEFAULT_LOG_TAIL, "previous": True})
        return payload

    def _events_payload(subject: str) -> Mapping[str, Any]:
        base = _pod_payload(subject)
        return {"namespace": base["namespace"], "limit": 64,
                "fieldSelector": f"involvedObject.name={base['name']}"}

    def _rs_payload(subject: str) -> Mapping[str, Any]:
        base = _deployment_payload(subject)
        return {"namespace": base["namespace"], "limit": 64}

    def _range_payload(_subject: str) -> Mapping[str, Any]:
        end = int(window.now.timestamp())
        start = max(int(window.baseline_start.timestamp()), end - RANGE_MAX_SPAN_SECONDS)
        return {"start": start, "end": end}

    tools = [
        InvestigationTool(
            key="k8s.pod_state", operation="kubernetes.pod.get",
            subject_kind="kubernetes:pod:", predicate="pod_state",
            describes="the pod's phase and why its container is waiting",
            project=_pod_state, source_ref=kubernetes_api, payload_from_subject=_pod_payload),
        InvestigationTool(
            key="k8s.pod_termination", operation="kubernetes.pod.get",
            subject_kind="kubernetes:pod:", predicate="last_termination",
            describes="the container's last exit code and termination reason",
            project=_termination, source_ref=kubernetes_api, payload_from_subject=_pod_payload),
        # Two log reads, because the kubelet keeps at most two instances: the
        # CURRENT container (for a pod waiting in back-off, that is the run
        # that just died) and the PREVIOUS one. Either may be gone; the
        # projection says so ("available") and an absent log decides nothing.
        InvestigationTool(
            key="k8s.pod_logs", operation="kubernetes.pod.logs",
            subject_kind="kubernetes:pod:", predicate="log_patterns",
            describes="the bounded message patterns of the current container log",
            project=_log_patterns, source_ref=INSTRUMENT_KUBELET_LOGS,
            payload_from_subject=_log_payload, absent_when=_LOG_UNAVAILABLE),
        InvestigationTool(
            key="k8s.pod_logs_previous", operation="kubernetes.pod.logs",
            subject_kind="kubernetes:pod:", predicate="log_patterns_previous",
            describes="the bounded message patterns of the previous container instance log",
            project=_log_patterns, source_ref=INSTRUMENT_KUBELET_LOGS,
            payload_from_subject=_previous_log_payload, absent_when=_LOG_UNAVAILABLE),
        InvestigationTool(
            key="k8s.pod_events", operation="kubernetes.events.list",
            subject_kind="kubernetes:pod:", predicate="events",
            describes="the control plane's events for the pod (back-off, probe, image pull)",
            project=_events, source_ref=kubernetes_api, payload_from_subject=_events_payload),
        InvestigationTool(
            key="k8s.deployment_state", operation="kubernetes.deployment.get",
            subject_kind="kubernetes:deployment:", predicate="deployment_state",
            describes="the deployment's replica counts, revision and image",
            project=_deployment_state, source_ref=kubernetes_api,
            payload_from_subject=_deployment_payload),
        InvestigationTool(
            key="k8s.deployment_revision", operation="kubernetes.deployment.get",
            subject_kind="kubernetes:deployment:", predicate="deployed_revision",
            describes="the deployment's current revision and container image",
            project=_deployment_revision, source_ref=kubernetes_api,
            payload_from_subject=_deployment_payload),
    ]
    if composition.workload:
        tools.append(InvestigationTool(
            key="k8s.rollout_history", operation=KUBERNETES_REPLICASETS_OPERATION,
            subject_kind="kubernetes:deployment:", predicate="rollout_history",
            describes="the ReplicaSet lineage: revisions, images, and whether a rollout "
                      "happened inside the change window",
            project=_rollout_history(composition.workload, window), source_ref=kubernetes_api,
            payload_from_subject=_rs_payload))
    if composition.prometheus:
        tools += [
            InvestigationTool(
                key="metrics.pod_memory", operation="prometheus.pod_memory_ratio",
                subject_kind="kubernetes:pod:", predicate="memory_pressure",
                describes="container working-set memory as a ratio of its limit (cAdvisor)",
                project=partial(_memory_ratio, pod=pod_name), source_ref=INSTRUMENT_KUBELET,
                payload_from_subject=lambda _s: {}),
            InvestigationTool(
                key="metrics.pod_restarts", operation=POD_RESTARTS_OPERATION,
                subject_kind="kubernetes:pod:", predicate="restart_count",
                describes="the restart count as the metrics pipeline reports it",
                project=partial(_restart_count_for, pod=pod_name), source_ref=INSTRUMENT_KUBE_STATE_METRICS,
                payload_from_subject=lambda _s: {}),
            InvestigationTool(
                key="metrics.restart_timeline", operation=POD_RESTARTS_RANGE_OPERATION,
                subject_kind="kubernetes:pod:", predicate="restart_onset",
                describes="whether restarts increased across the investigation window",
                project=partial(_restart_onset, pod=pod_name), source_ref=INSTRUMENT_KUBE_STATE_METRICS,
                payload_from_subject=_range_payload),
            InvestigationTool(
                key="metrics.deployment_unavailable", operation=DEPLOYMENT_UNAVAILABLE_OPERATION,
                subject_kind="kubernetes:deployment:", predicate="replicas_unavailable",
                describes="replicas the deployment is short of, as kube-state-metrics reports",
                project=partial(_replicas_unavailable, deployment=workload), source_ref=INSTRUMENT_KUBE_STATE_METRICS,
                payload_from_subject=lambda _s: {}),
        ]
    return tuple(tools)


# ---------------------------------------------------------------------------
# The deterministic test plan
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlannedTest:
    hypothesis: str
    tool: str
    subject_kind: str            # "pod" | "deployment"
    predicate: str
    evidence_expected: str
    supports_if: str
    contradicts_if: str
    supports_value: Any
    contradicts_value: Any
    residual_uncertainty: str = ""


def _logs_have_errors() -> dict:
    return {"errorLineCount": {"$gte": 1}}


def _log_tests(hypothesis: str, supports_if: str, contradicts_if: str, supports: dict,
               contradicts: Optional[dict], residual: str) -> tuple:
    """The same log test against the current AND the previous container log.
    Both expectations require the log to be available; an absent log matches
    nothing and leaves the hypothesis where it was."""
    from backend.intelligence.application.matching import is_condition

    def _guard(expectation):
        # A plain mapping gains the availability guard; a $-condition keeps its
        # shape (a mapping mixing a key and an operator would match nothing).
        if expectation is None:
            return None
        if is_condition(expectation):
            return {op: [_guard(alt) for alt in alts] if op == "$any_of" else alts
                    for op, alts in expectation.items()}
        return {"available": True, **expectation}

    out = []
    for tool, predicate, which in (("k8s.pod_logs", "log_patterns", "current"),
                                   ("k8s.pod_logs_previous", "log_patterns_previous", "previous")):
        out.append(PlannedTest(
            hypothesis, tool, "pod", predicate,
            f"the container log patterns ({which} instance)",
            supports_if, contradicts_if, _guard(supports), _guard(contradicts), residual))
    return tuple(out)


def _kernel_kill_test(hypothesis: str) -> PlannedTest:
    """The container's last termination, read against an APPLICATION-exit
    hypothesis. Contradiction only: a kernel OOM kill (exit 137 / OOMKilled)
    means the process did not fail on its own, so "it failed at startup on X"
    is not what the restarts are. An ordinary non-zero exit supports nothing
    here -- it says an application failed, not which way (S3 must stay open)."""
    return PlannedTest(
        hypothesis, "k8s.pod_termination", "pod", "last_termination",
        "the container's last exit code and termination reason",
        "(nothing: an application exit does not say which application failure)",
        "the kernel killed the container for memory (exit 137 / OOMKilled); it did not fail on its own",
        None,
        {"$any_of": [{"exitCode": 137}, {"reason": "OOMKilled"}]},
        "a setting that oversizes a heap can still be why the limit was exceeded")


_PLAN: dict = {
    H_RESOURCE: (
        PlannedTest(H_RESOURCE, "k8s.pod_termination", "pod", "last_termination",
                    "the container's last exit code and termination reason",
                    "exit code 137 or reason OOMKilled",
                    "any other exit code and reason",
                    {"$any_of": [{"exitCode": 137}, {"reason": "OOMKilled"}]},
                    {"exitCode": {"$not_in": [137]}, "reason": {"$not_in": ["OOMKilled"]}},
                    "a kernel OOM kill is reported by the kubelet; an application self-limit is not"),
        # Support only. A sample below the limit refutes nothing: cAdvisor
        # updates every ten to fifteen seconds and Prometheus scrapes what it
        # holds, so a burst shorter than that is invisible to the metric. In the
        # OOM scenario the kernel killed the container within a second of the
        # allocation and the scraped peak stayed under a tenth of the limit;
        # the kubelet's termination reason is the direct evidence there.
        PlannedTest(H_RESOURCE, "metrics.pod_memory", "pod", "memory_pressure",
                    "working-set memory as a ratio of the configured limit",
                    "the scraped peak reached the memory limit",
                    "(nothing: a scraped sample below the limit does not exclude a burst between samples)",
                    {"atOrAboveLimit": True},
                    None,
                    "a burst shorter than the scrape interval is invisible to this metric"),
    ),
    H_CONFIG: _log_tests(
        H_CONFIG,
        "the log carries a configuration-shaped error (missing/invalid/required)",
        "the log carries errors and none is configuration-shaped",
        {"configError": True},
        {"configError": False, "dependencyError": True},
        "an application may fail on configuration without saying so") + (_kernel_kill_test(H_CONFIG),),
    H_DEPENDENCY: _log_tests(
        H_DEPENDENCY,
        "the log carries a connectivity-shaped error (refused/timeout/unreachable/dns)",
        "the log carries errors and none is connectivity-shaped",
        {"dependencyError": True},
        {"dependencyError": False, **_logs_have_errors()},
        "a dependency may fail silently or after startup") + (_kernel_kill_test(H_DEPENDENCY),),
    H_STARTUP: _log_tests(
        H_STARTUP,
        "a crash signature (traceback/panic/exception) with no configuration or dependency error",
        "a configuration or dependency error explains the exit instead",
        {"crashTrace": True, "configError": False, "dependencyError": False},
        {"$any_of": [{"configError": True}, {"dependencyError": True}]},
        "an empty log leaves this open: the container may have said nothing") + (_kernel_kill_test(H_STARTUP),),
    H_REGRESSION: (
        PlannedTest(H_REGRESSION, "k8s.rollout_history", "deployment", "rollout_history",
                    "the ReplicaSet lineage of the workload",
                    "a rollout happened inside the change window and it changed what the "
                    "containers run (image, command, args, env, resources)",
                    "no rollout happened inside the change window, or the workload has only "
                    "ever had one revision (nothing to regress from)",
                    {"recentChange": True, "containerSpecChanged": True},
                    {"$any_of": [{"recentChange": False}, {"revisionCount": 1}]},
                    "a rollout that changed only metadata stays open: correlation is not cause"),
    ),
    H_PROBE: (
        PlannedTest(H_PROBE, "k8s.pod_events", "pod", "events",
                    "the control plane's events for the pod",
                    "an Unhealthy / probe-failed event was recorded",
                    "no probe failure was recorded and the pod is crash-looping instead",
                    {"probeFailure": True},
                    {"probeFailure": False, "backoff": True},
                    "events are retained for about an hour by the API server"),
    ),
    H_IMAGE: (
        PlannedTest(H_IMAGE, "k8s.pod_state", "pod", "pod_state",
                    "the pod's phase and waiting reason",
                    "the container waits on ErrImagePull / ImagePullBackOff",
                    "the container waits on something else or runs",
                    {"waitingReason": {"$in": ["ErrImagePull", "ImagePullBackOff"]}},
                    {"waitingReason": {"$not_in": ["ErrImagePull", "ImagePullBackOff"]}},
                    "a pull that eventually succeeds leaves no trace in the current state"),
        PlannedTest(H_IMAGE, "k8s.pod_events", "pod", "events",
                    "the control plane's events for the pod",
                    "an image pull failure event was recorded",
                    "no image pull failure was recorded",
                    {"imagePullFailure": True},
                    {"imagePullFailure": False},
                    "events are retained for about an hour by the API server"),
    ),
}


def planned_tests(*, incident_class: str, available_tools: Sequence[str]) -> tuple:
    """The plan entries whose hypothesis is in the class's differential and
    whose tool is actually exposed."""
    refs = [entry[0] for entry in _DIFFERENTIALS.get(incident_class, ())]
    exposed = set(available_tools)
    return tuple(test for ref in refs for test in _PLAN.get(ref, ()) if test.tool in exposed)


def _planned_to_schema(test: PlannedTest, *, pod_subject: str, deployment_subject_ref: Optional[str]) -> Optional[dict]:
    subject = pod_subject if test.subject_kind == "pod" else deployment_subject_ref
    if not subject:
        return None
    return {
        "discriminates": test.hypothesis, "tool": test.tool, "subject_ref": subject,
        "predicate": test.predicate, "evidence_expected": test.evidence_expected,
        "supports_if": test.supports_if, "contradicts_if": test.contradicts_if,
        "residual_uncertainty": test.residual_uncertainty,
        "supports_value": test.supports_value, "contradicts_value": test.contradicts_value,
    }


def _context_from_prompt(prompt: str) -> dict:
    try:
        document = json.loads(prompt)
    except (TypeError, ValueError):
        return {}
    sections = document.get("sections") if isinstance(document, Mapping) else None
    out: dict = {}
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, Mapping) and section.get("included", True):
                out[section.get("section_type")] = section.get("content")
    return out


class PlanModelPort:
    """A ``harness.ModelPort`` that emits the deterministic test plan as a
    schema-shaped proposal. ``provider="deterministic"``: it holds no
    credential, calls nothing, and every trace says so. It reads the assembled
    context (the prompt) only to skip hypotheses already REFUTED and tests
    already run."""

    provider = "deterministic"
    model = "investigation-plan/1"

    def __init__(self, *, incident_class: str, subject_ref: str, available_tools: Sequence[str]) -> None:
        self._class = incident_class
        self._subject = subject_ref
        self._deployment = deployment_subject(subject_ref)
        self._plan = planned_tests(incident_class=incident_class, available_tools=available_tools)
        # Phase 11.3 (ADR-123 D-16): the plan is STAGED. A test's stage is its
        # position among its own hypothesis's tests: every hypothesis's primary
        # discriminator is stage 0, the previous-instance log and the memory
        # ratio are stage 1, the kernel-kill contradictions stage 2. The port
        # offers only the earliest stage that still has an unrun test, so the
        # engine (which breaks ties on test identity, deliberately never on
        # anything a model could steer) spends the step budget on the decisive
        # reads first. Measured: without staging the silent scenario spent ten
        # steps and never reached the termination read that eliminates
        # resource exhaustion.
        seen: dict = {}
        self._stage: list = []
        for planned in self._plan:
            stage = seen.get(planned.hypothesis, 0)
            seen[planned.hypothesis] = stage + 1
            self._stage.append(stage)
        self._noted: set = set()

    def note_prior_tests(self, refs: Sequence[str]) -> None:
        """What the investigation's own ledger says has run. Phase 11.3 (ADR-123
        D-16): the assembled context drops its ``prior_tests`` section under
        token-budget pressure on real evidence (measured: "context token budget
        exceeded" on the OOM scenario), and a port that learned what ran only
        from the prompt then offered the first stage again and again until the
        engine, finding every offer redundant, settled early. The runner hands
        the port the durable test references before each step; the prompt's
        section is still honoured when present."""
        self._noted.update(str(ref) for ref in refs)

    def proposal_document(self, prompt: str) -> dict:
        from backend.intelligence.application.proposal import test_identity

        context = _context_from_prompt(prompt)
        statuses = {h.get("hypothesis_ref"): h.get("status")
                    for h in (context.get("hypotheses") or []) if isinstance(h, Mapping)}
        ran = {str(ref) for ref in (context.get("prior_tests") or [])} | self._noted
        staged: list = []
        for planned, stage in zip(self._plan, self._stage):
            if statuses.get(planned.hypothesis) == "refuted":
                continue
            shaped = _planned_to_schema(planned, pod_subject=self._subject,
                                        deployment_subject_ref=self._deployment)
            if shaped is None:
                continue
            identity = test_identity(discriminates=shaped["discriminates"], tool=shaped["tool"],
                                     subject_ref=shaped["subject_ref"], predicate=shaped["predicate"])
            if any(identity in ref for ref in ran):
                continue
            staged.append((stage, shaped))
        current = min((stage for stage, _ in staged), default=None)
        tests = [shaped for stage, shaped in staged if stage == current]
        remaining = len(staged)
        return {"interpretation": f"platform test plan for {self._class}: "
                                  f"{remaining} admissible test(s) remain; "
                                  f"offering stage {current} ({len(tests)})",
                "hypotheses": [], "tests": tests}

    async def generate(self, *, system_prompt: str, prompt: str):
        from backend.harness.llm_boundary import ModelInvocation

        started = time.perf_counter()
        document = self.proposal_document(prompt)
        return ModelInvocation(content=json.dumps(document), provider=self.provider,
                               model=self.model, latency_ms=(time.perf_counter() - started) * 1000.0,
                               usage=None, config={"source": "test-plan"})


class PlanAugmentedModelPort:
    """A ``harness.ModelPort`` that asks a REAL model and augments its answer
    with the deterministic plan — or, when the model is unavailable, times out,
    exceeds the token budget or answers unparseably, falls back to the plan
    alone and SAYS SO in the provider label the trace records.

    The model may add hypotheses and tests. It cannot remove a planned test,
    cannot name a tool outside the allowlist (the platform refuses it later),
    and cannot carry any authoritative field (the schema refuses it later).
    """

    def __init__(self, *, model_port: Any, plan: PlanModelPort, timeout_seconds: float = 120.0,
                 max_tokens: Optional[int] = None) -> None:
        self._model = model_port
        self._plan = plan
        self._timeout = timeout_seconds
        self._max_tokens = max_tokens
        self.tokens_used = 0
        self.model_calls = 0
        self.model_failures: list = []

    async def generate(self, *, system_prompt: str, prompt: str):
        import asyncio

        from backend.harness.llm_boundary import ModelInvocation

        plan_document = self._plan.proposal_document(prompt)
        if self._max_tokens is not None and self.tokens_used >= self._max_tokens:
            self.model_failures.append("token budget exhausted")
            return self._plan_only(plan_document, reason="token budget exhausted")
        started = time.perf_counter()
        try:
            self.model_calls += 1
            invocation = await asyncio.wait_for(
                self._model.generate(system_prompt=system_prompt, prompt=prompt),
                timeout=self._timeout)
        except asyncio.TimeoutError:
            self.model_failures.append(f"timeout after {self._timeout:.0f}s")
            return self._plan_only(plan_document, reason="model timeout")
        except Exception as exc:  # noqa: BLE001 - a provider failure is not investigation failure
            from backend.harness.llm_boundary import scrub_text

            self.model_failures.append(f"{type(exc).__name__}: {exc}"[:200])
            # Phase 11.3 (ADR-123 D-17): the span says why the plan answered
            # (e.g. a prompt refused for the provider's window), scrubbed.
            detail = scrub_text(str(exc), max_length=160)
            reason = f"model unavailable: {type(exc).__name__}" + (f": {detail}" if detail else "")
            return self._plan_only(plan_document, reason=reason)
        if invocation.usage is not None:
            self.tokens_used += invocation.usage.total_tokens
        merged, note = _merge_model_and_plan(invocation.content, plan_document)
        if note:
            self.model_failures.append(note)
        config = dict(invocation.config or {})
        used = note is None or note.startswith(PARTIAL_MODEL_OUTPUT)
        config.update({"plan_augmented": True, "model_output_used": used,
                       "model_latency_ms": round((time.perf_counter() - started) * 1000.0, 1)})
        if note:
            config["model_output_problem"] = note
        return ModelInvocation(content=json.dumps(merged), provider=invocation.provider,
                               model=invocation.model, latency_ms=invocation.latency_ms,
                               usage=invocation.usage, config=config)

    @staticmethod
    def _plan_only(document: dict, *, reason: str):
        from backend.harness.llm_boundary import ModelInvocation

        return ModelInvocation(content=json.dumps(document), provider="deterministic",
                               model="investigation-plan/1", latency_ms=0.0, usage=None,
                               config={"source": "test-plan", "fallback_reason": reason})


def _merge_model_and_plan(model_text: str, plan_document: dict) -> tuple:
    """Union the model's proposal with the plan. The model's text is parsed
    loosely here ONLY to merge; the governed boundary re-validates the merged
    document strictly, so nothing the model wrote reaches the engine unless it
    fits the schema. Returns (document, problem-or-None)."""
    from backend.harness.llm_boundary import _strip_markdown_fence

    try:
        parsed = json.loads(_strip_markdown_fence(model_text))
    except (TypeError, ValueError) as exc:
        return dict(plan_document), f"model output is not JSON ({type(exc).__name__})"
    if not isinstance(parsed, Mapping):
        return dict(plan_document), "model output is not an object"
    merged: dict = {
        "interpretation": str(parsed.get("interpretation", ""))[:2000],
        "hypotheses": [], "tests": [],
    }
    dropped = 0
    for item in parsed.get("hypotheses") or []:
        if not isinstance(item, Mapping):
            continue
        ref = str(item.get("ref") or "").strip()
        proposition = str(item.get("proposition") or "").strip()
        subject = str(item.get("subject_ref") or "").strip()
        if not ref or not proposition or not subject:
            # Phase 11.3 (ADR-123 D-20): a hypothesis without a reference cannot be
            # tracked by the differential (glm-5.2 restated the seeded ones with
            # empty references). It is dropped and the drop is stated; the model's
            # valid tests are still used.
            dropped += 1
            continue
        merged["hypotheses"].append({
            "ref": ref[:80], "proposition": proposition[:500],
            "subject_ref": subject[:200],
            "temporal_fit": str(item.get("temporal_fit", "unknown"))[:20]})
    seen = set()
    candidate_tests = list(parsed.get("tests") or [])
    single = parsed.get("test")
    if isinstance(single, Mapping):
        candidate_tests.append(single)
    for item in candidate_tests:
        if not isinstance(item, Mapping):
            continue
        key = (item.get("discriminates"), item.get("tool"), item.get("subject_ref"), item.get("predicate"))
        if key in seen:
            continue
        seen.add(key)
        merged["tests"].append({k: item.get(k) for k in (
            "discriminates", "tool", "subject_ref", "predicate", "evidence_expected",
            "supports_if", "contradicts_if", "residual_uncertainty",
            "supports_value", "contradicts_value") if k in item})
    for planned in plan_document.get("tests", []):
        key = (planned["discriminates"], planned["tool"], planned["subject_ref"], planned["predicate"])
        if key not in seen:
            seen.add(key)
            merged["tests"].append(planned)
    if not merged["interpretation"]:
        merged["interpretation"] = plan_document.get("interpretation", "")
    if dropped:
        return merged, f"{PARTIAL_MODEL_OUTPUT} {dropped} model hypothesis(es) without a reference, subject or proposition dropped"
    return merged, None


# A merge note that begins with this means the model's output WAS used, minus what
# the note names; any other note means the plan answered alone.
PARTIAL_MODEL_OUTPUT = "partial:"
