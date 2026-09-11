"""Phase 9.4 (ADR-084): multi-source observability corroboration — unit evidence.

What these prove without a network:

- A governed Prometheus operation has **no caller parameter at all**, so there is
  no surface through which a model could compose, extend or influence PromQL. The
  query is a constant of the operation and is in its digest.
- The catalog is scoped to one namespace at construction, and a namespace that
  could alter the declared selector is refused.
- Prometheus's ``{"status": "error"}`` **with HTTP 200** classifies as a failure,
  not a success with a confusing shape.
- The vector normalizer preserves the provider's own sample timestamp and value
  exactly, and refuses every envelope it does not understand rather than
  reshaping it.
- The declared lineage says kube-state-metrics is DERIVED from the *Kubernetes*
  origin — so a Prometheus reading and a Kubernetes reading of the same number
  are CORRELATED, never INDEPENDENT.
- Unknown lineage is INDETERMINATE. Distinct known origins are INDEPENDENT.
  Disagreement at equal authority is CONTRADICTED and both paths survive.
- Both providers project onto the same proposition shape, which is the only
  reason corroboration can compare them at all.

The real-cluster/real-Prometheus legs live in
``scripts/phase94_observability_harness.py``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.provider import ProviderDelivery, ProviderFailure
from backend.contexts.execution.infrastructure.adapters.channel import ProviderExchange
from backend.contexts.execution.infrastructure.adapters.connectors.prometheus import (
    INSTRUMENT_KUBE_STATE_METRICS,
    INSTRUMENT_PROMETHEUS_SELF,
    POD_RESTARTS_OPERATION,
    PROMETHEUS_MAX_SERIES,
    PROMETHEUS_READ_OPERATIONS,
    PrometheusResponseTranslator,
    PrometheusVectorNormalizer,
    prometheus_read_catalog,
    prometheus_read_profiles,
)
from backend.api.observability_evidence import (
    INSTRUMENT_KUBERNETES_API,
    ORIGIN_KUBERNETES_CLUSTER,
    ORIGIN_PROMETHEUS_SERVER,
    RESTART_COUNT_PREDICATE,
    observability_authority_policy,
    observability_freshness_policy,
    observability_lineage_policy,
    pod_subject,
    restart_count_legs_from_kubernetes,
    restart_count_legs_from_prometheus,
)

NS = "cortex-p94"


def _spec(operation=POD_RESTARTS_OPERATION):
    return prometheus_read_catalog(namespace=NS).require(operation)


def _vector(*series, result_type="vector"):
    return {"status": "success",
            "data": {"resultType": result_type, "result": list(series)}}


def _sample(pod="flapper-1", value="7", ts=1788508710.0, container="flapper"):
    return {"metric": {"pod": pod, "namespace": NS, "container": container},
            "value": [ts, value]}


# ---------------------------------------------------------------------------
# The declaration
# ---------------------------------------------------------------------------

class TestPrometheusDeclaration:
    def test_no_operation_accepts_any_caller_parameter(self):
        # The whole PromQL-injection surface, absent by construction rather than
        # closed by a check somebody has to remember. Phase 11.3 added ONE range
        # query whose only parameters are two bounded INTEGER instants (start,
        # end) the platform computes from the investigation window -- nothing a
        # caller supplies can reach the query text.
        from backend.contexts.execution.domain.provider_operation import ParameterKind

        catalog = prometheus_read_catalog(namespace=NS)
        for operation in catalog.operations:
            spec = catalog.require(operation)
            if spec.path_template == "/api/v1/query_range":
                assert tuple(p.name for p in spec.parameters) == ("start", "end")
                assert all(p.kind is ParameterKind.INTEGER for p in spec.parameters)
                assert "query" in spec.static_query and "step" in spec.static_query
            else:
                assert spec.parameters == ()

    def test_the_promql_is_declared_and_in_the_digest(self):
        import dataclasses
        spec = _spec()
        assert "kube_pod_container_status_restarts_total" in spec.static_query["query"]
        assert f'namespace="{NS}"' in spec.static_query["query"]
        widened = dataclasses.replace(spec, static_query={"query": "up"})
        assert widened.digest != spec.digest

    def test_a_caller_cannot_smuggle_a_query_in(self):
        spec = _spec()
        assert spec.input_problems({"query": "drop_everything"})
        with pytest.raises(ContractViolation):
            spec.plan({"query": "drop_everything"})
        # ...and the plan that IS built carries only the declared query.
        assert spec.plan({}).query == {"query": spec.static_query["query"]}

    def test_the_catalog_is_scoped_to_one_namespace(self):
        other = prometheus_read_catalog(namespace="somewhere-else")
        assert (other.require(POD_RESTARTS_OPERATION).static_query["query"]
                != _spec().static_query["query"])

    def test_a_namespace_that_could_alter_the_selector_is_refused(self):
        for hostile in ('a"} or on() (', "a{b", "a\nb", "a\\b"):
            with pytest.raises(ValueError):
                prometheus_read_catalog(namespace=hostile)
        with pytest.raises(ValueError):
            prometheus_read_catalog(namespace="")

    def test_every_operation_is_read_only(self):
        from backend.contracts.execution import EffectSemantics, SideEffectClass
        catalog = prometheus_read_catalog(namespace=NS)
        for operation in catalog.operations:
            spec = catalog.require(operation)
            assert spec.side_effect_class is SideEffectClass.READ
            assert spec.effect_semantics is EffectSemantics.READ_ONLY
            assert spec.method == "GET"

    def test_profiles_are_read_only_and_capped_at_investigate(self):
        from backend.contracts.intelligence.investigation import AutonomyLevel
        from backend.contracts.intelligence.capability_profile import VerificationRequirement
        profiles = prometheus_read_profiles()
        assert set(profiles) == set(PROMETHEUS_READ_OPERATIONS)
        for profile in profiles.values():
            assert profile.autonomy_ceiling is AutonomyLevel.A1_INVESTIGATE
            assert profile.verification_requirement is VerificationRequirement.NONE

    def test_the_channel_refuses_plaintext_without_a_stated_exception(self):
        from backend.contexts.execution.infrastructure.adapters.connectors.prometheus import (
            build_prometheus_channel,
        )

        class _Tls:
            allow_plaintext = False

        class _Policy:
            tls = _Tls()

        from backend.contracts.execution import ExecutionEnvironment

        with pytest.raises(ValueError, match="plaintext"):
            build_prometheus_channel(
                broker=object(), policy=_Policy(),
                environment=ExecutionEnvironment.DEVELOPMENT,
                base_url="http://127.0.0.1:9090")


# ---------------------------------------------------------------------------
# The translator
# ---------------------------------------------------------------------------

class TestPrometheusTranslator:
    def _classify(self, status, body):
        exchange = ProviderExchange(delivery=ProviderDelivery.DELIVERED,
                                     status_code=status)
        return PrometheusResponseTranslator().classify(_spec(), exchange, body)

    def test_a_200_that_says_error_is_a_failure(self):
        # The dangerous one: Prometheus reports some query failures with HTTP 200.
        failure = self._classify(200, {"status": "error", "errorType": "bad_data",
                                        "error": "invalid parameter"})
        assert failure is ProviderFailure.PROTOCOL_ERROR

    def test_a_real_success_is_a_success(self):
        assert self._classify(200, _vector(_sample())) is None

    def test_the_providers_own_message_survives(self):
        exchange = ProviderExchange(delivery=ProviderDelivery.DELIVERED, status_code=200)
        _, message = PrometheusResponseTranslator().describe(
            exchange, {"status": "error", "errorType": "bad_data",
                       "error": "1:1: parse error"})
        assert "bad_data" in message and "parse error" in message

    def test_http_failures_still_classify(self):
        assert self._classify(401, {}) is ProviderFailure.AUTHENTICATION_FAILURE
        assert self._classify(403, {}) is ProviderFailure.AUTHORIZATION_FAILURE


# ---------------------------------------------------------------------------
# The normalizer
# ---------------------------------------------------------------------------

class TestVectorNormalizer:
    def _normalize(self, body):
        return PrometheusVectorNormalizer().normalize(_spec(), body)

    def test_series_become_declared_bounded_records(self):
        out = self._normalize(_vector(_sample(pod="a", value="3", ts=1788508710.5)))
        assert out["seriesCount"] == 1
        assert out["series"][0] == {"value": "3", "timestamp": 1788508710.5,
                                    "pod": "a", "namespace": NS,
                                    "container": "flapper"}

    def test_the_provider_timestamp_is_lifted_for_observed_at(self):
        out = self._normalize(_vector(_sample(ts=1788508710.0),
                                       _sample(pod="b", ts=1788508715.0)))
        assert out["sampleTimestamp"] == 1788508715.0

    def test_the_value_stays_exactly_what_prometheus_sent(self):
        # A string, not a float: coercing here would silently lose NaN/+Inf and
        # the exact decimal the provider reported.
        out = self._normalize(_vector(_sample(value="0")))
        assert out["series"][0]["value"] == "0"
        assert isinstance(out["series"][0]["value"], str)

    def test_an_empty_vector_is_a_successful_answer(self):
        out = self._normalize(_vector())
        assert out["seriesCount"] == 0
        assert _spec().response_problems(out) == ()

    def test_a_non_vector_result_is_refused(self):
        with pytest.raises(ValueError, match="vector"):
            self._normalize(_vector(result_type="matrix"))

    def test_a_series_without_a_timestamp_is_refused(self):
        with pytest.raises(ValueError, match="timestamp"):
            self._normalize(_vector({"metric": {"pod": "a"}, "value": ["7"]}))

    def test_a_non_string_value_is_refused(self):
        with pytest.raises(ValueError, match="non-string value"):
            self._normalize(_vector({"metric": {"pod": "a"},
                                      "value": [1788508710.0, 7]}))

    def test_a_missing_data_object_is_refused(self):
        with pytest.raises(ValueError, match="no data object"):
            self._normalize({"status": "success"})

    def test_a_window_over_the_declared_cap_is_refused_not_trimmed(self):
        out = self._normalize(_vector(*[_sample(pod=f"p{i}")
                                        for i in range(PROMETHEUS_MAX_SERIES + 1)]))
        problems = _spec().response_problems(out)
        assert problems and "refused rather than trimmed" in problems[0]


# ---------------------------------------------------------------------------
# The declared policies
# ---------------------------------------------------------------------------

class TestDeclaredPolicies:
    def test_kube_state_metrics_shares_the_cluster_origin(self):
        from backend.world.application.lineage import LineageRelation
        policy = observability_lineage_policy()
        k8s = policy.lineage_of(source_kind="connector",
                                source_ref=INSTRUMENT_KUBERNETES_API)
        ksm = policy.lineage_of(source_kind="connector",
                                source_ref=INSTRUMENT_KUBE_STATE_METRICS)
        # The load-bearing assertion of the whole phase.
        assert k8s.origin_id == ksm.origin_id == ORIGIN_KUBERNETES_CLUSTER
        assert k8s.relation is LineageRelation.DIRECT
        assert ksm.relation is LineageRelation.DERIVED

    def test_prometheus_itself_is_a_distinct_origin(self):
        policy = observability_lineage_policy()
        assert policy.lineage_of(
            source_kind="connector", source_ref=INSTRUMENT_PROMETHEUS_SELF
        ).origin_id == ORIGIN_PROMETHEUS_SERVER

    def test_an_unmapped_instrument_is_unknown_not_independent(self):
        from backend.world.application.lineage import LineageRelation
        lineage = observability_lineage_policy().lineage_of(
            source_kind="connector", source_ref="connector:never-heard-of-it")
        assert lineage.relation is LineageRelation.UNKNOWN
        assert not lineage.is_known

    def test_authority_ranks_the_api_above_its_own_re_export(self):
        from backend.contracts.world.confidence import SourceAuthority
        policy = observability_authority_policy()
        api = policy.authority_of(source_kind="connector",
                                  source_ref=INSTRUMENT_KUBERNETES_API)
        ksm = policy.authority_of(source_kind="connector",
                                  source_ref=INSTRUMENT_KUBE_STATE_METRICS)
        assert api is SourceAuthority.AUTHORITATIVE
        assert ksm is SourceAuthority.SINGLE_SOURCE
        assert api.rank > ksm.rank
        # Equal standing between the two metric instruments, so a disagreement
        # between them is a real conflict rather than something authority hides.
        assert ksm is policy.authority_of(source_kind="connector",
                                          source_ref=INSTRUMENT_PROMETHEUS_SELF)

    def test_an_unmapped_source_is_unverified(self):
        from backend.contracts.world.confidence import SourceAuthority
        assert observability_authority_policy().authority_of(
            source_kind="connector", source_ref="connector:whoever"
        ) is SourceAuthority.UNVERIFIED

    def test_freshness_is_stated_per_domain_with_no_universal_ttl(self):
        from backend.world.application.freshness import FreshnessState
        policy = observability_freshness_policy()
        now = datetime.now(timezone.utc)
        fresh = policy.evaluate(observed_at=now - timedelta(seconds=5), now=now,
                                source_kind="connector",
                                predicate=RESTART_COUNT_PREDICATE)
        stale = policy.evaluate(observed_at=now - timedelta(hours=3), now=now,
                                source_kind="connector",
                                predicate=RESTART_COUNT_PREDICATE)
        ungoverned = policy.evaluate(observed_at=now, now=now,
                                     source_kind="connector",
                                     predicate="something-nobody-stated")
        assert fresh.state is FreshnessState.FRESH
        assert stale.state is FreshnessState.STALE
        assert ungoverned.state is FreshnessState.UNKNOWN


# ---------------------------------------------------------------------------
# The shared proposition
# ---------------------------------------------------------------------------

class TestSharedProposition:
    def test_both_providers_project_onto_an_identical_value(self):
        now = datetime.now(timezone.utc)
        k8s = restart_count_legs_from_kubernetes(
            evidence={"pods": [{"name": "flapper-1", "restartCount": 7}]},
            namespace=NS, observed_at=now)
        prom = restart_count_legs_from_prometheus(
            evidence={"series": [{"pod": "flapper-1", "namespace": NS,
                                  "value": "7", "timestamp": now.timestamp() - 1}]},
            namespace=NS, fallback_observed_at=now, retrieved_at=now)
        assert len(k8s) == len(prom) == 1
        # Same subject AND same value bytes — the only way corroboration can
        # compare them, since it compares value digests.
        assert k8s[0].subject_ref == prom[0].subject_ref == pod_subject(
            namespace=NS, pod="flapper-1")
        assert k8s[0].predicate == prom[0].predicate == RESTART_COUNT_PREDICATE
        assert k8s[0].value == prom[0].value == {"restartCount": 7}
        assert json.dumps(k8s[0].value, sort_keys=True) == json.dumps(
            prom[0].value, sort_keys=True)

    def test_the_prometheus_observed_at_is_the_providers_own_time(self):
        now = datetime.now(timezone.utc)
        provider_time = now - timedelta(seconds=30)
        legs = restart_count_legs_from_prometheus(
            evidence={"series": [{"pod": "a", "namespace": NS, "value": "1",
                                  "timestamp": provider_time.timestamp()}]},
            namespace=NS, fallback_observed_at=now, retrieved_at=now)
        assert abs((legs[0].observed_at - provider_time).total_seconds()) < 0.01
        assert legs[0].retrieved_at == now

    def test_a_provider_clock_slightly_ahead_is_reconciled_not_rejected(self):
        now = datetime.now(timezone.utc)
        ahead = now + timedelta(seconds=2)
        legs = restart_count_legs_from_prometheus(
            evidence={"series": [{"pod": "a", "namespace": NS, "value": "1",
                                  "timestamp": ahead.timestamp()}]},
            namespace=NS, fallback_observed_at=now, retrieved_at=now)
        # observed_at is untouched; retrieved_at moves up to meet it so the
        # record is orderable, and the value stays a pure proposition.
        assert abs((legs[0].observed_at - ahead).total_seconds()) < 0.01
        assert legs[0].retrieved_at == legs[0].observed_at
        assert legs[0].value == {"restartCount": 1}

    def test_a_provider_clock_wildly_ahead_is_refused(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ContractViolation, match="clocks disagree"):
            restart_count_legs_from_prometheus(
                evidence={"series": [{"pod": "a", "namespace": NS, "value": "1",
                                      "timestamp": (now + timedelta(hours=1)).timestamp()}]},
                namespace=NS, fallback_observed_at=now, retrieved_at=now)

    def test_a_pod_with_no_restart_count_is_skipped_not_defaulted_to_zero(self):
        now = datetime.now(timezone.utc)
        legs = restart_count_legs_from_kubernetes(
            evidence={"pods": [{"name": "starting-up"}]}, namespace=NS,
            observed_at=now)
        assert legs == ()

    def test_a_non_integer_metric_value_is_skipped(self):
        now = datetime.now(timezone.utc)
        for hostile in ("NaN", "+Inf", "7.5", "not-a-number"):
            legs = restart_count_legs_from_prometheus(
                evidence={"series": [{"pod": "a", "namespace": NS, "value": hostile,
                                      "timestamp": now.timestamp()}]},
                namespace=NS, fallback_observed_at=now, retrieved_at=now)
            assert legs == (), hostile

    def test_a_series_from_another_namespace_is_not_relabelled(self):
        now = datetime.now(timezone.utc)
        legs = restart_count_legs_from_prometheus(
            evidence={"series": [{"pod": "a", "namespace": "somewhere-else",
                                  "value": "1", "timestamp": now.timestamp()}]},
            namespace=NS, fallback_observed_at=now, retrieved_at=now)
        assert legs == ()


# ---------------------------------------------------------------------------
# Corroboration over the declared policies
# ---------------------------------------------------------------------------

class _Obs:
    """The minimum an Observation needs to be corroborated over."""

    def __init__(self, source_ref, value, observed_at):
        from backend.contracts.world import (
            Observation, ObservationInstant, ObservationSource,
            ObservationSourceKind, ProvenanceRef,
        )
        from backend.contracts.evidence import SourceStatus
        from backend.contracts.tenant import TenantRef
        from backend.platform.identity.generators import prefixed_id

        self.observation = Observation(
            record_id=prefixed_id("wobs"), tenant=TenantRef(tenant_id="dev"),
            recorded_at=observed_at,
            provenance=ProvenanceRef(produced_by=source_ref, source_ref=source_ref,
                                     execution_ref="ex-1"),
            source=ObservationSource(kind=ObservationSourceKind.CONNECTOR,
                                     source_ref=source_ref),
            subject_ref="kubernetes:pod:cortex-p94/flapper-1",
            predicate=RESTART_COUNT_PREDICATE, value=value,
            status=SourceStatus.RETURNED_DATA,
            instant=ObservationInstant(observed_at=observed_at,
                                       retrieved_at=observed_at))


def _corroborate(pairs):
    """Run the real corroboration decision over the real declared lineage."""
    from backend.world.application.belief import BeliefFormation
    from backend.contracts.tenant import TenantRef
    from backend.contracts.world.epistemic import EpistemicStatus
    from backend.platform.hashing import compute_digest

    now = datetime.now(timezone.utc)
    observations = [_Obs(ref, value, now).observation for ref, value in pairs]
    latest = {o.source.source_ref: o for o in observations}
    digests = {compute_digest(o.value).value for o in observations}
    effective = (next(iter(digests)) if len(digests) == 1 else None)
    status = (EpistemicStatus.AFFIRMED if len(digests) == 1
              else EpistemicStatus.CONFLICTED)
    formation = BeliefFormation(
        query=None, observations=None,
        authority_policy=observability_authority_policy(),
        lineage_policy=observability_lineage_policy())
    return formation._corroborate(  # noqa: SLF001 — the decision under test
        latest, {ref: 1 for ref in latest}, effective, status)


class TestCorroborationOverDeclaredLineage:
    def test_case_c_same_origin_agreeing_is_correlated(self):
        from backend.world.application.belief import CorroborationLevel
        result = _corroborate([(INSTRUMENT_KUBERNETES_API, {"restartCount": 7}),
                               (INSTRUMENT_KUBE_STATE_METRICS, {"restartCount": 7})])
        assert result.level is CorroborationLevel.CORRELATED
        assert result.independent_origins == (ORIGIN_KUBERNETES_CLUSTER,)
        assert ORIGIN_KUBERNETES_CLUSTER in result.reason
        assert len(result.supporting) == 2   # both preserved, neither counted twice

    def test_case_e_distinct_origins_agreeing_is_independent(self):
        from backend.world.application.belief import CorroborationLevel
        result = _corroborate([(INSTRUMENT_KUBERNETES_API, {"restartCount": 7}),
                               (INSTRUMENT_PROMETHEUS_SELF, {"restartCount": 7})])
        assert result.level is CorroborationLevel.INDEPENDENT
        assert set(result.independent_origins) == {ORIGIN_KUBERNETES_CLUSTER,
                                                    ORIGIN_PROMETHEUS_SERVER}

    def test_case_d_unknown_lineage_is_indeterminate(self):
        from backend.world.application.belief import CorroborationLevel
        result = _corroborate([("connector:mystery-a", {"restartCount": 7}),
                               ("connector:mystery-b", {"restartCount": 7})])
        assert result.level is CorroborationLevel.INDETERMINATE
        assert "unproven" in result.reason.lower()

    def test_case_f_disagreement_is_contradicted_and_preserved(self):
        from backend.world.application.belief import CorroborationLevel
        result = _corroborate([(INSTRUMENT_KUBE_STATE_METRICS, {"restartCount": 7}),
                               (INSTRUMENT_PROMETHEUS_SELF, {"restartCount": 9})])
        assert result.level is CorroborationLevel.CONTRADICTED
        assert result.contradicting or result.supporting

    def test_one_source_alone_is_never_corroborated(self):
        from backend.world.application.belief import CorroborationLevel
        result = _corroborate([(INSTRUMENT_KUBERNETES_API, {"restartCount": 7})])
        assert result.level is CorroborationLevel.SINGLE

    def test_no_numeric_confidence_appears_anywhere(self):
        result = _corroborate([(INSTRUMENT_KUBERNETES_API, {"restartCount": 7}),
                               (INSTRUMENT_KUBE_STATE_METRICS, {"restartCount": 7})])
        document = result.to_dict()
        assert not any(isinstance(v, float) for v in document.values())
        assert "confidence" not in json.dumps(document).lower()


class TestIntelligenceCannotReachAProvider:
    def test_the_world_read_port_holds_only_a_query(self):
        from backend.api.observability_evidence import WorldQueryEvidencePort
        assert WorldQueryEvidencePort.__slots__ == ("_query",)

    def test_no_intelligence_module_imports_a_connector_or_http_client(self):
        import os
        import backend.intelligence as intel
        offenders = []
        for root, _dirs, files in os.walk(os.path.dirname(intel.__file__)):
            for name in files:
                if not name.endswith(".py"):
                    continue
                text = open(os.path.join(root, name), encoding="utf-8").read()
                if ("adapters.connectors" in text or "import httpx" in text
                        or "backend.connectors" in text):
                    offenders.append(name)
        assert offenders == []

    def test_the_v1_prometheus_client_is_not_reachable_from_the_governed_path(self):
        # The quarantined connector takes a caller-supplied PromQL string. The
        # governed module must not import it, directly or otherwise.
        import backend.contexts.execution.infrastructure.adapters.connectors.prometheus as governed
        # Checked as IMPORTS, not as text: the module legitimately *names* the
        # quarantined zone in prose to say that it does not use it.
        import ast
        tree = ast.parse(open(governed.__file__, encoding="utf-8").read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any(name in ("os", "httpx", "requests", "aiohttp")
                       or name.startswith("backend.connectors")
                       or name.startswith("prometheus_client")
                       for name in imported), sorted(imported)
