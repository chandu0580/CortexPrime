# CortexPrime Disaster Recovery Runbook v1.0.0 GA

> **Document Version:** 1.0.0  
> **Last Updated:** 2026-07-04  
> **Status:** GA

---

## 1. DR Overview

### 1.1 RPO/RTO Targets

| Component | Recovery Point Objective (RPO) | Recovery Time Objective (RTO) |
|---|---|---|
| PostgreSQL (missions, users) | 5 minutes (WAL streaming) | 1 hour |
| PostgreSQL (configuration) | 24 hours (daily backup) | 2 hours |
| Redis (cache, sessions) | 1 hour (RDB snapshots) | 15 minutes |
| Neo4j (knowledge graph) | 1 hour (daily dump) | 2 hours |
| Application binaries / config | 24 hours (IaC + backup) | 30 minutes |
| **Full system recovery** | 1 hour | 4 hours |

### 1.2 Recovery Tiers

| Tier | Recovery Scope | Max RTO | Max RPO |
|---|---|---|---|
| **Tier 0** | Redis cache/session loss | 15 min | 1 hour |
| **Tier 1** | Single database failure | 1 hour | 5 min |
| **Tier 2** | Multi-component failure | 2 hours | 1 hour |
| **Tier 3** | Complete region loss | 4 hours | 1 hour |
| **Tier 4** | Catastrophic data corruption | 8 hours | 1 hour (clean backup) |

### 1.3 DR Team Contacts

| Role | Primary | Secondary |
|---|---|---|
| DR Coordinator | SRE Lead: `+1-555-0101` | Eng Manager: `+1-555-0102` |
| Database Recovery | DBRE: `+1-555-0103` | SRE: `+1-555-0104` |
| Infrastructure Recovery | Platform Eng: `+1-555-0105` | Cloud Ops: `+1-555-0106` |
| Security Lead | Security Eng: `+1-555-0107` | CISO: `+1-555-0108` |
| Communications | Product Manager: `+1-555-0109` | VP Eng: `+1-555-0110` |

### 1.4 Communication Plan

```
1. INCIDENT DECLARED:
   - Declare in PagerDuty (severity SEV-1)
   - Post in #dr-war-room Slack channel
   - Notify DR coordinator
   - Open bridge call: https://meet.cortexprime.internal/dr-bridge

2. STATUS UPDATES (every 30 minutes):
   - Current status (Investigating / Mitigating / Recovering / Monitoring)
   - Services affected
   - Estimated time to recovery
   - Actions taken / planned

3. CUSTOMER COMMUNICATION:
   - DR coordinator decides on external comms
   - Use status page: https://status.cortexprime.io
   - Email template: see Section 6.3

4. RESOLUTION:
   - Announce in #dr-war-room
   - Update status page
   - Schedule post-mortem
```

---

## 2. Backup Architecture

### 2.1 PostgreSQL Backup Strategy

```yaml
# Backup configuration (managed via cortexctl)
postgres:
  primary:
    backup_type: pg_dump + WAL streaming
    schedule: continuous WAL + daily full dump at 02:00 UTC
    retention:
      hourly: 24
      daily: 30
      weekly: 12
      monthly: 12
    destination: s3://cortexprime-backups/postgres/
    encryption: aws:kms
    verification: automatic checksum + test restore weekly

  replicas:
    read_replicas: 2 (us-east-1a, us-east-1b)
    cross_region_replica: 1 (us-west-2)
    wal_stream_target: s3://cortexprime-backups-dr/postgres-wal/
```

**Backup command:**
```powershell
# Manual full backup
cortexctl backup create --component postgres

# Verify WAL streaming
cortexctl db wal-status
# Expected: "WAL archiving: ACTIVE | Last WAL pushed: 30s ago"
```

### 2.2 Redis Persistence

