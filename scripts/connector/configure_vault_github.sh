#!/bin/sh
# Configure Vault for the CortexPrime GitHub connector (Phase 11.2).
#
# Run ONCE per connection, by the operator who administers Vault, with the
# `vault` CLI and an administrative VAULT_TOKEN. Idempotent: re-running it
# converges to the same configuration.
#
#   TENANT=tenant-a ENVIRONMENT=production \
#     VAULT_ADDR=https://vault.example:8200 VAULT_TOKEN=<admin> \
#     sh scripts/connector/configure_vault_github.sh
#
# What it sets up, and nothing else:
#   * one policy granting READ on exactly this tenant's GitHub credential
#     paths, for exactly this environment;
#   * that policy added to the Kubernetes auth role CortexPrime already logs in
#     with, beside whatever policies it already carries.
#
# What it does NOT do: it never writes the credential. The operator stores the
# GitHub App private key (production) or the token (development) themselves:
#
#   vault kv put secret/cortexprime/github/app app_id=<id> private_key=@key.pem
#   vault kv put secret/cortexprime/providers/<tenant>/<env>/github token=-
#
# (`token=-` makes the CLI read the value from stdin, so the credential never
# appears in a shell history or a process list.)
set -eu

: "${TENANT:?set TENANT (the CortexPrime tenant that owns this GitHub connection)}"
: "${ENVIRONMENT:?set ENVIRONMENT (development, staging or production)}"
AUTH_MOUNT="${AUTH_MOUNT:-kubernetes}"
AUTH_ROLE="${AUTH_ROLE:-cortexprime}"
# The auth role is rewritten whole (Vault replaces a role rather than patching
# it), so its bindings are stated here exactly as the Kubernetes connector's
# script states them. Anything omitted would be silently dropped.
RELEASE_NAMESPACE="${RELEASE_NAMESPACE:-cortexprime}"
RUNTIME_SA="${RUNTIME_SA:-cortexprime-governed}"
ROLE_TTL="${ROLE_TTL:-1h}"
ROLE_MAX_TTL="${ROLE_MAX_TTL:-4h}"
KV_MOUNT="${KV_MOUNT:-secret}"
KV_PREFIX="${KV_PREFIX:-cortexprime/providers}"
APP_SECRET_PATH="${APP_SECRET_PATH:-cortexprime/github/app}"
POLICY="cortexprime-github-${TENANT}-${ENVIRONMENT}"

echo "==> policy ${POLICY} (read only, this tenant, this environment)"
vault policy write "$POLICY" - <<EOF
# The token (or App key) for one tenant's GitHub connection. READ only: the
# platform consumes credentials and never writes them.
path "${KV_MOUNT}/data/${KV_PREFIX}/${TENANT}/${ENVIRONMENT}/github" {
  capabilities = ["read"]
}
path "${KV_MOUNT}/data/${KV_PREFIX}/${TENANT}/${ENVIRONMENT}/github-contained" {
  capabilities = ["read"]
}
path "${KV_MOUNT}/data/${APP_SECRET_PATH}" {
  capabilities = ["read"]
}
EOF

echo "==> auth role ${AUTH_ROLE}: add ${POLICY} to the policies it already has"
CURRENT=$(vault read -field=token_policies -format=json "auth/${AUTH_MOUNT}/role/${AUTH_ROLE}" 2>/dev/null \
          | tr -d '[]"' | tr ',' '\n' | sed 's/^ *//;s/ *$//' | grep -v '^$' | grep -v "^${POLICY}$" || true)
POLICIES=$(printf '%s\n%s\n' "$CURRENT" "$POLICY" | grep -v '^$' | paste -sd, -)
vault write "auth/${AUTH_MOUNT}/role/${AUTH_ROLE}" policies="$POLICIES" >/dev/null
echo "    policies now: ${POLICIES}"

echo "Vault is configured for the GitHub connection of ${TENANT} (${ENVIRONMENT})."
