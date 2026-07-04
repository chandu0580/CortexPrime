# ==============================================================
# CortexPrime — Operations Guide
# ==============================================================

## Table of Contents
1. Deployment Guide
2. Configuration Guide
3. Disaster Recovery
4. Backup and Restore
5. Scaling Guidance
6. Runbook

---

## 1. Deployment Guide

### Prerequisites

- Docker 24+ and Docker Compose v2
- Kubernetes 1.28+ (for K8s deployment)
- Helm 3.12+ (for Helm deployment)
- At least 4 CPU cores and 8GB RAM for the full stack

### Quick Start (Docker Compose)

```bash
# 1. Clone and configure
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys and passwords

# 2. Start all services
docker compose up -d

# 3. Verify health
curl http://localhost:8000/health
```

### Production Deployment (Docker Compose)

```bash
# 1. Generate TLS certificates
bash scripts/generate-certs.sh

# 2. Start with production overlay
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 3. Verify nginx termination
curl https://localhost/health -k
```

### Kubernetes Deployment

```bash
# 1. Create namespace and secrets
kubectl create namespace cortexprime
kubectl apply -f infra/kubernetes/infrastructure/postgres.yaml
kubectl apply -f infra/kubernetes/infrastructure/redis.yaml
kubectl apply -f infra/kubernetes/infrastructure/rabbitmq.yaml
kubectl apply -f infra/kubernetes/infrastructure/neo4j.yaml
kubectl apply -f infra/kubernetes/infrastructure/ingress-and-storage.yaml
kubectl apply -f infra/kubernetes/backend/deployment.yaml
kubectl apply -f infra/kubernetes/frontend/deployment.yaml

# 2. Verify all pods are running
kubectl get pods -n cortexprime -w
```

### Helm Deployment

```bash
# 1. Create secrets file
cat > secrets.yaml <<EOF
secrets:
  postgresPassword: "<secure-password>"
  redisPassword: "<secure-password>"
  rabbitmqPassword: "<secure-password>"
  neo4jPassword: "<secure-password>"
  jwtSecretKey: "<64-char-random>"
  jwtRefreshSecret: "<64-char-random>"
  openaiApiKey: "<key>"
EOF

# 2. Install
helm upgrade --install cortexprime infra/helm/cortexprime \
  --namespace cortexprime --create-namespace \
  -f configs/environments/production.yaml \
  -f secrets.yaml

# 3. Monitor rollout
kubectl rollout status deployment/cortexprime-backend -n cortexprime
```

---

## 2. Configuration Guide

### Environment Matrix

| Setting | Development | Testing | Staging | Production | Air-Gapped |
|---------|-------------|---------|---------|------------|------------|
| ENVIRONMENT | development | test | staging | production | air-gapped |
| Auth | Disabled | Disabled | Required | Required | Required |
| Rate Limiting | Off | Off | On | On | On |
| Embedding Validation | Off | Off | On | On | On |
| Migration Blocking | Off | Off | On | On | On |
| Structured Logging | On | Off | On | On | On |

### Required Environment Variables

| Variable | Description | Source |
|----------|-------------|--------|
| JWT_SECRET_KEY | 64-char random for token signing | Generated |
| JWT_REFRESH_SECRET | 64-char random for refresh tokens | Generated |
| POSTGRES_PASSWORD | PostgreSQL password | Generated |
| REDIS_PASSWORD | Redis password | Generated |
| RABBITMQ_PASSWORD | RabbitMQ password | Generated |
| NEO4J_PASSWORD | Neo4j password | Generated |
| OPENAI_API_KEY | OpenAI API key | OpenAI |
| AZURE_OPENAI_API_KEY | Azure OpenAI key | Azure |
| ANTHROPIC_API_KEY | Anthropic API key | Anthropic |
| TAVILY_API_KEY | Tavily search API key | Tavily |

All secrets must be stored in a vault (HashiCorp Vault, Azure Key Vault, AWS Secrets Manager) in production. Never commit secrets to source code.

---

## 3. Disaster Recovery

