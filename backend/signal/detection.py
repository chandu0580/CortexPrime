"""Deterministic detection over the signal fabric — Phase 11.3 (ADR-123).

SIGNAL → DETECTION EVENT → INCIDENT CANDIDATE → INVESTIGATION.

A *candidate* (Phase 11.2, ``correlation.project_candidates``) says "the latest
observation of this subject looks like a problem". A *detection* says more: the
condition has been SUSTAINED — seen across enough observations, or for long
enough — that it is worth an investigation, and it says why, with the evidence
that made the decision. Detection does not equal incident: a flapping pod that
back-offs once and recovers never becomes a detection.

Everything here is a pure function of observations already in the World Plane.
No model, no threshold learned from data, no I/O. Thresholds are stated
constants (``DetectionPolicy``) so a reviewer can see exactly what "sustained"
means; they are detection defaults, not a learned model, and are recorded on
every event.

A detection is durable: the handoff records it as a ``cw_reasoning`` row of kind
``detection`` with a deterministic identity (tenant, condition, subject, and the
incident-start instant), so a restart neither loses nor duplicates one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from backend.platform.hashing import compute_digest
from backend.signal.contract import (
    PREDICATE_ALERT, PREDICATE_STATE, SUBJECT_ALERTMANAGER_ALERT, SUBJECT_KUBERNETES_POD,
)
from backend.signal.correlation import BACKOFF_REASONS, RESTART_THRESHOLD, IncidentCandidate

__all__ = [
    "DetectionPolicy", "DetectionEvent", "detect", "detection_identity",
    "CONDITION_CRASHLOOP", "CONDITION_RESTARTING", "CONDITION_ALERT_FIRING",
    "CONDITION_POD_UNAVAILABLE",
]

CONDITION_CRASHLOOP = "kubernetes.pod.crashloop"
CONDITION_RESTARTING = "kubernetes.pod.restarting"
CONDITION_POD_UNAVAILABLE = "kubernetes.pod.unavailable"
CONDITION_ALERT_FIRING = "alertmanager.alert.firing"


@dataclass(frozen=True)
class DetectionPolicy:
    """What "sustained" means. Stated, not learned."""

    #: a back-off waiting reason must be observed this many times ...
    crashloop_min_observations: int = 2
    #: ... or persist for at least this long between first and latest observation
    crashloop_min_duration_seconds: float = 60.0
    #: restart-count detections need at least this many restarts
    restart_threshold: int = RESTART_THRESHOLD
    #: an alert must have been firing for at least this long (Alertmanager's own
    #: startsAt) so a flapping rule that resolves in seconds is not investigated
    alert_min_firing_seconds: float = 30.0
    #: a pod waiting on an image pull for this long is unavailable, not starting
    unavailable_min_duration_seconds: float = 120.0
    #: observations older than this are not part of the current condition
    lookback_seconds: float = 1800.0

    def to_dict(self) -> dict:
        return {
            "crashloop_min_observations": self.crashloop_min_observations,
            "crashloop_min_duration_seconds": self.crashloop_min_duration_seconds,
            "restart_threshold": self.restart_threshold,
            "alert_min_firing_seconds": self.alert_min_firing_seconds,
            "unavailable_min_duration_seconds": self.unavailable_min_duration_seconds,
            "lookback_seconds": self.lookback_seconds,
        }


@dataclass(frozen=True)
class DetectionEvent:
    detection_id: str
    tenant_id: str
    condition: str
    subject_ref: str
    severity: str
    signal: str                       # which source produced the signal
    window_start: datetime            # first observation of the condition
    window_end: datetime              # latest observation of the condition
    evidence: tuple                   # observation ids that made the decision
    reason: str
    correlation: Mapping[str, Any] = field(default_factory=dict)
    candidate_id: Optional[str] = None
    policy: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "detection_id": self.detection_id, "tenant_id": self.tenant_id,
            "condition": self.condition, "subject_ref": self.subject_ref,
            "severity": self.severity, "signal": self.signal,
            "window": {"start": self.window_start.isoformat(), "end": self.window_end.isoformat()},
            "evidence": list(self.evidence), "reason": self.reason,
            "correlation": dict(self.correlation), "candidate_id": self.candidate_id,
            "policy": dict(self.policy), "authority": "none",
        }


def detection_identity(*, tenant_id: str, condition: str, subject_ref: str,
                       window_start: datetime) -> str:
    """Deterministic: the same sustained condition on the same subject that
    began at the same instant is the same detection, however many times the
    detector runs."""
    digest = compute_digest({"tenant": tenant_id, "condition": condition,
                             "subject": subject_ref,
                             "start": window_start.replace(microsecond=0).isoformat()}).value
    return f"det_{digest[:24]}"


def _ts(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _observed_at(observation: Any) -> Optional[datetime]:
    instant = getattr(observation, "instant", None)
    if instant is not None:
        return _ts(getattr(instant, "observed_at", None))
    return _ts(getattr(observation, "observed_at", None))


def detect(*, candidates: Sequence[IncidentCandidate], observations: Sequence[Any],
           tenant_id: str, now: datetime, policy: Optional[DetectionPolicy] = None
           ) -> tuple[DetectionEvent, ...]:
    """Turn candidates into detections using the observation history behind
    each subject. ``observations`` is the tenant's recent observation history
    (any order); other tenants' rows are ignored, never mixed."""
    policy = policy or DetectionPolicy()
    horizon = now - timedelta(seconds=policy.lookback_seconds)
    by_subject: dict = {}
    for obs in observations:
        if getattr(getattr(obs, "tenant", None), "tenant_id", None) != tenant_id:
            continue
        when = _observed_at(obs)
        if when is None or when < horizon:
            continue
        by_subject.setdefault(obs.subject_ref, []).append((when, obs))
    for rows in by_subject.values():
        rows.sort(key=lambda pair: pair[0])

    events: list = []
    for candidate in candidates:
        if candidate.tenant_id != tenant_id:
            continue
        for subject in candidate.subject_refs:
            history = by_subject.get(subject, ())
            if subject.startswith(SUBJECT_KUBERNETES_POD):
                event = _detect_pod(candidate, subject, history, tenant_id, now, policy)
            elif subject.startswith(SUBJECT_ALERTMANAGER_ALERT):
                event = _detect_alert(candidate, subject, history, tenant_id, now, policy)
            else:
                event = None
            if event is not None:
                events.append(event)
    events.sort(key=lambda e: (e.window_start, e.subject_ref))
    return tuple(events)


