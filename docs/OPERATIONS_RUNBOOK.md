# CortexPrime Operations Runbook v1.0.0 GA

> **Document Version:** 1.0.0  
> **Last Updated:** 2026-07-04  
> **Status:** GA

---

## 1. Introduction

### 1.1 Purpose

This runbook provides day-to-day operational procedures for the CortexPrime platform. It is designed to guide on-call engineers, SREs, and platform operators through routine maintenance, incident response, and operational decision-making.

### 1.2 Audience

- Tier 1 Operations Engineers
- Tier 2 SREs
- Tier 3 Platform Engineers
- Engineering Managers on-call

### 1.3 Contact Information

| Role | Contact |
|---|---|
| Primary On-Call | `#ops-oncall` Slack | PagerDuty escalation |
| Secondary On-Call | `#sre-oncall` Slack |
| Engineering Lead | `#eng-leads` Slack |
| Security Team | `#security` Slack | security@cortexprime.io |
| Emergency | `+1-555-0129` (NOC hotline) |

### 1.4 Escalation Paths

```
Tier 1 (Ops Engineer) --15min--> Tier 2 (SRE) --30min--> Tier 3 (Platform Eng)
                             --60min--> Engineering Manager
                             --critical--> VP Engineering
```

**Severity classification for escalation:**

- **SEV-1 (Critical):** Immediate Tier 2 + Tier 3 page. Customer-facing outage or data loss.
- **SEV-2 (High):** Page Tier 2 within 15 minutes. Degraded service or partial outage.
- **SEV-3 (Medium):** Notify during business hours. Non-critical component failure.
- **SEV-4 (Low):** Log ticket. No immediate action required.

---

## 2. Daily Operations Checklist

### 2.1 Morning Checks (08:00 UTC)

```powershell
# 1. Verify all services are healthy
curl -s https://cortexprime.internal/health | ConvertFrom-Json | Format-Table

# 2. Check cluster node status
cortexctl cluster status

# 3. Verify database replication lag
cortexctl db replication-status

# 4. Check queue depths
cortexctl queue depths

# 5. Verify worker pool health
cortexctl worker list --status
```

### 2.2 Health Verification

```powershell
# Full system health check
cortexctl health --all

# Expected output:
# +-------------------+--------+----------+
# | Service           | Status | Uptime   |
# +-------------------+--------+----------+
# | api-gateway       | OK     | 14d 3h   |
# | mission-orchestr  | OK     | 14d 3h   |
# | worker-manager    | OK     | 14d 3h   |
# | connector-sync    | OK     | 14d 3h   |
# | postgres-primary  | OK     | 30d 12h  |
# | postgres-replica  | OK     | 30d 12h  |
# | redis-primary     | OK     | 30d 12h  |
# | redis-replica     | OK     | 30d 12h  |
# | neo4j-core        | OK     | 14d 3h   |
# +-------------------+--------+----------+
```

### 2.3 Log Review

```powershell
# Check for recent errors across all services
cortexctl logs search --level error --since 1h --all

# Review slow queries (>500ms)
cortexctl logs search --query "slow query" --since 24h

# Check authentication failures
cortexctl logs search --query "auth failed" --since 24h

# Export logs for analysis
cortexctl logs export --since 24h --format json --output daily-log-$(Get-Date -Format yyyyMMdd).json
```

### 2.4 Metric Review

```powershell
# API Gateway metrics
curl -s http://prometheus.cortexprime.internal:9090/api/v1/query `
  --data-urlencode 'query=rate(http_requests_total{status=~"5.."}[5m])'

# Worker utilization
curl -s http://prometheus.cortexprime.internal:9090/api/v1/query `
  --data-urlencode 'query=avg(worker_cpu_utilization) by (worker_pool)'

# Mission queue depth
curl -s http://prometheus.cortexprime.internal:9090/api/v1/query `
  --data-urlencode 'query=mission_queue_depth'
