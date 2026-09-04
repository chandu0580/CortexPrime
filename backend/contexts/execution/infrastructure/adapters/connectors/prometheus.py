"""The governed Prometheus READ capability — Phase 9.4 (ADR-084).

Why Prometheus, and why not through Grafana
---------------------------------------------
Phase 9.4 needs a *second* view of reality so the World Plane can say whether two
sources independently support a proposition. Grafana was the obvious candidate
and is the wrong one on evidence: its governed catalog declares two folder
operations and no query capability, and data read *through* Grafana is DERIVED
from Prometheus — so routing through it adds a hop and subtracts evidential
value. Prometheus is read directly.

The thing this module must not become
---------------------------------------
    connector.query(promql)

The quarantined V1 connector (``backend/connectors/prometheus.py``) has exactly
that: a caller-supplied PromQL string. It is the Prometheus form of
``request(url, method, body)`` — every operation it can perform is "whatever the
caller typed", so the capability authorizing it describes nothing and the
approval covering it covers nothing.

**So the PromQL is part of the operation's declaration**, in ``static_query``,
and therefore in the operation's digest. There is no parameter through which a
caller — or a model — can compose, extend or influence a query: an undeclared
input is refused outright before a request is built. The namespace an operation
observes is baked in at catalog construction from deployment configuration, the
same rule the channel's ``base_url`` follows.

The cost is stated: one declared operation per (metric, scope) pair. A declared,
validated selector-template mechanism is the successor, and is deliberately not
smuggled in here.

The proposition vocabulary, and why it is load-bearing
--------------------------------------------------------
Corroboration compares *value digests* for the same ``(subject_ref, predicate)``.
Two sources therefore corroborate only if they report the same proposition in the
same shape. Raw provider shapes never do: the Kubernetes API says
``restartCount: 7`` and Prometheus says ``value: "7"``, and those are two digests
— which would read as CONTRADICTED when the sources actually agree.

So each operation declares **which proposition it observes and in what shape**,
and the normalizer projects onto it. That projection is declared, deterministic,
and in the digest. It is not interpretation: the first vertical deliberately uses
a quantity both instruments *literally report* — a container's restart count —
so nothing is inferred. Deriving "this pod is unhealthy" from a restart count
would be interpretation, and is not done here.

Lineage
---------
``kube_pod_container_status_restarts_total`` comes from kube-state-metrics, which
scrapes the Kubernetes API. It is therefore **not independent** of a governed
Kubernetes read, however different the provider looks. Each operation declares
the instrument its evidence came from (``source_ref``), and the deployment's
``LineagePolicy`` maps that instrument to an origin — which is how the World
Plane arrives at CORRELATED rather than INDEPENDENT. Getting this wrong is how a
platform manufactures false confidence out of one fact counted twice.

This module imports no Prometheus client, no ``httpx``, no ``os``, no
``backend.connectors`` and no credential carrier.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from backend.contracts.execution import (
    EffectSemantics, ExecutionEnvironment, SideEffectClass,
)
from backend.contracts.policy import RiskClassification, RiskFactors, RiskLevel
from backend.contracts.provider import ProviderFailure, ProviderRef
from backend.contracts.transport import TransportKind
from backend.contracts.intelligence.investigation import AutonomyLevel
from backend.contracts.intelligence.capability_profile import (
    CapabilityProfile, VerificationRequirement,
)
from backend.contexts.execution.domain.provider_operation import (
    OperationCatalog, ProviderOperationSpec, RecordEvidenceSpec,
)
from backend.contexts.execution.infrastructure.adapters.channel import ProviderChannel
from backend.contexts.execution.infrastructure.adapters.connector import (
    HttpStatusTranslator,
)
from backend.platform.transport import ConnectionPolicy, TransportBroker, TransportEndpoint

__all__ = [
    "PROMETHEUS_PROVIDER_ID",
    "PROMETHEUS_PROVIDER",
    "PROMETHEUS_READ_OPERATIONS",
    "POD_RESTARTS_OPERATION",
    "PROMETHEUS_SELF_OPERATION",
    "POD_MEMORY_OPERATION",
    "INSTRUMENT_KUBELET",
    "INSTRUMENT_KUBE_STATE_METRICS",
    "INSTRUMENT_PROMETHEUS_SELF",
    "PROMETHEUS_MAX_SERIES",
    "PrometheusResponseTranslator",
    "PrometheusVectorNormalizer",
    "prometheus_read_catalog",
    "prometheus_read_profiles",
    "build_prometheus_channel",
]

PROMETHEUS_PROVIDER_ID = "prometheus"
PROMETHEUS_PROVIDER = ProviderRef(provider_id=PROMETHEUS_PROVIDER_ID)
_POLICY_VERSION = "prometheus-read-policy/1"

POD_RESTARTS_OPERATION = "prometheus.pod_restarts"
PROMETHEUS_SELF_OPERATION = "prometheus.self_build_info"
#: Phase 9.5 (ADR-085): the observable that FALSIFIES a resource-exhaustion
#: hypothesis. A container crashlooping under a memory limit is exactly the shape
#: an OOM kill takes, so "it might be OOM" is a legitimate thing to suspect --
#: and working-set bytes far below the limit is what rules it out.
POD_MEMORY_OPERATION = "prometheus.pod_memory_bytes"

PROMETHEUS_READ_OPERATIONS = (POD_RESTARTS_OPERATION, PROMETHEUS_SELF_OPERATION,
                              POD_MEMORY_OPERATION)

#: The instrument identifiers that reach an Observation's ``source_ref``.
#:
#: Two, and distinct, because that distinction is the entire mechanism by which
#: lineage is expressed: every World Plane policy — lineage, authority, freshness
#: — matches on ``(source_kind, source_ref)``. Calling both of these
#: ``connector:prometheus`` would make a kube-state-metrics reading and a
#: Prometheus self-reading indistinguishable to the lineage policy, and the
#: platform would lose its only way to notice that one of them is derived from
#: the Kubernetes API it is being compared against.
INSTRUMENT_KUBE_STATE_METRICS = "prometheus:kube-state-metrics"
INSTRUMENT_PROMETHEUS_SELF = "prometheus:self"
#: Container memory comes from the kubelet's own cAdvisor, which reads the
#: container runtime directly rather than the API server. A DIFFERENT origin from
#: the cluster's API, and the lineage policy says so.
INSTRUMENT_KUBELET = "prometheus:kubelet-cadvisor"

#: The most series one query may return. A larger answer is refused rather than
#: trimmed — a silently truncated result set is a partial view of the world
#: wearing the shape of a complete one.
PROMETHEUS_MAX_SERIES = 64

_TIMEOUT = 15.0

_PROM_HEADERS = {
    "accept": "application/json",
    "user-agent": "CortexPrime-ConnectorAdapter/1.0",
}


class PrometheusResponseTranslator(HttpStatusTranslator):
    """Prometheus's own dialect — and one genuinely dangerous departure.

    Prometheus can answer ``{"status": "error", "errorType": ..., "error": ...}``
    **with HTTP 200** for some failure modes. A status-only translator would call
    that a success, the shape check would then find no ``data``, and the operator
    would get "malformed response" instead of the query error Prometheus actually
    reported. Worse, a query that errored would be indistinguishable from one that
    legitimately matched nothing.

    So this translator reads the envelope's own ``status`` field and classifies
    an error body as a failure regardless of the HTTP status. It can only make a
    non-failure into a failure; it has no path that turns a failure into a
    success.
    """

    def classify(
        self, spec: ProviderOperationSpec, exchange: Any, body: Any
    ) -> Optional[ProviderFailure]:
        failure = super().classify(spec, exchange, body)
        if failure is not None:
            return failure
        if isinstance(body, Mapping) and body.get("status") == "error":
            # A 200 that says "error" is not a success this operation defines.
            return ProviderFailure.PROTOCOL_ERROR
        return None

    def describe(self, exchange: Any, body: Any) -> Tuple[Optional[str], Optional[str]]:
        code, reason = super().describe(exchange, body)
        if isinstance(body, Mapping):
            message = body.get("error")
            if isinstance(message, str) and message.strip():
                kind = body.get("errorType")
                label = f"{kind}: " if isinstance(kind, str) and kind else ""
                return code, f"{label}{message.strip()}"[:200]
        return code, reason


class PrometheusVectorNormalizer:
    """Lifts a Prometheus instant-query vector into declared, bounded evidence.

    The wire shape::

        {"status": "success",
         "data": {"resultType": "vector",
                  "result": [{"metric": {...labels...},
                              "value": [<unix_ts>, "<value>"]}]}}

    What this produces, and what it refuses:

    * One record per series, carrying only the labels the operation declared,
      plus ``value`` and ``timestamp`` **exactly as returned**. The value stays a
      string because that is what Prometheus sends; coercing it to a float here
      would silently lose ``NaN``/``+Inf`` and the exact decimal the provider
      reported.
    * ``sampleTimestamp`` — the provider's own time, lifted to the top level so
      the observation leg can use it as ``observed_at`` rather than a clock this
      process owns.
    * A ``resultType`` other than ``vector`` is **refused**. A matrix or a scalar
      is a different answer shape than this operation declares, and reshaping one
      into the other here would be inventing the operation's contract at runtime.
    * A missing ``data``/``result``, a non-list result, or a malformed
      ``value`` pair is refused. Absent stays absent; nothing is synthesized.

    Pure and deterministic. Raises on an envelope it does not understand, and the
    adapter turns that into ``MALFORMED_RESPONSE`` — a refusal, not an invention.
    """

    def normalize(self, spec: ProviderOperationSpec, body: Any) -> Any:
        if not isinstance(body, Mapping):
            raise ValueError(
                f"{spec.operation}: expected a Prometheus JSON envelope, "
                f"got {type(body).__name__}"
            )
        data = body.get("data")
        if not isinstance(data, Mapping):
            raise ValueError(f"{spec.operation}: the response carries no data object")
        result_type = data.get("resultType")
        if result_type != "vector":
            raise ValueError(
                f"{spec.operation}: expected an instant-query vector, got "
                f"resultType={result_type!r}; this operation is not defined for "
                "that answer shape"
            )
        result = data.get("result")
        if not isinstance(result, list):
            raise ValueError(f"{spec.operation}: the vector result is not a list")

        declared = spec.response_evidence_records
        label_fields = tuple(
            name for name in (declared.fields if declared else ())
            if name not in ("value", "timestamp")
        )

        series: list = []
        latest_timestamp: Optional[float] = None
        for index, item in enumerate(result):
            if not isinstance(item, Mapping):
                raise ValueError(f"{spec.operation}: series {index} is not an object")
            pair = item.get("value")
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError(
                    f"{spec.operation}: series {index} has no [timestamp, value] "
                    "pair; a sample without a time cannot be placed in the world"
                )
            timestamp, value = pair
            if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
                raise ValueError(
                    f"{spec.operation}: series {index} has a non-numeric timestamp"
                )
            if not isinstance(value, str):
                raise ValueError(
                    f"{spec.operation}: series {index} has a non-string value; "
                    "Prometheus sends sample values as strings and this keeps "
                    "them exactly as sent"
                )
            record = {"value": value, "timestamp": float(timestamp)}
            labels = item.get("metric")
            if isinstance(labels, Mapping):
                for name in label_fields:
                    label = labels.get(name)
                    if isinstance(label, str) and label:
                        record[name] = label
            series.append(record)
            latest_timestamp = (
                float(timestamp) if latest_timestamp is None
                else max(latest_timestamp, float(timestamp))
            )

        out: dict = {
            "status": body.get("status"),
            "resultType": result_type,
            "series": series,
            "seriesCount": len(series),
        }
        if latest_timestamp is not None:
            out["sampleTimestamp"] = latest_timestamp
        return out


def _instant_query(
    *, operation: str, promql: str, record_fields: Tuple[str, ...],
) -> ProviderOperationSpec:
    """One declared instant query. The PromQL is a constant of the operation."""
    return ProviderOperationSpec(
        operation=operation,
        method="GET",
        path_template="/api/v1/query",
        side_effect_class=SideEffectClass.READ,
        effect_semantics=EffectSemantics.READ_ONLY,
        # No parameters at all. There is nothing here a caller can supply, which
        # is what makes "the model cannot compose a query" structural rather
        # than a check somebody has to remember to write.
        parameters=(),
        static_query={"query": promql},
        success_statuses=(200,),
        # An empty vector is a legitimate answer (nothing matched), so the only
        # field a valid answer must always carry is the count.
        response_required_fields=("seriesCount",),
        response_evidence_fields=("status", "resultType", "seriesCount",
                                  "sampleTimestamp"),
        response_evidence_records=RecordEvidenceSpec(
            field_name="series", fields=record_fields,
            max_records=PROMETHEUS_MAX_SERIES),
        static_headers=_PROM_HEADERS,
        provider_timeout_seconds=_TIMEOUT,
        max_response_bytes=1024 * 1024,
    )


def prometheus_read_catalog(*, namespace: str) -> OperationCatalog:
    """The declared, READ-only Prometheus catalog for one observed namespace.

    ``namespace`` is deployment configuration, exactly like the channel's
    ``base_url``: it is compiled into the operation's declared query at
    composition, never supplied per invocation. A catalog built for one namespace
    cannot read another, and that is a property of the declaration rather than of
    a check at call time.
    """
    if not namespace or not isinstance(namespace, str):
        raise ValueError(
            "a Prometheus catalog is scoped to a named namespace; an unscoped "
            "catalog would read whatever the whole cluster reports"
        )
    if any(ch in namespace for ch in '"\\{}\n'):
        # The namespace is interpolated into a declared PromQL selector. It comes
        # from deployment configuration, but a value that could close the label
        # matcher would change the query's meaning, so it is refused at
        # construction rather than trusted for being configuration.
        raise ValueError(
            f"namespace {namespace!r} contains characters that would alter the "
            "declared PromQL selector"
        )
    return OperationCatalog(
        PROMETHEUS_PROVIDER_ID,
        (
            # The DERIVED instrument. kube-state-metrics reads the Kubernetes
            # API, so this reports the same number the API server reports — and
            # the lineage policy must therefore call the two CORRELATED.
            _instant_query(
                operation=POD_RESTARTS_OPERATION,
                promql=(
                    "max by (pod, namespace, container) "
                    "(kube_pod_container_status_restarts_total"
                    f'{{namespace="{namespace}"}})'
                ),
                record_fields=("pod", "namespace", "container", "value", "timestamp"),
            ),
            # Prometheus's own instrumentation — a different origin entirely,
            # derived from nothing in the cluster.
            _instant_query(
                operation=PROMETHEUS_SELF_OPERATION,
                promql="prometheus_build_info",
                record_fields=("version", "branch", "value", "timestamp"),
            ),
            # Working-set bytes per container — Phase 9.5's falsifier for a
            # resource-exhaustion hypothesis. kube-state-metrics does not export
            # this: it comes from the kubelet's cAdvisor, which measures the
            # container runtime directly rather than re-reading the API server,
            # and is therefore a genuinely different origin from the cluster API.
            _instant_query(
                operation=POD_MEMORY_OPERATION,
                promql=(
                    "max by (pod, namespace, container) "
                    "(container_memory_working_set_bytes"
                    f'{{namespace="{namespace}", container!=""}})'
                ),
                record_fields=("pod", "namespace", "container", "value", "timestamp"),
            ),
        ),
    )


def build_prometheus_channel(
    *,
    broker: TransportBroker,
    policy: ConnectionPolicy,
    environment: ExecutionEnvironment,
    base_url: str,
) -> ProviderChannel:
    """The channel Prometheus is reached through. Destination from configuration.

    Plaintext is permitted only when the policy explicitly carries the exception
    — the Grafana precedent, and the policy itself refuses that exception in
    production. Refused here as well as by policy, so a deployment that never
    stated it cannot reach a plaintext Prometheus by accident. There is
    deliberately no default address: no universal Prometheus exists.
    """
    endpoint = TransportEndpoint.parse(
        base_url, transport=TransportKind.HTTPS, environment=environment
    )
    if endpoint.is_plaintext and not getattr(policy.tls, "allow_plaintext", False):
        raise ValueError(
            "the Prometheus endpoint is plaintext and this policy does not state "
            "the plaintext exception; a bearer token on plaintext is exposed on "
            "every request"
        )
    return ProviderChannel(
        provider=PROMETHEUS_PROVIDER,
        broker=broker,
        base_endpoint=endpoint,
        policy=policy,
        transport=TransportKind.HTTPS,
    )


def _profile(operation: str) -> CapabilityProfile:
    """A READ profile: LOW blast radius, ceiling A1 (observe, never act), no
    verification (there is nothing to verify about a read), reversible by
    nature."""
    factors = RiskFactors(side_effect_class=SideEffectClass.READ,
                          environment="development", resource_count=1, reversible=True)
    return CapabilityProfile(
        capability_ref=f"platform.{operation}",
        provider=PROMETHEUS_PROVIDER_ID, operation=operation,
        side_effect_class=SideEffectClass.READ,
        effect_semantics=EffectSemantics.READ_ONLY,
        risk=RiskClassification(level=RiskLevel.LOW, factors=factors,
                                rationale=f"{operation}: read-only metric observation"),
        autonomy_ceiling=AutonomyLevel.A1_INVESTIGATE,
        verification_requirement=VerificationRequirement.NONE,
        resource_scope="namespace", reversible=True, timeout_seconds=_TIMEOUT,
        policy_version=_POLICY_VERSION)


def prometheus_read_profiles() -> dict:
    """The capability-bridge profile for each declared Prometheus operation."""
    return {op: _profile(op) for op in PROMETHEUS_READ_OPERATIONS}
