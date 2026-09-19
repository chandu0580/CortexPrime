#!/usr/bin/env bash
# Phase 11.4 (ADR-124) — provision the CONTAINED ROLLBACK worker beside the
# Phase 9.9B environment (cluster cortex-p99b, namespace cortex-p99b).
#
#   host                                    k3d cluster (disposable)
#   ────                                    ────────────────────────
#   CortexPrime ──envelope over HTTPS──►   contained-rollback-worker (Pod)
#   (governed chain)   127.0.0.1:18098       │ non-root, ro-rootfs, caps dropped
#        │             (socat forward)       │ stdlib only, ONE operation
#        │ governed READS (cortex-reader)    ▼
#        └──────────────────────────────►  API server ◄── GET deploy, LIST rs, PATCH deploy
#                                                          (cortex-rollbacker, ONE namespace)
#
# A third ServiceAccount, deliberately separate from the restarter: the rollback
# worker may read ReplicaSets (to find the approved revision's template itself)
# and patch Deployments, in one namespace, and nothing else. The restart worker
# keeps exactly its Phase 9.9B identity and cannot roll back.
#
# The worker is provisioned by the OPERATOR, never by CortexPrime (ADR-089).
#
# Usage:  bash scripts/phase114_provision.sh              (create/refresh + write .phase114.env)
#         bash scripts/phase114_provision.sh teardown     (remove only what this script created)
set -euo pipefail
kubectl() { command kubectl --request-timeout=45s "$@"; }

CLUSTER=cortex-p99b
NAMESPACE=cortex-p99b
OTHER_NAMESPACE=cortex-p99b-other
ROLLBACK_SA=cortex-rollbacker
WORKER_NAME=contained-rollback-worker
WORKER_IMAGE=cortexprime/contained-k8s-rollback:1.0.0
WORKER_NODEPORT=30098
WORKER_HOSTPORT=18098
FORWARDER=cortex-p114-rollback-fwd
K3D="${K3D:-$HOME/bin/k3d.exe}"
WORKDIR="$PWD/.phase114"
P99B="$PWD/.phase99b"
export KUBECONFIG="$P99B/kubeconfig"
TENANT="${TENANT:-dev}"
CAPABILITY_ID="platform.kubernetes.deployment.rollback"
CAPABILITY_VERSION=1
PROVIDER=kubernetes-contained-rollback
OPERATION=kubernetes.deployment.rollback

if [ "${1:-create}" = "teardown" ]; then
  docker rm -f "$FORWARDER" >/dev/null 2>&1 || true
  kubectl -n "$NAMESPACE" delete deploy "$WORKER_NAME" --ignore-not-found >/dev/null 2>&1 || true
  kubectl -n "$NAMESPACE" delete svc "$WORKER_NAME" --ignore-not-found >/dev/null 2>&1 || true
  kubectl -n "$NAMESPACE" delete networkpolicy "${WORKER_NAME}-egress" --ignore-not-found >/dev/null 2>&1 || true
  kubectl -n "$NAMESPACE" delete secret rollback-worker-tls --ignore-not-found >/dev/null 2>&1 || true
  kubectl -n "$NAMESPACE" delete rolebinding "$ROLLBACK_SA" --ignore-not-found >/dev/null 2>&1 || true
  kubectl -n "$NAMESPACE" delete role "$ROLLBACK_SA" --ignore-not-found >/dev/null 2>&1 || true
  kubectl -n "$NAMESPACE" delete sa "$ROLLBACK_SA" --ignore-not-found >/dev/null 2>&1 || true
  rm -rf "$WORKDIR" .phase114.env
  echo "phase 11.4 rollback worker removed (the 9.9B environment is untouched)"
  exit 0
fi

[ -f "$KUBECONFIG" ] || { echo "the Phase 9.9B environment is required (bash scripts/phase99b_provision.sh)"; exit 1; }
mkdir -p "$WORKDIR"
WINPWD=$(pwd -W 2>/dev/null || pwd)

