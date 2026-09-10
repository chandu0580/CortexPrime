"""Correlation context and incident-candidate projection — Phase 11.2 (ADR-122).

The bridge toward detection (Prompt 3), without pretending to be it.

A **correlation context** is what a later detector or investigator needs to
relate signals: tenant, cluster, namespace, workload, pod, alert name and
severity, timestamps, the observation ids that carry the evidence. It is
projected from durable observations; nothing here is stored separately, so
re-projecting the same ledger yields the same contexts.

An **incident candidate** is a deterministic grouping of current signals that
*would* interest a detector: pods in a crash or image-pull backoff, pods with
a high restart count, alerts that are firing. It carries the correlation
context and the evidence references and a deterministic ``candidate_id`` so
two projections of the same state agree. It is NOT an incident and NOT an
investigation: opening an investigation is Prompt 3's decision, made through
``InvestigationService.create`` with an ``incident_ref`` that this candidate
can supply. No candidate has authority; none can execute anything.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional

from backend.signal.contract import (
    PREDICATE_ALERT,
    PREDICATE_STATE,
    SUBJECT_ALERTMANAGER_ALERT,
    SUBJECT_KUBERNETES_POD,
    canonical_signal,
)

__all__ = [
    "BACKOFF_REASONS",
    "IncidentCandidate",
    "candidate_id_for",
    "workload_of",
    "project_candidates",
]

#: Container waiting reasons that mean "this pod is not going to become ready
#: by itself". Copied from the Kubernetes vocabulary, not invented.
BACKOFF_REASONS = frozenset({
    "CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "CreateContainerConfigError",
    "InvalidImageName", "CreateContainerError", "RunContainerError", "OOMKilled",
})

#: A pod restarting this many times is a signal even while its current reason
#: is transiently absent. A projection threshold, not a policy: Prompt 3 owns
#: detection policy and may replace it.
RESTART_THRESHOLD = 3


@dataclass(frozen=True)
class IncidentCandidate:
    candidate_id: str
    tenant_id: str
    kind: str
    subject_refs: tuple
    correlation: Mapping[str, Any]
    evidence: tuple  # observation ids
    first_observed_at: datetime
    last_recorded_at: datetime
    sources: tuple
    detail: str = ""
    handoff: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "tenant_id": self.tenant_id,
            "kind": self.kind,
            "subject_refs": list(self.subject_refs),
            "correlation": dict(self.correlation),
            "evidence": list(self.evidence),
            "first_observed_at": self.first_observed_at.isoformat(),
            "last_recorded_at": self.last_recorded_at.isoformat(),
            "sources": list(self.sources),
            "detail": self.detail,
            "handoff": dict(self.handoff),
            "authority": "none",
        }


def candidate_id_for(tenant_id: str, kind: str, key: str) -> str:
    """Deterministic: the same tenant, kind and grouping key always agree."""
    digest = hashlib.sha256(f"{tenant_id}|{kind}|{key}".encode("utf-8")).hexdigest()
    return f"cand_{digest[:24]}"


def workload_of(pod_name: str) -> Optional[str]:
    """The workload a pod name most likely belongs to. INFERRED, and labelled so.

    Deployment pods are ``<deployment>-<replicaset-hash>-<pod-id>``; the watch
    record does not carry ``ownerReferences`` (not a declared field of the
    governed watch operation), so the two trailing segments are stripped. A
    pod named without that shape yields nothing rather than a wrong answer.
    """
    if not pod_name or "-" not in pod_name:
        return None
    parts = pod_name.split("-")
    if len(parts) >= 3 and len(parts[-1]) >= 4 and len(parts[-2]) >= 5:
        return "-".join(parts[:-2])
    if len(parts) >= 2 and len(parts[-1]) >= 4:
        return "-".join(parts[:-1])
    return None


def _pod_candidate(signal, tenant_id: str) -> Optional[IncidentCandidate]:
    value = signal.value
    if value.get("eventType") == "DELETED":
        return None
    reason = value.get("waitingReason")
    restarts = value.get("restartCount")
    try:
        restarts_n = int(restarts) if restarts is not None else 0
    except (TypeError, ValueError):
        restarts_n = 0
    backoff = reason in BACKOFF_REASONS
    if not backoff and restarts_n < RESTART_THRESHOLD:
        return None
    namespace = signal.correlation.get("namespace")
    name = signal.correlation.get("name")
    workload = workload_of(name or "")
    kind = "kubernetes.pod.backoff" if backoff else "kubernetes.pod.restarting"
    key = f"{namespace}/{workload or name}/{reason or 'restarts'}"
    correlation = dict(signal.correlation)
    correlation.update({
        "tenant": tenant_id,
        "workload": workload,
        "workload_inferred_from_name": workload is not None,
        "source": "kubernetes",
        "observed_at": signal.observed_at.isoformat(),
        "recorded_at": signal.recorded_at.isoformat(),
        "resourceVersion": signal.native_identity.get("resourceVersion"),
    })
    return IncidentCandidate(
        candidate_id=candidate_id_for(tenant_id, kind, key),
        tenant_id=tenant_id,
        kind=kind,
        subject_refs=(signal.subject_ref,),
        correlation=correlation,
        evidence=(signal.global_id,),
        first_observed_at=signal.observed_at,
        last_recorded_at=signal.recorded_at,
        sources=("kubernetes",),
        detail=(f"{name} in {namespace}: {reason or 'no waiting reason'}, "
                f"restarts={restarts_n}"),
        handoff={"incident_ref": candidate_id_for(tenant_id, kind, key),
                 "subject_ref": signal.subject_ref, "predicate": PREDICATE_STATE},
    )


def _alert_candidate(signal, tenant_id: str) -> Optional[IncidentCandidate]:
    if signal.value.get("status") != "firing":
        return None
    alertname = signal.correlation.get("alertname") or "unnamed"
    severity = signal.correlation.get("severity")
    key = f"{alertname}/{signal.native_identity.get('fingerprint')}"
    correlation = dict(signal.correlation)
    correlation.update({
        "tenant": tenant_id, "source": "alertmanager",
        "fingerprint": signal.native_identity.get("fingerprint"),
        "startsAt": signal.native_identity.get("startsAt"),
        "recorded_at": signal.recorded_at.isoformat(),
    })
    return IncidentCandidate(
        candidate_id=candidate_id_for(tenant_id, "alertmanager.alert.firing", key),
        tenant_id=tenant_id,
        kind="alertmanager.alert.firing",
        subject_refs=(signal.subject_ref,),
        correlation=correlation,
        evidence=(signal.global_id,),
        first_observed_at=signal.observed_at,
        last_recorded_at=signal.recorded_at,
        sources=("alertmanager",),
        detail=f"{alertname} ({severity or 'no severity'}) firing",
        handoff={"incident_ref": candidate_id_for(tenant_id, "alertmanager.alert.firing", key),
                 "subject_ref": signal.subject_ref, "predicate": PREDICATE_ALERT},
    )


def _merge(existing: IncidentCandidate, new: IncidentCandidate) -> IncidentCandidate:
    """Two pods of one workload (or two evidence rows of one alert) fold into
    one candidate: subjects and evidence accumulate, times widen."""
    return IncidentCandidate(
        candidate_id=existing.candidate_id,
        tenant_id=existing.tenant_id,
        kind=existing.kind,
        subject_refs=tuple(sorted(set(existing.subject_refs) | set(new.subject_refs))),
        correlation={**existing.correlation,
                     "pods": sorted({*existing.correlation.get("pods", []),
                                     existing.correlation.get("name"), new.correlation.get("name")}
                                    - {None})},
        evidence=tuple(sorted(set(existing.evidence) | set(new.evidence))),
        first_observed_at=min(existing.first_observed_at, new.first_observed_at),
        last_recorded_at=max(existing.last_recorded_at, new.last_recorded_at),
        sources=tuple(sorted(set(existing.sources) | set(new.sources))),
        detail=existing.detail if len(existing.subject_refs) >= len(new.subject_refs)
        else new.detail,
        handoff=existing.handoff,
    )


def project_candidates(observations: Iterable[Any], *, tenant_id: str) -> tuple:
    """Project incident candidates from the LATEST observation of each subject.

    Pure and deterministic over its input. Fails closed on tenant: an
    observation of another tenant is skipped, never merged, because a
    candidate that mixed tenants would be the cross-tenant evidence leak the
    fabric exists to prevent.
    """
    by_id: dict = {}
    for observation in observations:
        if observation.tenant.tenant_id != tenant_id:
            continue
        signal = canonical_signal(observation)
        candidate: Optional[IncidentCandidate] = None
        if signal.subject_ref.startswith(SUBJECT_KUBERNETES_POD) and signal.predicate == PREDICATE_STATE:
            candidate = _pod_candidate(signal, tenant_id)
        elif signal.subject_ref.startswith(SUBJECT_ALERTMANAGER_ALERT) and signal.predicate == PREDICATE_ALERT:
            candidate = _alert_candidate(signal, tenant_id)
        if candidate is None:
            continue
        if candidate.candidate_id in by_id:
            by_id[candidate.candidate_id] = _merge(by_id[candidate.candidate_id], candidate)
        else:
            by_id[candidate.candidate_id] = candidate
    return tuple(sorted(by_id.values(), key=lambda c: (c.kind, c.candidate_id)))
