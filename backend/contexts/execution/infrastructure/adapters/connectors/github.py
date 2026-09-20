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
    RecordEvidenceSpec,
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
    "GITHUB_PERMISSIONS",
    "GitHubResponseTranslator",
    "GitHubResponseNormalizer",
    "GITHUB_READ_OPERATIONS",
    "GITHUB_WRITE_OPERATIONS",
    "github_read_profiles",
    "github_write_profiles",
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
    # Phase 11.2: the reads an incident investigation discriminates on --
    # what changed, when, by whom, in which pull request, which workflow run
    # and which deployment.
    "repository.list_commits": ("repo",),
    "repository.get_commit": ("repo",),
    "repository.list_pull_requests": ("repo",),
    "repository.list_workflow_runs": ("repo",),
    "repository.get_workflow_run": ("repo",),
    "repository.list_deployments": ("repo",),
}

#: The fine-grained GitHub App permission each operation needs, as GitHub names
#: it (docs: REST endpoints "Fine-grained access tokens for this endpoint").
#: Connector health asks for exactly these, and the manifest publishes them.
GITHUB_PERMISSIONS: Mapping[str, Tuple[str, ...]] = {
    "repository.get_repository": ("github:metadata:read",),
    "repository.list_commits": ("github:contents:read",),
    "repository.get_commit": ("github:contents:read",),
    "repository.list_pull_requests": ("github:pull_requests:read",),
    "repository.get_pull_request": ("github:pull_requests:read",),
    "repository.list_workflow_runs": ("github:actions:read",),
    "repository.get_workflow_run": ("github:actions:read",),
    "repository.list_deployments": ("github:deployments:read",),
    "repository.get_issue": ("github:issues:read",),
    "repository.create_issue": ("github:issues:write",),
    "repository.create_issue_comment": ("github:issues:write",),
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
                response_evidence_fields=(
                    "number", "state", "title", "author_login", "comments",
                    "created_at", "updated_at", "html_url",
                ),
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
                response_evidence_fields=(
                    "number", "title", "state", "merged", "author_login", "base_ref", "head_ref",
                    "head_sha", "changed_files", "additions", "deletions", "commits",
                    "created_at", "updated_at", "merged_at", "draft", "html_url",
                ),
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
                response_evidence_fields=(
                    "number", "html_url", "state", "id", "title", "author_login", "created_at",
                ),
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
                response_evidence_fields=(
                    "id", "html_url", "author_login", "created_at", "issue_url",
                ),
                static_headers=_GITHUB_HEADERS,
                provider_timeout_seconds=30.0,
                max_response_bytes=1 * 1024 * 1024,
            ),
            # -- Phase 11.2: what changed, when, who, and what ran ---------
            ProviderOperationSpec(
                operation="repository.list_commits",
                method="GET",
                path_template="/repos/{owner}/{repo}/commits",
                side_effect_class=SideEffectClass.READ,
                effect_semantics=EffectSemantics.READ_ONLY,
                parameters=(
                    _OWNER,
                    _REPO,
                    ParameterSpec(
                        name="sha",
                        kind=ParameterKind.STRING,
                        location=ParameterLocation.QUERY,
                        required=False,
                        max_length=255,
                    ),
                    ParameterSpec(
                        name="path",
                        kind=ParameterKind.STRING,
                        location=ParameterLocation.QUERY,
                        required=False,
                        max_length=255,
                    ),
                    ParameterSpec(
                        name="since",
                        kind=ParameterKind.STRING,
                        location=ParameterLocation.QUERY,
                        required=False,
                        max_length=32,
                    ),
                    ParameterSpec(
                        name="until",
                        kind=ParameterKind.STRING,
                        location=ParameterLocation.QUERY,
                        required=False,
                        max_length=32,
                    ),
                    ParameterSpec(
                        name="per_page",
                        kind=ParameterKind.INTEGER,
                        location=ParameterLocation.QUERY,
                        required=False,
                        min_value=1,
                        max_value=100,
                    ),
                ),
                success_statuses=(200,),
                response_required_fields=("count",),
                response_evidence_fields=("count",),
                response_evidence_records=RecordEvidenceSpec(
                    field_name="commits",
                    fields=("sha", "authored_at", "author_login", "message_line", "html_url"),
                    max_records=30,
                ),
                static_headers=_GITHUB_HEADERS,
                provider_timeout_seconds=30.0,
                max_response_bytes=4 * 1024 * 1024,
            ),
            ProviderOperationSpec(
                operation="repository.get_commit",
                method="GET",
                path_template="/repos/{owner}/{repo}/commits/{commit_sha}",
                side_effect_class=SideEffectClass.READ,
                effect_semantics=EffectSemantics.READ_ONLY,
                parameters=(
                    _OWNER,
                    _REPO,
                    ParameterSpec(
                        name="commit_sha",
                        kind=ParameterKind.RESOURCE_SEGMENT,
                        location=ParameterLocation.PATH,
                        max_length=255,
                    ),
                ),
                success_statuses=(200,),
                response_required_fields=("sha",),
                response_evidence_fields=(
                    "sha", "authored_at", "author_login", "committed_at", "message_line",
                    "files_changed", "additions", "deletions", "parent_count", "html_url",
                ),
                response_evidence_records=RecordEvidenceSpec(
                    field_name="files",
                    fields=("filename", "status", "additions", "deletions"),
                    max_records=50,
                ),
                static_headers=_GITHUB_HEADERS,
                provider_timeout_seconds=30.0,
                max_response_bytes=4 * 1024 * 1024,
            ),
            ProviderOperationSpec(
                operation="repository.list_pull_requests",
                method="GET",
                path_template="/repos/{owner}/{repo}/pulls",
                side_effect_class=SideEffectClass.READ,
                effect_semantics=EffectSemantics.READ_ONLY,
                parameters=(
                    _OWNER,
                    _REPO,
                    ParameterSpec(
                        name="state",
                        kind=ParameterKind.ENUM,
                        location=ParameterLocation.QUERY,
                        required=False,
                        allowed_values=("open", "closed", "all"),
                    ),
                    ParameterSpec(
                        name="base",
                        kind=ParameterKind.STRING,
                        location=ParameterLocation.QUERY,
                        required=False,
                        max_length=255,
                    ),
                    ParameterSpec(
                        name="sort",
                        kind=ParameterKind.ENUM,
                        location=ParameterLocation.QUERY,
                        required=False,
                        allowed_values=("created", "updated", "popularity"),
                    ),
                    ParameterSpec(
                        name="direction",
                        kind=ParameterKind.ENUM,
                        location=ParameterLocation.QUERY,
                        required=False,
                        allowed_values=("asc", "desc"),
                    ),
                    ParameterSpec(
                        name="per_page",
                        kind=ParameterKind.INTEGER,
                        location=ParameterLocation.QUERY,
                        required=False,
                        min_value=1,
                        max_value=100,
                    ),
                ),
                success_statuses=(200,),
                response_required_fields=("count",),
                response_evidence_fields=("count",),
                response_evidence_records=RecordEvidenceSpec(
                    field_name="pull_requests",
                    fields=("number", "title", "state", "author_login", "base_ref",
                            "head_ref", "head_sha", "created_at", "merged_at", "html_url"),
                    max_records=30,
                ),
                static_headers=_GITHUB_HEADERS,
                provider_timeout_seconds=30.0,
                max_response_bytes=4 * 1024 * 1024,
            ),
            ProviderOperationSpec(
                operation="repository.list_workflow_runs",
                method="GET",
                path_template="/repos/{owner}/{repo}/actions/runs",
                side_effect_class=SideEffectClass.READ,
                effect_semantics=EffectSemantics.READ_ONLY,
                parameters=(
                    _OWNER,
                    _REPO,
                    ParameterSpec(
                        name="branch",
                        kind=ParameterKind.STRING,
                        location=ParameterLocation.QUERY,
                        required=False,
                        max_length=255,
                    ),
                    ParameterSpec(
                        name="status",
                        kind=ParameterKind.ENUM,
                        location=ParameterLocation.QUERY,
                        required=False,
                        allowed_values=("completed", "in_progress", "queued", "success",
                                        "failure", "cancelled", "timed_out", "action_required"),
                    ),
                    ParameterSpec(
                        name="event",
                        kind=ParameterKind.STRING,
                        location=ParameterLocation.QUERY,
                        required=False,
                        max_length=64,
                    ),
                    ParameterSpec(
                        name="created",
                        kind=ParameterKind.STRING,
                        location=ParameterLocation.QUERY,
                        required=False,
                        max_length=64,
                    ),
                    ParameterSpec(
                        name="per_page",
                        kind=ParameterKind.INTEGER,
                        location=ParameterLocation.QUERY,
                        required=False,
                        min_value=1,
                        max_value=100,
                    ),
                ),
                success_statuses=(200,),
                response_required_fields=("count",),
                response_evidence_fields=("count", "total_count"),
                response_evidence_records=RecordEvidenceSpec(
                    field_name="workflow_runs",
                    fields=("id", "name", "status", "conclusion", "head_branch", "head_sha",
                            "event", "run_number", "created_at", "updated_at", "html_url"),
                    max_records=30,
                ),
                static_headers=_GITHUB_HEADERS,
                provider_timeout_seconds=30.0,
                max_response_bytes=4 * 1024 * 1024,
            ),
            ProviderOperationSpec(
                operation="repository.get_workflow_run",
                method="GET",
                path_template="/repos/{owner}/{repo}/actions/runs/{workflow_run_id}",
                side_effect_class=SideEffectClass.READ,
                effect_semantics=EffectSemantics.READ_ONLY,
                parameters=(
                    _OWNER,
                    _REPO,
                    ParameterSpec(
                        name="workflow_run_id",
                        kind=ParameterKind.RESOURCE_SEGMENT,
                        location=ParameterLocation.PATH,
                        max_length=20,
                    ),
                ),
                success_statuses=(200,),
                response_required_fields=("id", "status"),
                response_evidence_fields=(
                    "id", "name", "status", "conclusion", "head_branch", "head_sha",
                    "event", "run_number", "run_attempt", "created_at", "updated_at", "html_url",
                ),
                static_headers=_GITHUB_HEADERS,
                provider_timeout_seconds=30.0,
                max_response_bytes=4 * 1024 * 1024,
            ),
            ProviderOperationSpec(
                operation="repository.list_deployments",
                method="GET",
                path_template="/repos/{owner}/{repo}/deployments",
                side_effect_class=SideEffectClass.READ,
                effect_semantics=EffectSemantics.READ_ONLY,
                parameters=(
                    _OWNER,
                    _REPO,
                    ParameterSpec(
                        name="environment",
                        kind=ParameterKind.STRING,
                        location=ParameterLocation.QUERY,
                        required=False,
                        max_length=255,
                    ),
                    ParameterSpec(
                        name="ref",
                        kind=ParameterKind.STRING,
                        location=ParameterLocation.QUERY,
                        required=False,
                        max_length=255,
                    ),
                    ParameterSpec(
                        name="per_page",
                        kind=ParameterKind.INTEGER,
                        location=ParameterLocation.QUERY,
                        required=False,
                        min_value=1,
                        max_value=100,
                    ),
                ),
                success_statuses=(200,),
                response_required_fields=("count",),
                response_evidence_fields=("count",),
                response_evidence_records=RecordEvidenceSpec(
                    field_name="deployments",
                    fields=("id", "sha", "ref", "environment", "task", "created_at", "updated_at"),
                    max_records=30,
                ),
                static_headers=_GITHUB_HEADERS,
                provider_timeout_seconds=30.0,
                max_response_bytes=4 * 1024 * 1024,
            ),
        ),
    )


