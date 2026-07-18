# Decision Explainability - Phase 10

## Scenario 1: CSS Frontend Change

```json
{
  "explanation": {
    "why": "Change involves 2 category(ies): frontend, backend. Risk assessed at 22/100 (low). Deploying via no_deployment (95% confidence). Pipeline: Standard pipeline.",
    "factors": [
      {
        "factor": "frontend",
        "contribution": "10/100",
        "reason": "Frontend changes"
      },
      {
        "factor": "backend",
        "contribution": "35/100",
        "reason": "Backend code changes"
      }
    ],
    "evidence_chain": [
      {
        "step": "change_detection",
        "what": "1 files changed",
        "categories": [
          "frontend",
          "backend"
        ]
      },
      {
        "step": "impact_analysis",
        "what": "1 entities affected",
        "services": []
      },
      {
        "step": "risk_assessment",
        "what": "Risk score 22.5/100",
        "level": "low"
      },
      {
        "step": "execution_planning",
        "what": "Standard pipeline",
        "skipped_stages": []
      },
      {
        "step": "approval_determination",
        "what": "No approval needed",
        "approvers": []
      },
      {
        "step": "deployment_strategy",
        "what": "no_deployment",
        "confidence": 95
      }
    ],
    "confidence": 95,
    "alternatives": [
      "Reduced pipeline",
      "blue_green deployment"
    ]
  }
}
```

## Scenario 2: Payment Service Change

```json
{
  "explanation": {
    "why": "Change involves 1 category(ies): backend. Risk assessed at 72/100 (critical). Approval required from: engineering, security, architecture. Deploying via no_deployment (95% confidence). Pipeline: Critical risk \u2014 full pipeline with all safeguards.",
    "factors": [
      {
        "factor": "backend",
        "contribution": "35/100",
        "reason": "Backend code changes"
      },
      {
        "factor": "keyword:payment",
        "contribution": "90/100",
        "reason": "Payment processing"
      },
      {
        "factor": "keyword:payment",
        "contribution": "90/100",
        "reason": "Payment processing"
      }
    ],
    "evidence_chain": [
      {
        "step": "change_detection",
        "what": "2 files changed",
        "categories": [
          "backend"
        ]
      },
      {
        "step": "impact_analysis",
        "what": "2 entities affected",
        "services": []
      },
      {
        "step": "risk_assessment",
        "what": "Risk score 71.7/100",
        "level": "critical"
      },
      {
        "step": "execution_planning",
        "what": "Critical risk \u2014 full pipeline with all safeguards",
        "skipped_stages": []
      },
      {
        "step": "approval_determination",
        "what": "Approval required",
        "approvers": [
          "engineering",
          "security",
          "architecture"
        ]
      },
      {
        "step": "deployment_strategy",
        "what": "no_deployment",
        "confidence": 95
      }
    ],
    "confidence": 95,
    "alternatives": [
      "Reduced pipeline",
      "blue_green deployment"
    ]
  }
}
```

## Scenario 3: Terraform Infrastructure Change

```json
{
  "explanation": {
    "why": "Change involves 2 category(ies): infrastructure, infrastructure. Risk assessed at 70/100 (critical). Approval required from: engineering, security, architecture. Deploying via no_deployment (95% confidence). Pipeline: Critical risk \u2014 full pipeline with all safeguards.",
    "factors": [
      {
        "factor": "infrastructure",
        "contribution": "70/100",
        "reason": "Infrastructure as Code changes"
      },
      {
        "factor": "infrastructure",
        "contribution": "70/100",
        "reason": "Infrastructure as Code changes"
      },
      {
        "factor": "keyword:terraform",
        "contribution": "70/100",
        "reason": "Infrastructure as Code"
      },
      {
        "factor": "keyword:terraform",
        "contribution": "70/100",
        "reason": "Infrastructure as Code"
      }
    ],
    "evidence_chain": [
      {
        "step": "change_detection",
        "what": "2 files changed",
        "categories": [
          "infrastructure",
          "infrastructure"
        ]
      },
      {
        "step": "impact_analysis",
        "what": "2 entities affected",
        "services": []
      },
      {
        "step": "risk_assessment",
        "what": "Risk score 70.0/100",
        "level": "critical"
      },
      {
        "step": "execution_planning",
        "what": "Critical risk \u2014 full pipeline with all safeguards",
        "skipped_stages": []
      },
      {
        "step": "approval_determination",
        "what": "Approval required",
        "approvers": [
          "engineering",
          "security",
          "architecture"
        ]
      },
      {
        "step": "deployment_strategy",
        "what": "no_deployment",
        "confidence": 95
      }
    ],
    "confidence": 95,
    "alternatives": [
      "Reduced pipeline",
      "blue_green deployment"
    ]
  }
}
```