```yaml
redis:
  persistence:
    rdb:
      enabled: true
      save_interval: 900  # 15 min if >=1 key changed
      save_interval_dirty: 300  # 5 min if >=100 keys changed
      filename: dump.rdb
      path: /data/redis/

    aof:
      enabled: true
      fsync: everysec
      filename: appendonly.aof
      rewrite_last: 0

  backup:
    schedule: hourly RDB copy to S3
    destination: s3://cortexprime-backups/redis/
    retention: 24 hourly, 30 daily
```

### 2.3 Neo4j Backup

```yaml
neo4j:
  backup_type: neo4j-admin dump (full) + CDC log shipping
  schedule: daily full dump at 03:00 UTC
  retention:
    daily: 30
    weekly: 12
  destination: s3://cortexprime-backups/neo4j/
  verification: load-dump verification weekly
```

**Backup command:**
```powershell
# Manual Neo4j backup
cortexctl backup create --component neo4j

# Online backup (no downtime)
cortexctl neo4j backup-online --output s3://cortexprime-backups/neo4j/manual-$(Get-Date -Format yyyyMMdd-HHmmss).dump
```

### 2.4 Configuration Backup

```yaml
config_backup:
  scope:
    - cortexctl config export (all settings)
    - kubernetes manifests (deployments, configmaps, secrets)
    - terraform state (infrastructure)
    - env files (encrypted)
  schedule: daily at 02:00 UTC (bundled with full backup)
  destination: s3://cortexprime-backups/config/
  encryption: pgp + aws:kms
```

**Configuration export command:**
```powershell
# Export all configuration
cortexctl config export --format yaml --output cortex-config-$(Get-Date -Format yyyyMMdd).yaml

# Encrypt and upload
$passphrase = Read-Host -AsSecureString "Enter encryption passphrase"
cortexctl config encrypt --input cortex-config-*.yaml --passphrase $passphrase
aws s3 cp cortex-config-*.yaml.gpg s3://cortexprime-backups/config/
```

---

## 3. Recovery Scenarios

---

### 3.1 Scenario A: Database Failure (PostgreSQL)

**Symptoms:**
- API returns 500 errors with `database connection failed`
- Grafana dashboard shows `postgres_primary_down`
- PagerDuty alert: `PostgreSQL Primary Unreachable`
- Applications report `could not connect to server: Connection refused`

**Severity:** SEV-1

#### Immediate Response (first 5 minutes)

```powershell
# 1. Verify the outage
cortexctl db ping
# If timeout/failure → proceed

# 2. Check if replica is available
cortexctl db replication-status

# 3. Attempt automatic failover (if not already triggered)
cortexctl db failover --to-replica <replica-endpoint>

# 4. Verify failover succeeded
cortexctl db ping
cortexctl health --service api-gateway
```

#### Recovery from Backup (if failover fails)

```powershell
# 1. Identify latest valid backup
cortexctl backup list --component postgres --limit 5

# 2. Verify backup integrity
cortexctl backup verify --id <backup-id>

# 3. Restore backup to a replacement instance
cortexctl backup restore --id <backup-id> `
  --target-host <new-db-host> `
  --target-port 5432

# 4. Apply WAL logs for point-in-time recovery
cortexctl db pitr --backup-id <backup-id> --target-time "2026-07-04T14:25:00Z"

# 5. Update connection strings
cortexctl secrets propagate db-credentials --db postgres

# 6. Verify data integrity
cortexctl db verify-integrity
```

#### Point-in-Time Recovery (PITR)

```powershell
# Identify the target recovery time
# (e.g., just before a corrupting query was executed)

# List available WAL archive timestamps
cortexctl db wal-list --since 24h

# Perform PITR to specific timestamp
cortexctl db pitr `
  --backup-id <base-backup-id> `
  --target-time "2026-07-04T12:00:00Z" `
  --restore-target <new-db-instance>

# Verify recovered data
cortexctl db query --db cortexprime --command "SELECT COUNT(*) FROM missions;"
```

#### Validation

```powershell
# Run validation queries
cortexctl db query --db cortexprime --file validation-queries.sql

