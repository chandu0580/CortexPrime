#!/usr/bin/env bash
# Phase 9.9 Part B (ADR-089) — provision the disposable CONTAINED-WORKER environment.
#
# The topology exists to make ONE thing real: a worker that is genuinely out of
# CortexPrime's process, holding a credential CortexPrime's process never has,
# able to perform exactly one operation on exactly one namespace.
#
#   host                                   k3d cluster
#   ────                                   ───────────
#   CortexPrime  ──envelope over HTTP──►  contained worker (Pod)
#   (governed chain)                       │  non-root, ro-rootfs, caps dropped
#        │                                 │  stdlib only, one operation
#        │ governed READS (own SA)         ▼
#        └───────────────────────────►  API server  ◄── PATCH deployments (worker SA)
#
# Two ServiceAccounts, deliberately:
#   * cortex-reader   — get/list/watch, used by the platform's in-process READ
#                       path to verify the result INDEPENDENTLY of the worker.
#   * cortex-restarter— patch+get on deployments in ONE namespace. Nothing else.
#                       This is the only identity that can change anything.
#
# The worker is provisioned by the OPERATOR, never by CortexPrime. That is what
# keeps BND-PROCESS-SPAWN intact and avoids ADR-087's bootstrap regress: the
# platform dispatches to infrastructure it did not create, exactly as it does
# with PostgreSQL.
#
# Usage:   bash scripts/phase99b_provision.sh            (create + write .phase99b.env)
#          bash scripts/phase99b_provision.sh teardown   (delete everything)

set -euo pipefail

# kubectl has no default request timeout, so a momentarily busy API server hangs
# the whole provision indefinitely rather than failing (learned in 9.6).
kubectl() { command kubectl --request-timeout=45s "$@"; }

CLUSTER=cortex-p99b
NAMESPACE=cortex-p99b
OTHER_NAMESPACE=cortex-p99b-other   # for the cross-namespace refusal proof
READER_SA=cortex-reader
RESTART_SA=cortex-restarter
WORKER_IMAGE=cortexprime/contained-k8s-restart:1.0.0
WORKER_NODEPORT=30099
POD_MAX_PIDS=128
WORKER_HOSTPORT=18099
PG_CONTAINER=cortex-p99b-pg
PG_PORT=55437
PG_USER=cortex
PG_PASS=cortex
PG_DB=cortex_p99b
PG_IMAGE=pgvector/pgvector:pg16
TARGET_DEPLOY=payments-api
BYSTANDER_DEPLOY=billing-api        # must be untouched by the write
K3D="${K3D:-$HOME/bin/k3d.exe}"
WORKDIR="$PWD/.phase99b"
KUBECONFIG_PATH="$WORKDIR/kubeconfig"
CA_PATH="$WORKDIR/cluster-ca.crt"

TENANT="${TENANT:-dev}"
CAPABILITY_ID="platform.kubernetes.workload.rollout_restart"
CAPABILITY_VERSION=1
# ADR-089: the contained write path is its own provider boundary, not the
# in-process read connector's. Different address, identity and posture.
PROVIDER=kubernetes-contained
OPERATION=kubernetes.workload.rollout_restart

if [ "${1:-create}" = "teardown" ]; then
  "$K3D" cluster delete "$CLUSTER" >/dev/null 2>&1 || true
  docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
  rm -rf "$WORKDIR" .phase99b.env
  echo "phase 9.9B environment removed"
  exit 0
fi

mkdir -p "$WORKDIR"