def _detect_pod(candidate, subject, history, tenant_id, now, policy) -> Optional[DetectionEvent]:
    states = [(when, obs) for when, obs in history
              if getattr(obs, "predicate", None) == PREDICATE_STATE and isinstance(obs.value, Mapping)]
    if not states:
        return None
    backoff = [(when, obs) for when, obs in states
               if obs.value.get("waitingReason") in BACKOFF_REASONS]
    restarts = [(when, obs) for when, obs in states
                if isinstance(obs.value.get("restartCount"), int)
                and obs.value.get("restartCount", 0) >= policy.restart_threshold]
    pulls = [(when, obs) for when, obs in states
             if obs.value.get("waitingReason") in ("ErrImagePull", "ImagePullBackOff")]
    latest_when, latest = states[-1]
    correlation = dict(candidate.correlation)
    correlation["observed_at"] = latest_when.isoformat()

    if backoff:
        first, last = backoff[0][0], backoff[-1][0]
        duration = (last - first).total_seconds()
        sustained = (len(backoff) >= policy.crashloop_min_observations
                     or duration >= policy.crashloop_min_duration_seconds)
        if sustained or restarts:
            evidence = tuple(dict.fromkeys(o.record_id for _, o in backoff + restarts))
            start = min(first, restarts[0][0]) if restarts else first
            reason = (f"waiting reason {latest.value.get('waitingReason') or 'CrashLoopBackOff'} "
                      f"observed {len(backoff)} time(s) over {duration:.0f}s")
            if restarts:
                reason += f"; restart count {latest.value.get('restartCount')} >= {policy.restart_threshold}"
            return DetectionEvent(
                detection_id=detection_identity(tenant_id=tenant_id, condition=CONDITION_CRASHLOOP,
                                                subject_ref=subject, window_start=start),
                tenant_id=tenant_id, condition=CONDITION_CRASHLOOP, subject_ref=subject,
                severity="high", signal="kubernetes.watch", window_start=start,
                window_end=max(last, restarts[-1][0] if restarts else last),
                evidence=evidence, reason=reason, correlation=correlation,
                candidate_id=candidate.candidate_id, policy=policy.to_dict())
    if restarts:
        first, last = restarts[0][0], restarts[-1][0]
        evidence = tuple(dict.fromkeys(o.record_id for _, o in restarts))
        return DetectionEvent(
            detection_id=detection_identity(tenant_id=tenant_id, condition=CONDITION_RESTARTING,
                                            subject_ref=subject, window_start=first),
            tenant_id=tenant_id, condition=CONDITION_RESTARTING, subject_ref=subject,
            severity="medium", signal="kubernetes.watch", window_start=first, window_end=last,
            evidence=evidence,
            reason=f"restart count {latest.value.get('restartCount')} >= {policy.restart_threshold} "
                   f"without a back-off waiting reason",
            correlation=correlation, candidate_id=candidate.candidate_id, policy=policy.to_dict())
    if pulls:
        first, last = pulls[0][0], pulls[-1][0]
        if (last - first).total_seconds() >= policy.unavailable_min_duration_seconds:
            return DetectionEvent(
                detection_id=detection_identity(tenant_id=tenant_id, condition=CONDITION_POD_UNAVAILABLE,
                                                subject_ref=subject, window_start=first),
                tenant_id=tenant_id, condition=CONDITION_POD_UNAVAILABLE, subject_ref=subject,
                severity="high", signal="kubernetes.watch", window_start=first, window_end=last,
                evidence=tuple(dict.fromkeys(o.record_id for _, o in pulls)),
                reason=f"image pull failing for {(last - first).total_seconds():.0f}s",
                correlation=correlation, candidate_id=candidate.candidate_id, policy=policy.to_dict())
    return None