# Verify application connectivity
cortexctl health --all

# Compare row counts against known baseline
cortexctl db validate-row-counts --baseline baseline-$(Get-Date -Format yyyy-MM-dd).json
```

---

### 3.2 Scenario B: Redis Failure

**Symptoms:**
- Cache misses spike to 100%
- Session-based requests fail
- Rate limiting stops working
- Application latency increases significantly

**Severity:** SEV-2 (cache loss) / SEV-1 (session data loss)

#### Recovery from RDB Snapshot

```powershell
# 1. Identify latest valid RDB snapshot
cortexctl backup list --component redis --limit 5

# 2. Deploy replacement Redis instance
cortexctl redis deploy --instance-type cache.r6g.large --replicas 1

# 3. Load RDB snapshot
cortexctl redis restore --backup-id <backup-id> --target <new-redis-host>

# 4. Update application config
cortexctl secrets propagate redis-credentials

# 5. Verify connectivity
cortexctl redis ping --host <new-redis-host>
```

#### Recovery from AOF

```powershell
# If RDB is unavailable, use AOF replay
cortexctl redis restore-aof --aof-path s3://cortexprime-backups/redis/aof/latest/

# Monitor AOF replay progress
cortexctl redis aof-status

# Expected output:
# "AOF replay: 85% complete | 450MB processed | ETA: 2 minutes"
```

#### Cache Warmup

```powershell
# After Redis is restored, warm the cache
cortexctl cache warmup --strategy progressive --rate 1000

# Monitor cache hit ratio
cortexctl cache hit-ratio
# Expected: climbing from 0% to >80% within 10 minutes

# Verify key services
cortexctl health --service api-gateway --check-cache
```

---

### 3.3 Scenario C: Neo4j Failure

**Symptoms:**
- Knowledge graph queries fail
- Agent missions return "graph unavailable"
- Neo4j logs show `ERROR: Could not create connection to database`

**Severity:** SEV-1

#### Recovery from Dump

```powershell
# 1. List available Neo4j backups
cortexctl backup list --component neo4j --limit 5

# 2. Deploy replacement Neo4j instance
cortexctl neo4j deploy --edition enterprise --cluster-size 3

# 3. Restore from dump
cortexctl neo4j restore --backup-id <backup-id> --target <new-neo4j-host>

# 4. Rebuild indexes
cortexctl neo4j rebuild-indexes

# 5. Verify graph integrity
cortexctl neo4j verify --check-constraints --check-indexes
```

#### Graph Rebuild

```powershell
# If no backup is available, rebuild graph from mission history
cortexctl neo4j rebuild-from-missions --since 90d --batch-size 500

# Verify node/edge counts match expected
cortexctl neo4j stats
# Expected: "Nodes: 1,234,567 | Edges: 8,901,234 | Indexes: 12"
```

---

### 3.4 Scenario D: Complete Infrastructure Loss

**Symptoms:**
- All systems unreachable
- Cloud console shows region degraded
- No monitoring data received for >5 minutes

**Severity:** SEV-1 (critical)

#### Full Recovery from Backups (DR Region)

```powershell
# 1. DECLARE DISASTER
cortexctl dr declare --reason "us-east-1 complete infrastructure loss"

# 2. ACTIVATE DR region (us-west-2)
cortexctl dr activate --region us-west-2

# 3. PROVISION infrastructure via Terraform
cd terraform/environments/production
terraform workspace select us-west-2
terraform apply -auto-approve -var="dr_failover=true"

# 4. RESTORE PostgreSQL (latest full backup + WAL)
cortexctl backup restore --component postgres --backup-id <latest-dr-backup>
cortexctl secrets propagate db-credentials

# 5. RESTORE Redis
cortexctl backup restore --component redis --backup-id <latest-dr-backup>

# 6. RESTORE Neo4j
cortexctl backup restore --component neo4j --backup-id <latest-dr-backup>