# ---------------------------------------------------------------------------
# 1. The worker image. Built on the HOST from fixed source, then imported.
#    The digest is computed here and becomes the implementation identity that
#    both the worker and the platform are bound to.
# ---------------------------------------------------------------------------
echo "==> building the contained worker image"
IMPL_DIGEST=$(python -c "
import hashlib, sys
print(hashlib.sha256(open('workers/contained_k8s_restart/worker.py','rb').read()).hexdigest())
")
echo "   implementation digest: ${IMPL_DIGEST:0:16}..."
docker build -q -t "$WORKER_IMAGE" workers/contained_k8s_restart >/dev/null

# ---------------------------------------------------------------------------
# 1b. TLS for the worker. The credential travels as this connection's
#     authorization header, so the connection is not allowed to be plaintext --
#     the same rule the Kubernetes channel already enforces.
# ---------------------------------------------------------------------------
echo "==> generating worker TLS material"
WINPWD=$(pwd -W 2>/dev/null || pwd)
MSYS_NO_PATHCONV=1 docker run --rm -v "${WINPWD}/.phase99b:/out" alpine/openssl \
  req -x509 -newkey rsa:2048 -nodes -days 2 \
  -keyout /out/worker.key -out /out/worker.crt \
  -subj "/CN=cortex-contained-worker" \
  -addext "subjectAltName=IP:127.0.0.1,DNS:localhost" >/dev/null 2>&1

# ---------------------------------------------------------------------------
# 2. The cluster, with a host port mapped to the worker's NodePort
# ---------------------------------------------------------------------------
echo "==> k3d cluster ${CLUSTER}"
if ! "$K3D" cluster list "$CLUSTER" >/dev/null 2>&1; then
  # pod-max-pids sets each pod's cgroup pids.max. Without it the cap is "max",
  # which is what ADR-089 honestly reported as NOT VERIFIED. 128 is ample for a
  # stdlib HTTP server and far below anything a fork bomb needs.
  "$K3D" cluster create "$CLUSTER" --servers 1 --agents 0 --no-lb \
    --k3s-arg "--kubelet-arg=pod-max-pids=${POD_MAX_PIDS}@server:0" \
    --port "${WORKER_HOSTPORT}:${WORKER_NODEPORT}@server:0:direct" --wait
fi
"$K3D" kubeconfig get "$CLUSTER" > "$KUBECONFIG_PATH"
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

echo "==> importing images (no in-cluster pulls mid-run)"
for image in "$WORKER_IMAGE" busybox:1.36; do
  docker image inspect "$image" >/dev/null 2>&1 || docker pull "$image" >/dev/null
  timeout 240 "$K3D" image import "$image" -c "$CLUSTER" >/dev/null 2>&1 \
    || echo "   (import of $image skipped; the node will pull it)"
done

# ---------------------------------------------------------------------------
# 3. Namespaces and the workloads
# ---------------------------------------------------------------------------
echo "==> namespaces and workloads"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl create namespace "$OTHER_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

for deploy in "$TARGET_DEPLOY" "$BYSTANDER_DEPLOY"; do
  cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${deploy}
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels: {app: ${deploy}}
  template:
    metadata:
      labels: {app: ${deploy}}
    spec:
      terminationGracePeriodSeconds: 2
      containers:
        - name: app
          image: busybox:1.36
          imagePullPolicy: IfNotPresent
          command: ["sh", "-c", "while true; do sleep 3600; done"]
          resources:
            requests: {memory: "8Mi", cpu: "5m"}
            limits:   {memory: "32Mi", cpu: "100m"}
YAML
done

# A workload in the OTHER namespace, so "the worker cannot reach outside its
# bound namespace" is provable against something that actually exists.
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${TARGET_DEPLOY}
  namespace: ${OTHER_NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels: {app: ${TARGET_DEPLOY}}
  template:
    metadata:
      labels: {app: ${TARGET_DEPLOY}}
    spec:
      terminationGracePeriodSeconds: 2
      containers:
        - name: app
          image: busybox:1.36
          imagePullPolicy: IfNotPresent
          command: ["sh", "-c", "while true; do sleep 3600; done"]
          resources:
            requests: {memory: "8Mi", cpu: "5m"}
            limits:   {memory: "32Mi", cpu: "100m"}
YAML

# ---------------------------------------------------------------------------
# 4. Least-privilege RBAC. Two identities, namespace-scoped, no wildcards.
# ---------------------------------------------------------------------------
echo "==> RBAC (namespace-scoped, explicit verbs, no wildcards)"
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: v1
kind: ServiceAccount
metadata: {name: ${RESTART_SA}, namespace: ${NAMESPACE}}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: {name: ${RESTART_SA}, namespace: ${NAMESPACE}}
rules:
  # The MINIMUM for a rollout restart: patch the Deployment's pod template.
  # 'get' is included so the worker's own call can be verified to have landed;
  # nothing else is granted, and there is no wildcard verb or resource.
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: ${RESTART_SA}, namespace: ${NAMESPACE}}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: Role, name: ${RESTART_SA}}
subjects:
  - {kind: ServiceAccount, name: ${RESTART_SA}, namespace: ${NAMESPACE}}