```

---

## 3. System Monitoring

### 3.1 Prometheus Metrics to Watch

| Metric | Warning | Critical | Description |
|---|---|---|---|
| `http_request_duration_seconds{p95}` | >500ms | >2s | API response latency |
| `http_requests_total{status="5xx"}` | >1% rate | >5% rate | Server error rate |
| `worker_cpu_utilization` | >70% | >90% | Worker CPU usage |
| `worker_memory_utilization` | >75% | >90% | Worker memory usage |
| `mission_queue_depth` | >1000 | >5000 | Backlogged missions |
| `mission_duration_seconds{p95}` | >30s | >120s | Mission execution time |
| `postgres_replication_lag` | >10MB | >100MB | DB replication delay |
| `redis_memory_usage_bytes` | >70% | >85% | Redis memory pressure |
| `neo4j_heap_usage` | >75% | >90% | Neo4j heap pressure |
| `connector_sync_lag_seconds` | >60s | >300s | Connector sync delay |
| `tls_cert_expiry_days` | <30 | <7 | TLS cert expiration |

### 3.2 Grafana Dashboard Overview

| Dashboard | Description | Refresh |
|---|---|---|
| **CortexPrime Overview** | Global system health, top-level KPIs | 30s |
| **API Gateway** | Request rates, latencies, error codes | 15s |
| **Worker Pools** | Utilization, throughput, queue depths | 15s |
| **Databases** | PostgreSQL, Redis, Neo4j health | 30s |
| **Connectors** | Sync status, error rates, throughput | 30s |
| **Mission Performance** | Success rates, durations, failure reasons | 60s |

**Access:** `https://grafana.cortexprime.internal/d/cortexprime-overview`

### 3.3 Alert Thresholds

All alerts route through PagerDuty with the following escalation:

| Alert | Threshold | Window | Severity | Action |
|---|---|---|---|---|
| `HighErrorRate` | 5xx > 5% | 5m | SEV-2 | Check API Gateway logs |
| `ServiceDown` | Probe failure | 1m | SEV-1 | Restart service |
| `HighLatency` | p95 > 2s | 5m | SEV-2 | Scale workers, check DB |
| `QueueBacklog` | Queue > 5000 | 5m | SEV-2 | Scale workers |
| `DBReplicationLag` | Lag > 100MB | 5m | SEV-2 | Check replica health |
| `DiskFull` | Disk > 85% | 5m | SEV-2 | Clean up or expand |
| `CertExpiry` | Cert < 7 days | 1h | SEV-2 | Rotate certificate |

### 3.4 Sentry Error Monitoring

```powershell
# Fetch recent errors from Sentry API
$sentryToken = Get-Secret -Name "sentry-api-token" -AsPlainText
$headers = @{ Authorization = "Bearer $sentryToken" }
Invoke-RestMethod -Uri "https://sentry.cortexprime.internal/api/0/projects/cortexprime/errors/?statsPeriod=24h" `
  -Headers $headers | ConvertTo-Json

# Set up error grouping and alerting in Sentry UI:
#   - Group by: exception type, module
#   - Alert: >10 occurrences in 5min → PagerDuty
#   - Ignore: known non-critical errors (rate-limit, bot traffic)
```

---

## 4. Mission Management

### 4.1 Viewing Active Missions

```powershell
# List all active missions
cortexctl mission list --status running

# Detailed view of a specific mission
cortexctl mission get --id <mission-id>

# Filter by priority
cortexctl mission list --priority critical

# Filter by agent
cortexctl mission list --agent <agent-id>
```

### 4.2 Canceling Stuck Missions

```powershell
# Identify stuck missions (running > 30 minutes)
cortexctl mission list --status running --older-than 30m

# Cancel a stuck mission
cortexctl mission cancel --id <mission-id> --reason "Stuck - no progress for 30m"

# Force kill a mission (if graceful cancel fails)
cortexctl mission kill --id <mission-id> --force

# Bulk cancel stuck missions
cortexctl mission list --status running --older-than 30m --format json |
  ConvertFrom-Json |
  ForEach-Object { cortexctl mission cancel --id $_.id --reason "Bulk cancel stuck" }
```

### 4.3 Reviewing Failed Missions

```powershell
# List recent failures
cortexctl mission list --status failed --since 24h

# Get failure details
cortexctl mission get --id <mission-id> --show-logs

# Summarize failure reasons
cortexctl mission list --status failed --since 24h --format json |
  ConvertFrom-Json |
  Group-Object -Property failureReason |
  Select-Object Name, Count |
  Sort-Object Count -Descending

# Archive resolved failures
cortexctl mission archive --status failed --older-than 7d
```

### 4.4 Analyzing Mission Performance

```powershell
# Performance summary for last 7 days
cortexctl mission analyze --period 7d

