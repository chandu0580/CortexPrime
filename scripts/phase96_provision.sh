#!/usr/bin/env bash
# Phase 9.6 (ADR-086) — provision the disposable INCIDENT environment.
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
# Usage:   bash scripts/phase96_provision.sh            (create + write .phase96.env)
#          bash scripts/phase96_provision.sh teardown   (delete everything)

set -euo pipefail

# kubectl has no default request timeout, so a momentarily busy API server hangs
# the whole provision indefinitely rather than failing. On a loaded host that is
# the difference between a slow run and one that never ends.
kubectl() { command kubectl --request-timeout=45s "$@"; }

CLUSTER=cortex-p96
NAMESPACE=cortex-p96
SA=cortex-watcher
KSM_NODEPORT=30080
KSM_HOSTPORT=18082
PROM_CONTAINER=cortex-p96-prom
PROM_PORT=19094
PROXY_CONTAINER=cortex-p96-proxy
PROXY_PORT=19095
PG_CONTAINER=cortex-p96-pg
PG_PORT=55435
PG_USER=cortex
PG_PASS=cortex
PG_DB=cortex_p96
PG_IMAGE=pgvector/pgvector:pg16
PROM_IMAGE=prom/prometheus:v2.52.0
KSM_IMAGE=registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.13.0
K3D="${K3D:-$HOME/bin/k3d.exe}"
WORKDIR="$PWD/.phase96"
KUBECONFIG_PATH="$WORKDIR/kubeconfig"
CA_PATH="$WORKDIR/cluster-ca.crt"
# A fixed dev token for the proxy. Disposable, local, and printed into a
# gitignored env file — the same stated trust shape as CORTEX_GRAFANA_TOKEN.
PROM_TOKEN="${PROM_TOKEN:-p96-prometheus-dev-token}"

if [ "${1:-create}" = "teardown" ]; then
  "$K3D" cluster delete "$CLUSTER" >/dev/null 2>&1 || true
  docker rm -f "$PROM_CONTAINER" "$PROXY_CONTAINER" "$PG_CONTAINER" >/dev/null 2>&1 || true
  docker network rm "$CLUSTER-net" >/dev/null 2>&1 || true
  rm -rf "$WORKDIR" .phase96.env
  echo "phase 9.6 environment removed"
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

# Pull once on the HOST and import into the cluster. A k3d node pulling from the
# public CDN is a network dependency in the middle of an evidence run, and it has
# already failed once with a DNS error mid-provision.
echo "==> importing images into the cluster (no in-cluster pulls)"
for image in "$KSM_IMAGE" busybox:1.36; do
  docker image inspect "$image" >/dev/null 2>&1 || docker pull "$image" >/dev/null
  # Bounded: an import that stalls (it spawns a tools node, which competes with
  # whatever else Docker is running) must not hang the whole provision. If it
  # fails the node falls back to pulling, which is slower but still works.
  timeout 180 "$K3D" image import "$image" -c "$CLUSTER" >/dev/null 2>&1 ||     echo "   (import of $image skipped; the node will pull it)"
done

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
  # Phase 9.6: a regression hypothesis stands on the deployment's revision, so
  # the investigator must be able to READ deployments. get only -- no list, no
  # watch, and emphatically no patch/update/delete.
  - apiGroups: ["apps"]
    resources: ["deployments"]
    # Phase 9.6: `patch` is the ONE write this platform may perform, on
    # deployments, in THIS namespace. Not create, not delete, not update, not
    # scale, not exec, and nothing at all outside this namespace. The blast
    # radius is a property of the grant, not of the code that uses it.
    verbs: ["get", "patch"]
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

# The incident, staged as a REAL deployment regression.
#
# Revision 1 is healthy. Revision 2 changes the command so the container exits 1
# after a few seconds -> a genuine CrashLoopBackOff, with a genuine revision
# change behind it.
#
# The MISLEADING hypothesis is real, not a straw man: a crashlooping container
# with a memory limit is exactly the shape an OOMKill takes, so H4 is a
# legitimate thing to suspect. The evidence has to eliminate it -- exit code 1
# (not 137), reason "Error" (not OOMKilled), and working-set memory far below the
# limit -- rather than the scenario simply not offering it.
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payments-api
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels: {app: payments-api}
  template:
    metadata:
      labels: {app: payments-api}
    spec:
      terminationGracePeriodSeconds: 1
      containers:
        - name: api
          image: busybox:1.36
          imagePullPolicy: IfNotPresent
          command: ["sh", "-c", "sleep 100000"]
          resources:
            requests: {cpu: 10m, memory: 32Mi}
            limits:   {cpu: 100m, memory: 64Mi}
YAML
kubectl -n "$NAMESPACE" rollout status deployment/payments-api --timeout=180s >/dev/null
echo "   T0: payments-api revision $(kubectl -n "$NAMESPACE" get deploy payments-api -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}') healthy"