# 7. DEPLOY application containers
kubectl apply -f k8s/production/ -n cortexprime
kubectl rollout status deployment -n cortexprime --timeout=300s

# 8. UPDATE DNS
cortexctl dr update-dns --region us-west-2 --ttl 60

# 9. VERIFY full recovery
cortexctl health --all
cortexctl dr status
```

#### IaC Rebuild (if backups are also unavailable)

```powershell
# 1. Bootstrap infrastructure from Terraform state
terraform init -reconfigure -backend-config="bucket=cortexprime-terraform-dr"
terraform plan -out=tfplan
terraform apply "tfplan"

# 2. Initialize empty databases with schema
cortexctl db migrate --latest
cortexctl neo4j apply-schema

# 3. Load configuration from exported config
cortexctl config import --file cortex-config-recovery.yaml

# 4. Verify baseline services
cortexctl health --all
```

---

### 3.5 Scenario E: Data Corruption

**Symptoms:**
- Missions returning nonsensical results
- Queries returning inconsistent data
- Validation checksum mismatches
- Application error: `constraint violation` or `integrity check failed`

**Severity:** SEV-1

#### Detecting Corruption

```powershell
# Run integrity checks
cortexctl db verify-integrity --all

# Check for orphaned records
cortexctl db find-orphans

# Compare data checksums against last known good state
cortexctl db checksum-compare --baseline baseline-checksums.json

# Scan for constraint violations
cortexctl db validate-constraints
```

#### Restoring Clean Data

```powershell
# 1. Determine the scope of corruption
cortexctl db corruption-report
# Expected: "Corrupt tables: missions, mission_results | Time range: 2026-07-03 14:00 - 15:30 UTC"

# 2. Identify the last clean backup before corruption window
cortexctl backup list --component postgres --before "2026-07-03T14:00:00Z" --limit 1

# 3. Partial restore (table-level if supported)
cortexctl db partial-restore `
  --tables missions,mission_results `
  --backup-id <clean-backup-id> `
  --target-time "2026-07-03T13:59:00Z"

# 4. Full restore if partial not possible
cortexctl db pitr `
  --backup-id <clean-backup-id> `
  --target-time "2026-07-03T13:59:00Z" `
  --database cortexprime
```

#### Integrity Verification

```powershell
# Re-run integrity checks
cortexctl db verify-integrity --all

# Validate foreign keys
cortexctl db validate-fks

# Check application-level consistency
cortexctl db run-consistency-queries --file app-consistency-checks.sql

# Verify mission count matches expected
cortexctl db query --command "SELECT COUNT(*), status FROM missions GROUP BY status;"
```

---

### 3.6 Scenario F: Security Breach

**Symptoms:**
- Unauthorized API access detected
- Suspicious user activity in audit logs
- Unusual data export patterns
- Security alert from intrusion detection

**Severity:** SEV-1

#### Isolation

```powershell
# 1. Immediately isolate affected systems
cortexctl security isolate --service <affected-service>

# 2. Block compromised credentials
cortexctl user deactivate --id <compromised-user-id>
cortexctl user revoke-sessions --id <compromised-user-id>

# 3. Block suspicious IPs at the gateway
cortexctl security block-ip --cidr <suspicious-cidr> --reason "Security incident"

# 4. Enable read-only mode if needed
cortexctl system read-only --enable --reason "Security incident investigation"
```

#### Credential Rotation

```powershell
# Rotate ALL secrets immediately
cortexctl secrets rotate api-key --all
cortexctl secrets rotate db-credentials --all
cortexctl secrets rotate jwt-key --force

# Regenerate service accounts and tokens
cortexctl secrets regenerate --service <all> --force

# Verify old credentials no longer work
cortexctl secrets validate-expired
```

#### Forensic Analysis

```powershell
# Export all relevant audit logs
cortexctl logs export `
  --query "security" `
  --since 72h `
  --format json `
  --output security-incident-logs.json

# Capture memory/disk for forensic analysis
cortexctl security forensic-snapshot --service <affected-service>

