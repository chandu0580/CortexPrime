# Kubernetes connector — operator runbook

Connect CortexPrime to one Kubernetes namespace, read its health, and fix what
it reports. Architecture: `docs/CONNECTOR_ARCHITECTURE.md`. Decision record:
`docs/adr/ADR-125-phase-11-1-kubernetes-reference-connector.md`.

## What you need before installing

| Prerequisite | Why |
|---|---|
| Kubernetes 1.27+ with NetworkPolicy enforcement | the write workers' egress is restricted to the API server |
| PostgreSQL 16+ with the **pgvector** extension available, TLS on | the durable store; the migration Job runs `CREATE EXTENSION vector` |
| A Secret in the release namespace with key `url` = `postgresql://…?sslmode=require` | production refuses a database connection without TLS |
| HashiCorp Vault (TLS), reachable from the cluster | the only production credential source |
| Vault's ServiceAccount bound to `system:auth-delegator` | Vault's Kubernetes auth method validates the runtime's pod identity (TokenReview) |

No static Kubernetes token, kubeconfig or Vault token is ever given to CortexPrime.

## Install (one command after the one-time Vault step)

1. **Configure Vault once** for the connection (the Vault administrator runs this;
   idempotent):

   ```sh
   CONNECTION_NAMESPACE=<namespace> RELEASE_NAMESPACE=cortexprime \
   VAULT_ADDR=https://vault.example:8200 VAULT_TOKEN=<admin token> \
     sh scripts/connector/configure_vault_kubernetes.sh
   ```

   It enables Kubernetes auth + the Kubernetes secrets engine, creates three
   roles (reader / rollbacker / restarter) confined to that namespace with a 10
   minute default token TTL, and one policy the runtime may use. Nothing else.

2. **Install the chart:**

   ```sh
   helm upgrade --install cortexprime ./helm/cortexprime-governed -n cortexprime --create-namespace \
     --set connection.tenant=<tenant id> --set connection.namespace=<namespace> \
     --set database.existingSecret=<db secret> \
     --set vault.address=https://vault.vault.svc:8200 --set vault.caSecret=<ca secret> --wait
   ```

   The chart refuses to render without the four required values and names the
   one that is missing. It creates, in the connected namespace only: three
   ServiceAccounts (no automounted token, no token Secret), three namespace
   Roles, the two contained workers and their egress policy; and a Role letting
   Vault mint tokens for exactly those three ServiceAccounts. Nothing
   cluster-wide.

3. **Check health:** `GET /api/v1/connectors/kubernetes` with a token for the
   connection's tenant (see the chart's NOTES). `CONNECTED` means every shipped
   capability's requirements hold right now.

If the install cannot read `default/kubernetes` Endpoints (a dry run, or
credentials without that read), it **refuses** rather than deploying write
workers without their egress NetworkPolicy; pass the address yourself:
`--set workers.apiServerEndpoint=$(kubectl -n default get endpoints kubernetes -o jsonpath='{.subsets[0].addresses[0].ip}')`.

Optional values: `model.*` (a hosted model for investigation/remediation
proposals), `rateLimit.*`, `remediation.compensableAutonomy` (off by default:
every rollback needs a human), `health.intervalSeconds` (default 300).

## Reading health

| State | Meaning | What to do |
|---|---|---|
| CONNECTED | all checks pass | nothing |
| DEGRADED | reads work; some capability is unavailable (a worker is down, a permission partly missing) | the `unavailable` list names each capability and why |
| MISCONFIGURED | the API answers but the connection cannot work as declared | the check names the missing permission, contract conflict or refusal reason |
| AUTHENTICATION_REQUIRED | a credential was refused (Vault role, Vault auth, provider 401) | fix the Vault role / auth binding named in the check |
| RATE_LIMITED | the platform's own limiter or the provider refused for rate | wait, or raise `rateLimit.*` deliberately |
| UNAVAILABLE | the API server, Vault or a worker could not be reached | check network, Vault, API server |
| DISABLED | your tenant has no connection for this connector | install a connection for your tenant |

Health is produced through the same governed path production uses (a governed
`access.review` per required permission, with the connection's own
Vault-issued credential), so CONNECTED is evidence, not an assumption.

## Common failures and their fixes

| Health says | Cause | Fix |
|---|---|---|
| `missing: kubernetes:pods:list, …` | the reader's RoleBinding was removed or edited | `helm upgrade` restores it |
| credential-class refusal naming Vault | the Vault role or policy was removed; Vault restarted with in-memory storage | re-run `configure_vault_kubernetes.sh` |
| `authorization refused: environment_not_permitted` | a capability registered for another environment | the runtime's `environment` value must match the deployment's |
| `worker unreachable` for rollback/restart | the worker Deployment is down or its NetworkPolicy blocks the runtime | `kubectl -n <ns> get deploy contained-rollback-worker` |
| a contract `conflict` in commissioning | a different contract was registered under the same capability version | never edit a shipped version; bump the version |

## Rotating and revoking

- Kubernetes tokens are minted per action by Vault and expire (default 10
  minutes). There is nothing to rotate. To revoke all access immediately:
  `vault lease revoke -prefix kubernetes/creds/` and/or delete the Vault role.
- The runtime's Vault login uses its projected ServiceAccount token (re-read on
  every login), so rotating it needs nothing.
- The product API's signing secret is generated once and kept across upgrades;
  rotating it (`auth.existingSecret`) signs every user out.

## Limits (stated, not implied)

- One connection (tenant ↔ namespace) per deployment.
- One runtime replica (the governed loops hold leader-elected roles).
- The rate limiter is per process.
- A write worker's own RBAC is verified at provisioning and by the worker at
  execution, not by health (health would have to handle the worker's
  credential in-process, which the architecture forbids).
