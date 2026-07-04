# CortexPrime Security Guide

**Version:** 1.0.0 GA  
**Last Updated:** 2026-07-04  
**Classification:** Confidential — Security Team  

---

## Table of Contents

1. [Security Overview](#1-security-overview)
2. [Authentication](#2-authentication)
3. [Authorization](#3-authorization)
4. [Identity Management](#4-identity-management)
5. [Secrets Management](#5-secrets-management)
6. [API Security](#6-api-security)
7. [Safety Guardrails](#7-safety-guardrails)
8. [Approval Workflows](#8-approval-workflows)
9. [Emergency Procedures](#9-emergency-procedures)
10. [Audit Logging](#10-audit-logging)
11. [Network Security](#11-network-security)
12. [Security Best Practices](#12-security-best-practices)
13. [Compliance](#13-compliance)

---

## 1. Security Overview

### Philosophy

CortexPrime employs a defense-in-depth security model with multiple overlapping layers of protection. No single security control is relied upon in isolation. Every layer — network, application, data, identity, and runtime — implements independent controls such that a failure in one layer is contained by subsequent layers.

### Security Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DEFENSE-IN-DEPTH                            │
│                                                                     │
│  Tier 1: Network Security                                           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  TLS 1.3 · Network Policies · WAF · DDoS Protection         │    │
│  │  Egress Filtering · Internal Service Mesh (mTLS)             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  Tier 2: Authentication & Authorization                             │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  JWT · OAuth2 · API Keys · RBAC · ABAC · MFA                │    │
│  │  Session Management · Token Rotation · Permission Inheritance │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  Tier 3: Application Security                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Input Validation · SQL Injection Prevention · CSP Headers   │    │
│  │  Rate Limiting · Request Sanitization · Safe Deserialization │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  Tier 4: Data Security                                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Encryption at Rest (AES-256) · Encryption in Transit (TLS) │    │
│  │  Secrets Management · Data Masking · Backup Encryption       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  Tier 5: Runtime Security                                           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Container Isolation · Worker Sandboxing · Seccomp Profiles  │    │
│  │  AppArmor/SELinux · Read-Only Root Filesystem · Drop Caps   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  Tier 6: Detection & Response                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Audit Logging · SIEM Integration · Alert Rules              │    │
│  │  Incident Response · Emergency Stop · Break-Glass Procedures │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Authentication

### JWT Tokens

#### Token Structure

```
Header:  { "alg": "RS256", "typ": "JWT", "kid": "2026-q1-key-v1" }
Payload: {
  "sub": "user_2xRf9K3mLp8",
  "iss": "https://auth.cortexprime.com",
  "aud": "https://api.cortexprime.com",
  "iat": 1749000000,
  "exp": 1749000900,
  "jti": "a1b2c3d4-...",
  "sid": "session_8yHk4MnQ",
  "roles": ["admin", "user"],
  "permissions": ["mission.create", "memory.read"],
  "org_id": "org_a1B2C3",
  "mfa_verified": true
}
Signature: Base64URL(RSASHA256(header + "." + payload, private_key))
```

#### Signing and Key Management

| Algorithm | Key Size | Rotation | Key Usage |
|---|---|---|---|
| RS256 (RSA PKCS#1 v1.5) | 4096 bits | Every 90 days | Signing + Verification |
| ES256 (ECDSA P-256) | 256 bits | Every 180 days | Alternate signing |

Keys are stored in the vault (see Section 5) and never embedded in code or configuration files. JWKS endpoint available at `https://auth.cortexprime.com/.well-known/jwks.json`.

#### Expiry and Refresh

| Token | Lifetime | Refresh | Storage |
|---|---|---|---|
| Access Token | 15 minutes | Via refresh token | Memory (in-memory variable) |
| Refresh Token | 7 days | Via rotate endpoint | HTTP-only secure cookie |
| Session Token | 24 hours | Via idle timeout reset | Redis (session store) |

Refresh token rotation: each refresh request invalidates the previous refresh token and issues a new pair. Refresh tokens are single-use.

#### Token Revocation

```python
class TokenRevocationService:
    async def revoke_all_user_tokens(self, user_id: UUID) -> None:
        # Add all session IDs to blocklist
        sessions = await self.session_store.get_user_sessions(user_id)
        async with redis_client.pipeline() as pipe:
            for session in sessions:
                pipe.setex(f"revoked:{session.jti}", 86400, "1")
            pipe.delete(f"user_sessions:{user_id}")
        await pipe.execute()

    async def is_revoked(self, jti: str) -> bool:
        return await redis_client.exists(f"revoked:{jti}")
```

### OAuth2 Providers

| Provider | Endpoint | Scopes Required | User Info Endpoint |
|---|---|---|---|
| Google | `accounts.google.com` | openid, email, profile | `https://www.googleapis.com/oauth2/v3/userinfo` |
| GitHub | `github.com/login/oauth` | user:email, read:user | `https://api.github.com/user` |
| Microsoft | `login.microsoftonline.com` | openid, email, User.Read | `https://graph.microsoft.com/v1.0/me` |
| Okta | Org-specific URL | openid, email, profile | Org-specific userinfo endpoint |

All providers use the Authorization Code flow with PKCE (S256). State parameter is mandatory with 10-minute expiry.

### API Key Authentication

API keys are used for machine-to-machine communication and CI/CD integration.

#### Key Format

```
cp_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
│  │     │
│  │     └── Random 40-character hex string (160 bits)
│  └── Environment prefix (live/test)
└── Static prefix
```

#### Key Storage

```python
class APIKeyManager:
    async def create_key(self, user_id: UUID, permissions: list[str]) -> APIKeyResponse:
        raw_key = f"cp_{env_prefix}_{secrets.token_hex(20)}"
        key_hash = hashlib.pbkdf2_hmac(
            "sha256", raw_key.encode(), settings.API_KEY_SALT, 100000
        ).hex()
        # Store hash only
        await db.execute(
            "INSERT INTO api_keys (key_hash, user_id, permissions) VALUES (:hash, :uid, :perms)",
            {"hash": key_hash, "uid": user_id, "perms": permissions},
        )
        return APIKeyResponse(key=raw_key)

    async def validate_key(self, raw_key: str) -> APIKey | None:
        key_hash = hashlib.pbkdf2_hmac(
            "sha256", raw_key.encode(), settings.API_KEY_SALT, 100000
        ).hex()
        return await db.fetch_one(
            "SELECT * FROM api_keys WHERE key_hash = :hash AND expires_at > NOW()",
            {"hash": key_hash},
        )
```

---

## 3. Authorization

### RBAC Model

#### Role Hierarchy

```
admin
├── workspace_admin
│   ├── developer
│   │   ├── operator
│   │   │   └── viewer
│   │   └── auditor
│   └── compliance_officer
└── super_admin (org-wide, no tenant restrictions)
```

#### Role Permissions Matrix

| Permission / Action | viewer | operator | developer | workspace_admin | admin | super_admin |
|---|---|---|---|---|---|---|
| mission.create | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| mission.read (own) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| mission.read (all) | — | — | ✓ | ✓ | ✓ | ✓ |
| mission.cancel | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| memory.read (own) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| memory.read (all) | — | — | — | ✓ | ✓ | ✓ |
| memory.write | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| knowledge.read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| knowledge.write | — | — | ✓ | ✓ | ✓ | ✓ |
| connector.configure | — | — | ✓ | ✓ | ✓ | ✓ |
| connector.execute | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| admin.users | — | — | — | ✓ | ✓ | ✓ |
| admin.audit | — | — | — | ✓ | ✓ | ✓ |
| admin.approvals | — | — | — | ✓ | ✓ | ✓ |
| admin.settings | — | — | — | — | ✓ | ✓ |
| api_key.create | — | — | ✓ | ✓ | ✓ | ✓ |
| system.config | — | — | — | — | — | ✓ |

#### RBAC Implementation

```python
class RBACValidator:
    async def check(
        self,
        user: User,
        action: str,
        resource_type: str,
    ) -> bool:
        # Check role hierarchy for effective permissions
        effective_roles = await self._get_effective_roles(user)
        for role in effective_roles:
            if await self._role_has_permission(role, action, resource_type):
                return True
        return False

    async def _get_effective_roles(self, user: User) -> list[str]:
        roles = set(user.roles)
        for role in list(roles):
            # Include inherited roles (upwards in hierarchy)
            parents = await self._get_parent_roles(role)
            roles.update(parents)
        return list(roles)
```

### ABAC Model

ABAC evaluates access based on attributes of the user, resource, action, and environment.

#### Attribute Categories

| Category | Example Attributes |
|---|---|
| **User Attributes** | department, clearance_level, location, employment_type, team_id |
| **Resource Attributes** | classification, owner, project_id, created_after, tags |
| **Action Attributes** | action_type, http_method, api_version |
| **Environment Attributes** | time_of_day, ip_range, device_type, network_zone |

#### Policy Evaluation

```python
class ABACEngine:
    def __init__(self):
        self.policies: list[ABACPolicy] = []

    async def evaluate(
        self,
        user: User,
        action: str,
        resource: Resource,
        context: ABACContext,
    ) -> bool:
        for policy in self.policies:
            if not self._match_action(policy, action):
                continue
            if not self._match_resource(policy, resource):
                continue
            result = await self._evaluate_conditions(policy, user, resource, context)
            if result is not None:
                return result
        return False  # Default deny

    async def _evaluate_conditions(
        self,
        policy: ABACPolicy,
        user: User,
        resource: Resource,
        context: ABACContext,
    ) -> bool | None:
        for condition in policy.conditions:
            lhs = self._resolve_attribute(condition.lhs, user, resource, context)
            rhs = self._resolve_attribute(condition.rhs, user, resource, context)
            if not self._apply_operator(condition.op, lhs, rhs):
                return None  # Skip this policy
        return policy.effect  # "allow" or "deny"
```

### Combining RBAC + ABAC

```python
class AuthorizationService:
    async def authorize(
        self,
        user: User,
        action: str,
        resource: Resource,
    ) -> AuthorizationResult:
        # Fast path: RBAC check first
        if await self.rbac.check(user, action, resource.type):
            return AuthorizationResult.allowed()

        # Slow path: ABAC evaluation
        context = ABACContext(
            time=datetime.utcnow(),
            ip_address=resource.request_ip,
            network_zone=resource.network_zone,
            device_type=resource.device_type,
        )
        if await self.abac.evaluate(user, action, resource, context):
            return AuthorizationResult.allowed()

        return AuthorizationResult.denied(reason="Insufficient permissions")
```

---

## 4. Identity Management

### User Model

```python
@dataclass
class User:
    id: UUID
    email: str
    display_name: str
    roles: list[str]
    groups: list[str]
    org_id: UUID
    department: str | None
    mfa_enabled: bool
    mfa_method: MFAMethod | None  # totp, sms, webauthn
    status: UserStatus            # active, suspended, deactivated
    created_at: datetime
    last_login: datetime | None
```

### Groups and Roles

| Group Type | Purpose | Example |
|---|---|---|
| **Organization** | Root tenant grouping | `org_acme_corp` |
| **Team** | Department-level grouping | `team_engineering` |
| **Project** | Project-scoped grouping | `project_cortex_integration` |

Role assignment precedence: User-level > Group-level > Organization-level. More specific assignments override less specific ones.

### Service Identities

Service identities are non-human accounts used for automated operations:

```python
@dataclass
class ServiceIdentity:
    id: UUID
    name: str                    # e.g., "ci-cd-pipeline"
    type: ServiceIdentityType    # system, automation, integration
    api_key_prefix: str
    permissions: list[str]
    allowed_ips: list[str]
    rate_limit_multiplier: float
    audit_level: AuditLevel
```

### Organization Hierarchy

```
Organization
├── Admin (org-wide)
│   ├── Workspace Admin
│   │   ├── Developer
│   │   ├── Operator
│   │   └── Viewer
│   └── Compliance Officer
├── Teams
│   ├── Engineering
│   │   ├── Backend (sub-team)
│   │   └── Frontend (sub-team)
│   ├── Data Science
│   └── DevOps
└── Projects
    ├── CortexPrime Core
    └── CortexPrime Enterprise
```

Data isolation: users can only access resources within their organization (tenant boundary). Cross-organization access requires explicit sharing via Organization Links.

---

## 5. Secrets Management

### Supported Vault Providers

| Provider | Integration | Authentication |
|---|---|---|
| HashiCorp Vault | KV v2 engine + transit engine | Kubernetes auth + AppRole |
| Azure Key Vault | Managed HSM + secrets | Managed Identity |
| AWS Secrets Manager | Standard secrets + rotation | IAM roles for service accounts |

### Vault Integration Pattern

```python
class SecretsManager:
    def __init__(self, provider: str):
        if provider == "vault":
            self.client = hvac.Client(url=settings.VAULT_URL, token=self._get_vault_token())
        elif provider == "azure":
            self.client = AzureKeyVaultClient(vault_url=settings.AZURE_VAULT_URL)
        elif provider == "aws":
            self.client = boto3.client("secretsmanager")

    @cached(ttl=300)  # 5-minute cache
    async def get_secret(self, path: str) -> str:
        secret = await self._fetch_secret(path)
        return secret

    async def rotate_secret(self, path: str) -> None:
        new_value = SecretsGenerator.generate()
        await self._store_secret(path, new_value)
        await self._notify_rotation(path)
```

### Secrets Scope

| Secret | Vault Path | Rotation Period |
|---|---|---|
| Database password | `secret/cortexprime/db/password` | 90 days |
| Redis password | `secret/cortexprime/redis/password` | 90 days |
| Neo4j password | `secret/cortexprime/neo4j/password` | 90 days |
| JWT signing key | `transit/cortexprime/jwt/signing-key` | 90 days |
| JWT refresh key | `transit/cortexprime/jwt/refresh-key` | 90 days |
| Encryption key (at rest) | `transit/cortexprime/encryption/data-key` | 180 days |
| LLM API keys | `secret/cortexprime/llm/{provider}` | 30 days (or on compromise) |
| Connector secrets | `secret/cortexprime/connectors/{type}/{instance}` | 90 days |
| SMTP credentials | `secret/cortexprime/smtp/credentials` | 90 days |

### Secret Validation

```python
class SecretValidator:
    RULES = {
        "password": r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*]).{16,64}$",
        "api_key": r"^[A-Za-z0-9_-]{32,128}$",
        "jwt_key": r"^[A-Fa-f0-9]{64,}$",
    }

    @staticmethod
    def validate(name: str, value: str) -> bool:
        if name.endswith("password"):
            return bool(re.match(SecretValidator.RULES["password"], value))
        return len(value) >= 16
```

---

## 6. API Security

### Rate Limiting

| Endpoint Category | Rate Limit | Burst | Algorithm |
|---|---|---|---|
| `/api/v1/auth/*` | 10 req/min per user | 20 | Token bucket |
| `/api/v1/missions/*` | 60 req/min per user | 100 | Token bucket |
| `/api/v1/memory/*` | 120 req/min per user | 200 | Token bucket |
| `/api/v1/knowledge/*` | 120 req/min per user | 200 | Token bucket |
| `/api/v1/connectors/*` | 30 req/min per user | 50 | Token bucket |
| `/api/v1/admin/*` | 20 req/min per admin | 30 | Token bucket |
| `/ws/v1` (WebSocket) | 1000 msg/min per connection | 2000 | Sliding window |

#### Rate Limit Headers

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 42
X-RateLimit-Reset: 1749001200
Retry-After: 5
```

### CORS Configuration

```python
cors_config = {
    "allow_origins": [
        "https://app.cortexprime.com",
        "https://*.cortexprime.com",
    ],
    "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    "allow_headers": [
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "X-API-Key",
        "X-CSRF-Token",
    ],
    "expose_headers": ["X-Request-ID", "X-RateLimit-*"],
    "allow_credentials": True,
    "max_age": 600,
}
```

### CSP Headers

```
Content-Security-Policy: default-src 'self';
  script-src 'self' 'strict-dynamic' 'nonce-{random}';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https://*.cortexprime.com;
  connect-src 'self' https://api.cortexprime.com wss://api.cortexprime.com;
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
```

### Request Validation

All API inputs are validated using Pydantic models with strict typing:

```python
class MissionCreateSchema(BaseModel):
    model_config = {"extra": "forbid"}

    objective: str = Field(..., min_length=1, max_length=5000)
    context: dict = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    priority: Priority = Field(default=Priority.NORMAL)
    ttl: int = Field(default=3600, ge=60, le=86400)
```

### Input Sanitization

```python
class InputSanitizer:
    DANGEROUS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"data:text/html",
    ]

    @staticmethod
    def sanitize(text: str) -> str:
        text = html.escape(text, quote=True)
        for pattern in InputSanitizer.DANGEROUS_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)
        return text
```

---

## 7. Safety Guardrails

### Content Filtering Patterns

| Filter Type | Description | Action |
|---|---|---|
| **PII Redaction** | Email, SSN, credit card, phone, address patterns | Mask or block |
| **Profanity Filter** | Pattern-matched offensive language | Block with user warning |
| **Prompt Injection** | SQL injection, prompt leak, jailbreak attempts | Block + alert |
| **Code Injection** | Executable code in unexpected contexts | Block |
| **URL Validation** | Malicious or phishing URL detection | Block + log |
| **Content Policy** | NSFW, hate speech, harassment detection | Block + escalate |

### URL Allow/Block Lists

```python
class URLFilter:
    def __init__(self):
        self.allowlist = {
            "*.github.com",
            "*.gitlab.com",
            "docs.python.org",
            "developer.mozilla.org",
            "stackoverflow.com",
            "*.wikipedia.org",
            "*.npmjs.com",
            "pypi.org",
            "crates.io",
            "registry.npmjs.org",
        }
        self.blocklist = {
            "*.malware.example.com",
            "*.phishing.example.net",
        }

    async def check_url(self, url: str) -> URLFilterResult:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Check blocklist first
        if self._matches_pattern(domain, self.blocklist):
            return URLFilterResult.BLOCKED

        # Check allowlist for external navigation
        if not self._matches_pattern(domain, self.allowlist):
            return URLFilterResult.REQUIRES_APPROVAL

        return URLFilterResult.ALLOWED
```

### Malicious Input Detection

```python
class MaliciousInputDetector:
    PATTERNS = [
        (r"system\(.*\)", "Command injection attempt"),
        (r"exec\(.*\)", "Code execution attempt"),
        (r"eval\(.*\)", "Code evaluation attempt"),
        (r"<!--.*-->.*<script", "HTML injection + XSS"),
        (r"DROP\s+TABLE", "SQL injection"),
        (r"process\.env", "Environment variable access"),
        (r"process\.mainModule", "Node.js module access"),
        (r"__import__\(", "Python import injection"),
        (r"os\.system", "OS command attempt"),
        (r"subprocess\.", "Subprocess invocation"),
        (r"fs\.(read|write|copy)", "Filesystem access"),
        (r"require\('child_process'\)", "Node child process"),
    ]

    async def scan(self, text: str, source: str) -> ScanResult:
        for pattern, description in self.PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return ScanResult(
                    blocked=True,
                    reason=description,
                    pattern=pattern,
                    severity="high",
                )
        return ScanResult(blocked=False)
```

### Guardrail Integration

```python
class SafetyGuardrail:
    async def check_request(
        self,
        request: Request,
        content_type: ContentType,
    ) -> SafetyResult:
        checks = []

        if content_type in (ContentType.USER_INPUT, ContentType.MISSION_CONTEXT):
            checks.append(self.detector.scan(request.text, "user_input"))
            checks.append(self.url_filter.check_urls_in_text(request.text))

        if content_type == ContentType.LLM_OUTPUT:
            checks.append(self.content_policy.check(request.text))
            checks.append(self.pii_redactor.scan(request.text))

        results = await asyncio.gather(*checks)
        blocked = any(r.blocked for r in results)

        if blocked:
            await self.alert_service.send(SafetyAlert(
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                blocked_items=[r for r in results if r.blocked],
                timestamp=datetime.utcnow(),
            ))

        return SafetyResult(
            allowed=not blocked,
            details=[r for r in results if r.blocked],
        )
```

---

## 8. Approval Workflows

### Approval Levels

| Level | Description | Required Approvers | Escalation Time | SLA |
|---|---|---|---|---|
| **LOW** | Non-sensitive config changes | 1 team lead | — | 1 hour |
| **MEDIUM** | User/role modifications | 1 workspace admin | 4 hours | 4 hours |
| **HIGH** | Connector configuration, API key creation | 1 admin + 1 compliance officer | 8 hours | 8 hours |
| **CRITICAL** | System config, emergency access, data export | 2 admins + 1 super admin | 2 hours | 2 hours |

### Multi-Level Approval Flow

```
Request Submitted
  → Level Assessment (auto-calculated from resource + action)
  → Route to Approver Group (based on level)
  → Approver 1 responds (approve/reject/escalate/delegate)
    → If approved:
      → Level LOW/MED: Execute immediately
      → Level HIGH: Route to Approver 2
        → Approver 2 responds
          → If approved: Execute
          → If rejected: Notify requestor
    → If rejected: Notify requestor with reason
    → If escalated: Route to next-level approver (auto-calculated)
    → If delegated: Route to specified delegate
  → Timeout expiration → Auto-escalate
```

### Escalation Rules

```python
class EscalationManager:
    ESCALATION_CHAIN = {
        "LOW": ["team_lead", "workspace_admin"],
        "MEDIUM": ["workspace_admin", "admin"],
        "HIGH": ["admin", "compliance_officer", "super_admin"],
        "CRITICAL": ["admin", "super_admin", "super_admin"],
    }

    async def escalate(self, approval: Approval) -> Approval:
        current_idx = self.ESCALATION_CHAIN[approval.level].index(approval.current_approver_role)
        if current_idx < len(self.ESCALATION_CHAIN[approval.level]) - 1:
            next_role = self.ESCALATION_CHAIN[approval.level][current_idx + 1]
            approval.current_approver_role = next_role
            approval.escalation_count += 1
            await self._notify_approver(approval, next_role)
            return approval
        else:
            approval.status = ApprovalStatus.ESCALATED_MAX
            await self._notify_super_admin(approval)
            return approval
```

### Break-Glass Emergency Access

```python
class BreakGlassService:
    async def request_emergency_access(
        self,
        user: User,
        resource: Resource,
        reason: str,
        duration_minutes: int = 30,
    ) -> BreakGlassResult:
        # Generate one-time emergency code
        code = secrets.token_urlsafe(32)

        # Notify all admins
        await self.notification_service.send_alert(
            recipients=await self.user_service.get_admins(),
            title=f"Emergency access requested by {user.email}",
            body=f"Resource: {resource.id}\nReason: {reason}\nCode: {code[:8]}...",
            severity="critical",
        )

        # Start countdown timer
        async def revoke_after_timeout():
            await asyncio.sleep(duration_minutes * 60)
            await self.revoke_access(user.id, resource.id)
            await self.audit_service.log(
                action="emergency_access_expired",
                user_id=user.id,
                resource_id=resource.id,
            )

        asyncio.create_task(revoke_after_timeout())

        return BreakGlassResult(
            granted=True,
            code=code,
            expires_at=datetime.utcnow() + timedelta(minutes=duration_minutes),
        )
```

---

## 9. Emergency Procedures

### Emergency Stop

An **Emergency Stop** immediately halts all active mission execution and prevents new missions from starting.

```python
class EmergencyStopService:
    async def activate(self, initiator: User, reason: str) -> None:
        # 1. Halt all active missions
        active_missions = await self.mission_service.get_active_missions()
        for mission in active_missions:
            await self.mission_service.emergency_stop(mission.id)

        # 2. Block new mission creation
        await self.config_service.set("missions.block_new", True)

        # 3. Disconnect worker pool
        await self.worker_pool.drain_all()

        # 4. Pause connector execution
        await self.connector_service.pause_all()

        # 5. Log and notify
        await self.audit_service.log(
            action="emergency_stop.activated",
            user_id=initiator.id,
            details={"reason": reason, "missions_halted": len(active_missions)},
        )
        await self.notification_service.broadcast_system_alert(
            title="Emergency Stop Activated",
            body=f"All missions halted by {initiator.email}. Reason: {reason}",
            severity="critical",
        )

    async def deactivate(self, initiator: User) -> None:
        await self.config_service.set("missions.block_new", False)
        await self.connector_service.resume_all()
        await self.audit_service.log(
            action="emergency_stop.deactivated",
            user_id=initiator.id,
        )
```

### Incident Response

```
Phase 1: Detection (0-15 min)
  ├── Alert triggers (automated or user-reported)
  ├── Triage via Operations Center dashboard
  └── Initial severity assessment

Phase 2: Containment (15-60 min)
  ├── Emergency Stop if mission-related
  ├── Rotate compromised credentials
  ├── Block affected IPs / users
  └── Snapshot affected resources for forensics

Phase 3: Eradication (1-4 hours)
  ├── Identify root cause
  ├── Remove malicious artifacts
  ├── Patch vulnerable component
  └── Verify no persistence mechanisms

Phase 4: Recovery (4-24 hours)
  ├── Restore from clean backup if needed
  ├── Gradual re-enablement of services
  ├── Verify normal operation
  └── Monitor for recurrence

Phase 5: Post-Mortem (24-72 hours)
  ├── Full incident write-up
  ├── Root cause analysis document
  ├── Timeline of events
  ├── Remediation items tracked
  └── Security controls review
```

### System Isolation

```yaml
# Kubernetes: Isolate compromised service
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: isolate-compromised-service
spec:
  podSelector:
    matchLabels: { app: compromised-service }
  policyTypes: [Ingress, Egress]
  ingress: []      # Block all inbound
  egress: []       # Block all outbound
---
# Block via firewall (if not K8s)
# iptables -A INPUT -s <pod_ip> -j DROP
# iptables -A OUTPUT -d <pod_ip> -j DROP
```

---

## 10. Audit Logging

### Event Types Captured

| Category | Events | Retention | Storage |
|---|---|---|---|
| **Authentication** | login, logout, login_failed, token_refresh, mfa_* | 1 year | PostgreSQL (audit_log table) |
| **User Management** | user_created, user_updated, user_deleted, role_changed | 5 years | PostgreSQL + cold storage |
| **Authorization** | permission_denied, rbac_check, abac_eval, policy_update | 1 year | PostgreSQL |
| **Mission Operations** | mission_created, mission_cancelled, mission_completed | 2 years | PostgreSQL + event store |
| **Data Access** | memory_read, memory_write, graph_query, data_export | 2 years | PostgreSQL |
| **Configuration** | config_changed, feature_flag_toggled, setting_update | 3 years | PostgreSQL |
| **Security Events** | emergency_stop, break_glass, suspicious_activity, rate_limit_breach | 5 years | PostgreSQL + SIEM |
| **Connector Activity** | connector_connected, connector_execution, connector_failure | 1 year | PostgreSQL |
| **Admin Actions** | approval_action, system_announcement, license_update | 5 years | PostgreSQL |

### Audit Record Schema

```python
@dataclass
class AuditEntry:
    id: UUID
    timestamp: datetime
    correlation_id: UUID
    user_id: UUID | None
    session_id: str | None
    ip_address: str
    user_agent: str
    action: str
    resource_type: str
    resource_id: str
    outcome: str          # allowed, denied, error
    severity: str         # info, warning, critical
    request_data: dict | None   # Redacted sensitive fields
    response_data: dict | None  # Redacted sensitive fields
    metadata: dict        # Additional context
```

### Storage Strategy

```
Hot Storage (PostgreSQL, 30 days)
  ├── Supported indexes on: timestamp, user_id, action, resource_id
  ├── Partitioned by month
  └── Accessible via API for real-time queries

Warm Storage (PostgreSQL + TimescaleDB, 90 days)
  ├── Continuous aggregate tables
  └── Retention policy: automatic compression after 7 days

Cold Storage (S3/GCS, up to 5 years)
  ├── Daily exports in Parquet format
  ├── Encrypted at rest (AES-256)
  └── Accessible via Admin Console (requires super_admin)
```

### Querying Audit Trails

```python
class AuditQueryService:
    async def search(
        self,
        filters: AuditFilters,
        pagination: Pagination,
        user: User,
    ) -> PaginatedResult[AuditEntry]:
        # Verify user has audit read permission
        await self.auth_service.authorize(user, "admin.audit", Resource(type="audit_log"))

        query = "SELECT * FROM audit_log WHERE 1=1"
        params = {}

        if filters.user_id:
            query += " AND user_id = :user_id"
            params["user_id"] = filters.user_id

        if filters.action:
            query += " AND action LIKE :action"
            params["action"] = f"{filters.action}%"

        if filters.date_from:
            query += " AND timestamp >= :date_from"
            params["date_from"] = filters.date_from

        if filters.date_to:
            query += " AND timestamp <= :date_to"
            params["date_to"] = filters.date_to

        if filters.severity:
            query += " AND severity = :severity"
            params["severity"] = filters.severity

        query += " ORDER BY timestamp DESC"
        return await self._paginate(query, params, pagination)
```

---

## 11. Network Security

### TLS Termination

All external-facing endpoints terminate TLS at the ingress/gateway layer.

| Endpoint | Protocol | Certificate | HSTS |
|---|---|---|---|
| `https://app.cortexprime.com` | TLS 1.3 only | Public CA (Let's Encrypt) | max-age=31536000; includeSubDomains |
| `https://api.cortexprime.com` | TLS 1.3 only | Public CA (Let's Encrypt) | max-age=31536000 |
| `wss://api.cortexprime.com` | TLS 1.3 only | Public CA (Let's Encrypt) | — |

### Internal Service Communication

```
Service A ──mTLS──→ Service B
  │                   │
  ├─ Certificate:     ├─ Certificate:
  │   CN=api          │   CN=postgres
  │   Issuer: Istio   │   Issuer: Istio
  │   SPIFFE ID:      │   SPIFFE ID:
  │   spiffe://cp/ns/ │   spiffe://cp/ns/
  │   default/sa/api  │   default/sa/postgres
```

All inter-service communication uses mutual TLS (mTLS) via the service mesh. Each service identity has a SPIFFE-compliant certificate with 24-hour validity.

### Network Policies

```yaml
# Default deny-all ingress/egress
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
---
# Allow API server to access database
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-to-db
spec:
  podSelector:
    matchLabels: { app: api }
  egress:
    - to:
        - podSelector: { matchLabels: { app: postgres } }
      ports:
        - protocol: TCP
          port: 5432
    - to:
        - podSelector: { matchLabels: { app: redis } }
      ports:
        - protocol: TCP
          port: 6379
    - to:
        - podSelector: { matchLabels: { app: neo4j } }
      ports:
        - protocol: TCP
          port: 7687
```

### Port Exposure

| Component | Internal Port | External Port | Protocol |
|---|---|---|---|
| API Server | 8000 | 443 (via ingress) | HTTPS |
| WebSocket Server | 8001 | 443 (via ingress) | WSS |
| Web UI | 3000 | 443 (via ingress) | HTTPS |
| PostgreSQL | 5432 | — | TCP (internal only) |
| Redis | 6379 | — | TCP (internal only) |
| Neo4j | 7687 | — | Bolt (internal only) |
| Vault | 8200 | — | HTTPS (internal only) |
| Metrics (Prometheus) | 9090 | — | HTTP (internal only) |
| Worker Browser | 9222 | — | DevTools (loopback) |

---

## 12. Security Best Practices

### Operational Best Practices

1. **Enable MFA for all user accounts** — Require TOTP or WebAuthn for all human users. Service accounts must use API keys instead.

2. **Rotate secrets on a schedule** — Database passwords every 90 days, JWT signing keys every 90 days, encryption keys every 180 days.

3. **Use short-lived tokens** — Access tokens expire in 15 minutes. Refresh tokens use rotation on each use.

4. **Implement least privilege** — Start with `viewer` role for all users. Grant elevated permissions only as needed.

5. **Audit all admin actions** — Every configuration change, role assignment, and permission grant must be logged.

6. **Run workers in sandboxed environments** — Browser workers use isolated Chromium instances. Code execution workers use Firecracker microVMs.

7. **Set resource quotas** — Per-user rate limits, per-organization mission limits, per-connector throughput caps.

8. **Use network policies** — Default-deny for all inter-service traffic. Explicitly allow necessary connections only.

9. **Enable structured logging** — All services emit JSON-formatted logs with correlation IDs for tracing.

10. **Monitor for anomalies** — Set up alerts for unusual login patterns, API usage spikes, and permission escalation attempts.

### Development Best Practices

11. **Scan dependencies for vulnerabilities** — Run `npm audit` (frontend) and `pip audit`/`safety` (backend) in CI/CD pipelines.

12. **Use static analysis** — Run ESLint with security plugins, Bandit (Python), and Trivy (containers) on every commit.

13. **Don't hardcode secrets** — Never commit secrets to version control. Use vault injection or environment variables from secrets manager.

14. **Validate all inputs** — Use Pydantic schemas with strict mode for API inputs. Reject unexpected fields.

15. **Sanitize all outputs** — Escape HTML, encode URLs, and avoid exposing internal error details to clients.

16. **Use parameterized queries** — Never concatenate user input into SQL queries. Use SQLAlchemy ORM or raw parameterized queries.

17. **Run containers as non-root** — Use distroless base images and run applications with non-root UIDs (e.g., UID 1001).

18. **Enable read-only filesystems** — Set `readOnlyRootFilesystem: true` in container security contexts.

19. **Drop unnecessary capabilities** — Remove all Linux capabilities except those required (`NET_BIND_SERVICE` for web servers).

20. **Regular penetration testing** — Conduct quarterly external penetration tests and annual red team exercises.

### Configuration Hardening

```yaml
# Kubernetes Pod Security Context
securityContext:
  runAsNonRoot: true
  runAsUser: 1001
  runAsGroup: 1001
  fsGroup: 1001
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
    add: ["NET_BIND_SERVICE"]

# Dockerfile best practices
FROM python:3.12-slim AS base
RUN addgroup --system --gid 1001 cortexprime && \
    adduser --system --uid 1001 cortexprime
USER cortexprime
WORKDIR /app
COPY --chown=cortexprime:cortexprime . .
```

---

## 13. Compliance

### SOC 2

CortexPrime is designed to support SOC 2 Type II certification. Key controls:

| Trust Service Criteria | Implementation |
|---|---|
| **Security** | Access controls (RBAC/ABAC), encryption at rest and in transit, network segmentation, intrusion detection |
| **Availability** | Multi-zone deployment, auto-scaling, health checks, circuit breakers, backup/restore procedures |
| **Processing Integrity** | Input validation, idempotency keys, transaction logging, audit trails |
| **Confidentiality** | Data classification, encryption, access logging, data masking |
| **Privacy** | PII redaction, data retention policies, user consent management, GDPR support |

### GDPR

| Requirement | Implementation |
|---|---|
| **Right to Access** | User data export endpoint (`GET /api/v1/users/me/export`) |
| **Right to Rectification** | Profile editing and data correction endpoints |
| **Right to Erasure** | Account deletion with configurable data purge (default: 30 days) |
| **Data Portability** | JSON export of all user data, including mission history and memory |
| **Data Processing Records** | Audit log for all data access and processing activities |
| **DPA Support** | Data Processing Agreement with sub-processor disclosure |
| **Breach Notification** | Automated notification to DPO + affected users within 72 hours |

### HIPAA (BAAs)

When configured for HIPAA compliance:

| Requirement | Implementation |
|---|---|
| **Encryption at rest** | AES-256 for all databases and backups |
| **Encryption in transit** | TLS 1.3 for all communications |
| **Access controls** | MFA required, session timeouts (15 min idle), automatic logout |
| **Audit controls** | All PHI access logged, immutable audit trail |
| **Integrity controls** | Checksums on data exports, versioned backups |
| **Person/entity authentication** | Unique user IDs, MFA, role-based access |
| **Emergency access** | Break-glass procedure with audit trail |
| **Data backup** | Automated daily snapshots, 7-day retention |

### Data Retention

| Data Type | Active Retention | Archive Retention | Deletion Policy |
|---|---|---|---|
| Mission executions | 90 days | 2 years | Soft-delete → hard delete after 30 days |
| User sessions | 7 days | — | Expire from Redis |
| Audit logs | 90 days | 5 years | Compressed Parquet in S3 |
| Memory entries | 180 days | 3 years | Soft-delete → consolidation |
| Connector logs | 30 days | 1 year | Compressed JSON in S3 |
| PII / PHI | Duration of relationship | 7 years (HIPAA) | Anonymization → hard delete |

### Data Isolation

Multi-tenant data isolation is enforced at three layers:

1. **Database level**: All tables include `org_id` column. Queries are scoped via middleware.
2. **Graph level**: Neo4j nodes include `org_id` property. Graph queries filter by organization.
3. **Application level**: API middleware injects organization context. Authorization checks verify tenant boundaries.

Cross-organization data access requires explicit Organization Link agreements with audit-logged approvals.

---

*This document is maintained by the CortexPrime Security Team. For questions or security concerns, contact security@cortexprime.com.*