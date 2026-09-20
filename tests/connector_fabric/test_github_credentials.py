"""Phase 11.2: the GitHub credential path, and the V1 GitHub write gate.

The App path is deterministic here (a real RSA key, a scripted GitHub); the
live proof of a *governed* GitHub write is the harness. The V1 tests re-prove
audit finding S-1 for GitHub specifically: the old plane cannot write.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.contracts.execution import ExecutionEnvironment
from backend.platform.credentials.request import CredentialRefusal, CredentialRefused
from backend.platform.transport.endpoint import TransportEndpoint, TransportKind
from backend.platform.transport.policy import ConnectionPolicy
from backend.platform.transport.request import DeliveryState

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def private_key() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(serialization.Encoding.PEM,
                             serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()


from backend.platform.transport.broker import TransportBroker


class Broker(TransportBroker):
    """Records requests; answers from a script keyed by path suffix, in order.

    A real ``TransportBroker`` subclass because the Vault adapter refuses
    anything else: the credential route may not acquire a second outbound path.
    """

    def __init__(self, answers):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.requests = []

    def dial(self, request):
        self.requests.append(request)
        for suffix, queue in self.answers.items():
            if request.endpoint.path.endswith(suffix):
                status, document = queue.pop(0) if len(queue) > 1 else queue[0]
                body = json.dumps(document).encode() if document is not None else b""
                return SimpleNamespace(delivery=DeliveryState.DELIVERED, status_code=status,
                                       body=body, truncated=False)
        raise AssertionError(f"unexpected path {request.endpoint.path}")


def _endpoint(url="https://api.github.com"):
    return TransportEndpoint.parse(url, transport=TransportKind.HTTPS,
                                   environment=ExecutionEnvironment.PRODUCTION)


def _policy():
    return ConnectionPolicy(environment=ExecutionEnvironment.PRODUCTION)


TOKEN_PATH = "/app/installations/42/access_tokens"
GOOD_TOKEN = {"token": "ghs_INSTALLATION_TOKEN", "expires_at": "2026-09-20T13:00:00Z",
              "repository_selection": "selected"}


def _source(broker, private_key, **kwargs):
    from backend.api.github_credentials import GitHubAppIdentity, GitHubAppTokenSource

    identity = GitHubAppIdentity(app_id="424242", private_key_pem=private_key)
    kwargs.setdefault("repositories", ("chandu0580/CortexPrime",))
    kwargs.setdefault("permissions", {"metadata": "read", "issues": "write"})
    return GitHubAppTokenSource(broker=broker, endpoint=_endpoint(), policy=_policy(),
                               identity=identity, installation_id="42",
                               clock=lambda: NOW, **kwargs)


class TestAppAssertion:
    def test_the_jwt_is_rs256_backdated_and_under_ten_minutes(self, private_key):
        import jwt

        from backend.api.github_credentials import GitHubAppIdentity

        assertion = GitHubAppIdentity(app_id="424242", private_key_pem=private_key).assertion(now=NOW)
        claims = jwt.decode(assertion, options={"verify_signature": False})
        assert jwt.get_unverified_header(assertion)["alg"] == "RS256"
        assert claims["iss"] == "424242"
        assert claims["iat"] == int(NOW.timestamp()) - 60          # clock drift, per GitHub
        assert 0 < claims["exp"] - claims["iat"] <= 600            # GitHub's hard limit

    def test_a_key_that_is_not_a_key_is_refused(self):
        from backend.contracts.errors import ContractViolation
        from backend.api.github_credentials import GitHubAppIdentity

        with pytest.raises(ContractViolation):
            GitHubAppIdentity(app_id="1", private_key_pem="hunter2")

    def test_the_identity_never_reprs_its_key(self, private_key):
        from backend.api.github_credentials import GitHubAppIdentity

        identity = GitHubAppIdentity(app_id="424242", private_key_pem=private_key)
        assert "PRIVATE KEY" not in repr(identity) and "PRIVATE KEY" not in str(identity)


class TestInstallationToken:
    def test_the_token_is_minted_for_the_connected_repositories_only(self, private_key):
        broker = Broker({TOKEN_PATH: [(201, GOOD_TOKEN)]})
        token, expires = _source(broker, private_key).token()
        (request,) = broker.requests
        body = json.loads(request.body)
        assert body["repositories"] == ["CortexPrime"]        # names, scoped by installation owner
        assert body["permissions"] == {"metadata": "read", "issues": "write"}
        assert token == "ghs_INSTALLATION_TOKEN"
        assert expires == datetime(2026, 9, 20, 13, 0, tzinfo=timezone.utc)

    def test_the_assertion_is_presented_as_the_credential_never_in_the_body(self, private_key):
        broker = Broker({TOKEN_PATH: [(201, GOOD_TOKEN)]})
        _source(broker, private_key).token()
        (request,) = broker.requests
        assert request.credential is not None                 # the transport applies it
        assert "jwt" not in (request.body or b"").decode().lower()

    def test_a_cached_token_is_reused_until_it_is_due_for_renewal(self, private_key):
        broker = Broker({TOKEN_PATH: [(201, GOOD_TOKEN)]})
        source = _source(broker, private_key)
        first, _ = source.token()
        again, _ = source.token()
        assert first == again and len(broker.requests) == 1

    def test_a_refused_token_invalidates_the_cache_so_a_fresh_one_can_be_minted(self, private_key):
        broker = Broker({TOKEN_PATH: [(201, GOOD_TOKEN), (201, dict(GOOD_TOKEN, token="ghs_SECOND"))]})
        source = _source(broker, private_key)
        source.token()
        assert source.invalidate("ghs_INSTALLATION_TOKEN") is True
        assert source.invalidate("ghs_INSTALLATION_TOKEN") is False   # already gone
        second, _ = source.token()
        assert second == "ghs_SECOND" and len(broker.requests) == 2

    @pytest.mark.parametrize("status,refusal", [
        (401, CredentialRefusal.PROVIDER_REFUSED),
        (403, CredentialRefusal.PROVIDER_REFUSED),
        (404, CredentialRefusal.NO_PROVIDER),
        (422, CredentialRefusal.PROVIDER_REFUSED),
        (500, CredentialRefusal.PROVIDER_MALFORMED),
    ])
    def test_github_refusals_are_classified_not_swallowed(self, private_key, status, refusal):
        broker = Broker({TOKEN_PATH: [(status, {"message": "no"})]})
        with pytest.raises(CredentialRefused) as refused:
            _source(broker, private_key).token()
        assert refused.value.refusal is refusal

    def test_the_source_never_reprs_the_token(self, private_key):
        broker = Broker({TOKEN_PATH: [(201, GOOD_TOKEN)]})
        source = _source(broker, private_key)
        source.token()
        assert "ghs_" not in repr(source) and "ghs_" not in str(source)


class TestAppCredentialAdapter:
    def _adapter(self, broker, private_key, tenant="tenant-a"):
        from backend.api.github_credentials import GitHubAppCredentialAdapter

        return GitHubAppCredentialAdapter(
            provider_id="github", environments=frozenset({ExecutionEnvironment.PRODUCTION}),
            bindings={tenant: _source(broker, private_key)}, clock=lambda: NOW)

    def _request(self, tenant="tenant-a", provider="github",
                 environment=ExecutionEnvironment.PRODUCTION):
        from backend.contracts.credential import CredentialScope

        return SimpleNamespace(
            tenant_id=tenant, provider=provider, environment=environment, on_behalf_of=None,
            delegation_authorized=False, correlation_id="corr-1",
            scope=CredentialScope(tokens=frozenset({"github:issues:write"})),
            action_digest="a" * 64, binding_digest="b" * 64,
            effective_expiry=lambda now: NOW + timedelta(minutes=5),
            execution_id="e", node_id="n", attempt_id="at")

    def test_it_issues_a_bearer_credential_for_a_bound_tenant(self, private_key):
        broker = Broker({TOKEN_PATH: [(201, GOOD_TOKEN)]})
        issued = self._adapter(broker, private_key).acquire(
            self._request(), expires_at=NOW + timedelta(minutes=5))
        assert issued.grant.provider_reference == "github-app-installation"
        assert issued.grant.tenant_id == "tenant-a"

    def test_a_tenant_without_a_binding_gets_nothing(self, private_key):
        broker = Broker({TOKEN_PATH: [(201, GOOD_TOKEN)]})
        with pytest.raises(CredentialRefused) as refused:
            self._adapter(broker, private_key).acquire(
                self._request(tenant="tenant-b"), expires_at=NOW + timedelta(minutes=5))
        assert refused.value.refusal is CredentialRefusal.NO_PROVIDER
        assert not broker.requests          # refused before GitHub was contacted

    def test_the_credential_never_outlives_the_authority_window(self, private_key):
        broker = Broker({TOKEN_PATH: [(201, GOOD_TOKEN)]})   # token lives an hour
        issued = self._adapter(broker, private_key).acquire(
            self._request(), expires_at=NOW + timedelta(minutes=5))
        assert issued.grant.expires_at == NOW + timedelta(minutes=5)

    def test_a_wrong_environment_or_provider_is_refused(self, private_key):
        broker = Broker({TOKEN_PATH: [(201, GOOD_TOKEN)]})
        adapter = self._adapter(broker, private_key)
        for request, refusal in (
                (self._request(environment=ExecutionEnvironment.DEVELOPMENT),
                 CredentialRefusal.ENVIRONMENT_MISMATCH),
                (self._request(provider="gitlab"), CredentialRefusal.NO_PROVIDER)):
            with pytest.raises(CredentialRefused) as refused:
                adapter.acquire(request, expires_at=NOW + timedelta(minutes=5))
            assert refused.value.refusal is refusal


class TestProductionRefusesAStoredToken:
    def test_a_personal_access_token_is_not_a_production_credential(self, monkeypatch):
        from backend.api.github_connector import github_connector_extension
        from backend.contracts.errors import ContractViolation

        monkeypatch.setenv("CORTEX_GITHUB_TENANT", "tenant-a")
        monkeypatch.setenv("CORTEX_GITHUB_REPOSITORIES", "chandu0580/CortexPrime")
        monkeypatch.setenv("CORTEX_GITHUB_CREDENTIALS", "vault-token")
        with pytest.raises(ContractViolation) as refused:
            github_connector_extension(ExecutionEnvironment.PRODUCTION)
        assert "GitHub App" in str(refused.value)

    def test_the_same_connection_composes_outside_production(self, monkeypatch):
        from backend.api.github_connector import github_connector_extension

        monkeypatch.setenv("CORTEX_GITHUB_TENANT", "tenant-a")
        monkeypatch.setenv("CORTEX_GITHUB_REPOSITORIES", "chandu0580/CortexPrime")
        monkeypatch.setenv("CORTEX_GITHUB_CREDENTIALS", "vault-token")
        produced = github_connector_extension(ExecutionEnvironment.DEVELOPMENT)
        assert produced is not None and produced["manifests"]
        (scope,) = produced["connection_scopes"]
        assert scope.target_parameters == ("owner", "repo")

    def test_no_connection_configured_means_no_connector(self, monkeypatch):
        from backend.api.github_connector import github_connector_extension

        monkeypatch.delenv("CORTEX_GITHUB_TENANT", raising=False)
        monkeypatch.delenv("CORTEX_GITHUB_REPOSITORIES", raising=False)
        assert github_connector_extension(ExecutionEnvironment.PRODUCTION) is None


class TestTheV1GitHubPlaneCannotWrite:
    """Audit S-1, re-proven for GitHub: every V1 write is refused by default."""

    @pytest.mark.parametrize("operation", [
        "create_issue", "update_issue", "create_issue_comment", "dispatch_workflow",
        "cancel_workflow_run", "rerun_workflow", "create_branch", "create_pull_request",
        "merge_pull_request",
    ])
    def test_a_v1_write_operation_is_refused_without_the_legacy_flag(self, monkeypatch, operation):
        from backend.api.legacy_execution_boundary import LegacyExecutionRefused
        from backend.connectors.effects import assert_effect_permitted

        monkeypatch.delenv("CORTEXPRIME_ENABLE_LEGACY_EXECUTION", raising=False)
        with pytest.raises(LegacyExecutionRefused):
            assert_effect_permitted("github", operation)

    @pytest.mark.parametrize("verb", ["POST", "PATCH", "PUT", "DELETE"])
    def test_a_raw_state_changing_request_is_refused_outside_an_admitted_operation(
            self, monkeypatch, verb):
        from backend.api.legacy_execution_boundary import LegacyExecutionRefused
        from backend.connectors.effects import guard_raw_request

        monkeypatch.delenv("CORTEXPRIME_ENABLE_LEGACY_EXECUTION", raising=False)
        with pytest.raises(LegacyExecutionRefused):
            guard_raw_request("github", verb)

    def test_a_v1_read_is_not_gated(self, monkeypatch):
        from backend.connectors.effects import assert_effect_permitted, guard_raw_request

        monkeypatch.delenv("CORTEXPRIME_ENABLE_LEGACY_EXECUTION", raising=False)
        assert_effect_permitted("github", "get_repository")
        guard_raw_request("github", "GET")


class TestStaleVaultLoginOnTheKvPath:
    """Phase 11.2: the same lesson as 11.1-K F-9, on the credential path the
    GitHub token is read through. A policy added (or Vault restarted) after this
    process logged in made every acquisition fail until the cached login expired
    -- found live, by adding the GitHub policy to a running runtime."""

    def _adapter(self, broker, token_source):
        from backend.platform.credentials.vault import VaultCredentialAdapter

        return VaultCredentialAdapter(
            provider_id="github", environments=frozenset({ExecutionEnvironment.PRODUCTION}),
            broker=broker, endpoint=_endpoint("https://vault.vault.svc:8200"), policy=_policy(),
            vault_token=token_source, mount="secret", path_prefix="cortexprime/providers",
            secret_key="token", clock=lambda: NOW)

    def _request(self):
        from backend.contracts.credential import CredentialScope

        return SimpleNamespace(
            tenant_id="tenant-a", provider="github",
            environment=ExecutionEnvironment.PRODUCTION, on_behalf_of=None,
            delegation_authorized=False, correlation_id="c-1",
            scope=CredentialScope(tokens=frozenset({"github:issues:write"})),
            action_digest="a" * 64, binding_digest="b" * 64,
            effective_expiry=lambda now: NOW + timedelta(minutes=5),
            execution_id="e", node_id="n", attempt_id="at")

    class _Source:
        """A login that is refused once, then works -- as a stale one behaves."""

        def __init__(self):
            self.logins = 0
            self.invalidated = 0

        def material(self, *, correlation_id=None):
            from backend.contracts.credential import CredentialRef, CredentialType
            from backend.platform.credentials.material import CredentialMaterial

            self.logins += 1
            return CredentialMaterial(
                secret=f"hvs.LOGIN{self.logins}",
                ref=CredentialRef(tenant_id="cortexprime-platform", credential_id="vault"),
                credential_type=CredentialType.BEARER, expires_at=NOW + timedelta(hours=1),
                acquired_at=NOW, headers=("Authorization",))

        def invalidate(self, stale=None):
            self.invalidated += 1
            return True

    def test_a_refused_token_is_replaced_once_and_the_read_succeeds(self):
        secret_path = "/v1/secret/data/cortexprime/providers/tenant-a/production/github"
        broker = Broker({secret_path: [(403, {"errors": ["permission denied"]}),
                                       (200, {"data": {"data": {"token": "ghp_TOKEN"}}})]})
        source = self._Source()
        issued = self._adapter(broker, source).acquire(
            self._request(), expires_at=NOW + timedelta(minutes=5))
        assert issued.grant.tenant_id == "tenant-a"
        assert source.invalidated == 1 and source.logins == 2
        assert len(broker.requests) == 2

    def test_a_genuinely_forbidden_path_still_refuses_after_one_retry(self):
        secret_path = "/v1/secret/data/cortexprime/providers/tenant-a/production/github"
        broker = Broker({secret_path: [(403, {"errors": ["permission denied"]})]})
        source = self._Source()
        with pytest.raises(CredentialRefused) as refused:
            self._adapter(broker, source).acquire(
                self._request(), expires_at=NOW + timedelta(minutes=5))
        assert refused.value.refusal is CredentialRefusal.PROVIDER_REFUSED
        assert source.invalidated == 1 and len(broker.requests) == 2