echo "==> building the contained rollback worker image"
IMPL_DIGEST=$(python -c "
import hashlib
print(hashlib.sha256(open('workers/contained_k8s_rollback/worker.py','rb').read()).hexdigest())
")
echo "   implementation digest: ${IMPL_DIGEST:0:16}..."
docker build -q -t "$WORKER_IMAGE" workers/contained_k8s_rollback >/dev/null
timeout 240 "$K3D" image import "$WORKER_IMAGE" -c "$CLUSTER" >/dev/null 2>&1 \
  || { echo "   image import failed"; exit 1; }

# ---------------------------------------------------------------------------
# TLS. The rollback worker gets its own certificate. The restart worker's 2-day
# certificate (ADR-089) is re-minted here too when it expires within 6 hours,
# because the governance chain drives the restart worker and a certificate that
# lapses mid-chain reads as a regression (Phase 10.14).
# ---------------------------------------------------------------------------
cert_expires_soon() {  # file
  [ -f "$1" ] || return 0
  ! openssl x509 -in "$1" -noout -checkend 21600 >/dev/null 2>&1
}
echo "==> TLS material"
if cert_expires_soon "$WORKDIR/rollback-worker.crt"; then
  MSYS_NO_PATHCONV=1 docker run --rm -v "${WINPWD}/.phase114:/out" alpine/openssl \
    req -x509 -newkey rsa:2048 -nodes -days 7 \
    -keyout /out/rollback-worker.key -out /out/rollback-worker.crt \
    -subj "/CN=cortex-contained-rollback-worker" \
    -addext "subjectAltName=IP:127.0.0.1,DNS:localhost" >/dev/null 2>&1
fi
if cert_expires_soon "$P99B/worker.crt"; then
  echo "   the restart worker certificate expires within 6h: re-minting it"
  cp "$P99B/worker.crt" "$P99B/worker.crt.expiring.bak" 2>/dev/null || true
  MSYS_NO_PATHCONV=1 docker run --rm -v "${WINPWD}/.phase99b:/out" alpine/openssl \
    req -x509 -newkey rsa:2048 -nodes -days 2 \
    -keyout /out/worker.key -out /out/worker.crt \
    -subj "/CN=cortex-contained-worker" \
    -addext "subjectAltName=IP:127.0.0.1,DNS:localhost" >/dev/null 2>&1
  kubectl -n "$NAMESPACE" delete secret worker-tls >/dev/null 2>&1 || true
  kubectl -n "$NAMESPACE" create secret tls worker-tls --cert="$P99B/worker.crt" --key="$P99B/worker.key" >/dev/null
  kubectl -n "$NAMESPACE" rollout restart deploy/contained-worker >/dev/null
  kubectl -n "$NAMESPACE" rollout status deploy/contained-worker --timeout=180s >/dev/null
  cat "$P99B/cluster-ca.crt" "$P99B/worker.crt" > "$P99B/ca-bundle.pem"
fi
kubectl -n "$NAMESPACE" delete secret rollback-worker-tls >/dev/null 2>&1 || true
kubectl -n "$NAMESPACE" create secret tls rollback-worker-tls \
  --cert="$WORKDIR/rollback-worker.crt" --key="$WORKDIR/rollback-worker.key" >/dev/null
cat "$P99B/cluster-ca.crt" "$P99B/worker.crt" "$WORKDIR/rollback-worker.crt" > "$WORKDIR/ca-bundle.pem"

# ---------------------------------------------------------------------------
# Least privilege. Namespace Role, explicit verbs, no wildcard, no cluster role.
# ---------------------------------------------------------------------------
echo "==> RBAC for ${ROLLBACK_SA} (namespace-scoped, explicit verbs)"
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: v1
kind: ServiceAccount
metadata: {name: ${ROLLBACK_SA}, namespace: ${NAMESPACE}}
automountServiceAccountToken: false
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: {name: ${ROLLBACK_SA}, namespace: ${NAMESPACE}}
rules:
  # Read the Deployment it is asked about and write its pod template back to a
  # revision the controller already holds. No update, no delete, no subresource.
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "patch"]
  # Find the approved revision's template in the Deployment's own ReplicaSets.
  # List only: it never writes a ReplicaSet.
  - apiGroups: ["apps"]
    resources: ["replicasets"]
    verbs: ["list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: ${ROLLBACK_SA}, namespace: ${NAMESPACE}}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: Role, name: ${ROLLBACK_SA}}
subjects:
  - {kind: ServiceAccount, name: ${ROLLBACK_SA}, namespace: ${NAMESPACE}}
YAML

echo "==> deploying the contained rollback worker"
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: apps/v1
kind: Deployment
metadata: {name: ${WORKER_NAME}, namespace: ${NAMESPACE}}
spec:
  replicas: 1
  selector:
    matchLabels: {app: ${WORKER_NAME}}
  template:
    metadata:
      labels: {app: ${WORKER_NAME}}
    spec:
      serviceAccountName: ${ROLLBACK_SA}
      # The worker holds no standing credential: the token arrives per execution
      # as the connection's authorization header, from the platform's broker.
      automountServiceAccountToken: false
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
          volumeMounts:
            - {name: tmp, mountPath: /tmp}
            - {name: tls, mountPath: /tls, readOnly: true}
            - {name: kube-ca, mountPath: /var/run/secrets/kubernetes.io/serviceaccount, readOnly: true}
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
          secret: {secretName: rollback-worker-tls, defaultMode: 0444}
        # The cluster CA only (to verify the API server). No token is mounted.
        - name: kube-ca
          configMap:
            name: kube-root-ca.crt
            items: [{key: ca.crt, path: ca.crt}]
---
apiVersion: v1
kind: Service
metadata: {name: ${WORKER_NAME}, namespace: ${NAMESPACE}}
spec:
  type: NodePort
  selector: {app: ${WORKER_NAME}}
  ports:
    - {port: 8080, targetPort: 8080, nodePort: ${WORKER_NODEPORT}}
YAML

echo "==> restricting rollback worker egress (API server + DNS only)"
API_ENDPOINT=$(kubectl get endpoints kubernetes -n default -o jsonpath='{.subsets[0].addresses[0].ip}')
API_ENDPOINT_PORT=$(kubectl get endpoints kubernetes -n default -o jsonpath='{.subsets[0].ports[0].port}')
DNS_IP=$(kubectl get svc -n kube-system kube-dns -o jsonpath='{.spec.clusterIP}')
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: ${WORKER_NAME}-egress, namespace: ${NAMESPACE}}
spec:
  podSelector: {matchLabels: {app: ${WORKER_NAME}}}
  policyTypes: ["Egress"]
  egress:
    - to: [{ipBlock: {cidr: ${API_ENDPOINT}/32}}]
      ports: [{protocol: TCP, port: ${API_ENDPOINT_PORT}}]
    - to: [{ipBlock: {cidr: ${DNS_IP}/32}}]
      ports: [{protocol: UDP, port: 53}, {protocol: TCP, port: 53}]