# Analyze access patterns
cortexctl security analyze-access --timeframe 72h --output access-analysis.json

# Preserve evidence
cortexctl security preserve-evidence --output s3://cortexprime-forensics/incident-<id>/
```

#### Recovery

```powershell
# 1. After forensic analysis, rebuild compromised services
cortexctl service rebuild --service <affected-service>

# 2. Restore data from last clean backup
cortexctl backup restore --component postgres --backup-id <pre-breach-backup>

# 3. Apply security patches
cortexctl update apply --security-patches-only

# 4. Harden security configuration
cortexctl security apply-hardening --profile post-incident

# 5. Gradual re-enable services
cortexctl system read-only --disable
cortexctl security unblock-ip --all

# 6. Continuous monitoring for recurrence
cortexctl security enhanced-monitoring --enable
```

---

### 3.7 Scenario G: Regional Outage

**Symptoms:**
- All instances in primary region (us-east-1) become unavailable
- Cross-region health checks fail
- Cloud provider status page confirms regional outage

**Severity:** SEV-1

#### Multi-Region Failover

```powershell
# 1. CONFIRM regional outage
cortexctl dr region-status --region us-east-1
# If "DOWN" → proceed with failover

# 2. DECLARE DR event
cortexctl dr declare --reason "us-east-1 region outage" --type region-failover

# 3. PROMOTE DR region to primary
cortexctl dr promote-dr --region us-west-2

# 4. VERIFY DR region databases are healthy
cortexctl db ping --host cortexprime-dr.c9wj6xqoyl9w.us-west-2.rds.amazonaws.com
cortexctl redis ping --host cortexprime-dr.yxkz4h.ng.0001.usw2.cache.amazonaws.com
cortexctl neo4j ping --host cortexprime-dr-neo4j.us-west-2.neo4j.io

# 5. SCALE up DR infrastructure for full production load
cortexctl worker scale --pool default --replicas 20
cortexctl worker scale --pool research --replicas 15

# 6. SWITCH DNS to point to DR region
cortexctl dr switch-dns --target-region us-west-2

# Wait for DNS propagation (TTL: 60s)
Start-Sleep -Seconds 120
```

#### Traffic Shifting

```powershell
# Verify DNS propagation
cortexctl dr dns-status --domain cortexprime.io

# Shift traffic gradually (if both regions partially available)
cortexctl dr shift-traffic `
  --from-region us-east-1 `
  --to-region us-west-2 `
  --percentage 25 `
  --interval 60s

# Monitor traffic shifting
cortexctl dr traffic-distribution
# Expected: "us-east-1: 0% | us-west-2: 100%"
```

#### DNS Update

```powershell
# Update Route53 failover record
aws route53 change-resource-record-sets --hosted-zone-id ZONE123 `
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "cortexprime.io",
        "Type": "A",
        "SetIdentifier": "primary",
        "Failover": "SECONDARY",
        "AliasTarget": {
          "HostedZoneId": "ZONE456",
          "DNSName": "cortexprime-dr.us-west-2.elb.amazonaws.com",
          "EvaluateTargetHealth": true
        }
      }
    }]
  }'

# Monitor DNS health checks
aws route53 list-health-checks | ConvertFrom-Json |
  Select-Object -ExpandProperty HealthChecks |
  Where-Object { $_.HealthCheckConfig.FullyQualifiedDomainName -match "cortexprime" }
```

---

## 4. Recovery Procedures (Step-by-Step)

### 4.1 Generalized Recovery Workflow

