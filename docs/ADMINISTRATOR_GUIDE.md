# CortexPrime v1.0.0 GA — Administrator Guide

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Architecture Overview](#2-architecture-overview)
3. [Installation](#3-installation)
4. [Initial Configuration](#4-initial-configuration)
5. [User Management](#5-user-management)
6. [Organization Management](#6-organization-management)
7. [Connector Administration](#7-connector-administration)
8. [Worker Administration](#8-worker-administration)
9. [Secrets Management](#9-secrets-management)
10. [Monitoring & Observability](#10-monitoring--observability)
11. [Backup & Recovery](#11-backup--recovery)
12. [Security Administration](#12-security-administration)
13. [Licensing](#13-licensing)
14. [Platform Updates](#14-platform-updates)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Introduction

CortexPrime is an enterprise AI orchestration platform that connects large language models (LLMs), knowledge bases, automation tooling, and human-in-the-loop workflows into a unified runtime. It enables organizations to build, deploy, and govern AI agents at scale.

**Primary audience:**

- **Platform administrators** — responsible for installation, configuration, and day-to-day operations
- **IT operations teams** — managing infrastructure, scaling, backups, and monitoring
- **Security teams** — enforcing authentication, authorization, secrets management, and audit compliance

This guide covers every administrative surface of CortexPrime v1.0.0 GA. Commands are provided for Linux (bash) and Windows (PowerShell) where applicable.

---

## 2. Architecture Overview

CortexPrime follows a modular, microservices-based architecture with the following core components:

```
┌─────────────────────────────────────────────────────────────────┐
│                         Load Balancer                           │
│                   (Traefik / Nginx / ALB)                        │
└──────┬────────────────────┬─────────────────────┬───────────────┘
       │                    │                     │
┌──────▼──────┐    ┌───────▼───────┐    ┌────────▼──────────┐
│   API        │    │   Frontend    │    │   WebSocket Hub    │
│   Gateway    │    │   (Next.js)   │    │   (Real-time)      │
└──────┬──────┘    └───────────────┘    └────────┬──────────┘
       │                                         │
┌──────▼──────────────────────────────────────────▼──────────────┐
│                       Service Mesh                               │
│  (gRPC + NATS message broker for inter-service communication)   │
├────────┬────────┬────────┬────────┬────────┬────────┬─────────┤
│ Auth   │ Agent  │ Conn-  │ Worker │ Know-  │ Sched- │ Audit   │
│ Service│ Runtime│ ector  │ Mgmt   │ ledge  │ uler   │ Service │
│ :4001  │ :4002  │ :4003  │ :4004  │ :4005  │ :4006  │ :4007   │
└───┬────┴───┬────┴───┬────┴───┬────┴───┬────┴───┬────┴───┬────┘
    │        │        │        │        │        │        │
┌───▼────────▼────────▼────────▼────────▼────────▼────────▼──────┐
│                        Data Layer                               │
├──────────────┬─────────────────┬───────────────────────────────┤
│  PostgreSQL  │      Redis       │            Neo4j              │
│  (Primary    │   (Cache,        │   (Knowledge graph,           │
│   store)     │    sessions,     │    agent relationships)       │
│              │    queues)       │                               │
└──────────────┴─────────────────┴───────────────────────────────┘
```

**Component relationships:**

| Service     | Depends on                       | Purpose                                  |
|-------------|----------------------------------|------------------------------------------|
| API Gateway | Auth Service, PostgreSQL         | Route authentication, rate-limit requests |
| Auth        | PostgreSQL, Redis                | JWT issuance, MFA, SSO, session store     |
| Agent       | Auth, Connector, Knowledge, Neo4j| LLM orchestration, tool calling           |
| Connector   | Secrets Store, PostgreSQL        | Third-party API integration (GitHub, Jira)|
| Worker      | Redis, Secrets Store             | Browser, voice, desktop worker pools      |
| Knowledge   | PostgreSQL, Neo4j, Vector Store  | RAG pipelines, document indexing          |
| Scheduler   | PostgreSQL, Redis                | Cron-based agent triggers                 |
| Audit       | PostgreSQL                       | Immutable audit event log                 |

---

## 3. Installation

### 3.1 Prerequisites

| Requirement       | Minimum       | Recommended    |
|-------------------|---------------|----------------|
| CPU               | 8 cores       | 16+ cores      |
| RAM               | 32 GB         | 64+ GB         |
| Disk              | 100 GB SSD    | 500 GB NVMe    |
| Docker Engine     | 24.0+         | 26.0+          |
| Kubernetes        | 1.28+         | 1.30+          |
| PostgreSQL        | 15+           | 16+            |
| Redis             | 7.2+          | 7.4+           |
| Neo4j             | 5.x           | 5.20+          |

### 3.2 Docker Compose

**Prerequisites:** Docker Engine 24.0+, Docker Compose 2.24+.

```bash
# Download the compose file and environment template
curl -O https://releases.cortexprime.io/v1.0.0/docker-compose.yml
curl -O https://releases.cortexprime.io/v1.0.0/.env.example

# Copy and edit environment
cp .env.example .env
nano .env

# Start all services
docker compose up -d

# Verify health
docker compose ps
docker compose logs --tail=50 api-gateway
```

```powershell
# Windows PowerShell
Invoke-WebRequest -Uri "https://releases.cortexprime.io/v1.0.0/docker-compose.yml" -OutFile "docker-compose.yml"
Invoke-WebRequest -Uri "https://releases.cortexprime.io/v1.0.0/.env.example" -OutFile ".env.example"
Copy-Item .env.example .env
notepad .env
docker compose up -d
docker compose ps
```

### 3.3 Kubernetes (kubectl + manifests)

```bash
# Apply namespace and core resources
kubectl create namespace cortexprime
kubectl apply -f https://releases.cortexprime.io/v1.0.0/k8s/namespace.yaml
kubectl apply -f https://releases.cortexprime.io/v1.0.0/k8s/configmap.yaml
kubectl apply -f https://releases.cortexprime.io/v1.0.0/k8s/secrets.yaml
kubectl apply -f https://releases.cortexprime.io/v1.0.0/k8s/postgres.yaml
kubectl apply -f https://releases.cortexprime.io/v1.0.0/k8s/redis.yaml
kubectl apply -f https://releases.cortexprime.io/v1.0.0/k8s/neo4j.yaml

# Deploy services
kubectl apply -f https://releases.cortexprime.io/v1.0.0/k8s/services/

# Verify
kubectl -n cortexprime get pods
kubectl -n cortexprime get svc
```

### 3.4 Helm Chart

```bash
# Add the CortexPrime Helm repository
helm repo add cortexprime https://helm.cortexprime.io
helm repo update

# Install with defaults
helm install cortexprime cortexprime/cortexprime \
  --namespace cortexprime \
  --create-namespace \
  --set global.environment=production

# Install with custom values
helm install cortexprime cortexprime/cortexprime \
  --namespace cortexprime \
  --values custom-values.yaml
```

**custom-values.yaml** example:

```yaml
global:
  environment: production
  domain: cortexprime.example.com

postgresql:
  auth:
    password: change-me-please
  primary:
    persistence:
      size: 100Gi

redis:
  auth:
    password: change-me-too
  master:
    persistence:
      size: 20Gi

neo4j:
  password: change-me-three
  core:
    numberOfServers: 3

ingress:
  enabled: true
  className: nginx
  tls:
    - hosts:
        - cortexprime.example.com
      secretName: cortexprime-tls
```

### 3.5 Air-Gapped Installation

For environments with no internet access:

```bash
# Step 1: On an internet-connected machine, download the air-gap bundle
curl -O https://releases.cortexprime.io/v1.0.0/cortexprime-airgap-v1.0.0.tar.gz
curl -O https://releases.cortexprime.io/v1.0.0/cortexprime-airgap-v1.0.0.tar.gz.sha256

# Verify checksum
sha256sum --check cortexprime-airgap-v1.0.0.tar.gz.sha256

# Transfer bundle via secure media to the air-gapped host

# Step 2: On the air-gapped host, extract and load images
tar -xzf cortexprime-airgap-v1.0.0.tar.gz
cd cortexprime-airgap-v1.0.0

# Load Docker images
docker load -i images/cortexprime-api.tar
docker load -i images/cortexprime-frontend.tar
docker load -i images/cortexprime-agent.tar
docker load -i images/cortexprime-worker.tar
# ... repeat for all images

# Load into a private registry (optional, for K8s)
docker tag cortexprime/api:1.0.0 registry.internal/cortexprime/api:1.0.0
docker push registry.internal/cortexprime/api:1.0.0

# Deploy using the bundled compose or Helm chart
docker compose -f docker-compose.airgap.yml up -d
```

Air-gapped Helm install:

```bash
helm install cortexprime ./charts/cortexprime \
  --namespace cortexprime \
  --set image.registry=registry.internal/cortexprime \
  --set global.airgap=true
```

---

## 4. Initial Configuration

### 4.1 Environment Variables

The `.env` file (Docker) or ConfigMap (K8s) controls all runtime configuration. Key variables:

```bash
# --- Core ---
CORTEXPRIME_ENV=production
CORTEXPRIME_DOMAIN=cortexprime.example.com
CORTEXPRIME_SECRET_KEY=<generate with: openssl rand -hex 32>

# --- Database ---
DATABASE_URL=postgresql://cortexprime:password@postgres:5432/cortexprime
DATABASE_POOL_MIN=5
DATABASE_POOL_MAX=50

# --- Redis ---
REDIS_URL=redis://:password@redis:6379/0
REDIS_SENTINEL_URL=redis://:password@redis-sentinel:26379/0

# --- Neo4j ---
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# --- LLM Provider ---
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o
LLM_MAX_TOKENS=16384

# --- Auth ---
JWT_SECRET=<generate with: openssl rand -hex 64>
JWT_ACCESS_TOKEN_TTL=15m
JWT_REFRESH_TOKEN_TTL=7d
JWT_ISSUER=cortexprime

# --- Observability ---
SENTRY_DSN=https://key@sentry.io/project
METRICS_ENABLED=true
TRACING_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
```

### 4.2 Database Setup

```bash
# Run initial migrations
docker compose exec api-gateway npx prisma migrate deploy

# Apply seed data (admin user, default roles)
docker compose exec api-gateway npx prisma db seed

# Verify
docker compose exec postgres psql -U cortexprime -c "\dt"
```

```bash
# Manual migration (air-gapped)
kubectl -n cortexprime exec deployment/api-gateway -- npx prisma migrate deploy
```

### 4.3 Neo4j Setup

```bash
# Verify connectivity
docker compose exec api-gateway npx ts-node scripts/verify-neo4j.ts

# Create indexes for performance
docker compose exec neo4j cypher-shell -u neo4j -p password \
  "CREATE INDEX agent_name_idx IF NOT EXISTS FOR (a:Agent) ON (a.name);"

docker compose exec neo4j cypher-shell -u neo4j -p password \
  "CREATE INDEX knowledge_idx IF NOT EXISTS FOR (k:KnowledgeNode) ON (k.embedding);"

# Verify
docker compose exec neo4j cypher-shell -u neo4j -p password \
  "CALL db.indexes();"
```

### 4.4 Redis Setup

```bash
# Verify connectivity
docker compose exec redis redis-cli -a password PING
# Should return: PONG

# Configure maxmemory policy
docker compose exec redis redis-cli -a password CONFIG SET maxmemory 4gb
docker compose exec redis redis-cli -a password CONFIG SET maxmemory-policy allkeys-lru

# Verify
docker compose exec redis redis-cli -a password INFO memory
```

### 4.5 LLM Provider Setup

Supported providers (configured in the admin UI at **Settings > LLM Providers**):

| Provider        | Environment Variable              | Notes                        |
|-----------------|-----------------------------------|------------------------------|
| OpenAI          | `LLM_API_KEY`                     | Requires org ID for enterprise |
| Azure OpenAI    | `AZURE_OPENAI_ENDPOINT`           | Uses Azure AD auth           |
| Anthropic       | `ANTHROPIC_API_KEY`               | Sonnet 4, Opus models        |
| Google Gemini   | `GOOGLE_API_KEY`                  | Gemini 1.5 Pro / 2.0 Flash  |
| AWS Bedrock     | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | IAM-based           |
| Ollama (local)  | `OLLAMA_BASE_URL`                 | Self-hosted, air-gapped      |

```bash
# Test LLM connectivity
docker compose exec api-gateway npx ts-node scripts/test-llm.ts \
  --provider openai \
  --model gpt-4o \
  --prompt "Hello, respond with 'OK'"
```

---

## 5. User Management

### 5.1 Creating Users

**Via CLI (admin token required):**

```bash
# Generate an admin API token from the admin UI (Settings > API Tokens)
export ADMIN_TOKEN=cp_admin_xxxxxxxxxxxx

curl -X POST https://cortexprime.example.com/api/v1/admin/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "operator@example.com",
    "password": "SecurePass123!",
    "display_name": "Jane Operator",
    "roles": ["operator"]
  }'
```

**Via Admin UI:**

1. Navigate to **Admin > Users**
2. Click **Add User**
3. Fill in email, display name, and temporary password
4. Select roles and groups
5. Click **Create** — an invitation email is sent automatically

### 5.2 Managing Roles

CortexPrime ships with four built-in roles:

| Role          | Permissions                                                |
|---------------|------------------------------------------------------------|
| `super_admin` | Full platform access, including licensing and audit        |
| `admin`       | All org-level settings, user management, connector config  |
| `operator`    | Manage agents, workers, view dashboards                    |
| `viewer`      | Read-only access to assigned resources                     |

**Create a custom role:**

```bash
curl -X POST https://cortexprime.example.com/api/v1/admin/roles \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "deploy_engineer",
    "permissions": [
      "agents:deploy",
      "agents:rollback",
      "workers:view",
      "logs:read"
    ]
  }'
```

### 5.3 RBAC / ABAC

CortexPrime supports both Role-Based Access Control (RBAC) and Attribute-Based Access Control (ABAC).

**ABAC policy example** (stored in PostgreSQL `abac_policies` table):

```json
{
  "effect": "allow",
  "actions": ["agents:read", "agents:execute"],
  "conditions": {
    "resource.department": "${user.department}",
    "resource.environment": ["dev", "staging"],
    "time.between": ["06:00", "20:00"]
  }
}
```

Policies are evaluated at request time. To create an ABAC policy:

```bash
curl -X POST https://cortexprime.example.com/api/v1/admin/abac-policies \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d @abac-policy.json
```

### 5.4 Groups

```bash
# Create a group
curl -X POST https://cortexprime.example.com/api/v1/admin/groups \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "engineering-deploy",
    "description": "Engineering team with deploy permissions"
  }'

# Add user to group
curl -X POST https://cortexprime.example.com/api/v1/admin/groups/engineering-deploy/members \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "usr_abc123"}'
```

### 5.5 Sessions

Session configuration is managed via environment variables:

```bash
JWT_ACCESS_TOKEN_TTL=15m       # Short-lived access token
JWT_REFRESH_TOKEN_TTL=7d       # Refresh token expiry
SESSION_MAX_CONCURRENT=5       # Max concurrent sessions per user
SESSION_INACTIVITY_TIMEOUT=30m # Auto-terminate idle sessions
```

**List and terminate sessions:**

```bash
# List active sessions for a user
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/users/usr_abc123/sessions

# Terminate a specific session
curl -X DELETE \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/sessions/sess_xyz789

# Terminate all sessions for a user
curl -X DELETE \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/users/usr_abc123/sessions
```

### 5.6 Multi-Factor Authentication (MFA)

**Enforce MFA for all users:**

```bash
curl -X PATCH https://cortexprime.example.com/api/v1/admin/settings \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "mfa_policy": "required",
    "mfa_methods": ["totp", "webauthn", "sms"]
  }'
```

Supported MFA methods:
- **TOTP** — Time-based one-time password (Google Authenticator, Authy)
- **WebAuthn** — FIDO2 hardware keys (YubiKey, Touch ID)
- **SMS** — SMS-based codes (requires SMS provider configuration)

**Admin-enroll a user's MFA (for lost devices):**

```bash
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/users/usr_abc123/mfa/reset
```

### 5.7 Single Sign-On (SSO)

CortexPrime supports OIDC and SAML 2.0.

**OIDC configuration (Azure AD / Okta / Keycloak):**

```bash
curl -X PUT https://cortexprime.example.com/api/v1/admin/sso/oidc \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_name": "Azure AD",
    "issuer_url": "https://login.microsoftonline.com/{tenant}/v2.0",
    "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "client_secret": "yoursecret",
    "scopes": ["openid", "profile", "email", "groups"],
    "auto_provision": true,
    "default_role": "viewer"
  }'
```

**SAML 2.0 configuration:**

```bash
curl -X PUT https://cortexprime.example.com/api/v1/admin/sso/saml \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_name": "Okta",
    "idp_metadata_url": "https://okta.example.com/app/metadata.xml",
    "entity_id": "https://cortexprime.example.com/saml/metadata",
    "acs_url": "https://cortexprime.example.com/saml/acs",
    "auto_provision": true
  }'
```

---

## 6. Organization Management

### 6.1 Organizations

```bash
# Create an organization
curl -X POST https://cortexprime.example.com/api/v1/admin/organizations \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "slug": "acme-corp",
    "domain": "acme.com",
    "plan": "enterprise",
    "settings": {
      "max_seats": 500,
      "max_agents": 100,
      "storage_limit_gb": 500
    }
  }'

# List organizations
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/organizations

# Suspend an organization
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/organizations/org_abc/suspend
```

### 6.2 Departments

```bash
curl -X POST https://cortexprime.example.com/api/v1/admin/organizations/org_abc/departments \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Engineering",
    "parent_id": null
  }'
```

### 6.3 Tenants (Multi-Tenancy)

For MSP and multi-tenant deployments:

```bash
curl -X POST https://cortexprime.example.com/api/v1/admin/tenants \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "organization_id": "org_abc",
    "name": "Acme Production",
    "isolation_level": "database",  // "database", "schema", "shared"
    "database_url": "postgresql://cortexprime:pass@tenant-db:5432/acme"
  }'
```

Isolation levels:
- `database` — Each tenant gets a dedicated PostgreSQL database
- `schema` — Each tenant gets a dedicated schema in the shared database
- `shared` — Row-level tenant isolation in shared tables

### 6.4 Projects

Projects group agents, knowledge bases, and connections within an organization.

```bash
curl -X POST https://cortexprime.example.com/api/v1/admin/organizations/org_abc/projects \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Support Bot",
    "description": "AI agent for tier-1 customer support",
    "department_id": "dept_eng",
    "members": ["usr_abc123", "usr_def456"]
  }'
```

---

## 7. Connector Administration

Connectors link CortexPrime to external services. Each connector requires OAuth credentials or API keys.

### 7.1 GitHub Connector

```bash
# Register a GitHub App at https://github.com/settings/apps
# Set the callback URL to: https://cortexprime.example.com/api/v1/connectors/github/callback
# Obtain App ID, Client ID, and generate a private key

curl -X POST https://cortexprime.example.com/api/v1/admin/connectors \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "github",
    "name": "GitHub Production",
    "config": {
      "app_id": "123456",
      "client_id": "Iv1.xxxxxxxxxxxx",
      "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
      "installation_id": "987654",
      "webhook_secret": "whsec_xxxxx",
      "permissions": ["pull_requests", "issues", "actions", "code"]
    }
  }'

# Test the connector
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/connectors/conn_abc/test
```

### 7.2 Jira Connector

```bash
curl -X POST https://cortexprime.example.com/api/v1/admin/connectors \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "jira",
    "name": "Jira Cloud",
    "config": {
      "domain": "acme.atlassian.net",
      "email": "bot@acme.com",
      "api_token": "ATATT3xFfGF...",
      "project_keys": ["SUPPORT", "ENG", "PROD"],
      "jql_filters": ["status != Closed"]
    }
  }'
```

### 7.3 Slack Connector

```bash
# Create a Slack App at https://api.slack.com/apps
# Enable Socket Mode, add scopes, install to workspace

curl -X POST https://cortexprime.example.com/api/v1/admin/connectors \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "slack",
    "name": "Slack Workspace",
    "config": {
      "bot_token": "xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx",
      "app_token": "xapp-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx",
      "signing_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "channels": ["general", "support", "devops"],
      "enable_slash_commands": true
    }
  }'
```

### 7.4 Microsoft Teams Connector

```bash
# Register an app in Azure AD with Microsoft Graph permissions
# Generate a client secret

curl -X POST https://cortexprime.example.com/api/v1/admin/connectors \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "teams",
    "name": "MS Teams",
    "config": {
      "tenant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "client_secret": "xxxx~xxxx~xxxx",
      "teams": ["Customer-Support", "IT-Helpdesk"],
      "notification_webhook_url": "https://cortexprime.example.com/api/v1/connectors/teams/webhook"
    }
  }'
```

### 7.5 ServiceNow Connector

```bash
curl -X POST https://cortexprime.example.com/api/v1/admin/connectors \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "servicenow",
    "name": "ServiceNow Prod",
    "config": {
      "instance_url": "https://acme.service-now.com",
      "username": "admin",
      "password": "password",
      "tables": ["incident", "change_request", "sc_req_item"],
      "auto_resolve": true
    }
  }'
```

### 7.6 Confluence Connector

```bash
curl -X POST https://cortexprime.example.com/api/v1/admin/connectors \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "confluence",
    "name": "Confluence Wiki",
    "config": {
      "domain": "acme.atlassian.net/wiki",
      "username": "bot@acme.com",
      "api_token": "ATATT3xFfGF...",
      "space_keys": ["ENG", "OPS", "HR"],
      "sync_interval_minutes": 60,
      "include_attachments": false
    }
  }'
```

### 7.7 Notion Connector

```bash
# Create an integration at https://www.notion.so/my-integrations

curl -X POST https://cortexprime.example.com/api/v1/admin/connectors \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "notion",
    "name": "Notion Workspace",
    "config": {
      "integration_token": "ntn_xxxxxxxxxxxxxx",
      "databases": ["8a9b7c6d5e4f3a2b1c0d9e8f"],
      "sync_interval_minutes": 30
    }
  }'
```

### 7.8 Azure DevOps Connector

```bash
# Generate a PAT at https://dev.azure.com/{org}/_usersSettings/tokens

curl -X POST https://cortexprime.example.com/api/v1/admin/connectors \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "azure_devops",
    "name": "Azure DevOps",
    "config": {
      "organization": "acme-corp",
      "personal_access_token": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "projects": ["Platform", "Mobile"],
      "repositories": ["cortexprime-api", "cortexprime-frontend"],
      "webhook_url": "https://cortexprime.example.com/api/v1/connectors/azure-devops/webhook"
    }
  }'
```

---

## 8. Worker Administration

Workers are long-lived processes that execute agent actions: browser automation, voice processing, and desktop operations.

### 8.1 Worker Types

| Type      | Purpose                          | Resource Profile         |
|-----------|----------------------------------|--------------------------|
| Browser   | Web scraping, form filling, E2E  | 2 CPU, 4 GB RAM per pod  |
| Voice     | STT/TTS, call handling           | 4 CPU, 8 GB RAM + GPU    |
| Desktop   | RDP/VNC automation, UI testing   | 2 CPU, 4 GB RAM          |

### 8.2 Managing Workers

```bash
# List all workers
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/workers

# Get worker details
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/workers/wkr_abc

# Drain a worker (finish current tasks, then stop)
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/workers/wkr_abc/drain

# Force stop a worker
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/workers/wkr_abc/stop

# Restart a worker
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/workers/wkr_abc/restart
```

### 8.3 Scaling Workers

**Horizontal scaling (Docker Compose):**

```yaml
# docker-compose.override.yml
services:
  worker-browser:
    deploy:
      replicas: 10
  worker-voice:
    deploy:
      replicas: 3
  worker-desktop:
    deploy:
      replicas: 5
```

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

**Horizontal scaling (Kubernetes):**

```bash
# Scale browser workers
kubectl -n cortexprime scale deployment worker-browser --replicas=10

# Scale voice workers
kubectl -n cortexprime scale deployment worker-voice --replicas=3

# Autoscale based on queue depth
kubectl -n cortexprime autoscale deployment worker-browser \
  --min=3 --max=20 --cpu-percent=75
```

**Vertical scaling (resource limits):**

```bash
# Update resource requests/limits for a worker deployment
kubectl -n cortexprime set resources deployment/worker-voice \
  --requests=cpu=4,memory=8Gi \
  --limits=cpu=8,memory=16Gi
```

### 8.4 Health Checks

Workers expose a health endpoint at `/health` on port `9100`:

```bash
# Manual health check
curl http://worker-browser:9100/health

# Expected response:
# {
#   "status": "healthy",
#   "uptime_seconds": 3600,
#   "active_tasks": 2,
#   "queued_tasks": 0,
#   "last_heartbeat": "2026-07-04T10:00:00Z",
#   "memory_usage_mb": 512,
#   "cpu_usage_percent": 23.5
# }
```

**Configure health check (Kubernetes):**

```yaml
# deployment-worker-browser.yaml
livenessProbe:
  httpGet:
    path: /health
    port: 9100
  initialDelaySeconds: 30
  periodSeconds: 15
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /health
    port: 9100
  initialDelaySeconds: 10
  periodSeconds: 10
  failureThreshold: 2
```

---

## 9. Secrets Management

CortexPrime supports pluggable secrets backends. Choose one based on your infrastructure.

### 9.1 HashiCorp Vault

```bash
# Configure Vault as the secrets backend
curl -X PUT https://cortexprime.example.com/api/v1/admin/settings/secrets \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "backend": "vault",
    "config": {
      "address": "https://vault.example.com:8200",
      "token": "hvs.xxxxxxxxxxxx",
      "mount_path": "cortexprime",
      "tls_skip_verify": false
    }
  }'

# Test connectivity
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/settings/secrets/test
```

### 9.2 Azure Key Vault

```bash
curl -X PUT https://cortexprime.example.com/api/v1/admin/settings/secrets \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "backend": "azure_key_vault",
    "config": {
      "vault_url": "https://cortexprime-kv.vault.azure.net",
      "tenant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "client_secret": "xxxx~xxxx~xxxx",
      "managed_identity": false
    }
  }'
```

### 9.3 AWS Secrets Manager

```bash
curl -X PUT https://cortexprime.example.com/api/v1/admin/settings/secrets \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "backend": "aws_secrets_manager",
    "config": {
      "region": "us-east-1",
      "access_key_id": "AKIAxxxxxxxxxxxx",
      "secret_access_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "use_instance_profile": false,
      "kms_key_id": "arn:aws:kms:us-east-1:123456789012:key/xxxx"
    }
  }'
```

### 9.4 Rotation Policies

Configure automatic secret rotation:

```bash
curl -X POST https://cortexprime.example.com/api/v1/admin/settings/secrets/rotation-policies \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "llm-api-keys",
    "secret_selector": "llm.*",
    "rotation_interval_days": 30,
    "grace_period_hours": 24,
    "notification_channels": ["slack", "email"]
  }'
```

List and trigger manual rotation:

```bash
# List all rotation policies
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/settings/secrets/rotation-policies

# Trigger immediate rotation for a specific secret
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/settings/secrets/rotate \
  -H "Content-Type: application/json" \
  -d '{"secret_id": "sec_llm_openai_prod"}'
```

---

## 10. Monitoring & Observability

### 10.1 Prometheus Metrics

CortexPrime exposes metrics at `/metrics` on port `9090` for all services.

**Key metrics:**

```
# API Gateway
cortexprime_http_requests_total{method,path,status}     # Request count
cortexprime_http_request_duration_ms{method,path}        # Latency histogram
cortexprime_active_sessions                              # Concurrent sessions

# Agent Runtime
cortexprime_agent_invocations_total{agent_id,status}     # Agent runs
cortexprime_agent_invocation_duration_ms{agent_id}       # Execution time
cortexprime_agent_llm_token_usage{model}                 # Token consumption
cortexprime_agent_tool_calls_total{agent_id,tool}        # Tool usage

# Workers
cortexprime_worker_tasks_total{worker_type,status}       # Task throughput
cortexprime_worker_queue_depth{worker_type}              # Pending tasks
cortexprime_worker_memory_bytes{worker_id}               # Memory per worker

# System
cortexprime_queue_depth{queue}                           # NATS queue depth
cortexprime_db_connection_pool_usage                     # DB pool %
cortexprime_license_seats_used                           # Licensed seats
```

**Prometheus scrape config:**

```yaml
scrape_configs:
  - job_name: 'cortexprime'
    metrics_path: /metrics
    static_configs:
      - targets:
          - 'api-gateway:9090'
          - 'agent-runtime:9090'
          - 'connector:9090'
          - 'worker-browser:9090'
          - 'worker-voice:9090'
          - 'worker-desktop:9090'
          - 'auth-service:9090'
          - 'audit-service:9090'
```

### 10.2 Grafana Dashboards

Import the official CortexPrime dashboard:

1. In Grafana, go to **Dashboards > Import**
2. Enter the dashboard ID: `cortexprime-official` (Grafana Cloud)
3. Or download the JSON from `https://releases.cortexprime.io/v1.0.0/grafana/dashboard.json`
4. Select the Prometheus data source

**Available panels:**

- **API Health** — Request rate, error rate, p95 latency
- **Agent Activity** — Invocations, success rate, average duration
- **LLM Usage** — Token consumption by model, cost estimation
- **Worker Pool** — Queue depth, task throughput, worker count
- **Database** — Connection pool, query latency, replication lag
- **License** — Seat utilization, expiry countdown

### 10.3 Sentry (Error Tracking)

```bash
# Configure Sentry DSN
export SENTRY_DSN=https://xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx@sentry.io/1234567
export SENTRY_ENVIRONMENT=production
export SENTRY_TRACES_SAMPLE_RATE=0.2  # 20% of transactions
export SENTRY_PROFILES_SAMPLE_RATE=0.1
```

```bash
# Verify Sentry is working
curl -X POST https://cortexprime.example.com/api/v1/admin/diagnostics/test-sentry \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### 10.4 Structured Logging

Logs are output as JSON by default. Configure the log level and destination:

```bash
# Environment variables
LOG_LEVEL=info                  # debug | info | warn | error
LOG_FORMAT=json                 # json | text
LOG_OUTPUT=stdout               # stdout | file
LOG_FILE=/var/log/cortexprime.log
LOG_MAX_SIZE_MB=100
LOG_MAX_FILES=10
LOG_SENSITIVE_REDACTION=true    # Auto-redact tokens, passwords
```

**Example log line:**

```json
{
  "timestamp": "2026-07-04T10:00:00.123Z",
  "level": "info",
  "service": "agent-runtime",
  "trace_id": "tr_abcdef123456",
  "message": "Agent invocation completed",
  "agent_id": "ag_customer_support_v2",
  "duration_ms": 3421,
  "llm_tokens": 1542,
  "status": "success"
}
```

### 10.5 Alerting

**Pre-configured alert rules** are available in the repository at `monitoring/alerts/prometheus-rules.yaml`:

```yaml
groups:
  - name: cortexprime_critical
    rules:
      - alert: CortexPrimeServiceDown
        expr: up{job=~"cortexprime.*"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.job }} is down"

      - alert: CortexPrimeHighErrorRate
        expr: rate(cortexprime_http_requests_total{status=~"5.."}[5m]) / rate(cortexprime_http_requests_total[5m]) > 0.05
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Error rate > 5% on {{ $labels.instance }}"

      - alert: CortexPrimeQueueBacklog
        expr: cortexprime_worker_queue_depth > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Worker queue depth > 100 on {{ $labels.worker_type }}"

      - alert: CortexPrimeLicenseExpiring
        expr: cortexprime_license_days_remaining < 30
        labels:
          severity: warning
        annotations:
          summary: "License expires in {{ $value }} days"
```

**Notification channels:**

Configure alerts in Grafana or Alertmanager:

```yaml
# alertmanager.yml
receivers:
  - name: 'ops-team'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/T00/B00/xxxx'
        channel: '#cortexprime-alerts'
        send_resolved: true
    pagerduty_configs:
      - routing_key: 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        severity: critical
    email_configs:
      - to: 'ops@example.com'
```

---

## 11. Backup & Recovery

### 11.1 PostgreSQL Backup

**Automated backup script:**

```bash
#!/bin/bash
# /usr/local/bin/backup-postgres.sh

BACKUP_DIR="/var/backups/cortexprime/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

# Dump all databases
docker compose exec -T postgres pg_dumpall \
  -U cortexprime \
  --clean \
  --if-exists \
  > "$BACKUP_DIR/full_backup_$TIMESTAMP.sql"

# Compress
gzip "$BACKUP_DIR/full_backup_$TIMESTAMP.sql"

# Remove backups older than retention period
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_DIR/full_backup_$TIMESTAMP.sql.gz"
```

**Schedule with cron (Linux):**

```bash
0 3 * * * /usr/local/bin/backup-postgres.sh
```

**Schedule with Task Scheduler (Windows):**

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-File C:\scripts\backup-postgres.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 3am
Register-ScheduledTask -TaskName "CortexPrime-PostgresBackup" -Action $action -Trigger $trigger
```

**Continuous archiving (WAL):**

```bash
# Enable WAL archiving in postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'cp %p /var/backups/cortexprime/postgres/wal/%f'
archive_timeout = 60
```

### 11.2 Redis Backup

```bash
# Manual RDB snapshot
docker compose exec redis redis-cli -a password SAVE
docker compose cp redis:/data/dump.rdb /var/backups/cortexprime/redis/

# Manual AOF rewrite
docker compose exec redis redis-cli -a password BGREWRITEAOF

# Automated RDB snapshot (every 6 hours)
docker compose exec redis redis-cli -a password \
  CONFIG SET save "21600 1 43200 10 86400 100"
```

### 11.3 Neo4j Backup

```bash
#!/bin/bash
# /usr/local/bin/backup-neo4j.sh

BACKUP_DIR="/var/backups/cortexprime/neo4j"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

docker compose exec neo4j \
  neo4j-admin database dump neo4j \
  --to-path=/backups/neo4j_dump_$TIMESTAMP

docker compose cp neo4j:/backups/neo4j_dump_$TIMESTAMP "$BACKUP_DIR/"

# For Neo4j cluster (K8s):
kubectl -n cortexprime exec deployment/neo4j -- \
  neo4j-admin database dump neo4j \
  --to-path=/backups/
```

### 11.4 Full Restoration

**PostgreSQL restore:**

```bash
# Stop all services except the database
docker compose stop api-gateway agent-runtime connector worker-browser worker-voice worker-desktop

# Drop and recreate the database
docker compose exec postgres psql -U cortexprime -c \
  "DROP DATABASE IF EXISTS cortexprime;"
docker compose exec postgres psql -U cortexprime -c \
  "CREATE DATABASE cortexprime;"

# Restore from compressed backup
gunzip -c /var/backups/cortexprime/postgres/full_backup_20260704_030000.sql.gz | \
  docker compose exec -T postgres psql -U cortexprime

# Restart services
docker compose up -d
```

**Redis restore:**

```bash
# Stop Redis
docker compose stop redis

# Replace the RDB file
docker compose cp /var/backups/cortexprime/redis/dump.rdb redis:/data/

# Start Redis
docker compose up -d redis
```

**Neo4j restore:**

```bash
# Stop Neo4j
docker compose stop neo4j

# Restore database
docker compose exec neo4j \
  neo4j-admin database load neo4j \
  --from-path=/backups/neo4j_dump_20260704_030000 \
  --overwrite-destination=true

# Start Neo4j
docker compose up -d neo4j
```

**Complete disaster recovery (all components):**

```bash
#!/bin/bash
# /usr/local/bin/disaster-recovery.sh

echo "=== CortexPrime Disaster Recovery ==="
echo "Step 1: Ensure all services are stopped"
docker compose down

echo "Step 2: Restore PostgreSQL from latest backup"
LATEST_PG=$(ls -t /var/backups/cortexprime/postgres/*.sql.gz | head -1)
gunzip -c "$LATEST_PG" | docker compose exec -T postgres psql -U cortexprime

echo "Step 3: Restore Redis"
cp /var/backups/cortexprime/redis/dump.rdb ./data/redis/dump.rdb

echo "Step 4: Restore Neo4j"
docker compose up -d neo4j
sleep 10
LATEST_NEO=$(ls -t /var/backups/cortexprime/neo4j/ | head -1)
docker compose exec neo4j neo4j-admin database load neo4j \
  --from-path=/backups/"$LATEST_NEO" \
  --overwrite-destination=true

echo "Step 5: Start all services"
docker compose up -d

echo "Step 6: Verify health"
sleep 30
docker compose ps
curl -f http://localhost:4000/health && echo "API is healthy"
```

---

## 12. Security Administration

### 12.1 JWT Configuration

```bash
# Generate JWT secrets
JWT_SECRET=$(openssl rand -hex 64)
JWT_REFRESH_SECRET=$(openssl rand -hex 64)

# Configure via environment variables
export JWT_ALGORITHM=RS256                # RS256 (asymmetric) or HS256 (symmetric)
export JWT_SECRET=$JWT_SECRET             # Used for HS256
export JWT_PRIVATE_KEY_PATH=/etc/cortexprime/jwt/private.pem  # RS256 only
export JWT_PUBLIC_KEY_PATH=/etc/cortexprime/jwt/public.pem    # RS256 only
export JWT_ACCESS_TOKEN_TTL=15m
export JWT_REFRESH_TOKEN_TTL=7d
export JWT_ISSUER=cortexprime
export JWT_AUDIENCE=cortexprime-api

# Generate RSA key pair (recommended for production)
openssl genpkey -algorithm RSA -out /etc/cortexprime/jwt/private.pem -pkeyopt rsa_keygen_bits:4096
openssl rsa -pubout -in /etc/cortexprime/jwt/private.pem -out /etc/cortexprime/jwt/public.pem
```

### 12.2 API Keys

**Generate and manage API keys:**

```bash
# Create a new API key
curl -X POST https://cortexprime.example.com/api/v1/admin/api-keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CI/CD Pipeline Key",
    "permissions": ["agents:deploy", "agents:read", "workers:view"],
    "expires_at": "2027-01-01T00:00:00Z",
    "rate_limit_per_minute": 100
  }'

# Response contains the key (shown once):
# { "key": "cp_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" }

# List all API keys
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/api-keys

# Revoke an API key
curl -X DELETE \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/api-keys/key_abc123
```

### 12.3 Rate Limiting

Configure rate limits globally or per-route:

```bash
# Global rate limits (environment variables)
RATE_LIMIT_GLOBAL=1000                   # Requests per minute (global)
RATE_LIMIT_PER_IP=100                    # Requests per minute per IP
RATE_LIMIT_PER_USER=200                  # Requests per minute per authenticated user
RATE_LIMIT_PER_API_KEY=500               # Requests per minute per API key
RATE_LIMIT_BURST_MULTIPLIER=2            # Allow bursts up to 2x

# Per-route rate limits (via admin API)
curl -X PUT https://cortexprime.example.com/api/v1/admin/settings/rate-limits \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "routes": {
      "/api/v1/agents/*/execute": { "limit": 10, "window_seconds": 60 },
      "/api/v1/auth/login": { "limit": 5, "window_seconds": 60 },
      "/api/v1/connectors/*/sync": { "limit": 2, "window_seconds": 300 }
    }
  }'
```

**Rethink rate limit state (after Redis flush):**

```bash
# Reset rate limit counters
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/settings/rate-limits/reset
```

### 12.4 Audit Logging

All security-relevant events are captured in the `audit_log` table. Events are immutable and cryptographically chained.

**Audit events captured:**

| Category     | Events                                                     |
|--------------|------------------------------------------------------------|
| Auth         | login, logout, login_failed, mfa_enrolled, mfa_reset       |
| Users        | created, updated, deleted, role_changed, suspended          |
| Secrets      | accessed, rotated, deleted                                  |
| Connectors   | created, updated, test, credential_changed                  |
| Workers      | started, stopped, drained, crashed                          |
| Agents       | deployed, rolled_back, permissions_changed                  |
| Admin        | settings_changed, license_updated, backup_performed         |

**Query audit logs:**

```bash
# List recent audit events
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://cortexprime.example.com/api/v1/admin/audit-log?limit=50&offset=0"

# Filter by user
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://cortexprime.example.com/api/v1/admin/audit-log?user_id=usr_abc123"

# Filter by action and date range
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://cortexprime.example.com/api/v1/admin/audit-log?action=login_failed&from=2026-07-01&to=2026-07-04"

# Export audit log as CSV
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://cortexprime.example.com/api/v1/admin/audit-log/export?format=csv" \
  -o audit-export.csv
```

**Verify audit log integrity:**

```bash
# This command checks the SHA-256 hash chain
docker compose exec api-gateway npx ts-node scripts/verify-audit-chain.ts
```

### 12.5 Emergency Stop

In the event of a security incident, use the emergency stop to immediately halt all agent activity and user access.

```bash
# Trigger emergency stop
curl -X POST https://cortexprime.example.com/api/v1/admin/emergency/stop \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Security incident — unauthorized access detected",
    "notify_users": true,
    "notify_channels": ["slack", "email", "pagerduty"]
  }'

# Check emergency status
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/emergency/status

# Resume normal operations
curl -X POST https://cortexprime.example.com/api/v1/admin/emergency/resume \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Incident resolved — resuming operations",
    "audit_incident_id": "inc_987654"
  }'
```

**Emergency stop effects:**

1. All active agent invocations are force-terminated
2. New agent invocations are rejected
3. All user sessions are invalidated (except super_admin)
4. All webhook endpoints return 503
5. Worker pools are drained
6. A high-priority alert is sent to configured notification channels

---

## 13. Licensing

### 13.1 License Management

CortexPrime requires a valid license file for production use.

```bash
# Apply a license file
curl -X PUT https://cortexprime.example.com/api/v1/admin/license \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "CP-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX",
    "license_file": "-----BEGIN LICENSE-----\n...\n-----END LICENSE-----"
  }'

# Or upload via CLI
curl -X PUT https://cortexprime.example.com/api/v1/admin/license \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@/path/to/cortexprime.lic"

# View current license details
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/license

# Example response:
# {
#   "status": "active",
#   "tier": "enterprise",
#   "max_seats": 500,
#   "seats_used": 342,
#   "max_agents": 100,
#   "agents_used": 47,
#   "issued_at": "2026-01-01T00:00:00Z",
#   "expires_at": "2027-01-01T00:00:00Z",
#   "days_remaining": 180,
#   "features": ["sso", "audit", "vault", "abac", "airgap"]
# }
```

### 13.2 Seat Tracking

```bash
# List all active seats
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/license/seats

# View seat utilization over time
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://cortexprime.example.com/api/v1/admin/license/seats/history?days=90"

# Release a seat (deactivate a user without deletion)
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/users/usr_abc123/deactivate
```

### 13.3 Usage Monitoring

```bash
# View usage dashboard data
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://cortexprime.example.com/api/v1/admin/license/usage?period=month"

# Get cost estimate (token-based billing estimation)
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://cortexprime.example.com/api/v1/admin/license/cost-estimate

# Set usage alert thresholds
curl -X PUT https://cortexprime.example.com/api/v1/admin/settings \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "license_alert_threshold_percent": 80,
    "license_alert_recipients": ["ops@example.com", "finance@example.com"]
  }'
```

---

## 14. Platform Updates

### 14.1 Upgrade Procedure

**Before upgrading:**

1. **Review release notes** at `https://docs.cortexprime.io/releases/v1.0.1`
2. **Check compatibility** — see Section 14.3
3. **Back up** all data stores (see Section 11)
4. **Notify users** of planned downtime
5. **Test in staging environment first**

**Docker Compose upgrade:**

```bash
# Step 1: Pull the latest images
docker compose pull

# Step 2: Run pre-upgrade checks
docker compose exec api-gateway npx ts-node scripts/pre-upgrade-check.ts

# Step 3: Apply database migrations
docker compose exec api-gateway npx prisma migrate deploy

# Step 4: Perform Neo4j schema migration (if applicable)
docker compose exec neo4j cypher-shell -u neo4j -p password \
  -f /migrations/neo4j/v1.0.1.cypher

# Step 5: Recreate containers with the new images
docker compose up -d --remove-orphans

# Step 6: Verify all services are healthy
docker compose ps
curl -f http://localhost:4000/health
```

**Kubernetes / Helm upgrade:**

```bash
# Update Helm repository
helm repo update

# See what will change
helm diff upgrade cortexprime cortexprime/cortexprime \
  --namespace cortexprime \
  --values custom-values.yaml

# Perform the upgrade
helm upgrade cortexprime cortexprime/cortexprime \
  --namespace cortexprime \
  --values custom-values.yaml \
  --atomic \
  --timeout 10m

# Roll out database migration Job
kubectl -n cortexprime apply -f https://releases.cortexprime.io/v1.0.1/k8s/job-migrate.yaml

# Verify
kubectl -n cortexprime rollout status deployment/api-gateway
kubectl -n cortexprime get pods
```

### 14.2 Rollback

**Docker Compose rollback:**

```bash
# Revert to previous version tag
export CORTEXPRIME_VERSION=v1.0.0

# Restore database from pre-upgrade backup
gunzip -c /var/backups/cortexprime/postgres/pre_upgrade_v1.0.1.sql.gz | \
  docker compose exec -T postgres psql -U cortexprime

# Restart with old images
docker compose up -d --remove-orphans
```

**Helm rollback:**

```bash
# List Helm revision history
helm history cortexprime -n cortexprime

# Rollback to the previous revision (e.g., revision 3)
helm rollback cortexprime 3 --namespace cortexprime --atomic --timeout 10m

# Wait for rollback to complete
kubectl -n cortexprime rollout status deployment/api-gateway
kubectl -n cortexprime rollout status deployment/agent-runtime

# Verify
kubectl -n cortexprime get pods
curl -f https://cortexprime.example.com/health
```

### 14.3 Compatibility Checking

```bash
# Check if current infrastructure meets upgrade requirements
docker compose exec api-gateway npx ts-node scripts/check-compatibility.ts \
  --target-version v1.0.1

# Output example:
# ✅ PostgreSQL 16.3 — compatible
# ✅ Redis 7.4.1 — compatible
# ✅ Neo4j 5.21.0 — compatible
# ✅ Docker Engine 26.1.0 — compatible
# ⚠️  Migrations required: 3 pending
# ⚠️  Deprecated API endpoints: 2 (connectors v1 alpha)
```

---

## 15. Troubleshooting

### 15.1 Common Issues

| Issue                              | Likely Cause                          | Resolution                                    |
|------------------------------------|---------------------------------------|-----------------------------------------------|
| Services fail to start             | Port conflicts or missing env vars    | Check `docker compose logs <service>`         |
| Database connection errors         | Wrong `DATABASE_URL` or DB not ready  | Verify PostgreSQL is running and reachable    |
| Neo4j connection errors            | Incorrect credentials                 | Reset password via `neo4j-admin`              |
| Redis connection errors            | Wrong `REDIS_URL` or auth             | `redis-cli -a password PING`                  |
| LLM provider returns 401           | Invalid or expired API key            | Rotate key and update in admin UI             |
| Connector returns 403              | OAuth token expired                   | Re-authorize the connector in admin UI        |
| Workers not picking up tasks       | Queue empty or worker pool exhausted  | Scale workers; check `worker_queue_depth`     |
| JWT token expired                  | Clock skew or TTL too short           | Sync NTP; increase `JWT_ACCESS_TOKEN_TTL`     |
| Rate limit exceeded                | Legitimate traffic spike              | Adjust `RATE_LIMIT_GLOBAL` or burst multiplier|
| License validation failed          | Clock skew or expired license         | Check system time; re-apply license           |
| MFA enrollment fails               | Clock skew prevents TOTP validation   | Sync NTP; regenerate secret                   |
| SSO redirect loop                  | Wrong ACS URL or certificate          | Verify IdP metadata matches                   |
| High memory usage                  | Worker leak or connection pool        | Restart workers; reduce `DATABASE_POOL_MAX`   |

### 15.2 Diagnostic Commands

```bash
# System health overview
docker compose exec api-gateway npx ts-node scripts/diagnostics.ts

# Check individual service health
curl -f http://localhost:4000/health
curl -f http://localhost:4001/health  # Auth service
curl -f http://localhost:4002/health  # Agent runtime

# Database diagnostics
docker compose exec postgres psql -U cortexprime -c "SELECT * FROM pg_stat_activity;"
docker compose exec postgres psql -U cortexprime -c "SELECT pg_size_pretty(pg_database_size('cortexprime'));"

# Redis diagnostics
docker compose exec redis redis-cli -a password INFO stats
docker compose exec redis redis-cli -a password CLIENT LIST
docker compose exec redis redis-cli -a password SLOWLOG GET 10

# Neo4j diagnostics
docker compose exec neo4j cypher-shell -u neo4j -p password \
  "CALL dbms.listConfig();"
docker compose exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (n) RETURN count(n) AS total_nodes;"

# Network connectivity test
docker compose exec api-gateway nc -zv postgres 5432
docker compose exec api-gateway nc -zv redis 6379
docker compose exec api-gateway nc -zv neo4j 7687

# SSL certificate validation
echo | openssl s_client -connect cortexprime.example.com:443 -servername cortexprime.example.com 2>/dev/null | openssl x509 -noout -dates
```

### 15.3 Log Collection

```bash
# Stream logs for a specific service
docker compose logs --tail=100 --follow api-gateway

# Search logs for errors
docker compose logs api-gateway | grep -i error

# Export all logs for support
docker compose logs --tail=10000 api-gateway > logs/api-gateway.log
docker compose logs --tail=10000 agent-runtime > logs/agent-runtime.log
docker compose logs --tail=10000 auth-service > logs/auth-service.log
docker compose logs --tail=50000 > logs/all-services.log

# K8s log collection
kubectl -n cortexprime logs --tail=100 deployment/api-gateway
kubectl -n cortexprime logs --tail=100 --selector=app=cortexprime --all-containers
kubectl -n cortexprime describe pod api-gateway-xxxxx
kubectl -n cortexprime get events --sort-by='.lastTimestamp'
```

### 15.4 Support Contacts

| Channel           | Contact                                      | Availability      |
|-------------------|----------------------------------------------|-------------------|
| Documentation     | https://docs.cortexprime.io                  | 24/7              |
| Community Forum   | https://community.cortexprime.io              | Business hours    |
| Support Portal    | https://support.cortexprime.io                | 24/7 (critical)   |
| Email             | support@cortexprime.io                       | Business hours    |
| Emergency Phone   | +1-800-CORTEX-PRIME                          | P1 incidents only |

**When contacting support, include:**

1. CortexPrime version (`curl https://cortexprime.example.com/api/v1/version`)
2. Deployment type (Docker Compose / K8s / Helm / Air-Gapped)
3. Log archive from Section 15.3
4. Steps to reproduce
5. Expected vs actual behavior

**Generate support bundle:**

```bash
# Creates a single archive with logs, config, and diagnostics
docker compose exec api-gateway npx ts-node scripts/support-bundle.ts \
  --output /tmp/cortexprime-support-v1.0.0.tar.gz

# Upload or share with support team
```

---

> **Document version:** 1.0.0  
> **Last updated:** July 4, 2026  
> **Product:** CortexPrime v1.0.0 GA  
> **© CortexPrime** — Confidential and proprietary.