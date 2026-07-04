# CortexPrime v1.0.0 GA — Troubleshooting Guide

A comprehensive reference for diagnosing and resolving common issues in CortexPrime deployments.

---

## Table of Contents

1. [Installation Issues](#1-installation-issues)
2. [Configuration Issues](#2-configuration-issues)
3. [Authentication Issues](#3-authentication-issues)
4. [Mission Execution Issues](#4-mission-execution-issues)
5. [Worker Issues](#5-worker-issues)
6. [Connector Issues](#6-connector-issues)
7. [Database Issues](#7-database-issues)
8. [Memory Issues](#8-memory-issues)
9. [Knowledge Graph Issues](#9-knowledge-graph-issues)
10. [Replay Issues](#10-replay-issues)
11. [Observability Issues](#11-observability-issues)
12. [Performance Issues](#12-performance-issues)
13. [UI Issues](#13-ui-issues)
14. [Diagnostic Commands](#14-diagnostic-commands)
15. [Support Escalation](#15-support-escalation)

---

## 1. Installation Issues

### Docker Compose Fails

**Symptom:** `docker compose up` exits with non-zero code or services fail to start.

**Cause:** Missing or outdated Docker Compose version, incompatible Docker engine, or resource limits.

**Solution:**
```bash
# Verify Docker Compose version (requires v2.20+)
docker compose version

# Check Docker engine compatibility
docker info | grep -i "server version"

# Increase Docker memory limits (Docker Desktop → Settings → Resources)
# Minimum: 8 GB RAM, 4 CPUs, 64 GB disk

# Validate compose file syntax
docker compose config
```

**Prevention:** Pin Docker Compose version in CI/CD and run `docker compose config` in pre-flight checks.

---

### Port Conflicts

**Symptom:** `Error: listen tcp 0.0.0.0:8080: bind: address already in use`

**Cause:** Another process occupies the required port.

**Solution:**
```bash
# Identify the process holding the port
netstat -ano | findstr :8080
# or on Linux/macOS:
lsof -i :8080

# Stop the conflicting process or change the port in docker-compose.yml:
services:
  cortexprime-api:
    ports:
      - "9090:8080"  # map host 9090 to container 8080
```

**Prevention:** Use ephemeral ports in development and document all port reservations.

---

### Permission Errors

**Symptom:** `Permission denied` on volumes, certificates, or config files.

**Cause:** Container runs as non-root user but volume files are owned by root (Linux) or improper file permissions.

**Solution:**
```bash
# Fix volume ownership (Linux)
sudo chown -R 1000:1000 ./data ./logs

# On Windows, ensure shared drives are enabled in Docker Desktop
# Settings → Resources → File Sharing

# Set correct file permissions for secrets
chmod 600 ./secrets/*.pem
```

**Prevention:** Use Docker `user:` directive matching host UID/GID and include `.env` templates with ownership notes.

---

### Missing Dependencies

**Symptom:** `ModuleNotFoundError: No module named 'cortexprime'` or `npm ERR! missing script: start`.

**Cause:** Incomplete installation, missing Node.js/Python runtime, or broken `node_modules`.

**Solution:**
```bash
# Verify runtime versions
node --version   # >= 20 LTS
python --version # >= 3.11
npm --version    # >= 10

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Python dependencies
pip install -r requirements.txt
```

**Prevention:** Use `.nvmrc` and `runtime.txt` to pin versions; run `npm ci` (not `npm install`) in CI.

---

### Database Connection Failures

**Symptom:** `connect ECONNREFUSED 127.0.0.1:5432` or `could not connect to server: Connection refused`.

**Cause:** Database container not ready, wrong host/port, or network isolation.

**Solution:**
```bash
# Check if the database container is running
docker ps --filter "name=postgres"

# Verify connectivity from the app container
docker exec cortexprime-api ping postgres

# Use the wait-for-it script
./scripts/wait-for-it.sh postgres:5432 -- npm start
```

**Prevention:** Use Docker Compose `depends_on` with health checks and a wait-for-it init container.

---

## 2. Configuration Issues

### Invalid Environment Variables

**Symptom:** `Error: Invalid configuration value for CORTEXPRIME_LOG_LEVEL: expected one of [debug, info, warn, error]`.

**Cause:** Typo, wrong case, or unsupported value in `.env` or environment.

**Solution:**
```bash
# Validate all env vars against the schema
npm run validate:env

# Check for syntax errors in .env files
cat .env | grep -v '^\s*#' | grep -v '^\s*$' | while IFS='=' read -r key val; do
  if [ -z "$val" ]; then echo "WARN: $key is empty"; fi
done
```

**Prevention:** Run `validate:env` as a pre-start hook. Use a JSON schema for environment validation.

---

### Wrong Database URLs

**Symptom:** `SequelizeConnectionError: getaddrinfo ENOTFOUND wrong-hostname`.

**Cause:** `DATABASE_URL` points to a non-existent host, wrong port, or wrong database name.

**Solution:**
```bash
# Test the connection string
psql "$DATABASE_URL" -c "SELECT 1;"

# Correct format:
# DATABASE_URL=postgresql://user:password@host:5432/cortexprime
```

**Prevention:** Store connection strings in a secrets manager; validate via `DATABASE_URL` schema in CI.

---

### Certificate Errors

**Symptom:** `Error: self-signed certificate in certificate chain` or `UNABLE_TO_GET_ISSUER_CERT_LOCALLY`.

**Cause:** Expired TLS certificates, missing CA bundle, or using self-signed certs without trust.

**Solution:**
```bash
# Check certificate expiry
openssl x509 -in cert.pem -noout -dates

# Add CA to trusted store (Linux)
sudo cp ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates

# For Node.js, set the CA bundle path:
export NODE_EXTRA_CA_CERTS=/path/to/ca-bundle.crt
```

**Prevention:** Use certbot/Let's Encrypt for auto-renewal; monitor cert expiry with Prometheus.

---

### Timezone Mismatches

**Symptom:** Scheduled missions run at wrong times; timestamps in logs differ from expected.

**Cause:** Container timezone differs from host or application config.

**Solution:**
```yaml
# docker-compose.yml
services:
  cortexprime-api:
    environment:
      - TZ=UTC
```

```bash
# Verify timezone inside container
docker exec cortexprime-api date
docker exec cortexprime-api cat /etc/timezone
```

**Prevention:** Always set `TZ=UTC` in containers. Store all timestamps in UTC and convert on display.

---

## 3. Authentication Issues

### JWT Token Expired

**Symptom:** `401 Unauthorized: jwt expired` or `TokenExpiredError`.

**Cause:** Token lifetime exceeded (default 1 hour); clock skew between services.

**Solution:**
```bash
# Decode and inspect a JWT
echo $JWT | jwt-cli decode -

# Refresh the token
curl -X POST https://cortexprime.example.com/api/v1/auth/refresh \
  -H "Authorization: Bearer $REFRESH_TOKEN"

# Increase token expiry in config if appropriate:
# AUTH_JWT_EXPIRES_IN=8h
```

**Prevention:** Implement automatic token refresh in clients. Set `AUTH_JWT_CLOCK_TOLERANCE=30` seconds.

---

### Invalid API Key

**Symptom:** `403 Forbidden: invalid api key`.

**Cause:** API key revoked, malformed header, or wrong key format.

**Solution:**
```bash
# Test with the correct header format
curl -H "X-API-Key: sk-live-abc123def456" https://api.cortexprime.com/v1/health

# Regenerate a key from the admin dashboard
# Settings → API Keys → Generate New Key
```

**Prevention:** Rotate keys every 90 days. Use key prefixes (`sk-live-`, `sk-test-`) to distinguish environments.

---

### OAuth Provider Errors

**Symptom:** `error=redirect_uri_mismatch` or `invalid_grant`.

**Cause:** Misconfigured redirect URI in OAuth provider or expired authorization code.

**Solution:**
```bash
# Verify the registered redirect URI matches
# OAuth Provider Console → App Settings → Redirect URIs
# Must match: https://cortexprime.example.com/api/v1/auth/callback

# Check the OAuth error in logs
docker logs cortexprime-api --tail 100 | grep "oauth"
```

**Prevention:** Use environment-specific OAuth apps. Validate redirect URIs with a pre-deploy check.

---

### CORS Errors

**Symptom:** Browser console shows `Access-Control-Allow-Origin` missing.

**Cause:** Frontend origin not whitelisted in CORS configuration.

**Solution:**
```env
# .env
CORS_ORIGINS=https://app.cortexprime.example.com,http://localhost:3000
```

```bash
# Test CORS headers
curl -H "Origin: https://app.cortexprime.example.com" \
  -H "Access-Control-Request-Method: GET" \
  -X OPTIONS https://api.cortexprime.com/v1/health -v 2>&1 | grep -i "access-control"
```

**Prevention:** Use environment-specific CORS configs validated during deployment.

---

### Rate Limiting Hit

**Symptom:** `429 Too Many Requests` or `X-RateLimit-Remaining: 0`.

**Cause:** Exceeded API rate limit (default 1000 requests/minute per API key).

**Solution:**
```bash
# Check rate limit headers
curl -I https://api.cortexprime.com/v1/health | grep -i "x-ratelimit"

# Implement exponential backoff in client code
sleep $((RANDOM % 5 + 2 ** $retries))
```

**Prevention:** Use batch endpoints for bulk operations. Monitor rate limit headers and alert at 80% capacity.

---

## 4. Mission Execution Issues

### Mission Stuck in Queue

**Symptom:** Mission status remains `queued` for >5 minutes.

**Cause:** All workers busy, queue consumer crashed, or deadlock in mission scheduler.

**Solution:**
```bash
# Check queue depth
curl http://localhost:15672/api/queues/%2F/missions | jq '.messages_ready'

# Restart the mission scheduler
docker compose restart cortexprime-scheduler

# Force-resume stuck missions
curl -X POST http://localhost:8080/api/v1/missions/resume \
  -H "Content-Type: application/json" \
  -d '{"mission_id": "m-abc123"}'
```

**Prevention:** Set mission timeout in config (`MISSION_TIMEOUT_MS=300000`). Monitor queue depth with Prometheus.

---

### Agent Timeout

**Symptom:** `AgentTimeoutError: agent did not respond within 30000ms`.

**Cause:** Slow LLM response, network latency, or agent in infinite loop.

**Solution:**
```bash
# Check agent logs
docker logs cortexprime-agent-1 --tail 50

# Increase timeout in agent config
# AGENT_TIMEOUT_MS=60000
# AGENT_MAX_RETRIES=3

# Kill and restart the agent
docker compose kill cortexprime-agent-1
docker compose up -d cortexprime-agent-1
```

**Prevention:** Set realistic timeouts per agent type. Implement circuit breaker pattern for LLM calls.

---

### LLM Provider Errors

**Symptom:** `OpenAIError: 429 Too Many Requests` or `AnthropicError: overloaded`.

**Cause:** API rate limits, quota exceeded, or provider outage.

**Solution:**
```bash
# Check provider status
curl https://status.openai.com
curl https://status.anthropic.com

# Implement model fallback in config:
# LLM_FALLBACK_MODELS=gpt-4o-mini,claude-3-haiku

# Retry with exponential backoff
sleep $((2 ** $attempt * 1000))  # ms
```

**Prevention:** Configure multiple provider API keys and use a load balancer. Add model fallback chains.

---

### Memory Full

**Symptom:** `MemoryFullError: No available memory slots` or `Insert failed: storage at capacity`.

**Cause:** Memory store reached its configured limit.

**Solution:**
```bash
# Check memory store usage
curl http://localhost:8080/api/v1/memory/stats
# {"total_slots": 10000, "used_slots": 10000, "eviction_policy": "lru"}

# Increase memory capacity
# MEMORY_MAX_ENTRIES=50000

# Manually prune old entries
curl -X POST http://localhost:8080/api/v1/memory/prune \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 30}'
```

**Prevention:** Set `MEMORY_EVICTION_POLICY=lru` and monitor usage with alerts at 80% capacity.

---

### Context Limit Exceeded

**Symptom:** `ContextWindowExceededError: total tokens 132000 exceeds model maximum 128000`.

**Cause:** Mission accumulated too many messages exceeding the LLM context window.

**Solution:**
```bash
# Summarize older messages
curl -X POST http://localhost:8080/api/v1/missions/summarize \
  -H "Content-Type: application/json" \
  -d '{"mission_id": "m-abc123"}'

# Adjust context window config
# MAX_CONTEXT_TOKENS=64000
# CONTEXT_SUMMARIZE_AT=60000
```

**Prevention:** Implement sliding window or summarization-based context management. Monitor token usage per mission.

---

## 5. Worker Issues

### Browser Worker Not Starting

**Symptom:** `Error: Failed to launch browser process` or `BrowserWorker: unable to connect`.

**Cause:** Missing Chromium/Playwright browsers or sandbox incompatibility.

**Solution:**
```bash
# Install Playwright browsers
npx playwright install chromium

# Run without sandbox (development only, not for production)
export PLAYWRIGHT_LAUNCH_OPTIONS='{"args": ["--no-sandbox", "--disable-setuid-sandbox"]}'

# Verify installation
npx playwright install --dry-run
```

**Prevention:** Use official Playwright Docker images. Set `PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright` in containers.

---

### Playwright Dependency Missing

**Symptom:** `Error: libnss3.so: cannot open shared object file`.

**Cause:** Missing system libraries required by Playwright.

**Solution:**
```bash
# Install required system dependencies (Ubuntu/Debian)
sudo apt-get install -y \
  libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
  libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
  libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
  libpango-1.0-0 libcairo2 libasound2

# For Alpine-based containers
apk add chromium
```

**Prevention:** Use the `mcr.microsoft.com/playwright` base image in Dockerfile.

---

### Voice Worker Microphone Access

**Symptom:** `Error: getUserMedia error: NotAllowedError: Permission denied`.

**Cause:** Microphone permission not granted or missing in OS settings.

**Solution:**
```bash
# Check microphone permissions on macOS
systemsetup -getmicrophonestate

# On Linux, check PulseAudio
pactl list sources | grep -i "state"

# Grant permissions in container
--device /dev/snd:/dev/snd
```

**Prevention:** Document microphone requirements in setup guide. Add a permission check UI in the worker dashboard.

---

### Desktop Worker Permission Denied

**Symptom:** `Error: EACCES: permission denied, open '/var/log/cortexprime/worker.log'`.

**Cause:** Worker runs as non-root but lacks write permissions to log or temp directories.

**Solution:**
```bash
# Fix directory permissions
sudo chown -R 1000:1000 /var/log/cortexprime
sudo chmod -R 755 /var/log/cortexprime

# Use writable working directory
export WORKER_TEMP_DIR=/tmp/cortexprime-worker
mkdir -p $WORKER_TEMP_DIR
```

**Prevention:** Create directories in Dockerfile with correct ownership. Use `/tmp` for ephemeral files.

---

### Worker Crashes on Startup

**Symptom:** Worker container enters `restarting` loop or `Exit code: 137`.

**Cause:** Out of memory (OOM kill), missing config, or unhandled startup error.

**Solution:**
```bash
# Check container exit reason
docker inspect cortexprime-worker-1 --format '{{.State.ExitCode}} {{.State.Error}}'

# Increase memory limit
docker service update --limit-memory 2g cortexprime-worker

# View crash logs
docker logs cortexprime-worker-1 --tail 100

# Test config syntax
npm run config:validate
```

**Prevention:** Set memory limits and health checks. Use graceful shutdown handlers.

---

## 6. Connector Issues

### GitHub API Rate Limited

**Symptom:** `403 rate limit exceeded` or `API rate limit exceeded for user ID`.

**Cause:** Exceeded GitHub API rate limit (5000 requests/hour for authenticated).

**Solution:**
```bash
# Check current rate limit
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/rate_limit

# Implement caching
# GITHUB_CACHE_TTL=300
# GITHUB_CACHE_MAX_SIZE=1000

# Upgrade to GitHub App authentication for higher limits
```

**Prevention:** Use conditional requests (`If-None-Match`). Store etags in connector state. Monitor rate limit headers.

---

### Jira Authentication Failed

**Symptom:** `401 Unauthorized: Basic authentication with password is deprecated`.

**Cause:** Jira Cloud no longer accepts basic auth with passwords; API token required.

**Solution:**
```bash
# Generate an API token at https://id.atlassian.com/manage/api-tokens
# Use it in your connector config:
JIRA_AUTH_METHOD=api_token
JIRA_API_TOKEN=your-api-token
JIRA_EMAIL=user@example.com

# Test authentication
curl -u "user@example.com:$JIRA_API_TOKEN" \
  https://your-domain.atlassian.net/rest/api/3/myself
```

**Prevention:** Use OAuth 2.0 for Jira Cloud. Document API token generation in onboarding.

---

### Slack Token Expired

**Symptom:** `Error: Slack API error: token_revoked`.

**Cause:** Slack app token revoked, reinstalled, or expired.

**Solution:**
```bash
# Reinstall the Slack app to get a new token
# https://api.slack.com/apps → Your App → OAuth & Permissions → Reinstall App

# Update the token in CortexPrime config
# SLACK_BOT_TOKEN=xoxb-new-token
# SLACK_USER_TOKEN=xoxp-new-token

# Test new token
curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  https://slack.com/api/auth.test
```

**Prevention:** Monitor token expiry. Implement webhook notifications for token revocation events.

---

### Teams Channel Not Found

**Symptom:** `Error: Microsoft Teams API: Channel not found`.

**Cause:** Channel deleted, renamed, or wrong channel ID.

**Solution:**
```bash
# List all channels in a team
curl -H "Authorization: Bearer $TEAMS_TOKEN" \
  "https://graph.microsoft.com/v1.0/teams/{team-id}/channels"

# Update connector config with correct channel ID
# TEAMS_CHANNEL_ID=new-channel-id

# Test channel access
curl -H "Authorization: Bearer $TEAMS_TOKEN" \
  "https://graph.microsoft.com/v1.0/teams/{team-id}/channels/{channel-id}/messages"
```

**Prevention:** Store channel names (not IDs) and resolve to IDs at runtime. Add re-sync command.

---

### ServiceNow Instance Unreachable

**Symptom:** `Error: connect ETIMEDOUT your-instance.service-now.com:443`.

**Cause:** Network firewall blocking outbound connections, instance down, or DNS resolution failure.

**Solution:**
```bash
# Test connectivity
curl -v https://your-instance.service-now.com/api/now/table/sys_user?sysparm_limit=1

# Check DNS resolution
nslookup your-instance.service-now.com

# If behind a proxy, configure:
# SERVICENOW_PROXY_URL=http://proxy.company.com:8080
```

**Prevention:** Implement health checks in the connector. Use allowed IP lists and instance watcher.

---

### Confluence Page Not Found

**Symptom:** `Error: Confluence API: Page 'XYZ' not found at space 'ABC'`.

**Cause:** Page moved, deleted, or wrong space key.

**Solution:**
```bash
# Search for the page
curl -u "$CONFLUENCE_USER:$CONFLUENCE_API_TOKEN" \
  "https://your-domain.atlassian.net/wiki/rest/api/content?title=XYZ&spaceKey=ABC"

# Update the page ID or title in connector config
# CONFLUENCE_PAGE_ID=123456
```

**Prevention:** Use page IDs instead of titles. Implement periodic content sync to detect moved pages.

---

### Notion Integration Blocked

**Symptom:** `Error: Notion API: access_denied` or `missing_bot_capability`.

**Cause:** Integration not granted access to specific pages or missing capabilities.

**Solution:**
```bash
# Re-share the database/page with the integration
# Open Notion → Share → Add integrations → Select your integration

# Verify capabilities
curl -H "Authorization: Bearer $NOTION_TOKEN" \
  "https://api.notion.com/v1/users/me"
```

**Prevention:** Document required Notion integration capabilities. Use Notion API testing playground to validate.

---

### Azure DevOps PAT Expired

**Symptom:** `Error: Azure DevOps API: TF400813: Access denied`.

**Cause:** Personal Access Token expired or revoked.

**Solution:**
```bash
# Generate new PAT at https://dev.azure.com/{org}/_usersettings/tokens
# Required scopes: Code (Read), Work Items (Read), Build (Read)

# Update config
# AZURE_DEVOPS_PAT=new-pat

# Test new token
curl -u ":$AZURE_DEVOPS_PAT" \
  "https://dev.azure.com/{org}/_apis/projects?api-version=6.0"
```

**Prevention:** Set PAT expiry to max allowed (1 year). Add calendar reminders for renewal.

---

## 7. Database Issues

### PostgreSQL Connection Pool Exhausted

**Symptom:** `Error: remaining connection slots are reserved for non-replication superuser connections`.

**Cause:** All connections in pool are in use.

**Solution:**
```bash
# Check active connections
SELECT count(*) FROM pg_stat_activity;

# Increase pool size
# DB_POOL_MIN=5
# DB_POOL_MAX=50

# Kill idle connections
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE state = 'idle' AND state_change < now() - interval '5 minutes';
```

**Prevention:** Set `DB_POOL_MAX` based on workload. Implement connection monitoring in Grafana.

---

### Redis Out of Memory

**Symptom:** `OOM command not allowed when used memory > 'maxmemory'.`

**Cause:** Redis reached configured `maxmemory` limit.

**Solution:**
```bash
# Check Redis memory usage
redis-cli info memory | grep used_memory_human

# Increase maxmemory
redis-cli config set maxmemory 4gb

# Or enable eviction
redis-cli config set maxmemory-policy allkeys-lru
```

**Prevention:** Monitor Redis memory with `MEMORY STATS`. Set `maxmemory-policy` to `allkeys-lru`. Use Redis Cluster for sharding.

---

### Neo4j Transaction Contention

**Symptom:** `Lock client found that cannot acquire lock` or `Transaction guard detected contention`.

**Cause:** Concurrent writes to same graph entities without proper isolation.

**Solution:**
```bash
# Check for open transactions
CALL dbms.listTransactions();

# Kill a stuck transaction
CALL dbms.killTransaction('transaction-id');

# Set timeout in config
# NEO4J_TRANSACTION_TIMEOUT=30s
```

**Prevention:** Use `cypher.query.retry` for transient failures. Design graph model to minimize write hot spots.

---

### pgvector Index Build Failure

**Symptom:** `ERROR: index creation failed: out of memory` or `ERROR: could not create index: tuple too large`.

**Cause:** Memory limit hit during index build or oversized vectors.

**Solution:**
```sql
-- Set maintenance work memory higher
SET maintenance_work_mem = '2GB';

-- Rebuild with reduced parallelism
CREATE INDEX CONCURRENTLY idx_vectors ON memories USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Verify vector dimensions match
SELECT pg_typeof(embedding) FROM memories LIMIT 1;
```

**Prevention:** Set `maintenance_work_mem` in session. Use `IVFFlat` for approximate search. Validate vector dimensions at insert time.

---

### Slow Queries

**Symptom:** API endpoints take >1s; database CPU at 100%.

**Cause:** Missing indexes, full table scans, or N+1 queries.

**Solution:**
```sql
-- Find slow queries
SELECT query, calls, total_time / calls AS avg_time_ms
FROM pg_stat_statements
ORDER BY avg_time_ms DESC LIMIT 10;

-- Add missing indexes
CREATE INDEX CONCURRENTLY idx_missions_status ON missions(status);
CREATE INDEX CONCURRENTLY idx_missions_created_at ON missions(created_at);

-- Enable auto-explain for troubleshooting
SET client_min_messages = log;
SET auto_explain.log_min_duration = '1s';
```

**Prevention:** Run `EXPLAIN ANALYZE` on query plans. Monitor `pg_stat_statements`. Add indexes proactively.

---

## 8. Memory Issues

### Memory Retrieval Returns Empty

**Symptom:** Search queries return 0 results for known data.

**Cause:** Wrong embedding model, inverted index not updated, or namespace mismatch.

**Solution:**
```bash
# Check index stats
curl http://localhost:8080/api/v1/memory/index/stats

# Rebuild the index
curl -X POST http://localhost:8080/api/v1/memory/index/rebuild

# Verify embedding model is consistent
# MEMORY_EMBEDDING_MODEL=text-embedding-3-small
```

**Prevention:** Pin embedding model version. Run index rebuild as a maintenance task.

---

### Embedding Generation Fails

**Symptom:** `Error: OpenAI API error: invalid_request_error: model not found`.

**Cause:** Deprecated or unavailable embedding model.

**Solution:**
```bash
# Test embedding model
curl https://api.openai.com/v1/embeddings \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "test", "model": "text-embedding-3-small"}'

# Update model config
# MEMORY_EMBEDDING_MODEL=text-embedding-3-small
```

**Prevention:** Use model aliases (e.g., `latest-embedding`) that point to current stable models.

---

### Context Assembly Timeout

**Symptom:** `Error: ContextAssemblyTimeout: exceeded 10000ms`.

**Cause:** Too many memory entries retrieved; slow database queries.

**Solution:**
```bash
# Limit context size
# CONTEXT_MAX_RESULTS=20
# CONTEXT_ASSEMBLY_TIMEOUT_MS=30000

# Optimize database queries for memory retrieval
```

**Prevention:** Set `CONTEXT_MAX_RESULTS` to a reasonable limit. Parallelize memory fetches.

---

### Consolidation Fails

**Symptom:** `ConsolidationError: Failed to merge memory entries`.

**Cause:** Conflicting memory entries or timeout during consolidation.

**Solution:**
```bash
# Check consolidation logs
docker logs cortexprime-api --tail 50 | grep "consolidat"

# Run manual consolidation
curl -X POST http://localhost:8080/api/v1/memory/consolidate
```

**Prevention:** Configure consolidation schedule in off-peak hours. Set `CONSOLIDATION_BATCH_SIZE=100`.

---

### Search Relevance Low

**Symptom:** Search returns unrelated results or misses relevant entries.

**Cause:** Wrong distance metric, poor embedding quality, or insufficient training data.

**Solution:**
```bash
# Change distance metric
# MEMORY_SEARCH_METRIC=cosine  # options: cosine, euclidean, dot

# Adjust similarity threshold
# MEMORY_SIMILARITY_THRESHOLD=0.75

# Experiment with different models
# MEMORY_EMBEDDING_MODEL=text-embedding-ada-002
```

**Prevention:** Test different metrics and thresholds in a staging environment. Use A/B testing for relevance.

---

## 9. Knowledge Graph Issues

### Neo4j Connection Refused

**Symptom:** `Error: Neo4jError: connect ECONNREFUSED 127.0.0.1:7687`.

**Cause:** Neo4j service not running, wrong port, or network isolation.

**Solution:**
```bash
# Check Neo4j status
docker exec neo4j neo4j status

# Verify connectivity
docker exec cortexprime-api curl neo4j:7687

# Restart Neo4j
docker compose restart neo4j
```

**Prevention:** Use health checks in Docker Compose. Configure `NEO4J_RETRY_CONNECTION=true`.

---

### Cypher Query Syntax Error

**Symptom:** `Error: Invalid input '(': expected whitespace, comment or a relationship pattern`.

**Cause:** Malformed Cypher query, often from user input or dynamic query building.

**Solution:**
```bash
# Validate Cypher query in Neo4j Browser
EXPLAIN MATCH (n:Entity) WHERE n.name = $name RETURN n

# Escape user input properly
# Use parameterized queries (never string interpolation):
MATCH (n:Entity) WHERE n.name = $name RETURN n
```

**Prevention:** Use query builders that parameterize inputs. Run Cypher linting in CI.

---

### Entity Creation Fails

**Symptom:** `Error: Node 123 already exists with label Entity`.

**Cause:** Unique constraint violation on entity ID or name.

**Solution:**
```sql
-- Use MERGE instead of CREATE
MERGE (e:Entity {id: $id})
ON CREATE SET e.name = $name, e.created_at = timestamp()

-- Check constraints
SHOW CONSTRAINTS
```

**Prevention:** Always use `MERGE` for idempotent entity creation. Define unique constraints on entity IDs.

---

### Relationship Traversal Timeout

**Symptom:** `Error: Query execution took longer than the configured threshold of 30000 ms`.

**Cause:** Deep or cyclic graph traversals without limits.

**Solution:**
```cypher
// Add depth limits to traversals
MATCH path = (start:Entity {id: $id})-[*1..5]-(end)
RETURN path

// Use APOC for bounded path finding
CALL apoc.path.expand(start, "RELATES_TO>", "+Entity", 1, 5)
```

**Prevention:** Always specify depth bounds. Use `dbms.security.procedures.allowlist=apoc.*` for APOC utilities.

---

### Inference Engine Errors

**Symptom:** `InferenceError: Could not resolve entity relationship`.

**Cause:** Missing or circular inference rules.

**Solution:**
```bash
# Check inference rules
curl http://localhost:8080/api/v1/knowledge-graph/rules

# Validate rules syntax
curl -X POST http://localhost:8080/api/v1/knowledge-graph/rules/validate \
  -H "Content-Type: application/json" \
  -d '{"rule": "(?x is_a ?y) ∧ (?y is_a ?z) → (?x is_a ?z)"}'
```

**Prevention:** Test inference rules on a staging graph. Implement rule versioning.

---

## 10. Replay Issues

### No Replay Data Found

**Symptom:** Replay viewer shows empty state or `404 No replay data available`.

**Cause:** Replay recording disabled or mission completed before recording started.

**Solution:**
```bash
# Enable replay for the mission type
# REPLAY_ENABLED=true
# REPLAY_MISSION_TYPES=automation,research

# Check if replay data exists
curl http://localhost:8080/api/v1/replay/missions/m-abc123
```

**Prevention:** Enable replay by default for all missions. Adjust `REPLAY_MISSION_TYPES` as needed.

---

### Timeline Empty

**Symptom:** Replay timeline shows no events.

**Cause:** Events not being emitted or storage failure.

**Solution:**
```bash
# Check event stream
curl http://localhost:8080/api/v1/replay/events?mission_id=m-abc123

# Verify replay emitter is running
docker logs cortexprime-replay-emitter --tail 20
```

**Prevention:** Monitor event emission rate. Add health checks on the replay emitter service.

---

### Graph Missing Steps

**Symptom:** Replay graph shows disconnected nodes or missing edges.

**Cause:** Incomplete event capture or graph assembly failed.

**Solution:**
```bash
# Regenerate the graph for a specific mission
curl -X POST http://localhost:8080/api/v1/replay/graph/regenerate \
  -H "Content-Type: application/json" \
  -d '{"mission_id": "m-abc123"}'
```

**Prevention:** Set `REPLAY_EVENT_BUFFER_SIZE` to accommodate bursty event flows. Implement idempotent graph assembly.

---

### Export Fails

**Symptom:** `Error: Failed to export replay: storage quota exceeded`.

**Cause:** No space left on disk for export artifacts.

**Solution:**
```bash
# Check disk space
df -h /var/lib/cortexprime/replays

# Clean old exports
find /var/lib/cortexprime/replays -mtime +7 -exec rm {} \;

# Set export location to a volume with more space
# REPLAY_EXPORT_PATH=/mnt/large-volume/replays
```

**Prevention:** Set up automated cleanup of exports older than N days. Monitor disk usage with alerts.

---

### Replay Store Full

**Symptom:** `Error: Replay store capacity reached`.

**Cause:** MongoDB/PostgreSQL storage for replays is full.

**Solution:**
```bash
# Check replay store size
curl http://localhost:8080/api/v1/replay/stats

# Prune old replays
curl -X POST http://localhost:8080/api/v1/replay/prune \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 30}'
```

**Prevention:** Set `REPLAY_RETENTION_DAYS=30`. Use TTL indexes on replay collections.

---

## 11. Observability Issues

### Prometheus Metrics Missing

**Symptom:** Prometheus target shows as `DOWN` or no metrics received.

**Cause:** CortexPrime metrics endpoint not exposed or Scrape config mismatch.

**Solution:**
```bash
# Test metrics endpoint
curl http://localhost:9090/metrics | head -20

# Verify prometheus.yml scrape config
# static_configs:
#   - targets: ['cortexprime-api:9090']
```

**Prevention:** Validate Prometheus config with `promtool check config`. Use service discovery.

---

### Grafana Dashboard Not Loading

**Symptom:** Grafana shows "Dashboard not found" or panels show "No data".

**Cause:** Dashboard JSON missing, datasource misconfigured, or time range mismatch.

**Solution:**
```bash
# Check datasource configuration
curl http://localhost:3000/api/datasources

# Import dashboard from JSON
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @grafana/dashboards/cortexprime.json

# Adjust time range to match data availability
```

**Prevention:** Use provisioned dashboards. Store dashboard JSON in version control. Pin datasource UIDs.

---

### Sentry Events Not Reporting

**Symptom:** Errors not appearing in Sentry dashboard.

**Cause:** Missing DSN, client not initialized, or rate limited by Sentry.

**Solution:**
```bash
# Verify DSN is set
echo $SENTRY_DSN

# Test Sentry capture
curl https://sentry.io/api/0/projects/{org}/{project}/events/ \
  -H "Authorization: Bearer $SENTRY_AUTH_TOKEN"

# Check for Sentry rate limiting in logs
# "Sentry responded with 429 Too Many Requests"
```

**Prevention:** Set `SENTRY_ENVIRONMENT` correctly. Test Sentry integration in CI.

---

### Log Aggregation Failing

**Symptom:** Logs not appearing in Loki/ELK stack.

**Cause:** Log driver misconfiguration, network issue, or index rotation problem.

**Solution:**
```bash
# Check Docker log driver
docker info --format '{{.LoggingDriver}}'

# Verify log shipping
tail -f /var/log/cortexprime/api.log | nc -u loki 1514

# Check Elasticsearch index
curl http://localhost:9200/_cat/indices | grep cortexprime
```

**Prevention:** Use structured logging (JSON format). Implement log shipper health checks.

---

## 12. Performance Issues

### High Latency

**Symptom:** API response times exceed 2s (p99).

**Cause:** Slow database queries, blocking I/O, or inefficient code paths.

**Solution:**
```bash
# Profile endpoint latencies
curl -H "X-Profile: 1" http://localhost:8080/api/v1/missions

# Check for slow database queries (see Database Issues section)
# Check for memory pressure (see Memory Leaks section)

# Enable APM tracing
# APM_ENABLED=true
# APM_SERVICE_NAME=cortexprime-api
```

**Prevention:** Set up continuous profiling (e.g., Pyroscope). Run load tests before releases.

---

### Memory Leaks

**Symptom:** Container RSS grows indefinitely until OOM.

**Cause:** Unreleased references, uncapped caches, or event listener leaks.

**Solution:**
```bash
# Take a Node.js heap snapshot
node --inspect -e "process.kill(process.pid, 'SIGUSR2')"

# Analyze heap snapshot with Chrome DevTools
# Memory → Load → heap-xxx.heapsnapshot

# Restart the service as a temporary fix
docker compose restart cortexprime-api
```

**Prevention:** Set `NODE_OPTIONS=--max-old-space-size=2048`. Use heap dump analysis in CI. Implement cache TTLs.

---

### CPU Spikes

**Symptom:** CPU usage jumps to 100% for extended periods.

**Cause:** Inefficient loops, regex backtracking, or garbage collection storms.

**Solution:**
```bash
# Identify CPU-heavy processes
docker stats cortexprime-api

# Profile CPU usage
top -p $(pgrep -f "cortexprime-api")

# Enable CPU profiling
# CPU_PROFILING_ENABLED=true
```

**Prevention:** Use worker threads for CPU-intensive tasks. Set CPU limits per container.

---

### Slow API Responses

**Symptom:** Endpoints consistently return >500ms response times.

**Cause:** N+1 queries, missing indexes, or serialization bottlenecks.

**Solution:**
```bash
# Enable query logging
# DB_DEBUG=true

# Add eager loading
# MISSIONS_INCLUDE=steps,results

# Use pagination
curl "http://localhost:8080/api/v1/missions?limit=50&offset=0"
```

**Prevention:** Use database query analyzers. Implement response caching for read-heavy endpoints.

---

### Database Bottlenecks

**Symptom:** Database CPU at 90%+, connection pool saturated.

**Cause:** Inefficient queries, missing indexes, or insufficient resources.

**Solution:**
```bash
# Check database load
SELECT pg_stat_activity.datname, count(*) AS active_connections
FROM pg_stat_activity GROUP BY datname;

# Identify worst queries
SELECT query, calls, total_time / calls AS avg_time_ms
FROM pg_stat_statements
ORDER BY total_time DESC LIMIT 5;

# Add read replicas for query offloading
```

**Prevention:** Use connection pooling (PgBouncer). Set up read replicas. Implement query timeout.

---

## 13. UI Issues

### Page Not Loading

**Symptom:** Blank page, spinner indefinitely, or "Application error".

**Cause:** JavaScript bundle failed to load, API unreachable, or browser compatibility.

**Solution:**
```bash
# Check browser console for errors
# F12 → Console tab

# Verify API is reachable from browser
curl http://localhost:8080/api/v1/health

# Clear browser cache and hard reload
# Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (macOS)

# Check for CSP violations
```

**Prevention:** Use progressive loading. Implement error boundaries in React components.

---

### Component Errors

**Symptom:** Red error overlay or "Something went wrong" toast.

**Cause:** React component error, missing props, or state corruption.

**Solution:**
```bash
# Check Sentry for component error details
# Look for component stack trace

# Reset local state
localStorage.removeItem('cortexprime_state')

# Rebuild the frontend
npm run build
```

**Prevention:** Implement error boundaries with fallback UI. Add component-level tests.

---

### Theme Not Applying

**Symptom:** UI renders in default light theme despite dark mode selection.

**Cause:** Theme preference not persisted, CSS conflict, or local storage issue.

**Solution:**
```bash
# Clear theme cache
localStorage.removeItem('theme')

# Check CSS custom properties
# F12 → Elements → Computed → Check --bg-primary value

# Toggle theme in settings
curl -X PUT http://localhost:8080/api/v1/settings/theme \
  -H "Content-Type: application/json" \
  -d '{"theme": "dark"}'
```

**Prevention:** Use CSS variables with fallbacks. Persist theme preference in both localStorage and server-side.

---

### Keyboard Shortcuts Not Working

**Symptom:** `Ctrl+K` or `Cmd+K` does not open command palette.

**Cause:** Shortcut conflict, focus trap, or disabled shortcuts.

**Solution:**
```bash
# Check shortcut configuration
curl http://localhost:8080/api/v1/settings/keyboard-shortcuts

# Reset shortcuts to defaults
curl -X POST http://localhost:8080/api/v1/settings/keyboard-shortcuts/reset
```

**Prevention:** Allow user customization of shortcuts. Detect and warn about conflicts.

---

### Notifications Not Appearing

**Symptom:** Toasts or badge notifications not showing.

**Cause:** Notification permission denied, WebSocket disconnected, or browser tab inactive.

**Solution:**
```bash
# Check notification permissions
Notification.permission

# Reconnect WebSocket
window.cortexprime.reconnect()

# Verify WebSocket connection
# F12 → Network → WS → cortexprime.example.com
```

**Prevention:** Request notification permission on first login. Implement WebSocket reconnection with exponential backoff.

---

## 14. Diagnostic Commands

### Health Checks

```bash
# API health
curl http://localhost:8080/api/v1/health

# Detailed health (includes dependencies)
curl http://localhost:8080/api/v1/health/detailed

# Database health
curl http://localhost:8080/api/v1/health/database

# Worker status
curl http://localhost:8080/api/v1/workers/status
```

### Viewing Logs

```bash
# All services
docker compose logs --tail=100 -f

# Specific service
docker logs cortexprime-api --tail=50

# Follow logs with timestamps
docker logs -t --tail=50 cortexprime-api

# Search logs
docker logs cortexprime-api 2>&1 | grep "ERROR"

# Export logs
docker logs cortexprime-api > api.log 2>&1
```

### Database Queries

```sql
-- Active missions
SELECT id, status, created_at, updated_at FROM missions WHERE status != 'completed';

-- Recent errors
SELECT id, message, stack_trace, created_at FROM errors ORDER BY created_at DESC LIMIT 10;

-- Memory usage
SELECT count(*) AS total_entries, pg_size_pretty(pg_database_size(current_database())) AS db_size;

-- Queue depth
SELECT count(*) FROM missions WHERE status = 'queued';
```

```bash
# Run via docker
docker exec -it postgres psql -U cortexprime -d cortexprime -c "SELECT count(*) FROM missions;"
```

### Metrics Inspection

```bash
# Prometheus metrics endpoint
curl http://localhost:9090/metrics | grep cortexprime

# Query a specific metric
curl http://localhost:9090/api/v1/query?query=cortexprime_missions_total

# Check Redis metrics
redis-cli info stats | grep "total_"

# Check queue metrics
curl http://localhost:15672/api/queues/%2F/missions | jq .
```

### System Diagnostics

```bash
# Check all services status
docker compose ps

# Resource usage
docker stats --no-stream

# Disk space
df -h /var/lib/cortexprime

# Network connectivity test
docker run --rm alpine ping -c 3 google.com
```

---

## 15. Support Escalation

### When to Escalate

Escalate to CortexPrime support when:

1. **Critical outage** — Entire system is down or core functionality is broken
2. **Data loss** — Missions, memory, or graph data is corrupted or lost
3. **Security incident** — Suspected unauthorized access or data breach
4. **Bug reproduction** — You can reliably reproduce a previously unreported bug
5. **Performance regression** — Significant degradation after a version upgrade
6. **Third-party dependency failure** — Issue isolated to a provider (OpenAI, GitHub, etc.) requiring vendor coordination

### What Information to Provide

When filing a support request, include:

| Item | Description |
|------|-------------|
| **Version** | Output of `cortexprime --version` or Docker image tag |
| **Deployment** | Docker Compose, Kubernetes, or standalone |
| **Logs** | Relevant service logs from `docker logs <service> --tail=100` |
| **Config** | Sanitized `.env` or config file (redact secrets) |
| **Steps** | Exact steps to reproduce the issue |
| **Timestamps** | UTC timestamps of when the issue occurred |
| **Screenshots** | If UI-related, screenshots of the error and browser console |
| **Metrics** | Prometheus/Grafana graphs showing the issue |

### How to File a Bug Report

```bash
# Collect diagnostic bundle
cortexprime diagnose --output bundle.tar.gz

# This generates a bundle containing:
# - System info and version
# - Service logs (last 500 lines each)
# - Configuration (secrets redacted)
# - Health check results
# - Recent metrics snapshot
```

Submit the bundle via:

- **GitHub Issues**: https://github.com/cortexprime/cortexprime/issues/new/choose
- **Support Portal**: https://support.cortexprime.com
- **Email**: support@cortexprime.com

### Support Contact Information

| Channel | Contact | SLA |
|---------|---------|-----|
| Community Slack | cortexprime.slack.com | Best effort |
| GitHub Issues | github.com/cortexprime/cortexprime/issues | 2 business days |
| Email Support | support@cortexprime.com | 4 hours (critical) |
| Enterprise Support | enterprise@cortexprime.com | 1 hour (critical) |
| Security Issues | security@cortexprime.com | 1 hour |

Include your license key and support tier when contacting enterprise support.

---

*CortexPrime v1.0.0 GA — Last updated July 2026*