# Output:
# +---------------+-------+--------+---------+-----------+
# | Metric        | Value | p50    | p95     | p99       |
# +---------------+-------+--------+---------+-----------+
# | Success Rate  | 97.2% | -      | -       | -         |
# | Duration      | -     | 12.4s  | 45.2s   | 128.3s    |
# | Retries       | 2.1%  | 0      | 2       | 5         |
# | Cost/Mission  | $0.04 | $0.02  | $0.12   | $0.45     |
# +---------------+-------+--------+---------+-----------+

# Export performance data for trending
cortexctl mission analyze --period 30d --format json --output mission-performance.json
```

---

## 5. Worker Operations

### 5.1 Checking Worker Health

```powershell
# List all workers
cortexctl worker list

# Detailed health check
cortexctl worker health --pool <pool-name>

# Check resource usage per worker
cortexctl worker stats --pool <pool-name>

# Expected output per worker:
# +-----------+-----+------+--------+--------+
# | Worker ID | CPU | Mem  | Active | Queued |
# +-----------+-----+------+--------+--------+
# | w-001     | 45% | 1.2G | 3      | 2      |
# | w-002     | 62% | 1.8G | 5      | 4      |
# +-----------+-----+------+--------+--------+
```

### 5.2 Restarting Workers

```powershell
# Graceful restart of a single worker
cortexctl worker restart --id <worker-id> --graceful

# Rolling restart of an entire pool
cortexctl worker rolling-restart --pool <pool-name> --batch-size 2 --delay 30s

# Force restart (if unresponsive)
cortexctl worker restart --id <worker-id> --force

# Verify restart completed
cortexctl worker list --pool <pool-name> --status running
```

### 5.3 Draining Workers for Maintenance

```powershell
# Drain a worker (stop accepting new missions, finish current)
cortexctl worker drain --id <worker-id>

# Check drain status
cortexctl worker status --id <worker-id>
# Expected: Status=DRAINING, ActiveMissions=2

# Wait for drain to complete (all missions finished)
cortexctl worker wait-drained --id <worker-id> --timeout 300s

# Perform maintenance, then undrain
cortexctl worker undrain --id <worker-id>

# Drain all workers in a pool
cortexctl worker list --pool <pool-name> --format json |
  ConvertFrom-Json |
  ForEach-Object { cortexctl worker drain --id $_.id }

# Verify pool is fully drained
cortexctl worker list --pool <pool-name> --status draining
```

### 5.4 Scaling Workers Up/Down

```powershell
# Scale up a pool
cortexctl worker scale --pool <pool-name> --replicas 10

# Scale down (will drain excess workers first)
cortexctl worker scale --pool <pool-name> --replicas 5

# Auto-scale based on queue depth (via API)
curl -X POST https://cortexprime.internal/api/v1/worker/autoscale `
  -H "Authorization: Bearer $(Get-Secret -Name cortex-api-key)" `
  -H "Content-Type: application/json" `
  -d '{"pool": "default", "min": 3, "max": 20, "metric": "queue_depth", "target": 100}'

# HPA-style configuration (Kubernetes)
kubectl autoscale deployment cortex-worker-default `
  --cpu-percent=75 `
  --min=3 `
  --max=20 `
  -n cortexprime
```

---

## 6. Connector Operations

### 6.1 Verifying Connector Health

```powershell
# List all connectors
cortexctl connector list

# Check connector status
cortexctl connector status --id <connector-id>

# Verify end-to-end connectivity
cortexctl connector ping --id <connector-id>

# Expected statuses: CONNECTED, DISCONNECTED, ERROR, AUTH_EXPIRED, RATE_LIMITED
```

### 6.2 Re-authenticating Connectors

```powershell
# Detect expired auth
cortexctl connector list --status auth_expired

# Re-authenticate with stored credentials
cortexctl connector reauth --id <connector-id>

# Update credentials manually
cortexctl connector update --id <connector-id> `
  --config @{
    apiKey = (Read-Host -AsSecureString "Enter new API key")
    endpoint = "https://api.provider.com/v2"
  }

# Test re-authentication
cortexctl connector ping --id <connector-id>
```

### 6.3 Troubleshooting Sync Failures