### Recovery Strategy

| Scenario | RTO | RPO | Recovery Method |
|----------|-----|-----|-----------------|
| Pod crash | < 30s | N/A | Kubernetes auto-restart |
| Node failure | < 5m | N/A | Pod reschedule |
| Full AZ outage | < 30m | 5m | Multi-AZ deployment |
| Data corruption | < 2h | 24h | Point-in-time recovery |
| Accidental deletion | < 2h | 24h | PVC snapshot restore |
| Full region outage | < 4h | 1h | DR region failover |

### Recovery Steps

1. **Verify the issue scope**
   ```bash
   kubectl get pods -n cortexprime -o wide
   kubectl logs -n cortexprime deployment/cortexprime-backend --tail=50
   ```

2. **Restart degraded services**
   ```bash
   kubectl rollout restart deployment/cortexprime-backend -n cortexprime
   ```

3. **Restore database from backup**
   ```bash
   # Restore PostgreSQL
   pg_restore -U cortex -d cortexdb -1 latest_backup.dump

   # Restore Neo4j
   neo4j-admin load --from=backup.dump
   ```

4. **Verify recovery**
   ```bash
   curl https://api.cortexprime.ai/health/system
   ```

---

## 4. Backup and Restore

### PostgreSQL

```bash
# Automated daily backup
pg_dump -U cortex -d cortexdb -F c -f /backups/cortexdb_$(date +%Y%m%d).dump

# Point-in-time recovery
pg_restore -U cortex -d cortexdb -1 /backups/cortexdb_20260101.dump
```

### Redis

```bash
# Redis is configured with AOF persistence
# Backups are at /data/appendonly.aof

# Manual save
redis-cli -a $REDIS_PASSWORD SAVE
```

### Neo4j

```bash
# Online backup
neo4j-admin database dump neo4j --to=/backups/neo4j_$(date +%Y%m%d).dump

# Restore
neo4j-admin database load neo4j --from=/backups/neo4j_20260101.dump
```

### Kubernetes PVC Snapshots

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: cortexprime-postgres-snapshot-20260101
spec:
  volumeSnapshotClassName: csi-cinder-snapclass
  source:
    persistentVolumeClaimName: postgres-data-cortexprime-postgres-0