YAML
kubectl -n "$NAMESPACE" rollout status deploy/"$WORKER_NAME" --timeout=180s

# ---------------------------------------------------------------------------
# Host reachability. The cluster was created (Phase 9.9B, --no-lb) with only
# the restart worker's port mapped, and k3d cannot add a port to a node without
# a load balancer. A TCP forwarder on the cluster's docker network carries the
# connection; TLS is end to end between the platform and the worker, so the
# forwarder never sees a credential.
# ---------------------------------------------------------------------------
echo "==> host forwarder 127.0.0.1:${WORKER_HOSTPORT} -> node:${WORKER_NODEPORT}"
docker rm -f "$FORWARDER" >/dev/null 2>&1 || true
docker run -d --name "$FORWARDER" --network "k3d-${CLUSTER}" -p "127.0.0.1:${WORKER_HOSTPORT}:${WORKER_HOSTPORT}" \
  alpine/socat "tcp-listen:${WORKER_HOSTPORT},fork,reuseaddr" "tcp-connect:k3d-${CLUSTER}-server-0:${WORKER_NODEPORT}" >/dev/null
for _ in $(seq 1 30); do
  curl -s --cacert "$WORKDIR/rollback-worker.crt" "https://127.0.0.1:${WORKER_HOSTPORT}/healthz" >/dev/null 2>&1 && break
  sleep 1
