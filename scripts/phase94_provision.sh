#!/usr/bin/env bash
# Phase 9.4 (ADR-084) — provision the disposable multi-source evidence environment.
#
# The topology exists to make ONE thing real: two observations of the same
# quantity, from two instruments, whose lineage genuinely differs in the way the
# corroboration engine must detect.
#
#   k3d cluster ──┬─ API server ───────────────────► CortexPrime (governed K8s read)
#                 │        ▲
#                 │        │ scrapes the K8s API
#                 └─ kube-state-metrics ──► Prometheus ──► bearer proxy ──► CortexPrime
#
# kube-state-metrics reports `kube_pod_container_status_restarts_total`, which is
# the SAME number the API server reports as `restartCount` — because it reads the
# API server. Two sources, one origin. The platform must say CORRELATED, not
# INDEPENDENT, and that is the load-bearing demonstration.
#
# The bearer proxy is not decoration: the credential broker refuses per provider
# ("no credential adapter is registered for this provider"), Prometheus has no
# native bearer auth, and a proxy is how Prometheus is actually protected. It also
# makes the 401 negative test a real refusal.
#
# Usage:   bash scripts/phase94_provision.sh            (create + write .phase94.env)
#          bash scripts/phase94_provision.sh teardown   (delete everything)

set -euo pipefail

CLUSTER=cortex-p94
NAMESPACE=cortex-p94
SA=cortex-watcher
KSM_NODEPORT=30080
KSM_HOSTPORT=18080
PROM_CONTAINER=cortex-p94-prom
PROM_PORT=19090
PROXY_CONTAINER=cortex-p94-proxy
PROXY_PORT=19091
PG_CONTAINER=cortex-p94-pg
PG_PORT=55433
PG_USER=cortex
PG_PASS=cortex
PG_DB=cortex_p94
PG_IMAGE=pgvector/pgvector:pg16
PROM_IMAGE=prom/prometheus:v2.52.0
KSM_IMAGE=registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.13.0
K3D="${K3D:-$HOME/bin/k3d.exe}"
WORKDIR="$PWD/.phase94"
KUBECONFIG_PATH="$WORKDIR/kubeconfig"
CA_PATH="$WORKDIR/cluster-ca.crt"
# A fixed dev token for the proxy. Disposable, local, and printed into a
# gitignored env file — the same stated trust shape as CORTEX_GRAFANA_TOKEN.
PROM_TOKEN="${PROM_TOKEN:-p94-prometheus-dev-token}"

if [ "${1:-create}" = "teardown" ]; then
  "$K3D" cluster delete "$CLUSTER" >/dev/null 2>&1 || true
  docker rm -f "$PROM_CONTAINER" "$PROXY_CONTAINER" "$PG_CONTAINER" >/dev/null 2>&1 || true
  docker network rm "$CLUSTER-net" >/dev/null 2>&1 || true
  rm -rf "$WORKDIR" .phase94.env
  echo "phase 9.4 environment removed"
  exit 0
fi

mkdir -p "$WORKDIR"

# ---------------------------------------------------------------------------
# 1. The cluster, with a host port mapped to the kube-state-metrics NodePort
# ---------------------------------------------------------------------------
echo "==> k3d cluster ${CLUSTER}"
if ! "$K3D" cluster list "$CLUSTER" >/dev/null 2>&1; then
  "$K3D" cluster create "$CLUSTER" --servers 1 --agents 0 --no-lb \
    --port "${KSM_HOSTPORT}:${KSM_NODEPORT}@server:0:direct" --wait
fi
"$K3D" kubeconfig get "$CLUSTER" > "$KUBECONFIG_PATH"
# k3d writes host.docker.internal, which resolves to the LAN interface here and
# is unreachable from the host. Rewrite to the published loopback, which k3s also
# puts in the certificate SANs so TLS still verifies against the cluster CA.
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

# ---------------------------------------------------------------------------
# 2. Namespace, the workload to observe, and the read-only ServiceAccount
# ---------------------------------------------------------------------------
echo "==> namespace, workload, RBAC"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n "$NAMESPACE" create serviceaccount "$SA" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

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

# A pod that restarts on purpose. The restart count is the quantity BOTH the API
# server and kube-state-metrics report, which is the whole point of the vertical.
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flapper
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels: {app: flapper}
  template:
    metadata:
      labels: {app: flapper}
    spec:
      terminationGracePeriodSeconds: 1
      containers:
        - name: flapper
          image: busybox:1.36
          command: ["sh", "-c", "sleep 12; exit 1"]
          resources:
            requests: {cpu: 10m, memory: 16Mi}
