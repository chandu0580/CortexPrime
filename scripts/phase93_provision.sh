#!/usr/bin/env bash
# Phase 9.3 (ADR-083) — provision the disposable evidence environment.
#
# Creates, from nothing:
#   * a disposable k3d cluster (k3s in docker) with an isolated namespace,
#     a deployment to watch, and an RBAC-scoped ServiceAccount whose Role
#     grants get/list/WATCH on pods in that namespace and nothing else;
#   * a fresh Postgres database migrated to head.
#
# Everything it creates is disposable and named for this phase. It touches no
# production cluster and no production credential; the ServiceAccount token is
# short-lived and scoped to one namespace of a cluster that is deleted at the end.
#
# Usage:   bash scripts/phase93_provision.sh            (create + print env)
#          bash scripts/phase93_provision.sh teardown   (delete everything)

set -euo pipefail

CLUSTER=cortex-p93
NAMESPACE=cortex-p93
SA=cortex-watcher
PG_CONTAINER=cortex-p93-pg
PG_PORT=55432
PG_USER=cortex
PG_PASS=cortex
PG_DB=cortex_p93
# pgvector, not plain postgres: an early migration does CREATE EXTENSION vector,
# so a stock image fails at upgrade head rather than at anything interesting.
PG_IMAGE=pgvector/pgvector:pg16
K3D="${K3D:-$HOME/bin/k3d.exe}"
KUBECONFIG_PATH="${KUBECONFIG_PATH:-$PWD/.phase93-kubeconfig}"
CA_PATH="${CA_PATH:-$PWD/.phase93-ca.crt}"

if [ "${1:-create}" = "teardown" ]; then
  "$K3D" cluster delete "$CLUSTER" >/dev/null 2>&1 || true
  docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
  rm -f "$KUBECONFIG_PATH" "$CA_PATH"
  echo "phase 9.3 environment removed"
  exit 0
fi

echo "==> k3d cluster ${CLUSTER}"
if ! "$K3D" cluster list "$CLUSTER" >/dev/null 2>&1; then
  "$K3D" cluster create "$CLUSTER" --servers 1 --agents 0 --no-lb --wait
fi
"$K3D" kubeconfig get "$CLUSTER" > "$KUBECONFIG_PATH"
# k3d writes ``host.docker.internal`` as the server address, which on this host
# resolves to the LAN interface and is not reachable from the host itself.
# Rewrite it to the literal loopback the API port is actually published on —
# which k3s also puts in the certificate SANs, so TLS still verifies against the
# cluster CA. Turning verification off instead is not an option that exists: the
# transport has no such flag.
API_PORT=$(docker port "k3d-${CLUSTER}-server-0" 6443/tcp | head -1 | sed 's/.*://')
python -c "
import re, sys
path, port = sys.argv[1], sys.argv[2]
text = open(path, encoding='utf-8').read()
text = re.sub(r'server:\s*https://[^\s]+', 'server: https://127.0.0.1:' + port, text)
open(path, 'w', encoding='utf-8').write(text)
" "$KUBECONFIG_PATH" "$API_PORT"
export KUBECONFIG="$KUBECONFIG_PATH"

echo "==> waiting for the API server"
for _ in $(seq 1 60); do
  kubectl get namespace default >/dev/null 2>&1 && break
  sleep 2
done
kubectl version -o json | python -c "import sys,json;print('   k3s server:', json.load(sys.stdin)['serverVersion']['gitVersion'])"

echo "==> namespace, workload, RBAC"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n "$NAMESPACE" create serviceaccount "$SA" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

# get/list/watch on pods, in ONE namespace. No other verb, no other resource,
# no other namespace. A watch is a read and this Role says exactly that.
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-watcher
  namespace: ${NAMESPACE}
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: pod-watcher
  namespace: ${NAMESPACE}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: pod-watcher
subjects:
  - kind: ServiceAccount
    name: ${SA}
    namespace: ${NAMESPACE}
YAML

kubectl -n "$NAMESPACE" create deployment watched --image=rancher/mirrored-pause:3.6 \
  --replicas=1 --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n "$NAMESPACE" rollout status deployment/watched --timeout=120s >/dev/null