## Scenario 4: Helm Chart Change

```json
{
  "explanation": {
    "why": "Change involves 3 category(ies): infrastructure, configuration, infrastructure. Risk assessed at 61/100 (high). Approval required from: engineering, security. Deploying via no_deployment (95% confidence). Pipeline: High risk \u2014 full pipeline with all safeguards.",
    "factors": [
      {
        "factor": "infrastructure",
        "contribution": "70/100",
        "reason": "Infrastructure as Code changes"
      },
      {
        "factor": "configuration",
        "contribution": "45/100",
        "reason": "Configuration changes"
      },
      {
        "factor": "infrastructure",
        "contribution": "70/100",
        "reason": "Infrastructure as Code changes"
      },
      {
        "factor": "keyword:helm",
        "contribution": "60/100",
        "reason": "Helm chart change"
      },
      {
        "factor": "keyword:helm",
        "contribution": "60/100",
        "reason": "Helm chart change"
      }
    ],
    "evidence_chain": [
      {
        "step": "change_detection",
        "what": "2 files changed",
        "categories": [
          "infrastructure",
          "configuration",
          "infrastructure"
        ]
      },
      {
        "step": "impact_analysis",
        "what": "2 entities affected",
        "services": []
      },
      {
        "step": "risk_assessment",
        "what": "Risk score 61.0/100",
        "level": "high"
      },
      {
        "step": "execution_planning",
        "what": "High risk \u2014 full pipeline with all safeguards",
        "skipped_stages": []
      },
      {
        "step": "approval_determination",
        "what": "Approval required",
        "approvers": [
          "engineering",
          "security"
        ]
      },
      {
        "step": "deployment_strategy",
        "what": "no_deployment",
        "confidence": 95
      }
    ],
    "confidence": 95,
    "alternatives": [
      "Reduced pipeline",
      "blue_green deployment"
    ]
  }
}
```

## Scenario 5: Database Migration Change

```json
{
  "explanation": {
    "why": "Change involves 2 category(ies): database, backend. Risk assessed at 70/100 (critical). Approval required from: engineering, security, architecture. Deploying via no_deployment (95% confidence). Pipeline: Database migration \u2014 add backup validation.",
    "factors": [
      {
        "factor": "database_migration",
        "contribution": "90/100",
        "reason": "Database migration changes"
      },
      {
        "factor": "backend",
        "contribution": "35/100",
        "reason": "Backend code changes"
      },
      {
        "factor": "keyword:migration",
        "contribution": "85/100",
        "reason": "Database migration"
      }
    ],
    "evidence_chain": [
      {
        "step": "change_detection",
        "what": "2 files changed",
        "categories": [
          "database",
          "backend"
        ]
      },
      {
        "step": "impact_analysis",
        "what": "2 entities affected",
        "services": []
      },
      {
        "step": "risk_assessment",
        "what": "Risk score 70.0/100",
        "level": "critical"
      },
      {
        "step": "execution_planning",
        "what": "Database migration \u2014 add backup validation",
        "skipped_stages": []
      },
      {
        "step": "approval_determination",
        "what": "Approval required",
        "approvers": [
          "engineering",
          "security",
          "architecture"
        ]
      },
      {
        "step": "deployment_strategy",
        "what": "no_deployment",
        "confidence": 95
      }
    ],
    "confidence": 95,
    "alternatives": [
      "Reduced pipeline",
      "blue_green deployment"
    ]
  }
}
```

