# Migration Guide — Beta to v1.0.0-rc.1

## Important Notice

This is the first Release Candidate of CortexPrime. There is **no automated migration path** from earlier beta versions. A fresh installation is required.

If you are running a beta version (pre-1.0.0), follow this guide to migrate your data and configuration.

---

## Migration Overview

| Step | Description | Estimated Time |
|------|-------------|----------------|
| 1. Backup | Export all data from beta deployment | 30 min |
| 2. Install | Deploy fresh v1.0.0-rc.1 instance | 15 min |
| 3. Import | Restore mission data, replay events | 30 min |
| 4. Configure | Set up connectors, workers, secrets | 20 min |
| 5. Validate | Run certification suite | 10 min |

---

## Step 1: Backup Beta Data

### PostgreSQL
```bash
pg_dump -h <beta-host> -U cortexprime -d cortexprime > cortexprime_beta_backup.sql
```

### Redis
```bash
redis-cli -h <beta-host> SAVE
scp <beta-host>:/var/lib/redis/dump.rdb ./redis_beta_backup.rdb
```

### Neo4j
```bash
neo4j-admin dump --database=neo4j --to=neo4j_beta_backup.dump
```

### Configuration
```bash
cp .env .env_beta_backup
cp docker-compose.yml docker-compose_beta_backup.yml
```

---

## Step 2: Install v1.0.0-rc.1

```bash
# Clone the release
git clone https://github.com/cortexprime/cortexprime.git
cd cortexprime
git checkout v1.0.0-rc.1

# Configure
cp .env.example .env
# Edit .env with your settings

# Start
docker compose -f docker-compose.prod.yml up -d
```

---

## Step 3: Import Data

### PostgreSQL (selective import)
```bash
# Import only mission replay and memory data
pg_restore -h <new-host> -U cortexprime -d cortexprime \
  --data-only \
  --table=mission_replay_events \
  --table=episodic_memory \
  --table=semantic_memory \
  cortexprime_beta_backup.sql
```

### Redis
```bash
# Start fresh (replay data regenerates automatically)
```

### Neo4j
```bash
neo4j-admin load --database=neo4j --from=neo4j_beta_backup.dump
```

---

## Step 4: Reconfigure

Re-apply your configuration in the new `.env`:
- API keys (OpenAI, Deepgram, ElevenLabs, LiveKit)
- Database credentials
- Connector authentication
- JWT secrets

---

## Step 5: Validate

```bash
# Run certification
python scripts/run_certification.py

# Check health
curl http://localhost:8000/health

# Verify telemetry
curl http://localhost:8000/api/telemetry/health
```

---

## Breaking Changes from Beta

1. **API Prefix**: All API routes are now under `/api/` prefix
2. **Configuration Format**: `.env` format updated — review `.env.example`
3. **Database Schema**: Mission replay events table renamed and expanded
4. **Event Types**: Event type naming standardized (snake_case)
5. **Worker Configuration**: Worker config now under `workers/` in config directory

---

## Rollback

If migration fails, restore your beta deployment:

```bash
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose_beta_backup.yml up -d
```

---

## Support

- **Documentation**: See [Developer Portal](/developer-portal)
- **Issues**: https://github.com/cortexprime/cortexprime/issues