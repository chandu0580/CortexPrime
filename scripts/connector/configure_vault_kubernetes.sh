#!/bin/sh
# Configure Vault for the CortexPrime Kubernetes connector (Phase 11.1-K).
#
# Run ONCE per connection, by the operator who administers Vault, with the
# `vault` CLI and an administrative VAULT_TOKEN. Idempotent: re-running it
# converges to the same configuration.
#
#   CONNECTION_NAMESPACE=checkout RELEASE_NAMESPACE=cortexprime \
#     VAULT_ADDR=https://vault.example:8200 VAULT_TOKEN=<admin> \
#     sh scripts/connector/configure_vault_kubernetes.sh
#
# What it sets up, and nothing else:
#   * Vault Kubernetes AUTH  -- CortexPrime's runtime pod logs in with its own
#     projected ServiceAccount token (no static Vault token anywhere).
#   * Vault Kubernetes SECRETS ENGINE -- mints a short-lived token, per action,
#     for exactly one of three namespace-confined ServiceAccounts the Helm chart
#     creates (reader / rollbacker / restarter).
#   * One policy allowing the runtime to request exactly those three roles.
#
# Assumes Vault runs in the cluster (it then uses its own pod identity to reach
# the API server). For a Vault outside the cluster, set KUBERNETES_HOST,
# KUBERNETES_CA_CERT (path) and TOKEN_REVIEWER_JWT (path) before running.
#
# Vault's own prerequisites (not created here): its ServiceAccount must be
# bound to system:auth-delegator (TokenReview, for Kubernetes auth), and the
# Helm chart grants it `create serviceaccounts/token` for exactly the three
# CortexPrime ServiceAccounts in the connected namespace.
set -eu

: "${CONNECTION_NAMESPACE:?set CONNECTION_NAMESPACE (the namespace CortexPrime is connected to)}"
: "${RELEASE_NAMESPACE:?set RELEASE_NAMESPACE (where the cortexprime-governed chart is installed)}"
AUTH_MOUNT="${AUTH_MOUNT:-kubernetes}"
SECRETS_MOUNT="${SECRETS_MOUNT:-kubernetes}"
AUTH_ROLE="${AUTH_ROLE:-cortexprime}"
RUNTIME_SA="${RUNTIME_SA:-cortexprime-governed}"
READER_ROLE="${READER_ROLE:-cortexprime-reader}"
ROLLBACK_ROLE="${ROLLBACK_ROLE:-cortexprime-rollbacker}"
RESTART_ROLE="${RESTART_ROLE:-cortexprime-restarter}"
TOKEN_TTL="${TOKEN_TTL:-10m}"
POLICY="cortexprime-kubernetes-${CONNECTION_NAMESPACE}"

enabled() { vault "$1" list -format=json | grep -q "\"$2/\""; }

echo "==> Kubernetes auth (the runtime's own identity)"
enabled auth "$AUTH_MOUNT" || vault auth enable -path="$AUTH_MOUNT" kubernetes
if [ -n "${KUBERNETES_HOST:-}" ]; then
  vault write "auth/${AUTH_MOUNT}/config" kubernetes_host="$KUBERNETES_HOST" \
    kubernetes_ca_cert=@"${KUBERNETES_CA_CERT:?}" token_reviewer_jwt=@"${TOKEN_REVIEWER_JWT:?}"
else
  vault write "auth/${AUTH_MOUNT}/config" \
    kubernetes_host="https://${KUBERNETES_SERVICE_HOST:?}:${KUBERNETES_SERVICE_PORT:-443}"
fi

echo "==> Kubernetes secrets engine (per-action ServiceAccount tokens)"
enabled secrets "$SECRETS_MOUNT" || vault secrets enable -path="$SECRETS_MOUNT" kubernetes
if [ -n "${KUBERNETES_HOST:-}" ]; then
  vault write "${SECRETS_MOUNT}/config" kubernetes_host="$KUBERNETES_HOST" \
    kubernetes_ca_cert=@"${KUBERNETES_CA_CERT:?}" service_account_jwt=@"${TOKEN_REVIEWER_JWT:?}"
else
  vault write -f "${SECRETS_MOUNT}/config"
fi

for pair in "${READER_ROLE}:cortexprime-reader" "${ROLLBACK_ROLE}:cortexprime-rollbacker" \
            "${RESTART_ROLE}:cortexprime-restarter"; do
  role="${pair%%:*}"; sa="${pair##*:}"
  echo "    role ${role} -> ServiceAccount ${CONNECTION_NAMESPACE}/${sa}"
  vault write "${SECRETS_MOUNT}/roles/${role}" \
    allowed_kubernetes_namespaces="${CONNECTION_NAMESPACE}" \
    service_account_name="${sa}" \
    token_default_ttl="${TOKEN_TTL}" token_max_ttl=1h
done

echo "==> policy ${POLICY} (exactly three roles, update only)"
vault policy write "$POLICY" - <<EOF
path "${SECRETS_MOUNT}/creds/${READER_ROLE}"   { capabilities = ["update"] }
path "${SECRETS_MOUNT}/creds/${ROLLBACK_ROLE}" { capabilities = ["update"] }
path "${SECRETS_MOUNT}/creds/${RESTART_ROLE}"  { capabilities = ["update"] }
EOF

echo "==> auth role ${AUTH_ROLE}: ${RELEASE_NAMESPACE}/${RUNTIME_SA} may use ${POLICY}"
vault write "auth/${AUTH_MOUNT}/role/${AUTH_ROLE}" \
  bound_service_account_names="${RUNTIME_SA}" \
  bound_service_account_namespaces="${RELEASE_NAMESPACE}" \
  policies="${POLICY}" ttl=1h max_ttl=4h

echo "Vault is configured for connection ${CONNECTION_NAMESPACE}."