# The SECOND workload, where a restart is genuinely the right remediation.
#
# `envFrom` injects the ConfigMap's values into the container environment AT POD
# CREATION. They are never updated in a running pod. So when an operator fixes
# the ConfigMap, every pod already running keeps the old, broken value -- and the
# kubelet restarting a crashlooping container in place does NOT help, because it
# is the same pod with the same environment.
#
# Only REPLACING the pods picks up the corrected configuration. That is exactly
# what a rollout restart does, and it is one of the most common real reasons an
# operator reaches for one.
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: ${NAMESPACE}
data:
  MODE: "broken"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: config-consumer
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels: {app: config-consumer}
  template:
    metadata:
      labels: {app: config-consumer}
    spec:
      terminationGracePeriodSeconds: 1
      containers:
        - name: app
          image: busybox:1.36
          imagePullPolicy: IfNotPresent
          command:
            - sh
            - -c
            - 'if [ "\$MODE" = ok ]; then echo ready; sleep 100000; else echo "FATAL: MODE=\$MODE" >&2; sleep 4; exit 1; fi'
          envFrom:
            - configMapRef: {name: app-config}
          resources:
            requests: {cpu: 10m, memory: 16Mi}
            limits:   {cpu: 100m, memory: 64Mi}
YAML
echo "   T0: config-consumer deployed with MODE=broken (it will crashloop)"

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
          imagePullPolicy: IfNotPresent
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
echo "==> scrape credential for cAdvisor (Prometheus's own, not CortexPrime's)"
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: v1
kind: ServiceAccount
metadata: {name: prom-scraper, namespace: kube-system}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: {name: prom-scraper}
rules:
  - apiGroups: [""]
    resources: ["nodes/metrics", "nodes/proxy"]
    verbs: ["get"]
  - nonResourceURLs: ["/metrics"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: {name: prom-scraper}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: prom-scraper}
subjects:
  - {kind: ServiceAccount, name: prom-scraper, namespace: kube-system}
YAML
kubectl -n kube-system create token prom-scraper --duration=2h > "$WORKDIR/sa-token"
NODE_NAME=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
API_HOST_PORT="host.docker.internal:${API_PORT}"
echo "   node=${NODE_NAME} api=${API_HOST_PORT}"

echo "==> prometheus (scraping kube-state-metrics AND the kubelet, for real)"
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
  # The kubelet's cAdvisor, through the API server proxy. cAdvisor measures the
  # CONTAINER RUNTIME directly rather than re-reading the API server, so container
  # memory is a genuinely different origin from the cluster API — which is what
  # makes it an independent falsifier for a resource-exhaustion hypothesis.
  - job_name: "kubelet-cadvisor"
    scheme: https
    tls_config:
      ca_file: /etc/prometheus/cluster-ca.crt
      insecure_skip_verify: true
    bearer_token_file: /etc/prometheus/sa-token
    metrics_path: /api/v1/nodes/${NODE_NAME}/proxy/metrics/cadvisor
    static_configs:
      - targets: ["${API_HOST_PORT}"]
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
  -v "${WINPWD}/.phase96/prometheus.yml:/etc/prometheus/prometheus.yml:ro" \
  -v "${WINPWD}/.phase96/cluster-ca.crt:/etc/prometheus/cluster-ca.crt:ro" \
  -v "${WINPWD}/.phase96/sa-token:/etc/prometheus/sa-token:ro" \
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
  -v "${WINPWD}/.phase96/proxy.conf:/etc/nginx/conf.d/default.conf:ro" \
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

# ---------------------------------------------------------------------------
# 7. T1 — the regression. Applied only now, so Prometheus has a real healthy
#    baseline first and the failure genuinely BEGINS AFTER the revision change.
# ---------------------------------------------------------------------------
echo "==> T1: rolling out the regressing revision"
kubectl -n "$NAMESPACE" patch deployment payments-api --type=json -p \
  '[{"op":"replace","path":"/spec/template/spec/containers/0/command","value":["sh","-c","echo starting; sleep 6; echo FATAL: config parse failed >&2; exit 1"]}]' >/dev/null
REVISION=$(kubectl -n "$NAMESPACE" get deploy payments-api \
  -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')
echo "   T1: revision now ${REVISION}"

echo "==> T2-T4: waiting for a REAL CrashLoopBackOff"
POD=""; REASON=""; RESTARTS=0
for _ in $(seq 1 60); do
  POD=$(kubectl -n "$NAMESPACE" get pods -l app=payments-api \
    --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1:].metadata.name}' 2>/dev/null || true)
  [ -z "$POD" ] && { sleep 5; continue; }
  REASON=$(kubectl -n "$NAMESPACE" get pod "$POD" \
    -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}' 2>/dev/null || true)
  RESTARTS=$(kubectl -n "$NAMESPACE" get pod "$POD" \
    -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || echo 0)
  [ "$REASON" = "CrashLoopBackOff" ] && break
  sleep 5
done
EXIT_CODE=$(kubectl -n "$NAMESPACE" get pod "$POD" \
  -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}' 2>/dev/null || true)
