"""V1 credential surfaces: what exists, what it does, and what it does not do.

Why an inventory and not a rewrite
------------------------------------
Phase 4.1 builds the credential fabric. It does not migrate ten V1 modules onto
it, and rewriting unrelated subsystems on the strength of an architecture
document is how a security phase becomes an outage.

So each pre-existing credential path is named here with what was actually found
by reading it. Some are hazards, some are already inert, and one is a genuine
finding that should be dealt with before Phase 4.2 attaches a transport.

The distinction that matters for every entry
----------------------------------------------
None of these bypasses the **invocation gateway** — that is the property the
whole of Phase 3 established, and Phase 4.1 does not weaken it. What they bypass
is the *credential fabric*: they obtain provider secrets by their own means. A V1
connector holding a GitHub token can still only be reached through V1 routes,
and every V1 execution route is gated (ADR-039).

So the exposure is: a leaked V1 secret authenticates to a provider. It does not
authorize a CortexPrime action. That is precisely the separation Phase 4.1 exists
to make true, and it is why these can be migrated in order rather than at once.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "LegacyCredentialSurface",
    "LEGACY_CREDENTIAL_SURFACES",
    "unmigrated_surfaces",
    "hazards",
]


@dataclass(frozen=True)
class LegacyCredentialSurface:
    """One pre-existing path that obtains or holds a provider secret."""

    location: str
    mechanism: str
    finding: str
    tenant_aware: bool
    persists_secret: bool
    reachable_without_gateway: bool
    hazard: bool
    """Whether this needs action before Phase 4.2 rather than during the ordinary
    migration. Reserved for findings that are dangerous *now*, not merely
    unmigrated."""

    disposition: str


LEGACY_CREDENTIAL_SURFACES: tuple = (
    LegacyCredentialSurface(
        location="backend/auth/credential_store.py :: CredentialStore",
        mechanism="Fernet-encrypted files under data/credentials/, key from "
        "CREDENTIAL_ENCRYPTION_KEY or a generated .encryption_key file",
        finding="Decrypts **every** stored credential into a process-wide "
        "dictionary at construction (``_load_all``), keyed by a bare "
        "credential_id with no tenant anywhere in the type. A module-level "
        "singleton via ``get_credential_store()``. This is the global "
        "credential dictionary and the ambient-tenant lookup that Phase 4.1 "
        "forbids — in one object.",
        tenant_aware=False,
        persists_secret=True,
        reachable_without_gateway=True,
        hazard=True,
        disposition="**Quarantined in Phase 4.4.** Still unreferenced — "
        "re-verified by search — so closing it broke no caller. "
        "``CredentialStore`` now requires ``allow_non_production=True`` to "
        "construct, and ``get_credential_store()`` refuses outright, taking "
        "the memoising module singleton with it. Not deleted, because "
        "deleting a credential store is a decision with somebody's encrypted "
        "files and key attached to it — quarantined so that wiring it into "
        "a production path is something a reviewer cannot miss.",
    ),
    LegacyCredentialSurface(
        location="backend/connectors/*.py (github, jira, slack, teams, "
        "confluence, notion, servicenow, circleci, gitlab_ci, docker)",
        mechanism="``os.getenv(PROVIDER_TOKEN_ENV)`` at connector construction",
        finding="Ten connectors read a process-wide environment variable for "
        "their token. One process holds one token per provider for every "
        "tenant, which cannot express per-tenant credentials at all — and "
        "reading worker-environment credentials is explicitly what the fabric "
        "refuses to do.",
        tenant_aware=False,
        persists_secret=False,
        reachable_without_gateway=True,
        hazard=False,
        disposition="Strangler targets. Phase 4.3 replaced the first of them "
        "(GitHub) as an ``OperationCatalog`` behind the generic "
        "``ConnectorAdapter``; the replacement receives ``CredentialMaterial`` "
        "on the ``ProviderAuthority`` rather than reading the environment. The "
        "rest are inventoried in ``legacy_provider_inventory``. Every V1 route "
        "reaching them is gated (ADR-039), so they are inert unless an operator "
        "turns the flag on.",
    ),
    LegacyCredentialSurface(
        location="backend/infrastructure/vault/client.py :: VaultClient",
        mechanism="``VAULT_ADDR`` / ``VAULT_TOKEN`` from the environment, "
        "defaulting to http://localhost:8200",
        finding="A working Vault client with no tenant scoping and no "
        "connection to the authority chain. Its default address is localhost, "
        "so a misconfigured deployment reads from nothing rather than from the "
        "wrong vault — which is the safer of the two failure modes.",
        tenant_aware=False,
        persists_secret=False,
        reachable_without_gateway=True,
        hazard=False,
        disposition="**Superseded in Phase 4.4, and not by wrapping it.** "
        "``platform/credentials/vault.py`` speaks Vault's KV v2 HTTP API "
        "through the transport broker instead. Reading this client in 4.4 "
        "found three reasons wrapping was wrong: it is ``hvac``-based (not "
        "httpx, as the Phase 4.2 network inventory recorded — corrected "
        "there) so it would have been a second outbound path with no address "
        "policy; it is a module singleton holding one ``VAULT_TOKEN``; and "
        "``get_secret`` returns ``None`` on every exception, so a missing "
        "secret, an unreachable Vault and a rejected token are one answer. "
        "This client is untouched and still serves whatever else uses it.",
    ),
    LegacyCredentialSurface(
        location="backend/security_center/models.py :: SecretReference",
        mechanism="Metadata describing where a secret lives (provider + path)",
        finding="Metadata only — it holds no value, which is the right shape. "
        "It is a parallel vocabulary to ``CredentialRef`` rather than a leak.",
        tenant_aware=False,
        persists_secret=False,
        reachable_without_gateway=False,
        hazard=False,
        disposition="Not a second credential abstraction in the sense Phase 4.1 "
        "forbids: it describes secret *inventory* for the security centre UI, "
        "not credential *acquisition* for execution. Left alone. If the two "
        "ever need to converge, ``CredentialRef`` is the authoritative one.",
    ),
    LegacyCredentialSurface(
        location="backend/api/security_center_routes.py :: GET/POST /secrets",
        mechanism="Lists and registers ``SecretReference`` metadata",
        finding="Returns ``to_dict()`` of metadata objects that hold no secret "
        "value. No reveal endpoint, no value field. Checked by reading the "
        "model, not by assuming.",
        tenant_aware=False,
        persists_secret=False,
        reachable_without_gateway=False,
        hazard=False,
        disposition="Acceptable as inventory. Phase 4.1 adds no credential API "
        "at all — no listing, no reveal, no raw retrieval — so this remains the "
        "only secret-adjacent surface and it exposes only pointers.",
    ),
    LegacyCredentialSurface(
        location="backend/api/enterprise_credentials_routes.py",
        mechanism="Connector credential *health* monitoring",
        finding="Reports whether connector credentials work. Returns check "
        "results, not credentials.",
        tenant_aware=False,
        persists_secret=False,
        reachable_without_gateway=False,
        hazard=False,
        disposition="Observability over V1 connectors. Follows those connectors "
        "when they migrate.",
    ),
)


def unmigrated_surfaces() -> tuple:
    """Everything not yet on the fabric. All of it, today — nothing was migrated."""
    return LEGACY_CREDENTIAL_SURFACES


def hazards() -> tuple:
    """Surfaces needing a decision before Phase 4.2, rather than during it."""
    return tuple(s for s in LEGACY_CREDENTIAL_SURFACES if s.hazard)


def summary() -> dict:
    """A queryable form, so the gap is inspectable rather than only readable."""
    return {
        "total": len(LEGACY_CREDENTIAL_SURFACES),
        "hazards": [s.location for s in hazards()],
        "untenanted": [
            s.location for s in LEGACY_CREDENTIAL_SURFACES if not s.tenant_aware
        ],
        "persist_secrets": [
            s.location for s in LEGACY_CREDENTIAL_SURFACES if s.persists_secret
        ],
        "migrated_to_fabric": 1,
        "note": (
            "None of these bypasses the invocation gateway. They bypass the "
            "credential fabric: they obtain provider secrets by their own means. "
            "A leaked V1 secret authenticates to a provider; it does not "
            "authorize a CortexPrime action."
        ),
    }