YAML

# ---------------------------------------------------------------------------
# 3. kube-state-metrics — the DERIVED instrument. It reads the API server.
# ---------------------------------------------------------------------------
echo "==> kube-state-metrics (the derived instrument)"
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: v1
kind: ServiceAccount
metadata: {name: kube-state-metrics, namespace: kube-system}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: {name: kube-state-metrics}
rules:
  - apiGroups: [""]
    resources: ["pods", "nodes", "namespaces", "services", "replicationcontrollers", "resourcequotas"]
    verbs: ["list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets", "statefulsets", "daemonsets"]
    verbs: ["list", "watch"]
  - apiGroups: ["batch"]
    resources: ["jobs", "cronjobs"]
    verbs: ["list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: {name: kube-state-metrics}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: kube-state-metrics}
subjects:
  - {kind: ServiceAccount, name: kube-state-metrics, namespace: kube-system}
---
apiVersion: apps/v1
kind: Deployment
metadata: {name: kube-state-metrics, namespace: kube-system}
spec:
  replicas: 1
  selector:
    matchLabels: {app: kube-state-metrics}
  template:
    metadata:
      labels: {app: kube-state-metrics}
    spec:
      serviceAccountName: kube-state-metrics
      containers:
        - name: kube-state-metrics
          image: ${KSM_IMAGE}
          args: ["--resources=pods,deployments,nodes,namespaces"]
          ports: [{containerPort: 8080, name: http-metrics}]
---
apiVersion: v1
kind: Service
metadata: {name: kube-state-metrics, namespace: kube-system}
spec:
  type: NodePort
  selector: {app: kube-state-metrics}
  ports:
    - {port: 8080, targetPort: 8080, nodePort: ${KSM_NODEPORT}, name: http-metrics}
YAML

kubectl -n kube-system rollout status deployment/kube-state-metrics --timeout=180s >/dev/null
echo "   kube-state-metrics ready on nodePort ${KSM_NODEPORT} -> host ${KSM_HOSTPORT}"

echo "==> RBAC proof (the negative half matters most)"
AS="system:serviceaccount:${NAMESPACE}:${SA}"
for check in "watch pods" "list pods" "get pods"; do
  printf "   can-i %-12s in %s : %s\n" "$check" "$NAMESPACE" \
    "$(kubectl auth can-i $check -n "$NAMESPACE" --as="$AS")"
done
printf "   can-i %-12s in %s : %s\n" "delete pods" "$NAMESPACE" \
  "$(kubectl auth can-i delete pods -n "$NAMESPACE" --as="$AS" || true)"

echo "==> credential + CA"
TOKEN=$(kubectl -n "$NAMESPACE" create token "$SA" --duration=2h)
python - "$KUBECONFIG_PATH" "$CA_PATH" <<'PY'
import base64, re, sys
config = open(sys.argv[1], encoding="utf-8").read()
data = re.search(r"certificate-authority-data:\s*(\S+)", config).group(1)
open(sys.argv[2], "wb").write(base64.b64decode(data))
open(sys.argv[2] + ".server", "w", encoding="utf-8").write(
    re.search(r"server:\s*(\S+)", config).group(1))
PY
SERVER=$(cat "${CA_PATH}.server")

# ---------------------------------------------------------------------------
# 4. Prometheus — a REAL scraper, scraping the REAL derived instrument
# ---------------------------------------------------------------------------
echo "==> prometheus (scraping kube-state-metrics for real)"
cat > "$WORKDIR/prometheus.yml" <<YAML
global:
  scrape_interval: 5s
  evaluation_interval: 5s
scrape_configs:
  # The DERIVED instrument: kube-state-metrics reads the Kubernetes API, so
  # everything under this job shares the cluster's lineage origin.
  - job_name: "kube-state-metrics"
    static_configs:
      - targets: ["host.docker.internal:${KSM_HOSTPORT}"]
  # Prometheus's own instrumentation. A genuinely different origin from the
  # Kubernetes API — nothing here is derived from the cluster.
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]
YAML

docker rm -f "$PROM_CONTAINER" >/dev/null 2>&1 || true
# MSYS_NO_PATHCONV: Git Bash rewrites anything that looks like a POSIX path into
# a Windows one, which turns /etc/prometheus/prometheus.yml into
# "C:/Program Files/Git/etc/...". `pwd -W` gives the host path in the form the
# Docker Desktop daemon accepts for a bind mount.
WINPWD=$(pwd -W 2>/dev/null || pwd)
MSYS_NO_PATHCONV=1 docker run -d --name "$PROM_CONTAINER" \
  --add-host=host.docker.internal:host-gateway \
  -p "${PROM_PORT}:9090" \
  -v "${WINPWD}/.phase94/prometheus.yml:/etc/prometheus/prometheus.yml:ro" \
  "$PROM_IMAGE" --config.file=/etc/prometheus/prometheus.yml >/dev/null

