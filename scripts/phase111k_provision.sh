#!/usr/bin/env bash
# Phase 11.1-K -- the disposable environment the Kubernetes reference connector
# is proven in. It provisions ONLY what an operator already owns before
# installing CortexPrime: a PostgreSQL (with TLS), a Vault (with TLS), and the
# namespaces. CortexPrime itself is installed by the Helm chart
# (helm/cortexprime-governed) -- the product's one setup path -- in the harness.
#
#   cluster        k3d cortex-p99b (disposable; created by phase99b_provision.sh)
#   namespaces     cortexprime (release), vault, cortex-conn-a (connected),
#                  cortex-conn-b (another tenant's namespace, never connected)
#   postgres       cortexprime/cortexprime-postgres, ssl=on, sslmode=require
#   vault          vault/vault, dev storage, TLS listener on :8200 whose
#                  certificate names vault.vault.svc; root token only for the
#                  one-time configuration (scripts/connector/configure_vault_kubernetes.sh)
#
# Usage:  bash scripts/phase111k_provision.sh        (create / refresh)
#         bash scripts/phase111k_provision.sh teardown
set -euo pipefail
kubectl() { command kubectl --request-timeout=60s "$@"; }

K3D="${K3D:-$HOME/bin/k3d.exe}"
CLUSTER=cortex-p99b
export KUBECONFIG="$PWD/.phase99b/kubeconfig"
WORK="$PWD/.phase111k"
REL=cortexprime
CONN=cortex-conn-a
OTHER=cortex-conn-b
VAULT_IMAGE=hashicorp/vault:1.17.6
PG_IMAGE=pgvector/pgvector:pg16
RUNTIME_IMAGE=cortexprime/governed-runtime:${RUNTIME_TAG:-1.0.0-b3}

if [ "${1:-create}" = "teardown" ]; then
  command -v helm >/dev/null 2>&1 && helm -n "$REL" uninstall cortexprime >/dev/null 2>&1 || true
  kubectl delete ns "$REL" vault "$CONN" "$OTHER" --ignore-not-found >/dev/null 2>&1 || true
  kubectl delete clusterrolebinding vault-auth-delegator --ignore-not-found >/dev/null 2>&1 || true
  rm -rf "$WORK" .phase111k.env
  echo "phase 11.1-K environment removed"
  exit 0
fi

[ -f "$KUBECONFIG" ] || { echo "run scripts/phase99b_provision.sh first (the disposable cluster)"; exit 1; }
mkdir -p "$WORK"

echo "==> images into the cluster (runtime, vault, postgres, redis)"
# Imported with the node's own containerd (`ctr images import`), one image at a
# time, and then CHECKED: under Docker Desktop's containerd store `k3d image
# import` reported "Successfully imported" while the node kept a stale image
# under the same tag, or none at all (Phase 11.1-K run 3). Build the runtime
# image with --platform linux/amd64 --provenance=false and a unique tag.
NODE="k3d-${CLUSTER}-server-0"
for image in "$RUNTIME_IMAGE" "$VAULT_IMAGE" "$PG_IMAGE" redis:7-alpine; do
  docker save --platform linux/amd64 "$image" -o "$WORK/image.tar"
  MSYS_NO_PATHCONV=1 docker cp "$WORK/image.tar" "$NODE:/tmp/image.tar"
  MSYS_NO_PATHCONV=1 docker exec "$NODE" ctr -n k8s.io images import --all-platforms /tmp/image.tar >/dev/null
  MSYS_NO_PATHCONV=1 docker exec "$NODE" rm -f /tmp/image.tar
  rm -f "$WORK/image.tar"
  docker exec "$NODE" crictl images | grep -q "${image%%:*} *${image##*:} "     || { echo "image $image is not in the node after import"; exit 1; }
done

echo "==> namespaces"
for ns in "$REL" vault "$CONN" "$OTHER"; do
  kubectl create ns "$ns" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
done

echo "==> test CA and server certificates (disposable)"
WINPWD=$(cygpath -m "$PWD" 2>/dev/null || pwd)
if [ ! -f "$WORK/ca.crt" ]; then
  MSYS_NO_PATHCONV=1 docker run --rm --entrypoint sh -v "${WINPWD}/.phase111k:/out" alpine/openssl -c '
    set -e; cd /out
    openssl req -x509 -newkey rsa:2048 -nodes -keyout ca.key -out ca.crt -days 30 -subj "/CN=phase111k-test-ca" 2>/dev/null
    for svc in vault.vault.svc cortexprime-postgres.cortexprime.svc; do
      name=${svc%%.*}
      printf "subjectAltName=DNS:%s,DNS:%s\n" "$svc" "${svc%.svc}" > $name.ext
      openssl req -newkey rsa:2048 -nodes -keyout $name.key -out $name.csr -subj "/CN=$svc" 2>/dev/null
      openssl x509 -req -in $name.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out $name.crt -days 30 -extfile $name.ext 2>/dev/null
    done
    chmod 644 *.key'
fi

echo "==> PostgreSQL with TLS"
PG_PASS_FILE="$WORK/pg.password"
[ -f "$PG_PASS_FILE" ] || python -c "import secrets;print(secrets.token_urlsafe(24))" > "$PG_PASS_FILE"
PG_PASS=$(tr -d '\r\n' < "$PG_PASS_FILE")
kubectl -n "$REL" create secret generic cortexprime-postgres-tls --from-file=tls.crt="$WORK/cortexprime-postgres.crt" \
  --from-file=tls.key="$WORK/cortexprime-postgres.key" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n "$REL" create secret generic cortexprime-postgres-auth --from-literal=password="$PG_PASS" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n "$REL" create secret generic cortexprime-db \
  --from-literal=url="postgresql://cortex:${PG_PASS}@cortexprime-postgres.cortexprime.svc:5432/cortexprime?sslmode=require" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: apps/v1