```powershell
# Check recent sync errors
cortexctl connector sync-log --id <connector-id> --since 1h

# Common error codes:
#   ERR_RATE_LIMIT  - Back off and retry
#   ERR_AUTH        - Re-authenticate
#   ERR_TIMEOUT     - Check connectivity, increase timeout
#   ERR_SCHEMA      - Verify data schema compatibility
#   ERR_QUOTA       - Check provider API quota

# Force resync
cortexctl connector resync --id <connector-id> --since 24h

# Pause and resume sync
cortexctl connector pause --id <connector-id>
# ... investigate ...
cortexctl connector resume --id <connector-id>

# Reset connector state (if corrupted)
cortexctl connector reset --id <connector-id> --confirm
```

---

## 7. User Management

### 7.1 Adding Users

```powershell
# Invite a new user
cortexctl user invite --email "user@company.com" --role "engineer"

# Create user with specific permissions
cortexctl user create `
  --email "newhire@company.com" `
  --name "Jane Doe" `
  --role "admin" `
  --send-invite

# Verify user creation
cortexctl user get --email "newhire@company.com"
```

### 7.2 Modifying Roles

```powershell
# Available roles: admin, engineer, viewer, operator, connector-admin

# Change user role
cortexctl user update --id <user-id> --role "operator"

# Add role assignment
cortexctl user assign-role --id <user-id> --role "connector-admin" --scope "connectors/*"

# Remove role assignment
cortexctl user remove-role --id <user-id> --role "connector-admin"
```

### 7.3 Revoking Access

```powershell
# Deactivate user immediately
cortexctl user deactivate --id <user-id> --reason "Employee offboarding"

# Revoke all active sessions
cortexctl user revoke-sessions --id <user-id>

# Remove from all teams/projects
cortexctl user remove --id <user-id> --from-all

# Verify access revoked
cortexctl user get --id <user-id>
# Status should show: INACTIVE
```

### 7.4 Handling MFA Resets

```powershell
# Initiate MFA reset
cortexctl user mfa-reset --id <user-id>

# This will:
#   1. Invalidate existing MFA tokens
#   2. Send user a reset email
#   3. Log the action in security audit

# Verify MFA status
cortexctl user mfa-status --id <user-id>

# For emergency bypass (only with security approval):
cortexctl user mfa-bypass --id <user-id> --duration 4h --reason "Emergency access"
```

---

## 8. Secrets Rotation

### 8.1 Rotating API Keys

```powershell
# Generate new API key
cortexctl secrets rotate api-key --service <service-name>

# Verify new key is active
cortexctl secrets verify api-key --service <service-name>

# Update downstream consumers (example: GitHub Actions)
gh secret set CORTEX_API_KEY --body (Get-Secret -Name cortex-api-key-$service -AsPlainText) `
  --repo "cortexprime/deployments"

# Remove old key after verification window
cortexctl secrets expire-old api-key --service <service-name> --age 1h
```

### 8.2 Rotating Database Credentials

```powershell
# Rotate PostgreSQL credentials
cortexctl secrets rotate db-credentials --db postgres

# Update connection strings (will trigger rolling restart)
cortexctl secrets propagate db-credentials --db postgres --rolling

# Verify DB connectivity with new credentials
cortexctl db ping
```

### 8.3 Rotating JWT Signing Keys

```powershell
# Generate new JWT signing key pair
cortexctl secrets rotate jwt-key

# The system will:
#   1. Generate new RSA key pair
#   2. Add to key ring (old keys remain valid for token lifetime)
#   3. Begin signing new tokens with new key
#   4. Remove old key after configured overlap period

# Verify JWT signing status
cortexctl secrets jwt-status

# Force immediate switch (invalidates all existing tokens)
cortexctl secrets rotate jwt-key --force
```

---

## 9. Backup Procedures

### 9.1 Daily Backup Verification

```powershell
# List today's backups
cortexctl backup list --date (Get-Date -Format yyyy-MM-dd)

# Verify backup integrity
cortexctl backup verify --id <backup-id>

# Check backup size and metadata
cortexctl backup inspect --id <backup-id>

# Expected output:
# +-------------+-----------+----------+--------+
# | Type        | Size      | Checksum | Status |
# +-------------+-----------+----------+--------+
# | postgres    | 2.4 GB    | OK       | VALID  |
# | redis       | 180 MB    | OK       | VALID  |
# | neo4j       | 890 MB    | OK       | VALID  |
# | config      | 12 MB     | OK       | VALID  |
# +-------------+-----------+----------+--------+
```

### 9.2 On-Demand Backup

```powershell
# Trigger immediate full backup
cortexctl backup create --full

