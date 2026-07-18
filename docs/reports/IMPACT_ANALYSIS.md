# Impact Analysis - Phase 2

## Scenario 1: CSS Frontend Change

```json
{
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
  }
}
```

## Scenario 2: Payment Service Change

```json
{
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
  }
}
```

## Scenario 3: Terraform Infrastructure Change

```json
{
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
  }
}
```

## Scenario 4: Helm Chart Change

```json
{
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
  }
}
```

## Scenario 5: Database Migration Change

```json
{
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
  }
}
```

## Scenario 6: RBAC Change

```json
{
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
  }
}
```

## Scenario 7: Critical Hotfix (Payment + Secrets)

```json
{
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
  }
}
```