for _ in $(seq 1 60); do
  curl -sf "http://127.0.0.1:${PROM_PORT}/-/ready" >/dev/null 2>&1 && break
  sleep 2
done
echo "   prometheus ready on ${PROM_PORT}"

# ---------------------------------------------------------------------------
# 5. The bearer proxy — so the governed credential does real work
# ---------------------------------------------------------------------------
echo "==> bearer-token proxy in front of prometheus"
cat > "$WORKDIR/proxy.conf" <<CONF
server {
  listen 9091;
  location / {
    if (\$http_authorization != "Bearer ${PROM_TOKEN}") { return 401; }
    proxy_pass http://prom-upstream:9090;
    proxy_set_header Authorization "";
  }
}
CONF
docker rm -f "$PROXY_CONTAINER" >/dev/null 2>&1 || true
docker network create "$CLUSTER-net" >/dev/null 2>&1 || true
docker network connect --alias prom-upstream "$CLUSTER-net" "$PROM_CONTAINER" >/dev/null 2>&1 || true
MSYS_NO_PATHCONV=1 docker run -d --name "$PROXY_CONTAINER" --network "$CLUSTER-net" \
  -p "${PROXY_PORT}:9091" \
  -v "${WINPWD}/.phase94/proxy.conf:/etc/nginx/conf.d/default.conf:ro" \
  nginx:1.27-alpine >/dev/null

for _ in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${PROXY_PORT}/-/ready" || true)
  [ "$code" = "401" ] && break
  sleep 2
done
echo "   proxy: no token -> $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:${PROXY_PORT}/-/ready)"
echo "   proxy: token    -> $(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer ${PROM_TOKEN}" http://127.0.0.1:${PROXY_PORT}/-/ready)"

# ---------------------------------------------------------------------------
# 6. A fresh database
# ---------------------------------------------------------------------------
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
docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${PG_DB}'" >/dev/null 2>&1 || true
docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -c "DROP DATABASE IF EXISTS ${PG_DB}" >/dev/null
docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -c "CREATE DATABASE ${PG_DB}" >/dev/null

DSN="postgresql+psycopg2://${PG_USER}:${PG_PASS}@127.0.0.1:${PG_PORT}/${PG_DB}"
MIGRATION_DSN="postgresql://${PG_USER}:${PG_PASS}@127.0.0.1:${PG_PORT}/${PG_DB}"
echo "==> alembic upgrade head"
POSTGRES_URL="$MIGRATION_DSN" python -m alembic -c backend/database/migrations/alembic.ini upgrade head 2>&1 | tail -2

echo "==> waiting for the flapper to accumulate real restarts"
for _ in $(seq 1 40); do
  restarts=$(kubectl -n "$NAMESPACE" get pods -l app=flapper \
    -o jsonpath='{.items[0].status.containerStatuses[0].restartCount}' 2>/dev/null || echo 0)
  [ -n "$restarts" ] && [ "$restarts" -ge 1 ] 2>/dev/null && break
  sleep 5
done
echo "   API server reports restartCount = ${restarts:-0}"

cat > .phase94.env <<ENV
export CORTEX_DURABLE_URL='${DSN}'
export CORTEX_KUBERNETES_URL='${SERVER}'
export CORTEX_KUBERNETES_TOKEN='${TOKEN}'
export CORTEX_KUBERNETES_TENANT='dev'
export CORTEX_TLS_CA_BUNDLE='${CA_PATH}'
export CORTEX_PROMETHEUS_URL='http://127.0.0.1:${PROXY_PORT}'
export CORTEX_PROMETHEUS_TOKEN='${PROM_TOKEN}'
export CORTEX_PROMETHEUS_TENANT='dev'
export CORTEX_P94_NAMESPACE='${NAMESPACE}'
export KUBECONFIG='${KUBECONFIG_PATH}'
ENV
echo
echo "provisioned. source .phase94.env"
echo "  kubernetes  : ${SERVER}"
echo "  prometheus  : http://127.0.0.1:${PROXY_PORT} (bearer proxy) -> ${PROM_PORT}"
echo "  database    : ${PG_DB} (fresh, migrated to head)"