# Backup specific component only
cortexctl backup create --component postgres
cortexctl backup create --component neo4j --label "pre-upgrade-$(Get-Date -Format yyyyMMdd)"

# Monitor backup progress
cortexctl backup status --id <backup-id>
```

### 9.3 Backup Retention

| Backup Type | Retention | Frequency |
|---|---|---|
| Hourly | 24 hours | Every hour |
| Daily | 30 days | Daily at 02:00 UTC |
| Weekly | 12 weeks | Sunday at 02:00 UTC |
| Monthly | 12 months | 1st of month at 02:00 UTC |
| Yearly | 7 years | Jan 1 at 02:00 UTC |

```powershell
# Configure retention policy
cortexctl backup config-retention `
  --hourly 24 `
  --daily 30 `
  --weekly 12 `
  --monthly 12 `
  --yearly 7

# Enforce cleanup
cortexctl backup cleanup --dry-run
cortexctl backup cleanup --apply
```

### 9.4 Offsite Replication

```powershell
# Check replication status
cortexctl backup replication-status

# Trigger manual replication
cortexctl backup replicate --backup-id <backup-id> --target s3://cortexprime-backups-dr

# Verify offsite backup
cortexctl backup verify-remote --backup-id <backup-id> --target s3://cortexprime-backups-dr

# Configure replication target
cortexctl backup config-replication `
  --target "s3://cortexprime-backups-dr" `
  --region "us-west-2" `
  --encryption "aws:kms"
```

---

## 10. Capacity Management

### 10.1 Monitoring Resource Utilization

```powershell
# Cluster-wide resource overview
cortexctl capacity overview

# Per-service breakdown
cortexctl capacity service --service api-gateway

# Historical utilization trends
cortexctl capacity trends --period 30d --format json

# Key metrics to watch:
#   - CPU allocation vs. usage (aim for <70% sustained)
#   - Memory pressure (aim for <75% sustained)
#   - Disk I/O wait (aim for <10%)
#   - Network throughput (aim for <60% link capacity)
```

### 10.2 Scaling Decisions

| Metric | Action |
|---|---|
| CPU > 70% sustained 15 min | Scale up workers |
| Memory > 75% sustained 15 min | Increase instance size |
| Queue depth > 1000 sustained | Scale out worker count |
| DB connections > 80% of max | Increase connection pool |
| Disk > 75% | Clean or expand volume |

### 10.3 Adding Nodes

```powershell
# Add a new worker node to the cluster
cortexctl cluster add-node `
  --type worker `
  --pool default `
  --instance-type c6i.4xlarge `
  --count 3

# Add database read replica
cortexctl cluster add-node `
  --type postgres-replica `
  --instance-type r6i.2xlarge

# Verify new nodes join the cluster
cortexctl cluster status

# Run post-add health checks
cortexctl health --all
```

### 10.4 Vertical / Horizontal Scaling

```powershell
# Vertical scaling (resize existing instances)
cortexctl capacity scale-vertical `
  --service worker-pool-default `
  --instance-type c6i.8xlarge

# Horizontal scaling (add more instances)
cortexctl capacity scale-horizontal `
  --service worker-pool-default `
  --replicas 15

# Database vertical scaling
cortexctl capacity scale-vertical `
  --service postgres-primary `
  --instance-type r6i.4xlarge `
  --storage 500GB

# Verify scale operation
cortexctl capacity overview
```

---

## 11. Update Procedures

### 11.1 Applying Updates

```powershell
# Check for available updates
cortexctl update check

# Review changelog
cortexctl update changelog --version 1.0.1

# Pre-update health snapshot
cortexctl health --all --output pre-update-health.json
cortexctl backup create --full --label "pre-update-1.0.1"

# Apply update with rolling strategy
cortexctl update apply --version 1.0.1 --strategy rolling --batch-size 2

# Monitor update progress
cortexctl update status
```

### 11.2 Rolling Back Updates

```powershell
# Check available rollback points
cortexctl rollback list

# Rollback to previous version
cortexctl rollback apply --version 1.0.0

# Rollback a specific service only
cortexctl rollback apply --version 1.0.0 --service worker-manager

# Emergency rollback (fast, no health checks)
cortexctl rollback apply --version 1.0.0 --emergency

# Verify rollback
cortexctl health --all
cortexctl update status
```

### 11.3 Compatibility Verification

