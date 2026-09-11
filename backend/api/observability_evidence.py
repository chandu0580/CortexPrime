"""Multi-source observability evidence — Phase 9.4 (ADR-084).

Two things live here, and both are *deployment configuration* rather than
mechanism, which is why they are in the composition layer:

1. **The declared policy set** — which instrument came from which origin
   (lineage), which instrument has what standing (authority), and how long a
   given kind of evidence stays fresh. The World Plane's engines are already
   built and already correct; what they need is a deployment willing to *state*
   these things, because every one of them is unknowable from the data itself.

2. **The proposition mapper** — turning one governed read's declared evidence
   into the ``ObservationLeg``s the World Plane records.

Why the policies are stated and not derived
---------------------------------------------
Nothing in a Prometheus response says "this number came from the Kubernetes
API". kube-state-metrics reports ``kube_pod_container_status_restarts_total``
identically to how the API server reports ``restartCount``, because it scraped it
from there — and a platform that could not tell would count one fact twice and
call it corroboration. Lineage is an operator's statement about their own
topology. The right response to not knowing it is UNKNOWN, which the World Plane
already refuses to treat as independent.

The proposition vocabulary
----------------------------
Corroboration compares value digests for a shared ``(subject_ref, predicate)``.
So two providers only ever corroborate if they report the same proposition in the
same shape, and that shape has to be declared somewhere. It is declared here and
in each provider's catalog, never inferred.

The first vertical deliberately uses a quantity both instruments *literally*
report — a container's restart count — so nothing is interpreted. "This pod is
unhealthy" would be an interpretation and is not produced.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "ORIGIN_KUBERNETES_CLUSTER",
    "ORIGIN_PROMETHEUS_SERVER",
    "INSTRUMENT_KUBERNETES_API",
    "RESTART_COUNT_PREDICATE",
    "observability_lineage_policy",
    "observability_authority_policy",
    "observability_freshness_policy",
    "pod_subject",
    "restart_count_legs_from_kubernetes",
    "restart_count_legs_from_prometheus",
    "WorldQueryEvidencePort",
]

#: The origins this deployment can name. An origin is a *system whose view of the
#: world is its own* — not a provider, not an endpoint, not a connector.
ORIGIN_KUBERNETES_CLUSTER = "kubernetes-cluster"
ORIGIN_PROMETHEUS_SERVER = "prometheus-server"
#: Phase 11.3: the kubelet (cAdvisor + container logs) as its own origin.
ORIGIN_KUBELET = "kubelet"
INSTRUMENT_KUBELET_LOGS = "kubelet:container-logs"

#: The Kubernetes API's own instrument id, as the governed K8s reads record it.
INSTRUMENT_KUBERNETES_API = "connector:kubernetes"

#: The shared proposition. Both instruments literally report this number.
RESTART_COUNT_PREDICATE = "restart_count"

_METRIC_SOURCE_KIND = "connector"


def pod_subject(*, namespace: str, pod: str) -> str:
    """The subject both providers must agree on to corroborate at all."""
    return f"kubernetes:pod:{namespace}/{pod}"


# ---------------------------------------------------------------------------
# The declared policies
# ---------------------------------------------------------------------------

def observability_lineage_policy():
    """Where each instrument's evidence actually originates.

    The load-bearing rule is the second one. ``prometheus:kube-state-metrics`` is
    reached through the Prometheus provider, looks nothing like a Kubernetes
    read, and is nonetheless **the Kubernetes API's own number** — kube-state-
    metrics does nothing but scrape the API server and re-export it. Stating its
    origin as the cluster, with relation DERIVED, is what stops two views of one
    fact from being counted as independent support for it.

    ``prometheus:self`` is a genuinely different origin: Prometheus's own build
    information is derived from nothing in the cluster.

    Any instrument matched by no rule is UNKNOWN, and the corroboration engine
    will refuse to claim independence for it. That default is the honest one and
    is deliberately not overridden with a catch-all.
    """
    from backend.contexts.execution.infrastructure.adapters.connectors.prometheus import (
        INSTRUMENT_KUBE_STATE_METRICS, INSTRUMENT_KUBELET, INSTRUMENT_PROMETHEUS_SELF,
    )
    from backend.world.application.lineage import (
        LineagePolicy, LineageRelation, LineageRule,
    )

    return LineagePolicy(
        name="phase113-observability-lineage/2",
        rules=(
            # Phase 11.3 (ADR-123). The kubelet is a different origin from the
            # API server: cAdvisor measures the container runtime directly, and
            # container logs are read from the runtime's log files. Both are
            # the SAME daemon, so they share one origin -- two kubelet readings
            # corroborate each other but are not independent of each other.
            LineageRule(
                source_kind=_METRIC_SOURCE_KIND,
                source_ref=INSTRUMENT_KUBELET,
                origin_id=ORIGIN_KUBELET,
                relation=LineageRelation.DIRECT,
            ),
            LineageRule(
                source_kind=_METRIC_SOURCE_KIND,
                source_ref=INSTRUMENT_KUBELET_LOGS,
                origin_id=ORIGIN_KUBELET,
                relation=LineageRelation.DIRECT,
            ),
            # The cluster's own API, reporting its own state. The strongest
            # lineage there is.
            LineageRule(
                source_kind=_METRIC_SOURCE_KIND,
                source_ref=INSTRUMENT_KUBERNETES_API,
                origin_id=ORIGIN_KUBERNETES_CLUSTER,
                relation=LineageRelation.DIRECT,
            ),
            # Same origin, one hop away. NOT independent evidence about the
            # cluster, however different the provider looks.
            LineageRule(
                source_kind=_METRIC_SOURCE_KIND,
                source_ref=INSTRUMENT_KUBE_STATE_METRICS,
                origin_id=ORIGIN_KUBERNETES_CLUSTER,
                relation=LineageRelation.DERIVED,
            ),
            # A different system entirely.
            LineageRule(
                source_kind=_METRIC_SOURCE_KIND,
                source_ref=INSTRUMENT_PROMETHEUS_SELF,
                origin_id=ORIGIN_PROMETHEUS_SERVER,
                relation=LineageRelation.DIRECT,
            ),
        ),
    )


def observability_authority_policy():
    """Who has standing to ground a fact about cluster state.

    The Kubernetes API is AUTHORITATIVE about its own resources: it is not a
    report of the cluster's state, it *is* the cluster's state. A metric
    re-export of that same state is SINGLE_SOURCE — one configured instrument
    reporting, believable and not a thing that should overrule the API server
    about the API server's own data. (``CORROBORATED`` is deliberately not used
    as a tier here: it describes a *derived* state — multiple independent sources
    agreeing — which the corroboration engine decides, not something a policy can
    assert about one instrument in advance.)

    Note what this deliberately does not encode: recency. A newer metric
    observation does not outrank an older authoritative one, because authority
    and recency are separate axes and collapsing them is how "newest wins"
    systems end up believing a stale cache over the source of truth.
    """
    from backend.contracts.world.confidence import SourceAuthority
    from backend.contexts.execution.infrastructure.adapters.connectors.prometheus import (
        INSTRUMENT_KUBE_STATE_METRICS, INSTRUMENT_PROMETHEUS_SELF,
    )
    from backend.world.application.authority import AuthorityPolicy, AuthorityRule

    return AuthorityPolicy(
        name="phase94-observability-authority/1",
        rules=(
            AuthorityRule(source_kind=_METRIC_SOURCE_KIND,
                          source_ref=INSTRUMENT_KUBERNETES_API,
                          tier=SourceAuthority.AUTHORITATIVE),
            # Equal tiers, deliberately: two instruments that are each one
            # configured reporter. Equal standing is what makes a disagreement
            # between them a genuine CONFLICT rather than something authority
            # quietly resolves.
            AuthorityRule(source_kind=_METRIC_SOURCE_KIND,
                          source_ref=INSTRUMENT_KUBE_STATE_METRICS,
                          tier=SourceAuthority.SINGLE_SOURCE),
            AuthorityRule(source_kind=_METRIC_SOURCE_KIND,
                          source_ref=INSTRUMENT_PROMETHEUS_SELF,
                          tier=SourceAuthority.SINGLE_SOURCE),
        ),
    )


def observability_freshness_policy(*, metric_horizon_seconds: float = 120.0,
                                   cluster_horizon_seconds: float = 300.0,
                                   deployment_horizon_seconds: float = 3600.0):
    """How long each kind of evidence stays FRESH.

    Two horizons, because the two instruments go stale for different reasons and
    at different rates. A metric horizon must account for a real Prometheus
    property: an instant query returns the *evaluation* instant, and Prometheus
    resolves each series to the most recent sample within its lookback delta
    (5 minutes by default). So the timestamp on a metric sample can be newer than
    the observation it describes, and a tight horizon is the honest response.

    A predicate matched by no rule stays UNKNOWN, which is neither fresh nor
    false — the World Plane is explicit that STALE is not FALSE and UNKNOWN is
    not FALSE either.
    """
    from backend.world.application.freshness import FreshnessPolicy, FreshnessRule

    return FreshnessPolicy(
        name="phase94-observability-freshness/1",
        rules=(
            FreshnessRule(name="metric-restart-count",
                          source_kind=_METRIC_SOURCE_KIND,
                          predicate=RESTART_COUNT_PREDICATE,
                          horizon_seconds=metric_horizon_seconds),
            FreshnessRule(name="cluster-state",
                          source_kind=_METRIC_SOURCE_KIND,
                          predicate="state",
                          horizon_seconds=cluster_horizon_seconds),
            # Phase 9.5 (ADR-085): the predicates an incident investigation reads.
            # Each is stated rather than left to the UNKNOWN default, because an
            # investigator that cannot tell fresh evidence from old cannot refuse
            # to reuse the old — and refusing is the behaviour that matters.
            #
            # Two different horizons on purpose. A pod's phase changes second to
            # second while it crashloops; a deployment's revision changes only
            # when somebody deploys, so evidence about it stays useful far longer.
            FreshnessRule(name="pod-state", source_kind=_METRIC_SOURCE_KIND,
                          predicate="pod_state",
                          horizon_seconds=cluster_horizon_seconds),
            FreshnessRule(name="pod-last-termination", source_kind=_METRIC_SOURCE_KIND,
                          predicate="last_termination",
                          horizon_seconds=cluster_horizon_seconds),
            FreshnessRule(name="container-memory-pressure",
                          source_kind=_METRIC_SOURCE_KIND,
                          predicate="memory_pressure",
                          horizon_seconds=metric_horizon_seconds),
            FreshnessRule(name="deployed-revision", source_kind=_METRIC_SOURCE_KIND,
                          predicate="deployed_revision",
                          horizon_seconds=deployment_horizon_seconds),
            # Phase 11.3 (ADR-123): the investigation reads this phase added.
            # A log's patterns and a pod's events describe what already
            # happened, so they stay useful about as long as the cluster's
            # state; the rollout history changes only when somebody deploys.
            FreshnessRule(name="log-patterns", source_kind=_METRIC_SOURCE_KIND,
                          predicate="log_patterns", horizon_seconds=cluster_horizon_seconds),
            FreshnessRule(name="log-patterns-previous", source_kind=_METRIC_SOURCE_KIND,
                          predicate="log_patterns_previous", horizon_seconds=cluster_horizon_seconds),
            FreshnessRule(name="pod-events", source_kind=_METRIC_SOURCE_KIND,
                          predicate="events", horizon_seconds=cluster_horizon_seconds),
            FreshnessRule(name="rollout-history", source_kind=_METRIC_SOURCE_KIND,
                          predicate="rollout_history",
                          horizon_seconds=deployment_horizon_seconds),
            FreshnessRule(name="deployment-state", source_kind=_METRIC_SOURCE_KIND,
                          predicate="deployment_state",
                          horizon_seconds=cluster_horizon_seconds),
            FreshnessRule(name="replicas-unavailable", source_kind=_METRIC_SOURCE_KIND,
                          predicate="replicas_unavailable",
                          horizon_seconds=metric_horizon_seconds),
            FreshnessRule(name="restart-onset", source_kind=_METRIC_SOURCE_KIND,
                          predicate="restart_onset", horizon_seconds=metric_horizon_seconds),
        ),
    )


# ---------------------------------------------------------------------------
# The proposition mapper
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Sample:
    pod: str
    value: str
    observed_at: datetime


def _proposition(count: int) -> dict:
    """The declared shape of the shared proposition.

    One field, an integer. Both providers project onto exactly this, because
    corroboration compares value digests and two shapes never agree. The integer
    is the number each instrument reported — not a rounding, not a rate, not a
    verdict about health.
    """
    return {"restartCount": count}


def restart_count_legs_from_kubernetes(
    *, evidence: Mapping[str, Any], namespace: str, observed_at: datetime,
) -> tuple:
    """Project a governed ``kubernetes.pods.list`` answer onto the proposition.

    Uses the declared per-pod records the Kubernetes normalizer already produces.
    A pod whose record carries no restart count is **skipped**, not defaulted to
    zero: "we did not observe it" and "we observed zero" are different claims and
    only one of them is true.
    """
    from backend.api.governed_read_observer import ObservationLeg

    legs: list = []
    for record in evidence.get("pods") or ():
        if not isinstance(record, Mapping):
            continue
        name = record.get("name")
        restarts = record.get("restartCount")
        if not isinstance(name, str) or not name:
            continue
        if not isinstance(restarts, int) or isinstance(restarts, bool):
            continue
        legs.append(ObservationLeg(
            subject_ref=pod_subject(namespace=namespace, pod=name),
            predicate=RESTART_COUNT_PREDICATE,
            value=_proposition(restarts),
            observed_at=observed_at,
        ))
    return tuple(legs)


def restart_count_legs_from_prometheus(
    *, evidence: Mapping[str, Any], namespace: str, fallback_observed_at: datetime,
    retrieved_at: Optional[datetime] = None, max_clock_skew_seconds: float = 120.0,
) -> tuple:
    """Project a governed Prometheus vector onto the same proposition.

    ``observed_at`` comes from **the provider's own sample timestamp**, per
    series, not from this process's clock. That is the point of preserving it
    through the normalizer: the World Plane's valid time should be when the world
    was in this state according to the instrument, and Prometheus is one of the
    few providers that actually says.

    ``fallback_observed_at`` is used only for a series that carried no usable
    timestamp — which the normalizer already refuses, so it is a second line of
    defence rather than an expected path.

    A value Prometheus reports that is not a whole number is **skipped**. A
    restart count is a counter; ``NaN``, ``+Inf`` or ``7.5`` mean the query did
    not return what this proposition is about, and rounding one into an integer
    would be manufacturing a fact.

    Two clocks, reconciled explicitly
    -----------------------------------
    The provider's timestamp comes from the provider's clock and
    ``retrieved_at`` from ours, and those disagree — a container whose clock runs
    a second ahead produces ``observed_at > retrieved_at``, which the temporal
    contract refuses because a fetch cannot precede the moment it observed.

    That refusal is right, and the answer is not to overwrite the provider's
    time. ``observed_at`` stays exactly what Prometheus said; ``retrieved_at`` is
    advanced to it when the skew is small, and the skew is recorded in the
    observation so it is visible rather than silently absorbed. A skew beyond
    ``max_clock_skew_seconds`` is **refused**: a provider whose clock is minutes
    ahead of ours is a condition to surface, not to accommodate.
    """
    from backend.api.governed_read_observer import ObservationLeg

    legs: list = []
    for record in evidence.get("series") or ():
        if not isinstance(record, Mapping):
            continue
        pod = record.get("pod")
        raw = record.get("value")
        if not isinstance(pod, str) or not pod or not isinstance(raw, str):
            continue
        if isinstance(record.get("namespace"), str) and record["namespace"] != namespace:
            # The catalog already scopes the query, so this is defence in depth
            # rather than filtering: a series from elsewhere is not evidence
            # about this namespace and is not silently relabelled as such.
            continue
        try:
            numeric = float(raw)
        except (TypeError, ValueError):
            continue
        # Order matters: int(NaN) and int(+Inf) raise, so finiteness is checked
        # before whole-ness. A counter that is not a finite whole number means
        # the query did not return what this proposition is about, and coercing
        # one into an integer would be manufacturing a fact.
        if not math.isfinite(numeric) or numeric != int(numeric):
            continue
        stamp = record.get("timestamp")
        observed_at = (
            datetime.fromtimestamp(float(stamp), tz=timezone.utc)
            if isinstance(stamp, (int, float)) and not isinstance(stamp, bool)
            else fallback_observed_at
        )
        retrieved = retrieved_at or fallback_observed_at
        skew = (observed_at - retrieved).total_seconds()
        if skew > max_clock_skew_seconds:
            # Not accommodated. A provider claiming to have observed the world
            # minutes into our future is telling us something is wrong with one
            # of the two clocks, and recording it as evidence would bury that.
            raise ContractViolation(
                f"the provider's sample time is {skew:.1f}s ahead of retrieval "
                f"(limit {max_clock_skew_seconds}s); the two clocks disagree by "
                "more than this deployment is willing to absorb"
            )
        if skew > 0:
            # observed_at stays exactly what the provider said; retrieved_at
            # moves up to meet it so the record is orderable.
            #
            # The skew is deliberately NOT written into the value. The value is
            # the *proposition*, and it has to be byte-identical to what the
            # other instrument reports or corroboration compares two digests and
            # calls agreement a contradiction. Retrieval metadata does not belong
            # in a claim about the world. The skew stays reconstructable from
            # provenance: the observation names the execution that produced it,
            # and that execution carries CortexPrime's own wall-clock times.
            retrieved = observed_at
        legs.append(ObservationLeg(
            subject_ref=pod_subject(namespace=namespace, pod=pod),
            predicate=RESTART_COUNT_PREDICATE,
            value=_proposition(int(numeric)),
            observed_at=observed_at,
            retrieved_at=retrieved,
        ))
    return tuple(legs)


class WorldQueryEvidencePort:
    """The Intelligence Plane's read-only window onto World evidence.

    Implements the ``WorldReadPort`` protocol the investigation engine consumes,
    over ``WorldQuery`` and nothing else. It exists because the protocol was
    declared with no production adapter behind it — the same gap Phase 9.3 found
    for observation ingestion, in the other direction: a port every phase
    satisfied inside its own harness.

    What it is allowed to do is deliberately narrow. It reads. It holds a
    ``WorldQuery`` and has no provider, no connector, no credential, no ingestion
    boundary and no clock of its own — so there is no code path here through
    which an investigation could reach a provider, whatever it asked for. New
    evidence is acquired through the governed read path (``EvidenceAcquisition
    Port``), which is a different port with a different implementation.

    It flattens ``WorldQueryResult.to_dict()`` into the shape the engine reads,
    and **changes no verdict while doing so**: status, freshness and the
    authority reason are passed through exactly as the World Plane decided them.
    The engine is explicit that it "consumes WorldQuery's verdicts — it never
    reclassifies them itself", and neither does this.
    """

    __slots__ = ("_query",)

    def __init__(self, *, query: Any) -> None:
        self._query = query

    def evidence_for(
        self, *, tenant: Any, subject_ref: str, predicate: str, now: datetime
    ) -> dict:
        answer = self._query.current(tenant=tenant, subject_ref=subject_ref,
                                     predicate=predicate, now=now)
        document = answer.to_dict()
        return {
            # Flattened for the engine's reader, and lifted verbatim — the nested
            # document is kept alongside so nothing is lost in the projection.
            "value": document["what"]["value"],
            "status": document["status"],
            "freshness": document["fresh"]["state"],
            "source_ref": document["why"]["source_ref"],
            "conflicted": document["conflicted"],
            "evidence": document["evidence"],
            "world_query": document,
        }
