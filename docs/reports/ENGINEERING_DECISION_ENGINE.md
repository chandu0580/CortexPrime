# Engineering Decision Engine — Full Decision Reports

## Scenario 1: CSS Frontend Change

```json
{
  "report_id": "dr-0cfd72ac0e7a",
  "trigger_source": "github",
  "trigger_event": "push",
  "timestamp": "2026-07-12T12:21:09.223776+00:00",
  "repository": "org/repo",
  "branch": "main",
  "commit_sha": "abc123",
  "change_report": {
    "changed_files": [
      "frontend/styles/main.css"
    ],
    "changed_folders": [
      "frontend/styles"
    ],
    "changed_services": [],
    "changed_apis": [],
    "has_db_migrations": false,
    "has_infrastructure_changes": false,
    "has_frontend_changes": true,
    "has_backend_changes": true,
    "has_test_changes": false,
    "has_documentation_changes": false,
    "has_config_changes": false,
    "has_auth_changes": false,
    "has_rbac_changes": false,
    "has_secret_changes": false,
    "has_dependency_changes": false,
    "categories": [
      "frontend",
      "backend"
    ],
    "summary": "1 file(s) changed across 1 folder(s)",
    "raw_payload": {
      "head_commit": {
        "modified": [
          "frontend/styles/main.css"
        ]
      }
    }
  },
  "impact_graph": {
    "affected_modules": [
      "frontend"
    ],
    "affected_services": [],
    "affected_apis": [],
    "affected_packages": [],
    "affected_deployments": [],
    "affected_k8s_resources": [],
    "affected_pipelines": [],
    "affected_terraform_modules": [],
    "affected_helm_releases": [],
    "affected_dashboards": [],
    "affected_monitoring_rules": [],
    "affected_alert_rules": [],
    "affected_documentation": [],
    "total_affected_entities": 1
  },
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
  },
  "execution_plan": {
    "required_stages": [
      "trigger_pipeline",
      "repository",
      "workspace",
      "sandbox_execution",
      "code_intel_scan",
      "build",
      "qa",
      "security",
      "patch_generation",
      "engineering_review",
      "approval",
      "pr",
      "deployment",
      "gitops_sync",
      "k8s_verification",
      "observability",
      "root_cause_analysis",
      "learning",
      "recommendation",
      "replay_capture",
      "knowledge_graph",
      "complete"
    ],
    "skipped_stages": [],
    "requires_full_pipeline": true,
    "reasoning": "Standard pipeline"
  },
  "approval_requirements": {
    "approval_required": false,
    "required_approvers": [],
    "risk_justification": "Low risk \u2014 no approval required",
    "expected_impact": "Minimal impact expected"
  },
  "deployment_strategy": {
    "strategy": "no_deployment",
    "reasoning": "No services affected \u2014 skip deployment",
    "confidence": 95,
    "evidence": [
      "no_deployment (95% confidence)"
    ]
  },
  "decision_record": {
    "decision_id": "dr-0cfd72ac0e7a",
    "decision_type": "engineering_decision",
    "reason": "Low risk \u2014 standard automated pipeline",
    "evidence": [
      "Risk score: 22.5",
      "Risk level: low",
      "Changed files: 1",
      "Affected services: 0",
      "Execution plan: Standard pipeline",
      "Deployment strategy: no_deployment"
    ],
    "outcome": "Standard pipeline",
    "confidence": 95
  },
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
  },
  "executive_summary": {
    "repository": "org/repo",
    "change_summary": "1 file(s) changed \u2014 Frontend, Backend",
    "impact": "1 entities affected across 0 service(s), 0 API(s)",
    "risk_level": "low",
    "risk_score": 22.5,
    "affected_services": [],
    "required_tests": [
      "unit",
      "integration"
    ],
    "required_approvals": [],
    "deployment_strategy": "no_deployment",
    "rollback_strategy": "Automatic rollback via no_deployment rollback",
    "estimated_duration": "~5 min (22 stages, 0 skipped)",
    "confidence": 95,
    "recommendations": [
      "Standard deployment \u2014 no additional recommendations"
    ],
    "key_decision": "Standard pipeline"
  }
}
```

