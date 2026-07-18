#!/bin/bash
# ==============================================================
# CortexPrime — Kubernetes Bootstrap
# ==============================================================
# Sets up the cortexprime namespace, secrets, and core
# infrastructure on a fresh Kubernetes cluster.
# ==============================================================
set -euo pipefail

NAMESPACE="${1:-cortexprime}"
K8S_DIR="infra/kubernetes"

echo "=== CortexPrime K8s Bootstrap ==="
echo "Namespace: $NAMESPACE"
echo ""

# 1. Create namespace
echo ">>> Creating namespace..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# 2. Apply core infrastructure
echo ">>> Deploying core infrastructure..."
kubectl apply -f "${K8S_DIR}/infrastructure/postgres.yaml" -n "$NAMESPACE"
kubectl apply -f "${K8S_DIR}/infrastructure/redis.yaml" -n "$NAMESPACE"
kubectl apply -f "${K8S_DIR}/infrastructure/rabbitmq.yaml" -n "$NAMESPACE"
kubectl apply -f "${K8S_DIR}/infrastructure/neo4j.yaml" -n "$NAMESPACE"
kubectl apply -f "${K8S_DIR}/infrastructure/ingress-and-storage.yaml" -n "$NAMESPACE"

# 3. Apply network policies
echo ">>> Applying network policies..."
if [ -f "${K8S_DIR}/network-policies.yaml" ]; then
    kubectl apply -f "${K8S_DIR}/network-policies.yaml" -n "$NAMESPACE"
fi

# 4. Wait for infrastructure to be ready
echo ">>> Waiting for infrastructure pods..."
kubectl wait --for=condition=ready pod \
    -l app=cortexprime \
    -n "$NAMESPACE" \
    --timeout=300s 2>/dev/null || true

# 5. Deploy application
echo ">>> Deploying application services..."
kubectl apply -f "${K8S_DIR}/backend/deployment.yaml" -n "$NAMESPACE"
kubectl apply -f "${K8S_DIR}/frontend/deployment.yaml" -n "$NAMESPACE"

# 6. Wait for application to be ready
echo ">>> Waiting for application pods..."
kubectl wait --for=condition=ready pod \
    -l app=cortexprime \
    -n "$NAMESPACE" \
    --timeout=300s 2>/dev/null || true

# 7. Show status
echo ">>> Cluster status:"
kubectl get pods,svc,ingress -n "$NAMESPACE"

echo ""
echo "=== K8s bootstrap complete ==="
echo ""
echo "To expose the ingress, ensure your DNS points to the ingress controller:"
echo "  api.cortexprime.ai -> <ingress-controller-external-ip>"
echo "  app.cortexprime.ai -> <ingress-controller-external-ip>"