echo "==> RBAC proof (the negative half matters most)"
AS="system:serviceaccount:${NAMESPACE}:${SA}"
for check in "watch pods" "list pods" "get pods"; do
  printf "   can-i %-12s in %s : %s\n" "$check" "$NAMESPACE" \
    "$(kubectl auth can-i $check -n "$NAMESPACE" --as="$AS")"
done
printf "   can-i %-12s in %s : %s\n" "delete pods" "$NAMESPACE" \
  "$(kubectl auth can-i delete pods -n "$NAMESPACE" --as="$AS" || true)"
printf "   can-i %-12s in %s : %s\n" "watch pods" "default" \
  "$(kubectl auth can-i watch pods -n default --as="$AS" || true)"

echo "==> credential + CA"
TOKEN=$(kubectl -n "$NAMESPACE" create token "$SA" --duration=2h)
python - "$KUBECONFIG_PATH" "$CA_PATH" <<'PY'
import base64, re, sys
config = open(sys.argv[1], encoding="utf-8").read()
data = re.search(r"certificate-authority-data:\s*(\S+)", config).group(1)
open(sys.argv[2], "wb").write(base64.b64decode(data))
server = re.search(r"server:\s*(\S+)", config).group(1)
open(sys.argv[2] + ".server", "w", encoding="utf-8").write(server)
PY
SERVER=$(cat "${CA_PATH}.server")

echo "==> postgres ${PG_DB}"
if ! docker ps --format '{{.Names}}' | grep -q "^${PG_CONTAINER}$"; then
  docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
  docker run -d --name "$PG_CONTAINER" \
    -e POSTGRES_PASSWORD="$PG_PASS" -e POSTGRES_USER="$PG_USER" -e POSTGRES_DB="$PG_DB" \
    -p "${PG_PORT}:5432" "$PG_IMAGE" >/dev/null
fi
for _ in $(seq 1 60); do
  docker exec "$PG_CONTAINER" pg_isready -U "$PG_USER" >/dev/null 2>&1 && break
  sleep 1
done
# A FRESH database every run: a harness that proves crash recovery against
# yesterday's rows is proving something about yesterday.
# A crashed harness child leaves its connection behind, and a live session blocks
# DROP DATABASE. Evict first, so "fresh" is actually fresh rather than an error
# the next step silently inherits.
docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${PG_DB}'" >/dev/null 2>&1 || true
docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -c "DROP DATABASE IF EXISTS ${PG_DB}" >/dev/null
docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -c "CREATE DATABASE ${PG_DB}" >/dev/null

# Two DSNs for two consumers, deliberately, because they are two different
# things: ``CORTEX_DURABLE_URL`` is the governed runtime's synchronous durable
# store, and alembic builds its own async DSN from ``POSTGRES_URL``
# (backend/database/engine.py:_build_dsn). Setting only the first migrates
# nothing and fails against localhost:5432.
# psycopg2 is what is installed here; psycopg (v3) is not.
DSN="postgresql+psycopg2://${PG_USER}:${PG_PASS}@127.0.0.1:${PG_PORT}/${PG_DB}"
MIGRATION_DSN="postgresql://${PG_USER}:${PG_PASS}@127.0.0.1:${PG_PORT}/${PG_DB}"
echo "==> alembic upgrade head"
POSTGRES_URL="$MIGRATION_DSN" python -m alembic -c backend/database/migrations/alembic.ini upgrade head 2>&1 | tail -3

cat > .phase93.env <<ENV
export CORTEX_DURABLE_URL='${DSN}'
export CORTEX_KUBERNETES_URL='${SERVER}'
export CORTEX_KUBERNETES_TOKEN='${TOKEN}'
export CORTEX_KUBERNETES_TENANT='dev'
export CORTEX_TLS_CA_BUNDLE='${CA_PATH}'
export CORTEX_P93_NAMESPACE='${NAMESPACE}'
export KUBECONFIG='${KUBECONFIG_PATH}'
ENV
echo
echo "provisioned. source .phase93.env"
echo "  api server : ${SERVER}"
echo "  database   : ${PG_DB} (fresh, migrated to head)"