---
apiVersion: v1
kind: ServiceAccount
metadata: {name: ${READER_SA}, namespace: ${NAMESPACE}}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: {name: ${READER_SA}}
rules:
  - apiGroups: [""]
    resources: ["pods", "events"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: {name: ${READER_SA}}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: ${READER_SA}}
subjects:
  - {kind: ServiceAccount, name: ${READER_SA}, namespace: ${NAMESPACE}}
YAML

# ---------------------------------------------------------------------------
# 5. The worker. Hardened as far as this runtime actually supports.
#    Every field here is measured by the harness rather than trusted.
# ---------------------------------------------------------------------------
echo "==> deploying the contained worker"
kubectl -n "$NAMESPACE" delete secret worker-tls >/dev/null 2>&1 || true
kubectl -n "$NAMESPACE" create secret tls worker-tls \
  --cert="$WORKDIR/worker.crt" --key="$WORKDIR/worker.key" >/dev/null
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: apps/v1
kind: Deployment
metadata: {name: contained-worker, namespace: ${NAMESPACE}}
spec:
  replicas: 1
  selector:
    matchLabels: {app: contained-worker}
  template:
    metadata:
      labels: {app: contained-worker}
    spec:
      serviceAccountName: ${RESTART_SA}
      automountServiceAccountToken: true
      terminationGracePeriodSeconds: 2
      securityContext:
        runAsNonRoot: true
        runAsUser: 65532
        runAsGroup: 65532
        seccompProfile: {type: RuntimeDefault}
      containers:
        - name: worker
          image: ${WORKER_IMAGE}
          imagePullPolicy: IfNotPresent
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: {drop: ["ALL"]}
          ports: [{containerPort: 8080}]
          env:
            - {name: CORTEX_BIND_TENANT,             value: "${TENANT}"}
            - {name: CORTEX_BIND_CAPABILITY_ID,      value: "${CAPABILITY_ID}"}
            - {name: CORTEX_BIND_CAPABILITY_VERSION, value: "${CAPABILITY_VERSION}"}
            - {name: CORTEX_BIND_PROVIDER,           value: "${PROVIDER}"}
            - {name: CORTEX_BIND_OPERATION,          value: "${OPERATION}"}
            - {name: CORTEX_BIND_NAMESPACE,          value: "${NAMESPACE}"}
            - {name: CORTEX_IMPLEMENTATION_DIGEST,   value: "${IMPL_DIGEST}"}
            - {name: CORTEX_IMPLEMENTATION_VERSION,  value: "1.0.0"}
          # Python needs a writable temp dir; the root filesystem stays read-only.
          volumeMounts:
            - {name: tmp, mountPath: /tmp}
            - {name: tls, mountPath: /tls, readOnly: true}
          resources:
            requests: {memory: "32Mi", cpu: "10m"}
            limits:   {memory: "96Mi", cpu: "250m"}
          readinessProbe:
            httpGet: {path: /healthz, port: 8080, scheme: HTTPS}
            initialDelaySeconds: 2
            periodSeconds: 2
      volumes:
        - name: tmp
          emptyDir: {medium: Memory, sizeLimit: 8Mi}
        - name: tls
          secret: {secretName: worker-tls, defaultMode: 0444}
---
apiVersion: v1
kind: Service
metadata: {name: contained-worker, namespace: ${NAMESPACE}}
spec:
  type: NodePort
  selector: {app: contained-worker}
  ports:
    - {port: 8080, targetPort: 8080, nodePort: ${WORKER_NODEPORT}}
YAML