```
1. DETECT
   └── Confirm alert, assess severity, declare incident
   
2. ASSESS
   └── Determine scope (component, data loss, region)
   └── Identify last good state (backup timestamp, snapshot)
   └── Choose recovery strategy from scenarios above
   
3. COMMUNICATE
   └── Post in #dr-war-room
   └── Open bridge call
   └── Update status page
   
4. ISOLATE (if needed)
   └── Stop writes to affected systems
   └── Redirect traffic away from failed component
   └── Enable read-only mode if data integrity at risk
   
5. RECOVER
   └── Execute selected recovery procedure
   └── Restore from backup
   └── Rebuild infrastructure
   
6. VALIDATE
   └── Run health checks
   └── Verify data integrity
   └── Confirm application functionality
   
7. RESUME
   └── Restore full traffic
   └── Disable read-only mode
   └── Confirm all services operational
   
8. POST-MORTEM
   └── Document incident timeline
   └── Identify root cause
   └── Create action items
```

### 4.2 Critical Command Sequences

**PostgreSQL recovery sequence:**
```powershell
cortexctl backup verify --id <id>; if ($?) {
  cortexctl backup restore --id <id> --target-host <host>
  cortexctl secrets propagate db-credentials
  cortexctl db verify-integrity
  cortexctl health --all
}
```

**Full system recovery sequence:**
```powershell
# Infrastructure
terraform apply -auto-approve

# Databases
cortexctl backup restore --component postgres --backup-id <id>
cortexctl backup restore --component redis --backup-id <id>
cortexctl backup restore --component neo4j --backup-id <id>

# Applications
kubectl apply -f k8s/production/ -n cortexprime
kubectl rollout status deployment -n cortexprime --timeout=300s

# Verification
cortexctl health --all
cortexctl dr verification-report
```

---

## 5. Disaster Recovery Testing

### 5.1 Scheduled DR Tests

| Test Type | Frequency | Scope | Participants |
|---|---|---|---|
| Tabletop exercise | Monthly | Review procedures, walk through scenario | DR team |
| Component failover | Quarterly | Single database/Redis failover | SRE team |
| Regional failover | Semi-annual | Full DR region activation | Full DR team |
| Full recovery drill | Annual | Complete rebuild from zero | All teams |

### 5.2 Test Scenarios

```powershell
# Initiate a DR test (non-production environment)
cortexctl dr test begin --scenario "postgres-failover" --environment staging

# Monitor test progress
cortexctl dr test status --id <test-id>

# Component failover test command
cortexctl db failover-test --target-replica <replica-endpoint> --duration 10m

# Validation after test
cortexctl dr test validate --id <test-id>
cortexctl dr test report --id <test-id> --output dr-test-report.md
```

### 5.3 Validation Criteria

```yaml
dr_test_validation:
  postgresql:
    - "SELECT COUNT(*) FROM missions" matches pre-failover count
    - Replication lag < 10MB within 5 minutes of failback
    - Zero constraint violations
    - Application health checks pass

  redis:
    - Cache hit ratio > 70% within 10 minutes of warmup
    - Session data integrity verified
    - Rate limiting operational

  neo4j:
    - Node count matches pre-failover within 1%
    - All indexes rebuilt successfully
    - Graph queries return expected results

  application:
    - API p95 latency < 500ms
    - Error rate < 0.1%
    - All endpoints return 200
    - Mission execution success rate > 95%
```

---

## 6. Business Continuity

### 6.1 Degraded Mode Operations

| Degraded State | Available Features | Unavailable Features | Action Required |
|---|---|---|---|
| **No cache (Redis down)** | Core API, missions, connector sync | Rate limiting, session caching, real-time updates | Accept increased latency; warm cache on recovery |
| **No graph (Neo4j down)** | CRUD operations, connector sync | Knowledge graph queries, agent research missions | Use flat-file fallback for mission context |
| **No search (DB degraded)** | Read-only API | Mission creation, user management, connector sync | Enable read-only mode; queue writes |
| **Single region** | All features | Multi-region HA | No action; latent failover risk |
| **Reduced capacity** | Core features only | Batch processing, analytics, heavy research | Throttle non-critical missions |

### 6.2 Minimum Viable Service (MVS)

In a catastrophic scenario, the following services constitute the minimum viable service:

