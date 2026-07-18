# Change Intelligence - Phase 1

## Scenario 1: CSS Frontend Change

```json
{
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
  }
}
```

## Scenario 2: Payment Service Change

```json
{
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
  }
}
```

## Scenario 3: Terraform Infrastructure Change

```json
{
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
  }
}
```

## Scenario 4: Helm Chart Change

```json
{
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
  }
}
```

## Scenario 5: Database Migration Change

```json
{
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
  }
}
```

## Scenario 6: RBAC Change

```json
{
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
  }
}
```

## Scenario 7: Critical Hotfix (Payment + Secrets)

```json
{
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
  }
}
```
