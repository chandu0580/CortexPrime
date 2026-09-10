"""The canonical signal contract — Phase 11.2 (ADR-122).

One contract, by composition, not duplication
----------------------------------------------
CortexPrime already has two verified contracts at the two edges of the signal
path:

* Prompt 1's ``IngressEnvelope`` (``backend.safety.ingress_boundary``) is the
  **boundary receipt**: who delivered it, which tenant, how it authenticated,
  the payload digest, the trust class. It exists for HTTP ingress and is
  written to the audit trail, never persisted as world knowledge.
* the World Plane's ``Observation`` (``backend.contracts.world``) is the
  **durable canonical event**: tenant, instrument (source kind + ref), subject,
  predicate, value, the instant observed and retrieved, the moment recorded,
  provenance (produced_by, execution_ref, trace_ref), and an identity digest
  over (tenant, source, subject, predicate, observed_at, value) enforced by a
  unique constraint.

The canonical signal is therefore an Observation whose ``subject_ref`` and
``value`` follow a source-specific shape, viewed through :class:`CanonicalSignal`.
This module names the shapes, defines identity, and states delivery semantics.
It stores nothing.

Identity: GLOBAL + SOURCE-NATIVE
--------------------------------
* **Global event identity** — ``Observation.record_id`` (a ULID, unique) and
  the ``identity_digest`` (deterministic: two deliveries of the same external
  observation collide and the second is DEDUPED). Both are tenant-scoped by
  construction because the tenant is part of the digest.
* **Source-native identity** — what the source itself uses to name an event:

  ===============  ==========================================================
  Kubernetes       cluster ref + namespace + kind + name (+ uid) as the subject;
                   ``resourceVersion`` + ``eventType`` distinguish deliveries
  Alertmanager     ``fingerprint`` (Alertmanager's own label-set hash) as the
                   subject; ``startsAt`` + ``status`` distinguish lifecycle
  OTLP (V1 route)  trace id / span id (not yet a World signal; see ADR-122)
  ===============  ==========================================================

  Source-native identity is never forced into one scheme; it is carried in the
  subject and the value so a consumer can reason with the source's semantics.

Delivery semantics, by source (never exactly-once)
--------------------------------------------------
* Kubernetes watch: **at-least-once** by construction (events are recorded
  before the position advances; a crash re-delivers the window). Re-delivery
  is DEDUPED on identity. Loss is possible only across a ``410 Gone`` or a
  stall-relist, and both are recorded as checkpoint provenance
  (``origin=list_after_expiry`` / ``list_after_stall``) -- explicit, never
  silent.
* Alertmanager webhook: Alertmanager retries on non-2xx and re-notifies on
  ``repeat_interval``, so **at-least-once**; a repeated notification of the same
  alert lifecycle state collides on identity (``fingerprint`` + ``startsAt`` +
  the notification's value) and is DEDUPED -- **effectively-once per lifecycle
  state**, not per notification.
* HTTP token ingestion: at-least-once; identity per the same rule.

Ordering
--------
No global order is claimed. Kubernetes gives per-stream order through
``resourceVersion`` (opaque, comparable only for equality); Alertmanager gives
lifecycle order through ``startsAt``/``endsAt``; CortexPrime's own order is
``recorded_at`` + ULID. Consumers read ``recorded_at`` for "what did we learn
when" and the source fields for "what happened when".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional

__all__ = [
    "SUBJECT_KUBERNETES_POD",
    "SUBJECT_KUBERNETES_STREAM",
    "SUBJECT_ALERTMANAGER_ALERT",
    "PREDICATE_STATE",
    "PREDICATE_ALERT",
    "PREDICATE_WATCH_POSITION",
    "SOURCE_REF_KUBERNETES",
    "SOURCE_REF_ALERTMANAGER",
    "DeliverySemantics",
    "SignalSource",
    "CanonicalSignal",
    "canonical_signal",
]

SUBJECT_KUBERNETES_POD = "kubernetes:pod:"
SUBJECT_KUBERNETES_STREAM = "kubernetes:podstream:"
SUBJECT_ALERTMANAGER_ALERT = "alertmanager:alert:"

#: The pod-state predicate is the one the 9.2 governed read and the 9.3 watch
#: already use, so a pod seen by LIST, by WATCH and by GET is one proposition.
PREDICATE_STATE = "state"
PREDICATE_ALERT = "alert"
PREDICATE_WATCH_POSITION = "watch_position"

SOURCE_REF_KUBERNETES = "connector:kubernetes"
SOURCE_REF_ALERTMANAGER = "webhook:alertmanager"


class DeliverySemantics(str, Enum):
    AT_LEAST_ONCE = "at-least-once"
    EFFECTIVELY_ONCE_PER_STATE = "effectively-once-per-lifecycle-state"


class SignalSource(str, Enum):
    KUBERNETES = "kubernetes"
    ALERTMANAGER = "alertmanager"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CanonicalSignal:
    """A read-only view of one durable observation as a signal.

    Every field is copied from the observation or derived from its subject and
    value; nothing is invented. ``native_identity`` is the source's own naming
    (see the module docstring); ``global_id`` is the World Plane's.
    """

    global_id: str
    tenant_id: str
    source: SignalSource
    source_ref: str
    subject_ref: str
    predicate: str
    event_type: str
    observed_at: datetime
    recorded_at: datetime
    native_identity: Mapping[str, Any]
    correlation: Mapping[str, Any]
    delivery: DeliverySemantics
    produced_by: str
    execution_ref: Optional[str]
    trace_ref: Optional[str]
    value: Mapping[str, Any]

    def to_dict(self) -> dict:
        return {
            "global_id": self.global_id,
            "tenant_id": self.tenant_id,
            "source": self.source.value,
            "source_ref": self.source_ref,
            "subject_ref": self.subject_ref,
            "predicate": self.predicate,
            "event_type": self.event_type,
            "observed_at": self.observed_at.isoformat(),
            "recorded_at": self.recorded_at.isoformat(),
            "native_identity": dict(self.native_identity),
            "correlation": dict(self.correlation),
            "delivery": self.delivery.value,
            "provenance": {
                "produced_by": self.produced_by,
                "execution_ref": self.execution_ref,
                "trace_ref": self.trace_ref,
            },
            "trust": "untrusted_external",
        }


def _source_of(subject_ref: str) -> SignalSource:
    if subject_ref.startswith(SUBJECT_KUBERNETES_POD) or subject_ref.startswith(
            SUBJECT_KUBERNETES_STREAM):
        return SignalSource.KUBERNETES
    if subject_ref.startswith(SUBJECT_ALERTMANAGER_ALERT):
        return SignalSource.ALERTMANAGER
    return SignalSource.UNKNOWN


def _kubernetes_identity(subject_ref: str, value: Mapping[str, Any]) -> tuple[dict, dict, str]:
    rest = subject_ref.split(":", 2)[2] if subject_ref.count(":") >= 2 else ""
    namespace, _, name = rest.partition("/")
    native = {
        "cluster": value.get("cluster"),
        "namespace": value.get("namespace") or namespace or None,
        "kind": value.get("kind") or "Pod",
        "name": value.get("name") or name or None,
        "uid": value.get("uid"),
        "resourceVersion": value.get("resourceVersion"),
        "eventType": value.get("eventType") or value.get("observedVia"),
    }
    correlation = {
        "cluster": value.get("cluster"),
        "namespace": native["namespace"],
        "kind": native["kind"],
        "name": native["name"],
        "workload": value.get("workload"),
        "phase": value.get("phase"),
        "waitingReason": value.get("waitingReason"),
        "restartCount": value.get("restartCount"),
        "lastTerminationReason": value.get("lastTerminationReason"),
        "lastExitCode": value.get("lastExitCode"),
    }
    event_type = str(value.get("eventType") or value.get("origin") or "state")
    return native, correlation, event_type


def _alertmanager_identity(subject_ref: str, value: Mapping[str, Any]) -> tuple[dict, dict, str]:
    fingerprint = subject_ref[len(SUBJECT_ALERTMANAGER_ALERT):]
    labels = value.get("labels") if isinstance(value.get("labels"), Mapping) else {}
    native = {
        "fingerprint": fingerprint,
        "startsAt": value.get("startsAt"),
        "endsAt": value.get("endsAt"),
        "status": value.get("status"),
        "groupKey": value.get("groupKey"),
        "receiver": value.get("receiver"),
    }
    correlation = {
        "alertname": labels.get("alertname"),
        "severity": labels.get("severity"),
        "service": labels.get("service") or labels.get("job"),
        "namespace": labels.get("namespace"),
        "pod": labels.get("pod"),
        "instance": labels.get("instance"),
        "cluster": labels.get("cluster"),
        "generatorURL": value.get("generatorURL"),
    }
    return native, correlation, str(value.get("status") or "alert")


def canonical_signal(observation: Any) -> CanonicalSignal:
    """View one World ``Observation`` as a canonical signal. Pure."""
    value = observation.value if isinstance(observation.value, Mapping) else {}
    source = _source_of(observation.subject_ref)
    if source is SignalSource.KUBERNETES:
        native, correlation, event_type = _kubernetes_identity(observation.subject_ref, value)
        delivery = DeliverySemantics.AT_LEAST_ONCE
    elif source is SignalSource.ALERTMANAGER:
        native, correlation, event_type = _alertmanager_identity(observation.subject_ref, value)
        delivery = DeliverySemantics.EFFECTIVELY_ONCE_PER_STATE
    else:
        native, correlation, event_type = {}, {}, str(observation.predicate)
        delivery = DeliverySemantics.AT_LEAST_ONCE
    return CanonicalSignal(
        global_id=observation.record_id,
        tenant_id=observation.tenant.tenant_id,
        source=source,
        source_ref=observation.source.source_ref,
        subject_ref=observation.subject_ref,
        predicate=observation.predicate,
        event_type=event_type,
        observed_at=observation.instant.observed_at,
        recorded_at=observation.recorded_at,
        native_identity={k: v for k, v in native.items() if v is not None},
        correlation={k: v for k, v in correlation.items() if v is not None},
        delivery=delivery,
        produced_by=observation.provenance.produced_by,
        execution_ref=observation.provenance.execution_ref,
        trace_ref=observation.provenance.trace_ref,
        value=dict(value),
    )
