# Risk Engine - Phase 3

## Scenario 1: CSS Frontend Change

```json
{
  "risk_assessment": {
    "score": 22.5,
    "level": "low",
    "factors": [
      {
        "factor": "frontend",
        "weight": 10,
        "reason": "Frontend changes"
      },
      {
        "factor": "backend",
        "weight": 35,
        "reason": "Backend code changes"
      }
    ],
    "past_failure_count": 0,
    "past_failure_patterns": [],
    "reasoning": "Low risk \u2014 standard automated pipeline"
  }
}
```

## Scenario 2: Payment Service Change

```json
{
  "risk_assessment": {
    "score": 71.7,
    "level": "critical",
    "factors": [
      {
        "factor": "backend",
        "weight": 35,
        "reason": "Backend code changes"
      },
      {
        "factor": "keyword:payment",
        "weight": 90,
        "reason": "Payment processing"
      },
      {
        "factor": "keyword:payment",
        "weight": 90,
        "reason": "Payment processing"
      }
    ],
    "past_failure_count": 0,
    "past_failure_patterns": [],
    "reasoning": "Critical risk \u2014 requires mandatory approvals and enhanced validation"
  }
}
```

## Scenario 3: Terraform Infrastructure Change

```json
{
  "risk_assessment": {
    "score": 70.0,
    "level": "critical",
    "factors": [
      {
        "factor": "infrastructure",
        "weight": 70,
        "reason": "Infrastructure as Code changes"
      },
      {
        "factor": "infrastructure",
        "weight": 70,
        "reason": "Infrastructure as Code changes"
      },
      {
        "factor": "keyword:terraform",
        "weight": 70,
        "reason": "Infrastructure as Code"
      },
      {
        "factor": "keyword:terraform",
        "weight": 70,
        "reason": "Infrastructure as Code"
      }
    ],
    "past_failure_count": 0,
    "past_failure_patterns": [],
    "reasoning": "Critical risk \u2014 requires mandatory approvals and enhanced validation"
  }
}
```

## Scenario 4: Helm Chart Change

```json
{
  "risk_assessment": {
    "score": 61.0,
    "level": "high",
    "factors": [
      {
        "factor": "infrastructure",
        "weight": 70,
        "reason": "Infrastructure as Code changes"
      },
      {
        "factor": "configuration",
        "weight": 45,
        "reason": "Configuration changes"
      },
      {
        "factor": "infrastructure",
        "weight": 70,
        "reason": "Infrastructure as Code changes"
      },
      {
        "factor": "keyword:helm",
        "weight": 60,
        "reason": "Helm chart change"
      },
      {
        "factor": "keyword:helm",
        "weight": 60,
        "reason": "Helm chart change"
      }
    ],
    "past_failure_count": 0,
    "past_failure_patterns": [],
    "reasoning": "High risk \u2014 requires security and architecture review"
  }
}
```

## Scenario 5: Database Migration Change

```json
{
  "risk_assessment": {
    "score": 70.0,
    "level": "critical",
    "factors": [
      {
        "factor": "database_migration",
        "weight": 90,
        "reason": "Database migration changes"
      },
      {
        "factor": "backend",
        "weight": 35,
        "reason": "Backend code changes"
      },
      {
        "factor": "keyword:migration",
        "weight": 85,
        "reason": "Database migration"
      }
    ],
    "past_failure_count": 0,
    "past_failure_patterns": [],
    "reasoning": "Critical risk \u2014 requires mandatory approvals and enhanced validation"
  }
}
```

## Scenario 6: RBAC Change

```json
{
  "risk_assessment": {
    "score": 70.0,
    "level": "critical",
    "factors": [
      {
        "factor": "backend",
        "weight": 35,
        "reason": "Backend code changes"
      },
      {
        "factor": "authentication",
        "weight": 80,
        "reason": "Authentication logic changes"
      },
      {
        "factor": "rbac",
        "weight": 75,
        "reason": "RBAC/authorization changes"
      },
      {
        "factor": "keyword:auth",
        "weight": 80,
        "reason": "Authentication logic"
      },
      {
        "factor": "keyword:auth",
        "weight": 80,
        "reason": "Authentication logic"
      }
    ],
    "past_failure_count": 0,
    "past_failure_patterns": [],
    "reasoning": "Critical risk \u2014 requires mandatory approvals and enhanced validation"
  }
}
```

## Scenario 7: Critical Hotfix (Payment + Secrets)

```json
{
  "risk_assessment": {
    "score": 75.0,
    "level": "critical",
    "factors": [
      {
        "factor": "backend",
        "weight": 35,
        "reason": "Backend code changes"
      },
      {
        "factor": "authentication",
        "weight": 80,
        "reason": "Authentication logic changes"
      },
      {
        "factor": "secrets",
        "weight": 85,
        "reason": "Secret/credential changes"
      },
      {
        "factor": "keyword:secret",
        "weight": 85,
        "reason": "Secret or sensitive value"
      },
      {
        "factor": "keyword:payment",
        "weight": 90,
        "reason": "Payment processing"
      }
    ],
    "past_failure_count": 0,
    "past_failure_patterns": [],
    "reasoning": "Critical risk \u2014 requires mandatory approvals and enhanced validation"
  }
}
```
