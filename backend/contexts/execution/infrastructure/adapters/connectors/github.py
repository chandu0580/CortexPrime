"""GitHub: the first production connector, and the reference for every later one.

Why GitHub was chosen
-----------------------
Against the ADR-042 §45 preference order, from what is actually in this
repository rather than from popularity:

* **An existing working client.** ``backend/connectors/github.py`` is the
  largest and most exercised V1 connector — pull requests, issues, checks,
  deployments, branch protection. Its endpoints, status codes and error shapes
  are known from code that has run, not from documentation.
* **Documented, single-mechanism authentication.** One bearer token in one
  header. No signing, no per-request nonce, no SDK that insists on holding the
  credential itself — so the credential fabric can own the secret and the
  transport can inject the header, which is the arrangement Phase 4.1 and 4.2
  were built for.
* **A conventional REST API.** Path-shaped resources, ordinary status codes, one
  JSON error envelope. That lets the *generic* adapter carry almost all of it
  and keeps this file down to what is genuinely GitHub-specific.
* **Capability coverage that matters here.** Reading a repository, reading an
  issue or pull request, and opening an issue or a comment is the minimum
  vocabulary CortexPrime needs to explain a problem and propose the fix.
* **Bounded security ambiguity.** Resources are named explicitly by
  ``owner``/``repo``, which is what makes the tenancy rule below expressible.

Everything GitHub-specific lives here and nowhere else
--------------------------------------------------------
The adapter that performs these operations is the generic ``ConnectorAdapter``.
It has no GitHub branch and never will. What GitHub contributes is data (the
catalog below) and one narrow translator for the two places its API departs from
convention. That is the shape every subsequent provider takes.

The tenancy rule, stated because it is not automatic
------------------------------------------------------
A GitHub account is not a tenant (ADR-042 §30). Two CortexPrime tenants may
reach GitHub through the same installation, and nothing in an access token
distinguishes them. What distinguishes them is that ``owner`` and ``repo`` are
**required path parameters** on every operation here: they are part of the
validated input, therefore part of the action digest, therefore part of the
credential scope's ``resource``, and therefore part of what authorization
decided. Tenant A's repository cannot become tenant B's by accident, because
neither the capability nor the credential nor the digest would match.

There is deliberately no operation that lists what the token can see. "Show me
every repository this credential reaches" is exactly the shape that turns a
shared installation into a cross-tenant read.

What this file does not contain
---------------------------------
No HTTP client, no retry loop, no ``asyncio.sleep`` on a rate limit, no ETag
cache, no pagination walker, no token read from the environment — all five of
which the V1 connector has, and all five of which belong to a layer that is not
this one. Retry is Execution's (ADR-031), rate limits are returned as facts
(§25), the credential comes from the fabric (§17), and the socket is the
broker's (§18).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from backend.contracts.execution import (
    EffectSemantics,
    ExecutionEnvironment,
    SideEffectClass,
)
from backend.contracts.provider import ProviderRef
from backend.contracts.transport import TransportKind
from backend.contexts.execution.domain.provider_operation import (
    OperationCatalog,
    ParameterKind,
    ParameterLocation,
    ParameterSpec,
    ProviderOperationSpec,
)
from backend.contexts.execution.infrastructure.adapters.channel import ProviderChannel
from backend.contexts.execution.infrastructure.adapters.connector import (
    DEFAULT_STATUS_FAILURES,
    HttpStatusTranslator,
)
from backend.contracts.provider import ProviderFailure
from backend.platform.transport import ConnectionPolicy, TransportBroker, TransportEndpoint

__all__ = [
    "GITHUB_PROVIDER_ID",
    "GITHUB_PROVIDER",
    "GITHUB_API_BASE",
    "GITHUB_SCOPES",
    "GitHubResponseTranslator",
    "github_catalog",
    "build_github_channel",
]

GITHUB_PROVIDER_ID = "github"
GITHUB_PROVIDER = ProviderRef(provider_id=GITHUB_PROVIDER_ID)

GITHUB_API_BASE = "https://api.github.com"

#: The provider scopes each operation needs, for the composition root to request
#: through ``CredentialScope``. Listed here because scope vocabulary is the
#: provider's and this is the file about GitHub — but *requested* by the
#: gateway, which is the only component that may ask for a credential.
GITHUB_SCOPES: Mapping[str, Tuple[str, ...]] = {
    "repository.get_repository": ("repo",),
    "repository.get_issue": ("repo",),
    "repository.create_issue": ("repo",),
    "repository.create_issue_comment": ("repo",),
    "repository.get_pull_request": ("repo",),
}

#: Sent on every request. Non-secret, declared, and validated by the transport's
#: header rules before anything is sent — the only kind of provider-specific
#: header an adapter may contribute (ADR-042 §57).
_GITHUB_HEADERS = {
    "accept": "application/vnd.github+json",
    "x-github-api-version": "2022-11-28",
    "user-agent": "CortexPrime-ConnectorAdapter/1.0",
}

_OWNER = ParameterSpec(
    name="owner",
    kind=ParameterKind.RESOURCE_SEGMENT,
    location=ParameterLocation.PATH,
    max_length=39,  # GitHub's own limit for a login.
)
_REPO = ParameterSpec(
    name="repo",
    kind=ParameterKind.RESOURCE_SEGMENT,
    location=ParameterLocation.PATH,
    max_length=100,
)


class GitHubResponseTranslator(HttpStatusTranslator):
    """The two places GitHub's API departs from the conventional mapping.

    Kept to two on purpose. Every additional special case here is a behaviour
    the generic adapter does not have and therefore cannot be reasoned about
    generically, so each one needs a reason that survives being read a year
    later.
    """

    def classify(
        self, spec: ProviderOperationSpec, exchange: Any, body: Any
    ) -> Optional[ProviderFailure]:
        status = exchange.status_code
        if status is None:
            return ProviderFailure.UNKNOWN_OUTCOME
        if status in spec.success_statuses:
            return None

        # 1. GitHub answers a rate limit with 403, not 429. Classified as
        #    ``AUTHORIZATION_FAILURE`` it would look like a permissions problem
        #    and send an operator to check scopes on a token that is fine.
        if status == 403 and self._is_rate_limit(exchange, body):
            return ProviderFailure.RATE_LIMITED

        # 2. GitHub answers 404 for a private resource the credential cannot
        #    see, deliberately, so that existence is not disclosed. We do not
        #    try to distinguish it -- guessing "this is really a permissions
        #    problem" would be inventing a fact, and NOT_FOUND is what the
        #    provider actually said.
        mapped = DEFAULT_STATUS_FAILURES.get(status)
        if mapped is not None:
            return mapped
        if 500 <= status < 600:
            return ProviderFailure.UNAVAILABLE
        if 400 <= status < 500:
            return ProviderFailure.VALIDATION_FAILURE
        return ProviderFailure.PROTOCOL_ERROR

    def describe(self, exchange: Any, body: Any) -> Tuple[Optional[str], Optional[str]]:
        """Extract GitHub's ``message`` field, bounded.

        Bounded because it is content GitHub composes, sometimes from input the
        caller supplied, and it reaches a log line. ``documentation_url`` is
        deliberately not included: it is a constant per error type and adds
        nothing an operator does not already have.
        """
        code = str(exchange.status_code) if exchange.status_code is not None else None
        if isinstance(body, Mapping):
            message = body.get("message")
            if isinstance(message, str) and message.strip():
                errors = body.get("errors")
                if isinstance(errors, list) and errors:
                    detail = "; ".join(
                        str(entry.get("message") or entry.get("code") or "")
                        for entry in errors[:5]
                        if isinstance(entry, Mapping)
                    )
                    if detail.strip(" ;"):
                        return code, f"{message.strip()[:200]}: {detail[:200]}"
                return code, message.strip()[:300]
        return code, exchange.reason

    @staticmethod
    def _is_rate_limit(exchange: Any, body: Any) -> bool:
        """Two independent signals, either of which is enough.

        The header is authoritative when present; the message is the fallback
        for the secondary-rate-limit responses that do not carry one.
        """
        remaining = exchange.headers.get("x-ratelimit-remaining")
        if remaining is not None and remaining.strip() == "0":
            return True
        if isinstance(body, Mapping):
            message = str(body.get("message") or "").lower()
            return "rate limit" in message or "abuse detection" in message
        return False


def github_catalog() -> OperationCatalog:
    """Every GitHub operation this fabric can perform. Five, and no others.

    Small on purpose. Each entry is a capability somebody has to register, a
    contract somebody has to approve and a scope somebody has to grant; a
    catalog that mirrored the whole GitHub API would be a list of things nobody
    decided to allow.

    ``supports_idempotency_key`` is ``False`` throughout because **GitHub has no
    idempotency mechanism**. Stated rather than worked around: a key sent to a
    provider that ignores it is protection that is not there, and Execution's
    retry rules need to know which of the two they are dealing with (§20).
    """
    return OperationCatalog(
        GITHUB_PROVIDER_ID,
        (
            ProviderOperationSpec(
                operation="repository.get_repository",
                method="GET",
                path_template="/repos/{owner}/{repo}",
                side_effect_class=SideEffectClass.READ,
                effect_semantics=EffectSemantics.READ_ONLY,
                parameters=(_OWNER, _REPO),
                success_statuses=(200,),
                response_required_fields=("id", "full_name"),
                response_evidence_fields=("id", "full_name", "private", "default_branch"),
                static_headers=_GITHUB_HEADERS,
                provider_timeout_seconds=30.0,
                max_response_bytes=1 * 1024 * 1024,
            ),
            ProviderOperationSpec(
                operation="repository.get_issue",
                method="GET",
                path_template="/repos/{owner}/{repo}/issues/{issue_number}",
                side_effect_class=SideEffectClass.READ,
                effect_semantics=EffectSemantics.READ_ONLY,
                parameters=(
                    _OWNER,
                    _REPO,
                    ParameterSpec(
                        name="issue_number",
                        kind=ParameterKind.RESOURCE_SEGMENT,
                        location=ParameterLocation.PATH,
                        max_length=12,
                    ),
                ),
                success_statuses=(200,),
                response_required_fields=("number", "state"),
                response_evidence_fields=("number", "state", "html_url", "title"),
                static_headers=_GITHUB_HEADERS,
                provider_timeout_seconds=30.0,
                max_response_bytes=1 * 1024 * 1024,
            ),
            ProviderOperationSpec(
                operation="repository.get_pull_request",
                method="GET",
                path_template="/repos/{owner}/{repo}/pulls/{pull_number}",
                side_effect_class=SideEffectClass.READ,
                effect_semantics=EffectSemantics.READ_ONLY,
                parameters=(
                    _OWNER,
                    _REPO,
                    ParameterSpec(
                        name="pull_number",
                        kind=ParameterKind.RESOURCE_SEGMENT,
                        location=ParameterLocation.PATH,
                        max_length=12,
                    ),
                ),
                success_statuses=(200,),
                response_required_fields=("number", "state"),
                response_evidence_fields=("number", "state", "html_url", "merged"),
                static_headers=_GITHUB_HEADERS,
                provider_timeout_seconds=30.0,
                max_response_bytes=4 * 1024 * 1024,
            ),
            ProviderOperationSpec(
                operation="repository.create_issue",
                method="POST",
                path_template="/repos/{owner}/{repo}/issues",
                # Irreversible, not reversible: closing an issue is not deleting
                # it, and Constitution P2 says an action with no complete inverse
                # is classified irreversible rather than optimistically.
                side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE,
                # Non-idempotent, and this is the operationally important one:
                # posting the same body twice creates two issues, so a blind
                # retry after an ambiguous outcome duplicates it. Declaring it
                # honestly is what stops that.
                effect_semantics=EffectSemantics.NON_IDEMPOTENT_WRITE,
                parameters=(
                    _OWNER,
                    _REPO,
                    ParameterSpec(
                        name="title",
                        kind=ParameterKind.STRING,
                        location=ParameterLocation.BODY,
                        max_length=256,
                    ),
                    ParameterSpec(
                        name="body",
                        kind=ParameterKind.TEXT,
                        location=ParameterLocation.BODY,
                        required=False,
                        max_length=65536,
                    ),
                    ParameterSpec(
                        name="labels",
                        kind=ParameterKind.STRING_LIST,
                        location=ParameterLocation.BODY,
                        required=False,
                        max_length=64,
                    ),
                    ParameterSpec(
                        name="assignees",
                        kind=ParameterKind.STRING_LIST,
                        location=ParameterLocation.BODY,
                        required=False,
                        max_length=64,
                    ),
                ),
                success_statuses=(201,),
                response_required_fields=("number", "html_url"),
                response_evidence_fields=("number", "html_url", "state", "id"),
                static_headers=_GITHUB_HEADERS,
                provider_timeout_seconds=30.0,
                max_response_bytes=1 * 1024 * 1024,
            ),
            ProviderOperationSpec(
                operation="repository.create_issue_comment",
                method="POST",
                path_template="/repos/{owner}/{repo}/issues/{issue_number}/comments",
                side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE,
                effect_semantics=EffectSemantics.NON_IDEMPOTENT_WRITE,
                parameters=(
                    _OWNER,
                    _REPO,
                    ParameterSpec(
                        name="issue_number",
                        kind=ParameterKind.RESOURCE_SEGMENT,
                        location=ParameterLocation.PATH,
                        max_length=12,
                    ),
                    ParameterSpec(
                        name="body",
                        kind=ParameterKind.TEXT,
                        location=ParameterLocation.BODY,
                        max_length=65536,
                    ),
                ),
                success_statuses=(201,),
                response_required_fields=("id", "html_url"),
                response_evidence_fields=("id", "html_url"),
                static_headers=_GITHUB_HEADERS,
                provider_timeout_seconds=30.0,
                max_response_bytes=1 * 1024 * 1024,
            ),
        ),
    )


def build_github_channel(
    *,
    broker: TransportBroker,
    policy: ConnectionPolicy,
    environment: ExecutionEnvironment,
    base_url: str = GITHUB_API_BASE,
) -> ProviderChannel:
    """The channel GitHub is reached through. Destination from configuration.

    ``base_url`` is a parameter so an enterprise deployment can name its own
    GitHub host — and it is *deployment configuration*, never request input.
    Nothing downstream of this can influence the scheme, host or port; an
    operation contributes a path built from a declared template and validated
    segments, and that is the whole of what varies per call.
    """
    endpoint = TransportEndpoint.parse(
        base_url, transport=TransportKind.HTTPS, environment=environment
    )
    if endpoint.is_plaintext:
        # Refused here as well as by policy. A plaintext GitHub endpoint would
        # expose the bearer token on every request, and a deployment that has
        # relaxed plaintext for a local sidecar should not silently get it here.
        raise ValueError(
            "the GitHub endpoint must be https; a plaintext one exposes the "
            "bearer token on every request"
        )
    return ProviderChannel(
        provider=GITHUB_PROVIDER,
        broker=broker,
        base_endpoint=endpoint,
        policy=policy,
        transport=TransportKind.HTTPS,
    )