# ---------------------------------------------------------------------------
# 5b. Egress. The worker may reach the Kubernetes API server and DNS. Nothing
#     else -- not the internet, not another service in this cluster.
#
#     The API server rule names the ENDPOINT (node IP:6443), not the ClusterIP.
#     kube-proxy DNATs the ClusterIP and NetworkPolicy is evaluated after that,
#     so an ipBlock for 10.43.0.1 silently blocks the API server. That mistake
#     was made and caught by probing before it reached the worker.
# ---------------------------------------------------------------------------
echo "==> restricting worker egress (API server + DNS only)"
API_ENDPOINT=$(kubectl get endpoints kubernetes -n default \
  -o jsonpath='{.subsets[0].addresses[0].ip}' 2>/dev/null)
API_ENDPOINT_PORT=$(kubectl get endpoints kubernetes -n default \
  -o jsonpath='{.subsets[0].ports[0].port}' 2>/dev/null)
DNS_IP=$(kubectl get svc -n kube-system kube-dns -o jsonpath='{.spec.clusterIP}' 2>/dev/null)
if [ -n "$API_ENDPOINT" ] && [ -n "$DNS_IP" ]; then
  cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: contained-worker-egress, namespace: ${NAMESPACE}}
spec:
  podSelector: {matchLabels: {app: contained-worker}}
  policyTypes: ["Egress"]
  egress:
    - to: [{ipBlock: {cidr: ${API_ENDPOINT}/32}}]
      ports: [{protocol: TCP, port: ${API_ENDPOINT_PORT}}]
    - to: [{ipBlock: {cidr: ${DNS_IP}/32}}]
      ports: [{protocol: UDP, port: 53}, {protocol: TCP, port: 53}]
YAML
  echo "   egress: ${API_ENDPOINT}:${API_ENDPOINT_PORT} + DNS ${DNS_IP} only"
else
  echo "   (could not resolve the API endpoint; NO egress policy applied)"
fi

echo "==> waiting for the worker to become ready"
kubectl -n "$NAMESPACE" rollout status deploy/contained-worker --timeout=180s
for deploy in "$TARGET_DEPLOY" "$BYSTANDER_DEPLOY"; do
  kubectl -n "$NAMESPACE" rollout status "deploy/$deploy" --timeout=120s
done

# ---------------------------------------------------------------------------
# 6. Verify the RBAC against the REAL cluster, not the YAML we just applied
# ---------------------------------------------------------------------------
echo "==> verifying least privilege against the live API server"
AS_RESTART="system:serviceaccount:${NAMESPACE}:${RESTART_SA}"
check_rbac() {  # verb resource namespace expected
  local got
  # `auth can-i` prints its answer AND exits non-zero when the answer is "no",
  # so a `|| echo no` fallback would append a second line to a correct answer.
  # ...and `set -o pipefail` then makes the whole assignment fail under `set -e`,
  # so the trailing `|| true` is what keeps a correct "no" from killing the run.
  got=$(kubectl auth can-i "$1" "$2" --as="$AS_RESTART" -n "$3" 2>/dev/null | head -1 || true)
  [ -n "$got" ] || got=no
  printf "   %-38s %-22s %-4s (want %s)\n" "$1 $2" "ns=$3" "$got" "$4"
  [ "$got" = "$4" ] || { echo "   RBAC IS NOT AS DECLARED"; exit 1; }
}
check_rbac patch deployments "$NAMESPACE"       yes
check_rbac get   deployments "$NAMESPACE"       yes
check_rbac delete deployments "$NAMESPACE"      no
check_rbac create pods       "$NAMESPACE"       no
check_rbac get   secrets     "$NAMESPACE"       no
check_rbac create pods/exec  "$NAMESPACE"       no
check_rbac patch deployments "$OTHER_NAMESPACE" no
check_rbac patch deployments kube-system        no

# ---------------------------------------------------------------------------
# 7. Short-lived credentials (real TokenRequest, not a static Secret)
# ---------------------------------------------------------------------------
echo "==> minting short-lived tokens (TokenRequest)"
RESTART_TOKEN=$(kubectl -n "$NAMESPACE" create token "$RESTART_SA" --duration=2h)
READER_TOKEN=$(kubectl -n "$NAMESPACE" create token "$READER_SA" --duration=2h)
OTHER_TOKEN=$(kubectl -n "$NAMESPACE" create token "$READER_SA" --duration=2h)