```powershell
# Check compatibility matrix
cortexctl update compatibility --from 1.0.0 --to 1.1.0

# Expected output:
# +------------------+--------+------------------+----------+
# | Component        | Status | Required Version | Notes    |
# +------------------+--------+------------------+----------+
# | API Gateway      | OK     | >=1.0.0          |          |
# | Worker Manager   | OK     | >=1.0.0          |          |
# | PostgreSQL       | WARN   | >=14             | Upgrade  |
# | Redis            | OK     | >=7.0            |          |
# | Neo4j            | FAIL   | >=5.15           | Required |
# +------------------+--------+------------------+----------+
```

### 11.4 Post-Update Validation

```powershell
# Run post-update test suite
cortexctl update validate

# Manual validation checklist:
#   1. All services healthy
#   2. Missions executing successfully
#   3. Connectors syncing
#   4. Metrics being reported
#   5. Alerts firing correctly
#   6. Logs flowing to central logging
#   7. User authentication working
#   8. API endpoints responding

# Compare health snapshots
cortexctl health --all --output post-update-health.json
```

---

## 12. Incident Response

### 12.1 Severity Classification

| Severity | Description | Response Time | SLA |
|---|---|---|---|
| **SEV-1** | Complete outage, data loss, security breach | Immediate | 15min response, 4hr resolution |
| **SEV-2** | Degraded service, partial outage, performance degradation | 15min | 1hr response, 8hr resolution |
| **SEV-3** | Minor functionality issue, non-critical component | 1 business hour | 8hr response, 48hr resolution |
| **SEV-4** | Cosmetic issue, informational alert | Next business day | Best effort |

### 12.2 Tier 1 Response Procedures

```
1. ACKNOWLEDGE alert in PagerDuty
2. ASSESS severity using runbook:
   a. Is the service completely down? -> SEV-1
   b. Is performance degraded? -> SEV-2
   c. Is it a non-critical component? -> SEV-3
3. COMMUNICATE in #incident Slack channel:
   - What is happening
   - What is affected
   - What you are doing
4. EXECUTE runbook procedures for the specific issue
5. ESCALATE to Tier 2 if:
   - Cannot resolve within 15 minutes (SEV-1)
   - Cannot resolve within 1 hour (SEV-2)
   - Need database or infrastructure access
```

### 12.3 Tier 2 / Tier 3 Escalation

```
TIER 2 (SRE) RESPONSIBILITIES:
- Complex debugging and root cause analysis
- Database performance tuning
- Infrastructure changes (scale, failover)
- Coordinating with external vendors
- Hotfix deployment

TIER 3 (PLATFORM ENGINEERING) RESPONSIBILITIES:
- Code-level debugging
- Schema migrations
- Complex recovery procedures
- Security incident response
- Post-mortem coordination
```

### 12.4 Incident Response Procedures

```powershell
# Declare incident
cortexctl incident declare `
  --severity SEV-1 `
  --title "PostgreSQL primary failure" `
  --description "Primary DB node unresponsive, failing over..."

# Add timeline entries
cortexctl incident timeline --id <incident-id> --entry "16:45 UTC - Failing over to replica"

# Resolve incident
cortexctl incident resolve --id <incident-id> --resolution "Failover completed, primary rebuilt"
```

### 12.5 Post-Mortem Process

```
1. SCHEDULE post-mortem within 48 hours of resolution
2. GATHER data:
   - Incident timeline
   - Monitoring dashboards (export PDF)
   - Logs from affected services
   - Chat transcripts
3. DOCUMENT:
   - What happened
   - Why it happened
   - What was done to resolve it
   - What went well
   - What went wrong
   - Action items (with owners and deadlines)
4. TRACK action items in project management tool
5. SHARE post-mortem with engineering team
```

**Post-mortem template:** `docs/templates/post-mortem.md`

---

## 13. Runbook Automation

### 13.1 Scripts for Common Tasks

Save the following PowerShell scripts to `ops/scripts/`:

**`ops/scripts/Health-Check.ps1:**
```powershell
param(
    [string]$Endpoint = "https://cortexprime.internal/health",
    [string]$OutputPath = "health-report.json"
)

$health = Invoke-RestMethod -Uri $Endpoint
$unhealthy = $health.services | Where-Object { $_.status -ne "OK" }

if ($unhealthy) {
    Write-Warning "Unhealthy services detected:"
    $unhealthy | Format-Table
    exit 1
} else {
    Write-Output "All services healthy"
    $health | ConvertTo-Json -Depth 5 | Out-File -FilePath $OutputPath
}
```