## Scenario 2: Payment Service Change

```json
{
  "report_id": "dr-d28e4f96ad1c",
  "trigger_source": "github",
  "trigger_event": "push",
  "timestamp": "2026-07-12T12:21:10.464310+00:00",
  "repository": "org/repo",
  "branch": "main",
  "commit_sha": "abc123",
  "change_report": {
    "changed_files": [
      "backend/services/payment/models.py",
      "backend/services/payment/processor.py"
    ],
    "changed_folders": [
      "backend/services/payment"
    ],
    "changed_services": [
      "payment"
    ],
    "changed_apis": [],
    "has_db_migrations": false,
    "has_infrastructure_changes": false,
    "has_frontend_changes": false,
    "has_backend_changes": true,
    "has_test_changes": false,
    "has_documentation_changes": false,
    "has_config_changes": false,
    "has_auth_changes": false,
    "has_rbac_changes": false,
    "has_secret_changes": false,
    "has_dependency_changes": false,
    "categories": [
      "backend"
    ],
    "summary": "2 file(s) changed across 1 folder(s)",
    "raw_payload": {
      "head_commit": {
        "modified": [
          "backend/services/payment/processor.py",
          "backend/services/payment/models.py"
        ]
      }
    }
  },
  "impact_graph": {
    "affected_modules": [
      "backend",
      "backend"
    ],
    "affected_services": [],
    "affected_apis": [],
    "affected_packages": [],
    "affected_deployments": [],
    "affected_k8s_resources": [],
    "affected_pipelines": [],
    "affected_terraform_modules": [],
    "affected_helm_releases": [],
    "affected_dashboards": [],
    "affected_monitoring_rules": [],
    "affected_alert_rules": [],
    "affected_documentation": [],
    "total_affected_entities": 2
  },
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
  },
  "execution_plan": {
    "required_stages": [
      "trigger_pipeline",
      "repository",
      "workspace",
      "sandbox_execution",
      "code_intel_scan",
      "build",
      "qa",
      "security",
      "patch_generation",
      "engineering_review",
      "approval",
      "pr",
      "deployment",
      "gitops_sync",
      "k8s_verification",
      "observability",
      "root_cause_analysis",
      "learning",
      "recommendation",
      "replay_capture",
      "knowledge_graph",
      "complete"
    ],
    "skipped_stages": [],
    "requires_full_pipeline": true,
    "reasoning": "Critical risk \u2014 full pipeline with all safeguards"
  },
  "approval_requirements": {
    "approval_required": true,
    "required_approvers": [
      "engineering",
      "security",
      "architecture"
    ],
    "risk_justification": "Critical risk \u2014 requires engineering, security, and architecture sign-off",
    "expected_impact": "Changes may affect system stability, security, or data integrity"
  },
  "deployment_strategy": {
    "strategy": "no_deployment",
    "reasoning": "No services affected \u2014 skip deployment",
    "confidence": 95,
    "evidence": [
      "no_deployment (95% confidence)",
      "hotfix (10% confidence)"
    ]
  },
  "decision_record": {
    "decision_id": "dr-d28e4f96ad1c",
    "decision_type": "engineering_decision",
    "reason": "Critical risk \u2014 requires mandatory approvals and enhanced validation",
    "evidence": [
      "Risk score: 71.7",
      "Risk level: critical",
      "Changed files: 2",
      "Affected services: 0",
      "Execution plan: Critical risk \u2014 full pipeline with all safeguards",
      "Deployment strategy: no_deployment"
    ],
    "outcome": "Critical risk \u2014 full pipeline with all safeguards",
    "confidence": 95
  },
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
  },
  "executive_summary": {
    "repository": "org/repo",
    "change_summary": "2 file(s) changed \u2014 Backend",
    "impact": "2 entities affected across 0 service(s), 0 API(s)",
    "risk_level": "critical",
    "risk_score": 71.7,
    "affected_services": [],
    "required_tests": [
      "unit",
      "integration"
    ],
    "required_approvals": [
      "engineering",
      "security",
      "architecture"
    ],
    "deployment_strategy": "no_deployment",
    "rollback_strategy": "Automatic rollback via no_deployment rollback",
    "estimated_duration": "~45 min (22 stages, 0 skipped)",
    "confidence": 95,
    "recommendations": [
      "Enable enhanced monitoring and alerting for this deployment",
      "Prepare rollback plan before starting deployment"
    ],
    "key_decision": "Critical risk \u2014 full pipeline with all safeguards"
  }
}
```

