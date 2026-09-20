"""The GitHub connector: manifest, connection and health (Phase 11.2, ADR-126).

Connector #2, and the proof that the architecture Kubernetes established
(ADR-125) carries to a software-development provider without being redesigned.
The shape is deliberately the same file-for-file: one manifest declaring every
capability, one explicit connection binding a CortexPrime tenant to provider
targets, the provider permissions each capability needs, and a health probe that
answers through the governed path rather than beside it.

Capabilities (and why only these)
-----------------------------------
READ (provider ``github``, in-process, read-only): the reads an incident
investigation actually discriminates on -- what changed (``list_commits``,
``get_commit``), what shipped (``list_deployments``), what ran and how it ended
(``list_workflow_runs``, ``get_workflow_run``), what was proposed and merged
(``list_pull_requests``, ``get_pull_request``), plus the repository itself and
one issue read that makes a comment verifiable.

WRITE (provider ``github-contained``, its own worker, its own binding): one --
``create_issue_comment``. It is the safest high-value write GitHub offers: it
adds a message to a thread somebody already opened, it is visible, it is
attributable, and it can be read back exactly. ``create_issue`` is declared in
the catalog and is deliberately **not shipped** as a capability in this phase:
opening issues is a second blast radius (new records, new notifications, no
delete) and nothing in the current use case needs it.

Tenancy (the relationship, stated)
------------------------------------
A GitHub organization is NOT a CortexPrime tenant, and an installation is not
one either. A **connection** binds one tenant to named repositories:

    CortexPrime tenant --connection--> GitHub installation --> repositories

Enforced three times, independently: the gateway's input stage refuses a target
outside the tenant's connection (``backend.api.connector_scope``, composite
``owner``/``repo``); the credential is an installation token minted for exactly
those repositories; and the write worker holds its own compiled repository
binding. Any one of the three refuses a cross-repository call on its own.

Untrusted content
-------------------
Everything this connector returns -- a commit message, a pull-request title, an
issue body -- is text somebody else wrote, and some of it is text an attacker
chose. It is evidence, never instruction: it is bounded and truncated by the
operation's declared evidence, it never becomes a capability argument by itself,
and no capability here can be reached by anything a repository contains.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

from backend.contracts.connector_manifest import CapabilityManifest, ConnectorManifest
from backend.contracts.errors import ContractViolation

log = logging.getLogger(__name__)

__all__ = [
    "GITHUB_CONNECTOR_ID",
    "GITHUB_API_BASE",
    "GitHubConnection",
    "github_manifest",
    "github_connector_extension",
    "github_health_probe",
    "SHIPPED_READS",
    "SHIPPED_WRITES",
]

GITHUB_CONNECTOR_ID = "github"
GITHUB_API_BASE = "https://api.github.com"

SHIPPED_READS: Tuple[str, ...] = (
    "repository.get_repository",
    "repository.list_commits",
    "repository.get_commit",
    "repository.list_pull_requests",
    "repository.get_pull_request",
    "repository.list_workflow_runs",
    "repository.get_workflow_run",
    "repository.list_deployments",
    "repository.get_issue",
)
SHIPPED_WRITES: Tuple[str, ...] = ("repository.create_issue_comment",)

#: Which provider (worker boundary) serves each capability.
_PROVIDER = {"repository.create_issue_comment": "github-contained"}

_CATEGORY = {
    "repository.get_repository": "observation",
    "repository.get_issue": "observation",
    "repository.create_issue_comment": "remediation",
}

#: Written for the two readers that matter: an operator scanning a list, and a
#: model deciding which capability answers the question in front of it. Each one
#: says what it returns and when to reach for it.
_DESCRIPTIONS = {
    "repository.get_repository": (
        "Read one repository's identity: full name, default branch, visibility and when it was "
        "last pushed. Use to confirm which repository an incident is about before reading its history."),
    "repository.list_commits": (
        "List recent commits on a branch or path, newest first, each with its sha, author, "
        "timestamp and subject line. Use to answer 'what changed, when and by whom' in a window "
        "around an incident; narrow it with since/until or a path."),
    "repository.get_commit": (
        "Read one commit in detail: author, timestamps, subject, how many files changed, lines "
        "added and removed, and the files themselves. Use once a commit is suspected, to see "
        "whether it touched the failing component."),
    "repository.list_pull_requests": (
        "List pull requests with their number, title, state, author, base and head branch and "
        "merge time. Use to find the change that introduced or fixed a behaviour, or what is "
        "waiting to merge into the branch that broke."),
    "repository.get_pull_request": (
        "Read one pull request: state, whether it merged, its head sha, branches, size and "
        "timestamps. Use to tie a deployment or a commit back to the change that proposed it."),
    "repository.list_workflow_runs": (
        "List CI/CD workflow runs with their status, conclusion, branch, head sha, event and "
        "timestamps. Use to find the failing or last successful run, or what ran just before an "
        "incident began; filter by branch, status or event."),
    "repository.get_workflow_run": (
        "Read one workflow run: status, conclusion, attempt, branch, head sha and timing. Use "
        "after a run is identified, to establish exactly how the pipeline ended."),
    "repository.list_deployments": (
        "List deployments with their environment, ref, commit sha and timestamps. Use to answer "
        "'what was deployed to this environment, and when' and to find the deployment an "
        "incident followed."),
    "repository.get_issue": (
        "Read one issue or pull-request thread: state, title, author, comment count and "
        "timestamps. Use to confirm a thread exists and is open before commenting on it, and to "
        "verify afterwards."),
    "repository.create_issue_comment": (
        "Post one comment on an existing issue or pull request in the connected repository. "
        "Governed: requires human approval, runs in a contained worker, is attributed to the "
        "CortexPrime action that produced it, and is independently read back before it counts "
        "as done."),
}


def github_manifest() -> ConnectorManifest:
    """The one declaration of the GitHub connector."""
    from backend.contexts.execution.infrastructure.adapters.connectors.github import (
        GITHUB_PERMISSIONS,
        github_read_profiles,
        github_write_profiles,
    )

    profiles = {**github_read_profiles(), **github_write_profiles()}
    capabilities = tuple(
        CapabilityManifest(
            capability_id=f"platform.github.{operation}", version=1, operation=operation,
            provider=_PROVIDER.get(operation, GITHUB_CONNECTOR_ID),
            description=_DESCRIPTIONS[operation],
            category=_CATEGORY.get(operation, "investigation"),
            profile=profiles[operation],
            required_permissions=tuple(GITHUB_PERMISSIONS.get(operation, ())),
            target_parameter="owner",
            target_parameters=("owner", "repo"),
        )
        for operation in SHIPPED_READS + SHIPPED_WRITES
    )
    return ConnectorManifest(
        connector_id=GITHUB_CONNECTOR_ID, display_name="GitHub", version="1.0.0",
        description=("Read what changed in the connected repositories -- commits, pull requests, "
                     "workflow runs and deployments -- and post one governed, independently "
                     "verified comment."),
        capabilities=capabilities)


@dataclass(frozen=True)
class GitHubConnection:
    """One tenant bound to named repositories. Deployment configuration only."""

    tenant_id: str
    repositories: Tuple[str, ...]
    api_url: str = GITHUB_API_BASE
    installation_id: str = ""
    #: ``app`` (production: GitHub App installation tokens) or ``vault-token``
    #: (a token held in Vault; refused in production, see the extension).
    credentials: str = "app"
    app_secret_path: str = "cortexprime/github/app"

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ContractViolation("a GitHub connection names the tenant it belongs to")
        if not self.repositories:
            raise ContractViolation(
                "a GitHub connection names the repositories it may reach; a connection to "
                "'whatever the token can see' is not a connection")
        for repository in self.repositories:
            if repository.count("/") != 1 or not all(part.strip() for part in repository.split("/")):
                raise ContractViolation(
                    f"{repository!r} is not owner/repo; a repository is identified by both")
        if not self.api_url.lower().startswith("https://"):
            raise ContractViolation(
                "the GitHub API is reached over https only; a bearer token on plaintext is "
                "exposed on every request")
        if self.credentials not in ("app", "vault-token"):
            raise ContractViolation("CORTEX_GITHUB_CREDENTIALS is 'app' or 'vault-token'")

    @property
    def owners(self) -> Tuple[str, ...]:
        return tuple(sorted({r.split("/")[0] for r in self.repositories}))

    @classmethod
    def from_env(cls, environ: Optional[Mapping[str, str]] = None) -> Optional["GitHubConnection"]:
        """``CORTEX_GITHUB_TENANT`` + ``CORTEX_GITHUB_REPOSITORIES`` (comma-separated
        ``owner/repo``); everything else has a default."""
        env = os.environ if environ is None else environ
        tenant = (env.get("CORTEX_GITHUB_TENANT") or "").strip()
        repositories = tuple(
            entry.strip() for entry in (env.get("CORTEX_GITHUB_REPOSITORIES") or "").split(",")
            if entry.strip())
        if not tenant or not repositories:
            return None
        return cls(
            tenant_id=tenant, repositories=repositories,
            api_url=(env.get("CORTEX_GITHUB_API_URL") or GITHUB_API_BASE).strip(),
            installation_id=(env.get("CORTEX_GITHUB_APP_INSTALLATION_ID") or "").strip(),
            credentials=(env.get("CORTEX_GITHUB_CREDENTIALS") or "app").strip().lower(),
            app_secret_path=(env.get("CORTEX_GITHUB_APP_SECRET_PATH")
                             or "cortexprime/github/app").strip())


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def github_connector_extension(environment: Any) -> Optional[dict]:
    """``CORTEX_CONNECTOR_FACTORIES`` entry for the GitHub connector.

    Composes, from ONE connection: the read connector, the contained comment
    worker when it is deployed, the manifest (commissioned at boot), the
    connection scope (enforced at the gateway) and the health probe. Returns
    ``None`` when no connection is configured, so a deployment that did not ask
    for GitHub does not get it.

    Credentials (``CORTEX_GITHUB_CREDENTIALS``):
      * ``app`` (the default, and the only mode production accepts): a GitHub
        App installation token minted per action for the connected repositories,
        from a private key held in Vault.
      * ``vault-token`` : a token stored in Vault KV under the tenant's path,
        for development and for the live proof of a deployment that has no App.
        **Refused in production** -- a personal access token is long-lived and
        account-wide, which is the opposite of what a production connection
        should hold.
    """
    from backend.contracts.execution import ExecutionEnvironment

    connection = GitHubConnection.from_env()
    if connection is None:
        return None
    production = environment is ExecutionEnvironment.PRODUCTION
    if production and connection.credentials != "app":
        raise ContractViolation(
            "a production GitHub connection authenticates as a GitHub App installation; "
            "a stored personal access token is long-lived and account-wide, and is a "
            "development path (CORTEX_GITHUB_CREDENTIALS=app)")

    from backend.api.capability_execution_composition import (
        CONTAINED_GITHUB_PROVIDER_ID,
        build_contained_github_worker_connector,
        build_github_connector,
    )
    from backend.api.connector_scope import ConnectionScope

    api_url = connection.api_url
    worker_ca = _env("CORTEX_WORKER_CA_BUNDLE") or _env("CORTEX_TLS_CA_BUNDLE")

    def read_builder(*, transport_broker: Any, connection_policy: Any, environment: Any,
                     preflight: Any = None, metrics: Any = None) -> tuple:
        return build_github_connector(
            transport_broker=transport_broker, connection_policy=connection_policy,
            environment=environment, base_url=api_url, preflight=preflight, metrics=metrics)

    connectors = [read_builder]
    providers = [GITHUB_CONNECTOR_ID]

    worker_url, worker_digest = _env("CORTEX_GITHUB_WORKER_URL"), _env("CORTEX_GITHUB_IMPL_DIGEST")
    if worker_url and worker_digest:
        def worker_builder(*, transport_broker: Any, connection_policy: Any, environment: Any,
                           preflight: Any = None, metrics: Any = None) -> tuple:
            from backend.api.kubernetes_connector import _pinned

            return build_contained_github_worker_connector(
                transport_broker=transport_broker,
                connection_policy=_pinned(connection_policy, worker_url, worker_ca),
                environment=environment, worker_url=worker_url,
                capability_id="platform.github.repository.create_issue_comment",
                capability_version=1, implementation_digest=worker_digest,
                preflight=preflight, metrics=metrics)

        connectors.append(worker_builder)
        providers.append(CONTAINED_GITHUB_PROVIDER_ID)

    produced: dict = {
        "connectors": connectors,
        "manifests": [github_manifest()],
        "connection_scopes": [ConnectionScope(
            tenant_id=connection.tenant_id, providers=frozenset(providers),
            targets=frozenset(connection.repositories),
            target_parameters=("owner", "repo"))],
        "credential_providers": [],
        "credential_provider_builders": [
            _credential_builder(provider_id, connection, environment)
            for provider_id in providers
        ],
        "health_probes": {GITHUB_CONNECTOR_ID: lambda runtime: github_health_probe(
            runtime, connection, environment)},
    }
    return produced


def _credential_builder(provider_id: str, connection: GitHubConnection, environment: Any) -> Any:
    """A credential adapter for one GitHub provider, built once the broker exists."""

    def build(connectivity: Any) -> Any:
        from backend.api.transport_composition import build_connection_policy
        from backend.platform.transport.endpoint import TransportEndpoint, TransportKind

        if connection.credentials == "vault-token":
            # The development path: the token lives in Vault KV under the
            # tenant's own path, never in the environment, and the generic Vault
            # adapter reads it. Nothing GitHub-specific is needed to do that.
            from backend.platform.credentials.vault import VaultCredentialAdapter

            address = _env("CORTEX_VAULT_ADDR")
            if not address:
                raise ContractViolation(
                    "CORTEX_VAULT_ADDR is required: a GitHub token is read from Vault, "
                    "never from the environment")
            endpoint = TransportEndpoint.parse(address, transport=TransportKind.HTTPS,
                                               environment=environment)
            policy = _vault_policy(address, environment)
            return VaultCredentialAdapter(
                provider_id=provider_id, environments=frozenset({environment}),
                broker=connectivity.transport_broker, endpoint=endpoint, policy=policy,
                vault_token=_vault_token(connectivity, endpoint, policy, environment),
                mount=_env("CORTEX_VAULT_KV_MOUNT", "secret"),
                path_prefix=_env("CORTEX_VAULT_KV_PREFIX", "cortexprime/providers"),
                secret_key=_env("CORTEX_GITHUB_TOKEN_FIELD", "token"))

        from backend.api.github_credentials import (
            GitHubAppCredentialAdapter,
            GitHubAppIdentity,
            GitHubAppTokenSource,
            read_vault_kv,
        )
        from backend.contexts.execution.infrastructure.adapters.connectors.github import (
            GITHUB_PERMISSIONS,
        )

        address = _env("CORTEX_VAULT_ADDR")
        if not address:
            raise ContractViolation(
                "CORTEX_VAULT_ADDR is required: the GitHub App private key is held in Vault")
        if not connection.installation_id:
            raise ContractViolation(
                "CORTEX_GITHUB_APP_INSTALLATION_ID is required for App authentication; "
                "an installation is what a token is minted against")
        vault_endpoint = TransportEndpoint.parse(address, transport=TransportKind.HTTPS,
                                                 environment=environment)
        vault_policy = _vault_policy(address, environment)
        secret = read_vault_kv(
            broker=connectivity.transport_broker, endpoint=vault_endpoint, policy=vault_policy,
            token=_vault_token(connectivity, vault_endpoint, vault_policy, environment),
            mount=_env("CORTEX_VAULT_KV_MOUNT", "secret"), path=connection.app_secret_path)
        identity = GitHubAppIdentity(
            app_id=str(secret.get("app_id") or ""),
            private_key_pem=str(secret.get("private_key") or ""))
        # Ask for exactly the permissions the shipped capabilities declare, and
        # no more: GitHub scopes the minted token down to what is requested.
        permissions: dict = {}
        for operation in SHIPPED_READS + SHIPPED_WRITES:
            for entry in GITHUB_PERMISSIONS.get(operation, ()):
                # "github:<resource>:<level>" -- the manifest qualifies every
                # permission with its provider; GitHub itself wants the last two.
                parts = entry.split(":")
                if len(parts) < 3:
                    continue
                name, level = parts[-2], parts[-1]
                if permissions.get(name) != "write":
                    permissions[name] = level or "read"
        github_endpoint = TransportEndpoint.parse(connection.api_url, transport=TransportKind.HTTPS,
                                                  environment=environment)
        source = GitHubAppTokenSource(
            broker=connectivity.transport_broker, endpoint=github_endpoint,
            policy=build_connection_policy(environment), identity=identity,
            installation_id=connection.installation_id,
            repositories=connection.repositories, permissions=permissions)
        return GitHubAppCredentialAdapter(
            provider_id=provider_id, environments=frozenset({environment}),
            broker=connectivity.transport_broker, endpoint=github_endpoint,
            policy=build_connection_policy(environment),
            vault_token=None, bindings={connection.tenant_id: source})

    return build


def _vault_policy(address: str, environment: Any) -> Any:
    from backend.api.kubernetes_connector import _ca, _pinned
    from backend.api.transport_composition import build_connection_policy

    return _pinned(build_connection_policy(environment), address, _ca("CORTEX_VAULT_CA_BUNDLE"))


def _vault_token(connectivity: Any, endpoint: Any, policy: Any, environment: Any) -> Any:
    """The platform's own Vault credential: a static token, or Kubernetes auth.

    The same two ways the Kubernetes connector gets one (11.1-K), reused rather
    than re-implemented: a deployment that already told CortexPrime how to log
    in to Vault does not tell it twice.
    """
    from datetime import datetime, timedelta, timezone

    from backend.contracts.credential import CredentialRef, CredentialType
    from backend.platform.credentials.material import CredentialMaterial
    from backend.platform.credentials.vault_kubernetes import VaultKubernetesAuth

    static = _env("VAULT_TOKEN")
    if static:
        now = datetime.now(timezone.utc)
        return CredentialMaterial(
            secret=static,
            ref=CredentialRef(tenant_id="cortexprime-platform", credential_id="vault-bootstrap"),
            credential_type=CredentialType.BEARER, expires_at=now + timedelta(days=365),
            acquired_at=now, headers=("Authorization",))
    return VaultKubernetesAuth(
        broker=connectivity.transport_broker, endpoint=endpoint, policy=policy,
        role=_env("CORTEX_VAULT_AUTH_ROLE", "cortexprime"),
        mount=_env("CORTEX_VAULT_AUTH_MOUNT", "kubernetes"))


def github_health_probe(runtime: Any, connection: GitHubConnection, environment: Any) -> Any:
    """The GitHub connector's health probe (returns a zero-argument callable).

    Evidence, in order; the first failure that makes later checks meaningless
    stops them:

      1. commissioning -- every shipped capability registered as declared;
      2. authentication, reachability and repository access -- one governed
         ``repository.get_repository`` per connected repository, in the
         connection tenant's own context, with its own credential: the real
         path, rate limit and audit included. GitHub has no "may I?" endpoint,
         so the cheapest real read is the check;
      3. each deployed contained worker answers ``/healthz`` over verified TLS.

    GitHub answers 404 for a repository a credential cannot see, deliberately,
    so that existence is not disclosed. Health reports that as MISCONFIGURED
    naming the repository -- "connected to something this credential cannot
    reach" is the operator's problem either way, and guessing which of the two
    it is would be inventing a fact.
    """
    from backend.api.connector_health import ConnectorHealth, ConnectorHealthState, HealthCheck
    from backend.contracts.connector_errors import (
        ConnectorErrorClass,
        classify_failure_text,
        classify_status,
    )

    S = ConnectorHealthState
    state_for = {
        ConnectorErrorClass.AUTHENTICATION_FAILED: S.AUTHENTICATION_REQUIRED,
        ConnectorErrorClass.AUTHORIZATION_DENIED: S.PERMISSION_DENIED,
        ConnectorErrorClass.RATE_LIMITED: S.RATE_LIMITED,
        ConnectorErrorClass.SECONDARY_RATE_LIMITED: S.RATE_LIMITED,
        ConnectorErrorClass.NETWORK_FAILURE: S.UNAVAILABLE,
        ConnectorErrorClass.TIMEOUT: S.UNAVAILABLE,
        ConnectorErrorClass.PROVIDER_UNAVAILABLE: S.UNAVAILABLE,
        ConnectorErrorClass.NOT_FOUND: S.MISCONFIGURED,
    }

    def probe() -> ConnectorHealth:
        import time as _time

        from backend.api.capability_execution_composition import GovernedCapabilityReader
        from backend.api.connector_commissioning import commissioned_capability
        from backend.contracts.identity import PrincipalKind, PrincipalRef
        from backend.platform.context import ExecutionContext
        from backend.platform.context.identity import IdentityContext

        started = _time.monotonic()
        manifest = github_manifest()
        checks: list = []
        unavailable: dict = {}
        report = getattr(runtime, "connector_reports", {}).get(GITHUB_CONNECTOR_ID)
        if report is None:
            checks.append(HealthCheck("commissioning", False, S.MISCONFIGURED,
                                      "the connector was not commissioned in this process"))
            return ConnectorHealth.from_checks(GITHUB_CONNECTOR_ID, connection.tenant_id, checks,
                                               duration_seconds=_time.monotonic() - started)
        broken = {**report.conflicts, **report.failed}
        checks.append(HealthCheck(
            "commissioning", not broken, S.MISCONFIGURED,
            "; ".join(f"{k}: {v}" for k, v in broken.items())
            or f"{len(report.available)} capabilities commissioned"))
        for cid, reason in report.skipped.items():
            unavailable[cid] = reason

        definition = commissioned_capability(runtime, "platform.github.repository.get_repository")
        if definition is None:
            checks.append(HealthCheck("repositories", False, S.MISCONFIGURED,
                                      "the repository read capability is not commissioned"))
        else:
            reader = GovernedCapabilityReader(
                runtime=runtime,
                capability_definitions={"repository.get_repository": definition},
                principal=PrincipalRef(principal_id="connector-health", kind=PrincipalKind.PLATFORM))
            tenant_ctx = ExecutionContext.for_tenant(
                tenant_id=connection.tenant_id,
                identity=IdentityContext(
                    principal=PrincipalRef(principal_id="connector-health",
                                           kind=PrincipalKind.PLATFORM),
                    capabilities=("capability:invoke",)),
                source="connector-health")
            unreachable: dict = {}
            worst_error: Optional[ConnectorErrorClass] = None
            for repository in connection.repositories:
                owner, _, repo = repository.partition("/")
                outcome = reader.read(tenant_ctx, operation="repository.get_repository",
                                      payload={"owner": owner, "repo": repo})
                if getattr(outcome, "succeeded", False):
                    continue
                reason = str(getattr(outcome, "failure_reason", "") or "")
                error = (classify_status(getattr(outcome, "status", None))
                         or classify_failure_text(reason))
                unreachable[repository] = f"{error.value}: {reason[:160]}"
                worst_error = error
            if unreachable:
                checks.append(HealthCheck(
                    "repositories", False, state_for.get(worst_error, S.MISCONFIGURED),
                    "; ".join(f"{k} -> {v}" for k, v in unreachable.items()),
                    error_class=worst_error.value if worst_error else None))
            else:
                checks.append(HealthCheck(
                    "repositories", True, S.MISCONFIGURED,
                    f"all {len(connection.repositories)} connected repositories are readable "
                    f"with this connection's own credential"))

        worker_url = _env("CORTEX_GITHUB_WORKER_URL")
        if worker_url:
            from backend.api.kubernetes_connector import _worker_reachable

            ok, detail = _worker_reachable(runtime, connection, worker_url, environment)
            checks.append(HealthCheck("worker:github-contained", ok, S.DEGRADED, detail))
            if not ok:
                for capability in manifest.capabilities:
                    if capability.provider == "github-contained":
                        unavailable[capability.capability_id] = f"worker unreachable: {detail}"
        else:
            for capability in manifest.capabilities:
                if capability.provider == "github-contained":
                    unavailable[capability.capability_id] = (
                        "no contained worker is deployed for this connection; the write "
                        "capability is declared but cannot run")

        available = tuple(c for c in report.available if c not in unavailable)
        return ConnectorHealth.from_checks(GITHUB_CONNECTOR_ID, connection.tenant_id, checks,
                                           available=available, unavailable=unavailable,
                                           duration_seconds=_time.monotonic() - started)

    return probe