**`ops/scripts/Drain-WorkerPool.ps1`:**
```powershell
param(
    [Parameter(Mandatory)] [string]$PoolName,
    [int]$TimeoutSeconds = 300
)

$workers = cortexctl worker list --pool $PoolName --format json | ConvertFrom-Json
foreach ($worker in $workers) {
    cortexctl worker drain --id $worker.id
}

foreach ($worker in $workers) {
    cortexctl worker wait-drained --id $worker.id --timeout $TimeoutSeconds
}

Write-Output "Pool $PoolName fully drained"
```

**`ops/scripts/Rotate-AllSecrets.ps1`:**
```powershell
Write-Output "Starting full secrets rotation..."
cortexctl secrets rotate api-key --service api-gateway
cortexctl secrets rotate db-credentials --db postgres
cortexctl secrets rotate jwt-key
cortexctl secrets propagate db-credentials
Write-Output "Secrets rotation complete. Verify all services."
```

### 13.2 API Endpoints for Automation

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/health` | GET | System health check |
| `/api/v1/missions` | GET | List missions |
| `/api/v1/missions/{id}/cancel` | POST | Cancel mission |
| `/api/v1/workers/{id}/drain` | POST | Drain worker |
| `/api/v1/workers/scale` | POST | Scale worker pool |
| `/api/v1/connectors/{id}/resync` | POST | Force connector resync |
| `/api/v1/backup/create` | POST | Trigger backup |
| `/api/v1/backup/{id}/restore` | POST | Restore from backup |
| `/api/v1/secrets/rotate` | POST | Rotate secrets |

```powershell
# Example: Trigger backup via API
$token = Get-Secret -Name cortex-api-key -AsPlainText
$body = @{ type = "full"; label = "manual-backup" } | ConvertTo-Json
Invoke-RestMethod -Uri "https://cortexprime.internal/api/v1/backup/create" `
  -Method POST `
  -Headers @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" } `
  -Body $body
```

### 13.3 Webhook Integrations

```powershell
# Register a webhook for mission completion events
cortexctl webhook create `
  --url "https://hooks.slack.com/services/T00/B00/xxxxx" `
  --events mission.completed,mission.failed `
  --description "Slack notifications for mission events"

# Register webhook for health alerts
cortexctl webhook create `
  --url "https://api.pagerduty.com/v2/xxxxx" `
  --events alert.critical,alert.warning `
  --description "PagerDuty integration"

# List registered webhooks
cortexctl webhook list

# Test a webhook
cortexctl webhook test --id <webhook-id>

# Remove a webhook
cortexctl webhook delete --id <webhook-id>
```

**Webhook payload format:**
```json
{
  "event": "mission.failed",
  "timestamp": "2026-07-04T14:30:00Z",
  "data": {
    "mission_id": "m-abc123",
    "agent": "research-agent",
    "failure_reason": "timeout",
    "duration_seconds": 120.5
  },
  "environment": "production"
}
```

---

## Appendix A: Useful Commands Quick Reference

```powershell
# System
cortexctl health --all
cortexctl cluster status
cortexctl version

# Missions
cortexctl mission list --status running
cortexctl mission cancel --id <id>
cortexctl mission analyze --period 7d

# Workers
cortexctl worker list
cortexctl worker restart --id <id> --graceful
cortexctl worker scale --pool default --replicas 10

# Connectors
cortexctl connector list
cortexctl connector ping --id <id>
cortexctl connector resync --id <id>

# Backups
cortexctl backup list
cortexctl backup create --full
cortexctl backup verify --id <id>

# Logs
cortexctl logs search --level error --since 1h
cortexctl logs export --since 24h
```

## Appendix B: Environment Details

| Property | Value |
|---|---|
| Production URL | `https://cortexprime.io` |
| API Base URL | `https://cortexprime.internal/api/v1` |
| Grafana | `https://grafana.cortexprime.internal` |
| Prometheus | `http://prometheus.cortexprime.internal:9090` |
| Sentry | `https://sentry.cortexprime.internal` |
| PagerDuty Service | `cortexprime-prod` |
| Slack Channel | `#ops-oncall` |
| Cloud Provider | AWS (us-east-1 primary, us-west-2 DR) |
| Orchestration | Kubernetes (EKS) |
| Database | PostgreSQL 16 (RDS), Redis 7 (ElastiCache), Neo4j 5.15 |