## Scenario 3: Terraform Infrastructure Change

```json
{
  "report_id": "dr-2910d0d33a0f",
  "trigger_source": "github",
  "trigger_event": "push",
  "timestamp": "2026-07-12T12:21:10.466189+00:00",
  "repository": "org/repo",
  "branch": "main",
  "commit_sha": "abc123",
  "change_report": {
    "changed_files": [
      "terraform/aws/main.tf",
      "terraform/aws/variables.tf"
    ],
    "changed_folders": [
      "terraform/aws"
    ],
    "changed_services": [],
    "changed_apis": [],
    "has_db_migrations": false,
    "has_infrastructure_changes": true,
    "has_frontend_changes": false,
    "has_backend_changes": false,
    "has_test_changes": false,
    "has_documentation_changes": false,
    "has_config_changes": false,
    "has_auth_changes": false,
    "has_rbac_changes": false,
    "has_secret_changes": false,
    "has_dependency_changes": false,
    "categories": [
      "infrastructure",
      "infrastructure"
    ],
    "summary": "2 file(s) changed across 1 folder(s)",
    "raw_payload": {
      "head_commit": {
        "modified": [
          "terraform/aws/main.tf",
          "terraform/aws/variables.tf"
        ]
      }
    }
  },
  "impact_graph": {
    "affected_modules": [
      "terraform",
      "terraform"
    ],
    "affected_services": [],
    "affected_apis": [],
    "affected_packages": [],
    "affected_deployments": [],
    "affected_k8s_resources": [],
    "affected_pipelines": [],
    "affected_terraform_modules": [
      "terraform/aws/main.tf",
      "terraform/aws/variables.tf"
    ],
    "affected_helm_releases": [],
    "affected_dashboards": [],
    "affected_monitoring_rules": [],
    "affected_alert_rules": [],
    "affected_documentation": [],
    "total_affected_entities": 2
  },
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
  },
  "execution_plan": {
    "required_stages": [
      "trigger_pipeline",
      "repository",
      "workspace",
      "sandbox_execution",
      "code_intel_scan",
      "build",
      "qa",
      "security",
      "patch_generation",
      "engineering_review",
      "approval",
      "pr",
      "deployment",
      "gitops_sync",
      "k8s_verification",
      "observability",
      "root_cause_analysis",
      "learning",
      "recommendation",
      "replay_capture",
      "knowledge_graph",
      "complete"
    ],
    "skipped_stages": [],
    "requires_full_pipeline": true,
    "reasoning": "Critical risk \u2014 full pipeline with all safeguards"
  },
  "approval_requirements": {
    "approval_required": true,
    "required_approvers": [
      "engineering",
      "security",
      "architecture"
    ],
    "risk_justification": "Critical risk \u2014 requires engineering, security, and architecture sign-off",
    "expected_impact": "Changes may affect system stability, security, or data integrity"
  },
  "deployment_strategy": {
    "strategy": "no_deployment",
    "reasoning": "No services affected \u2014 skip deployment",
    "confidence": 95,
    "evidence": [
      "no_deployment (95% confidence)",
      "hotfix (10% confidence)"
    ]
  },
  "decision_record": {
    "decision_id": "dr-2910d0d33a0f",
    "decision_type": "engineering_decision",
    "reason": "Critical risk \u2014 requires mandatory approvals and enhanced validation",
    "evidence": [
      "Risk score: 70.0",
      "Risk level: critical",
      "Changed files: 2",
      "Affected services: 0",
      "Execution plan: Critical risk \u2014 full pipeline with all safeguards",
      "Deployment strategy: no_deployment"
    ],
    "outcome": "Critical risk \u2014 full pipeline with all safeguards",
    "confidence": 95
  },
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
  },
  "executive_summary": {
    "repository": "org/repo",
    "change_summary": "2 file(s) changed \u2014 Infrastructure, Infrastructure",
    "impact": "2 entities affected across 0 service(s), 0 API(s)",
    "risk_level": "critical",
    "risk_score": 70.0,
    "affected_services": [],
    "required_tests": [],
    "required_approvals": [
      "engineering",
      "security",
      "architecture"
    ],
    "deployment_strategy": "no_deployment",
    "rollback_strategy": "Automatic rollback via no_deployment rollback",
    "estimated_duration": "~60 min (22 stages, 0 skipped)",
    "confidence": 95,
    "recommendations": [
      "Enable enhanced monitoring and alerting for this deployment",
      "Prepare rollback plan before starting deployment",
      "Run Terraform plan review before apply",
      "Validate infrastructure changes in a sandbox environment first"
    ],
    "key_decision": "Critical risk \u2014 full pipeline with all safeguards"
  }
}
```

