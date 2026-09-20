# The CortexPrime connector architecture (governed plane)

Status: established by Phase 11.1-K (ADR-125). Kubernetes is the reference
implementation. **This is the only connector architecture.** The V1 connectors
under `backend/connectors/` are frozen legacy: their writes are gated
(`guard_raw_request`, `guard_legacy_execution`) and none of them is a model for
new work.

> Simple outside, sophisticated inside. An operator configures a *connection*
> (who, where, which credential source) and reads one health line. Everything
> else — registration, schemas, permissions, retries, rate limits, audit,
> verification — is derived from one manifest and enforced by the platform.

## 1. What a connector is

A connector is five things, all composed from one `CORTEX_CONNECTOR_FACTORIES`
entry (a function `extension(environment) -> dict | None`):

| Key | What it is | Kubernetes reference |
|---|---|---|
| `connectors` | builders of the provider adapters (catalog + transport) | `build_kubernetes_connector`, the two contained worker connectors |
| `manifests` | one `ConnectorManifest`: every capability the connector ships | `kubernetes_manifest()` — 8 reads, 2 writes |
| `connection_scopes` | which tenant may reach which provider targets | tenant A → `{namespace}` for 3 providers |
| `credential_provider_builders` | credential adapters built once the transport broker exists | Vault Kubernetes secrets engine, one role per provider |
| `health_probes` | `connector_id -> (runtime) -> probe()` | `kubernetes_health_probe` |

It returns `None` when its connection is not configured: a deployment that did
not ask for the connector does not get it.

## 2. The typed contract (`backend/contracts/connector_manifest.py`)

Each `CapabilityManifest` declares:

- **identity**: `capability_id` (`platform.<operation>`), `version`, `operation`, `provider`
- **description**: written for the model and the operator — what it does and *when to use it*
- **category**: observation / signal / health / remediation
- **profile** (from the adapter's `CapabilityProfile`): risk, reversibility,
  compensation, autonomy ceiling, verification requirement, timeout, side-effect class
- **required_permissions**: provider permission strings (`kubernetes:<resource>:<verb>`)
- **target_parameter**: which input names the tenant-scoped target (`namespace`)
- derived: `mutates`, `retry` (`SAFE` for reads, `NEVER` for writes)

Input and output schemas are derived from the adapter's operation spec
(`backend/api/connector_schema.py`) and registered as content-addressed
references (sha256), so a contract change is a new version, never a silent edit.

## 3. Registration (`backend/api/connector_commissioning.py`)

At boot, every manifest is commissioned into the durable capability registry:
register → validate → enable → trust, idempotently.

- identical contract already registered → `already_current`
- a *different* contract under the same version → `conflict` (never overwritten;
  health reports MISCONFIGURED and names it)
- a capability whose provider is not composed (e.g. a worker not deployed) →
  `skipped`, reported as unavailable with the reason

## 4. The one execution path

Every invocation, read or write, goes through
`SecureCapabilityInvocationGateway.admit`:
identity → tenant → capability → **input (schema + connection scope)** → digest
→ approval → **rate limit** → credential → transport broker (SSRF + DNS pinning,
TLS verification) → adapter → normalizer. There is no raw client, no arbitrary
request, no shell. A model can only name a registered capability.

- **Writes** run in a *contained worker* (own process, own ServiceAccount,
  non-root, read-only rootfs, egress policy) that holds no standing credential:
  the platform presents a per-action credential. Approval is digest-bound;
  outcomes are established by independent verification, never the executor's
  word. Writes are **never retried**; an UNKNOWN outcome is reconciled by
  verification.
- **Reads** are retried only on retryable failures, honouring the provider's
  `Retry-After` as a floor.

## 5. Credentials

The production source is Vault. The runtime authenticates to Vault with its own
pod identity (Kubernetes auth; no static Vault token) and asks a secrets engine
for a short-lived provider credential per acquisition, per provider role.
Material is revealed at exactly one site (the HTTP adapter's header
construction). Static credentials exist only for development and are refused
in production.

## 6. Tenancy

A provider target (namespace, project, repository…) is **not** a tenant. A
*connection* binds one CortexPrime tenant to one provider target. It is
enforced twice, independently:

1. the gateway input stage (`ConnectionScopeValidator`): a target outside the
   invoking tenant's connection is refused before a credential is acquired;
2. the provider: the credential minted for that tenant is authorised (RBAC)
   only inside that target.

## 7. Errors (`backend/contracts/connector_errors.py`)

Every failure maps to one of: AUTHENTICATION_FAILED, AUTHORIZATION_DENIED,
NOT_FOUND, INVALID_REQUEST, RATE_LIMITED, TIMEOUT, NETWORK_FAILURE,
PROVIDER_UNAVAILABLE, CONFLICT, VERIFICATION_FAILED, INSUFFICIENT_EVIDENCE,
INTERNAL_ERROR.

## 8. Health (`backend/api/connector_health.py`)

States: CONNECTED, DEGRADED, AUTHENTICATION_REQUIRED, RATE_LIMITED, UNAVAILABLE,
MISCONFIGURED, DISABLED. A probe returns named checks; the connector's state is
the worst failing check. Health is produced **through the governed path** (the
Kubernetes probe issues governed `access.review` reads with the connection's own
credential), so it tests what production actually uses. Each capability is
listed as available or unavailable with the reason. Product API:
`GET /api/v1/connectors`, `GET /api/v1/connectors/{id}` (tenant-scoped: another
tenant's connection reads DISABLED with no detail).

## 9. Observability

Prometheus on `CORTEX_METRICS_PORT`: `cortex_connector_health{connector,state}`,
`cortex_gateway_rate_limited{scope,provider}` and the gateway/transport metrics.
Label names that could carry a credential are dropped; values are capped.

## 10. Adding the next connector — checklist

1. Adapter: operation specs + normalizer + `CapabilityProfile` per operation
   (reads first; a write only with a contained worker and independent verification).
2. `backend/api/<name>_connector.py`: manifest, connection (`from_env`),
   extension, health probe. Copy `kubernetes_connector.py`'s shape.
3. Credentials: a Vault-backed adapter for the provider's credential type.
4. Chart values for the connection; setup script for the provider side.
5. Tests: `tests/connector_fabric/` (contract, scope, errors, health) +
   a real-provider harness with the stages in
   `scripts/phase111k_kubernetes_connector_harness.py`.
6. LOCK only when every gate in ADR-125's checklist is proven against the real provider.
