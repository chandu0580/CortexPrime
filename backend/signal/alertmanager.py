"""Alertmanager webhook normalisation — Phase 11.2 (ADR-122).

What Alertmanager owns, and CortexPrime does not rebuild
--------------------------------------------------------
Deduplication of raw alerts, grouping (``group_by``), routing, inhibition,
silencing and HA are Alertmanager's. The webhook payload CortexPrime receives
is the *output* of those decisions: one notification per group, carrying the
alerts in it with Alertmanager's own ``fingerprint`` (a hash of the label set),
lifecycle timestamps (``startsAt``/``endsAt``), ``status`` and the
``generatorURL`` pointing back at the rule. This module maps that payload to
World observations and nothing more.

Identity
--------
One observation per alert, subject ``alertmanager:alert:<fingerprint>``,
predicate ``alert``. ``observed_at`` is the alert's own ``startsAt``, so a
repeated notification of the same firing alert produces the SAME identity
digest and is DEDUPED by the World Plane; a resolution changes ``status`` and
``endsAt`` and is a new observation of the same subject. Group-level fields
(``groupKey``, ``receiver``) ride in the value because a regroup is a different
notification, but ``externalURL`` and anything volatile do not.

The payload is DATA. Labels and annotations are copied, bounded and never
interpreted; nothing here has authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.signal.contract import (
    PREDICATE_ALERT,
    SOURCE_REF_ALERTMANAGER,
    SUBJECT_ALERTMANAGER_ALERT,
)

__all__ = [
    "AlertmanagerAlert",
    "AlertmanagerPayload",
    "NormalisedAlert",
    "normalise_alertmanager",
    "parse_alertmanager_time",
]

_MAX_LABELS = 64
_MAX_ANNOTATIONS = 32
_MAX_TEXT = 2048
_MAX_ALERTS = 200
_ZERO_TIME = "0001-01-01T00:00:00Z"


class AlertmanagerAlert(BaseModel):
    """One alert as Alertmanager's webhook (version 4) carries it."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(pattern=r"^(firing|resolved)$")
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str
    endsAt: str = _ZERO_TIME
    generatorURL: str = ""
    fingerprint: str = Field(min_length=1, max_length=64, pattern=r"^[0-9a-fA-F]+$")


class AlertmanagerPayload(BaseModel):
    """The webhook body. ``version`` "4" is the only one Alertmanager sends."""

    model_config = ConfigDict(extra="ignore")

    version: str = "4"
    groupKey: str = Field(default="", max_length=1024)
    truncatedAlerts: int = 0
    status: str = Field(default="firing", pattern=r"^(firing|resolved)$")
    receiver: str = Field(default="", max_length=256)
    groupLabels: dict[str, str] = Field(default_factory=dict)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)
    externalURL: str = ""
    alerts: list[AlertmanagerAlert] = Field(min_length=1, max_length=_MAX_ALERTS)


def parse_alertmanager_time(text: str) -> Optional[datetime]:
    """RFC 3339 as Alertmanager writes it (nanoseconds, ``Z`` or offset).
    The zero time (an alert that has not ended) is ``None``."""
    if not isinstance(text, str) or not text or text.startswith("0001-01-01"):
        return None
    raw = text.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    # Python parses at most microseconds; Alertmanager may write nanoseconds.
    if "." in raw:
        head, _, tail = raw.partition(".")
        digits = ""
        rest = ""
        for index, character in enumerate(tail):
            if character.isdigit():
                digits += character
            else:
                rest = tail[index:]
                break
        raw = f"{head}.{digits[:6]}{rest}"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _bounded(mapping: Mapping[str, Any], *, limit: int) -> dict:
    out: dict = {}
    for index, (key, value) in enumerate(sorted(mapping.items())):
        if index >= limit:
            out["_truncated"] = True
            break
        out[str(key)[:256]] = str(value)[:_MAX_TEXT]
    return out


class NormalisedAlert:
    """One alert mapped to the World Plane's read contract."""

    def __init__(self, *, subject_ref: str, predicate: str, value: dict,
                 observed_at: datetime, fingerprint: str) -> None:
        self.subject_ref = subject_ref
        self.predicate = predicate
        self.value = value
        self.observed_at = observed_at
        self.fingerprint = fingerprint

    def to_read(self, *, retrieved_at: datetime, produced_by: str,
                trace_ref: Optional[str] = None):
        from backend.contracts.evidence import SourceStatus
        from backend.contracts.world import ObservationSourceKind
        from backend.world.application import ReadObservation

        return ReadObservation(
            # Alertmanager is an instrument that evaluated the world (through
            # Prometheus); PROBE is the closest honest kind. Never a model.
            source_kind=ObservationSourceKind.PROBE,
            source_ref=SOURCE_REF_ALERTMANAGER,
            subject_ref=self.subject_ref,
            predicate=self.predicate,
            value=self.value,
            status=SourceStatus.RETURNED_DATA,
            observed_at=self.observed_at,
            retrieved_at=retrieved_at,
            produced_by=produced_by,
            trace_ref=trace_ref,
        )


def normalise_alertmanager(payload: AlertmanagerPayload, *, received_at: datetime) -> tuple:
    """Every alert in the notification → one :class:`NormalisedAlert`.

    An alert with an unparseable ``startsAt`` takes ``received_at`` as its
    observed time and says so in the value (``startsAtUnparsed``); it is not
    dropped, because dropping is silent loss.
    """
    out: list = []
    for alert in payload.alerts:
        starts = parse_alertmanager_time(alert.startsAt)
        ends = parse_alertmanager_time(alert.endsAt)
        value = {
            "status": alert.status,
            "labels": _bounded(alert.labels, limit=_MAX_LABELS),
            "annotations": _bounded(alert.annotations, limit=_MAX_ANNOTATIONS),
            "startsAt": starts.isoformat() if starts else None,
            "endsAt": ends.isoformat() if ends else None,
            "generatorURL": alert.generatorURL[:_MAX_TEXT],
            "fingerprint": alert.fingerprint.lower(),
            "groupKey": payload.groupKey,
            "receiver": payload.receiver,
            "groupStatus": payload.status,
            "observedVia": "alertmanager-webhook",
        }
        if starts is None:
            value["startsAtUnparsed"] = alert.startsAt[:64]
        observed_at = starts or received_at
        if observed_at > received_at:
            # Clock skew: the alert claims to have started after we received
            # it. A fetch cannot precede what it observed (the World Plane
            # refuses that), so the observed time is clamped to receipt and
            # the skew is recorded rather than hidden.
            value["startsAtSkewSeconds"] = round((observed_at - received_at).total_seconds(), 3)
            observed_at = received_at
        out.append(NormalisedAlert(
            subject_ref=f"{SUBJECT_ALERTMANAGER_ALERT}{alert.fingerprint.lower()}",
            predicate=PREDICATE_ALERT,
            value=value,
            observed_at=observed_at,
            fingerprint=alert.fingerprint.lower(),
        ))
    return tuple(out)