```

---

## 5. Scaling Guidance

### Horizontal Pod Autoscaling

| Component | Min | Max | CPU Trigger | Memory Trigger |
|-----------|-----|-----|-------------|----------------|
| Backend | 2 | 10 | 70% | 80% |
| Frontend | 2 | 6 | 70% | — |

### Vertical Resource Recommendations

| Component | Request CPU | Request Memory | Limit CPU | Limit Memory |
|-----------|-------------|----------------|-----------|--------------|
| Backend | 500m | 512Mi | 2 | 2Gi |
| Frontend | 250m | 128Mi | 1 | 512Mi |
| PostgreSQL | 500m | 1Gi | 1 | 2Gi |
| Redis | 250m | 256Mi | 500m | 512Mi |
| RabbitMQ | 250m | 256Mi | 500m | 512Mi |
| Neo4j | 500m | 512Mi | 1 | 1Gi |

### Storage Requirements

| Component | Storage | Growth Rate | Retention |
|-----------|---------|-------------|-----------|
| PostgreSQL | 50Gi | ~1GB/day | 90 days |
| Redis | 10Gi | ~500MB/day | 7 days |
| RabbitMQ | 10Gi | ~200MB/day | 7 days |
| Neo4j | 20Gi | ~500MB/day | 30 days |
| Chroma | 10Gi | ~100MB/day | 30 days |

---

## 6. Runbook

### Alert: Backend Pod Failing Health Checks

1. Check pod status
   ```bash
   kubectl describe pod -n cortexprime -l app=cortexprime,component=backend
   ```
2. Check logs
   ```bash
   kubectl logs -n cortexprime deployment/cortexprime-backend --tail=100
   ```
3. Check dependent services
   ```bash
   kubectl get pods -n cortexprime
   ```
4. Restart if needed
   ```bash
   kubectl rollout restart deployment/cortexprime-backend -n cortexprime
   ```

### Alert: Database Connection Failures

1. Check PostgreSQL pod
   ```bash
   kubectl exec -n cortexprime deploy/cortexprime-postgres-0 -- pg_isready -U cortex
   ```
2. Check disk space
   ```bash
   kubectl exec -n cortexprime deploy/cortexprime-postgres-0 -- df -h
   ```
3. Check PostgreSQL logs
   ```bash
   kubectl logs -n cortexprime statefulset/cortexprime-postgres --tail=50
   ```
4. Verify connection string in backend config
   ```bash
   kubectl describe configmap cortexprime-backend-config -n cortexprime
   ```

### Alert: High Memory Usage

1. Identify top consumers
   ```bash
   kubectl top pods -n cortexprime
   ```
2. Check individual pod resource usage
   ```bash
   kubectl top pod -n cortexprime cortexprime-backend-xxxxx
   ```
3. Verify HPA metrics
   ```bash
   kubectl describe hpa -n cortexprime
   ```
4. Scale manually if HPA is not responding
   ```bash
   kubectl scale deployment/cortexprime-backend -n cortexprime --replicas=5
   ```

### Alert: Redis Connection Lost

1. Check Redis pod
   ```bash
   kubectl exec -n cortexprime statefulset/cortexprime-redis-0 -- redis-cli ping
   ```
2. Check Redis logs
   ```bash
   kubectl logs -n cortexprime statefulset/cortexprime-redis --tail=30
   ```
3. Verify network policy
   ```bash
   kubectl get networkpolicies -n cortexprime
   ```
4. Backend enters degraded mode automatically (in-memory fallback)

### Alert: Neo4j Connection Lost

1. Check Neo4j pod
   ```bash
   kubectl exec -n cortexprime statefulset/cortexprime-neo4j-0 -- curl -s http://localhost:7474
   ```
2. Check Neo4j logs
   ```bash
   kubectl logs -n cortexprime statefulset/cortexprime-neo4j --tail=30
   ```
3. Backend enters degraded mode automatically

### Graceful Shutdown Procedure

```bash
# 1. Drain backend pods (completes in-flight missions)
kubectl rollout pause deployment/cortexprime-backend -n cortexprime
kubectl delete pod -n cortexprime -l app=cortexprime,component=backend --grace-period=120

# 2. Scale down frontend
kubectl scale deployment/cortexprime-frontend -n cortexprime --replicas=0

# 3. Stop data services (after verifying all missions complete)
kubectl scale statefulset/cortexprime-postgres -n cortexprime --replicas=0
kubectl scale statefulset/cortexprime-redis -n cortexprime --replicas=0
kubectl scale statefulset/cortexprime-neo4j -n cortexprime --replicas=0
kubectl scale statefulset/cortexprime-rabbitmq -n cortexprime --replicas=0
```

### Cold Start Verification

```bash
# After full deployment, verify:

# 1. All pods running
kubectl get pods -n cortexprime
# Expected: all pods in Running/Ready state

# 2. Health endpoints respond
curl https://api.cortexprime.ai/health
# Expected: {"status": "healthy"}

# 3. All subsystems online
curl https://api.cortexprime.ai/health/system
# Expected: overall status "healthy"

# 4. Database migrated
curl https://api.cortexprime.ai/health/database
# Expected: {"status": "healthy", "migration": {"up_to_date": true}}

# 5. Embeddings validated
curl https://api.cortexprime.ai/health/embeddings
# Expected: {"embedding_status": "healthy"}

# 6. Auth operational
curl https://api.cortexprime.ai/health/auth
# Expected: {"status": "healthy"}

# 7. Mission execution works
curl -X POST https://api.cortexprime.ai/api/mission-library/missions/knowledge_discovery/execute \
  -H "Content-Type: application/json" \
  -d '{"params": {"topic": "CortexPrime platform", "context": "Verify cold start", "focus_areas": "architecture,capabilities", "sources": "internal"}}'
# Expected: {"status": "completed"}
```