done
curl -s --cacert "$WORKDIR/rollback-worker.crt" "https://127.0.0.1:${WORKER_HOSTPORT}/healthz" | grep -q '"ok"' \
  || { echo "   the rollback worker is not reachable over verified TLS"; exit 1; }

echo "==> verifying least privilege against the live API server (token-only identity)"
SERVER=$(grep -oE 'server: .*' "$KUBECONFIG" | head -1 | awk '{print $2}')
TOKEN=$(kubectl -n "$NAMESPACE" create token "$ROLLBACK_SA" --duration=24h)
can() {  # verb resource namespace [subresource]
  local extra=()
  [ -n "${4:-}" ] && extra=(--subresource="$4")
  command kubectl --kubeconfig=/dev/null --server="$SERVER" --certificate-authority="$P99B/cluster-ca.crt" \
    --token="$TOKEN" --request-timeout=30s auth can-i "$1" "$2" -n "$3" "${extra[@]}" 2>/dev/null | head -1 || true
}
check() {  # want verb resource namespace [subresource]
  local got; got=$(can "$2" "$3" "$4" "${5:-}"); [ -n "$got" ] || got=no
  printf "   %-7s %-22s %-10s ns=%-20s %-4s (want %s)\n" "$2" "$3" "${5:-}" "$4" "$got" "$1"
  [ "$got" = "$1" ] || { echo "   RBAC IS NOT AS DECLARED"; exit 1; }
}
check yes get deployments "$NAMESPACE"
check yes patch deployments "$NAMESPACE"
check yes list replicasets "$NAMESPACE"
check no update deployments "$NAMESPACE"
check no delete deployments "$NAMESPACE"
check no patch deployments "$NAMESPACE" scale
check no patch replicasets "$NAMESPACE"
check no delete replicasets "$NAMESPACE"
check no create pods "$NAMESPACE"
check no delete pods "$NAMESPACE"
check no create pods "$NAMESPACE" exec
check no get secrets "$NAMESPACE"
check no patch deployments "$OTHER_NAMESPACE"
check no patch deployments default
check no escalate roles "$NAMESPACE"
check no bind rolebindings "$NAMESPACE"
check no impersonate serviceaccounts "$NAMESPACE"
printf '%s' "$TOKEN" > "$WORKDIR/rollback.token"
chmod 600 "$WORKDIR/rollback.token" 2>/dev/null || true
unset TOKEN

cat > .phase114.env <<ENV
# Phase 11.4 — disposable. Written by scripts/phase114_provision.sh. No credential in this file.
CORTEX_ROLLBACK_WORKER_URL=https://127.0.0.1:${WORKER_HOSTPORT}
CORTEX_ROLLBACK_CAPABILITY_ID=${CAPABILITY_ID}
CORTEX_ROLLBACK_CAPABILITY_VERSION=${CAPABILITY_VERSION}
CORTEX_ROLLBACK_IMPL_DIGEST=${IMPL_DIGEST}
CORTEX_P114_CA_BUNDLE=${WORKDIR}/ca-bundle.pem
CORTEX_P114_ROLLBACK_TOKEN_FILE=${WORKDIR}/rollback.token
CORTEX_P114_WORKER_NAME=${WORKER_NAME}
CORTEX_P114_NAMESPACE=${NAMESPACE}
ENV
echo "phase 11.4 rollback worker ready: https://127.0.0.1:${WORKER_HOSTPORT} (digest ${IMPL_DIGEST:0:16}...)"