class GitHubResponseNormalizer:
    """Lifts GitHub's nested answer into the flat, bounded shape each operation
    declares as its evidence (the ``ProviderBodyNormalizer`` port).

    Why a normalizer rather than wider evidence
    ---------------------------------------------
    Governed evidence is top-level scalars plus one declared record list, on
    purpose: a raw provider payload is unbounded and can carry the caller's own
    data back. GitHub, however, nests exactly the facts an investigation needs
    -- who wrote a commit (``author.login``), what it said
    (``commit.message``), how much it changed (``stats``) -- and answers some
    reads with a bare JSON array. This lifts those declared fields, and only
    those, in GitHub's own module.

    What it may not do (the port's contract): it cannot authorize, cannot change
    the operation or destination, and cannot fabricate provider state. A field
    GitHub did not send stays missing, and the operation's shape check then
    refuses the answer rather than inventing one. The first line of a commit
    message is a *truncation* of what GitHub sent, never a paraphrase.
    """

    #: Operations whose answer is a bare JSON array, and the record field each
    #: one is lifted into.
    _LISTS: Mapping[str, str] = {
        "repository.list_commits": "commits",
        "repository.list_pull_requests": "pull_requests",
        "repository.list_deployments": "deployments",
    }

    def normalize(self, spec: ProviderOperationSpec, body: Any) -> Any:
        operation = spec.operation
        if operation in self._LISTS:
            if not isinstance(body, list):
                raise ValueError(f"{operation}: expected a JSON array, got {type(body).__name__}")
            field = self._LISTS[operation]
            records = [self._record(operation, entry) for entry in body if isinstance(entry, Mapping)]
            return {"count": len(records), field: records}
        if not isinstance(body, Mapping):
            raise ValueError(f"{operation}: expected a JSON object, got {type(body).__name__}")
        if operation == "repository.list_workflow_runs":
            runs = body.get("workflow_runs")
            entries = [self._run(r) for r in runs if isinstance(r, Mapping)] if isinstance(runs, list) else []
            out = {"count": len(entries), "workflow_runs": entries}
            if isinstance(body.get("total_count"), int):
                out["total_count"] = body["total_count"]
            return out
        if operation == "repository.get_commit":
            return self._commit_detail(body)
        if operation == "repository.get_workflow_run":
            return self._run(body)
        if operation == "repository.get_pull_request":
            return {**body, **self._pull_request(body)}
        if operation in ("repository.get_issue", "repository.create_issue"):
            return {**body, **self._actor(body, "user", "author_login")}
        if operation == "repository.create_issue_comment":
            return {**body, **self._actor(body, "user", "author_login")}
        return body

    # -- per-shape lifting ---------------------------------------------------

    def _record(self, operation: str, entry: Mapping) -> dict:
        if operation == "repository.list_commits":
            return self._commit_summary(entry)
        if operation == "repository.list_pull_requests":
            return self._pull_request(entry)
        return dict(self._scalars(entry))

    def _commit_summary(self, entry: Mapping) -> dict:
        commit = entry.get("commit") if isinstance(entry.get("commit"), Mapping) else {}
        author = commit.get("author") if isinstance(commit.get("author"), Mapping) else {}
        out = {"sha": entry.get("sha"), "html_url": entry.get("html_url")}
        if isinstance(author.get("date"), str):
            out["authored_at"] = author["date"]
        login = self._login(entry.get("author")) or author.get("name")
        if isinstance(login, str):
            out["author_login"] = login
        message = commit.get("message")
        if isinstance(message, str):
            out["message_line"] = message.splitlines()[0] if message.splitlines() else ""
        return {k: v for k, v in out.items() if v is not None}

    def _commit_detail(self, body: Mapping) -> dict:
        out = self._commit_summary(body)
        commit = body.get("commit") if isinstance(body.get("commit"), Mapping) else {}
        committer = commit.get("committer") if isinstance(commit.get("committer"), Mapping) else {}
        if isinstance(committer.get("date"), str):
            out["committed_at"] = committer["date"]
        stats = body.get("stats") if isinstance(body.get("stats"), Mapping) else {}
        for key in ("additions", "deletions"):
            if isinstance(stats.get(key), int):
                out[key] = stats[key]
        files = body.get("files")
        if isinstance(files, list):
            out["files_changed"] = len(files)
            out["files"] = [
                {k: f.get(k) for k in ("filename", "status", "additions", "deletions") if k in f}
                for f in files if isinstance(f, Mapping)
            ]
        parents = body.get("parents")
        if isinstance(parents, list):
            out["parent_count"] = len(parents)
        return out

    def _pull_request(self, entry: Mapping) -> dict:
        base = entry.get("base") if isinstance(entry.get("base"), Mapping) else {}
        head = entry.get("head") if isinstance(entry.get("head"), Mapping) else {}
        out = {
            "number": entry.get("number"), "title": entry.get("title"),
            "state": entry.get("state"), "created_at": entry.get("created_at"),
            "updated_at": entry.get("updated_at"), "merged_at": entry.get("merged_at"),
            "html_url": entry.get("html_url"), "draft": entry.get("draft"),
            "base_ref": base.get("ref"), "head_ref": head.get("ref"), "head_sha": head.get("sha"),
        }
        for key in ("merged", "changed_files", "additions", "deletions", "commits"):
            if key in entry:
                out[key] = entry[key]
        login = self._login(entry.get("user"))
        if login:
            out["author_login"] = login
        return {k: v for k, v in out.items() if v is not None}

    def _run(self, entry: Mapping) -> dict:
        keep = ("id", "name", "status", "conclusion", "head_branch", "head_sha", "event",
                "run_number", "run_attempt", "created_at", "updated_at", "html_url")
        return {k: entry[k] for k in keep if k in entry and entry[k] is not None}

    def _actor(self, body: Mapping, source: str, target: str) -> dict:
        login = self._login(body.get(source))
        return {target: login} if login else {}

    @staticmethod
    def _login(value: Any) -> Optional[str]:
        if isinstance(value, Mapping) and isinstance(value.get("login"), str):
            return value["login"]
        return None

    @staticmethod
    def _scalars(entry: Mapping) -> dict:
        return {k: v for k, v in entry.items() if isinstance(v, (int, float, bool, str))}