kubectl config view --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' \
  | python -c "import base64,sys;sys.stdout.write(base64.b64decode(sys.stdin.read()).decode())" \
  > "$CA_PATH"

echo "==> building the TLS trust bundle (cluster CA + worker certificate)"
cat "$CA_PATH" "$WORKDIR/worker.crt" > "$WORKDIR/ca-bundle.pem"

# ---------------------------------------------------------------------------
# 8. PostgreSQL + migrations
# ---------------------------------------------------------------------------
echo "==> PostgreSQL ${PG_CONTAINER}"
docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$PG_CONTAINER" \
  -e POSTGRES_PASSWORD="$PG_PASS" -e POSTGRES_USER="$PG_USER" -e POSTGRES_DB="$PG_DB" \
  -p "${PG_PORT}:5432" "$PG_IMAGE" >/dev/null
for _ in $(seq 1 60); do
  docker exec "$PG_CONTAINER" pg_isready -U "$PG_USER" -d "$PG_DB" >/dev/null 2>&1 && break
  sleep 2
done

DSN="postgresql+psycopg2://${PG_USER}:${PG_PASS}@127.0.0.1:${PG_PORT}/${PG_DB}"
MIGRATION_DSN="postgresql://${PG_USER}:${PG_PASS}@127.0.0.1:${PG_PORT}/${PG_DB}"
echo "==> alembic upgrade head"
POSTGRES_URL="$MIGRATION_DSN" python -m alembic \
  -c backend/database/migrations/alembic.ini upgrade head 2>&1 | tail -2

# ---------------------------------------------------------------------------
# 9. The environment file
# ---------------------------------------------------------------------------
cat > .phase99b.env <<ENV
# Phase 9.9B — disposable. Written by scripts/phase99b_provision.sh.
CORTEX_KUBERNETES_URL=https://127.0.0.1:${API_PORT}
CORTEX_KUBERNETES_TOKEN=${READER_TOKEN}
CORTEX_KUBERNETES_TENANT=${TENANT}
CORTEX_TLS_CA_BUNDLE=${WORKDIR}/ca-bundle.pem
CORTEX_P99B_WORKER_URL=https://127.0.0.1:${WORKER_HOSTPORT}
CORTEX_P99B_RESTART_TOKEN=${RESTART_TOKEN}
CORTEX_P99B_OTHER_TOKEN=${OTHER_TOKEN}
CORTEX_P99B_NAMESPACE=${NAMESPACE}
CORTEX_P99B_OTHER_NAMESPACE=${OTHER_NAMESPACE}
CORTEX_P99B_TARGET=${TARGET_DEPLOY}
CORTEX_P99B_BYSTANDER=${BYSTANDER_DEPLOY}
CORTEX_P99B_IMPL_DIGEST=${IMPL_DIGEST}
CORTEX_P99B_POD_MAX_PIDS=${POD_MAX_PIDS}
CORTEX_P99B_API_ENDPOINT=${API_ENDPOINT}
CORTEX_P99B_CAPABILITY_ID=${CAPABILITY_ID}
CORTEX_P99B_CAPABILITY_VERSION=${CAPABILITY_VERSION}
CORTEX_P99B_OPERATION=${OPERATION}
CORTEX_P99B_TENANT=${TENANT}
KUBECONFIG=${KUBECONFIG_PATH}
POSTGRES_URL=${MIGRATION_DSN}
CORTEX_DURABLE_URL=${DSN}
ENV

echo
echo "phase 9.9B environment ready"
echo "   worker:    https://127.0.0.1:${WORKER_HOSTPORT}  (in-cluster, out of CortexPrime's process)"
echo "   API:       https://127.0.0.1:${API_PORT}"
echo "   postgres:  ${PG_PORT}"
echo "   run: set -a; . ./.phase99b.env; set +a; python -m scripts.phase99b_contained_worker_harness"
