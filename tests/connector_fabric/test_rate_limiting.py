"""Phase 11.1-K, audit S-3: the gateway rate limiter exists, is wired, and refuses.

Deterministic: an injected clock drives the buckets. The gateway-level test
runs the REAL ``SecureCapabilityInvocationGateway`` (the invocation matrix
fixture) with the REAL limiter, so "wired and refusing" is proven at the one
choke point every provider call passes, not just in the limiter's own unit.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.contracts.errors import ContractViolation
from backend.contexts.execution.infrastructure.rate_limiting import (
    RATE_LIMIT_METRIC,
    RateLimitPolicy,
    TokenBucketRateLimiter,
    build_rate_limiter,
)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class Metrics:
    def __init__(self) -> None:
        self.counts: list = []

    def increment(self, name, *, value=1, labels=None):
        self.counts.append((name, dict(labels or {})))


def _req(tenant="t-a", capability="platform.kubernetes.pods.list@1",
         operation="kubernetes.pods.list"):
    return SimpleNamespace(tenant_id=tenant, capability_ref=capability, operation=operation)


def _limiter(**policy):
    clock, metrics = Clock(), Metrics()
    defaults = dict(capability_per_minute=60, capability_burst=2, tenant_per_minute=120,
                    tenant_burst=3, provider_per_minute=600, provider_burst=100)
    defaults.update(policy)
    return TokenBucketRateLimiter(RateLimitPolicy(**defaults), clock=clock, metrics=metrics), clock, metrics


class TestBudgets:
    def test_within_budget_passes_and_the_burst_is_spent(self):
        limiter, _, _ = _limiter()
        assert limiter.check(None, _req()) == ()
        assert limiter.check(None, _req()) == ()
        exceeded = limiter.check(None, _req())
        assert exceeded and "platform.kubernetes.pods.list@1 for this tenant" in exceeded[0]

    def test_tokens_refill_with_time(self):
        limiter, clock, _ = _limiter()
        limiter.check(None, _req()), limiter.check(None, _req())
        assert limiter.check(None, _req())
        clock.now += 1.0  # 60/min == 1 per second
        assert limiter.check(None, _req()) == ()

    def test_the_tenant_budget_spans_capabilities(self):
        limiter, _, _ = _limiter()
        for capability in ("a@1", "b@1", "c@1"):
            assert limiter.check(None, _req(capability=capability)) == ()
        exceeded = limiter.check(None, _req(capability="d@1"))
        assert exceeded and any("this tenant" in e for e in exceeded)

    def test_one_tenant_cannot_spend_another_tenants_budget(self):
        limiter, _, _ = _limiter()
        for _ in range(2):
            limiter.check(None, _req(tenant="t-a"))
        assert limiter.check(None, _req(tenant="t-a"))
        assert limiter.check(None, _req(tenant="t-b")) == ()

    def test_the_provider_budget_protects_the_provider_across_tenants(self):
        limiter, _, _ = _limiter(provider_burst=2, capability_burst=5, tenant_burst=5)
        assert limiter.check(None, _req(tenant="t-a")) == ()
        assert limiter.check(None, _req(tenant="t-b")) == ()
        exceeded = limiter.check(None, _req(tenant="t-c"))
        assert exceeded and any("kubernetes provider" in e for e in exceeded)

    def test_a_refusal_consumes_nothing(self):
        limiter, clock, _ = _limiter(capability_burst=1, tenant_burst=2)
        assert limiter.check(None, _req(capability="a@1")) == ()
        assert limiter.check(None, _req(capability="a@1"))  # capability empty
        # The tenant budget was NOT charged by the refused request: one left.
        assert limiter.check(None, _req(capability="b@1")) == ()

    def test_a_refusal_is_counted_by_scope(self):
        limiter, _, metrics = _limiter(capability_burst=1)
        limiter.check(None, _req())
        limiter.check(None, _req())
        assert (RATE_LIMIT_METRIC, {"scope": "capability", "provider": "kubernetes"}) in metrics.counts

    def test_the_refusal_names_the_budget_and_never_a_payload(self):
        limiter, _, _ = _limiter(capability_burst=1)
        limiter.check(None, _req())
        reason = limiter.check(None, _req())[0]
        assert "retry after" in reason and "/min" in reason


class TestPolicy:
    @pytest.mark.parametrize("bad", [0, -1, True])
    def test_a_budget_must_be_positive(self, bad):
        with pytest.raises(ContractViolation):
            RateLimitPolicy(capability_burst=bad)

    def test_a_capability_budget_above_the_tenant_budget_is_refused(self):
        with pytest.raises(ContractViolation):
            RateLimitPolicy(capability_per_minute=1000, tenant_per_minute=10)

    def test_environment_overrides_resize_and_cannot_remove(self):
        policy = RateLimitPolicy.from_env({"CORTEX_RATE_LIMIT_TENANT_PER_MINUTE": "900"})
        assert policy.tenant_per_minute == 900
        with pytest.raises(ContractViolation):
            RateLimitPolicy.from_env({"CORTEX_RATE_LIMIT_TENANT_BURST": "0"})
        with pytest.raises(ContractViolation):
            RateLimitPolicy.from_env({"CORTEX_RATE_LIMIT_TENANT_BURST": "lots"})

    def test_the_runtime_builder_always_returns_a_limiter(self):
        assert isinstance(build_rate_limiter(environ={}), TokenBucketRateLimiter)


class TestWiredIntoTheGateway:
    """The real gateway, the real limiter: the second call over budget is refused
    at the rate stage, before any credential exists, and the provider is never called."""

    def test_the_gateway_refuses_over_budget_before_a_credential(self):
        from backend.contexts.execution.domain.invocation import InvocationRefusal, InvocationRefused
        from tests.contexts.execution.test_invocation_gateway_matrix import Fixture

        fx = Fixture()
        clock = Clock()
        fx.gateway._rate_limiter = TokenBucketRateLimiter(
            RateLimitPolicy(capability_per_minute=1, capability_burst=1, tenant_per_minute=10,
                            tenant_burst=10), clock=clock)
        fx.gateway.admit(fx.context, fx.request, fx.binding)
        credentials_before = fx.credentials.acquisitions
        with pytest.raises(InvocationRefused) as refused:
            fx.gateway.admit(fx.context, fx.request, fx.binding)
        assert refused.value.refusal is InvocationRefusal.RATE_LIMITED
        assert refused.value.retryable
        assert fx.credentials.acquisitions == credentials_before

    def test_the_governed_runtime_composes_a_limiter(self):
        import inspect

        from backend.api import application_runtime

        source = inspect.getsource(application_runtime.build_governed_runtime)
        assert "rate_limiter=rate_limiter" in source and "build_rate_limiter(" in source


class TestRetryAfter:
    def _decide(self, retry_after, *, attempts_allowed=3, repeatable=True):
        from backend.contexts.execution.domain.failure import FailureClass, FailureRecord
        from backend.contexts.execution.domain.retry import RetryPolicy, decide_retry
        from backend.contracts.execution import EffectSemantics

        effect = SimpleNamespace(
            may_retry_after_ambiguity=False,
            semantics=EffectSemantics.READ_ONLY if repeatable else EffectSemantics.NON_IDEMPOTENT_WRITE)
        failure = FailureRecord(failure_class=FailureClass.TRANSIENT_FAILURE, reason="429",
                                detail={"provider_retry_after_seconds": retry_after}
                                if retry_after is not None else {})
        return decide_retry(node_id="n", attempts_spent=1, attempts_allowed=attempts_allowed,
                            effect=effect, failure=failure,
                            policy=RetryPolicy(initial_delay_seconds=1, max_delay_seconds=60))

    def test_the_providers_retry_after_is_a_floor(self):
        assert self._decide(12.2).delay_seconds == 13

    def test_it_never_exceeds_the_policy_ceiling(self):
        assert self._decide(10_000).delay_seconds == 60

    def test_it_never_creates_a_retry_the_budget_refused(self):
        decision = self._decide(5, attempts_allowed=1)
        assert decision.next_attempt is None


class TestErrorTaxonomy:
    def test_provider_failures_map_to_stable_classes(self):
        from backend.contracts.connector_errors import ConnectorErrorClass as E
        from backend.contracts.connector_errors import classify_provider_failure
        from backend.contracts.provider import ProviderFailure

        assert classify_provider_failure(ProviderFailure.AUTHENTICATION_FAILURE) is E.AUTHENTICATION_FAILED
        assert classify_provider_failure(ProviderFailure.RATE_LIMITED) is E.RATE_LIMITED
        assert classify_provider_failure(ProviderFailure.UNKNOWN_OUTCOME) is E.INTERNAL_ERROR
        for member in ProviderFailure:
            assert isinstance(classify_provider_failure(member), E)

    @pytest.mark.parametrize("status,expected", [(401, "authentication_failed"), (403, "authorization_denied"),
                                                 (404, "not_found"), (409, "conflict"), (422, "conflict"),
                                                 (429, "rate_limited"), (503, "provider_unavailable"),
                                                 (504, "timeout"), (200, None)])
    def test_statuses(self, status, expected):
        from backend.contracts.connector_errors import classify_status

        result = classify_status(status)
        assert (result.value if result else None) == expected

    @pytest.mark.parametrize("text,expected", [
        ("invocation refused at dispatch: rate_limited", "rate_limited"),
        ("authorization refused: approval_required", "authorization_denied"),
        ("target_unreadable: Unauthorized", "authentication_failed"),
        ("namespace 'x' is outside this tenant's kubernetes connection", "authorization_denied"),
        ("this tenant has no connection for kubernetes; x", "authorization_denied"),
        ("Vault could not be reached (dns)", "provider_unavailable"),
        ("something nobody anticipated", "internal_error"),
    ])
    def test_platform_refusal_text(self, text, expected):
        from backend.contracts.connector_errors import classify_failure_text

        assert classify_failure_text(text).value == expected