## Scenario 4: Helm Chart Change

```json
{
  "report_id": "dr-7c54aa47ce04",
  "trigger_source": "github",
  "trigger_event": "push",
  "timestamp": "2026-07-12T12:21:10.467086+00:00",
  "repository": "org/repo",
  "branch": "main",
  "commit_sha": "abc123",
  "change_report": {
    "changed_files": [
      "helm/cortexprime/values.yaml",
      "helm/cortexprime/templates/deployment.yaml"
    ],
    "changed_folders": [
      "helm/cortexprime/templates",
      "helm/cortexprime"
    ],
    "changed_services": [],
    "changed_apis": [],
    "has_db_migrations": false,
    "has_infrastructure_changes": true,
    "has_frontend_changes": false,
    "has_backend_changes": false,
    "has_test_changes": false,
    "has_documentation_changes": false,
    "has_config_changes": true,
    "has_auth_changes": false,
    "has_rbac_changes": false,
    "has_secret_changes": false,
    "has_dependency_changes": false,
    "categories": [
      "infrastructure",
      "configuration",
      "infrastructure"
    ],
    "summary": "2 file(s) changed across 2 folder(s)",
    "raw_payload": {
      "head_commit": {
        "modified": [
          "helm/cortexprime/templates/deployment.yaml",
          "helm/cortexprime/values.yaml"
        ]
      }
    }
  },
  "impact_graph": {
    "affected_modules": [
      "helm",
      "helm"
    ],
    "affected_services": [],
    "affected_apis": [],
    "affected_packages": [],
    "affected_deployments": [],
    "affected_k8s_resources": [],
    "affected_pipelines": [],
    "affected_terraform_modules": [],
    "affected_helm_releases": [
      "helm/cortexprime/values.yaml",
      "helm/cortexprime/templates/deployment.yaml"
    ],
    "affected_dashboards": [],
    "affected_monitoring_rules": [],
    "affected_alert_rules": [],
    "affected_documentation": [],
    "total_affected_entities": 2
  },
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
  },
  "execution_plan": {
    "required_stages": [
      "trigger_pipeline",
      "repository",
      "workspace",
      "sandbox_execution",
      "code_intel_scan",
      "build",
      "qa",
      "security",
      "patch_generation",
      "engineering_review",
      "approval",
      "pr",
      "deployment",
      "gitops_sync",
      "k8s_verification",
      "observability",
      "root_cause_analysis",
      "learning",
      "recommendation",
      "replay_capture",
      "knowledge_graph",
      "complete"
    ],
    "skipped_stages": [],
    "requires_full_pipeline": true,
    "reasoning": "High risk \u2014 full pipeline with all safeguards"
  },
  "approval_requirements": {
    "approval_required": true,
    "required_approvers": [
      "engineering",
      "security"
    ],
    "risk_justification": "High risk \u2014 requires engineering and security review",
    "expected_impact": "Changes may affect security posture or service reliability"
  },
  "deployment_strategy": {
    "strategy": "no_deployment",
    "reasoning": "No services affected \u2014 skip deployment",
    "confidence": 95,
    "evidence": [
      "no_deployment (95% confidence)"
    ]
  },
  "decision_record": {
    "decision_id": "dr-7c54aa47ce04",
    "decision_type": "engineering_decision",
    "reason": "High risk \u2014 requires security and architecture review",
    "evidence": [
      "Risk score: 61.0",
      "Risk level: high",
      "Changed files: 2",
      "Affected services: 0",
      "Execution plan: High risk \u2014 full pipeline with all safeguards",
      "Deployment strategy: no_deployment"
    ],
    "outcome": "High risk \u2014 full pipeline with all safeguards",
    "confidence": 95
  },
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
  },
  "executive_summary": {
    "repository": "org/repo",
    "change_summary": "2 file(s) changed \u2014 Infrastructure, Configuration, Infrastructure",
    "impact": "2 entities affected across 0 service(s), 0 API(s)",
    "risk_level": "high",
    "risk_score": 61.0,
    "affected_services": [],
    "required_tests": [],
    "required_approvals": [
      "engineering",
      "security"
    ],
    "deployment_strategy": "no_deployment",
    "rollback_strategy": "Automatic rollback via no_deployment rollback",
    "estimated_duration": "~60 min (22 stages, 0 skipped)",
    "confidence": 95,
    "recommendations": [
      "Enable enhanced monitoring and alerting for this deployment",
      "Prepare rollback plan before starting deployment",
      "Run Terraform plan review before apply",
      "Validate infrastructure changes in a sandbox environment first"
    ],
    "key_decision": "High risk \u2014 full pipeline with all safeguards"
  }
}
```