```
1. API Gateway (authenticated endpoints only)
2. PostgreSQL (read-write)
3. Worker Manager (limited pool: 3 workers)
4. Connector Sync (critical connectors only)
5. Redis (if available)

Non-essential services to deprioritize:
- Neo4j graph queries (fallback to flat files)
- Mission analytics / reporting
- Batch processing jobs
- User management (except security)
- Webhook delivery
```

**MVS activation command:**
```powershell
cortexctl system mvs --enable --reason "Regional capacity constraint"
cortexctl worker scale --pool default --replicas 3
cortexctl connector pause --all --except critical
cortexctl mission disable --type analytics,batch,report
```

### 6.3 Communication Templates

**Internal incident notification (Slack):**
```
:rotating_light: *INCIDENT DECLARED* :rotating_light:
Severity: SEV-1
Service: {service_name}
Impact: {impact_description}
Started: {timestamp}
Status: Investigating / Mitigating
Lead: @{dr_coordinator}
Bridge: https://meet.cortexprime.internal/dr-bridge
```

**Customer-facing status page:**
```
We are currently investigating an issue affecting {service_name}. 
Some users may experience {impact_description}. 
We will provide updates every 30 minutes. 
Next update: {timestamp + 30min}
```

**Post-incident summary (email):**
```
Subject: [Post-Mortem] {incident_title} - {date}

Summary:
{2-3 sentence summary of what happened}

Timeline:
- {time} - Incident detected
- {time} - Mitigation started
- {time} - Service restored
- {time} - All clear declared

Root Cause:
{root cause description}

Impact:
- Duration: {duration}
- Affected users: {count}
- Data loss: {yes/no}

Action Items:
1. {action item} - Owner: @person - Due: {date}
2. {action item} - Owner: @person - Due: {date}

Full post-mortem: {link to document}
```

---

## 7. Post-Recovery

### 7.1 Verification Checklist

```markdown
## Post-Recovery Verification Checklist

### Services
- [ ] All pods healthy: `kubectl get pods -n cortexprime | grep -v Running`
- [ ] No PagerDuty alerts firing
- [ ] Prometheus targets all UP

### API
- [ ] Health endpoint returns 200: `curl -s https://cortexprime.internal/health`
- [ ] Authentication working: `curl -s -o /dev/null -w "%{http_code}" https://cortexprime.internal/api/v1/auth/verify`
- [ ] Mission CRUD operational: `cortexctl mission list --limit 1`

### Databases
- [ ] PostgreSQL connected: `cortexctl db ping`
- [ ] Replication lag < 10MB: `cortexctl db replication-status`
- [ ] Redis connected: `cortexctl redis ping`
- [ ] Neo4j connected: `cortexctl neo4j ping`

### Data Integrity
- [ ] Row counts match expected baseline
- [ ] No orphaned records
- [ ] All indexes valid
- [ ] Checksums verified

### Performance
- [ ] API p95 latency < 500ms
- [ ] Mission p95 duration < 60s
- [ ] Error rate < 0.1%
- [ ] Cache hit ratio > 70%
```

### 7.2 Data Integrity Validation

```powershell
# Run comprehensive integrity checks
cortexctl dr validate-data-integrity --full

# Cross-check counts
cortexctl dr validate-data-integrity --check counts

# Verify checksums against last known good state
cortexctl dr validate-data-integrity --check checksums

# Check referential integrity
cortexctl dr validate-data-integrity --check referential

# Generate integrity report
cortexctl dr validate-data-integrity --report --output integrity-report.json
```

### 7.3 Performance Validation

```powershell
# Run performance benchmark
cortexctl dr benchmark --duration 5m

# Expected results:
# +---------------------+----------------+----------------+
# | Metric              | Pre-Incident   | Post-Recovery  |
# +---------------------+----------------+----------------+
# | API p95 latency     | 120ms          | 135ms          |
# | Requests/sec        | 2,450          | 2,380          |
# | Mission p95 duration| 12.5s          | 13.2s          |
# | Error rate          | 0.02%          | 0.03%          |
# +---------------------+----------------+----------------+

