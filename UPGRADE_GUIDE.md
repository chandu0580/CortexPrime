# Upgrade Guide — CortexPrime v1.0.0-rc.1

## Overview

This guide covers upgrading an existing CortexPrime deployment to v1.0.0-rc.1.

> **Note**: This is the first Release Candidate. If upgrading from beta, see [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) instead.

---

## Upgrade Paths

| From | Method | Downtime | Risk |
|------|--------|----------|------|
| Fresh install | Docker Compose | N/A | None |
| Beta (pre-1.0.0) | Fresh install required | Full | Low |

---

## Pre-Upgrade Checklist

- [ ] Review [RELEASE_NOTES.md](./RELEASE_NOTES.md)
- [ ] Review [CHANGELOG.md](./CHANGELOG.md)
- [ ] Check [SUPPORT_MATRIX.md](./SUPPORT_MATRIX.md) for dependency versions
- [ ] Backup all databases (PostgreSQL, Redis, Neo4j)
- [ ] Backup configuration (`.env`, `docker-compose.yml`)
- [ ] Verify sufficient disk space (2× current usage)
- [ ] Notify users of expected downtime
- [ ] Run current certification suite to establish baseline

---

## Docker Compose Upgrade

### 1. Pull Latest Images

```bash
docker compose pull
```

### 2. Backup Data

```bash
# PostgreSQL
docker exec <postgres-container> pg_dump -U cortexprime cortexprime > pre_upgrade_backup.sql

# Redis
docker exec <redis-container> redis-cli SAVE
docker cp <redis-container>:/data/dump.rdb ./pre_upgrade_redis.rdb

# Neo4j
docker exec <neo4j-container> neo4j-admin dump --database=neo4j --to=/backups/pre_upgrade.dump
docker cp <neo4j-container>:/backups/pre_upgrade.dump ./
```

### 3. Update Configuration

```bash
# Backup current config
cp .env .env.pre_upgrade
cp docker-compose.yml docker-compose.pre_upgrade.yml

# Review new env template
cp .env.example .env
# Merge your custom settings from .env.pre_upgrade
```

### 4. Deploy New Version

```bash
docker compose -f docker-compose.prod.yml up -d
```

### 5. Verify Deployment

```bash
# Health check
curl http://localhost:8000/health

# Check services
docker compose ps

# View logs
docker compose logs --tail=50
```

### 6. Run Validation

```bash
# Run certification suite
python scripts/run_certification.py

# Verify telemetry
curl http://localhost:8000/api/telemetry/health

# Verify replay
curl http://localhost:8000/api/mission-replay/
```

---

## Kubernetes Upgrade

### 1. Update Helm Repo

```bash
helm repo update cortexprime
helm search repo cortexprime --versions
```

### 2. Review Values

```bash
helm show values cortexprime/cortexprime --version 1.0.0-rc.1 > new_values.yaml
# Compare with your current values.yaml
```

### 3. Upgrade Release

```bash
helm upgrade my-release cortexprime/cortexprime \
  --version 1.0.0-rc.1 \
  --values my-values.yaml \
  --atomic \
  --timeout 10m
```

### 4. Rollback if Needed

```bash
helm rollback my-release <revision>
```

---

## Post-Upgrade Validation

- [ ] All services show "healthy" status
- [ ] Mission execution succeeds
- [ ] Replay data accessible
- [ ] Connectors authenticated and syncing
- [ ] Workers responsive
- [ ] Notifications delivering
- [ ] Metrics populating
- [ ] Audit log recording

---

## Troubleshooting

### Service fails to start
```bash
docker compose logs <service-name>
# Check .env configuration
# Verify database connectivity
```

### Database connection errors
```bash
# Verify credentials in .env
# Check database is running: docker compose ps
# Test connection: docker compose exec backend python -c "from backend.database.engine import check_health; print(check_health())"
```

### Workers not responding
```bash
# Check worker logs
docker compose logs browser-worker
docker compose logs voice-worker
# Verify Playwright/Deepgram/ElevenLabs credentials
```

---

## Rollback Procedure

```bash
# Docker Compose
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.pre_upgrade.yml up -d

# Kubernetes
helm rollback my-release 0
```