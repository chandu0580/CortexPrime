# Executive Decision Report

## Overview

Phase 11 of the Engineering Decision Engine. Generates an executive-facing summary of every engineering decision, suitable for dashboards, notifications, and audit trails.

## Report Template

```
Repository: org/repo
Change Summary: 2 file(s) changed — Backend, Secrets
Impact: 5 entities affected across 2 service(s), 1 API(s)
Risk Level: HIGH
Risk Score: 72/100
Affected Services: [payment-service, auth-service]
Required Tests: [unit, integration]
Required Approvals: [engineering, security]
Deployment Strategy: canary
Rollback Strategy: Automatic rollback via canary rollback
Estimated Duration: ~15 min (22 stages, 0 skipped)
Confidence: 60%
Key Decision: High risk — full pipeline with all safeguards

Recommendations:
- Enable enhanced monitoring and alerting for this deployment
- Prepare rollback plan before starting deployment
- Audit secret rotation — ensure no hardcoded credentials
```

## ExecutiveSummary Structure

```
ExecutiveSummary
├── repository: str
├── change_summary: str
├── impact: str
├── risk_level: str
├── risk_score: float
├── affected_services: List[str]
├── required_tests: List[str]
├── required_approvals: List[str]
├── deployment_strategy: str
├── rollback_strategy: str
├── estimated_duration: str
├── confidence: float
├── recommendations: List[str]
└── key_decision: str
```

## Duration Estimation

| Factor | Time Added |
|--------|-----------|
| Base pipeline | 5 min |
| Database migration | +10 min |
| Infrastructure change | +15 min |
| HIGH/CRITICAL risk | +10 min |
| Human approval | +30 min |

## Recommendation Generation

| Condition | Recommendation |
|-----------|---------------|
| Database migration | Ensure backup, use transactional migration |
| HIGH/CRITICAL risk | Enhanced monitoring, prepare rollback plan |
| Dependency change | Vulnerability scan, license check |
| Secret change | Audit secret rotation |
| Infrastructure change | Terraform plan review, sandbox validation |
| None of above | Standard deployment — no additional recommendations |

## Full DecisionReport

The `DecisionReport` contains all phase outputs serializable via `.to_dict()`:

```python
report = await engineering_decision_engine.analyze(...)
report_dict = report.to_dict()
# Keys: report_id, trigger_source, trigger_event, timestamp,
#        repository, branch, commit_sha,
#        change_report, impact_graph, risk_assessment,
#        execution_plan, approval_requirements,
#        deployment_strategy, decision_record,
#        explanation, executive_summary
```