## Scenario 5: Database Migration Change

```json
{
  "report_id": "dr-c726e20fbb9b",
  "trigger_source": "github",
  "trigger_event": "push",
  "timestamp": "2026-07-12T12:21:10.467939+00:00",
  "repository": "org/repo",
  "branch": "main",
  "commit_sha": "abc123",
  "change_report": {
    "changed_files": [
      "backend/migrations/2024_01_add_users_table.py",
      "backend/models/user.py"
    ],
    "changed_folders": [
      "backend/migrations",
      "backend/models"
    ],
    "changed_services": [],
    "changed_apis": [],
    "has_db_migrations": true,
    "has_infrastructure_changes": false,
    "has_frontend_changes": false,
    "has_backend_changes": true,
    "has_test_changes": false,
    "has_documentation_changes": false,
    "has_config_changes": false,
    "has_auth_changes": false,
    "has_rbac_changes": false,
    "has_secret_changes": false,
    "has_dependency_changes": false,
    "categories": [
      "database",
      "backend"
    ],
    "summary": "2 file(s) changed across 2 folder(s)",
    "raw_payload": {
      "head_commit": {
        "modified": [
          "backend/migrations/2024_01_add_users_table.py",
          "backend/models/user.py"
        ]
      }
    }
  },
  "impact_graph": {
    "affected_modules": [
      "backend",
      "backend"
    ],
    "affected_services": [],
    "affected_apis": [],
    "affected_packages": [],
    "affected_deployments": [
      "database-migration"
    ],
    "affected_k8s_resources": [],
    "affected_pipelines": [],
    "affected_terraform_modules": [],
    "affected_helm_releases": [],
    "affected_dashboards": [],
    "affected_monitoring_rules": [],
    "affected_alert_rules": [],
    "affected_documentation": [],
    "total_affected_entities": 2
  },
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
  },
  "execution_plan": {
    "required_stages": [
      "trigger_pipeline",
      "repository",
      "workspace",
      "sandbox_execution",
      "code_intel_scan",
      "build",
      "qa",
      "security",
      "patch_generation",
      "engineering_review",
      "approval",
      "pr",
      "deployment",
      "gitops_sync",
      "k8s_verification",
      "observability",
      "root_cause_analysis",
      "learning",
      "recommendation",
      "replay_capture",
      "knowledge_graph",
      "complete"
    ],
    "skipped_stages": [],
    "requires_full_pipeline": true,
    "reasoning": "Database migration \u2014 add backup validation"
  },
  "approval_requirements": {
    "approval_required": true,
    "required_approvers": [
      "engineering",
      "security",
      "architecture"
    ],
    "risk_justification": "Critical risk \u2014 requires engineering, security, and architecture sign-off",
    "expected_impact": "Changes may affect system stability, security, or data integrity"
  },
  "deployment_strategy": {
    "strategy": "no_deployment",
    "reasoning": "No services affected \u2014 skip deployment",
    "confidence": 95,
    "evidence": [
      "no_deployment (95% confidence)",
      "hotfix (10% confidence)"
    ]
  },
  "decision_record": {
    "decision_id": "dr-c726e20fbb9b",
    "decision_type": "engineering_decision",
    "reason": "Critical risk \u2014 requires mandatory approvals and enhanced validation",
    "evidence": [
      "Risk score: 70.0",
      "Risk level: critical",
      "Changed files: 2",
      "Affected services: 0",
      "Execution plan: Database migration \u2014 add backup validation",
      "Deployment strategy: no_deployment"
    ],
    "outcome": "Database migration \u2014 add backup validation",
    "confidence": 95
  },
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
  },
  "executive_summary": {
    "repository": "org/repo",
    "change_summary": "2 file(s) changed \u2014 Database, Backend",
    "impact": "2 entities affected across 0 service(s), 0 API(s)",
    "risk_level": "critical",
    "risk_score": 70.0,
    "affected_services": [],
    "required_tests": [
      "unit",
      "integration"
    ],
    "required_approvals": [
      "engineering",
      "security",
      "architecture"
    ],
    "deployment_strategy": "no_deployment",
    "rollback_strategy": "Automatic rollback via no_deployment rollback",
    "estimated_duration": "~55 min (22 stages, 0 skipped)",
    "confidence": 95,
    "recommendations": [
      "Ensure database backup before migration",
      "Run migration in a transaction with rollback capability",
      "Enable enhanced monitoring and alerting for this deployment",
      "Prepare rollback plan before starting deployment"
    ],
    "key_decision": "Database migration \u2014 add backup validation"
  }
}
```

