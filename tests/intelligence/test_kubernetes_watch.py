"""Phase 9.3 (ADR-083): the governed Kubernetes WATCH — unit evidence.

What these prove without a network:

- ``watch=true`` and ``allowWatchBookmarks=true`` are part of the *operation*,
  not of caller input: they come from ``static_query``, they are in the digest,
  and a caller cannot supply or override them.
- The NDJSON decoder reads a real watch window, and refuses a truncated one, an
  unparseable line, and a non-object line — never half-accepting.
- The normalizer turns a window into declared, bounded per-event records; fails
  closed on an unknown event type, a missing ``metadata.resourceVersion`` and a
  mutation identifying no resource; keeps BOOKMARK distinct from a mutation; and
  surfaces an in-stream 410 as a scalar without ever making it an event.
- ``resourceVersion`` survives every hop byte-for-byte and is never ordered,
  parsed or compared as a number.
- Bounded record evidence is bounded: a window over the declared cap is refused,
  not trimmed, and a nested structure inside a record is dropped.
- The driver records mutations as Observations, never a bookmark; advances only
  after the events are durable; never reuses an expired position; and bounds its
  expiry recovery.

The real-cluster legs live in ``scripts/phase93_kubernetes_watch_harness.py``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.provider import ProviderDelivery, ProviderFailure
from backend.contexts.execution.domain.provider_operation import RecordEvidenceSpec
from backend.contexts.execution.infrastructure.adapters.channel import ProviderExchange
from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
    KUBERNETES_REAL_READ_OPERATIONS,
    KUBERNETES_WATCH_OPERATION,
    WATCH_MAX_EVENTS,
    WATCH_WINDOW_SECONDS,
    KubernetesReadNormalizer,
    KubernetesResponseTranslator,
    KubernetesWatchDecoder,
    kubernetes_read_catalog,
    kubernetes_real_read_catalog,
)


def _spec():
    return kubernetes_real_read_catalog().require(KUBERNETES_WATCH_OPERATION)


def _pod(name="web-1", rv="100", uid="uid-1"):
    return {"kind": "Pod", "apiVersion": "v1",
            "metadata": {"name": name, "namespace": "cortex-p93",
                         "uid": uid, "resourceVersion": rv}}


def _ndjson(*events) -> bytes:
    return ("\n".join(json.dumps(e) for e in events)).encode()


class _Exchange:
    """Just enough of a ProviderExchange for the decoder; ``json`` is the
    fallback path and must not be reached for a watch operation."""

    def __init__(self, body, truncated=False, status_code=200):
        self.body, self.truncated = body, truncated
        self.status_code = status_code
        self.json_called = False

    def json(self):
        self.json_called = True
        return {"fallback": True}, None


# ---------------------------------------------------------------------------
# The declaration
# ---------------------------------------------------------------------------

class TestWatchDeclaration:
    def test_watch_is_declared_not_passed(self):
        spec = _spec()
        assert spec.static_query == {"watch": "true", "allowWatchBookmarks": "true"}
        plan = spec.plan({"namespace": "cortex-p93", "resourceVersion": "4954",
                          "timeoutSeconds": 20})
        assert plan.query["watch"] == "true"
        assert plan.query["allowWatchBookmarks"] == "true"
        # Same path as the list; the query is what makes it a watch.
        assert plan.path == "/api/v1/namespaces/cortex-p93/pods"

    def test_a_caller_cannot_override_the_static_query(self):
        # Stronger than "the override is ignored": an undeclared input is a hard
        # refusal, so a caller trying to turn the watch off gets no request at
        # all rather than a request that quietly did something else.
        spec = _spec()
        problems = spec.input_problems(
            {"namespace": "n", "resourceVersion": "1", "timeoutSeconds": 5,
             "watch": "false", "allowWatchBookmarks": "false"})
        assert any("watch" in p for p in problems)
        with pytest.raises(ContractViolation):
            spec.plan({"namespace": "n", "resourceVersion": "1", "timeoutSeconds": 5,
                       "watch": "false"})

    def test_a_spec_cannot_declare_a_static_query_a_caller_also_supplies(self):
        from backend.contexts.execution.domain.provider_operation import (
            ParameterKind, ParameterLocation, ParameterSpec, ProviderOperationSpec,
        )
        from backend.contracts.execution import EffectSemantics, SideEffectClass

        with pytest.raises(ContractViolation):
            ProviderOperationSpec(
                operation="x.y", method="GET", path_template="/x",
                side_effect_class=SideEffectClass.READ,
                effect_semantics=EffectSemantics.READ_ONLY,
                parameters=(ParameterSpec(name="watch", kind=ParameterKind.STRING,
                                          location=ParameterLocation.QUERY,
                                          required=False),),
                static_query={"watch": "true"})

    def test_static_query_and_records_are_in_the_digest(self):
        spec = _spec()
        import dataclasses
        widened = dataclasses.replace(
            spec, response_evidence_records=RecordEvidenceSpec(
                field_name="events", fields=("type",), max_records=1024))
        assert widened.digest != spec.digest
        no_watch = dataclasses.replace(spec, static_query={})
        assert no_watch.digest != spec.digest

    def test_watch_is_a_read_and_the_real_exposure_is_list_plus_watch(self):
        from backend.contracts.execution import EffectSemantics, SideEffectClass
        spec = _spec()
        assert spec.side_effect_class is SideEffectClass.READ
        assert spec.effect_semantics is EffectSemantics.READ_ONLY
        assert spec.method == "GET"
        # The watch is one of the real exposures; 9.5 added two more reads.
        # What matters here is that the watch is among them and is a READ.
        assert KUBERNETES_WATCH_OPERATION in KUBERNETES_REAL_READ_OPERATIONS
        assert "kubernetes.pods.list" in KUBERNETES_REAL_READ_OPERATIONS

    def test_the_window_cannot_outlive_the_transport_read_timeout(self):
        from backend.platform.transport.policy import TimeoutPolicy
        # The declared ceiling on timeoutSeconds must stay under the read
        # timeout, or a quiet window becomes an ambiguous ReadTimeout.
        assert WATCH_WINDOW_SECONDS < TimeoutPolicy().read_seconds
        assert _spec().input_problems(
            {"namespace": "n", "resourceVersion": "1",
             "timeoutSeconds": WATCH_WINDOW_SECONDS + 1})

    def test_a_watch_without_a_position_is_refused(self):
        # No resourceVersion means "from now, plus everything" — a different
        # operation with no continuity. Declared required, so it is refused.
        assert _spec().input_problems({"namespace": "n", "timeoutSeconds": 5})

    def test_the_watch_profile_is_read_only_and_capped_at_investigate(self):
        from backend.contracts.intelligence.investigation import AutonomyLevel
        from backend.contracts.intelligence.capability_profile import VerificationRequirement
        from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
            kubernetes_read_profiles,
        )
        profile = kubernetes_read_profiles()[KUBERNETES_WATCH_OPERATION]
        assert profile.autonomy_ceiling is AutonomyLevel.A1_INVESTIGATE
        assert profile.verification_requirement is VerificationRequirement.NONE
        assert profile.reversible is True


# ---------------------------------------------------------------------------
# The decoder
# ---------------------------------------------------------------------------

class TestWatchDecoder:
    def test_decodes_a_real_window(self):
        body, problem = KubernetesWatchDecoder().decode(_spec(), _Exchange(_ndjson(
            {"type": "ADDED", "object": _pod(rv="10")},
            {"type": "MODIFIED", "object": _pod(rv="11")},
        )))
        assert problem is None
        assert [e["type"] for e in body["events"]] == ["ADDED", "MODIFIED"]

    def test_an_empty_window_is_an_empty_window_not_an_error(self):
        body, problem = KubernetesWatchDecoder().decode(_spec(), _Exchange(b""))
        assert (problem, body) == (None, {"events": []})

    def test_a_truncated_window_is_refused_not_partially_accepted(self):
        body, problem = KubernetesWatchDecoder().decode(
            _spec(), _Exchange(_ndjson({"type": "ADDED", "object": _pod()}), truncated=True))
        assert body is None and "truncated" in problem

    def test_one_bad_line_refuses_the_whole_window(self):
        body, problem = KubernetesWatchDecoder().decode(
            _spec(), _Exchange(b'{"type":"ADDED","object":{}}\n{not json}'))
        assert body is None and "line 2" in problem

    def test_a_non_object_line_is_refused(self):
        body, problem = KubernetesWatchDecoder().decode(_spec(), _Exchange(b'[1,2,3]'))
        assert body is None and "not a" in problem

    def test_a_failure_body_keeps_the_provider_dialect(self):
        # A refused watch is not a stream: Kubernetes answers with an ordinary
        # Status document, and wrapping it in an events envelope would cost the
        # operator the cluster's own sentence.
        exchange = _Exchange(b'{"kind":"Status","code":410}', status_code=410)
        body, problem = KubernetesWatchDecoder().decode(_spec(), exchange)
        assert exchange.json_called and body == {"fallback": True}

    def test_a_non_watch_operation_falls_through_to_json(self):
        spec = kubernetes_real_read_catalog().require("kubernetes.pods.list")
        exchange = _Exchange(b"{}")
        body, problem = KubernetesWatchDecoder().decode(spec, exchange)
        assert exchange.json_called and body == {"fallback": True}


# ---------------------------------------------------------------------------
# The normalizer
# ---------------------------------------------------------------------------

class TestWatchNormalizer:
    def _normalize(self, *events):
        body, problem = KubernetesWatchDecoder().decode(_spec(), _Exchange(_ndjson(*events)))
        assert problem is None
        return KubernetesReadNormalizer().normalize(_spec(), body)

    def test_events_become_declared_bounded_records(self):
        out = self._normalize(
            {"type": "ADDED", "object": _pod(name="a", rv="10", uid="u-a")},
            {"type": "DELETED", "object": _pod(name="b", rv="12", uid="u-b")},
        )
        assert out["eventCount"] == 2
        assert out["events"][0] == {"type": "ADDED", "resourceVersion": "10",
                                    "kind": "Pod", "name": "a",
                                    "namespace": "cortex-p93", "uid": "u-a"}
        assert out["lastResourceVersion"] == "12"

    def test_resource_version_is_opaque_and_exact(self):
        for rv in ("00123", "9a8b7c", "999999999999999999999999"):
            out = self._normalize({"type": "MODIFIED", "object": _pod(rv=rv)})
            assert out["events"][0]["resourceVersion"] == rv
            assert out["lastResourceVersion"] == rv
            assert isinstance(out["lastResourceVersion"], str)

    def test_last_position_is_the_last_event_not_the_largest(self):
        # Opaque means no ordering. The last event's value wins even when a
        # numeric reading would pick a different one.
        out = self._normalize(
            {"type": "ADDED", "object": _pod(rv="900")},
            {"type": "MODIFIED", "object": _pod(rv="1000")},
            {"type": "MODIFIED", "object": _pod(rv="99")},
        )
        assert out["lastResourceVersion"] == "99"

    def test_bookmark_advances_position_and_is_not_a_mutation(self):
        out = self._normalize(
            {"type": "BOOKMARK", "object": {"metadata": {"resourceVersion": "77"}}})
        assert out["bookmarkCount"] == 1
        assert out["lastResourceVersion"] == "77"
        assert out["events"] == [{"type": "BOOKMARK", "resourceVersion": "77"}]
        assert "name" not in out["events"][0]

    def test_unknown_event_type_fails_closed(self):
        with pytest.raises(ValueError, match="does not understand"):
            self._normalize({"type": "SYNTHESIZED", "object": _pod()})

    def test_missing_resource_version_fails_closed(self):
        with pytest.raises(ValueError, match="resourceVersion"):
            self._normalize({"type": "ADDED",
                             "object": {"kind": "Pod", "metadata": {"name": "a"}}})

    def test_a_mutation_identifying_no_resource_fails_closed(self):
        with pytest.raises(ValueError, match="identifies no resource"):
            self._normalize({"type": "ADDED", "object": {
                "kind": "Pod", "metadata": {"resourceVersion": "10"}}})

    def test_an_event_with_no_object_fails_closed(self):
        with pytest.raises(ValueError, match="carries no object"):
            self._normalize({"type": "ADDED"})

    def test_in_stream_410_is_surfaced_and_never_becomes_an_event(self):
        out = self._normalize(
            {"type": "ADDED", "object": _pod(name="a", rv="10")},
            {"type": "ERROR", "object": {"kind": "Status", "code": 410,
                                          "reason": "Expired",
                                          "message": "too old resource version: 10 (99)"}},
            {"type": "ADDED", "object": _pod(name="after", rv="99")},
        )
        assert out["streamErrorCode"] == 410
        assert "Expired" in out["streamErrorReason"]
        # The event before the error is real and kept; nothing after it is read.
        assert [e["type"] for e in out["events"]] == ["ADDED"]
        assert out["lastResourceVersion"] == "10"
        assert all(e["type"] != "ERROR" for e in out["events"])

    def test_an_empty_window_is_a_successful_answer(self):
        out = self._normalize()
        assert out["eventCount"] == 0
        assert "lastResourceVersion" not in out
        assert _spec().response_problems(out) == ()


# ---------------------------------------------------------------------------
# Bounded record evidence
# ---------------------------------------------------------------------------

class TestRecordEvidence:
    def test_a_window_over_the_cap_is_refused_not_trimmed(self):
        body = {"eventCount": WATCH_MAX_EVENTS + 1, "events": [
            {"type": "ADDED", "resourceVersion": str(i), "name": f"p{i}"}
            for i in range(WATCH_MAX_EVENTS + 1)]}
        problems = _spec().response_problems(body)
        assert problems and "refused rather than trimmed" in problems[0]

    def test_only_declared_scalar_fields_survive(self):
        spec = RecordEvidenceSpec(field_name="events", fields=("type", "name"))
        got = spec.extract({"events": [{
            "type": "ADDED", "name": "a", "undeclared": "dropped",
            "nested": {"payload": "dropped"}, "list": [1, 2, 3]}]})
        assert got == ({"type": "ADDED", "name": "a"},)

    def test_strings_are_truncated_like_flat_evidence(self):
        spec = RecordEvidenceSpec(field_name="e", fields=("v",), max_string_length=8)
        assert spec.extract({"e": [{"v": "x" * 100}]}) == ({"v": "x" * 8},)

    def test_a_record_spec_must_declare_its_fields_and_a_finite_cap(self):
        with pytest.raises(ContractViolation):
            RecordEvidenceSpec(field_name="e", fields=())
        with pytest.raises(ContractViolation):
            RecordEvidenceSpec(field_name="e", fields=("a",), max_records=0)
        with pytest.raises(ContractViolation):
            RecordEvidenceSpec(field_name="e", fields=("a",), max_records=99999)

    def test_records_are_absent_from_evidence_when_the_window_is_empty(self):
        assert "events" not in _spec().evidence({"eventCount": 0, "events": []})

    def test_record_evidence_stays_the_exception_not_the_rule(self):
        # Only the two operations whose answer is genuinely a SEQUENCE declare
        # record evidence: a watch window (9.3) and a pod list (9.4). Every other
        # read keeps flat scalar evidence, and only the watch carries a static
        # query. Pinned so record evidence does not spread by habit.
        with_records, with_query = set(), set()
        for name in kubernetes_read_catalog().operations:
            spec = kubernetes_read_catalog().require(name)
            if spec.response_evidence_records is not None:
                with_records.add(name)
            if spec.static_query:
                with_query.add(name)
        assert with_records == {KUBERNETES_WATCH_OPERATION, "kubernetes.pods.list"}
        assert with_query == {KUBERNETES_WATCH_OPERATION}


# ---------------------------------------------------------------------------
# Through the real generic adapter
# ---------------------------------------------------------------------------

class _WatchAdapter:
    """The real ``ConnectorAdapter``, real catalog, real decoder/normalizer/
    translator, driven at the ``_normalise`` seam. No channel, no network."""

    def __init__(self):
        from backend.contracts.connector import IsolationTier
        from backend.contracts.execution import ExecutionEnvironment
        from backend.contracts.provider import ProviderRef
        from backend.contexts.execution import WorkerInterface, WorkerScope
        from backend.contexts.execution.domain.worker import WorkerKind
        from backend.contexts.execution.domain.worker_directory import WorkerImplementation
        from backend.contexts.execution.infrastructure.adapters.connector import ConnectorAdapter

        catalog = kubernetes_real_read_catalog()
        implementation = WorkerImplementation(
            worker_id="kubernetes-connector", worker_kind=WorkerKind.CONNECTOR,
            interface=WorkerInterface.CONNECTOR,
            implementation="ConnectorAdapter+connectors.kubernetes",
            implementation_version="1.0.0", isolation=IsolationTier.CONTAINED,
            scope=WorkerScope.PLATFORM,
            supported_environments=frozenset({ExecutionEnvironment.DEVELOPMENT}),
            supported_effects=frozenset(
                {catalog.require(op).effect_semantics for op in catalog.operations}),
            supported_providers=frozenset({"kubernetes"}),
            supported_operations=frozenset(catalog.operations),
            supports_provider_idempotency=False)
        self.adapter = ConnectorAdapter(
            implementation=implementation,
            provider=ProviderRef(provider_id="kubernetes"),
            catalog=catalog,
            translator=KubernetesResponseTranslator(),
            normalizer=KubernetesReadNormalizer(),
            decoder=KubernetesWatchDecoder(),
        )
        self.spec = catalog.require(KUBERNETES_WATCH_OPERATION)

    def normalise(self, *, status=200, body=b"", truncated=False):
        class _A:
            operation = KUBERNETES_WATCH_OPERATION
            idempotency_key = None
        exchange = ProviderExchange(
            delivery=ProviderDelivery.DELIVERED, status_code=status,
            body=body, truncated=truncated, response_digest="d")
        return self.adapter._normalise(self.spec, _A(), exchange)


class TestThroughTheAdapter:
    def test_a_window_reaches_evidence_as_records(self):
        outcome = _WatchAdapter().normalise(body=_ndjson(
            {"type": "ADDED", "object": _pod(name="a", rv="10", uid="u-a")},
            {"type": "BOOKMARK", "object": {"metadata": {"resourceVersion": "11"}}},
        ))
        assert outcome.succeeded
        assert outcome.evidence["eventCount"] == 2
        assert outcome.evidence["lastResourceVersion"] == "11"
        assert outcome.evidence["bookmarkCount"] == 1
        assert outcome.evidence["events"][0]["name"] == "a"

    def test_an_unknown_event_type_is_malformed_through_the_adapter(self):
        outcome = _WatchAdapter().normalise(
            body=_ndjson({"type": "NOPE", "object": _pod()}))
        assert not outcome.succeeded
        assert outcome.provider_failure is ProviderFailure.MALFORMED_RESPONSE
        assert not outcome.evidence

    def test_a_truncated_window_is_malformed_through_the_adapter(self):
        outcome = _WatchAdapter().normalise(
            body=_ndjson({"type": "ADDED", "object": _pod()}), truncated=True)
        assert not outcome.succeeded
        assert outcome.provider_failure is ProviderFailure.RESPONSE_TOO_LARGE
        assert not outcome.evidence

    def test_http_410_is_a_failure_carrying_no_evidence(self):
        outcome = _WatchAdapter().normalise(status=410, body=json.dumps(
            {"kind": "Status", "code": 410, "reason": "Expired",
             "message": "too old resource version: 4 (99)"}).encode())
        assert not outcome.succeeded
        assert outcome.status_code == 410
        assert not outcome.evidence
        # The cluster's own sentence survives: a failure body keeps the
        # provider's dialect and is never decoded as a stream.
        assert "too old resource version" in outcome.error_message

    def test_a_failure_status_never_produces_events(self):
        for status in (401, 403, 429, 500):
            outcome = _WatchAdapter().normalise(
                status=status, body=b'{"kind":"Status","message":"no"}')
            assert not outcome.succeeded and not outcome.evidence


# ---------------------------------------------------------------------------
# The driver
# ---------------------------------------------------------------------------

class _Outcome:
    def __init__(self, evidence, succeeded=True, status=None, execution_id="ex-1"):
        self.evidence, self.succeeded, self.status = evidence, succeeded, status
        self.execution_id, self.operation = execution_id, "op"
        self.failure_reason, self.node_state, self.duration_seconds = None, "x", 0.01

    @property
    def expired(self):
        from backend.api.governed_read_observer import GovernedReadOutcome
        return GovernedReadOutcome.expired.fget(self)


class _Reader:
    def __init__(self, script): self.script, self.calls = list(script), []

    def read(self, context, *, operation, payload, **kw):
        self.calls.append((operation, dict(payload)))
        return self.script.pop(0)


class _Observer:
    def __init__(self): self.legs = []

    def observe(self, *, tenant, outcome, legs, trace_ref=None, now=None):
        self.legs.extend(legs)
        return tuple((leg, True) for leg in legs)


class _Observations:
    def __init__(self, latest=None): self.latest = latest

    def latest_for_subject(self, **kw): return self.latest


class _Leadership:
    def __init__(self, granted=True): self.granted, self.asserted = granted, 0

    def acquire(self, **kw): return object() if self.granted else None

    def heartbeat(self, handle, **kw): return handle if self.granted else None

    def assert_current(self, handle): self.asserted += 1

    def release(self, handle): return True


def _driver(reader, observer, observations, leadership=None):
    from backend.api.kubernetes_watch_driver import KubernetesWatchDriver
    from backend.contracts.tenant import TenantRef
    return KubernetesWatchDriver(
        reader=reader, observer=observer, observations=observations,
        leadership=leadership or _Leadership(), tenant=TenantRef(tenant_id="dev"),
        namespace="cortex-p93", list_operation="kubernetes.pods.list",
        watch_operation=KUBERNETES_WATCH_OPERATION,
        window_seconds=WATCH_WINDOW_SECONDS,
        clock=lambda: datetime(2026, 9, 4, tzinfo=timezone.utc))


class _Position:
    def __init__(self, value): self.value, self.record_id = value, "wobs_1"


class TestWatchDriver:
    def test_a_first_cycle_establishes_from_a_governed_list(self):
        reader = _Reader([_Outcome({"resourceVersion": "500", "podCount": 2})])
        observer = _Observer()
        report = _driver(reader, observer, _Observations()).cycle(None)
        assert report.outcome == "established" and report.advanced_to == "500"
        assert reader.calls[0][0] == "kubernetes.pods.list"
        assert observer.legs[0].value["resourceVersion"] == "500"
        assert observer.legs[0].value["origin"] == "list"

    def test_the_watch_starts_from_the_exact_recorded_position(self):
        reader = _Reader([_Outcome({"eventCount": 0, "events": []})])
        observations = _Observations(_Position({"resourceVersion": "00500",
                                                "origin": "list"}))
        report = _driver(reader, _Observer(), observations).cycle(None)
        operation, payload = reader.calls[0]
        assert operation == KUBERNETES_WATCH_OPERATION
        assert payload["resourceVersion"] == "00500"   # byte-for-byte, opaque
        assert payload["timeoutSeconds"] == WATCH_WINDOW_SECONDS
        assert report.outcome == "idle" and report.advanced_to is None

    def test_mutations_become_observations_and_bookmarks_do_not(self):
        reader = _Reader([_Outcome({
            "eventCount": 3, "bookmarkCount": 1, "lastResourceVersion": "13",
            "events": [
                {"type": "ADDED", "name": "a", "uid": "u-a", "kind": "Pod",
                 "namespace": "cortex-p93", "resourceVersion": "11"},
                {"type": "BOOKMARK", "resourceVersion": "12"},
                {"type": "DELETED", "name": "b", "uid": "u-b", "kind": "Pod",
                 "namespace": "cortex-p93", "resourceVersion": "13"},
            ]})])
        observer = _Observer()
        report = _driver(reader, observer,
                         _Observations(_Position({"resourceVersion": "10"}))).cycle(None)
        mutations = [leg for leg in observer.legs if leg.predicate == "state"]
        assert [leg.value["eventType"] for leg in mutations] == ["ADDED", "DELETED"]
        assert [leg.subject_ref for leg in mutations] == [
            "kubernetes:pod:cortex-p93/a", "kubernetes:pod:cortex-p93/b"]
        # ...and no observation asserts a resource state from the bookmark.
        assert all("BOOKMARK" != leg.value.get("eventType") for leg in observer.legs)
        checkpoints = [leg for leg in observer.legs if leg.predicate == "watch_position"]
        assert len(checkpoints) == 1
        assert checkpoints[0].value == {"resourceVersion": "13", "origin": "watch",
                                        "namespace": "cortex-p93", "eventCount": 3}
        assert report.advanced_to == "13" and report.bookmarks == 1

    def test_events_are_recorded_before_the_position_advances(self):
        reader = _Reader([_Outcome({
            "eventCount": 1, "lastResourceVersion": "11",
            "events": [{"type": "ADDED", "name": "a", "uid": "u", "kind": "Pod",
                        "namespace": "cortex-p93", "resourceVersion": "11"}]})])
        observer = _Observer()
        _driver(reader, observer,
                _Observations(_Position({"resourceVersion": "10"}))).cycle(None)
        # Order is the crash-safety property: lose the checkpoint and the event
        # is re-delivered; lose the event and it is gone.
        assert [leg.predicate for leg in observer.legs] == ["state", "watch_position"]

    def test_a_failed_watch_records_nothing_and_does_not_advance(self):
        failed = _Outcome({}, succeeded=False, status=403)
        reader = _Reader([failed])
        observer = _Observer()
        report = _driver(reader, observer,
                         _Observations(_Position({"resourceVersion": "10"}))).cycle(None)
        assert report.outcome == "watch_failed"
        assert report.advanced_to is None and observer.legs == []
        assert len(reader.calls) == 1   # no fresh LIST: 403 is not an expiry

    def test_410_takes_a_fresh_governed_list_and_never_reuses_the_old_position(self):
        expired = _Outcome({"streamErrorCode": 410, "eventCount": 0, "events": []})
        relisted = _Outcome({"resourceVersion": "900", "podCount": 1})
        reader = _Reader([expired, relisted])
        observer = _Observer()
        report = _driver(reader, observer,
                         _Observations(_Position({"resourceVersion": "10"}))).cycle(None)
        assert report.outcome == "recovered_from_expiry"
        assert report.recovered_from_expiry and report.started_from == "10"
        assert report.advanced_to == "900"
        assert [c[0] for c in reader.calls] == [
            KUBERNETES_WATCH_OPERATION, "kubernetes.pods.list"]
        # The expired position is never presented again...
        assert reader.calls[1][1] == {"namespace": "cortex-p93"}
        # ...and the recovery is legible in provenance rather than smoothed over.
        checkpoint = [l for l in observer.legs if l.predicate == "watch_position"][0]
        assert checkpoint.value["origin"] == "list_after_expiry"
        assert checkpoint.value["resourceVersion"] == "900"

    def test_http_410_is_treated_as_expiry_too(self):
        reader = _Reader([_Outcome({}, succeeded=False, status=410),
                          _Outcome({"resourceVersion": "901"})])
        report = _driver(reader, _Observer(),
                         _Observations(_Position({"resourceVersion": "10"}))).cycle(None)
        assert report.recovered_from_expiry and report.advanced_to == "901"

    def test_expiry_recovery_is_bounded(self):
        driver = _driver(
            _Reader([_Outcome({"streamErrorCode": 410, "eventCount": 0, "events": []}),
                     _Outcome({"resourceVersion": "1"})] * 6),
            _Observer(), _Observations(_Position({"resourceVersion": "10"})))
        outcomes = [driver.cycle(None).outcome for _ in range(4)]
        assert outcomes[-1] == "expiry_recovery_exhausted"

    def test_a_follower_does_nothing_at_all(self):
        reader = _Reader([])
        observer = _Observer()
        report = _driver(reader, observer, _Observations(),
                         leadership=_Leadership(granted=False)).cycle(None)
        assert report.outcome == "follower"
        assert reader.calls == [] and observer.legs == []

    def test_a_fenced_watcher_keeps_its_events_but_does_not_advance(self):
        class _Fenced(_Leadership):
            """Grants the role, then the database refuses to renew it — which is
            what a stale holder actually experiences: ``heartbeat`` is a
            conditional UPDATE on the fencing token, so a process whose role was
            taken while it worked gets None back from the store."""

            def heartbeat(self, handle, **kw):
                return None

        reader = _Reader([_Outcome({
            "eventCount": 1, "lastResourceVersion": "11",
            "events": [{"type": "ADDED", "name": "a", "uid": "u", "kind": "Pod",
                        "namespace": "cortex-p93", "resourceVersion": "11"}]})])
        observer = _Observer()
        report = _driver(reader, observer,
                         _Observations(_Position({"resourceVersion": "10"})),
                         leadership=_Fenced()).cycle(None)
        assert report.outcome == "fenced" and report.advanced_to is None
        assert [leg.predicate for leg in observer.legs] == ["state"]

    def test_a_position_may_never_be_empty(self):
        from backend.api.kubernetes_watch_driver import WatchPosition
        with pytest.raises(ContractViolation):
            WatchPosition(resource_version="", origin="list")


class TestObserverRefusals:
    def test_a_failed_read_produces_no_observation(self):
        from backend.api.governed_read_observer import (
            GovernedReadObserver, GovernedReadOutcome, ObservationLeg,
        )

        class _Ingest:
            def ingest(self, **kw): raise AssertionError("must not be reached")

        observer = GovernedReadObserver(
            ingestion=_Ingest(), source_ref="connector:kubernetes",
            produced_by="connector:kubernetes")
        with pytest.raises(ContractViolation, match="observed nothing"):
            observer.observe(
                tenant=object(),
                outcome=GovernedReadOutcome(
                    operation="op", execution_id="e", node_state="failed",
                    succeeded=False, evidence={}),
                legs=(ObservationLeg(subject_ref="s", predicate="p", value={}),))
