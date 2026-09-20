"""Phase 11.1-K: the production Kubernetes credential path, deterministically.

A fake ``TransportBroker`` records every Vault request so the tests can prove
what was asked for (path, body, the platform token presented) and that nothing
secret escapes (repr, grant, audit reference). The real path -- a real Vault
minting real Kubernetes tokens against a real API server -- is proven by the
live harness.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.contracts.credential import CredentialState, CredentialType
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionEnvironment
from backend.platform.credentials.request import CredentialRefusal, CredentialRefused
from backend.platform.transport.broker import TransportBroker
from backend.platform.transport.endpoint import TransportEndpoint, TransportKind
from backend.platform.transport.policy import ConnectionPolicy
from backend.platform.transport.request import DeliveryState

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
SA_TOKEN = "eyJhbGciOiJSUzI1NiJ9.FAKE-KUBERNETES-SERVICEACCOUNT-TOKEN.sig"


class Broker(TransportBroker):
    """Records requests; answers from a script keyed by path suffix."""

    def __init__(self, answers):
        self.answers = answers
        self.requests = []

    def dial(self, request):
        self.requests.append(request)
        for suffix, (status, document) in self.answers.items():
            if request.endpoint.path.endswith(suffix):
                body = json.dumps(document).encode() if document is not None else b""
                return SimpleNamespace(delivery=DeliveryState.DELIVERED, status_code=status,
                                       body=body, truncated=False)
        raise AssertionError(f"unexpected Vault path {request.endpoint.path}")


def _endpoint():
    return TransportEndpoint.parse("https://vault.vault.svc:8200", transport=TransportKind.HTTPS,
                                   environment=ExecutionEnvironment.PRODUCTION)


def _policy():
    return ConnectionPolicy(environment=ExecutionEnvironment.PRODUCTION)


def _platform_token():
    from backend.contracts.credential import CredentialRef
    from backend.platform.credentials.material import CredentialMaterial

    return CredentialMaterial(secret="hvs.PLATFORM-VAULT-TOKEN", ref=CredentialRef(
        tenant_id="cortexprime-platform", credential_id="vault-bootstrap"),
        credential_type=CredentialType.BEARER, expires_at=NOW + timedelta(days=1),
        acquired_at=NOW, headers=("Authorization",))


def _adapter(broker, **kwargs):
    from backend.platform.credentials.vault_kubernetes import VaultKubernetesCredentialAdapter

    return VaultKubernetesCredentialAdapter(
        provider_id="kubernetes", environments=frozenset({ExecutionEnvironment.PRODUCTION}),
        broker=broker, endpoint=_endpoint(), policy=_policy(), vault_token=_platform_token(),
        bindings={"tenant-a": ("ns-a", "cortexprime-reader")}, clock=lambda: NOW, **kwargs)


def _scope():
    from backend.contracts.credential import CredentialScope

    return CredentialScope(tokens=frozenset({"kubernetes:pods:list"}))


def _request(tenant="tenant-a", provider="kubernetes", environment=ExecutionEnvironment.PRODUCTION):
    return SimpleNamespace(
        tenant_id=tenant, provider=provider, environment=environment, on_behalf_of=None,
        delegation_authorized=False, correlation_id="corr-1", scope=_scope(),
        action_digest="a" * 64, binding_digest="b" * 64,
        effective_expiry=lambda now: NOW + timedelta(minutes=5), execution_id="e", node_id="n",
        attempt_id="at")


GOOD = {"/v1/kubernetes/creds/cortexprime-reader": (200, {
    "lease_duration": 600, "data": {"service_account_token": SA_TOKEN,
                                    "service_account_name": "cortexprime-reader"}})}


class TestIssuance:
    def test_a_fresh_token_per_acquisition_for_the_tenants_namespace_and_role(self):
        broker = Broker(GOOD)
        issued = _adapter(broker).acquire(_request(), expires_at=NOW + timedelta(minutes=5))
        (request,) = broker.requests
        assert request.method == "POST"
        assert request.endpoint.path == "/v1/kubernetes/creds/cortexprime-reader"
        assert json.loads(request.body) == {"kubernetes_namespace": "ns-a", "ttl": "600s"}
        assert request.credential.reveal(purpose="test") == "hvs.PLATFORM-VAULT-TOKEN"
        assert issued.material.reveal(purpose="test") == SA_TOKEN
        assert issued.material.credential_type is CredentialType.BEARER
        assert issued.grant.state is CredentialState.ACTIVE
        assert issued.grant.provider_reference == "vault-kubernetes:kubernetes"

    def test_the_credential_never_outlives_the_authority(self):
        issued = _adapter(Broker(GOOD)).acquire(_request(), expires_at=NOW + timedelta(seconds=90))
        assert issued.grant.expires_at == NOW + timedelta(seconds=90)

    def test_each_acquisition_asks_vault_again(self):
        broker = Broker(GOOD)
        adapter = _adapter(broker)
        adapter.acquire(_request(), expires_at=NOW + timedelta(minutes=5))
        adapter.acquire(_request(), expires_at=NOW + timedelta(minutes=5))
        assert len(broker.requests) == 2

    def test_nothing_secret_is_in_the_repr_or_the_grant(self):
        adapter = _adapter(Broker(GOOD))
        issued = adapter.acquire(_request(), expires_at=NOW + timedelta(minutes=5))
        assert SA_TOKEN not in repr(adapter) and "hvs." not in repr(adapter)
        assert SA_TOKEN not in repr(issued.grant)


class TestRefusals:
    def test_a_tenant_without_a_binding_gets_nothing_and_vault_is_not_asked(self):
        broker = Broker(GOOD)
        with pytest.raises(CredentialRefused) as refused:
            _adapter(broker).acquire(_request(tenant="tenant-b"), expires_at=NOW + timedelta(minutes=5))
        assert refused.value.refusal is CredentialRefusal.NO_PROVIDER
        assert broker.requests == []

    @pytest.mark.parametrize("status,refusal", [
        (403, CredentialRefusal.PROVIDER_REFUSED), (401, CredentialRefusal.PROVIDER_REFUSED),
        (404, CredentialRefusal.NO_PROVIDER), (400, CredentialRefusal.NO_PROVIDER),
        (500, CredentialRefusal.PROVIDER_MALFORMED)])
    def test_vault_answers_map_to_explicit_refusals(self, status, refusal):
        broker = Broker({"/v1/kubernetes/creds/cortexprime-reader": (status, {"errors": ["x"]})})
        with pytest.raises(CredentialRefused) as refused:
            _adapter(broker).acquire(_request(), expires_at=NOW + timedelta(minutes=5))
        assert refused.value.refusal is refusal

    def test_a_200_without_a_token_is_malformed_not_empty_success(self):
        broker = Broker({"/v1/kubernetes/creds/cortexprime-reader": (200, {"data": {}})})
        with pytest.raises(CredentialRefused) as refused:
            _adapter(broker).acquire(_request(), expires_at=NOW + timedelta(minutes=5))
        assert refused.value.refusal is CredentialRefusal.PROVIDER_MALFORMED

    def test_another_provider_or_environment_is_refused(self):
        adapter = _adapter(Broker(GOOD))
        with pytest.raises(CredentialRefused):
            adapter.acquire(_request(provider="github"), expires_at=NOW + timedelta(minutes=5))
        with pytest.raises(CredentialRefused):
            adapter.acquire(_request(environment=ExecutionEnvironment.DEVELOPMENT),
                            expires_at=NOW + timedelta(minutes=5))

    def test_a_closed_authority_window_is_refused_before_vault(self):
        broker = Broker(GOOD)
        with pytest.raises(CredentialRefused):
            _adapter(broker).acquire(_request(), expires_at=NOW - timedelta(seconds=1))
        assert broker.requests == []

    def test_no_bindings_does_not_construct(self):
        from backend.platform.credentials.vault_kubernetes import VaultKubernetesCredentialAdapter

        with pytest.raises(ContractViolation):
            VaultKubernetesCredentialAdapter(
                provider_id="kubernetes", environments=frozenset({ExecutionEnvironment.PRODUCTION}),
                broker=Broker(GOOD), endpoint=_endpoint(), policy=_policy(),
                vault_token=_platform_token(), bindings={})

    def test_a_path_traversal_role_or_namespace_does_not_construct(self):
        from backend.platform.credentials.vault_kubernetes import VaultKubernetesCredentialAdapter

        for bindings in ({"tenant-a": ("ns-a", "../sys/raw")}, {"tenant-a": ("ns/../b", "r")}):
            with pytest.raises(ContractViolation):
                VaultKubernetesCredentialAdapter(
                    provider_id="kubernetes", environments=frozenset({ExecutionEnvironment.PRODUCTION}),
                    broker=Broker(GOOD), endpoint=_endpoint(), policy=_policy(),
                    vault_token=_platform_token(), bindings=bindings)


class TestVaultKubernetesAuth:
    def _auth(self, tmp_path, broker, clock):
        from backend.platform.credentials.vault_kubernetes import VaultKubernetesAuth

        jwt = tmp_path / "token"
        jwt.write_text("projected-pod-jwt", encoding="utf-8")
        return VaultKubernetesAuth(broker=broker, endpoint=_endpoint(), policy=_policy(),
                                   role="cortexprime", jwt_path=str(jwt), clock=clock), jwt

    def test_it_logs_in_with_the_projected_token_and_caches_until_renewal(self, tmp_path):
        broker = Broker({"/v1/auth/kubernetes/login": (200, {"auth": {"client_token": "hvs.LOGIN",
                                                                         "lease_duration": 100}})})
        now = [NOW]
        auth, _ = self._auth(tmp_path, broker, lambda: now[0])
        first = auth.material()
        assert json.loads(broker.requests[0].body) == {"role": "cortexprime", "jwt": "projected-pod-jwt"}
        assert broker.requests[0].credential is None
        assert auth.material() is first and len(broker.requests) == 1
        now[0] = NOW + timedelta(seconds=61)  # past 60% of the lease
        auth.material()
        assert len(broker.requests) == 2

    def test_the_jwt_is_read_again_on_every_login_because_the_kubelet_rotates_it(self, tmp_path):
        broker = Broker({"/v1/auth/kubernetes/login": (200, {"auth": {"client_token": "t",
                                                                         "lease_duration": 10}})})
        now = [NOW]
        auth, jwt = self._auth(tmp_path, broker, lambda: now[0])
        auth.material()
        jwt.write_text("rotated-jwt", encoding="utf-8")
        now[0] = NOW + timedelta(seconds=30)
        auth.material()
        assert json.loads(broker.requests[1].body)["jwt"] == "rotated-jwt"

    def test_a_refused_login_is_a_refusal(self, tmp_path):
        broker = Broker({"/v1/auth/kubernetes/login": (403, {"errors": ["permission denied"]})})
        auth, _ = self._auth(tmp_path, broker, lambda: NOW)
        with pytest.raises(CredentialRefused) as refused:
            auth.material()
        assert refused.value.refusal is CredentialRefusal.PROVIDER_REFUSED

    def test_no_projected_token_is_a_refusal(self, tmp_path):
        from backend.platform.credentials.vault_kubernetes import VaultKubernetesAuth

        auth = VaultKubernetesAuth(broker=Broker({}), endpoint=_endpoint(), policy=_policy(),
                                   role="cortexprime", jwt_path=str(tmp_path / "absent"))
        with pytest.raises(CredentialRefused) as refused:
            auth.material()
        assert refused.value.refusal is CredentialRefusal.NO_PROVIDER

    def test_the_adapter_presents_the_login_token_to_vault(self, tmp_path):
        broker = Broker({"/v1/auth/kubernetes/login": (200, {"auth": {"client_token": "hvs.LOGIN",
                                                                         "lease_duration": 100}}),
                         **GOOD})
        auth, _ = self._auth(tmp_path, broker, lambda: NOW)
        from backend.platform.credentials.vault_kubernetes import VaultKubernetesCredentialAdapter

        adapter = VaultKubernetesCredentialAdapter(
            provider_id="kubernetes", environments=frozenset({ExecutionEnvironment.PRODUCTION}),
            broker=broker, endpoint=_endpoint(), policy=_policy(), vault_token=auth,
            bindings={"tenant-a": ("ns-a", "cortexprime-reader")}, clock=lambda: NOW)
        adapter.acquire(_request(), expires_at=NOW + timedelta(minutes=5))
        creds_call = broker.requests[-1]
        assert creds_call.credential.reveal(purpose="test") == "hvs.LOGIN"


class TestPinnedPolicy:
    def test_an_in_cluster_endpoint_is_pinned_to_its_exact_address(self):
        from backend.api.kubernetes_connector import _pinned

        policy = _pinned(ConnectionPolicy(environment=ExecutionEnvironment.PRODUCTION),
                         "https://10.43.0.1:443")
        assert policy.allowed_private_addresses == frozenset({"10.43.0.1"})

    def test_the_exact_address_allowance_admits_nothing_wider(self):
        import socket

        from backend.platform.transport.ssrf import AddressClass, AddressJudgement

        policy = ConnectionPolicy(environment=ExecutionEnvironment.PRODUCTION,
                                  allowed_private_addresses=frozenset({"10.43.0.1"}))
        judge = lambda a, c: policy.judge_address(AddressJudgement(address=a, address_class=c,
                                                                   family=socket.AF_INET))
        assert judge("10.43.0.1", AddressClass.PRIVATE) is None
        assert judge("10.43.0.2", AddressClass.PRIVATE) is not None
        assert judge("169.254.169.254", AddressClass.LINK_LOCAL) is not None

    @pytest.mark.parametrize("bad", ["127.0.0.1", "169.254.169.254", "8.8.8.8", "10.0.0.0/8", "fe80::1"])
    def test_only_private_literals_can_be_allowed(self, bad):
        with pytest.raises(ContractViolation):
            ConnectionPolicy(environment=ExecutionEnvironment.PRODUCTION,
                             allowed_private_addresses=frozenset({bad}))


class SequenceBroker(Broker):
    """Answers each path suffix from a queue, in order (the last answer repeats)."""

    def dial(self, request):
        self.requests.append(request)
        for suffix, answers in self.answers.items():
            if request.endpoint.path.endswith(suffix):
                status, document = answers.pop(0) if len(answers) > 1 else answers[0]
                body = json.dumps(document).encode() if document is not None else b""
                return SimpleNamespace(delivery=DeliveryState.DELIVERED, status_code=status,
                                       body=body, truncated=False)
        raise AssertionError(f"unexpected Vault path {request.endpoint.path}")


class TestStaleVaultLogin:
    """Phase 11.1-K: Vault restarted under a running runtime. The cached login
    was dead and every acquisition failed for its remaining lifetime (~36 min)
    although one fresh login would have worked."""

    def _adapter(self, tmp_path, answers):
        from backend.platform.credentials.vault_kubernetes import (
            VaultKubernetesAuth, VaultKubernetesCredentialAdapter)

        jwt = tmp_path / "token"
        jwt.write_text("projected-pod-jwt", encoding="utf-8")
        broker = SequenceBroker(answers)
        auth = VaultKubernetesAuth(broker=broker, endpoint=_endpoint(), policy=_policy(), role="cortexprime",
                                   jwt_path=str(jwt), clock=lambda: NOW)
        adapter = VaultKubernetesCredentialAdapter(
            provider_id="kubernetes", environments=frozenset({ExecutionEnvironment.PRODUCTION}),
            broker=broker, endpoint=_endpoint(), policy=_policy(), vault_token=auth,
            bindings={"tenant-a": ("ns-a", "cortexprime-reader")}, clock=lambda: NOW)
        return adapter, broker

    def _logins(self, broker):
        return [r for r in broker.requests if r.endpoint.path.endswith("/login")]

    def test_a_dead_login_is_replaced_once_and_the_acquisition_succeeds(self, tmp_path):
        adapter, broker = self._adapter(tmp_path, {
            "/v1/auth/kubernetes/login": [(200, {"auth": {"client_token": "hvs.OLD", "lease_duration": 3600}}),
                                          (200, {"auth": {"client_token": "hvs.NEW", "lease_duration": 3600}})],
            "/v1/kubernetes/creds/cortexprime-reader": [(403, {"errors": ["permission denied"]}),
                                                       GOOD["/v1/kubernetes/creds/cortexprime-reader"]]})
        issued = adapter.acquire(_request(), expires_at=NOW + timedelta(minutes=5))
        assert issued.grant.provider_reference == "vault-kubernetes:kubernetes"
        mints = [r for r in broker.requests if "/creds/" in r.endpoint.path]
        assert len(self._logins(broker)) == 2 and len(mints) == 2
        assert mints[0].credential.fingerprint() != mints[1].credential.fingerprint()   # the NEW login was used

    def test_restart_recovers_without_waiting_for_the_cached_lease(self, tmp_path):
        adapter, broker = self._adapter(tmp_path, {
            "/v1/auth/kubernetes/login": [(200, {"auth": {"client_token": "hvs.OLD", "lease_duration": 3600}}),
                                          (200, {"auth": {"client_token": "hvs.NEW", "lease_duration": 3600}})],
            "/v1/kubernetes/creds/cortexprime-reader": [GOOD["/v1/kubernetes/creds/cortexprime-reader"],
                                                       (403, {"errors": ["permission denied"]}),
                                                       GOOD["/v1/kubernetes/creds/cortexprime-reader"]]})
        adapter.acquire(_request(), expires_at=NOW + timedelta(minutes=5))      # healthy: login OLD, mint
        issued = adapter.acquire(_request(), expires_at=NOW + timedelta(minutes=5))  # Vault restarted
        assert issued.grant.provider_reference == "vault-kubernetes:kubernetes"
        assert len(self._logins(broker)) == 2                                   # exactly one fresh login
        mints = [r for r in broker.requests if "/creds/" in r.endpoint.path]
        assert len(mints) == 3                                                  # one retry, no more

    def test_a_refused_role_still_refuses_after_one_fresh_login(self, tmp_path):
        adapter, broker = self._adapter(tmp_path, {
            "/v1/auth/kubernetes/login": [(200, {"auth": {"client_token": "hvs.A", "lease_duration": 3600}}),
                                          (200, {"auth": {"client_token": "hvs.B", "lease_duration": 3600}})],
            "/v1/kubernetes/creds/cortexprime-reader": [(403, {"errors": ["permission denied"]})]})
        with pytest.raises(CredentialRefused) as refused:
            adapter.acquire(_request(), expires_at=NOW + timedelta(minutes=5))
        assert refused.value.refusal is CredentialRefusal.PROVIDER_REFUSED
        assert len(self._logins(broker)) == 2
        assert len([r for r in broker.requests if "/creds/" in r.endpoint.path]) == 2