## Scenario 6: RBAC Change

```json
{
  "report_id": "dr-aa8d6810e9f3",
  "trigger_source": "github",
  "trigger_event": "push",
  "timestamp": "2026-07-12T12:21:10.468930+00:00",
  "repository": "org/repo",
  "branch": "main",
  "commit_sha": "abc123",
  "change_report": {
    "changed_files": [
      "backend/auth/rbac.py",
      "backend/auth/permissions.py"
    ],
    "changed_folders": [
      "backend/auth"
    ],
    "changed_services": [],
    "changed_apis": [],
    "has_db_migrations": false,
    "has_infrastructure_changes": false,
    "has_frontend_changes": false,
    "has_backend_changes": true,
    "has_test_changes": false,
    "has_documentation_changes": false,
    "has_config_changes": false,
    "has_auth_changes": true,
    "has_rbac_changes": true,
    "has_secret_changes": false,
    "has_dependency_changes": false,
    "categories": [
      "backend",
      "authentication",
      "rbac"
    ],
    "summary": "2 file(s) changed across 1 folder(s)",
    "raw_payload": {
      "head_commit": {
        "modified": [
          "backend/auth/rbac.py",
          "backend/auth/permissions.py"
        ]
      }
    }
  },
  "impact_graph": {
    "affected_modules": [
      "backend",
      "backend"
    ],
    "affected_services": [],
    "affected_apis": [],
    "affected_packages": [],
    "affected_deployments": [
      "security-layer"
    ],
    "affected_k8s_resources": [],
    "affected_pipelines": [],
    "affected_terraform_modules": [],
    "affected_helm_releases": [],
    "affected_dashboards": [],
    "affected_monitoring_rules": [],
    "affected_alert_rules": [],
    "affected_documentation": [],
    "total_affected_entities": 2
  },
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
  },
  "execution_plan": {
    "required_stages": [
      "trigger_pipeline",
      "repository",
      "workspace",
      "sandbox_execution",
      "code_intel_scan",
      "build",
      "qa",
      "security",
      "patch_generation",
      "engineering_review",
      "approval",
      "pr",
      "deployment",
      "gitops_sync",
      "k8s_verification",
      "observability",
      "root_cause_analysis",
      "learning",
      "recommendation",
      "replay_capture",
      "knowledge_graph",
      "complete"
    ],
    "skipped_stages": [],
    "requires_full_pipeline": true,
    "reasoning": "Critical risk \u2014 full pipeline with all safeguards"
  },
  "approval_requirements": {
    "approval_required": true,
    "required_approvers": [
      "engineering",
      "security",
      "architecture"
    ],
    "risk_justification": "Critical risk \u2014 requires engineering, security, and architecture sign-off",
    "expected_impact": "Changes may affect system stability, security, or data integrity"
  },
  "deployment_strategy": {
    "strategy": "no_deployment",
    "reasoning": "No services affected \u2014 skip deployment",
    "confidence": 95,
    "evidence": [
      "no_deployment (95% confidence)",
      "hotfix (10% confidence)"
    ]
  },
  "decision_record": {
    "decision_id": "dr-aa8d6810e9f3",
    "decision_type": "engineering_decision",
    "reason": "Critical risk \u2014 requires mandatory approvals and enhanced validation",
    "evidence": [
      "Risk score: 70.0",
      "Risk level: critical",
      "Changed files: 2",
      "Affected services: 0",
      "Execution plan: Critical risk \u2014 full pipeline with all safeguards",
      "Deployment strategy: no_deployment"
    ],
    "outcome": "Critical risk \u2014 full pipeline with all safeguards",
    "confidence": 95
  },
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
  },
  "executive_summary": {
    "repository": "org/repo",
    "change_summary": "2 file(s) changed \u2014 Backend, Authentication, Rbac",
    "impact": "2 entities affected across 0 service(s), 0 API(s)",
    "risk_level": "critical",
    "risk_score": 70.0,
    "affected_services": [],
    "required_tests": [
      "unit",
      "integration"
    ],
    "required_approvals": [
      "engineering",
      "security",
      "architecture"
    ],
    "deployment_strategy": "no_deployment",
    "rollback_strategy": "Automatic rollback via no_deployment rollback",
    "estimated_duration": "~45 min (22 stages, 0 skipped)",
    "confidence": 95,
    "recommendations": [
      "Enable enhanced monitoring and alerting for this deployment",
      "Prepare rollback plan before starting deployment"
    ],
    "key_decision": "Critical risk \u2014 full pipeline with all safeguards"
  }
}
```

