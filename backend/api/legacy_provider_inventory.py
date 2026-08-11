"""V1 provider mechanisms: what exists, what it does, and where each one goes.

Why an inventory and not a rewrite
------------------------------------
Phase 4.3 builds the provider adapter fabric and migrates **one** connector onto
it. It does not rewrite eighteen provider clients, four registries and an MCP
gateway — migrating everything on the strength of an architecture document is
how a security phase becomes an outage, and a migration nobody can review one
piece at a time is one nobody reviews.

So each pre-existing provider mechanism is named here with what was found by
reading it, and classified. The classification is the deliverable: it is what
turns "there is a lot of old code" into a list somebody can work through.

The five classifications
--------------------------
``SAFE_TO_REUSE``     Correct as it stands, and the fabric depends on it.
``ADAPTER_TARGET``    Becomes a declaration behind the new fabric — a catalog
                      entry, a translator — rather than being rewritten.
``STRANGLER_TARGET``  Stays, gated, until something replaces it. The gate is
                      already there (ADR-039); this records what it is holding.
``SECURITY_HAZARD``   Dangerous *now*, not merely unmigrated. Needs a decision
                      before it needs a migration.
``REMOVE_LATER``      Provably unused or fully superseded. Deleting it is a
                      separate decision with its own review.

The property that still holds across all of them
--------------------------------------------------
None of these bypasses the **invocation gateway**. Every V1 execution route is
gated and refuses by default (ADR-039, ``legacy_execution_boundary``). What they
bypass is the *provider fabric*: they choose their own operations, hold their
own credentials and dial by their own means.

So the exposure is bounded by the gate in front of them rather than by anything
in the client itself — with one exception, recorded below as a hazard.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "Disposition",
    "LegacyProviderMechanism",
    "LEGACY_PROVIDER_MECHANISMS",
    "MIGRATED",
    "hazards",
    "by_disposition",
    "summary",
]


class Disposition(str, Enum):
    """Where a V1 mechanism goes. Five answers, and none of them is 'later'."""

    SAFE_TO_REUSE = "safe_to_reuse"
    ADAPTER_TARGET = "adapter_target"
    STRANGLER_TARGET = "strangler_target"
    SECURITY_HAZARD = "security_hazard"
    REMOVE_LATER = "remove_later"


@dataclass(frozen=True)
class LegacyProviderMechanism:
    """One pre-existing way CortexPrime reaches, or chooses, a provider."""

    location: str
    mechanism: str
    finding: str
    disposition: Disposition

    chooses_operation: bool
    """Whether the mechanism decides *what* is performed, rather than performing
    something already decided. The single most important column: a mechanism that
    chooses is one where a capability, an approval and an audit record describe
    something other than what happened."""

    holds_credential: bool
    dials_directly: bool
    tenant_aware: bool
    mutable_singleton: bool
    migrated: bool = False
    note: str = ""


LEGACY_PROVIDER_MECHANISMS: tuple = (
    # ------------------------------------------------------------------
    # MCP
    # ------------------------------------------------------------------
    LegacyProviderMechanism(
        location="backend/mcp/registry.py :: MCPRegistry, mcp_registry",
        mechanism="Module-level mutable singleton mapping connector name to "
        "MCPConnector, with ``execute(request)`` scanning every connector's "
        "tool list for a matching name",
        finding="``execute`` resolves a tool **by name across every registered "
        "connector** and calls the first match, authenticating the connector on "
        "the way past if it is not already. That is dynamic tool selection: the "
        "tool that runs is chosen at invocation time from a mutable global, so "
        "registering a connector that happens to expose the same tool name "
        "changes what an existing call does. There is no tenant anywhere in the "
        "path.",
        disposition=Disposition.STRANGLER_TARGET,
        chooses_operation=True,
        holds_credential=True,
        dials_directly=False,
        tenant_aware=False,
        mutable_singleton=True,
        note="Superseded by ``McpToolAdapter``, where the tool comes from the "
        "binding by exact field copy and there is no lookup by name. Kept "
        "because ``/api/v2/mcp/execute`` still reaches it and that route is "
        "gated off rather than deleted. **Phase 4.4 gated the write side "
        "too**: ``/api/v2/mcp/connectors/register`` inserted caller-named "
        "tools into this singleton, and first-match-wins resolution meant a "
        "registration could shadow an existing tool name process-wide.",
    ),
    LegacyProviderMechanism(
        location="backend/mcp/gateway.py :: MCPGateway, mcp_gateway",
        mechanism="A second module-level singleton wrapping ``mcp_registry``",
        finding="Delegates every method to the registry and adds a health "
        "summary. It holds no state of its own, so it is a facade over the "
        "hazard above rather than a separate one.",
        disposition=Disposition.STRANGLER_TARGET,
        chooses_operation=True,
        holds_credential=False,
        dials_directly=False,
        tenant_aware=False,
        mutable_singleton=True,
        note="Follows the registry. Nothing new depends on it.",
    ),
    LegacyProviderMechanism(
        location="backend/mcp/connector.py :: MCPConnector",
        mechanism="Abstract base with ``authenticate`` and ``execute_tool``",
        finding="Each connector owns its own authentication and its own "
        "``_authenticated`` flag, so a credential's lifetime is the process's. "
        "There is no session lifecycle, no protocol version, no initialization "
        "and no notion of a scope — it predates all of them.",
        disposition=Disposition.STRANGLER_TARGET,
        chooses_operation=False,
        holds_credential=True,
        dials_directly=False,
        tenant_aware=False,
        mutable_singleton=False,
        note="Replaced by ``McpToolAdapter`` plus ``McpSession``: a scoped "
        "session with an enumerated lifecycle, a negotiated protocol version, "
        "and credential material that arrives per invocation and is not kept.",
    ),
    LegacyProviderMechanism(
        location="backend/mcp/models.py",
        mechanism="``MCPRequest``/``MCPResponse``/``MCPToolDefinition`` dataclasses",
        finding="Plain vocabulary with no authority in it. ``MCPRequest`` carries "
        "a tool name and a params dict and nothing else — which is exactly why "
        "the routes above have nothing to check.",
        disposition=Disposition.REMOVE_LATER,
        chooses_operation=False,
        holds_credential=False,
        dials_directly=False,
        tenant_aware=False,
        mutable_singleton=False,
        note="Harmless in itself. Removable once the V1 MCP path is.",
    ),
    LegacyProviderMechanism(
        location="backend/mcp/connectors/web.py :: WebConnector",
        mechanism="``httpx.AsyncClient(timeout=30.0, follow_redirects=True)`` "
        "behind ``fetch_url`` and ``http_get`` MCP tools",
        finding="**Takes a caller-supplied URL and caller-supplied headers and "
        "follows redirects.** A complete SSRF primitive: any reachable address, "
        "any scheme httpx accepts, and a redirect chain that is never "
        "re-validated. The only guard is a prefix regex in "
        "``safety/guardrails_engine`` which misses decimal, hexadecimal and "
        "octal address forms, IPv4-mapped IPv6, link-local, and every hostname "
        "that merely *resolves* to a private address. Already recorded as the "
        "one genuine hazard by the Phase 4.2 network inventory.",
        disposition=Disposition.SECURITY_HAZARD,
        chooses_operation=True,
        holds_credential=False,
        dials_directly=True,
        tenant_aware=False,
        mutable_singleton=False,
        note="Reachable only through the gated ``/api/v2/mcp/execute``, so it "
        "is inert unless an operator sets the migration flag. It has no "
        "migration path as written: a capability whose operation is 'fetch a "
        "URL the caller names' cannot be expressed in the operation model, "
        "which is the point of the operation model. **Remove the two tools or "
        "replace them with declared, host-pinned operations.** Not changed in "
        "this phase because deleting a tool somebody may use is a decision with "
        "an owner.",
    ),
    LegacyProviderMechanism(
        location="backend/mcp/connectors/filesystem.py",
        mechanism="MCP tools over the local filesystem",
        finding="Reaches the local filesystem rather than a provider. It is not "
        "an outbound provider mechanism at all, so the transport and credential "
        "fabrics have nothing to say about it — what it needs is the worker "
        "sandbox boundary, which is a different concern.",
        disposition=Disposition.STRANGLER_TARGET,
        chooses_operation=True,
        holds_credential=False,
        dials_directly=False,
        tenant_aware=False,
        mutable_singleton=False,
        note="Gated with the rest of the V1 MCP path. A filesystem capability "
        "belongs behind an isolation tier, not behind a transport policy.",
    ),
    # ------------------------------------------------------------------
    # Connectors
    # ------------------------------------------------------------------
    LegacyProviderMechanism(
        location="backend/connectors/github.py :: GitHubConnector",
        mechanism="``httpx.AsyncClient`` against api.github.com with a bearer "
        "token from ``GITHUB_TOKEN``, an in-client retry loop, an ETag cache "
        "and a rate-limit sleep",
        finding="The most complete V1 connector — issues, pull requests, checks, "
        "deployments, releases, branch protection, contents. It reads its token "
        "from the process environment, retries up to three times with backoff, "
        "sleeps on a 403 rate limit, and caches responses by ETag. Every one of "
        "those is a decision the new fabric places elsewhere: the credential in "
        "Phase 4.1, retry in Execution (ADR-031), rate limits as returned facts "
        "(§25), and the socket in Phase 4.2.",
        disposition=Disposition.ADAPTER_TARGET,
        chooses_operation=False,
        holds_credential=True,
        dials_directly=True,
        tenant_aware=False,
        mutable_singleton=False,
        migrated=True,
        note="**Migrated in Phase 4.3, as declarations rather than as code.** "
        "``adapters/connectors/github.py`` contributes an operation catalog and "
        "a translator; the generic ``ConnectorAdapter`` performs them. Five "
        "operations of this connector's surface are covered — get_repository, "
        "get_issue, get_pull_request, create_issue, create_issue_comment. The "
        "V1 client is untouched and still serves every other V1 caller.",
    ),
    LegacyProviderMechanism(
        location="backend/connectors/*.py (jira, slack, teams, confluence, "
        "notion, servicenow, circleci, gitlab_ci, azure_devops, argocd, "
        "jenkins, grafana, loki, prometheus, opentelemetry, terraform, docker, "
        "kubernetes)",
        mechanism="One ``httpx.AsyncClient`` per provider against a fixed base "
        "URL, most with a token from a provider-specific environment variable",
        finding="Roughly eighteen clients following the GitHub connector's "
        "shape. Destinations are fixed at construction rather than "
        "caller-chosen, which bounds them: there is no SSRF surface here, only "
        "an unmigrated one. Ten read a process-wide environment variable for "
        "their credential, which cannot express per-tenant credentials at all. "
        "``docker`` and ``kubernetes`` are different in kind — they write to "
        "``os.environ`` at configure time and talk to a local daemon or "
        "kubeconfig rather than an HTTPS API.",
        disposition=Disposition.ADAPTER_TARGET,
        chooses_operation=False,
        holds_credential=True,
        dials_directly=True,
        tenant_aware=False,
        mutable_singleton=False,
        note="Each becomes a catalog plus a translator, in the order a "
        "deployment needs them. ``docker`` and ``kubernetes`` are **not** "
        "connector-adapter targets: a local daemon socket and a kubeconfig are "
        "not HTTPS transports, and forcing them through one would be the "
        "provider-specific bypass §42 forbids. They need their own seam.",
    ),
    LegacyProviderMechanism(
        location="backend/connectors/base.py :: BaseConnector",
        mechanism="Abstract base with automatic activity recording, plus "
        "``get_operations()`` reflecting over public methods",
        finding="Derives a connector's 'capabilities' by **inspecting its public "
        "method names at runtime**. That is a capability surface nobody "
        "declared: adding a method adds an operation, and the planner then sees "
        "it. It also injects activity recording and audit into every call, "
        "which is the useful half.",
        disposition=Disposition.STRANGLER_TARGET,
        chooses_operation=False,
        holds_credential=False,
        dials_directly=False,
        tenant_aware=False,
        mutable_singleton=False,
        note="Reflection-derived operations are the opposite of the operation "
        "model: ``OperationCatalog`` is constructed whole and cannot gain an "
        "entry by somebody adding a method. Nothing in the new fabric imports "
        "this.",
    ),
    LegacyProviderMechanism(
        location="backend/connectors/registry.py :: ConnectorRegistry",
        mechanism="Module-level mutable singleton, register/get/list, "
        "``register`` **overwrites** an existing entry with a warning",
        finding="A global dictionary where a later registration silently "
        "replaces an earlier one. Whatever holds the name last is what runs, "
        "and the only trace is a log line.",
        disposition=Disposition.STRANGLER_TARGET,
        chooses_operation=True,
        holds_credential=False,
        dials_directly=False,
        tenant_aware=False,
        mutable_singleton=True,
        note="Superseded by the worker directory, which refuses a duplicate "
        "registration rather than overwriting, records lifecycle and trust, and "
        "confines a tenant's registration to that tenant. Nothing in the new "
        "fabric reads this singleton's state (§34).",
    ),
    # ------------------------------------------------------------------
    # Agents and tools
    # ------------------------------------------------------------------
    LegacyProviderMechanism(
        location="backend/agents/registry.py, backend/runtime/agent_registry.py",
        mechanism="Two module-level mutable agent registries",
        finding="Two of them, which is itself the finding: an agent resolved "
        "through one is not necessarily the agent resolved through the other. "
        "Reached from ``/api/agents/run`` and ``/api/agents/delegate``, both of "
        "which read ``tenant_id`` from the request body.",
        disposition=Disposition.STRANGLER_TARGET,
        chooses_operation=True,
        holds_credential=False,
        dials_directly=False,
        tenant_aware=False,
        mutable_singleton=True,
        note="``AgentAdapter`` is the governed seam and deliberately performs "
        "nothing until an agent runtime is attached — and refuses a *mutating* "
        "binding unless that runtime declares it confines effects (§31).",
    ),
    LegacyProviderMechanism(
        location="backend/tools/tool_registry.py, "
        "backend/tools/tool_execution_engine.py",
        mechanism="Module-level tool registry and an execution engine over it",
        finding="Tool selection and execution outside the capability model. "
        "Reached from the V1 cognition and orchestrator paths, all of which are "
        "gated.",
        disposition=Disposition.STRANGLER_TARGET,
        chooses_operation=True,
        holds_credential=False,
        dials_directly=False,
        tenant_aware=False,
        mutable_singleton=True,
        note="A tool is a capability. Migration means registering capabilities "
        "in BC-8, not bridging a registry.",
    ),
    # ------------------------------------------------------------------
    # What the fabric actually depends on
    # ------------------------------------------------------------------
    LegacyProviderMechanism(
        location="backend/platform/transport (Phase 4.2)",
        mechanism="``TransportBroker``, endpoint model, SSRF policy, pinning, "
        "connection policy, header rules, resource budgets",
        finding="The only route to the network the new adapters have. Extended "
        "in this phase by two additive fields on ``TransportOutcome`` — "
        "``body`` and ``response_headers`` — because an adapter cannot normalise "
        "or validate an answer it cannot see. Both are excluded from "
        "``to_dict``, and credential-bearing header names are refused at "
        "construction rather than filtered later.",
        disposition=Disposition.SAFE_TO_REUSE,
        chooses_operation=False,
        holds_credential=False,
        dials_directly=True,
        tenant_aware=True,
        mutable_singleton=False,
        note="No transport adapter is registered. Every dial refuses "
        "``transport_unavailable`` until Phase 4.4 attaches one.",
    ),
    LegacyProviderMechanism(
        location="backend/platform/credentials (Phase 4.1)",
        mechanism="``CredentialBroker``, ``CredentialRequest``, "
        "``CredentialMaterial``, action-digest binding",
        finding="The only source of provider secrets for the new adapters, and "
        "unchanged by this phase. Material reaches an adapter on the "
        "``ProviderAuthority`` and is handed to transport without being written "
        "down anywhere in between.",
        disposition=Disposition.SAFE_TO_REUSE,
        chooses_operation=False,
        holds_credential=True,
        dials_directly=False,
        tenant_aware=True,
        mutable_singleton=False,
        note="No vendor adapter is registered. Every acquisition refuses "
        "``credential_no_provider``.",
    ),
    LegacyProviderMechanism(
        location="backend/infrastructure/vault/client.py :: VaultClient",
        mechanism="httpx against ``VAULT_ADDR`` with ``VAULT_TOKEN``",
        finding="A working Vault client with no tenant scoping and no "
        "connection to the authority chain. Already named by the Phase 4.1 "
        "inventory as the natural first credential adapter.",
        disposition=Disposition.ADAPTER_TARGET,
        chooses_operation=False,
        holds_credential=True,
        dials_directly=True,
        tenant_aware=False,
        mutable_singleton=False,
        note="A ``CredentialAdapter`` target, not a ``ProviderAdapter`` one. "
        "Out of scope for 4.3: this phase commits to no credential vendor.",
    ),
)

#: What was actually migrated in this phase. One entry, and it is meant to be
#: one: §13 asks for exactly one reference connector, so that the pattern is
#: demonstrated by something real rather than asserted by something broad.
MIGRATED = tuple(m for m in LEGACY_PROVIDER_MECHANISMS if m.migrated)


def hazards() -> tuple:
    """Mechanisms needing a decision before a migration, rather than during one."""
    return tuple(
        m
        for m in LEGACY_PROVIDER_MECHANISMS
        if m.disposition is Disposition.SECURITY_HAZARD
    )


def by_disposition(disposition: Disposition) -> tuple:
    return tuple(m for m in LEGACY_PROVIDER_MECHANISMS if m.disposition is disposition)


def operation_choosers() -> tuple:
    """Mechanisms that decide *what* is performed.

    The set that matters most. Every one of them is a place where the capability
    that was authorized and the operation that ran can differ, which is the
    defect the whole adapter fabric exists to remove.
    """
    return tuple(m for m in LEGACY_PROVIDER_MECHANISMS if m.chooses_operation)


def summary() -> dict:
    """A queryable form, so the gap is inspectable rather than only readable."""
    return {
        "total": len(LEGACY_PROVIDER_MECHANISMS),
        "migrated": [m.location for m in MIGRATED],
        "hazards": [m.location for m in hazards()],
        "choose_their_own_operation": [m.location for m in operation_choosers()],
        "hold_their_own_credential": [
            m.location for m in LEGACY_PROVIDER_MECHANISMS if m.holds_credential
        ],
        "dial_directly": [
            m.location for m in LEGACY_PROVIDER_MECHANISMS if m.dials_directly
        ],
        "mutable_singletons": [
            m.location for m in LEGACY_PROVIDER_MECHANISMS if m.mutable_singleton
        ],
        "untenanted": [
            m.location for m in LEGACY_PROVIDER_MECHANISMS if not m.tenant_aware
        ],
        "by_disposition": {
            d.value: [m.location for m in by_disposition(d)] for d in Disposition
        },
        "note": (
            "None of these bypasses the invocation gateway; every V1 execution "
            "route is gated off by default (ADR-039). They bypass the provider "
            "fabric: they choose their own operations, hold their own "
            "credentials and dial by their own means."
        ),
    }