def _detect_alert(candidate, subject, history, tenant_id, now, policy) -> Optional[DetectionEvent]:
    alerts = [(when, obs) for when, obs in history
              if getattr(obs, "predicate", None) == PREDICATE_ALERT and isinstance(obs.value, Mapping)]
    if not alerts:
        return None
    latest_when, latest = alerts[-1]
    if latest.value.get("status") != "firing":
        return None
    started = _ts(latest.value.get("startsAt")) or latest_when
    firing_for = (now - started).total_seconds()
    if firing_for < policy.alert_min_firing_seconds:
        return None
    labels = latest.value.get("labels") if isinstance(latest.value.get("labels"), Mapping) else {}
    severity = str(labels.get("severity") or "medium").lower()
    correlation = dict(candidate.correlation)
    correlation.update({"alertname": labels.get("alertname"), "startsAt": latest.value.get("startsAt")})
    return DetectionEvent(
        detection_id=detection_identity(tenant_id=tenant_id, condition=CONDITION_ALERT_FIRING,
                                        subject_ref=subject, window_start=started),
        tenant_id=tenant_id, condition=CONDITION_ALERT_FIRING, subject_ref=subject,
        severity=severity if severity in ("critical", "high", "medium", "low") else "medium",
        signal="alertmanager.webhook", window_start=started, window_end=latest_when,
        evidence=tuple(dict.fromkeys(o.record_id for _, o in alerts)),
        reason=f"alert {labels.get('alertname') or subject} firing for {firing_for:.0f}s "
               f"(>= {policy.alert_min_firing_seconds:.0f}s)",
        correlation=correlation, candidate_id=candidate.candidate_id, policy=policy.to_dict())