# If performance is degraded beyond 20% of baseline, investigate:
cortexctl capacity overview
cortexctl logs search --level warn --since 5m
```

### 7.4 Incident Report

```powershell
# Generate automated incident report
cortexctl dr incident-report --id <incident-id> --output dr-incident-report.md

# Include:
# - Summary
# - Timeline (from incident timeline entries)
# - Root cause analysis
# - Recovery actions taken
# - Data integrity validation results
# - Performance comparison
# - Action items

# Export supporting data
cortexctl logs export --since 48h --format json --output incident-logs.json
cortexctl dr benchmark --output benchmark-results.json
```

---

## Appendix A: Backup Location Reference

| Component | Primary Backup Path | DR Backup Path |
|---|---|---|
| PostgreSQL | `s3://cortexprime-backups/postgres/` | `s3://cortexprime-backups-dr/postgres/` |
| Redis | `s3://cortexprime-backups/redis/` | `s3://cortexprime-backups-dr/redis/` |
| Neo4j | `s3://cortexprime-backups/neo4j/` | `s3://cortexprime-backups-dr/neo4j/` |
| Config | `s3://cortexprime-backups/config/` | `s3://cortexprime-backups-dr/config/` |
| Terraform State | `s3://cortexprime-terraform/state/` | `s3://cortexprime-terraform-dr/state/` |

## Appendix B: DR Quick Reference Card

```yaml
scenario: postgres_failure
procedure:
  ping: cortexctl db ping
  failover: cortexctl db failover --to-replica <host>
  restore: cortexctl backup restore --id <id> --target-host <host>
  pitr: cortexctl db pitr --backup-id <id> --target-time <time>
  verify: cortexctl db verify-integrity

scenario: redis_failure
procedure:
  ping: cortexctl redis ping
  restore_rdb: cortexctl redis restore --backup-id <id>
  restore_aof: cortexctl redis restore-aof --aof-path <path>
  warmup: cortexctl cache warmup

scenario: neo4j_failure
procedure:
  ping: cortexctl neo4j ping
  restore: cortexctl neo4j restore --backup-id <id>
  rebuild: cortexctl neo4j rebuild-from-missions
  verify: cortexctl neo4j verify --check-constraints

scenario: full_region_loss
procedure:
  declare: cortexctl dr declare --reason "Regional outage"
  deploy: terraform apply -auto-approve -var="dr_failover=true"
  restore_db: cortexctl backup restore --component postgres --backup-id <id>
  restore_cache: cortexctl backup restore --component redis --backup-id <id>
  restore_graph: cortexctl backup restore --component neo4j --backup-id <id>
  deploy_app: kubectl apply -f k8s/production/ -n cortexprime
  dns: cortexctl dr switch-dns --target-region us-west-2
  verify: cortexctl health --all

scenario: data_corruption
procedure:
  detect: cortexctl db verify-integrity --all
  identify_clean: cortexctl backup list --component postgres --before <corruption-time>
  restore: cortexctl db pitr --backup-id <id> --target-time <pre-corruption-time>
  verify: cortexctl db validate-constraints; cortexctl db verify-integrity --all

scenario: security_breach
procedure:
  isolate: cortexctl security isolate --service <service>
  rotate: cortexctl secrets rotate --all --force
  forensics: cortexctl security forensic-snapshot --service <service>
  rebuild: cortexctl service rebuild --service <service>
  harden: cortexctl security apply-hardening --profile post-incident

scenario: regional_failover
procedure:
  confirm: cortexctl dr region-status --region us-east-1
  declare: cortexctl dr declare --type region-failover
  promote: cortexctl dr promote-dr --region us-west-2
  verify_db: cortexctl db ping --host <dr-host>
  scale: cortexctl worker scale --pool default --replicas 20
  dns: cortexctl dr switch-dns --target-region us-west-2
  traffic: cortexctl dr traffic-distribution