# ---------------------------------------------------------------------------
# Capability-bridge profiles (Phase 11.2)
# ---------------------------------------------------------------------------

GITHUB_READ_OPERATIONS: Tuple[str, ...] = (
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

GITHUB_WRITE_OPERATIONS: Tuple[str, ...] = (
    "repository.create_issue_comment",
    "repository.create_issue",
)

#: What each operation is scoped to, in the provider's own vocabulary.
_RESOURCE_SCOPE: Mapping[str, str] = {
    "repository.get_repository": "repository",
    "repository.list_commits": "repository",
    "repository.get_commit": "commit",
    "repository.list_pull_requests": "repository",
    "repository.get_pull_request": "pull_request",
    "repository.list_workflow_runs": "repository",
    "repository.get_workflow_run": "workflow_run",
    "repository.list_deployments": "repository",
    "repository.get_issue": "issue",
    "repository.create_issue_comment": "issue",
    "repository.create_issue": "repository",
}

_TIMEOUT = 30.0
_POLICY_VERSION = "github-connector/1"


def github_read_profiles() -> dict:
    """READ profiles: LOW risk, ceiling A1 (observe/investigate, never an
    action), no verification (nothing was changed), reversible by nature."""
    from backend.contracts.intelligence.capability_profile import (
        CapabilityProfile, VerificationRequirement)
    from backend.contracts.intelligence.investigation import AutonomyLevel
    from backend.contracts.policy import RiskClassification, RiskFactors, RiskLevel

    profiles = {}
    for operation in GITHUB_READ_OPERATIONS:
        factors = RiskFactors(side_effect_class=SideEffectClass.READ, environment="development",
                              resource_count=1, reversible=True)
        profiles[operation] = CapabilityProfile(
            capability_ref=f"platform.github.{operation}",
            provider=GITHUB_PROVIDER_ID, operation=operation,
            side_effect_class=SideEffectClass.READ, effect_semantics=EffectSemantics.READ_ONLY,
            risk=RiskClassification(level=RiskLevel.LOW, factors=factors,
                                    rationale=f"{operation}: read-only repository observation"),
            autonomy_ceiling=AutonomyLevel.A1_INVESTIGATE,
            verification_requirement=VerificationRequirement.NONE,
            resource_scope=_RESOURCE_SCOPE[operation], reversible=True,
            timeout_seconds=_TIMEOUT, policy_version=_POLICY_VERSION)
    return profiles


def github_write_profiles() -> dict:
    """WRITE profiles. Every field is a claim the platform has to live with.

    * ``reversible=False`` — GitHub has no inverse for either write. Deleting a
      comment is a second act that leaves its own trace, and an issue cannot be
      deleted at all through the REST API; Constitution P2 says an action with
      no complete inverse is classified irreversible rather than optimistically.
    * ``compensation=None`` — and stated rather than invented. The Kubernetes
      rollback could name a real compensating action; neither of these can, so
      neither may earn the compensable-autonomy path (ADR-124 D-4/D-5). Every
      GitHub write faces a human.
    * ``verification_requirement=INDEPENDENT_READBACK`` — the created comment or
      issue is read back by identity and content. "GitHub returned 201" is not
      the same claim as "the comment exists and says what we intended".
    * ``autonomy_ceiling=A3`` — approved action, never A4.
    * ``RiskLevel.MEDIUM`` for a comment, ``HIGH`` for opening an issue: a
      comment adds a message to a conversation somebody already started; an
      issue creates a new record that notifies subscribers and enters a backlog.
      Both route through approval, and the difference is honest rather than
      decorative.
    """
    from backend.contracts.intelligence.capability_profile import (
        CapabilityProfile, VerificationRequirement)
    from backend.contracts.intelligence.investigation import AutonomyLevel
    from backend.contracts.policy import RiskClassification, RiskFactors, RiskLevel

    levels = {"repository.create_issue_comment": RiskLevel.MEDIUM,
              "repository.create_issue": RiskLevel.HIGH}
    rationale = {
        "repository.create_issue_comment":
            "posts a visible comment, attributable to CortexPrime, on an existing thread",
        "repository.create_issue":
            "opens a new tracked record that notifies subscribers and cannot be deleted",
    }
    profiles = {}
    for operation in GITHUB_WRITE_OPERATIONS:
        factors = RiskFactors(side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE,
                              environment="development", resource_count=1, reversible=False)
        profiles[operation] = CapabilityProfile(
            capability_ref=f"platform.github.{operation}",
            provider=GITHUB_PROVIDER_ID, operation=operation,
            side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE,
            effect_semantics=EffectSemantics.NON_IDEMPOTENT_WRITE,
            risk=RiskClassification(level=levels[operation], factors=factors,
                                    rationale=f"{operation}: {rationale[operation]}"),
            autonomy_ceiling=AutonomyLevel.A3_APPROVED_ACTION,
            verification_requirement=VerificationRequirement.INDEPENDENT_READBACK,
            resource_scope=_RESOURCE_SCOPE[operation], reversible=False,
            timeout_seconds=_TIMEOUT, policy_version=_POLICY_VERSION,
            compensation=None)
    return profiles


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