TERM_REASON=$(kubectl -n "$NAMESPACE" get pod "$POD" \
  -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}' 2>/dev/null || true)
echo "   pod        : ${POD}"
echo "   waiting    : ${REASON:-<none>}   restarts: ${RESTARTS:-0}"
echo "   terminated : exitCode=${EXIT_CODE:-?} reason=${TERM_REASON:-?}"
echo "   (exit 1 / Error, NOT 137 / OOMKilled — H4 must be eliminated BY EVIDENCE)"

echo "==> waiting for config-consumer to crashloop on the BROKEN value"
CFG_POD=""
for _ in $(seq 1 60); do
  CFG_POD=$(kubectl -n "$NAMESPACE" get pods -l app=config-consumer \
    --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1:].metadata.name}' 2>/dev/null || true)
  [ -z "$CFG_POD" ] && { sleep 5; continue; }
  CFG_REASON=$(kubectl -n "$NAMESPACE" get pod "$CFG_POD" \
    -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}' 2>/dev/null || true)
  [ "$CFG_REASON" = "CrashLoopBackOff" ] && break
  sleep 5
done
CFG_RESTARTS=$(kubectl -n "$NAMESPACE" get pod "$CFG_POD" \
  -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || echo 0)
echo "   config-consumer pod ${CFG_POD}: ${CFG_REASON:-<none>} (${CFG_RESTARTS:-0} restarts)"

echo "==> T5: an operator FIXES the ConfigMap (running pods keep the old env)"
kubectl -n "$NAMESPACE" patch configmap app-config --type=merge \
  -p '{"data":{"MODE":"ok"}}' >/dev/null
echo "   ConfigMap MODE=ok; the running pod still has MODE=broken in its env,"
echo "   so ONLY replacing the pods can remediate this. That is the write under test."

echo "==> confirming the kubelet metric that falsifies H4 is really present"
MEM=""
for _ in $(seq 1 24); do
  MEM=$(curl -s -H "Authorization: Bearer ${PROM_TOKEN}" --get \
    "http://127.0.0.1:${PROXY_PORT}/api/v1/query" \
    --data-urlencode "query=max(container_memory_working_set_bytes{namespace=\"${NAMESPACE}\", container!=\"\"})" \
    | python -c "import sys,json;d=json.load(sys.stdin).get('data',{}).get('result',[]);print(d[0]['value'][1] if d else '')" 2>/dev/null || true)
  [ -n "$MEM" ] && break
  sleep 5
done
echo "   container_memory_working_set_bytes = ${MEM:-<absent>}  (limit 67108864)"

cat > .phase96.env <<ENV
export CORTEX_DURABLE_URL='${DSN}'
export CORTEX_KUBERNETES_URL='${SERVER}'
export CORTEX_KUBERNETES_TOKEN='${TOKEN}'
export CORTEX_KUBERNETES_TENANT='dev'
export CORTEX_TLS_CA_BUNDLE='${CA_PATH}'
export CORTEX_PROMETHEUS_URL='http://127.0.0.1:${PROXY_PORT}'
export CORTEX_PROMETHEUS_TOKEN='${PROM_TOKEN}'
export CORTEX_PROMETHEUS_TENANT='dev'
export CORTEX_P96_NAMESPACE='${NAMESPACE}'
export CORTEX_P96_WORKLOAD='payments-api'
export CORTEX_P96_FIXABLE_WORKLOAD='config-consumer'
export CORTEX_P96_FIXABLE_POD='${CFG_POD}'
export CORTEX_P96_POD='${POD}'
export CORTEX_P96_REVISION='${REVISION}'
export CORTEX_P96_EXIT_CODE='${EXIT_CODE}'
export CORTEX_P96_TERM_REASON='${TERM_REASON}'
export CORTEX_P96_MEMORY_LIMIT_BYTES='67108864'
export KUBECONFIG='${KUBECONFIG_PATH}'
ENV
echo
echo "provisioned. source .phase96.env"
echo "  kubernetes  : ${SERVER}"
echo "  prometheus  : http://127.0.0.1:${PROXY_PORT} (bearer proxy) -> ${PROM_PORT}"
echo "  database    : ${PG_DB} (fresh, migrated to head)"
echo "  remediable  : ${NAMESPACE}/config-consumer — ConfigMap fixed, pods stale"
echo "                (a rollout restart IS the correct remediation here)"
echo "  unremediable: ${NAMESPACE}/payments-api — a broken command in revision ${REVISION}"
echo "                (a rollout restart will NOT fix it; the platform must say so)"
echo "  incident    : ${NAMESPACE}/${POD} CrashLoopBackOff at revision ${REVISION},"
echo "                exit ${EXIT_CODE} (${TERM_REASON}), memory ${MEM:-?} of 67108864"
echo "  incident    : ${NAMESPACE}/${POD} CrashLoopBackOff, revision ${REVISION},"
echo "                exit ${EXIT_CODE} (${TERM_REASON}), memory limit 64Mi"