## Scenario 7: Critical Hotfix (Payment + Secrets)

```json
{
  "report_id": "dr-9764fe5c5b9e",
  "trigger_source": "github",
  "trigger_event": "push",
  "timestamp": "2026-07-12T12:21:10.470167+00:00",
  "repository": "org/repo",
  "branch": "main",
  "commit_sha": "abc123",
  "change_report": {
    "changed_files": [
      "backend/auth/secrets.py",
      "backend/services/payment/processor.py"
    ],
    "changed_folders": [
      "backend/services/payment",
      "backend/auth"
    ],
    "changed_services": [
      "payment"
    ],
    "changed_apis": [],
    "has_db_migrations": false,
    "has_infrastructure_changes": false,
    "has_frontend_changes": false,
    "has_backend_changes": true,
    "has_test_changes": false,
    "has_documentation_changes": false,
    "has_config_changes": false,
    "has_auth_changes": true,
    "has_rbac_changes": false,
    "has_secret_changes": true,
    "has_dependency_changes": false,
    "categories": [
      "backend",
      "authentication",
      "secrets"
    ],
    "summary": "2 file(s) changed across 2 folder(s)",
    "raw_payload": {
      "head_commit": {
        "modified": [
          "backend/services/payment/processor.py",
          "backend/auth/secrets.py"
        ]
      }
    }
  },
  "impact_graph": {
    "affected_modules": [
      "backend",
      "backend"
    ],
    "affected_services": [],
    "affected_apis": [],
    "affected_packages": [],
    "affected_deployments": [
      "security-layer"
    ],
    "affected_k8s_resources": [],
    "affected_pipelines": [],
    "affected_terraform_modules": [],
    "affected_helm_releases": [],
    "affected_dashboards": [],
    "affected_monitoring_rules": [],
    "affected_alert_rules": [],
    "affected_documentation": [],
    "total_affected_entities": 2
  },
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
  },
  "execution_plan": {
    "required_stages": [
      "trigger_pipeline",
      "repository",
      "workspace",
      "sandbox_execution",
      "code_intel_scan",
      "build",
      "qa",
      "security",
      "patch_generation",
      "engineering_review",
      "approval",
      "pr",
      "deployment",
      "gitops_sync",
      "k8s_verification",
      "observability",
      "root_cause_analysis",
      "learning",
      "recommendation",
      "replay_capture",
      "knowledge_graph",
      "complete"
    ],
    "skipped_stages": [],
    "requires_full_pipeline": true,
    "reasoning": "Critical risk \u2014 full pipeline with all safeguards"
  },
  "approval_requirements": {
    "approval_required": true,
    "required_approvers": [
      "engineering",
      "security",
      "architecture"
    ],
    "risk_justification": "Critical risk \u2014 requires engineering, security, and architecture sign-off",
    "expected_impact": "Changes may affect system stability, security, or data integrity"
  },
  "deployment_strategy": {
    "strategy": "no_deployment",
    "reasoning": "No services affected \u2014 skip deployment",
    "confidence": 95,
    "evidence": [
      "no_deployment (95% confidence)",
      "hotfix (10% confidence)"
    ]
  },
  "decision_record": {
    "decision_id": "dr-9764fe5c5b9e",
    "decision_type": "engineering_decision",
    "reason": "Critical risk \u2014 requires mandatory approvals and enhanced validation",
    "evidence": [
      "Risk score: 75.0",
      "Risk level: critical",
      "Changed files: 2",
      "Affected services: 0",
      "Execution plan: Critical risk \u2014 full pipeline with all safeguards",
      "Deployment strategy: no_deployment"
    ],
    "outcome": "Critical risk \u2014 full pipeline with all safeguards",
    "confidence": 95
  },
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
  },
  "executive_summary": {
    "repository": "org/repo",
    "change_summary": "2 file(s) changed \u2014 Backend, Authentication, Secrets",
    "impact": "2 entities affected across 0 service(s), 0 API(s)",
    "risk_level": "critical",
    "risk_score": 75.0,
    "affected_services": [],
    "required_tests": [
      "unit",
      "integration"
    ],
    "required_approvals": [
      "engineering",
      "security",
      "architecture"
    ],
    "deployment_strategy": "no_deployment",
    "rollback_strategy": "Automatic rollback via no_deployment rollback",
    "estimated_duration": "~45 min (22 stages, 0 skipped)",
    "confidence": 95,
    "recommendations": [
      "Enable enhanced monitoring and alerting for this deployment",
      "Prepare rollback plan before starting deployment",
      "Audit secret rotation \u2014 ensure no hardcoded credentials"
    ],
    "key_decision": "Critical risk \u2014 full pipeline with all safeguards"
  }
}
```