kind: Deployment
metadata: {name: cortexprime-postgres, namespace: ${REL}}
spec:
  replicas: 1
  selector: {matchLabels: {app: cortexprime-postgres}}
  template:
    metadata: {labels: {app: cortexprime-postgres}}
    spec:
      securityContext: {fsGroup: 999}
      containers:
        - name: postgres
          image: ${PG_IMAGE}
          imagePullPolicy: IfNotPresent
          args: ["-c", "ssl=on", "-c", "ssl_cert_file=/tls/tls.crt", "-c", "ssl_key_file=/tls/tls.key"]
          env:
            - {name: POSTGRES_USER, value: cortex}
            - {name: POSTGRES_DB, value: cortexprime}
            - name: POSTGRES_PASSWORD
              valueFrom: {secretKeyRef: {name: cortexprime-postgres-auth, key: password}}
            - {name: PGDATA, value: /var/lib/postgresql/data/pgdata}
          ports: [{containerPort: 5432}]
          volumeMounts:
            - {name: tls, mountPath: /tls, readOnly: true}
            - {name: data, mountPath: /var/lib/postgresql/data}
          readinessProbe:
            exec: {command: ["pg_isready", "-U", "cortex", "-d", "cortexprime"]}
            periodSeconds: 3
      volumes:
        - name: tls
          secret: {secretName: cortexprime-postgres-tls, defaultMode: 0640}
        - {name: data, emptyDir: {}}
---
apiVersion: v1
kind: Service
metadata: {name: cortexprime-postgres, namespace: ${REL}}
spec:
  selector: {app: cortexprime-postgres}
  ports: [{port: 5432, targetPort: 5432}]
YAML

echo "==> Vault with a TLS listener naming vault.vault.svc"
kubectl -n vault create secret generic vault-tls --from-file=tls.crt="$WORK/vault.crt" \
  --from-file=tls.key="$WORK/vault.key" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n "$REL" create secret generic vault-ca --from-file=ca.crt="$WORK/ca.crt" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: v1
kind: ServiceAccount
metadata: {name: vault, namespace: vault}
---
# Vault's own prerequisite for Kubernetes auth: TokenReview.
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: {name: vault-auth-delegator}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: system:auth-delegator}
subjects: [{kind: ServiceAccount, name: vault, namespace: vault}]
---
apiVersion: v1
kind: ConfigMap
metadata: {name: vault-listener, namespace: vault}
data:
  listener.hcl: |
    disable_mlock = true
    listener "tcp" {
      address       = "0.0.0.0:8200"
      tls_cert_file = "/vault/tls/tls.crt"
      tls_key_file  = "/vault/tls/tls.key"
    }
---
apiVersion: apps/v1
kind: Deployment
metadata: {name: vault, namespace: vault}
spec:
  replicas: 1
  selector: {matchLabels: {app: vault}}
  template:
    metadata: {labels: {app: vault}}
    spec:
      serviceAccountName: vault
      containers:
        - name: vault
          image: ${VAULT_IMAGE}
          imagePullPolicy: IfNotPresent
          args: ["server", "-dev", "-config=/vault/listener/listener.hcl"]
          env:
            - {name: SKIP_SETCAP, value: "true"}
            - {name: VAULT_DEV_ROOT_TOKEN_ID, value: root}
            - {name: VAULT_DEV_LISTEN_ADDRESS, value: "127.0.0.1:8201"}
          ports: [{containerPort: 8200}]
          volumeMounts:
            - {name: tls, mountPath: /vault/tls, readOnly: true}
            - {name: listener, mountPath: /vault/listener, readOnly: true}
          readinessProbe:
            httpGet: {path: /v1/sys/health, port: 8200, scheme: HTTPS}
            periodSeconds: 3
      volumes:
        - name: tls
          secret: {secretName: vault-tls}
        - name: listener
          configMap: {name: vault-listener}
---
apiVersion: v1
kind: Service
metadata: {name: vault, namespace: vault}
spec:
  selector: {app: vault}
  ports: [{port: 8200, targetPort: 8200}]
YAML

kubectl -n "$REL" rollout status deploy/cortexprime-postgres --timeout=240s >/dev/null
kubectl -n vault rollout status deploy/vault --timeout=240s >/dev/null

echo "==> configuring Vault for the connection (the operator's one-time step)"
VPOD=$(kubectl -n vault get pod -l app=vault -o jsonpath='{.items[0].metadata.name}')
kubectl -n vault exec -i "$VPOD" -- env VAULT_ADDR=http://127.0.0.1:8201 VAULT_TOKEN=root \
  CONNECTION_NAMESPACE="$CONN" RELEASE_NAMESPACE="$REL" sh -s < scripts/connector/configure_vault_kubernetes.sh

cat > .phase111k.env <<ENV
# Phase 11.1-K disposable environment -- written by scripts/phase111k_provision.sh
P111K_RELEASE_NAMESPACE=${REL}
P111K_CONNECTION_NAMESPACE=${CONN}
P111K_OTHER_NAMESPACE=${OTHER}
P111K_VAULT_ADDRESS=https://vault.vault.svc:8200
ENV
echo "phase 11.1-K environment ready (postgres+TLS, vault+TLS, namespaces ${CONN} ${OTHER})"