## Scenario 6: RBAC Change

```json
{
  "explanation": {
    "why": "Change involves 3 category(ies): backend, authentication, rbac. Risk assessed at 70/100 (critical). Approval required from: engineering, security, architecture. Deploying via no_deployment (95% confidence). Pipeline: Critical risk \u2014 full pipeline with all safeguards.",
    "factors": [
      {
        "factor": "backend",
        "contribution": "35/100",
        "reason": "Backend code changes"
      },
      {
        "factor": "authentication",
        "contribution": "80/100",
        "reason": "Authentication logic changes"
      },
      {
        "factor": "rbac",
        "contribution": "75/100",
        "reason": "RBAC/authorization changes"
      },
      {
        "factor": "keyword:auth",
        "contribution": "80/100",
        "reason": "Authentication logic"
      },
      {
        "factor": "keyword:auth",
        "contribution": "80/100",
        "reason": "Authentication logic"
      }
    ],
    "evidence_chain": [
      {
        "step": "change_detection",
        "what": "2 files changed",
        "categories": [
          "backend",
          "authentication",
          "rbac"
        ]
      },
      {
        "step": "impact_analysis",
        "what": "2 entities affected",
        "services": []
      },
      {
        "step": "risk_assessment",
        "what": "Risk score 70.0/100",
        "level": "critical"
      },
      {
        "step": "execution_planning",
        "what": "Critical risk \u2014 full pipeline with all safeguards",
        "skipped_stages": []
      },
      {
        "step": "approval_determination",
        "what": "Approval required",
        "approvers": [
          "engineering",
          "security",
          "architecture"
        ]
      },
      {
        "step": "deployment_strategy",
        "what": "no_deployment",
        "confidence": 95
      }
    ],
    "confidence": 95,
    "alternatives": [
      "Reduced pipeline",
      "blue_green deployment"
    ]
  }
}
```

## Scenario 7: Critical Hotfix (Payment + Secrets)

```json
{
  "explanation": {
    "why": "Change involves 3 category(ies): backend, authentication, secrets. Risk assessed at 75/100 (critical). Approval required from: engineering, security, architecture. Deploying via no_deployment (95% confidence). Pipeline: Critical risk \u2014 full pipeline with all safeguards.",
    "factors": [
      {
        "factor": "backend",
        "contribution": "35/100",
        "reason": "Backend code changes"
      },
      {
        "factor": "authentication",
        "contribution": "80/100",
        "reason": "Authentication logic changes"
      },
      {
        "factor": "secrets",
        "contribution": "85/100",
        "reason": "Secret/credential changes"
      },
      {
        "factor": "keyword:secret",
        "contribution": "85/100",
        "reason": "Secret or sensitive value"
      },
      {
        "factor": "keyword:payment",
        "contribution": "90/100",
        "reason": "Payment processing"
      }
    ],
    "evidence_chain": [
      {
        "step": "change_detection",
        "what": "2 files changed",
        "categories": [
          "backend",
          "authentication",
          "secrets"
        ]
      },
      {
        "step": "impact_analysis",
        "what": "2 entities affected",
        "services": []
      },
      {
        "step": "risk_assessment",
        "what": "Risk score 75.0/100",
        "level": "critical"
      },
      {
        "step": "execution_planning",
        "what": "Critical risk \u2014 full pipeline with all safeguards",
        "skipped_stages": []
      },
      {
        "step": "approval_determination",
        "what": "Approval required",
        "approvers": [
          "engineering",
          "security",
          "architecture"
        ]
      },
      {
        "step": "deployment_strategy",
        "what": "no_deployment",
        "confidence": 95
      }
    ],
    "confidence": 95,
    "alternatives": [
      "Reduced pipeline",
      "blue_green deployment"
    ]
  }
}
```
