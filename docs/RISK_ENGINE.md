# Engineering Risk Engine

## Overview

Phase 3 of the Engineering Decision Engine. Calculates a risk score (0-100) and level for every change. Combines category-based risk weights, file keyword analysis, and past failure patterns from the Learning Engine.

## Risk Score Formula

```
score = average(weight for each risk factor)
score = min(score, 100)
if past failure matches: score = min(score + 10, 100)
```

## Risk Levels

| Score Range | Level | Behavior |
|-------------|-------|----------|
| 0-24 | LOW | Standard automated pipeline |
| 25-49 | MEDIUM | Standard validation + targeted reviews |
| 50-69 | HIGH | Security + architecture review required |
| 70-100 | CRITICAL | Mandatory approvals + enhanced validation |

## Category Risk Weights

| Category | Weight | Reasoning |
|----------|--------|-----------|
| DATABASE | 90 | Schema changes affect data integrity |
| SECRETS | 85 | Credential exposure risk |
| AUTHENTICATION | 80 | Security boundary changes |
| RBAC | 75 | Authorization model changes |
| INFRASTRUCTURE | 70 | Infrastructure stability risk |
| API | 55 | Contract changes affect consumers |
| CONFIGURATION | 45 | Runtime behavior changes |
| CI_CD | 40 | Pipeline integrity changes |
| BACKEND | 35 | Application logic changes |
| DEPENDENCY | 30 | Supply chain risk |
| FRONTEND | 10 | Presentation layer only |
| TEST | 5 | Test-only changes |
| DOCUMENTATION | 2 | No production impact |

## Keyword Risk Weights

| Keyword | Weight | Risk Pattern |
|---------|--------|-------------|
| payment | 90 | Payment processing |
| billing | 85 | Billing system |
| pii | 90 | Personal identifiable information |
| password | 90 | Credential detected |
| secret | 85 | Sensitive value |
| migration | 85 | Database migration |
| oauth | 85 | OAuth flow |
| gdpr | 85 | GDPR compliance |
| token | 85 | Authentication token |
| encrypt | 80 | Encryption logic |
| schema | 80 | Database schema change |
| auth | 80 | Authentication logic |
| certificate | 75 | Certificate change |
| rbac | 75 | Role-based access control |
| firewall | 75 | Firewall rule |
| terraform | 70 | Infrastructure as Code |
| permission | 70 | Permission change |
| key | 70 | Cryptographic key |
| kubernetes | 65 | Kubernetes manifest |
| network | 65 | Network change |
| helm | 60 | Helm chart change |
| hotfix | 60 | Hotfix change |
| docker | 50 | Dockerfile change |
| rollback | 50 | Rollback change |
| config | 45 | Configuration change |
| deployment | 45 | Deployment config |

## Past Failure Integration

When a changed file matches a known failure pattern (from EnterpriseLearningService), the risk score increases by 10 points and the failure pattern is recorded in the assessment.

## RiskAssessment Structure

```
RiskAssessment
├── score: float (0-100)
├── level: RiskLevel (LOW | MEDIUM | HIGH | CRITICAL)
├── factors: List[Dict] — each factor has factor, weight, reason
├── past_failure_count: int
├── past_failure_patterns: List[str]
└── reasoning: str
```
